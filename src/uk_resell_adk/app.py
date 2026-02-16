from __future__ import annotations

from uk_resell_adk.agents import build_multi_agent_system
from uk_resell_adk.config import DEFAULT_CONFIG
from uk_resell_adk.tracing import configure_langsmith

# ADK convention: expose root_agent for adk web / runner entrypoints.
configure_langsmith()
root_agent = build_multi_agent_system(DEFAULT_CONFIG)
