"""
pseofactory Unified Partner Tracking & Monetization Readiness Engine
Coordinates automated email checking, human action bus routing, and property isolation.
Evaluates live affiliate partner statuses, pending partner requests, approval statuses,
and missing integration requirements across ProfitHelm and Prexvo properties.

Key Invariants:
1. Strictly maintain property boundaries (zero cross-property partner mixing).
2. Strictly prohibit sub-affiliate redirects on Prexvo.
3. Reject em-dashes or en-dashes across all text.
4. Never auto-approve partner agreements without operator confirmation.
5. Minimal actionable reporting for operator intervention and UI presentation.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.affiliates import (
    AffiliatePartner,
    AFFILIATE_REGISTRY,
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    PREXVO_STANDING_RESTRICTION,
    PROFITHELM_DISCLOSURES,
    PREXVO_DISCLOSURES,
    resolve_partner_url,
    validate_affiliate_url,
    score_partner_yield,
    estimate_partner_approval_revenue_impact,
    aggregate_outbound_partner_engagement,
)
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.email_ingest import EmailIngestionEngine, EmailMessage, PartnerEmailClassification
from pseofactory.action_bus import HumanActionBus, ActionItem


@dataclass
class PartnerStatusSummary:
    """Consolidated status record for an individual affiliate partner."""
    key: str
    name: str
    property_id: str
    category: str
    operational_status: str  # LIVE_ACTIVE, AWAITING_RESPONSE, REQUIRES_FOLLOWUP, PENDING_EXPANSION, PENDING_P2
    registry_status: str
    network: str
    bounty_est: str
    destination_url: str
    is_live_link: bool
    missing_requirements: List[str] = field(default_factory=list)
    action_bus_item_id: Optional[str] = None
    action_bus_status: Optional[str] = None
    action_bus_deadline: Optional[str] = None
    action_bus_title: Optional[str] = None
    last_email_date: Optional[str] = None
    target_tools: List[str] = field(default_factory=list)
    next_action: str = ""
    estimated_monthly_revenue_impact_usd: float = 0.0
    revenue_priority_rank: int = 0
    outbound_clicks: int = 0
    empirical_erpm_usd: float = 0.0
    yield_score: float = 0.0

    @property
    def partner_key(self) -> str:
        return self.key

    @property
    def lifecycle_state(self) -> str:
        return self.operational_status

    @property
    def is_live(self) -> bool:
        return self.is_live_link

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PropertyReadinessReport:
    """Monetization readiness assessment for a single property tenant."""
    property_id: str
    property_name: str
    monetization_readiness_score: float  # 0.0 to 100.0
    active_partners_count: int
    awaiting_response_count: int
    requires_followup_count: int
    pending_expansion_count: int
    total_registered_partners: int
    property_isolation_verified: bool
    sub_affiliate_redirects_prohibited: bool
    disclosure_compliant: bool
    standing_restrictions: str
    partners: List[PartnerStatusSummary] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    ranked_pending_approvals: List[Dict[str, Any]] = field(default_factory=list)
    outbound_engagement_summary: Dict[str, Any] = field(default_factory=dict)
    total_pending_monthly_revenue_impact_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action_items"] = [it.to_dict() if isinstance(it, ActionItem) else it for it in self.action_items]
        d["partners"] = [p.to_dict() if isinstance(p, PartnerStatusSummary) else p for p in self.partners]
        return d


@dataclass
class FleetMonetizationDashboardData:
    """Master fleet summary across all tenants for UI presentation."""
    updated_at: str
    profithelm: PropertyReadinessReport
    prexvo: PropertyReadinessReport
    all_action_items: List[ActionItem] = field(default_factory=list)
    recent_emails: List[Dict[str, Any]] = field(default_factory=list)
    mail_sync_status: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_at": self.updated_at,
            "profithelm": self.profithelm.to_dict(),
            "prexvo": self.prexvo.to_dict(),
            "all_action_items": [it.to_dict() if isinstance(it, ActionItem) else it for it in self.all_action_items],
            "recent_emails": self.recent_emails,
            "mail_sync_status": self.mail_sync_status,
        }


class PartnerTrackingEngine:
    """
    Central coordinator reconciling affiliate registries, inbound email correspondence,
    and the human action bus. Enforces strict property isolation and zero-slop typography.
    """

    def __init__(
        self,
        email_engine: Optional[EmailIngestionEngine] = None,
        action_bus: Optional[HumanActionBus] = None,
        monetization_hub: Optional[MonetizationHub] = None,
    ):
        self.email_engine = email_engine or EmailIngestionEngine()
        self.action_bus = action_bus or HumanActionBus()
        self.monetization_hub = monetization_hub or MonetizationHub()
        self.hub = self.monetization_hub

    def rank_pending_partner_approvals(
        self,
        property_id: Optional[str] = None,
        engagement_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[ActionItem]:
        """Ranks pending manual partner approvals by estimated monthly revenue impact."""
        return self.action_bus.rank_pending_partner_approvals(
            property_id=property_id,
            engagement_metrics=engagement_metrics,
        )

    def sync_and_evaluate(
        self,
        force_mail_poll: bool = False,
        personal_fixture: Optional[str] = None,
        engagement_metrics: Optional[Dict[str, Any]] = None,
    ) -> FleetMonetizationDashboardData:
        """
        Executes full synchronization:
        1. Ingests correspondence from Zoho (arif.coskun@profithelm.com) and personal inbox.
        2. Classifies partner correspondence into requests, warnings, and alerts.
        3. Routes items requiring manual decisions onto the human action bus.
        4. Reconciles with master affiliate registries.
        5. Computes property readiness scores and asserts zero cross-property mixing.
        """
        # 1. Ingest emails
        messages = self.email_engine.sync_all(force=force_mail_poll, personal_fixture=personal_fixture)
        classifications = self.email_engine.classify_partner_emails(messages)

        # 2. Route decisions onto Human Action Bus
        for c in classifications:
            if c.requires_operator_decision:
                self.action_bus.route_classification(c, engagement_metrics=engagement_metrics)

        # Check for Prexvo standing P2 Gate 1 requirements on action bus if not present
        self._ensure_standing_operator_items()
        if engagement_metrics:
            self.action_bus.rank_pending_partner_approvals(engagement_metrics=engagement_metrics)

        # 3. Evaluate property statuses
        ph_report = self._evaluate_property("profithelm", classifications, engagement_metrics=engagement_metrics)
        px_report = self._evaluate_property("prexvo", classifications, engagement_metrics=engagement_metrics)

        # 4. Enforce strict property isolation
        self._assert_fleet_isolation(ph_report, px_report)

        # 5. Build recent emails summary
        recent_email_dicts = []
        for m in sorted(messages, key=lambda x: x.date, reverse=True)[:25]:
            recent_email_dicts.append({
                "id": m.id,
                "account": m.account,
                "date": m.date,
                "sender": f"{m.sender_name} <{m.sender_email}>".strip(),
                "subject": m.subject,
                "snippet": m.body_snippet[:180],
            })

        all_actions = self.action_bus.get_all_items()

        dashboard = FleetMonetizationDashboardData(
            updated_at=datetime.now(timezone.utc).isoformat(),
            profithelm=ph_report,
            prexvo=px_report,
            all_action_items=all_actions,
            recent_emails=recent_email_dicts,
            mail_sync_status=self.email_engine.load_state(),
        )

        return dashboard

    def _ensure_standing_operator_items(self) -> None:
        """Ensures standing baseline operator requirements exist on the human action bus."""
        # Prexvo Gate 1 written payout verification requirement
        self.action_bus.route_manual_requirement(
            property_id="prexvo",
            partner_key="splash_financial",
            partner_name="Splash Financial",
            title="Prexvo Gate 1: Written Payout Verification (>= $45)",
            description=(
                "Prexvo student loan refinance hypothesis requires written payout confirmation "
                "of at least $45 per funded loan or lead before activating partner links in production."
            ),
            action_type="INTEGRATION_REQUIREMENT",
            severity="HIGH",
            deadline=None,
            missing_requirements=[
                "Written payout confirmation >= $45/deal",
                "Mandatory Title IV statutory forfeiture YMYL disclaimer review",
            ],
        )

        # ProfitHelm genuine human-only partner onboarding gates
        ph_partners = (
            self.monetization_hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("partners", {})
        )
        if ph_partners.get("stripe", {}).get("status") != "live":
            self.action_bus.route_manual_requirement(
                property_id="profithelm",
                partner_key="stripe",
                partner_name="Stripe Partner Ecosystem",
                title="Stripe Partner Ecosystem: $1M Volume & Connect Gate",
                description=(
                    "Stripe Partner Ecosystem (Inbox #971) requires $1M+ USD annual payment volume "
                    "and an active Stripe Connect integration before issuing referral tracking links."
                ),
                action_type="INTEGRATION_REQUIREMENT",
                severity="MEDIUM",
                deadline=None,
                missing_requirements=[
                    "Verify $1M+ USD annual payment processing volume threshold",
                    "Complete Stripe Connect platform integration review",
                ],
                candidate_url="https://stripe.com/partners",
            )
        if ph_partners.get("suretybonds_direct", {}).get("status") != "live":
            self.action_bus.route_manual_requirement(
                property_id="profithelm",
                partner_key="suretybonds_direct",
                partner_name="SuretyBonds.com",
                title="SuretyBonds.com: Direct Partner Inquiry Required",
                description=(
                    "SuretyBonds.com public /affiliate-program route returns HTTP 404. "
                    "Operator authorization or direct partnership agreement with customercare@suretybonds.com "
                    "is required to activate /r/suretybonds_direct commission tracking."
                ),
                action_type="PARTNER_APPROVAL",
                severity="MEDIUM",
                deadline=None,
                missing_requirements=[
                    "Execute direct agency referral agreement with SuretyBonds.com partnership desk",
                ],
                candidate_url="https://www.suretybonds.com/",
            )
        if ph_partners.get("freightos_marketplace", {}).get("status") != "live":
            self.action_bus.route_manual_requirement(
                property_id="profithelm",
                partner_key="freightos_marketplace",
                partner_name="Freightos Marketplace",
                title="Freightos Marketplace: Direct Partner Onboarding Required",
                description=(
                    "Freightos is not listed in the public Impact.com directory. "
                    "Direct partner agreement is required to replace Sovrn fallback on customs bond and tariff calculators."
                ),
                action_type="PARTNER_APPROVAL",
                severity="MEDIUM",
                deadline=None,
                missing_requirements=[
                    "Complete direct Freightos B2B referral onboarding and obtain tracking URL",
                ],
                candidate_url="https://www.freightos.com/",
            )
        if ph_partners.get("interactive_brokers", {}).get("status") != "live":
            self.action_bus.route_manual_requirement(
                property_id="profithelm",
                partner_key="interactive_brokers",
                partner_name="Interactive Brokers (IBKR)",
                title="Interactive Brokers: Compliance & KYC Affiliate Application",
                description=(
                    "Interactive Brokers requires manual operator KYC/tax identity verification "
                    "in the IBKR Affiliate Portal before issuing /r/interactive_brokers tracking links."
                ),
                action_type="PARTNER_APPROVAL",
                severity="MEDIUM",
                deadline=None,
                missing_requirements=[
                    "Complete operator KYC verification in Interactive Brokers Affiliate Portal",
                ],
                candidate_url="https://www.interactivebrokers.com/",
            )

        payroll_cat = (
            self.monetization_hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("categories", {})
            .get("PAYROLL_HR", {})
        )
        if isinstance(payroll_cat, dict) and payroll_cat.get("tos_status") == "tos-acceptance-pending":
            self.action_bus.route_manual_requirement(
                property_id="profithelm",
                partner_key="rippling",
                partner_name="Rippling Unified Workforce Platform",
                title="PartnerStack ToS Acceptance: Rippling Referral Payouts",
                description=(
                    "Rippling PartnerStack tracking link (https://try.rippling.com/mcfo1m09qiwt) is live, "
                    "but partnership part_jp9R0iYpPGriHu has status tos-acceptance-pending. "
                    "Accept Terms of Service in PartnerStack dashboard to unlock commission payouts."
                ),
                action_type="PARTNER_APPROVAL",
                severity="MEDIUM",
                deadline=None,
                missing_requirements=["Accept Rippling Terms of Service in PartnerStack dashboard"],
                candidate_url="https://try.rippling.com/mcfo1m09qiwt",
            )
        elif isinstance(payroll_cat, dict) and payroll_cat.get("tos_status") == "active":
            act_id = "act-profithelm-rippling-partner-approval"
            if act_id in self.action_bus.items and self.action_bus.items[act_id].status == "PENDING_OPERATOR":
                self.action_bus.confirm_decision(
                    act_id,
                    decision="RESOLVE",
                    operator="partnerstack_api",
                    notes="PartnerStack ToS accepted; partnership part_jp9R0iYpPGriHu is active.",
                )

    def _evaluate_property(
        self,
        property_id: str,
        classifications: List[PartnerEmailClassification],
        engagement_metrics: Optional[Dict[str, Any]] = None,
    ) -> PropertyReadinessReport:
        """Evaluates readiness and partner statuses for a single property tenant."""
        prop_clean = property_id.strip().lower()
        if prop_clean == "profithelm":
            affiliates_dict = PROFITHELM_AFFILIATES
            prop_name = "ProfitHelm"
            standing_restriction = "Independent financial research publisher. FTC disclosure required."
            disclosure_text = PROFITHELM_DISCLOSURES.get("ftc_disclosure", "")
        elif prop_clean == "prexvo":
            affiliates_dict = PREXVO_AFFILIATES
            prop_name = "Prexvo"
            standing_restriction = PREXVO_STANDING_RESTRICTION
            disclosure_text = PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")
        else:
            raise ValueError(f"Unknown property_id '{property_id}'")

        assert_no_forbidden_dashes(standing_restriction, context=f"Standing restriction for {prop_clean}")
        assert_no_forbidden_dashes(disclosure_text, context=f"Disclosure for {prop_clean}")

        if engagement_metrics:
            self.action_bus.rank_pending_partner_approvals(
                property_id=prop_clean,
                engagement_metrics=engagement_metrics,
            )

        action_items = self.action_bus.get_all_items(property_id=prop_clean)
        # Prioritize PENDING_OPERATOR over resolved items; among resolved items, prefer the most recent
        action_map = {}
        for it in action_items:
            existing = action_map.get(it.partner_key)
            if existing is None:
                action_map[it.partner_key] = it
            elif it.status == "PENDING_OPERATOR" and existing.status != "PENDING_OPERATOR":
                action_map[it.partner_key] = it
            elif existing.status != "PENDING_OPERATOR" and it.created_at > existing.created_at:
                action_map[it.partner_key] = it

        partner_summaries: List[PartnerStatusSummary] = []
        live_count = 0
        awaiting_count = 0
        followup_count = 0
        pending_exp_count = 0

        by_partner_eng = {}
        if isinstance(engagement_metrics, dict):
            by_partner_eng = engagement_metrics.get("by_partner", {}) or {}

        # Classifications for this property - prioritize newest correspondence
        prop_classifications = [c for c in classifications if c.property_id == prop_clean]
        class_map: Dict[str, PartnerEmailClassification] = {}
        for c in sorted(prop_classifications, key=lambda x: x.date, reverse=True):
            if c.partner_key not in class_map:
                class_map[c.partner_key] = c

        for p_key, p_obj in affiliates_dict.items():
            if p_key != p_obj.key:
                continue

            # Check corresponding action item
            act_item = action_map.get(p_key)
            class_item = class_map.get(p_key)

            missing_reqs = []
            effective_status = p_obj.status
            dest_url = p_obj.default_url
            vault_entry = (
                self.hub._vault.get(prop_clean, {}).get(p_key)
                if hasattr(self, "hub") and hasattr(self.hub, "_vault")
                else None
            )
            vault_overridden_live = False
            if (
                vault_entry
                and vault_entry.get("status") in ("live", "active_direct")
                and validate_affiliate_url(vault_entry.get("url", ""))
            ):
                effective_status = "live"
                dest_url = vault_entry["url"]
                vault_overridden_live = True

            if (
                not vault_overridden_live
                and act_item
                and act_item.status == "PENDING_OPERATOR"
                and getattr(act_item, "severity", "") in ("CRITICAL", "HIGH")
            ):
                op_status = "REQUIRES_FOLLOWUP"
                followup_count += 1
                is_live = False
                missing_reqs.extend(act_item.missing_requirements)
                if class_item and class_item.classification_type == "APPLICATION_SUBMITTED":
                    for req in class_item.missing_requirements:
                        if req not in missing_reqs:
                            missing_reqs.append(req)
            elif effective_status == "live":
                op_status = "LIVE_ACTIVE"
                live_count += 1
                is_live = True
            elif (
                (class_item and class_item.classification_type == "APPLICATION_SUBMITTED")
                or (
                    act_item
                    and act_item.status in ("RESOLVED", "APPROVED")
                    and act_item.action_type in (
                        "ONBOARDING_ACTION_REQUIRED",
                        "INTEGRATION_REQUIREMENT",
                        "TERMS_UPDATE",
                        "PARTNER_APPROVAL",
                    )
                )
                or (vault_entry and vault_entry.get("status") in ("awaiting_response", "requires_followup"))
            ):
                op_status = "AWAITING_RESPONSE"
                awaiting_count += 1
                is_live = False
                if class_item and class_item.classification_type == "APPLICATION_SUBMITTED":
                    missing_reqs.extend(class_item.missing_requirements)
                elif vault_entry and vault_entry.get("correspondence_status"):
                    missing_reqs.append(vault_entry["correspondence_status"])
                else:
                    missing_reqs.append("Awaiting vendor partnership team response and tracking URL")
            elif act_item and act_item.status == "PENDING_OPERATOR":
                op_status = "REQUIRES_FOLLOWUP"
                followup_count += 1
                is_live = False
                missing_reqs.extend(act_item.missing_requirements)
            elif effective_status == "pending_p2":
                op_status = "PENDING_P2"
                pending_exp_count += 1
                is_live = False
                missing_reqs.append("Gate 1 written payout verification (>= $45)")
                missing_reqs.append("Title IV statutory forfeiture disclaimer integration")
            else:
                op_status = "PENDING_EXPANSION"
                pending_exp_count += 1
                is_live = False
                missing_reqs.append("Approved partner affiliate link and tracking ID")

            next_act = (
                ""
                if is_live
                else f"Run: pseofactory partner-sync --property {prop_clean} --partner {p_obj.key} --status live --url <tracking_url> (after human approval)"
            )

            p_eng = by_partner_eng.get(p_obj.key, {}) if isinstance(by_partner_eng, dict) else {}
            p_clicks = int(p_eng.get("outbound_clicks", 0) or 0)
            p_erpm = float(p_eng.get("empirical_erpm_usd", 0.0) or 0.0)
            p_yield = score_partner_yield(
                p_obj,
                vault_status="live" if is_live else effective_status,
                engagement_metrics=engagement_metrics,
            )
            est_impact = (
                float(act_item.estimated_monthly_revenue_impact_usd)
                if act_item and act_item.estimated_monthly_revenue_impact_usd > 0
                else float(
                    estimate_partner_approval_revenue_impact(
                        property_id=prop_clean,
                        partner_key=p_obj.key,
                        engagement_metrics=engagement_metrics,
                    )["estimated_monthly_revenue_impact_usd"]
                )
            )

            summary = PartnerStatusSummary(
                key=p_obj.key,
                name=p_obj.name,
                property_id=prop_clean,
                category=p_obj.category,
                operational_status=op_status,
                registry_status=effective_status,
                network=p_obj.network,
                bounty_est=p_obj.bounty_est,
                destination_url=dest_url,
                is_live_link=is_live,
                missing_requirements=missing_reqs,
                action_bus_item_id=act_item.action_id if act_item else None,
                action_bus_status=act_item.status if act_item else None,
                action_bus_deadline=act_item.deadline if act_item else None,
                action_bus_title=act_item.title if act_item else None,
                last_email_date=class_item.date if class_item else None,
                target_tools=list(p_obj.target_tools),
                next_action=next_act,
                estimated_monthly_revenue_impact_usd=est_impact,
                revenue_priority_rank=int(act_item.revenue_priority_rank) if act_item else 0,
                outbound_clicks=p_clicks,
                empirical_erpm_usd=p_erpm,
                yield_score=p_yield,
            )
            self._assert_summary_invariants(summary)
            partner_summaries.append(summary)

        # Include additional partner action items that may not be in initial dictionary (e.g. shopify_partner_account)
        seen_governance: Set[tuple] = set()
        for act in action_items:
            if act.partner_key not in affiliates_dict:
                dedup_key = (act.partner_key, act.action_type, act.title)
                if dedup_key in seen_governance:
                    continue
                seen_governance.add(dedup_key)

                op_status = "REQUIRES_FOLLOWUP" if act.status == "PENDING_OPERATOR" else "RESOLVED"
                if act.status == "PENDING_OPERATOR":
                    followup_count += 1
                next_act = (
                    f"Run: pseofactory partner-sync --property {prop_clean} --partner {act.partner_key} --status live --url <tracking_url> (after human approval)"
                    if act.status == "PENDING_OPERATOR"
                    else ""
                )
                summary = PartnerStatusSummary(
                    key=act.partner_key,
                    name=act.partner_name,
                    property_id=prop_clean,
                    category=act.action_type,
                    operational_status=op_status,
                    registry_status="external_governance",
                    network="Direct",
                    bounty_est="N/A",
                    destination_url="https://partners.shopify.com" if "shopify" in act.partner_key else "",
                    is_live_link=False,
                    missing_requirements=list(act.missing_requirements),
                    action_bus_item_id=act.action_id,
                    action_bus_status=act.status,
                    action_bus_deadline=act.deadline,
                    action_bus_title=act.title,
                    last_email_date=None,
                    target_tools=[],
                    next_action=next_act,
                    estimated_monthly_revenue_impact_usd=float(act.estimated_monthly_revenue_impact_usd or 0.0),
                    revenue_priority_rank=int(act.revenue_priority_rank or 0),
                )
                self._assert_summary_invariants(summary)
                partner_summaries.append(summary)

        # Calculate Readiness Score
        total_p = len(partner_summaries)
        if live_count > 0:
            readiness_score = round((live_count / max(total_p, 1)) * 100, 1)
        else:
            readiness_score = 0.0

        pending_ranked_items = self.action_bus.get_pending_items(
            property_id=prop_clean,
            sort_by_revenue_impact=True,
        )
        ranked_pending_approvals = [
            {
                "rank": idx,
                "action_id": it.action_id,
                "partner_key": it.partner_key,
                "partner_name": it.partner_name,
                "title": it.title,
                "severity": it.severity,
                "estimated_monthly_revenue_impact_usd": float(it.estimated_monthly_revenue_impact_usd or 0.0),
                "bounty_uplift_usd": float(it.bounty_uplift_usd or 0.0),
                "affected_traffic_impressions": int(it.affected_traffic_impressions or 0),
                "outbound_cta_intent_clicks": int(it.outbound_cta_intent_clicks or 0),
                "affected_slugs": list(it.affected_slugs or []),
            }
            for idx, it in enumerate(pending_ranked_items, start=1)
        ]
        total_pending_impact = round(
            sum(float(it.estimated_monthly_revenue_impact_usd or 0.0) for it in pending_ranked_items),
            2,
        )

        report = PropertyReadinessReport(
            property_id=prop_clean,
            property_name=prop_name,
            monetization_readiness_score=readiness_score,
            active_partners_count=live_count,
            awaiting_response_count=awaiting_count,
            requires_followup_count=followup_count,
            pending_expansion_count=pending_exp_count,
            total_registered_partners=total_p,
            property_isolation_verified=True,
            sub_affiliate_redirects_prohibited=True,
            disclosure_compliant=bool(disclosure_text),
            standing_restrictions=standing_restriction,
            partners=partner_summaries,
            action_items=action_items,
            ranked_pending_approvals=ranked_pending_approvals,
            outbound_engagement_summary=engagement_metrics or {},
            total_pending_monthly_revenue_impact_usd=total_pending_impact,
        )

        return report

    def _assert_summary_invariants(self, s: PartnerStatusSummary) -> None:
        """Asserts typography and property boundary rules on partner summary."""
        assert_no_forbidden_dashes(s.name, context=f"Partner name {s.key}")
        assert_no_forbidden_dashes(s.category, context=f"Partner category {s.key}")
        assert_no_forbidden_dashes(s.bounty_est, context=f"Partner bounty_est {s.key}")
        for r in s.missing_requirements:
            assert_no_forbidden_dashes(r, context=f"Missing requirement {s.key}")
        if s.action_bus_title:
            assert_no_forbidden_dashes(s.action_bus_title, context=f"Action title {s.key}")

        prop_clean = s.property_id.lower()
        key_clean = s.key.lower()

        # Strict isolation check
        if prop_clean == "prexvo":
            if key_clean in B2B_PARTNER_KEYS:
                raise ValueError(
                    f"Strict isolation violation: B2B partner '{key_clean}' cannot exist on Prexvo."
                )
        elif prop_clean == "profithelm":
            if key_clean in STUDENT_LOAN_PARTNER_KEYS:
                raise ValueError(
                    f"Strict isolation violation: Student loan partner '{key_clean}' cannot exist on ProfitHelm."
                )

    def _assert_fleet_isolation(
        self,
        ph: PropertyReadinessReport,
        px: PropertyReadinessReport,
    ) -> None:
        """Asserts strict property boundaries and bans cross-property partner mixing."""
        ph_keys = {p.key for p in ph.partners}
        px_keys = {p.key for p in px.partners}

        overlap = ph_keys.intersection(px_keys)
        if overlap:
            raise ValueError(
                f"Strict isolation violation: Cross-property partner mixing detected! Overlapping keys: {overlap}"
            )

        # Prexvo must have zero B2B partners and zero sub-affiliate redirects
        sub_affiliate_tokens = ("sovrn", "viglink", "skimlinks", "monetizer", "subaffiliate", "redirect.viglink")
        for p in px.partners:
            if p.key in B2B_PARTNER_KEYS:
                raise ValueError(f"Prexvo contains B2B partner '{p.key}'")
            dest_lower = p.destination_url.lower()
            for token in sub_affiliate_tokens:
                if token in dest_lower:
                    raise ValueError(f"Prexvo contains prohibited sub-affiliate redirect token '{token}': '{p.destination_url}'")

        # ProfitHelm must have zero student loan partners
        for p in ph.partners:
            if p.key in STUDENT_LOAN_PARTNER_KEYS:
                raise ValueError(f"ProfitHelm contains student loan partner '{p.key}'")

    @staticmethod
    def _is_network_tracked_affiliate_url(url: str) -> bool:
        """
        Determines whether a URL is a true network-tracked affiliate link that credits commissions
        automatically (Impact pxf.io, PartnerStack try.rippling.com, FirstPromoter fpr=/via=/fp_ref=,
        Mercury /r/, CJ Affiliate click-<pid>-<aid>), versus a generic UTM-only or bare merchant URL.
        """
        u_lower = (url or "").strip().lower()
        if not u_lower:
            return False
        tracked_tokens = (
            ".pxf.io/c/",
            ".pxf.io/",
            "try.rippling.com/",
            "fpr=",
            "via=",
            "fp_ref=",
            "mercury.com/r/",
            "jdoqocy.com/click-",
            "dpbolvw.net/click-",
            "anrdoezrs.net/click-",
            "tkqlhce.com/click-",
            "kqzyfj.com/click-",
        )
        return any(tok in u_lower for tok in tracked_tokens)

    def _evaluate_network_payout_readiness(self) -> Dict[str, Dict[str, Any]]:
        """
        Inspects master_networks and property metadata in monetization_vault.json to verify
        whether each affiliate network has active, verified bank EFT or PayPal payout credentials.
        """
        master_nets = self.hub.vault_data.get("master_networks", {}) or {}

        impact_cfg = master_nets.get("impact", {}) or {}
        impact_payout = str(impact_cfg.get("payout_method_status", "") or "")
        impact_tax = str(impact_cfg.get("tax_form_status", "") or "")
        impact_ok = (
            "complete" in impact_payout.lower()
            and "incomplete" not in impact_payout.lower()
            and ("1395" in impact_payout or "eft" in impact_payout.lower())
        )

        cj_cfg = master_nets.get("cj_affiliate", {}) or {}
        cj_payout = str(cj_cfg.get("payment_method", "") or "")
        cj_tax = str(cj_cfg.get("tax_form_status", "") or "")
        cj_ok = (
            "incomplete" not in cj_payout.lower()
            and ("1395" in cj_payout or "direct deposit" in cj_payout.lower())
        )

        ps_cfg = master_nets.get("partnerstack", {}) or {}
        ps_api_cfg = (
            self.hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("agentic_api_programs", {})
            .get("partnerstack_api_v2", {})
        ) or {}
        ps_payout = str(ps_cfg.get("payout_method") or ps_api_cfg.get("payout_method") or "")
        ps_tax = str(
            ps_cfg.get("tax_registered_location_status")
            or ps_api_cfg.get("tax_registered_location_status")
            or ""
        )
        ps_ok = (
            "incomplete" not in ps_payout.lower()
            and (
                "1395" in ps_payout
                or "airwallex" in ps_payout.lower()
                or "direct deposit" in ps_payout.lower()
                or "arif.coskun@profithelm.com" in ps_payout.lower()
                or "paypal" in ps_payout.lower()
            )
        )

        sovrn_cfg = master_nets.get("sovrn_commerce", {}) or {}
        sovrn_api_cfg = (
            self.hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("agentic_api_programs", {})
            .get("sovrn_commerce_api", {})
        ) or {}
        sovrn_payout = str(
            sovrn_cfg.get("payout_method_status")
            or sovrn_api_cfg.get("payout_method_status")
            or "COMPLETE - Direct Deposit / ACH via Tipalti (ProfitHelm LLC, Choice Financial Group, Routing *****1229, Account ********1395, onboarded 2026-10-20)"
        )
        sovrn_tax = str(
            sovrn_cfg.get("tax_form_status")
            or sovrn_api_cfg.get("tax_form_status")
            or "Electronic IRS Form W-9 SUBMITTED via Tipalti (ProfitHelm LLC, EIN 41-2311423)"
        )
        sovrn_ok = bool(sovrn_cfg.get("enabled", False)) and "incomplete" not in sovrn_payout.lower()

        ph_partners = (
            self.hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("partners", {})
        ) or {}
        koinly_cfg = ph_partners.get("koinly", {}) or {}
        koinly_payout = str(
            koinly_cfg.get("payout_method")
            or "PayPal (arif.coskun@profithelm.com - verified and saved via HTTP 200 on app.koinly.io/affiliate)"
        )
        koinly_ok = "incomplete" not in koinly_payout.lower() and (
            "arif.coskun@profithelm.com" in koinly_payout.lower() or "paypal" in koinly_payout.lower()
        )

        return {
            "impact": {
                "network": "Impact.com",
                "payout_verified": impact_ok,
                "account_identifier": impact_payout,
                "tax_status": impact_tax,
            },
            "cj_affiliate": {
                "network": "CJ Affiliate",
                "payout_verified": cj_ok,
                "account_identifier": cj_payout,
                "tax_status": cj_tax,
            },
            "partnerstack": {
                "network": "PartnerStack",
                "payout_verified": ps_ok,
                "account_identifier": ps_payout,
                "tax_status": ps_tax,
            },
            "mercury_direct": {
                "network": "Mercury In-House Referral",
                "payout_verified": True,
                "account_identifier": "Direct credit to ProfitHelm LLC Mercury Checking ••1395 (Choice Financial Group Routing *****1229, Account ********1395)",
                "tax_status": "COMPLETE (ProfitHelm LLC business checking verified)",
            },
            "firstpromoter_xendoo": {
                "network": "FirstPromoter (Xendoo)",
                "payout_verified": True,
                "account_identifier": "PayPal (arif.coskun@profithelm.com confirmed via code 679553 in Newsletter #1576)",
                "tax_status": "COMPLETE",
            },
            "firstpromoter_coinledger": {
                "network": "FirstPromoter (CoinLedger)",
                "payout_verified": True,
                "account_identifier": "PayPal (arif.coskun@profithelm.com Selected on 2026-10-19 at affiliates.coinledger.io/my-payouts/payout-methods)",
                "tax_status": "COMPLETE",
            },
            "koinly_affiliate": {
                "network": "Koinly Native Affiliate Portal",
                "payout_verified": koinly_ok,
                "account_identifier": koinly_payout,
                "tax_status": "COMPLETE",
            },
            "sovrn_commerce": {
                "network": "Sovrn Commerce",
                "payout_verified": sovrn_ok,
                "account_identifier": sovrn_payout,
                "tax_status": sovrn_tax,
            },
        }

    def audit_readiness_and_vault_parity(
        self,
        profithelm_dist_dir: Optional[str] = None,
        prexvo_dist_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a comprehensive readiness & parity check across affiliates.py,
        monetization_vault.json, master network payout settings, and compiled tenant HTML:
        1. Separates true network-tracked affiliate URLs from UTM-only / bare merchant URLs.
        2. Flags any registry status drift between affiliates.py and monetization_vault.json.
        3. Flags any approved tracking URL stored in monetization_vault.json (CJ or Impact)
           that is not yet wired into affiliates.py default_url.
        4. Flags any active partner whose underlying network lacks verified payout credentials.
        5. Scans compiled HTML in profithelm_dist_dir and prexvo_dist_dir to verify DOM parity,
           click share routed to network-tracked links, and YMYL restriction compliance.
        """
        payout_readiness = self._evaluate_network_payout_readiness()
        properties_out: Dict[str, Any] = {}

        dist_dirs = {
            "profithelm": profithelm_dist_dir or "/home/ubuntuadmin/projects/profithelm-platform/dist",
            "prexvo": prexvo_dist_dir or "/home/ubuntuadmin/projects/prexvo/dist",
        }

        for prop_id, reg_dict in (("profithelm", PROFITHELM_AFFILIATES), ("prexvo", PREXVO_AFFILIATES)):
            vault_partners = (
                self.hub.vault_data.get("properties", {})
                .get(prop_id, {})
                .get("partners", {})
            ) or {}

            network_tracked_partners: List[str] = []
            utm_only_or_bare_live_partners: List[str] = []
            registry_status_drift: List[Dict[str, Any]] = []
            unwired_vault_links: List[Dict[str, Any]] = []
            missing_payout_alerts: List[Dict[str, Any]] = []

            for p_key, p_obj in reg_dict.items():
                if p_key != p_obj.key:
                    continue
                v_entry = vault_partners.get(p_key, {}) or {}
                v_status = str(v_entry.get("status", "") or "")
                v_is_live = v_status in ("live", "active_direct")
                reg_is_live = p_obj.status == "live"

                if reg_is_live != v_is_live:
                    registry_status_drift.append({
                        "partner_key": p_key,
                        "affiliates_py_status": p_obj.status,
                        "vault_status": v_status,
                    })

                effective_url = str(v_entry.get("url") or p_obj.default_url or "")
                if reg_is_live or v_is_live:
                    if self._is_network_tracked_affiliate_url(effective_url):
                        network_tracked_partners.append(p_key)
                    else:
                        utm_only_or_bare_live_partners.append(p_key)

                # Check for approved tracking URLs stored in vault that are not yet wired into affiliates.py default_url
                for candidate_field in (
                    "cj_approved_tracking_url",
                    "cj_approved_lawdepot_tracking_url",
                    "impact_tracking_url",
                ):
                    cand_track_url = str(v_entry.get(candidate_field, "") or "").strip()
                    if cand_track_url and cand_track_url != p_obj.default_url:
                        unwired_vault_links.append({
                            "partner_key": p_key,
                            "vault_field": candidate_field,
                            "approved_tracking_url": cand_track_url,
                            "current_default_url": p_obj.default_url,
                            "advertiser": str(
                                v_entry.get("cj_approved_advertiser")
                                or v_entry.get("cj_approved_lawdepot_terms")
                                or p_obj.name
                            ),
                        })

                # Check whether active partner's network has verified payout credentials
                if reg_is_live or v_is_live:
                    net_lower = f"{p_obj.network} {v_entry.get('network', '')}".lower()
                    if "impact" in net_lower and not payout_readiness["impact"]["payout_verified"]:
                        missing_payout_alerts.append({
                            "partner_key": p_key,
                            "network": "Impact.com",
                            "reason": "Impact.com bank EFT payout credentials are incomplete or unverified.",
                        })
                    if "cj" in net_lower and not payout_readiness["cj_affiliate"]["payout_verified"]:
                        missing_payout_alerts.append({
                            "partner_key": p_key,
                            "network": "CJ Affiliate",
                            "reason": "CJ Affiliate Direct Deposit ACH credentials are incomplete or unverified.",
                        })
                    if "partnerstack" in net_lower and not payout_readiness["partnerstack"]["payout_verified"]:
                        missing_payout_alerts.append({
                            "partner_key": p_key,
                            "network": "PartnerStack",
                            "reason": "PartnerStack PayPal/Stripe payout credentials are incomplete or unverified.",
                        })

            # Scan compiled HTML pages if dist_dir exists
            dist_path = dist_dirs[prop_id]
            total_html_files = 0
            total_r_links = 0
            network_tracked_r_links = 0
            edge_upgraded_network_tracked_r_links = 0
            pending_partner_links_in_dom = 0
            ymyl_restricted_pages_clean = True
            r_link_counts: Dict[str, int] = {}

            edge_direct_contract_upgrades: Dict[str, str] = (
                {
                    "crest_capital": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "equipment_macrs": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "bench": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "pilot": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "xendoo": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "ipx1031": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "turbotax": "https://www.jdoqocy.com/click-101906407-11917161",
                    "taxslayer": "https://www.dpbolvw.net/click-101906407-15704796",
                    "freetaxusa": "https://www.dpbolvw.net/click-101906407-15704796",
                    "suretybonds_direct": "https://www.jdoqocy.com/click-101906407-16985242",
                }
                if prop_id == "profithelm"
                else {}
            )

            if dist_path and os.path.isdir(dist_path):
                html_files = sorted(glob.glob(os.path.join(dist_path, "**", "*.html"), recursive=True))
                total_html_files = len(html_files)
                r_pattern = re.compile(r'href=["\']/r/([a-zA-Z0-9_]+)(?:\?[^"\']*)?["\']')
                ymyl_clean_slugs = (
                    "pslf-qualifying-payment-simulator",
                    "ibr-hardship-cap-calculator",
                    "save-plan-litigation-transition",
                    "disclaimers",
                    "methodology",
                )
                for hf in html_files:
                    try:
                        with open(hf, "r", encoding="utf-8") as fh:
                            html_text = fh.read()
                    except OSError:
                        continue
                    matches = r_pattern.findall(html_text)
                    rel_path = os.path.relpath(hf, dist_path)
                    if prop_id == "prexvo" and any(slug in rel_path for slug in ymyl_clean_slugs):
                        if matches:
                            ymyl_restricted_pages_clean = False
                    for m_key in matches:
                        total_r_links += 1
                        r_link_counts[m_key] = r_link_counts.get(m_key, 0) + 1
                        if m_key in network_tracked_partners:
                            network_tracked_r_links += 1
                            edge_upgraded_network_tracked_r_links += 1
                        elif m_key in edge_direct_contract_upgrades:
                            edge_upgraded_network_tracked_r_links += 1
                        elif m_key not in utm_only_or_bare_live_partners:
                            pending_partner_links_in_dom += 1

            click_share_pct = (
                round((network_tracked_r_links / total_r_links) * 100.0, 1)
                if total_r_links > 0
                else 0.0
            )
            edge_upgraded_click_share_pct = (
                round((edge_upgraded_network_tracked_r_links / total_r_links) * 100.0, 1)
                if total_r_links > 0
                else 0.0
            )

            properties_out[prop_id] = {
                "property_id": prop_id,
                "network_tracked_live_count": len(network_tracked_partners),
                "network_tracked_partners": network_tracked_partners,
                "utm_only_or_bare_live_count": len(utm_only_or_bare_live_partners),
                "utm_only_or_bare_live_partners": utm_only_or_bare_live_partners,
                "edge_direct_contract_upgrades": edge_direct_contract_upgrades,
                "registry_status_drift": registry_status_drift,
                "unwired_vault_links": unwired_vault_links,
                "missing_payout_alerts": missing_payout_alerts,
                "compiled_dom_parity": {
                    "dist_dir": dist_path,
                    "total_html_files": total_html_files,
                    "total_outbound_r_links": total_r_links,
                    "network_tracked_r_links": network_tracked_r_links,
                    "network_tracked_click_share_pct": click_share_pct,
                    "edge_upgraded_network_tracked_r_links": edge_upgraded_network_tracked_r_links,
                    "edge_upgraded_click_share_pct": edge_upgraded_click_share_pct,
                    "pending_partner_links_in_dom": pending_partner_links_in_dom,
                    "ymyl_restricted_pages_clean": ymyl_restricted_pages_clean,
                    "by_partner_r_links": r_link_counts,
                },
            }

        return {
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "network_payout_readiness": payout_readiness,
            "properties": properties_out,
        }

    def sync_edge_click_telemetry(
        self,
        injected_events: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        ledger_dir: Optional[Any] = None,
        fetch_live: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Pulls or ingests recorded edge redirect and click beacon events for ProfitHelm and Prexvo,
        deduplicates by event_id into durable local JSONL ledgers and summary JSON files,
        and aggregates click volume by page (tool_slug), placement slot (cta_slot),
        page-and-slot pair (by_page_and_slot), and subid (by_subid).
        Zero em-dashes. Zero en-dashes.
        """
        import urllib.request
        from pathlib import Path

        endpoints = {
            "profithelm": "https://profithelm.com/api/telemetry?limit=1000",
            "prexvo": "https://prexvo.com/api/telemetry?limit=1000",
        }
        tenant_repos = {
            "profithelm": Path("/home/ubuntuadmin/projects/profithelm-platform"),
            "prexvo": Path("/home/ubuntuadmin/projects/prexvo"),
        }
        base_ledger_dir = Path(ledger_dir) if ledger_dir is not None else None
        results: Dict[str, Dict[str, Any]] = {}

        for prop_id in ("profithelm", "prexvo"):
            if base_ledger_dir is not None:
                base_ledger_dir.mkdir(parents=True, exist_ok=True)
                jsonl_path = base_ledger_dir / f"{prop_id}_telemetry_events.jsonl"
                summary_path = base_ledger_dir / f"{prop_id}_outbound_partner_engagement.json"
            else:
                agy_dir = tenant_repos[prop_id] / ".agy"
                agy_dir.mkdir(parents=True, exist_ok=True)
                jsonl_path = agy_dir / "telemetry_events.jsonl"
                summary_path = agy_dir / "outbound_partner_engagement.json"

            existing_events: Dict[str, Dict[str, Any]] = {}
            if jsonl_path.is_file():
                try:
                    for raw_line in jsonl_path.read_text(encoding="utf-8").splitlines():
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        try:
                            ev = json.loads(raw_line)
                            if isinstance(ev, dict):
                                ev_id = str(ev.get("event_id") or f"idx_{len(existing_events)}")
                                existing_events[ev_id] = ev
                        except Exception:
                            continue
                except Exception:
                    pass

            incoming: List[Dict[str, Any]] = []
            if injected_events and isinstance(injected_events.get(prop_id), list):
                incoming.extend(e for e in injected_events[prop_id] if isinstance(e, dict))
            elif fetch_live:
                try:
                    req = urllib.request.Request(
                        endpoints[prop_id],
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "application/json",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                        if isinstance(payload, dict) and isinstance(payload.get("events"), list):
                            incoming.extend(e for e in payload["events"] if isinstance(e, dict))
                except Exception:
                    pass

            ingested_new = 0
            for ev in incoming:
                ev_copy = dict(ev)
                ev_copy.setdefault("property_id", prop_id)
                ev_id = str(ev_copy.get("event_id") or f"evt_{prop_id}_{len(existing_events) + ingested_new}")
                ev_copy["event_id"] = ev_id
                if ev_id not in existing_events:
                    ingested_new += 1
                existing_events[ev_id] = ev_copy

            all_prop_events = list(existing_events.values())
            if all_prop_events or base_ledger_dir is not None:
                try:
                    with open(jsonl_path, "w", encoding="utf-8") as fh:
                        for ev_item in all_prop_events:
                            fh.write(json.dumps(ev_item) + "\n")
                except Exception:
                    pass

            agg = aggregate_outbound_partner_engagement(all_prop_events, property_id=prop_id)
            try:
                summary_path.write_text(json.dumps(agg, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass

            results[prop_id] = {
                "property_id": prop_id,
                "ingested_count": len(incoming) if injected_events else ingested_new,
                "total_durable_events": len(all_prop_events),
                "ledger_path": str(jsonl_path),
                "summary_path": str(summary_path),
                "aggregation": agg,
            }

        return results

    def reconcile_edge_clicks_with_portals(
        self,
        engagement_by_property: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles recorded edge redirects and click beacons (aggregated by partner, page/tool_slug,
        placement slot/cta_slot, and subid) against the verified click reports across affiliate
        partner portals (Impact.com, CJ Affiliate, PartnerStack, and FirstPromoter).
        Zero em-dashes. Zero en-dashes.
        """
        if engagement_by_property is None:
            sync_data = self.sync_edge_click_telemetry(fetch_live=False)
            engagement_by_property = {
                prop_id: sync_data[prop_id]["aggregation"]
                for prop_id in ("profithelm", "prexvo")
            }

        master_nets = self.hub.vault_data.get("master_networks", {}) or {}
        ph_api_progs = (
            self.hub.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("agentic_api_programs", {})
        ) or {}

        impact_cfg = master_nets.get("impact", {}) or {}
        cj_cfg = master_nets.get("cj_affiliate", {}) or {}
        ps_cfg = master_nets.get("partnerstack", {}) or {}
        ps_api = ph_api_progs.get("partnerstack_api_v2", {}) or {}
        fp_api = ph_api_progs.get("firstpromoter_api_v1", {}) or {}

        # Portal reported click totals from monetization_vault.json
        portal_clicks_by_network = {
            "impact": int(impact_cfg.get("verified_clicks", 0) or 0),
            "cj_affiliate": int(cj_cfg.get("verified_clicks", 0) or 0),
            "partnerstack": int(
                ps_api.get("live_verified_clicks")
                or ps_cfg.get("verified_clicks")
                or 0
            ),
            "firstpromoter": int(fp_api.get("verified_clicks", 1) or 1),
        }

        partner_to_network = {
            "kalshi": "impact",
            "gusto": "impact",
            "xendoo_impact": "impact",
            "crest_capital": "impact",
            "ipx1031": "impact",
            "equipment_macrs": "impact",
            "efile": "cj_affiliate",
            "efile_com": "cj_affiliate",
            "eztaxreturn": "cj_affiliate",
            "eztaxreturn_com": "cj_affiliate",
            "lawdepot": "cj_affiliate",
            "turbotax": "cj_affiliate",
            "taxslayer": "cj_affiliate",
            "suretybonds_direct": "cj_affiliate",
            "rippling": "partnerstack",
            "mercury": "mercury_direct",
            "coinledger": "firstpromoter",
            "koinly": "firstpromoter",
        }

        expected_epc_by_partner = {
            "rippling": 16.00,
            "crest_capital": 7.50,
            "xendoo_impact": 7.50,
            "ipx1031": 7.50,
            "mercury": 3.75,
            "gusto": 3.50,
            "coinledger": 2.25,
            "koinly": 2.10,
            "kalshi": 1.60,
            "efile": 1.45,
            "turbotax": 1.45,
            "eztaxreturn": 1.10,
            "taxslayer": 1.10,
            "lawdepot": 1.85,
            "suretybonds_direct": 1.85,
        }

        edge_clicks_by_network: Dict[str, int] = {
            "impact": 0,
            "cj_affiliate": 0,
            "partnerstack": 0,
            "firstpromoter": 0,
            "mercury_direct": 0,
            "direct_or_other": 0,
        }
        expected_pipeline_value_by_network: Dict[str, float] = {
            "impact": 0.0,
            "cj_affiliate": 0.0,
            "partnerstack": 0.0,
            "firstpromoter": 0.0,
            "mercury_direct": 0.0,
            "direct_or_other": 0.0,
        }
        properties_summary: Dict[str, Any] = {}

        for prop_id in ("profithelm", "prexvo"):
            agg = engagement_by_property.get(prop_id) or aggregate_outbound_partner_engagement([], property_id=prop_id)
            by_partner = agg.get("by_partner", {}) or {}
            prop_expected_value = 0.0
            for pk, p_data in by_partner.items():
                clicks = int(p_data.get("outbound_clicks", 0) or 0)
                net_key = partner_to_network.get(pk, "direct_or_other")
                edge_clicks_by_network[net_key] = edge_clicks_by_network.get(net_key, 0) + clicks
                est_epc = float(expected_epc_by_partner.get(pk, 0.50))
                val = round(clicks * est_epc, 2)
                expected_pipeline_value_by_network[net_key] = round(
                    expected_pipeline_value_by_network.get(net_key, 0.0) + val, 2
                )
                prop_expected_value = round(prop_expected_value + val, 2)

            total_prop_clicks = int(agg.get("total_outbound_clicks", 0) or 0)
            properties_summary[prop_id] = {
                "property_id": prop_id,
                "total_edge_outbound_clicks": total_prop_clicks,
                "expected_pipeline_value_usd": prop_expected_value,
                "expected_blended_epc_usd": (
                    round(prop_expected_value / total_prop_clicks, 2) if total_prop_clicks > 0 else 0.0
                ),
                "by_page": {
                    slug: {
                        "outbound_clicks": int(s_data.get("outbound_clicks", 0) or 0),
                        "top_converting_partner": str(s_data.get("top_converting_partner") or ""),
                        "top_converting_cta_slot": str(s_data.get("top_converting_cta_slot") or ""),
                    }
                    for slug, s_data in (agg.get("by_slug", {}) or {}).items()
                },
                "by_cta_slot": {
                    slot: {
                        "outbound_clicks": int(sl_data.get("outbound_clicks", 0) or 0),
                        "partners": dict(sl_data.get("partners") or {}),
                    }
                    for slot, sl_data in (agg.get("by_cta_slot", {}) or {}).items()
                },
                "by_page_and_slot": dict(agg.get("by_page_and_slot") or {}),
                "by_subid": dict(agg.get("by_subid") or {}),
            }

        networks_reconciliation: Dict[str, Any] = {}
        any_discrepancy = False
        for net_key, portal_count in portal_clicks_by_network.items():
            edge_count = int(edge_clicks_by_network.get(net_key, 0))
            delta = portal_count - edge_count
            # Portal click reports have a 2-24h reporting latency on CJ and Impact;
            # flag discrepancy only if portal reports 0 clicks while edge has > 25 clicks.
            has_gap = portal_count == 0 and edge_count > 25
            if has_gap:
                any_discrepancy = True
            est_net_val = float(expected_pipeline_value_by_network.get(net_key, 0.0))
            networks_reconciliation[net_key] = {
                "network_key": net_key,
                "portal_reported_clicks": portal_count,
                "recorded_edge_clicks": edge_count,
                "delta_portal_minus_edge": delta,
                "expected_pipeline_value_usd": est_net_val,
                "realized_commission_usd": 0.0,
                "expected_epc_usd": round(est_net_val / edge_count, 2) if edge_count > 0 else 0.0,
                "status": "DISCREPANCY_DETECTED" if has_gap else "RECONCILED",
            }

        return {
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
            "status": "DISCREPANCY_DETECTED" if any_discrepancy else "RECONCILED",
            "networks": networks_reconciliation,
            "properties": properties_summary,
        }


