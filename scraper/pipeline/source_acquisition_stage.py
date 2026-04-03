from __future__ import annotations

from pathlib import Path
from typing import Callable

from .fetcher import ElectronetFetcher, FetchError
from .models import CLIInput, GalleryImage, SourceProductData
from .prepare_provider_resolution import PrepareProviderResolutionResult, resolve_prepare_provider_resolution
from .source_acquisition_models import SourceAcquisitionResult
from .source_detection import validate_url_scope
from .utils import ensure_directory


def execute_source_acquisition_stage(
    *,
    model: str,
    url: str,
    photos: int,
    model_dir: Path,
    validate_url_scope_fn: Callable[[str], tuple[str, bool, str]] = validate_url_scope,
    fetcher_factory: Callable[[], ElectronetFetcher] = ElectronetFetcher,
    resolve_prepare_provider_input_fn: Callable[..., PrepareProviderResolutionResult] = resolve_prepare_provider_resolution,
) -> SourceAcquisitionResult:
    resolved_model_dir = ensure_directory(model_dir)
    fetcher = fetcher_factory()
    provider_resolution = resolve_prepare_provider_input_fn(
        CLIInput(
            model=model,
            url=url,
            photos=max(int(photos), 0),
            sections=0,
            skroutz_status=0,
            boxnow=0,
            price=0,
            out=str(resolved_model_dir),
        ),
        validate_url_scope_fn=validate_url_scope_fn,
        fetcher_factory=lambda: fetcher,
    )
    fetch = provider_resolution.fetch
    parsed = provider_resolution.parsed
    extracted_gallery_count = len(parsed.source.gallery_images)
    gallery_images_for_download = _inject_energy_label_into_gallery(parsed.source)
    requested_gallery_photos = _resolve_requested_gallery_photos(photos, parsed.source)
    gallery_warnings: list[str] = []
    gallery_files: list[str] = []
    downloaded_gallery: list[GalleryImage] = []
    if gallery_images_for_download:
        try:
            downloaded_gallery, gallery_warnings, gallery_files = fetcher.download_gallery_images(
                images=gallery_images_for_download,
                model=model,
                output_dir=resolved_model_dir,
                requested_photos=requested_gallery_photos,
            )
            if downloaded_gallery:
                parsed.source.gallery_images = downloaded_gallery
        except FetchError as exc:
            gallery_warnings.append(f"gallery_download_failed:{exc}")

    return SourceAcquisitionResult(
        model_dir=resolved_model_dir,
        source=provider_resolution.source,
        provider_id=provider_resolution.provider_id,
        fetch=fetch,
        parsed=parsed,
        extracted_gallery_count=extracted_gallery_count,
        requested_gallery_photos=requested_gallery_photos,
        downloaded_gallery=downloaded_gallery,
        gallery_warnings=gallery_warnings,
        gallery_files=gallery_files,
        snapshot_provenance={
            "requested_url": fetch.url,
            "detected_source": provider_resolution.source,
            "provider_id": provider_resolution.provider_id,
            "final_url": fetch.final_url,
            "status_code": fetch.status_code,
            "fetch_method": fetch.method,
            "fallback_used": fetch.fallback_used,
            "response_headers": dict(fetch.response_headers),
            "gallery_requested_photos": requested_gallery_photos,
            "gallery_downloaded_count": len(downloaded_gallery),
        },
    )


def _inject_energy_label_into_gallery(source: SourceProductData) -> list[GalleryImage]:
    gallery_images = list(getattr(source, "gallery_images", []) or [])
    energy_label_asset_url = str(getattr(source, "energy_label_asset_url", "") or "").strip()
    if not gallery_images or not energy_label_asset_url:
        return gallery_images

    primary_image = gallery_images[0]
    remaining_images = gallery_images[1:]
    injected_images = [
        GalleryImage(
            url=primary_image.url,
            alt=primary_image.alt,
            position=1,
        ),
        GalleryImage(
            url=energy_label_asset_url,
            alt="Energy Label",
            position=2,
        ),
    ]
    for index, image in enumerate(remaining_images, start=3):
        injected_images.append(
            GalleryImage(
                url=image.url,
                alt=image.alt,
                position=index,
            )
        )
    return injected_images


def _resolve_requested_gallery_photos(requested_photos: int, source: SourceProductData) -> int:
    requested = max(int(requested_photos), 0)
    if requested <= 0:
        return requested
    if not str(source.energy_label_asset_url or "").strip():
        return requested
    return requested + 1
