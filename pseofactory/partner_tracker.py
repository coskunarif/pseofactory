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

import json
import os
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

    def sync_and_evaluate(
        self,
        force_mail_poll: bool = False,
        personal_fixture: Optional[str] = None,
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
                self.action_bus.route_classification(c)

        # Check for Prexvo standing P2 Gate 1 requirements on action bus if not present
        self._ensure_standing_operator_items()

        # 3. Evaluate property statuses
        ph_report = self._evaluate_property("profithelm", classifications)
        px_report = self._evaluate_property("prexvo", classifications)

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

    def _evaluate_property(
        self,
        property_id: str,
        classifications: List[PartnerEmailClassification],
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

        action_items = self.action_bus.get_all_items(property_id=prop_clean)
        # Prioritize PENDING_OPERATOR over resolved items so pending operator intervention is never masked
        action_map = {}
        for it in action_items:
            if it.partner_key not in action_map or it.status == "PENDING_OPERATOR":
                action_map[it.partner_key] = it

        partner_summaries: List[PartnerStatusSummary] = []
        live_count = 0
        awaiting_count = 0
        followup_count = 0
        pending_exp_count = 0

        # Classifications for this property - prioritize newest correspondence
        prop_classifications = [c for c in classifications if c.property_id == prop_clean]
        class_map: Dict[str, PartnerEmailClassification] = {}
        for c in sorted(prop_classifications, key=lambda x: x.date, reverse=True):
            if c.partner_key not in class_map:
                class_map[c.partner_key] = c

        for p_key, p_obj in affiliates_dict.items():
            # Check corresponding action item
            act_item = action_map.get(p_key)
            class_item = class_map.get(p_key)

            missing_reqs = []
            dest_url = p_obj.default_url

            if p_obj.status == "live":
                op_status = "LIVE_ACTIVE"
                live_count += 1
                is_live = True
            elif p_key == "ipx1031":
                # Active direct in 1031 exchange
                op_status = "LIVE_ACTIVE"
                live_count += 1
                is_live = True
            elif class_item and class_item.classification_type == "APPLICATION_SUBMITTED":
                op_status = "AWAITING_RESPONSE"
                awaiting_count += 1
                is_live = False
                missing_reqs.extend(class_item.missing_requirements)
            elif act_item and act_item.status == "PENDING_OPERATOR":
                op_status = "REQUIRES_FOLLOWUP"
                followup_count += 1
                is_live = False
                missing_reqs.extend(act_item.missing_requirements)
            elif p_obj.status == "pending_p2":
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

            summary = PartnerStatusSummary(
                key=p_obj.key,
                name=p_obj.name,
                property_id=prop_clean,
                category=p_obj.category,
                operational_status=op_status,
                registry_status=p_obj.status,
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
            )
            self._assert_summary_invariants(summary)
            partner_summaries.append(summary)

        # Include additional partner action items that may not be in initial dictionary (e.g. shopify_partner_account)
        for act in action_items:
            if act.partner_key not in affiliates_dict:
                op_status = "REQUIRES_FOLLOWUP" if act.status == "PENDING_OPERATOR" else "RESOLVED"
                if act.status == "PENDING_OPERATOR":
                    followup_count += 1
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
                )
                self._assert_summary_invariants(summary)
                partner_summaries.append(summary)

        # Calculate Readiness Score
        total_p = len(partner_summaries)
        if live_count > 0:
            readiness_score = round((live_count / max(total_p, 1)) * 100, 1)
        else:
            readiness_score = 0.0

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
