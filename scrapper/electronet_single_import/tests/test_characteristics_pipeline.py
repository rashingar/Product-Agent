from pathlib import Path

from bs4 import BeautifulSoup

from electronet_single_import.characteristics_pipeline import CharacteristicsTemplateRegistry, build_characteristics_for_product
from electronet_single_import.mapping import build_row
from electronet_single_import.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from electronet_single_import.normalize import normalize_for_match
from electronet_single_import.schema_matcher import SchemaMatcher


TV_TEMPLATE_SCHEMA_ID = "sha1:954c8413f2da941e78f3ddce65df522654336c8c"
HOOD_SCHEMA_ID = "sha1:0afca19ffd5ea62d89eedacca3c889e8d0e67b37"
BUILT_IN_HOB_SCHEMA_ID = "sha1:5fd482e1bc95f854984188f4d55892e272bf6d82"


def write_tv_raw_html(tmp_path: Path) -> Path:
    raw_html = """
    <html>
      <body>
        <div class="product-name" title='Hisense 55A6Q TV, 55" (139.7cm) 4K/UHD DLED Smart TV, HDR10+, Dolby Vision, Dolby Atmos, DTS Virtual:X, DVB-T2/C/S2, Wi-Fi, Bluetooth, LAN, 3x HDMI, 2x USB'></div>
        <div class="product-name" title='Hisense 55" A6Q, 4K Ultra HD 3840x2160, DLED, DFA, Precision Colour, HDR 10+, HLG, Dolby Vision, Smart TV, AnyView Cast, Gaming Mode, 1xHDMI2 eArc, 3xHDMI, 2xUSB, LAN, CI+, DVB-T2/C/S2, Black'></div>
        <p class="usp-description">Έχεις τουλάχιστον 2 χρόνια εγγύηση.</p>
        <dl><dt>Λογισμικό</dt><dd>Vidaa</dd></dl>
      </body>
    </html>
    """
    path = tmp_path / "143051-tv.html"
    path.write_text(raw_html, encoding="utf-8")
    return path


def make_tv_source(tmp_path: Path) -> SourceProductData:
    raw_html_path = write_tv_raw_html(tmp_path)
    return SourceProductData(
        source_name="skroutz",
        page_type="product",
        url="https://www.skroutz.gr/s/61351575/hisense-smart-tileorasi-55-4k-uhd-led-a6q-hdr-2025-55a6q.html",
        canonical_url="https://www.skroutz.gr/s/61351575/hisense-smart-tileorasi-55-4k-uhd-led-a6q-hdr-2025-55a6q.html",
        name='Hisense Smart Τηλεόραση 55" 4K UHD LED A6Q HDR (2025) 55A6Q',
        hero_summary=(
            "Το AI 4K Upscaler της Hisense αναβαθμίζει το περιεχόμενο σε 4K. "
            "Το Game Mode PLUS και το Game Bar βελτιώνουν το gaming, ενώ οι τεχνολογίες VRR και ALLM "
            "μειώνουν την καθυστέρηση. Η Hisense TV αποδίδει Dolby Audio και DTS Virtual:X."
        ),
        presentation_source_text=(
            "Το AI 4K Upscaler αναβαθμίζει την εικόνα. "
            "Το Game Mode PLUS και το Game Bar προσθέτουν έλεγχο. "
            "Το Hisense Voice Remote διευκολύνει τη χρήση."
        ),
        raw_html_path=str(raw_html_path),
        taxonomy_tv_inches=55,
        key_specs=[
            SpecItem(label="Διαγώνιος", value='55 "'),
            SpecItem(label="Ευκρίνεια", value="4K Ultra HD"),
            SpecItem(label="Ρυθμός Ανανέωσης", value="50/60 Hz"),
            SpecItem(label="Τύπος Panel", value="Direct LED"),
            SpecItem(label="Τύποι HDR", value="HDR10, HDR10+, Dolby Vision, HLG"),
            SpecItem(label="Κανάλια", value="2.1"),
            SpecItem(label="Ισχύς", value="20 W"),
        ],
        spec_sections=[
            SpecSection(
                section="Εικόνα",
                items=[
                    SpecItem(label="Διαγώνιος", value='55 "'),
                    SpecItem(label="Ευκρίνεια", value="4K Ultra HD"),
                    SpecItem(label="Ρυθμός Ανανέωσης", value="50/60 Hz"),
                    SpecItem(label="Τύπος Panel", value="Direct LED"),
                    SpecItem(label="Τύποι HDR", value="HDR10, HDR10+, Dolby Vision, HLG"),
                ],
            ),
            SpecSection(
                section="Ήχος",
                items=[
                    SpecItem(label="Κανάλια", value="2.1"),
                    SpecItem(label="Ισχύς", value="20 W"),
                    SpecItem(label="Πρότυπα Ήχου", value="DTS Virtual: X"),
                ],
            ),
            SpecSection(
                section="Δυνατότητες & Λειτουργίες",
                items=[SpecItem(label="Δέκτης", value="DVB-C, DVB-S2, DVB-T2")],
            ),
            SpecSection(
                section="Ενσύρματες Συνδέσεις",
                items=[
                    SpecItem(label="Πλήθος USB", value="2"),
                    SpecItem(label="Σύνολο Θυρών HDMI", value="3"),
                ],
            ),
            SpecSection(
                section="Γενικά",
                items=[
                    SpecItem(label="Βάρος", value="10,9 kg"),
                    SpecItem(label="VESA Mount", value="400 x 200 mm"),
                ],
            ),
            SpecSection(
                section="Ενεργειακή Ετικέτα",
                items=[SpecItem(label="Ενεργειακή Κλάση", value="E")],
            ),
            SpecSection(
                section="Διαστάσεις (με Βάση)",
                items=[
                    SpecItem(label="Πλάτος", value="1234 mm"),
                    SpecItem(label="Ύψος", value="751 mm"),
                    SpecItem(label="Πάχος", value="298 mm"),
                ],
            ),
        ],
    )


def make_tv_taxonomy() -> TaxonomyResolution:
    return TaxonomyResolution(
        parent_category="ΕΙΚΟΝΑ & ΗΧΟΣ",
        leaf_category="Τηλεοράσεις",
        sub_category="50'' & άνω",
        cta_url="https://www.etranoulis.gr/eikona-hxos/thleoraseis/50-anw",
    )


def test_build_row_uses_schema_first_tv_characteristics_template(tmp_path: Path) -> None:
    source = make_tv_source(tmp_path)
    cli = CLIInput(model="143051", url=source.url, photos=4, sections=6, skroutz_status=1, boxnow=0, price="329")
    parsed = ParsedProduct(source=source)
    row, normalized, warnings = build_row(
        cli=cli,
        parsed=parsed,
        taxonomy=make_tv_taxonomy(),
        schema_match=SchemaMatchResult(matched_schema_id=TV_TEMPLATE_SCHEMA_ID, score=0.9),
    )

    soup = BeautifulSoup(row["characteristics"], "lxml")
    section_titles = [normalize_for_match(node.get_text(" ", strip=True)) for node in soup.select("thead strong")]
    labels = [normalize_for_match(node.get_text(" ", strip=True)) for node in soup.select("tbody tr td:first-child")]
    values = [node.get_text(" ", strip=True) for node in soup.select("tbody tr td strong")]
    normalized_values = [normalize_for_match(value) for value in values]
    diagnostics = normalized["characteristics_diagnostics"]

    assert normalize_for_match("Εικόνα - Ήχος") in section_titles
    assert normalize_for_match("Λειτουργίες") in section_titles
    assert normalize_for_match("Συνδέσεις") in section_titles
    assert normalize_for_match("Γενικά") in section_titles
    assert normalize_for_match("Τεχνολογία Οθόνης") in labels
    assert normalize_for_match("Διαγώνιος Οθόνης ( Ίντσες )") in labels
    assert "ULTRA HD ( 4K )" in values
    assert "DVB-T2/C/S2" in values
    assert "Ναι,3,eARC" in values
    assert "Ναι,2" in values
    assert normalize_for_match("200 × 400") in normalized_values
    assert diagnostics["template_id"] == f"schema:{TV_TEMPLATE_SCHEMA_ID}"
    assert diagnostics["template_source"] == "schema_library_with_custom_overrides"
    assert diagnostics["custom_template_id"] == "skroutz_tv_v1"
    assert diagnostics["matched_schema_id"] == TV_TEMPLATE_SCHEMA_ID
    assert diagnostics["selection_reason"] == "matched_schema_template_with_custom_overrides"
    assert f"characteristics_template_used:schema:{TV_TEMPLATE_SCHEMA_ID}" in warnings


def test_characteristics_pipeline_falls_back_to_raw_sections_without_template() -> None:
    source = SourceProductData(
        source_name="electronet",
        name="Simple Product",
        spec_sections=[SpecSection(section="Γενικά", items=[SpecItem(label="Χρώμα", value="Λευκό")])],
    )
    taxonomy = TaxonomyResolution(parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ", leaf_category="Κουζίνες")

    html, diagnostics, warnings = build_characteristics_for_product(source, taxonomy)

    assert diagnostics["mode"] == "raw_spec_sections"
    assert diagnostics["template_id"] == ""
    assert warnings == []
    assert "<strong>Γενικά</strong>" in html
    assert "<td>Χρώμα</td>" in html


def test_characteristics_pipeline_uses_matched_schema_layout_for_generic_categories() -> None:
    source = SourceProductData(
        source_name="skroutz",
        name="Bosch Hood Example",
        spec_sections=[
            SpecSection(
                section="Επισκόπηση",
                items=[
                    SpecItem(label="Τρόπος Τοποθέτησης", value="Καμινάδα"),
                    SpecItem(label="Χειρισμός", value="Αφής"),
                    SpecItem(label="Μέγιστη Απόδοση Εξαγωγής Αέρα (m3/h)", value="650"),
                ],
            ),
            SpecSection(
                section="Ενεργειακά",
                items=[
                    SpecItem(label="Ενεργειακή Κλάση", value="A"),
                    SpecItem(label="Επίπεδο Θορύβου σε dB", value="62"),
                ],
            ),
            SpecSection(
                section="Γενικά",
                items=[
                    SpecItem(label="Χρώμα", value="Inox"),
                    SpecItem(label="Εγγύηση Κατασκευαστή", value="2 έτη"),
                ],
            ),
        ],
    )
    taxonomy = TaxonomyResolution(parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ", leaf_category="Απορροφητήρες")

    html, diagnostics, warnings = build_characteristics_for_product(
        source,
        taxonomy,
        schema_match=SchemaMatchResult(matched_schema_id=HOOD_SCHEMA_ID, score=0.91),
    )

    soup = BeautifulSoup(html, "lxml")
    section_titles = [normalize_for_match(node.get_text(" ", strip=True)) for node in soup.select("thead strong")]
    labels = [normalize_for_match(node.get_text(" ", strip=True)) for node in soup.select("tbody tr td:first-child")]
    values = [normalize_for_match(node.get_text(" ", strip=True)) for node in soup.select("tbody tr td strong")]

    assert diagnostics["mode"] == "template"
    assert diagnostics["template_id"] == f"schema:{HOOD_SCHEMA_ID}"
    assert diagnostics["template_source"] == "schema_library"
    assert diagnostics["custom_template_id"] == ""
    assert diagnostics["matched_schema_id"] == HOOD_SCHEMA_ID
    assert diagnostics["selection_reason"] == "matched_schema_template"
    assert f"characteristics_template_used:schema:{HOOD_SCHEMA_ID}" in warnings
    assert normalize_for_match("Επισκόπηση Προϊόντος") in section_titles
    assert normalize_for_match("Ενεργειακά Χαρακτηριστικά") in section_titles
    assert normalize_for_match("Γενικά Χαρακτηριστικά") in section_titles
    assert normalize_for_match("Επισκόπηση") not in section_titles
    assert normalize_for_match("Τρόπος Τοποθέτησης") in labels
    assert normalize_for_match("Ενεργειακή Κλάση") in labels
    assert normalize_for_match("Χρώμα") in labels
    assert normalize_for_match("Καμινάδα") in values
    assert normalize_for_match("a") in values
    assert normalize_for_match("inox") in values


def test_schema_matcher_prefers_template_source_files_for_tv_sections() -> None:
    sections = [
        SpecSection(
            section="Εικόνα",
            items=[
                SpecItem("Διαγώνιος", '55 "'),
                SpecItem("Ευκρίνεια", "4K Ultra HD"),
                SpecItem("Ρυθμός Ανανέωσης", "50/60 Hz"),
                SpecItem("Τύπος Panel", "Direct LED"),
                SpecItem("Τύποι HDR", "HDR10, HDR10+, Dolby Vision, HLG"),
                SpecItem("Local Dimming", "Όχι"),
            ],
        ),
        SpecSection(
            section="Ήχος",
            items=[
                SpecItem("Κανάλια", "2.1"),
                SpecItem("Ισχύς", "20 W"),
                SpecItem("Πρότυπα Ήχου", "DTS Virtual: X"),
            ],
        ),
        SpecSection(
            section="Δυνατότητες & Λειτουργίες",
            items=[
                SpecItem("Δέκτης", "DVB-C, DVB-S2, DVB-T2"),
                SpecItem("Media Player", "Ναι"),
                SpecItem("Εγγραφή PVR", "Όχι"),
                SpecItem("Hotel Mode", "Όχι"),
                SpecItem("Φωνητικές Εντολές", "Όχι"),
                SpecItem("HbbTV", "Όχι"),
                SpecItem("VRR", "Όχι"),
            ],
        ),
        SpecSection(
            section="Smart Δυνατότητες",
            items=[
                SpecItem("Υποστηριζόμενες Εφαρμογές", "Netflix, Youtube, Prime Video, DisneyPlus, Eon"),
                SpecItem("Λογισμικό", "Vidaa"),
            ],
        ),
        SpecSection(
            section="Ενσύρματες Συνδέσεις",
            items=[
                SpecItem("Ethernet", "Ναι"),
                SpecItem("Headphones", "Όχι"),
                SpecItem("Digital Audio Optical", "Ναι"),
                SpecItem("Πλήθος USB", "2"),
                SpecItem("Σύνολο Θυρών HDMI", "3"),
                SpecItem("Πλήθος HDMI 2.1", "-"),
            ],
        ),
        SpecSection(
            section="Ασύρματες Συνδέσεις",
            items=[
                SpecItem("Wi-Fi", "Ναι"),
                SpecItem("Bluetooth", "Όχι"),
                SpecItem("Miracast", "Όχι"),
                SpecItem("Chromecast Built-In", "Όχι"),
                SpecItem("Screen Mirroring", "Όχι"),
                SpecItem("AirPlay", "Ναι"),
            ],
        ),
        SpecSection(
            section="Γενικά",
            items=[
                SpecItem("Έτος Κυκλοφορίας", "2025"),
                SpecItem("Βάρος", "10,9 kg"),
                SpecItem("VESA Mount", "400 x 200 mm"),
            ],
        ),
        SpecSection(section="Ενεργειακή Ετικέτα", items=[SpecItem("Ενεργειακή Κλάση", "E")]),
        SpecSection(
            section="Διαστάσεις (Χωρίς Βάση)",
            items=[
                SpecItem("Πλάτος", "1234 mm"),
                SpecItem("Ύψος", "716 mm"),
                SpecItem("Πάχος", "81 mm"),
            ],
        ),
        SpecSection(
            section="Διαστάσεις (με Βάση)",
            items=[
                SpecItem("Πλάτος", "1234 mm"),
                SpecItem("Ύψος", "751 mm"),
                SpecItem("Πάχος", "298 mm"),
            ],
        ),
    ]
    matcher = SchemaMatcher()

    default_result, _default_candidates = matcher.match(sections, taxonomy_sub_category="50'' & άνω")
    preferred_result, preferred_candidates = matcher.match(
        sections,
        taxonomy_sub_category="50'' & άνω",
        preferred_source_files=["tileoraseis.json"],
    )

    assert default_result.matched_schema_id != TV_TEMPLATE_SCHEMA_ID
    assert preferred_result.matched_schema_id == TV_TEMPLATE_SCHEMA_ID
    assert preferred_candidates[0]["source_files"] == ["tileoraseis.json"]


def test_characteristics_registry_prefers_built_in_hob_schema_for_skroutz() -> None:
    registry = CharacteristicsTemplateRegistry()
    source = SourceProductData(source_name="skroutz", name="Neff Hob")
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Εντοιχιζόμενες Συσκευές",
        sub_category="Εστίες",
    )

    preferred_source_files = registry.preferred_schema_source_files(source, taxonomy)
    template = registry.select_template(
        source,
        taxonomy,
        schema_match=SchemaMatchResult(matched_schema_id=BUILT_IN_HOB_SCHEMA_ID, score=0.9),
    )

    assert preferred_source_files == ["esties.json"]
    assert template is not None
    assert template["matched_schema_id"] == BUILT_IN_HOB_SCHEMA_ID
    assert template["preferred_schema_source_files"] == ["esties.json"]
    assert template["template_source"] == "schema_library_with_custom_overrides"
    assert template["custom_template_id"] == "skroutz_built_in_hob_v1"


def test_built_in_hob_characteristics_use_source_and_manufacturer_evidence() -> None:
    source = SourceProductData(
        source_name="skroutz",
        brand="Neff",
        mpn="T16BT60N0",
        name="Neff T16BT60N0 Hob",
        spec_sections=[
            SpecSection(
                section="Γενικά",
                items=[
                    SpecItem(label="Τύπος", value="Κεραμική"),
                    SpecItem(label="Αριθμός Εστιών", value="4"),
                    SpecItem(label="Διακόπτες", value="Αφής"),
                    SpecItem(label="Χρώμα", value="Μαύρο"),
                ],
            ),
            SpecSection(
                section="Δυνατότητες & Λειτουργίες",
                items=[
                    SpecItem(label="Smart", value="Όχι"),
                    SpecItem(label="Λειτουργία Κλειδώματος", value="Ναι"),
                    SpecItem(label="Χρονοδιακόπτης", value="Ναι"),
                    SpecItem(label="Ένδειξη Υπολοίπου Θερμότητας", value="Ναι"),
                ],
            ),
            SpecSection(
                section="Διαστάσεις Συσκευής",
                items=[
                    SpecItem(label="Ύψος", value="4,8 cm"),
                    SpecItem(label="Πλάτος", value="58,3 cm"),
                    SpecItem(label="Βάθος", value="51,3 cm"),
                ],
            ),
            SpecSection(
                section="Διαστάσεις Εντοιχισμού",
                items=[
                    SpecItem(label="Πλάτος Εντοιχισμού", value="56 cm"),
                    SpecItem(label="Βάθος Εντοιχισμού", value="50 cm"),
                ],
            ),
        ],
        manufacturer_spec_sections=[
            SpecSection(
                section="Τεχνικά στοιχεία",
                items=[
                    SpecItem(label="Τύπος εγκατάστασης", value="Εντοιχιζόμενη συσκευή"),
                    SpecItem(label="Τύπος λειτουργίας", value="Ηλεκτρική"),
                    SpecItem(label="Βασικό υλικό επιφανειών", value="Υαλοκεραμική"),
                    SpecItem(label="Συνολικός αριθμός ζωνών που μπορούν να χρησιμοποιηθούν ταυτόχρονα", value="4"),
                    SpecItem(label="Διαστάσεις εντοιχισμού (υ x π x β)", value="48 x 560 x 490 - 500 mm"),
                    SpecItem(label="Διαστάσεις συσκευής (ΥxΠxΒ mm)", value="48 x 583 x 513"),
                    SpecItem(label="Καθαρό βάρος", value="8.0 kg"),
                    SpecItem(label="Χρώμα πλαισίου", value="Ανοξείδωτο"),
                ],
            ),
            SpecSection(
                section="Γενικά χαρακτηριστικά",
                items=[
                    SpecItem(label="Είδος ηλεκτρονικού ελέγχου", value="TwistPad4: πλήρης έλεγχος της ισχύος"),
                    SpecItem(label="Ψηφιακό χρονόμετρο", value="ένδειξη του χρόνου που έχει περάσει"),
                    SpecItem(label="Αυτόματη απενεργοποίηση ασφαλείας", value="η εστία σταματά να θερμαίνεται"),
                    SpecItem(label="Κλείδωμα ασφαλείας για τα παιδιά", value="αποτροπή ενεργοποίησης"),
                    SpecItem(label="Συνολική ισχύς", value="6.3 ΚW"),
                ],
            ),
        ],
        manufacturer_source_text=(
            "TwistPad 17 βαθμίδες ισχύος Λειτουργία Restart Λειτουργία Alarm "
            "Λειτουργία διατήρησης θερμότητας Ψηφιακό χρονόμετρο "
            "Μπροστά αριστερά: 145 mm, 1.2 ΚW Πίσω αριστερά: 210 mm, 120 mm, 0.75 ΚW "
            "Μπροστά δεξιά: 180 mm, 80 mm, 0.4 ΚW Πίσω δεξιά: 145 mm, 1.2 ΚW"
        ),
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Εντοιχιζόμενες Συσκευές",
        sub_category="Εστίες",
    )

    html, diagnostics, _warnings = build_characteristics_for_product(
        source,
        taxonomy,
        schema_match=SchemaMatchResult(matched_schema_id=BUILT_IN_HOB_SCHEMA_ID, score=0.9),
    )

    soup = BeautifulSoup(html, "lxml")
    values = {
        normalize_for_match(cells[0].get_text(" ", strip=True)): cells[1].get_text(" ", strip=True)
        for cells in (row.find_all("td") for row in soup.select("tbody tr"))
        if len(cells) == 2
    }

    assert diagnostics["template_source"] == "schema_library_with_custom_overrides"
    assert values[normalize_for_match("Τρόπος Τοποθέτησης")] == "Εντοιχιζόμενη συσκευή"
    assert values[normalize_for_match("Τεχνολογία Πλατώ Εστιών")] == "Υαλοκεραμική"
    assert values[normalize_for_match("Αριθμός Ζωνών")] == "4"
    assert values[normalize_for_match("Τύπος Χειριστηρίου")] == "TwistPad®"
    assert values[normalize_for_match("Ψηφιακές Ενδείξεις")] == "Ναι"
    assert values[normalize_for_match("Σύνδεση με Φυσικό Αέριο")] == "Όχι"
    assert values[normalize_for_match("Συνδεσιμότητα")] == "Όχι"
    assert values[normalize_for_match("Άλλα Χαρακτηριστικά")] == "17 βαθμίδες ισχύος, λειτουργία Restart, λειτουργία Alarm, διατήρηση θερμότητας"
    assert values[normalize_for_match("Ισχύς Εστίας Μπροστά Αριστερά (KW")] == "1.2 kW"
    assert values[normalize_for_match("Ισχύς Εστίας Πίσω Αριστερά (KW")] == "0.75 kW"
    assert values[normalize_for_match("Μέγιστη Ονομαστική Ισχύς (W")] == "6300 W"
    assert values[normalize_for_match("Χρώμα Πλαισίου")] == "Ανοξείδωτο"
    assert values[normalize_for_match("Βάρος Συσκευής σε Κιλά")] == "8.0"
    assert values[normalize_for_match("Ύψος Διάστασης Εντοιχισμού")] == "4.8 cm"
    assert values[normalize_for_match("Βάθος Διάστασης Εντοιχισμού σε Εκατοστά")] == "49 - 50 cm"
