import argparse
import json
from pathlib import Path

from electronet_single_import.models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from electronet_single_import.workflow import build_cli_input_from_args, prepare_workflow, render_workflow


def build_intro(words: int = 120) -> str:
    return " ".join(["λέξη"] * words)


def test_build_cli_input_from_template_file(tmp_path: Path, monkeypatch) -> None:
    template = tmp_path / "input.txt"
    template.write_text(
        "model: 233541\nurl: https://www.electronet.gr/oikiakes-syskeyes/example\nphotos: 6\nsections: 5\nskroutz_status: 1\nboxnow: 0\nprice: 2099\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        template_file=str(template),
        stdin=False,
        model=None,
        url=None,
        photos=None,
        sections=None,
        skroutz_status=None,
        boxnow=None,
        price=None,
    )
    cli = build_cli_input_from_args(args)

    assert cli.model == "233541"
    assert cli.photos == 6
    assert cli.sections == 5
    assert str(cli.price) == "2099"


def test_prepare_workflow_writes_prompt_artifacts(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")

    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code="233541",
        brand="LG",
        name="Ψυγείο Ντουλάπα LG GSGV80PYLL Ασημί E",
        hero_summary="Σύντομη περιγραφή",
        key_specs=[SpecItem(label="Συνολική Καθαρή Χωρητικότητα", value="635")],
    )
    cli = CLIInput(model="233541", url="https://www.electronet.gr/example", photos=6, sections=2, skroutz_status=1, boxnow=0, price="2099", out=str(tmp_path))

    def fake_run_cli_input(_cli):
        return {
            "normalized": {
                "deterministic_product": {
                    "brand": "LG",
                    "mpn": "GSGV80PYLL",
                    "manufacturer": "LG",
                    "name": "LG GSGV80PYLL – Ψυγείο Ντουλάπα 635Lt",
                    "meta_title": "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt | eTranoulis",
                    "seo_keyword": "lg-gsgv80pyll-psygeio-ntoulapa-635lt",
                }
            },
            "parsed": ParsedProduct(source=source),
            "taxonomy": TaxonomyResolution(
                parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
                leaf_category="Ψυγεία & Καταψύκτες",
                sub_category="Ψυγεία Ντουλάπες",
                cta_url="https://www.etranoulis.gr/psygeia-ntoulapes",
            ),
            "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9),
        }

    monkeypatch.setattr(workflow, "run_cli_input", fake_run_cli_input)

    result = prepare_workflow(cli)

    assert result["llm_context_path"].exists()
    assert result["prompt_path"].exists()
    llm_context = json.loads(result["llm_context_path"].read_text(encoding="utf-8"))
    prompt_text = result["prompt_path"].read_text(encoding="utf-8")
    assert llm_context["writer_rules"]["intro_html_rule"] == "120-180 Greek words in one intro paragraph."
    assert "between 120 and 180 Greek words" in prompt_text
    assert "120-180 Greek words" in prompt_text


def test_prepare_workflow_normalizes_scrape_artifact_paths(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")

    model = "233541"
    generated_scrape_dir = tmp_path / "work" / model / "scrape" / model
    generated_scrape_dir.mkdir(parents=True)
    old_prefix = str(generated_scrape_dir)
    raw_html_path = generated_scrape_dir / f"{model}.raw.html"
    source_json_path = generated_scrape_dir / f"{model}.source.json"
    normalized_json_path = generated_scrape_dir / f"{model}.normalized.json"
    report_json_path = generated_scrape_dir / f"{model}.report.json"
    csv_path = generated_scrape_dir / f"{model}.csv"

    raw_html_path.write_text("<html></html>", encoding="utf-8")
    csv_path.write_text("model\n233541\n", encoding="utf-8")

    source_payload = {
        "url": "https://www.electronet.gr/example",
        "canonical_url": "https://www.electronet.gr/example",
        "product_code": model,
        "brand": "LG",
        "name": "Ψυγείο Ντουλάπα LG GSGV80PYLL",
        "raw_html_path": str(raw_html_path),
        "gallery_images": [{"local_path": f"{old_prefix}\\gallery\\{model}-1.jpg"}],
        "besco_images": [{"local_path": f"{old_prefix}\\bescos\\besco1.jpg"}],
    }
    normalized_payload = {
        "deterministic_product": {
            "brand": "LG",
            "mpn": "GSGV80PYLL",
            "manufacturer": "LG",
            "name": "LG GSGV80PYLL – Ψυγείο Ντουλάπα",
            "meta_title": "LG GSGV80PYLL Ψυγείο Ντουλάπα | eTranoulis",
            "seo_keyword": "lg-gsgv80pyll-psygeio-ntoulapa",
        },
        "input": {"out": str(tmp_path / "work" / model / "scrape")},
        "csv_row": {"model": model},
    }
    report_payload = {"files_written": [str(raw_html_path), str(source_json_path), str(normalized_json_path), str(report_json_path), str(csv_path)]}

    source_json_path.write_text(json.dumps(source_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    normalized_json_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    parsed = ParsedProduct(
        source=SourceProductData(
            url="https://www.electronet.gr/example",
            canonical_url="https://www.electronet.gr/example",
            product_code=model,
            brand="LG",
            name="Ψυγείο Ντουλάπα LG GSGV80PYLL",
            raw_html_path=str(raw_html_path),
            gallery_images=[GalleryImage(url="https://example.com/1.jpg", local_path=f"{old_prefix}\\gallery\\{model}-1.jpg")],
            besco_images=[GalleryImage(url="https://example.com/besco1.jpg", local_path=f"{old_prefix}\\bescos\\besco1.jpg")],
        )
    )
    cli = CLIInput(model=model, url="https://www.electronet.gr/example", photos=6, sections=2, skroutz_status=1, boxnow=0, price="2099", out=str(tmp_path))

    def fake_run_cli_input(_cli):
        return {
            "normalized": normalized_payload,
            "parsed": parsed,
            "taxonomy": TaxonomyResolution(
                parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
                leaf_category="Ψυγεία & Καταψύκτες",
                sub_category="Ψυγεία Ντουλάπες",
                cta_url="https://www.etranoulis.gr/psygeia-ntoulapes",
            ),
            "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9),
            "report": report_payload,
            "model_dir": generated_scrape_dir,
            "raw_html_path": raw_html_path,
            "source_json_path": source_json_path,
            "normalized_json_path": normalized_json_path,
            "report_json_path": report_json_path,
            "csv_path": csv_path,
        }

    monkeypatch.setattr(workflow, "run_cli_input", fake_run_cli_input)

    result = prepare_workflow(cli)
    scrape_dir = result["scrape_dir"]
    rewritten_source = json.loads((scrape_dir / f"{model}.source.json").read_text(encoding="utf-8"))
    rewritten_report = json.loads((scrape_dir / f"{model}.report.json").read_text(encoding="utf-8"))

    assert result["scrape_result"]["model_dir"] == scrape_dir
    assert rewritten_source["raw_html_path"] == str(scrape_dir / f"{model}.raw.html")
    assert all(Path(path).parent == scrape_dir for path in rewritten_report["files_written"])
    assert rewritten_source["gallery_images"][0]["local_path"] == str(scrape_dir / "gallery" / f"{model}-1.jpg")


def test_render_workflow_writes_candidate_bundle(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")

    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    products_dir = tmp_path / "products"
    scrape_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code=model,
        brand="LG",
        name="Ψυγείο Ντουλάπα LG GSGV80PYLL Ασημί E",
        hero_summary="Το LG GSGV80PYLL προσφέρει μεγάλη χωρητικότητα.",
        price_text="2.099,00 €",
        price_value=2099.0,
        gallery_images=[GalleryImage(url="https://example.com/233541-1.jpg", position=1, local_filename="233541-1.jpg", downloaded=True)],
        besco_images=[GalleryImage(url="https://example.com/besco1.jpg", position=1, local_filename="besco1.jpg", downloaded=True)],
        key_specs=[
            SpecItem(label="Συνολική Καθαρή Χωρητικότητα", value="635"),
            SpecItem(label="Τεχνολογία Ψύξης", value="Total No Frost"),
            SpecItem(label="Συνδεσιμότητα", value="WiFi"),
        ],
        spec_sections=[
            SpecSection(section="Επισκόπηση Προϊόντος", items=[SpecItem(label="Τύπος Ψυγείου", value="Ντουλάπα")]),
        ],
    )
    source_json = scrape_dir / f"{model}.source.json"
    source_json.write_text(__import__("json").dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    normalized_payload = {
        "input": {
            "model": model,
            "url": "https://www.electronet.gr/example",
            "photos": 1,
            "sections": 1,
            "skroutz_status": 1,
            "boxnow": 0,
            "price": "2099",
            "out": str(scrape_dir),
        },
        "taxonomy": TaxonomyResolution(
            parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
            leaf_category="Ψυγεία & Καταψύκτες",
            sub_category="Ψυγεία Ντουλάπες",
            cta_url="https://www.etranoulis.gr/oikiakes-syskeues/psygeia-katapsyktes/psygeia-ntoulapes",
        ).to_dict(),
        "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9).to_dict(),
    }
    (scrape_dir / f"{model}.normalized.json").write_text(__import__("json").dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    llm_output = {
        "product": {
            "meta_description": "Το LG GSGV80PYLL είναι ψυγείο ντουλάπα 635 λίτρων με Total No Frost και WiFi για άνεση κάθε μέρα.",
            "meta_keywords": ["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα", "Total No Frost"],
        },
        "presentation": {
            "intro_html": build_intro(),
            "cta_text": "Δείτε περισσότερα ψυγεία ντουλάπες εδώ",
            "sections": [
                {
                    "title": "NatureFRESH για καθημερινή φρεσκάδα",
                    "body_html": "Το <strong>NatureFRESH</strong> βοηθά στη σωστή συντήρηση.",
                }
            ],
        },
    }
    (tmp_path / "work" / model / "llm_output.json").write_text(__import__("json").dumps(llm_output, ensure_ascii=False, indent=2), encoding="utf-8")

    result = render_workflow(model)

    assert result["candidate_csv_path"].exists()
    assert result["validation_report_path"].exists()
    assert "field_health" in result["validation_report"]
