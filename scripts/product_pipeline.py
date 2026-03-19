from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STOCK_STATUS = "Έως 30 ημέρες"
BOXNOW_OVERLAY = "Μικροσυσκευές"
REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

FILTER_LABEL_ALIASES = {
    "Πλάτος cm": ["Πλάτος Συσκευής σε Εκατοστά", "Πλάτος"],
    "Χρώμα": ["Χρώμα", "Χρώμα Πλαϊνών"],
    "Ενεργειακή Κλάση": ["Ενεργειακή Κλάση"],
    "Ψύξη": ["Τεχνολογία Ψύξης"],
    "Συνδεσιμότητα": ["Συνδεσιμότητα"],
    "Ονομαστική Απόδοση (Btu/h)": ["Ονομαστική Απόδοση (Btu/h)", "Ονομαστική Απόδοση"],
    "Συνολική Χωρητικότητα": ["Συνολική Καθαρή Χωρητικότητα", "Καθαρή Χωρητικότητα"],
    "Χωρητικότητα σε Λίτρα": ["Συνολική Καθαρή Χωρητικότητα", "Χωρητικότητα"],
    "Ύψος cm": ["Ύψος Συσκευής σε Εκατοστά", "Υψος Συσκευής σε Εκατοστά", "Ύψος"],
    "Θόρυβος (db)": ["Επίπεδο Θορύβου σε dB", "Θόρυβος"],
    "WiFi": ["Συνδεσιμότητα"],
    "Τεχνολογία Ψύξης": ["Τεχνολογία Ψύξης"],
    "Τύπος Ψυγείου": ["Τύπος Ψυγείου"],
}

KEY_SPEC_HINTS = [
    "ονομαστικη αποδοση",
    "συνολικη καθαρη χωρητικοτητα",
    "καθαρη χωρητικοτητα",
    "ενεργειακη κλαση",
    "τεχνολογια ψυξης",
    "τεχνολογια κλιματιστικου",
    "συνδεσιμοτητα",
    "χρωμα",
    "seer",
    "scop",
    "θορυβου",
    "πλατος",
    "υψος",
    "βαθος",
    "διαστασεις",
    "ψυκτικο υγρο",
    "θερμικη αποδοση",
    "ψυκτικη αποδοση",
]


def collapse_spaces(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_lookup(value: str | None) -> str:
    text = collapse_spaces(value)
    text = text.replace("\xa0", " ")
    text = text.replace("&", " ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace("+", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^0-9a-zα-ω\s]", " ", text)
    return collapse_spaces(text)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_model(model: str) -> None:
    if not re.fullmatch(r"\d{6}", model):
        raise ValueError("Generation failed, provide 6-digit model")


def load_taxonomy_entries() -> list[dict[str, Any]]:
    taxonomy = read_json(ROOT / "catalog_taxonomy.json")
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    for bucket in taxonomy["indexes"]["by_parent_category"].values():
        for entry in bucket:
            key = (
                entry.get("parent_category"),
                entry.get("leaf_category"),
                entry.get("sub_category"),
                entry.get("url"),
            )
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    return entries


def load_filter_map() -> dict[str, Any]:
    return read_json(ROOT / "filter_map.json")


def load_csv_header() -> list[str]:
    with (ROOT / "product_import_template.csv").open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def category_to_serialized(entry: dict[str, Any] | None, boxnow: int) -> str:
    if not entry or not entry.get("parent_category") or not entry.get("leaf_category"):
        return ""
    parent = entry["parent_category"]
    leaf = entry["leaf_category"]
    sub = entry.get("sub_category")
    value = f"{parent}:::{parent}///{leaf}"
    if sub:
        value += f":::{parent}///{leaf}///{sub}"
    if boxnow:
        value += f":::{BOXNOW_OVERLAY}"
    return value


def build_image_fields(model: str, photos: int) -> tuple[str, str]:
    image = f"catalog/01_main/{model}/{model}-1.jpg"
    if photos <= 1:
        return image, ""
    extra = [
        f"catalog/01_main/{model}/{model}-{index}.jpg"
        for index in range(2, photos + 1)
    ]
    return image, ":::".join(extra)


def is_electronet_url(url: str) -> bool:
    return "electronet.gr" in (urlparse(url).netloc or "").lower()


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def extract_breadcrumbs(soup: BeautifulSoup) -> list[str]:
    nav = soup.select_one("nav.breadcrumb")
    if not nav:
        return []
    labels = [collapse_spaces(item.get_text(" ", strip=True)) for item in nav.select("li")]
    return [
        label
        for label in labels
        if label and normalize_lookup(label) not in {"breadcrumb", "αρχικη", "home"}
    ]


def resolve_taxonomy_entry(
    breadcrumbs: list[str],
    taxonomy_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if len(breadcrumbs) < 3:
        return None
    parent, leaf, sub = breadcrumbs[-3:]
    parent_norm = normalize_lookup(parent)
    leaf_norm = normalize_lookup(leaf)
    sub_norm = normalize_lookup(sub)
    for entry in taxonomy_entries:
        if (
            normalize_lookup(entry.get("parent_category")) == parent_norm
            and normalize_lookup(entry.get("leaf_category")) == leaf_norm
            and normalize_lookup(entry.get("sub_category")) == sub_norm
        ):
            return entry
    return None


def extract_title(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    return collapse_spaces(heading.get_text(" ", strip=True) if heading else "")


def extract_meta_description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"})
    return collapse_spaces(tag.get("content", "") if tag else "")


def parse_price_value(raw_value: str) -> str:
    digits = re.sub(r"[^\d,\.]", "", raw_value)
    if not digits:
        return "0"
    digits = digits.replace(".", "").replace(",", ".")
    try:
        number = float(digits)
    except ValueError:
        return "0"
    return str(int(number)) if number.is_integer() else f"{number:.2f}".rstrip("0").rstrip(".")


def extract_price(soup: BeautifulSoup) -> str:
    node = soup.select_one(".price")
    return parse_price_value(node.get_text(" ", strip=True) if node else "")


def extract_presentation_blocks(soup: BeautifulSoup) -> list[dict[str, str]]:
    article = soup.select_one("article.product-page")
    if not article:
        return []
    blocks: list[dict[str, str]] = []
    for block in article.select("div.ck-text.inline"):
        h2_values = [collapse_spaces(node.get_text(" ", strip=True)) for node in block.find_all("h2")]
        h3_values = [collapse_spaces(node.get_text(" ", strip=True)) for node in block.find_all("h3")]
        paragraphs = [
            collapse_spaces(node.get_text(" ", strip=True))
            for node in block.find_all("p")
            if collapse_spaces(node.get_text(" ", strip=True))
        ]
        heading = next((value for value in h2_values if value), "")
        subheading = next((value for value in h3_values if value), "")
        body = " ".join(paragraphs).strip()
        if not heading and not subheading and not body:
            continue
        blocks.append(
            {
                "heading": heading,
                "subheading": subheading if subheading != heading else "",
                "body": body,
            }
        )
    return blocks


def extract_technical_specs(soup: BeautifulSoup) -> list[dict[str, Any]]:
    article = soup.select_one("article.product-page")
    if not article:
        return []
    groups: list[dict[str, Any]] = []
    for wrapper in article.select("div.prop-group-wrapper"):
        title_node = wrapper.select_one(".prop-group-title")
        title = collapse_spaces(title_node.get_text(" ", strip=True) if title_node else "")
        rows: list[dict[str, str]] = []
        for prop in wrapper.select(".property"):
            columns = prop.find_all("div", recursive=False)
            if len(columns) < 2:
                continue
            label = collapse_spaces(columns[0].get_text(" ", strip=True))
            value = collapse_spaces(columns[-1].get_text(" ", strip=True)) or "-"
            if label:
                rows.append({"label": label, "value": value})
        if title and rows:
            groups.append({"title": title, "rows": rows})
    return groups


def flatten_specs(groups: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for group in groups:
        for row in group["rows"]:
            rows.append({"section": group["title"], "label": row["label"], "value": row["value"]})
    return rows


def detect_mpn(title: str) -> str:
    candidates = re.findall(r"[A-Za-z0-9][A-Za-z0-9/+\-\.]{3,}", title)
    candidates = [item.strip(".,;:()[]") for item in candidates if any(char.isdigit() for char in item)]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: ("/" in item, len(item)), reverse=True)
    return candidates[0]


def detect_brand(title: str, mpn: str) -> str:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-\.]{1,}", title)
    if not tokens:
        return ""
    if mpn and mpn in title:
        prefix = title.split(mpn, 1)[0]
        prefix_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-\.]{1,}", prefix)
        candidates = [token for token in prefix_tokens if len(token) > 2]
        if candidates:
            return candidates[-1]
    candidates = [token for token in tokens if len(token) > 2]
    return candidates[0] if candidates else tokens[0]


def choose_key_specs(spec_rows: list[dict[str, str]], limit: int = 14) -> list[dict[str, str]]:
    scored: list[tuple[int, int, dict[str, str]]] = []
    for index, row in enumerate(spec_rows):
        if not row["value"] or row["value"] == "-":
            continue
        label_norm = normalize_lookup(row["label"])
        score = 1
        for hint in KEY_SPEC_HINTS:
            if hint in label_norm:
                score += 5
        if len(row["value"]) <= 40:
            score += 1
        scored.append((score, -index, row))
    scored.sort(reverse=True)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, _, row in scored:
        key = normalize_lookup(row["label"])
        if key in seen:
            continue
        seen.add(key)
        selected.append({"label": row["label"], "value": row["value"]})
        if len(selected) >= limit:
            break
    if selected:
        return selected
    return [
        {"label": row["label"], "value": row["value"]}
        for row in spec_rows
        if row["value"] and row["value"] != "-"
    ][:limit]


def get_filter_groups(
    entry: dict[str, Any] | None,
    filter_map: dict[str, Any],
) -> list[str]:
    if not entry or not entry.get("sub_category"):
        return []
    sub_key = entry["sub_category"]
    if "by_sub_category_key" in filter_map and sub_key in filter_map["by_sub_category_key"]:
        return filter_map["by_sub_category_key"][sub_key].get("filter_groups", [])
    for row in filter_map.get("subcategories", []):
        if row.get("sub_category") == sub_key:
            return row.get("filter_groups", [])
    return []


def token_overlap_score(group_norm: str, label_norm: str) -> int:
    group_tokens = set(group_norm.split())
    label_tokens = set(label_norm.split())
    if not group_tokens or not label_tokens:
        return 0
    overlap = len(group_tokens & label_tokens)
    if not overlap:
        return 0
    return int(50 * overlap / max(len(group_tokens), len(label_tokens)))


def infer_filters(
    filter_groups: list[str],
    spec_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for group in filter_groups:
        alias_values = [group] + FILTER_LABEL_ALIASES.get(group, [])
        alias_norms = [normalize_lookup(item) for item in alias_values if item]
        best_score = 0
        best_row: dict[str, str] | None = None
        for row in spec_rows:
            value = collapse_spaces(row["value"])
            if not value or value == "-":
                continue
            label_norm = normalize_lookup(row["label"])
            score = 0
            for alias_norm in alias_norms:
                if not alias_norm:
                    continue
                if alias_norm == label_norm:
                    score = max(score, 100)
                elif alias_norm in label_norm or label_norm in alias_norm:
                    score = max(score, 80)
                else:
                    score = max(score, token_overlap_score(alias_norm, label_norm))
            if score > best_score:
                best_score = score
                best_row = row
        if best_row and best_score >= 35:
            results.append({"group": group, "value": best_row["value"]})
    return results


def strip_outer_paragraph(text: str) -> str:
    stripped = text.strip()
    if stripped.lower().startswith("<p") and stripped.lower().endswith("</p>"):
        stripped = re.sub(r"^<p[^>]*>", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"</p>$", "", stripped, flags=re.IGNORECASE).strip()
    return stripped


def compact_meta_keywords(value: list[str] | str) -> str:
    if isinstance(value, list):
        return ", ".join(collapse_spaces(item) for item in value if collapse_spaces(item))
    return collapse_spaces(value)


def apply_dimension_multiplication(value: str) -> str:
    return re.sub(r"(?<=\d)\s*[xXχΧ]\s*(?=\d)", " × ", value)


def render_technical_specs_html(groups: list[dict[str, Any]]) -> str:
    parts = ['<table class="table table-bordered">']
    for group in groups:
        parts.append(
            f'<thead><tr><td colspan="2"><strong>{group["title"]}</strong></td></tr></thead>'
        )
        parts.append("<tbody>")
        for row in group["rows"]:
            label = collapse_spaces(row["label"])
            value = apply_dimension_multiplication(collapse_spaces(row["value"]))
            parts.append(
                f'<tr><td>{label}</td><td style="text-align:right;"><strong>{value or "-"}</strong></td></tr>'
            )
        parts.append("</tbody>")
    parts.append("</table>")
    return "".join(parts)


def default_cta_text(entry: dict[str, Any] | None) -> str:
    if entry and entry.get("sub_category"):
        return f"Δείτε περισσότερα {entry['sub_category']} εδώ"
    if entry and entry.get("leaf_category"):
        return f"Δείτε περισσότερα {entry['leaf_category']} εδώ"
    return "Δείτε περισσότερα προϊόντα εδώ"


def render_description_html(context: dict[str, Any], response: dict[str, Any]) -> str:
    product = response["product"]
    presentation = response["presentation"]
    model = context["input"]["model"]
    sections_required = int(context["input"]["sections"])
    sections = presentation.get("sections", [])
    if sections_required and len(sections) < sections_required:
        raise ValueError("The renderer expected more presentation sections than the LLM response returned.")
    sections = sections[:sections_required]
    intro_html = strip_outer_paragraph(presentation["intro_html"])
    cta_text = collapse_spaces(presentation.get("cta_text")) or default_cta_text(context["category"])
    cta_url = context["render"]["cta_url"] or "https://www.etranoulis.gr/"
    lines = [
        '<div class="etr-desc">',
        f'  <h2 style="text-align:center"><span style="font-size:36px"><strong>{product["name"]}</strong></span></h2>',
        "",
        f'  <p style="margin-left:auto; margin-right:auto; text-align:left"><span style="font-size:24px">{intro_html}</span></p>',
        "",
        f'  <div style="margin-bottom:20px; margin-left:auto; margin-right:auto; margin-top:20px; text-align:center"><a href="{cta_url}" style="font-size: 20px; padding: 12px 28px; background-color: #03BABE; color: #F7FCFC; border-radius: 12px; text-decoration: none;">{cta_text}</a></div>',
        "",
        "  <hr />",
        '  <div class="etr-desc">',
    ]
    for index, section in enumerate(sections, start=1):
        wrapper = "etr-sec rev" if index % 2 == 0 else "etr-sec"
        image_url = f"https://www.etranoulis.gr/image/catalog/01_bescos/{model}/besco{index}.jpg"
        image_style = ' style="display:block; margin-left:auto; margin-right:0;"' if index % 2 == 0 else ""
        body_html = strip_outer_paragraph(section["body_html"])
        lines.extend(
            [
                f'    <div class="{wrapper}">',
                '      <div class="etr-text">',
                f'        <h2><span style="font-size:24px"><strong>{section["title"]}</strong></span></h2>',
                f'        <p><span style="font-size:22px">{body_html}</span></p>',
                "      </div>",
                f'      <div class="etr-img"><img alt="{section["title"]}" src="{image_url}"{image_style} /></div>',
                "    </div>",
                "",
            ]
        )
    lines.extend(["  </div>", "</div>"])
    return "\n".join(lines)


def render_chat_output(model: str, filters: list[dict[str, str]]) -> str:
    lines = [f"products/{model}.csv", "", "0) **Φίλτρα**"]
    if not filters:
        lines.extend(["```text", "-", "```"])
        return "\n".join(lines)
    for item in filters:
        lines.extend(
            [
                "```text",
                item["group"],
                "```",
                "```text",
                item["value"],
                "```",
            ]
        )
    return "\n".join(lines)


def build_context_record(
    *,
    model: str,
    url: str,
    photos: int,
    sections: int,
    skroutz_status: int,
    boxnow: int,
    price: str,
) -> dict[str, Any]:
    validate_model(model)
    taxonomy_entries = load_taxonomy_entries()
    filter_map = load_filter_map()
    scraped: dict[str, Any] = {
        "breadcrumbs": [],
        "title": "",
        "meta_description": "",
        "scraped_price": "0",
        "presentation_source_sections": [],
        "technical_specs": [],
    }
    if is_electronet_url(url):
        soup = fetch_soup(url)
        scraped["breadcrumbs"] = extract_breadcrumbs(soup)
        scraped["title"] = extract_title(soup)
        scraped["meta_description"] = extract_meta_description(soup)
        scraped["scraped_price"] = extract_price(soup)
        scraped["presentation_source_sections"] = extract_presentation_blocks(soup)
        scraped["technical_specs"] = extract_technical_specs(soup)
    category = resolve_taxonomy_entry(scraped["breadcrumbs"], taxonomy_entries)
    filter_groups = get_filter_groups(category, filter_map)
    spec_rows = flatten_specs(scraped["technical_specs"])
    auto_filters = infer_filters(filter_groups, spec_rows)
    mpn_hint = detect_mpn(scraped["title"])
    brand_hint = detect_brand(scraped["title"], mpn_hint)
    image, additional_image = build_image_fields(model, photos)
    numeric_price = collapse_spaces(price) or "0"
    if numeric_price == "0" and scraped["scraped_price"] != "0":
        numeric_price = scraped["scraped_price"]
    llm_context = {
        "input": {
            "model": model,
            "url": url,
            "price": numeric_price,
            "photos": photos,
            "sections": sections,
        },
        "source": {
            "domain": urlparse(url).netloc,
            "title": scraped["title"],
            "meta_description": scraped["meta_description"],
            "breadcrumbs": scraped["breadcrumbs"],
        },
        "hints": {
            "brand": brand_hint,
            "mpn": mpn_hint,
            "category": category,
        },
        "key_specs": choose_key_specs(spec_rows),
        "presentation_source_sections": scraped["presentation_source_sections"][: max(sections, 0)],
        "writer_rules": {
            "language": "Greek",
            "sections_required": sections,
            "intro_words": "150-200",
            "intro_html_rule": "Return inner HTML only. Allowed tag: <strong>.",
            "section_body_rule": "Return inner HTML only. Allowed tag: <strong>.",
            "meta_description_rule": "Exactly one sentence.",
            "chat_output_note": "The renderer handles chat output and only shows filters.",
        },
    }
    return {
        "input": {
            "model": model,
            "url": url,
            "photos": photos,
            "sections": sections,
            "skroutz_status": skroutz_status,
            "boxnow": boxnow,
            "price": numeric_price,
        },
        "source": scraped,
        "category": category,
        "filter_groups": filter_groups,
        "auto_filters": auto_filters,
        "render": {
            "category_serialized": category_to_serialized(category, boxnow),
            "cta_url": category.get("cta_url") if category else "https://www.etranoulis.gr/",
            "image": image,
            "additional_image": additional_image,
            "stock_status": DEFAULT_STOCK_STATUS,
        },
        "llm_context": llm_context,
    }


def validate_response_payload(payload: dict[str, Any], expected_sections: int) -> None:
    if "product" not in payload or "presentation" not in payload:
        raise ValueError("LLM response must contain `product` and `presentation` objects.")
    product = payload["product"]
    presentation = payload["presentation"]
    required_product = [
        "brand",
        "mpn",
        "manufacturer",
        "name",
        "seo_keyword",
        "meta_title",
        "meta_description",
        "meta_keywords",
    ]
    for key in required_product:
        if key not in product:
            raise ValueError(f"Missing product field: {key}")
    required_presentation = ["intro_html", "cta_text", "sections"]
    for key in required_presentation:
        if key not in presentation:
            raise ValueError(f"Missing presentation field: {key}")
    if not isinstance(presentation["sections"], list):
        raise ValueError("Presentation `sections` must be a list.")
    if len(presentation["sections"]) != expected_sections:
        raise ValueError(
            f"The LLM response must return exactly {expected_sections} sections, "
            f"received {len(presentation['sections'])}."
        )
    for index, section in enumerate(presentation["sections"], start=1):
        if "title" not in section or "body_html" not in section:
            raise ValueError(f"Missing section fields in section {index}.")


def build_csv_row(context: dict[str, Any], response: dict[str, Any]) -> dict[str, str]:
    product = response["product"]
    description_html = render_description_html(context, response)
    technical_specs_html = render_technical_specs_html(context["source"]["technical_specs"])
    meta_keywords = compact_meta_keywords(product["meta_keywords"])
    return {
        "model": context["input"]["model"],
        "mpn": collapse_spaces(product["mpn"]),
        "name": collapse_spaces(product["name"]),
        "description": description_html,
        "characteristics": technical_specs_html,
        "category": context["render"]["category_serialized"],
        "image": context["render"]["image"],
        "additional_image": context["render"]["additional_image"],
        "manufacturer": collapse_spaces(product["manufacturer"]) or collapse_spaces(product["brand"]),
        "price": context["input"]["price"],
        "quantity": "0",
        "minimum": "1",
        "subtract": "1",
        "stock_status": context["render"]["stock_status"],
        "status": "0",
        "meta_keyword": meta_keywords,
        "meta_title": collapse_spaces(product["meta_title"]),
        "meta_description": collapse_spaces(product["meta_description"]),
        "seo_keyword": collapse_spaces(product["seo_keyword"]),
        "product_url": f'https://www.etranoulis.gr/{collapse_spaces(product["seo_keyword"])}',
        "related_product": "",
        "bestprice_status": "1",
        "skroutz_status": str(context["input"]["skroutz_status"]),
        "boxnow": str(context["input"]["boxnow"]),
    }


def write_csv(path: Path, header: list[str], row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in header})
