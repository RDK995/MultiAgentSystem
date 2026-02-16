from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class MarketplaceSite:
    name: str
    country: str
    url: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class CandidateItem:
    site_name: str
    title: str
    url: str
    source_price_gbp: float
    shipping_to_uk_gbp: float
    condition: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ProfitabilityAssessment:
    item_title: str
    item_url: str
    total_landed_cost_gbp: float
    ebay_median_sale_price_gbp: float
    estimated_fees_gbp: float
    estimated_profit_gbp: float
    estimated_margin_percent: float
    confidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ResellLeadReport:
    executive_summary: str
    high_confidence_leads: list[ProfitabilityAssessment]
    medium_confidence_leads: list[ProfitabilityAssessment]
    low_confidence_leads: list[ProfitabilityAssessment]
    risks: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "executive_summary": self.executive_summary,
            "high_confidence_leads": [x.to_dict() for x in self.high_confidence_leads],
            "medium_confidence_leads": [x.to_dict() for x in self.medium_confidence_leads],
            "low_confidence_leads": [x.to_dict() for x in self.low_confidence_leads],
            "risks": self.risks,
            "recommendations": self.recommendations,
        }
