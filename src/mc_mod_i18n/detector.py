from __future__ import annotations

from dataclasses import dataclass
import json
import re
from zipfile import ZipFile


@dataclass(frozen=True)
class ModMetadata:
    jar_name: str
    loader: str
    mod_id: str
    name: str
    version: str


def detect_mod(zf: ZipFile, jar_name: str) -> ModMetadata:
    names = set(zf.namelist())

    for path, loader in (
        ("fabric.mod.json", "fabric"),
        ("quilt.mod.json", "quilt"),
    ):
        if path in names:
            try:
                data = json.loads(zf.read(path).decode("utf-8-sig"))
                return ModMetadata(
                    jar_name=jar_name,
                    loader=loader,
                    mod_id=str(data.get("id") or _fallback_mod_id(names, jar_name)),
                    name=str(data.get("name") or data.get("id") or jar_name),
                    version=str(data.get("version") or "unknown"),
                )
            except Exception:
                break

    if "META-INF/mods.toml" in names:
        text = zf.read("META-INF/mods.toml").decode("utf-8", errors="replace")
        mod_id = _toml_string(text, "modId") or _fallback_mod_id(names, jar_name)
        return ModMetadata(
            jar_name=jar_name,
            loader="forge/neoforge",
            mod_id=mod_id,
            name=_toml_string(text, "displayName") or mod_id,
            version=_toml_string(text, "version") or "unknown",
        )

    if "mcmod.info" in names:
        try:
            data = json.loads(zf.read("mcmod.info").decode("utf-8-sig"))
            first = data[0] if isinstance(data, list) and data else data
            if isinstance(first, dict):
                mod_id = str(first.get("modid") or _fallback_mod_id(names, jar_name))
                return ModMetadata(
                    jar_name=jar_name,
                    loader="legacy-forge",
                    mod_id=mod_id,
                    name=str(first.get("name") or mod_id),
                    version=str(first.get("version") or "unknown"),
                )
        except Exception:
            pass

    mod_id = _fallback_mod_id(names, jar_name)
    return ModMetadata(jar_name=jar_name, loader="unknown", mod_id=mod_id, name=mod_id, version="unknown")


def _toml_string(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1) if match else None


def _fallback_mod_id(names: set[str], jar_name: str) -> str:
    asset_ids: list[str] = []
    for name in names:
        match = re.match(r"assets/([^/]+)/lang/", name)
        if match:
            asset_ids.append(match.group(1))
    if asset_ids:
        return sorted(asset_ids)[0]

    stem = re.sub(r"\.jar$", "", jar_name, flags=re.IGNORECASE)
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stem).strip("_")
    return stem.lower() or "unknown_mod"
