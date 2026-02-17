from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from uk_resell_adk.models import CandidateItem


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    key: str
    name: str
    country: str
    home_url: str
    reason: str
    strict_live_required: bool = True


class SourceAdapter(Protocol):
    descriptor: SourceDescriptor

    def fetch_candidates(
        self,
        limit: int,
        timeout_seconds: float = 10,
        retries: int = 2,
        allow_fallback: bool = False,
    ) -> Sequence[CandidateItem]:
        ...
