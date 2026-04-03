from __future__ import annotations

from pathlib import Path

from pipeline.fetcher import FetchError
from pipeline.models import FetchResult, GalleryImage, ParsedProduct, SourceProductData
from pipeline.prepare_provider_resolution import PrepareProviderResolutionResult
from pipeline.source_acquisition_stage import execute_source_acquisition_stage


def _build_provider_resolution_result(
    *,
    source: str,
    provider_id: str,
    url: str,
    parsed: ParsedProduct,
    response_headers: dict[str, str] | None = None,
) -> PrepareProviderResolutionResult:
    return PrepareProviderResolutionResult(
        source=source,
        provider_id=provider_id,
        fetch=FetchResult(
            url=url,
            final_url=url,
            html="<html></html>",
            status_code=200,
            method="fixture",
            fallback_used=False,
            response_headers=response_headers or {"content-type": "text/html"},
        ),
        parsed=parsed,
    )


class RecordingFetcher:
    def __init__(
        self,
        *,
        gallery_result: tuple[list[GalleryImage], list[str], list[str]] | None = None,
        gallery_error: Exception | None = None,
    ) -> None:
        self.gallery_result = gallery_result or ([], [], [])
        self.gallery_error = gallery_error
        self.gallery_download_calls: list[dict[str, object]] = []

    def download_gallery_images(self, **kwargs):
        self.gallery_download_calls.append(kwargs)
        if self.gallery_error is not None:
            raise self.gallery_error
        return self.gallery_result


def test_execute_source_acquisition_stage_returns_acquisition_owned_fields_only(tmp_path: Path) -> None:
    model = "233541"
    url = "https://www.electronet.gr/example"
    source = SourceProductData(
        source_name="electronet",
        page_type="product",
        url=url,
        canonical_url=url,
        product_code=model,
        brand="LG",
        mpn="GSGV80PYLL",
        name="LG GSGV80PYLL",
        gallery_images=[
            GalleryImage(url="https://cdn.example/main.jpg", alt="main", position=1),
            GalleryImage(url="https://cdn.example/second.jpg", alt="second", position=2),
        ],
        energy_label_asset_url="https://eprel.ec.europa.eu/labels/example.png",
    )
    parsed = ParsedProduct(source=source)
    downloaded_gallery = [
        GalleryImage(
            url="https://cdn.example/main.jpg",
            alt="main",
            position=1,
            local_filename=f"{model}-1.jpg",
            local_path=str(tmp_path / model / "gallery" / f"{model}-1.jpg"),
            downloaded=True,
        ),
        GalleryImage(
            url="https://eprel.ec.europa.eu/labels/example.png",
            alt="Energy Label",
            position=2,
            local_filename=f"{model}-2.jpg",
            local_path=str(tmp_path / model / "gallery" / f"{model}-2.jpg"),
            downloaded=True,
        ),
        GalleryImage(
            url="https://cdn.example/second.jpg",
            alt="second",
            position=3,
            local_filename=f"{model}-3.jpg",
            local_path=str(tmp_path / model / "gallery" / f"{model}-3.jpg"),
            downloaded=True,
        ),
    ]
    fetcher = RecordingFetcher(gallery_result=(downloaded_gallery, ["gallery_warning"], ["gallery/file1.jpg"]))
    provider_calls: list[tuple[object, dict[str, object]]] = []

    def fake_resolve_prepare_provider_input(cli, **kwargs):
        provider_calls.append((cli, kwargs))
        return _build_provider_resolution_result(
            source="electronet",
            provider_id="electronet",
            url=cli.url,
            parsed=parsed,
            response_headers={"content-type": "text/html", "x-test": "1"},
        )

    result = execute_source_acquisition_stage(
        model=model,
        url=url,
        photos=2,
        model_dir=tmp_path / model,
        validate_url_scope_fn=lambda _url: ("electronet", True, "electronet_domain"),
        fetcher_factory=lambda: fetcher,
        resolve_prepare_provider_input_fn=fake_resolve_prepare_provider_input,
    )

    assert provider_calls and provider_calls[0][0].model == model
    assert provider_calls[0][0].url == url
    assert provider_calls[0][0].photos == 2
    assert provider_calls[0][0].sections == 0
    assert provider_calls[0][1]["fetcher_factory"]() is fetcher
    assert not hasattr(result, "cli")
    assert result.model_dir == tmp_path / model
    assert result.source == "electronet"
    assert result.provider_id == "electronet"
    assert result.parsed is parsed
    assert result.extracted_gallery_count == 2
    assert result.requested_gallery_photos == 3
    assert result.downloaded_gallery == downloaded_gallery
    assert result.gallery_warnings == ["gallery_warning"]
    assert result.gallery_files == ["gallery/file1.jpg"]
    assert result.parsed.source.gallery_images == downloaded_gallery
    assert len(fetcher.gallery_download_calls) == 1
    assert fetcher.gallery_download_calls[0]["requested_photos"] == 3
    assert [item.position for item in fetcher.gallery_download_calls[0]["images"]] == [1, 2, 3]
    assert [item.url for item in fetcher.gallery_download_calls[0]["images"]] == [
        "https://cdn.example/main.jpg",
        "https://eprel.ec.europa.eu/labels/example.png",
        "https://cdn.example/second.jpg",
    ]
    assert result.snapshot_provenance == {
        "requested_url": url,
        "detected_source": "electronet",
        "provider_id": "electronet",
        "final_url": url,
        "status_code": 200,
        "fetch_method": "fixture",
        "fallback_used": False,
        "response_headers": {"content-type": "text/html", "x-test": "1"},
        "gallery_requested_photos": 3,
        "gallery_downloaded_count": 3,
    }


def test_execute_source_acquisition_stage_keeps_gallery_failure_as_warning_only(tmp_path: Path) -> None:
    model = "233541"
    url = "https://www.electronet.gr/example"
    original_gallery = [GalleryImage(url="https://cdn.example/main.jpg", alt="main", position=1)]
    parsed = ParsedProduct(
        source=SourceProductData(
            source_name="electronet",
            page_type="product",
            url=url,
            canonical_url=url,
            product_code=model,
            brand="LG",
            mpn="GSGV80PYLL",
            name="LG GSGV80PYLL",
            gallery_images=list(original_gallery),
        )
    )
    fetcher = RecordingFetcher(gallery_error=FetchError("gallery exploded"))

    result = execute_source_acquisition_stage(
        model=model,
        url=url,
        photos=1,
        model_dir=tmp_path / model,
        validate_url_scope_fn=lambda _url: ("electronet", True, "electronet_domain"),
        fetcher_factory=lambda: fetcher,
        resolve_prepare_provider_input_fn=lambda cli, **_kwargs: _build_provider_resolution_result(
            source="electronet",
            provider_id="electronet",
            url=cli.url,
            parsed=parsed,
        ),
    )

    assert result.downloaded_gallery == []
    assert result.gallery_files == []
    assert result.gallery_warnings == ["gallery_download_failed:gallery exploded"]
    assert result.extracted_gallery_count == 1
    assert result.requested_gallery_photos == 1
    assert result.parsed.source.gallery_images == original_gallery
    assert result.snapshot_provenance["gallery_downloaded_count"] == 0
