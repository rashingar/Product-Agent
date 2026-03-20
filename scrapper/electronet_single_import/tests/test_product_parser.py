from electronet_single_import.parser_product import ElectronetProductParser
from electronet_single_import.schema_matcher import SchemaMatcher

HTML = """
<html>
  <head>
    <title>Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο - Electronet.gr</title>
    <link rel="canonical" href="https://www.electronet.gr/exoplismos-spitioy/skoypisma/skoypes-stick/skoypa-stick-rowenta-x-force-flex-960-rh2099-kokkino" />
  </head>
  <body>
    <nav class="breadcrumb"><a>Αρχική</a><a>Εξοπλισμός Σπιτιού</a><a>Σκούπισμα</a><a>Σκούπες Stick</a></nav>
    <div>ΚΩΔΙΚΟΣ ΠΡΟΪΟΝΤΟΣ: 343700</div>
    <div>Σύγκριση</div>
    <div>Rowenta</div>
    <h1>Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο</h1>
    <div>249,00 €</div>
    <div>12 άτοκες δόσεις</div>
    <div>Απολαύστε ισχυρή απόδοση και άνεση στον καθαρισμό με τη Rowenta RH2099.</div>
    <div>Τάση Volt</div><div>18,5</div>
    <div>Χρόνος Λειτουργίας σε Λεπτά</div><div>45</div>
    <div>Παράδοση</div><div>Διαθέσιμο για παράδοση στον χώρο σου</div>
    <div>Παραλαβή</div><div>Επιλέξτε κατάστημα για να δείτε τη διαθεσιμότητα</div>
    <img src="/image/catalog/products/343700/main.jpg" alt="Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο" />
    <img src="/image/catalog/products/343700/2.jpg" alt="Σκούπα Stick Rowenta X-Force Flex 9.60 RH2099 Κόκκινο πλευρικά" />
    <h2>Παρουσίαση Προϊόντος</h2>
    <h3>ΕΞΑΙΡΕΤΙΚΑ ΑΠΟΤΕΛΕΣΜΑΤΙΚΟ ΚΑΘΑΡΙΣΜΑ</h3>
    <p>Εξαιρετικά αποτελεσματικό καθάρισμα σε όλα τα δάπεδα.</p>
    <h3>ΔΙΠΛΑΣΙΑ ΑΥΤΟΝΟΜΙΑ</h3>
    <p>Δύο αφαιρούμενες μπαταρίες για καθαρισμό χωρίς διακοπές.</p>
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
  </body>
</html>
"""


def test_product_parser_extracts_visible_code_and_specs() -> None:
    matcher = SchemaMatcher()
    parser = ElectronetProductParser(known_section_titles=matcher.known_section_titles)
    parsed = parser.parse(HTML, "https://www.electronet.gr/exoplismos-spitioy/skoypisma/skoypes-stick/skoypa-stick-rowenta-x-force-flex-960-rh2099-kokkino")
    assert parsed.source.product_code == "343700"
    assert parsed.source.brand == "Rowenta"
    assert parsed.source.name.startswith("Σκούπα Stick Rowenta")
    assert parsed.source.price_value == 249.0
    assert parsed.source.breadcrumbs[-1] == "Σκούπες Stick"
    assert len(parsed.source.spec_sections) == 2
    assert parsed.source.spec_sections[0].items[0].label == "Τύπος Μπαταρίας"
