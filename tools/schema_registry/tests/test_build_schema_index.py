from __future__ import annotations

from tools.schema_registry.build_schema_index import FIELDNAMES, build_rows


def test_build_schema_index_emits_deterministic_rows_with_stable_columns() -> None:
    payload = {
        "schemas": [
            {
                "schema_id": "b",
                "template_id": "beta",
                "authored_template_id": "beta_electronet_labels_v1",
                "category_path": "B > Category > -",
                "parent_category": "B",
                "leaf_category": "Category",
                "sub_category": None,
                "category_gr": "Category",
                "cta_map_key": "Category",
                "cta_url": "https://example.test/b",
                "template_status": "active",
                "match_mode": "direct_single",
                "fingerprint": "fingerprint-b",
                "source_template_file": "resources/templates/electronet/beta.json",
                "electronet_examples": ["https://example.test/product-b"],
                "n_sections": 2,
                "n_rows_total": 3,
                "sentinel": {"last_section": "Τέλος", "last_label": "Ετικέτα 3"},
            },
            {
                "schema_id": "a",
                "template_id": "alpha",
                "authored_template_id": "alpha_electronet_labels_v1",
                "category_path": "A > Category > -",
                "parent_category": "A",
                "leaf_category": "Category",
                "sub_category": None,
                "category_gr": "Category",
                "cta_map_key": "Category",
                "cta_url": "https://example.test/a",
                "template_status": "manual_only",
                "match_mode": "manual_only",
                "fingerprint": "fingerprint-a",
                "source_template_file": "resources/templates/electronet/alpha.json",
                "electronet_examples": [],
                "n_sections": 1,
                "n_rows_total": 1,
                "sentinel": {"last_section": "TODO", "last_label": "NEEDS_MANUAL_LABELS"},
            },
        ]
    }

    first = build_rows(payload)
    second = build_rows(payload)

    assert first == second
    assert list(first[0].keys()) == FIELDNAMES
    assert [row["schema_id"] for row in first] == ["a", "b"]


def test_build_schema_index_computes_sentinel_derived_fields_correctly() -> None:
    payload = {
        "schemas": [
            {
                "schema_id": "schema-1",
                "template_id": "demo",
                "authored_template_id": "demo_electronet_labels_v1",
                "category_path": "Demo > Path > -",
                "parent_category": "Demo",
                "leaf_category": "Path",
                "sub_category": "",
                "category_gr": "Path",
                "cta_map_key": "Path",
                "cta_url": "https://example.test/demo",
                "template_status": "active",
                "match_mode": "direct_single",
                "fingerprint": "fp",
                "source_template_file": "resources/templates/electronet/demo.json",
                "electronet_examples": ["https://example.test/example-1", "https://example.test/example-2"],
                "n_sections": 3,
                "n_rows_total": 8,
                "sentinel": {"last_section": "Τελική Ενότητα", "last_label": "Τελική Ετικέτα"},
            }
        ]
    }

    row = build_rows(payload)[0]

    assert row["last_section"] == "Τελική Ενότητα"
    assert row["last_label"] == "Τελική Ετικέτα"
    assert row["example_count"] == 2
    assert row["first_example"] == "https://example.test/example-1"
