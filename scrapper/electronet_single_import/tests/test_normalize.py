from electronet_single_import.normalize import clean_breadcrumbs, normalize_whitespace, nullify_dash_values, strip_nbsp
from electronet_single_import.utils import build_additional_image_value


def test_nbsp_and_whitespace_normalization() -> None:
    assert strip_nbsp("798,00\xa0€") == "798,00 €"
    assert normalize_whitespace("  Σκούπα\u00a0\u00a0Stick   Rowenta ") == "Σκούπα Stick Rowenta"


def test_dash_null_handling() -> None:
    assert nullify_dash_values("-") is None
    assert nullify_dash_values("  — ") is None
    assert nullify_dash_values("WiFi") == "WiFi"


def test_clean_breadcrumbs_and_additional_images() -> None:
    assert clean_breadcrumbs(["Αρχική", "Οικιακές Συσκευές", "Οικιακές Συσκευές", "Πλυντήρια"]) == [
        "Αρχική",
        "Οικιακές Συσκευές",
        "Πλυντήρια",
    ]
    assert build_additional_image_value("330825", 1) == ""
    assert build_additional_image_value("330825", 3) == (
        "catalog/01_main/330825/330825-2.jpg:::catalog/01_main/330825/330825-3.jpg"
    )
