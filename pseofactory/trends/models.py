"""
pseofactory Trend Data Models & Contracts
Defines dataclasses for streaming spikes, candidate topics, treg metrics, and Jev decisions.
Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from pseofactory.contracts import assert_no_forbidden_dashes, assert_url_safe_slug


@dataclass
class FeedSpike:
    """Raw momentum spike detected from streaming suggest or feed endpoints."""
    id: str
    query: str
    source: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sample_count: int = 1
    velocity: float = 0.0
    acceleration: float = 0.0
    z_score: float = 0.0
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    raw_payload: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "FeedSpike.query")
        assert_no_forbidden_dashes(self.source, "FeedSpike.source")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedSpike":
        return cls(
            id=str(data.get("id", "")),
            query=str(data.get("query", "")),
            source=str(data.get("source", "unknown")),
            detected_at=str(data.get("detected_at", datetime.now(timezone.utc).isoformat())),
            sample_count=int(data.get("sample_count", 1)),
            velocity=float(data.get("velocity", 0.0)),
            acceleration=float(data.get("acceleration", 0.0)),
            z_score=float(data.get("z_score", 0.0)),
            baseline_mean=float(data.get("baseline_mean", 0.0)),
            raw_payload=data.get("raw_payload") or data,
        )


@dataclass
class TrendCandidate:
    """Noise-filtered candidate topic surviving acceleration gating and transient chatter rejection."""
    id: str
    query: str
    slug: str
    source: str
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    velocity: float = 0.0
    acceleration: float = 0.0
    z_score: float = 0.0
    intent_cluster: str = "informational"
    is_transient_noise: bool = False
    qualification_status: str = "PENDING_TREG"
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "TrendCandidate.query")
        assert_no_forbidden_dashes(self.slug, "TrendCandidate.slug")
        if self.slug:
            assert_url_safe_slug(self.slug)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrendCandidate":
        return cls(
            id=str(data.get("id", "")),
            query=str(data.get("query", "")),
            slug=str(data.get("slug", "")),
            source=str(data.get("source", "unknown")),
            discovered_at=str(data.get("discovered_at", datetime.now(timezone.utc).isoformat())),
            velocity=float(data.get("velocity", 0.0)),
            acceleration=float(data.get("acceleration", 0.0)),
            z_score=float(data.get("z_score", 0.0)),
            intent_cluster=str(data.get("intent_cluster", "informational")),
            is_transient_noise=bool(data.get("is_transient_noise", False)),
            qualification_status=str(data.get("qualification_status", "PENDING_TREG")),
            metadata=data.get("metadata"),
        )


@dataclass
class TregDurabilityResult:
    """External search demand and competition metrics cross-checked via treg catalog endpoints."""
    query: str
    endpoint_called: str = "treg.google.keywords.ideas"
    search_volume: int = 0
    cpc_usd: float = 0.0
    competition_index: float = 0.0
    keyword_difficulty: float = 0.0
    position_zero_vacant: bool = False
    historical_stability: float = 0.85
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_ideas: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "TregDurabilityResult.query")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TregDurabilityResult":
        return cls(
            query=str(data.get("query", "")),
            endpoint_called=str(data.get("endpoint_called", "treg.google.keywords.ideas")),
            search_volume=int(data.get("search_volume", 0)),
            cpc_usd=float(data.get("cpc_usd", 0.0)),
            competition_index=float(data.get("competition_index", 0.0)),
            keyword_difficulty=float(data.get("keyword_difficulty", 0.0)),
            position_zero_vacant=bool(data.get("position_zero_vacant", False)),
            historical_stability=float(data.get("historical_stability", 0.85)),
            checked_at=str(data.get("checked_at", datetime.now(timezone.utc).isoformat())),
            raw_ideas=data.get("raw_ideas"),
        )


@dataclass
class JevDecisionResult:
    """Final strategic decision record generated by TypeSafe AI System One decision engine."""
    query: str
    slug: str
    action: str
    jev_score: float = 0.0
    durable_prob: float = 0.0
    composite_profit_yield: float = 0.0
    cannibalization_risk: float = 0.0
    target_asset_type: str = "none"
    decision_reason: str = ""
    passed_thresholds: bool = False
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    matching_tool: Optional[str] = None
    overlay_spec: Optional[Dict[str, Any]] = None
    candidate_spec: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "JevDecisionResult.query")
        assert_no_forbidden_dashes(self.slug, "JevDecisionResult.slug")
        assert_no_forbidden_dashes(self.decision_reason, "JevDecisionResult.decision_reason")
        if self.slug:
            assert_url_safe_slug(self.slug)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JevDecisionResult":
        return cls(
            query=str(data.get("query", "")),
            slug=str(data.get("slug", "")),
            action=str(data.get("action", "REJECT")),
            jev_score=float(data.get("jev_score", 0.0)),
            durable_prob=float(data.get("durable_prob", 0.0)),
            composite_profit_yield=float(data.get("composite_profit_yield", 0.0)),
            cannibalization_risk=float(data.get("cannibalization_risk", 0.0)),
            target_asset_type=str(data.get("target_asset_type", "none")),
            decision_reason=str(data.get("decision_reason", "")),
            passed_thresholds=bool(data.get("passed_thresholds", False)),
            evaluated_at=str(data.get("evaluated_at", datetime.now(timezone.utc).isoformat())),
            matching_tool=data.get("matching_tool"),
            overlay_spec=data.get("overlay_spec"),
            candidate_spec=data.get("candidate_spec"),
        )
