from pipeline.parser_product import ElectronetProductParser
from pipeline.schema_matcher import SchemaMatcher

HTML = """
<html>
  <head>
    <title>Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο - Electronet.gr</title>
    <link rel="canonical" href="https://www.electronet.gr/exoplismos-spitioy/skoypisma/skoypes-stick/skoypa-stick-rowenta-x-force-flex-960-rh2099-kokkino" />
  </head>
  <body>
    <nav class="breadcrumb"><a>Αρχική</a><a>Εξοπλισμός Σπιτιού</a><a>Σκούπισμα</a><a>Σκούπες Stick</a></nav>
    <div id="cscp-sku">343700</div>
    <article class="product-page available" data-sku="343700">
      <div id="product-brand-logo"><a href="/brand/rowenta">Rowenta</a></div>
      <h1 class="product-title">Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο</h1>
      <div id="product-price" data-price="249">
        <span class="price">249,00 €</span>
        <ul><li class="prod-tags-freeinstallments">12 άτοκες δόσεις</li></ul>
      </div>
      <div class="product-desc"><p>Απολαύστε ισχυρή απόδοση και άνεση στον καθαρισμό με τη Rowenta RH2099.</p></div>
      <div id="product-main-attributes">
        <div class="product-main-attribute"><span class="my-label">Τάση Volt</span><span class="my-value">18,5</span></div>
        <div class="product-main-attribute"><span class="my-label">Χρόνος Λειτουργίας σε Λεπτά</span><span class="my-value">45</span></div>
      </div>
      <div class="availability">
        <div><div class="cpa-label">Παράδοση</div><div>Διαθέσιμο για παράδοση στον χώρο σου</div></div>
        <div><div class="cpa-label">Παραλαβή</div><div>Επιλέξτε κατάστημα για να δείτε τη διαθεσιμότητα</div></div>
      </div>
      <img class="lightbox" src="/image/catalog/products/343700/main.jpg" alt="Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο" />
      <img class="lightbox" src="/image/catalog/products/343700/2.jpg" alt="Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο πλευρικά" />
      <h2>Παρουσίαση Προϊόντος</h2>
      <div class="ck-text inline"><h3>ΕΞΑΙΡΕΤΙΚΑ ΑΠΟΤΕΛΕΣΜΑΤΙΚΟ ΚΑΘΑΡΙΣΜΑ</h3><p>Εξαιρετικά αποτελεσματικό καθάρισμα σε όλα τα δάπεδα.</p></div>
      <div class="ck-text inline"><h3>ΔΙΠΛΑΣΙΑ ΑΥΤΟΝΟΜΙΑ</h3><p>Δύο αφαιρούμενες μπαταρίες για καθαρισμό χωρίς διακοπές.</p></div>
      <h2>Τεχνικά Χαρακτηριστικά</h2>
      <h3>Επισκόπηση Προϊόντος</h3>
      <table>
        <tr><th>Τύπος Μπαταρίας</th><td>Li-Ion</td></tr>
        <tr><th>Τάση Volt</th><td>18,5</td></tr>
      </table>
      <h3>Γενικά Χαρακτηριστικά</h3>
      <table>
        <tr><th>Χρώμα</th><td>Κόκκινο</td></tr>
      </table>
    </article>
  </body>
</html>
"""


def test_product_parser_extracts_visible_code_and_specs() -> None:
    matcher = SchemaMatcher()
    parser = ElectronetProductParser(known_section_titles=matcher.known_section_titles)
    parsed = parser.parse(HTML, "https://www.electronet.gr/exoplismos-spitioy/skoypisma/skoypes-stick/skoypa-stick-rowenta-x-force-flex-960-rh2099-kokkino")
    assert parsed.source.product_code == "343700"
    assert parsed.source.brand == "Rowenta"
    assert parsed.source.mpn == "RH2099"
    assert parsed.source.name.startswith("Σκούπα Stick Rowenta")
    assert parsed.source.price_value == 249.0
    assert parsed.source.breadcrumbs[-1] == "Σκούπες Stick"
    assert len(parsed.source.spec_sections) == 2
    assert parsed.source.spec_sections[0].items[0].label == "Τύπος Μπαταρίας"
    assert parsed.field_diagnostics["brand"].confidence > 0.0
    assert parsed.field_diagnostics["brand"].selector_trace
    assert parsed.field_diagnostics["spec_sections"].value_present is True
    assert parsed.field_diagnostics["spec_sections"].selector_trace


def test_product_parser_preserves_video_block_in_presentation_source_html() -> None:
    matcher = SchemaMatcher()
    parser = ElectronetProductParser(known_section_titles=matcher.known_section_titles)
    html = """
    <html>
      <body>
        <article class="product-page available">
          <div id="product-presentation">
            <h2>Παρουσίαση Προϊόντος</h2>
            <div class="ck-text whole">
              <h2>Video Title</h2>
              <video autoplay="" loop="" muted="" playsinline="" style="width: 70%;"><source src="/media/demo.mp4" type="video/mp4" /></video>
            </div>
            <div class="ck-text inline"><h2>Section One</h2><p>Paragraph one.</p></div>
            <div class="ck-text inline"><h2>Section Two</h2><ul><li>Bullet one.</li></ul></div>
          </div>
          <div id="product-details"><div class="prop-group-wrapper"><h3>Επισκόπηση Προϊόντος</h3></div></div>
          <div id="product-brand-logo"><a href="/brand/rowenta">Rowenta</a></div>
          <h1 class="product-title">Rowenta Example RH2099</h1>
          <div id="cscp-sku">343700</div>
          <div id="product-price"><span class="price">249,00 €</span></div>
        </article>
      </body>
    </html>
    """

    parsed = parser.parse(html, "https://www.electronet.gr/example")

    assert '<video autoplay="" loop="" muted="" playsinline="" style="width: 70%;"><source src="/media/demo.mp4" type="video/mp4"/></video>' in parsed.source.presentation_source_html
    assert parsed.field_diagnostics["presentation_blocks"].value_present is True
    assert parsed.field_diagnostics["presentation_blocks"].value_preview == "2"

