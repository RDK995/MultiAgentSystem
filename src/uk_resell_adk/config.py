from __future__ import annotations

"""Runtime configuration defaults for local and ADK execution."""

from dataclasses import dataclass
from typing import TypedDict


@dataclass(slots=True)
class RuntimeConfig:
    """Runtime settings for the resale multi-agent system."""

    model_name: str = "gemini-2.0-flash"
    max_foreign_sites: int = 10
    max_items_per_source: int = 8
    profitability_concurrency: int = 10
    ebay_region: str = "GB"
    request_timeout_seconds: float = 10.0
    max_retries: int = 2
    enabled_sources: tuple[str, ...] = ("hlj", "ninningame", "surugaya")
    source_concurrency: int = 4


DEFAULT_CONFIG = RuntimeConfig()


class RuntimeConfigOverrides(TypedDict, total=False):
    max_foreign_sites: int
    profitability_concurrency: int
    source_concurrency: int


def runtime_config_with_overrides(overrides: RuntimeConfigOverrides | None = None) -> RuntimeConfig:
    """Build a validated runtime config from optional run-level overrides."""
    if not overrides:
        return DEFAULT_CONFIG

    max_foreign_sites = int(overrides.get("max_foreign_sites", DEFAULT_CONFIG.max_foreign_sites))
    profitability_concurrency = int(overrides.get("profitability_concurrency", DEFAULT_CONFIG.profitability_concurrency))
    source_concurrency = int(overrides.get("source_concurrency", DEFAULT_CONFIG.source_concurrency))

    return RuntimeConfig(
        model_name=DEFAULT_CONFIG.model_name,
        max_foreign_sites=max(1, max_foreign_sites),
        max_items_per_source=DEFAULT_CONFIG.max_items_per_source,
        profitability_concurrency=max(1, profitability_concurrency),
        ebay_region=DEFAULT_CONFIG.ebay_region,
        request_timeout_seconds=DEFAULT_CONFIG.request_timeout_seconds,
        max_retries=DEFAULT_CONFIG.max_retries,
        enabled_sources=DEFAULT_CONFIG.enabled_sources,
        source_concurrency=max(1, source_concurrency),
    )
