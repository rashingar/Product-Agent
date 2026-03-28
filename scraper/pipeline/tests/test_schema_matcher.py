from pipeline.models import SpecItem, SpecSection
from pipeline.schema_matcher import SchemaMatcher


def test_schema_matching_scores_overlap() -> None:
    matcher = SchemaMatcher()
    sections = [
        SpecSection(
            section="Επισκόπηση Προϊόντος",
            items=[
                SpecItem("Τύπος Μπαταρίας", "Li-Ion"),
                SpecItem("Τάση Volt", "18,5"),
                SpecItem("Χρόνος Λειτουργίας σε Λεπτά", "45"),
            ],
        ),
        SpecSection(
            section="Γενικά Χαρακτηριστικά",
            items=[SpecItem("Χρώμα", "Κόκκινο")],
        ),
    ]
    result, candidates = matcher.match(sections, taxonomy_sub_category="Σκούπες Stick")
    assert result.matched_schema_id is not None
    assert result.score > 0.2
    assert candidates[0]["score"] >= candidates[-1]["score"]

