from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_BRAND_LOGO = "cat"
SYSTEM_SETTINGS_DIRNAME = "settings"
SYSTEM_SETTINGS_FILENAME = "system.json"
BRANDING_CONFIG_FILENAME = "branding.json"

BRAND_LOGO_OPTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "cat",
        "label": "猫猫头像",
        "menu_name": "猫 PNG",
        "png": "co1dsand_logo_cat.png",
        "svg": "co1dsand_logo_cat.svg",
        "ico": "co1dsand_logo_cat.ico",
    },
    {
        "id": "grass",
        "label": "草方块",
        "menu_name": "草方块",
        "png": "minecraft.png",
        "svg": "minecraft.svg",
        "ico": "minecraft.ico",
    },
    {
        "id": "sign",
        "label": "签名标识",
        "menu_name": "签名 PNG",
        "png": "co1dsand_logo_sign.png",
        "svg": "co1dsand_logo_sign.svg",
        "ico": "co1dsand_logo_sign.ico",
    },
)
BRAND_LOGO_BY_ID = {item["id"]: item for item in BRAND_LOGO_OPTIONS}


def normalize_brand_logo_choice(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "cat_png": "cat",
        "cat_logo": "cat",
        "minecraft": "grass",
        "grass_block": "grass",
        "grass_png": "grass",
        "sign_png": "sign",
        "signature": "sign",
        "logo_sign": "sign",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in BRAND_LOGO_BY_ID else DEFAULT_BRAND_LOGO


def brand_logo_options_payload() -> list[dict[str, str]]:
    return [
        {"id": item["id"], "label": item["label"], "menu_name": item["menu_name"]}
        for item in BRAND_LOGO_OPTIONS
    ]


def logo_root(resource_root: Path) -> Path:
    return resource_root / "logo"


def brand_logo_asset_path(choice: Any, kind: str, resource_root: Path) -> Path:
    option = BRAND_LOGO_BY_ID[normalize_brand_logo_choice(choice)]
    base = logo_root(resource_root)
    if kind == "png":
        return base / "png" / option["png"]
    if kind == "svg":
        return base / "svg" / option["svg"]
    if kind == "ico":
        return base / option["ico"]
    raise ValueError(f"unsupported logo asset kind: {kind}")


def sidebar_logo_path(resource_root: Path) -> Path:
    return brand_logo_asset_path("grass", "svg", resource_root)


def cat_ico_path(resource_root: Path) -> Path:
    return brand_logo_asset_path("cat", "ico", resource_root)


def system_settings_payload(
    workdir: Path,
    *,
    settings: dict[str, Any],
    default_cache_dir: Path,
    default_ui_locale_dir: Path,
) -> dict[str, Any]:
    return {
        **settings,
        "brand_options": brand_logo_options_payload(),
        "data_dir": str(workdir.resolve()),
        "default_cache_dir": str(default_cache_dir),
        "default_ui_locale_dir": str(default_ui_locale_dir),
    }


def system_settings_path(workdir: Path) -> Path:
    settings_dir = workdir / SYSTEM_SETTINGS_DIRNAME
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / SYSTEM_SETTINGS_FILENAME


def branding_config_path(resource_root: Path) -> Path:
    return logo_root(resource_root) / BRANDING_CONFIG_FILENAME


def read_branding_build_config(resource_root: Path) -> dict[str, str]:
    path = branding_config_path(resource_root)
    if not path.is_file():
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    if not isinstance(payload, dict):
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    return {"brand_logo": normalize_brand_logo_choice(payload.get("brand_logo"))}


def write_branding_build_config(brand_logo: Any, resource_root: Path) -> None:
    path = branding_config_path(resource_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"brand_logo": normalize_brand_logo_choice(brand_logo)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def should_sync_branding_build_config(
    workdir: Path,
    *,
    project_root: Path,
    frozen: bool = False,
    sync_build_config: bool = False,
) -> bool:
    if frozen:
        return False
    if sync_build_config:
        return True
    try:
        workdir.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False
    return True


def read_system_settings(workdir: Path) -> dict[str, Any]:
    path = system_settings_path(workdir)
    if not path.is_file():
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    if not isinstance(payload, dict):
        return {"brand_logo": DEFAULT_BRAND_LOGO}
    return {"brand_logo": normalize_brand_logo_choice(payload.get("brand_logo"))}


def write_system_settings(workdir: Path, *, brand_logo: Any) -> dict[str, Any]:
    payload = {"brand_logo": normalize_brand_logo_choice(brand_logo)}
    path = system_settings_path(workdir)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def co1dsand_pack_logo_paths(
    resource_root: Path,
    cwd: Path | None = None,
    *,
    brand_logo: Any = DEFAULT_BRAND_LOGO,
) -> tuple[Path, ...]:
    selected = normalize_brand_logo_choice(brand_logo)
    candidates = [brand_logo_asset_path(selected, "png", resource_root)]
    if selected != DEFAULT_BRAND_LOGO:
        candidates.append(brand_logo_asset_path(DEFAULT_BRAND_LOGO, "png", resource_root))
    if cwd is not None:
        candidates.append(brand_logo_asset_path(selected, "png", cwd))
        if selected != DEFAULT_BRAND_LOGO:
            candidates.append(brand_logo_asset_path(DEFAULT_BRAND_LOGO, "png", cwd))
    return tuple(dict.fromkeys(candidates))
