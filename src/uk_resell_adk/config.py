from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeConfig:
    """Runtime settings for the resale multi-agent system."""

    model_name: str = "gemini-2.0-flash"
    max_foreign_sites: int = 10
    max_items_per_site: int = 5
    ebay_region: str = "GB"


DEFAULT_CONFIG = RuntimeConfig()
