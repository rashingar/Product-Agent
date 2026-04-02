from pathlib import Path

from pipeline.llm_contract import (
    INTRO_MAX_WORDS,
    INTRO_MIN_WORDS,
    build_intro_text_context,
    build_seo_meta_context,
    validate_intro_text_output,
    validate_seo_meta_output,
)
from pipeline.models import CLIInput, ParsedProduct, SourceProductData, SpecItem, TaxonomyResolution
from pipeline.repo_paths import REPO_ROOT


def build_intro(words: int = INTRO_MIN_WORDS) -> str:
    return " ".join(["Ξ»Ξ­ΞΎΞ·"] * words)


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
    assert set(context["evidence"]) >= {
        "meta_description_draft",
        "hero_summary",
        "key_specs",
        "deterministic_differentiators",
    }
    assert context["product"]["meta_title"] == "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt | eTranoulis"
    assert context["evidence"]["meta_description_draft"] == "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με 635Lt."
    assert "2 natural Greek sentences" in context["writer_rules"]["meta_description_rule"]
    assert "Exactly one sentence" not in context["writer_rules"]["meta_description_rule"]
    assert "Smooth the Greek grammar" not in context["writer_rules"]["meta_description_rule"]


def test_validate_intro_text_output_accepts_plain_text_only() -> None:
    normalized, errors = validate_intro_text_output(" ".join(["λέξη"] * INTRO_MIN_WORDS))

    assert errors == []
    assert normalized.startswith("λέξη")


def test_validate_intro_text_output_rejects_short_intro() -> None:
    _, errors = validate_intro_text_output(" ".join(["λέξη"] * (INTRO_MIN_WORDS - 1)))

    assert "llm_intro_text_word_count_invalid" in errors


def test_validate_intro_text_output_rejects_html() -> None:
    _, errors = validate_intro_text_output("<p>λέξη</p> " + " ".join(["λέξη"] * (INTRO_MIN_WORDS - 1)))

    assert "llm_intro_text_html_invalid" in errors


def test_validate_intro_text_output_rejects_long_intro() -> None:
    _, errors = validate_intro_text_output(" ".join(["λέξη"] * (INTRO_MAX_WORDS + 1)))

    assert "llm_intro_text_word_count_invalid" in errors


def test_validate_seo_meta_output_accepts_product_meta_only_shape() -> None:
    normalized, errors = validate_seo_meta_output(
        {
            "product": {
                "meta_description": "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με πρακτική καθημερινή χρήση.",
                "meta_keywords": ["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα"],
            }
        }
    )

    assert errors == []
    assert normalized["product"]["meta_keywords"] == ["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα"]


def test_validate_seo_meta_output_accepts_two_sentence_meta_description() -> None:
    normalized, errors = validate_seo_meta_output(
        {
            "product": {
                "meta_description": (
                    "Το TCL 115C7K είναι τηλεόραση Mini LED 115 ιντσών με 4K Ultra HD ανάλυση και Google TV. "
                    "Προσφέρει verified χαρακτηριστικά εικόνας και συνδεσιμότητας από τα διαθέσιμα στοιχεία."
                ),
                "meta_keywords": ["TCL", "115C7K", "Τηλεόραση"],
            }
        }
    )

    assert errors == []
    assert normalized["product"]["meta_description"].count(".") >= 2


def test_validate_seo_meta_output_rejects_legacy_presentation_shape() -> None:
    _, errors = validate_seo_meta_output(
        {
            "product": {
                "meta_description": "ok",
                "meta_keywords": ["LG"],
            },
            "presentation": {
                "intro_html": build_intro(),
            },
        }
    )

    assert errors == ["llm_seo_meta_root_shape_invalid"]


def test_seo_meta_prompt_source_uses_repo_root_relative_path_and_updated_guidance() -> None:
    prompt_path = REPO_ROOT / "resources" / "prompts" / "seo_meta_prompt.txt"
    prompt = Path(prompt_path).read_text(encoding="utf-8")
    lowered = prompt.casefold()

    assert prompt_path.is_file()
    assert "exactly one sentence" not in lowered
    assert "verified evidence" in lowered
    assert "return json only" in lowered

