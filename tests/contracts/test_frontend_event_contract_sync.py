from __future__ import annotations

from pathlib import Path
import re

from uk_resell_adk.contracts.events import AGENT_STATUSES, EVENT_TYPES


def _extract_literal_block(content: str, variable: str) -> list[str]:
    match = re.search(rf"export const {variable} = \[(.*?)\] as const;", content, flags=re.DOTALL)
    assert match is not None, f"Could not locate {variable} contract in frontend file."
    return re.findall(r'"([^"]+)"', match.group(1))


def test_frontend_event_contracts_stay_in_sync_with_backend() -> None:
    contract_path = Path(__file__).resolve().parents[2] / "frontend/src/shared/contracts/eventContracts.ts"
    content = contract_path.read_text(encoding="utf-8")

    frontend_statuses = _extract_literal_block(content, "AGENT_STATUSES")
    frontend_event_types = _extract_literal_block(content, "EVENT_TYPES")

    assert tuple(frontend_statuses) == AGENT_STATUSES
    assert tuple(frontend_event_types) == EVENT_TYPES
