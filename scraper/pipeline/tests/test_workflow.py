import argparse
import json
from pathlib import Path

import pytest

from pipeline.models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from pipeline.services import PrepareRequest, PublishRequest, RenderRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceError, ServiceErrorCode, ServiceResult
from pipeline.workflow import build_cli_input_from_args, build_parser, prepare_workflow, render_workflow, resolve_model_for_render


def build_intro(words: int = 120) -> str:
    return " ".join(["λέξη"] * words)


def write_split_llm_outputs(model_root: Path, *, intro_text: str, meta_description: str, meta_keywords: list[str]) -> None:
    llm_dir = model_root / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / "intro_text.output.txt").write_text(intro_text, encoding="utf-8")
    (llm_dir / "seo_meta.output.json").write_text(
        json.dumps(
            {
                "product": {
                    "meta_description": meta_description,
                    "meta_keywords": meta_keywords,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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


def test_build_parser_pins_supported_workflow_cli_surface() -> None:
    parser = build_parser()
    subparsers_action = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))

    assert parser.prog == "python -m pipeline.workflow"
    assert set(subparsers_action.choices) == {"prepare", "render"}

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["run"])

    assert excinfo.value.code == 2


def test_resolve_model_for_render_accepts_explicit_model_argument() -> None:
    args = argparse.Namespace(model="233541", template_file=None, stdin=False)

    assert resolve_model_for_render(args) == "233541"


def test_resolve_model_for_render_reads_model_from_template_file(tmp_path: Path) -> None:
    template = tmp_path / "render-input.txt"
    template.write_text("model: 233541\n", encoding="utf-8")
    args = argparse.Namespace(model=None, template_file=str(template), stdin=False)

    assert resolve_model_for_render(args) == "233541"


@pytest.mark.parametrize("model", [None, "", "23354", "233541a", "abc123", "2335417"])
def test_resolve_model_for_render_rejects_missing_or_invalid_model(model: str | None) -> None:
    from pipeline import workflow

    args = argparse.Namespace(model=model, template_file=None, stdin=False)

    with pytest.raises(ValueError) as excinfo:
        resolve_model_for_render(args)

    assert str(excinfo.value) == workflow.FAIL_MESSAGE


def test_prepare_workflow_delegates_to_service_execution(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    cli = CLIInput(model="233541", url="https://www.electronet.gr/example", photos=6, sections=2, skroutz_status=1, boxnow=0, price="2099", out=str(tmp_path))

    def fake_execute_prepare_stage(_cli, *, model_dir):
        assert model_dir == tmp_path / "work" / "233541" / "scrape"
        return {"unused": True}

    def fake_execute_prepare_workflow(cli_arg, *, work_root, execute_prepare_stage_fn):
        assert cli_arg is cli
        assert work_root == tmp_path / "work"
        assert execute_prepare_stage_fn is fake_execute_prepare_stage
        return {"delegated": True}

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "execute_prepare_stage", fake_execute_prepare_stage)
    monkeypatch.setattr(workflow, "execute_prepare_workflow", fake_execute_prepare_workflow)

    assert workflow.prepare_workflow(cli) == {"delegated": True}


def test_prepare_workflow_writes_prompt_artifacts(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

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

    def fake_execute_prepare_stage(_cli, *, model_dir):
        assert model_dir == tmp_path / "work" / "233541" / "scrape"
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

    monkeypatch.setattr(workflow, "execute_prepare_stage", fake_execute_prepare_stage)

    result = prepare_workflow(cli)

    assert result["llm_dir"].exists()
    assert result["task_manifest_path"].exists()
    assert result["intro_text_context_path"].exists()
    assert result["intro_text_prompt_path"].exists()
    assert result["seo_meta_context_path"].exists()
    assert result["seo_meta_prompt_path"].exists()
    assert result["metadata_path"].exists()
    task_manifest = json.loads(result["task_manifest_path"].read_text(encoding="utf-8"))
    intro_text_context = json.loads(result["intro_text_context_path"].read_text(encoding="utf-8"))
    seo_meta_context = json.loads(result["seo_meta_context_path"].read_text(encoding="utf-8"))
    intro_text_prompt = result["intro_text_prompt_path"].read_text(encoding="utf-8")
    seo_meta_prompt = result["seo_meta_prompt_path"].read_text(encoding="utf-8")
    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    assert task_manifest["prepare_mode"] == "split_tasks"
    assert task_manifest["primary_outputs"]["tasks"]["intro_text"]["context_path"] == str(result["intro_text_context_path"])
    assert task_manifest["primary_outputs"]["tasks"]["seo_meta"]["prompt_path"] == str(result["seo_meta_prompt_path"])
    assert intro_text_context["task"] == "intro_text"
    assert intro_text_context["writer_rules"]["plain_text_only"] is True
    assert intro_text_context["writer_rules"]["llm_owned_fields"] == ["intro_text"]
    assert "presentation_source_sections" not in intro_text_context
    assert "Do not use HTML." in intro_text_prompt
    assert "Do not use CTA language" in intro_text_prompt
    assert seo_meta_context["task"] == "seo_meta"
    assert seo_meta_context["writer_rules"]["required_keywords"] == ["LG", "GSGV80PYLL"]
    assert seo_meta_context["product"]["meta_title"] == "LG GSGV80PYLL Ψυγείο Ντουλάπα 635Lt | eTranoulis"
    assert "always include the provided brand and mpn/model values" in seo_meta_prompt
    assert result["metadata_path"].name == "prepare.run.json"
    assert metadata["run"]["model"] == "233541"
    assert metadata["run"]["run_type"] == "prepare"
    assert metadata["run"]["status"] == "completed"
    assert metadata["artifacts"]["llm_dir"] == str(result["llm_dir"])
    assert metadata["artifacts"]["llm_task_manifest_path"] == str(result["task_manifest_path"])
    assert metadata["artifacts"]["intro_text_context_path"] == str(result["intro_text_context_path"])
    assert metadata["artifacts"]["seo_meta_context_path"] == str(result["seo_meta_context_path"])
    assert metadata["artifacts"]["metadata_path"] == str(result["metadata_path"])
    assert metadata["details"]["llm_prepare_mode"] == "split_tasks"
    assert metadata["details"]["source"] == ""


def test_render_workflow_delegates_to_service_execution(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    def fake_execute_render_workflow(model, *, work_root, products_root):
        assert model == "233541"
        assert work_root == tmp_path / "work"
        assert products_root == tmp_path / "products"
        return {"delegated": True}

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")
    monkeypatch.setattr(workflow, "execute_render_workflow", fake_execute_render_workflow)

    assert workflow.render_workflow("233541") == {"delegated": True}


def test_prepare_workflow_keeps_prepare_scrape_only_without_candidate_csv(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")

    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    raw_html_path = scrape_dir / f"{model}.raw.html"
    source_json_path = scrape_dir / f"{model}.source.json"
    normalized_json_path = scrape_dir / f"{model}.normalized.json"
    report_json_path = scrape_dir / f"{model}.report.json"

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
    }
    report_payload = {"warnings": [], "files_written": [str(raw_html_path), str(source_json_path), str(normalized_json_path), str(report_json_path)]}

    parsed = ParsedProduct(
        source=SourceProductData(
            url="https://www.electronet.gr/example",
            canonical_url="https://www.electronet.gr/example",
            product_code=model,
            brand="LG",
            name="Ψυγείο Ντουλάπα LG GSGV80PYLL",
            raw_html_path=str(raw_html_path),
            gallery_images=[GalleryImage(url="https://example.com/1.jpg", local_path=str(scrape_dir / "gallery" / f"{model}-1.jpg"))],
            besco_images=[GalleryImage(url="https://example.com/besco1.jpg", local_path=str(scrape_dir / "bescos" / "besco1.jpg"))],
        )
    )
    cli = CLIInput(model=model, url="https://www.electronet.gr/example", photos=6, sections=2, skroutz_status=1, boxnow=0, price="2099", out=str(tmp_path))

    def fake_execute_prepare_stage(_cli, *, model_dir):
        assert model_dir == scrape_dir
        model_dir.mkdir(parents=True, exist_ok=True)
        raw_html_path.write_text("<html></html>", encoding="utf-8")
        source_json_path.write_text(
            json.dumps(
                {
                    "url": "https://www.electronet.gr/example",
                    "canonical_url": "https://www.electronet.gr/example",
                    "product_code": model,
                    "brand": "LG",
                    "name": "Ψυγείο Ντουλάπα LG GSGV80PYLL",
                    "raw_html_path": str(raw_html_path),
                    "gallery_images": [{"local_path": str(scrape_dir / "gallery" / f"{model}-1.jpg")}],
                    "besco_images": [{"local_path": str(scrape_dir / "bescos" / "besco1.jpg")}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        normalized_json_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report_json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
            "model_dir": scrape_dir,
            "raw_html_path": raw_html_path,
            "source_json_path": source_json_path,
            "normalized_json_path": normalized_json_path,
            "report_json_path": report_json_path,
        }

    monkeypatch.setattr(workflow, "execute_prepare_stage", fake_execute_prepare_stage)

    result = prepare_workflow(cli)
    assert result["scrape_result"]["model_dir"] == scrape_dir
    assert (scrape_dir / f"{model}.source.json").exists()
    assert (scrape_dir / f"{model}.normalized.json").exists()
    assert (scrape_dir / f"{model}.report.json").exists()
    assert not (scrape_dir / f"{model}.csv").exists()
    assert not (tmp_path / "work" / model / "candidate" / f"{model}.csv").exists()


def test_prepare_workflow_writes_failed_metadata_on_error(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    cli = CLIInput(model="233541", url="https://www.electronet.gr/example", photos=1, sections=0, skroutz_status=0, boxnow=0, price="0", out=str(tmp_path))

    def fake_execute_prepare_stage(_cli, *, model_dir):
        assert model_dir == tmp_path / "work" / "233541" / "scrape"
        raise RuntimeError("prepare exploded")

    monkeypatch.setattr(workflow, "execute_prepare_stage", fake_execute_prepare_stage)

    try:
        prepare_workflow(cli)
    except RuntimeError as exc:
        assert str(exc) == "prepare exploded"
    else:
        raise AssertionError("Expected RuntimeError")

    metadata_path = tmp_path / "work" / "233541" / "prepare.run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["run"]["status"] == "failed"
    assert metadata["run"]["error_code"] == ServiceErrorCode.UNEXPECTED_FAILURE.value
    assert metadata["run"]["error_detail"] == "prepare exploded"


def test_render_workflow_writes_candidate_bundle_when_publish_is_skipped(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

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
        presentation_source_html="""
        <section>
          <h3>NatureFRESH για καθημερινή φρεσκάδα</h3>
          <p>Το NatureFRESH βοηθά στη σωστή συντήρηση και υποστηρίζει σταθερή ψύξη σε όλη τη διάρκεια της ημέρας
          με καθαρή οργάνωση, πρακτική χρήση και άνετη πρόσβαση στα τρόφιμα για όλη την οικογένεια.</p>
        </section>
        """,
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

    write_split_llm_outputs(
        tmp_path / "work" / model,
        intro_text="Σύντομο κείμενο.",
        meta_description="Το LG GSGV80PYLL είναι ψυγείο ντουλάπα 635 λίτρων με Total No Frost και WiFi για άνεση κάθε μέρα.",
        meta_keywords=["LG", "GSGV80PYLL", "Ψυγείο Ντουλάπα", "Total No Frost"],
    )

    result = render_workflow(model)

    assert result["candidate_csv_path"].exists()
    assert result["published_csv_path"] is None
    assert result["validation_report_path"].exists()
    assert result["metadata_path"].exists()
    assert result["run_status"] == "failed"
    assert result["validation_report"]["ok"] is False
    assert "field_health" in result["validation_report"]
    assert result["validation_report"]["errors"] == ["llm_intro_text_word_count_invalid"]
    assert "Candidate failed validation; skipping publish to products/." in result["validation_report"]["warnings"]
    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    assert result["metadata_path"].name == "render.run.json"
    assert metadata["run"]["model"] == model
    assert metadata["run"]["run_type"] == "render"
    assert metadata["run"]["status"] == "failed"
    assert metadata["run"]["error_code"] == ServiceErrorCode.VALIDATION_FAILURE.value
    assert metadata["run"]["error_detail"] == "Candidate validation failed"
    assert metadata["artifacts"]["candidate_csv_path"] == str(result["candidate_csv_path"])
    assert metadata["artifacts"]["published_csv_path"] is None
    assert metadata["artifacts"]["validation_report_path"] == str(result["validation_report_path"])
    assert metadata["artifacts"]["metadata_path"] == str(result["metadata_path"])
    assert metadata["details"]["validation_ok"] is False
    assert metadata["details"]["published"] is False
    assert "upload_attempted" not in metadata["details"]
    assert "upload_ok" not in metadata["details"]
    assert "upload_report_path" not in metadata["details"]
    assert "upload_warning" not in metadata["details"]


def test_render_workflow_writes_failed_metadata_when_llm_output_is_missing(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")

    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    scrape_dir.mkdir(parents=True)
    source = SourceProductData(url="https://www.electronet.gr/example", canonical_url="https://www.electronet.gr/example", product_code=model, brand="LG", name="LG Example")
    (scrape_dir / f"{model}.source.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (scrape_dir / f"{model}.normalized.json").write_text(
        json.dumps(
            {
                "input": {
                    "model": model,
                    "url": "https://www.electronet.gr/example",
                    "photos": 1,
                    "sections": 0,
                    "skroutz_status": 0,
                    "boxnow": 0,
                    "price": "0",
                },
                "taxonomy": {},
                "schema_match": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        render_workflow(model)
    except FileNotFoundError as exc:
        assert str(exc) == f"Missing split-task LLM outputs in {tmp_path / 'work' / model / 'llm'}"
    else:
        raise AssertionError("Expected FileNotFoundError")

    metadata_path = tmp_path / "work" / model / "render.run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["run"]["status"] == "failed"
    assert metadata["run"]["error_code"] == ServiceErrorCode.MISSING_ARTIFACT.value
    assert "Missing split-task LLM outputs" in metadata["run"]["error_detail"]


def test_render_workflow_builds_description_from_split_outputs_and_deterministic_sections(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")

    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    scrape_dir.mkdir(parents=True)

    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code=model,
        brand="LG",
        mpn="GSGV80PYLL",
        name="Ψυγείο Ντουλάπα LG GSGV80PYLL Ασημί E",
        hero_summary="Το LG GSGV80PYLL προσφέρει μεγάλη χωρητικότητα.",
        price_text="2.099,00 €",
        price_value=2099.0,
        gallery_images=[GalleryImage(url="https://example.com/233541-1.jpg", position=1, local_filename="233541-1.jpg", downloaded=True)],
        besco_images=[
            GalleryImage(url="https://example.com/besco1.jpg", position=1, local_filename="besco1.jpg", downloaded=True),
            GalleryImage(url="https://example.com/besco2.jpg", position=2, local_filename="besco2.jpg", downloaded=True),
        ],
        key_specs=[
            SpecItem(label="Συνολική Καθαρή Χωρητικότητα", value="635"),
            SpecItem(label="Τεχνολογία Ψύξης", value="Total No Frost"),
            SpecItem(label="Συνδεσιμότητα", value="WiFi"),
        ],
        spec_sections=[SpecSection(section="Βασικά Χαρακτηριστικά", items=[SpecItem(label="Τύπος Ψυγείου", value="Ντουλάπα")])],
        presentation_source_html="""
        <section>
          <h3>NatureFRESH για καθημερινή φρεσκάδα</h3>
          <p>Το NatureFRESH βοηθά στη σωστή συντήρηση και διατηρεί σταθερή ψύξη σε όλο τον θάλαμο,
          προσφέροντας πρακτική οργάνωση και εύκολη καθημερινή πρόσβαση στα τρόφιμα με σταθερή απόδοση και άνεση.</p>
        </section>
        <section>
          <h3>DoorCooling+ για ομοιόμορφη ψύξη</h3>
          <p>Η λειτουργία DoorCooling+ ενισχύει την ομοιόμορφη κατανομή του αέρα και υποστηρίζει σταθερή ψύξη,
          ώστε τα τρόφιμα να παραμένουν οργανωμένα και προσβάσιμα με καθαρή και πρακτική καθημερινή χρήση.</p>
        </section>
        """,
    )
    (scrape_dir / f"{model}.source.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (scrape_dir / f"{model}.normalized.json").write_text(
        json.dumps(
            {
                "input": {
                    "model": model,
                    "url": "https://www.electronet.gr/example",
                    "photos": 1,
                    "sections": 2,
                    "skroutz_status": 1,
                    "boxnow": 0,
                    "price": "2099",
                },
                "taxonomy": TaxonomyResolution(
                    parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
                    leaf_category="Ψυγεία & Καταψύκτες",
                    sub_category="Ψυγεία Ντουλάπες",
                    cta_url="https://www.etranoulis.gr/oikiakes-syskeues/psygeia-katapsyktes/psygeia-ntoulapes",
                ).to_dict(),
                "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9).to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_split_llm_outputs(
        tmp_path / "work" / model,
        intro_text=build_intro(),
        meta_description="Το LG GSGV80PYLL είναι ψυγείο ντουλάπα 635 λίτρων με Total No Frost και WiFi για άνεση κάθε μέρα.",
        meta_keywords=["Ψυγεία Ντουλάπες", "Ψυγείο Ντουλάπα", "Total No Frost"],
    )

    result = render_workflow(model)
    description = result["description_path"].read_text(encoding="utf-8")
    candidate_row = next(__import__("csv").DictReader(result["candidate_csv_path"].open("r", encoding="utf-8-sig", newline="")))

    assert result["run_status"] == "completed"
    assert result["published_csv_path"] == tmp_path / "products" / f"{model}.csv"
    assert "NatureFRESH για καθημερινή φρεσκάδα" in description
    assert "DoorCooling+ για ομοιόμορφη ψύξη" in description
    assert "λέξη λέξη λέξη" in description
    assert candidate_row["meta_keyword"].startswith("LG, GSGV80PYLL")
    assert candidate_row["meta_keyword"].count("Ψυγ") == 1

    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["details"]["validation_ok"] is True
    assert metadata["details"]["published"] is True
    assert "upload_attempted" not in metadata["details"]

def test_workflow_main_render_reports_publish_failure_without_failing_render(monkeypatch, capsys, tmp_path: Path) -> None:
    from pipeline import workflow

    def fake_resolve_model_for_render(_args) -> str:
        return "233541"

    def fake_render_product(request: RenderRequest) -> ServiceResult:
        assert request.model == "233541"
        return ServiceResult(
            run=RunMetadata(model="233541", run_type=RunType.RENDER, status=RunStatus.COMPLETED),
            artifacts=RunArtifacts(
                candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
                published_csv_path=tmp_path / "products" / "233541.csv",
                validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
                metadata_path=tmp_path / "work" / "233541" / "render.run.json",
            ),
            details={"validation_ok": True, "published": True},
        )

    def fake_publish_product(request: PublishRequest) -> ServiceResult:
        assert request.model == "233541"
        assert request.current_job_product_file == tmp_path / "products" / "233541.csv"
        return ServiceResult(
            run=RunMetadata(
                model="233541",
                run_type=RunType.PUBLISH,
                status=RunStatus.FAILED,
                warnings=["OpenCart publish failed during image_upload: exit=12"],
            ),
            artifacts=RunArtifacts(metadata_path=tmp_path / "work" / "233541" / "publish.run.json"),
            details={
                "publish_attempted": True,
                "publish_status": "failed",
                "publish_stage": "image_upload",
                "publish_message": "OpenCart publish failed during image_upload: exit=12",
                "upload_report_path": str(tmp_path / "work" / "233541" / "upload.opencart.json"),
                "import_report_path": str(tmp_path / "work" / "233541" / "import.opencart.json"),
            },
        )

    monkeypatch.setattr(workflow, "resolve_model_for_render", fake_resolve_model_for_render)
    monkeypatch.setattr(workflow, "render_product", fake_render_product)
    monkeypatch.setattr(workflow, "publish_product", fake_publish_product)

    exit_code = workflow.main(["render"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Render status: success" in captured.out
    assert "Publish status: failed" in captured.out
    assert "Publish stage: image_upload" in captured.out
    assert "Publish message: OpenCart publish failed during image_upload: exit=12" in captured.out
    assert f"OpenCart upload report: {tmp_path / 'work' / '233541' / 'upload.opencart.json'}" in captured.out
    assert f"OpenCart import report: {tmp_path / 'work' / '233541' / 'import.opencart.json'}" in captured.out
    assert f"Publish metadata path: {tmp_path / 'work' / '233541' / 'publish.run.json'}" in captured.out
    return

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")

    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    scrape_dir.mkdir(parents=True)

    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code=model,
        brand="LG",
        mpn="GSGV80PYLL",
        name="LG Example Product",
        hero_summary="Example summary for validation coverage.",
        price_text="999,00 €",
        price_value=999.0,
        gallery_images=[GalleryImage(url="https://example.com/233541-1.jpg", position=1, local_filename="233541-1.jpg", downloaded=True)],
        key_specs=[SpecItem(label="Power", value="2200 W")],
        spec_sections=[SpecSection(section="Specs", items=[SpecItem(label="Type", value="Example")])],
        presentation_source_html="""
        <section>
          <h3>Example section</h3>
          <p>This section provides a clearly written product explanation with enough descriptive text about performance, daily use, practical convenience, and overall behavior to remain usable during deterministic rendering for the final product description output.</p>
        </section>
        """,
    )
    (scrape_dir / f"{model}.source.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (scrape_dir / f"{model}.normalized.json").write_text(
        json.dumps(
            {
                "input": {
                    "model": model,
                    "url": source.url,
                    "photos": 1,
                    "sections": 1,
                    "skroutz_status": 0,
                    "boxnow": 0,
                    "price": "0",
                },
                "taxonomy": TaxonomyResolution(
                    parent_category="Home",
                    leaf_category="Example",
                    sub_category="Examples",
                    cta_url="https://example.com",
                ).to_dict(),
                "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9).to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_split_llm_outputs(
        tmp_path / "work" / model,
        intro_text=build_intro(),
        meta_description="Valid meta description for upload warning coverage.",
        meta_keywords=["LG", "GSGV80PYLL", "Example"],
    )
    monkeypatch.setattr(
        render_execution,
        "_run_opencart_image_upload",
        lambda **_kwargs: {
            "upload_attempted": True,
            "upload_ok": False,
            "upload_report_path": render_execution.REPO_ROOT / "work" / model / "upload.opencart.json",
            "upload_warning": "opencart_image_upload_failed: exit=1: upload failed",
        },
    )

    result = render_workflow(model)

    assert result["run_status"] == "completed"
    assert result["published_csv_path"] == tmp_path / "products" / f"{model}.csv"
    assert result["upload_attempted"] is True
    assert result["upload_ok"] is False
    assert result["upload_warning"] == "opencart_image_upload_failed: exit=1: upload failed"
    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    assert metadata["run"]["status"] == "completed"
    assert "opencart_image_upload_failed: exit=1: upload failed" in metadata["run"]["warnings"]
    assert metadata["details"]["upload_attempted"] is True
    assert metadata["details"]["upload_ok"] is False
    assert metadata["details"]["upload_warning"] == "opencart_image_upload_failed: exit=1: upload failed"


def test_execute_publish_workflow_passes_model_and_current_job_product_file(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import publish_execution

    repo_root = tmp_path
    model = "233541"
    script_path = repo_root / "tools" / "run_opencart_pipeline.sh"
    current_job_product_file = repo_root / "products" / "233541.csv"
    main_image_path = repo_root / "work" / model / "scrape" / "gallery" / f"{model}-1.jpg"
    (repo_root / "work" / model).mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    current_job_product_file.parent.mkdir(parents=True)
    main_image_path.parent.mkdir(parents=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    current_job_product_file.write_text("header\nvalue\n", encoding="utf-8")
    main_image_path.write_text("image", encoding="utf-8")
    captured: dict[str, object] = {}
    calls: list[list[str]] = []

    class DummyCompleted:
        def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, *, cwd, capture_output, text, check, env=None):
        calls.append(cmd)
        captured["cwd"] = cwd
        captured["env"] = env
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        if cmd[-1] == "--version":
            return DummyCompleted(0, "GNU bash, version 5.2.0\n", "")
        captured["cmd"] = cmd
        return DummyCompleted(0, "[opencart-publish] ok\n", "")

    monkeypatch.setattr(publish_execution.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)
    monkeypatch.setattr(publish_execution.subprocess, "run", fake_run)

    result = publish_execution.execute_publish_workflow(
        repo_root=repo_root,
        work_root=repo_root / "work",
        products_root=repo_root / "products",
        model=model,
        current_job_product_file=current_job_product_file,
    )

    assert calls == [
        ["/usr/bin/bash", "--version"],
        ["/usr/bin/bash", "tools/run_opencart_pipeline.sh", model],
    ]
    assert captured["cmd"] == ["/usr/bin/bash", "tools/run_opencart_pipeline.sh", model]
    assert captured["cwd"] == repo_root
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
    assert captured["env"]["CURRENT_JOB_PRODUCT_FILE"] == "products/233541.csv"
    assert "REPO_ROOT" not in captured["env"]
    assert result["publish_attempted"] is True
    assert result["publish_status"] == "warning"
    assert result["publish_stage"] == "csv_import"
    assert result["upload_report_path"] == repo_root / "work" / model / "upload.opencart.json"
    assert result["import_report_path"] == repo_root / "work" / model / "import.opencart.json"
    return

    repo_root = tmp_path
    script_path = repo_root / "tools" / "run_opencart_image_upload.sh"
    current_job_product_file = repo_root / "products" / "233541.csv"
    script_path.parent.mkdir(parents=True)
    current_job_product_file.parent.mkdir(parents=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    current_job_product_file.write_text("header\nvalue\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class DummyCompleted:
        returncode = 0
        stdout = "[opencart-upload] ok\n"
        stderr = ""

    def fake_run(cmd, *, cwd, env, capture_output, text, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        return DummyCompleted()

    monkeypatch.setattr(render_execution.subprocess, "run", fake_run)

    result = render_execution._run_opencart_image_upload(
        repo_root=repo_root,
        model="233541",
        current_job_product_file=current_job_product_file,
    )

    assert captured["cmd"] == ["bash", str(script_path)]
    assert captured["cwd"] == repo_root
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
    assert captured["env"]["CURRENT_JOB_PRODUCT_FILE"] == str(current_job_product_file)
    assert captured["env"]["REPO_ROOT"] == str(repo_root)
    assert result["upload_attempted"] is True
    assert result["upload_ok"] is True
    assert result["upload_report_path"] == repo_root / "work" / "233541" / "upload.opencart.json"
    assert result["upload_warning"] is None


def test_execute_publish_workflow_fails_preflight_when_bash_is_missing(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import publish_execution

    repo_root = tmp_path
    model = "233541"
    script_path = repo_root / "tools" / "run_opencart_pipeline.sh"
    current_job_product_file = repo_root / "products" / "233541.csv"
    main_image_path = repo_root / "work" / model / "scrape" / "gallery" / f"{model}-1.jpg"
    script_path.parent.mkdir(parents=True)
    current_job_product_file.parent.mkdir(parents=True)
    main_image_path.parent.mkdir(parents=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    current_job_product_file.write_text("header\nvalue\n", encoding="utf-8")
    main_image_path.write_text("image", encoding="utf-8")

    monkeypatch.setattr(publish_execution.shutil, "which", lambda _name: None)

    result = publish_execution.execute_publish_workflow(
        repo_root=repo_root,
        work_root=repo_root / "work",
        products_root=repo_root / "products",
        model=model,
        current_job_product_file=current_job_product_file,
    )

    assert result["publish_status"] == "failed"
    assert result["publish_stage"] == "preflight"
    assert result["publish_message"] == "OpenCart publish failed during preflight: bash executable not found on PATH"


def test_execute_publish_workflow_classifies_wsl_launcher_probe_failures(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import publish_execution

    repo_root = tmp_path
    model = "233541"
    script_path = repo_root / "tools" / "run_opencart_pipeline.sh"
    current_job_product_file = repo_root / "products" / "233541.csv"
    main_image_path = repo_root / "work" / model / "scrape" / "gallery" / f"{model}-1.jpg"
    script_path.parent.mkdir(parents=True)
    current_job_product_file.parent.mkdir(parents=True)
    main_image_path.parent.mkdir(parents=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    current_job_product_file.write_text("header\nvalue\n", encoding="utf-8")
    main_image_path.write_text("image", encoding="utf-8")

    class DummyCompleted:
        returncode = 1
        stdout = "Error code: Wsl/Service/CreateInstance/0xd0000022\n"
        stderr = ""

    monkeypatch.setattr(publish_execution.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)
    monkeypatch.setattr(publish_execution.subprocess, "run", lambda *args, **kwargs: DummyCompleted())

    result = publish_execution.execute_publish_workflow(
        repo_root=repo_root,
        work_root=repo_root / "work",
        products_root=repo_root / "products",
        model=model,
        current_job_product_file=current_job_product_file,
    )

    assert result["publish_status"] == "failed"
    assert result["publish_stage"] == "preflight"
    assert "bash_or_wsl_startup_failure" in str(result["publish_message"])
    assert "CreateInstance/0xd0000022" in str(result["publish_message"])


def test_execute_publish_workflow_fails_preflight_when_main_image_is_missing(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import publish_execution

    repo_root = tmp_path
    model = "233541"
    script_path = repo_root / "tools" / "run_opencart_pipeline.sh"
    current_job_product_file = repo_root / "products" / "233541.csv"
    script_path.parent.mkdir(parents=True)
    current_job_product_file.parent.mkdir(parents=True)
    (repo_root / "work" / model / "scrape").mkdir(parents=True)
    script_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    current_job_product_file.write_text("header\nvalue\n", encoding="utf-8")

    # Missing gallery/<model>-1.jpg should be reported before shell invocation.
    monkeypatch.setattr(publish_execution.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None)

    result = publish_execution.execute_publish_workflow(
        repo_root=repo_root,
        work_root=repo_root / "work",
        products_root=repo_root / "products",
        model=model,
        current_job_product_file=current_job_product_file,
    )

    assert result["publish_status"] == "failed"
    assert result["publish_stage"] == "preflight"
    assert "missing gallery image" in str(result["publish_message"])

def test_render_workflow_fails_when_source_sections_are_missing_entirely(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    scrape_dir.mkdir(parents=True)
    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code=model,
        brand="LG",
        mpn="GSGV80PYLL",
        name="LG Example",
    )
    (scrape_dir / f"{model}.source.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (scrape_dir / f"{model}.normalized.json").write_text(
        json.dumps(
            {
                "input": {"model": model, "url": source.url, "photos": 1, "sections": 1, "skroutz_status": 0, "boxnow": 0, "price": "0"},
                "taxonomy": TaxonomyResolution(cta_url="https://example.com", leaf_category="Ψυγεία & Καταψύκτες").to_dict(),
                "schema_match": SchemaMatchResult().to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_split_llm_outputs(
        tmp_path / "work" / model,
        intro_text=build_intro(),
        meta_description="Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με άνετη καθημερινή χρήση.",
        meta_keywords=["LG", "GSGV80PYLL"],
    )

    with pytest.raises(ValueError) as excinfo:
        render_workflow(model)

    assert str(excinfo.value) == "Missing presentation source sections for requested render sections"


def test_render_workflow_warns_and_continues_when_one_requested_section_is_missing(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")
    model = "233541"
    scrape_dir = tmp_path / "work" / model / "scrape"
    scrape_dir.mkdir(parents=True)
    source = SourceProductData(
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code=model,
        brand="LG",
        mpn="GSGV80PYLL",
        name="LG Example",
        spec_sections=[SpecSection(section="Βασικά Χαρακτηριστικά", items=[SpecItem(label="Τύπος Ψυγείου", value="Ντουλάπα")])],
        presentation_source_html="""
        <section>
          <h3>Κανονική ενότητα</h3>
          <p>Η συγκεκριμένη ενότητα περιγράφει καθαρά τη λειτουργία της συσκευής με αρκετές λέξεις και
          σταθερό περιεχόμενο ώστε να θεωρείται χρήσιμη για τελική προβολή στη σελίδα προϊόντος.</p>
        </section>
        <section>
          <h3>Εικόνα μόνο</h3>
          <img src="https://example.com/image.jpg" />
        </section>
        """,
        besco_images=[GalleryImage(url="https://example.com/besco1.jpg", position=1, local_filename="besco1.jpg", downloaded=True)],
    )
    (scrape_dir / f"{model}.source.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (scrape_dir / f"{model}.normalized.json").write_text(
        json.dumps(
            {
                "input": {"model": model, "url": source.url, "photos": 1, "sections": 2, "skroutz_status": 0, "boxnow": 0, "price": "0"},
                "taxonomy": TaxonomyResolution(parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ", cta_url="https://example.com", leaf_category="Ψυγεία & Καταψύκτες").to_dict(),
                "schema_match": SchemaMatchResult().to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_split_llm_outputs(
        tmp_path / "work" / model,
        intro_text=build_intro(),
        meta_description="Το LG GSGV80PYLL είναι ψυγείο ντουλάπα με άνετη καθημερινή χρήση.",
        meta_keywords=["Ψυγείο Ντουλάπες", "Ψυγείο Ντουλάπα"],
    )

    result = render_workflow(model)
    description = result["description_path"].read_text(encoding="utf-8")

    assert result["run_status"] == "completed"
    assert "Κανονική ενότητα" in description
    assert result["validation_report"]["ok"] is True
    assert "presentation_sections_missing:1" in result["validation_report"]["warnings"]
    assert "requested_sections_reduced:1" in result["validation_report"]["warnings"]


def test_workflow_main_prepare_routes_through_prepare_service(monkeypatch, capsys, tmp_path: Path) -> None:
    from pipeline import workflow

    cli = CLIInput(
        model="233541",
        url="https://www.electronet.gr/example",
        photos=2,
        sections=1,
        skroutz_status=1,
        boxnow=0,
        price="2099",
        out=str(tmp_path),
    )

    def fake_build_cli_input_from_args(_args):
        return cli

    def fake_prepare_product(request: PrepareRequest) -> ServiceResult:
        assert request.model == cli.model
        assert request.url == cli.url
        assert request.photos == cli.photos
        assert request.sections == cli.sections
        assert request.skroutz_status == cli.skroutz_status
        assert request.boxnow == cli.boxnow
        assert request.price == cli.price
        return ServiceResult(
            run=RunMetadata(model=cli.model, run_type=RunType.PREPARE, status=RunStatus.COMPLETED),
            artifacts=RunArtifacts(
                scrape_dir=tmp_path / "work" / cli.model / "scrape",
                llm_task_manifest_path=tmp_path / "work" / cli.model / "llm" / "task_manifest.json",
                intro_text_context_path=tmp_path / "work" / cli.model / "llm" / "intro_text.context.json",
                intro_text_prompt_path=tmp_path / "work" / cli.model / "llm" / "intro_text.prompt.txt",
                seo_meta_context_path=tmp_path / "work" / cli.model / "llm" / "seo_meta.context.json",
                seo_meta_prompt_path=tmp_path / "work" / cli.model / "llm" / "seo_meta.prompt.txt",
                metadata_path=tmp_path / "work" / cli.model / "prepare.run.json",
            ),
        )

    monkeypatch.setattr(workflow, "build_cli_input_from_args", fake_build_cli_input_from_args)
    monkeypatch.setattr(workflow, "prepare_product", fake_prepare_product)

    exit_code = workflow.main(["prepare"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Scrape artifacts: {tmp_path / 'work' / cli.model / 'scrape'}" in captured.out
    assert f"LLM task manifest: {tmp_path / 'work' / cli.model / 'llm' / 'task_manifest.json'}" in captured.out
    assert f"Intro task context: {tmp_path / 'work' / cli.model / 'llm' / 'intro_text.context.json'}" in captured.out
    assert f"Intro task prompt: {tmp_path / 'work' / cli.model / 'llm' / 'intro_text.prompt.txt'}" in captured.out
    assert f"SEO task context: {tmp_path / 'work' / cli.model / 'llm' / 'seo_meta.context.json'}" in captured.out
    assert f"SEO task prompt: {tmp_path / 'work' / cli.model / 'llm' / 'seo_meta.prompt.txt'}" in captured.out
    assert "Run status: completed" in captured.out
    assert f"Metadata path: {tmp_path / 'work' / cli.model / 'prepare.run.json'}" in captured.out


def test_workflow_main_render_routes_through_render_service(monkeypatch, capsys, tmp_path: Path) -> None:
    from pipeline import workflow

    def fake_resolve_model_for_render(_args) -> str:
        return "233541"

    def fake_render_product(request: RenderRequest) -> ServiceResult:
        assert request.model == "233541"
        return ServiceResult(
            run=RunMetadata(model="233541", run_type=RunType.RENDER, status=RunStatus.COMPLETED),
            artifacts=RunArtifacts(
                candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
                published_csv_path=tmp_path / "products" / "233541.csv",
                validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
                metadata_path=tmp_path / "work" / "233541" / "render.run.json",
            ),
            details={"validation_ok": True, "published": True},
        )

    def fake_publish_product(request: PublishRequest) -> ServiceResult:
        assert request.model == "233541"
        assert request.current_job_product_file == tmp_path / "products" / "233541.csv"
        return ServiceResult(
            run=RunMetadata(model="233541", run_type=RunType.PUBLISH, status=RunStatus.COMPLETED),
            artifacts=RunArtifacts(metadata_path=tmp_path / "work" / "233541" / "publish.run.json"),
            details={
                "publish_attempted": True,
                "publish_status": "success",
                "publish_stage": "csv_import",
                "publish_message": "OpenCart publish completed successfully.",
                "upload_report_path": str(tmp_path / "work" / "233541" / "upload.opencart.json"),
                "import_report_path": str(tmp_path / "work" / "233541" / "import.opencart.json"),
            },
        )

    monkeypatch.setattr(workflow, "resolve_model_for_render", fake_resolve_model_for_render)
    monkeypatch.setattr(workflow, "render_product", fake_render_product)
    monkeypatch.setattr(workflow, "publish_product", fake_publish_product)

    exit_code = workflow.main(["render"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Candidate CSV: {tmp_path / 'work' / '233541' / 'candidate' / '233541.csv'}" in captured.out
    assert f"Published CSV: {tmp_path / 'products' / '233541.csv'}" in captured.out
    assert f"Validation report: {tmp_path / 'work' / '233541' / 'candidate' / '233541.validation.json'}" in captured.out
    assert "Validation ok: True" in captured.out
    assert "Render status: success" in captured.out
    assert "Publish status: success" in captured.out
    assert "Publish stage: csv_import" in captured.out
    assert "Publish message: OpenCart publish completed successfully." in captured.out
    assert f"OpenCart upload report: {tmp_path / 'work' / '233541' / 'upload.opencart.json'}" in captured.out
    assert f"OpenCart import report: {tmp_path / 'work' / '233541' / 'import.opencart.json'}" in captured.out
    assert "Run status: completed" in captured.out
    assert f"Metadata path: {tmp_path / 'work' / '233541' / 'render.run.json'}" in captured.out
    assert f"Publish metadata path: {tmp_path / 'work' / '233541' / 'publish.run.json'}" in captured.out


@pytest.mark.parametrize(
    ("service_code", "expected_exit"),
    [
        (ServiceErrorCode.MISSING_ARTIFACT.value, 3),
        (ServiceErrorCode.PROVIDER_FAILURE.value, 4),
        (ServiceErrorCode.PARSE_FAILURE.value, 6),
        (ServiceErrorCode.PUBLISH_FAILURE.value, 7),
        (ServiceErrorCode.UNEXPECTED_FAILURE.value, 8),
    ],
)
def test_workflow_main_maps_service_error_codes_to_explicit_exit_codes(monkeypatch, capsys, service_code: str, expected_exit: int) -> None:
    from pipeline import workflow

    def fake_build_cli_input_from_args(_args):
        return CLIInput(
            model="233541",
            url="https://www.electronet.gr/example",
            photos=2,
            sections=1,
            skroutz_status=1,
            boxnow=0,
            price="2099",
            out="out",
        )

    def fake_prepare_product(_request: PrepareRequest) -> ServiceResult:
        raise ServiceError(service_code, f"{service_code} message")

    monkeypatch.setattr(workflow, "build_cli_input_from_args", fake_build_cli_input_from_args)
    monkeypatch.setattr(workflow, "prepare_product", fake_prepare_product)

    exit_code = workflow.main(["prepare"])
    captured = capsys.readouterr()

    assert exit_code == expected_exit
    assert f"{service_code} message" in captured.err


def test_workflow_main_render_uses_validation_failure_exit_code(monkeypatch, capsys, tmp_path: Path) -> None:
    from pipeline import workflow

    def fake_resolve_model_for_render(_args) -> str:
        return "233541"

    def fake_render_product(request: RenderRequest) -> ServiceResult:
        assert request.model == "233541"
        return ServiceResult(
            run=RunMetadata(
                model="233541",
                run_type=RunType.RENDER,
                status=RunStatus.FAILED,
                error_code=ServiceErrorCode.VALIDATION_FAILURE.value,
                error_detail="Candidate validation failed",
            ),
            artifacts=RunArtifacts(
                candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
                validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
                metadata_path=tmp_path / "work" / "233541" / "render.run.json",
            ),
            details={"validation_ok": False},
        )

    monkeypatch.setattr(workflow, "resolve_model_for_render", fake_resolve_model_for_render)
    monkeypatch.setattr(workflow, "render_product", fake_render_product)

    exit_code = workflow.main(["render"])
    captured = capsys.readouterr()

    assert exit_code == 5
    assert "Validation ok: False" in captured.out

