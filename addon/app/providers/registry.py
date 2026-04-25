from __future__ import annotations

from app.config import Settings
from app.providers.etilbudsavis import EtilbudsavisProvider
from app.providers.fixtures import MockFixtureProvider
from app.providers.minetilbud import MineTilbudProvider


PROVIDER_FACTORIES = {
    "mock": lambda settings: MockFixtureProvider(settings.fixture_dir),
    "etilbudsavis": lambda settings: EtilbudsavisProvider(settings),
    "minetilbud": lambda settings: MineTilbudProvider(settings),
}


def get_known_provider_names() -> list[str]:
    return sorted(PROVIDER_FACTORIES)


def build_provider(name: str, settings: Settings):
    if name not in PROVIDER_FACTORIES:
        raise KeyError(f"Unknown provider: {name}")
    return PROVIDER_FACTORIES[name](settings)


def build_enabled_providers(settings: Settings, selected_provider: str | None = None):
    enabled = settings.providers
    if selected_provider:
        if selected_provider not in enabled:
            raise KeyError(f"Provider '{selected_provider}' is not enabled")
        return [build_provider(selected_provider, settings)]
    return [build_provider(name, settings) for name in enabled]
