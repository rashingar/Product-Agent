from pipeline.characteristics_pipeline import CharacteristicsTemplateRegistry
from pipeline.models import SchemaMatchResult, SourceProductData, TaxonomyResolution


ROBOT_VACUUM_SCHEMA_ID = "sha1:f8946b92f12cb64ac319de114c2e5c850d916b79"


def test_characteristics_registry_prefers_robot_vacuum_schema_for_skroutz() -> None:
    registry = CharacteristicsTemplateRegistry()
    source = SourceProductData(source_name="skroutz", name="Rowenta Robot Vacuum")
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκούπες Ρομπότ",
    )

    preferred_source_files = registry.preferred_schema_source_files(source, taxonomy)
    template = registry.select_template(
        source,
        taxonomy,
        schema_match=SchemaMatchResult(matched_schema_id=ROBOT_VACUUM_SCHEMA_ID, score=0.9),
    )

    assert preferred_source_files == ["skoypes_rompot.json"]
    assert template is not None
    assert template["matched_schema_id"] == ROBOT_VACUUM_SCHEMA_ID
    assert template["preferred_schema_source_files"] == ["skoypes_rompot.json"]
    assert template["template_source"] == "schema_library_with_custom_overrides"
    assert template["custom_template_id"] == "skroutz_robot_vacuum_v1"

