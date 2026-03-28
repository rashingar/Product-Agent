from __future__ import annotations

from .base import ProductProvider, ProviderError
from .models import ProviderDefinition, ProviderErrorCode, ProviderKind, ProviderStage


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProductProvider] = {}

    def register(self, provider: ProductProvider) -> None:
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ProviderError.build(
                provider_id="",
                code=ProviderErrorCode.REGISTRATION_FAILED,
                stage=ProviderStage.REGISTRY,
                message="Provider id must be non-empty",
            )
        if provider_id in self._providers:
            raise ProviderError.build(
                provider_id=provider_id,
                code=ProviderErrorCode.REGISTRATION_FAILED,
                stage=ProviderStage.REGISTRY,
                message=f"Provider '{provider_id}' is already registered",
            )
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> ProductProvider | None:
        return self._providers.get(provider_id.strip())

    def require(self, provider_id: str) -> ProductProvider:
        provider = self.get(provider_id)
        if provider is None:
            raise ProviderError.build(
                provider_id=provider_id.strip(),
                code=ProviderErrorCode.NOT_FOUND,
                stage=ProviderStage.REGISTRY,
                message=f"Provider '{provider_id}' is not registered",
            )
        return provider

    def definitions(self, *, kind: ProviderKind | None = None) -> list[ProviderDefinition]:
        definitions = [provider.definition for provider in self._providers.values()]
        if kind is not None:
            definitions = [definition for definition in definitions if definition.kind == kind]
        return sorted(definitions, key=lambda definition: definition.provider_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
