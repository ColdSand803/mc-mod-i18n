from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from zipfile import BadZipFile, ZipFile

from .core import compute_translation_config_hash, compute_zip_source_hash, create_translator, process_jar, report_has_uncacheable_failures
from .ftbquests import (
    compute_ftbquests_config_hash,
    compute_ftbquests_source_hash,
    ftbquests_cache_key,
    load_ftbquests_checkpoint,
    load_ftbquests_checkpoint_config_hash,
    load_ftbquests_checkpoint_source_hash,
    load_ftbquests_source,
    process_ftbquests_source,
    save_ftbquests_checkpoint,
    write_ftbquests_html_report,
    write_ftbquests_json_report,
    write_ftbquests_outputs,
)
from .hardcoded import _NESTED_JAR_PREFIXES, scan_jar_for_hardcoded
from .lang import collect_lang_documents, target_path_for
from .pack import (
    OutputLangDocument,
    completed_jar_stems,
    load_checkpoint,
    load_checkpoint_config_hash,
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
from .validator import pre_check_lang_documents
from .web import read_co1dsand_pack_icon


@dataclass
class DryRunStats:
    processed_jars: int = 0
    nested_jars: int = 0
    source_language_files: int = 0
    target_language_files: int = 0
    entries_to_translate: int = 0
    existing_entries: int = 0
    precheck_warnings: int = 0
    precheck_errors: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "translate":
        return translate_command(args)
    if args.command == "ftbquests":
        return ftbquests_command(args)
    if args.command == "serve":
        from .web import serve

        serve(host=args.host, port=args.port, workdir=Path(args.workdir))
        return 0
    if args.command == "desktop":
        from .desktop import run_desktop

        return run_desktop(
            host=args.host,
            port=args.port,
            workdir=Path(args.workdir) if args.workdir else None,
            width=args.width,
            height=args.height,
            zoom=args.zoom,
        )

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
    translate.add_argument("--ignore-cache", action="store_true", help="ignore existing checkpoints/cache and translate again")
    translate.add_argument("--dry-run", action="store_true", help="scan inputs and print work estimates without translating")
    translate.add_argument("--pack-format", default="15")
    translate.add_argument("--api-url", "--api-base-url", dest="api_url", default="https://api.openai.com/v1", help="API BaseURL; full provider endpoint is also accepted")
    translate.add_argument("--api-key-env", default="OPENAI_API_KEY")
    translate.add_argument("--api-key", default="", help="API key value; if omitted, --api-key-env is used")
    translate.add_argument("--api-region", default="", help="provider region, used by Azure Translator and similar services")
    translate.add_argument("--api-debug-log", default="", help="write API request/response JSONL log")
    translate.add_argument("--api-concurrency", type=int, default=1, help="parallel API work budget shared across JARs and batches")
    translate.add_argument("--api-retries", type=int, default=5, help="retry count for retryable API failures")
    translate.add_argument("--api-batch-size", type=int, default=40, help="translation entries per API request")
    translate.add_argument("--api-timeout", type=float, default=10.0, help="API request timeout seconds")
    translate.add_argument("--model", default="gpt-4o-mini")
    translate.add_argument("--scan-hardcoded", action="store_true", help="scan class constant pools and write hardcoded reports")
    translate.add_argument("--hardcoded-limit", type=int, default=5000, help="maximum hardcoded candidates to report")
    translate.add_argument("--brand-logo", choices=["cat", "grass", "sign"], default="", help="resource pack icon brand; defaults to logo/branding.json")

    ftbquests = subparsers.add_parser("ftbquests", help="translate FTB Quests lang SNBT files")
    ftbquests.add_argument("input", help="FTB Quests folder, modpack ZIP, or lang/<locale>.snbt")
    ftbquests.add_argument("--out", default="dist", help="output directory")
    ftbquests.add_argument("--source-locale", default="en_us")
    ftbquests.add_argument("--target-locale", default="zh_cn")
    ftbquests.add_argument("--provider", choices=["copy", "glossary", *AI_PROVIDER_PRESETS.keys()], default="glossary")
    ftbquests.add_argument("--glossary", help="path to glossary JSON object")
    ftbquests.add_argument("--overwrite-existing", action="store_true", help="overwrite existing target locale entries")
    ftbquests.add_argument("--ignore-cache", action="store_true", help="ignore existing FTB Quests checkpoints/cache")
    ftbquests.add_argument("--cache-dir", default="", help="shared cache directory; defaults to <out>/.ftbquests-cache")
    ftbquests.add_argument("--output-mode", choices=["directory", "patch", "both"], default="both")
    ftbquests.add_argument("--api-url", "--api-base-url", dest="api_url", default="https://api.openai.com/v1", help="API BaseURL; full provider endpoint is also accepted")
    ftbquests.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ftbquests.add_argument("--api-key", default="", help="API key value; if omitted, --api-key-env is used")
    ftbquests.add_argument("--api-region", default="", help="provider region, used by Azure Translator and similar services")
    ftbquests.add_argument("--api-debug-log", default="", help="write API request/response JSONL log")
    ftbquests.add_argument("--api-concurrency", type=int, default=1, help="parallel API work budget")
    ftbquests.add_argument("--api-retries", type=int, default=5, help="retry count for retryable API failures")
    ftbquests.add_argument("--api-batch-size", type=int, default=40, help="translation entries per API request")
    ftbquests.add_argument("--api-timeout", type=float, default=10.0, help="API request timeout seconds")
    ftbquests.add_argument("--model", default="gpt-4o-mini")

    serve = subparsers.add_parser("serve", help="start the local web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--workdir", default=".ui_runs", help="directory for uploaded files and generated outputs")

    desktop = subparsers.add_parser("desktop", help="start the single-window desktop UI")
    desktop.add_argument("--host", default="127.0.0.1")
    desktop.add_argument("--port", type=int, default=0, help="local port; 0 chooses an available port")
    desktop.add_argument("--workdir", default="", help="desktop app data directory; defaults to the user app data folder")
    desktop.add_argument("--width", type=int, default=1280)
    desktop.add_argument("--height", type=int, default=860)
    desktop.add_argument("--zoom", type=float, default=0, help="desktop page zoom; 0 auto-counteracts Windows DPI scaling")
    return parser


def ftbquests_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        source = load_ftbquests_source(input_path, args.source_locale)
    except (OSError, ValueError) as exc:
        print(f"FTB Quests input failed: {exc}", file=sys.stderr)
        return 2

    config_hash = compute_ftbquests_config_hash(args)
    cache_root = Path(args.cache_dir) if args.cache_dir else out_dir / ".ftbquests-cache"
    cache_scope = cache_root / config_hash[:16]
    cache_scope.mkdir(parents=True, exist_ok=True)
    cache_key = ftbquests_cache_key(input_path)
    source_hash = compute_ftbquests_source_hash(source)
    result = None
    if not getattr(args, "ignore_cache", False):
        cached_hash = load_ftbquests_checkpoint_source_hash(cache_scope, cache_key)
        cached_config_hash = load_ftbquests_checkpoint_config_hash(cache_scope, cache_key)
        if cached_hash == source_hash and cached_config_hash == config_hash:
            result = load_ftbquests_checkpoint(cache_scope, cache_key)
            if result is not None:
                print(f"[cache] loaded FTB Quests checkpoint: {input_path}", file=sys.stderr)

    if result is None:
        translator = create_translator(args)
        result = process_ftbquests_source(source, args, translator)
        save_ftbquests_checkpoint(cache_scope, cache_key, result, config_hash=config_hash)

    directory_path, patch_path = write_ftbquests_outputs(out_dir, result, args.output_mode)
    html_report = out_dir / "ftbquests-report.html"
    json_report = out_dir / "ftbquests-report.json"
    write_ftbquests_html_report(html_report, result)
    write_ftbquests_json_report(json_report, result)

    summary: dict[str, int] = {}
    for entry in result.report_entries:
        summary[entry.status] = summary.get(entry.status, 0) + 1
    print(f"Mode: {result.mode}")
    print(f"Texts translated: {summary.get('translated', 0)}")
    print(f"Existing entries kept: {summary.get('existing', 0)}")
    print(f"Output files: {len(result.output_files)}")
    if directory_path:
        print(f"FTB Quests directory: {directory_path}")
    if patch_path:
        print(f"FTB Quests patch ZIP: {patch_path}")
    print(f"Report: {html_report}")
    print(f"JSON report: {json_report}")
    return 0


def translate_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    out_dir = Path(args.out)
    jars = discover_jars(input_path)
    if not jars:
        print(f"No JAR files found: {input_path}", file=sys.stderr)
        return 2
    input_jars = list(jars)

    pack_format = resolve_pack_format(args.pack_format)
    config_hash = compute_translation_config_hash(args)
    if getattr(args, "dry_run", False):
        return dry_run_command(args, input_jars)

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
    if getattr(args, "resume", False) and not getattr(args, "ignore_cache", False):
        completed = completed_jar_stems(out_dir)
        remaining_jars: list[Path] = []
        for jp in jars:
            if sanitize_pack_name(jp.stem) in completed:
                checkpoint_hash = load_checkpoint_source_hash(out_dir, jp.stem)
                checkpoint_config_hash = load_checkpoint_config_hash(out_dir, jp.stem)
                current_hash = ""
                try:
                    with ZipFile(jp) as zf:
                        current_hash = compute_zip_source_hash(zf, args.source_locale)
                except (BadZipFile, OSError, ValueError):
                    current_hash = ""
                result = load_checkpoint(out_dir, jp.stem)
                if (
                    result is not None
                    and checkpoint_hash
                    and checkpoint_hash == current_hash
                    and checkpoint_config_hash
                    and checkpoint_config_hash == config_hash
                ):
                    loaded_docs, loaded_reports = result
                    if report_has_uncacheable_failures(loaded_reports):
                        remaining_jars.append(jp)
                        continue
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
        save_checkpoint(out_dir, jar_path.stem, docs, report, source_hash=source_hash, config_hash=config_hash)
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
            read_co1dsand_pack_icon(brand_logo=args.brand_logo or None),
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


def dry_run_command(args: argparse.Namespace, jars: list[Path]) -> int:
    stats = DryRunStats(processed_jars=len(jars))
    for jar_path in jars:
        try:
            with ZipFile(jar_path) as zf:
                collect_dry_run_stats(zf, args, stats)
        except (BadZipFile, OSError, ValueError) as exc:
            print(f"[dry-run] jar_failed: {jar_path.name}: {exc}", file=sys.stderr)

    batch_size = max(1, int(getattr(args, "api_batch_size", 40) or 40))
    api_batches = math.ceil(stats.entries_to_translate / batch_size) if is_ai_provider(args.provider) else 0
    print("Dry run: yes")
    print(f"Processed JARs: {stats.processed_jars}")
    print(f"Nested JARs: {stats.nested_jars}")
    print(f"Source language files: {stats.source_language_files}")
    print(f"Target language files: {stats.target_language_files}")
    print(f"Entries to translate: {stats.entries_to_translate}")
    print(f"Existing entries kept: {stats.existing_entries}")
    print(f"Pre-check warnings: {stats.precheck_warnings}")
    print(f"Pre-check errors: {stats.precheck_errors}")
    print(f"Estimated API batches: {api_batches}")
    print("Outputs written: no")
    return 0


def collect_dry_run_stats(zf: ZipFile, args: argparse.Namespace, stats: DryRunStats) -> None:
    nested_jars = [
        name for name in sorted(zf.namelist())
        if any(name.startswith(prefix) for prefix in _NESTED_JAR_PREFIXES) and name.endswith(".jar")
    ]
    for nested_name in nested_jars:
        try:
            with ZipFile(BytesIO(zf.read(nested_name))) as nested_zf:
                stats.nested_jars += 1
                collect_dry_run_stats(nested_zf, args, stats)
        except BadZipFile:
            continue

    source_docs = collect_lang_documents(zf, args.source_locale)
    target_docs_list = collect_lang_documents(zf, args.target_locale)
    target_docs = {doc.path: doc for doc in target_docs_list}
    stats.source_language_files += len(source_docs)
    stats.target_language_files += len(target_docs_list)

    if source_docs:
        warnings = pre_check_lang_documents(source_docs)
        stats.precheck_warnings += sum(1 for warning in warnings if warning.severity != "error")
        stats.precheck_errors += sum(1 for warning in warnings if warning.severity == "error")

    if getattr(args, "skip_translated", False) and any(doc.format == "json" for doc in target_docs_list):
        return

    for source_doc in source_docs:
        target_path = target_path_for(source_doc.path, args.source_locale, args.target_locale)
        existing_entries = target_docs.get(target_path).entries if target_path in target_docs else {}
        for key in source_doc.entries:
            if key in existing_entries and not args.overwrite_existing:
                stats.existing_entries += 1
            else:
                stats.entries_to_translate += 1


def discover_jars(input_path: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".jar":
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.rglob("*.jar") if path.is_file())
    return []
