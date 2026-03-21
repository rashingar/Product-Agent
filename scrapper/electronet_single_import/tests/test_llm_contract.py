from electronet_single_import.llm_contract import INTRO_MAX_WORDS, INTRO_MIN_WORDS, validate_llm_output


def build_intro(words: int = INTRO_MIN_WORDS) -> str:
    return " ".join(["Ξ»Ξ­ΞΎΞ·"] * words)


def test_validate_llm_output_accepts_reduced_contract() -> None:
    payload = {
        "product": {
            "meta_description": "Ξ¤ΞΏ LG GSGV80PYLL ΞµΞ―Ξ½Ξ±ΞΉ ΟΟ…Ξ³ΞµΞ―ΞΏ Ξ½Ο„ΞΏΟ…Ξ»Ξ¬Ο€Ξ± 635 Ξ»Ξ―Ο„ΟΟ‰Ξ½ ΞΌΞµ Total No Frost ΞΊΞ±ΞΉ WiFi Ξ³ΞΉΞ± Ξ¬Ξ½ΞµΟƒΞ· ΞΊΞ¬ΞΈΞµ ΞΌΞ­ΟΞ±.",
            "meta_keywords": ["LG", "GSGV80PYLL", "Ξ¨Ο…Ξ³ΞµΞ―ΞΏ ΞΟ„ΞΏΟ…Ξ»Ξ¬Ο€Ξ±", "Total No Frost"],
        },
        "presentation": {
            "intro_html": build_intro(),
            "cta_text": "Ξ”ΞµΞ―Ο„Ξµ Ο€ΞµΟΞΉΟƒΟƒΟΟ„ΞµΟΞ± ΟΟ…Ξ³ΞµΞ―Ξ± Ξ½Ο„ΞΏΟ…Ξ»Ξ¬Ο€ΞµΟ‚ ΞµΞ΄Ο",
            "sections": [
                {"title": "NatureFRESH Ξ³ΞΉΞ± ΞΊΞ±ΞΈΞ·ΞΌΞµΟΞΉΞ½Ξ® Ο†ΟΞµΟƒΞΊΞ¬Ξ΄Ξ±", "body_html": "Ξ¤ΞΏ <strong>NatureFRESH</strong> Ξ²ΞΏΞ·ΞΈΞ¬ ΟƒΟ„Ξ· ΟƒΟ‰ΟƒΟ„Ξ® ΟƒΟ…Ξ½Ο„Ξ®ΟΞ·ΟƒΞ·."},
                {"title": "DoorCooling+ Ξ³ΞΉΞ± ΞΏΞΌΞΏΞΉΟΞΌΞΏΟΟ†Ξ· ΟΟΞΎΞ·", "body_html": "Ξ— Ξ»ΞµΞΉΟ„ΞΏΟ…ΟΞ³Ξ―Ξ± <strong>DoorCooling+</strong> ΞµΞ½ΞΉΟƒΟ‡ΟΞµΞΉ Ο„Ξ·Ξ½ ΟΟΞΎΞ·."},
            ],
        },
    }

    normalized, errors = validate_llm_output(payload, sections_required=2)

    assert errors == []
    assert normalized["product"]["meta_keywords"] == ["LG", "GSGV80PYLL", "Ξ¨Ο…Ξ³ΞµΞ―ΞΏ ΞΟ„ΞΏΟ…Ξ»Ξ¬Ο€Ξ±", "Total No Frost"]
    assert normalized["presentation"]["sections"][0]["title"] == "NatureFRESH Ξ³ΞΉΞ± ΞΊΞ±ΞΈΞ·ΞΌΞµΟΞΉΞ½Ξ® Ο†ΟΞµΟƒΞΊΞ¬Ξ΄Ξ±"


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


def test_validate_llm_output_rejects_short_intro() -> None:
    payload = {
        "product": {
            "meta_description": "Ξ¤ΞΏ Ο€ΟΞΏΟΟΞ½ ΞµΞ―Ξ½Ξ±ΞΉ Ο€ΟΞ±ΞΊΟ„ΞΉΞΊΞ® Ξ»ΟΟƒΞ· Ξ³ΞΉΞ± ΞΊΞ±ΞΈΞ·ΞΌΞµΟΞΉΞ½Ξ® Ο‡ΟΞ®ΟƒΞ· ΟƒΟ„Ξ·Ξ½ ΞΊΞΏΟ…Ξ¶Ξ―Ξ½Ξ±.",
            "meta_keywords": ["ΞΊΞΏΟ…Ξ¶Ξ―Ξ½Ξ±"],
        },
        "presentation": {
            "intro_html": "Ξ£ΟΞ½Ο„ΞΏΞΌΞΏ ΞΊΞµΞ―ΞΌΞµΞ½ΞΏ.",
            "cta_text": "Ξ”ΞµΞ―Ο„Ξµ Ο€ΞµΟΞΉΟƒΟƒΟΟ„ΞµΟΞ± ΞµΞ΄Ο",
            "sections": [],
        },
    }

    _, errors = validate_llm_output(payload, sections_required=0)

    assert "llm_intro_word_count_invalid" in errors


def test_validate_llm_output_rejects_long_intro() -> None:
    payload = {
        "product": {
            "meta_description": "Ξ¤ΞΏ Ο€ΟΞΏΟΟΞ½ ΞµΞ―Ξ½Ξ±ΞΉ Ο€ΟΞ±ΞΊΟ„ΞΉΞΊΞ® Ξ»ΟΟƒΞ· Ξ³ΞΉΞ± ΞΊΞ±ΞΈΞ·ΞΌΞµΟΞΉΞ½Ξ® Ο‡ΟΞ®ΟƒΞ· ΟƒΟ„Ξ·Ξ½ ΞΊΞΏΟ…Ξ¶Ξ―Ξ½Ξ±.",
            "meta_keywords": ["ΞΊΞΏΟ…Ξ¶Ξ―Ξ½Ξ±"],
        },
        "presentation": {
            "intro_html": build_intro(INTRO_MAX_WORDS + 1),
            "cta_text": "Ξ”ΞµΞ―Ο„Ξµ Ο€ΞµΟΞΉΟƒΟƒΟΟ„ΞµΟΞ± ΞµΞ΄Ο",
            "sections": [],
        },
    }

    _, errors = validate_llm_output(payload, sections_required=0)

    assert "llm_intro_word_count_invalid" in errors
