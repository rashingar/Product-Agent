import argparse
import csv
import json
from pathlib import Path

from bs4 import BeautifulSoup

from electronet_single_import.cli import validate_input
from electronet_single_import.mapping import build_row, derive_seo_keyword
from electronet_single_import.models import CLIInput, FetchResult, ParsedProduct, SchemaMatchResult, SourceProductData, TaxonomyResolution
from electronet_single_import.parser_product_skroutz import SkroutzProductParser
from electronet_single_import.taxonomy import TaxonomyResolver
from electronet_single_import.workflow import prepare_workflow, render_workflow

REPO_ROOT = Path(r"c:\Users\user\Documents\VS_Projects\tranoulis\Product-Agent")
FIXTURES_ROOT = REPO_ROOT / "scrapper" / "electronet_single_import" / "tests" / "fixtures" / "skroutz"
PRODUCTS_ROOT = REPO_ROOT / "products"
JPEG_BYTES = b"\xff\xd8\xff\xdb\x00C\x00" + (b"\x08" * 64) + b"\xff\xd9"

SAMPLES = {
    "143481": {
        "url": "https://www.skroutz.gr/s/61800471/tcl-q65h-soundbar-5-1-bluetooth-hdmi-kai-wi-fi-me-asyrmato-subwoofer-mayro.html",
        "photos": 8,
        "sections": 9,
        "skroutz_status": 1,
        "boxnow": 0,
        "price": "269",
    },
    "344317": {
        "url": "https://www.skroutz.cy/s/65282590/tefal-subito-kafetiera-filtrou-1000w.html",
        "photos": 2,
        "sections": 0,
        "skroutz_status": 0,
        "boxnow": 0,
        "price": "39",
    },
    "341490": {
        "url": "https://www.skroutz.gr/s/51055155/Estia-Intense-Vrastiras-1-7lt-2200W-Luminus-Mat.html",
        "photos": 7,
        "sections": 0,
        "skroutz_status": 0,
        "boxnow": 1,
        "price": "19",
    },
    "307497": {
        "url": "https://www.skroutz.gr/s/21656760/Fancy-0013-Epitrapezia-Estia-Emagie-Dipli-Leyki-0013.html",
        "photos": 2,
        "sections": 0,
        "skroutz_status": 0,
        "boxnow": 1,
        "price": "65",
    },
}


def read_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))


def build_llm_payload_from_baseline(path: Path) -> dict[str, object]:
    row = read_csv_row(path)
    soup = BeautifulSoup(row["description"], "lxml")
    intro_span = soup.select_one("p span")
    cta = soup.select_one("a")
    section_nodes = soup.select("div.etr-sec, div.etr-sec.rev")
    intro_html = intro_span.decode_contents().strip() if intro_span else ""
    cta_text = cta.get_text(" ", strip=True) if cta else ""
    meta_keywords = [item.strip() for item in row["meta_keyword"].split(",") if item.strip()]
    return {
        "product": {
            "meta_description": row["meta_description"],
            "meta_keywords": meta_keywords,
        },
        "presentation": {
            "intro_html": intro_html,
            "cta_text": cta_text,
            "sections": [
                {
                    "title": section.select_one(".etr-text h2").get_text(" ", strip=True),
                    "body_html": section.select_one(".etr-text p span").decode_contents().strip(),
                }
                for section in section_nodes
                if section.select_one(".etr-text h2") is not None and section.select_one(".etr-text p span") is not None
            ],
        },
    }


def install_fixture_fetcher(monkeypatch) -> None:
    from electronet_single_import import fetcher

    def fake_fetch_httpx(self, url: str):
        raise fetcher.FetchError(f"httpx disabled for test: {url}")

    def fake_fetch_playwright(self, url: str):
        model = next(model for model, sample in SAMPLES.items() if sample["url"] == url)
        html = (FIXTURES_ROOT / f"{model}.html").read_text(encoding="utf-8")
        return FetchResult(url=url, final_url=url, html=html, status_code=200, method="playwright", fallback_used=True, response_headers={})

    def fake_fetch_binary(self, url: str):
        return JPEG_BYTES, "image/jpeg"

    def fake_extract_skroutz_section_image_records(self, url: str):
        model = next(model for model, sample in SAMPLES.items() if sample["url"] == url)
        path = FIXTURES_ROOT / f"{model}.rendered_sections.json"
        if not path.exists():
            return {"window": {}, "containers": [], "sections": []}
        return json.loads(path.read_text(encoding="utf-8"))

    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_httpx", fake_fetch_httpx)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_playwright", fake_fetch_playwright)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_binary", fake_fetch_binary)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "extract_skroutz_section_image_records", fake_extract_skroutz_section_image_records)


def make_cli(model: str) -> CLIInput:
    sample = SAMPLES[model]
    return CLIInput(
        model=model,
        url=sample["url"],
        photos=sample["photos"],
        sections=sample["sections"],
        skroutz_status=sample["skroutz_status"],
        boxnow=sample["boxnow"],
        price=sample["price"],
        out="unused",
    )


def copy_baseline_products(tmp_products_root: Path) -> None:
    tmp_products_root.mkdir(parents=True, exist_ok=True)
    for model in SAMPLES:
        (tmp_products_root / f"{model}.csv").write_text((PRODUCTS_ROOT / f"{model}.csv").read_text(encoding="utf-8-sig"), encoding="utf-8")


def test_validate_input_accepts_skroutz_sections_for_v2() -> None:
    args = argparse.Namespace(
        model="143481",
        url=SAMPLES["143481"]["url"],
        photos=8,
        sections=9,
        skroutz_status=1,
        boxnow=0,
        price="269",
        out="out",
    )
    cli = validate_input(args)
    assert cli.model == "143481"
    assert cli.sections == 9
    assert cli.skroutz_status == 1


def test_validate_input_rejects_non_product_skroutz_url() -> None:
    args = argparse.Namespace(model="341490", url="https://www.skroutz.gr/c/699/vrastires.html", photos=1, sections=0, skroutz_status=0, boxnow=0, price="19", out="out")
    try:
        validate_input(args)
    except ValueError as exc:
        assert str(exc) == "Input URL must be a Skroutz product URL"
    else:
        raise AssertionError("Expected ValueError")


def test_build_row_keeps_prompt_price_contract() -> None:
    cli = CLIInput(model="341490", url=SAMPLES["341490"]["url"], price="0")
    parsed = ParsedProduct(source=SourceProductData(source_name="skroutz", brand="Estia", mpn="06-24567", name="Estia 06-24567", price_value=15.9))
    taxonomy = TaxonomyResolution(parent_category="ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", leaf_category="Συσκευές Κουζίνας", sub_category="Βραστήρες", cta_url="https://example.com")
    row, _, _ = build_row(cli=cli, parsed=parsed, taxonomy=taxonomy, schema_match=SchemaMatchResult())
    assert row["price"] == "0"


def test_skroutz_parser_and_deterministic_fields_cover_supported_families() -> None:
    parser = SkroutzProductParser()
    resolver = TaxonomyResolver()

    expected = {
        "344317": {
            "name": "Tefal CM5S1DE – Καφετιέρα Φίλτρου 1000W 1,25Lt 10-15 Φλιτζάνια",
            "meta_title": "Tefal CM5S1DE Καφετιέρα Φίλτρου 1000W 1,25Lt | eTranoulis",
            "seo_keyword": "tefal-cm5s1de-kafetiera-filtrou-1000w-1-25lt",
        },
        "341490": {
            "name": "Estia 06-24567 – Βραστήρας 1,7Lt 2200W Λευκό Ματ",
            "meta_title": "Estia 06-24567 Βραστήρας 1,7Lt 2200W Λευκό Ματ | eTranoulis",
            "seo_keyword": "estia-06-24567-vrastiras-1-7lt-2200w-luminus-mat",
        },
        "307497": {
            "name": "Fancy 0013 – Επιτραπέζια Εστία 2 Εστιών 2450W Εμαγιέ",
            "meta_title": "Fancy 0013 Επιτραπέζια Εστία 2 Εστιών 2450W | eTranoulis",
            "seo_keyword": "fancy-0013-epitrapezia-estia-2-esties-2450w-emagie",
        },
    }

    for model, sample in ((model, SAMPLES[model]) for model in expected):
        parsed = parser.parse((FIXTURES_ROOT / f"{model}.html").read_text(encoding="utf-8"), sample["url"])
        taxonomy, _ = resolver.resolve(parsed.source.breadcrumbs, parsed.source.canonical_url or sample["url"], parsed.source.name, parsed.source.key_specs, parsed.source.spec_sections)
        deterministic = build_row(
            cli=make_cli(model),
            parsed=parsed,
            taxonomy=taxonomy,
            schema_match=SchemaMatchResult(),
        )[1]["deterministic_product"]
        assert parsed.source.page_type == "product"
        assert deterministic["name"] == expected[model]["name"]
        assert deterministic["meta_title"] == expected[model]["meta_title"]
        assert deterministic["seo_keyword"] == expected[model]["seo_keyword"]


def test_prepare_and_render_workflow_with_skroutz_fixtures(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    install_fixture_fetcher(monkeypatch)
    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")
    copy_baseline_products(tmp_path / "products")

    expected_match_fields = {"mpn", "name", "meta_title", "seo_keyword", "price", "category"}

    for model in SAMPLES:
        prepare_result = prepare_workflow(make_cli(model))
        source_payload = json.loads((prepare_result["scrape_dir"] / f"{model}.source.json").read_text(encoding="utf-8"))
        assert source_payload["source_name"] == "skroutz"
        assert len(source_payload["gallery_images"]) == SAMPLES[model]["photos"]
        if SAMPLES[model]["sections"] > 0:
            assert [item["local_filename"] for item in source_payload["besco_images"]] == [
                f"besco{index}.jpg" for index in range(1, SAMPLES[model]["sections"] + 1)
            ]
            report = json.loads((prepare_result["scrape_dir"] / f"{model}.report.json").read_text(encoding="utf-8"))
            assert report["sections_extracted"] == SAMPLES[model]["sections"]
            assert report["section_extraction_window"]["start_anchor"] == "Περιγραφή"
            assert report["section_extraction_window"]["stop_anchor"] == "Κατασκευαστής"
            assert len(report["section_image_urls_resolved"]) == SAMPLES[model]["sections"]

        llm_output_path = prepare_result["model_root"] / "llm_output.json"
        llm_output_path.write_text(json.dumps(build_llm_payload_from_baseline(PRODUCTS_ROOT / f"{model}.csv"), ensure_ascii=False, indent=2), encoding="utf-8")

        render_result = render_workflow(model)
        candidate_row = read_csv_row(render_result["candidate_csv_path"])
        baseline_row = read_csv_row(PRODUCTS_ROOT / f"{model}.csv")
        validation = render_result["validation_report"]

        assert validation["ok"] is True
        assert validation["summary"]["missing"] == 0
        for field in expected_match_fields:
            assert candidate_row[field] == baseline_row[field]
            assert validation["field_health"][field]["status"] == "match"
