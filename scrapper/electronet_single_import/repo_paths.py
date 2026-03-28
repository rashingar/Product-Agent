from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

PRODUCT_TEMPLATE_PATH = REPO_ROOT / "product_import_template.csv"
PRESENTATION_TEMPLATE_PATH = REPO_ROOT / "TEMPLATE_presentation.html"
CATALOG_TAXONOMY_PATH = REPO_ROOT / "catalog_taxonomy.json"
SCHEMA_LIBRARY_PATH = REPO_ROOT / "electronet_schema_library.json"
CHARACTERISTICS_TEMPLATES_PATH = REPO_ROOT / "characteristics_templates.json"
FILTER_MAP_PATH = REPO_ROOT / "filter_map.json"
NAME_RULES_PATH = REPO_ROOT / "name_rules.json"
DIFFERENTIATOR_PRIORITY_MAP_PATH = REPO_ROOT / "differentiator_priority_map.csv"
MASTER_PROMPT_PATH = REPO_ROOT / "master_prompt+.txt"
COMPACT_RESPONSE_SCHEMA_PATH = REPO_ROOT / "schemas" / "compact_response.schema.json"
MANUFACTURER_SOURCE_MAP_PATH = REPO_ROOT / "MANUFACTURER_SOURCE_MAP.json"
SCHEMA_INDEX_PATH = REPO_ROOT / "schema_index.csv"
TAXONOMY_MAPPING_TEMPLATE_PATH = REPO_ROOT / "taxonomy_mapping_template.csv"
