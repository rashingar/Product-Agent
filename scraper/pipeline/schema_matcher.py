from __future__ import annotations

from typing import Any

from .models import SchemaMatchResult, SpecSection
from .normalize import normalize_for_match
from .repo_paths import SCHEMA_LIBRARY_PATH
from .utils import read_json


class SchemaMatcher:
    def __init__(self, schema_path: str = str(SCHEMA_LIBRARY_PATH)) -> None:
        self.schema_path = schema_path
        self.payload = read_json(schema_path)
        self.schemas: list[dict[str, Any]] = self.payload.get("schemas", [])
        self.schemas_by_id: dict[str, dict[str, Any]] = {
            str(schema.get("schema_id", "")).strip(): schema
            for schema in self.schemas
            if str(schema.get("schema_id", "")).strip()
        }
        self.schemas_by_category_path: dict[str, list[dict[str, Any]]] = {}
        self.schemas_by_parent_leaf: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for schema in self.schemas:
            category_key = normalize_for_match(schema.get("category_path", ""))
            if category_key:
                self.schemas_by_category_path.setdefault(category_key, []).append(schema)
            parent_leaf_key = self._parent_leaf_key(
                schema.get("parent_category"),
                schema.get("leaf_category"),
            )
            if parent_leaf_key is not None:
                self.schemas_by_parent_leaf.setdefault(parent_leaf_key, []).append(schema)
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
        taxonomy_path: str | None = None,
        taxonomy_parent_category: str | None = None,
        taxonomy_leaf_category: str | None = None,
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
        extracted_pairs = {
            normalize_for_match(f"{section.section} || {item.label}")
            for section in spec_sections
            for item in section.items
            if section.section and item.label
        }
        category_pool = self.build_candidate_pool(
            taxonomy_sub_category=taxonomy_sub_category,
            taxonomy_path=taxonomy_path,
            taxonomy_parent_category=taxonomy_parent_category,
            taxonomy_leaf_category=taxonomy_leaf_category,
            preferred_source_files=preferred_source_files or [],
        )
        if not category_pool:
            return SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["no_safe_template_match"]), []

        safe_templates, inactive_candidates = self.filter_inactive_templates(category_pool)
        if not safe_templates:
            return SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["no_safe_template_match"]), inactive_candidates[:5]

        if len(safe_templates) == 1:
            selected = safe_templates[0]
            diagnostics = [
                self._candidate_record(
                    selected,
                    extracted_titles=extracted_titles,
                    extracted_labels=extracted_labels,
                    extracted_pairs=extracted_pairs,
                    score=1.0,
                    gate_status="bypassed_direct_single",
                    gate_reasons=[],
                )
            ]
            return self.select_safe_template(
                selected,
                diagnostics,
                extracted_titles=extracted_titles,
                extracted_labels=extracted_labels,
                taxonomy_sub_category=taxonomy_sub_category,
                score=1.0,
            )

        gated_templates, gated_candidates = self.apply_hard_gates(
            safe_templates,
            extracted_titles=extracted_titles,
            extracted_labels=extracted_labels,
            extracted_pairs=extracted_pairs,
        )
        if not gated_templates:
            gated_candidates.sort(key=self._candidate_sort_key)
            return (
                SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["no_safe_template_match"]),
                gated_candidates[:5],
            )

        scored_candidates = self.score_sibling_candidates(
            gated_templates,
            extracted_titles=extracted_titles,
            extracted_labels=extracted_labels,
            extracted_pairs=extracted_pairs,
        )
        selected = self.schemas_by_id.get(str(scored_candidates[0]["matched_schema_id"]).strip())
        if selected is None:
            return SchemaMatchResult(None, taxonomy_sub_category, 0.0, ["no_safe_template_match"]), scored_candidates[:5]
        return self.select_safe_template(
            selected,
            scored_candidates,
            extracted_titles=extracted_titles,
            extracted_labels=extracted_labels,
            taxonomy_sub_category=taxonomy_sub_category,
            score=float(scored_candidates[0]["score"]),
        )

    def build_candidate_pool(
        self,
        *,
        taxonomy_sub_category: str | None,
        taxonomy_path: str | None,
        taxonomy_parent_category: str | None,
        taxonomy_leaf_category: str | None,
        preferred_source_files: list[str],
    ) -> list[dict[str, Any]]:
        normalized_taxonomy_path = normalize_for_match(taxonomy_path)
        if not normalized_taxonomy_path and taxonomy_parent_category and taxonomy_leaf_category:
            normalized_taxonomy_path = self._normalize_category_path(
                taxonomy_parent_category,
                taxonomy_leaf_category,
                taxonomy_sub_category,
            )

        pool = list(self.schemas_by_category_path.get(normalized_taxonomy_path, [])) if normalized_taxonomy_path else []
        if not pool and taxonomy_parent_category and taxonomy_leaf_category and taxonomy_sub_category:
            pool = self._leaf_only_candidates(taxonomy_parent_category, taxonomy_leaf_category)

        if not pool:
            return []

        normalized_preferred_files = {
            normalize_for_match(item)
            for item in preferred_source_files
            if normalize_for_match(item)
        }
        if not normalized_preferred_files:
            return pool

        preferred_pool = [
            schema
            for schema in pool
            if normalized_preferred_files & self._normalized_source_files(schema)
        ]
        return preferred_pool or pool

    def filter_inactive_templates(self, candidate_pool: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        safe_templates: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for schema in candidate_pool:
            template_status = normalize_for_match(schema.get("template_status", ""))
            if template_status == "active":
                safe_templates.append(schema)
                continue
            diagnostics.append(
                self._candidate_record(
                    schema,
                    extracted_titles=set(),
                    extracted_labels=set(),
                    extracted_pairs=set(),
                    score=0.0,
                    gate_status="inactive",
                    gate_reasons=[f"template_status:{schema.get('template_status', '') or 'unknown'}"],
                )
            )
        diagnostics.sort(key=self._candidate_sort_key)
        return safe_templates, diagnostics

    def apply_hard_gates(
        self,
        candidates: list[dict[str, Any]],
        *,
        extracted_titles: set[str],
        extracted_labels: set[str],
        extracted_pairs: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        passed: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for schema in candidates:
            section_overlap = len(extracted_titles & set(schema.get("section_names_normalized", [])))
            label_overlap = len(extracted_labels & set(schema.get("label_set_normalized", [])))
            gate_reasons: list[str] = []
            required_any = set(schema.get("required_labels_any", []))
            required_all = set(schema.get("required_labels_all", []))
            forbidden = set(schema.get("forbidden_labels", []))

            if required_all and not required_all <= extracted_labels:
                gate_reasons.append("missing_required_labels_all")
            if required_any and not (required_any & extracted_labels):
                gate_reasons.append("missing_required_labels_any")
            if forbidden and (forbidden & extracted_labels):
                gate_reasons.append("forbidden_labels_present")
            if section_overlap < int(schema.get("min_section_overlap") or 0):
                gate_reasons.append("min_section_overlap")
            if label_overlap < int(schema.get("min_label_overlap") or 0):
                gate_reasons.append("min_label_overlap")

            diagnostics.append(
                self._candidate_record(
                    schema,
                    extracted_titles=extracted_titles,
                    extracted_labels=extracted_labels,
                    extracted_pairs=extracted_pairs,
                    score=0.0,
                    gate_status="passed" if not gate_reasons else "failed",
                    gate_reasons=gate_reasons,
                )
            )
            if not gate_reasons:
                passed.append(schema)

        diagnostics.sort(key=self._candidate_sort_key)
        return passed, diagnostics

    def score_sibling_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        extracted_titles: set[str],
        extracted_labels: set[str],
        extracted_pairs: set[str],
    ) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        for schema in candidates:
            section_names = set(schema.get("section_names_normalized", []))
            labels = set(schema.get("label_set_normalized", []))
            section_label_pairs = set(schema.get("section_label_pairs_normalized", []))
            discriminator_labels = set(schema.get("discriminator_labels", []))

            section_overlap = len(extracted_titles & section_names)
            label_overlap = len(extracted_labels & labels)
            pair_overlap = len(extracted_pairs & section_label_pairs)
            discriminator_overlap = len(extracted_labels & discriminator_labels)

            section_ratio = section_overlap / max(len(section_names), 1)
            label_ratio = label_overlap / max(len(labels), 1)
            pair_ratio = pair_overlap / max(len(section_label_pairs), 1)
            discriminator_ratio = discriminator_overlap / max(len(discriminator_labels), 1)
            score = (0.2 * section_ratio) + (0.3 * label_ratio) + (0.4 * pair_ratio) + (0.1 * discriminator_ratio)

            scored.append(
                self._candidate_record(
                    schema,
                    extracted_titles=extracted_titles,
                    extracted_labels=extracted_labels,
                    extracted_pairs=extracted_pairs,
                    score=score,
                    gate_status="passed",
                    gate_reasons=[],
                )
            )

        scored.sort(key=self._candidate_sort_key)
        return scored

    def select_safe_template(
        self,
        schema: dict[str, Any],
        candidates: list[dict[str, Any]],
        *,
        extracted_titles: set[str],
        extracted_labels: set[str],
        taxonomy_sub_category: str | None,
        score: float,
    ) -> tuple[SchemaMatchResult, list[dict[str, Any]]]:
        warnings: list[str] = []
        if len(candidates) > 1 and score < 0.35:
            warnings.append("weak_schema_match")
        warnings.extend(self._selection_warnings(schema, extracted_titles=extracted_titles, extracted_labels=extracted_labels))
        return (
            SchemaMatchResult(
                matched_schema_id=str(schema.get("schema_id", "")).strip() or None,
                matched_sub_category=schema.get("sub_category") or taxonomy_sub_category,
                score=round(score, 4),
                warnings=warnings,
            ),
            candidates[:5],
        )

    def _candidate_record(
        self,
        schema: dict[str, Any],
        *,
        extracted_titles: set[str],
        extracted_labels: set[str],
        extracted_pairs: set[str],
        score: float,
        gate_status: str,
        gate_reasons: list[str],
    ) -> dict[str, Any]:
        section_names = set(schema.get("section_names_normalized", []))
        labels = set(schema.get("label_set_normalized", []))
        section_label_pairs = set(schema.get("section_label_pairs_normalized", []))
        discriminator_labels = set(schema.get("discriminator_labels", []))
        section_overlap = len(extracted_titles & section_names)
        label_overlap = len(extracted_labels & labels)
        pair_overlap = len(extracted_pairs & section_label_pairs)
        discriminator_overlap = len(extracted_labels & discriminator_labels)
        return {
            "matched_schema_id": schema.get("schema_id"),
            "template_id": schema.get("template_id"),
            "matched_sub_category": schema.get("sub_category"),
            "category_path": schema.get("category_path", ""),
            "template_status": schema.get("template_status", ""),
            "match_mode": schema.get("match_mode", ""),
            "score": round(score, 4),
            "section_overlap": section_overlap,
            "label_overlap": label_overlap,
            "pair_overlap": pair_overlap,
            "discriminator_overlap": discriminator_overlap,
            "gate_status": gate_status,
            "gate_reasons": gate_reasons,
            "n_sections": schema.get("n_sections"),
            "n_rows_total": schema.get("n_rows_total"),
            "source_files": list(schema.get("source_files", [])),
        }

    def _selection_warnings(
        self,
        schema: dict[str, Any],
        *,
        extracted_titles: set[str],
        extracted_labels: set[str],
    ) -> list[str]:
        warnings: list[str] = []
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
        return warnings

    def _leaf_only_candidates(self, parent_category: str | None, leaf_category: str | None) -> list[dict[str, Any]]:
        parent_leaf_key = self._parent_leaf_key(parent_category, leaf_category)
        if parent_leaf_key is None:
            return []
        return [
            schema
            for schema in self.schemas_by_parent_leaf.get(parent_leaf_key, [])
            if not normalize_for_match(schema.get("sub_category", ""))
        ]

    def _normalized_source_files(self, schema: dict[str, Any]) -> set[str]:
        return {
            normalize_for_match(source_file)
            for source_file in schema.get("source_files", [])
            if normalize_for_match(source_file)
        }

    def _normalize_category_path(
        self,
        parent_category: str | None,
        leaf_category: str | None,
        sub_category: str | None,
    ) -> str:
        parent = str(parent_category or "").strip()
        leaf = str(leaf_category or "").strip()
        if not parent or not leaf:
            return ""
        return normalize_for_match(f"{parent} > {leaf} > {sub_category or '-'}")

    def _parent_leaf_key(self, parent_category: str | None, leaf_category: str | None) -> tuple[str, str] | None:
        parent = normalize_for_match(parent_category)
        leaf = normalize_for_match(leaf_category)
        if not parent or not leaf:
            return None
        return parent, leaf

    def _candidate_sort_key(self, item: dict[str, Any]) -> tuple[float, int, int, int, int, str]:
        return (
            -float(item.get("score", 0.0)),
            -int(item.get("pair_overlap", 0)),
            -int(item.get("label_overlap", 0)),
            -int(item.get("section_overlap", 0)),
            -int(item.get("discriminator_overlap", 0)),
            str(item.get("template_id", "")),
        )
