from pipeline.llm_contract import (
    INTRO_MAX_WORDS,
    INTRO_MIN_WORDS,
    build_intro_text_context,
    build_seo_meta_context,
    validate_llm_output,
)
from pipeline.models import CLIInput, ParsedProduct, SourceProductData, SpecItem, TaxonomyResolution


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
            "sections": [],
        },
    }

    _, errors = validate_llm_output(payload, sections_required=0)

    assert "llm_intro_word_count_invalid" in errors


def test_build_intro_text_context_excludes_section_generation() -> None:
    context = build_intro_text_context(
        cli=CLIInput(model="233541", url="https://www.electronet.gr/example"),
        parsed=ParsedProduct(
            source=SourceProductData(
                brand="LG",
                mpn="GSGV80PYLL",
                name="LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt",
                hero_summary="Σύντομη σύνοψη για καθημερινή χρήση.",
                key_specs=[SpecItem(label="Χωρητικότητα", value="635Lt")],
                presentation_source_html="<section><h3>Τίτλος</h3><p>Κείμενο</p></section>",
            )
        ),
        taxonomy=TaxonomyResolution(leaf_category="Ψυγεία & Καταψύκτες", sub_category="Ψυγεία Ντουλάπες"),
        deterministic_product={
            "name": "LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt",
            "brand": "LG",
            "mpn": "GSGV80PYLL",
            "category_phrase": "Ψυγείο Ντουλάπα",
            "name_differentiators": ["635Lt", "Total No Frost"],
        },
    )

    assert context["task"] == "intro_text"
    assert context["writer_rules"]["llm_owned_fields"] == ["intro_text"]
    assert context["writer_rules"]["plain_text_only"] is True
    assert context["writer_rules"]["forbidden_outputs"] == ["html", "bullets", "cta_language"]
    assert "presentation_source_sections" not in context
    assert "sections" not in context


def test_build_seo_meta_context_includes_required_keyword_evidence() -> None:
    context = build_seo_meta_context(
        cli=CLIInput(model="233541", url="https://www.electronet.gr/example"),
        parsed=ParsedProduct(
            source=SourceProductData(
                brand="LG",
                mpn="GSGV80PYLL",
                name="LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt",
                hero_summary="Σύντομη σύνοψη για καθημερινή χρήση.",
                key_specs=[SpecItem(label="Χωρητικότητα", value="635Lt")],
            )
        ),
        taxonomy=TaxonomyResolution(leaf_category="Ψυγεία & Καταψύκτες", sub_category="Ψυγεία Ντουλάπες"),
        deterministic_product={
            "name": "LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt",
            "brand": "LG",
            "mpn": "GSGV80PYLL",
            "category_phrase": "Ψυγείο Ντουλάπα",
            "meta_title": "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt | eTranoulis",
            "meta_description_draft": "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με 635Lt.",
            "name_differentiators": ["635Lt", "Total No Frost"],
            "seo_keyword": "lg-gsgv80pyll-psygeio-ntoulapa-635lt",
        },
    )

    assert context["task"] == "seo_meta"
    assert context["writer_rules"]["llm_owned_fields"] == ["product.meta_description", "product.meta_keywords"]
    assert context["writer_rules"]["required_keywords"] == ["LG", "GSGV80PYLL"]
    assert context["product"]["meta_title"] == "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt | eTranoulis"
    assert context["evidence"]["meta_description_draft"] == "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με 635Lt."

