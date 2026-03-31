from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.models import CLIInput, ParsedProduct, SchemaMatchResult, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from pipeline.prepare_stage import execute_prepare_stage
from pipeline.providers import ProviderInputIdentity, ProviderRegistry, bootstrap_runtime_provider_registry, source_to_provider_id
from pipeline.providers.models import (
    ProviderCapability,
    ProviderDefinition,
    ProviderKind,
    ProviderResult,
    ProviderSnapshot,
    ProviderSnapshotKind,
)
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


def test_execute_prepare_stage_uses_test_injected_skroutz_provider(tmp_path: Path, skroutz_fixtures_root: Path) -> None:
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
    registry = ProviderRegistry()
    registry.register(provider)

    result = execute_prepare_stage(
        cli,
        model_dir=tmp_path / SAMPLE_MODEL,
        detect_source_fn=lambda _url: "skroutz",
        validate_url_scope_fn=lambda _url: ("skroutz", True, "skroutz_product_path"),
        schema_matcher_factory=DummySchemaMatcher,
        electronet_parser_factory=lambda **_kwargs: object(),
        skroutz_parser_factory=lambda: object(),
        manufacturer_parser_factory=lambda: object(),
        fetcher_factory=DummyFetcher,
        taxonomy_resolver_factory=DummyResolver,
        bootstrap_provider_registry_fn=lambda **_kwargs: registry,
        enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: _build_manufacturer_enrichment_stub(),
    )

    assert result["report"]["source"] == "skroutz"
    assert result["report"]["fetch_mode"] == "fixture"
    assert result["fetch"].method == "fixture"
    assert result["parsed"].source.source_name == "skroutz"
    assert result["source_json_path"].exists()


def test_execute_prepare_stage_allows_electronet_product_code_mismatch(tmp_path: Path) -> None:
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
    provider_calls: list[ProviderInputIdentity] = []

    class DummyElectronetProvider:
        definition = ProviderDefinition(
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
        )

        @property
        def provider_id(self) -> str:
            return self.definition.provider_id

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
                provider=self.definition,
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    registry = ProviderRegistry()
    registry.register(DummyElectronetProvider())

    result = execute_prepare_stage(
        cli,
        model_dir=tmp_path / cli.model,
        detect_source_fn=lambda _url: "electronet",
        validate_url_scope_fn=lambda _url: ("electronet", True, ""),
        schema_matcher_factory=DummySchemaMatcher,
        electronet_parser_factory=lambda **_kwargs: object(),
        skroutz_parser_factory=lambda: object(),
        manufacturer_parser_factory=lambda: object(),
        fetcher_factory=DummyFetcher,
        taxonomy_resolver_factory=DummyResolver,
        bootstrap_provider_registry_fn=lambda **_kwargs: registry,
        enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: {},
    )

    assert provider_calls == [ProviderInputIdentity(model="229957", url="https://www.electronet.gr/example")]
    assert result["parsed"].warnings == ["source_product_code_mismatch:input=229957:page=235370"]
    assert result["report"]["source"] == "electronet"
    assert result["report"]["identity_checks"]["source"] == "electronet"


def test_execute_prepare_stage_routes_skroutz_through_provider_by_default(tmp_path: Path) -> None:
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

    class DummySkroutzProvider:
        definition = ProviderDefinition(
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
        )

        @property
        def provider_id(self) -> str:
            return self.definition.provider_id

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
                provider=self.definition,
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    registry = ProviderRegistry()
    registry.register(DummySkroutzProvider())

    result = execute_prepare_stage(
        cli,
        model_dir=tmp_path / cli.model,
        detect_source_fn=lambda _url: "skroutz",
        validate_url_scope_fn=lambda _url: ("skroutz", True, "skroutz_product_path"),
        schema_matcher_factory=DummySchemaMatcher,
        electronet_parser_factory=lambda **_kwargs: object(),
        skroutz_parser_factory=lambda: object(),
        manufacturer_parser_factory=lambda: object(),
        fetcher_factory=DummyFetcher,
        taxonomy_resolver_factory=DummyResolver,
        bootstrap_provider_registry_fn=lambda **_kwargs: registry,
        enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: _build_manufacturer_enrichment_stub(),
    )

    assert provider_calls == [ProviderInputIdentity(model=SAMPLE_MODEL, url=cli.url)]
    assert result["report"]["source"] == "skroutz"
    assert result["report"]["fetch_mode"] == "playwright"
    assert result["fetch"].method == "playwright"
    assert result["parsed"].source.source_name == "skroutz"


def test_execute_prepare_stage_routes_manufacturer_tefal_through_provider_by_default(tmp_path: Path) -> None:
    cli = CLIInput(
        model=MANUFACTURER_MODEL,
        url=MANUFACTURER_URL,
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

    class DummyManufacturerResolver:
        def resolve(self, **_kwargs):
            return (
                TaxonomyResolution(
                    parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ",
                    leaf_category="Μικροί Μάγειρες",
                    sub_category="Παγωτομηχανές",
                ),
                [],
            )

    class DummyManufacturerTefalProvider:
        definition = ProviderDefinition(
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
        )

        @property
        def provider_id(self) -> str:
            return self.definition.provider_id

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
                provider=self.definition,
                identity=identity,
                snapshot=snapshot,
                product=parsed.source,
                provenance=dict(parsed.provenance),
                field_diagnostics=dict(parsed.field_diagnostics),
                warnings=list(parsed.warnings),
                missing_fields=list(parsed.missing_fields),
                critical_missing=list(parsed.critical_missing),
            )

    registry = ProviderRegistry()
    registry.register(DummyManufacturerTefalProvider())

    result = execute_prepare_stage(
        cli,
        model_dir=tmp_path / cli.model,
        detect_source_fn=lambda _url: "manufacturer_tefal",
        validate_url_scope_fn=lambda _url: ("manufacturer_tefal", True, "manufacturer_tefal_product_path"),
        schema_matcher_factory=DummySchemaMatcher,
        electronet_parser_factory=lambda **_kwargs: object(),
        skroutz_parser_factory=lambda: object(),
        manufacturer_parser_factory=lambda: object(),
        fetcher_factory=DummyFetcher,
        taxonomy_resolver_factory=DummyManufacturerResolver,
        bootstrap_provider_registry_fn=lambda **_kwargs: registry,
        enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: {"applied": False, "documents": [], "presentation_applied": False},
    )

    assert provider_calls == [ProviderInputIdentity(model=MANUFACTURER_MODEL, url=cli.url)]
    assert result["parsed"].source.source_name == "manufacturer_tefal"
    assert result["report"]["fetch_mode"] == "httpx"
    assert result["fetch"].method == "httpx"
    assert result["normalized"]["deterministic_product"]["mpn"] == "IG602A"


def test_execute_prepare_stage_fails_fast_when_supported_source_has_no_provider(tmp_path: Path) -> None:
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

    with pytest.raises(RuntimeError, match="Provider 'skroutz' is not registered"):
        execute_prepare_stage(
            cli,
            model_dir=tmp_path / SAMPLE_MODEL,
            detect_source_fn=lambda _url: "skroutz",
            validate_url_scope_fn=lambda _url: ("skroutz", True, "skroutz_product_path"),
            schema_matcher_factory=DummySchemaMatcher,
            electronet_parser_factory=lambda **_kwargs: object(),
            skroutz_parser_factory=lambda: object(),
            manufacturer_parser_factory=lambda: object(),
            fetcher_factory=DummyFetcher,
            taxonomy_resolver_factory=DummyResolver,
            bootstrap_provider_registry_fn=lambda **_kwargs: ProviderRegistry(),
            enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: _build_manufacturer_enrichment_stub(),
        )

