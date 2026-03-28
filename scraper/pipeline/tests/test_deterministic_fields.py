from pipeline.deterministic_fields import build_deterministic_product_fields
from pipeline.mapping import derive_seo_keyword
from pipeline.models import SourceProductData, SpecItem, SpecSection, TaxonomyResolution


def test_skroutz_fridge_freezer_uses_requested_name_schema() -> None:
    source = SourceProductData(
        source_name="skroutz",
        brand="Bosch",
        mpn="KGN36NLEA",
        name="Bosch Ψυγειοκαταψύκτης 305lt Total NoFrost Υ186xΠ60xΒ66εκ. Metal Look KGN36NLEA",
        key_specs=[
            SpecItem(label="Σύστημα Ψύξης", value="Total NoFrost"),
            SpecItem(label="Συνολική Χωρητικότητα", value="305 lt"),
            SpecItem(label="Χρώμα", value="Inox"),
        ],
        spec_sections=[
            SpecSection(section="Νέα Ενεργειακή Ετικέτα", items=[SpecItem(label="Ενεργειακή Κλάση", value="E")]),
            SpecSection(section="Διαστάσεις", items=[SpecItem(label="Πλάτος", value="60 cm")]),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Ψυγεία & Καταψύκτες",
        sub_category="Ψυγειοκαταψύκτες",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "229957", derive_seo_keyword)

    assert fields["name"] == "Bosch KGN36NLEA – Ψυγειοκαταψύκτης Total No Frost 305 lt Inox 60 cm E"
    assert fields["meta_title"] == "Bosch KGN36NLEA Ψυγειοκαταψύκτης Total No Frost 305 lt | eTranoulis"
    assert fields["seo_keyword"] == "bosch-kgn36nlea-psygeiokatapsyktis-total-no-frost-305-lt-inox-60-cm-e"


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

    assert fields["name"] == "LG GSGV80PYLL – Ψυγείο Ντουλάπα Total No Frost 635Lt E"
    assert fields["meta_title"] == "LG GSGV80PYLL Ψυγείο Ντουλάπα Total No Frost 635Lt | eTranoulis"
    assert fields["seo_keyword"] == "lg-gsgv80pyll-psygeio-ntoulapa-total-no-frost-635lt-e"


def test_deterministic_fields_rebuild_name_from_schema_with_title_family_and_color() -> None:
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

    assert fields["preserve_parsed_title"] is False
    assert fields["name"] == "Rowenta RH2099 – Σκούπα Stick X-Force Flex 9.60 Κόκκινο"
    assert fields["meta_title"] == "Rowenta RH2099 Σκούπα Stick X-Force Flex 9.60 Κόκκινο | eTranoulis"
    assert fields["seo_keyword"] == "rowenta-rh2099-skoupa-stick-x-force-flex-960-kokkino"


def test_deterministic_fields_keep_family_and_color_for_small_appliances() -> None:
    source = SourceProductData(
        brand="Tefal",
        mpn="DN853B",
        name="Πολυκόπτης Tefal Fresh Express DN853B Γκρι",
        key_specs=[
            SpecItem(label="Τύπος Πολυκόπτη", value="Κοπτήριο άμεσου σερβιρίσματος"),
            SpecItem(label="Ισχύς σε Watts", value="150"),
            SpecItem(label="Χρώμα", value="Γκρι"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Συσκευές Κουζίνας",
        sub_category="Κοπτήρια-Ράβδοι",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "344424", derive_seo_keyword)

    assert fields["name"] == "Tefal DN853B – Πολυκόπτης Fresh Express Γκρι"
    assert fields["meta_title"] == "Tefal DN853B Πολυκόπτης Fresh Express Γκρι | eTranoulis"
    assert fields["seo_keyword"] == "tefal-dn853b-polykoptis-fresh-express-gkri"


def test_deterministic_fields_use_capacity_and_energy_for_dryers() -> None:
    source = SourceProductData(
        brand="LG",
        mpn="RHX5009TWB",
        name="Στεγνωτήριο ρούχων LG RHX5009TWB 9 kg B",
        key_specs=[
            SpecItem(label="Χωρητικότητα Στεγνώματος", value="9 κιλά"),
            SpecItem(label="Τεχνολογία Στεγνώματος", value="Αντλίας θερμότητας"),
            SpecItem(label="Χρώμα", value="Λευκό"),
        ],
        spec_sections=[
            SpecSection(section="Ενεργειακά Χαρακτηριστικά", items=[SpecItem(label="Ενεργειακή Κλάση", value="B")]),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Πλυντήρια-Στεγνωτήρια",
        sub_category="Στεγνωτήρια Ρούχων",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "235370", derive_seo_keyword)

    assert fields["name"] == "LG RHX5009TWB – Στεγνωτήριο ρούχων 9 kg B"
    assert fields["meta_title"] == "LG RHX5009TWB Στεγνωτήριο ρούχων 9 kg B | eTranoulis"
    assert fields["seo_keyword"] == "lg-rhx5009twb-stegnotirio-rouchon-9-kg-b"


def test_skroutz_name_prefers_manufacturer_evidence_when_specs_conflict() -> None:
    source = SourceProductData(
        source_name="skroutz",
        brand="Bosch",
        mpn="KGN36NLEA",
        name="Bosch Ψυγειοκαταψύκτης KGN36NLEA",
        key_specs=[
            SpecItem(label="Σύστημα Ψύξης", value="Low Frost"),
            SpecItem(label="Συνολική Χωρητικότητα", value="290 lt"),
            SpecItem(label="Χρώμα", value="Λευκό"),
        ],
        spec_sections=[
            SpecSection(section="Διαστάσεις", items=[SpecItem(label="Πλάτος", value="60 cm")]),
            SpecSection(section="Νέα Ενεργειακή Ετικέτα", items=[SpecItem(label="Ενεργειακή Κλάση", value="F")]),
        ],
        manufacturer_spec_sections=[
            SpecSection(
                section="Τεχνικά στοιχεία",
                items=[
                    SpecItem(label="Σύστημα Ψύξης", value="Total No Frost"),
                    SpecItem(label="Συνολική Χωρητικότητα", value="305 lt"),
                    SpecItem(label="Χρώμα", value="Inox"),
                    SpecItem(label="Πλάτος", value="70 cm"),
                    SpecItem(label="Ενεργειακή Κλάση", value="E"),
                ],
            )
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Ψυγεία & Καταψύκτες",
        sub_category="Ψυγειοκαταψύκτες",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "229957", derive_seo_keyword)

    assert "Total No Frost" in fields["name"]
    assert "305 lt" in fields["name"]
    assert "Inox" in fields["name"]
    assert "70 cm" in fields["name"]
    assert fields["name"].endswith("E")
    assert "Low Frost" not in fields["name"]
    assert "290 lt" not in fields["name"]
    assert "Λευκό" not in fields["name"]
    assert "60 cm" not in fields["name"]
    assert fields["meta_title"] == "Bosch KGN36NLEA Ψυγειοκαταψύκτης Total No Frost 305 lt | eTranoulis"
    assert fields["seo_keyword"] == "bosch-kgn36nlea-psygeiokatapsyktis-total-no-frost-305-lt-inox-70-cm-e"

