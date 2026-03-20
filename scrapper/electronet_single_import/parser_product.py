from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .models import GalleryImage, ParsedProduct, SourceProductData, SpecItem, SpecSection
from .normalize import (
    clean_breadcrumbs,
    dedupe_urls_preserve_order,
    make_absolute_url,
    normalize_for_match,
    normalize_whitespace,
    nullify_dash_values,
    parse_euro_price,
    safe_text,
    split_visible_lines,
)
from .utils import utcnow_iso

STOP_HEADINGS = {
    normalize_for_match("Σχετικά προϊόντα"),
    normalize_for_match("Περισσότερες φωτογραφίες"),
    normalize_for_match("Το ήξερες;"),
}
CRITICAL_FIELDS = ["name", "product_code", "price", "breadcrumbs", "spec_sections", "gallery_images", "hero_summary"]
PRICE_RE = re.compile(r"\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?\s*€")
INSTALLMENTS_RE = re.compile(r"\d+\s+άτοκες\s+δόσεις", re.IGNORECASE)
CODE_RE = re.compile(r"ΚΩΔΙΚΟΣ\s+ΠΡΟΪΟΝΤΟΣ\s*:?\s*([0-9]{6})", re.IGNORECASE)


class ElectronetProductParser:
    def __init__(self, known_section_titles: set[str] | None = None) -> None:
        self.known_section_titles = known_section_titles or set()

    def parse(self, html: str, url: str, fallback_used: bool = False) -> ParsedProduct:
        soup = BeautifulSoup(html, "lxml")
        text_lines = split_visible_lines(soup.get_text("\n"))
        jsonld = self._parse_jsonld(soup)
        provenance: dict[str, str] = {}
        warnings: list[str] = []

        canonical_url = self._extract_canonical_url(soup, url)
        breadcrumbs = self._extract_breadcrumbs(soup, text_lines)
        provenance["breadcrumbs"] = "visible" if breadcrumbs else "missing"

        product_code, product_code_source = self._extract_product_code(soup, text_lines, jsonld)
        provenance["product_code"] = product_code_source

        name, name_source = self._extract_name(soup, jsonld)
        provenance["name"] = name_source

        brand, brand_source = self._extract_brand(soup, text_lines, jsonld, name)
        provenance["brand"] = brand_source

        price_text, price_value, price_source = self._extract_price(soup, text_lines, jsonld)
        provenance["price"] = price_source

        installments_text = self._extract_installments_text(text_lines)
        delivery_text, pickup_text = self._extract_delivery_and_pickup(text_lines)
        hero_summary = self._extract_hero_summary(text_lines, name)
        presentation_html, presentation_text = self._extract_presentation_source(soup)
        key_specs = self._extract_key_specs(text_lines, name)
        spec_sections = self._extract_spec_sections(soup, text_lines)
        mpn = self._extract_mpn(key_specs, spec_sections)

        gallery_images = self._extract_gallery_images(soup, url, name, brand, product_code)
        if not gallery_images:
            warnings.append("gallery_images_missing")

        energy_label_asset_url, product_sheet_asset_url = self._extract_assets(soup, url)

        source = SourceProductData(
            page_type="product",
            url=url,
            canonical_url=canonical_url,
            breadcrumbs=breadcrumbs,
            product_code=product_code,
            brand=brand,
            name=name,
            hero_summary=hero_summary,
            price_text=price_text,
            price_value=price_value,
            installments_text=installments_text,
            delivery_text=delivery_text,
            pickup_text=pickup_text,
            gallery_images=gallery_images,
            energy_label_asset_url=energy_label_asset_url,
            product_sheet_asset_url=product_sheet_asset_url,
            key_specs=key_specs,
            spec_sections=spec_sections,
            presentation_source_html=presentation_html,
            presentation_source_text=presentation_text,
            raw_html_path="",
            scraped_at=utcnow_iso(),
            fallback_used=fallback_used,
            mpn=mpn,
        )
        missing_fields = self._collect_missing_fields(source)
        critical_missing = self._collect_critical_missing(source)
        return ParsedProduct(source=source, provenance=provenance, missing_fields=missing_fields, warnings=warnings, critical_missing=critical_missing)

    def _parse_jsonld(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, list):
                payload.extend(item for item in parsed if isinstance(item, dict))
            elif isinstance(parsed, dict):
                payload.append(parsed)
        return payload

    def _extract_canonical_url(self, soup: BeautifulSoup, url: str) -> str:
        link = soup.find("link", rel=lambda value: value and "canonical" in value.lower())
        if link and link.get("href"):
            return make_absolute_url(link["href"], url)
        return url

    def _extract_breadcrumbs(self, soup: BeautifulSoup, text_lines: list[str]) -> list[str]:
        candidates: list[str] = []
        for selector in [
            "nav.breadcrumb a",
            ".breadcrumb a",
            ".breadcrumb li",
            "[aria-label='breadcrumb'] a",
            "[class*='breadcrumb'] a",
            "[class*='breadcrumb'] li",
        ]:
            for node in soup.select(selector):
                text = safe_text(node)
                if text:
                    candidates.append(text)
        if candidates:
            return clean_breadcrumbs(candidates)

        if "Breadcrumb" in text_lines:
            start = text_lines.index("Breadcrumb") + 1
            extracted: list[str] = []
            for line in text_lines[start: start + 10]:
                match = re.match(r"\d+\.\s*(.+)", line)
                if match:
                    extracted.append(match.group(1))
            return clean_breadcrumbs(extracted)
        return []

    def _extract_product_code(self, soup: BeautifulSoup, text_lines: list[str], jsonld: list[dict[str, Any]]) -> tuple[str, str]:
        page_text = soup.get_text(" ", strip=True)
        match = CODE_RE.search(page_text)
        if match:
            return match.group(1), "label"
        for line in text_lines:
            match = CODE_RE.search(line)
            if match:
                return match.group(1), "regex"
        for item in jsonld:
            sku = item.get("sku") or item.get("productID")
            if sku and re.fullmatch(r"\d{6}", normalize_whitespace(str(sku))):
                return normalize_whitespace(str(sku)), "jsonld"
        return "", "missing"

    def _extract_name(self, soup: BeautifulSoup, jsonld: list[dict[str, Any]]) -> tuple[str, str]:
        h1 = soup.find("h1")
        if h1:
            text = safe_text(h1)
            if text:
                return text, "h1"
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            return normalize_whitespace(og["content"]), "og:title"
        title = soup.find("title")
        if title:
            text = safe_text(title)
            if text:
                return text.split(" - ")[0].strip(), "title"
        for item in jsonld:
            name = item.get("name")
            if name:
                return normalize_whitespace(str(name)), "jsonld"
        return "", "missing"

    def _extract_brand(self, soup: BeautifulSoup, text_lines: list[str], jsonld: list[dict[str, Any]], name: str) -> tuple[str, str]:
        for selector in ["[class*='brand'] a", "[class*='brand']", "a[title*='brand']", "a[href*='brand']"]:
            node = soup.select_one(selector)
            if node:
                text = safe_text(node)
                if text:
                    return text, "visible"
        if "Σύγκριση" in text_lines:
            idx = text_lines.index("Σύγκριση")
            if idx + 1 < len(text_lines):
                candidate = normalize_whitespace(text_lines[idx + 1])
                if candidate and len(candidate.split()) <= 3:
                    return candidate, "visible"
        for item in jsonld:
            brand = item.get("brand") or item.get("manufacturer")
            if isinstance(brand, dict):
                brand = brand.get("name")
            if brand:
                return normalize_whitespace(str(brand)), "jsonld"
        if name:
            token = name.split()[0]
            if token and len(token) > 1:
                return token, "title_token"
        return "", "missing"

    def _extract_price(self, soup: BeautifulSoup, text_lines: list[str], jsonld: list[dict[str, Any]]) -> tuple[str, float | None, str]:
        for selector in [
            "meta[property='product:price:amount']",
            "meta[itemprop='price']",
            "[itemprop='price']",
            "[class*='price']",
        ]:
            node = soup.select_one(selector)
            if node:
                text = normalize_whitespace(node.get("content") or safe_text(node))
                price = parse_euro_price(text) if "€" in text or re.search(r"\d", text) else parse_euro_price(node.get("content"))
                if price is not None:
                    return text or f"{price}", price, "visible"
        for line in text_lines:
            if PRICE_RE.search(line):
                price = parse_euro_price(line)
                if price is not None:
                    return normalize_whitespace(line), price, "visible"
        for item in jsonld:
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                if price is not None:
                    return normalize_whitespace(str(price)), float(price), "jsonld"
        return "", None, "missing"

    def _extract_installments_text(self, text_lines: list[str]) -> str:
        for line in text_lines:
            if INSTALLMENTS_RE.search(line):
                return normalize_whitespace(line)
        return ""

    def _extract_delivery_and_pickup(self, text_lines: list[str]) -> tuple[str, str]:
        delivery = ""
        pickup = ""
        for idx, line in enumerate(text_lines):
            if line == "Παράδοση" and idx + 1 < len(text_lines):
                delivery = text_lines[idx + 1]
            if line == "Παραλαβή" and idx + 1 < len(text_lines):
                pickup = text_lines[idx + 1]
        return delivery, pickup

    def _extract_hero_summary(self, text_lines: list[str], name: str) -> str:
        start = 0
        if name and name in text_lines:
            start = text_lines.index(name) + 1
        for idx in range(start, min(len(text_lines), start + 40)):
            line = text_lines[idx]
            norm = normalize_for_match(line)
            if not line or PRICE_RE.search(line):
                continue
            if INSTALLMENTS_RE.search(line):
                continue
            if line in {"Φωτογραφίες", "Παρουσίαση", "Χαρακτηριστικά", "Παράδοση", "Παραλαβή"}:
                continue
            if norm in STOP_HEADINGS:
                break
            if len(line) >= 40 and not line.isupper():
                return line
        return ""

    def _extract_key_specs(self, text_lines: list[str], name: str) -> list[SpecItem]:
        items: list[SpecItem] = []
        start = 0
        if name and name in text_lines:
            start = text_lines.index(name) + 1
        hero_seen = False
        idx = start
        while idx < len(text_lines):
            line = text_lines[idx]
            if line == "Παράδοση":
                break
            if len(line) >= 40 and not hero_seen and not PRICE_RE.search(line) and not INSTALLMENTS_RE.search(line):
                hero_seen = True
                idx += 1
                continue
            if line in {"Φωτογραφίες", "Παρουσίαση", "Χαρακτηριστικά"}:
                idx += 1
                continue
            if idx + 1 < len(text_lines) and text_lines[idx + 1] != "Παράδοση":
                label = line
                value = text_lines[idx + 1]
                if label and value and not PRICE_RE.search(label) and not INSTALLMENTS_RE.search(label):
                    items.append(SpecItem(label=label, value=nullify_dash_values(value)))
                    idx += 2
                    continue
            idx += 1
        deduped: list[SpecItem] = []
        seen: set[str] = set()
        for item in items:
            key = normalize_for_match(item.label)
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    def _extract_presentation_source(self, soup: BeautifulSoup) -> tuple[str, str]:
        start_heading = self._find_heading(soup, "Παρουσίαση Προϊόντος")
        stop_heading = self._find_heading(soup, "Τεχνικά Χαρακτηριστικά")
        if not start_heading or not stop_heading:
            return "", ""
        chunks: list[str] = []
        text_parts: list[str] = []
        for node in start_heading.next_siblings:
            if node == stop_heading:
                break
            if isinstance(node, Tag):
                chunks.append(str(node))
                text = safe_text(node)
                if text:
                    text_parts.append(text)
            else:
                text = normalize_whitespace(str(node))
                if text:
                    text_parts.append(text)
        return "\n".join(chunks).strip(), "\n".join(text_parts).strip()

    def _find_heading(self, soup: BeautifulSoup, exact_text: str) -> Tag | None:
        target = normalize_for_match(exact_text)
        for tag in soup.find_all(re.compile(r"^h[1-6]$")):
            if normalize_for_match(safe_text(tag)) == target:
                return tag
        return None

    def _extract_spec_sections(self, soup: BeautifulSoup, text_lines: list[str]) -> list[SpecSection]:
        sections = self._extract_spec_sections_from_dom(soup)
        if sections:
            return sections
        return self._extract_spec_sections_from_lines(text_lines)

    def _extract_spec_sections_from_dom(self, soup: BeautifulSoup) -> list[SpecSection]:
        start_heading = self._find_heading(soup, "Τεχνικά Χαρακτηριστικά")
        if not start_heading:
            return []
        sections: list[SpecSection] = []
        current: SpecSection | None = None
        for node in start_heading.next_elements:
            if not isinstance(node, Tag):
                continue
            if node == start_heading:
                continue
            if node.name and re.fullmatch(r"h[1-6]", node.name):
                heading = safe_text(node)
                norm = normalize_for_match(heading)
                if norm in STOP_HEADINGS:
                    break
                if heading != "Τεχνικά Χαρακτηριστικά":
                    current = SpecSection(section=heading, items=[])
                    sections.append(current)
                continue
            if current is None:
                continue
            if node.name == "tr":
                cells = [safe_text(cell) for cell in node.find_all(["th", "td"])]
                if len(cells) >= 2:
                    current.items.append(SpecItem(label=cells[0], value=nullify_dash_values(cells[1])))
            elif node.name == "dt":
                sibling = node.find_next_sibling("dd")
                current.items.append(SpecItem(label=safe_text(node), value=nullify_dash_values(safe_text(sibling))))
        sections = [section for section in sections if section.items]
        return sections

    def _extract_spec_sections_from_lines(self, text_lines: list[str]) -> list[SpecSection]:
        if "Τεχνικά Χαρακτηριστικά" not in text_lines:
            return []
        start = text_lines.index("Τεχνικά Χαρακτηριστικά") + 1
        sections: list[SpecSection] = []
        current: SpecSection | None = None
        idx = start
        while idx < len(text_lines):
            line = text_lines[idx]
            norm = normalize_for_match(line)
            if norm in STOP_HEADINGS:
                break
            if self._is_section_title(line):
                current = SpecSection(section=line, items=[])
                sections.append(current)
                idx += 1
                continue
            if current is None:
                idx += 1
                continue
            label = line
            if idx + 1 >= len(text_lines):
                current.items.append(SpecItem(label=label, value=None))
                idx += 1
                continue
            next_line = text_lines[idx + 1]
            if self._is_section_title(next_line) or normalize_for_match(next_line) in STOP_HEADINGS:
                current.items.append(SpecItem(label=label, value=None))
                idx += 1
                continue
            current.items.append(SpecItem(label=label, value=nullify_dash_values(next_line)))
            idx += 2
        return [section for section in sections if section.items]

    def _is_section_title(self, line: str) -> bool:
        norm = normalize_for_match(line)
        if not norm:
            return False
        if norm in self.known_section_titles:
            return True
        if line.startswith("### "):
            return True
        return False

    def _extract_gallery_images(self, soup: BeautifulSoup, url: str, name: str, brand: str, product_code: str) -> list[GalleryImage]:
        scored: list[tuple[int, int, str, str]] = []
        product_tokens = [token for token in normalize_for_match(name).split() if len(token) > 2][:8]
        brand_token = normalize_for_match(brand)
        for position, img in enumerate(soup.find_all("img"), start=1):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
            abs_url = make_absolute_url(src, url)
            alt = normalize_whitespace(img.get("alt") or img.get("title") or "")
            haystack = normalize_for_match(f"{abs_url} {alt}")
            score = 0
            if any(token in haystack for token in product_tokens):
                score += 4
            if brand_token and brand_token in haystack:
                score += 1
            if product_code and product_code in haystack:
                score += 3
            if "/image/" in abs_url or "/catalog/" in abs_url or "/cache/" in abs_url:
                score += 1
            bad = ["logo", "icon", "energy", "share", "facebook", "twitter", "payment", "visa", "mastercard"]
            if any(token in haystack for token in bad):
                score -= 5
            if score > 0:
                scored.append((score, position, abs_url, alt))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ordered_urls = dedupe_urls_preserve_order([item[2] for item in scored])
        out: list[GalleryImage] = []
        for position, image_url in enumerate(ordered_urls, start=1):
            alt = next((item[3] for item in scored if item[2] == image_url), "")
            out.append(GalleryImage(url=image_url, alt=alt, position=position))
        return out

    def _extract_assets(self, soup: BeautifulSoup, url: str) -> tuple[str, str]:
        energy_label = ""
        product_sheet = ""
        for link in soup.find_all("a", href=True):
            text = normalize_for_match(link.get_text(" ", strip=True))
            img = link.find("img")
            img_alt = normalize_for_match(img.get("alt") if img else "")
            if ("δελτιο προιοντος" in text or "product sheet" in text) and not product_sheet:
                product_sheet = make_absolute_url(link["href"], url)
            if any(token in f"{text} {img_alt}" for token in ["energy class", "ενεργειακη", "δελτιο προιοντος"]):
                if img and img.get("src") and not energy_label:
                    energy_label = make_absolute_url(img["src"], url)
        return energy_label, product_sheet

    def _extract_mpn(self, key_specs: list[SpecItem], spec_sections: list[SpecSection]) -> str:
        mpn_labels = {normalize_for_match(label) for label in ["MPN", "Μοντέλο", "Model"]}
        for item in key_specs:
            if normalize_for_match(item.label) in mpn_labels and item.value:
                return item.value
        for section in spec_sections:
            for item in section.items:
                if normalize_for_match(item.label) in mpn_labels and item.value:
                    return item.value
        return ""

    def _collect_missing_fields(self, source: SourceProductData) -> list[str]:
        missing: list[str] = []
        if not source.product_code:
            missing.append("product_code")
        if not source.brand:
            missing.append("brand")
        if not source.name:
            missing.append("name")
        if not source.price_text:
            missing.append("price")
        if not source.breadcrumbs:
            missing.append("breadcrumbs")
        if not source.hero_summary:
            missing.append("hero_summary")
        if not source.gallery_images:
            missing.append("gallery_images")
        if not source.spec_sections:
            missing.append("spec_sections")
        return missing

    def _collect_critical_missing(self, source: SourceProductData) -> list[str]:
        critical: list[str] = []
        if not source.name:
            critical.append("name")
        if not source.product_code:
            critical.append("product_code")
        if source.price_value is None:
            critical.append("price")
        if not source.breadcrumbs:
            critical.append("breadcrumbs")
        if not source.spec_sections:
            critical.append("spec_sections")
        if not source.gallery_images:
            critical.append("gallery_images")
        if not source.hero_summary:
            critical.append("hero_summary")
        return critical
