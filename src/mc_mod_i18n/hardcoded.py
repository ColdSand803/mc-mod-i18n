from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
import struct
from zipfile import BadZipFile, ZipFile


@dataclass(frozen=True)
class HardcodedEntry:
    jar: str
    class_path: str
    text: str
    category: str
    risk: str
    suggestion: str


ENGLISH_RE = re.compile(r"[A-Za-z][A-Za-z0-9 ,.!?;:'\"()_\-/%]+")
EXCLUDE_RE = re.compile(
    r"^(?:"
    r"[a-z0-9_.$/:-]+|"
    r"\([^)]+\).+|"
    r"L[^;]+;|"
    r"[A-Z_]+|"
    r".*\.(?:png|json|toml|ogg|class|xml|txt|md|obj|mtl|glsl|fsh|vsh)"
    r")$",
    re.IGNORECASE,
)


def scan_jar_for_hardcoded(path: str, max_entries: int = 5000) -> list[HardcodedEntry]:
    entries: list[HardcodedEntry] = []
    with ZipFile(path) as zf:
        entries.extend(scan_zip_for_hardcoded(zf, label=_basename(path), max_entries=max_entries))
    return entries[:max_entries]


def scan_zip_for_hardcoded(zf: ZipFile, label: str, max_entries: int = 5000) -> list[HardcodedEntry]:
    entries: list[HardcodedEntry] = []
    seen: set[tuple[str, str, str]] = set()

    for name in sorted(zf.namelist()):
        if name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
            try:
                with ZipFile(BytesIO(zf.read(name))) as nested:
                    nested_label = f"{label}::{name}"
                    for entry in scan_zip_for_hardcoded(nested, nested_label, max_entries=max_entries - len(entries)):
                        key = (entry.jar, entry.class_path, entry.text)
                        if key not in seen:
                            seen.add(key)
                            entries.append(entry)
                        if len(entries) >= max_entries:
                            return entries
            except BadZipFile:
                continue
            continue

        if not name.endswith(".class"):
            continue

        try:
            strings = extract_constant_pool_strings(zf.read(name))
        except (IndexError, struct.error):
            continue

        for text in strings:
            normalized = normalize_candidate(text)
            if not normalized or not is_ui_candidate(normalized):
                continue
            category, risk, suggestion = classify_candidate(name, normalized)
            key = (label, name, normalized)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                HardcodedEntry(
                    jar=label,
                    class_path=name,
                    text=normalized,
                    category=category,
                    risk=risk,
                    suggestion=suggestion,
                )
            )
            if len(entries) >= max_entries:
                return entries

    return entries


def extract_constant_pool_strings(data: bytes) -> list[str]:
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        return []

    pos = 8
    constant_pool_count = struct.unpack(">H", data[pos : pos + 2])[0]
    pos += 2
    strings: list[str] = []
    index = 1

    while index < constant_pool_count and pos < len(data):
        tag = data[pos]
        pos += 1

        if tag == 1:
            length = struct.unpack(">H", data[pos : pos + 2])[0]
            pos += 2
            raw = data[pos : pos + length]
            pos += length
            try:
                strings.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                pass
        elif tag in (3, 4):
            pos += 4
        elif tag in (5, 6):
            pos += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            pos += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag == 15:
            pos += 3
        else:
            break

        index += 1

    return strings


def normalize_candidate(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", "", text)).strip()


def is_ui_candidate(text: str) -> bool:
    if len(text) < 4 or len(text) > 180:
        return False
    if not ENGLISH_RE.search(text):
        return False
    if EXCLUDE_RE.match(text):
        return False
    if "/" in text or "\\" in text:
        return False
    if text.count(".") > 2 and " " not in text:
        return False
    if re.search(r"[{};=<>]", text) and " " not in text:
        return False
    return bool(" " in text or re.search(r"[.!?:]", text))


def classify_candidate(class_path: str, text: str) -> tuple[str, str, str]:
    lowered = class_path.lower()
    if "/ponder/scenes/" in lowered or "/content/ponder/scenes/" in lowered:
        return "ponder", "high", "生成 i18n patch mod，在 Ponder 文本显示入口按原文替换。"
    if ("/config/" in lowered or "comments.class" in lowered) and is_config_comment_text(text):
        return "config_comment", "medium", "优先生成汉化配置模板；后续可做配置注释运行时补丁。"
    if "advancement" in lowered:
        return "advancement_datagen", "low", "多数应已进入 lang 文件；只在游戏中仍显示英文时处理。"
    if "tooltip" in lowered or "screen" in lowered or "gui" in lowered:
        return "ui_literal", "high", "确认是客户端显示文本后，加入补丁 Mod 映射表。"
    if re.search(r"\b(?:rpm|kpg|gpn|mpg|mpn|kpn)\b", text, re.IGNORECASE):
        return "unit_or_label", "low", "多半是单位或缩写，通常不建议翻译。"
    return "unknown_literal", "medium", "人工确认用途后再决定是否加入硬编码翻译映射。"


def is_config_comment_text(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ("unable to", "missing", "must ", "not registered", "callback", "impl ")):
        return False
    return bool(
        re.match(
            r"^(?:The|Whether|Maximum|Minimum|Configure|Parameters|Settings|Fine tune|Enable|Disable|Disallow|Allow|When)\b",
            text,
        )
    )


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]
