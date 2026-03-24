from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from .normalize import normalize_for_match, normalize_whitespace
from .utils import dedupe_strings, ensure_directory, write_bytes, write_text

try:  # pragma: no cover - dependency availability is environment-dependent
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover - dependency availability is environment-dependent
    PdfReader = None
    PDF_IMPORT_ERROR = str(exc)
else:  # pragma: no cover - simple import success branch
    PDF_IMPORT_ERROR = ""


NEFF_SPECSHEET_URL = "https://media3.neff-international.com/Documents/specsheet/el-GR/{mpn}.pdf"
BOSCH_SPECSHEET_URL = "https://media3.bosch-home.com/Documents/specsheet/el-GR/{mpn}.pdf"
PDF_HEADINGS = {
    "Χαρακτηριστικά",
    "Τεχνικά στοιχεία",
    "Τεχνικά χαρακτηριστικά",
    "Γενικά χαρακτηριστικά",
    "Διαστάσεις",
    "Σχέδια διαστάσεων",
}
BOSCH_SECTION_TITLES = {
    "Τεχνικά στοιχεία",
    "Τεχνικά Χαρακτηριστικά",
    "Γενικά χαρακτηριστικά",
    "Στη συντήρηση",
    "Στην κατάψυξη",
    "Διαστάσεις Συσκευής",
}


@dataclass(slots=True)
class OfficialDocumentCandidate:
    provider_id: str
    document_type: str
    url: str
    name: str = "document"
    content_type_hint: str = ""
    priority: int = 100


@dataclass(slots=True)
class EnrichmentResult:
    manufacturer_spec_sections: list[SpecSection] = field(default_factory=list)
    manufacturer_source_text: str = ""
    warnings: list[str] = field(default_factory=list)


class OfficialDocAdapter:
    provider_id = ""

    def matches(self, source: SourceProductData) -> bool:
        raise NotImplementedError

    def discover(self, source: SourceProductData, taxonomy: TaxonomyResolution) -> list[OfficialDocumentCandidate]:
        raise NotImplementedError

    def parse(self, candidate: OfficialDocumentCandidate, payload: bytes | str, source: SourceProductData, taxonomy: TaxonomyResolution) -> EnrichmentResult:
        raise NotImplementedError


class _StaticPdfAdapter(OfficialDocAdapter):
    url_template = ""
    parser = staticmethod(lambda _text: [])

    def matches(self, source: SourceProductData) -> bool:
        return bool(normalize_whitespace(source.mpn))

    def discover(self, source: SourceProductData, taxonomy: TaxonomyResolution) -> list[OfficialDocumentCandidate]:
        mpn = normalize_whitespace(source.mpn)
        if not mpn or not self.url_template:
            return []
        return [
            OfficialDocumentCandidate(
                provider_id=self.provider_id,
                document_type="pdf",
                url=self.url_template.format(mpn=mpn),
                name="specsheet",
                content_type_hint="application/pdf",
                priority=10,
            )
        ]

    def parse(self, candidate: OfficialDocumentCandidate, payload: bytes | str, source: SourceProductData, taxonomy: TaxonomyResolution) -> EnrichmentResult:
        if PdfReader is None:
            raise RuntimeError(f"manufacturer_pdf_parser_unavailable:{PDF_IMPORT_ERROR}")
        if not isinstance(payload, (bytes, bytearray)):
            raise RuntimeError("manufacturer_pdf_payload_invalid")
        text = _extract_pdf_text(bytes(payload))
        sections = self.parser(text)
        return EnrichmentResult(
            manufacturer_spec_sections=sections,
            manufacturer_source_text=normalize_whitespace(text),
        )


class BoschSpecsheetAdapter(_StaticPdfAdapter):
    provider_id = "bosch"
    url_template = BOSCH_SPECSHEET_URL
    parser = staticmethod(lambda text: _parse_bosch_specsheet(text))

    def matches(self, source: SourceProductData) -> bool:
        return normalize_for_match(source.brand) == normalize_for_match("Bosch") and super().matches(source)


class NeffSpecsheetAdapter(_StaticPdfAdapter):
    provider_id = "neff"
    url_template = NEFF_SPECSHEET_URL
    parser = staticmethod(lambda text: _parse_neff_specsheet(text))

    def matches(self, source: SourceProductData) -> bool:
        return normalize_for_match(source.brand) == normalize_for_match("Neff") and super().matches(source)


def get_official_doc_adapters() -> list[OfficialDocAdapter]:
    return [BoschSpecsheetAdapter(), NeffSpecsheetAdapter()]


def enrich_source_from_manufacturer_docs(
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    fetcher,
    output_dir: str | Path,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "applied": False,
        "provider": "",
        "providers_considered": [],
        "matched_providers": [],
        "documents": [],
        "documents_discovered": 0,
        "documents_parsed": 0,
        "warnings": [],
        "section_count": 0,
        "field_count": 0,
        "fallback_reason": "",
    }
    source.manufacturer_spec_sections = []
    source.manufacturer_source_text = ""
    source.manufacturer_documents = []

    if normalize_for_match(source.source_name) != "skroutz":
        diagnostics["fallback_reason"] = "not_applicable_non_skroutz"
        return diagnostics

    adapters = get_official_doc_adapters()
    diagnostics["providers_considered"] = [adapter.provider_id for adapter in adapters]
    matched_adapters = [adapter for adapter in adapters if adapter.matches(source)]
    diagnostics["matched_providers"] = [adapter.provider_id for adapter in matched_adapters]
    diagnostics["provider"] = ",".join(diagnostics["matched_providers"])

    if not normalize_whitespace(source.mpn):
        diagnostics["fallback_reason"] = "missing_mpn"
        return diagnostics
    if not matched_adapters:
        diagnostics["fallback_reason"] = "no_matching_provider"
        return diagnostics

    provider_dir = ensure_directory(output_dir)
    merged_sections: list[SpecSection] = []
    merged_text_parts: list[str] = []
    successful_providers: list[str] = []

    for adapter in matched_adapters:
        candidates = sorted(
            adapter.discover(source, taxonomy),
            key=lambda candidate: (candidate.priority, candidate.name, candidate.url),
        )
        diagnostics["documents_discovered"] += len(candidates)
        for index, candidate in enumerate(candidates, start=1):
            document_entry = _create_document_entry(candidate)
            diagnostics["documents"].append(document_entry)
            try:
                payload, content_type, final_url = _fetch_candidate(fetcher, candidate)
            except Exception as exc:
                document_entry["warnings"].append(f"fetch_failed:{exc}")
                diagnostics["warnings"].append(f"manufacturer_doc_fetch_failed:{candidate.name}")
                continue

            document_entry["available"] = True
            document_entry["content_type"] = content_type
            document_entry["final_url"] = final_url
            local_path = _write_document_payload(provider_dir, candidate, payload, index)
            document_entry["local_path"] = str(local_path)

            try:
                result = adapter.parse(candidate, payload, source, taxonomy)
            except Exception as exc:
                document_entry["warnings"].append(f"parse_failed:{exc}")
                diagnostics["warnings"].append(f"manufacturer_doc_parse_failed:{candidate.name}")
                continue

            text_payload = normalize_whitespace(result.manufacturer_source_text) or _fallback_document_text(candidate, payload)
            if text_payload:
                text_path = provider_dir / f"{local_path.stem}.txt"
                write_text(text_path, text_payload)
                document_entry["text_path"] = str(text_path)

            parsed_sections = _dedupe_sections(result.manufacturer_spec_sections)
            section_count = len(parsed_sections)
            field_count = sum(len(section.items) for section in parsed_sections)

            document_entry["parsed"] = field_count > 0
            document_entry["section_count"] = section_count
            document_entry["field_count"] = field_count
            document_entry["warnings"].extend(result.warnings)

            if not field_count:
                continue

            diagnostics["documents_parsed"] += 1
            successful_providers.append(adapter.provider_id)
            merged_sections = _merge_sections(merged_sections, parsed_sections)
            if text_payload:
                merged_text_parts.append(text_payload)

    merged_text = normalize_whitespace(" ".join(part for part in merged_text_parts if part))
    source.manufacturer_spec_sections = merged_sections
    source.manufacturer_source_text = merged_text
    source.manufacturer_documents = diagnostics["documents"]

    diagnostics["provider"] = ",".join(dedupe_strings(successful_providers or diagnostics["matched_providers"]))
    diagnostics["section_count"] = len(merged_sections)
    diagnostics["field_count"] = sum(len(section.items) for section in merged_sections)
    diagnostics["applied"] = diagnostics["field_count"] > 0

    if not diagnostics["applied"] and not diagnostics["fallback_reason"]:
        if diagnostics["documents_discovered"] == 0:
            diagnostics["fallback_reason"] = "no_documents_discovered"
        elif diagnostics["documents_parsed"] == 0:
            diagnostics["fallback_reason"] = "no_documents_parsed"

    return diagnostics


def _create_document_entry(candidate: OfficialDocumentCandidate) -> dict[str, Any]:
    return {
        "name": candidate.name,
        "provider_id": candidate.provider_id,
        "document_type": candidate.document_type,
        "url": candidate.url,
        "final_url": candidate.url,
        "content_type_hint": candidate.content_type_hint,
        "local_path": "",
        "text_path": "",
        "content_type": "",
        "available": False,
        "parsed": False,
        "field_count": 0,
        "section_count": 0,
        "warnings": [],
    }


def _fetch_candidate(fetcher, candidate: OfficialDocumentCandidate) -> tuple[bytes | str, str, str]:
    document_type = normalize_for_match(candidate.document_type)
    if document_type == "pdf":
        payload, content_type = fetcher.fetch_binary(candidate.url)
        return payload, content_type, candidate.url
    if document_type == "html":
        fetch = fetcher.fetch_playwright(candidate.url)
        return fetch.html, "text/html", fetch.final_url
    raise RuntimeError(f"unsupported_document_type:{candidate.document_type}")


def _write_document_payload(output_dir: Path, candidate: OfficialDocumentCandidate, payload: bytes | str, index: int) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", candidate.name or f"document_{index}").strip("._") or f"document_{index}"
    if index > 1:
        safe_name = f"{safe_name}_{index}"
    suffix = ".pdf" if normalize_for_match(candidate.document_type) == "pdf" else ".html"
    local_path = output_dir / f"{safe_name}{suffix}"
    if isinstance(payload, (bytes, bytearray)):
        write_bytes(local_path, bytes(payload))
    else:
        write_text(local_path, str(payload))
    return local_path


def _fallback_document_text(candidate: OfficialDocumentCandidate, payload: bytes | str) -> str:
    if normalize_for_match(candidate.document_type) == "html" and isinstance(payload, str):
        return _extract_html_text(payload)
    return ""


def _merge_sections(existing: list[SpecSection], incoming: list[SpecSection]) -> list[SpecSection]:
    grouped: dict[str, list[SpecItem]] = {}
    ordered_titles: list[str] = []
    for section in [*existing, *incoming]:
        title = normalize_whitespace(section.section)
        if not title:
            continue
        key = normalize_for_match(title)
        if key not in grouped:
            grouped[key] = []
            ordered_titles.append(title)
        grouped[key].extend(section.items)
    return [SpecSection(section=title, items=_dedupe_items(grouped[normalize_for_match(title)])) for title in ordered_titles]


def _dedupe_sections(sections: list[SpecSection]) -> list[SpecSection]:
    return _merge_sections([], sections)


def _extract_pdf_text(payload: bytes) -> str:
    reader = PdfReader(io.BytesIO(payload))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_html_text(html: str) -> str:
    return normalize_whitespace(BeautifulSoup(html, "lxml").get_text(" ", strip=True))


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


def _parse_bosch_specsheet(text: str) -> list[SpecSection]:
    lines = _normalize_bosch_pdf_lines(text)
    grouped: dict[str, list[SpecItem]] = {}
    current_section = "Κατασκευαστής"

    for line in lines:
        if line in BOSCH_SECTION_TITLES:
            current_section = line
            continue
        if line.startswith("- "):
            label, value = _split_label_value(line[2:].strip())
            if label and value:
                grouped.setdefault(current_section, []).append(SpecItem(label=label, value=value))
            else:
                grouped.setdefault(current_section, []).append(SpecItem(label="Ξ£Ξ·ΞΌΞµΞ―Ο‰ΟƒΞ·", value=line[2:].strip()))
            continue
        label, value = _split_label_value(line)
        if label and value:
            grouped.setdefault(current_section, []).append(SpecItem(label=label, value=value))

    return [SpecSection(section=section, items=_dedupe_items(items)) for section, items in grouped.items() if items]


def _normalize_bosch_pdf_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_whitespace(raw_line)
        line = re.sub(r"\.{2,}", " ", line)
        if not line or re.fullmatch(r"\d+\s*/", line):
            continue
        if line.startswith("Σειρά ") or line == "1 /" or line == "2 /" or line == "3 /":
            continue
        if line.startswith("Ο ψυγειοκαταψύκτης ") or line.startswith("• "):
            continue
        lines.append(line)
    return lines


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
        normalize_for_match("Αυτόνομη ηλεκτρική εστία με TwistPadΒ®"),
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
