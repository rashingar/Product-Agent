from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from .models import FieldDiagnostic, GalleryImage, ParsedProduct, SelectorTraceEntry, SourceProductData, SpecItem, SpecSection
from .normalize import clean_breadcrumbs, dedupe_urls_preserve_order, make_absolute_url, normalize_for_match, normalize_whitespace, parse_euro_price, safe_text
from .utils import utcnow_iso

INTERSTITIAL_MARKERS = {"just a moment", "enable javascript and cookies", "περιμένετε"}
MODEL_TOKEN_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9][A-Z0-9._/-]{2,}$")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?")
CUPS_RE = re.compile(r"(\d+(?:\s*-\s*\d+)?)\s*(?:φλιτζ|cups?)", re.IGNORECASE)
CAPACITY_LT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*lt", re.IGNORECASE)
DIMENSIONS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[xX×]\s*(\d+(?:[.,]\d+)?)(?:\s*[xX×]\s*(\d+(?:[.,]\d+)?))?")
WEIGHT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\b", re.IGNORECASE)
WARRANTY_RE = re.compile(r"(\d+)\s*(?:έτη|έτος|χρόνια|χρονα|years?)", re.IGNORECASE)
TITLE_CODE_SUFFIX_RE = re.compile(r"\s+Κωδικός:\s*[A-Z0-9.-]+\s*$", re.IGNORECASE)
SUMMARY_PAIR_RE = re.compile(r"([^:]{2,80}?):\s*(.+?)(?=(?:\s+[A-Za-zΑ-ΩΆ-Ώα-ωά-ώ][^:]{1,40}:)|$)")

SKROUTZ_FAMILIES: dict[str, dict[str, Any]] = {
    "soundbar": {
        "category_labels": {"Soundbar", "Soundbars", "Sound Bars"},
        "breadcrumbs": ["Αρχική", "ΕΙΚΟΝΑ & ΗΧΟΣ", "Audio Systems", "Sound Bars"],
        "sections": [],
    },
    "coffee_filter": {
        "category_labels": {"Καφετιέρες Φίλτρου"},
        "breadcrumbs": ["Αρχική", "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", "Καφές-Ροφήματα-Χυμοί", "Καφετιέρες Φίλτρου"],
        "sections": [
            ("Επισκόπηση Προϊόντος", ["Χωρητικότητα σε Φλυτζάνια", "Υλικό Κανάτας", "Ισχύς σε Watts", "Χωρητικότητα Δοχείου Νερού σε Λίτρα", "Ένδειξη Στάθμης Νερού", "Αποσπώμενο Δοχείο Νερού", "Θερμαινόμενη Βάση", "Ενδεικτική Λυχνία Λειτουργίας", "Ηχητικό Σήμα Ειδοποίησης", "Αποθήκευση Καλωδίου"]),
            ("Ειδικές Λειτουργίες", ["Διακοπή Σταξίματος", "Λειτουργία Aroma", "Αυτόματη Διακοπή Λειτουργίας", "Χρονοδιακόπτης Λειτουργίας"]),
            ("Γενικά Χαρακτηριστικά", ["Χρώμα", "Βάρος Συσκευής σε Κιλά", "Διαστάσεις Συσκευής σε Εκατοστά. (Υ χ Π χ Β", "Εγγύηση Κατασκευαστή"]),
        ],
    },
    "kettle": {
        "category_labels": {"Βραστήρες"},
        "breadcrumbs": ["Αρχική", "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", "Συσκευές Κουζίνας", "Βραστήρες"],
        "sections": [
            ("Επισκόπηση Προϊόντος", ["Χωρητικότητα σε Λίτρα", "Ισχύς σε Watts", "Αποσπώμενη Βάση", "Βάση 360 Μοιρών", "Φίλτρο Νερού", "Άνοιγμα του Καπακιού με το Πάτημα ενός Κουμπιού", "Καλυμμένη Αντίσταση", "Υλικό Κατασκευής", "Αποθήκευση Καλωδίου"]),
            ("Λειτουργίες - Ενδείξεις", ["Ένδειξη Στάθμης Νερού", "Ένδειξη Λειτουργίας", "Ηχητικό Σήμα Ειδοποίησης", "Επιλογές Θερμοκρασίας Βρασμού", "Λειτουργία Διατήρησης Θερμοκρασίας", "Αυτόματος Τερματισμός Λειτουργίας", "Προστασία από Βρασμό Χωρίς Νερό"]),
            ("Γενικά Χαρακτηριστικά", ["Χρώμα", "Βάρος Συσκευής σε Κιλά", "Διαστάσεις Συσκευής σε Εκατοστά. (Υ χ Π χ Β", "Εγγύηση Κατασκευαστή"]),
        ],
    },
    "tabletop_hob": {
        "category_labels": {"Επιτραπέζιες Εστίες"},
        "breadcrumbs": ["Αρχική", "ΟΙΚΙΑΚΟΣ ΕΞΟΠΛΙΣΜΟΣ", "Μικροί Μάγειρες", "Εστίες"],
        "sections": [("Χαρακτηριστικά Μοντέλου", ["Κατασκευαστής", "Μοντέλο"]), ("Γενικά Χαρακτηριστικά", ["Εστία"]), ("Διαστάσεις", ["Πλάτος", "Βάθος"])],
    },
}


class SkroutzProductParser:
    def parse(self, html: str, url: str, fallback_used: bool = False) -> ParsedProduct:
        soup = BeautifulSoup(html, "lxml")
        if self._is_interstitial(soup):
            source = SourceProductData(source_name="skroutz", page_type="interstitial", url=url, canonical_url=url, raw_html_path="", scraped_at=utcnow_iso(), fallback_used=fallback_used)
            return ParsedProduct(source=source, missing_fields=["name", "brand", "breadcrumbs", "gallery_images", "spec_sections"], warnings=["skroutz_interstitial_detected"], critical_missing=["name", "breadcrumbs", "gallery_images", "spec_sections"])

        jsonld = self._parse_product_jsonld(soup)
        provenance: dict[str, str] = {}
        diagnostics: dict[str, FieldDiagnostic] = {}
        warnings: list[str] = []
        canonical_url = self._extract_canonical_url(soup, url)

        title, title_source, title_trace = self._extract_title(soup, jsonld)
        provenance["name"] = title_source
        diagnostics["name"] = self._make_diagnostic(title, title_source, 0.99 if title else 0.0, title_trace)
        category_hint, category_source, category_trace = self._extract_category_hint(soup, jsonld)
        family = self._resolve_family(category_hint, title)
        if not family:
            warnings.append("unsupported_skroutz_category")

        breadcrumbs = clean_breadcrumbs(SKROUTZ_FAMILIES.get(family, {}).get("breadcrumbs", []))
        provenance["breadcrumbs"] = category_source if breadcrumbs else "missing"
        diagnostics["breadcrumbs"] = self._make_diagnostic(breadcrumbs, provenance["breadcrumbs"], 0.95 if breadcrumbs else 0.0, category_trace)

        merchant_titles = self._extract_merchant_titles(soup)
        brand, brand_source, brand_trace = self._extract_brand(soup, jsonld, title, merchant_titles)
        provenance["brand"] = brand_source
        diagnostics["brand"] = self._make_diagnostic(brand, brand_source, 0.96 if brand else 0.0, brand_trace)

        product_code, code_source, code_trace = self._extract_page_sku(soup, jsonld, canonical_url)
        provenance["product_code"] = code_source
        diagnostics["product_code"] = self._make_diagnostic(product_code, code_source, 0.95 if product_code else 0.0, code_trace)

        summary_html, hero_summary, summary_source, summary_trace, summary_pairs = self._extract_summary_block(soup)
        provenance["hero_summary"] = summary_source
        diagnostics["hero_summary"] = self._make_diagnostic(hero_summary, summary_source, 0.88 if hero_summary else 0.0, summary_trace)

        _raw_sections, raw_pairs, spec_source, spec_trace = self._extract_raw_specs(soup)
        if raw_pairs and summary_pairs:
            warnings.append("merchant_summary_and_structured_characteristics_present")

        mpn, mpn_source, mpn_trace = self._extract_mpn(soup, jsonld, title, brand, product_code, merchant_titles)
        provenance["mpn"] = mpn_source
        diagnostics["mpn"] = self._make_diagnostic(mpn, mpn_source, 0.92 if mpn else 0.0, mpn_trace)

        price_text, price_value, price_source, price_trace = self._extract_price(soup, jsonld)
        provenance["price"] = price_source
        diagnostics["price"] = self._make_diagnostic(price_text or price_value, price_source, 0.95 if price_text or price_value else 0.0, price_trace)

        canonical_sections = self._build_canonical_sections(family=family, brand=brand, mpn=mpn, title=title, hero_summary=hero_summary, raw_pairs=raw_pairs, summary_pairs=summary_pairs, merchant_titles=merchant_titles)
        provenance["spec_sections"] = spec_source
        diagnostics["spec_sections"] = self._make_diagnostic(canonical_sections, spec_source, 0.92 if canonical_sections else 0.0, spec_trace)
        key_specs = self._build_key_specs(family, canonical_sections, raw_pairs, summary_pairs)
        provenance["key_specs"] = "canonical_from_specs" if key_specs else "missing"
        diagnostics["key_specs"] = self._make_diagnostic(key_specs, provenance["key_specs"], 0.9 if key_specs else 0.0, [])
        gallery_images, gallery_source, gallery_trace = self._extract_gallery_images(soup, jsonld, canonical_url, title)
        provenance["gallery_images"] = gallery_source
        diagnostics["gallery_images"] = self._make_diagnostic(gallery_images, gallery_source, 0.95 if gallery_images else 0.0, gallery_trace)

        source = SourceProductData(source_name="skroutz", page_type="product" if family else "unsupported_family", url=url, canonical_url=canonical_url, breadcrumbs=breadcrumbs, product_code=product_code, brand=brand, name=title, hero_summary=hero_summary, price_text=price_text, price_value=price_value, gallery_images=gallery_images, key_specs=key_specs, spec_sections=canonical_sections, presentation_source_html=summary_html, presentation_source_text=hero_summary, raw_html_path="", scraped_at=utcnow_iso(), fallback_used=fallback_used, mpn=mpn)
        missing_fields = self._collect_missing_fields(source)
        critical_missing = self._collect_critical_missing(source, family)
        return ParsedProduct(source=source, provenance=provenance, field_diagnostics=diagnostics, missing_fields=missing_fields, warnings=warnings, critical_missing=critical_missing)

    def _is_interstitial(self, soup: BeautifulSoup) -> bool:
        title = normalize_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
        body_text = normalize_for_match(safe_text(soup.body)[:1000])
        haystack = normalize_for_match(f"{title} {body_text}")
        return any(marker in haystack for marker in INTERSTITIAL_MARKERS)

    def _parse_product_jsonld(self, soup: BeautifulSoup) -> dict[str, Any]:
        node = soup.select_one("#product-schema") or soup.select_one("script[type='application/ld+json']")
        if not node:
            return {}
        raw = node.string or node.get_text(" ", strip=True)
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _extract_canonical_url(self, soup: BeautifulSoup, fallback_url: str) -> str:
        node = soup.select_one("link[rel='canonical']")
        href = node.get("href") if node else ""
        return make_absolute_url(href, fallback_url) if href else fallback_url

    def _extract_title(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> tuple[str, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        node = soup.select_one("div.sku-title h1.page-title")
        trace.append(self._trace("dom", "div.sku-title h1.page-title", [node] if node else [], node))
        if node:
            clone = BeautifulSoup(str(node), "lxml").select_one("h1")
            small = clone.select_one("small") if clone else None
            if small:
                small.decompose()
            title = self._clean_title(safe_text(clone))
            if title:
                return title, "dom:div.sku-title h1.page-title", trace
        for selector in ["meta[property='og:title']", "meta[name='twitter:title']", "title"]:
            node = soup.select_one(selector)
            trace.append(self._trace("dom", selector, [node] if node else [], node))
            if not node:
                continue
            value = normalize_whitespace(node.get("content") or safe_text(node))
            if selector == "title":
                value = value.split("|")[0].strip()
            value = self._clean_title(value)
            if value:
                return value, f"dom:{selector}", trace
        title = self._clean_title(normalize_whitespace(jsonld.get("name")))
        return (title, "jsonld:name", trace) if title else ("", "missing", trace)

    def _clean_title(self, title: str) -> str:
        cleaned = normalize_whitespace(title)
        if not cleaned:
            return ""
        return TITLE_CODE_SUFFIX_RE.sub("", cleaned).strip()

    def _extract_category_hint(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> tuple[str, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        node = soup.select_one("div.sku-title a.category-tag")
        trace.append(self._trace("dom", "div.sku-title a.category-tag", [node] if node else [], node))
        value = safe_text(node)
        if value:
            return value, "dom:div.sku-title a.category-tag", trace
        value = normalize_whitespace(jsonld.get("category"))
        return (value, "jsonld:category", trace) if value else ("", "missing", trace)

    def _resolve_family(self, category_hint: str, title: str) -> str | None:
        category_norm = normalize_for_match(category_hint)
        title_norm = normalize_for_match(title)
        for family, config in SKROUTZ_FAMILIES.items():
            labels = {normalize_for_match(label) for label in config["category_labels"]}
            if category_norm in labels:
                return family
            if family == "soundbar" and "soundbar" in title_norm:
                return family
            if family == "coffee_filter" and "καφετιερ" in title_norm and "φιλτρ" in title_norm:
                return family
            if family == "kettle" and "βραστηρ" in title_norm:
                return family
            if family == "tabletop_hob" and "εστια" in title_norm:
                return family
        return None

    def _extract_brand(self, soup: BeautifulSoup, jsonld: dict[str, Any], title: str, merchant_titles: list[str]) -> tuple[str, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        for selector in ["a.brand-page-link img", "a.brand-page-link span"]:
            node = soup.select_one(selector)
            trace.append(self._trace("dom", selector, [node] if node else [], node))
            if not node:
                continue
            value = normalize_whitespace(node.get("alt") if node.name == "img" else safe_text(node)).replace(" στο Skroutz", "").strip()
            if value:
                return value, f"dom:{selector}", trace
        brand = jsonld.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        value = normalize_whitespace(brand)
        if value:
            return value, "jsonld:brand", trace
        fallback = self._derive_brand_from_titles([title, *merchant_titles])
        return (fallback, "heuristic:title_brand", trace) if fallback else ("", "missing", trace)

    def _derive_brand_from_titles(self, texts: list[str]) -> str:
        for text in texts:
            tokens = normalize_whitespace(text).split()
            if tokens and not NUMERIC_RE.fullmatch(tokens[0]):
                return tokens[0].strip(" -–/|,.;:()[]{}")
        return ""

    def _extract_page_sku(self, soup: BeautifulSoup, jsonld: dict[str, Any], url: str) -> tuple[str, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        node = soup.select_one("h1 small.sku-code")
        trace.append(self._trace("dom", "h1 small.sku-code", [node] if node else [], node))
        if node:
            match = re.search(r"([A-Z0-9.-]{3,})$", safe_text(node), re.IGNORECASE)
            if match:
                return match.group(1), "dom:h1 small.sku-code", trace
        value = normalize_whitespace(jsonld.get("sku"))
        if value:
            return value, "jsonld:sku", trace
        match = re.search(r"/s/(\d+)/", url)
        return (match.group(1), "url:path_sku", trace) if match else ("", "missing", trace)

    def _extract_mpn(self, soup: BeautifulSoup, jsonld: dict[str, Any], title: str, brand: str, product_code: str, merchant_titles: list[str]) -> tuple[str, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        value = normalize_whitespace(jsonld.get("mpn"))
        if value:
            return value, "jsonld:mpn", trace
        node = soup.select_one("#specs dt:-soup-contains('Κωδικός Προϊόντος') + dd")
        trace.append(self._trace("dom", "#specs dt:-soup-contains('Κωδικός Προϊόντος') + dd", [node] if node else [], node))
        if node and safe_text(node):
            return safe_text(node), "dom:#specs dt+dd", trace
        if product_code and not product_code.isdigit():
            return product_code, "heuristic:page_code", trace
        best = self._best_model_token([title, *merchant_titles], brand)
        return (best, "heuristic:model_token", trace) if best else ("", "missing", trace)

    def _extract_price(self, soup: BeautifulSoup, jsonld: dict[str, Any]) -> tuple[str, float | None, str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        node = soup.select_one(".prices .final-price")
        trace.append(self._trace("dom", ".prices .final-price", [node] if node else [], node))
        if node:
            integer_part = safe_text(node.select_one(".integer-part"))
            decimal_part = safe_text(node.select_one(".decimal-part"))
            if integer_part and decimal_part:
                text = f"{integer_part},{decimal_part} €"
                try:
                    price = float(f"{integer_part}.{decimal_part}")
                except ValueError:
                    price = parse_euro_price(text)
                return text, price, "dom:.prices .final-price", trace
            text = safe_text(node)
            price = parse_euro_price(text)
            if price is not None:
                return text, price, "dom:.prices .final-price", trace
        offers = jsonld.get("offers") or {}
        price_value = offers.get("price")
        if price_value is not None:
            text = normalize_whitespace(str(price_value))
            try:
                numeric = float(str(price_value))
            except ValueError:
                numeric = parse_euro_price(text)
            return text, numeric, "jsonld:offers.price", trace
        return "", None, "missing", trace

    def _extract_summary_block(self, soup: BeautifulSoup) -> tuple[str, str, str, list[SelectorTraceEntry], list[tuple[str, str, str]]]:
        trace: list[SelectorTraceEntry] = []
        selectors = [".sku-description", "#description .simple-description", "div.summary .description.long", "div.summary .description.bullets"]
        for selector in selectors:
            node = soup.select_one(selector)
            trace.append(self._trace("dom", selector, [node] if node else [], node))
            if not node:
                continue
            segments = self._collect_summary_segments(node)
            pairs = self._extract_summary_pairs(node)
            supplemental = soup.select_one("div.summary .description.bullets")
            if supplemental is not None and supplemental is not node:
                for pair in self._extract_summary_pairs(supplemental):
                    if pair not in pairs:
                        pairs.append(pair)
            text = normalize_whitespace(" ".join(segments))
            if text or pairs:
                return str(node), text, f"dom:{selector}", trace, pairs
        return "", "", "missing", trace, []

    def _collect_summary_segments(self, node: Tag) -> list[str]:
        chunks: list[str] = []
        for body_text in node.select(".body-text"):
            text = safe_text(body_text)
            if text:
                chunks.append(text)
        if not chunks:
            for paragraph in node.find_all("p"):
                text = safe_text(paragraph)
                if text:
                    chunks.append(text)
        for item in node.find_all("li"):
            text = safe_text(item)
            if text and text not in chunks:
                chunks.append(text)
        if not chunks:
            text = safe_text(node)
            if text:
                chunks.append(text)
        return self._dedupe_preserve_order(chunks)

    def _extract_summary_pairs(self, node: Tag) -> list[tuple[str, str, str]]:
        pairs: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        chunks: list[str] = []
        for text_node in [*node.select(".body-text"), *node.find_all("li"), *node.find_all("p")]:
            text = safe_text(text_node)
            if text:
                chunks.append(text)
        for chunk in chunks:
            for label, value in self._scan_pairs(chunk):
                key = (normalize_for_match(label), normalize_for_match(value))
                if not key[0] or key in seen:
                    continue
                seen.add(key)
                pairs.append(("Σύνοψη", label, value))
        return pairs

    def _scan_pairs(self, text: str) -> list[tuple[str, str]]:
        normalized = normalize_whitespace(text)
        if not normalized or ":" not in normalized:
            return []
        pairs: list[tuple[str, str]] = []
        for label, value in SUMMARY_PAIR_RE.findall(normalized):
            clean_label = normalize_whitespace(label)
            clean_value = normalize_whitespace(value)
            if clean_label and clean_value:
                pairs.append((clean_label, clean_value))
        return pairs

    def _extract_raw_specs(self, soup: BeautifulSoup) -> tuple[list[SpecSection], list[tuple[str, str, str]], str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        containers = soup.select("#specs .spec-groups, #combined-specs-content .spec-groups")
        trace.append(self._trace("dom", "#specs .spec-groups", containers, containers[0] if containers else None))
        if not containers:
            return [], [], "missing", trace

        sections: list[SpecSection] = []
        flat_pairs: list[tuple[str, str, str]] = []
        seen_pairs: set[tuple[str, str, str]] = set()
        for container in containers:
            for detail in container.find_all("div", class_="spec-details", recursive=False):
                section_title = safe_text(detail.find("h3", recursive=False)) or "Γενικά"
                items: list[SpecItem] = []
                for block in detail.find_all("dl", recursive=False):
                    dt = block.find("dt", recursive=False)
                    dd = block.find("dd", recursive=False)
                    label = safe_text(dt)
                    value = safe_text(dd)
                    if not label or not value:
                        continue
                    pair_key = (section_title, label, value)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    items.append(SpecItem(label=label, value=value))
                    flat_pairs.append(pair_key)
                if items:
                    sections.append(SpecSection(section=section_title, items=items))
        return sections, flat_pairs, "dom:#specs .spec-groups", trace

    def _extract_gallery_images(self, soup: BeautifulSoup, jsonld: dict[str, Any], url: str, title: str) -> tuple[list[GalleryImage], str, list[SelectorTraceEntry]]:
        trace: list[SelectorTraceEntry] = []
        images = jsonld.get("image")
        urls: list[str] = []
        if isinstance(images, list):
            urls.extend(make_absolute_url(item, url) for item in images if item)
        elif isinstance(images, str) and images:
            urls.append(make_absolute_url(images, url))
        if urls:
            normalized = dedupe_urls_preserve_order(urls)
            return [GalleryImage(url=item, alt=title, position=index) for index, item in enumerate(normalized, start=1)], "jsonld:image", trace

        nodes = soup.select("img[data-modal-data], img[data-sku-page--gallery--swipe-gallery-target='image']")
        trace.append(self._trace("dom", "img[data-modal-data]", nodes, nodes[0] if nodes else None))
        for node in nodes:
            src = node.get("data-fallback-src") or node.get("data-src") or node.get("src") or ""
            if src:
                urls.append(make_absolute_url(src, url))
        normalized = dedupe_urls_preserve_order(urls)
        return [GalleryImage(url=item, alt=title, position=index) for index, item in enumerate(normalized, start=1)], "dom:img[data-modal-data]", trace

    def _extract_merchant_titles(self, soup: BeautifulSoup) -> list[str]:
        titles = [normalize_whitespace(node.get("title") or safe_text(node)) for node in soup.select("#prices .product-name[title], .selected-product-cards .product-name[title]")]
        return self._dedupe_preserve_order([title for title in titles if title])

    def _best_model_token(self, texts: list[str], brand: str) -> str:
        brand_norm = normalize_for_match(brand)
        best = ""
        best_score = 0
        for text in texts:
            for raw in normalize_whitespace(text).split():
                token = raw.strip(" -–/|,.;:()[]{}")
                upper = token.upper()
                if not token or normalize_for_match(token) == brand_norm or not MODEL_TOKEN_RE.match(upper):
                    continue
                score = 10 + sum(bool(re.search(pattern, upper)) for pattern in [r"[A-Z]", r"\d"])
                score += len(upper)
                if score > best_score:
                    best = upper
                    best_score = score
        return best

    def _build_canonical_sections(
        self,
        family: str | None,
        brand: str,
        mpn: str,
        title: str,
        hero_summary: str,
        raw_pairs: list[tuple[str, str, str]],
        summary_pairs: list[tuple[str, str, str]],
        merchant_titles: list[str],
    ) -> list[SpecSection]:
        if family not in SKROUTZ_FAMILIES:
            return []
        lookup = self._build_label_lookup(raw_pairs, summary_pairs)
        full_text = normalize_whitespace(" ".join([title, hero_summary, *merchant_titles, *lookup.values()]))
        if family == "soundbar":
            return self._soundbar_sections(raw_pairs, merchant_titles)
        if family == "coffee_filter":
            section_values = self._coffee_values(lookup, full_text, merchant_titles)
        elif family == "kettle":
            section_values = self._kettle_values(lookup, title, full_text, merchant_titles)
        else:
            section_values = self._tabletop_hob_values(lookup, brand, mpn, title, full_text)

        out: list[SpecSection] = []
        for section_title, labels in SKROUTZ_FAMILIES[family]["sections"]:
            items = [SpecItem(label=label, value=section_values.get(label, "-")) for label in labels]
            out.append(SpecSection(section=section_title, items=items))
        return out

    def _build_label_lookup(self, raw_pairs: list[tuple[str, str, str]], summary_pairs: list[tuple[str, str, str]]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for _, label, value in [*raw_pairs, *summary_pairs]:
            normalized_label = normalize_for_match(label)
            normalized_value = normalize_whitespace(value)
            if normalized_label and normalized_value and normalized_label not in lookup:
                lookup[normalized_label] = normalized_value
        return lookup

    def _coffee_values(self, lookup: dict[str, str], full_text: str, merchant_titles: list[str]) -> dict[str, str]:
        normalized_text = normalize_for_match(full_text)
        dimensions = self._extract_dimensions_text(full_text, expected_parts=3)
        return {
            "Χωρητικότητα σε Φλυτζάνια": self._extract_cups(full_text) or self._normalize_cups(lookup.get(normalize_for_match("Χωρητικότητα Φλυτζάνια"))) or "-",
            "Υλικό Κανάτας": self._clean_placeholder(lookup.get(normalize_for_match("Υλικό Κανάτας")) or lookup.get(normalize_for_match("Κανάτα"))),
            "Ισχύς σε Watts": self._number_only(lookup.get(normalize_for_match("Ισχύς"))),
            "Χωρητικότητα Δοχείου Νερού σε Λίτρα": self._extract_capacity_from_titles(merchant_titles) or self._number_only(lookup.get(normalize_for_match("Χωρητικότητα lt"))),
            "Ένδειξη Στάθμης Νερού": self._bool_from_text(normalized_text, ["σταθμη", "νερου"]),
            "Αποσπώμενο Δοχείο Νερού": self._boolean_or_placeholder(lookup.get(normalize_for_match("Αποσπώμενο Δοχείο Νερού"))),
            "Θερμαινόμενη Βάση": self._boolean_or_placeholder(lookup.get(normalize_for_match("Θερμαινόμενη Βάση"))),
            "Ενδεικτική Λυχνία Λειτουργίας": self._boolean_or_placeholder(lookup.get(normalize_for_match("Ενδεικτική Λυχνία Λειτουργίας"))),
            "Ηχητικό Σήμα Ειδοποίησης": self._boolean_or_placeholder(lookup.get(normalize_for_match("Ηχητικό Σήμα Ειδοποίησης"))),
            "Αποθήκευση Καλωδίου": self._boolean_or_placeholder(lookup.get(normalize_for_match("Αποθήκευση Καλωδίου"))),
            "Διακοπή Σταξίματος": self._bool_from_text(normalized_text, ["σταξ"]),
            "Λειτουργία Aroma": self._boolean_or_placeholder(lookup.get(normalize_for_match("Λειτουργία Aroma"))),
            "Αυτόματη Διακοπή Λειτουργίας": self._bool_from_text(normalized_text, ["αυτοματ"]),
            "Χρονοδιακόπτης Λειτουργίας": self._boolean_or_placeholder(lookup.get(normalize_for_match("Χρονοδιακόπτης Λειτουργίας"))),
            "Χρώμα": self._clean_placeholder(lookup.get(normalize_for_match("Χρώμα"))),
            "Βάρος Συσκευής σε Κιλά": self._extract_weight(full_text),
            "Διαστάσεις Συσκευής σε Εκατοστά. (Υ χ Π χ Β": dimensions or "-",
            "Εγγύηση Κατασκευαστή": self._extract_warranty(full_text),
        }

    def _kettle_values(self, lookup: dict[str, str], title: str, full_text: str, merchant_titles: list[str]) -> dict[str, str]:
        normalized_text = normalize_for_match(full_text)
        dimensions = self._extract_dimensions_text(" ".join(merchant_titles + [full_text]), expected_parts=3)
        return {
            "Χωρητικότητα σε Λίτρα": self._number_only(lookup.get(normalize_for_match("Χωρητικότητα"))),
            "Ισχύς σε Watts": self._number_only(lookup.get(normalize_for_match("Ισχύς"))),
            "Αποσπώμενη Βάση": self._boolean_or_placeholder(lookup.get(normalize_for_match("Αποσπώμενη Βάση"))),
            "Βάση 360 Μοιρών": self._bool_from_text(normalized_text, ["360"]),
            "Φίλτρο Νερού": self._clean_placeholder(lookup.get(normalize_for_match("Φίλτρο Νερού")) or lookup.get(normalize_for_match("Είδος Φίλτρου"))),
            "Άνοιγμα του Καπακιού με το Πάτημα ενός Κουμπιού": self._bool_from_text(normalized_text, ["καπακ", "κουμπ"]),
            "Καλυμμένη Αντίσταση": self._boolean_or_placeholder(lookup.get(normalize_for_match("Καλυμμένη Αντίσταση"))),
            "Υλικό Κατασκευής": self._clean_placeholder(lookup.get(normalize_for_match("Υλικό Κανάτας"))),
            "Αποθήκευση Καλωδίου": self._bool_from_text(normalized_text, ["καλωδι"]),
            "Ένδειξη Στάθμης Νερού": self._bool_from_text(normalized_text, ["σταθμη"]),
            "Ένδειξη Λειτουργίας": self._bool_from_text(normalized_text, ["λυχνι"]),
            "Ηχητικό Σήμα Ειδοποίησης": self._boolean_or_placeholder(lookup.get(normalize_for_match("Ηχητικό Σήμα Ειδοποίησης"))),
            "Επιλογές Θερμοκρασίας Βρασμού": self._boolean_or_placeholder(lookup.get(normalize_for_match("Επιλογή Θερμοκρασίας"))),
            "Λειτουργία Διατήρησης Θερμοκρασίας": self._boolean_or_placeholder(lookup.get(normalize_for_match("Διατήρηση Θερμοκρασίας"))),
            "Αυτόματος Τερματισμός Λειτουργίας": self._bool_from_text(normalized_text, ["αυτοματ"]),
            "Προστασία από Βρασμό Χωρίς Νερό": self._boolean_or_placeholder(lookup.get(normalize_for_match("Προστασία από Βρασμό Χωρίς Νερό"))),
            "Χρώμα": self._clean_placeholder(lookup.get(normalize_for_match("Χρώμα"))),
            "Βάρος Συσκευής σε Κιλά": self._extract_weight(full_text),
            "Διαστάσεις Συσκευής σε Εκατοστά. (Υ χ Π χ Β": dimensions or "-",
            "Εγγύηση Κατασκευαστή": self._extract_warranty(full_text),
            "_title_color_suffix": self._title_color_suffix(title, lookup.get(normalize_for_match("Χρώμα"))),
        }

    def _tabletop_hob_values(self, lookup: dict[str, str], brand: str, mpn: str, title: str, full_text: str) -> dict[str, str]:
        normalized_title = normalize_for_match(title)
        width, depth = self._extract_dimensions_2(full_text)
        surface = self._clean_placeholder(lookup.get(normalize_for_match("Τύπος Εστίας")))
        if surface == "-" and "εμαγι" in normalized_title:
            surface = "Εμαγιέ"
        count = self._number_only(lookup.get(normalize_for_match("Εστίες")))
        return {
            "Κατασκευαστής": brand or "-",
            "Μοντέλο": mpn or "-",
            "Εστία": self._render_hob_type(count),
            "Πλάτος": f"{width} cm" if width else "-",
            "Βάθος": f"{depth} cm" if depth else "-",
            "_Ισχύς": self._number_only(lookup.get(normalize_for_match("Ισχύς"))),
            "_Τύπος Εστίας": surface,
            "_Εστίες": count or "-",
            "_Χρώμα": self._clean_placeholder(lookup.get(normalize_for_match("Χρώμα"))),
            "_Είδος Διακόπτη": self._clean_placeholder(lookup.get(normalize_for_match("Είδος Διακόπτη"))),
        }

    def _build_key_specs(self, family: str | None, sections: list[SpecSection], raw_pairs: list[tuple[str, str, str]], summary_pairs: list[tuple[str, str, str]]) -> list[SpecItem]:
        if not family or not sections:
            return []
        lookup = {item.label: item.value or "-" for section in sections for item in section.items}
        supplemental_lookup = self._build_label_lookup(raw_pairs, summary_pairs)
        selected_labels = {
            "soundbar": ["Κανάλια", "Πρότυπα Ήχου", "Συνδεσιμότητα", "Subwoofer", "Χρώμα", "Ισχύς"],
            "coffee_filter": ["Χωρητικότητα σε Φλυτζάνια", "Χωρητικότητα Δοχείου Νερού σε Λίτρα", "Ισχύς σε Watts", "Υλικό Κανάτας", "Χρώμα"],
            "kettle": ["Χωρητικότητα σε Λίτρα", "Ισχύς σε Watts", "Βάση 360 Μοιρών", "Υλικό Κατασκευής", "Χρώμα"],
            "tabletop_hob": ["Κατασκευαστής", "Μοντέλο", "Εστία", "Πλάτος", "Βάθος"],
        }[family]
        items = [SpecItem(label=label, value=lookup[label]) for label in selected_labels if lookup.get(label)]
        if family == "tabletop_hob":
            for label in ["Ισχύς", "Τύπος Εστίας", "Εστίες", "Χρώμα", "Είδος Διακόπτη"]:
                value = supplemental_lookup.get(normalize_for_match(label))
                if value:
                    items.append(SpecItem(label=label, value=value))
        return items

    def _soundbar_sections(self, raw_pairs: list[tuple[str, str, str]], merchant_titles: list[str]) -> list[SpecSection]:
        grouped: dict[str, list[SpecItem]] = {}
        for section_title, label, value in raw_pairs:
            normalized_title = normalize_whitespace(section_title) or "Τεχνικά Χαρακτηριστικά"
            grouped.setdefault(normalized_title, []).append(SpecItem(label=label, value=value))
        derived_power = self._extract_soundbar_power(" ".join(merchant_titles))
        if derived_power:
            target_section = next(iter(grouped), "Χαρακτηριστικά")
            grouped.setdefault(target_section, []).append(SpecItem(label="Ισχύς", value=derived_power))
        return [SpecSection(section=title, items=items) for title, items in grouped.items()]

    def _extract_soundbar_power(self, text: str) -> str:
        matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*W\b", text or "", flags=re.IGNORECASE)
        if not matches:
            return ""
        numeric = max(float(value.replace(",", ".")) for value in matches)
        return f"{int(numeric)} W"

    def _extract_cups(self, text: str) -> str:
        match = CUPS_RE.search(text)
        return normalize_whitespace(match.group(1)).replace("-", " - ") if match else ""

    def _normalize_cups(self, value: str | None) -> str:
        normalized = normalize_whitespace(value)
        if not normalized:
            return ""
        match = CUPS_RE.search(normalized)
        if match:
            return normalize_whitespace(match.group(1)).replace("-", " - ")
        return self._number_only(normalized)

    def _extract_capacity_from_titles(self, merchant_titles: list[str]) -> str:
        for title in merchant_titles:
            match = CAPACITY_LT_RE.search(title)
            if match:
                return match.group(1).replace(".", ",")
        return ""

    def _extract_dimensions_text(self, text: str, expected_parts: int) -> str:
        for match in DIMENSIONS_RE.finditer(text):
            values = [part.replace(".", ",") for part in match.groups() if part]
            if len(values) == expected_parts:
                return " × ".join(values)
        return ""

    def _extract_dimensions_2(self, text: str) -> tuple[str, str]:
        for match in DIMENSIONS_RE.finditer(text):
            values = [part.replace(".", ",") for part in match.groups() if part]
            if len(values) >= 2:
                return values[0], values[1]
        return "", ""

    def _extract_weight(self, text: str) -> str:
        match = WEIGHT_RE.search(text)
        return match.group(1).replace(".", ",") if match else "-"

    def _extract_warranty(self, text: str) -> str:
        match = WARRANTY_RE.search(text)
        if not match:
            return "-"
        years = match.group(1)
        return f"{years} Χρόνια" if years != "1" else "1 Χρόνος"

    def _title_color_suffix(self, title: str, raw_color: str | None) -> str:
        color = self._clean_placeholder(raw_color)
        if color == "-":
            return ""
        if re.search(r"\bmat\b", title, flags=re.IGNORECASE):
            return f"{color} Ματ"
        return color

    def _number_only(self, value: str | None) -> str:
        if not value:
            return "-"
        match = NUMERIC_RE.search(value.replace("×", " "))
        return match.group(0).replace(".", ",") if match else normalize_whitespace(value)

    def _bool_from_text(self, normalized_text: str, tokens: list[str]) -> str:
        return "Ναι" if all(token in normalized_text for token in tokens) else "-"

    def _clean_placeholder(self, value: str | None) -> str:
        normalized = normalize_whitespace(value)
        return normalized if normalized else "-"

    def _boolean_or_placeholder(self, value: str | None) -> str:
        normalized = normalize_for_match(value)
        if normalized in {"ναι", "yes"}:
            return "Ναι"
        if normalized in {"οχι", "όχι", "no"}:
            return "Όχι"
        return normalize_whitespace(value) or "-"

    def _render_hob_type(self, count: str) -> str:
        if count == "2":
            return "Διπλή*"
        if count == "1":
            return "Μονή*"
        return count or "-"

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = normalize_whitespace(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
        return out

    def _collect_missing_fields(self, source: SourceProductData) -> list[str]:
        missing: list[str] = []
        if not source.name:
            missing.append("name")
        if not source.brand:
            missing.append("brand")
        if not source.breadcrumbs:
            missing.append("breadcrumbs")
        if not source.hero_summary:
            missing.append("hero_summary")
        if not source.gallery_images:
            missing.append("gallery_images")
        if not source.spec_sections:
            missing.append("spec_sections")
        return missing

    def _collect_critical_missing(self, source: SourceProductData, family: str | None) -> list[str]:
        critical: list[str] = []
        if not source.name:
            critical.append("name")
        if not source.brand:
            critical.append("brand")
        if not source.breadcrumbs:
            critical.append("breadcrumbs")
        if not source.gallery_images:
            critical.append("gallery_images")
        if not source.spec_sections:
            critical.append("spec_sections")
        if family is None:
            critical.append("supported_family")
        return sorted(set(critical))

    def _make_diagnostic(self, value: Any, selected_strategy: str, confidence: float, selector_trace: list[SelectorTraceEntry]) -> FieldDiagnostic:
        return FieldDiagnostic(confidence=round(confidence, 4), selected_strategy=selected_strategy, value_present=self._value_present(value), value_preview=self._preview_value(value), selector_trace=selector_trace)

    def _value_present(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(normalize_whitespace(value))
        if isinstance(value, list):
            return bool(value)
        return True

    def _preview_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return normalize_whitespace(value)[:160]
        if isinstance(value, list):
            if not value:
                return ""
            first = value[0]
            if isinstance(first, SpecSection):
                return f"{len(value)} sections; first={first.section}"
            if isinstance(first, GalleryImage):
                return f"{len(value)} images; first={first.url}"
            if isinstance(first, SpecItem):
                return f"{len(value)} items; first={first.label}"
            return f"{len(value)} items"
        return normalize_whitespace(str(value))[:160]

    def _trace(self, strategy: str, selector: str, nodes: list[Tag], chosen: Tag | None) -> SelectorTraceEntry:
        return SelectorTraceEntry(strategy=strategy, selector=selector, match_count=len(nodes), success=chosen is not None, chosen_preview=safe_text(chosen)[:120] if chosen else "", note="")
