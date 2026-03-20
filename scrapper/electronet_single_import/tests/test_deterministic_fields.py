from electronet_single_import.deterministic_fields import build_deterministic_product_fields
from electronet_single_import.mapping import derive_seo_keyword
from electronet_single_import.models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution


def test_deterministic_name_and_meta_title_follow_business_rules() -> None:
    source = SourceProductData(
        brand="LG",
        mpn="GSGV80PYLL",
        name="Ψυγείο Ντουλάπα LG GSGV80PYLL Ασημί E",
        key_specs=[
            SpecItem(label="Συνολική Καθαρή Χωρητικότητα", value="635"),
            SpecItem(label="Τεχνολογία Ψύξης", value="Total No Frost"),
            SpecItem(label="Συνδεσιμότητα", value="WiFi"),
        ],
        spec_sections=[
            SpecSection(section="Ενεργειακά χαρακτηριστικά", items=[SpecItem(label="Ενεργειακή Κλάση", value="E")]),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Ψυγεία & Καταψύκτες",
        sub_category="Ψυγεία Ντουλάπες",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "233541", derive_seo_keyword)

    assert fields["name"] == "LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt Total No Frost WiFi"
    assert fields["meta_title"] == "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt Total No Frost | eTranoulis"
    assert fields["seo_keyword"] == "lg-gsgv80pyll-psygeio-ntoulapa-635lt-total-no-frost-wifi"


def test_deterministic_fields_preserve_commercial_title_when_family_precedes_model() -> None:
    source = SourceProductData(
        brand="Rowenta",
        mpn="RH2099",
        name="Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο",
        key_specs=[
            SpecItem(label="Τάση Volt", value="18,5"),
            SpecItem(label="Χρόνος Λειτουργίας σε Λεπτά", value="45"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκούπες Stick",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "343700", derive_seo_keyword)

    assert fields["preserve_parsed_title"] is True
    assert fields["name"] == "Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο"
    assert fields["meta_title"] == "Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο | eTranoulis"
    assert fields["seo_keyword"] == "skoupa-stick-rowenta-x-force-flex-960-rh2099-kokkino"
