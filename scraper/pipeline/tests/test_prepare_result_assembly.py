from __future__ import annotations

from pathlib import Path

from pipeline.models import CLIInput, FetchResult, ParsedProduct, SourceProductData, SpecItem, SpecSection, TaxonomyResolution
from pipeline.prepare_provider_resolution import PrepareProviderResolutionResult
from pipeline.prepare_scrape_persistence import PrepareScrapePersistenceInput, PrepareScrapePersistenceResult
from pipeline.prepare_stage import execute_prepare_stage
from pipeline.schema_matcher import SchemaMatcher


TV_TEMPLATE_SCHEMA_ID = "sha1:954c8413f2da941e78f3ddce65df522654336c8c"
BUILT_IN_HOB_SCHEMA_ID = "sha1:5fd482e1bc95f854984188f4d55892e272bf6d82"


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


def _build_prepare_provider_resolution_result(
    *,
    source: str,
    url: str,
    parsed: ParsedProduct,
    fetch_method: str,
) -> PrepareProviderResolutionResult:
    return PrepareProviderResolutionResult(
        source=source,
        provider_id=source,
        fetch=FetchResult(
            url=url,
            final_url=url,
            html="<html></html>",
            status_code=200,
            method=fetch_method,
            fallback_used=False,
        ),
        parsed=parsed,
    )


def _persist_stub(persistence_input: PrepareScrapePersistenceInput) -> PrepareScrapePersistenceResult:
    return PrepareScrapePersistenceResult(
        scrape_dir=persistence_input.scrape_dir,
        raw_html_path=persistence_input.raw_html_path,
        source_json_path=persistence_input.source_json_path,
        normalized_json_path=persistence_input.normalized_json_path,
        report_json_path=persistence_input.report_json_path,
        bescos_raw_path=persistence_input.bescos_raw_path,
    )


def _build_cli(tmp_path: Path, *, model: str = "344424", url: str) -> CLIInput:
    return CLIInput(
        model=model,
        url=url,
        photos=2,
        sections=0,
        skroutz_status=1,
        boxnow=0,
        price="299",
        out=str(tmp_path),
    )


def _build_hob_taxonomy() -> TaxonomyResolution:
    return TaxonomyResolution(
        parent_category="ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ",
        leaf_category="Εντοιχιζόμενες Συσκευές",
        sub_category="Εστίες",
    )


def _build_tv_taxonomy() -> TaxonomyResolution:
    return TaxonomyResolution(
        parent_category="ΕΙΚΟΝΑ & ΗΧΟΣ",
        leaf_category="Τηλεοράσεις",
        sub_category="50'' & άνω",
        cta_url="https://www.etranoulis.gr/eikona-hxos/thleoraseis/50-anw",
    )


def _build_skroutz_tv_source() -> SourceProductData:
    return SourceProductData(
        source_name="skroutz",
        page_type="product",
        url="https://www.skroutz.gr/s/61351575/hisense-smart-tileorasi-55-4k-uhd-led-a6q-hdr-2025-55a6q.html",
        canonical_url="https://www.skroutz.gr/s/61351575/hisense-smart-tileorasi-55-4k-uhd-led-a6q-hdr-2025-55a6q.html",
        product_code="143051",
        brand="Hisense",
        mpn="55A6Q",
        name='Hisense Smart Τηλεόραση 55" 4K UHD LED A6Q HDR (2025) 55A6Q',
        hero_summary=(
            "Το AI 4K Upscaler της Hisense αναβαθμίζει το περιεχόμενο σε 4K. "
            "Το Game Mode PLUS και το Game Bar βελτιώνουν το gaming, ενώ οι τεχνολογίες VRR και ALLM "
            "μειώνουν την καθυστέρηση. Η Hisense TV αποδίδει Dolby Audio και DTS Virtual:X."
        ),
        presentation_source_text=(
            "Το AI 4K Upscaler αναβαθμίζει την εικόνα. "
            "Το Game Mode PLUS και το Game Bar προσθέτουν έλεγχο. "
            "Το Hisense Voice Remote διευκολύνει τη χρήση."
        ),
        taxonomy_tv_inches=55,
        key_specs=[
            SpecItem(label="Διαγώνιος", value='55 "'),
            SpecItem(label="Ευκρίνεια", value="4K Ultra HD"),
            SpecItem(label="Ρυθμός Ανανέωσης", value="50/60 Hz"),
            SpecItem(label="Τύπος Panel", value="Direct LED"),
            SpecItem(label="Τύποι HDR", value="HDR10, HDR10+, Dolby Vision, HLG"),
            SpecItem(label="Κανάλια", value="2.1"),
            SpecItem(label="Ισχύς", value="20 W"),
        ],
        spec_sections=[
            SpecSection(
                section="Εικόνα",
                items=[
                    SpecItem(label="Διαγώνιος", value='55 "'),
                    SpecItem(label="Ευκρίνεια", value="4K Ultra HD"),
                    SpecItem(label="Ρυθμός Ανανέωσης", value="50/60 Hz"),
                    SpecItem(label="Τύπος Panel", value="Direct LED"),
                    SpecItem(label="Τύποι HDR", value="HDR10, HDR10+, Dolby Vision, HLG"),
                ],
            ),
            SpecSection(
                section="Ήχος",
                items=[
                    SpecItem(label="Κανάλια", value="2.1"),
                    SpecItem(label="Ισχύς", value="20 W"),
                    SpecItem(label="Πρότυπα Ήχου", value="DTS Virtual: X"),
                ],
            ),
            SpecSection(
                section="Δυνατότητες & Λειτουργίες",
                items=[SpecItem(label="Δέκτης", value="DVB-C, DVB-S2, DVB-T2")],
            ),
            SpecSection(
                section="Ενσύρματες Συνδέσεις",
                items=[
                    SpecItem(label="Πλήθος USB", value="2"),
                    SpecItem(label="Σύνολο Θυρών HDMI", value="3"),
                ],
            ),
            SpecSection(
                section="Γενικά",
                items=[
                    SpecItem(label="Βάρος", value="10,9 kg"),
                    SpecItem(label="VESA Mount", value="400 x 200 mm"),
                ],
            ),
            SpecSection(
                section="Ενεργειακή Ετικέτα",
                items=[SpecItem(label="Ενεργειακή Κλάση", value="E")],
            ),
            SpecSection(
                section="Διαστάσεις (με Βάση)",
                items=[
                    SpecItem(label="Πλάτος", value="1234 mm"),
                    SpecItem(label="Ύψος", value="751 mm"),
                    SpecItem(label="Πάχος", value="298 mm"),
                ],
            ),
        ],
    )


def _build_skroutz_hob_source() -> SourceProductData:
    return SourceProductData(
        source_name="skroutz",
        page_type="product",
        url="https://www.skroutz.gr/s/344424/Neff-T16BT60N0.html",
        canonical_url="https://www.skroutz.gr/s/344424/Neff-T16BT60N0.html",
        product_code="344424",
        brand="Neff",
        mpn="T16BT60N0",
        name="Neff T16BT60N0 Hob",
        price_text="299,00 €",
        price_value=299.0,
        hero_summary="Κεραμική εντοιχιζόμενη εστία με 4 ζώνες και χειρισμό TwistPad.",
        spec_sections=[
            SpecSection(
                section="Γενικά",
                items=[
                    SpecItem(label="Τύπος", value="Κεραμική"),
                    SpecItem(label="Αριθμός Εστιών", value="4"),
                    SpecItem(label="Διακόπτες", value="Αφής"),
                    SpecItem(label="Χρώμα", value="Μαύρο"),
                ],
            ),
            SpecSection(
                section="Δυνατότητες & Λειτουργίες",
                items=[
                    SpecItem(label="Smart", value="Όχι"),
                    SpecItem(label="Λειτουργία Κλειδώματος", value="Ναι"),
                    SpecItem(label="Χρονοδιακόπτης", value="Ναι"),
                    SpecItem(label="Ένδειξη Υπολοίπου Θερμότητας", value="Ναι"),
                ],
            ),
            SpecSection(
                section="Διαστάσεις Συσκευής",
                items=[
                    SpecItem(label="Ύψος", value="4,8 cm"),
                    SpecItem(label="Πλάτος", value="58,3 cm"),
                    SpecItem(label="Βάθος", value="51,3 cm"),
                ],
            ),
        ],
        manufacturer_spec_sections=[
            SpecSection(
                section="Τεχνικά στοιχεία",
                items=[
                    SpecItem(label="Τύπος εγκατάστασης", value="Εντοιχιζόμενη συσκευή"),
                    SpecItem(label="Τύπος λειτουργίας", value="Ηλεκτρική"),
                    SpecItem(label="Βασικό υλικό επιφανειών", value="Υαλοκεραμική"),
                    SpecItem(label="Συνολικός αριθμός ζωνών που μπορούν να χρησιμοποιηθούν ταυτόχρονα", value="4"),
                    SpecItem(label="Διαστάσεις εντοιχισμού (υ x π x β)", value="48 x 560 x 490 - 500 mm"),
                    SpecItem(label="Διαστάσεις συσκευής (ΥxΠxΒ mm)", value="48 x 583 x 513"),
                    SpecItem(label="Καθαρό βάρος", value="8.0 kg"),
                    SpecItem(label="Χρώμα πλαισίου", value="Ανοξείδωτο"),
                ],
            ),
            SpecSection(
                section="Γενικά χαρακτηριστικά",
                items=[
                    SpecItem(label="Είδος ηλεκτρονικού ελέγχου", value="TwistPad®"),
                    SpecItem(label="Ψηφιακό χρονόμετρο", value="ένδειξη του χρόνου που έχει περάσει"),
                    SpecItem(label="Αυτόματη απενεργοποίηση ασφαλείας", value="η εστία σταματά να θερμαίνεται"),
                    SpecItem(label="Κλείδωμα ασφαλείας για τα παιδιά", value="αποτροπή ενεργοποίησης"),
                    SpecItem(label="Συνολική ισχύς", value="6.3 kW"),
                ],
            ),
        ],
        manufacturer_source_text=(
            "TwistPad 17 βαθμίδες ισχύος λειτουργία Restart λειτουργία Alarm "
            "λειτουργία διατήρησης θερμότητας ψηφιακό χρονόμετρο."
        ),
    )


def _build_sparse_skroutz_hob_source() -> SourceProductData:
    return SourceProductData(
        source_name="skroutz",
        page_type="product",
        url="https://www.skroutz.gr/s/999999/Weak-Hob.html",
        canonical_url="https://www.skroutz.gr/s/999999/Weak-Hob.html",
        product_code="999999",
        brand="Neff",
        mpn="WEAK123",
        name="Neff WEAK123 Hob",
        spec_sections=[
            SpecSection(
                section="Γενικά",
                items=[SpecItem(label="Τύπος", value="Κεραμική")],
            )
        ],
    )


def _build_no_specs_source() -> SourceProductData:
    return SourceProductData(
        source_name="electronet",
        page_type="product",
        url="https://www.electronet.gr/no-spec-product",
        canonical_url="https://www.electronet.gr/no-spec-product",
        product_code="000001",
        brand="LG",
        mpn="NO-SPECS-1",
        name="LG NO-SPECS-1",
    )


def _build_parsed(source: SourceProductData) -> ParsedProduct:
    return ParsedProduct(
        source=source,
        provenance={
            "product_code": "parser",
            "brand": "parser",
            "mpn": "parser",
            "name": "parser",
            "price": "parser",
        },
    )


def _run_prepare_stage(
    tmp_path: Path,
    *,
    source: SourceProductData,
    taxonomy: TaxonomyResolution,
    taxonomy_candidates: list[dict[str, object]] | None = None,
    schema_matcher_factory=SchemaMatcher,
    model: str = "344424",
) -> tuple[CLIInput, dict[str, object]]:
    cli = _build_cli(tmp_path, model=model, url=source.url)
    parsed = _build_parsed(source)

    class StaticResolver:
        def resolve(self, **_kwargs):
            return taxonomy, taxonomy_candidates or []

    result = execute_prepare_stage(
        cli,
        model_dir=tmp_path / cli.model,
        validate_url_scope_fn=lambda _url: (source.source_name or "unknown", True, "test_scope"),
        schema_matcher_factory=schema_matcher_factory,
        fetcher_factory=lambda: object(),
        taxonomy_resolver_factory=lambda: StaticResolver(),
        resolve_prepare_provider_input_fn=lambda cli_arg, **_kwargs: _build_prepare_provider_resolution_result(
            source=source.source_name or "unknown",
            url=cli_arg.url,
            parsed=parsed,
            fetch_method="fixture",
        ),
        enrich_source_from_manufacturer_docs_fn=lambda **_kwargs: _build_manufacturer_enrichment_stub(),
        persist_prepare_scrape_artifacts_fn=_persist_stub,
    )
    return cli, result


def test_prepare_stage_passes_effective_sections_and_schema_preferences_to_schema_matcher(tmp_path: Path) -> None:
    source = _build_skroutz_hob_source()
    matcher_calls: list[dict[str, object]] = []

    class RecordingSchemaMatcher:
        def __init__(self, *args, **kwargs) -> None:
            self._matcher = SchemaMatcher(*args, **kwargs)
            self.known_section_titles = self._matcher.known_section_titles

        def match(self, spec_sections, taxonomy_sub_category=None, preferred_source_files=None):
            matcher_calls.append(
                {
                    "section_titles": [section.section for section in spec_sections],
                    "taxonomy_sub_category": taxonomy_sub_category,
                    "preferred_source_files": list(preferred_source_files or []),
                }
            )
            return self._matcher.match(spec_sections, taxonomy_sub_category, preferred_source_files)

    _, result = _run_prepare_stage(
        tmp_path,
        source=source,
        taxonomy=_build_hob_taxonomy(),
        taxonomy_candidates=[{"taxonomy_path": "ΟΙΚΙΑΚΕΣ ΣΥΣΚΕΥΕΣ > Εντοιχιζόμενες Συσκευές > Εστίες"}],
        schema_matcher_factory=RecordingSchemaMatcher,
    )

    assert matcher_calls == [
        {
            "section_titles": [
                "Τεχνικά στοιχεία",
                "Γενικά χαρακτηριστικά",
                "Γενικά",
                "Δυνατότητες & Λειτουργίες",
                "Διαστάσεις Συσκευής",
            ],
            "taxonomy_sub_category": "Εστίες",
            "preferred_source_files": ["esties.json"],
        }
    ]
    assert result["schema_match"].matched_schema_id == BUILT_IN_HOB_SCHEMA_ID
    assert result["schema_candidates"][0]["source_files"] == ["esties.json"]
    assert result["report"]["schema_preference"]["preferred_source_files"] == ["esties.json"]


def test_prepare_stage_pins_matched_schema_row_and_normalized_payload_shape(tmp_path: Path) -> None:
    cli, result = _run_prepare_stage(
        tmp_path,
        source=_build_skroutz_tv_source(),
        taxonomy=_build_tv_taxonomy(),
        model="143051",
    )

    normalized = result["normalized"]
    row = result["row"]

    assert set(normalized) == {
        "input",
        "source",
        "taxonomy",
        "schema_match",
        "deterministic_product",
        "characteristics_diagnostics",
        "downloaded_gallery_count",
        "downloaded_besco_count",
        "llm_product",
        "llm_intro_text",
        "deterministic_presentation_sections",
        "llm_presentation",
        "csv_row",
    }
    assert normalized["input"]["model"] == cli.model
    assert normalized["source"]["spec_sections"][0]["section"] == "Εικόνα"
    assert normalized["schema_match"]["matched_schema_id"] == TV_TEMPLATE_SCHEMA_ID
    assert 0.0 < normalized["schema_match"]["score"] < 0.35
    assert "weak_schema_match" in normalized["schema_match"]["warnings"]
    assert normalized["characteristics_diagnostics"]["template_source"] == "schema_library_with_custom_overrides"
    assert normalized["characteristics_diagnostics"]["matched_schema_id"] == TV_TEMPLATE_SCHEMA_ID
    assert normalized["downloaded_gallery_count"] == 0
    assert normalized["downloaded_besco_count"] == 0
    assert normalized["llm_product"] == {"meta_keywords": ["Hisense", "55A6Q"]}
    assert normalized["llm_intro_text"] == ""
    assert normalized["deterministic_presentation_sections"] == []
    assert normalized["llm_presentation"] == {}
    assert normalized["csv_row"] == row
    assert row["model"] == cli.model
    assert row["mpn"] == "55A6Q"
    assert row["manufacturer"] == "Hisense"
    assert row["meta_title"] == normalized["deterministic_product"]["meta_title"]
    assert row["seo_keyword"] == normalized["deterministic_product"]["seo_keyword"]
    assert "ULTRA HD ( 4K )" in row["characteristics"]
    assert "DVB-T2/C/S2" in row["characteristics"]


def test_prepare_stage_pins_report_fields_used_downstream(tmp_path: Path) -> None:
    cli, result = _run_prepare_stage(
        tmp_path,
        source=_build_skroutz_tv_source(),
        taxonomy=_build_tv_taxonomy(),
        taxonomy_candidates=[{"taxonomy_path": "ΕΙΚΟΝΑ & ΗΧΟΣ > Τηλεοράσεις > 50'' & άνω"}],
        model="143051",
    )

    report = result["report"]

    for key in (
        "source",
        "fetch_mode",
        "source_resolution",
        "identity_checks",
        "url_scope_validation",
        "taxonomy_resolution",
        "manufacturer_enrichment",
        "schema_resolution",
        "characteristics_diagnostics",
        "schema_preference",
        "critical_extractors",
        "warnings",
        "taxonomy_candidates",
        "schema_candidates",
        "gallery_summary",
        "besco_summary",
        "files_written",
    ):
        assert key in report

    assert report["source"] == "skroutz"
    assert report["fetch_mode"] == "fixture"
    assert report["source_resolution"] == {
        "requested_url": cli.url,
        "detected_source": "skroutz",
        "resolved_url": cli.url,
    }
    assert report["identity_checks"] == {
        "source": "skroutz",
        "input_model": cli.model,
        "page_type": "product",
        "page_product_code": "143051",
        "name_present": True,
        "brand_present": True,
        "mpn_present": True,
    }
    assert report["url_scope_validation"] == {
        "ok": True,
        "reason": "test_scope",
        "final_url_source": "skroutz",
    }
    assert report["schema_resolution"] == result["schema_match"].to_dict()
    assert report["characteristics_diagnostics"] == result["normalized"]["characteristics_diagnostics"]
    assert report["schema_preference"] == {"preferred_source_files": ["tileoraseis.json"]}
    assert report["critical_extractors"]["taxonomy"] == "resolved"
    assert report["critical_extractors"]["schema_match"] == "weak"
    assert "weak_schema_match" in report["warnings"]
    assert f"characteristics_template_used:schema:{TV_TEMPLATE_SCHEMA_ID}" in report["warnings"]
    assert report["taxonomy_candidates"] == [{"taxonomy_path": "ΕΙΚΟΝΑ & ΗΧΟΣ > Τηλεοράσεις > 50'' & άνω"}]
    assert report["schema_candidates"][0]["matched_schema_id"] == TV_TEMPLATE_SCHEMA_ID
    assert report["gallery_summary"] == {"extracted_count": 0, "downloaded_count": 0, "requested_photos": 2}
    assert report["besco_summary"] == {
        "presentation_blocks_count": 0,
        "extracted_count": 0,
        "downloaded_count": 0,
        "requested_sections": 0,
    }
    assert report["files_written"] == [
        str((tmp_path / cli.model / f"{cli.model}.raw.html")),
        str((tmp_path / cli.model / f"{cli.model}.source.json")),
        str((tmp_path / cli.model / f"{cli.model}.normalized.json")),
        str((tmp_path / cli.model / f"{cli.model}.report.json")),
    ]


def test_prepare_stage_preserves_weak_schema_match_semantics(tmp_path: Path) -> None:
    _, result = _run_prepare_stage(
        tmp_path,
        source=_build_sparse_skroutz_hob_source(),
        taxonomy=_build_hob_taxonomy(),
        model="999999",
    )

    schema_match = result["schema_match"]

    assert schema_match.matched_schema_id == BUILT_IN_HOB_SCHEMA_ID
    assert 0.0 < schema_match.score < 0.35
    assert "weak_schema_match" in schema_match.warnings
    assert result["report"]["critical_extractors"]["schema_match"] == "weak"
    assert "weak_schema_match" in result["report"]["warnings"]
    assert result["report"]["schema_candidates"][0]["matched_schema_id"] == BUILT_IN_HOB_SCHEMA_ID


def test_prepare_stage_preserves_no_spec_sections_and_unresolved_taxonomy_semantics(tmp_path: Path) -> None:
    _, result = _run_prepare_stage(
        tmp_path,
        source=_build_no_specs_source(),
        taxonomy=TaxonomyResolution(),
        model="000001",
    )

    schema_match = result["schema_match"]

    assert schema_match.matched_schema_id is None
    assert schema_match.score == 0.0
    assert schema_match.warnings == ["no_spec_sections_extracted"]
    assert result["normalized"]["schema_match"] == schema_match.to_dict()
    assert result["normalized"]["characteristics_diagnostics"]["mode"] == "raw_spec_sections"
    assert result["report"]["critical_extractors"]["taxonomy"] == "unresolved"
    assert result["report"]["critical_extractors"]["schema_match"] == "none"
    assert result["report"]["warnings"] == [
        "description_not_built_from_source",
        "cta_url_unresolved",
        "no_spec_sections_extracted",
    ]
    assert result["report"]["schema_candidates"] == []
