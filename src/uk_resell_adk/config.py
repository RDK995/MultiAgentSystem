from __future__ import annotations

"""Runtime configuration defaults for local and ADK execution."""

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeConfig:
    """Runtime settings for the resale multi-agent system."""

    model_name: str = "gemini-2.0-flash"
    max_foreign_sites: int = 10
    max_items_per_source: int = 8
    ebay_region: str = "GB"
    request_timeout_seconds: float = 10.0
    max_retries: int = 2
    enabled_sources: tuple[str, ...] = ("hlj", "ninningame", "surugaya")


DEFAULT_CONFIG = RuntimeConfig()
