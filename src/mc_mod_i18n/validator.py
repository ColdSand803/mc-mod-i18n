from __future__ import annotations

from collections import Counter
import re


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
