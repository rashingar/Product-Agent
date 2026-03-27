from electronet_single_import.manufacturer_enrichment import _parse_tefal_shop_product_html
from electronet_single_import.normalize import normalize_for_match


def test_parse_tefal_shop_product_html_extracts_spec_rows() -> None:
    html = """
    <div data-tab-content="about-the-product">
      <div class="u-flex u-justify-between u-items-center u-py-16 u-border-b u-border-light-grey u-gap-4">
        <span class="t-text-medium u-text-dark-grey u-w-1/2">Τύπος βούρτσας</span>
        <div class="t-text u-text-dark-grey u-text-right u-w-1/2">Βούρτσα Animal Turbo</div>
      </div>
      <div class="u-flex u-justify-between u-items-center u-py-16 u-border-b u-border-light-grey u-gap-4">
        <span class="t-text-medium u-text-dark-grey u-w-1/2">Χωρητικότητα δοχείου σκόνης</span>
        <div class="t-text u-text-dark-grey u-text-right u-w-1/2">0.26 L</div>
      </div>
    </div>
    """

    sections = _parse_tefal_shop_product_html(html)
    flattened = {
        normalize_for_match(item.label): item.value
        for section in sections
        for item in section.items
    }

    assert len(sections) == 1
    assert sections[0].section == "Χαρακτηριστικά Κατασκευαστή"
    assert flattened[normalize_for_match("Τύπος βούρτσας")] == "Βούρτσα Animal Turbo"
    assert flattened[normalize_for_match("Χωρητικότητα δοχείου σκόνης")] == "0.26 L"
