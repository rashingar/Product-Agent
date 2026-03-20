from __future__ import annotations

from html import escape

from bs4 import BeautifulSoup, Tag

from .models import SpecSection
from .normalize import make_absolute_url, normalize_whitespace, split_visible_lines



def build_characteristics_html(spec_sections: list[SpecSection]) -> str:
    if not spec_sections:
        return ""
    parts = ["<div class=\"product-specs\">"]
    for section in spec_sections:
        parts.append("<div class=\"product-specs-section\">")
        parts.append(f"<h3>{escape(section.section)}</h3>")
        parts.append("<table>")
        for item in section.items:
            value = "" if item.value is None else escape(item.value)
            parts.append(f"<tr><th>{escape(item.label)}</th><td>{value}</td></tr>")
        parts.append("</table>")
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)



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

    cta_text = f"Δείτε περισσότερα {cta_label} εδώ" if cta_label else "Δείτε περισσότερα εδώ"
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
