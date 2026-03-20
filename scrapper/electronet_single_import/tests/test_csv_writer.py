from pathlib import Path

from electronet_single_import.csv_writer import write_csv_row
from electronet_single_import.html_builders import build_characteristics_html, build_description_html, extract_presentation_blocks
from electronet_single_import.models import SpecItem, SpecSection



def test_csv_header_order_preserved_from_template(tmp_path: Path) -> None:
    template = tmp_path / "template.csv"
    template.write_text("b,a,c\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    headers, ordered = write_csv_row({"a": "1", "b": "2", "c": "3"}, out, template)
    assert headers == ["b", "a", "c"]
    assert ordered == {"b": "2", "a": "1", "c": "3"}
    assert out.read_text(encoding="utf-8").splitlines()[0] == "b,a,c"



def test_characteristics_html_and_safe_blank_description() -> None:
    html = build_characteristics_html([SpecSection(section="Γενικά Χαρακτηριστικά", items=[SpecItem("Χρώμα", "Κόκκινο")])])
    assert "<h3>Γενικά Χαρακτηριστικά</h3>" in html
    description, warnings = build_description_html(
        product_name="Σκούπα",
        hero_summary="",
        presentation_source_html="",
        presentation_source_text="",
        model="343700",
        sections_requested=3,
        cta_url="https://www.etranoulis.gr/example",
        cta_label="Σκούπες Stick",
    )
    assert description == ""
    assert "description_not_built_from_source" in warnings


def test_presentation_blocks_extract_images_and_description_uses_downloaded_bescos() -> None:
    presentation_html = """
    <h3>Section One</h3>
    <p>Paragraph one.</p>
    <img src="/image/catalog/products/343700/section-one.webp" />
    <h3>Section Two</h3>
    <p>Paragraph two.</p>
    """

    blocks = extract_presentation_blocks(
        presentation_source_html=presentation_html,
        presentation_source_text="",
        base_url="https://www.electronet.gr/product/example",
    )

    assert blocks[0]["image_url"] == "https://www.electronet.gr/image/catalog/products/343700/section-one.webp"

    description, warnings = build_description_html(
        product_name="Example Product",
        hero_summary="Intro text",
        presentation_source_html=presentation_html,
        presentation_source_text="",
        model="343700",
        sections_requested=2,
        cta_url="https://www.etranoulis.gr/example",
        cta_label="Category",
        besco_filenames_by_section={1: "besco1.webp"},
    )

    assert warnings == []
    assert "01_bescos/343700/besco1.webp" in description
    assert "01_bescos/343700/besco2.jpg" not in description
