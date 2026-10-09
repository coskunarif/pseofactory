"""
pseofactory Keyword Content Angle Discovery Engine
Enforces the Grant O Triad, Search Intent Doctrine, and Value Proposition Divergence:
1. Grant O Triad: Specific audience niche, specific problem scope, specific geography/vertical.
2. Search Intent Doctrine: Never mistake exploratory impressions for missing voids.
3. Divergence Oracle: Token Jaccard divergence >= 0.50 against incumbents, rejecting clones.

Zero em-dashes. Zero en-dashes. Zero prompt leakage terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from pseofactory.contracts import assert_no_forbidden_dashes, assert_no_prompt_leakage
from pseofactory.qualification import qualify_search_intent


# Standard English stopwords for deterministic token filtering
ENGLISH_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "you", "your",
    "yours", "yourself", "yourselves",
}

# Five validated underdog content archetypes
VALID_UNDERDOG_ARCHETYPES: List[str] = [
    "Vertical/Niche Specificity",
    "Practitioner/Operator Teardown",
    "Contrarian/Anti-Consensus Benchmark",
    "Free Interactive Tool/Calculator",
    "Regulatory/Audit Checklist",
]


@dataclass
class GrantOTriad:
    """
    Orthogonal three-dimensional bounds for underdog content positioning:
    1. Audience niche
    2. Problem scope
    3. Geographic or vertical bound
    """
    audience_niche: str
    problem_scope: str
    geographic_or_vertical_bound: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> bool:
        if not self.audience_niche or not str(self.audience_niche).strip():
            raise ValueError("Grant O Triad requires a non-empty audience niche.")
        if not self.problem_scope or not str(self.problem_scope).strip():
            raise ValueError("Grant O Triad requires a non-empty problem scope.")
        if not self.geographic_or_vertical_bound or not str(self.geographic_or_vertical_bound).strip():
            raise ValueError("Grant O Triad requires a non-empty geographic or vertical bound.")
        return True

    def to_dict(self) -> Dict[str, str]:
        return {
            "audience_niche": self.audience_niche,
            "problem_scope": self.problem_scope,
            "geographic_or_vertical_bound": self.geographic_or_vertical_bound,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GrantOTriad:
        return cls(
            audience_niche=str(data.get("audience_niche", data.get("target_audience_niche", ""))),
            problem_scope=str(data.get("problem_scope", "")),
            geographic_or_vertical_bound=str(data.get("geographic_or_vertical_bound", "")),
        )


@dataclass
class IncumbentSummary:
    """Summary of an entrenched incumbent SERP competitor."""
    domain: str
    rank: int
    title: str
    weakness_category: str
    weakness_detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "rank": self.rank,
            "title": self.title,
            "weakness_category": self.weakness_category,
            "weakness_detail": self.weakness_detail,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IncumbentSummary:
        return cls(
            domain=str(data.get("domain", "")),
            rank=int(data.get("rank", 0)),
            title=str(data.get("title", "")),
            weakness_category=str(data.get("weakness_category", "")),
            weakness_detail=str(data.get("weakness_detail", "")),
        )


@dataclass
class TeardownEvaluationVector:
    """Structured evaluation vector comparing an incumbent tool against operator reality."""
    vector_id: str
    benchmark_label: str
    operator_baseline: str
    incumbent_gap: str
    verifiable_metric: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "vector_id": self.vector_id,
            "benchmark_label": self.benchmark_label,
            "operator_baseline": self.operator_baseline,
            "incumbent_gap": self.incumbent_gap,
            "verifiable_metric": self.verifiable_metric,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TeardownEvaluationVector:
        return cls(
            vector_id=str(data.get("vector_id", "")),
            benchmark_label=str(data.get("benchmark_label", "")),
            operator_baseline=str(data.get("operator_baseline", "")),
            incumbent_gap=str(data.get("incumbent_gap", "")),
            verifiable_metric=str(data.get("verifiable_metric", "")),
        )


@dataclass
class PractitionerTeardownSpec:
    """Specification model capturing practitioner teardown heuristics (Zviadadze/Goodey)."""
    framework_author: str
    teardown_subject: str
    icp_profile: str
    evaluation_vectors: List[TeardownEvaluationVector] = field(default_factory=list)
    reproducible_workflow_steps: List[str] = field(default_factory=list)
    utility_asset_type: str = "interactive_comparison_matrix"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework_author": self.framework_author,
            "teardown_subject": self.teardown_subject,
            "icp_profile": self.icp_profile,
            "evaluation_vectors": [v.to_dict() for v in self.evaluation_vectors],
            "reproducible_workflow_steps": self.reproducible_workflow_steps,
            "utility_asset_type": self.utility_asset_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PractitionerTeardownSpec:
        raw_vectors = data.get("evaluation_vectors", [])
        vectors = [
            v if isinstance(v, TeardownEvaluationVector) else TeardownEvaluationVector.from_dict(v)
            for v in raw_vectors
        ]
        return cls(
            framework_author=str(data.get("framework_author", "")),
            teardown_subject=str(data.get("teardown_subject", "")),
            icp_profile=str(data.get("icp_profile", "")),
            evaluation_vectors=vectors,
            reproducible_workflow_steps=[str(s) for s in data.get("reproducible_workflow_steps", [])],
            utility_asset_type=str(data.get("utility_asset_type", "interactive_comparison_matrix")),
        )


@dataclass
class TechnicalAuditChecklistItem:
    """Actionable technical audit item inspired by Kristina Azarenko technical SEO audits."""
    check_id: str
    category: str
    severity: str
    diagnostic_rule: str
    verification_heuristic: str
    remediation_pattern: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "severity": self.severity,
            "diagnostic_rule": self.diagnostic_rule,
            "verification_heuristic": self.verification_heuristic,
            "remediation_pattern": self.remediation_pattern,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TechnicalAuditChecklistItem:
        return cls(
            check_id=str(data.get("check_id", "")),
            category=str(data.get("category", "")),
            severity=str(data.get("severity", "MEDIUM")),
            diagnostic_rule=str(data.get("diagnostic_rule", "")),
            verification_heuristic=str(data.get("verification_heuristic", "")),
            remediation_pattern=str(data.get("remediation_pattern", "")),
        )


@dataclass
class SaaSTechnicalAuditSpec:
    """Specification model capturing technical audit heuristics (Kristina Azarenko)."""
    framework_author: str
    audit_domain_scope: str
    checklist: List[TechnicalAuditChecklistItem] = field(default_factory=list)
    metric_thresholds: Dict[str, Union[int, float, str]] = field(default_factory=dict)
    utility_asset_type: str = "faceted_indexation_decision_tree"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework_author": self.framework_author,
            "audit_domain_scope": self.audit_domain_scope,
            "checklist": [c.to_dict() for c in self.checklist],
            "metric_thresholds": self.metric_thresholds,
            "utility_asset_type": self.utility_asset_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SaaSTechnicalAuditSpec:
        raw_checklist = data.get("checklist", [])
        items = [
            c if isinstance(c, TechnicalAuditChecklistItem) else TechnicalAuditChecklistItem.from_dict(c)
            for c in raw_checklist
        ]
        return cls(
            framework_author=str(data.get("framework_author", "")),
            audit_domain_scope=str(data.get("audit_domain_scope", "")),
            checklist=items,
            metric_thresholds=dict(data.get("metric_thresholds", {})),
            utility_asset_type=str(data.get("utility_asset_type", "faceted_indexation_decision_tree")),
        )


@dataclass
class UnderdogAngle:
    """An underdog content angle engineered to outrank incumbents."""
    angle_id: str
    triad: GrantOTriad
    archetype: str
    primary_value_proposition: str
    first_party_utility_asset: str
    divergence_score: float = 0.0
    teardown_spec: Optional[PractitionerTeardownSpec] = None
    audit_spec: Optional[SaaSTechnicalAuditSpec] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "angle_id": self.angle_id,
            "triad": self.triad.to_dict(),
            "archetype": self.archetype,
            "primary_value_proposition": self.primary_value_proposition,
            "first_party_utility_asset": self.first_party_utility_asset,
            "divergence_score": self.divergence_score,
        }
        if self.teardown_spec is not None:
            result["teardown_spec"] = self.teardown_spec.to_dict()
        if self.audit_spec is not None:
            result["audit_spec"] = self.audit_spec.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnderdogAngle:
        triad_data = data.get("triad")
        if isinstance(triad_data, GrantOTriad):
            triad = triad_data
        elif isinstance(triad_data, dict):
            triad = GrantOTriad.from_dict(triad_data)
        else:
            triad = GrantOTriad(
                audience_niche=str(data.get("target_audience_niche", data.get("audience_niche", ""))),
                problem_scope=str(data.get("problem_scope", "")),
                geographic_or_vertical_bound=str(data.get("geographic_or_vertical_bound", "")),
            )

        teardown = None
        if "teardown_spec" in data and data["teardown_spec"]:
            raw_t = data["teardown_spec"]
            teardown = raw_t if isinstance(raw_t, PractitionerTeardownSpec) else PractitionerTeardownSpec.from_dict(raw_t)

        audit = None
        if "audit_spec" in data and data["audit_spec"]:
            raw_a = data["audit_spec"]
            audit = raw_a if isinstance(raw_a, SaaSTechnicalAuditSpec) else SaaSTechnicalAuditSpec.from_dict(raw_a)

        return cls(
            angle_id=str(data.get("angle_id", "")),
            triad=triad,
            archetype=str(data.get("archetype", "Vertical/Niche Specificity")),
            primary_value_proposition=str(data.get("primary_value_proposition", "")),
            first_party_utility_asset=str(data.get("first_party_utility_asset", "")),
            divergence_score=float(data.get("divergence_score", data.get("divergence_score_min", 0.0))),
            teardown_spec=teardown,
            audit_spec=audit,
        )



@dataclass
class ContentAngleBrief:
    """Comprehensive content angle brief synthesized for generation."""
    query: str
    triage_action: str
    angles: List[UnderdogAngle] = field(default_factory=list)
    evaluation_summary: str = ""
    markdown_brief: str = ""
    target_position: float = 100.0
    impressions: int = 0
    overlay_spec: Optional[Dict[str, Any]] = None
    candidate_spec: Optional[Dict[str, Any]] = None

    def to_markdown(self) -> str:
        return self.markdown_brief

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "triage_action": self.triage_action,
            "angles": [a.to_dict() for a in self.angles],
            "evaluation_summary": self.evaluation_summary,
            "markdown_brief": self.markdown_brief,
            "target_position": self.target_position,
            "impressions": self.impressions,
            "overlay_spec": self.overlay_spec,
            "candidate_spec": self.candidate_spec,
        }


def _tokenize_text(text: str) -> Set[str]:
    """Extracts lowercase alphanumeric tokens and filters common English stopwords."""
    if not text:
        return set()
    raw_tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
    return {t for t in raw_tokens if t not in ENGLISH_STOPWORDS}


def _normalize_incumbent_texts(
    incumbent_texts: Union[List[str], List[Dict[str, Any]], List[IncumbentSummary]],
) -> List[str]:
    """Extracts raw text strings from diverse incumbent representations."""
    normalized: List[str] = []
    for item in incumbent_texts:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, IncumbentSummary):
            normalized.append(f"{item.title} {item.weakness_detail}")
        elif isinstance(item, dict):
            title = str(item.get("title", ""))
            detail = str(item.get("weakness_detail", item.get("summary", "")))
            normalized.append(f"{title} {detail}".strip())
    return normalized


def calculate_token_jaccard_divergence(
    candidate_text: str,
    incumbent_texts: Union[List[str], List[Dict[str, Any]], List[IncumbentSummary]],
) -> float:
    """
    Computes token Jaccard distance between candidate angle and incumbent texts:
    divergence = 1.0 - (len(tokens_cand & tokens_inc) / len(tokens_cand | tokens_inc))

    Returns float rounded to 4 decimals in range [0.0, 1.0].
    """
    cand_tokens = _tokenize_text(candidate_text)
    if not cand_tokens:
        return 0.0

    raw_incumbents = _normalize_incumbent_texts(incumbent_texts)
    inc_tokens: Set[str] = set()
    for text in raw_incumbents:
        inc_tokens.update(_tokenize_text(text))

    if not inc_tokens:
        return 1.0

    intersection = len(cand_tokens & inc_tokens)
    union = len(cand_tokens | inc_tokens)
    if union == 0:
        return 1.0

    jaccard_similarity = intersection / union
    divergence = 1.0 - jaccard_similarity
    return round(divergence, 4)


def assert_underdog_angle_divergence(
    candidate_text_or_angle: Union[str, UnderdogAngle],
    incumbent_texts: Union[List[str], List[Dict[str, Any]], List[IncumbentSummary]],
    min_threshold: float = 0.50,
) -> float:
    """
    Validates that a candidate underdog angle achieves the minimum divergence threshold.
    Raises ValueError if divergence is below the minimum threshold.
    """
    if isinstance(candidate_text_or_angle, UnderdogAngle):
        cand_text = candidate_text_or_angle.primary_value_proposition
    else:
        cand_text = str(candidate_text_or_angle)

    divergence = calculate_token_jaccard_divergence(cand_text, incumbent_texts)
    if divergence < min_threshold:
        raise ValueError(
            f"Derivative clone rejected: calculated divergence {divergence:.4f} is below required threshold {min_threshold:.2f}."
        )

    if isinstance(candidate_text_or_angle, UnderdogAngle):
        candidate_text_or_angle.divergence_score = divergence

    return divergence


def generate_markdown_brief(
    query: str,
    triage_action: str,
    evaluation_summary: str,
    angles: List[UnderdogAngle],
    incumbents: List[IncumbentSummary],
    position: float = 100.0,
    impressions: int = 0,
    overlay_spec: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Synthesizes a markdown content angle brief adhering strictly to:
    1. Zero em-dashes and zero en-dashes.
    2. Zero prompt leakage terms.
    """
    lines: List[str] = [
        f"# Content Angle Brief: {query}",
        "",
        "## Search Intent Doctrine Triage",
        f"- Target Query: {query}",
        f"- Triage Action: {triage_action}",
        f"- Observed Position: {position:.1f}",
        f"- Observed Impressions: {impressions}",
        f"- Status Evaluation: {evaluation_summary}",
    ]

    if overlay_spec:
        lines.extend([
            "",
            "## Refactoring Overlay Specification",
            f"- Existing Tool Slug: {overlay_spec.get('slug', 'none')}",
            f"- Measurement Lock: {overlay_spec.get('measurement_lock_days', 28)} days",
            f"- Locked Until: {overlay_spec.get('locked_until', 'none')}",
        ])

    if incumbents:
        lines.extend([
            "",
            "## Incumbent Competitor SERP Analysis",
        ])
        for inc in incumbents:
            lines.extend([
                f"### {inc.rank}. {inc.domain} ({inc.title})",
                f"- Weakness Category: {inc.weakness_category}",
                f"- Weakness Detail: {inc.weakness_detail}",
            ])

    if angles:
        lines.extend([
            "",
            "## Underdog Angles (Grant O Triad)",
        ])
        for angle in angles:
            triad = angle.triad
            lines.extend([
                f"### Angle: {angle.angle_id} ({angle.archetype})",
                f"- Audience Niche: {triad.audience_niche}",
                f"- Problem Scope: {triad.problem_scope}",
                f"- Geographic or Vertical Bound: {triad.geographic_or_vertical_bound}",
                f"- Value Proposition: {angle.primary_value_proposition}",
                f"- First-Party Utility Asset: {angle.first_party_utility_asset}",
                f"- Divergence Score: {angle.divergence_score:.4f}",
            ])
            if angle.teardown_spec:
                ts = angle.teardown_spec
                lines.extend([
                    "#### Practitioner Teardown Specification",
                    f"- Framework Author: {ts.framework_author}",
                    f"- Teardown Subject: {ts.teardown_subject}",
                    f"- ICP Profile: {ts.icp_profile}",
                    f"- Utility Asset Type: {ts.utility_asset_type}",
                ])
                if ts.evaluation_vectors:
                    lines.append("##### Evaluation Vectors")
                    for vec in ts.evaluation_vectors:
                        lines.extend([
                            f"- Vector {vec.vector_id}: {vec.benchmark_label}",
                            f"  - Operator Baseline: {vec.operator_baseline}",
                            f"  - Incumbent Gap: {vec.incumbent_gap}",
                            f"  - Verifiable Metric: {vec.verifiable_metric}",
                        ])
                if ts.reproducible_workflow_steps:
                    lines.append("##### Reproducible Workflow Steps")
                    for i, step in enumerate(ts.reproducible_workflow_steps, start=1):
                        lines.append(f"{i}. {step}")
            if angle.audit_spec:
                aspec = angle.audit_spec
                lines.extend([
                    "#### SaaS Technical Audit Specification",
                    f"- Framework Author: {aspec.framework_author}",
                    f"- Audit Domain Scope: {aspec.audit_domain_scope}",
                    f"- Utility Asset Type: {aspec.utility_asset_type}",
                ])
                if aspec.metric_thresholds:
                    lines.append("##### Metric Thresholds")
                    for k, v in aspec.metric_thresholds.items():
                        lines.append(f"- {k}: {v}")
                if aspec.checklist:
                    lines.append("##### Technical Audit Checklist")
                    for item in aspec.checklist:
                        lines.extend([
                            f"- Check {item.check_id} [{item.severity}] ({item.category})",
                            f"  - Diagnostic Rule: {item.diagnostic_rule}",
                            f"  - Verification Heuristic: {item.verification_heuristic}",
                            f"  - Remediation Pattern: {item.remediation_pattern}",
                        ])
    else:
        lines.extend([
            "",
            "## Underdog Angles",
            "- No new page angles generated: action held per Search Intent Doctrine.",
        ])

    brief_text = "\n".join(lines) + "\n"

    # Enforce contracts
    assert_no_forbidden_dashes(brief_text, "ContentAngleBrief")
    assert_no_prompt_leakage(brief_text, "ContentAngleBrief")

    return brief_text


def evaluate_content_angles(
    query_data: Dict[str, Any],
    incumbents: Optional[List[Union[Dict[str, Any], IncumbentSummary]]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    total_site_impressions: int = 500,
    candidate_angles: Optional[List[Union[Dict[str, Any], UnderdogAngle]]] = None,
) -> ContentAngleBrief:
    """
    Evaluates candidate query content angles across the complete pipeline:
    1. Enforces Search Intent Doctrine qualification triage.
    2. Disallows page creation on exploratory impressions.
    3. Directs striking distance matching queries to 28-day refactoring overlays.
    4. Evaluates underdog angles against the Grant O Triad and divergence oracle.
    5. Emits certified ContentAngleBrief with verified punctuation contracts.
    """
    # 1. Normalize query data
    q_text = str(query_data.get("query", "")).strip()

    # Extract metrics from gsc_metrics or top-level keys
    gsc = query_data.get("gsc_metrics") or {}
    pos = float(gsc.get("position", query_data.get("position", 100.0)))
    impr = int(float(gsc.get("impressions", query_data.get("impressions", 0))))
    days = int(gsc.get("days_observed", query_data.get("days", 0)))
    clicks = int(float(gsc.get("clicks", query_data.get("clicks", 0))))

    normalized_query_data = {
        "query": q_text,
        "position": pos,
        "impressions": impr,
        "days": days,
        "clicks": clicks,
        "matching_tool": query_data.get("matching_tool"),
        "competing_pages": query_data.get("competing_pages"),
    }

    # Normalize existing tools
    if existing_tools is None:
        existing_tools = query_data.get("existing_site_catalog", query_data.get("existing_tools", []))

    # Normalize incumbents
    if incumbents is None:
        raw_incumbents = query_data.get("incumbents", [])
    else:
        raw_incumbents = incumbents

    incumbent_objects: List[IncumbentSummary] = []
    for inc in raw_incumbents:
        if isinstance(inc, IncumbentSummary):
            incumbent_objects.append(inc)
        elif isinstance(inc, dict):
            incumbent_objects.append(IncumbentSummary.from_dict(inc))

    # 2. Qualify search intent
    qualification = qualify_search_intent(
        normalized_query_data,
        existing_tools=existing_tools,
        total_site_impressions=total_site_impressions,
    )
    triage_action = qualification["action"]
    evaluation_summary = qualification.get("reason", "")
    overlay_spec = qualification.get("overlay_spec")
    candidate_spec = qualification.get("candidate_spec")

    # 3. Extract candidate angles
    raw_angles: List[Union[Dict[str, Any], UnderdogAngle]] = []
    if candidate_angles is not None:
        raw_angles = candidate_angles
    elif "underdog_angle_specs" in query_data:
        raw_angles = query_data["underdog_angle_specs"]
    elif "angles" in query_data:
        raw_angles = query_data["angles"]

    validated_angles: List[UnderdogAngle] = []

    # 4. Process angles according to triage action
    if triage_action == "MONITOR":
        # For exploratory monitoring, do not qualify or publish new page angles
        if raw_angles:
            for item in raw_angles:
                angle_obj = item if isinstance(item, UnderdogAngle) else UnderdogAngle.from_dict(item)
                angle_obj.divergence_score = 0.0
                validated_angles.append(angle_obj)
    else:
        for item in raw_angles:
            angle_obj = item if isinstance(item, UnderdogAngle) else UnderdogAngle.from_dict(item)
            # Validate Grant O Triad
            angle_obj.triad.validate()
            # Calculate divergence against incumbents
            divergence = calculate_token_jaccard_divergence(
                angle_obj.primary_value_proposition,
                incumbent_objects,
            )
            angle_obj.divergence_score = divergence
            if triage_action == "BUILD_PAGE" and divergence < 0.50:
                raise ValueError(
                    f"Candidate angle '{angle_obj.angle_id}' rejected: divergence score {divergence:.4f} is below 0.50 minimum."
                )
            validated_angles.append(angle_obj)

    # 5. Synthesize markdown brief
    brief_markdown = generate_markdown_brief(
        query=q_text,
        triage_action=triage_action,
        evaluation_summary=evaluation_summary,
        angles=validated_angles,
        incumbents=incumbent_objects,
        position=pos,
        impressions=impr,
        overlay_spec=overlay_spec,
    )

    return ContentAngleBrief(
        query=q_text,
        triage_action=triage_action,
        angles=validated_angles,
        evaluation_summary=evaluation_summary,
        markdown_brief=brief_markdown,
        target_position=pos,
        impressions=impr,
        overlay_spec=overlay_spec,
        candidate_spec=candidate_spec,
    )
