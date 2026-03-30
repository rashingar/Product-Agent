import inspect
from pathlib import Path

import pytest

from pipeline.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from pipeline.providers.base import ProviderError
from pipeline.providers.models import ProviderErrorCode, ProviderStage
from pipeline.services import (
    FullRunRequest,
    PrepareRequest,
    RenderRequest,
    RunArtifacts,
    RunMetadata,
    ServiceErrorCode,
    RunStatus,
    RunType,
    ServiceError,
    ServiceResult,
    prepare_product,
    run_product,
    render_product,
)


def test_service_modules_do_not_import_workflow() -> None:
    from pipeline.services import prepare_service, render_service, run_execution, run_service

    assert "from .. import workflow" not in inspect.getsource(prepare_service)
    assert "from .. import workflow" not in inspect.getsource(render_service)
    assert "from .. import workflow" not in inspect.getsource(run_execution)
    assert "from .. import workflow" not in inspect.getsource(run_service)


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
                "taxonomy": TaxonomyResolution(parent_category="A", leaf_category="B", sub_category="C"),
                "schema_match": SchemaMatchResult(matched_schema_id="schema-1", score=0.9),
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
    assert result.artifacts.llm_dir == tmp_path / "work" / "233541" / "llm"
    assert result.artifacts.llm_task_manifest_path == tmp_path / "work" / "233541" / "llm" / "task_manifest.json"
    assert result.artifacts.intro_text_context_path == tmp_path / "work" / "233541" / "llm" / "intro_text.context.json"
    assert result.artifacts.seo_meta_context_path == tmp_path / "work" / "233541" / "llm" / "seo_meta.context.json"
    assert result.artifacts.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.artifacts.source_json_path == tmp_path / "work" / "233541" / "scrape" / "233541.source.json"
    assert result.artifacts.metadata_path == tmp_path / "work" / "233541" / "prepare.run.json"
    assert result.details["source"] == "electronet"
    assert result.details["product_name"] == "LG Example"
    assert result.details["product_code"] == "233541"
    assert result.details["brand"] == "LG"
    assert result.details["matched_schema_id"] == "schema-1"
    assert result.details["schema_score"] == 0.9
    assert result.details["llm_prepare_mode"] == "split_tasks"


def test_prepare_product_wraps_execution_errors(monkeypatch) -> None:
    from pipeline.services import prepare_service

    def fake_execute_prepare_workflow(_cli, *, work_root):
        raise RuntimeError("prepare exploded")

    monkeypatch.setattr(prepare_service, "execute_prepare_workflow", fake_execute_prepare_workflow)

    with pytest.raises(ServiceError) as excinfo:
        prepare_product(PrepareRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == ServiceErrorCode.UNEXPECTED_FAILURE.value
    assert excinfo.value.message == "prepare exploded"
    assert excinfo.value.retryable is False
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


def test_render_product_allows_missing_published_csv_path(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import render_service

    def fake_execute_render_workflow(model: str):
        assert model == "233541"
        return {
            "candidate_dir": tmp_path / "work" / model / "candidate",
            "candidate_csv_path": tmp_path / "work" / model / "candidate" / f"{model}.csv",
            "published_csv_path": None,
            "description_path": tmp_path / "work" / model / "candidate" / "description.html",
            "characteristics_path": tmp_path / "work" / model / "candidate" / "characteristics.html",
            "validation_report_path": tmp_path / "work" / model / "candidate" / f"{model}.validation.json",
            "run_status": "failed",
            "metadata_path": tmp_path / "work" / model / "render.run.json",
            "validation_report": {"ok": False, "warnings": ["render warning"]},
        }

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

    result = render_product(RenderRequest(model="233541"))

    assert result.run.status == RunStatus.FAILED
    assert result.run.error_code == ServiceErrorCode.VALIDATION_FAILURE.value
    assert result.run.error_detail == "Candidate validation failed"
    assert result.artifacts.published_csv_path is None
    assert result.details["validation_ok"] is False


def test_render_product_wraps_execution_errors(monkeypatch) -> None:
    from pipeline.services import render_service

    def fake_execute_render_workflow(_model: str):
        raise FileNotFoundError("Missing LLM output")

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

    with pytest.raises(ServiceError) as excinfo:
        render_product(RenderRequest(model="233541"))

    assert excinfo.value.code == ServiceErrorCode.MISSING_ARTIFACT.value
    assert excinfo.value.message == "Missing LLM output"
    assert excinfo.value.retryable is False
    assert isinstance(excinfo.value.cause, FileNotFoundError)


def test_prepare_product_maps_provider_failures_to_stable_service_codes(monkeypatch) -> None:
    from pipeline.services import prepare_service

    def fake_execute_prepare_workflow(_cli, *, work_root):
        provider_error = ProviderError.build(
            provider_id="skroutz",
            code=ProviderErrorCode.FETCH_FAILED,
            stage=ProviderStage.FETCH,
            message="Skroutz fetch failed",
            retryable=True,
            details={"url": "https://www.skroutz.gr/example"},
        )
        raise RuntimeError("provider failed") from provider_error

    monkeypatch.setattr(prepare_service, "execute_prepare_workflow", fake_execute_prepare_workflow)

    with pytest.raises(ServiceError) as excinfo:
        prepare_product(PrepareRequest(model="233541", url="https://www.skroutz.gr/example"))

    assert excinfo.value.code == ServiceErrorCode.PROVIDER_FAILURE.value
    assert excinfo.value.message == "Skroutz fetch failed"
    assert excinfo.value.retryable is True
    assert excinfo.value.details["provider_id"] == "skroutz"
    assert excinfo.value.details["provider_code"] == "fetch_failed"
    assert excinfo.value.details["provider_stage"] == "fetch"
    assert excinfo.value.details["url"] == "https://www.skroutz.gr/example"


def test_execute_run_workflow_composes_prepare_and_render_results(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import run_execution

    call_order: list[str] = []
    prepare_result = ServiceResult(
        run=RunMetadata(model="233541", run_type=RunType.PREPARE, status=RunStatus.COMPLETED, warnings=["prepare warning"]),
        artifacts=RunArtifacts(
            model_root=tmp_path / "work" / "233541",
            scrape_dir=tmp_path / "work" / "233541" / "scrape",
            llm_dir=tmp_path / "work" / "233541" / "llm",
            raw_html_path=tmp_path / "work" / "233541" / "scrape" / "233541.raw.html",
            source_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.source.json",
            scrape_normalized_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.normalized.json",
            source_report_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.report.json",
            llm_task_manifest_path=tmp_path / "work" / "233541" / "llm" / "task_manifest.json",
            intro_text_context_path=tmp_path / "work" / "233541" / "llm" / "intro_text.context.json",
            intro_text_prompt_path=tmp_path / "work" / "233541" / "llm" / "intro_text.prompt.txt",
            intro_text_output_path=tmp_path / "work" / "233541" / "llm" / "intro_text.output.txt",
            seo_meta_context_path=tmp_path / "work" / "233541" / "llm" / "seo_meta.context.json",
            seo_meta_prompt_path=tmp_path / "work" / "233541" / "llm" / "seo_meta.prompt.txt",
            seo_meta_output_path=tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json",
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

    monkeypatch.setattr(run_execution, "prepare_product", fake_prepare)
    monkeypatch.setattr(run_execution, "render_product", fake_render)

    result = run_execution.execute_run_workflow(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert call_order == ["prepare", "render"]
    assert result.run.run_type == RunType.FULL
    assert result.run.status == RunStatus.COMPLETED
    assert result.run.warnings == ["prepare warning", "render warning"]
    assert result.artifacts.llm_dir == tmp_path / "work" / "233541" / "llm"
    assert result.artifacts.llm_task_manifest_path == tmp_path / "work" / "233541" / "llm" / "task_manifest.json"
    assert result.artifacts.candidate_csv_path == tmp_path / "work" / "233541" / "candidate" / "233541.csv"
    assert result.details["prepare_metadata_path"] == str(tmp_path / "work" / "233541" / "prepare.run.json")
    assert result.details["render_metadata_path"] == str(tmp_path / "work" / "233541" / "render.run.json")
    assert result.details["validation_ok"] is True
    assert result.details["product_name"] == "LG Example"


def test_run_product_delegates_to_service_owned_execution(monkeypatch) -> None:
    from pipeline.services import run_service

    expected = ServiceResult(
        run=RunMetadata(model="233541", run_type=RunType.FULL, status=RunStatus.COMPLETED),
        artifacts=RunArtifacts(),
        details={},
    )

    def fake_execute_run_workflow(request: FullRunRequest) -> ServiceResult:
        assert request.model == "233541"
        assert request.url == "https://www.electronet.gr/example"
        return expected

    monkeypatch.setattr(run_service, "execute_run_workflow", fake_execute_run_workflow)

    assert run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example")) is expected


def test_run_product_wraps_execution_errors(monkeypatch) -> None:
    from pipeline.services import run_service

    def fake_execute_run_workflow(_request: FullRunRequest) -> ServiceResult:
        raise RuntimeError("full run exploded")

    monkeypatch.setattr(run_service, "execute_run_workflow", fake_execute_run_workflow)

    with pytest.raises(ServiceError) as excinfo:
        run_product(FullRunRequest(model="233541", url="https://www.electronet.gr/example"))

    assert excinfo.value.code == ServiceErrorCode.UNEXPECTED_FAILURE.value
    assert excinfo.value.message == "full run exploded"
    assert excinfo.value.retryable is False

