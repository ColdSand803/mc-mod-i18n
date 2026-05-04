from __future__ import annotations

import argparse
from pathlib import Path
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from zipfile import BadZipFile, ZipFile

from .core import compute_zip_source_hash, create_translator, process_jar
from .hardcoded import scan_jar_for_hardcoded
from .pack import (
    OutputLangDocument,
    completed_jar_stems,
    load_checkpoint,
    load_checkpoint_source_hash,
    read_pack_icon,
    resolve_pack_format,
    resource_pack_filename,
    sanitize_pack_name,
    save_checkpoint,
    write_resource_pack,
)
from .report import ReportEntry, write_hardcoded_map_template, write_hardcoded_report, write_report
from .translator import AI_PROVIDER_PRESETS, is_ai_provider


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "translate":
        return translate_command(args)
    if args.command == "serve":
        from .web import serve

        serve(host=args.host, port=args.port, workdir=Path(args.workdir))
        return 0

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mc-mod-i18n")
    subparsers = parser.add_subparsers(dest="command")

    translate = subparsers.add_parser("translate", help="translate mod JAR language files into a resource pack")
    translate.add_argument("input", help="a mod JAR file or a folder containing JAR files")
    translate.add_argument("--out", default="dist", help="output directory")
    translate.add_argument("--source-locale", default="en_us")
    translate.add_argument("--target-locale", default="zh_cn")
    translate.add_argument("--provider", choices=["copy", "glossary", *AI_PROVIDER_PRESETS.keys()], default="glossary")
    translate.add_argument("--glossary", help="path to glossary JSON object")
    translate.add_argument("--overwrite-existing", action="store_true", help="overwrite existing target locale entries")
    translate.add_argument("--skip-translated", action="store_true", help="skip JARs that already contain target locale files")
    translate.add_argument("--resume", action="store_true", help="resume from checkpoints, skipping completed JARs")
    translate.add_argument("--pack-format", default="15")
    translate.add_argument("--api-url", default="https://api.openai.com/v1/chat/completions")
    translate.add_argument("--api-key-env", default="OPENAI_API_KEY")
    translate.add_argument("--api-key", default="", help="API key value; if omitted, --api-key-env is used")
    translate.add_argument("--api-debug-log", default="", help="write OpenAI-compatible request/response JSONL log")
    translate.add_argument("--api-concurrency", type=int, default=1, help="parallel API work budget shared across JARs and batches")
    translate.add_argument("--api-retries", type=int, default=5, help="retry count for retryable API failures")
    translate.add_argument("--api-batch-size", type=int, default=40, help="translation entries per API request")
    translate.add_argument("--api-timeout", type=float, default=10.0, help="API request timeout seconds")
    translate.add_argument("--model", default="gpt-4o-mini")
    translate.add_argument("--scan-hardcoded", action="store_true", help="scan class constant pools and write hardcoded reports")
    translate.add_argument("--hardcoded-limit", type=int, default=5000, help="maximum hardcoded candidates to report")

    serve = subparsers.add_parser("serve", help="start the local web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--workdir", default=".ui_runs", help="directory for uploaded files and generated outputs")
    return parser


def translate_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    out_dir = Path(args.out)
    jars = discover_jars(input_path)
    if not jars:
        print(f"No JAR files found: {input_path}", file=sys.stderr)
        return 2
    input_jars = list(jars)

    pack_format = resolve_pack_format(args.pack_format)
    translator = create_translator(args)
    task_id = uuid.uuid4().hex[:12]
    if hasattr(translator, "task_id"):
        translator.task_id = task_id
    if args.api_debug_log and hasattr(translator, "debug_log_path"):
        log_path = Path(args.api_debug_log)
        task_log_name = f"{log_path.stem}.{task_id}{log_path.suffix}"
        translator.debug_log_path = str(log_path.parent / task_log_name)

    output_documents: list[OutputLangDocument] = []
    report_entries: list[ReportEntry] = []
    hardcoded_entries = []

    # Resume from checkpoints
    if getattr(args, "resume", False):
        completed = completed_jar_stems(out_dir)
        remaining_jars: list[Path] = []
        for jp in jars:
            if sanitize_pack_name(jp.stem) in completed:
                checkpoint_hash = load_checkpoint_source_hash(out_dir, jp.stem)
                current_hash = ""
                try:
                    with ZipFile(jp) as zf:
                        current_hash = compute_zip_source_hash(zf, args.source_locale)
                except (BadZipFile, OSError, ValueError):
                    current_hash = ""
                result = load_checkpoint(out_dir, jp.stem)
                if result is not None and checkpoint_hash and checkpoint_hash == current_hash:
                    loaded_docs, loaded_reports = result
                    output_documents.extend(loaded_docs)
                    report_entries.extend(loaded_reports)
                    print(f"[resume] loaded checkpoint: {jp.name}", file=sys.stderr)
                    continue
            remaining_jars.append(jp)
        jars = remaining_jars

    def process_single(jar_path: Path) -> tuple[list[OutputLangDocument], list[ReportEntry], list]:
        docs: list[OutputLangDocument] = []
        report: list[ReportEntry] = []
        hardcoded: list = []
        source_hash = ""
        try:
            jar_documents, jar_report, source_hash = process_jar(jar_path, args, translator)
            docs.extend(jar_documents)
            report.extend(jar_report)
            if args.scan_hardcoded:
                hardcoded.extend(scan_jar_for_hardcoded(str(jar_path), max_entries=args.hardcoded_limit))
        except (BadZipFile, RuntimeError, ValueError) as exc:
            report.append(
                ReportEntry(
                    jar=jar_path.name,
                    mod_id="unknown",
                    file="",
                    key="",
                    source="",
                    target="",
                    status="jar_failed",
                    message=str(exc),
                )
            )
        save_checkpoint(out_dir, jar_path.stem, docs, report, source_hash=source_hash)
        return docs, report, hardcoded

    if len(jars) <= 1:
        for jar_path in jars:
            jar_documents, jar_report, jar_hardcoded = process_single(jar_path)
            output_documents.extend(jar_documents)
            report_entries.extend(jar_report)
            hardcoded_entries.extend(jar_hardcoded)
    else:
        worker_count = max(1, getattr(args, "api_concurrency", 1)) if is_ai_provider(args.provider) else len(jars)
        with ThreadPoolExecutor(max_workers=min(worker_count, len(jars))) as executor:
            futures = {executor.submit(process_single, jar_path): jar_path for jar_path in jars}
            for future in as_completed(futures):
                jar_documents, jar_report, jar_hardcoded = future.result()
                output_documents.extend(jar_documents)
                report_entries.extend(jar_report)
                hardcoded_entries.extend(jar_hardcoded)

    pack_path = out_dir / resource_pack_filename(input_jars)
    report_path = out_dir / "report.html"
    hardcoded_report_path = out_dir / "hardcoded-report.html"
    hardcoded_map_path = out_dir / "hardcoded-map.template.json"
    if output_documents:
        write_resource_pack(
            pack_path,
            output_documents,
            pack_format,
            "§b汉化工具§r§6By co1dsand",
            read_pack_icon(Path.cwd() / "co1dsand_logo.png"),
        )
    write_report(report_path, report_entries)
    if args.scan_hardcoded:
        write_hardcoded_report(hardcoded_report_path, hardcoded_entries)
        write_hardcoded_map_template(hardcoded_map_path, hardcoded_entries)

    print(f"Processed JARs: {len(input_jars)}")
    print(f"Language files generated: {len(output_documents)}")
    if output_documents:
        print(f"Resource pack: {pack_path}")
    print(f"Report: {report_path}")
    if args.scan_hardcoded:
        print(f"Hardcoded report: {hardcoded_report_path}")
        print(f"Hardcoded map template: {hardcoded_map_path}")
    return 0


def discover_jars(input_path: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".jar":
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.rglob("*.jar") if path.is_file())
    return []
