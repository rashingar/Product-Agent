from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .models import FetchResult, GalleryImage
from .utils import ensure_directory, guess_extension, write_bytes

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 ElectronetSingleImport/0.1"
)
CRAWL_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class RobotsDisallowedError(FetchError):
    pass


class ElectronetFetcher:
    def __init__(self, user_agent: str = USER_AGENT, timeout: httpx.Timeout = CRAWL_TIMEOUT) -> None:
        self.user_agent = user_agent
        self.timeout = timeout

    def _robots_allowed(self, url: str) -> tuple[bool, str]:
        parts = urlsplit(url)
        robots_url = urljoin(f"{parts.scheme}://{parts.netloc}", "/robots.txt")
        parser = RobotFileParser()
        try:
            with httpx.Client(timeout=self.timeout, headers={"User-Agent": self.user_agent}, follow_redirects=True) as client:
                response = client.get(robots_url)
                if response.status_code >= 400 or not response.text.strip():
                    return True, "robots_unavailable"
                parser.parse(response.text.splitlines())
                return parser.can_fetch(self.user_agent, url), robots_url
        except Exception:
            return True, "robots_unavailable"

    def _base_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }

    def fetch_httpx(self, url: str) -> FetchResult:
        allowed, robots_info = self._robots_allowed(url)
        if not allowed:
            raise RobotsDisallowedError(f"Robots.txt disallows scraping for: {url}")

        last_error: Exception | None = None
        for attempt in range(1, 5):
            time.sleep(random.uniform(0.15, 0.55))
            try:
                with httpx.Client(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=self._base_headers(),
                ) as client:
                    response = client.get(url)
                if response.status_code in RETRYABLE_STATUS:
                    last_error = FetchError(f"HTTP {response.status_code} for {url}")
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0.0, 0.35))
                    continue
                response.raise_for_status()
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    html=response.text,
                    status_code=response.status_code,
                    method="httpx",
                    fallback_used=False,
                    response_headers={**dict(response.headers), "x-robots-source": robots_info},
                )
            except Exception as exc:
                last_error = exc
                if attempt < 4:
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0.0, 0.35))
        raise FetchError(f"HTTP fetch failed for {url}: {last_error}")

    def fetch_playwright(self, url: str) -> FetchResult:
        allowed, robots_info = self._robots_allowed(url)
        if not allowed:
            raise RobotsDisallowedError(f"Robots.txt disallows scraping for: {url}")
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - import path is environment-dependent
            raise FetchError(f"Playwright is not available: {exc}") from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.user_agent, locale="el-GR")
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_load_state("networkidle", timeout=15000)
                html = page.content()
                final_url = page.url
                browser.close()
            return FetchResult(
                url=url,
                final_url=final_url,
                html=html,
                status_code=200,
                method="playwright",
                fallback_used=True,
                response_headers={"x-robots-source": robots_info},
            )
        except Exception as exc:
            raise FetchError(f"Playwright fetch failed for {url}: {exc}") from exc

    def fetch_binary(self, url: str) -> tuple[bytes, str]:
        allowed, _ = self._robots_allowed(url)
        if not allowed:
            raise RobotsDisallowedError(f"Robots.txt disallows scraping for: {url}")

        last_error: Exception | None = None
        for attempt in range(1, 5):
            time.sleep(random.uniform(0.10, 0.30))
            try:
                with httpx.Client(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers={**self._base_headers(), "Accept": "image/*,*/*;q=0.8"},
                ) as client:
                    response = client.get(url)
                if response.status_code in RETRYABLE_STATUS:
                    last_error = FetchError(f"HTTP {response.status_code} for {url}")
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0.0, 0.25))
                    continue
                response.raise_for_status()
                return response.content, response.headers.get("content-type", "")
            except Exception as exc:
                last_error = exc
                if attempt < 4:
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0.0, 0.25))
        raise FetchError(f"Binary fetch failed for {url}: {last_error}")

    def download_gallery_images(
        self,
        images: list[GalleryImage],
        model: str,
        output_dir: str | Path,
        requested_photos: int | None = None,
    ) -> tuple[list[GalleryImage], list[str], list[str]]:
        return self._download_images(
            images=images,
            output_dir=output_dir,
            output_subdir="gallery",
            requested_count=requested_photos,
            shortage_warning="gallery_images_less_than_requested_photos",
            non_jpg_warning_prefix="gallery_image_non_jpg_saved",
            filename_builder=lambda position, ext: f"{model}-{position}{ext}",
        )

    def download_besco_images(
        self,
        images: list[GalleryImage],
        output_dir: str | Path,
        requested_sections: int | None = None,
    ) -> tuple[list[GalleryImage], list[str], list[str]]:
        return self._download_images(
            images=images,
            output_dir=output_dir,
            output_subdir="bescos",
            requested_count=requested_sections,
            shortage_warning="besco_images_less_than_requested_sections",
            non_jpg_warning_prefix="besco_image_non_jpg_saved",
            filename_builder=lambda position, ext: f"besco{position}{ext}",
        )

    def _download_images(
        self,
        images: list[GalleryImage],
        output_dir: str | Path,
        output_subdir: str,
        requested_count: int | None,
        shortage_warning: str,
        non_jpg_warning_prefix: str,
        filename_builder: Callable[[int, str], str],
    ) -> tuple[list[GalleryImage], list[str], list[str]]:
        target_dir = ensure_directory(Path(output_dir) / output_subdir)
        selected = images
        if requested_count is not None and requested_count > 0:
            selected = images[:requested_count]

        warnings: list[str] = []
        written_files: list[str] = []
        downloaded: list[GalleryImage] = []

        if requested_count and len(images) < requested_count:
            warnings.append(shortage_warning)

        for fallback_position, image in enumerate(selected, start=1):
            asset_position = image.position if image.position > 0 else fallback_position
            payload, content_type = self.fetch_binary(image.url)
            ext = guess_extension(content_type, image.url)
            if ext != ".jpg":
                warnings.append(f"{non_jpg_warning_prefix}:{asset_position}:{ext}")
            filename = filename_builder(asset_position, ext)
            local_path = target_dir / filename
            write_bytes(local_path, payload)
            downloaded_image = GalleryImage(
                url=image.url,
                alt=image.alt,
                position=asset_position,
                local_filename=filename,
                local_path=str(local_path),
                content_type=content_type,
                downloaded=True,
            )
            downloaded.append(downloaded_image)
            written_files.append(str(local_path))
        return downloaded, warnings, written_files
