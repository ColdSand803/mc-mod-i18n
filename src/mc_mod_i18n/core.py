from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from .detector import detect_mod
from .hardcoded import _NESTED_JAR_PREFIXES
from .lang import collect_lang_documents, extract_plain_text, target_path_for
from .pack import OutputLangDocument
from .report import ReportEntry
from .translator import (
    CopyTranslator,
    GlossaryTranslator,
    OpenAICompatibleTranslator,
    TranslationItem,
    get_provider_preset,
    is_ai_provider,
    load_glossary,
)
from .validator import pre_check_lang_documents, validate_document_completeness, validate_translation


def compute_source_hash(source_docs: list) -> str:
    payload = [
        {
            "path": doc.path,
            "mod_id": doc.mod_id,
            "locale": doc.locale,
            "format": doc.format,
            "entries": doc.entries,
        }
        for doc in source_docs
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def combine_source_hashes(root_hash: str, nested_hashes: list[str]) -> str:
    if not nested_hashes:
        return root_hash
    return hashlib.sha256(
        json.dumps(
            {
                "root": root_hash,
                "nested": sorted(nested_hashes),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def compute_zip_source_hash(zf: ZipFile, source_locale: str) -> str:
    nested_hashes: list[str] = []
    for nested_name in sorted(zf.namelist()):
        if not any(nested_name.startswith(prefix) for prefix in _NESTED_JAR_PREFIXES) or not nested_name.endswith(".jar"):
            continue
        try:
            with ZipFile(BytesIO(zf.read(nested_name))) as nested_zf:
                nested_hashes.append(compute_zip_source_hash(nested_zf, source_locale))
        except BadZipFile:
            continue
    return combine_source_hashes(
        compute_source_hash(collect_lang_documents(zf, source_locale)),
        nested_hashes,
    )


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


def process_jar(jar_path: Path, args: argparse.Namespace, translator) -> tuple[list[OutputLangDocument], list[ReportEntry], str]:
    with ZipFile(jar_path) as zf:
        return process_zip(zf, jar_path.name, args, translator)


def process_zip(
    zf: ZipFile,
    jar_label: str,
    args: argparse.Namespace,
    translator,
) -> tuple[list[OutputLangDocument], list[ReportEntry], str]:
    documents: list[OutputLangDocument] = []
    report: list[ReportEntry] = []

    if getattr(args, "skip_translated", False):
        json_target_docs = [doc for doc in collect_lang_documents(zf, args.target_locale) if doc.format == "json"]
        if json_target_docs:
            source_hash = compute_zip_source_hash(zf, args.source_locale)
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
            return documents, report, source_hash

    nested_jars = [
        name for name in sorted(zf.namelist())
        if any(name.startswith(p) for p in _NESTED_JAR_PREFIXES) and name.endswith(".jar")
    ]
    nested_source_hashes: list[str] = []
    for nested_name in nested_jars:
        try:
            with ZipFile(BytesIO(zf.read(nested_name))) as nested_zf:
                nested_docs, nested_report, nested_hash = process_zip(nested_zf, f"{jar_label}::{nested_name}", args, translator)
                documents.extend(nested_docs)
                report.extend(nested_report)
                if nested_hash:
                    nested_source_hashes.append(nested_hash)
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
    source_hash = combine_source_hashes(compute_source_hash(source_docs), nested_source_hashes)
    target_docs = {
        doc.path: doc
        for doc in collect_lang_documents(zf, args.target_locale)
    }

    precheck_warnings = pre_check_lang_documents(source_docs)
    for w in precheck_warnings:
        print(f"[pre-check] {w.severity}: [{w.category}] {w.file}:{w.key} — {w.message}", file=sys.stderr)

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
        return documents, report, source_hash

    for source_doc in source_docs:
        target_path = target_path_for(source_doc.path, args.source_locale, args.target_locale)
        existing_entries = target_docs.get(target_path).entries if target_path in target_docs else {}
        output_entries = dict(existing_entries)
        items: list[TranslationItem] = []
        item_sources: dict[str, tuple[str, str, object]] = {}

        for key, raw_value in source_doc.entries.items():
            source_text = extract_plain_text(raw_value)
            if key in existing_entries and not args.overwrite_existing:
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=extract_plain_text(existing_entries[key]),
                        status="existing",
                        message="kept existing target translation",
                    )
                )
                continue

            item_id = f"{jar_label}{source_doc.path}{key}"
            item_sources[item_id] = (key, source_text, raw_value)
            items.append(TranslationItem(id=item_id, key=key, text=source_text, mod_id=source_doc.mod_id))

        translations = translator.translate_batch(items) if items else {}
        failed_items = getattr(translator, "failed_items", {})

        for item_id, (key, source_text, raw_value) in item_sources.items():
            if item_id in failed_items:
                output_entries[key] = raw_value
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=source_text,
                        status="api_failed",
                        message=str(failed_items[item_id]),
                    )
                )
                continue
            translated = translations.get(item_id, source_text)
            errors = validate_translation(source_text, translated)
            if errors:
                output_entries[key] = raw_value
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key=key,
                        source=source_text,
                        target=source_text,
                        status="failed",
                        message="; ".join(errors),
                    )
                )
                continue

            if isinstance(raw_value, dict):
                translated_dict: dict[str, object] = dict(raw_value)
                translated_dict["text"] = translated
                output_entries[key] = translated_dict
            else:
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
            doc_errors = validate_document_completeness(source_doc.entries, output_entries)
            for de in doc_errors:
                report.append(
                    ReportEntry(
                        jar=jar_label,
                        mod_id=source_doc.mod_id,
                        file=target_path,
                        key="",
                        source="",
                        target="",
                        status="incomplete",
                        message=de,
                    )
                )
            documents.append(OutputLangDocument(path=target_path, format=source_doc.format, entries=output_entries))

    return documents, report, source_hash
