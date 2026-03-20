from __future__ import annotations

import re
import unicodedata
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

NBSP_PATTERN = re.compile(r"[\u00A0\u202F\u2007]")
WS_PATTERN = re.compile(r"\s+")
DASH_NULLS = {"", "-", "–", "—", "−"}

_GREEK_TRANSLIT = {
    "α": "a",
    "β": "v",
    "γ": "g",
    "δ": "d",
    "ε": "e",
    "ζ": "z",
    "η": "i",
    "θ": "th",
    "ι": "i",
    "κ": "k",
    "λ": "l",
    "μ": "m",
    "ν": "n",
    "ξ": "x",
    "ο": "o",
    "π": "p",
    "ρ": "r",
    "σ": "s",
    "ς": "s",
    "τ": "t",
    "υ": "y",
    "φ": "f",
    "χ": "ch",
    "ψ": "ps",
    "ω": "o",
}


def strip_nbsp(text: str | None) -> str:
    if text is None:
        return ""
    return NBSP_PATTERN.sub(" ", unescape(str(text)))



def normalize_whitespace(text: str | None) -> str:
    return WS_PATTERN.sub(" ", strip_nbsp(text)).strip()



def safe_text(node: object) -> str:
    if node is None:
        return ""
    if hasattr(node, "get_text"):
        return normalize_whitespace(node.get_text(" ", strip=True))
    return normalize_whitespace(str(node))



def make_absolute_url(url: str | None, base: str) -> str:
    if not url:
        return ""
    return urljoin(base, url)



def parse_euro_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned_text = strip_nbsp(text)
    candidates = re.findall(r"(?:\d{1,3}(?:[.\s]\d{3})*|\d+)(?:,\d{1,2})?\s*€?", cleaned_text)
    if not candidates:
        return None
    for candidate in reversed(candidates):
        numeric = re.sub(r"[^0-9,.-]", "", candidate)
        if not numeric:
            continue
        if "," in numeric:
            numeric = numeric.replace(".", "").replace(",", ".")
        else:
            parts = numeric.split(".")
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
                numeric = "".join(parts)
        try:
            return float(numeric)
        except ValueError:
            continue
    return None



def nullify_dash_values(value: str | None) -> str | None:
    normalized = normalize_whitespace(value)
    return None if normalized in DASH_NULLS else normalized



def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")



def normalize_for_match(text: str | None) -> str:
    text = normalize_whitespace(text)
    if not text:
        return ""
    text = _strip_accents(text).lower()
    text = text.replace("&", " και ")
    text = re.sub(r"[^a-z0-9α-ω\s]+", " ", text, flags=re.IGNORECASE)
    return normalize_whitespace(text)



def slugify_greek_for_seo(text: str | None) -> str:
    text = normalize_whitespace(text)
    if not text:
        return ""
    text = _strip_accents(text).lower()
    text = text.replace("ου", "ou")
    text = re.sub(r"(?<=\d)[.,](?=\d)", "", text)
    chars: list[str] = []
    for ch in text:
        if ch in _GREEK_TRANSLIT:
            chars.append(_GREEK_TRANSLIT[ch])
        elif ch.isalnum():
            chars.append(ch)
        else:
            chars.append("-")
    slug = "".join(chars)
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug



def dedupe_urls_preserve_order(urls: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        url = normalize_whitespace(raw)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out



def clean_breadcrumbs(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    previous = None
    for item in items:
        value = normalize_whitespace(item)
        if not value:
            continue
        if value == previous:
            continue
        cleaned.append(value)
        previous = value
    return cleaned



def split_visible_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines = [normalize_whitespace(line) for line in strip_nbsp(text).splitlines()]
    return [line for line in lines if line]
