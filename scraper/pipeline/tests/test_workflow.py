import argparse
import json
from pathlib import Path

import pytest

from pipeline.models import CLIInput, GalleryImage, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from pipeline.services import PrepareRequest, RenderRequest, RunArtifacts, RunMetadata, RunStatus, RunType, ServiceResult
from pipeline.workflow import build_cli_input_from_args, prepare_workflow, render_workflow


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

    def fake_execute_full_run(_cli):
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

    monkeypatch.setattr(workflow, "execute_full_run", fake_execute_full_run)

    result = prepare_workflow(cli)

    assert result["llm_context_path"].exists()
    assert result["prompt_path"].exists()
    assert result["metadata_path"].exists()
    llm_context = json.loads(result["llm_context_path"].read_text(encoding="utf-8"))
    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    prompt_text = result["prompt_path"].read_text(encoding="utf-8")
    assert llm_context["writer_rules"]["intro_html_rule"] == "120-180 Greek words in one intro paragraph."
    assert "between 120 and 180 Greek words" in prompt_text
    assert "120-180 Greek words" in prompt_text
    assert result["metadata_path"].name == "prepare.run.json"
    assert metadata["run"]["model"] == "233541"
    assert metadata["run"]["run_type"] == "prepare"
    assert metadata["run"]["status"] == "completed"
    assert metadata["artifacts"]["llm_context_path"] == str(result["llm_context_path"])
    assert metadata["artifacts"]["prompt_path"] == str(result["prompt_path"])
    assert metadata["artifacts"]["metadata_path"] == str(result["metadata_path"])
    assert metadata["artifacts"]["llm_output_path"] == str(result["model_root"] / "llm_output.json")
    assert metadata["details"]["source"] == ""


def test_execute_full_run_allows_electronet_product_code_mismatch(monkeypatch, tmp_path: Path) -> None:
    from pipeline import full_run as run_module
    from pipeline.models import FetchResult
    from pipeline.providers.models import (
        ProviderCapability,
        ProviderDefinition,
        ProviderInputIdentity,
        ProviderKind,
        ProviderResult,
        ProviderSnapshot,
        ProviderSnapshotKind,
    )

    cli = CLIInput(
        model="229957",
        url="https://www.electronet.gr/example",
        photos=2,
        sections=0,
        skroutz_status=1,
        boxnow=0,
        price="599",
        out=str(tmp_path),
    )
    parsed = ParsedProduct(
        source=SourceProductData(
            url=cli.url,
            canonical_url=cli.url,
            product_code="235370",
            brand="LG",
            name="LG RHX5009TWB",
        ),
    )

    class DummyFetcher:
        def fetch_httpx(self, _url):
            return FetchResult(url=cli.url, final_url=cli.url, html="<html></html>", status_code=200, method="httpx", fallback_used=False, response_headers={})

        def fetch_playwright(self, _url):
            return FetchResult(url=cli.url, final_url=cli.url, html="<html></html>", status_code=200, method="playwright", fallback_used=True, response_headers={})

        def download_gallery_images(self, **_kwargs):
            return [], [], []

        def download_besco_images(self, **_kwargs):
            return [], [], []

    class DummyResolver:
        def resolve(self, **_kwargs):
            return TaxonomyResolution(parent_category="A", leaf_category="B", sub_category="C"), []

    class DummySchemaMatcher:
        known_section_titles = set()

        def __init__(self, *_args, **_kwargs):
            pass

        def match(self, *_args, **_kwargs):
            return SchemaMatchResult(matched_schema_id="schema-1", score=0.9), []

    provider_calls: list[ProviderInputIdentity] = []

    class UnexpectedParser:
        def parse(self, *_args, **_kwargs):
            raise AssertionError("Electronet parser should not be called directly")

    class DummyElectronetProvider:
        def __init__(self, *, fetcher, parser):
            assert isinstance(fetcher, DummyFetcher)
            assert isinstance(parser, UnexpectedParser)

        def fetch_snapshot(self, identity: ProviderInputIdentity) -> ProviderSnapshot:
            provider_calls.append(identity)
            return ProviderSnapshot(
                provider_id="electronet",
                identity=identity,
                snapshot_kind=ProviderSnapshotKind.HTML,
                requested_url=identity.url,
                final_url=identity.url,
                content_type="text/html",
                status_code=200,
                body_text="<html></html>",
                metadata={"fetch_method": "httpx", "fallback_used": False},
            )

        def normalize(self, snapshot: ProviderSnapshot, identity: ProviderInputIdentity) -> ProviderResult:
            assert snapshot.requested_url == identity.url
            return ProviderResult(
                provider=ProviderDefinition(
                    provider_id="electronet",
                    source_name="electronet",
                    kind=ProviderKind.VENDOR_SITE,
                    capabilities=frozenset(
                        {
                            ProviderCapability.URL_INPUT,
                            ProviderCapability.LIVE_FETCH,
                            ProviderCapability.HTML_SNAPSHOT,
                            ProviderCapability.NORMALIZED_PRODUCT,
                        }
                    ),
                ),
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    monkeypatch.setattr(run_module, "detect_source", lambda _url: "electronet")
    monkeypatch.setattr(run_module, "validate_url_scope", lambda _url: ("electronet", True, ""))
    monkeypatch.setattr(run_module, "ElectronetFetcher", lambda: DummyFetcher())
    monkeypatch.setattr(run_module, "ElectronetProvider", DummyElectronetProvider)
    monkeypatch.setattr(run_module, "ElectronetProductParser", lambda known_section_titles=None: UnexpectedParser())
    monkeypatch.setattr(run_module, "SkroutzProductParser", lambda: type("P", (), {"parse": lambda self, *_args, **_kwargs: parsed})())
    monkeypatch.setattr(run_module, "TaxonomyResolver", lambda: DummyResolver())
    monkeypatch.setattr(run_module, "SchemaMatcher", DummySchemaMatcher)
    monkeypatch.setattr(run_module, "enrich_source_from_manufacturer_docs", lambda **_kwargs: {})

    result = run_module.execute_full_run(cli)

    assert provider_calls == [ProviderInputIdentity(model="229957", url="https://www.electronet.gr/example")]
    assert result["parsed"].warnings == ["source_product_code_mismatch:input=229957:page=235370"]
    assert result["report"]["source"] == "electronet"
    assert result["report"]["identity_checks"]["source"] == "electronet"


def test_execute_full_run_routes_skroutz_through_provider_by_default(monkeypatch, tmp_path: Path) -> None:
    from pipeline import full_run as run_module
    from pipeline.providers.models import (
        ProviderCapability,
        ProviderDefinition,
        ProviderInputIdentity,
        ProviderKind,
        ProviderResult,
        ProviderSnapshot,
        ProviderSnapshotKind,
    )

    cli = CLIInput(
        model="341490",
        url="https://www.skroutz.gr/s/51055155/Estia-Intense-Vrastiras-1-7lt-2200W-Luminus-Mat.html",
        photos=2,
        sections=0,
        skroutz_status=0,
        boxnow=1,
        price="19",
        out=str(tmp_path),
    )
    parsed = ParsedProduct(
        source=SourceProductData(
            source_name="skroutz",
            page_type="product",
            url=cli.url,
            canonical_url=cli.url,
            product_code=cli.model,
            brand="Estia",
            mpn="06-24567",
            name="Estia 06-24567",
            breadcrumbs=["Αρχική", "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", "Συσκευές Κουζίνας", "Βραστήρες"],
            taxonomy_source_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ:::Συσκευές Κουζίνας///Βραστήρες",
            taxonomy_match_type="exact_category",
            taxonomy_rule_id="family:kettle",
            price_text="19,00 €",
            price_value=19.0,
            key_specs=[SpecItem(label="Ισχύς", value="2200 W")],
            spec_sections=[SpecSection(section="Χαρακτηριστικά", items=[SpecItem(label="Ισχύς", value="2200 W")])],
        ),
    )
    provider_calls: list[ProviderInputIdentity] = []

    class DummyFetcher:
        def download_gallery_images(self, **_kwargs):
            return [], [], []

        def download_besco_images(self, **_kwargs):
            return [], [], []

    class DummyResolver:
        def resolve(self, **_kwargs):
            return TaxonomyResolution(parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", leaf_category="Συσκευές Κουζίνας", sub_category="Βραστήρες"), []

    class DummySchemaMatcher:
        known_section_titles = set()

        def __init__(self, *_args, **_kwargs):
            pass

        def match(self, *_args, **_kwargs):
            return SchemaMatchResult(matched_schema_id="schema-1", score=0.9), []

    class UnexpectedParser:
        def parse(self, *_args, **_kwargs):
            raise AssertionError("Skroutz parser should not be called directly outside the provider seam")

    class UnexpectedElectronetProvider:
        def __init__(self, **_kwargs):
            raise AssertionError("Electronet provider should not be selected for Skroutz by default")

    class DummySkroutzProvider:
        def __init__(self, *, fetcher, parser):
            assert isinstance(fetcher, DummyFetcher)
            assert isinstance(parser, UnexpectedParser)

        def fetch_snapshot(self, identity: ProviderInputIdentity) -> ProviderSnapshot:
            provider_calls.append(identity)
            return ProviderSnapshot(
                provider_id="skroutz",
                identity=identity,
                snapshot_kind=ProviderSnapshotKind.HTML,
                requested_url=identity.url,
                final_url=identity.url,
                content_type="text/html",
                status_code=200,
                body_text="<html></html>",
                metadata={"fetch_method": "playwright", "fallback_used": True},
            )

        def normalize(self, snapshot: ProviderSnapshot, identity: ProviderInputIdentity) -> ProviderResult:
            assert snapshot.requested_url == identity.url
            return ProviderResult(
                provider=ProviderDefinition(
                    provider_id="skroutz",
                    source_name="skroutz",
                    kind=ProviderKind.VENDOR_SITE,
                    capabilities=frozenset(
                        {
                            ProviderCapability.URL_INPUT,
                            ProviderCapability.LIVE_FETCH,
                            ProviderCapability.HTML_SNAPSHOT,
                            ProviderCapability.NORMALIZED_PRODUCT,
                        }
                    ),
                ),
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    monkeypatch.setattr(run_module, "detect_source", lambda _url: "skroutz")
    monkeypatch.setattr(run_module, "validate_url_scope", lambda _url: ("skroutz", True, "skroutz_product_path"))
    monkeypatch.setattr(run_module, "ElectronetFetcher", lambda: DummyFetcher())
    monkeypatch.setattr(run_module, "SchemaMatcher", DummySchemaMatcher)
    monkeypatch.setattr(run_module, "SkroutzProductParser", lambda: UnexpectedParser())
    monkeypatch.setattr(run_module, "SkroutzProvider", DummySkroutzProvider)
    monkeypatch.setattr(run_module, "ElectronetProvider", UnexpectedElectronetProvider)
    monkeypatch.setattr(run_module, "TaxonomyResolver", lambda: DummyResolver())
    monkeypatch.setattr(
        run_module,
        "enrich_source_from_manufacturer_docs",
        lambda **_kwargs: {
            "applied": False,
            "provider": "",
            "providers_considered": [],
            "matched_providers": [],
            "documents": [],
            "documents_discovered": 0,
            "documents_parsed": 0,
            "warnings": [],
            "section_count": 0,
            "field_count": 0,
            "hero_summary_applied": False,
            "presentation_applied": False,
            "presentation_block_count": 0,
            "fallback_reason": "test_stub",
        },
    )

    result = run_module.execute_full_run(cli)

    assert provider_calls == [ProviderInputIdentity(model="341490", url=cli.url)]
    assert result["report"]["source"] == "skroutz"
    assert result["report"]["fetch_mode"] == "playwright"
    assert result["fetch"].method == "playwright"


def test_execute_full_run_routes_manufacturer_tefal_through_provider_by_default(monkeypatch, tmp_path: Path) -> None:
    from pipeline import full_run as run_module
    from pipeline.providers.models import (
        ProviderCapability,
        ProviderDefinition,
        ProviderInputIdentity,
        ProviderKind,
        ProviderResult,
        ProviderSnapshot,
        ProviderSnapshotKind,
    )

    cli = CLIInput(
        model="344709",
        url="https://shop.tefal.gr/products/dolci-%CF%80%CE%B1%CE%B3%CF%89%CF%84%CE%BF%CE%BC%CE%B7%CF%87%CE%B1%CE%BD%CE%AE-ig602a",
        photos=3,
        sections=0,
        skroutz_status=0,
        boxnow=1,
        price="219",
        out=str(tmp_path),
    )
    parsed = ParsedProduct(
        source=SourceProductData(
            source_name="manufacturer_tefal",
            page_type="product",
            url=cli.url,
            canonical_url=cli.url,
            product_code="IG602A",
            brand="Tefal",
            mpn="IG602A",
            name="Tefal Dolci Παγωτομηχανή IG602A",
            breadcrumbs=["Αρχική", "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", "Μικροί Μάγειρες", "Παγωτομηχανές"],
            taxonomy_source_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ:::ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ///Μικροί Μάγειρες///Παγωτομηχανές",
            taxonomy_match_type="exact_category",
            taxonomy_rule_id="manufacturer_tefal:ice_cream_maker",
            price_text="229,90 €",
            price_value=229.9,
            key_specs=[
                SpecItem(label="Χωρητικότητα", value="1.4 lt"),
                SpecItem(label="Αριθμός Προγραμμάτων", value="10"),
                SpecItem(label="Αριθμός Δοχείων", value="3"),
            ],
            spec_sections=[
                SpecSection(
                    section="Παραγωγή & Δυνατότητες",
                    items=[
                        SpecItem(label="Χωρητικότητα", value="1.4 lt"),
                        SpecItem(label="Αριθμός Προγραμμάτων", value="10"),
                        SpecItem(label="Αριθμός Δοχείων", value="3"),
                    ],
                )
            ],
            manufacturer_spec_sections=[
                SpecSection(
                    section="Χαρακτηριστικά Κατασκευαστή",
                    items=[SpecItem(label="Τάση", value="220-240 V")],
                )
            ],
        ),
    )
    provider_calls: list[ProviderInputIdentity] = []

    class DummyFetcher:
        def download_gallery_images(self, **_kwargs):
            return [], [], []

        def download_besco_images(self, **_kwargs):
            return [], [], []

    class DummyResolver:
        def resolve(self, **_kwargs):
            return TaxonomyResolution(parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", leaf_category="Μικροί Μάγειρες", sub_category="Παγωτομηχανές"), []

    class DummySchemaMatcher:
        known_section_titles = set()

        def __init__(self, *_args, **_kwargs):
            pass

        def match(self, *_args, **_kwargs):
            return SchemaMatchResult(matched_schema_id="schema-1", score=0.9), []

    class UnexpectedParser:
        def parse(self, *_args, **_kwargs):
            raise AssertionError("Manufacturer parser should not be called directly outside the provider seam")

    class DummyManufacturerTefalProvider:
        def __init__(self, *, fetcher, parser):
            assert isinstance(fetcher, DummyFetcher)
            assert isinstance(parser, UnexpectedParser)

        def fetch_snapshot(self, identity: ProviderInputIdentity) -> ProviderSnapshot:
            provider_calls.append(identity)
            return ProviderSnapshot(
                provider_id="manufacturer_tefal",
                identity=identity,
                snapshot_kind=ProviderSnapshotKind.HTML,
                requested_url=identity.url,
                final_url=identity.url,
                content_type="text/html",
                status_code=200,
                body_text="<html></html>",
                metadata={"fetch_method": "httpx", "fallback_used": False},
            )

        def normalize(self, snapshot: ProviderSnapshot, identity: ProviderInputIdentity) -> ProviderResult:
            assert snapshot.requested_url == identity.url
            return ProviderResult(
                provider=ProviderDefinition(
                    provider_id="manufacturer_tefal",
                    source_name="manufacturer_tefal",
                    kind=ProviderKind.MANUFACTURER_SITE,
                    capabilities=frozenset(
                        {
                            ProviderCapability.URL_INPUT,
                            ProviderCapability.LIVE_FETCH,
                            ProviderCapability.HTML_SNAPSHOT,
                            ProviderCapability.NORMALIZED_PRODUCT,
                        }
                    ),
                ),
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    monkeypatch.setattr(run_module, "detect_source", lambda _url: "manufacturer_tefal")
    monkeypatch.setattr(run_module, "validate_url_scope", lambda _url: ("manufacturer_tefal", True, "manufacturer_tefal_product_path"))
    monkeypatch.setattr(run_module, "ElectronetFetcher", lambda: DummyFetcher())
    monkeypatch.setattr(run_module, "ElectronetProductParser", lambda known_section_titles=None: UnexpectedParser())
    monkeypatch.setattr(run_module, "SkroutzProductParser", lambda: UnexpectedParser())
    monkeypatch.setattr(run_module, "ManufacturerProductParser", lambda: UnexpectedParser())
    monkeypatch.setattr(run_module, "ManufacturerTefalProvider", DummyManufacturerTefalProvider)
    monkeypatch.setattr(run_module, "TaxonomyResolver", lambda: DummyResolver())
    monkeypatch.setattr(run_module, "SchemaMatcher", DummySchemaMatcher)
    monkeypatch.setattr(run_module, "enrich_source_from_manufacturer_docs", lambda **_kwargs: {"applied": False, "documents": [], "presentation_applied": False})

    result = run_module.execute_full_run(cli)

    assert provider_calls == [ProviderInputIdentity(model="344709", url=cli.url)]
    assert result["parsed"].source.source_name == "manufacturer_tefal"
    assert result["report"]["fetch_mode"] == "httpx"
    assert result["fetch"].method == "httpx"
    assert result["normalized"]["deterministic_product"]["mpn"] == "IG602A"


def test_prepare_workflow_normalizes_scrape_artifact_paths(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

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

    def fake_execute_full_run(_cli):
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

    monkeypatch.setattr(workflow, "execute_full_run", fake_execute_full_run)

    result = prepare_workflow(cli)
    scrape_dir = result["scrape_dir"]
    rewritten_source = json.loads((scrape_dir / f"{model}.source.json").read_text(encoding="utf-8"))
    rewritten_report = json.loads((scrape_dir / f"{model}.report.json").read_text(encoding="utf-8"))

    assert result["scrape_result"]["model_dir"] == scrape_dir
    assert rewritten_source["raw_html_path"] == str(scrape_dir / f"{model}.raw.html")
    assert all(Path(path).parent == scrape_dir for path in rewritten_report["files_written"])
    assert rewritten_source["gallery_images"][0]["local_path"] == str(scrape_dir / "gallery" / f"{model}-1.jpg")


def test_prepare_workflow_writes_failed_metadata_on_error(tmp_path: Path, monkeypatch) -> None:
    from pipeline import workflow

    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    cli = CLIInput(model="233541", url="https://www.electronet.gr/example", photos=1, sections=0, skroutz_status=0, boxnow=0, price="0", out=str(tmp_path))

    def fake_execute_full_run(_cli):
        raise RuntimeError("prepare exploded")

    monkeypatch.setattr(workflow, "execute_full_run", fake_execute_full_run)

    try:
        prepare_workflow(cli)
    except RuntimeError as exc:
        assert str(exc) == "prepare exploded"
    else:
        raise AssertionError("Expected RuntimeError")

    metadata_path = tmp_path / "work" / "233541" / "prepare.run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["run"]["status"] == "failed"
    assert metadata["run"]["error_code"] == "RuntimeError"
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
    assert result["published_csv_path"] is None
    assert result["validation_report_path"].exists()
    assert result["metadata_path"].exists()
    assert result["run_status"] == "failed"
    assert result["validation_report"]["ok"] is False
    assert "field_health" in result["validation_report"]
    assert result["validation_report"]["errors"] == ["llm_presentation_shape_invalid"]
    assert "Candidate failed validation; skipping publish to products/." in result["validation_report"]["warnings"]
    metadata = json.loads(result["metadata_path"].read_text(encoding="utf-8"))
    assert result["metadata_path"].name == "render.run.json"
    assert metadata["run"]["model"] == model
    assert metadata["run"]["run_type"] == "render"
    assert metadata["run"]["status"] == "failed"
    assert metadata["artifacts"]["candidate_csv_path"] == str(result["candidate_csv_path"])
    assert metadata["artifacts"]["published_csv_path"] is None
    assert metadata["artifacts"]["validation_report_path"] == str(result["validation_report_path"])
    assert metadata["artifacts"]["metadata_path"] == str(result["metadata_path"])
    assert metadata["details"]["validation_ok"] is False
    assert metadata["details"]["published"] is False


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
        assert str(exc) == f"Missing LLM output: {tmp_path / 'work' / model / 'llm_output.json'}"
    else:
        raise AssertionError("Expected FileNotFoundError")

    metadata_path = tmp_path / "work" / model / "render.run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["run"]["status"] == "failed"
    assert metadata["run"]["error_code"] == "FileNotFoundError"
    assert "Missing LLM output" in metadata["run"]["error_detail"]


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
        return ServiceResult(
            run=RunMetadata(model=cli.model, run_type=RunType.PREPARE, status=RunStatus.COMPLETED),
            artifacts=RunArtifacts(
                scrape_dir=tmp_path / "work" / cli.model / "scrape",
                llm_context_path=tmp_path / "work" / cli.model / "llm_context.json",
                prompt_path=tmp_path / "work" / cli.model / "prompt.txt",
                metadata_path=tmp_path / "work" / cli.model / "prepare.run.json",
            ),
        )

    monkeypatch.setattr(workflow, "build_cli_input_from_args", fake_build_cli_input_from_args)
    monkeypatch.setattr(workflow, "prepare_product", fake_prepare_product)

    exit_code = workflow.main(["prepare"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Scrape artifacts: {tmp_path / 'work' / cli.model / 'scrape'}" in captured.out
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
                validation_report_path=tmp_path / "work" / "233541" / "candidate" / "233541.validation.json",
                metadata_path=tmp_path / "work" / "233541" / "render.run.json",
            ),
            details={"validation_ok": True},
        )

    monkeypatch.setattr(workflow, "resolve_model_for_render", fake_resolve_model_for_render)
    monkeypatch.setattr(workflow, "render_product", fake_render_product)

    exit_code = workflow.main(["render"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Candidate CSV: {tmp_path / 'work' / '233541' / 'candidate' / '233541.csv'}" in captured.out
    assert "Validation ok: True" in captured.out


def test_run_cli_input_calls_service_layer(monkeypatch) -> None:
    from pipeline import cli as cli_module

    cli = CLIInput(
        model="233541",
        url="https://www.electronet.gr/example",
        photos=2,
        sections=1,
        skroutz_status=1,
        boxnow=0,
        price="2099",
        out="out",
    )
    expected = ServiceResult(
        run=RunMetadata(model="233541", run_type=RunType.FULL, status=RunStatus.COMPLETED),
        artifacts=RunArtifacts(),
        details={},
    )

    def fake_run_product(request):
        assert request.model == cli.model
        assert request.url == cli.url
        assert request.out == cli.out
        return expected

    monkeypatch.setattr(cli_module, "run_product", fake_run_product)

    assert cli_module.run_cli_input(cli) is expected

