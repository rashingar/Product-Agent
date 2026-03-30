from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCES_DIR = REPO_ROOT / "resources"
MAPPINGS_DIR = RESOURCES_DIR / "mappings"
SCHEMAS_DIR = RESOURCES_DIR / "schemas"
TEMPLATES_DIR = RESOURCES_DIR / "templates"
PROMPTS_DIR = RESOURCES_DIR / "prompts"

PRODUCT_TEMPLATE_PATH = TEMPLATES_DIR / "product_import_template.csv"
PRESENTATION_TEMPLATE_PATH = TEMPLATES_DIR / "TEMPLATE_presentation.html"
CATALOG_TAXONOMY_PATH = MAPPINGS_DIR / "catalog_taxonomy.json"
SCHEMA_LIBRARY_PATH = SCHEMAS_DIR / "electronet_schema_library.json"
CHARACTERISTICS_TEMPLATES_PATH = TEMPLATES_DIR / "characteristics_templates.json"
FILTER_MAP_PATH = MAPPINGS_DIR / "filter_map.json"
NAME_RULES_PATH = MAPPINGS_DIR / "name_rules.json"
DIFFERENTIATOR_PRIORITY_MAP_PATH = MAPPINGS_DIR / "differentiator_priority_map.csv"
INTRO_TEXT_PROMPT_PATH = PROMPTS_DIR / "intro_text_prompt.txt"
SEO_META_PROMPT_PATH = PROMPTS_DIR / "seo_meta_prompt.txt"
MANUFACTURER_SOURCE_MAP_PATH = MAPPINGS_DIR / "MANUFACTURER_SOURCE_MAP.json"
SCHEMA_INDEX_PATH = SCHEMAS_DIR / "schema_index.csv"
TAXONOMY_MAPPING_TEMPLATE_PATH = MAPPINGS_DIR / "taxonomy_mapping_template.csv"
