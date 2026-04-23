import json

from pipeline.repo_paths import (
    CATALOG_TAXONOMY_PATH,
    CHARACTERISTICS_TEMPLATES_PATH,
    DIFFERENTIATOR_PRIORITY_MAP_PATH,
    FILTER_MAP_PATH,
    INTRO_TEXT_PROMPT_PATH,
    MANUFACTURER_SOURCE_MAP_PATH,
    NAME_RULES_PATH,
    PRESENTATION_TEMPLATE_PATH,
    PRODUCT_TEMPLATE_PATH,
    REPO_ROOT,
    SCHEMA_LIBRARY_PATH,
    SCHEMA_INDEX_PATH,
    SCHEMA_POLICY_RULES_PATH,
    SEO_META_PROMPT_PATH,
    TAXONOMY_MAPPING_TEMPLATE_PATH,
)


def test_support_files_resolve_from_resources_layout() -> None:
    assert REPO_ROOT.name == "Product-Agent"
    expected_paths = [
        (PRODUCT_TEMPLATE_PATH, REPO_ROOT / "resources" / "templates" / "product_import_template.csv"),
        (PRESENTATION_TEMPLATE_PATH, REPO_ROOT / "resources" / "templates" / "TEMPLATE_presentation.html"),
        (CATALOG_TAXONOMY_PATH, REPO_ROOT / "resources" / "mappings" / "catalog_taxonomy.json"),
        (SCHEMA_LIBRARY_PATH, REPO_ROOT / "resources" / "schemas" / "electronet_schema_library.json"),
        (
            CHARACTERISTICS_TEMPLATES_PATH,
            REPO_ROOT / "resources" / "templates" / "characteristics_templates.json",
        ),
        (FILTER_MAP_PATH, REPO_ROOT / "resources" / "mappings" / "filter_map.json"),
        (NAME_RULES_PATH, REPO_ROOT / "resources" / "mappings" / "name_rules.json"),
        (
            SCHEMA_POLICY_RULES_PATH,
            REPO_ROOT / "resources" / "mappings" / "schema_policy_rules.json",
        ),
        (
            DIFFERENTIATOR_PRIORITY_MAP_PATH,
            REPO_ROOT / "resources" / "mappings" / "differentiator_priority_map.csv",
        ),
        (INTRO_TEXT_PROMPT_PATH, REPO_ROOT / "resources" / "prompts" / "intro_text_prompt.txt"),
        (SEO_META_PROMPT_PATH, REPO_ROOT / "resources" / "prompts" / "seo_meta_prompt.txt"),
        (
            MANUFACTURER_SOURCE_MAP_PATH,
            REPO_ROOT / "resources" / "mappings" / "MANUFACTURER_SOURCE_MAP.json",
        ),
        (SCHEMA_INDEX_PATH, REPO_ROOT / "resources" / "schemas" / "schema_index.csv"),
        (
            TAXONOMY_MAPPING_TEMPLATE_PATH,
            REPO_ROOT / "resources" / "mappings" / "taxonomy_mapping_template.csv",
        ),
    ]
    for actual_path, expected_path in expected_paths:
        assert actual_path == expected_path
        assert actual_path.exists()


def test_kouzines_emagie_filter_map_has_expected_category_filters() -> None:
    filter_map = json.loads(FILTER_MAP_PATH.read_text(encoding="utf-8"))
    expected = ["Τύπος φούρνου", "Ενεργειακή Κλάση", "Χρώμα", "Χωρητικότητα Φούρνου"]

    subcategory_row = next(row for row in filter_map["subcategories"] if row["key"] == "Κουζίνες Εμαγιέ")

    assert subcategory_row["filter_groups"] == expected
    assert filter_map["by_sub_category_key"]["Κουζίνες Εμαγιέ"]["filter_groups"] == expected

