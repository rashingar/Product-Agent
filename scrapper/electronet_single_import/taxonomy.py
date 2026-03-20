from __future__ import annotations

from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from .models import SpecSection, TaxonomyResolution
from .normalize import normalize_for_match
from .utils import CATALOG_TAXONOMY_PATH, FILTER_MAP_PATH, dedupe_strings, read_json

ALIASES = {
    normalize_for_match("Εξοπλισμός Σπιτιού"): "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
    normalize_for_match("Οικιακές Συσκευές"): "ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
    normalize_for_match("Πλυντήρια Ρούχων Εμπρόσθιας Φόρτωσης"): "Πλυντήρια Ρούχων",
    normalize_for_match("Πλυντήρια Ρούχων Άνω Φόρτωσης"): "Πλυντήρια Ρούχων",
    normalize_for_match("Audio Home Systems"): "Audio Systems",
    normalize_for_match("Sound Bars - Docking Stations"): "Sound Bars",
    normalize_for_match("Σταθερά Dect"): "Σταθέρα",
    normalize_for_match("Εντοιχιζόμενες"): "Εντοιχιζόμενες Συσκευές",
    normalize_for_match("Σκούπα Stick"): "Σκούπες Stick",
}


class TaxonomyResolver:
    def __init__(self, taxonomy_path: str = str(CATALOG_TAXONOMY_PATH), filter_map_path: str = str(FILTER_MAP_PATH)) -> None:
        self.taxonomy = read_json(taxonomy_path)
        self.filter_map = read_json(filter_map_path)
        self.paths: list[dict[str, Any]] = self.taxonomy.get("paths", [])
        self.filter_rows: list[dict[str, Any]] = self.filter_map.get("subcategories", [])
        self.filter_by_path = {
            normalize_for_match(item.get("path", "")): item
            for item in self.filter_rows
            if item.get("path")
        }

    def resolve(
        self,
        breadcrumbs: list[str],
        url: str,
        name: str,
        key_specs: list[dict[str, Any]] | list[Any],
        spec_sections: list[SpecSection],
    ) -> tuple[TaxonomyResolution, list[dict[str, Any]]]:
        mapped_crumbs = [self._alias(item) for item in breadcrumbs]
        crumb_norms = [normalize_for_match(item) for item in mapped_crumbs if item]
        url_tokens = set(normalize_for_match(urlparse(url).path).split())
        name_tokens = set(normalize_for_match(name).split())
        spec_labels = {
            normalize_for_match(item.label)
            for section in spec_sections
            for item in section.items
            if item.label
        }

        candidates: list[dict[str, Any]] = []
        for candidate in self.paths:
            parent = candidate.get("parent_category") or ""
            leaf = candidate.get("leaf_category") or ""
            sub = candidate.get("sub_category")
            parent_norm = normalize_for_match(parent)
            leaf_norm = normalize_for_match(leaf)
            sub_norm = normalize_for_match(sub or "")
            candidate_path_norm = normalize_for_match(candidate.get("path", ""))
            score = 0.0
            reasons: list[str] = []

            if crumb_norms:
                if parent_norm and parent_norm in crumb_norms:
                    score += 3.0
                    reasons.append("parent_breadcrumb")
                if leaf_norm and leaf_norm in crumb_norms:
                    score += 4.0
                    reasons.append("leaf_breadcrumb")
                if sub_norm and sub_norm in crumb_norms:
                    score += 5.0
                    reasons.append("sub_breadcrumb")
                if len(crumb_norms) >= 3:
                    path_guess = normalize_for_match(" > ".join(mapped_crumbs[1:4]))
                    if path_guess and path_guess == candidate_path_norm:
                        score += 4.0
                        reasons.append("full_breadcrumb_path")

            candidate_url_tokens = set(normalize_for_match(candidate.get("url", "")).split())
            shared_url = len(url_tokens & candidate_url_tokens)
            if shared_url:
                score += min(shared_url * 0.5, 3.0)
                reasons.append("url_overlap")

            leaf_tokens = set(leaf_norm.split())
            sub_tokens = set(sub_norm.split()) if sub_norm else set()
            if leaf_tokens and leaf_tokens & name_tokens:
                score += 1.5
                reasons.append("leaf_name_overlap")
            if sub_tokens and sub_tokens & name_tokens:
                score += 2.0
                reasons.append("sub_name_overlap")

            filter_row = self.filter_by_path.get(candidate_path_norm)
            if filter_row:
                matched_filters = 0
                for filter_group in filter_row.get("filter_groups", []):
                    if normalize_for_match(filter_group) in spec_labels:
                        matched_filters += 1
                if matched_filters:
                    score += min(matched_filters * 0.25, 1.0)
                    reasons.append("filter_map_tiebreak")

            candidates.append(
                {
                    "parent_category": parent,
                    "leaf_category": leaf,
                    "sub_category": sub,
                    "taxonomy_path": candidate.get("path", ""),
                    "cta_url": candidate.get("cta_url") or candidate.get("url") or "",
                    "confidence": round(score, 4),
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        best = candidates[0] if candidates else None
        second = candidates[1] if len(candidates) > 1 else None
        if not best:
            return TaxonomyResolution(reason="no_candidates"), []

        delta = best["confidence"] - (second["confidence"] if second else 0.0)
        resolved = False
        if best["confidence"] >= 7.0:
            resolved = True
        elif best["confidence"] >= 5.0 and delta >= 1.5 and any(reason in best["reasons"] for reason in ["sub_breadcrumb", "full_breadcrumb_path"]):
            resolved = True
        elif best["confidence"] >= 4.5 and delta >= 2.0 and "leaf_breadcrumb" in best["reasons"]:
            resolved = True

        if not resolved:
            return TaxonomyResolution(confidence=best["confidence"], reason="low_confidence"), candidates[:5]

        return (
            TaxonomyResolution(
                parent_category=best["parent_category"],
                leaf_category=best["leaf_category"],
                sub_category=best.get("sub_category"),
                taxonomy_path=best.get("taxonomy_path", ""),
                cta_url=best.get("cta_url", ""),
                confidence=best["confidence"],
                reason=",".join(best["reasons"]),
            ),
            candidates[:5],
        )

    def serialize_category(self, resolution: TaxonomyResolution, boxnow: int = 0) -> str:
        if not resolution.parent_category or not resolution.leaf_category:
            return ""
        parent = resolution.parent_category
        leaf = resolution.leaf_category
        if resolution.sub_category:
            serialized = f"{parent}:::{parent}///{leaf}:::{parent}///{leaf}///{resolution.sub_category}"
        else:
            serialized = f"{parent}:::{parent}///{leaf}"
        if int(boxnow) == 1:
            serialized += ":::Μικροσυσκευές"
        return serialized

    def _alias(self, value: str) -> str:
        return ALIASES.get(normalize_for_match(value), value)
