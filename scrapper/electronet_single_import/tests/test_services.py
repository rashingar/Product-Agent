from pathlib import Path

import pytest

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
    render_product,
    run_product,
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


def test_run_product_composes_stage_services_and_aggregates_metadata_paths(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import.services import run_service

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
        details={"source": "electronet"},
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
    assert result.artifacts.metadata_path is None
    assert result.artifacts.candidate_csv_path == tmp_path / "work" / "233541" / "candidate" / "233541.csv"
    assert result.details["prepare_metadata_path"] == str(tmp_path / "work" / "233541" / "prepare.run.json")
    assert result.details["render_metadata_path"] == str(tmp_path / "work" / "233541" / "render.run.json")
    assert result.details["validation_ok"] is True


def test_run_product_stops_when_prepare_fails(monkeypatch) -> None:
    from electronet_single_import.services import run_service

    render_calls: list[str] = []

    def fake_prepare(_request: PrepareRequest) -> ServiceResult:
        raise ServiceError("RuntimeError", "prepare exploded")

    def fake_render(_request: RenderRequest) -> ServiceResult:
        render_calls.append("render")
        raise AssertionError("render should not run")

    monkeypatch.setattr(run_service, "prepare_product", fake_prepare)
    monkeypatch.setattr(run_service, "render_product", fake_render)

    with pytest.raises(ServiceError) as excinfo:
        run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == "RuntimeError"
    assert excinfo.value.message == "prepare exploded"
    assert render_calls == []

