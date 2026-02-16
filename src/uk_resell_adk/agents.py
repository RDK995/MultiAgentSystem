from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from uk_resell_adk.config import RuntimeConfig
from uk_resell_adk.tools import (
    assess_profitability_against_ebay,
    discover_foreign_marketplaces,
    find_candidate_items,
)


def build_multi_agent_system(config: RuntimeConfig) -> SequentialAgent:
    """Build the ADK multi-agent pipeline.

    Agent topology:
    1) Marketplace discovery agent
    2) Candidate sourcing agent
    3) Profitability analyst agent
    4) Report writer agent
    5) Orchestrator (parent sequence) exposed to the user
    """

    marketplace_discovery_agent = LlmAgent(
        name="marketplace_discovery_agent",
        model=config.model_name,
        instruction=(
            "You identify foreign marketplaces that UK resellers can source from. "
            "Use the tool and return a concise, structured list with compliance notes."
        ),
        tools=[FunctionTool(discover_foreign_marketplaces)],
        output_key="marketplaces",
    )

    item_sourcing_agent = LlmAgent(
        name="item_sourcing_agent",
        model=config.model_name,
        instruction=(
            "Use discovered marketplaces and call find_candidate_items for each source. "
            "Return items with landed-cost assumptions suitable for UK resale validation."
        ),
        tools=[FunctionTool(find_candidate_items)],
        output_key="candidate_items",
    )

    profitability_agent = LlmAgent(
        name="profitability_agent",
        model=config.model_name,
        instruction=(
            "Cross-reference each candidate item against eBay UK sold-price signals using the tool. "
            "Output structured profitability assessments and confidence levels."
        ),
        tools=[FunctionTool(assess_profitability_against_ebay)],
        output_key="assessments",
    )

    report_writer_agent = LlmAgent(
        name="report_writer_agent",
        model=config.model_name,
        instruction=(
            "Create a data lead report with executive summary, high/medium/low-confidence leads, "
            "risk factors, and concrete recommendations for next sourcing actions."
        ),
        output_key="lead_report",
    )

    orchestrator_agent = SequentialAgent(
        name="uk_resell_orchestrator",
        description="Top-level orchestrator that coordinates all specialist agents and answers users.",
        sub_agents=[
            marketplace_discovery_agent,
            item_sourcing_agent,
            profitability_agent,
            report_writer_agent,
        ],
    )

    return orchestrator_agent
