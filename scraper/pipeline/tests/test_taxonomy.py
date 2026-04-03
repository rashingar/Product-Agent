from pipeline.models import TaxonomyResolution
from pipeline.models import SpecItem, SpecSection
from pipeline.taxonomy import TaxonomyResolver


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


def test_taxonomy_resolution_prefers_television_size_bucket_for_50_inches() -> None:
    resolver = TaxonomyResolver()
    resolution, candidates = resolver.resolve(
        breadcrumbs=["Αρχική", "Εικόνα - Ήχος", "Τηλεοράσεις", "Όλες οι Τηλεοράσεις"],
        url="https://www.electronet.gr/eikona-ihos/tileoraseis/oles-oi-tileoraseis/tv-samsung-qe50qn80f-50-smart-4k-mini-led-ai",
        name="TV Samsung QE50QN80F 50'' Smart 4K Mini LED AI",
        key_specs=[SpecItem(label="Διαγώνιος Οθόνης ( Ίντσες )", value="50")],
        spec_sections=[
            SpecSection(
                section="Εικόνα - Ήχος",
                items=[SpecItem(label="Διαγώνιος Οθόνης ( Ίντσες )", value="50")],
            )
        ],
    )

    assert resolution.parent_category == "ΕΙΚΟΝΑ & ΗΧΟΣ"
    assert resolution.leaf_category == "Τηλεοράσεις"
    assert resolution.sub_category == "33''-50''"
    assert resolution.cta_url == "https://www.etranoulis.gr/eikona-hxos/thleoraseis/33-50"
    assert "television_size_bucket" in resolution.reason
    assert candidates[0]["sub_category"] == "33''-50''"

