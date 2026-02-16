from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from uk_resell_adk.config import RuntimeConfig
from uk_resell_adk.tracing import traceable
from uk_resell_adk.tools import (
    assess_profitability_against_ebay,
    find_candidate_items,
)


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
            "Focus only on Meccha Japan as the sourcing channel. "
            "Call find_candidate_items and return product-specific candidates "
            "with landed-cost assumptions suitable for UK resale validation."
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
            item_sourcing_agent,
            profitability_agent,
            report_writer_agent,
        ],
    )

    return orchestrator_agent
