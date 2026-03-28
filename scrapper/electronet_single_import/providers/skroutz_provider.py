from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ..parser_product_skroutz import SkroutzProductParser
from .base import ProductProvider, ProviderError
from .models import (
    ProviderCapability,
    ProviderDefinition,
    ProviderErrorCode,
    ProviderInputIdentity,
    ProviderKind,
    ProviderResult,
    ProviderSnapshot,
    ProviderSnapshotKind,
    ProviderStage,
)


class SkroutzProvider(ProductProvider):
    definition = ProviderDefinition(
        provider_id="skroutz",
        source_name="skroutz",
        kind=ProviderKind.FIXTURE,
        capabilities=frozenset(
            {
                ProviderCapability.URL_INPUT,
                ProviderCapability.FIXTURE_FETCH,
                ProviderCapability.HTML_SNAPSHOT,
                ProviderCapability.NORMALIZED_PRODUCT,
            }
        ),
        display_name="Skroutz",
        description="Fixture-backed Skroutz provider adapter for deterministic tests.",
    )

    def __init__(
        self,
        *,
        fixture_html_by_url: Mapping[str, Path] | None = None,
        parser: SkroutzProductParser | None = None,
    ) -> None:
        self._fixture_html_by_url = {url: Path(path) for url, path in (fixture_html_by_url or {}).items()}
        self._parser = parser or SkroutzProductParser()

    def supports_identity(self, identity: ProviderInputIdentity) -> bool:
        return bool(identity.url.strip()) and identity.url.strip() in self._fixture_html_by_url

    def fetch_snapshot(self, identity: ProviderInputIdentity) -> ProviderSnapshot:
        url = identity.url.strip()
        if not url:
            raise ProviderError.build(
                provider_id=self.provider_id,
                code=ProviderErrorCode.UNSUPPORTED_IDENTITY,
                stage=ProviderStage.IDENTITY,
                message="Skroutz provider requires a URL identity",
            )

        fixture_path = self._fixture_html_by_url.get(url)
        if fixture_path is None:
            raise ProviderError.build(
                provider_id=self.provider_id,
                code=ProviderErrorCode.UNSUPPORTED_IDENTITY,
                stage=ProviderStage.IDENTITY,
                message=f"No Skroutz fixture is configured for '{url}'",
                details={"url": url},
            )

        if not fixture_path.exists():
            raise ProviderError.build(
                provider_id=self.provider_id,
                code=ProviderErrorCode.NOT_FOUND,
                stage=ProviderStage.FETCH,
                message=f"Skroutz fixture does not exist: {fixture_path}",
                details={"url": url, "fixture_path": str(fixture_path)},
            )

        try:
            html = fixture_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProviderError.build(
                provider_id=self.provider_id,
                code=ProviderErrorCode.FETCH_FAILED,
                stage=ProviderStage.FETCH,
                message=f"Failed to read Skroutz fixture: {fixture_path}",
                details={"url": url, "fixture_path": str(fixture_path)},
                cause=exc,
            ) from exc

        return ProviderSnapshot(
            provider_id=self.provider_id,
            identity=identity,
            snapshot_kind=ProviderSnapshotKind.HTML,
            requested_url=url,
            final_url=url,
            content_type="text/html; charset=utf-8",
            status_code=200,
            body_text=html,
            metadata={
                "fetch_method": "fixture",
                "fallback_used": False,
                "fixture_path": str(fixture_path),
            },
        )

    def normalize(self, snapshot: ProviderSnapshot, identity: ProviderInputIdentity) -> ProviderResult:
        try:
            parsed = self._parser.parse(
                snapshot.body_text,
                snapshot.final_url or snapshot.requested_url or identity.url,
                fallback_used=bool(snapshot.metadata.get("fallback_used", False)),
            )
        except Exception as exc:
            raise ProviderError.build(
                provider_id=self.provider_id,
                code=ProviderErrorCode.NORMALIZATION_FAILED,
                stage=ProviderStage.NORMALIZE,
                message=str(exc),
                details={"url": identity.url},
                cause=exc,
            ) from exc

        return ProviderResult(
            provider=self.definition,
            identity=identity,
            snapshot=snapshot,
            product=parsed.source,
            provenance=dict(parsed.provenance),
            field_diagnostics=dict(parsed.field_diagnostics),
            warnings=list(parsed.warnings),
            missing_fields=list(parsed.missing_fields),
            critical_missing=list(parsed.critical_missing),
            metadata={
                "fetch_method": str(snapshot.metadata.get("fetch_method", "")),
                "fallback_used": bool(snapshot.metadata.get("fallback_used", False)),
                "fixture_path": str(snapshot.metadata.get("fixture_path", "")),
            },
        )
