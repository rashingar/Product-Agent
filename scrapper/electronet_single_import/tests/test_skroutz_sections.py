import csv
import json
from pathlib import Path

from bs4 import BeautifulSoup

from electronet_single_import.models import CLIInput, FetchResult
from electronet_single_import.skroutz_sections import extract_skroutz_section_window, is_placeholder_image_url, resolve_skroutz_section_image_url
from electronet_single_import.workflow import prepare_workflow, render_workflow

REPO_ROOT = Path(r"c:\Users\user\Documents\VS_Projects\tranoulis\Product-Agent")
FIXTURES_ROOT = REPO_ROOT / "scrapper" / "electronet_single_import" / "tests" / "fixtures" / "skroutz"
PRODUCTS_ROOT = REPO_ROOT / "products"
JPEG_BYTES = b"\xff\xd8\xff\xdb\x00C\x00" + (b"\x08" * 64) + b"\xff\xd9"
SAMPLE = {
    "model": "143481",
    "url": "https://www.skroutz.gr/s/61800471/tcl-q65h-soundbar-5-1-bluetooth-hdmi-kai-wi-fi-me-asyrmato-subwoofer-mayro.html",
    "photos": 8,
    "sections": 9,
    "skroutz_status": 1,
    "boxnow": 0,
    "price": "269",
}
EXPECTED_TITLES = [
    "Καλός ήχος από όλες τις κατευθύνσεις",
    "Ευρύτερο ηχητικό πεδίο, καθαρότερος ήχος",
    "Προσαρμοσμένο τουίτερ:",
    "Ενισχυμένη Κόρνα 60°*:",
    "Ισορροπημένη βελτιστοποίηση, ευρύτερο ηχητικό πεδίο",
    "Τρισδιάστατο πραγματικό surround 360°, βυθιστείτε στο περιεχόμενο",
    "Υψηλή πιστότητα, συγκινητικές καρδιές.",
    "Καθαρά φωνητικά, καθηλωτικοί διάλογοι",
    "Διαφανείς υψηλές συχνότητες, μαγευτική μουσική",
]


def read_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.DictReader(handle))


def build_llm_payload_from_baseline(path: Path) -> dict[str, object]:
    row = read_csv_row(path)
    soup = BeautifulSoup(row["description"], "lxml")
    intro_span = soup.select_one("p span")
    cta = soup.select_one("a")
    return {
        "product": {
            "meta_description": row["meta_description"],
            "meta_keywords": [item.strip() for item in row["meta_keyword"].split(",") if item.strip()],
        },
        "presentation": {
            "intro_html": intro_span.decode_contents().strip() if intro_span else "",
            "cta_text": cta.get_text(" ", strip=True) if cta else "",
            "sections": [
                {
                    "title": section.select_one(".etr-text h2").get_text(" ", strip=True),
                    "body_html": section.select_one(".etr-text p span").decode_contents().strip(),
                }
                for section in soup.select("div.etr-sec, div.etr-sec.rev")
                if section.select_one(".etr-text h2") is not None and section.select_one(".etr-text p span") is not None
            ],
        },
    }


def install_143481_fixture_fetcher(monkeypatch) -> None:
    from electronet_single_import import fetcher

    def fake_fetch_httpx(self, url: str):
        raise fetcher.FetchError(f"httpx disabled for test: {url}")

    def fake_fetch_playwright(self, url: str):
        html = (FIXTURES_ROOT / "143481.html").read_text(encoding="utf-8")
        return FetchResult(url=url, final_url=url, html=html, status_code=200, method="playwright", fallback_used=True, response_headers={})

    def fake_fetch_binary(self, url: str):
        return JPEG_BYTES, "image/jpeg"

    def fake_extract_skroutz_section_image_records(self, url: str):
        return json.loads((FIXTURES_ROOT / "143481.rendered_sections.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_httpx", fake_fetch_httpx)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_playwright", fake_fetch_playwright)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "fetch_binary", fake_fetch_binary)
    monkeypatch.setattr(fetcher.ElectronetFetcher, "extract_skroutz_section_image_records", fake_extract_skroutz_section_image_records)


def test_143481_html_fixture_resolves_9_sections_in_stable_order() -> None:
    html = (FIXTURES_ROOT / "143481.html").read_text(encoding="utf-8")
    extracted = extract_skroutz_section_window(html, SAMPLE["url"])

    assert extracted["window"]["start_anchor"] == "Περιγραφή"
    assert extracted["window"]["stop_anchor"] == "Κατασκευαστής"
    assert extracted["window"]["duplicate_signatures_skipped"] == 1
    assert [section["title"] for section in extracted["sections"]] == EXPECTED_TITLES
    assert len(extracted["sections"]) == 9
    assert "Χρυσή γωνία 60°" in extracted["sections"][3]["paragraph"]
    assert "Εξαιρετικά υψηλός ρυθμός ανάκλασης υπερήχων" in extracted["sections"][3]["paragraph"]
    assert extracted["sections"][0]["image_candidates"][0].endswith("transparent.gif")


def test_placeholder_urls_are_rejected_for_resolved_section_images() -> None:
    rendered = json.loads((FIXTURES_ROOT / "143481.rendered_sections.json").read_text(encoding="utf-8"))
    lazy_attr = rendered["sections"][0]["image_record"]["lazy_attrs"]["data-lazy-media-src-value"]
    record = {
        "currentSrc": "",
        "img_attrs": {"src": "//www.skroutz.gr/assets/transparent.gif"},
        "lazy_attrs": {"data-lazy-media-src-value": lazy_attr},
        "ancestor_data_attrs": {},
        "source_srcsets": [],
    }

    resolved = resolve_skroutz_section_image_url(record, base_url=SAMPLE["url"])
    assert is_placeholder_image_url(record["img_attrs"]["src"]) is True
    assert is_placeholder_image_url(resolved) is False
    assert resolved.endswith(".png")
    assert all(is_placeholder_image_url(section["resolved_image_url"]) is False for section in rendered["sections"])


def test_143481_rendered_description_preserves_locked_wrappers(tmp_path: Path, monkeypatch) -> None:
    from electronet_single_import import workflow

    install_143481_fixture_fetcher(monkeypatch)
    monkeypatch.setattr(workflow, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(workflow, "PRODUCTS_ROOT", tmp_path / "products")
    (tmp_path / "products").mkdir(parents=True, exist_ok=True)
    (tmp_path / "products" / "143481.csv").write_text((PRODUCTS_ROOT / "143481.csv").read_text(encoding="utf-8-sig"), encoding="utf-8")

    cli = CLIInput(
        model=SAMPLE["model"],
        url=SAMPLE["url"],
        photos=SAMPLE["photos"],
        sections=SAMPLE["sections"],
        skroutz_status=SAMPLE["skroutz_status"],
        boxnow=SAMPLE["boxnow"],
        price=SAMPLE["price"],
        out="unused",
    )
    prepare_result = prepare_workflow(cli)
    llm_output_path = prepare_result["model_root"] / "llm_output.json"
    llm_output_path.write_text(
        json.dumps(build_llm_payload_from_baseline(PRODUCTS_ROOT / "143481.csv"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    render_result = render_workflow("143481")
    description = render_result["description_path"].read_text(encoding="utf-8")
    soup = BeautifulSoup(description, "lxml")
    section_nodes = soup.select("div.etr-sec, div.etr-sec.rev")
    besco_dir = prepare_result["scrape_dir"] / "bescos"

    assert description.count('class="etr-sec"') == 5
    assert description.count('class="etr-sec rev"') == 4
    assert description.count("<!-- SECTION ") == 9
    assert len(section_nodes) == 9
    assert sorted(path.name for path in besco_dir.glob("*.jpg")) == [f"besco{index}.jpg" for index in range(1, 10)]

    for index, section in enumerate(section_nodes, start=1):
        expected_class = ["etr-sec", "rev"] if index % 2 == 0 else ["etr-sec"]
        assert section.get("class") == expected_class
        direct_children = [child for child in section.find_all(recursive=False)]
        assert [child.get("class") for child in direct_children] == [["etr-text"], ["etr-img"]]
        image = section.select_one(".etr-img img")
        assert image is not None
        assert image.get("src", "").endswith(f"/143481/besco{index}.jpg")
        if index % 2 == 0:
            assert image.get("style") == "display:block; margin-left:auto; margin-right:0;"
        else:
            assert image.get("style") is None
