from electronet_single_import.utils import (
    CATALOG_TAXONOMY_PATH,
    FILTER_MAP_PATH,
    PRESENTATION_TEMPLATE_PATH,
    PRODUCT_TEMPLATE_PATH,
    REPO_ROOT,
    RULES_PATH,
    SCHEMA_LIBRARY_PATH,
)


def test_support_files_resolve_from_repo_root() -> None:
    assert REPO_ROOT.name == "Product-Agent"
    assert PRODUCT_TEMPLATE_PATH.exists()
    assert RULES_PATH.exists()
    assert PRESENTATION_TEMPLATE_PATH.exists()
    assert CATALOG_TAXONOMY_PATH.exists()
    assert SCHEMA_LIBRARY_PATH.exists()
    assert FILTER_MAP_PATH.exists()
