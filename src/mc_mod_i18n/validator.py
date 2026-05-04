from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .lang import extract_plain_text, LangDocument

PRINTF_RE = re.compile(r"%(?!%)(?:\d+\$)?[+#\-0,( ]*(?:\d+)?(?:\.\d+)?[bcdeEfgGaAosxXhHsd]")
BRACE_RE = re.compile(r"\{[A-Za-z0-9_.:-]+\}")
COLOR_RE = re.compile(r"§[0-9A-FK-ORa-fk-or]")


def validate_translation(source: str, target: str) -> list[str]:
    errors: list[str] = []
    if not target.strip():
        errors.append("translation is empty")

    for label, regex in (
        ("printf placeholder", PRINTF_RE),
        ("brace placeholder", BRACE_RE),
        ("minecraft format code", COLOR_RE),
    ):
        missing = _missing_tokens(regex.findall(source), regex.findall(target))
        if missing:
            errors.append(f"missing {label}: {', '.join(missing)}")

    source_nl = source.count("\n")
    target_nl = target.count("\n")
    if source_nl != target_nl:
        errors.append(f"newline count mismatch: source={source_nl}, target={target_nl}")

    for label, regex in (
        ("printf placeholder", PRINTF_RE),
        ("brace placeholder", BRACE_RE),
    ):
        extra = _extra_tokens(regex.findall(source), regex.findall(target))
        if extra:
            errors.append(f"extra {label}: {', '.join(extra)}")

    if source and target:
        source_lead = len(source) - len(source.lstrip())
        source_trail = len(source) - len(source.rstrip())
        target_lead = len(target) - len(target.lstrip())
        target_trail = len(target) - len(target.rstrip())
        if source_lead != target_lead:
            errors.append(f"leading whitespace mismatch: source={source_lead}, target={target_lead}")
        if source_trail != target_trail:
            errors.append(f"trailing whitespace mismatch: source={source_trail}, target={target_trail}")

    return errors


def _missing_tokens(source_tokens: list[str], target_tokens: list[str]) -> list[str]:
    source_counter = Counter(source_tokens)
    target_counter = Counter(target_tokens)
    missing: list[str] = []
    for token, count in source_counter.items():
        delta = count - target_counter[token]
        if delta > 0:
            missing.extend([token] * delta)
    return missing


def _extra_tokens(source_tokens: list[str], target_tokens: list[str]) -> list[str]:
    source_counter = Counter(source_tokens)
    target_counter = Counter(target_tokens)
    extra: list[str] = []
    for token, count in target_counter.items():
        delta = count - source_counter.get(token, 0)
        if delta > 0:
            extra.extend([token] * delta)
    return extra


def validate_document_completeness(
    source_entries: dict[str, str | dict[str, object]],
    target_entries: dict[str, str | dict[str, object]],
) -> list[str]:
    errors: list[str] = []
    missing_keys = set(source_entries.keys()) - set(target_entries.keys())
    if missing_keys:
        count = len(missing_keys)
        sample = sorted(missing_keys)[:5]
        errors.append(f"missing {count} keys from target: {', '.join(sample)}")
    return errors


@dataclass
class PreCheckWarning:
    severity: str          # "error" | "warning" | "info"
    category: str          # "empty_key" | "duplicate_key" | "empty_value" | "very_long" | "unusual_placeholder" | "no_files"
    file: str
    key: str
    message: str
    value_snippet: str = ""


def pre_check_lang_documents(
    docs: list[LangDocument],
    max_text_length: int = 500,
) -> list[PreCheckWarning]:
    warnings: list[PreCheckWarning] = []
    if not docs:
        warnings.append(PreCheckWarning(
            severity="error", category="no_files",
            file="", key="",
            message="No source language files found",
        ))
        return warnings

    for doc in docs:
        seen_keys: set[str] = set()
        for key, raw_value in doc.entries.items():
            text = extract_plain_text(raw_value)

            if not key.strip():
                warnings.append(PreCheckWarning(
                    severity="error", category="empty_key",
                    file=doc.path, key=key,
                    message="Key is empty or whitespace-only",
                ))
                continue

            if key in seen_keys:
                warnings.append(PreCheckWarning(
                    severity="warning", category="duplicate_key",
                    file=doc.path, key=key,
                    message=f"Duplicate key in {doc.path}",
                ))
            seen_keys.add(key)

            if not text.strip():
                warnings.append(PreCheckWarning(
                    severity="warning", category="empty_value",
                    file=doc.path, key=key,
                    message=f"Empty value for key '{key}'",
                ))

            if len(text) > max_text_length:
                warnings.append(PreCheckWarning(
                    severity="info", category="very_long",
                    file=doc.path, key=key,
                    message=f"Text length {len(text)} exceeds {max_text_length}",
                    value_snippet=text[:80],
                ))

            pct_count = text.count("%")
            pct_excluding_escaped = pct_count - 2 * text.count("%%")
            valid_pct = len(PRINTF_RE.findall(text))
            if pct_excluding_escaped > valid_pct:
                warnings.append(PreCheckWarning(
                    severity="info", category="unusual_placeholder",
                    file=doc.path, key=key,
                    message=f"Possible non-standard % specifiers: {pct_excluding_escaped - valid_pct} unmatched",
                ))

    return warnings
