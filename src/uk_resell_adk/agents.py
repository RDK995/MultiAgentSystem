from __future__ import annotations

"""ADK agent graph wiring for the resale workflow."""

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from uk_resell_adk.config import RuntimeConfig
from uk_resell_adk.tools import assess_profitability_against_ebay, find_candidate_items
from uk_resell_adk.tracing import traceable


@traceable(name="build_multi_agent_system", run_type="chain")
def build_multi_agent_system(config: RuntimeConfig) -> SequentialAgent:
    """Build the ADK multi-agent pipeline.

    Agent topology:
    1) Candidate sourcing agent
    2) Profitability analyst agent
    3) Report writer agent
    4) Orchestrator (parent sequence) exposed to the user
    """

    item_sourcing_agent = LlmAgent(
        name="item_sourcing_agent",
        model=config.model_name,
        instruction=(
            "Focus on Japanese trading card sources that ship to the UK: "
            "HobbyLink Japan, Nin-Nin-Game, and Suruga-ya. "
            "Call find_candidate_items for each source and gather a broad candidate pool "
            "for trading cards only (booster boxes, decks, singles where available), "
            "with landed-cost assumptions suitable for UK resale validation."
        ),
        tools=[FunctionTool(find_candidate_items)],
        output_key="candidate_items",
    )

    profitability_agent = LlmAgent(
        name="profitability_agent",
        model=config.model_name,
        instruction=(
            "Cross-reference every candidate item against eBay UK sold-price signals using the tool. "
            "Evaluate the full sourced pool and output structured profitability assessments and confidence levels."
        ),
        tools=[FunctionTool(assess_profitability_against_ebay)],
        output_key="assessments",
    )

    report_writer_agent = LlmAgent(
        name="report_writer_agent",
        model=config.model_name,
        instruction=(
            "Create a data lead report focused on the most profitable opportunities from the full assessed pool. "
            "Include executive summary, high/medium/low-confidence leads, "
            "risk factors, and concrete recommendations for next sourcing actions."
        ),
        output_key="lead_report",
    )

    return SequentialAgent(
        name="uk_resell_orchestrator",
        description="Top-level orchestrator that coordinates all specialist agents and answers users.",
        sub_agents=[item_sourcing_agent, profitability_agent, report_writer_agent],
    )
