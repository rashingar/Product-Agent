from __future__ import annotations

from tools.schema_registry.refresh_template_coverage import (
    ExpectedCategory,
    ObservedTemplate,
    assess_template_coverage,
    build_markdown_table,
)


def test_refresh_template_coverage_marks_statuses_and_is_deterministic() -> None:
    expected = [
        ExpectedCategory(
            key="Κατηγορία Α",
            label="Κατηγορία Α",
            parent_category="P1",
            leaf_category="L1",
            sub_category=None,
            category_path="P1 > L1 > -",
            cta_url="https://example.test/a",
        ),
        ExpectedCategory(
            key="Κατηγορία Β",
            label="Κατηγορία Β",
            parent_category="P1",
            leaf_category="L2",
            sub_category=None,
            category_path="P1 > L2 > -",
            cta_url="https://example.test/b",
        ),
        ExpectedCategory(
            key="Κατηγορία Γ",
            label="Κατηγορία Γ",
            parent_category="P1",
            leaf_category="L3",
            sub_category=None,
            category_path="P1 > L3 > -",
            cta_url="https://example.test/c",
        ),
    ]
    observed = [
        ObservedTemplate(
            template_id="active",
            template_file="active.json",
            category_path="P1 > L1 > -",
            template_status="active",
            examples=("https://example.test/product-a",),
        ),
        ObservedTemplate(
            template_id="manual",
            template_file="manual.json",
            category_path="P1 > L2 > -",
            template_status="manual_only",
            examples=(),
        ),
    ]

    first = assess_template_coverage(expected, observed)
    second = assess_template_coverage(expected, observed)

    assert first == second
    assert [row["Status"] for row in first] == ["OK", "NEEDS_MANUAL", "MISSING"]


def test_refresh_template_coverage_disambiguates_duplicate_leaf_labels_when_needed() -> None:
    expected = [
        ExpectedCategory(
            key="Android [ΤΗΛΕΦΩΝΙΑ > Smartphones]",
            label="Android",
            parent_category="ΤΗΛΕΦΩΝΙΑ",
            leaf_category="Smartphones",
            sub_category="Android",
            category_path="ΤΗΛΕΦΩΝΙΑ > Smartphones > Android",
            cta_url="https://example.test/android-phone",
        ),
        ExpectedCategory(
            key="Android [ΤΗΛΕΦΩΝΙΑ > Tablets]",
            label="Android",
            parent_category="ΤΗΛΕΦΩΝΙΑ",
            leaf_category="Tablets",
            sub_category="Android",
            category_path="ΤΗΛΕΦΩΝΙΑ > Tablets > Android",
            cta_url="https://example.test/android-tablet",
        ),
    ]
    observed = [
        ObservedTemplate(
            template_id="android_phone",
            template_file="android_phone.json",
            category_path="ΤΗΛΕΦΩΝΙΑ > Smartphones > Android",
            template_status="active",
            examples=("https://example.test/android-phone-1",),
        )
    ]

    rows = assess_template_coverage(expected, observed)
    markdown = build_markdown_table(rows)

    assert rows[0]["CTA Leaf Category"] == "Android [ΤΗΛΕΦΩΝΙΑ > Smartphones]"
    assert rows[1]["CTA Leaf Category"] == "Android [ΤΗΛΕΦΩΝΙΑ > Tablets]"
    assert rows[1]["Status"] == "MISSING"
    assert markdown == build_markdown_table(rows)
