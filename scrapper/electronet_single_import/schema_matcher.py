from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import SchemaMatchResult, SpecSection
from .normalize import normalize_for_match
from .utils import SCHEMA_LIBRARY_PATH, read_json


class SchemaMatcher:
    def __init__(self, schema_path: str = str(SCHEMA_LIBRARY_PATH)) -> None:
        self.schema_path = schema_path
        self.payload = read_json(schema_path)
        self.schemas: list[dict[str, Any]] = self.payload.get("schemas", [])
        self._known_titles = {
            normalize_for_match(section.get("title", ""))
            for schema in self.schemas
            for section in schema.get("sections", [])
            if section.get("title")
        }
        self._known_titles.update(
            {
                normalize_for_match("Επιλογές Πλύσης"),
                normalize_for_match("Επιλογές"),
                normalize_for_match("Ασφάλεια"),
                normalize_for_match("Συνδέσεις"),
                normalize_for_match("Γενικά Χαρακτηριστικά"),
                normalize_for_match("Ενεργειακά χαρακτηριστικά"),
            }
        )

    @property
    def known_section_titles(self) -> set[str]:
        return {title for title in self._known_titles if title}

    def match(
        self,
        spec_sections: list[SpecSection],
        taxonomy_sub_category: str | None = None,
        preferred_source_files: list[str] | None = None,
    ) -> tuple[SchemaMatchResult, list[dict[str, Any]]]:
        if not spec_sections:
            return SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["no_spec_sections_extracted"]), []

        extracted_titles = {normalize_for_match(section.section) for section in spec_sections if section.section}
        extracted_labels = {
            normalize_for_match(item.label)
            for section in spec_sections
            for item in section.items
            if item.label
        }

        candidate_schemas = self.schemas
        preferred_source_files = preferred_source_files or []
        normalized_preferred_files = {
            normalize_for_match(item)
            for item in preferred_source_files
            if normalize_for_match(item)
        }
        if normalized_preferred_files:
            filtered_schemas = [
                schema
                for schema in self.schemas
                if normalized_preferred_files
                & {
                    normalize_for_match(source_file)
                    for source_file in schema.get("source_files", [])
                    if source_file
                }
            ]
            if filtered_schemas:
                candidate_schemas = filtered_schemas

        candidates: list[dict[str, Any]] = []
        for schema in candidate_schemas:
            schema_titles = {
                normalize_for_match(section.get("title", ""))
                for section in schema.get("sections", [])
                if section.get("title")
            }
            schema_labels = {
                normalize_for_match(label)
                for section in schema.get("sections", [])
                for label in section.get("labels", [])
                if label
            }
            title_overlap = len(extracted_titles & schema_titles) / max(len(schema_titles), 1)
            label_overlap = len(extracted_labels & schema_labels) / max(len(schema_labels), 1)
            score = (0.55 * title_overlap) + (0.45 * label_overlap)

            candidate_sub = schema.get("sub_category")
            if taxonomy_sub_category and candidate_sub and normalize_for_match(candidate_sub) == normalize_for_match(taxonomy_sub_category):
                score += 0.05
            if taxonomy_sub_category and not candidate_sub:
                score += 0.01

            candidates.append(
                {
                    "matched_schema_id": schema.get("schema_id"),
                    "matched_sub_category": candidate_sub,
                    "score": round(score, 4),
                    "n_sections": schema.get("n_sections"),
                    "n_rows_total": schema.get("n_rows_total"),
                    "source_files": list(schema.get("source_files", [])),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        best = candidates[0] if candidates else None
        warnings: list[str] = []
        if best is None:
            return SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["schema_not_found"]), candidates

        if best["score"] < 0.35:
            warnings.append("weak_schema_match")

        schema = next((item for item in self.schemas if item.get("schema_id") == best["matched_schema_id"]), None)
        if schema:
            expected_titles = {
                normalize_for_match(section.get("title", ""))
                for section in schema.get("sections", [])
                if section.get("title")
            }
            missing_titles = sorted(title for title in expected_titles if title and title not in extracted_titles)
            if missing_titles:
                warnings.append(f"missing_expected_sections:{len(missing_titles)}")
            sentinel = schema.get("sentinel") or {}
            last_section = normalize_for_match(sentinel.get("last_section", ""))
            last_label = normalize_for_match(sentinel.get("last_label", ""))
            if last_section and last_section not in extracted_titles:
                warnings.append("schema_sentinel_section_missing")
            if last_label and last_label not in extracted_labels:
                warnings.append("schema_sentinel_label_missing")

        return (
            SchemaMatchResult(
                matched_schema_id=best["matched_schema_id"],
                matched_sub_category=best.get("matched_sub_category") or taxonomy_sub_category,
                score=best["score"],
                warnings=warnings,
            ),
            candidates[:5],
        )
