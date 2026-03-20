from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class CLIInput:
    model: str
    url: str
    photos: int = 1
    sections: int = 0
    skroutz_status: int = 0
    boxnow: int = 0
    price: str | float | int = 0
    out: str = "out"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    html: str
    status_code: int
    method: str
    fallback_used: bool = False
    response_headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GalleryImage:
    url: str
    alt: str = ""
    position: int = 0
    local_filename: str = ""
    local_path: str = ""
    content_type: str = ""
    downloaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpecItem:
    label: str
    value: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpecSection:
    section: str
    items: list[SpecItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"section": self.section, "items": [item.to_dict() for item in self.items]}


@dataclass(slots=True)
class SourceProductData:
    page_type: str = "product"
    url: str = ""
    canonical_url: str = ""
    breadcrumbs: list[str] = field(default_factory=list)
    product_code: str = ""
    brand: str = ""
    name: str = ""
    hero_summary: str = ""
    price_text: str = ""
    price_value: Optional[float] = None
    installments_text: str = ""
    delivery_text: str = ""
    pickup_text: str = ""
    gallery_images: list[GalleryImage] = field(default_factory=list)
    besco_images: list[GalleryImage] = field(default_factory=list)
    energy_label_asset_url: str = ""
    product_sheet_asset_url: str = ""
    key_specs: list[SpecItem] = field(default_factory=list)
    spec_sections: list[SpecSection] = field(default_factory=list)
    presentation_source_html: str = ""
    presentation_source_text: str = ""
    raw_html_path: str = ""
    scraped_at: str = ""
    fallback_used: bool = False
    mpn: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_type": self.page_type,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "breadcrumbs": self.breadcrumbs,
            "product_code": self.product_code,
            "brand": self.brand,
            "name": self.name,
            "hero_summary": self.hero_summary,
            "price_text": self.price_text,
            "price_value": self.price_value,
            "installments_text": self.installments_text,
            "delivery_text": self.delivery_text,
            "pickup_text": self.pickup_text,
            "gallery_images": [img.to_dict() for img in self.gallery_images],
            "besco_images": [img.to_dict() for img in self.besco_images],
            "energy_label_asset_url": self.energy_label_asset_url,
            "product_sheet_asset_url": self.product_sheet_asset_url,
            "key_specs": [item.to_dict() for item in self.key_specs],
            "spec_sections": [section.to_dict() for section in self.spec_sections],
            "presentation_source_html": self.presentation_source_html,
            "presentation_source_text": self.presentation_source_text,
            "raw_html_path": self.raw_html_path,
            "scraped_at": self.scraped_at,
            "fallback_used": self.fallback_used,
            "mpn": self.mpn,
        }


@dataclass(slots=True)
class ParsedProduct:
    source: SourceProductData
    provenance: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    critical_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "provenance": self.provenance,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "critical_missing": self.critical_missing,
        }


@dataclass(slots=True)
class TaxonomyResolution:
    parent_category: str = ""
    leaf_category: str = ""
    sub_category: Optional[str] = None
    taxonomy_path: str = ""
    cta_url: str = ""
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchemaMatchResult:
    matched_schema_id: Optional[str] = None
    matched_sub_category: Optional[str] = None
    score: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
