from __future__ import annotations

import importlib
import sys
import types
from typing import Any

from uk_resell_adk.config import RuntimeConfig


class _FakeFunctionTool:
    def __init__(self, func: Any) -> None:
        self.func = func


class _FakeLlmAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.name = kwargs["name"]
        self.model = kwargs["model"]
        self.instruction = kwargs["instruction"]
        self.tools = kwargs.get("tools", [])
        self.output_key = kwargs.get("output_key")


class _FakeSequentialAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.name = kwargs["name"]
        self.description = kwargs["description"]
        self.sub_agents = kwargs["sub_agents"]


if "google.adk.agents" not in sys.modules:
    google_mod = types.ModuleType("google")
    adk_mod = types.ModuleType("google.adk")
    agents_mod = types.ModuleType("google.adk.agents")
    tools_mod = types.ModuleType("google.adk.tools")

    class _Placeholder:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    agents_mod.LlmAgent = _Placeholder
    agents_mod.SequentialAgent = _Placeholder
    tools_mod.FunctionTool = _Placeholder

    sys.modules.setdefault("google", google_mod)
    sys.modules.setdefault("google.adk", adk_mod)
    sys.modules["google.adk.agents"] = agents_mod
    sys.modules["google.adk.tools"] = tools_mod

agents = importlib.import_module("uk_resell_adk.agents")


def test_build_multi_agent_system_wires_expected_agents(monkeypatch: Any) -> None:
    monkeypatch.setattr(agents, "FunctionTool", _FakeFunctionTool)
    monkeypatch.setattr(agents, "LlmAgent", _FakeLlmAgent)
    monkeypatch.setattr(agents, "SequentialAgent", _FakeSequentialAgent)

    config = RuntimeConfig(model_name="gemini-test")
    orchestrator = agents.build_multi_agent_system(config)

    assert orchestrator.name == "uk_resell_orchestrator"
    assert len(orchestrator.sub_agents) == 3

    item_agent, profitability_agent, report_agent = orchestrator.sub_agents

    assert item_agent.name == "item_sourcing_agent"
    assert item_agent.model == "gemini-test"
    assert item_agent.output_key == "candidate_items"
    assert item_agent.tools[0].func is agents.find_candidate_items

    assert profitability_agent.name == "profitability_agent"
    assert profitability_agent.output_key == "assessments"
    assert profitability_agent.tools[0].func is agents.assess_profitability_against_ebay

    assert report_agent.name == "report_writer_agent"
    assert report_agent.output_key == "lead_report"


def test_item_sourcing_instruction_mentions_supported_sources(monkeypatch: Any) -> None:
    monkeypatch.setattr(agents, "FunctionTool", _FakeFunctionTool)
    monkeypatch.setattr(agents, "LlmAgent", _FakeLlmAgent)
    monkeypatch.setattr(agents, "SequentialAgent", _FakeSequentialAgent)

    orchestrator = agents.build_multi_agent_system(RuntimeConfig())

    item_agent = orchestrator.sub_agents[0]
    assert "HobbyLink Japan" in item_agent.instruction
    assert "Nin-Nin-Game" in item_agent.instruction
    assert "find_candidate_items" in item_agent.instruction
