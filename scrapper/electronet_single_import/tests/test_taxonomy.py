from electronet_single_import.models import TaxonomyResolution
from electronet_single_import.taxonomy import TaxonomyResolver


def test_taxonomy_serialization() -> None:
    resolver = TaxonomyResolver()
    resolution = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκούπες Stick",
    )
    assert resolver.serialize_category(resolution, 0) == (
        "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ:::ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ///Σκούπισμα:::"
        "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ///Σκούπισμα///Σκούπες Stick"
    )
    assert resolver.serialize_category(resolution, 1).endswith(":::Μικροσυσκευές")


def test_taxonomy_resolution_prefers_breadcrumb_match() -> None:
    resolver = TaxonomyResolver()
    resolution, candidates = resolver.resolve(
        breadcrumbs=["Αρχική", "Εξοπλισμός Σπιτιού", "Σκούπισμα", "Σκούπες Stick"],
        url="https://www.electronet.gr/exoplismos-spitioy/skoypisma/skoypes-stick/example",
        name="Σκούπα Stick Rowenta X-Force",
        key_specs=[],
        spec_sections=[],
    )
    assert resolution.parent_category == "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ"
    assert resolution.leaf_category == "Σκούπισμα"
    assert resolution.sub_category == "Σκούπες Stick"
    assert candidates[0]["confidence"] >= candidates[-1]["confidence"]
