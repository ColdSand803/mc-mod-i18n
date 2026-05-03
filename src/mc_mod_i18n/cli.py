from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from zipfile import BadZipFile, ZipFile

from .detector import detect_mod
from .hardcoded import scan_jar_for_hardcoded
from .lang import collect_lang_documents, target_path_for
from .pack import OutputLangDocument, read_pack_icon, resource_pack_filename, write_resource_pack
from .report import ReportEntry, write_hardcoded_map_template, write_hardcoded_report, write_report
from .translator import (
    AI_PROVIDER_PRESETS,
    CopyTranslator,
    GlossaryTranslator,
    OpenAICompatibleTranslator,
    TranslationItem,
    get_provider_preset,
    is_ai_provider,
    load_glossary,
)
from .validator import validate_translation


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
    translate.add_argument("--pack-format", type=int, default=15)
    translate.add_argument("--api-url", default="https://api.openai.com/v1/chat/completions")
    translate.add_argument("--api-key-env", default="OPENAI_API_KEY")
    translate.add_argument("--api-key", default="", help="API key value; if omitted, --api-key-env is used")
    translate.add_argument("--api-debug-log", default="", help="write OpenAI-compatible request/response JSONL log")
    translate.add_argument("--api-concurrency", type=int, default=1, help="parallel API batches for OpenAI-compatible providers")
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

    translator = create_translator(args)
    output_documents: list[OutputLangDocument] = []
    report_entries: list[ReportEntry] = []
    hardcoded_entries = []

    def process_single(jar_path: Path) -> tuple[list[OutputLangDocument], list[ReportEntry], list]:
        docs: list[OutputLangDocument] = []
        report: list[ReportEntry] = []
        hardcoded: list = []
        try:
            jar_documents, jar_report = process_jar(jar_path, args, translator)
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
        return docs, report, hardcoded

    if len(jars) <= 1:
        for jar_path in jars:
            jar_documents, jar_report, jar_hardcoded = process_single(jar_path)
            output_documents.extend(jar_documents)
            report_entries.extend(jar_report)
            hardcoded_entries.extend(jar_hardcoded)
    else:
        worker_count = 1 if is_ai_provider(args.provider) else len(jars)
        with ThreadPoolExecutor(max_workers=min(worker_count, len(jars))) as executor:
            futures = {executor.submit(process_single, jar_path): jar_path for jar_path in jars}
            for future in as_completed(futures):
                jar_documents, jar_report, jar_hardcoded = future.result()
                output_documents.extend(jar_documents)
                report_entries.extend(jar_report)
                hardcoded_entries.extend(jar_hardcoded)

    pack_path = out_dir / resource_pack_filename(jars)
    report_path = out_dir / "report.html"
    hardcoded_report_path = out_dir / "hardcoded-report.html"
    hardcoded_map_path = out_dir / "hardcoded-map.template.json"
    if output_documents:
        write_resource_pack(
            pack_path,
            output_documents,
            args.pack_format,
            "§b汉化工具§r§6By co1dsand",
            read_pack_icon(Path.cwd() / "co1dsand_logo.png"),
        )
    write_report(report_path, report_entries)
    if args.scan_hardcoded:
        write_hardcoded_report(hardcoded_report_path, hardcoded_entries)
        write_hardcoded_map_template(hardcoded_map_path, hardcoded_entries)

    print(f"Processed JARs: {len(jars)}")
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


def create_translator(args: argparse.Namespace):
    if args.provider == "copy":
        return CopyTranslator()
    if args.provider == "glossary":
        return GlossaryTranslator(load_glossary(args.glossary))
    if not is_ai_provider(args.provider):
        raise ValueError(f"unknown provider: {args.provider}")
    preset = get_provider_preset(args.provider)
    default_preset = get_provider_preset("openai-compatible")
    api_url = args.api_url or preset.api_url
    api_key_env = args.api_key_env or preset.api_key_env
    model = args.model or preset.model
    if args.provider != "openai-compatible":
        if args.api_url == default_preset.api_url:
            api_url = preset.api_url
        if args.api_key_env == default_preset.api_key_env:
            api_key_env = preset.api_key_env
        if args.model == default_preset.model:
            model = preset.model
    return OpenAICompatibleTranslator(
        api_url=api_url,
        api_key_env=api_key_env,
        api_key=getattr(args, "api_key", ""),
        model=model,
        provider_label=preset.label,
        debug_log_path=getattr(args, "api_debug_log", ""),
        concurrency=getattr(args, "api_concurrency", 1),
        max_retries=getattr(args, "api_retries", 5),
        batch_size=max(1, getattr(args, "api_batch_size", 40)),
        request_timeout=max(1.0, getattr(args, "api_timeout", 10.0)),
        progress_callback=getattr(args, "progress_callback", None),
    )


def process_jar(jar_path: Path, args: argparse.Namespace, translator) -> tuple[list[OutputLangDocument], list[ReportEntry]]:
    with ZipFile(jar_path) as zf:
        return process_zip(zf, jar_path.name, args, translator)


def process_zip(
    zf: ZipFile,
    jar_label: str,
    args: argparse.Namespace,
    translator,
) -> tuple[list[OutputLangDocument], list[ReportEntry]]:
    documents: list[OutputLangDocument] = []
    report: list[ReportEntry] = []

    if getattr(args, "skip_translated", False):
        json_target_docs = [doc for doc in collect_lang_documents(zf, args.target_locale) if doc.format == "json"]
        if json_target_docs:
            metadata = detect_mod(zf, jar_label)
            report.append(
                ReportEntry(
                    jar=jar_label,
                    mod_id=metadata.mod_id,
                    file="",
                    key="",
                    source="",
                    target="",
                    status="skipped",
                    message=f"already contains {args.target_locale} translations",
                )
            )
            return documents, report

    nested_jars = [name for name in sorted(zf.namelist()) if name.startswith("META-INF/jarjar/") and name.endswith(".jar")]
    for nested_name in nested_jars:
        try:
            with ZipFile(BytesIO(zf.read(nested_name))) as nested_zf:
                nested_docs, nested_report = process_zip(nested_zf, f"{jar_label}::{nested_name}", args, translator)
                documents.extend(nested_docs)
                report.extend(nested_report)
        except BadZipFile as exc:
            report.append(
                ReportEntry(
                    jar=jar_label,
                    mod_id="unknown",
                    file=nested_name,
                    key="",
                    source="",
                    target="",
                    status="jar_failed",
                    message=f"invalid nested jar: {exc}",
                )
            )

    metadata = detect_mod(zf, jar_label)
    source_docs = collect_lang_documents(zf, args.source_locale)
    target_docs = {
        doc.path: doc
        for doc in collect_lang_documents(zf, args.target_locale)
    }

    if not source_docs:
        if not nested_jars:
            report.append(
                ReportEntry(
                    jar=jar_label,
                    mod_id=metadata.mod_id,
                    file="",
                    key="",
                    source="",
                    target="",
                    status="skipped",
                    message=f"no {args.source_locale} language files found",
                )
            )
        return documents, report

    for source_doc in source_docs:
        target_path = target_path_for(source_doc.path, args.source_locale, args.target_locale)
        existing_entries = target_docs.get(target_path).entries if target_path in target_docs else {}
        output_entries = dict(existing_entries)
        items: list[TranslationItem] = []
        item_sources: dict[str, tuple[str, str]] = {}

        for key, source_text in source_doc.entries.items():
            if key in existing_entries and not args.overwrite_existing:
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=existing_entries[key],
                        status="existing",
                        message="kept existing target translation",
                    )
                )
                continue

            item_id = f"{jar_label}\u0000{source_doc.path}\u0000{key}"
            item_sources[item_id] = (key, source_text)
            items.append(TranslationItem(id=item_id, key=key, text=source_text, mod_id=source_doc.mod_id))

        translations = translator.translate_batch(items) if items else {}
        failed_items = getattr(translator, "failed_items", {})

        for item_id, (key, source_text) in item_sources.items():
            if item_id in failed_items:
                fallback = existing_entries.get(key, source_text)
                output_entries[key] = fallback
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=fallback,
                        status="api_failed",
                        message=str(failed_items[item_id]),
                    )
                )
                continue
            translated = translations.get(item_id, source_text)
            errors = validate_translation(source_text, translated)
            if errors:
                fallback = existing_entries.get(key, source_text)
                output_entries[key] = fallback
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=fallback,
                        status="failed",
                        message="; ".join(errors),
                    )
                )
                continue

            output_entries[key] = translated
            report.append(
                ReportEntry(
                    jar=jar_label,
                    mod_id=source_doc.mod_id,
                    file=target_path,
                    key=key,
                    source=source_text,
                    target=translated,
                    status="translated",
                    message="",
                )
            )

        if output_entries:
            documents.append(OutputLangDocument(path=target_path, format=source_doc.format, entries=output_entries))

    return documents, report
