from pathlib import Path

from pipeline.models import ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from pipeline.services.execution_models import PrepareExecutionResult, RenderExecutionResult
from pipeline.services.models import RunStatus


def test_prepare_execution_result_from_mapping_matches_current_prepare_payload(tmp_path: Path) -> None:
    payload = {
        "model_root": tmp_path / "work" / "233541",
        "scrape_dir": tmp_path / "work" / "233541" / "scrape",
        "llm_dir": tmp_path / "work" / "233541" / "llm",
        "task_manifest_path": tmp_path / "work" / "233541" / "llm" / "task_manifest.json",
        "intro_text_context_path": tmp_path / "work" / "233541" / "llm" / "intro_text.context.json",
        "intro_text_prompt_path": tmp_path / "work" / "233541" / "llm" / "intro_text.prompt.txt",
        "intro_text_output_path": tmp_path / "work" / "233541" / "llm" / "intro_text.output.txt",
        "seo_meta_context_path": tmp_path / "work" / "233541" / "llm" / "seo_meta.context.json",
        "seo_meta_prompt_path": tmp_path / "work" / "233541" / "llm" / "seo_meta.prompt.txt",
        "seo_meta_output_path": tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json",
        "run_status": "completed",
        "metadata_path": tmp_path / "work" / "233541" / "prepare.run.json",
        "scrape_result": {
            "source": "electronet",
            "parsed": ParsedProduct(
                source=SourceProductData(
                    url="https://www.electronet.gr/example",
                    canonical_url="https://www.electronet.gr/example",
                    product_code="233541",
                    brand="LG",
                    name="LG Example",
                )
            ),
            "taxonomy": TaxonomyResolution(
                parent_category="A",
                leaf_category="B",
                sub_category="C",
                taxonomy_path="A > B > C",
            ),
            "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9),
            "report": {"warnings": ["prepare warning"]},
        },
    }

    result = PrepareExecutionResult.from_mapping(payload)

    assert result.model_root == tmp_path / "work" / "233541"
    assert result.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.llm_dir == tmp_path / "work" / "233541" / "llm"
    assert result.task_manifest_path == tmp_path / "work" / "233541" / "llm" / "task_manifest.json"
    assert result.intro_text_context_path == tmp_path / "work" / "233541" / "llm" / "intro_text.context.json"
    assert result.intro_text_prompt_path == tmp_path / "work" / "233541" / "llm" / "intro_text.prompt.txt"
    assert result.intro_text_output_path == tmp_path / "work" / "233541" / "llm" / "intro_text.output.txt"
    assert result.seo_meta_context_path == tmp_path / "work" / "233541" / "llm" / "seo_meta.context.json"
    assert result.seo_meta_prompt_path == tmp_path / "work" / "233541" / "llm" / "seo_meta.prompt.txt"
    assert result.seo_meta_output_path == tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json"
    assert result.run_status == RunStatus.COMPLETED
    assert result.metadata_path == tmp_path / "work" / "233541" / "prepare.run.json"
    assert result.scrape_result.source == "electronet"
    assert result.scrape_result.parsed is payload["scrape_result"]["parsed"]
    assert result.scrape_result.taxonomy is payload["scrape_result"]["taxonomy"]
    assert result.scrape_result.schema_match is payload["scrape_result"]["schema_match"]
    assert result.scrape_result.report_warnings == ["prepare warning"]
    assert result.payload == payload


def test_render_execution_result_from_mapping_matches_current_render_payload(tmp_path: Path) -> None:
    payload = {
        "candidate_dir": tmp_path / "work" / "233541" / "candidate",
        "candidate_csv_path": tmp_path / "work" / "233541" / "candidate" / "233541.csv",
        "published_csv_path": None,
        "description_path": tmp_path / "work" / "233541" / "candidate" / "description.html",
        "characteristics_path": tmp_path / "work" / "233541" / "candidate" / "characteristics.html",
        "validation_report_path": tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
        "run_status": "failed",
        "metadata_path": tmp_path / "work" / "233541" / "render.run.json",
        "validation_report": {
            "ok": False,
            "warnings": ["render warning"],
            "errors": ["llm_intro_text_word_count_invalid"],
        },
    }

    result = RenderExecutionResult.from_mapping(payload)

    assert result.candidate_dir == tmp_path / "work" / "233541" / "candidate"
    assert result.candidate_csv_path == tmp_path / "work" / "233541" / "candidate" / "233541.csv"
    assert result.published_csv_path is None
    assert result.description_path == tmp_path / "work" / "233541" / "candidate" / "description.html"
    assert result.characteristics_path == tmp_path / "work" / "233541" / "candidate" / "characteristics.html"
    assert result.validation_report_path == tmp_path / "work" / "233541" / "candidate" / "233541.validation.json"
    assert result.run_status == RunStatus.FAILED
    assert result.metadata_path == tmp_path / "work" / "233541" / "render.run.json"
    assert result.validation_report.ok is False
    assert result.validation_report.warnings == ["render warning"]
    assert result.validation_report.payload == payload["validation_report"]
    assert result.model_root == tmp_path / "work" / "233541"
    assert result.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.llm_dir == tmp_path / "work" / "233541" / "llm"
    assert result.payload == payload
