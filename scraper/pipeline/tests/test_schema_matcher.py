import json
from pathlib import Path

from pipeline.models import SpecItem, SpecSection
from pipeline.normalize import normalize_for_match
from pipeline.schema_matcher import SchemaMatcher


def _write_schema_library(tmp_path: Path, schemas: list[dict[str, object]]) -> Path:
    path = tmp_path / "schema_library.json"
    path.write_text(json.dumps({"schemas": schemas}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _schema(
    *,
    schema_id: str,
    template_id: str,
    category_path: str,
    parent_category: str,
    leaf_category: str,
    sub_category: str | None,
    sections: list[tuple[str, list[str]]],
    template_status: str = "active",
    match_mode: str = "direct_single",
    sibling_template_ids: list[str] | None = None,
    required_labels_any: list[str] | None = None,
    required_labels_all: list[str] | None = None,
    forbidden_labels: list[str] | None = None,
    min_section_overlap: int = 1,
    min_label_overlap: int = 1,
) -> dict[str, object]:
    label_set_exact = _preserve_order([label for _section, labels in sections for label in labels])
    section_names_normalized = [normalize_for_match(section) for section, _labels in sections]
    label_set_normalized = [normalize_for_match(label) for label in label_set_exact]
    section_label_pairs_normalized = _preserve_order(
        [
            normalize_for_match(f"{section} || {label}")
            for section, labels in sections
            for label in labels
        ]
    )
    return {
        "schema_id": schema_id,
        "template_id": template_id,
        "category_path": category_path,
        "parent_category": parent_category,
        "leaf_category": leaf_category,
        "sub_category": sub_category,
        "template_status": template_status,
        "match_mode": match_mode,
        "section_names_exact": [section for section, _labels in sections],
        "section_names_normalized": section_names_normalized,
        "label_set_exact": label_set_exact,
        "label_set_normalized": label_set_normalized,
        "section_label_pairs_normalized": section_label_pairs_normalized,
        "discriminator_labels": [],
        "required_labels_any": [normalize_for_match(label) for label in (required_labels_any or [])],
        "required_labels_all": [normalize_for_match(label) for label in (required_labels_all or [])],
        "forbidden_labels": [normalize_for_match(label) for label in (forbidden_labels or [])],
        "min_section_overlap": min_section_overlap,
        "min_label_overlap": min_label_overlap,
        "sibling_template_ids": list(sibling_template_ids or []),
        "n_sections": len(sections),
        "n_rows_total": sum(len(labels) for _section, labels in sections),
        "sections": [{"title": section, "labels": labels} for section, labels in sections],
        "sentinel": {},
        "source_files": [f"{template_id}.json"],
    }


def _spec_sections(*sections: tuple[str, list[str]]) -> list[SpecSection]:
    return [
        SpecSection(section=section, items=[SpecItem(label=label, value="x") for label in labels])
        for section, labels in sections
    ]


def test_direct_single_category_selects_only_active_safe_template(tmp_path: Path) -> None:
    schema_path = _write_schema_library(
        tmp_path,
        [
            _schema(
                schema_id="wm-1",
                template_id="washing_machine_active",
                category_path="Home > Laundry > Washing Machines",
                parent_category="Home",
                leaf_category="Laundry",
                sub_category="Washing Machines",
                sections=[
                    ("Overview", ["Capacity", "Spin Speed"]),
                    ("Programs", ["Steam Program", "Delay End"]),
                ],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="wm-manual",
                template_id="washing_machine_manual",
                category_path="Home > Laundry > Washing Machines",
                parent_category="Home",
                leaf_category="Laundry",
                sub_category="Washing Machines",
                sections=[("TODO", ["Needs Manual Labels"])],
                template_status="manual_only",
                match_mode="manual_only",
            ),
            _schema(
                schema_id="wm-deprecated",
                template_id="washing_machine_deprecated",
                category_path="Home > Laundry > Washing Machines",
                parent_category="Home",
                leaf_category="Laundry",
                sub_category="Washing Machines",
                sections=[("Overview", ["Old Capacity"])],
                template_status="deprecated",
                match_mode="manual_only",
            ),
            _schema(
                schema_id="toaster-1",
                template_id="toaster",
                category_path="Home > Small Appliances > Toasters",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Toasters",
                sections=[("Overview", ["Slots", "Power"])],
            ),
        ],
    )
    matcher = SchemaMatcher(str(schema_path))

    result, candidates = matcher.match(
        _spec_sections(
            ("Overview", ["Capacity", "Spin Speed"]),
            ("Programs", ["Steam Program", "Delay End"]),
        ),
        taxonomy_sub_category="Washing Machines",
        taxonomy_path="Home > Laundry > Washing Machines",
        taxonomy_parent_category="Home",
        taxonomy_leaf_category="Laundry",
    )

    assert result.matched_schema_id == "wm-1"
    assert result.score == 1.0
    assert "weak_schema_match" not in result.warnings
    assert candidates == [
        {
            "matched_schema_id": "wm-1",
            "template_id": "washing_machine_active",
            "matched_sub_category": "Washing Machines",
            "category_path": "Home > Laundry > Washing Machines",
            "template_status": "active",
            "match_mode": "direct_single",
            "score": 1.0,
            "section_overlap": 2,
            "label_overlap": 4,
            "pair_overlap": 4,
            "discriminator_overlap": 0,
            "gate_status": "bypassed_direct_single",
            "gate_reasons": [],
            "n_sections": 2,
            "n_rows_total": 4,
            "source_files": ["washing_machine_active.json"],
        }
    ]


def test_category_pool_compares_only_sibling_templates(tmp_path: Path) -> None:
    schema_path = _write_schema_library(
        tmp_path,
        [
            _schema(
                schema_id="kettle-basic",
                template_id="kettle_basic",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Cordless"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_glass"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="kettle-glass",
                template_id="kettle_glass",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Glass Body", "Temperature Control"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_basic"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="toaster-1",
                template_id="toaster",
                category_path="Home > Small Appliances > Toasters",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Toasters",
                sections=[
                    ("Overview", ["Power", "Color", "Crumb Tray"]),
                    ("Features", ["Defrost"]),
                ],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
        ],
    )
    matcher = SchemaMatcher(str(schema_path))

    result, candidates = matcher.match(
        _spec_sections(
            ("Overview", ["Capacity", "Power", "Color"]),
            ("Features", ["Glass Body", "Temperature Control"]),
        ),
        taxonomy_sub_category="Kettles",
        taxonomy_path="Home > Small Appliances > Kettles",
        taxonomy_parent_category="Home",
        taxonomy_leaf_category="Small Appliances",
    )

    assert result.matched_schema_id == "kettle-glass"
    assert {candidate["matched_schema_id"] for candidate in candidates} == {"kettle-basic", "kettle-glass"}
    assert all(candidate["category_path"] == "Home > Small Appliances > Kettles" for candidate in candidates)


def test_wrong_category_schema_cannot_be_selected(tmp_path: Path) -> None:
    schema_path = _write_schema_library(
        tmp_path,
        [
            _schema(
                schema_id="wm-1",
                template_id="washing_machine_active",
                category_path="Home > Laundry > Washing Machines",
                parent_category="Home",
                leaf_category="Laundry",
                sub_category="Washing Machines",
                sections=[
                    ("Overview", ["Capacity", "Spin Speed"]),
                    ("Programs", ["Steam Program", "Delay End"]),
                ],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="kettle-basic",
                template_id="kettle_basic",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Cordless"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_glass"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="kettle-glass",
                template_id="kettle_glass",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Glass Body", "Temperature Control"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_basic"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
        ],
    )
    matcher = SchemaMatcher(str(schema_path))

    result, candidates = matcher.match(
        _spec_sections(
            ("Overview", ["Spin Speed", "Drum Size"]),
            ("Programs", ["Steam Program", "Delay End"]),
        ),
        taxonomy_sub_category="Kettles",
        taxonomy_path="Home > Small Appliances > Kettles",
        taxonomy_parent_category="Home",
        taxonomy_leaf_category="Small Appliances",
    )

    assert result.matched_schema_id is None
    assert result.warnings == ["no_safe_template_match"]
    assert {candidate["matched_schema_id"] for candidate in candidates} == {"kettle-basic", "kettle-glass"}
    assert "wm-1" not in {candidate["matched_schema_id"] for candidate in candidates}


def test_generic_overlap_fails_closed_instead_of_global_drift(tmp_path: Path) -> None:
    schema_path = _write_schema_library(
        tmp_path,
        [
            _schema(
                schema_id="kettle-basic",
                template_id="kettle_basic",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Cordless"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_glass"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=3,
            ),
            _schema(
                schema_id="kettle-glass",
                template_id="kettle_glass",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Glass Body", "Temperature Control"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_basic"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=3,
            ),
            _schema(
                schema_id="wm-1",
                template_id="washing_machine_active",
                category_path="Home > Laundry > Washing Machines",
                parent_category="Home",
                leaf_category="Laundry",
                sub_category="Washing Machines",
                sections=[
                    ("Overview", ["Capacity", "Spin Speed"]),
                    ("Programs", ["Steam Program", "Delay End"]),
                ],
            ),
        ],
    )
    matcher = SchemaMatcher(str(schema_path))

    result, candidates = matcher.match(
        _spec_sections(("Overview", ["Power", "Color"])),
        taxonomy_sub_category="Kettles",
        taxonomy_path="Home > Small Appliances > Kettles",
        taxonomy_parent_category="Home",
        taxonomy_leaf_category="Small Appliances",
    )

    assert result.matched_schema_id is None
    assert result.warnings == ["no_safe_template_match"]
    assert {candidate["matched_schema_id"] for candidate in candidates} == {"kettle-basic", "kettle-glass"}
    assert all(candidate["gate_status"] == "failed" for candidate in candidates)


def test_washing_machine_like_specs_cannot_select_small_appliance_template(tmp_path: Path) -> None:
    schema_path = _write_schema_library(
        tmp_path,
        [
            _schema(
                schema_id="kettle-basic",
                template_id="kettle_basic",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Capacity", "Power", "Color"]),
                    ("Features", ["Cordless"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["toaster-1"],
                required_labels_any=["Capacity"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
            _schema(
                schema_id="toaster-1",
                template_id="toaster",
                category_path="Home > Small Appliances > Kettles",
                parent_category="Home",
                leaf_category="Small Appliances",
                sub_category="Kettles",
                sections=[
                    ("Overview", ["Power", "Color", "Slots"]),
                    ("Features", ["Defrost"]),
                ],
                match_mode="category_pool",
                sibling_template_ids=["kettle_basic"],
                required_labels_any=["Power"],
                min_section_overlap=1,
                min_label_overlap=2,
            ),
        ],
    )
    matcher = SchemaMatcher(str(schema_path))

    result, candidates = matcher.match(
        _spec_sections(
            ("Overview", ["Spin Speed", "Drum Size"]),
            ("Programs", ["Steam Program", "Delay End", "Child Lock"]),
        ),
        taxonomy_sub_category="Kettles",
        taxonomy_path="Home > Small Appliances > Kettles",
        taxonomy_parent_category="Home",
        taxonomy_leaf_category="Small Appliances",
    )

    assert result.matched_schema_id is None
    assert result.warnings == ["no_safe_template_match"]
    assert {candidate["matched_schema_id"] for candidate in candidates} == {"kettle-basic", "toaster-1"}
