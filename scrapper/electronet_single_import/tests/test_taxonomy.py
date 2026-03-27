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


def test_taxonomy_resolution_maps_koptiria_ravdomplenter_to_exact_subcategory() -> None:
    resolver = TaxonomyResolver()
    resolution, _ = resolver.resolve(
        breadcrumbs=["Αρχική", "Εξοπλισμός Σπιτιού", "Συσκευές Κουζίνας", "Κοπτήρια - Ραβδομπλέντερ"],
        url="https://www.electronet.gr/exoplismos-spitioy/syskeyes-koyzinas/koptiria-rabdomplenter/example",
        name="Πολυκόπτης Tefal Fresh Express DN853B Γκρι",
        key_specs=[],
        spec_sections=[],
    )

    assert resolution.sub_category == "Κοπτήρια-Ράβδοι"
    assert resolution.cta_url == "https://www.etranoulis.gr/oikiakos-eksoplismos/syskeues-kouzinas/kopthria-ravdoi"


def test_taxonomy_resolution_prefers_dryer_subcategory_for_singular_product_name() -> None:
    resolver = TaxonomyResolver()
    resolution, candidates = resolver.resolve(
        breadcrumbs=["Αρχική", "Οικιακές Συσκευές", "Πλυντήρια - Στεγνωτήρια", "Στεγνωτήρια"],
        url="https://www.electronet.gr/oikiakes-syskeyes/plyntiria-stegnotiria/stegnotiria/stegnotirio-royhon-lg-rhx5009twb-9-kg-b",
        name="Στεγνωτήριο ρούχων LG RHX5009TWB 9 kg B",
        key_specs=[],
        spec_sections=[],
    )

    assert resolution.sub_category == "Στεγνωτήρια Ρούχων"
    assert resolution.cta_url == "https://www.etranoulis.gr/oikiakes-syskeues/plynthria-stegnwthria/stegnwthria-rouxwn"
    assert candidates[0]["sub_category"] == "Στεγνωτήρια Ρούχων"
