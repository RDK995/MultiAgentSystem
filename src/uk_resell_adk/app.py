from __future__ import annotations

from uk_resell_adk.agents import build_multi_agent_system
from uk_resell_adk.config import DEFAULT_CONFIG

# ADK convention: expose root_agent for adk web / runner entrypoints.
root_agent = build_multi_agent_system(DEFAULT_CONFIG)
