from __future__ import annotations

from pathlib import Path

from pipeline import full_run as run_module
from pipeline.models import CLIInput, SchemaMatchResult, TaxonomyResolution
from pipeline.providers import ProviderInputIdentity, ProviderRegistry, bootstrap_runtime_provider_registry, source_to_provider_id
from pipeline.providers.models import ProviderKind, ProviderSnapshotKind
from pipeline.providers.manufacturer_tefal_provider import ManufacturerTefalProvider
from pipeline.providers.skroutz_provider import SkroutzProvider

SAMPLE_MODEL = "341490"
SAMPLE_URL = "https://www.skroutz.gr/s/51055155/Estia-Intense-Vrastiras-1-7lt-2200W-Luminus-Mat.html"
MANUFACTURER_MODEL = "344709"
MANUFACTURER_URL = "https://shop.tefal.gr/products/dolci-%CF%80%CE%B1%CE%B3%CF%89%CF%84%CE%BF%CE%BC%CE%B7%CF%87%CE%B1%CE%BD%CE%AE-ig602a"


def _build_manufacturer_enrichment_stub() -> dict[str, object]:
    return {
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
    }


class DummyResolver:
    def resolve(self, **_kwargs):
        return (
            TaxonomyResolution(
                parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
                leaf_category="Συσκευές Κουζίνας",
                sub_category="Βραστήρες",
            ),
            [],
        )


class DummySchemaMatcher:
    known_section_titles = set()

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def match(self, *_args, **_kwargs):
        return SchemaMatchResult(matched_schema_id="schema-1", score=0.9), []


class DummyFetcher:
    def fetch_httpx(self, _url):
        raise AssertionError("Legacy Skroutz fetch should not be used when a test-injected provider is selected")

    def fetch_playwright(self, _url):
        raise AssertionError("Legacy Skroutz fetch should not be used when a test-injected provider is selected")

    def download_gallery_images(self, **_kwargs):
        return [], [], []

    def download_besco_images(self, **_kwargs):
        return [], [], []


def build_provider(skroutz_fixtures_root: Path) -> SkroutzProvider:
    return SkroutzProvider(fixture_html_by_url={SAMPLE_URL: skroutz_fixtures_root / "html" / f"{SAMPLE_MODEL}.html"})


def build_manufacturer_provider(manufacturer_tefal_provider_fixtures_root: Path) -> ManufacturerTefalProvider:
    return ManufacturerTefalProvider(
        fixture_html_by_url={MANUFACTURER_URL: manufacturer_tefal_provider_fixtures_root / MANUFACTURER_MODEL / "product.html"}
    )


def test_bootstrap_runtime_provider_registry_registers_active_providers() -> None:
    registry = bootstrap_runtime_provider_registry(
        fetcher=object(),
        electronet_parser=object(),
        skroutz_parser=object(),
        manufacturer_parser=object(),
    )

    assert registry.ids() == ("electronet", "manufacturer_tefal", "skroutz")
    assert [definition.provider_id for definition in registry.definitions()] == ["electronet", "manufacturer_tefal", "skroutz"]


def test_source_to_provider_id_maps_supported_sources() -> None:
    assert source_to_provider_id("electronet") == "electronet"
    assert source_to_provider_id("skroutz") == "skroutz"
    assert source_to_provider_id("manufacturer_tefal") == "manufacturer_tefal"
    assert source_to_provider_id("unsupported_source") is None


def test_skroutz_provider_fetch_snapshot_reads_fixture_html(skroutz_fixtures_root: Path) -> None:
    provider = build_provider(skroutz_fixtures_root)
    identity = ProviderInputIdentity(model=SAMPLE_MODEL, url=SAMPLE_URL)

    snapshot = provider.fetch_snapshot(identity)

    assert provider.supports_identity(identity) is True
    assert snapshot.snapshot_kind == ProviderSnapshotKind.HTML
    assert snapshot.requested_url == SAMPLE_URL
    assert snapshot.final_url == SAMPLE_URL
    assert snapshot.status_code == 200
    assert snapshot.metadata["fetch_method"] == "fixture"
    assert str(snapshot.metadata["fixture_path"]).endswith(f"{SAMPLE_MODEL}.html")
    assert "Estia" in snapshot.body_text


def test_skroutz_provider_normalize_returns_provider_result(skroutz_fixtures_root: Path) -> None:
    provider = build_provider(skroutz_fixtures_root)
    identity = ProviderInputIdentity(model=SAMPLE_MODEL, url=SAMPLE_URL)

    snapshot = provider.fetch_snapshot(identity)
    result = provider.normalize(snapshot, identity)

    assert result.provider.provider_id == "skroutz"
    assert result.provider.kind == ProviderKind.VENDOR_SITE
    assert result.snapshot is snapshot
    assert result.product.source_name == "skroutz"
    assert result.product.page_type == "product"
    assert result.product.canonical_url == SAMPLE_URL
    assert result.metadata["fetch_method"] == "fixture"
    assert "name" in result.provenance
    assert "name" in result.field_diagnostics


def test_skroutz_provider_fetch_snapshot_uses_live_fetcher_when_no_fixture_override() -> None:
    identity = ProviderInputIdentity(model=SAMPLE_MODEL, url=SAMPLE_URL)
    calls = {"playwright": 0, "httpx": 0}

    class LiveFetcher:
        def fetch_playwright(self, url: str):
            calls["playwright"] += 1
            return type(
                "Fetch",
                (),
                {
                    "url": url,
                    "final_url": url,
                    "html": "<html></html>",
                    "status_code": 200,
                    "method": "playwright",
                    "fallback_used": True,
                    "response_headers": {"content-type": "text/html"},
                },
            )()

        def fetch_httpx(self, _url: str):
            calls["httpx"] += 1
            raise AssertionError("HTTPX should not be used when Skroutz Playwright succeeds")

    provider = SkroutzProvider(fetcher=LiveFetcher())

    snapshot = provider.fetch_snapshot(identity)

    assert calls == {"playwright": 1, "httpx": 0}
    assert snapshot.requested_url == SAMPLE_URL
    assert snapshot.final_url == SAMPLE_URL
    assert snapshot.metadata["fetch_method"] == "playwright"
    assert snapshot.metadata["fallback_used"] is True


def test_manufacturer_tefal_provider_fetch_snapshot_reads_fixture_html(
    manufacturer_tefal_provider_fixtures_root: Path,
) -> None:
    provider = build_manufacturer_provider(manufacturer_tefal_provider_fixtures_root)
    identity = ProviderInputIdentity(model=MANUFACTURER_MODEL, url=MANUFACTURER_URL)

    snapshot = provider.fetch_snapshot(identity)

    assert provider.supports_identity(identity) is True
    assert snapshot.snapshot_kind == ProviderSnapshotKind.HTML
    assert snapshot.requested_url == MANUFACTURER_URL
    assert snapshot.final_url == MANUFACTURER_URL
    assert snapshot.status_code == 200
    assert snapshot.metadata["fetch_method"] == "fixture"
    assert str(snapshot.metadata["fixture_path"]).endswith("product.html")
    assert "Tefal Dolci Παγωτομηχανή IG602A" in snapshot.body_text


def test_manufacturer_tefal_provider_normalize_returns_provider_result(
    manufacturer_tefal_provider_fixtures_root: Path,
) -> None:
    provider = build_manufacturer_provider(manufacturer_tefal_provider_fixtures_root)
    identity = ProviderInputIdentity(model=MANUFACTURER_MODEL, url=MANUFACTURER_URL)

    snapshot = provider.fetch_snapshot(identity)
    result = provider.normalize(snapshot, identity)

    assert result.provider.provider_id == "manufacturer_tefal"
    assert result.provider.kind == ProviderKind.MANUFACTURER_SITE
    assert result.snapshot is snapshot
    assert result.product.source_name == "manufacturer_tefal"
    assert result.product.page_type == "product"
    assert result.product.canonical_url == MANUFACTURER_URL
    assert result.product.mpn == "IG602A"
    assert result.metadata["fetch_method"] == "fixture"
    assert "name" in result.provenance
    assert "name" in result.field_diagnostics


def test_execute_full_run_uses_test_injected_skroutz_provider(monkeypatch, tmp_path: Path, skroutz_fixtures_root: Path) -> None:
    cli = CLIInput(
        model=SAMPLE_MODEL,
        url=SAMPLE_URL,
        photos=2,
        sections=0,
        skroutz_status=0,
        boxnow=1,
        price="19",
        out=str(tmp_path),
    )
    provider = build_provider(skroutz_fixtures_root)

    monkeypatch.setattr(run_module, "detect_source", lambda _url: "skroutz")
    monkeypatch.setattr(run_module, "validate_url_scope", lambda _url: ("skroutz", True, "skroutz_product_path"))
    monkeypatch.setattr(run_module, "ElectronetFetcher", lambda: DummyFetcher())
    monkeypatch.setattr(run_module, "SchemaMatcher", DummySchemaMatcher)
    monkeypatch.setattr(run_module, "TaxonomyResolver", lambda: DummyResolver())
    monkeypatch.setattr(run_module, "enrich_source_from_manufacturer_docs", lambda **_kwargs: _build_manufacturer_enrichment_stub())
    registry = ProviderRegistry()
    registry.register(provider)
    monkeypatch.setattr(run_module, "bootstrap_runtime_provider_registry", lambda **_kwargs: registry)

    result = run_module.execute_full_run(cli)

    assert result["report"]["source"] == "skroutz"
    assert result["report"]["fetch_mode"] == "fixture"
    assert result["fetch"].method == "fixture"
    assert result["parsed"].source.source_name == "skroutz"
    assert result["source_json_path"].exists()

