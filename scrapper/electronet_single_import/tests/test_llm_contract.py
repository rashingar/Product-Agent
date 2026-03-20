from electronet_single_import.llm_contract import validate_llm_output


def test_validate_llm_output_accepts_reduced_contract() -> None:
    payload = {
        "product": {
            "meta_description": "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα 635 λίτρων με Total No Frost και WiFi για άνεση κάθε μέρα.",
            "meta_keywords": ["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα", "Total No Frost"],
        },
        "presentation": {
            "intro_html": 'Το <strong>LG GSGV80PYLL</strong> προσφέρει μεγάλη χωρητικότητα.',
            "cta_text": "Δείτε περισσότερα ψυγεία ντουλάπες εδώ",
            "sections": [
                {"title": "NatureFRESH για καθημερινή φρεσκάδα", "body_html": "Το <strong>NatureFRESH</strong> βοηθά στη σωστή συντήρηση."},
                {"title": "DoorCooling+ για ομοιόμορφη ψύξη", "body_html": "Η λειτουργία <strong>DoorCooling+</strong> ενισχύει την ψύξη."},
            ],
        },
    }

    normalized, errors = validate_llm_output(payload, sections_required=2)

    assert errors == []
    assert normalized["product"]["meta_keywords"] == ["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα", "Total No Frost"]
    assert normalized["presentation"]["sections"][0]["title"] == "NatureFRESH για καθημερινή φρεσκάδα"


def test_validate_llm_output_rejects_old_contract_shape() -> None:
    payload = {
        "product": {
            "brand": "LG",
            "name": "bad",
            "meta_description": "bad",
            "meta_keywords": [],
        },
        "presentation": {
            "intro_html": "",
            "cta_text": "",
            "sections": [],
        },
    }

    _, errors = validate_llm_output(payload, sections_required=0)

    assert "llm_product_shape_invalid" in errors
