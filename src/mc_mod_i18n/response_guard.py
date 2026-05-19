from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class ResponseGuardRule:
    id: str
    pattern: re.Pattern[str]
    description: str


@dataclass(frozen=True)
class ResponseGuardMatch:
    rule_id: str
    description: str
    snippet: str


@dataclass(frozen=True)
class ResponseGuardResult:
    blocked: bool
    matches: tuple[ResponseGuardMatch, ...]

    @property
    def message(self) -> str:
        if not self.matches:
            return ""
        details = "; ".join(f"{match.rule_id}: {match.snippet}" for match in self.matches)
        return f"blocked suspicious provider response ({details})"


@dataclass(frozen=True)
class ResponseSanitizerResult:
    text: str
    changed: bool
    matches: tuple[ResponseGuardMatch, ...]

    @property
    def message(self) -> str:
        if not self.matches:
            return ""
        details = "; ".join(f"{match.rule_id}: {match.snippet}" for match in self.matches)
        return f"filtered suspicious provider response ({details})"


DEFAULT_RESPONSE_GUARD_RULES: tuple[ResponseGuardRule, ...] = (
    ResponseGuardRule(
        id="public-token-notice",
        pattern=re.compile(r"(?:公益|免费|共享)\s*(?:token|key|api\s*key)\w*", re.IGNORECASE),
        description="public/shared token notice",
    ),
    ResponseGuardRule(
        id="notification-group",
        pattern=re.compile(r"(?:通知群|交流群|官方群|群号|加群|qq群|qq\s*群)", re.IGNORECASE),
        description="chat group promotion or notification",
    ),
    ResponseGuardRule(
        id="group-number-nearby",
        pattern=re.compile(r"(?:通知群|交流群|官方群|群号|加群|qq群|qq\s*群)[^\n\r]{0,24}\d{6,12}", re.IGNORECASE),
        description="chat group number near group keyword",
    ),
)


def build_keyword_rules(keywords: Iterable[str]) -> tuple[ResponseGuardRule, ...]:
    rules: list[ResponseGuardRule] = []
    for index, keyword in enumerate(keywords):
        normalized = str(keyword or "").strip()
        if not normalized:
            continue
        rules.append(
            ResponseGuardRule(
                id=f"custom-keyword-{index + 1}",
                pattern=re.compile(re.escape(normalized), re.IGNORECASE),
                description=f"custom keyword: {normalized}",
            )
        )
    return tuple(rules)


def inspect_provider_response(
    text: object,
    *,
    extra_keywords: Iterable[str] = (),
    rules: Iterable[ResponseGuardRule] = DEFAULT_RESPONSE_GUARD_RULES,
    max_snippet: int = 96,
) -> ResponseGuardResult:
    value = "" if text is None else str(text)
    if not value:
        return ResponseGuardResult(False, ())
    active_rules = tuple(rules) + build_keyword_rules(extra_keywords)
    matches: list[ResponseGuardMatch] = []
    for rule in active_rules:
        match = rule.pattern.search(value)
        if not match:
            continue
        snippet = _compact_snippet(match.group(0), max_snippet)
        matches.append(ResponseGuardMatch(rule.id, rule.description, snippet))
    return ResponseGuardResult(bool(matches), tuple(matches))


def sanitize_provider_response(
    text: object,
    *,
    extra_keywords: Iterable[str] = (),
    rules: Iterable[ResponseGuardRule] = DEFAULT_RESPONSE_GUARD_RULES,
    max_snippet: int = 96,
) -> ResponseSanitizerResult:
    value = "" if text is None else str(text)
    if not value:
        return ResponseSanitizerResult(value, False, ())
    active_rules = tuple(rules) + build_keyword_rules(extra_keywords)
    ranges: list[tuple[int, int]] = []
    matches: list[ResponseGuardMatch] = []
    for rule in active_rules:
        for match in rule.pattern.finditer(value):
            start, end = _expand_to_line(value, match.start(), match.end())
            snippet = _compact_snippet(value[start:end] or match.group(0), max_snippet)
            matches.append(ResponseGuardMatch(rule.id, rule.description, snippet))
            ranges.append((start, end))
    if not ranges:
        return ResponseSanitizerResult(value, False, ())
    cleaned = _remove_ranges(value, ranges).strip()
    return ResponseSanitizerResult(cleaned, cleaned != value, tuple(matches))


def _expand_to_line(value: str, start: int, end: int) -> tuple[int, int]:
    line_start = value.rfind("\n", 0, start) + 1
    line_end = value.find("\n", end)
    if line_end < 0:
        line_end = len(value)
    else:
        line_end += 1
    if line_start > 0 and value[line_start - 2 : line_start] == "\r\n":
        line_start -= 1
    return line_start, line_end


def _remove_ranges(value: str, ranges: Iterable[tuple[int, int]]) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end in sorted(ranges):
        start = max(cursor, start)
        if start > cursor:
            pieces.append(value[cursor:start])
        cursor = max(cursor, end)
    pieces.append(value[cursor:])
    return "".join(pieces)


def _compact_snippet(value: str, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max(0, max_length - 1)].rstrip() + "..."
