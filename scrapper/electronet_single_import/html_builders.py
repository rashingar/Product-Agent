from __future__ import annotations

import re
from html import escape

from bs4 import BeautifulSoup, Tag

from .models import SpecSection
from .normalize import make_absolute_url, normalize_for_match, normalize_whitespace, split_visible_lines


def default_cta_text(cta_label: str) -> str:
    label = normalize_whitespace(cta_label)
    return f"Δείτε περισσότερα {label} εδώ" if label else "Δείτε περισσότερα εδώ"


def resolve_cta_text(cta_text: str, cta_label: str) -> str:
    normalized = normalize_whitespace(cta_text)
    if not normalized:
        return default_cta_text(cta_label)
    generic_values = {
        normalize_for_match("Δείτε περισσότερα"),
        normalize_for_match("Δείτε περισσότερα εδώ"),
    }
    if normalize_for_match(normalized) in generic_values:
        return default_cta_text(cta_label)
    return normalized



def build_characteristics_html(spec_sections: list[SpecSection]) -> str:
    if not spec_sections:
        return ""
    parts = ['<table class="table table-bordered">']
    for section in spec_sections:
        parts.append("<thead>")
        parts.append("<tr>")
        parts.append(f'<td colspan="2"><strong>{escape(section.section)}</strong></td>')
        parts.append("</tr>")
        parts.append("</thead>")
        parts.append("<tbody>")
        for item in section.items:
            label = escape(_normalize_characteristics_label(item.label))
            value = escape(_normalize_characteristics_value(item.label, item.value))
            parts.append("<tr>")
            parts.append(f"<td>{label}</td>")
            parts.append(f'<td style="text-align:right;"><strong>{value}</strong></td>')
            parts.append("</tr>")
        parts.append("</tbody>")
    parts.append("</table>")
    return "".join(parts)


def _normalize_characteristics_label(label: str) -> str:
    normalized = normalize_whitespace(label)
    if normalized.startswith("Υψος "):
        return normalized.replace("Υψος ", "Ύψος ", 1)
    return normalized


def _normalize_characteristics_value(label: str, value: str | None) -> str:
    normalized = normalize_whitespace(value)
    if not normalized:
        return "-"
    label_key = normalize_for_match(label)
    if label_key == normalize_for_match("Επιπλέον Χαρακτηριστικά") and ("," in normalized or len(normalized.split()) > 3):
        return "-"
    if "σε εκατοστα" in label_key and re.fullmatch(r"\d+(?:[.,]\d+)?", normalized):
        numeric = float(normalized.replace(",", "."))
        return f"{numeric:.2f}"
    return re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " × ", normalized)



def build_description_html(
    product_name: str,
    hero_summary: str,
    presentation_source_html: str,
    presentation_source_text: str,
    model: str,
    sections_requested: int,
    cta_url: str,
    cta_label: str,
    besco_filenames_by_section: dict[int, str] | None = None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not product_name:
        return "", ["description_not_built_from_source"]
    if not cta_url:
        return "", ["description_not_built_from_source", "cta_url_unresolved"]

    intro = normalize_whitespace(hero_summary)
    blocks = extract_presentation_blocks(presentation_source_html, presentation_source_text)
    if not intro and blocks:
        intro = blocks[0]["paragraph"]
    if not intro:
        return "", ["description_not_built_from_source"]

    selected_blocks = []
    if sections_requested > 0:
        selected_blocks = blocks[:sections_requested]
        if not selected_blocks:
            return "", ["description_not_built_from_source"]
        if len(selected_blocks) < sections_requested:
            warnings.append("requested_sections_exceed_source_sections")
    use_besco_asset_map = besco_filenames_by_section is not None
    besco_filenames_by_section = besco_filenames_by_section or {}

    cta_text = default_cta_text(cta_label)
    out = ['<div class="etr-desc">']
    out.append(f'<h2 style="text-align:center"><span style="font-size:36px"><strong>{escape(product_name)}</strong></span></h2>')
    out.append('')
    out.append('<p style="margin-left:auto; margin-right:auto; text-align:left"><span style="font-size:24px">')
    out.append(escape(intro))
    out.append('</span></p>')
    out.append('')
    out.append('<div style="margin-bottom:20px; margin-left:auto; margin-right:auto; margin-top:20px; text-align:center">')
    out.append(
        f'<a href="{escape(cta_url, quote=True)}" style="font-size: 20px; padding: 12px 28px; background-color: #03BABE; color: #F7FCFC; border-radius: 12px; text-decoration: none;">{escape(cta_text)}</a>'
    )
    out.append('</div>')
    out.append('')
    out.append('<hr />')
    out.append('<div class="etr-desc">')
    out.append('')

    for idx, block in enumerate(selected_blocks, start=1):
        cls = 'etr-sec rev' if idx % 2 == 0 else 'etr-sec'
        out.append(f'  <!-- SECTION {idx} -->')
        out.append(f'  <div class="{cls}">')
        out.append('    <div class="etr-text">')
        out.append(f'      <h2><span style="font-size:24px"><strong>{escape(block["title"])}</strong></span></h2>')
        out.append(f'      <p><span style="font-size:22px">{escape(block["paragraph"])}</span></p>')
        out.append('    </div>')
        default_besco_filename = f"besco{idx}.jpg"
        besco_filename = besco_filenames_by_section.get(idx, "" if use_besco_asset_map else default_besco_filename)
        if besco_filename:
            out.append('    <div class="etr-img">')
            img_style = ' style="display:block; margin-left:auto; margin-right:0;"' if idx % 2 == 0 else ''
            out.append(
                f'      <img alt="{escape(block["title"], quote=True)}" src="https://www.etranoulis.gr/image/catalog/01_bescos/{escape(model, quote=True)}/{escape(besco_filename, quote=True)}"{img_style} />'
            )
            out.append('    </div>')
        out.append('  </div>')
        out.append('')

    out.append('</div>')
    out.append('</div>')
    return "\n".join(out), warnings


def build_description_html_from_llm(
    product_name: str,
    model: str,
    cta_url: str,
    cta_label: str,
    intro_html: str,
    cta_text: str,
    sections: list[dict[str, str]],
    besco_filenames_by_section: dict[int, str] | None = None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not product_name:
        return "", ["description_not_built_from_llm"]
    if not cta_url:
        return "", ["description_not_built_from_llm", "cta_url_unresolved"]
    if not normalize_whitespace(intro_html):
        return "", ["description_not_built_from_llm", "llm_intro_missing"]

    use_besco_asset_map = besco_filenames_by_section is not None
    besco_filenames_by_section = besco_filenames_by_section or {}
    out = ['<div class="etr-desc">']
    out.append(f'<h2 style="text-align:center"><span style="font-size:36px"><strong>{escape(product_name)}</strong></span></h2>')
    out.append("")
    out.append('<p style="margin-left:auto; margin-right:auto; text-align:left"><span style="font-size:24px">')
    out.append(intro_html.strip())
    out.append("</span></p>")
    out.append("")
    out.append('<div style="margin-bottom:20px; margin-left:auto; margin-right:auto; margin-top:20px; text-align:center">')
    out.append(
        f'<a href="{escape(cta_url, quote=True)}" style="font-size: 20px; padding: 12px 28px; background-color: #03BABE; color: #F7FCFC; border-radius: 12px; text-decoration: none;">{escape(resolve_cta_text(cta_text, cta_label))}</a>'
    )
    out.append("</div>")
    out.append("")
    out.append("<hr />")
    out.append('<div class="etr-desc">')
    out.append("")

    for idx, block in enumerate(sections, start=1):
        title = normalize_whitespace(block.get("title"))
        body_html = (block.get("body_html") or "").strip()
        if not title or not normalize_whitespace(body_html):
            warnings.append(f"llm_section_incomplete:{idx}")
            continue
        cls = 'etr-sec rev' if idx % 2 == 0 else 'etr-sec'
        out.append(f'  <!-- SECTION {idx} -->')
        out.append(f'  <div class="{cls}">')
        out.append('    <div class="etr-text">')
        out.append(f'      <h2><span style="font-size:24px"><strong>{escape(title)}</strong></span></h2>')
        out.append(f'      <p><span style="font-size:22px">{body_html}</span></p>')
        out.append('    </div>')
        default_besco_filename = f"besco{idx}.jpg"
        besco_filename = besco_filenames_by_section.get(idx, "" if use_besco_asset_map else default_besco_filename)
        if besco_filename:
            out.append('    <div class="etr-img">')
            img_style = ' style="display:block; margin-left:auto; margin-right:0;"' if idx % 2 == 0 else ''
            out.append(
                f'      <img alt="{escape(title, quote=True)}" src="https://www.etranoulis.gr/image/catalog/01_bescos/{escape(model, quote=True)}/{escape(besco_filename, quote=True)}"{img_style} />'
            )
            out.append("    </div>")
        out.append("  </div>")
        out.append("")

    out.append("</div>")
    out.append("</div>")
    return "\n".join(out), warnings


def extract_presentation_blocks(
    presentation_source_html: str,
    presentation_source_text: str,
    base_url: str = "",
) -> list[dict[str, str]]:
    blocks = _blocks_from_html(presentation_source_html, base_url)
    if blocks:
        return blocks
    return _blocks_from_text(presentation_source_text)



def _blocks_from_html(source_html: str, base_url: str = "") -> list[dict[str, str]]:
    if not source_html.strip():
        return []
    soup = BeautifulSoup(source_html, "lxml")
    container_blocks = _blocks_from_html_containers(soup, base_url)
    if container_blocks:
        return container_blocks
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "img"]):
        if not isinstance(node, Tag):
            continue
        if node.name.startswith("h"):
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if not text:
                continue
            if current and current.get("title") and current.get("paragraph"):
                blocks.append(current)
            current = {"title": text, "paragraph": "", "image_url": ""}
        elif node.name == "p" and current is not None:
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if not text:
                continue
            current["paragraph"] = f"{current['paragraph']} {text}".strip()
        elif node.name == "img" and current is not None and not current.get("image_url"):
            src = node.get("src") or node.get("data-src") or node.get("data-original")
            image_url = make_absolute_url(src, base_url) if src else ""
            if image_url:
                current["image_url"] = image_url
    if current and current.get("title") and current.get("paragraph"):
        blocks.append(current)
    return blocks


def _blocks_from_html_containers(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for container in soup.select(".ck-text.inline"):
        if not isinstance(container, Tag):
            continue
        title = _select_presentation_title(container)
        paragraphs = [normalize_whitespace(node.get_text(" ", strip=True)) for node in container.find_all("p")]
        paragraph = normalize_whitespace(" ".join(text for text in paragraphs if text))
        image_node = container.find("img")
        src = ""
        if isinstance(image_node, Tag):
            src = image_node.get("src") or image_node.get("data-src") or image_node.get("data-original") or ""
        image_url = make_absolute_url(src, base_url) if src else ""
        if title and paragraph:
            blocks.append({"title": title, "paragraph": paragraph, "image_url": image_url})
    return blocks


def _select_presentation_title(container: Tag) -> str:
    for tag_name in ["h3", "h4", "h2", "h1"]:
        for node in container.find_all(tag_name):
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if text:
                return text
    return ""



def _blocks_from_text(source_text: str) -> list[dict[str, str]]:
    lines = split_visible_lines(source_text)
    if not lines:
        return []
    blocks: list[dict[str, str]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.isupper() or (len(line) < 90 and idx + 1 < len(lines) and len(lines[idx + 1]) > 20):
            title = line
            idx += 1
            paragraphs: list[str] = []
            while idx < len(lines) and not lines[idx].isupper() and len(lines[idx]) > 10:
                paragraphs.append(lines[idx])
                idx += 1
            paragraph = normalize_whitespace(" ".join(paragraphs))
            if title and paragraph:
                blocks.append({"title": title.title() if title.isupper() else title, "paragraph": paragraph, "image_url": ""})
            continue
        idx += 1
    return blocks
