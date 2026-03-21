from electronet_single_import.manufacturer_enrichment import _parse_neff_specsheet
from electronet_single_import.normalize import normalize_for_match


NEFF_SPECSHEET_SAMPLE = """
N 70, Ηλεκτρικές εστίες, 60 cm,
εντοιχιζόμενη με πλαίσιο
T16BT60N0
Χαρακτηριστικά
Τεχνικά στοιχεία
Τύπος εγκατάστασης: ................................. Εντοιχιζόμενη συσκευή
Συνολικός αριθμός ζωνών που μπορούν να χρησιμοποιηθούν
ταυτόχρονα: ................................................................................ 4
Διαστάσεις εντοιχισμού (υ x π x β): .... 48 x 560-560 x 490-500 mm
Καθαρό βάρος: ..................................................................... 8.0 kg
Βασικό υλικό επιφανειών: .........................................Υαλοκεραμική
Χρώμα πλαισίου: ..........................................................Aνοξείδωτο
Τεχνικά χαρακτηριστικά
• Είδος ηλεκτρονικού ελέγχου: TwistPad4: πλήρης έλεγχος της ισχύος
μέσω του αφαιρούμενου μαγνητικού διακόπτη.
• Μπροστά αριστερά: 145 mm, 1.2 ΚW
• Πίσω αριστερά: 210 mm, 120 mm, 0.75 ΚW
Γενικά χαρακτηριστικά
• Λειτουργία Restart: εάν η εστία απενεργοποιηθεί καταλάθος, μπορεί
να επαναφέρει όλες τις προηγούμενες ρυθμίσεις της.
• Συνολική ισχύς: 6.3 ΚW
"""


def test_parse_neff_specsheet_extracts_structured_sections() -> None:
    sections = _parse_neff_specsheet(NEFF_SPECSHEET_SAMPLE)
    flattened = {
        normalize_for_match(item.label): item.value
        for section in sections
        for item in section.items
    }

    assert flattened[normalize_for_match("Τύπος εγκατάστασης")] == "Εντοιχιζόμενη συσκευή"
    assert flattened[normalize_for_match("Συνολικός αριθμός ζωνών που μπορούν να χρησιμοποιηθούν ταυτόχρονα")] == "4"
    assert flattened[normalize_for_match("Καθαρό βάρος")] == "8.0 kg"
    assert flattened[normalize_for_match("Χρώμα πλαισίου")] == "Ανοξείδωτο"
    assert flattened[normalize_for_match("Είδος ηλεκτρονικού ελέγχου")].startswith("TwistPad4")
    assert flattened[normalize_for_match("Μπροστά αριστερά")] == "145 mm, 1.2 ΚW"
    assert flattened[normalize_for_match("Συνολική ισχύς")] == "6.3 ΚW"
