from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .lang import extract_plain_text, LangDocument

PRINTF_RE = re.compile(
    r"%(?!%)"
    r"(?:(?:\d+\$|<)?[+#\-0,(]*(?:\d+)?(?:\.\d+)?[bBhHsScC]"
    r"|(?:\d+\$|<)?[+#\-0,( ]*(?:\d+)?(?:\.\d+)?[doxXeEfgGaA]"
    r"|(?:\d+\$|<)?[+#\-0,(]*(?:\d+)?(?:\.\d+)?[tT][A-Za-z]"
    r"|n)"
)
BRACE_RE = re.compile(r"\{[A-Za-z0-9_.:-]+\}")
COLOR_RE = re.compile(r"§[0-9A-FK-ORa-fk-or]")
NUMBERED_TEXT_LINE_RE = re.compile(r"^(?P<prefix>.+\.(?:desc|description|hint|info|line|summary|text|tooltip))\.\d+$", re.IGNORECASE)


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

            if not text.strip() and not _looks_like_intentional_blank_line(key, doc.entries):
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

            unusual_pct = _unusual_percent_count(text)
            if unusual_pct:
                warnings.append(PreCheckWarning(
                    severity="info", category="unusual_placeholder",
                    file=doc.path, key=key,
                    message=f"Possible non-standard % specifiers: {unusual_pct} unmatched",
                ))

    return warnings


def _looks_like_intentional_blank_line(
    key: str,
    entries: dict[str, str | dict[str, object]],
) -> bool:
    match = NUMBERED_TEXT_LINE_RE.match(key)
    if not match:
        return False

    prefix = match.group("prefix")
    sibling_prefix = f"{prefix}."
    for sibling_key, sibling_value in entries.items():
        if sibling_key != key and sibling_key.startswith(sibling_prefix) and extract_plain_text(sibling_value).strip():
            return True
    return False


def _unusual_percent_count(text: str) -> int:
    count = 0
    index = 0
    while index < len(text):
        if text[index] != "%":
            index += 1
            continue

        if text.startswith("%%", index):
            index += 2
            continue

        match = PRINTF_RE.match(text, index)
        if match:
            index = match.end()
            continue

        if _previous_non_space_char(text, index).isdigit():
            index += 1
            continue

        count += 1
        index += 1
    return count


def _previous_non_space_char(text: str, index: int) -> str:
    cursor = index - 1
    while cursor >= 0:
        if not text[cursor].isspace():
            return text[cursor]
        cursor -= 1
    return ""
