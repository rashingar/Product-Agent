from pipeline.deterministic_fields import (
    _build_preferred_spec_lookup,
    apply_name_rule,
    build_deterministic_product_fields,
    compose_name,
    resolve_name_rule_component,
)
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

    assert fields["name"] == "Bosch KGN36NLEA – Ψυγειοκαταψύκτης Total No Frost 305Lt Inox 60cm E"
    assert fields["meta_title"] == "Bosch KGN36NLEA Ψυγειοκαταψύκτης Total No Frost 305Lt | eTranoulis"
    assert fields["seo_keyword"] == "bosch-kgn36nlea-psygeiokatapsyktis-total-no-frost-305lt-inox-60cm-e"


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

    assert fields["name"] == "LG RHX5009TWB – Στεγνωτήριο ρούχων 9kg B"
    assert fields["meta_title"] == "LG RHX5009TWB Στεγνωτήριο ρούχων 9kg B | eTranoulis"
    assert fields["seo_keyword"] == "lg-rhx5009twb-stegnotirio-rouchon-9kg-b"


def test_deterministic_fields_compact_voltage_differentiator_for_handheld_vacuums() -> None:
    source = SourceProductData(
        source_name="electronet",
        brand="Black&Decker",
        mpn="PV1820L-QW",
        name="Σκουπάκι Black & Decker Dustbuster Pivot PV1820L-QW 18 Volt",
        key_specs=[
            SpecItem(label="Τάση Volt", value="18,00"),
            SpecItem(label="Χρώμα", value="Ανθρακί"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκουπάκια",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "331566", derive_seo_keyword)

    assert fields["name"] == "Black&Decker PV1820L-QW – Σκουπάκι 18V Ανθρακί"
    assert fields["meta_title"] == "Black&Decker PV1820L-QW Σκουπάκι 18V Ανθρακί | eTranoulis"
    assert fields["meta_description_draft"] == "Το Black&Decker PV1820L-QW είναι Σκουπάκι με 18V, Ανθρακί."
    assert fields["seo_keyword"] == "black-decker-pv1820l-qw-skoupaki-18v-anthraki"


def test_resolve_name_rule_component_prefers_partial_spec_label_match_before_title_fallback() -> None:
    source = SourceProductData(
        source_name="electronet",
        brand="Black&Decker",
        mpn="PV1820L-QW",
        name="Σκουπάκι Black & Decker Dustbuster Pivot PV1820L-QW 18 Volt",
        key_specs=[SpecItem(label="Τάση Volt", value="18,00")],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκουπάκια",
    )

    resolved = resolve_name_rule_component(
        source,
        _build_preferred_spec_lookup(source),
        ["Τάση", "Volt", "V"],
        "Σκουπάκι",
        taxonomy,
    )

    assert resolved.source == "fuzzy_spec"
    assert resolved.matched_label == "ταση volt"
    assert resolved.value == "18V"


def test_resolve_name_rule_component_compacts_power_and_dimensions_from_partial_labels() -> None:
    source = SourceProductData(
        brand="Example",
        mpn="ABC123",
        name="Παράδειγμα προϊόντος",
        key_specs=[
            SpecItem(label="Ισχύς σε Watts", value="1200"),
            SpecItem(label="Πλάτος σε cm", value="60"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Συσκευές Κουζίνας",
        sub_category="Μπλέντερ",
    )
    spec_lookup = _build_preferred_spec_lookup(source)

    power = resolve_name_rule_component(source, spec_lookup, ["Ισχύς", "Ισχύς σε Watt", "Watt"], "Μπλέντερ", taxonomy)
    width = resolve_name_rule_component(source, spec_lookup, ["Πλάτος", "Πλάτος σε cm"], "Μπλέντερ", taxonomy)

    assert power.value == "1200W"
    assert width.value == "60cm"


def test_resolve_name_rule_component_does_not_fuzzy_match_generic_type_alias_to_unrelated_spec() -> None:
    source = SourceProductData(
        brand="Black&Decker",
        mpn="PV1820L-QW",
        name="Σκουπάκι Black & Decker Dustbuster Pivot PV1820L-QW 18 Volt",
        key_specs=[SpecItem(label="Τύπος Μπαταρίας", value="Λιθίου")],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
        leaf_category="Σκούπισμα",
        sub_category="Σκουπάκια",
    )

    resolved = resolve_name_rule_component(
        source,
        _build_preferred_spec_lookup(source),
        ["Τύπος", "Χειρός"],
        "Σκουπάκι",
        taxonomy,
    )

    assert resolved.value == ""


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
    assert "305Lt" in fields["name"]
    assert "Inox" in fields["name"]
    assert "70cm" in fields["name"]
    assert fields["name"].endswith("E")
    assert "Low Frost" not in fields["name"]
    assert "290Lt" not in fields["name"]
    assert "Λευκό" not in fields["name"]
    assert "60cm" not in fields["name"]
    assert fields["meta_title"] == "Bosch KGN36NLEA Ψυγειοκαταψύκτης Total No Frost 305Lt | eTranoulis"
    assert fields["seo_keyword"] == "bosch-kgn36nlea-psygeiokatapsyktis-total-no-frost-305lt-inox-70cm-e"


def test_tv_name_rule_uses_resolution_from_eukrineia_in_final_name() -> None:
    source = SourceProductData(
        brand="TCL",
        mpn="115C7K",
        name='TCL 115C7K Smart Τηλεόραση 115" Mini LED',
        key_specs=[
            SpecItem(label="Τεχνολογία Οθόνης", value="Mini LED"),
            SpecItem(label="Διαγώνιος", value="115 ''"),
            SpecItem(label="Ευκρίνεια", value="ULTRA HD ( 4K )"),
            SpecItem(label="Smart Platform", value="Google TV"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΕΙΚΟΝΑ & ΗΧΟΣ",
        leaf_category="Τηλεοράσεις",
        sub_category="50'' & άνω",
    )

    fields = build_deterministic_product_fields(source, taxonomy, "142677", derive_seo_keyword)

    assert fields["name"] == 'TCL 115C7K – Τηλεόραση Mini LED 115" 4K Google TV'


def test_apply_name_rule_dedupes_tv_resolution_and_prefers_concrete_platform_from_analysi_othonis() -> None:
    source = SourceProductData(
        brand="TCL",
        mpn="115C7K",
        name='TCL 115C7K Smart Τηλεόραση 115" Mini LED',
        key_specs=[
            SpecItem(label="Τεχνολογία Οθόνης", value="Mini LED"),
            SpecItem(label="Διαγώνιος Οθόνης", value='115 "'),
            SpecItem(label="Ανάλυση Οθόνης", value="8K UHD"),
            SpecItem(label="Ευκρίνεια", value="ULTRA HD ( 8K )"),
            SpecItem(label="Λειτουργικό Σύστημα", value="Smart TV"),
            SpecItem(label="Smart Platform", value="Google TV"),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΕΙΚΟΝΑ & ΗΧΟΣ",
        leaf_category="Τηλεοράσεις",
        sub_category="50'' & άνω",
    )
    rule = {
        "category_phrase": "Τηλεόραση",
        "differentiator_specs": [
            [["Τεχνολογία Οθόνης"]],
            [["Διαγώνιος Οθόνης"]],
            [["Ανάλυση Οθόνης"]],
            [["Ευκρίνεια"]],
            [["Λειτουργικό Σύστημα"]],
            [["Smart Platform"]],
        ],
        "max_differentiators": 6,
        "_matched_exact": True,
    }

    category_phrase, differentiators = apply_name_rule(rule, source, "TCL", "115C7K", taxonomy)

    assert category_phrase == "Τηλεόραση"
    assert differentiators == ["Mini LED", '115"', "8K", "Google TV"]
    assert compose_name("TCL", "115C7K", category_phrase, differentiators) == 'TCL 115C7K – Τηλεόραση Mini LED 115" 8K Google TV'

