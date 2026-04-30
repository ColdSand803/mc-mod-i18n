from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .lang import render_lang


@dataclass(frozen=True)
class OutputLangDocument:
    path: str
    format: str
    entries: dict[str, str]


def write_resource_pack(
    output_zip: Path,
    documents: list[OutputLangDocument],
    pack_format: int,
    description: str,
) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    pack_meta = {
        "pack": {
            "pack_format": pack_format,
            "description": description,
        }
    }

    with ZipFile(output_zip, "w", ZIP_DEFLATED) as zf:
        zf.writestr("pack.mcmeta", json.dumps(pack_meta, ensure_ascii=False, indent=2) + "\n")
        for document in sorted(documents, key=lambda item: item.path):
            zf.writestr(document.path, render_lang(document.entries, document.format))
