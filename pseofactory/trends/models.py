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


@dataclass
class CrawlCycleRecord:
    """Ledger record capturing crawl provenance and operational metrics for a daily cron run."""
    cycle_id: str
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    seeds_used: List[str] = field(default_factory=list)
    sources_crawled: List[str] = field(default_factory=list)
    total_raw_observations: int = 0
    unique_queries_count: int = 0
    status: str = "RUNNING"
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.cycle_id, "CrawlCycleRecord.cycle_id")
        assert_no_forbidden_dashes(self.status, "CrawlCycleRecord.status")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlCycleRecord":
        return cls(
            cycle_id=str(data.get("cycle_id", "")),
            executed_at=str(data.get("executed_at", datetime.now(timezone.utc).isoformat())),
            seeds_used=list(data.get("seeds_used", [])),
            sources_crawled=list(data.get("sources_crawled", [])),
            total_raw_observations=int(data.get("total_raw_observations", 0)),
            unique_queries_count=int(data.get("unique_queries_count", 0)),
            status=str(data.get("status", "RUNNING")),
            metadata=data.get("metadata"),
        )


@dataclass
class RawObservationRecord:
    """Append-only observation hit from suggestion endpoints."""
    observation_id: str
    cycle_id: str
    source: str
    query: str
    normalized_query: str
    rank_position: int = 0
    observed_velocity: float = 0.0
    observed_acceleration: float = 0.0
    observed_z_score: float = 0.0
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_payload: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.observation_id, "RawObservationRecord.observation_id")
        assert_no_forbidden_dashes(self.cycle_id, "RawObservationRecord.cycle_id")
        assert_no_forbidden_dashes(self.source, "RawObservationRecord.source")
        assert_no_forbidden_dashes(self.query, "RawObservationRecord.query")
        assert_no_forbidden_dashes(self.normalized_query, "RawObservationRecord.normalized_query")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawObservationRecord":
        return cls(
            observation_id=str(data.get("observation_id", "")),
            cycle_id=str(data.get("cycle_id", "")),
            source=str(data.get("source", "")),
            query=str(data.get("query", "")),
            normalized_query=str(data.get("normalized_query", "")),
            rank_position=int(data.get("rank_position", 0)),
            observed_velocity=float(data.get("observed_velocity", 0.0)),
            observed_acceleration=float(data.get("observed_acceleration", 0.0)),
            observed_z_score=float(data.get("observed_z_score", 0.0)),
            observed_at=str(data.get("observed_at", datetime.now(timezone.utc).isoformat())),
            raw_payload=data.get("raw_payload"),
        )


@dataclass
class LongitudinalKeywordRecord:
    """Longitudinal keyword entity tracking demand velocity, streaks, and acceleration."""
    query_slug: str
    query: str
    intent_cluster: str = "informational"
    first_seen_cycle_id: Optional[str] = None
    first_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen_cycle_id: Optional[str] = None
    last_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consecutive_cycles_count: int = 1
    total_cycles_count: int = 1
    lifetime_observations_count: int = 1
    current_property_id: str = "unassigned"
    status: str = "candidate"
    latest_velocity: float = 0.0
    velocity_delta: float = 0.0
    acceleration_2nd_deriv: float = 0.0
    velocity_variance: float = 0.0

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "LongitudinalKeywordRecord.query")
        assert_no_forbidden_dashes(self.query_slug, "LongitudinalKeywordRecord.query_slug")
        if self.query_slug:
            assert_url_safe_slug(self.query_slug)
        assert_no_forbidden_dashes(self.current_property_id, "LongitudinalKeywordRecord.current_property_id")
        assert_no_forbidden_dashes(self.status, "LongitudinalKeywordRecord.status")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LongitudinalKeywordRecord":
        return cls(
            query_slug=str(data.get("query_slug", "")),
            query=str(data.get("query", "")),
            intent_cluster=str(data.get("intent_cluster", "informational")),
            first_seen_cycle_id=data.get("first_seen_cycle_id"),
            first_seen_at=str(data.get("first_seen_at", datetime.now(timezone.utc).isoformat())),
            last_seen_cycle_id=data.get("last_seen_cycle_id"),
            last_seen_at=str(data.get("last_seen_at", datetime.now(timezone.utc).isoformat())),
            consecutive_cycles_count=int(data.get("consecutive_cycles_count", 1)),
            total_cycles_count=int(data.get("total_cycles_count", 1)),
            lifetime_observations_count=int(data.get("lifetime_observations_count", 1)),
            current_property_id=str(data.get("current_property_id", "unassigned")),
            status=str(data.get("status", "candidate")),
            latest_velocity=float(data.get("latest_velocity", 0.0)),
            velocity_delta=float(data.get("velocity_delta", 0.0)),
            acceleration_2nd_deriv=float(data.get("acceleration_2nd_deriv", 0.0)),
            velocity_variance=float(data.get("velocity_variance", 0.0)),
        )


@dataclass
class PropertyAssignmentRecord:
    """Property tenant assignment enforcing boundaries between Prexvo, ProfitHelm, and unassigned."""
    assignment_id: str
    query_slug: str
    cycle_id: str
    property_id: str = "unassigned"
    assignment_basis: str = "unassigned_cluster"
    matched_existing_slug: Optional[str] = None
    cannibalization_score: float = 0.0
    current_position: float = 100.0
    contamination_scan_passed: int = 1
    assigned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        assert_no_forbidden_dashes(self.assignment_id, "PropertyAssignmentRecord.assignment_id")
        assert_no_forbidden_dashes(self.query_slug, "PropertyAssignmentRecord.query_slug")
        if self.query_slug:
            assert_url_safe_slug(self.query_slug)
        if self.matched_existing_slug:
            assert_url_safe_slug(self.matched_existing_slug)
        assert_no_forbidden_dashes(self.property_id, "PropertyAssignmentRecord.property_id")
        assert_no_forbidden_dashes(self.assignment_basis, "PropertyAssignmentRecord.assignment_basis")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PropertyAssignmentRecord":
        return cls(
            assignment_id=str(data.get("assignment_id", "")),
            query_slug=str(data.get("query_slug", "")),
            cycle_id=str(data.get("cycle_id", "")),
            property_id=str(data.get("property_id", "unassigned")),
            assignment_basis=str(data.get("assignment_basis", "unassigned_cluster")),
            matched_existing_slug=data.get("matched_existing_slug"),
            cannibalization_score=float(data.get("cannibalization_score", 0.0)),
            current_position=float(data.get("current_position", 100.0)),
            contamination_scan_passed=int(data.get("contamination_scan_passed", 1)),
            assigned_at=str(data.get("assigned_at", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class TregSnapshotRecord:
    """Search demand and difficulty metrics captured per keyword cycle observation."""
    snapshot_id: str
    query_slug: str
    cycle_id: str
    search_volume: int = 0
    cpc_usd: float = 0.0
    competition_index: float = 0.0
    keyword_difficulty: float = 0.0
    position_zero_vacant: int = 0
    historical_stability: float = 0.85
    volume_delta_pct: float = 0.0
    cpc_delta_pct: float = 0.0
    volatility_score: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        assert_no_forbidden_dashes(self.snapshot_id, "TregSnapshotRecord.snapshot_id")
        assert_no_forbidden_dashes(self.query_slug, "TregSnapshotRecord.query_slug")
        if self.query_slug:
            assert_url_safe_slug(self.query_slug)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TregSnapshotRecord":
        return cls(
            snapshot_id=str(data.get("snapshot_id", "")),
            query_slug=str(data.get("query_slug", "")),
            cycle_id=str(data.get("cycle_id", "")),
            search_volume=int(data.get("search_volume", 0)),
            cpc_usd=float(data.get("cpc_usd", 0.0)),
            competition_index=float(data.get("competition_index", 0.0)),
            keyword_difficulty=float(data.get("keyword_difficulty", 0.0)),
            position_zero_vacant=int(data.get("position_zero_vacant", 0)),
            historical_stability=float(data.get("historical_stability", 0.85)),
            volume_delta_pct=float(data.get("volume_delta_pct", 0.0)),
            cpc_delta_pct=float(data.get("cpc_delta_pct", 0.0)),
            volatility_score=float(data.get("volatility_score", 0.0)),
            checked_at=str(data.get("checked_at", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class JevEvaluationRecord:
    """Strategic decision record produced by JevEngine for a keyword in a cycle."""
    evaluation_id: str
    query_slug: str
    cycle_id: str
    property_id: str = "unassigned"
    jev_score: float = 0.0
    durable_prob: float = 0.0
    composite_profit_yield: float = 0.0
    cannibalization_risk: float = 0.0
    action: str = "MONITOR"
    target_asset_type: str = "none"
    passed_thresholds: int = 0
    decision_reason: str = ""
    spec_payload: Optional[Dict[str, Any]] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        assert_no_forbidden_dashes(self.evaluation_id, "JevEvaluationRecord.evaluation_id")
        assert_no_forbidden_dashes(self.query_slug, "JevEvaluationRecord.query_slug")
        if self.query_slug:
            assert_url_safe_slug(self.query_slug)
        assert_no_forbidden_dashes(self.property_id, "JevEvaluationRecord.property_id")
        assert_no_forbidden_dashes(self.action, "JevEvaluationRecord.action")
        assert_no_forbidden_dashes(self.target_asset_type, "JevEvaluationRecord.target_asset_type")
        assert_no_forbidden_dashes(self.decision_reason, "JevEvaluationRecord.decision_reason")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JevEvaluationRecord":
        return cls(
            evaluation_id=str(data.get("evaluation_id", "")),
            query_slug=str(data.get("query_slug", "")),
            cycle_id=str(data.get("cycle_id", "")),
            property_id=str(data.get("property_id", "unassigned")),
            jev_score=float(data.get("jev_score", 0.0)),
            durable_prob=float(data.get("durable_prob", 0.0)),
            composite_profit_yield=float(data.get("composite_profit_yield", 0.0)),
            cannibalization_risk=float(data.get("cannibalization_risk", 0.0)),
            action=str(data.get("action", "MONITOR")),
            target_asset_type=str(data.get("target_asset_type", "none")),
            passed_thresholds=int(data.get("passed_thresholds", 0)),
            decision_reason=str(data.get("decision_reason", "")),
            spec_payload=data.get("spec_payload"),
            evaluated_at=str(data.get("evaluated_at", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class NicheClusterProposal:
    """Candidate proposal for launching a new standalone programmatic application."""
    proposal_id: str
    cluster_slug: str
    cluster_title: str
    first_observed_cycle_id: Optional[str] = None
    confirmed_cycle_id: Optional[str] = None
    consecutive_cycles_sustained: int = 3
    mean_composite_yield: float = 0.0
    aggregate_search_volume: int = 0
    mean_cpc_usd: float = 0.0
    treg_stability_index: float = 0.85
    primary_queries: List[str] = field(default_factory=list)
    recommended_domain_archetype: str = "standalone_factory"
    status: str = "PROPOSED"
    proposal_spec: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        assert_no_forbidden_dashes(self.proposal_id, "NicheClusterProposal.proposal_id")
        assert_no_forbidden_dashes(self.cluster_slug, "NicheClusterProposal.cluster_slug")
        if self.cluster_slug:
            assert_url_safe_slug(self.cluster_slug)
        assert_no_forbidden_dashes(self.cluster_title, "NicheClusterProposal.cluster_title")
        assert_no_forbidden_dashes(self.recommended_domain_archetype, "NicheClusterProposal.recommended_domain_archetype")
        assert_no_forbidden_dashes(self.status, "NicheClusterProposal.status")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NicheClusterProposal":
        return cls(
            proposal_id=str(data.get("proposal_id", "")),
            cluster_slug=str(data.get("cluster_slug", "")),
            cluster_title=str(data.get("cluster_title", "")),
            first_observed_cycle_id=data.get("first_observed_cycle_id"),
            confirmed_cycle_id=data.get("confirmed_cycle_id"),
            consecutive_cycles_sustained=int(data.get("consecutive_cycles_sustained", 3)),
            mean_composite_yield=float(data.get("mean_composite_yield", 0.0)),
            aggregate_search_volume=int(data.get("aggregate_search_volume", 0)),
            mean_cpc_usd=float(data.get("mean_cpc_usd", 0.0)),
            treg_stability_index=float(data.get("treg_stability_index", 0.85)),
            primary_queries=list(data.get("primary_queries", [])),
            recommended_domain_archetype=str(data.get("recommended_domain_archetype", "standalone_factory")),
            status=str(data.get("status", "PROPOSED")),
            proposal_spec=dict(data.get("proposal_spec", {})),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=str(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class GSCDailyMetricRecord:
    """Historical Google Search Console performance metric record for a property on a single date."""
    property_id: str
    date: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        assert_no_forbidden_dashes(self.property_id, "GSCDailyMetricRecord.property_id")
        assert_no_forbidden_dashes(self.date, "GSCDailyMetricRecord.date")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GSCDailyMetricRecord":
        return cls(
            property_id=str(data.get("property_id", "")),
            date=str(data.get("date", "")),
            clicks=int(data.get("clicks", 0)),
            impressions=int(data.get("impressions", 0)),
            ctr=float(data.get("ctr", 0.0)),
            position=float(data.get("position", 0.0)),
            recorded_at=str(data.get("recorded_at", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class GoogleUpdateEvent:
    """Dated Google ranking algorithm update event."""
    event_id: str
    name: str
    update_type: str = "CORE"
    start_date: str = ""
    end_date: Optional[str] = None
    impact_buffer_days: int = 14
    confirmed: int = 1
    notes: str = ""

    def __post_init__(self):
        assert_no_forbidden_dashes(self.event_id, "GoogleUpdateEvent.event_id")
        assert_no_forbidden_dashes(self.name, "GoogleUpdateEvent.name")
        assert_no_forbidden_dashes(self.update_type, "GoogleUpdateEvent.update_type")
        assert_no_forbidden_dashes(self.start_date, "GoogleUpdateEvent.start_date")
        if self.end_date:
            assert_no_forbidden_dashes(self.end_date, "GoogleUpdateEvent.end_date")
        if self.notes:
            assert_no_forbidden_dashes(self.notes, "GoogleUpdateEvent.notes")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoogleUpdateEvent":
        return cls(
            event_id=str(data.get("event_id", "")),
            name=str(data.get("name", "")),
            update_type=str(data.get("update_type", "CORE")),
            start_date=str(data.get("start_date", "")),
            end_date=str(data["end_date"]) if data.get("end_date") else None,
            impact_buffer_days=int(data.get("impact_buffer_days", 14)),
            confirmed=int(data.get("confirmed", 1)),
            notes=str(data.get("notes", "")),
        )


@dataclass
class CeilingThresholdSpec:
    """Threshold specification for algorithmic glass ceiling detection."""
    threshold: float = 0.35
    min_lookback_days: int = 28
    analysis_window_days: int = 480
    variance_cv_threshold: float = 0.35
    drop_ratio_weight: float = 0.40
    plateau_resistance_weight: float = 0.40
    position_stagnation_weight: float = 0.20

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CeilingThresholdSpec":
        return cls(
            threshold=float(data.get("threshold", 0.35)),
            min_lookback_days=int(data.get("min_lookback_days", 28)),
            analysis_window_days=int(data.get("analysis_window_days", 480)),
            variance_cv_threshold=float(data.get("variance_cv_threshold", 0.35)),
            drop_ratio_weight=float(data.get("drop_ratio_weight", 0.40)),
            plateau_resistance_weight=float(data.get("plateau_resistance_weight", 0.40)),
            position_stagnation_weight=float(data.get("position_stagnation_weight", 0.20)),
        )


@dataclass
class AlgorithmicCeilingAnalysis:
    """Analytical evaluation of Search Console traffic trajectory against algorithmic ceilings."""
    property_id: str
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    analysis_window_days: int = 480
    total_days: int = 0
    peak_impressions_rma28: float = 0.0
    current_impressions_rma28: float = 0.0
    ceiling_threshold: float = 0.35
    ceiling_dampening_score: float = 0.0
    ceiling_detected: bool = False
    suppression_severity: str = "NONE"
    correlated_updates: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = "BUILD_PAGE"
    metrics_timeline: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.property_id, "AlgorithmicCeilingAnalysis.property_id")
        assert_no_forbidden_dashes(self.suppression_severity, "AlgorithmicCeilingAnalysis.suppression_severity")
        assert_no_forbidden_dashes(self.recommendation, "AlgorithmicCeilingAnalysis.recommendation")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlgorithmicCeilingAnalysis":
        return cls(
            property_id=str(data.get("property_id", "")),
            computed_at=str(data.get("computed_at", datetime.now(timezone.utc).isoformat())),
            analysis_window_days=int(data.get("analysis_window_days", 480)),
            total_days=int(data.get("total_days", 0)),
            peak_impressions_rma28=float(data.get("peak_impressions_rma28", 0.0)),
            current_impressions_rma28=float(data.get("current_impressions_rma28", 0.0)),
            ceiling_threshold=float(data.get("ceiling_threshold", 0.35)),
            ceiling_dampening_score=float(data.get("ceiling_dampening_score", 0.0)),
            ceiling_detected=bool(data.get("ceiling_detected", False)),
            suppression_severity=str(data.get("suppression_severity", "NONE")),
            correlated_updates=list(data.get("correlated_updates", [])),
            recommendation=str(data.get("recommendation", "BUILD_PAGE")),
            metrics_timeline=list(data.get("metrics_timeline", [])),
            metadata=data.get("metadata"),
        )

