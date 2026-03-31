import inspect
from pathlib import Path

import pytest

from pipeline.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from pipeline.providers.base import ProviderError
from pipeline.providers.models import ProviderErrorCode, ProviderStage
from pipeline.services.execution_models import (
    PrepareExecutionResult,
    PrepareExecutionScrapeResult,
    RenderExecutionResult,
    RenderExecutionValidationReport,
)
from pipeline.services import (
    PrepareRequest,
    PublishRequest,
    RenderRequest,
    RunArtifacts,
    RunMetadata,
    ServiceErrorCode,
    RunStatus,
    RunType,
    ServiceError,
    ServiceResult,
    prepare_product,
    publish_product,
    render_product,
)


def test_run_type_matches_workflow_only_service_surface() -> None:
    assert tuple(run_type.value for run_type in RunType) == ("prepare", "render", "publish")


def test_services_package_no_longer_exports_full_run_contract() -> None:
    import pipeline.services as services

    legacy_request_name = "Full" + "RunRequest"
    legacy_runner_name = "run_" + "product"

    assert hasattr(services, "PrepareRequest")
    assert hasattr(services, "RenderRequest")
    assert hasattr(services, "PublishRequest")
    assert not hasattr(services, legacy_request_name)
    assert not hasattr(services, legacy_runner_name)


def test_service_modules_do_not_import_workflow() -> None:
    from pipeline.services import prepare_service, render_service

    assert "from .. import workflow" not in inspect.getsource(prepare_service)
    assert "from .. import workflow" not in inspect.getsource(render_service)


def _build_prepare_execution_result(root: Path, *, model: str = "233541", warnings: list[str] | None = None) -> PrepareExecutionResult:
    warnings = ["prepare warning"] if warnings is None else warnings
    model_root = root / "work" / model
    scrape_dir = model_root / "scrape"
    llm_dir = model_root / "llm"
    return PrepareExecutionResult(
        model_root=model_root,
        scrape_dir=scrape_dir,
        llm_dir=llm_dir,
        task_manifest_path=llm_dir / "task_manifest.json",
        intro_text_context_path=llm_dir / "intro_text.context.json",
        intro_text_prompt_path=llm_dir / "intro_text.prompt.txt",
        intro_text_output_path=llm_dir / "intro_text.output.txt",
        seo_meta_context_path=llm_dir / "seo_meta.context.json",
        seo_meta_prompt_path=llm_dir / "seo_meta.prompt.txt",
        seo_meta_output_path=llm_dir / "seo_meta.output.json",
        run_status=RunStatus.COMPLETED,
        metadata_path=model_root / "prepare.run.json",
        scrape_result=PrepareExecutionScrapeResult(
            source="electronet",
            parsed=ParsedProduct(
                source=SourceProductData(
                    url="https://www.electronet.gr/example",
                    canonical_url="https://www.electronet.gr/example",
                    product_code=model,
                    brand="LG",
                    name="LG Example",
                )
            ),
            taxonomy=TaxonomyResolution(
                parent_category="A",
                leaf_category="B",
                sub_category="C",
                taxonomy_path="A > B > C",
            ),
            schema_match=SchemaMatchResult(matched_schema_id="schema-1", score=0.9),
            report_warnings=warnings,
        ),
    )


def _build_render_execution_result(root: Path, *, model: str = "233541", validation_ok: bool = True) -> RenderExecutionResult:
    candidate_dir = root / "work" / model / "candidate"
    published_csv_path = root / "products" / f"{model}.csv" if validation_ok else None
    return RenderExecutionResult(
        candidate_dir=candidate_dir,
        candidate_csv_path=candidate_dir / f"{model}.csv",
        published_csv_path=published_csv_path,
        description_path=candidate_dir / "description.html",
        characteristics_path=candidate_dir / "characteristics.html",
        validation_report_path=candidate_dir / f"{model}.validation.json",
        run_status=RunStatus.COMPLETED if validation_ok else RunStatus.FAILED,
        metadata_path=root / "work" / model / "render.run.json",
        validation_report=RenderExecutionValidationReport(
            ok=validation_ok,
            warnings=["render warning"],
        ),
    )


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
        return _build_prepare_execution_result(tmp_path)

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

    assert result == ServiceResult(
        run=RunMetadata(
            model="233541",
            run_type=RunType.PREPARE,
            status=RunStatus.COMPLETED,
            warnings=["prepare warning"],
        ),
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
            "warnings_count": 1,
            "llm_prepare_mode": "split_tasks",
        },
    )


def test_prepare_product_keeps_detail_defaults_when_scrape_result_fields_are_missing(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import prepare_service

    monkeypatch.setattr(prepare_service, "WORK_ROOT", tmp_path / "work")

    def fake_execute_prepare_workflow(_cli, *, work_root):
        assert work_root == tmp_path / "work"
        payload = _build_prepare_execution_result(tmp_path, warnings=[])
        payload.scrape_result = PrepareExecutionScrapeResult()
        return payload

    monkeypatch.setattr(prepare_service, "execute_prepare_workflow", fake_execute_prepare_workflow)

    result = prepare_product(PrepareRequest(model="233541", url="https://www.electronet.gr/example"))

    assert result.run == RunMetadata(
        model="233541",
        run_type=RunType.PREPARE,
        status=RunStatus.COMPLETED,
        warnings=[],
    )
    assert result.details == {
        "source": "",
        "product_name": "",
        "product_code": "",
        "brand": "",
        "taxonomy_path": "",
        "matched_schema_id": "",
        "schema_score": 0.0,
        "warnings_count": 0,
        "llm_prepare_mode": "split_tasks",
    }
    assert result.artifacts.metadata_path == tmp_path / "work" / "233541" / "prepare.run.json"
    assert result.artifacts.model_root == tmp_path / "work" / "233541"
    assert result.artifacts.scrape_dir == tmp_path / "work" / "233541" / "scrape"
    assert result.artifacts.intro_text_prompt_path == tmp_path / "work" / "233541" / "llm" / "intro_text.prompt.txt"
    assert result.artifacts.seo_meta_output_path == tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json"


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
        return _build_render_execution_result(tmp_path)

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

    result = render_product(RenderRequest(model="233541"))

    assert result == ServiceResult(
        run=RunMetadata(
            model="233541",
            run_type=RunType.RENDER,
            status=RunStatus.COMPLETED,
            warnings=["render warning"],
        ),
        artifacts=RunArtifacts(
            model_root=tmp_path / "work" / "233541",
            scrape_dir=tmp_path / "work" / "233541" / "scrape",
            llm_dir=tmp_path / "work" / "233541" / "llm",
            candidate_dir=tmp_path / "work" / "233541" / "candidate",
            source_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.source.json",
            scrape_normalized_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.normalized.json",
            llm_task_manifest_path=tmp_path / "work" / "233541" / "llm" / "task_manifest.json",
            intro_text_output_path=tmp_path / "work" / "233541" / "llm" / "intro_text.output.txt",
            seo_meta_output_path=tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json",
            candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
            published_csv_path=tmp_path / "products" / "233541.csv",
            candidate_normalized_json_path=tmp_path / "work" / "233541" / "candidate" / "233541.normalized.json",
            validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
            description_html_path=tmp_path / "work" / "233541" / "candidate" / "description.html",
            characteristics_html_path=tmp_path / "work" / "233541" / "candidate" / "characteristics.html",
            metadata_path=tmp_path / "work" / "233541" / "render.run.json",
        ),
        details={
            "validation_ok": True,
            "published": True,
        },
    )


def test_render_product_allows_missing_published_csv_path(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import render_service

    def fake_execute_render_workflow(model: str):
        assert model == "233541"
        return _build_render_execution_result(tmp_path, validation_ok=False)

    monkeypatch.setattr(render_service, "execute_render_workflow", fake_execute_render_workflow)

    result = render_product(RenderRequest(model="233541"))

    assert result == ServiceResult(
        run=RunMetadata(
            model="233541",
            run_type=RunType.RENDER,
            status=RunStatus.FAILED,
            warnings=["render warning"],
            error_code=ServiceErrorCode.VALIDATION_FAILURE.value,
            error_detail="Candidate validation failed",
        ),
        artifacts=RunArtifacts(
            model_root=tmp_path / "work" / "233541",
            scrape_dir=tmp_path / "work" / "233541" / "scrape",
            llm_dir=tmp_path / "work" / "233541" / "llm",
            candidate_dir=tmp_path / "work" / "233541" / "candidate",
            source_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.source.json",
            scrape_normalized_json_path=tmp_path / "work" / "233541" / "scrape" / "233541.normalized.json",
            llm_task_manifest_path=tmp_path / "work" / "233541" / "llm" / "task_manifest.json",
            intro_text_output_path=tmp_path / "work" / "233541" / "llm" / "intro_text.output.txt",
            seo_meta_output_path=tmp_path / "work" / "233541" / "llm" / "seo_meta.output.json",
            candidate_csv_path=tmp_path / "work" / "233541" / "candidate" / "233541.csv",
            published_csv_path=None,
            candidate_normalized_json_path=tmp_path / "work" / "233541" / "candidate" / "233541.normalized.json",
            validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
            description_html_path=tmp_path / "work" / "233541" / "candidate" / "description.html",
            characteristics_html_path=tmp_path / "work" / "233541" / "candidate" / "characteristics.html",
            metadata_path=tmp_path / "work" / "233541" / "render.run.json",
        ),
        details={
            "validation_ok": False,
            "published": False,
        },
    )


def test_publish_product_maps_execution_result(tmp_path: Path, monkeypatch) -> None:
    from pipeline.services import publish_service

    def fake_execute_publish_workflow(model: str, *, current_job_product_file=None):
        assert model == "233541"
        assert current_job_product_file == tmp_path / "products" / "233541.csv"
        return {
            "run_status": "failed",
            "metadata_path": tmp_path / "work" / model / "publish.run.json",
            "published_csv_path": tmp_path / "products" / "233541.csv",
            "publish_attempted": True,
            "publish_status": "failed",
            "publish_stage": "csv_import",
            "publish_message": "OpenCart publish failed during csv_import: exit=13",
            "upload_report_path": tmp_path / "work" / model / "upload.opencart.json",
            "import_report_path": tmp_path / "work" / model / "import.opencart.json",
        }

    monkeypatch.setattr(publish_service, "execute_publish_workflow", fake_execute_publish_workflow)

    result = publish_product(
        PublishRequest(
            model="233541",
            current_job_product_file=tmp_path / "products" / "233541.csv",
        )
    )

    assert result.run.run_type == RunType.PUBLISH
    assert result.run.status == RunStatus.FAILED
    assert result.run.error_code == ServiceErrorCode.PUBLISH_FAILURE.value
    assert result.run.warnings == ["OpenCart publish failed during csv_import: exit=13"]
    assert result.details["publish_attempted"] is True
    assert result.details["publish_status"] == "failed"
    assert result.details["publish_stage"] == "csv_import"
    assert result.details["upload_report_path"] == str(tmp_path / "work" / "233541" / "upload.opencart.json")
    assert result.details["import_report_path"] == str(tmp_path / "work" / "233541" / "import.opencart.json")


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



