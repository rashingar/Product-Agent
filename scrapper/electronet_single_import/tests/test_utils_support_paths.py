from electronet_single_import.repo_paths import (
    CATALOG_TAXONOMY_PATH,
    CHARACTERISTICS_TEMPLATES_PATH,
    COMPACT_RESPONSE_SCHEMA_PATH,
    DIFFERENTIATOR_PRIORITY_MAP_PATH,
    FILTER_MAP_PATH,
    MANUFACTURER_SOURCE_MAP_PATH,
    MASTER_PROMPT_PATH,
    NAME_RULES_PATH,
    PRESENTATION_TEMPLATE_PATH,
    PRODUCT_TEMPLATE_PATH,
    REPO_ROOT,
    SCHEMA_LIBRARY_PATH,
    SCHEMA_INDEX_PATH,
    TAXONOMY_MAPPING_TEMPLATE_PATH,
)


def test_support_files_resolve_from_repo_root() -> None:
    assert REPO_ROOT.name == "Product-Agent"
    assert PRODUCT_TEMPLATE_PATH.exists()
    assert PRESENTATION_TEMPLATE_PATH.exists()
    assert CATALOG_TAXONOMY_PATH.exists()
    assert SCHEMA_LIBRARY_PATH.exists()
    assert CHARACTERISTICS_TEMPLATES_PATH.exists()
    assert FILTER_MAP_PATH.exists()
    assert NAME_RULES_PATH.exists()
    assert DIFFERENTIATOR_PRIORITY_MAP_PATH.exists()
    assert MASTER_PROMPT_PATH.exists()
    assert COMPACT_RESPONSE_SCHEMA_PATH.exists()
    assert MANUFACTURER_SOURCE_MAP_PATH.exists()
    assert SCHEMA_INDEX_PATH.exists()
    assert TAXONOMY_MAPPING_TEMPLATE_PATH.exists()
