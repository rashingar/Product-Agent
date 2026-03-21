from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from .models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace
from .utils import ensure_directory, write_bytes, write_text

try:  # pragma: no cover - dependency availability is environment-dependent
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover - dependency availability is environment-dependent
    PdfReader = None
    PDF_IMPORT_ERROR = str(exc)
else:  # pragma: no cover - simple import success branch
    PDF_IMPORT_ERROR = ""


NEFF_SPECSHEET_URL = "https://media3.neff-international.com/Documents/specsheet/el-GR/{mpn}.pdf"
PDF_HEADINGS = {
    "Χαρακτηριστικά",
    "Τεχνικά στοιχεία",
    "Τεχνικά χαρακτηριστικά",
    "Γενικά χαρακτηριστικά",
    "Διαστάσεις",
    "Σχέδια διαστάσεων",
}


def enrich_source_from_manufacturer_docs(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    fetcher,
    output_dir: str | Path,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "applied": False,
        "provider": "",
        "documents": [],
        "warnings": [],
        "section_count": 0,
        "field_count": 0,
    }
    brand = normalize_for_match(source.brand)
    mpn = normalize_whitespace(source.mpn)
    if brand != normalize_for_match("Neff") or not mpn:
        diagnostics["provider"] = "unsupported_brand_or_missing_mpn"
        return diagnostics
    if PdfReader is None:
        diagnostics["provider"] = "neff"
        diagnostics["warnings"].append(f"manufacturer_pdf_parser_unavailable:{PDF_IMPORT_ERROR}")
        return diagnostics

    provider_dir = ensure_directory(output_dir)
    diagnostics["provider"] = "neff"
    specsheet_url = NEFF_SPECSHEET_URL.format(mpn=mpn)
    document_entry = {
        "name": "specsheet",
        "url": specsheet_url,
        "local_path": "",
        "text_path": "",
        "content_type": "",
        "available": False,
        "field_count": 0,
        "section_count": 0,
        "warnings": [],
    }
    diagnostics["documents"].append(document_entry)

    try:
        payload, content_type = fetcher.fetch_binary(specsheet_url)
    except Exception as exc:
        document_entry["warnings"].append(f"fetch_failed:{exc}")
        diagnostics["warnings"].append("manufacturer_doc_fetch_failed:specsheet")
        return diagnostics

    document_entry["content_type"] = content_type
    pdf_path = provider_dir / "specsheet.pdf"
    write_bytes(pdf_path, payload)
    document_entry["local_path"] = str(pdf_path)

    try:
        text = _extract_pdf_text(payload)
    except Exception as exc:
        document_entry["warnings"].append(f"parse_failed:{exc}")
        diagnostics["warnings"].append("manufacturer_doc_parse_failed:specsheet")
        return diagnostics

    text_path = provider_dir / "specsheet.txt"
    write_text(text_path, text)
    document_entry["text_path"] = str(text_path)
    document_entry["available"] = True

    parsed_sections = _parse_neff_specsheet(text)
    source.manufacturer_spec_sections = parsed_sections
    source.manufacturer_source_text = normalize_whitespace(text)
    source.manufacturer_documents = [document_entry]

    field_count = sum(len(section.items) for section in parsed_sections)
    document_entry["field_count"] = field_count
    document_entry["section_count"] = len(parsed_sections)
    diagnostics["applied"] = field_count > 0
    diagnostics["section_count"] = len(parsed_sections)
    diagnostics["field_count"] = field_count
    return diagnostics


def _extract_pdf_text(payload: bytes) -> str:
    reader = PdfReader(io.BytesIO(payload))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_neff_specsheet(text: str) -> list[SpecSection]:
    lines = _normalize_pdf_lines(text)
    grouped: dict[str, list[SpecItem]] = {}
    current_section = "Κατασκευαστής"

    for line in lines:
        if line in PDF_HEADINGS:
            current_section = line
            continue
        label, value = _split_label_value(line)
        if not label or not value:
            continue
        grouped.setdefault(current_section, []).append(SpecItem(label=label, value=value))

    return [SpecSection(section=section, items=_dedupe_items(items)) for section, items in grouped.items() if items]


def _normalize_pdf_lines(text: str) -> list[str]:
    raw_lines: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_whitespace(raw_line.replace("\uf0b7", "•").replace("√", ""))
        line = re.sub(r"\.{2,}", " ", line)
        if not line or re.fullmatch(r"\d+\s*/", line):
            continue
        raw_lines.append(line)

    combined: list[str] = []
    for line in raw_lines:
        if line.startswith("• :") and combined:
            combined[-1] = normalize_whitespace(f"{combined[-1].rstrip(':')} {line[3:].lstrip(': ').strip()}")
            continue
        if combined and _should_join_pdf_line(combined[-1], line):
            combined[-1] = normalize_whitespace(f"{combined[-1]} {line}")
            continue
        combined.append(line)

    return [line for line in combined if not _ignore_pdf_line(line)]


def _should_join_pdf_line(previous: str, current: str) -> bool:
    if current in PDF_HEADINGS or previous in PDF_HEADINGS:
        return False
    if current.startswith("• "):
        return False
    if re.fullmatch(r"\d+\s*/", current):
        return False
    if ":" not in previous:
        return True
    return previous.endswith((",", "(", ":", "-", "και")) or previous.startswith("• ")


def _ignore_pdf_line(line: str) -> bool:
    normalized = normalize_for_match(line)
    if not normalized:
        return True
    if normalized in {normalize_for_match(heading) for heading in PDF_HEADINGS}:
        return False
    if normalized in {
        normalize_for_match("N 70, Ηλεκτρικές εστίες, 60 cm, εντοιχιζόμενη με πλαίσιο"),
        normalize_for_match("T16BT60N0"),
        normalize_for_match("Προαιρετικά εξαρτήματα"),
        normalize_for_match("Αυτόνομη ηλεκτρική εστία με TwistPad®"),
    }:
        return True
    if normalized.startswith(normalize_for_match("Z1365WX0")) or normalized.startswith(normalize_for_match("Z943SE0")):
        return True
    return False


def _split_label_value(line: str) -> tuple[str, str]:
    value_line = line[2:].strip() if line.startswith("• ") else line
    if ":" not in value_line:
        return "", ""
    label, value = value_line.split(":", 1)
    label = normalize_whitespace(label)
    value = normalize_whitespace(value).replace("Aνοξείδωτο", "Ανοξείδωτο")
    if not label or not value:
        return "", ""
    return label, value


def _dedupe_items(items: list[SpecItem]) -> list[SpecItem]:
    deduped: list[SpecItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (normalize_for_match(item.label), normalize_for_match(item.value or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
