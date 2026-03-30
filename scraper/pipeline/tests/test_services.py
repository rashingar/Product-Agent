import inspect
from pathlib import Path

import pytest

from pipeline.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from pipeline.services import (
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


def test_service_modules_do_not_import_workflow() -> None:
    from pipeline.services import prepare_service, render_service

    assert "from .. import workflow" not in inspect.getsource(prepare_service)
    assert "from .. import workflow" not in inspect.getsource(render_service)


def test_prepare_product_maps_execution_result(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import prepare_service

    monkeypatch.setattr(prepare_service, "WORK_ROOT", tmp_path / "work")

    def fake_execute_prepare_workflow(cli, *, work_root):
        assert cli.model == "233541"
        assert cli.url == "https://www.electronet.gr/example"
        assert cli.photos == 6
        assert cli.sections == 2
        assert cli.skroutz_status == 1
        assert cli.boxnow == 0
        assert str(cli.price) == "2099"
        assert cli.out == str(tmp_path / "work" / "233541" / "scrape")
        assert work_root == tmp_path / "work"
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

    monkeypatch.setattr(prepare_service, "execute_prepare_workflow", fake_execute_prepare_workflow)

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


def test_prepare_product_wraps_execution_errors(monkeypatch) -> None:
    from pipeline.services import prepare_service

    def fake_execute_prepare_workflow(_cli, *, work_root):
        raise RuntimeError("prepare exploded")

    monkeypatch.setattr(prepare_service, "execute_prepare_workflow", fake_execute_prepare_workflow)

    with pytest.raises(ServiceError) as excinfo:
        prepare_product(PrepareRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == "RuntimeError"
    assert excinfo.value.message == "prepare exploded"
    assert isinstance(excinfo.value.cause, RuntimeError)


def test_render_product_maps_execution_result(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import render_service

    def fake_execute_render_workflow(model: str):
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

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

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


def test_render_product_wraps_execution_errors(monkeypatch) -> None:
    from pipeline.services import render_service

    def fake_execute_render_workflow(_model: str):
        raise FileNotFoundError("Missing LLM output")

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

    with pytest.raises(ServiceError) as excinfo:
        render_product(RenderRequest(model="233541"))

    assert excinfo.value.code == "FileNotFoundError"
    assert excinfo.value.message == "Missing LLM output"
    assert isinstance(excinfo.value.cause, FileNotFoundError)


def test_run_product_maps_cli_result(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import run_service

    call_order: list[str] = []
    prepare_result = ServiceResult(
        run=RunMetadata(model="233541", run_type=RunType.PREPARE, status=RunStatus.COMPLETED, warnings=["prepare warning"]),
        artifacts=RunArtifacts(
            model_root=tmp_path / "work" / "233541",
            scrape_dir=tmp_path / "work" / "233541" / "scrape",
            raw_html_path=tmp_path / "work" / "233541" / "scrape" / "233541.raw.html",
            source_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.source.json",
            scrape_normalized_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.normalized.json",
            source_report_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.report.json",
            llm_context_path=tmp_path / "work" / "233541" / "llm_context.json",
            prompt_path=tmp_path / "work" / "233541" / "prompt.txt",
            llm_output_path=tmp_path / "work" / "233541" / "llm_output.json",
            metadata_path=tmp_path / "work" / "233541" / "prepare.run.json",
        ),
        details={
            "source": "electronet",
            "product_name": "LG Example",
            "product_code": "233541",
            "brand": "LG",
            "taxonomy_path": "A > B > C",
            "matched_schema_id": "schema-1",
            "schema_score": 0.9,
        },
    )
    render_result = ServiceResult(
        run=RunMetadata(model="233541", run_type=RunType.RENDER, status=RunStatus.COMPLETED, warnings=["render warning"]),
        artifacts=RunArtifacts(
            model_root=tmp_path / "work" / "233541",
            scrape_dir=tmp_path / "work" / "233541" / "scrape",
            candidate_dir=tmp_path / "work" / "233541" / "candidate",
            candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
            published_csv_path=tmp_path / "products" / "233541.csv",
            candidate_normalized_json_path=tmp_path / "work" / "233541" / "candidate" / "233541.normalized.json",
            validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
            description_html_path=tmp_path / "work" / "233541" / "candidate" / "description.html",
            characteristics_html_path=tmp_path / "work" / "233541" / "candidate" / "characteristics.html",
            metadata_path=tmp_path / "work" / "233541" / "render.run.json",
        ),
        details={"validation_ok": True},
    )

    def fake_prepare(request: PrepareRequest) -> ServiceResult:
        call_order.append("prepare")
        assert request.model == "233541"
        return prepare_result

    def fake_render(request: RenderRequest) -> ServiceResult:
        call_order.append("render")
        assert request.model == "233541"
        return render_result

    monkeypatch.setattr(run_service, "prepare_product", fake_prepare)
    monkeypatch.setattr(run_service, "render_product", fake_render)

    result = run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert call_order == ["prepare", "render"]
    assert result.run.run_type == RunType.FULL
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.warnings == ["prepare warning", "render warning"]
    assert result.artifacts.candidate_csv_path == tmp_path / "work" / "233541" / "candidate" / "233541.csv"
    assert result.details["prepare_metadata_path"] == str(tmp_path / "work" / "233541" / "prepare.run.json")
    assert result.details["render_metadata_path"] == str(tmp_path / "work" / "233541" / "render.run.json")
    assert result.details["validation_ok"] is True
    assert result.details["product_name"] == "LG Example"


def test_run_product_wraps_cli_errors(monkeypatch) -> None:
    from pipeline.services import run_service

    def fake_prepare(_request: PrepareRequest):
        raise RuntimeError("full run exploded")

    monkeypatch.setattr(run_service, "prepare_product", fake_prepare)

    with pytest.raises(ServiceError) as excinfo:
        run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == "RuntimeError"
    assert excinfo.value.message == "full run exploded"

