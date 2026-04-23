from bs4 import BeautifulSoup

from pipeline.characteristics_pipeline import build_characteristics_for_product
from pipeline.models import SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from pipeline.normalize import normalize_for_match


BUILT_IN_OVEN_SCHEMA_ID = "sha1:a5ada7b3cbca265e72442764a28970c39d91d102"


def test_skroutz_built_in_oven_characteristics_use_alias_enrichment() -> None:
    source = SourceProductData(
        source_name="skroutz",
        brand="LG",
        mpn="WSED7612S",
        name="LG Φούρνος άνω Πάγκου 76lt Π59.2εκ. Inox",
        canonical_url="https://www.skroutz.gr/s/49286715/LG-WSED7612S-Fournos-ano-Pagou-76lt-P59-2ek-Inox.html",
        spec_sections=[
            SpecSection(
                section="Κύρια Χαρακτηριστικά",
                items=[
                    SpecItem(label="Είδος", value="Φούρνος άνω Πάγκου χωρίς Εστίες"),
                    SpecItem(label="Ενεργειακή Κλάση", value="A+"),
                    SpecItem(label="Χρώμα", value="Inox"),
                ],
            ),
            SpecSection(
                section="Χαρακτηριστικά Φούρνου",
                items=[
                    SpecItem(label="Χωρητικότητα Φούρνου", value="76 lt"),
                    SpecItem(label="Τρόποι Ψησίματος", value="15"),
                    SpecItem(label="Τύποι Ψησίματος", value="Grill"),
                    SpecItem(label="Διακόπτες", value="Αφής"),
                    SpecItem(label="Σύστημα Καθαρισμού", value="Πυρόλυση"),
                    SpecItem(label="Ψηφιακή Οθόνη", value="Ναι"),
                    SpecItem(label="Κλείδωμα", value="Ναι"),
                    SpecItem(label="WiFi", value="Ναι"),
                    SpecItem(label="Air Fry", value="Ναι"),
                    SpecItem(label="Αξεσουάρ", value="Ταψί"),
                ],
            ),
        ],
    )
    taxonomy = TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Εντοιχιζόμενες Συσκευές",
        sub_category="Φούρνοι",
    )

    html, diagnostics, _warnings = build_characteristics_for_product(
        source,
        taxonomy,
        schema_match=SchemaMatchResult(matched_schema_id=BUILT_IN_OVEN_SCHEMA_ID, score=0.9),
    )

    soup = BeautifulSoup(html, "lxml")
    values = {
        normalize_for_match(cells[0].get_text(" ", strip=True)): cells[1].get_text(" ", strip=True)
        for cells in (row.find_all("td") for row in soup.select("tbody tr"))
        if len(cells) == 2
    }

    assert diagnostics["template_source"] == "schema_library_with_custom_overrides"
    assert values[normalize_for_match("Τρόπος Εντοιχισμού")] == "Άνω Πάγκου"
    assert values[normalize_for_match("Χωρητικότητα Φούρνου σε Λίτρα")] == "76"
    assert values[normalize_for_match("Αριθμός Λειτουργιών Ψησίματος")] == "15"
    assert values[normalize_for_match("Τρόποι Λειτουργίας Ψησίματος")] == "Grill"
    assert values[normalize_for_match("Οθόνη Ψηφιακών Ενδείξεων")] == "Ναι"
    assert values[normalize_for_match("Χειρισμός")] == "Αφής"
    assert values[normalize_for_match("Ηλεκτρονικό Ρολόι")] == "Ναι"
    assert values[normalize_for_match("Καθαρισμός Φούρνου")] == "Πυρόλυση"
    assert values[normalize_for_match("Συνδεσιμότητα")] == "WiFi"
    assert values[normalize_for_match("Κλείδωμα Ασφαλείας για Παιδιά")] == "Ναι"
