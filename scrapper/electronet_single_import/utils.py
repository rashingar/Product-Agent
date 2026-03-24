from __future__ import annotations

import csv
import json
import mimetypes
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .normalize import normalize_for_match, normalize_whitespace


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_TEMPLATE_PATH = REPO_ROOT / "product_import_template.csv"
RULES_PATH = REPO_ROOT / "RULES.md"
PRESENTATION_TEMPLATE_PATH = REPO_ROOT / "TEMPLATE_presentation.html"
CATALOG_TAXONOMY_PATH = REPO_ROOT / "catalog_taxonomy.json"
SCHEMA_LIBRARY_PATH = REPO_ROOT / "electronet_schema_library.json"
CHARACTERISTICS_TEMPLATES_PATH = REPO_ROOT / "characteristics_templates.json"
FILTER_MAP_PATH = REPO_ROOT / "filter_map.json"
NAME_RULES_PATH = REPO_ROOT / "name_rules.json"
MASTER_PROMPT_PATH = REPO_ROOT / "master_prompt+.txt"
COMPACT_RESPONSE_SCHEMA_PATH = REPO_ROOT / "schemas" / "compact_response.schema.json"



def ensure_directory(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out



def build_model_output_dir(base_out: str | Path, model: str) -> Path:
    return ensure_directory(Path(base_out) / model)



def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()



def read_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)



def write_json(path: str | Path, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")



def write_text(path: str | Path, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)



def write_bytes(path: str | Path, payload: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(payload)



def load_template_headers(path: str | Path = PRODUCT_TEMPLATE_PATH) -> list[str]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)



def first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        normalized = normalize_whitespace(value)
        if normalized:
            return normalized
    return ""



def as_decimal_string(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return normalize_whitespace(str(value))
    if dec == dec.to_integral():
        return str(int(dec))
    normalized = format(dec.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized



def build_additional_image_value(model: str, photos: int) -> str:
    if photos <= 1:
        return ""
    parts = [f"catalog/01_main/{model}/{model}-{index}.jpg" for index in range(2, photos + 1)]
    return ":::".join(parts)



def dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = normalize_for_match(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(normalize_whitespace(value))
    return out



def guess_extension_from_url(url: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}:
        return suffix
    return ""



def guess_extension(content_type: str | None, url: str) -> str:
    normalized_type = normalize_whitespace(content_type).split(";")[0].strip().lower()
    if normalized_type == "image/jpeg":
        return ".jpg"
    if normalized_type:
        guessed = mimetypes.guess_extension(normalized_type, strict=False) or ""
        if guessed == ".jpe":
            guessed = ".jpg"
        if guessed:
            return guessed
    url_ext = guess_extension_from_url(url)
    return url_ext or ".jpg"
