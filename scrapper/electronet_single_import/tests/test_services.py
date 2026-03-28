from pathlib import Path

import pytest

from electronet_single_import.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from electronet_single_import.services import (
    FullRunRequest,
    PrepareRequest,
    RenderRequest,
    RunArtifacts,
    RunMetadata,
    RunStatus,
    RunType,
    ServiceError,
    ServiceResult,
    prepare_product,
    run_product,
    render_product,
)


def test_prepare_product_maps_workflow_result(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")

    def fake_prepare_workflow(cli):
        assert cli.model == "233541"
        assert cli.url == "https://www.electronet.gr/example"
        assert cli.photos == 6
        assert cli.sections == 2
        assert cli.skroutz_status == 1
        assert cli.boxnow == 0
        assert str(cli.price) == "2099"
        assert cli.out == str(tmp_path / "work" / "233541" / "scrape")
        return {
            "model_root": tmp_path / "work" / "233541",
            "scrape_dir": tmp_path / "work" / "233541" / "scrape",
            "llm_context_path": tmp_path / "work" / "233541" / "llm_context.json",
            "prompt_path": tmp_path / "work" / "233541" / "prompt.txt",
            "run_status": "completed",
            "metadata_path": tmp_path / "work" / "233541" / "prepare.run.json",
            "scrape_result": {
                "source": "electronet",
                "report": {"warnings": ["prepare warning"]},
            },
        }

    monkeypatch.setattr(workflow, "prepare_workflow", fake_prepare_workflow)

    result = prepare_product(
        PrepareRequest(
            model="233541",
            url="https://www.electronet.gr/example",
            photos=6,
            sections=2,
            skroutz_status=1,
            boxnow=0,
            price="2099",
        )
    )

    assert result.run.model == "233541"
    assert result.run.run_type == RunType.PREPARE
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.warnings == ["prepare warning"]
    assert result.artifacts.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.artifacts.source_json_path == tmp_path / "work" / "233541" / "scrape" / "233541.source.json"
    assert result.artifacts.llm_output_path == tmp_path / "work" / "233541" / "llm_output.json"
    assert result.artifacts.metadata_path == tmp_path / "work" / "233541" / "prepare.run.json"
    assert result.details["source"] == "electronet"


def test_prepare_product_wraps_workflow_errors(monkeypatch) -> None:
    from electronet_single_import import workflow

    def fake_prepare_workflow(_cli):
        raise RuntimeError("prepare exploded")

    monkeypatch.setattr(workflow, "prepare_workflow", fake_prepare_workflow)

    with pytest.raises(ServiceError) as excinfo:
        prepare_product(PrepareRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == "RuntimeError"
    assert excinfo.value.message == "prepare exploded"
    assert isinstance(excinfo.value.cause, RuntimeError)


def test_render_product_maps_workflow_result(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    def fake_render_workflow(model: str):
        assert model == "233541"
        return {
            "candidate_dir": tmp_path / "work" / model / "candidate",
            "candidate_csv_path": tmp_path / "work" / model / "candidate" / f"{model}.csv",
            "published_csv_path": tmp_path / "products" / f"{model}.csv",
            "description_path": tmp_path / "work" / model / "candidate" / "description.html",
            "characteristics_path": tmp_path / "work" / model / "candidate" / "characteristics.html",
            "validation_report_path": tmp_path / "work" / model / "candidate" / f"{model}.validation.json",
            "run_status": "completed",
            "metadata_path": tmp_path / "work" / model / "render.run.json",
            "validation_report": {"ok": True, "warnings": ["render warning"]},
        }

    monkeypatch.setattr(workflow, "render_workflow", fake_render_workflow)

    result = render_product(RenderRequest(model="233541"))

    assert result.run.model == "233541"
    assert result.run.run_type == RunType.RENDER
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.warnings == ["render warning"]
    assert result.artifacts.model_root == tmp_path / "work" / "233541"
    assert result.artifacts.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.artifacts.candidate_csv_path == tmp_path / "work" / "233541" / "candidate" / "233541.csv"
    assert result.artifacts.metadata_path == tmp_path / "work" / "233541" / "render.run.json"
    assert result.details["validation_ok"] is True


def test_render_product_wraps_workflow_errors(monkeypatch) -> None:
    from electronet_single_import import workflow

    def fake_render_workflow(_model: str):
        raise FileNotFoundError("Missing LLM output")

    monkeypatch.setattr(workflow, "render_workflow", fake_render_workflow)

    with pytest.raises(ServiceError) as excinfo:
        render_product(RenderRequest(model="233541"))

    assert excinfo.value.code == "FileNotFoundError"
    assert excinfo.value.message == "Missing LLM output"
    assert isinstance(excinfo.value.cause, FileNotFoundError)


def test_run_product_maps_cli_result(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import cli as cli_module

    source = SourceProductData(
        source_name="electronet",
        url="https://www.electronet.gr/example",
        canonical_url="https://www.electronet.gr/example",
        product_code="233541",
        brand="LG",
        name="LG Example",
    )
    parsed = ParsedProduct(source=source)
    taxonomy = TaxonomyResolution(
        parent_category="A",
        leaf_category="B",
        sub_category="C",
        taxonomy_path="A > B > C",
    )
    schema_match = SchemaMatchResult(matched_schema_id="schema-1", score=0.9)

    def fake_run_cli_input(cli: CLIInput):
        assert cli.model == "233541"
        assert cli.url == "https://www.electronet.gr/example"
        assert cli.out == "out"
        return {
            "source": "electronet",
            "parsed": parsed,
            "taxonomy": taxonomy,
            "schema_match": schema_match,
            "report": {"warnings": ["full warning"]},
            "model_dir": tmp_path / "out" / "233541",
            "raw_html_path": tmp_path / "out" / "233541" / "233541.raw.html",
            "source_json_path": tmp_path / "out" / "233541" / "233541.source.json",
            "normalized_json_path": tmp_path / "out" / "233541" / "233541.normalized.json",
            "report_json_path": tmp_path / "out" / "233541" / "233541.report.json",
            "csv_path": tmp_path / "out" / "233541" / "233541.csv",
        }

    monkeypatch.setattr(cli_module, "run_cli_input", fake_run_cli_input)

    result = run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert result.run.run_type == RunType.FULL
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.warnings == ["full warning"]
    assert result.artifacts.model_root == tmp_path / "out" / "233541"
    assert result.artifacts.source_report_json_path == tmp_path / "out" / "233541" / "233541.report.json"
    assert result.details["csv_path"] == str(tmp_path / "out" / "233541" / "233541.csv")
    assert result.details["taxonomy_path"] == "A > B > C"
    assert result.details["matched_schema_id"] == "schema-1"
    assert result.details["warnings_count"] == 1


def test_run_product_wraps_cli_errors(monkeypatch) -> None:
    from electronet_single_import import cli as cli_module

    def fake_run_cli_input(_cli: CLIInput):
        raise RuntimeError("full run exploded")

    monkeypatch.setattr(cli_module, "run_cli_input", fake_run_cli_input)

    with pytest.raises(ServiceError) as excinfo:
        run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == "RuntimeError"
    assert excinfo.value.message == "full run exploded"
