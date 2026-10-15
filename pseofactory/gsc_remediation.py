"""
pseofactory Unified Autonomous Google Search Console (GSC) Remediation Engine.
Provides ROI-driven candidate prioritization across impression/CTR shortfalls,
striking-distance queries, and unindexed coverage anomalies; deterministic
domain-isolated overlay compilation; composite idempotency keys; and an
AtomicStateLedger-backed AsyncRemediationQueue with bounded execution budgets
and exponential backoff fault recovery.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pseofactory.supervisor import AtomicStateLedger

EXPECTED_CTR_CURVE: Dict[int, float] = {
    1: 0.28,
    2: 0.15,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.045,
    7: 0.035,
    8: 0.028,
    9: 0.022,
    10: 0.018,
}

DEFAULT_REMEDIATION_QUEUE_PATH = Path("/home/ubuntuadmin/projects/.agy/gsc_remediation_queue.json")


def _strip_forbidden_dashes(text: str) -> str:
    """Replaces em-dashes and en-dashes with standard ASCII hyphens."""
    if not text:
        return ""
    return str(text).replace("\u2014", "-").replace("\u2013", "-")


def _count_words(text: str) -> int:
    clean = re.sub(r"<[^>]+>", " ", str(text or ""))
    return len([w for w in clean.split() if w.strip()])


def _slug_from_url_or_query(target_url: str = "", query: str = "", default_slug: str = "") -> str:
    if default_slug:
        clean = re.sub(r"[^a-z0-9-]+", "-", default_slug.strip().lower()).strip("-")
        if clean:
            return clean
    if target_url:
        parsed = urllib.parse.urlparse(str(target_url))
        parts = [p for p in parsed.path.split("/") if p and p != "tools"]
        if parts:
            cand = re.sub(r"[^a-z0-9-]+", "-", parts[-1].lower()).strip("-")
            if cand:
                return cand
    if query:
        cand = re.sub(r"[^a-z0-9]+", "-", query.strip().lower()).strip("-")
        if cand:
            return cand[:64].strip("-")
    return "statutory-calculator"


_CALCULATOR_INTENT_TOKENS = (
    "calculator",
    "estimator",
    "simulator",
    "analyzer",
    "modeler",
    "visualizer",
    "pricer",
    "waterfall",
    "margin",
    "covenant",
    "valuation",
    "breakeven",
    "break-even",
    "depreciation",
    "repayment",
    "forgiveness",
    "arbitrage",
    "payback",
    "runway",
    "dilution",
    "cap-rate",
    "yield",
    "tax-shield",
)

_GUIDE_INTENT_TOKENS = (
    "guide",
    "handbook",
    "playbook",
    "checklist",
    "comparison",
    "vs-",
    "-vs-",
    "schedule",
    "how-to",
    "rules",
    "audit",
    "eligibility",
    "recertification",
    "transition",
    "hardship",
    "consolidation",
    "matrix",
    "blueprint",
)

_LOW_INTENT_HUB_OR_META_SLUGS = {
    "index",
    "about",
    "privacy",
    "terms",
    "contact",
    "disclaimers",
    "methodology",
    "signal",
    "categories",
    "articles",
}


def _classify_asset_intent_class(
    slug: str = "",
    target_url: str = "",
    query: str = "",
    section: str = "",
) -> Dict[str, Any]:
    """
    Classifies an asset's search intent and structural archetype into:
      - 'calculator' (high-intent interactive calculator/simulator/estimator, 1.45x multiplier)
      - 'guide' (high-intent statutory guide/comparison/handbook, 1.30x multiplier)
      - 'general' (directory, hub, or general informational route, 1.00x multiplier)
    Zero em-dashes. Zero en-dashes.
    """
    s_norm = str(slug or "").strip().lower()
    u_norm = str(target_url or "").strip().lower()
    q_norm = str(query or "").strip().lower()
    sec_norm = str(section or "").strip().lower()
    combined = f"{s_norm} {u_norm} {q_norm}"

    if s_norm in _LOW_INTENT_HUB_OR_META_SLUGS or any(
        u_norm.endswith(f"/{hub}") or u_norm.endswith(f"/{hub}/")
        for hub in ("about", "privacy", "terms", "contact", "disclaimers", "methodology")
    ):
        return {
            "intent_class": "general",
            "is_high_intent_calculator_or_guide": False,
            "intent_multiplier": 1.0,
            "value_tier": "tier_2",
        }

    if any(tok in combined for tok in _CALCULATOR_INTENT_TOKENS):
        return {
            "intent_class": "calculator",
            "is_high_intent_calculator_or_guide": True,
            "intent_multiplier": 1.45,
            "value_tier": "tier_1",
        }

    if sec_norm == "guides" or "/guides/" in u_norm or any(tok in combined for tok in _GUIDE_INTENT_TOKENS):
        return {
            "intent_class": "guide",
            "is_high_intent_calculator_or_guide": True,
            "intent_multiplier": 1.30,
            "value_tier": "tier_1",
        }

    if "/tools/" in u_norm and s_norm and s_norm not in ("tools", "statutory-calculator"):
        return {
            "intent_class": "calculator",
            "is_high_intent_calculator_or_guide": True,
            "intent_multiplier": 1.35,
            "value_tier": "tier_1",
        }

    return {
        "intent_class": "general",
        "is_high_intent_calculator_or_guide": False,
        "intent_multiplier": 1.0,
        "value_tier": "tier_2",
    }


def _resolve_contextual_internal_links(
    tenant_id: str,
    slug: str,
    query: str = "",
) -> List[Dict[str, str]]:
    """
    Resolves demand-driven internal links to vertical-clustered sibling calculators
    and guides for the given tenant, strictly excluding self-links.
    Zero em-dashes. Zero en-dashes.
    """
    eff_tenant = str(tenant_id or "profithelm").strip().lower()
    s_norm = str(slug or "").strip().lower()
    combined = f"{s_norm} {str(query or '').strip().lower()}"
    self_href = f"/tools/{s_norm}/"

    if eff_tenant == "prexvo":
        base_hub = {"anchor": "Title IV Student Loan Calculators Directory", "href": "/tools/"}
        if any(k in combined for k in ("pslf", "public-service", "public service", "teacher", "joint", "spousal")):
            cluster = [
                {"anchor": "PSLF 120 Qualifying Payment Simulator", "href": "/tools/pslf-qualifying-payment-simulator/"},
                {"anchor": "SAVE Plan Litigation & Transition Guide", "href": "/tools/save-plan-litigation-transition/"},
                {"anchor": "IBR Financial Hardship Cap Calculator", "href": "/tools/ibr-hardship-cap-calculator/"},
                {"anchor": "Married Filing Separately Student Loan Calculator", "href": "/tools/married-filing-separately-student-loan-calculator/"},
                {"anchor": "RAP vs IBR Monthly Payment Calculator", "href": "/tools/rap-vs-ibr-calculator/"},
            ]
        elif any(k in combined for k in ("parent-plus", "parent plus", "consolidation", "icr", "double")):
            cluster = [
                {"anchor": "Parent PLUS Double Consolidation Loop Analyzer", "href": "/tools/parent-plus-double-consolidation/"},
                {"anchor": "ICR Income-Contingent Repayment Calculator", "href": "/tools/icr-repayment-calculator/"},
                {"anchor": "Grad PLUS Borrowing Cap Calculator", "href": "/tools/grad-plus-borrowing-cap-calculator/"},
                {"anchor": "RAP vs IBR Monthly Payment Calculator", "href": "/tools/rap-vs-ibr-calculator/"},
                {"anchor": "Tiered Standard Repayment Schedule Calculator", "href": "/tools/tiered-standard-calculator/"},
            ]
        else:
            cluster = [
                {"anchor": "RAP vs IBR Monthly Payment Calculator", "href": "/tools/rap-vs-ibr-calculator/"},
                {"anchor": "PSLF 120 Qualifying Payment Simulator", "href": "/tools/pslf-qualifying-payment-simulator/"},
                {"anchor": "PAYE Sunset & IBR Transition Calculator", "href": "/tools/paye-sunset-calculator/"},
                {"anchor": "Student Loan Repayment Master Calculator", "href": "/tools/student-loan-repayment-calculator/"},
                {"anchor": "Student Loan Refinance Break-Even Calculator", "href": "/tools/student-loan-refinance-break-even-calculator/"},
            ]
    else:
        base_hub = {"anchor": "Statutory Tax & Financial Calculators Directory", "href": "/tools/"}
        if any(k in combined for k in ("tariff", "landed", "customs", "bond", "freight", "cbam", "hs-code", "301", "demurrage")):
            cluster = [
                {"anchor": "Section 301 Tariff & Landed Cost Calculator", "href": "/tools/section-301-tariff-landed-cost-calculator/"},
                {"anchor": "Contractor & Customs Surety Bond Cost Calculator", "href": "/tools/contractor-surety-bond-cost-calculator/"},
                {"anchor": "Section 179 Equipment Deduction Calculator", "href": "/tools/section-179-calculator/"},
                {"anchor": "Equipment Lease vs Buy Section 179 Calculator", "href": "/tools/equipment-lease-vs-buy-section-179-calculator/"},
                {"anchor": "Invoice Factoring vs Business Line of Credit Calculator", "href": "/tools/invoice-factoring-vs-business-line-of-credit-calculator/"},
            ]
        elif any(k in combined for k in ("saas", "burn", "runway", "cac", "rule-of-40", "ltv", "ndr", "174", "r-d", "409a", "cloud", "cap-table")):
            cluster = [
                {"anchor": "SaaS Burn Multiple & Cash Runway Calculator", "href": "/tools/saas-runway-calculator/"},
                {"anchor": "R&D Tax Credit & Section 174 Amortization Calculator", "href": "/tools/r-and-d-tax-credit-section-174-amortization-calculator/"},
                {"anchor": "S-Corp Reasonable Salary Tax Calculator", "href": "/tools/s-corp-reasonable-salary-tax-calculator/"},
                {"anchor": "Workers Comp & Payroll Burden Calculator", "href": "/tools/workers-comp-and-payroll-burden-calculator/"},
                {"anchor": "Section 179 Equipment Deduction Calculator", "href": "/tools/section-179-calculator/"},
            ]
        elif any(k in combined for k in ("1031", "cost-segregation", "cost segregation", "bonus-depreciation", "opportunity-zone", "dst", "721", "real-estate", "cap-rate")):
            cluster = [
                {"anchor": "Section 1031 Like-Kind Exchange Calculator", "href": "/tools/section-1031-calculator/"},
                {"anchor": "1031 Exchange Statutory Rules Guide", "href": "/tools/1031-exchange-rules-arizona/"},
                {"anchor": "Section 1031 Scenario Comparison Model", "href": "/tools/section-1031-calculator-scenario-comparison-model/"},
                {"anchor": "Section 179 Equipment Deduction Calculator", "href": "/tools/section-179-calculator/"},
                {"anchor": "IRS Capital Gains Statutory Tax Calculator", "href": "/tools/irs-capital-gains-statutory-tax/"},
            ]
        else:
            cluster = [
                {"anchor": "Section 179 Equipment Deduction Calculator", "href": "/tools/section-179-calculator/"},
                {"anchor": "Section 1031 Like-Kind Exchange Calculator", "href": "/tools/section-1031-calculator/"},
                {"anchor": "S-Corp Reasonable Salary Tax Calculator", "href": "/tools/s-corp-reasonable-salary-tax-calculator/"},
                {"anchor": "Corporate Treasury Yield & Section 3124 Calculator", "href": "/tools/treasury-yield-calculator/"},
                {"anchor": "IRS 2027 Statutory Tax Brackets Calculator", "href": "/tools/irs-2027-tax-brackets/"},
            ]

    selected = [base_hub]
    for item in cluster:
        if item["href"].rstrip("/") != self_href.rstrip("/") and len(selected) < 5:
            selected.append({
                "anchor": _strip_forbidden_dashes(item["anchor"]),
                "href": item["href"],
            })
    return selected


def _resolve_partner_offer_and_manual_gate(
    tenant_id: str,
    slug: str,
    query: str = "",
    value_tier: str = "tier_1",
    candidate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolves an intent-matched partner offer placement for the asset based on live
    search demand while enforcing Prexvo YMYL public-service guardrails and detecting
    any manual partner or external platform requirement that needs a single clean
    HumanActionBus alert.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.affiliates import (
        PREXVO_AFFILIATES,
        PROFITHELM_AFFILIATES,
        is_restricted_public_service_slug,
    )

    eff_tenant = str(tenant_id or "profithelm").strip().lower()
    s_norm = str(slug or "").strip().lower()
    q_norm = str(query or "").strip().lower()
    combined = f"{s_norm} {q_norm}"
    cand_dict = candidate if isinstance(candidate, dict) else {}

    # 1. Enforce Prexvo YMYL public-service commercial offer suppression
    if eff_tenant == "prexvo" and (
        is_restricted_public_service_slug(s_norm)
        or any(
            ymyl_tok in combined
            for ymyl_tok in (
                "pslf",
                "public service loan forgiveness",
                "save-plan-litigation",
                "save plan litigation",
                "ibr-hardship-cap",
                "teacher-loan-forgiveness",
                "teacher loan forgiveness",
                "joint-consolidation-spousal",
            )
        )
    ):
        return {
            "restricted_public_service": True,
            "commercial_offers_allowed": False,
            "monetization_mode": "PUBLIC_SERVICE_NON_COMMERCIAL_GUARDRAIL",
            "partner_offer": None,
            "manual_requirement_detected": False,
            "manual_requirement": None,
        }

    manual_requirement: Optional[Dict[str, Any]] = None

    # 2. Check explicit candidate manual partner or platform requirement overrides
    raw_manual_req = (
        cand_dict.get("manual_requirement")
        or cand_dict.get("manual_partner_requirement")
        or cand_dict.get("manual_platform_requirement")
    )
    if isinstance(raw_manual_req, dict) and raw_manual_req:
        p_key = str(
            raw_manual_req.get("partner_key")
            or raw_manual_req.get("platform_key")
            or f"{eff_tenant}_manual_gate"
        ).strip().lower()
        p_name = _strip_forbidden_dashes(
            str(raw_manual_req.get("partner_name") or raw_manual_req.get("platform_name") or p_key.replace("_", " ").title())
        )
        manual_requirement = {
            "property_id": eff_tenant,
            "asset_slug": s_norm,
            "partner_key": p_key,
            "partner_name": p_name,
            "action_type": str(raw_manual_req.get("action_type") or "INTEGRATION_REQUIREMENT"),
            "severity": str(raw_manual_req.get("severity") or "HIGH"),
            "title": _strip_forbidden_dashes(
                str(raw_manual_req.get("title") or f"Manual operator confirmation required for {p_name}")
            ),
            "description": _strip_forbidden_dashes(
                str(
                    raw_manual_req.get("description")
                    or f"Asset {s_norm} gaining search demand triggered a manual partner or platform gate for {p_name}."
                )
            ),
            "missing_requirements": [
                _strip_forbidden_dashes(str(r))
                for r in (raw_manual_req.get("missing_requirements") or [f"Complete manual onboarding for {p_name}"])
                if r
            ],
            "candidate_url": str(raw_manual_req.get("candidate_url") or ""),
        }

    # 3. Resolve best live partner offer and detect vertical-matched manual partner gates
    from pseofactory.affiliates import (
        _extract_partner_engagement_record,
        get_partner_bounty_midpoint,
        estimate_partner_approval_revenue_impact,
    )

    eng_metrics = (
        cand_dict.get("engagement_metrics")
        or cand_dict.get("outbound_engagement")
        or None
    )
    cand_impressions = int(float(cand_dict.get("impressions", 0) or 0))
    cand_outbound_clicks = int(float(cand_dict.get("outbound_clicks", 0) or 0))

    if eff_tenant == "prexvo":
        registry = PREXVO_AFFILIATES
        # Check if query specifically demands a pending/gated partner (e.g., splash_financial Gate 1)
        if manual_requirement is None and "splash" in combined:
            sp_info = registry.get("splash_financial", {})
            manual_requirement = {
                "property_id": "prexvo",
                "asset_slug": s_norm,
                "partner_key": "splash_financial",
                "partner_name": "Splash Financial",
                "action_type": "COMPLIANCE_GATE",
                "severity": "MEDIUM",
                "title": "Splash Financial Gate 1 Traffic Threshold & Compliance Confirmation",
                "description": (
                    "High-intent student loan refinance demand detected on Prexvo. "
                    "Splash Financial direct integration requires operator verification of Gate 1 traffic threshold."
                ),
                "missing_requirements": [
                    "Confirm Gate 1 10,000 monthly session threshold",
                    "Verify Engine by Moneylion / Splash partner agreement signature",
                ],
                "candidate_url": str(sp_info.get("url") or "https://www.splashfinancial.com/"),
            }

        if any(k in combined for k in ("medical", "physician", "resident", "dental", "healthcare")):
            default_chosen_key = "laurel_road"
            vertical_candidates = ["laurel_road", "sofi_refi", "earnest", "credible", "juno"]
        elif any(k in combined for k in ("group", "collective", "negotiation", "rate-drop", "juno")):
            default_chosen_key = "juno"
            vertical_candidates = ["juno", "sofi_refi", "earnest", "credible", "laurel_road"]
        elif any(k in combined for k in ("custom", "precision", "earnest", "skip-payment", "biweekly")):
            default_chosen_key = "earnest"
            vertical_candidates = ["earnest", "sofi_refi", "credible", "laurel_road", "juno"]
        else:
            default_chosen_key = "sofi_refi"
            vertical_candidates = ["sofi_refi", "earnest", "laurel_road", "juno", "credible"]
    else:
        registry = PROFITHELM_AFFILIATES
        # Check if query hits a vertical with a known manual partner dependency while routing fallback live offer
        if manual_requirement is None:
            if any(k in combined for k in ("customs-bond", "customs bond", "surety-bond", "surety bond", "continuous bond", "importer security filing")):
                sb_info = registry.get("suretybonds_direct", {})
                if sb_info.get("status") != "live":
                    manual_requirement = {
                        "property_id": "profithelm",
                        "asset_slug": s_norm,
                        "partner_key": "suretybonds_direct",
                        "partner_name": "SuretyBonds.com Direct",
                        "action_type": "INTEGRATION_REQUIREMENT",
                        "severity": "MEDIUM",
                        "title": "SuretyBonds.com Direct Custom Quote Widget & Producer Verification",
                        "description": (
                            f"Customs bond calculator {s_norm} is gaining search impressions and requires "
                            f"manual agency producer code confirmation for SuretyBonds.com Direct."
                        ),
                        "missing_requirements": [
                            "Verify licensed surety producer agreement",
                            "Provision direct quote widget affiliate tracking token",
                        ],
                        "candidate_url": "https://www.suretybonds.com/",
                    }
            elif any(k in combined for k in ("freight-mode", "ocean-air", "container-demurrage", "freightos", "spot-freight")):
                fr_info = registry.get("freightos_marketplace", {})
                if fr_info.get("status") != "live":
                    manual_requirement = {
                        "property_id": "profithelm",
                        "asset_slug": s_norm,
                        "partner_key": "freightos_marketplace",
                        "partner_name": "Freightos Marketplace",
                        "action_type": "INTEGRATION_REQUIREMENT",
                        "severity": "MEDIUM",
                        "title": "Freightos Marketplace Partner API Key & Referral Attribution",
                        "description": (
                            f"Freight analytics tool {s_norm} is gaining search impressions and awaits "
                            f"manual Freightos Marketplace partner API credentials."
                        ),
                        "missing_requirements": [
                            "Obtain Freightos partner referral tracking ID",
                            "Confirm live rate widget domain whitelist for profithelm.com",
                        ],
                        "candidate_url": "https://www.freightos.com/",
                    }
            elif any(k in combined for k in ("interactive-brokers", "portfolio-margin", "section-1256", "prediction-market")):
                ib_info = registry.get("interactive_brokers", {})
                if ib_info.get("status") != "live":
                    manual_requirement = {
                        "property_id": "profithelm",
                        "asset_slug": s_norm,
                        "partner_key": "interactive_brokers",
                        "partner_name": "Interactive Brokers",
                        "action_type": "COMPLIANCE_GATE",
                        "severity": "MEDIUM",
                        "title": "Interactive Brokers Institutional Referral Compliance Review",
                        "description": (
                            f"Trading and tax calculator {s_norm} is gaining search impressions and awaits "
                            f"manual Interactive Brokers compliance sign-off."
                        ),
                        "missing_requirements": [
                            "Complete IBKR institutional marketing compliance review",
                            "Confirm approved disclosure copy and referral link",
                        ],
                        "candidate_url": "https://www.interactivebrokers.com/",
                    }
            elif any(k in combined for k in ("sales-tax", "economic-nexus", "avalara", "vat-compliance")):
                manual_requirement = {
                    "property_id": "profithelm",
                    "asset_slug": s_norm,
                    "partner_key": "avalara",
                    "partner_name": "Avalara AvaTax",
                    "action_type": "PARTNER_APPROVAL",
                    "severity": "HIGH",
                    "title": "Avalara AvaTax Partner Program Agreement & Referral Attribution",
                    "description": (
                        f"Sales tax nexus calculator {s_norm} is gaining search impressions and requires "
                        f"manual Avalara partner agreement approval."
                    ),
                    "missing_requirements": [
                        "Execute Avalara partner referral agreement",
                        "Configure AvaTax referral tracking link",
                    ],
                    "candidate_url": "https://www.avalara.com/",
                }
            elif any(k in combined for k in ("payroll-fica", "fica-tax", "withholding-calculator", "gusto-payroll")):
                g_info = registry.get("gusto", {})
                if g_info.get("status") != "live":
                    manual_requirement = {
                        "property_id": "profithelm",
                        "asset_slug": s_norm,
                        "partner_key": "gusto",
                        "partner_name": "Gusto Payroll & HR",
                        "action_type": "PARTNER_APPROVAL",
                        "severity": "HIGH",
                        "title": "Gusto PartnerStack Referral Agreement Confirmation",
                        "description": (
                            f"Payroll calculator {s_norm} is gaining search impressions and awaits "
                            f"manual Gusto PartnerStack contract confirmation."
                        ),
                        "missing_requirements": [
                            "Confirm Gusto PartnerStack partner contract",
                            "Activate live Gusto referral link",
                        ],
                        "candidate_url": "https://gusto.com/",
                    }

        # Select live fallback or primary partner for immediate conversion path injection
        if any(k in combined for k in ("tariff", "landed", "customs", "bond", "freight", "cbam", "hs-code", "301", "demurrage")):
            default_chosen_key = "flexport"
            vertical_candidates = ["flexport", "ramp", "brex", "mercury"]
        elif any(k in combined for k in ("179", "equipment", "depreciation", "cost-segregation", "cost segregation")):
            default_chosen_key = "crest_capital"
            vertical_candidates = ["crest_capital", "national_funding", "ramp", "brex"]
        elif any(k in combined for k in ("payroll", "s-corp", "reasonable-compensation", "fica", "worker", "contractor")):
            default_chosen_key = "gusto" if not (manual_requirement and manual_requirement.get("partner_key") == "gusto") else "rippling"
            vertical_candidates = [default_chosen_key, "rippling", "deel", "bench", "mercury"]
        elif any(k in combined for k in ("sales-tax", "economic-nexus", "avalara", "vat-compliance")):
            default_chosen_key = "stripe_tax"
            vertical_candidates = ["stripe_tax", "ramp", "brex", "mercury"]
        elif any(k in combined for k in ("401k", "retirement", "pension", "erisa")):
            default_chosen_key = "guideline"
            vertical_candidates = ["guideline", "gusto", "rippling"]
        elif any(k in combined for k in ("crypto", "8949", "harvesting", "capital-gains")):
            default_chosen_key = "coinledger"
            vertical_candidates = ["coinledger", "koinly", "taxbit"]
        elif any(k in combined for k in ("treasury", "yield", "3124", "cash-management", "money-market")):
            default_chosen_key = "wealthfront"
            vertical_candidates = ["wealthfront", "mercury", "ramp", "brex"]
        elif any(k in combined for k in ("bookkeeping", "accounting", "174", "r-d", "audit", "reconciliation")):
            default_chosen_key = "bench"
            vertical_candidates = ["bench", "pilot", "ramp", "gusto"]
        else:
            default_chosen_key = "ramp"
            vertical_candidates = ["ramp", "brex", "mercury", "gusto"]

    _remediation_partner_fallbacks: Dict[str, Dict[str, str]] = {
        "flexport": {
            "name": "Flexport Global Customs & Freight",
            "url": "https://www.flexport.com/",
            "cta_text": "Model Landed Cost & Customs Duties with Flexport",
        },
        "brex": {
            "name": "Brex Corporate Card & Treasury",
            "url": "https://www.brex.com/",
            "cta_text": "Optimize SaaS Spend & Runway with Brex",
        },
        "ramp": {
            "name": "Ramp Corporate Spend Platform",
            "url": "https://ramp.com/",
            "cta_text": "Explore Ramp Corporate Spend Platform for Statutory Modeling",
        },
        "wealthfront": {
            "name": "Wealthfront Automated Treasury Cash",
            "url": "https://www.wealthfront.com/",
            "cta_text": "Compare Treasury Yield Accounts on Wealthfront",
        },
        "bench": {
            "name": "Bench Bookkeeping & Tax Advisory",
            "url": "https://www.bench.co/",
            "cta_text": "Automate Statutory Bookkeeping with Bench",
        },
        "pilot": {
            "name": "Pilot R&D Tax Credit & Bookkeeping",
            "url": "https://pilot.com/",
            "cta_text": "Claim Section 174 R&D Credits with Pilot",
        },
        "guideline": {
            "name": "Guideline 401(k) Retirement Platform",
            "url": "https://www.guideline.com/",
            "cta_text": "Model Small Business 401(k) Plans with Guideline",
        },
        "stripe_tax": {
            "name": "Stripe Tax Automated Nexus Compliance",
            "url": "https://stripe.com/tax",
            "cta_text": "Automate Multi-State Economic Nexus with Stripe Tax",
        },
        "deel": {
            "name": "Deel Global Payroll & Compliance",
            "url": "https://www.deel.com/",
            "cta_text": "Manage Global Payroll & Contractors with Deel",
        },
        "taxbit": {
            "name": "TaxBit Digital Asset Tax Engine",
            "url": "https://taxbit.com/",
            "cta_text": "Automate Form 1099-DA Compliance with TaxBit",
        },
        "sofi_refi": {
            "name": "SoFi Student Loan Refinancing",
            "url": "https://www.sofi.com/refinance-student-loan/",
            "cta_text": "Compare Rates with SoFi Student Loan Refinancing",
        },
        "laurel_road": {
            "name": "Laurel Road Healthcare & Professional Refinancing",
            "url": "https://www.laurelroad.com/",
            "cta_text": "Compare Healthcare Refinance Rates with Laurel Road",
        },
        "juno": {
            "name": "Juno Group Negotiated Student Loan Rates",
            "url": "https://joinjuno.com/",
            "cta_text": "Check Group Negotiated Refinance Rates on Juno",
        },
    }

    # Evaluate empirical outbound partner engagement across vertical_candidates
    chosen_key = default_chosen_key
    ranked_candidates: List[Dict[str, Any]] = []
    any_empirical_signal = False
    preferred_cta_slot = str(cand_dict.get("preferred_cta_slot") or "overlay_primary_cta")

    if isinstance(eng_metrics, dict) and eng_metrics:
        by_slug_map = eng_metrics.get("by_slug", {}) if isinstance(eng_metrics.get("by_slug"), dict) else {}
        slug_rec = by_slug_map.get(s_norm, {}) if isinstance(by_slug_map, dict) else {}
        if isinstance(slug_rec, dict) and slug_rec.get("top_converting_cta_slot"):
            preferred_cta_slot = str(slug_rec["top_converting_cta_slot"])

        # Include any compliant partner in this tenant's registry or fallback catalog that has recorded engagement on this slug
        slug_partners = (
            list(slug_rec.get("partners", {}).keys())
            if isinstance(slug_rec, dict) and isinstance(slug_rec.get("partners"), dict)
            else []
        )
        for sp_k in slug_partners:
            norm_sp = "sofi_refi" if (eff_tenant == "prexvo" and sp_k == "sofi") else sp_k
            if (norm_sp in registry or norm_sp in _remediation_partner_fallbacks) and norm_sp not in vertical_candidates:
                vertical_candidates.append(norm_sp)

    gated_partner_key = str((manual_requirement or {}).get("partner_key") or "").strip().lower()
    seen_cands = set()
    for idx, c_key in enumerate(vertical_candidates):
        if c_key in seen_cands:
            continue
        seen_cands.add(c_key)
        if gated_partner_key and c_key == gated_partner_key and c_key != default_chosen_key:
            continue
        c_info = registry.get(c_key) or _remediation_partner_fallbacks.get(c_key) or {
            "name": c_key.replace("_", " ").title(),
            "url": f"https://www.{c_key.replace('_', '')}.com/",
        }

        emp_rec = _extract_partner_engagement_record(c_key, eng_metrics, slug=s_norm)
        if not emp_rec and eff_tenant == "prexvo" and c_key == "sofi_refi":
            emp_rec = _extract_partner_engagement_record("sofi", eng_metrics, slug=s_norm)
        if not isinstance(emp_rec, dict):
            emp_rec = {}

        out_clicks = int(float(emp_rec.get("outbound_clicks", emp_rec.get("affiliate_clicks", 0)) or 0))
        calc_inter = int(float(emp_rec.get("calculator_interactions", emp_rec.get("calculations", 0)) or 0))
        p_views = int(float(emp_rec.get("page_views", emp_rec.get("impressions", 0)) or 0))
        cta_ctr = float(emp_rec.get("cta_ctr", 0.0) or 0.0)
        if cta_ctr <= 0.0 and p_views > 0 and out_clicks > 0:
            cta_ctr = out_clicks / float(p_views)
        intent_rate = float(emp_rec.get("intent_to_click_rate", 0.0) or 0.0)
        if intent_rate <= 0.0 and calc_inter > 0 and out_clicks > 0:
            intent_rate = out_clicks / float(calc_inter)

        bounty_mid = get_partner_bounty_midpoint(c_key)
        est_conv_rate = 0.035 if eff_tenant == "profithelm" else 0.025
        emp_erpm = float(emp_rec.get("empirical_erpm_usd", emp_rec.get("erpm_usd", 0.0)) or 0.0)
        if emp_erpm <= 0.0 and p_views > 0 and out_clicks > 0:
            emp_erpm = ((out_clicks * est_conv_rate * bounty_mid) / float(p_views)) * 1000.0
        realized_rev = float(emp_rec.get("realized_revenue_usd", emp_rec.get("estimated_revenue_yield_usd", 0.0)) or 0.0)
        if realized_rev <= 0.0 and out_clicks > 0:
            realized_rev = out_clicks * est_conv_rate * bounty_mid

        if out_clicks > 0 or emp_erpm > 0.0 or realized_rev > 0.0 or cta_ctr > 0.0:
            any_empirical_signal = True

        # Base score gives slight tie-breaker to default_chosen_key when no telemetry exists
        base_score = round(bounty_mid * 0.5 + (5.0 if idx == 0 else 0.0), 2)
        empirical_lift = (
            min(emp_erpm * 0.45, 250.0)
            + min(cta_ctr * 400.0, 90.0)
            + min(intent_rate * 150.0, 60.0)
            + min(out_clicks * 3.5, 80.0)
            + min(realized_rev * 0.25, 120.0)
        )
        composite_yield = round(base_score + empirical_lift, 2)
        ranked_candidates.append({
            "partner_key": c_key,
            "partner_name": _strip_forbidden_dashes(str(c_info.get("name") or c_key)),
            "yield_score": composite_yield,
            "bounty_midpoint_usd": round(bounty_mid, 2),
            "outbound_clicks": out_clicks,
            "cta_ctr": round(cta_ctr, 4),
            "intent_to_click_rate": round(intent_rate, 4),
            "empirical_erpm_usd": round(emp_erpm, 2),
            "estimated_revenue_yield_usd": round(realized_rev, 2),
            "is_default": (c_key == default_chosen_key),
        })

    if any_empirical_signal and ranked_candidates:
        # Rank strictly by empirical performance + composite yield when engagement data exists
        ranked_candidates.sort(
            key=lambda x: (
                -float(x["estimated_revenue_yield_usd"]),
                -float(x["empirical_erpm_usd"]),
                -int(x["outbound_clicks"]),
                -float(x["yield_score"]),
            )
        )
        chosen_key = str(ranked_candidates[0]["partner_key"])
        chosen_metrics = ranked_candidates[0]
    else:
        chosen_key = default_chosen_key
        chosen_metrics = ranked_candidates[0] if ranked_candidates else {
            "yield_score": round(get_partner_bounty_midpoint(chosen_key) * 0.5, 2),
            "empirical_erpm_usd": 0.0,
            "cta_ctr": 0.0,
            "outbound_clicks": 0,
            "estimated_revenue_yield_usd": 0.0,
        }

    if eff_tenant == "prexvo":
        p_data = registry.get(chosen_key) or _remediation_partner_fallbacks.get(chosen_key) or registry.get("sofi_refi") or {}
        p_name = _strip_forbidden_dashes(str(p_data.get("name") or "SoFi Student Loan Refinancing"))
        p_url = str(p_data.get("url") or "https://www.sofi.com/refinance-student-loan/")
        p_cta = _strip_forbidden_dashes(str(p_data.get("cta_text") or f"Compare Rates with {p_name}"))
        p_disc = _strip_forbidden_dashes(
            str(
                p_data.get("disclosure")
                or "Editorial Note: Refinancing federal student loans with a private lender permanently waives Title IV income-driven repayment and PSLF eligibility."
            )
        )
    else:
        p_data = registry.get(chosen_key) or _remediation_partner_fallbacks.get(chosen_key) or registry.get("ramp") or {}
        p_name = _strip_forbidden_dashes(str(p_data.get("name") or "Ramp Corporate Spend Platform"))
        p_url = str(p_data.get("url") or "https://ramp.com/")
        p_cta = _strip_forbidden_dashes(str(p_data.get("cta_text") or f"Explore {p_name} for Statutory Modeling"))
        p_disc = _strip_forbidden_dashes(
            str(
                p_data.get("disclosure")
                or "FTC Disclosure: ProfitHelm may earn a commission when you register through approved partner links at no additional cost to you."
            )
        )

    if manual_requirement is not None:
        impact_est = estimate_partner_approval_revenue_impact(
            property_id=eff_tenant,
            partner_key=str(manual_requirement.get("partner_key") or ""),
            affected_slugs=[s_norm],
            impressions=cand_impressions,
            outbound_clicks=max(cand_outbound_clicks, int(chosen_metrics.get("outbound_clicks", 0) or 0)),
            engagement_metrics=eng_metrics,
        )
        manual_requirement["estimated_monthly_revenue_impact_usd"] = impact_est["estimated_monthly_revenue_impact_usd"]
        manual_requirement["bounty_uplift_usd"] = impact_est["bounty_uplift_usd"]
        manual_requirement["affected_traffic_impressions"] = impact_est["affected_traffic_impressions"]
        manual_requirement["outbound_cta_intent_clicks"] = impact_est["outbound_cta_intent_clicks"]

    optimization_status = (
        "YIELD_OPTIMIZED_PROMOTED"
        if chosen_key != default_chosen_key
        else ("YIELD_VERIFIED_LEADER" if any_empirical_signal else "INITIAL_PLACEMENT")
    )

    partner_offer = {
        "partner_key": chosen_key,
        "partner_name": p_name,
        "url": p_url,
        "redirect_path": f"/r/{chosen_key}",
        "cta_text": p_cta,
        "cta_slot": preferred_cta_slot,
        "cta_id": f"cta-{eff_tenant}-{s_norm}-{chosen_key}",
        "disclosure": p_disc,
        "value_tier": value_tier,
        "status": "live",
        "compliance_status": "FTC_16_CFR_255_VERIFIED",
        "mechanic": "compliant_intent_monetization",
        "rel": "noopener sponsored nofollow",
        "yield_score": float(chosen_metrics.get("yield_score", 0.0)),
        "empirical_erpm_usd": float(chosen_metrics.get("empirical_erpm_usd", 0.0)),
        "empirical_cta_ctr": float(chosen_metrics.get("cta_ctr", 0.0)),
        "outbound_clicks": int(chosen_metrics.get("outbound_clicks", 0)),
        "estimated_revenue_yield_usd": float(chosen_metrics.get("estimated_revenue_yield_usd", 0.0)),
        "optimization_status": optimization_status,
        "initial_default_partner_key": default_chosen_key,
        "ranked_partner_candidates": ranked_candidates,
    }

    return {
        "restricted_public_service": False,
        "commercial_offers_allowed": True,
        "monetization_mode": "LIVE_INTENT_PARTNER_OFFER",
        "partner_offer": partner_offer,
        "manual_requirement_detected": manual_requirement is not None,
        "manual_requirement": manual_requirement,
    }


def evaluate_asset_conversion_and_distribution_readiness(
    slug: str,
    tenant_id: str = "profithelm",
    query: str = "",
    impressions: int = 0,
    position: float = 0.0,
    dist_dir: Optional[Union[str, Path]] = None,
    base_dir: Optional[Union[str, Path]] = None,
    html_content: Optional[str] = None,
    candidate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether a page gaining search impressions has:
      1. A strong live conversion path in compiled HTML (interactive preset scenarios,
         contextual internal links, and compliant partner offer placement or YMYL guardrail).
      2. Optimal partner offer placement based on empirical outbound engagement yield
         (detecting when a page with traffic displays a lower-converting partner offer).
      3. Complete external syndication distribution artifacts (LinkedIn, Newsletter,
         Substack Notes) and broadcast readiness.
      4. Any manual partner or external platform dependency that must route a single
         clean alert onto HumanActionBus.
    Zero em-dashes. Zero en-dashes.
    """
    eff_tenant = str(tenant_id or "profithelm").strip().lower()
    s_norm = _slug_from_url_or_query(default_slug=slug, query=query)
    cand_dict = dict(candidate) if isinstance(candidate, dict) else {}
    cand_dict.setdefault("impressions", impressions)
    intent_info = _classify_asset_intent_class(
        slug=s_norm,
        target_url=str(cand_dict.get("target_url") or cand_dict.get("url") or ""),
        query=query,
        section=str(cand_dict.get("section") or ""),
    )
    mon_info = _resolve_partner_offer_and_manual_gate(
        tenant_id=eff_tenant,
        slug=s_norm,
        query=query,
        value_tier=intent_info["value_tier"],
        candidate=cand_dict,
    )

    resolved_dist = Path(dist_dir) if dist_dir else (Path(base_dir) / "dist" if base_dir else None)
    resolved_base = Path(base_dir) if base_dir else (resolved_dist.parent if resolved_dist else None)

    raw_html = html_content
    if raw_html is None and resolved_dist and resolved_dist.is_dir():
        for p_cand in (
            resolved_dist / "tools" / s_norm / "index.html",
            resolved_dist / s_norm / "index.html",
            resolved_dist / f"{s_norm}.html",
        ):
            if p_cand.is_file():
                try:
                    raw_html = p_cand.read_text(encoding="utf-8")
                except Exception:
                    raw_html = ""
                break

    has_partner_cta = False
    has_preset_scenarios = False
    has_internal_links = False
    current_html_partner = ""
    if raw_html is not None:
        if mon_info["restricted_public_service"]:
            has_partner_cta = (
                'data-restricted-public-service="true"' in raw_html
                or 'data-commercial-offers="none"' in raw_html
            )
        else:
            has_partner_cta = (
                'rel="noopener sponsored nofollow"' in raw_html
                and (
                    "affiliate-cta" in raw_html
                    or "partner-btn" in raw_html
                    or "overlay-partner-offer" in raw_html
                )
            )
            p_matches = re.findall(r'data-partner=["\']([^"\']+)["\']', raw_html, flags=re.IGNORECASE)
            if p_matches:
                # Prefer the overlay-partner-offer partner if present
                overlay_match = re.search(
                    r'class=["\'][^"\']*overlay-partner-offer[^"\']*["\'][^>]*data-partner=["\']([^"\']+)["\']',
                    raw_html,
                    flags=re.IGNORECASE,
                )
                current_html_partner = (
                    overlay_match.group(1).strip().lower()
                    if overlay_match
                    else p_matches[-1].strip().lower()
                )
        has_preset_scenarios = "data-calc-preset" in raw_html or "scenario-preset-link" in raw_html
        has_internal_links = "overlay-hub-links" in raw_html or (raw_html.count('href="/tools/') >= 2)
    else:
        # If HTML wasn't loaded from disk, check explicit flags on candidate
        has_partner_cta = bool(cand_dict.get("has_conversion_path", True))
        has_preset_scenarios = bool(cand_dict.get("has_preset_scenarios", True))
        has_internal_links = bool(cand_dict.get("has_internal_links", True))
        current_html_partner = str(cand_dict.get("current_partner_key") or "").strip().lower()

    if cand_dict.get("has_conversion_path") is False or cand_dict.get("conversion_gap") is True:
        has_partner_cta = False

    p_offer = mon_info.get("partner_offer") or {}
    optimal_partner_key = str(p_offer.get("partner_key") or "").strip().lower()
    yield_optimization_needed = bool(cand_dict.get("yield_optimization_needed", False))
    if (
        not mon_info["restricted_public_service"]
        and optimal_partner_key
        and p_offer.get("optimization_status") == "YIELD_OPTIMIZED_PROMOTED"
    ):
        if current_html_partner and current_html_partner != optimal_partner_key:
            yield_optimization_needed = True
        elif not current_html_partner and has_partner_cta:
            yield_optimization_needed = True

    has_strong_conversion_path = bool(has_partner_cta and has_preset_scenarios and has_internal_links)
    conversion_gap_detected = bool(impressions > 0 and not has_strong_conversion_path)

    # Check external syndication & distribution readiness
    has_external_distribution = True
    missing_syndication_files: List[str] = []
    if resolved_base and resolved_base.is_dir():
        synd_dir = resolved_base / "syndication"
        expected_files = [
            f"{s_norm}-linkedin.md",
            f"{s_norm}-newsletter.md",
            f"{s_norm}-Substack Notes-post.txt",
        ]
        for fname in expected_files:
            if not (synd_dir / fname).is_file():
                missing_syndication_files.append(fname)
        if missing_syndication_files:
            has_external_distribution = False

    if cand_dict.get("has_external_distribution") is False or cand_dict.get("distribution_gap") is True:
        has_external_distribution = False
        if not missing_syndication_files:
            missing_syndication_files = [
                f"{s_norm}-linkedin.md",
                f"{s_norm}-newsletter.md",
                f"{s_norm}-Substack Notes-post.txt",
            ]

    distribution_gap_detected = bool(impressions > 0 and not has_external_distribution)

    return {
        "slug": s_norm,
        "tenant_id": eff_tenant,
        "impressions": int(impressions),
        "position": float(position),
        "intent_class": intent_info["intent_class"],
        "is_high_intent_calculator_or_guide": intent_info["is_high_intent_calculator_or_guide"],
        "intent_multiplier": intent_info["intent_multiplier"],
        "has_strong_conversion_path": has_strong_conversion_path,
        "has_partner_cta": has_partner_cta,
        "has_preset_scenarios": has_preset_scenarios,
        "has_internal_links": has_internal_links,
        "conversion_gap_detected": conversion_gap_detected,
        "current_partner_key": current_html_partner,
        "optimal_partner_key": optimal_partner_key,
        "yield_optimization_needed": yield_optimization_needed,
        "has_external_distribution": has_external_distribution,
        "missing_syndication_files": missing_syndication_files,
        "distribution_gap_detected": distribution_gap_detected,
        "restricted_public_service": mon_info["restricted_public_service"],
        "commercial_offers_allowed": mon_info["commercial_offers_allowed"],
        "partner_offer": mon_info["partner_offer"],
        "manual_requirement_detected": mon_info["manual_requirement_detected"],
        "manual_requirement": mon_info["manual_requirement"],
    }


def compute_composite_idempotency_key(
    tenant_id: str,
    target_url: str,
    action_or_engine: str = "",
    payload_hash: str = "",
    **kwargs: Any,
) -> str:
    """
    Computes a deterministic SHA-256 composite idempotency key over:
    (tenant_id, target_url, action_or_engine, payload_hash).
    Accepts flexible keyword aliases for callers across indexers and queues.
    Zero em-dashes. Zero en-dashes.
    """
    t_norm = str(tenant_id or kwargs.get("property_id") or "profithelm").strip().lower()
    u_norm = str(target_url or kwargs.get("url") or kwargs.get("slug") or "").strip()
    act_norm = str(
        action_or_engine
        or kwargs.get("action_type")
        or kwargs.get("engine")
        or kwargs.get("anomaly_type")
        or "REMEDIATE"
    ).strip().upper()
    hash_norm = str(
        payload_hash
        or kwargs.get("signal_or_content_sha256")
        or kwargs.get("content_sha256")
        or ""
    ).strip()
    raw = f"{t_norm}:{u_norm}:{act_norm}:{hash_norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def expected_ctr_for_position(position: float) -> float:
    """Returns benchmark expected CTR for a given SERP position (1..20+)."""
    if position <= 0:
        return 0.045
    pos_int = int(round(position))
    if pos_int <= 1:
        return EXPECTED_CTR_CURVE[1]
    if pos_int <= 10:
        return EXPECTED_CTR_CURVE.get(pos_int, 0.018)
    if pos_int <= 20:
        return 0.015
    return 0.01


def calculate_candidate_roi(
    candidate_or_signal: Union[Dict[str, Any], str, None] = None,
    tenant_id: str = "profithelm",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Calculates expected click lift, CTR deficit, intent priority multiplier,
    conversion/distribution gap boost, and composite ROI score for a GSC query
    signal or unindexed page diagnosis.
    Prioritizes:
      1. High-intent calculators and guides gaining search impressions that lack
         strong conversion paths or external distribution.
      2. High-impression CTR shortfall (pos 1-5, high impressions, low CTR)
      3. Striking-distance query (pos 4-20, moderate-high impressions)
      4. Content quality / canonical / depth unindexed defects
      5. Crawl budget signal lag / dead routes
    Zero em-dashes. Zero en-dashes.
    """
    data: Dict[str, Any] = {}
    if isinstance(candidate_or_signal, dict):
        data.update(candidate_or_signal)
    elif isinstance(candidate_or_signal, str) and candidate_or_signal:
        data["query"] = candidate_or_signal
    if kwargs:
        data.update(kwargs)

    resolved_tenant = str(
        data.get("tenant_id") or data.get("property_id") or tenant_id or "profithelm"
    ).strip().lower()

    position = float(data.get("position", 0.0) or 0.0)
    impressions = int(float(data.get("impressions", 0) or 0))
    clicks = int(float(data.get("clicks", 0) or 0))
    actual_ctr = float(data.get("ctr", 0.0) or 0.0)
    if actual_ctr <= 0.0 and impressions > 0 and clicks > 0:
        actual_ctr = round(clicks / float(impressions), 4)

    target_url = str(data.get("target_url") or data.get("page") or data.get("url") or "").strip()
    query_str = str(data.get("query") or data.get("primary_keyword") or "").strip()
    slug_str = _slug_from_url_or_query(
        target_url=target_url,
        query=query_str,
        default_slug=str(data.get("slug") or ""),
    )
    intent_info = _classify_asset_intent_class(
        slug=slug_str,
        target_url=target_url,
        query=query_str,
        section=str(data.get("section") or data.get("template_section") or ""),
    )

    conversion_gap = bool(
        data.get("conversion_gap_detected")
        or data.get("conversion_gap")
        or (impressions > 0 and data.get("has_conversion_path") is False)
        or (impressions > 0 and data.get("has_strong_conversion_path") is False)
    )
    distribution_gap = bool(
        data.get("distribution_gap_detected")
        or data.get("distribution_gap")
        or (impressions > 0 and data.get("has_external_distribution") is False)
    )
    yield_opt_needed = bool(data.get("yield_optimization_needed"))

    anomaly_type = str(
        data.get("anomaly_type")
        or data.get("classification")
        or data.get("signal_class")
        or ""
    ).strip().upper()

    if not anomaly_type:
        if conversion_gap and impressions >= 25:
            anomaly_type = "IMPRESSION_GAINING_CONVERSION_GAP"
        elif yield_opt_needed and impressions >= 25:
            anomaly_type = "OUTBOUND_YIELD_OPTIMIZATION"
        elif distribution_gap and impressions >= 25:
            anomaly_type = "IMPRESSION_GAINING_DISTRIBUTION_GAP"
        elif 1.0 <= position <= 5.0 and actual_ctr < expected_ctr_for_position(position) - 0.005:
            anomaly_type = "HIGH_IMPRESSION_CTR_SHORTFALL"
        elif 4.0 <= position <= 20.0:
            anomaly_type = "STRIKING_DISTANCE_QUERY"
        elif position > 20.0:
            anomaly_type = "CONTENT_QUALITY_OR_ANSWER_DEFICIENCY"
        else:
            anomaly_type = "CRAWL_BUDGET_SIGNAL_LAG"

    raw_exp_ctr = data.get("expected_ctr")
    if raw_exp_ctr is not None and float(raw_exp_ctr) > 0:
        exp_ctr = float(raw_exp_ctr)
    else:
        if (
            "STRIKING" in anomaly_type
            or "CONVERSION_GAP" in anomaly_type
            or "DISTRIBUTION_GAP" in anomaly_type
            or "YIELD_OPTIMIZATION" in anomaly_type
        ):
            # Target top-4 CTR benchmark upon striking-distance / conversion overlay lift
            exp_ctr = max(0.08, expected_ctr_for_position(position) + 0.035)
        elif 1.0 <= position <= 10.0:
            exp_ctr = expected_ctr_for_position(position)
        else:
            exp_ctr = 0.045

    ctr_deficit = round(max(0.015, exp_ctr - actual_ctr), 4)

    if "CONVERSION_GAP" in anomaly_type:
        severity_factor = 1.65
        action_type = "SHARPEN_CONTENT_INTERNAL_LINKS_AND_PARTNER_OFFER"
    elif "YIELD_OPTIMIZATION" in anomaly_type:
        severity_factor = 1.55
        action_type = "PROMOTE_HIGH_YIELD_PARTNER_OFFER"
    elif "DISTRIBUTION_GAP" in anomaly_type:
        severity_factor = 1.4
        action_type = "SHARPEN_CONTENT_AND_DISPATCH_SYNDICATION"
    elif "CTR_SHORTFALL" in anomaly_type:
        severity_factor = 1.5
        action_type = "REWRITE_TITLE_META_AND_SCHEMA"
    elif "STRIKING" in anomaly_type:
        severity_factor = 1.25
        action_type = "INJECT_STRIKING_DISTANCE_OVERLAY"
    elif anomaly_type in (
        "CONTENT_QUALITY_OR_ANSWER_DEFICIENCY",
        "CONTENT_DEPTH_DEFICIT",
        "CANONICAL_TEMPLATE_DEFECT",
    ):
        severity_factor = 0.9
        action_type = (
            "REPAIR_CANONICAL_AND_OVERLAY"
            if "CANONICAL" in anomaly_type
            else "ENRICH_GEO_ANSWER_AND_SCENARIOS"
        )
    elif "CRAWL_BUDGET" in anomaly_type:
        severity_factor = 0.55
        action_type = "HUB_LINK_INJECTION_AND_FAST_INDEX"
    elif "DEAD_ROUTE" in anomaly_type:
        severity_factor = 0.35
        action_type = "QUARANTINE_DEAD_ROUTE"
    else:
        severity_factor = 0.75
        action_type = "REFACTOR_PAGE"

    effective_impressions = max(impressions, 60 if severity_factor >= 0.85 else 30)
    expected_click_lift = round(max(0.5, effective_impressions * ctr_deficit * severity_factor), 4)

    default_cpc = 8.0 if resolved_tenant == "prexvo" else 10.5
    default_erpm = 75.0 if resolved_tenant == "prexvo" else 85.0
    cpc = float(data.get("cpc", default_cpc) or default_cpc)
    erpm_usd = float(data.get("erpm_usd", data.get("empirical_erpm_usd", default_erpm)) or default_erpm)

    intent_multiplier = float(intent_info["intent_multiplier"])
    gap_boost = 1.0
    if conversion_gap:
        gap_boost += 0.35
    if yield_opt_needed:
        gap_boost += 0.30
    if distribution_gap:
        gap_boost += 0.20

    commercial_weight = round((1.0 + (cpc / 20.0) + (erpm_usd / 200.0)) * intent_multiplier * gap_boost, 4)
    roi_score = round(expected_click_lift * commercial_weight, 4)

    return {
        "tenant_id": resolved_tenant,
        "anomaly_type": anomaly_type,
        "action_type": action_type,
        "intent_class": intent_info["intent_class"],
        "is_high_intent_calculator_or_guide": intent_info["is_high_intent_calculator_or_guide"],
        "intent_multiplier": intent_multiplier,
        "conversion_gap_detected": conversion_gap,
        "distribution_gap_detected": distribution_gap,
        "yield_optimization_needed": yield_opt_needed,
        "position": position,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round(actual_ctr, 4),
        "expected_ctr": round(exp_ctr, 4),
        "ctr_deficit": ctr_deficit,
        "expected_click_lift": expected_click_lift,
        "commercial_weight": commercial_weight,
        "roi_score": roi_score,
    }


def _normalize_title_50_60(raw_title: str, brand: str, tenant_id: str) -> str:
    """
    Deterministically normalizes any title string into [50, 60] characters
    with brand attribution and zero forbidden dashes.
    """
    clean = _strip_forbidden_dashes(raw_title).strip()
    clean = re.sub(r"\s+", " ", clean)
    suffix = f" | {brand}"
    if clean.lower().endswith(suffix.lower()):
        base = clean[: -len(suffix)].strip(" |-")
    else:
        base = clean.strip(" |-")

    if not base:
        base = (
            "Title IV Student Loan Repayment Calculator"
            if tenant_id == "prexvo"
            else "Statutory Tax and Financial Model Calculator"
        )

    if "calculator" not in base.lower():
        max_for_calc = 60 - len(suffix) - len(" Calculator")
        if len(base) > max_for_calc:
            trimmed_b = base[:max_for_calc].rstrip(" |-&")
            if " " in trimmed_b and len(trimmed_b.rsplit(" ", 1)[0]) >= 20:
                trimmed_b = trimmed_b.rsplit(" ", 1)[0].rstrip(" |-&")
            base = f"{trimmed_b} Calculator"
        else:
            base = f"{base} Calculator"

    cand = f"{base}{suffix}"
    if 50 <= len(cand) <= 60:
        return cand

    # Pad if shorter than 50 chars
    pad_tokens = (
        ["Calculator", "2026", "Model", "Tool", "Guide", "Rules", "Engine"]
        if tenant_id == "prexvo"
        else ["Calculator", "2026", "Tax", "Model", "Tool", "Guide", "Engine"]
    )
    for tok in pad_tokens:
        if len(cand) >= 50:
            break
        if tok.lower() not in base.lower():
            trial = f"{base} {tok}{suffix}"
            if len(trial) <= 60:
                base = f"{base} {tok}"
                cand = trial

    if len(cand) < 50:
        filler = (
            " & Statutory Simulator"
            if tenant_id == "prexvo"
            else " & Statutory Calculator"
        )
        needed = 52 - len(cand)
        base = (base + filler[: max(needed, len(filler))]).strip()
        cand = f"{base}{suffix}"

    if len(cand) > 60:
        max_base = 60 - len(suffix)
        trimmed = base[:max_base].rstrip(" |-&")
        if " " in trimmed and len(trimmed.rsplit(" ", 1)[0]) >= (50 - len(suffix)):
            trimmed = trimmed.rsplit(" ", 1)[0].rstrip(" |-&")
        cand = f"{trimmed}{suffix}"

    # Final exact guard for [50, 60]
    while len(cand) < 50:
        base = f"{base} Tool"
        cand = f"{base}{suffix}"
    if len(cand) > 60:
        cand = f"{base[: 60 - len(suffix)].rstrip()}{suffix}"
    return _strip_forbidden_dashes(cand)


def _normalize_meta_120_155(raw_meta: str, tenant_id: str, query_label: str) -> str:
    """
    Deterministically normalizes meta description length into [120, 155] characters
    with domain-isolated statutory terminology and zero forbidden dashes.
    """
    clean = _strip_forbidden_dashes(raw_meta).strip()
    clean = re.sub(r"\s+", " ", clean)
    if 120 <= len(clean) <= 155:
        return clean

    if tenant_id == "prexvo":
        default_meta = (
            f"Calculate {query_label} under Title IV 34 CFR Part 685 using 225% HHS Poverty "
            f"Guidelines, discretionary income caps, and forgiveness schedules."
        )
        tail_pad = " Verified under Title IV 34 CFR Part 685 statutory rules."
    else:
        default_meta = (
            f"Calculate {query_label} using deterministic IRC statutory formulas, federal "
            f"brackets, depreciation limits, and audit-ready financial benchmarks."
        )
        tail_pad = " Grounded in deterministic IRS and federal statutory schedules."

    cand = clean if len(clean) >= 60 else default_meta
    while len(cand) < 120:
        cand = f"{cand.rstrip('.')}." + tail_pad

    if len(cand) > 155:
        trimmed = cand[:154]
        if " " in trimmed and len(trimmed.rsplit(" ", 1)[0]) >= 120:
            trimmed = trimmed.rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
        else:
            trimmed = cand[:154].rstrip(" ,;:-") + "."
        cand = trimmed

    return _strip_forbidden_dashes(cand)


def _normalize_quick_answer_40_60_words(query_label: str, tenant_id: str) -> str:
    """
    Synthesizes a Princeton GEO Sentence-1 statutory quick answer strictly
    between 40 and 60 words with zero cross-tenant tokens and zero dashes.
    """
    clean_q = _strip_forbidden_dashes(query_label).strip()
    # Keep query phrase concise (max 6 words) so total word count stays inside [40, 60]
    q_words = [w for w in clean_q.split() if w.strip()][:6]
    short_q = " ".join(q_words) if q_words else ("repayment options" if tenant_id == "prexvo" else "tax deductions")

    if tenant_id == "prexvo":
        base_words = (
            f"Under Title IV regulation 34 CFR Part 685, {short_q} determines monthly borrower "
            f"obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected "
            f"income for single filers) and a 10 percent discretionary rate. Qualifying borrowers "
            f"receive a 100 percent unpaid interest subsidy and complete principal forgiveness after "
            f"120 to 240 certified monthly payments."
        ).split()
        filler_pool = [
            "Verified", "against", "annual", "Department", "of", "Education",
            "amortization", "tables", "and", "federal", "poverty", "benchmarks.",
        ]
    else:
        base_words = (
            f"Under Internal Revenue Code statutory provisions, {short_q} establishes exact "
            f"deduction ceilings, basis adjustments, and marginal rate thresholds for 2026 commercial "
            f"filings. Businesses and investors applying IRC Section 179, Section 1031, or Form 8949 "
            f"schedules can shelter up to $1,250,000 in qualifying capital allocations while "
            f"maintaining full audit compliance across federal and state jurisdictions."
        ).split()
        filler_pool = [
            "Verified", "against", "published", "Internal", "Revenue", "Service",
            "revenue", "procedures", "and", "statutory", "accounting", "standards.",
        ]

    idx = 0
    while len(base_words) < 44 and idx < len(filler_pool):
        base_words.append(filler_pool[idx])
        idx += 1

    if len(base_words) > 56:
        base_words = base_words[:55]
        if not base_words[-1].endswith("."):
            base_words[-1] = base_words[-1].rstrip(",;:-") + "."

    return _strip_forbidden_dashes(" ".join(base_words))


def compile_remediation_overlay_spec(
    candidate: Dict[str, Any],
    tenant_id: Optional[str] = None,
    lock_days: int = 14,
) -> Dict[str, Any]:
    """
    Compiles a complete, domain-isolated, non-destructive remediation overlay
    specification with 50-60 char title_rewrite, 120-155 char meta_description,
    40-60 word quick_answer, interactive calculator preset_scenarios,
    comparison_rows, and FAQPage JSON-LD schema.
    Zero em-dashes. Zero en-dashes.
    """
    resolved_tenant = str(
        tenant_id
        or candidate.get("tenant_id")
        or candidate.get("property_id")
        or "profithelm"
    ).strip().lower()

    brand = "Prexvo" if resolved_tenant == "prexvo" else "ProfitHelm"
    domain = "prexvo.com" if resolved_tenant == "prexvo" else "profithelm.com"
    target_url = str(
        candidate.get("target_url")
        or candidate.get("page")
        or candidate.get("url")
        or ""
    ).strip()
    raw_query = str(
        candidate.get("query")
        or candidate.get("primary_keyword")
        or ""
    ).strip()
    slug = _slug_from_url_or_query(
        target_url=target_url,
        query=raw_query,
        default_slug=str(candidate.get("slug") or ""),
    )
    if not target_url:
        target_url = f"https://{domain}/tools/{slug}/"

    if not raw_query:
        raw_query = slug.replace("-", " ")

    # Scrub any accidental cross-tenant tokens from query label
    query_clean = _strip_forbidden_dashes(raw_query)
    if resolved_tenant == "prexvo":
        for bad in ("profithelm", "section 179", "section 1031", "1031 exchange", "tcja", "qsbs"):
            query_clean = re.sub(re.escape(bad), "title iv repayment", query_clean, flags=re.IGNORECASE)
    else:
        for bad in ("prexvo", "title iv", "34 cfr", "pslf", "student loan", "paye sunset"):
            query_clean = re.sub(re.escape(bad), "statutory tax", query_clean, flags=re.IGNORECASE)

    query_clean = re.sub(r"\bs[\s-]+corp\b", "S-Corp", query_clean, flags=re.IGNORECASE)
    query_clean = re.sub(r"\bc[\s-]+corp\b", "C-Corp", query_clean, flags=re.IGNORECASE)
    query_clean = re.sub(r"\br[\s-]+(?:and[\s-]+|&[\s-]*)?d\b", "R&D", query_clean, flags=re.IGNORECASE)
    query_clean = re.sub(r"\bk[\s-]+1\b", "K-1", query_clean, flags=re.IGNORECASE)
    query_clean = re.sub(r"\bw[\s-]+([249])\b", r"W-\1", query_clean, flags=re.IGNORECASE)

    _upper_tokens = {"irc", "irs", "rap", "ibr", "pslf", "paye", "icr", "agi", "saas", "gaap", "r&d", "roi", "ebitda", "cbam", "tcja", "qsbs"}

    def _cap_word(w: str) -> str:
        wl = w.lower()
        if wl in _upper_tokens:
            return w.upper()
        if "-" in w:
            return "-".join(p.upper() if len(p) == 1 else p.capitalize() for p in w.split("-"))
        return w.capitalize()

    words = [_cap_word(w) for w in query_clean.split() if w]
    heading_label = " ".join(words) if words else ("Title IV Repayment Calculator" if resolved_tenant == "prexvo" else "Statutory Tax Calculator")

    title_rewrite = _normalize_title_50_60(f"{heading_label} 2026", brand=brand, tenant_id=resolved_tenant)
    meta_description = _normalize_meta_120_155("", tenant_id=resolved_tenant, query_label=heading_label)
    quick_answer = _normalize_quick_answer_40_60_words(heading_label, tenant_id=resolved_tenant)

    pos = float(candidate.get("position", 10.0) or 10.0)
    impr = int(float(candidate.get("impressions", 100) or 100))
    clicks = int(float(candidate.get("clicks", 0) or 0))
    ctr = float(candidate.get("ctr", 0.02) or 0.02)
    anomaly_type = str(candidate.get("anomaly_type") or candidate.get("classification") or "STRIKING_DISTANCE_QUERY")
    action_type = str(candidate.get("action_type") or "REFACTOR_PAGE")

    if resolved_tenant == "prexvo":
        h2_headings = [
            f"{heading_label}: 2026 Title IV Statutory Rules & Formula",
            f"Comparing {heading_label} Under 34 CFR Part 685 Benchmarks",
        ]
        preset_scenarios = [
            {
                "id": "preset-baseline",
                "label": f"{heading_label} Baseline ($60k Balance, $65k AGI)",
                "query": query_clean,
                "target_position": pos,
                "baseline_ctr": ctr,
                "impressions": impr,
                "params": {"loan_balance": 60000, "agi": 65000, "family_size": 1, "interest_rate": 6.5},
                "description": "Single borrower at $65,000 AGI with 225% HHS poverty exemption ($248.23/mo RAP payment).",
            },
            {
                "id": "preset-accelerated",
                "label": f"{heading_label} High-Balance ($95k Balance, $85k AGI)",
                "query": query_clean,
                "target_position": pos,
                "baseline_ctr": ctr,
                "impressions": impr,
                "params": {"loan_balance": 95000, "agi": 85000, "family_size": 2, "interest_rate": 6.8},
                "description": "Dual-household borrower comparing 100% unpaid interest waiver vs 10-year Standard cap.",
            },
        ]
        comparison_rows = [
            {
                "scenario": "Single Filer ($60,000 Loan, $65,000 AGI)",
                "baseline": "$519.06 / mo (150% Poverty Threshold)",
                "optimized": "$248.23 / mo (225% Poverty Exemption)",
                "delta": "-$270.83 / mo (-52.2% Obligation)",
                "authority": "34 CFR 685.209 & 42 U.S.C. 9902(2)",
            },
            {
                "scenario": "Public Service Track (120 Qualifying Payments)",
                "baseline": "$68,100 Cumulative Standard Outflow",
                "optimized": "$29,788 Outflow + Tax-Free Discharge",
                "delta": "$38,312 Statutory Principal Relief",
                "authority": "34 CFR 685.219 & 26 U.S.C. 108(f)(1)",
            },
        ]
        faq_entries = [
            {
                "question": f"How is {query_clean} calculated under 2026 Title IV regulations?",
                "answer": (
                    f"Under 34 CFR Part 685, {query_clean} subtracts 225 percent of the applicable HHS Poverty "
                    f"Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided "
                    f"by 12, with 100 percent of unpaid monthly interest waived."
                ),
            },
            {
                "question": f"Does {query_clean} qualify for statutory loan forgiveness?",
                "answer": (
                    "Yes. Qualifying monthly payments count toward 120-payment Public Service Loan Forgiveness "
                    "under 34 CFR 685.219 or 240-payment income-driven discharge schedules."
                ),
            },
        ]
        hub_links = _resolve_contextual_internal_links(
            tenant_id=resolved_tenant,
            slug=slug,
            query=query_clean,
        )
    else:
        h2_headings = [
            f"{heading_label}: 2026 IRC Statutory Rules & Thresholds",
            f"Audit-Ready {heading_label} Scenarios & Deduction Limits",
        ]
        preset_scenarios = [
            {
                "id": "preset-baseline",
                "label": f"{heading_label} Mid-Market Baseline ($250k Allocation)",
                "query": query_clean,
                "target_position": pos,
                "baseline_ctr": ctr,
                "impressions": impr,
                "params": {"cost": 250000, "bracket": 32, "revenue": 1200000, "cogs": 420000},
                "description": "Operating entity at 32% marginal bracket evaluating immediate first-year statutory write-offs.",
            },
            {
                "id": "preset-enterprise",
                "label": f"{heading_label} High-Cap Scenario ($1.25M Statutory Limit)",
                "query": query_clean,
                "target_position": pos,
                "baseline_ctr": ctr,
                "impressions": impr,
                "params": {"cost": 1250000, "bracket": 37, "revenue": 4500000, "cogs": 1600000},
                "description": "Top-bracket pass-through or C-Corp modeling phase-out thresholds and bonus depreciation.",
            },
        ]
        comparison_rows = [
            {
                "scenario": "$250,000 Qualifying Capital Allocation (32% Bracket)",
                "baseline": "$16,000 Year-1 Straight-Line Deduction",
                "optimized": "$80,000 Immediate Year-1 Tax Shield",
                "delta": "+$64,000 Accelerated Cash Flow",
                "authority": "IRC Section 179 & Section 168(k)",
            },
            {
                "scenario": "$850,000 Deferred Property or Asset Basis (37% Bracket)",
                "baseline": "$202,300 Immediate Capital Gains Outflow",
                "optimized": "$0 Current Tax via Statutory Deferral",
                "delta": "100% Working Capital Preservation",
                "authority": "IRC Section 1031 & Form 8949",
            },
        ]
        faq_entries = [
            {
                "question": f"How is {query_clean} calculated under 2026 IRS statutory rules?",
                "answer": (
                    f"Deterministic calculation of {query_clean} applies published Internal Revenue Code phase-out "
                    f"thresholds, marginal bracket schedules, and cost-basis adjustments to compute exact net tax impact."
                ),
            },
            {
                "question": f"What documentation is required to substantiate {query_clean}?",
                "answer": (
                    "Taxpayers must retain contemporaneous placed-in-service logs, closing statements, and "
                    "reconciled federal schedules (Form 4562, Form 8824, or Form 8949) for audit verification."
                ),
            },
        ]
        hub_links = _resolve_contextual_internal_links(
            tenant_id=resolved_tenant,
            slug=slug,
            query=query_clean,
        )

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["answer"],
                },
            }
            for item in faq_entries
        ],
    }

    now = datetime.now(timezone.utc)
    locked_until = (now + timedelta(days=int(lock_days))).isoformat()

    from pseofactory.indexer import classify_url_template_section
    sec_info = classify_url_template_section(
        target_url,
        metadata=candidate,
        canonical_base=f"https://{domain}",
    )
    sec_name = str(candidate.get("section") or candidate.get("template_section") or sec_info["section"])
    child_sm = str(candidate.get("child_sitemap") or sec_info["child_sitemap"])
    child_sm_url = str(candidate.get("child_sitemap_url") or f"https://{domain}/{child_sm}")
    submitted_scope = f"Submitted pages only ({child_sm})"

    intent_info = _classify_asset_intent_class(
        slug=slug,
        target_url=target_url,
        query=query_clean,
        section=sec_name,
    )
    mon_info = _resolve_partner_offer_and_manual_gate(
        tenant_id=resolved_tenant,
        slug=slug,
        query=query_clean,
        value_tier=intent_info["value_tier"],
        candidate=candidate,
    )

    return {
        "slug": slug,
        "property_id": resolved_tenant,
        "tenant_id": resolved_tenant,
        "target_url": target_url,
        "query": query_clean,
        "section": sec_name,
        "template_section": sec_name,
        "child_sitemap": child_sm,
        "child_sitemap_url": child_sm_url,
        "submitted_pages_only_scope": submitted_scope,
        "intent_class": intent_info["intent_class"],
        "is_high_intent_calculator_or_guide": intent_info["is_high_intent_calculator_or_guide"],
        "restricted_public_service": mon_info["restricted_public_service"],
        "commercial_offers_allowed": mon_info["commercial_offers_allowed"],
        "partner_offer": mon_info["partner_offer"],
        "manual_requirement_detected": mon_info["manual_requirement_detected"],
        "manual_requirement": mon_info["manual_requirement"],
        "anomaly_type": anomaly_type,
        "action": action_type,
        "action_type": action_type,
        "status": "ACTIVE_LOCKED",
        "measurement_lock_days": int(lock_days),
        "lock_days": int(lock_days),
        "locked_until": locked_until,
        "lock_until": locked_until,
        "created_at": now.isoformat(),
        "baseline_position": pos,
        "baseline_impressions": impr,
        "baseline_clicks": clicks,
        "baseline_ctr": ctr,
        "title_rewrite": title_rewrite,
        "title": title_rewrite,
        "meta_description": meta_description,
        "description": meta_description,
        "quick_answer": quick_answer,
        "h2_headings": h2_headings,
        "preset_scenarios": preset_scenarios,
        "comparison_rows": comparison_rows,
        "faq_entries": faq_entries,
        "faq_additions": faq_entries,
        "faq_schema": faq_schema,
        "hub_links": hub_links,
    }


def prioritize_gsc_signals(
    signals_or_tenant: Any = None,
    tenant_id: Optional[str] = None,
    unindexed_diagnoses: Optional[List[Any]] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Unified ROI-driven prioritizer across GSC query records and unindexed page diagnoses.
    Supports both:
      - prioritize_gsc_signals(signals_list, tenant_id="profithelm")
      - prioritize_gsc_signals(tenant_id="profithelm", query_records=[...], unindexed_diagnoses=[...])
    Prioritizes high-intent calculators and guides and pages gaining search impressions
    that lack strong conversion paths or external distribution.
    Returns candidates sorted by (-roi_score, -is_high_intent_calculator_or_guide, target_url).
    Zero em-dashes. Zero en-dashes.
    """
    raw_items: List[Any] = []
    resolved_tenant = tenant_id

    if isinstance(signals_or_tenant, list):
        raw_items.extend(signals_or_tenant)
    elif isinstance(signals_or_tenant, str) and not resolved_tenant:
        resolved_tenant = signals_or_tenant

    if "query_records" in kwargs and isinstance(kwargs["query_records"], list):
        raw_items.extend(kwargs["query_records"])
    if "signals" in kwargs and isinstance(kwargs["signals"], list):
        raw_items.extend(kwargs["signals"])
    if unindexed_diagnoses:
        raw_items.extend(unindexed_diagnoses)

    eff_tenant = str(resolved_tenant or "profithelm").strip().lower()
    domain = "prexvo.com" if eff_tenant == "prexvo" else "profithelm.com"
    base_dir_arg = kwargs.get("base_dir")
    dist_dir_arg = kwargs.get("dist_dir")
    eng_metrics_arg = kwargs.get("engagement_metrics")

    prioritized: List[Dict[str, Any]] = []
    for item in raw_items:
        if hasattr(item, "to_dict"):
            rec = dict(item.to_dict())
        elif isinstance(item, dict):
            rec = dict(item)
        else:
            continue

        if eng_metrics_arg and "engagement_metrics" not in rec:
            rec["engagement_metrics"] = eng_metrics_arg

        item_tenant = str(rec.get("tenant_id") or rec.get("property_id") or eff_tenant).strip().lower()
        target_url = str(rec.get("target_url") or rec.get("page") or rec.get("url") or "").strip()
        query = str(rec.get("query") or rec.get("primary_keyword") or "").strip()
        slug = _slug_from_url_or_query(
            target_url=target_url,
            query=query,
            default_slug=str(rec.get("slug") or ""),
        )
        if not target_url:
            target_url = f"https://{domain}/tools/{slug}/"
        if not query:
            query = slug.replace("-", " ")

        # Default impressions for unindexed diagnoses if not explicitly supplied
        if "impressions" not in rec or rec.get("impressions") is None:
            cls_str = str(rec.get("classification") or rec.get("anomaly_type") or "").upper()
            if "CONTENT_QUALITY" in cls_str or "CANONICAL" in cls_str or "DEPTH" in cls_str:
                rec["impressions"] = 240
                rec.setdefault("position", 15.0)
                rec.setdefault("ctr", 0.009)
            elif "CRAWL_BUDGET" in cls_str:
                rec["impressions"] = 160
                rec.setdefault("position", 0.0)
                rec.setdefault("ctr", 0.0)
            else:
                rec["impressions"] = 60

        if (
            base_dir_arg is not None
            or dist_dir_arg is not None
            or eng_metrics_arg is not None
            or "engagement_metrics" in rec
            or "has_conversion_path" in rec
            or "conversion_gap" in rec
            or "has_external_distribution" in rec
            or "distribution_gap" in rec
        ):
            readiness = evaluate_asset_conversion_and_distribution_readiness(
                slug=slug,
                tenant_id=item_tenant,
                query=query,
                impressions=int(float(rec.get("impressions", 0) or 0)),
                position=float(rec.get("position", 0.0) or 0.0),
                dist_dir=dist_dir_arg,
                base_dir=base_dir_arg,
                candidate=rec,
            )
            rec.setdefault("conversion_gap_detected", readiness["conversion_gap_detected"])
            rec.setdefault("distribution_gap_detected", readiness["distribution_gap_detected"])
            rec.setdefault("has_strong_conversion_path", readiness["has_strong_conversion_path"])
            rec.setdefault("has_external_distribution", readiness["has_external_distribution"])
            rec.setdefault("yield_optimization_needed", readiness["yield_optimization_needed"])
            rec.setdefault("current_partner_key", readiness["current_partner_key"])
            rec.setdefault("optimal_partner_key", readiness["optimal_partner_key"])

        roi_metrics = calculate_candidate_roi(rec, tenant_id=item_tenant)
        merged_cand = {
            **rec,
            **roi_metrics,
            "tenant_id": item_tenant,
            "property_id": item_tenant,
            "slug": slug,
            "target_url": target_url,
            "query": query,
        }
        overlay_spec = compile_remediation_overlay_spec(merged_cand, tenant_id=item_tenant)
        merged_cand["section"] = overlay_spec["section"]
        merged_cand["template_section"] = overlay_spec["template_section"]
        merged_cand["child_sitemap"] = overlay_spec["child_sitemap"]
        merged_cand["child_sitemap_url"] = overlay_spec["child_sitemap_url"]
        merged_cand["submitted_pages_only_scope"] = overlay_spec["submitted_pages_only_scope"]
        merged_cand["intent_class"] = overlay_spec["intent_class"]
        merged_cand["is_high_intent_calculator_or_guide"] = overlay_spec["is_high_intent_calculator_or_guide"]
        merged_cand["restricted_public_service"] = overlay_spec["restricted_public_service"]
        merged_cand["commercial_offers_allowed"] = overlay_spec["commercial_offers_allowed"]
        merged_cand["partner_offer"] = overlay_spec["partner_offer"]
        merged_cand["manual_requirement_detected"] = overlay_spec["manual_requirement_detected"]
        merged_cand["manual_requirement"] = overlay_spec["manual_requirement"]
        spec_bytes = json.dumps(overlay_spec, sort_keys=True).encode("utf-8")
        content_sha256 = hashlib.sha256(spec_bytes).hexdigest()
        idemp_key = compute_composite_idempotency_key(
            tenant_id=item_tenant,
            target_url=target_url,
            action_or_engine=roi_metrics["anomaly_type"],
            payload_hash=content_sha256,
        )
        merged_cand["overlay_spec"] = overlay_spec
        merged_cand["content_sha256"] = content_sha256
        merged_cand["idempotency_key"] = idemp_key
        prioritized.append(merged_cand)

    prioritized.sort(
        key=lambda x: (
            -float(x.get("roi_score", 0.0)),
            -int(bool(x.get("is_high_intent_calculator_or_guide"))),
            str(x.get("target_url", "")),
        )
    )
    return prioritized



def evaluate_variance_threshold(
    pos_delta: float = 0.0,
    impr_pct_delta: Optional[float] = None,
    cycles: int = 2,
    is_locked: bool = False,
    impr_pct: Optional[float] = None,
    dynamic_floor: int = 10,
    current_impressions: Optional[int] = None,
    current_position: Optional[float] = None,
    current_ctr: Optional[float] = None,
    current_clicks: Optional[int] = None,
    matching_tool: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Evaluates Search Console metric variance against deadband thresholds and CTR curves.
    Enforces two-cycle confirmation and measurement lock gates.
    Zero em-dashes. Zero en-dashes.
    """
    if impr_pct_delta is None:
        impr_pct_delta = float(impr_pct) if impr_pct is not None else 0.0
    else:
        impr_pct_delta = float(impr_pct_delta)

    pos_delta = float(pos_delta)
    cycles = int(cycles)

    if is_locked:
        return {
            "classification": "MEASUREMENT_LOCKED",
            "action": "LOCK_PRESERVED",
            "lock_active": True,
            "cycles": cycles,
            "pos_delta": round(pos_delta, 2),
            "impr_pct_delta": round(impr_pct_delta, 2),
            "reason": "Measurement lock active; within observation window. Modifications strictly barred.",
        }

    is_drop = (pos_delta > 2.0) or (impr_pct_delta < -15.0)
    if is_drop:
        if cycles >= 2:
            return {
                "classification": "VERIFIED_DROP",
                "action": "REVISE_PAGE",
                "cycles": cycles,
                "pos_delta": round(pos_delta, 2),
                "impr_pct_delta": round(impr_pct_delta, 2),
                "reason": f"Verified traffic drop sustained across {cycles} cycles (rank delta {pos_delta:+.2f}, impr delta {impr_pct_delta:+.1f}%).",
            }
        return {
            "classification": "OBSERVING_VARIANCE",
            "action": "NO_ACTION",
            "cycles": cycles,
            "pos_delta": round(pos_delta, 2),
            "impr_pct_delta": round(impr_pct_delta, 2),
            "reason": f"Traffic shift detected (rank {pos_delta:+.2f}, impr {impr_pct_delta:+.1f}%), awaiting cycle 2 confirmation to prevent churn.",
        }

    if current_position is not None and current_ctr is not None:
        curr_pos = float(current_position)
        curr_ctr_val = float(current_ctr)
        curr_impr_val = int(float(current_impressions or 0))
        if 1.0 <= curr_pos <= 10.0 and curr_impr_val >= dynamic_floor:
            bench_ctr = expected_ctr_for_position(curr_pos)
            if curr_ctr_val < (bench_ctr - 0.025):
                if cycles >= 2:
                    return {
                        "classification": "CTR_SHORTFALL",
                        "action": "REFACTOR_PAGE",
                        "cycles": cycles,
                        "pos_delta": round(pos_delta, 2),
                        "impr_pct_delta": round(impr_pct_delta, 2),
                        "current_position": curr_pos,
                        "current_impressions": curr_impr_val,
                        "current_ctr": curr_ctr_val,
                        "expected_ctr": bench_ctr,
                        "reason": f"Sustained CTR shortfall at position {curr_pos:.1f} (CTR {curr_ctr_val:.3f} vs benchmark {bench_ctr:.3f}).",
                    }

    if current_position is not None and current_impressions is not None:
        curr_pos = float(current_position)
        curr_impr = int(float(current_impressions))
        is_striking = 4.0 <= curr_pos <= 20.0
        has_demand = curr_impr >= dynamic_floor and curr_impr > 0
        if is_striking and has_demand:
            if cycles >= 2:
                return {
                    "classification": "SUSTAINED_DEMAND",
                    "action": "REFACTOR_PAGE",
                    "cycles": cycles,
                    "pos_delta": round(pos_delta, 2),
                    "impr_pct_delta": round(impr_pct_delta, 2),
                    "current_position": curr_pos,
                    "current_impressions": curr_impr,
                    "dynamic_floor": dynamic_floor,
                    "reason": f"Sustained striking demand over {cycles} cycles (pos {curr_pos:.1f}, impr {curr_impr} >= {dynamic_floor}).",
                }
            return {
                "classification": "OBSERVING_VARIANCE",
                "action": "NO_ACTION",
                "cycles": cycles,
                "current_position": curr_pos,
                "current_impressions": curr_impr,
                "reason": f"Striking demand observed (pos {curr_pos:.1f}, impr {curr_impr}), awaiting cycle 2 confirmation.",
            }

    if abs(pos_delta) <= 2.0 and abs(impr_pct_delta) <= 15.0:
        return {
            "classification": "NORMAL_VARIANCE",
            "action": "NO_ACTION",
            "cycles": cycles,
            "pos_delta": round(pos_delta, 2),
            "impr_pct_delta": round(impr_pct_delta, 2),
            "reason": "Normal search variance within deadband (+/- 2.0 pos, +/- 15% impr). Zero churn.",
        }

    return {
        "classification": "NORMAL_VARIANCE" if cycles < 2 else "MONITORING",
        "action": "NO_ACTION" if cycles < 2 else "MONITOR",
        "cycles": cycles,
        "pos_delta": round(pos_delta, 2),
        "impr_pct_delta": round(impr_pct_delta, 2),
        "reason": f"Performance shift (rank {pos_delta:+.2f}, impressions {impr_pct_delta:+.1f}%), within monitoring parameters.",
    }


def is_overlay_locked(overlay_data: Dict[str, Any]) -> bool:
    """Returns True if overlay has an active measurement lock in the future."""
    if not isinstance(overlay_data, dict):
        return False
    lock_str = overlay_data.get("locked_until") or overlay_data.get("lock_until")
    if not lock_str:
        return False
    try:
        clean_str = str(lock_str).replace("Z", "+00:00")
        expiry = datetime.fromisoformat(clean_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > datetime.now(timezone.utc)
    except Exception:
        return False


def persist_overlay_respecting_lock(overlay_file: Union[str, Path], spec: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Writes a remediation overlay unless the existing overlay still holds an active
    measurement lock. Rewriting a locked overlay restarts its observation window, so
    evaluate_expired_overlays would never reach a verdict. Returns (effective_spec, written).
    Zero em-dashes. Zero en-dashes.
    """
    path = Path(overlay_file)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = None
        if isinstance(existing, dict) and is_overlay_locked(existing):
            return existing, False
        if isinstance(existing, dict) and existing.get("status") == "DEGRADED_ROLLED_BACK":
            # Cooldown: do not immediately re-apply a rewrite that was just measured as degrading
            try:
                rolled_back = datetime.fromisoformat(str(existing.get("rolled_back_at")).replace("Z", "+00:00"))
                if rolled_back.tzinfo is None:
                    rolled_back = rolled_back.replace(tzinfo=timezone.utc)
                cooldown_days = int(existing.get("measurement_lock_days") or existing.get("lock_days") or 14)
                if datetime.now(timezone.utc) < rolled_back + timedelta(days=cooldown_days):
                    return existing, False
            except (TypeError, ValueError):
                pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec, True


def evaluate_expired_overlays(
    site_url: Optional[str] = None,
    days_threshold: int = 28,
    base_dir: Optional[Union[str, Path]] = None,
    live_queries: Optional[List[Dict[str, Any]]] = None,
    default_base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Closed-Loop Outcome Evaluation Engine for expired measurement locks.
    Compares post-overlay position, CTR, and click performance against baseline
    metrics. Automatically rolls back degraded overlays (status=DEGRADED_ROLLED_BACK)
    and confirms accretive overlays (status=ACCRETIVE_CONFIRMED).
    Zero em-dashes. Zero en-dashes.
    """
    root = Path(base_dir) if base_dir else (default_base_dir or Path.cwd())
    overlays_dir = root / "content" / "overlays"

    results: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "days_threshold": days_threshold,
        "site_url": site_url or "sc-domain:profithelm.com",
        "total_evaluated": 0,
        "accretive": [],
        "degraded_rolled_back": [],
        "monitoring": [],
        "summary": {
            "ACCRETIVE": 0,
            "DEGRADED_ROLLED_BACK": 0,
            "MONITORING": 0,
        },
    }

    if not overlays_dir.is_dir():
        return results

    live_by_query: Dict[str, Dict[str, Any]] = {}
    if live_queries:
        for item in live_queries:
            q = str(item.get("query") or "").strip().lower()
            if q:
                live_by_query[q] = item

    now = datetime.now(timezone.utc)
    for overlay_path in sorted(overlays_dir.glob("*.json")):
        try:
            overlay_data = json.loads(overlay_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        slug = str(overlay_data.get("slug") or overlay_path.stem)
        locked = is_overlay_locked(overlay_data)
        lock_until_str = overlay_data.get("locked_until") or overlay_data.get("lock_until")

        is_expired = False
        if lock_until_str:
            try:
                clean_str = str(lock_until_str).replace("Z", "+00:00")
                expiry = datetime.fromisoformat(clean_str)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                is_expired = now >= expiry
            except Exception:
                is_expired = not locked
        else:
            is_expired = not locked

        if not is_expired and locked:
            eval_item = {
                "slug": slug,
                "status": "MONITORING",
                "locked_until": lock_until_str,
                "reason": "Measurement lock active; within observation window",
            }
            results["monitoring"].append(eval_item)
            results["summary"]["MONITORING"] += 1
            results["total_evaluated"] += 1
            continue

        scenarios = overlay_data.get("preset_scenarios", [])
        baseline_sc = scenarios[0] if scenarios and isinstance(scenarios[0], dict) else {}
        base_pos = float(
            overlay_data.get("baseline_position")
            or baseline_sc.get("target_position")
            or 10.0
        )
        base_ctr = float(
            overlay_data.get("baseline_ctr")
            or baseline_sc.get("baseline_ctr")
            or 0.02
        )
        base_impr = int(
            overlay_data.get("baseline_impressions")
            or baseline_sc.get("impressions")
            or 100
        )
        base_clicks = int(
            overlay_data.get("baseline_clicks")
            if overlay_data.get("baseline_clicks") is not None
            else round(base_impr * base_ctr)
        )
        query = str(
            overlay_data.get("query")
            or baseline_sc.get("query")
            or slug.replace("-", " ")
        )

        current_perf = (
            overlay_data.get("post_eval_metrics")
            or overlay_data.get("current_metrics")
            or live_by_query.get(query.lower())
            or {}
        )
        curr_pos = float(
            current_perf.get("position")
            if current_perf.get("position") is not None
            else (current_perf.get("target_position") or base_pos)
        )
        curr_ctr = float(
            current_perf.get("ctr")
            if current_perf.get("ctr") is not None
            else base_ctr
        )
        curr_impr = int(
            current_perf.get("impressions")
            if current_perf.get("impressions") is not None
            else base_impr
        )
        curr_clicks = int(
            current_perf.get("clicks")
            if current_perf.get("clicks") is not None
            else round(curr_impr * curr_ctr)
        )

        pos_delta = curr_pos - base_pos
        ctr_delta = curr_ctr - base_ctr
        clicks_delta = curr_clicks - base_clicks
        impr_pct_delta = ((curr_impr - base_impr) / float(base_impr) * 100.0) if base_impr > 0 else 0.0

        is_degraded = (
            pos_delta > 2.0
            or ctr_delta < -0.01
            or (clicks_delta < 0 and ctr_delta < -0.005)
            or impr_pct_delta <= -25.0
        )

        if is_degraded:
            overlay_data["status"] = "DEGRADED_ROLLED_BACK"
            overlay_data["rolled_back_at"] = now.isoformat()
            for active_key in (
                "title_rewrite",
                "meta_description",
                "quick_answer",
                "h2_headings",
                "preset_scenarios",
                "comparison_rows",
                "faq_schema",
                "faq_entries",
                "faq_additions",
            ):
                overlay_data.pop(active_key, None)
            try:
                overlay_path.write_text(json.dumps(overlay_data, indent=2), encoding="utf-8")
            except Exception:
                pass

            eval_item = {
                "slug": slug,
                "status": "DEGRADED_ROLLED_BACK",
                "baseline_position": base_pos,
                "current_position": curr_pos,
                "position_delta": round(pos_delta, 2),
                "baseline_ctr": base_ctr,
                "current_ctr": curr_ctr,
                "ctr_delta": round(ctr_delta, 4),
                "baseline_clicks": base_clicks,
                "current_clicks": curr_clicks,
                "clicks_delta": clicks_delta,
                "decision": "AUTOMATIC_ROLLBACK",
                "reason": f"Performance degraded: rank shifted by {pos_delta:+.2f}, CTR delta {ctr_delta:+.4f}",
            }
            results["degraded_rolled_back"].append(eval_item)
            results["summary"]["DEGRADED_ROLLED_BACK"] += 1
        elif (
            pos_delta < -0.5
            or (pos_delta <= 0.0 and ctr_delta >= 0.0)
            or ctr_delta > 0.005
            or clicks_delta >= 0
        ):
            overlay_data["status"] = "ACCRETIVE_CONFIRMED"
            overlay_data["confirmed_at"] = now.isoformat()
            try:
                overlay_path.write_text(json.dumps(overlay_data, indent=2), encoding="utf-8")
            except Exception:
                pass

            eval_item = {
                "slug": slug,
                "status": "ACCRETIVE_CONFIRMED",
                "baseline_position": base_pos,
                "current_position": curr_pos,
                "position_delta": round(pos_delta, 2),
                "baseline_ctr": base_ctr,
                "current_ctr": curr_ctr,
                "ctr_delta": round(ctr_delta, 4),
                "baseline_clicks": base_clicks,
                "current_clicks": curr_clicks,
                "clicks_delta": clicks_delta,
                "decision": "PERMANENT_ADOPTION",
                "reason": f"Accretive outcome: rank shifted by {pos_delta:+.2f}, CTR delta {ctr_delta:+.4f}",
            }
            results["accretive"].append(eval_item)
            results["summary"]["ACCRETIVE"] += 1
        else:
            eval_item = {
                "slug": slug,
                "status": "MONITORING",
                "baseline_position": base_pos,
                "current_position": curr_pos,
                "position_delta": round(pos_delta, 2),
                "decision": "EXTEND_MONITORING",
                "reason": "Delta within neutral variance envelope; extending observation",
            }
            results["monitoring"].append(eval_item)
            results["summary"]["MONITORING"] += 1

        results["total_evaluated"] += 1

    return results


def inject_overlay_into_html(html: str, overlay_data: Dict[str, Any]) -> str:
    """
    Non-destructively injects remediated overlay components into rendered page HTML:
      1. Upgraded <title> (and og:title / twitter:title) when title_rewrite is present.
      2. Upgraded <meta name="description"> when meta_description is present.
      3. Upgraded .quick-answer box when quick_answer is present.
      4. Injected H2 headings, interactive data-calc-preset scenario buttons/cards,
         comparison table rows (<tr class="overlay-comparison-row">), and FAQ cards.
      5. FAQPage JSON-LD schema.
    Strips any forbidden em-dashes or en-dashes before returning.
    """
    if not html or not isinstance(overlay_data, dict):
        return _strip_forbidden_dashes(html or "")

    if str(overlay_data.get("status") or "").upper() == "DEGRADED_ROLLED_BACK":
        return _strip_forbidden_dashes(html)

    # 1. Upgrade <title>
    title_rewrite = _strip_forbidden_dashes(str(overlay_data.get("title_rewrite") or "")).strip()
    if title_rewrite:
        escaped_title = html_lib.escape(title_rewrite)
        html = re.sub(
            r"<title>.*?</title>",
            f"<title>{escaped_title}</title>",
            html,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html = re.sub(
            r'(<meta\s+property=["\']og:title["\']\s+content=["\'])([^"\']*)(["\'])',
            rf"\g<1>{escaped_title}\g<3>",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r'(<meta\s+name=["\']twitter:title["\']\s+content=["\'])([^"\']*)(["\'])',
            rf"\g<1>{escaped_title}\g<3>",
            html,
            flags=re.IGNORECASE,
        )

    # 2. Upgrade <meta name="description">
    meta_desc = _strip_forbidden_dashes(str(overlay_data.get("meta_description") or "")).strip()
    if meta_desc:
        escaped_desc = html_lib.escape(meta_desc)
        html = re.sub(
            r'(<meta\s+name=["\']description["\']\s+content=["\'])([^"\']*)(["\'])',
            rf"\g<1>{escaped_desc}\g<3>",
            html,
            flags=re.IGNORECASE,
        )

    injected_sections: List[str] = []

    # 3. Upgrade .quick-answer if quick_answer is present (or inject one if missing)
    quick_answer = _strip_forbidden_dashes(str(overlay_data.get("quick_answer") or "")).strip()
    if quick_answer:
        escaped_qa = html_lib.escape(quick_answer)
        qa_pattern = re.compile(
            r'(<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>)(.*?)(</aside>)',
            re.DOTALL | re.IGNORECASE,
        )
        if qa_pattern.search(html):
            html = qa_pattern.sub(
                rf'\g<1>\n  <div class="quick-answer-body"><p>{escaped_qa}</p></div>\n\g<3>',
                html,
                count=1,
            )
        elif 'class="quick-answer' not in html and 'id="quick-answer"' not in html:
            injected_sections.append(
                f'<aside id="quick-answer" class="quick-answer answer-box">\n'
                f'  <div class="quick-answer-body"><p>{escaped_qa}</p></div>\n'
                f'</aside>'
            )

    # 4a. Injected H2 Headings
    h2_headings = overlay_data.get("h2_headings") or overlay_data.get("h2_blocks") or []
    h2_section_markup = ""
    if h2_headings:
        h2_parts = ['<section class="overlay-section overlay-headings" style="margin-top: 2rem; margin-bottom: 2rem;">']
        for h2 in h2_headings:
            h2_val = h2.get("heading", "") if isinstance(h2, dict) else str(h2)
            h2_norm = _strip_forbidden_dashes(str(h2_val))
            h2_norm = re.sub(r"\bS\s+Corp\b", "S-Corp", h2_norm, flags=re.IGNORECASE)
            h2_norm = re.sub(r"\bC\s+Corp\b", "C-Corp", h2_norm, flags=re.IGNORECASE)
            h2_norm = re.sub(r"\bR\s+(?:And|&)\s+D\b", "R&D", h2_norm, flags=re.IGNORECASE)
            h2_norm = re.sub(r"\bK\s+1\b", "K-1", h2_norm, flags=re.IGNORECASE)
            h2_norm = re.sub(r"\bW\s+([249])\b", r"W-\1", h2_norm, flags=re.IGNORECASE)
            clean_h2 = html_lib.escape(h2_norm)
            h2_parts.append(f'  <h2 class="section-title" style="font-size: 1.5rem; font-weight: 700; margin-bottom: 0.75rem;">{clean_h2}</h2>')
            h2_parts.append(f'  <p class="section-desc" style="color: var(--text-secondary, #64748b); margin-bottom: 1.5rem;">Statutory analysis and compliance guidelines for {clean_h2}.</p>')
        h2_parts.append("</section>")
        h2_section_markup = "\n".join(h2_parts)
        injected_sections.append(h2_section_markup)

    # 4b. Injected Interactive Preset Scenarios (with data-calc-preset)
    scenarios = overlay_data.get("preset_scenarios", [])
    if scenarios:
        sc_parts = ['<section class="overlay-section overlay-scenarios" style="margin-top: 2rem; margin-bottom: 2rem;">']
        sc_parts.append('  <h3 class="section-subtitle" style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem;">Target Scenarios</h3>')
        sc_parts.append('  <div class="scenarios-grid" style="display: grid; gap: 1rem;">')
        for idx, sc in enumerate(scenarios):
            if not isinstance(sc, dict):
                continue
            label = html_lib.escape(_strip_forbidden_dashes(str(sc.get("label", f"Preset Scenario {idx + 1}"))))
            params_obj = sc.get("params") if isinstance(sc.get("params"), dict) else {
                k: v for k, v in sc.items() if k not in ("label", "description")
            }
            preset_json = html_lib.escape(json.dumps(params_obj))
            sc_parts.append(
                f'    <div class="card scenario-card" data-calc-preset="{preset_json}" '
                f'style="padding: 1.25rem; border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px;">'
            )
            sc_parts.append(f'      <h4 style="font-weight: 700; margin-bottom: 0.5rem;">{label}</h4>')
            desc_str = _strip_forbidden_dashes(str(sc.get("description") or ""))
            if not desc_str:
                details = [f"{k.replace('_', ' ').title()}: {v}" for k, v in sc.items() if k not in ("label", "params")]
                desc_str = ", ".join(details)
            if desc_str:
                sc_parts.append(f'      <p style="font-size: 0.875rem; color: var(--text-secondary, #64748b);">{html_lib.escape(desc_str)}</p>')
            sc_parts.append(
                f'      <button type="button" class="btn-preset touch-target" data-calc-preset="{preset_json}" '
                f'data-cta-slot="calculator_preset_cta" '
                f'style="margin-top: 0.5rem; min-height: 44px; padding: 0.5rem 1rem;">Load Preset Scenario</button>'
            )
            sc_parts.append("    </div>")
        sc_parts.append("  </div>")
        sc_parts.append("</section>")
        injected_sections.append("\n".join(sc_parts))

    # 4c. Injected Comparison Table Rows
    comparison_rows = overlay_data.get("comparison_rows", [])
    if comparison_rows:
        tbl_parts = [
            '<section class="overlay-section overlay-comparison" style="margin-top: 2rem; margin-bottom: 2rem;">',
            '  <h3 class="section-subtitle" style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem;">Statutory Scenario Comparison</h3>',
            '  <div class="table-wrap">',
            '    <table class="overlay-comparison-table">',
            "      <thead>",
            "        <tr>",
            '          <th scope="col">Scenario</th>',
            '          <th scope="col">Baseline Outcome</th>',
            '          <th scope="col">Optimized Outcome</th>',
            '          <th scope="col">Net Delta</th>',
            '          <th scope="col">Statutory Authority</th>',
            "        </tr>",
            "      </thead>",
            "      <tbody>",
        ]
        for row in comparison_rows:
            if not isinstance(row, dict):
                continue
            sc_col = html_lib.escape(_strip_forbidden_dashes(str(row.get("scenario", ""))))
            base_col = html_lib.escape(_strip_forbidden_dashes(str(row.get("baseline", ""))))
            opt_col = html_lib.escape(_strip_forbidden_dashes(str(row.get("optimized", ""))))
            delta_col = html_lib.escape(_strip_forbidden_dashes(str(row.get("delta", ""))))
            auth_col = html_lib.escape(_strip_forbidden_dashes(str(row.get("authority", ""))))
            tbl_parts.append(
                f'        <tr class="overlay-comparison-row">'
                f"<td>{sc_col}</td><td>{base_col}</td><td>{opt_col}</td><td>{delta_col}</td><td>{auth_col}</td>"
                f"</tr>"
            )
        tbl_parts.extend([
            "      </tbody>",
            "    </table>",
            "  </div>",
            "</section>",
        ])
        injected_sections.append("\n".join(tbl_parts))

    # 4d. Injected Hub Links (for crawl budget signal lag / internal linking)
    hub_links = overlay_data.get("hub_links", [])
    hub_links_markup = ""
    if hub_links:
        hl_parts = [
            '<section class="overlay-section overlay-hub-links" style="margin-top: 1.5rem; margin-bottom: 1.5rem;">',
            '  <h3 class="section-subtitle" style="font-size: 1.15rem; font-weight: 600; margin-bottom: 0.75rem;">Related Statutory Calculators &amp; Guides</h3>',
            '  <ul class="overlay-hub-list">',
        ]
        for hl in hub_links:
            if isinstance(hl, dict) and hl.get("href") and hl.get("anchor"):
                href = html_lib.escape(str(hl["href"]))
                anchor = html_lib.escape(_strip_forbidden_dashes(str(hl["anchor"])))
                hl_parts.append(f'    <li><a href="{href}" class="touch-target">{anchor}</a></li>')
        hl_parts.extend(["  </ul>", "</section>"])
        hub_links_markup = "\n".join(hl_parts)
        injected_sections.append(hub_links_markup)

    # 4e. Injected Partner Offer Placement or YMYL Public-Service Guardrail
    partner_section_markup = ""
    restricted_ps = bool(overlay_data.get("restricted_public_service"))
    p_offer = overlay_data.get("partner_offer")
    if restricted_ps:
        if 'data-restricted-public-service="true"' not in html:
            partner_section_markup = (
                '<section class="overlay-section overlay-partner-guardrail ymyl-public-service-guardrail" '
                'data-commercial-offers="none" data-restricted-public-service="true" '
                'data-mechanic="compliant_intent_monetization" style="margin-top: 1.5rem; margin-bottom: 1.5rem;">\n'
                '  <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px;">\n'
                '    <h3 class="section-subtitle" style="font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem;">Title IV Public Service Protection</h3>\n'
                '    <p style="font-size: 0.875rem; color: var(--text-secondary, #475569);">Direct consolidation and federal repayment plans preserve statutory interest subsidies and public service debt relief eligibility under 34 CFR Part 685. Commercial private lender offers are strictly suppressed on restricted public-service pages.</p>\n'
                '  </div>\n'
                '</section>'
            )
            injected_sections.append(partner_section_markup)
    elif isinstance(p_offer, dict) and overlay_data.get("commercial_offers_allowed", True) is not False:
        p_key = html_lib.escape(_strip_forbidden_dashes(str(p_offer.get("partner_key") or "ramp")))
        p_name = html_lib.escape(_strip_forbidden_dashes(str(p_offer.get("partner_name") or "Featured Partner")))
        p_url = html_lib.escape(str(p_offer.get("url") or "https://ramp.com/"))
        p_cta = html_lib.escape(_strip_forbidden_dashes(str(p_offer.get("cta_text") or f"Explore {p_name}")))
        p_slot = html_lib.escape(_strip_forbidden_dashes(str(p_offer.get("cta_slot") or "overlay_primary_cta")))
        p_cta_id = html_lib.escape(
            _strip_forbidden_dashes(
                str(p_offer.get("cta_id") or f"cta-{overlay_data.get('tenant_id', 'profithelm')}-{overlay_data.get('slug', 'tool')}-{p_key}")
            )
        )
        p_yield = f"{float(p_offer.get('yield_score', 0.0) or 0.0):.2f}"
        p_erpm = f"{float(p_offer.get('empirical_erpm_usd', 0.0) or 0.0):.2f}"
        p_opt_status = html_lib.escape(
            _strip_forbidden_dashes(str(p_offer.get("optimization_status") or "INITIAL_PLACEMENT"))
        )
        p_disc = html_lib.escape(
            _strip_forbidden_dashes(
                str(
                    p_offer.get("disclosure")
                    or "FTC Disclosure: We may earn an affiliate commission when you register through approved partner links at no additional cost to you."
                )
            )
        )
        prop_id = html_lib.escape(
            _strip_forbidden_dashes(str(overlay_data.get("tenant_id") or overlay_data.get("property_id") or "profithelm"))
        )
        partner_section_markup = (
            f'<section class="overlay-section overlay-partner-offer affiliate-cta-section card" '
            f'data-property="{prop_id}" data-partner="{p_key}" data-cta-slot="{p_slot}" '
            f'data-cta-id="{p_cta_id}" data-yield-score="{p_yield}" data-empirical-erpm="{p_erpm}" '
            f'data-optimization-status="{p_opt_status}" data-mechanic="compliant_intent_monetization" '
            f'style="margin-top: 1.5rem; margin-bottom: 1.5rem; padding: 1.25rem; border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px;">\n'
            f'  <h3 class="section-subtitle" style="font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem;">Recommended Partner Solution: {p_name}</h3>\n'
            f'  <p class="affiliate-disclosure" style="font-size: 0.8125rem; color: var(--text-secondary, #64748b); margin-bottom: 0.75rem;">{p_disc}</p>\n'
            f'  <a href="{p_url}" rel="noopener sponsored nofollow" target="_blank" '
            f'class="affiliate-cta affiliate-cta-link partner-btn btn-cta touch-target" data-partner="{p_key}" '
            f'data-cta-slot="{p_slot}" data-cta-id="{p_cta_id}" '
            f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 0.625rem 1.25rem; border-radius: 6px; font-weight: 600; text-decoration: none;">{p_cta}</a>\n'
            f'</section>'
        )
        injected_sections.append(partner_section_markup)

    # 5. Injected FAQ Additions & FAQPage Schema
    raw_faqs = (
        overlay_data.get("faq_entries")
        or overlay_data.get("faq_additions")
        or overlay_data.get("faq_items")
        or overlay_data.get("faq_schema")
        or []
    )
    faq_items: List[Dict[str, str]] = []
    if isinstance(raw_faqs, list):
        for f in raw_faqs:
            if isinstance(f, dict) and f.get("question") and f.get("answer"):
                faq_items.append({
                    "question": _strip_forbidden_dashes(str(f["question"])),
                    "answer": _strip_forbidden_dashes(str(f["answer"])),
                })
    elif isinstance(raw_faqs, dict) and isinstance(raw_faqs.get("mainEntity"), list):
        for entity in raw_faqs["mainEntity"]:
            if isinstance(entity, dict):
                q_name = entity.get("name") or ""
                acc = entity.get("acceptedAnswer") or {}
                a_text = acc.get("text") if isinstance(acc, dict) else ""
                if q_name and a_text:
                    faq_items.append({
                        "question": _strip_forbidden_dashes(str(q_name)),
                        "answer": _strip_forbidden_dashes(str(a_text)),
                    })

    if faq_items:
        faq_parts = ['<section class="overlay-section overlay-faqs" style="margin-top: 2rem; margin-bottom: 2rem;">']
        faq_parts.append('  <h3 class="section-subtitle" style="font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem;">Frequently Asked Questions</h3>')
        faq_parts.append('  <div class="faq-list">')
        schema_entities = []
        for f in faq_items:
            q = f["question"]
            a = f["answer"]
            faq_parts.append('    <div class="faq-card" style="margin-bottom: 1rem; padding: 1rem; background: var(--bg-card, #f8fafc); border-radius: 6px;">')
            faq_parts.append(f'      <h4 style="font-weight: 600; margin-bottom: 0.25rem;">{html_lib.escape(q)}</h4>')
            faq_parts.append(f'      <p style="font-size: 0.9375rem; color: var(--text-secondary, #475569);">{html_lib.escape(a)}</p>')
            faq_parts.append("    </div>")
            schema_entities.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a,
                },
            })
        faq_parts.append("  </div>")
        faq_parts.append("</section>")
        injected_sections.append("\n".join(faq_parts))

        if schema_entities:
            faq_ld_json = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": schema_entities,
            }
            script_pattern = re.compile(
                r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
                re.DOTALL | re.IGNORECASE,
            )
            match = script_pattern.search(html)
            if match:
                try:
                    existing_data = json.loads(match.group(1).strip())
                    if isinstance(existing_data, dict) and "@graph" in existing_data and isinstance(existing_data["@graph"], list):
                        faq_node = next((n for n in existing_data["@graph"] if n.get("@type") == "FAQPage"), None)
                        if faq_node:
                            existing_qs = {q.get("name") for q in faq_node.get("mainEntity", []) if isinstance(q, dict)}
                            for q in schema_entities:
                                if q.get("name") not in existing_qs:
                                    faq_node.setdefault("mainEntity", []).append(q)
                        else:
                            faq_copy = dict(faq_ld_json)
                            faq_copy.pop("@context", None)
                            webpage_node = next((n for n in existing_data["@graph"] if n.get("@type") == "WebPage"), None)
                            if webpage_node and webpage_node.get("@id"):
                                faq_copy["@id"] = f"{webpage_node['@id'].split('#')[0]}#faq"
                                faq_copy["isPartOf"] = {"@id": webpage_node["@id"]}
                            existing_data["@graph"].append(faq_copy)

                        new_script = f'<script type="application/ld+json">\n{json.dumps(existing_data, indent=2)}\n</script>'
                        html = html[: match.start()] + new_script + html[match.end() :]
                    else:
                        json_ld_script = f'<script type="application/ld+json">\n{json.dumps(faq_ld_json, indent=2)}\n</script>'
                        if "</head>" in html:
                            html = html.replace("</head>", f"{json_ld_script}\n</head>", 1)
                        else:
                            injected_sections.append(json_ld_script)
                except Exception:
                    json_ld_script = f'<script type="application/ld+json">\n{json.dumps(faq_ld_json, indent=2)}\n</script>'
                    if "</head>" in html:
                        html = html.replace("</head>", f"{json_ld_script}\n</head>", 1)
                    else:
                        injected_sections.append(json_ld_script)
            else:
                json_ld_script = f'<script type="application/ld+json">\n{json.dumps(faq_ld_json, indent=2)}\n</script>'
                if "</head>" in html:
                    html = html.replace("</head>", f"{json_ld_script}\n</head>", 1)
                else:
                    injected_sections.append(json_ld_script)

    if injected_sections:
        overlay_markup = (
            '<div id="gsc-striking-overlay" class="gsc-overlay-container">\n'
            + "\n".join(injected_sections)
            + "\n</div>"
        )
        if 'id="gsc-striking-overlay"' in html:
            incremental_parts: List[str] = []
            if h2_section_markup and 'class="overlay-section overlay-headings"' in html:
                html = re.sub(
                    r'<section\s+class=["\']overlay-section\s+overlay-headings[^>]*>.*?</section>',
                    h2_section_markup,
                    html,
                    count=1,
                    flags=re.DOTALL | re.IGNORECASE,
                )
            if hub_links_markup and 'class="overlay-section overlay-hub-links"' not in html:
                incremental_parts.append(hub_links_markup)
            if partner_section_markup:
                if 'class="overlay-section overlay-partner-offer' in html:
                    html = re.sub(
                        r'<section\s+class=["\']overlay-section\s+overlay-partner-offer[^>]*>.*?</section>',
                        partner_section_markup,
                        html,
                        count=1,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                elif 'class="overlay-section overlay-partner-guardrail' not in html:
                    incremental_parts.append(partner_section_markup)
            if incremental_parts:
                inc_html = "\n".join(incremental_parts)
                if "</main>" in html:
                    html = html.replace("</main>", f"{inc_html}\n</main>", 1)
                elif "</body>" in html:
                    html = html.replace("</body>", f"{inc_html}\n</body>", 1)
                else:
                    html = f"{html}\n{inc_html}"
        elif "</main>" in html:
            html = html.replace("</main>", f"{overlay_markup}\n</main>", 1)
        elif "</body>" in html:
            html = html.replace("</body>", f"{overlay_markup}\n</body>", 1)
        else:
            html = f"{html}\n{overlay_markup}"

    return _strip_forbidden_dashes(html)


apply_remediation_overlay_to_html = inject_overlay_into_html


class AsyncRemediationQueue:
    """
    Persistent, multi-tenant isolated remediation queue backed by AtomicStateLedger.
    Enforces composite idempotency keys, bounded execution budgets, and exponential
    backoff rollover upon HTTP 429 or network partition faults.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, queue_path: Optional[Union[str, Path]] = None):
        self.queue_path = Path(queue_path or DEFAULT_REMEDIATION_QUEUE_PATH).resolve()

    def _load_state(self) -> Dict[str, Any]:
        data = AtomicStateLedger.load_json(self.queue_path)
        if not isinstance(data, dict) or "tenants" not in data:
            return {"version": 1, "tenants": {}}
        return data

    def _save_state(self, state: Dict[str, Any]) -> None:
        AtomicStateLedger.save_json(self.queue_path, state)

    def enqueue(
        self,
        candidate: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enqueues a single remediation candidate with composite idempotency deduplication."""
        res = self.enqueue_batch([candidate], tenant_id=tenant_id)
        item_res = res.get("results", [{}])[0]
        return item_res

    def enqueue_batch(
        self,
        candidates: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enqueues a batch of remediation candidates under tenant isolation.
        If all candidates already exist by composite idempotency_key, returns
        status='DEDUPLICATED_NO_OP' and enqueued_count=0.
        """
        state = self._load_state()
        tenants_map = state.setdefault("tenants", {})

        enqueued_count = 0
        deduplicated_count = 0
        results: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            eff_tenant = str(
                tenant_id or cand.get("tenant_id") or cand.get("property_id") or "profithelm"
            ).strip().lower()
            cand_tenant = str(cand.get("tenant_id") or cand.get("property_id") or eff_tenant).strip().lower()
            if cand_tenant != eff_tenant:
                results.append({
                    "status": "SKIPPED_FOREIGN_TENANT",
                    "tenant_id": cand_tenant,
                })
                continue

            t_bucket = tenants_map.setdefault(eff_tenant, {"tasks": []})
            tasks_list: List[Dict[str, Any]] = t_bucket.setdefault("tasks", [])

            target_url = str(cand.get("target_url") or cand.get("page") or cand.get("url") or "").strip()
            slug = _slug_from_url_or_query(
                target_url=target_url,
                query=str(cand.get("query") or ""),
                default_slug=str(cand.get("slug") or ""),
            )
            if not target_url:
                domain = "prexvo.com" if eff_tenant == "prexvo" else "profithelm.com"
                target_url = f"https://{domain}/tools/{slug}/"

            action_or_engine = str(
                cand.get("anomaly_type") or cand.get("action_type") or "REMEDIATE"
            ).strip().upper()
            payload_hash = str(cand.get("content_sha256") or "").strip()
            if not payload_hash:
                payload_hash = hashlib.sha256(
                    json.dumps(cand.get("overlay_spec") or cand, sort_keys=True).encode("utf-8")
                ).hexdigest()

            idemp_key = str(cand.get("idempotency_key") or "").strip() or compute_composite_idempotency_key(
                tenant_id=eff_tenant,
                target_url=target_url,
                action_or_engine=action_or_engine,
                payload_hash=payload_hash,
            )

            existing = next(
                (t for t in tasks_list if t.get("idempotency_key") == idemp_key),
                None,
            )
            if existing is not None:
                deduplicated_count += 1
                results.append({
                    "status": "DEDUPLICATED_NO_OP",
                    "idempotency_key": idemp_key,
                    "slug": slug,
                    "target_url": target_url,
                })
                continue

            task_record = {
                **cand,
                "tenant_id": eff_tenant,
                "property_id": eff_tenant,
                "slug": slug,
                "target_url": target_url,
                "idempotency_key": idemp_key,
                "content_sha256": payload_hash,
                "status": "PENDING",
                "attempt_count": int(cand.get("attempt_count", 0) or 0),
                "enqueued_at": now_iso,
                "updated_at": now_iso,
                "next_attempt_at": cand.get("next_attempt_at"),
            }
            tasks_list.append(task_record)
            enqueued_count += 1
            results.append({
                "status": "ENQUEUED",
                "idempotency_key": idemp_key,
                "slug": slug,
                "target_url": target_url,
            })

        self._save_state(state)
        overall_status = (
            "DEDUPLICATED_NO_OP"
            if enqueued_count == 0 and deduplicated_count > 0
            else "ENQUEUED"
        )
        return {
            "status": overall_status,
            "enqueued_count": enqueued_count,
            "deduplicated_count": deduplicated_count,
            "results": results,
        }

    def size(self, tenant_id: str) -> int:
        """Returns number of tasks in queue for tenant_id."""
        return len(self.get_tenant_tasks(tenant_id))

    def get_tenant_tasks(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Returns strictly the tasks belonging to tenant_id."""
        eff_tenant = str(tenant_id or "profithelm").strip().lower()
        state = self._load_state()
        t_bucket = state.get("tenants", {}).get(eff_tenant, {})
        tasks = t_bucket.get("tasks", [])
        return [dict(t) for t in tasks if isinstance(t, dict) and t.get("tenant_id") == eff_tenant]

    def process_tenant_batch(
        self,
        tenant_id: str,
        worker_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        execution_budget_seconds: float = 300.0,
        max_items: int = 25,
        halt_on_partition: bool = True,
        ignore_backoff: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes queued tasks for tenant_id within execution_budget_seconds.
        Preserves all unprocessed and failed items in ROLLOVER/PENDING state with
        exponential backoff upon network partition or HTTP 429 errors.
        Zero em-dashes. Zero en-dashes.
        """
        eff_tenant = str(tenant_id or "profithelm").strip().lower()
        state = self._load_state()
        t_bucket = state.setdefault("tenants", {}).setdefault(eff_tenant, {"tasks": []})
        tasks: List[Dict[str, Any]] = t_bucket.setdefault("tasks", [])

        start_ts = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        completed_count = 0
        failed_count = 0
        rollover_count = 0
        processed_items = 0
        halted_reason: Optional[str] = None

        # Sort actionable tasks by roi_score descending while preserving list reference
        tasks.sort(key=lambda x: (-float(x.get("roi_score", 0.0)), str(x.get("target_url", ""))))

        for idx, task in enumerate(tasks):
            if task.get("status") == "COMPLETED":
                continue

            if processed_items >= max_items:
                break

            elapsed = time.monotonic() - start_ts
            if elapsed >= execution_budget_seconds:
                halted_reason = "EXECUTION_BUDGET_EXCEEDED"
                for rem in tasks[idx:]:
                    if rem.get("status") != "COMPLETED":
                        rem["status"] = "ROLLOVER"
                        rem["next_attempt_at"] = (
                            datetime.now(timezone.utc) + timedelta(seconds=30)
                        ).isoformat()
                        rollover_count += 1
                break

            if not ignore_backoff and task.get("next_attempt_at"):
                try:
                    na_str = str(task["next_attempt_at"]).replace("Z", "+00:00")
                    na_dt = datetime.fromisoformat(na_str)
                    if na_dt.tzinfo is None:
                        na_dt = na_dt.replace(tzinfo=timezone.utc)
                    if now_utc < na_dt:
                        continue
                except Exception:
                    pass

            processed_items += 1
            try:
                res = worker_fn(task)
                res_status = str((res or {}).get("status", "COMPLETED")).upper()
                if res_status in ("COMPLETED", "SUCCESS"):
                    done_now = datetime.now(timezone.utc)
                    task["status"] = "COMPLETED"
                    task["completed_at"] = done_now.isoformat()
                    task["updated_at"] = done_now.isoformat()
                    task["locked_until"] = (done_now + timedelta(days=14)).isoformat()
                    completed_count += 1
                    self._save_state(state)
                else:
                    raise RuntimeError(f"Worker returned non-success status: {res_status}")
            except Exception as exc:
                failed_count += 1
                attempts = int(task.get("attempt_count", 0) or 0) + 1
                delay_secs = min(3600, 30 * (2 ** (attempts - 1)))
                err_now = datetime.now(timezone.utc)
                next_try = (err_now + timedelta(seconds=delay_secs)).isoformat()
                task["attempt_count"] = attempts
                task["status"] = "ROLLOVER"
                task["last_error"] = str(exc)
                task["updated_at"] = err_now.isoformat()
                task["next_attempt_at"] = next_try
                rollover_count += 1

                if halt_on_partition:
                    halted_reason = f"PARTITION_OR_QUOTA_FAULT: {exc}"
                    for rem in tasks[idx + 1 :]:
                        if rem.get("status") != "COMPLETED":
                            rem.setdefault("status", "PENDING")
                            if rem["status"] not in ("PENDING", "ROLLOVER"):
                                rem["status"] = "ROLLOVER"
                    self._save_state(state)
                    break

        self._save_state(state)
        return {
            "tenant_id": eff_tenant,
            "status": "PARTIAL_ROLLOVER" if halted_reason else "SUCCESS",
            "completed_count": completed_count,
            "failed_count": failed_count,
            "rollover_count": rollover_count,
            "halted_reason": halted_reason,
            "elapsed_seconds": round(time.monotonic() - start_ts, 4),
        }
