"""
pseofactory Unified Affiliate Partner Registry & Dynamic Routing Engine
Centralized, single-source-of-truth affiliate configuration for pseofactory
properties (ProfitHelm and Prexvo).

Key Invariants:
1. Unified partner registry conforming to AffiliatePartner schema.
2. Property isolation: strict boundary enforcement preventing B2B monetization
   on Prexvo and student loan monetization on ProfitHelm.
3. Dynamic environment variable override engine (AFFILIATE_<KEY>_URL) with
   strict URL syntax validation (http/https only, no javascript/relative URLs).
4. Outbound link attributes: rel="noopener sponsored nofollow", target="_blank".
5. Mandatory FTC publisher disclosures and Prexvo Title IV statutory forfeiture disclaimers.
6. Zero em-dashes and zero en-dashes across all partner entries and disclosure copy.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, asdict
import html as html_lib
import json
import os
from pathlib import Path
import re
from typing import Dict, Any, List, Optional, Sequence, Set, Tuple
import urllib.parse

from pseofactory.contracts import assert_no_forbidden_dashes


CANONICAL_PARTNERSHIP_MODELS: Tuple[str, ...] = (
    "RECURRING_SAAS_REVSHARE",
    "CPA_BOUNTY",
    "QUALIFIED_LEAD_CPL",
    "HYBRID_CPA_REVSHARE",
    "USAGE_API_REFERRAL",
)

PARTNER_PARTNERSHIP_MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    # 1. Recurring SaaS Rev-Share (RECURRING_SAAS_REVSHARE)
    "coinledger": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 62.50,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 25.0,
        "recurring_horizon_months": 24,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.048,
        "ltv_bounty_equivalent_usd": 140.63,
    },
    "koinly": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 45.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.046,
        "ltv_bounty_equivalent_usd": 45.00,
    },
    "xendoo": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 500.00,
    },
    "efile_com": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 45.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 35.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.058,
        "ltv_bounty_equivalent_usd": 65.00,
    },
    "eztaxreturn_com": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 35.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.056,
        "ltv_bounty_equivalent_usd": 48.00,
    },
    "wallethub": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 50.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.062,
        "ltv_bounty_equivalent_usd": 50.00,
    },
    "taxbit": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 70.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 25.0,
        "recurring_horizon_months": 24,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 157.50,
    },
    "flexport": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 50.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 350.00,
    },
    "bench": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 225.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.042,
        "ltv_bounty_equivalent_usd": 292.50,
    },
    "pilot": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 300.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.042,
        "ltv_bounty_equivalent_usd": 390.00,
    },
    "jobber_field_service": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 160.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.048,
        "ltv_bounty_equivalent_usd": 217.60,
    },
    "aurora_solar_saas": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 180.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 244.80,
    },
    "simplepractice_ehr": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 135.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.048,
        "ltv_bounty_equivalent_usd": 183.60,
    },
    # 2. Hybrid Multi-Stage / CPA + Recurring Deals (HYBRID_CPA_REVSHARE)
    "rippling": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 1000.00,
        "cpl_lead_bounty_usd": 600.00,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"sqo_demo_usd": 600.0, "closed_won_usd": 1000.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 1100.00,
    },
    "deel": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 200.00,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"qualified_demo_usd": 200.0, "closed_won_usd": 500.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.042,
        "ltv_bounty_equivalent_usd": 455.00,
    },
    "crest_capital": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"firstpromoter_base_usd": 250.0, "impact_onboarded_usd": 500.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 575.00,
    },
    "equipment_macrs": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"firstpromoter_base_usd": 250.0, "impact_onboarded_usd": 500.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 575.00,
    },
    "suretybonds_direct": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 175.00,
        "cpl_lead_bounty_usd": 6.50,
        "recurring_revshare_pct": 30.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"free_trial_lead_usd": 6.50, "paid_contract_revshare_pct": 30.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 230.25,
    },
    "lawdepot": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 45.00,
        "cpl_lead_bounty_usd": 6.50,
        "recurring_revshare_pct": 30.0,
        "recurring_horizon_months": 12,
        "hybrid_stage_bounties_usd": {"free_trial_lead_usd": 6.50, "paid_subscription_revshare_pct": 30.0},
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.055,
        "ltv_bounty_equivalent_usd": 85.50,
    },
    "easyship_commerce": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 120.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.046,
        "ltv_bounty_equivalent_usd": 163.20,
    },
    "sprinto_compliance": {
        "partnership_model": "HYBRID_CPA_REVSHARE",
        "cpa_bounty_usd": 225.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 285.75,
    },
    "vanta_security": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 350.00,
        "cpl_lead_bounty_usd": 350.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.072,
        "ltv_bounty_equivalent_usd": 350.00,
    },
    "drata_compliance": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 300.00,
        "cpl_lead_bounty_usd": 300.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.070,
        "ltv_bounty_equivalent_usd": 300.00,
    },
    "thoropass_audit": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 325.00,
        "cpl_lead_bounty_usd": 325.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.068,
        "ltv_bounty_equivalent_usd": 325.00,
    },
    "coalition_cyber_insurance": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.075,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "cobalt_pentest": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 275.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 275.00,
    },
    "thimble_contractor": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 125.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.068,
        "ltv_bounty_equivalent_usd": 125.00,
    },
    "jobber_field_service": {
        "partnership_model": "RECURRING_SAAS_REVSHARE",
        "cpa_bounty_usd": 160.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 20.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.060,
        "ltv_bounty_equivalent_usd": 195.00,
    },
    "levelset_lien_filing": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 190.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Statutory preliminary notice and mechanics lien filing volume",
        "click_to_conversion_rate": 0.065,
        "ltv_bounty_equivalent_usd": 190.00,
    },
    # 3. Flat CPA Bounties (CPA_BOUNTY)
    "mercury": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.040,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "ramp": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.040,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "rho": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.040,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "brex": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 375.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.038,
        "ltv_bounty_equivalent_usd": 375.00,
    },
    "gusto": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 100.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 100.00,
    },
    "turbotax": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 45.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.055,
        "ltv_bounty_equivalent_usd": 45.00,
    },
    "taxslayer": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 32.50,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.055,
        "ltv_bounty_equivalent_usd": 32.50,
    },
    "freetaxusa": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 32.50,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.055,
        "ltv_bounty_equivalent_usd": 32.50,
    },
    "splash_financial": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 300.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.035,
        "ltv_bounty_equivalent_usd": 300.00,
    },
    "sofi": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 120.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.038,
        "ltv_bounty_equivalent_usd": 120.00,
    },
    "sofi_refi": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 120.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.038,
        "ltv_bounty_equivalent_usd": 120.00,
    },
    "earnest": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 200.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.036,
        "ltv_bounty_equivalent_usd": 200.00,
    },
    "laurel_road": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.036,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "juno": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 137.50,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.042,
        "ltv_bounty_equivalent_usd": 137.50,
    },
    "freightos_marketplace": {
        "partnership_model": "CPA_BOUNTY",
        "cpa_bounty_usd": 185.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.045,
        "ltv_bounty_equivalent_usd": 185.00,
    },
    # 4. Qualified Lead-Gen / CPL (QUALIFIED_LEAD_CPL)
    "ipx1031": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 500.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.068,
        "ltv_bounty_equivalent_usd": 500.00,
    },
    "exeter1031": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.072,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "simply_business": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 185.00,
        "cpl_lead_bounty_usd": 185.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.080,
        "ltv_bounty_equivalent_usd": 185.00,
    },
    "next_insurance_b2b": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 160.00,
        "cpl_lead_bounty_usd": 160.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.082,
        "ltv_bounty_equivalent_usd": 160.00,
    },
    "national_funding_med": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 200.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.070,
        "ltv_bounty_equivalent_usd": 500.00,
    },
    "national_funding": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 200.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.070,
        "ltv_bounty_equivalent_usd": 500.00,
    },
    "otr_solutions_factoring": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.074,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    "credible": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 112.50,
        "cpl_lead_bounty_usd": 112.50,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.075,
        "ltv_bounty_equivalent_usd": 112.50,
    },
    "guideline": {
        "partnership_model": "QUALIFIED_LEAD_CPL",
        "cpa_bounty_usd": 250.00,
        "cpl_lead_bounty_usd": 250.00,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 0,
        "usage_referral_basis": "",
        "click_to_conversion_rate": 0.068,
        "ltv_bounty_equivalent_usd": 250.00,
    },
    # 5. Usage / API / Transaction Volume Referrals (USAGE_API_REFERRAL)
    "kalshi": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 25.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 15.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "CFTC event contract exchange trading volume & $25 funded trader activation",
        "click_to_conversion_rate": 0.062,
        "ltv_bounty_equivalent_usd": 85.00,
    },
    "stripe": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 500.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 10.0,
        "recurring_horizon_months": 24,
        "usage_referral_basis": "Commercial payment processing volume & API merchant settlement",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 500.00,
    },
    "stripe_tax": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 200.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 10.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "Automated sales tax & 1099 API filing volume",
        "click_to_conversion_rate": 0.055,
        "ltv_bounty_equivalent_usd": 240.00,
    },
    "avalara": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 275.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 10.0,
        "recurring_horizon_months": 18,
        "usage_referral_basis": "Automated economic nexus & 1099 API transaction tier",
        "click_to_conversion_rate": 0.050,
        "ltv_bounty_equivalent_usd": 315.00,
    },
    "interactive_brokers": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 200.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Institutional treasury & quantitative execution account activity",
        "click_to_conversion_rate": 0.050,
        "ltv_bounty_equivalent_usd": 200.00,
    },
    "public_com": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 100.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Treasury bill & brokerage AUM allocation volume",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 100.00,
    },
    "wealthfront": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 175.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "High-yield cash sweep & automated treasury AUM allocation",
        "click_to_conversion_rate": 0.052,
        "ltv_bounty_equivalent_usd": 175.00,
    },
    "first_american": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 100.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Fractional real estate debt & 1031 capital deployment volume",
        "click_to_conversion_rate": 0.050,
        "ltv_bounty_equivalent_usd": 100.00,
    },
    "first_american_1031": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 100.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Fractional real estate debt & 1031 capital deployment volume",
        "click_to_conversion_rate": 0.050,
        "ltv_bounty_equivalent_usd": 100.00,
    },
    "lendkey": {
        "partnership_model": "USAGE_API_REFERRAL",
        "cpa_bounty_usd": 200.00,
        "cpl_lead_bounty_usd": 0.0,
        "recurring_revshare_pct": 0.0,
        "recurring_horizon_months": 12,
        "usage_referral_basis": "Credit union & community bank network loan origination referral",
        "click_to_conversion_rate": 0.048,
        "ltv_bounty_equivalent_usd": 200.00,
    },
}


def resolve_partnership_model_spec(partner_key: str, partner_obj: Optional[Any] = None) -> Dict[str, Any]:
    """
    Resolves the structured partnership model specification (RECURRING_SAAS_REVSHARE,
    CPA_BOUNTY, QUALIFIED_LEAD_CPL, HYBRID_CPA_REVSHARE, or USAGE_API_REFERRAL) for any
    partner key or AffiliatePartner instance.
    Zero em-dashes. Zero en-dashes.
    """
    pk = str(partner_key or getattr(partner_obj, "key", "") or "").strip().lower()
    if pk in PARTNER_PARTNERSHIP_MODEL_SPECS:
        spec = dict(PARTNER_PARTNERSHIP_MODEL_SPECS[pk])
        spec["partner_key"] = pk
        return spec

    comm_raw = str(getattr(partner_obj, "commission_est", "") or "").lower()
    bounty_raw = str(getattr(partner_obj, "bounty_est", "") or "").lower()
    combined = f"{pk} {comm_raw} {bounty_raw}"
    if "sqo" in combined or ("+" in combined and ("recurring" in combined or "onboarded" in combined or "trial" in combined)):
        model = "HYBRID_CPA_REVSHARE"
        conv_rate = 0.045
    elif "recurring" in combined or "revshare" in combined:
        model = "RECURRING_SAAS_REVSHARE"
        conv_rate = 0.046
    elif any(k in combined for k in ("lead", "quote", "cpl", "demo", "contact")):
        model = "QUALIFIED_LEAD_CPL"
        conv_rate = 0.072
    elif any(k in combined for k in ("api", "volume", "usage", "interchange", "event contract")):
        model = "USAGE_API_REFERRAL"
        conv_rate = 0.055
    else:
        model = "CPA_BOUNTY"
        conv_rate = 0.038

    return {
        "partner_key": pk,
        "partnership_model": model,
        "cpa_bounty_usd": 120.0,
        "cpl_lead_bounty_usd": 120.0 if model == "QUALIFIED_LEAD_CPL" else 0.0,
        "recurring_revshare_pct": 20.0 if model in ("RECURRING_SAAS_REVSHARE", "HYBRID_CPA_REVSHARE") else 0.0,
        "recurring_horizon_months": 12 if model in ("RECURRING_SAAS_REVSHARE", "HYBRID_CPA_REVSHARE") else 0,
        "usage_referral_basis": "Metered API or transaction volume" if model == "USAGE_API_REFERRAL" else "",
        "click_to_conversion_rate": conv_rate,
        "ltv_bounty_equivalent_usd": 150.0,
    }


def score_partnership_model_intent_fit(
    partnership_model: str,
    commercial_intent: str,
    vertical_family: str,
    query: str = "",
    page_archetype: str = "",
) -> float:
    """
    Computes a deterministic intent-fit multiplier (1.00 to 1.45) scoring how well a
    partnership model matches the page's audience intent and vertical family.
    Zero em-dashes. Zero en-dashes.
    """
    model = (partnership_model or "CPA_BOUNTY").strip().upper()
    intent = (commercial_intent or "").strip().lower()
    vert = (vertical_family or "").strip().lower()
    q_low = (query or "").strip().lower()

    mult = 1.0
    if model == "HYBRID_CPA_REVSHARE":
        if vert in (
            "section_179_equipment_capex",
            "s_corp_payroll_reasonable_comp",
            "workers_comp_labor_burden",
            "rd_section_174_bookkeeping",
            "b2b_cyber_compliance",
            "surety_bond_compliance",
            "construction_contractor_finance",
            "tariff_customs_freight_trade",
            "commercial_working_capital_factoring",
        ):
            mult = 1.32
        else:
            mult = 1.18
    elif model == "QUALIFIED_LEAD_CPL":
        if vert in (
            "1031_like_kind_exchange",
            "surety_bond_compliance",
            "commercial_solar_energy",
            "medical_practice_capex",
            "commercial_working_capital_factoring",
            "b2b_cyber_compliance",
        ) or any(k in q_low for k in ("quote", "rates", "compare", "exchange", "bond", "demo", "install")):
            mult = 1.35
        elif intent == "comparative_evaluation_matrix":
            mult = 1.25
        else:
            mult = 1.12
    elif model == "RECURRING_SAAS_REVSHARE":
        if vert in (
            "crypto_digital_asset_tax",
            "prediction_market_tax_1256",
            "rd_section_174_bookkeeping",
            "saas_unit_economics_spend",
        ) or any(k in q_low for k in ("software", "automation", "import", "8949", "1099-da", "recurring")):
            mult = 1.34
        else:
            mult = 1.15
    elif model == "USAGE_API_REFERRAL":
        if vert in (
            "prediction_market_event_contracts",
            "payment_processing_api_usage",
            "sales_tax_1099_nexus",
            "treasury_cash_runway",
        ) or any(k in q_low for k in ("kalshi", "odds", "kelly", "arbitrage", "interchange", "api", "processing", "tbill", "yield")):
            mult = 1.36
        else:
            mult = 1.10
    elif model == "CPA_BOUNTY":
        if vert in (
            "student_loan_refinancing",
            "treasury_cash_runway",
            "saas_unit_economics_spend",
            "federal_state_tax_brackets",
        ):
            mult = 1.26
        else:
            mult = 1.15
    return round(mult, 4)


@dataclass
class AffiliatePartner:
    """
    Unified Affiliate Partner Schema.
    Represents an authorized affiliate monetization partner across pseofactory properties.
    """
    key: str
    name: str
    category: str
    property_id: str
    status: str
    env_var: str
    default_url: str
    badge: str
    commission_est: str
    bounty_est: str
    network: str
    description: str
    target_tools: List[str]
    supported_params: List[str]
    cta_text: str = ""
    partnership_model: str = ""

    def __post_init__(self) -> None:
        if not self.partnership_model or not str(self.partnership_model).strip():
            self.partnership_model = str(
                resolve_partnership_model_spec(self.key, self).get("partnership_model") or "CPA_BOUNTY"
            )

    @property
    def url(self) -> str:
        return resolve_partner_url(self)

    @property
    def estimated_bounty(self) -> str:
        return self.bounty_est

    def __getitem__(self, item: str) -> Any:
        if not isinstance(item, str):
            raise KeyError(item)
        if item == "url":
            return self.url
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "url":
            return self.url
        return getattr(self, item, default)

    def __contains__(self, item: Any) -> bool:
        if not isinstance(item, str):
            return False
        if item == "url":
            return True
        return hasattr(self, item)

    def keys(self) -> List[str]:
        return list(asdict(self).keys()) + ["url"]

    def values(self) -> List[Any]:
        return [getattr(self, k) if k != "url" else self.url for k in self.keys()]

    def items(self) -> List[Tuple[str, Any]]:
        return [(k, self[k]) for k in self.keys()]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ProfitHelm Disclosures & Monetization Registry
# ---------------------------------------------------------------------------

PROFITHELM_DISCLOSURES: Dict[str, str] = {
    "ftc_disclosure": (
        "ProfitHelm is an independent financial research publisher. We may earn a commission "
        "when you register or subscribe through approved affiliate links on this site (including Xendoo, Ramp, "
        "Mercury, Rippling, Gusto, CoinLedger, Koinly, Kalshi, E-file.com, ezTaxReturn.com, FreeTaxUSA, WalletHub, "
        "and LawDepot) at no additional cost to you. Calculations are for educational and informational modeling "
        "purposes only and do not constitute formal tax or legal advice."
    ),
}


def get_contextual_ftc_disclosure(
    property_id: str,
    slug: str = "",
    partner_name: str = "",
) -> str:
    """
    Returns a vertical-matched, 16 CFR Part 255 compliant FTC disclosure tailored to the page vertical
    so users on 1031 exchange, Section 179 equipment, SaaS runway, or crypto tax pages see accurate
    contextual partner disclosures rather than mismatched vertical names.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    prop = (property_id or "profithelm").strip().lower()
    if prop == "prexvo":
        return PREXVO_DISCLOSURES.get("ftc_disclosure", "")
    if prop == "gainhelm":
        return GAINHELM_DISCLOSURES.get("ftc_disclosure", "")
    if prop == "lienbond":
        return LIENBOND_DISCLOSURES.get("ftc_disclosure", "")
    s_lower = (slug or "").strip().lower()
    if any(k in s_lower for k in ("1031", "like-kind", "exchange", "real-estate")):
        vertical_partners = "LawDepot, Xendoo, Mercury, WalletHub, and approved real estate legal, tax, or treasury partners"
    elif any(k in s_lower for k in ("179", "equipment", "macrs", "depreciation", "vehicle", "truck", "suv", "lease")):
        vertical_partners = "Xendoo, Ramp, Mercury, Rippling, LawDepot, and approved Section 179 accounting or corporate finance partners"
    elif any(k in s_lower for k in ("saas", "runway", "burn", "s-corp", "payroll", "174", "workers-comp", "factoring", "tariff", "surety")):
        vertical_partners = "Mercury, Ramp, Rippling, Gusto, Xendoo, WalletHub, LawDepot, and approved commercial treasury or payroll partners"
    elif any(k in s_lower for k in ("treasury", "tbill", "hysa", "yield", "qsbs", "1202")):
        vertical_partners = "Mercury, Ramp, Kalshi, Xendoo, WalletHub, and approved institutional yield or treasury partners"
    elif any(k in s_lower for k in ("crypto", "8949", "1099-da", "prediction", "1256", "kalshi", "polymarket")):
        vertical_partners = "CoinLedger, Koinly, Kalshi, E-file.com, ezTaxReturn.com, FreeTaxUSA, and approved digital asset or tax reporting partners"
    elif any(k in s_lower for k in ("tax-bracket", "tax bracket", "irs-2027", "ca-tax", "capital-gains", "tcja")):
        vertical_partners = "E-file.com, ezTaxReturn.com, FreeTaxUSA, CoinLedger, Koinly, WalletHub, and approved tax filing partners"
    elif partner_name:
        vertical_partners = f"{partner_name} and approved tax or financial research partners (including Xendoo, Ramp, Mercury, CoinLedger, and Koinly)"
    else:
        return PROFITHELM_DISCLOSURES["ftc_disclosure"]
    return (
        f"ProfitHelm is an independent financial research publisher. We may earn a commission "
        f"when you register or subscribe through approved affiliate links on this page ({vertical_partners}) "
        f"at no additional cost to you. Calculations are for educational and informational modeling purposes "
        f"only and do not constitute formal tax or legal advice."
    )


PROFITHELM_AFFILIATES: Dict[str, AffiliatePartner] = {
    # 13 Live Approved ProfitHelm Affiliate Partners
    "coinledger": AffiliatePartner(
        key="coinledger",
        name="CoinLedger Crypto Tax",
        category="Digital Assets",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_COINLEDGER_URL",
        default_url="https://coinledger.io/?fpr=arif-554004",
        badge="Recommended for Digital Assets",
        commission_est="25% recurring ($35-$90/sale)",
        bounty_est="$35-$90",
        network="FirstPromoter",
        description="Automated import for 500+ exchanges, DeFi protocols, and NFT marketplaces to generate IRS Form 8949.",
        target_tools=[
            "crypto-tax-calculator",
            "crypto-tax-calculator-scenario-comparison-model",
            "crypto-tax-form-1099-da-mandatory-reporting",
            "prediction-market-tax",
            "irs-capital-gains-statutory-tax",
            "tcja-sunset-capital-gains",
            "tcja-sunset-capital-gains-scenario-comparison-model",
        ],
        supported_params=["fpr", "ph_tier"],
        cta_text="Calculate & Export Crypto Taxes with CoinLedger",
    ),
    "koinly": AffiliatePartner(
        key="koinly",
        name="Koinly Crypto Tax Software",
        category="Digital Assets",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_KOINLY_URL",
        default_url="https://koinly.io/?via=F0D55B86&utm_source=affiliate",
        badge="Multi-Country Support",
        commission_est="20% one-time first purchase",
        bounty_est="$10-$55",
        network="Koinly Native Affiliate",
        description="Track cryptocurrency portfolios and generate country-specific IRS Form 8949 and Schedule D tax reports in minutes.",
        target_tools=[
            "crypto-tax-calculator",
            "crypto-tax-calculator-scenario-comparison-model",
            "crypto-tax-form-1099-da-mandatory-reporting",
            "prediction-market-tax",
            "tcja-sunset-capital-gains",
        ],
        supported_params=["via", "utm_source", "ph_tier"],
        cta_text="Track Crypto Portfolios with Koinly",
        partnership_model="CPA_BOUNTY",
    ),
    "mercury": AffiliatePartner(
        key="mercury",
        name="Mercury Startup Banking",
        category="Business Banking",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_MERCURY_URL",
        default_url="https://mercury.com/r/profithelm-llc",
        badge="Built for High-Growth Startups",
        commission_est="$250/funded account",
        bounty_est="$250 flat",
        network="In-House Direct",
        description="FDIC-insured business checking, treasury yield, and automated runway management for founders.",
        target_tools=[
            "saas-runway-calculator",
            "saas-burn-multiple-benchmarks-2026",
            "treasury-yield-calculator",
            "r-and-d-tax-credit-section-174-amortization-calculator",
            "s-corp-reasonable-salary-tax-calculator",
            "invoice-factoring-vs-business-line-of-credit-calculator",
            "qsbs-section-1202-tax-calculator",
            "qsbs-83b-tax-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Apply for Mercury Startup Banking",
    ),
    "ramp": AffiliatePartner(
        key="ramp",
        name="Ramp Corporate Card & Spend Management",
        category="Corporate Finance",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_RAMP_URL",
        default_url="https://join.ramp.com/c/7932737/3981015/51436",
        badge="Corporate Card & Spend Control",
        commission_est="$100-$4,000 Closed Won / $50-$2,000 SQL",
        bounty_est="$250 flat",
        network="Impact.com",
        description="Corporate cards with automated expense categorization, bill pay, and accounting sync for startups and SMBs. Approved on Impact.com (Account 7932737, Campaign #51436, Ad #3981015).",
        target_tools=[
            "saas-runway-calculator",
            "saas-burn-multiple-benchmarks-2026",
            "section-179-calculator",
            "equipment-lease-vs-buy-section-179-calculator",
            "r-and-d-tax-credit-section-174-amortization-calculator",
            "section-301-tariff-landed-cost-calculator",
            "invoice-factoring-vs-business-line-of-credit-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Compare Ramp Corporate Cards",
    ),
    "gusto": AffiliatePartner(
        key="gusto",
        name="Gusto Payroll, Benefits & HR Platform",
        category="Corporate Finance",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_GUSTO_URL",
        default_url="https://gusto.pxf.io/c/7932737/1226287/15154",
        badge="Automated S-Corp & Team Payroll",
        commission_est="$200-$300/sale",
        bounty_est="$200-$300",
        network="Impact.com",
        description="Automated small business and S-Corp payroll tax filing, W-2 and 1099 compliance, benefits administration, and same-day direct deposit.",
        target_tools=[
            "saas-runway-calculator",
            "s-corp-reasonable-salary-tax-calculator",
            "workers-comp-and-payroll-burden-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Automate S-Corp & Team Payroll with Gusto",
    ),
    "rippling": AffiliatePartner(
        key="rippling",
        name="Rippling Unified Workforce Platform",
        category="Corporate Finance",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_RIPPLING_URL",
        default_url="https://try.rippling.com/mcfo1m09qiwt",
        badge="Global Workforce Management",
        commission_est="Up to $1600",
        bounty_est="Up to $1600",
        network="PartnerStack",
        description="Unified HR, IT, and payroll infrastructure for scaling tech companies and distributed teams.",
        target_tools=[
            "saas-runway-calculator",
            "saas-burn-multiple-benchmarks-2026",
            "s-corp-reasonable-salary-tax-calculator",
            "workers-comp-and-payroll-burden-calculator",
            "r-and-d-tax-credit-section-174-amortization-calculator",
            "section-301-tariff-landed-cost-calculator",
            "contractor-surety-bond-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Schedule Rippling Demo",
    ),
    "xendoo": AffiliatePartner(
        key="xendoo",
        name="Xendoo Online Bookkeeping & CPA Tax Advisory",
        category="Corporate Tax & Bookkeeping",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_XENDOO_URL",
        default_url="https://xendoo.pxf.io/c/7932737/1357375/16354",
        badge="Section 179 & Business CPA Specialist",
        commission_est="$500/onboarded client",
        bounty_est="$500",
        network="Impact.com",
        description="Dedicated online bookkeeping, federal and state CPA tax advisory, and IRS Form 4562 Section 179 depreciation schedules for businesses and S-Corps.",
        target_tools=[
            "section-179-calculator",
            "section-179-vehicle-equipment-deduction",
            "equipment-lease-vs-buy-section-179-calculator",
            "equipment-lease-tax-deduction",
            "commercial-heavy-vehicle-section-179-weight-calculator",
            "medical-and-dental-equipment-section-179-roi-calculator",
            "s-corp-reasonable-salary-tax-calculator",
            "r-and-d-tax-credit-section-174-amortization-calculator",
            "section-1031-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Optimize Business Bookkeeping & Taxes with Xendoo",
    ),
    "kalshi": AffiliatePartner(
        key="kalshi",
        name="Kalshi CFTC-Regulated Event Contract Exchange",
        category="Market Arbitrage",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_KALSHI_URL",
        default_url="https://kalshi.pxf.io/c/7932737/3078072/37770",
        badge="CFTC-Regulated Event Contracts",
        commission_est="$40/qualified trade",
        bounty_est="$40-$150",
        network="Impact.com",
        description="Trade CFTC-regulated event contracts on macroeconomic indicators, Federal Reserve rate decisions, and tax policy outcomes on Kalshi.",
        target_tools=[
            "prediction-market-tax",
            "prediction-market-odds",
            "prediction-market-ev",
            "prediction-market-kelly-criterion",
            "prediction-market-implied-probability",
            "prediction-market-kalshi-fees",
            "prediction-market-arbitrage",
            "prediction-market-vig-spread",
            "prediction-market-break-even",
        ],
        supported_params=["ph_tier"],
        cta_text="Trade Regulated Event Contracts on Kalshi",
    ),
    "efile_com": AffiliatePartner(
        key="efile_com",
        name="E-file.com IRS Authorized Online Tax Filing",
        category="Tax Intelligence",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_EFILE_COM_URL",
        default_url="https://www.jdoqocy.com/click-101906407-11917161",
        badge="IRS Authorized E-File Provider",
        commission_est="30%-40% revshare",
        bounty_est="$35-$75",
        network="CJ Affiliate",
        description="IRS-authorized electronic federal and state tax return filing with guided bracket optimization, Schedule D capital gains, and itemized deduction support.",
        target_tools=[
            "irs-2027-tax-brackets",
            "tcja-sunset-bracket-calculator",
            "ca-tax-brackets-2026",
            "tcja-sunset-capital-gains",
        ],
        supported_params=["sid"],
        cta_text="E-File Your Federal & State Tax Return on E-file.com",
    ),
    "eztaxreturn_com": AffiliatePartner(
        key="eztaxreturn_com",
        name="ezTaxReturn.com Fast Federal & State Online Tax Filing",
        category="Tax Intelligence",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_EZTAXRETURN_COM_URL",
        default_url="https://www.dpbolvw.net/click-101906407-15704796",
        badge="30-Minute Guided Return",
        commission_est="15% new / 5% returning",
        bounty_est="$25-$50",
        network="CJ Affiliate",
        description="Guided step-by-step online federal and state tax preparation with audit defense options and fast direct-deposit refunds.",
        target_tools=[
            "irs-2027-tax-brackets",
            "tcja-sunset-bracket-calculator",
            "ca-tax-brackets-2026",
        ],
        supported_params=["sid"],
        cta_text="File Your Federal & State Return Fast with ezTaxReturn.com",
    ),
    "freetaxusa": AffiliatePartner(
        key="freetaxusa",
        name="FreeTaxUSA $0 Federal Online Tax Return Filing",
        category="Tax Intelligence",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_FREETAXUSA_URL",
        default_url="https://www.jdoqocy.com/click-101906407-12306188",
        badge="$0 Federal Filing + Schedule D/C",
        commission_est="10%-20% revshare",
        bounty_est="$20-$45",
        network="CJ Affiliate",
        description="IRS-authorized $0 federal tax filing covering investments, capital gains (Form 8949 / Schedule D), rental real estate (Schedule E), and small business Schedule C.",
        target_tools=[
            "irs-2027-tax-brackets",
            "tcja-sunset-bracket-calculator",
            "ca-tax-brackets-2026",
            "tcja-sunset-capital-gains",
            "crypto-tax-calculator",
        ],
        supported_params=["sid"],
        cta_text="File Federal Taxes Free ($0 Fed) with FreeTaxUSA",
    ),
    "wallethub": AffiliatePartner(
        key="wallethub",
        name="WalletHub Credit Score, Business Credit & Rate Comparison",
        category="Credit & Capital Comparison",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_WALLETHUB_URL",
        default_url="https://www.jdoqocy.com/click-101906407-16952385",
        badge="Daily Credit & Yield Comparison",
        commission_est="$50 CPA",
        bounty_est="$50",
        network="CJ Affiliate",
        description="Compare business credit cards, high-yield deposit accounts, commercial financing rates, and daily credit underwriting tiers on WalletHub.",
        target_tools=[
            "treasury-yield-calculator",
            "invoice-factoring-vs-business-line-of-credit-calculator",
            "contractor-surety-bond-cost-calculator",
            "equipment-lease-vs-buy-section-179-calculator",
            "tcja-sunset-capital-gains",
        ],
        supported_params=["sid"],
        cta_text="Compare Credit Tiers & Monitor Scores on WalletHub",
    ),
    "lawdepot": AffiliatePartner(
        key="lawdepot",
        name="LawDepot Commercial Lease, LLC Operating & Holding Contracts",
        category="Entity & Commercial Legal Documents",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_LAWDEPOT_URL",
        default_url="https://www.jdoqocy.com/click-101906407-16985242",
        badge="State-Specific Commercial Templates",
        commission_est="30% revshare ($45-$85)",
        bounty_est="$45-$85",
        network="CJ Affiliate",
        description="Generate state-specific LLC operating agreements, commercial real estate holding contracts, equipment lease agreements, and independent contractor templates at LawDepot.",
        target_tools=[
            "section-1031-calculator",
            "section-1031-calculator-scenario-comparison-model",
            "1031-exchange-rules-arizona",
            "equipment-lease-vs-buy-section-179-calculator",
            "s-corp-reasonable-salary-tax-calculator",
            "qsbs-section-1202-tax-calculator",
            "contractor-surety-bond-cost-calculator",
        ],
        supported_params=["sid"],
        cta_text="Generate State-Specific LLC, Lease & Holding Agreements at LawDepot",
    ),

    # Pending & Declined ProfitHelm Catalog Entries (Brand-Honest, Never Rendered as Live Paid Swaps)
    "stripe": AffiliatePartner(
        key="stripe",
        name="Stripe Commercial Payments & Billing Infrastructure",
        category="B2B Treasury / Commercial Banking",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_STRIPE_URL",
        default_url="https://stripe.com/",
        badge="Commercial Payments Infrastructure",
        commission_est="Pending direct partnership",
        bounty_est="$0",
        network="In-House Direct",
        description="Commercial payment processing, SaaS subscription billing, and financial infrastructure for startups and internet businesses.",
        target_tools=[
            "saas-runway-calculator",
            "saas-burn-multiple-benchmarks-2026",
            "qsbs-section-1202-tax-calculator",
            "qsbs-83b-tax-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Explore Stripe Billing & Payments",
    ),
    "rho": AffiliatePartner(
        key="rho",
        name="Rho Corporate Treasury & Spend Management",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_RHO_URL",
        default_url="https://www.rho.co/",
        badge="Enterprise Treasury Platform",
        commission_est="Pending direct partnership",
        bounty_est="$0",
        network="In-House Direct",
        description="Commercial banking, treasury management, corporate cards, and AP automation for middle-market and venture-backed companies.",
        target_tools=["saas-runway-calculator", "qsbs-section-1202-tax-calculator"],
        supported_params=["ph_tier"],
        cta_text="Explore Rho Corporate Treasury",
    ),
    "crest_capital": AffiliatePartner(
        key="crest_capital",
        name="Crest Capital Section 179 Equipment Financing",
        category="Equipment Financing",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_CREST_CAPITAL_URL",
        default_url="https://www.crestcapital.com/",
        badge="Equipment Financing Underwriting",
        commission_est="Pending direct partnership",
        bounty_est="$0",
        network="In-House Direct",
        description="Fixed-rate commercial equipment financing and Section 179 capital lease structures for small and mid-sized businesses.",
        target_tools=[
            "section-179-calculator",
            "section-179-vehicle-equipment-deduction",
            "equipment-lease-vs-buy-section-179-calculator",
            "equipment-lease-tax-deduction",
            "commercial-heavy-vehicle-section-179-weight-calculator",
            "medical-and-dental-equipment-section-179-roi-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Review Crest Capital Equipment Financing",
    ),
    "ipx1031": AffiliatePartner(
        key="ipx1031",
        name="IPX1031 Qualified Intermediary",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_IPX1031_URL",
        default_url="https://www.ipx1031.com/",
        badge="Qualified Intermediary Directory",
        commission_est="Pending direct agreement",
        bounty_est="$250-$750",
        network="In-House Direct",
        description="Qualified intermediary subsidiary of Fidelity National Financial facilitating IRC Section 1031 delayed, reverse, and improvement exchanges.",
        target_tools=[
            "section-1031-calculator",
            "section-1031-calculator-scenario-comparison-model",
            "1031-exchange-rules-arizona",
        ],
        supported_params=["ph_tier"],
        cta_text="Review IPX1031 Qualified Intermediary Overview",
    ),
    "turbotax": AffiliatePartner(
        key="turbotax",
        name="Intuit TurboTax Online Tax Filing",
        category="Tax Intelligence",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_TURBOTAX_URL",
        default_url="https://turbotax.intuit.com/",
        badge="Consumer Tax Filing",
        commission_est="Pending CJ approval",
        bounty_est="$0",
        network="CJ Affiliate",
        description="Online federal and state individual tax preparation software with W-2, 1099, and investment import.",
        target_tools=["irs-2027-tax-brackets", "tcja-sunset-bracket-calculator"],
        supported_params=["ph_tier"],
        cta_text="Review TurboTax Filing Options",
    ),
    "taxslayer": AffiliatePartner(
        key="taxslayer",
        name="TaxSlayer Online Tax Filing",
        category="Tax Intelligence",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_TAXSLAYER_URL",
        default_url="https://www.taxslayer.com/",
        badge="Self-Employed & Schedule C",
        commission_est="Pending CJ approval",
        bounty_est="$0",
        network="CJ Affiliate",
        description="Electronic federal and state filing with support for investment and self-employment schedules.",
        target_tools=["irs-2027-tax-brackets"],
        supported_params=["ph_tier"],
        cta_text="Review TaxSlayer Filing Options",
    ),
    "interactive_brokers": AffiliatePartner(
        key="interactive_brokers",
        name="Interactive Brokers Institutional & Margin Brokerage",
        category="Yield Arbitrage",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_IBKR_URL",
        default_url="https://www.interactivebrokers.com/",
        badge="Direct Treasury & Bond Desk",
        commission_est="Pending direct approval",
        bounty_est="$0",
        network="In-House Direct",
        description="Direct market access to U.S. Treasury bills, notes, corporate bonds, equities, and futures.",
        target_tools=["treasury-yield-calculator"],
        supported_params=["ph_tier"],
        cta_text="Review Interactive Brokers Treasury Access",
    ),
    "exeter1031": AffiliatePartner(
        key="exeter1031",
        name="Exeter 1031 Exchange Services",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_EXETER1031_URL",
        default_url="https://www.exeterco.com/",
        badge="1031 Qualified Intermediary",
        commission_est="Pending direct agreement",
        bounty_est="$0",
        network="In-House Direct",
        description="Institutional Qualified Intermediary administering forward, reverse, and build-to-suit Section 1031 exchanges.",
        target_tools=[
            "section-1031-calculator",
            "section-1031-calculator-scenario-comparison-model",
            "1031-exchange-rules-arizona",
        ],
        supported_params=["ph_tier"],
        cta_text="Review Exeter 1031 Exchange Services",
    ),
    "first_american": AffiliatePartner(
        key="first_american",
        name="First American Exchange Company",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_FIRST_AMERICAN_URL",
        default_url="https://www.firstexchange.com/",
        badge="1031 Qualified Intermediary",
        commission_est="Pending direct agreement",
        bounty_est="$0",
        network="In-House Direct",
        description="Qualified intermediary providing Section 1031 tax-deferred real estate exchange escrow and title coordination.",
        target_tools=[
            "section-1031-calculator",
            "section-1031-calculator-scenario-comparison-model",
            "1031-exchange-rules-arizona",
        ],
        supported_params=["ph_tier"],
        cta_text="Review First American Exchange Overview",
    ),
    "simply_business": AffiliatePartner(
        key="simply_business",
        name="Simply Business Commercial Insurance",
        category="Commercial Insurance & Workers Comp",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_SIMPLY_BUSINESS_URL",
        default_url="https://www.simplybusiness.com/",
        badge="Instant Multi-Carrier Quotes",
        commission_est="Pending Impact approval",
        bounty_est="$0",
        network="Impact.com",
        description="Compare commercial workers compensation, general liability, and contractor insurance quotes across top carriers.",
        target_tools=[
            "workers-comp-and-payroll-burden-calculator",
            "contractor-surety-bond-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Compare Commercial Insurance Quotes on Simply Business",
    ),
    "suretybonds_direct": AffiliatePartner(
        key="suretybonds_direct",
        name="SuretyBondsDirect.com Commercial & Contractor Surety Bonds",
        category="Commercial Surety & Bonds",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_SURETYBONDS_DIRECT_URL",
        default_url="https://www.suretybondsdirect.com/",
        badge="Commercial & License Surety Bonds",
        commission_est="Pending direct approval",
        bounty_est="$0",
        network="In-House Direct",
        description="Online underwriting for state contractor license bonds, commercial surety bonds, and performance bonds.",
        target_tools=["contractor-surety-bond-cost-calculator"],
        supported_params=["ph_tier"],
        cta_text="Review Surety Bond Quotes at SuretyBondsDirect.com",
    ),
    "next_insurance_b2b": AffiliatePartner(
        key="next_insurance_b2b",
        name="Next Insurance Commercial Coverage",
        category="Commercial Insurance & Workers Comp",
        property_id="profithelm",
        status="declined",
        env_var="AFFILIATE_NEXT_INSURANCE_B2B_URL",
        default_url="https://www.nextinsurance.com/",
        badge="Declined Application",
        commission_est="Declined on Impact",
        bounty_est="$0",
        network="Impact.com",
        description="Digital commercial insurance for workers compensation, general liability, and commercial auto.",
        target_tools=[],
        supported_params=["ph_tier"],
        cta_text="Next Insurance Overview",
    ),
    "invoice_simple": AffiliatePartner(
        key="invoice_simple",
        name="Invoice Simple Commercial Invoicing",
        category="Corporate Finance",
        property_id="profithelm",
        status="declined",
        env_var="AFFILIATE_INVOICE_SIMPLE_URL",
        default_url="https://www.invoicesimple.com/",
        badge="Declined Application",
        commission_est="Declined on Impact",
        bounty_est="$0",
        network="Impact.com",
        description="Mobile and web invoicing software for small businesses and contractors.",
        target_tools=[],
        supported_params=["ph_tier"],
        cta_text="Invoice Simple Overview",
    ),
    "national_funding_med": AffiliatePartner(
        key="national_funding_med",
        name="National Funding Commercial & Medical Equipment Financing",
        category="Equipment Financing",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_NATIONAL_FUNDING_MED_URL",
        default_url="https://www.nationalfunding.com/",
        badge="Medical & Commercial Equipment Loans",
        commission_est="Pending direct approval",
        bounty_est="$0",
        network="In-House Direct",
        description="Working capital loans and commercial equipment leasing for medical, dental, and industrial operators.",
        target_tools=[
            "medical-and-dental-equipment-section-179-roi-calculator",
            "equipment-lease-vs-buy-section-179-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Review National Funding Equipment Options",
    ),
    "otr_solutions_factoring": AffiliatePartner(
        key="otr_solutions_factoring",
        name="OTR Solutions Freight & Commercial Invoice Factoring",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_OTR_SOLUTIONS_FACTORING_URL",
        default_url="https://www.otrsolutions.com/",
        badge="Non-Recourse Freight Factoring",
        commission_est="Pending direct approval",
        bounty_est="$0",
        network="In-House Direct",
        description="Same-day invoice factoring and working capital solutions for freight carriers, brokers, and B2B operators.",
        target_tools=[
            "invoice-factoring-vs-business-line-of-credit-calculator",
            "section-301-tariff-landed-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Review OTR Solutions Factoring Terms",
    ),
    "freightos_marketplace": AffiliatePartner(
        key="freightos_marketplace",
        name="Freightos Global Freight & Customs Marketplace",
        category="Customs & Trade Finance",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_FREIGHTOS_MARKETPLACE_URL",
        default_url="https://www.freightos.com/",
        badge="Instant Ocean & Air Freight Quotes",
        commission_est="Pending direct approval",
        bounty_est="$0",
        network="In-House Direct",
        description="Compare ocean, air, and customs brokerage freight quotes across global forwarders.",
        target_tools=["section-301-tariff-landed-cost-calculator"],
        supported_params=["ph_tier"],
        cta_text="Compare Freight Quotes on Freightos",
    ),
}

# Legacy Aliases (mapped cleanly without cross-brand spoofing)
PROFITHELM_AFFILIATES["equipment_macrs"] = PROFITHELM_AFFILIATES["crest_capital"]
PROFITHELM_AFFILIATES["first_american_1031"] = PROFITHELM_AFFILIATES["first_american"]


# ---------------------------------------------------------------------------
# Prexvo Disclosures, Standing Restriction & Monetization Registry
# ---------------------------------------------------------------------------

PREXVO_STANDING_RESTRICTION: str = (
    "Strict prohibition on B2B monetization on Prexvo student loan pages. "
    "Prexvo visitors seek defensive relief from federal student debt (RAP, IBR, SAVE, PSLF) "
    "and possess zero corporate spending authority. Student loan refinance hypothesis remains "
    "conditional pending Gate 1 (written payout >= $45) and requires mandatory YMYL warning "
    "that refinancing federal loans permanently forfeits federal protections."
)

PREXVO_DISCLOSURES: Dict[str, str] = {
    "ymyl_forfeiture_disclaimer": (
        "Refinancing federal student loans permanently eliminates federal protections, "
        "including income-driven repayment (IDR), Public Service Loan Forgiveness (PSLF), "
        "federal interest subsidies, mandatory deferment, and forbearance options."
    ),
    "ftc_disclosure": (
        "Prexvo is an independent financial education and research publisher. "
        "We offer direct statutory repayment workbooks and may receive compensation from approved student loan "
        "marketplace partners (if and when active partner agreements are in force, such as Splash Financial, "
        "Credible, or LendKey) at no additional cost to you. "
        "Prexvo does not provide personalized financial, investment, or legal advice."
    ),
    "disclaimer_no_advice": (
        "Prexvo does not provide personalized financial, investment, or legal advice. "
        "All calculations, comparisons, and schedules are provided strictly for educational "
        "and informational modeling purposes pursuant to Title IV statutory formulas."
    ),
    "public_service_non_commercial_notice": (
        "Public Service Protection Notice: Commercial private lender offers are strictly suppressed "
        "on Public Service Loan Forgiveness (PSLF), statutory hardship, and federal discharge pages "
        "to protect borrower eligibility under Title IV 34 CFR Part 685."
    ),
}

PREXVO_MONETIZED_CALCULATOR_SLUGS: List[str] = [
    "student-loan-repayment-calculator",
    "rap-vs-ibr-calculator",
    "rap-payment-calculator",
    "tiered-standard-calculator",
    "paye-sunset-calculator",
    "icr-repayment-calculator",
    "parent-plus-double-consolidation",
    "grad-plus-borrowing-cap-calculator",
    "married-filing-separately-student-loan-calculator",
    "student-loan-refinance-break-even-calculator",
]

PREXVO_AFFILIATES: Dict[str, AffiliatePartner] = {
    "splash_financial": AffiliatePartner(
        key="splash_financial",
        name="Splash Financial",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending",
        env_var="AFFILIATE_SPLASH_FINANCIAL_URL",
        default_url="https://www.splashfinancial.com/",
        badge="Multi-Lender Comparison",
        commission_est="$200-$240/funded loan",
        bounty_est="$200-$240",
        network="Impact.com",
        description="Compare competing fixed and variable rate refinancing offers across multiple lenders with a single soft inquiry.",
        target_tools=list(PREXVO_MONETIZED_CALCULATOR_SLUGS),
        supported_params=[],
        cta_text="Compare Rates with Splash Financial",
    ),
    "sofi": AffiliatePartner(
        key="sofi",
        name="SoFi",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="declined",
        env_var="AFFILIATE_SOFI_URL",
        default_url="https://www.sofi.com/",
        badge="Declined Application",
        commission_est="Declined on Impact",
        bounty_est="$0",
        network="Impact.com",
        description="Zero origination fee refinancing with unemployment protection, career coaching, and member rate discounts.",
        target_tools=[],
        supported_params=[],
        cta_text="Check Rates with SoFi",
    ),
    "credible": AffiliatePartner(
        key="credible",
        name="Credible",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending",
        env_var="AFFILIATE_CREDIBLE_URL",
        default_url="https://www.credible.com/refinance-student-loans",
        badge="Prequalified Rate Engine",
        commission_est="$100-$150/lead",
        bounty_est="$100-$150",
        network="Impact.com",
        description="Multi-lender comparison engine showing prequalified rates and monthly payment projections in two minutes.",
        target_tools=list(PREXVO_MONETIZED_CALCULATOR_SLUGS),
        supported_params=[],
        cta_text="Compare Rates with Credible",
    ),
    "earnest": AffiliatePartner(
        key="earnest",
        name="Earnest",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="declined",
        env_var="AFFILIATE_EARNEST_URL",
        default_url="https://www.earnest.com/",
        badge="Declined Application",
        commission_est="Declined on Impact",
        bounty_est="$0",
        network="Impact.com",
        description="Customizable repayment terms, precision monthly payment matching, and biweekly autopay interest rate discounts.",
        target_tools=[],
        supported_params=[],
        cta_text="Check Rates with Earnest",
    ),
    "lendkey": AffiliatePartner(
        key="lendkey",
        name="LendKey",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending",
        env_var="AFFILIATE_LENDKEY_URL",
        default_url="https://www.lendkey.com/student-loan-refinancing/",
        badge="Credit Union Network",
        commission_est="$100-$150/funded loan",
        bounty_est="$100-$150",
        network="In-House Direct",
        description="Community bank and credit union network offering relationship-based student refinancing terms.",
        target_tools=list(PREXVO_MONETIZED_CALCULATOR_SLUGS),
        supported_params=[],
        cta_text="Explore Community Rates with LendKey",
    ),
}

GAINHELM_DISCLOSURES: Dict[str, str] = {
    "statutory_compliance_disclaimer": (
        "Statutory Compliance & Audit Scoping Disclaimer (Non-CPA / Non-C3PAO / Non-Legal Attestation): "
        "GainHelm provides deterministic statutory security governance, audit budget, and regulatory penalty "
        "modeling pursuant to AICPA SSAE 18 (AT-C 205), DoD 32 CFR Part 170 (CMMC 2.0), NIST SP 800-171, "
        "ISO/IEC 27006-1:2024, 45 CFR 160.404 (HIPAA), and PCI DSS v4.0.1. GainHelm is not a licensed CPA firm, "
        "Cyber-AB C3PAO, PCI SSC QSA, or legal counsel."
    ),
    "ftc_disclosure": (
        "FTC Partner Compensation Disclosure: GainHelm is an independent enterprise security governance and "
        "GRC financial research publisher. We offer direct audit readiness toolkits and may receive referral "
        "compensation when active partner agreements are in force (such as Vanta, Drata, Sprinto, Thoropass, "
        "Coalition, or Cobalt) at no additional cost to you."
    ),
    "independent_publisher_disclaimer": (
        "Independent Publisher Disclaimer: GainHelm is an independent enterprise security governance calculation "
        "publisher and is not affiliated with AICPA, the U.S. Department of Defense, Cyber-AB, HHS OCR, or PCI SSC."
    ),
}

GAINHELM_MONETIZED_CALCULATOR_SLUGS: List[str] = [
    "soc-2-audit-cost-calculator",
    "cmmc-2-0-compliance-cost-calculator",
    "nist-800-171-sprs-score-calculator",
    "iso-27001-certification-cost-calculator",
    "hipaa-violation-penalty-breach-cost-calculator",
    "pci-dss-4-0-compliance-cost-calculator",
    "fedramp-authorization-3pao-cost-calculator",
    "hitrust-csf-e1-i1-r2-certification-cost-calculator",
    "penetration-testing-scoping-cost-calculator",
    "cyber-liability-insurance-breach-exposure-calculator",
]

GAINHELM_AFFILIATES: Dict[str, AffiliatePartner] = {
    "vanta_security": AffiliatePartner(
        key="vanta_security",
        name="Vanta Automated Trust & GRC Platform",
        category="Enterprise GRC Automation",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_VANTA_SECURITY_URL",
        default_url="https://www.vanta.com/products/soc-2",
        badge="Automated SOC 2, ISO 27001 & HIPAA",
        commission_est="$300-$400/qualified demo",
        bounty_est="$350",
        network="PartnerStack",
        description="Automated continuous control monitoring across AWS, GCP, Azure, GitHub, and Okta to cut SOC 2, ISO 27001, HIPAA, and CMMC audit readiness hours by up to 82%.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Automate Audit Evidence Collection with Vanta",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "drata_compliance": AffiliatePartner(
        key="drata_compliance",
        name="Drata Continuous GRC & Audit Automation",
        category="Enterprise GRC Automation",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_DRATA_COMPLIANCE_URL",
        default_url="https://drata.com/",
        badge="Continuous NIST, CMMC & SOC 2 Controls",
        commission_est="$250-$350/qualified demo",
        bounty_est="$300",
        network="PartnerStack",
        description="Continuous control monitoring, automated NIST SP 800-171 POA&M tracking, and Audit Hub workspace for SOC 2 Type II, CMMC 2.0 Level 2, ISO 27001:2022, and PCI DSS v4.0.1.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Benchmark GRC Automation ROI with Drata",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "sprinto_compliance": AffiliatePartner(
        key="sprinto_compliance",
        name="Sprinto Cloud Security & Compliance",
        category="Enterprise GRC Automation",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_SPRINTO_COMPLIANCE_URL",
        default_url="https://sprinto.com/",
        badge="Fast-Track Cloud SaaS Audit Readiness",
        commission_est="$225/demo + 15% revshare",
        bounty_est="$225-$350",
        network="PartnerStack",
        description="Turnkey security compliance automation for B2B SaaS teams pursuing rapid SOC 2 Type I/II, ISO 27001, HIPAA, GDPR, and PCI DSS 4.0 certification.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Accelerate Multi-Framework Readiness with Sprinto",
        partnership_model="HYBRID_CPA_REVSHARE",
    ),
    "thoropass_audit": AffiliatePartner(
        key="thoropass_audit",
        name="Thoropass Integrated GRC + CPA Audit",
        category="Bundled GRC + Attestation",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_THOROPASS_AUDIT_URL",
        default_url="https://www.thoropass.com/solutions",
        badge="Bundled GRC Software + Licensed CPA/QSA Audit",
        commission_est="$300-$350/qualified demo",
        bounty_est="$325",
        network="PartnerStack",
        description="Unified compliance automation and in-house AICPA CPA, HITRUST CSF Assessor, and PCI QSA audit execution eliminating third-party auditor coordination friction.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Scope Bundled GRC + CPA Audit with Thoropass",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "coalition_cyber_insurance": AffiliatePartner(
        key="coalition_cyber_insurance",
        name="Coalition Active Cyber Liability Insurance",
        category="Cyber Liability & Breach Coverage",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_COALITION_CYBER_INSURANCE_URL",
        default_url="https://www.coalitioninc.com/cyber-insurance",
        badge="Active Cyber Risk & Breach Response",
        commission_est="$200-$300/qualified quote",
        bounty_est="$250",
        network="Impact.com",
        description="Active cyber liability insurance combining continuous external attack surface monitoring with first-party HITECH/SEC breach response, forensics, and regulatory defense coverage.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Model Active Cyber Liability Coverage with Coalition",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "cobalt_pentest": AffiliatePartner(
        key="cobalt_pentest",
        name="Cobalt Offensive Security & Pentest as a Service",
        category="Offensive Security & Penetration Testing",
        property_id="gainhelm",
        status="pending",
        env_var="AFFILIATE_COBALT_PENTEST_URL",
        default_url="https://www.cobalt.io/",
        badge="CREST & OSCP Certified PtaaS",
        commission_est="$250-$300/scoped pentest",
        bounty_est="$275",
        network="PartnerStack",
        description="On-demand CREST, OSCP, and GPEN certified Penetration Testing as a Service (PtaaS) with real-time Jira/GitHub remediation workflows and free retesting for SOC 2, PCI DSS 11.4, and ISO 27001.",
        target_tools=list(GAINHELM_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Scope Certified PtaaS Engagement with Cobalt",
        partnership_model="CPA_BOUNTY",
    ),
}


def classify_gainhelm_framework(slug: str = "", vertical: str = "") -> str:
    """
    Classifies a GainHelm calculator slug or vertical into its canonical statutory framework key
    so workpapers, disclosures, trend series, and partner copy never leak SOC 2 / CMMC / HIPAA
    text onto EU DORA, EU AI Act, SEC Form 8-K, or other specialized framework calculators.
    Zero em-dashes. Zero en-dashes.
    """
    combined = (
        f"{slug or ''} {vertical or ''}".strip().lower().replace("_", "-")
    )
    if any(k in combined for k in ("dora", "ict-third-party", "2022/2554", "2022-2554")):
        return "dora"
    if any(k in combined for k in ("eu-ai-act", "eu ai act", "2024/1689", "2024-1689", "article43", "conformity-assessment")):
        return "eu_ai_act"
    if any(k in combined for k in ("sec-cybersecurity", "8k-item-105", "item-105", "229.106", "materiality-8k", "sec-8k", "sec-cyber-disclosure")):
        return "sec_8k"
    if "gdpr" in combined:
        return "gdpr"
    if any(k in combined for k in ("ccpa", "cpra")):
        return "ccpa"
    if any(k in combined for k in ("nis2", "nis-2")):
        return "nis2"
    if any(k in combined for k in ("hipaa", "hitech")):
        return "hipaa"
    if any(k in combined for k in ("iso-27001", "iso27001", "27001")):
        return "iso_27001"
    if any(k in combined for k in ("pci-dss", "pci-", "qsa")):
        return "pci_dss"
    if "hitrust" in combined:
        return "hitrust"
    if any(k in combined for k in ("fedramp", "stateramp", "txramp")):
        return "fedramp"
    if any(k in combined for k in ("penetration-test", "pentest", "penetration")):
        return "pentest"
    if any(k in combined for k in ("cyber-liability", "cyber-insurance", "breach-exposure")):
        return "cyber_insurance"
    if any(k in combined for k in ("cmmc", "sprs", "800-171", "federal-defense-grc")):
        return "cmmc"
    return "soc2"


GAINHELM_FRAMEWORK_PROFILES: Dict[str, Dict[str, Any]] = {
    "dora": {
        "framework_key": "dora",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm DORA ICT Third-Party Risk & TLPT Compliance Workpaper Suite",
        "statutory_authority": "Regulation (EU) 2022/2554 (DORA Articles 5-30), Commission Delegated Regulation (EU) 2024/1772 & EBA/ESMA/EIOPA RTS",
        "economic_dataset": "ESA DORA Joint Technical Standards & ENISA ICT Resilience Cost Benchmarks",
        "regulator_name": "European Supervisory Authorities (EBA, ESMA, EIOPA)",
        "default_sku_slug": "dora-ict-third-party-risk-compliance-cost-calculator",
        "vertical": "dora_eu_ict_resilience",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/solutions/dora",
        "partner_rep_desk": "Vanta EU DORA & Enterprise GRC Automation Desk",
        "deliverables": [
            "JSON + CSV DORA ICT risk governance, Register of Information & Article 28 third-party matrix",
            "Threat-Led Penetration Testing (TLPT Article 26) scoping schedule & Article 19 incident classification log",
            "Statutory penalty model (Article 50/51 daily periodic fines up to 1% average daily worldwide turnover)",
            "Controller and financial entity board approval workbook for multi-year ICT vendor resilience budgets",
        ],
        "preferred_trend_ids": (
            "eu_dora_tlpt_redteam_benchmark",
            "eu_dora_ict_vendor_audit_unit_cost",
            "bls_soc_15_1212_infosec_wage",
            "iso_27006_stage2_auditor_days",
        ),
        "compliance_sentence": (
            "EU DORA Articles 26-27 Threat-Led Penetration Testing (TLPT) must be executed by accredited independent "
            "testers or qualifying internal red teams under designated Competent Authority oversight."
        ),
        "statutory_disclaimer": (
            "EU DORA Compliance Disclaimer: ICT risk, TLPT scoping, and Register of Information cost figures are "
            "deterministic computational models and do not constitute EU legal counsel, Competent Authority clearance, "
            "or a certified DORA TLPT attestation."
        ),
        "quick_unlock_heading": "Get Your DORA ICT Risk, TLPT &amp; Register of Information Worksheet",
        "quick_unlock_summary": (
            "Unlocks DORA Article 28 third-party contract checklist, TLPT scoping estimator, "
            "and board budget approval schedule."
        ),
        "quick_btn_text": "Download DORA Compliance Worksheet",
        "quote_heading_prefix": "DORA ICT Resilience &amp; Enterprise GRC Quote Intake",
        "quote_sub_template": (
            "DORA readiness budgets at or above {threshold_fmt} qualify for direct GRC automation platform quotes, "
            "TLPT / red-team scoping, and Article 28 third-party risk monitoring matching. "
            "Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": (
            "matched GRC automation, ICT resilience, penetration testing, or cyber risk partners "
            "(including Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt)"
        ),
        "quote_btn_text": "Request Matched DORA GRC Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "eu_ai_act": {
        "framework_key": "eu_ai_act",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm EU AI Act High-Risk Conformity & Article 99 Exposure Workpaper Suite",
        "statutory_authority": "Regulation (EU) 2024/1689 (EU AI Act Annex III, Articles 9-17, 43 & 99) & ISO/IEC 42001:2023",
        "economic_dataset": "European AI Office Implementing Rules & Notified Body Conformity Benchmarks",
        "regulator_name": "European AI Office and National Market Surveillance Authorities",
        "default_sku_slug": "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
        "vertical": "eu_ai_act_conformity",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/solutions/ai-governance",
        "partner_rep_desk": "Vanta AI Governance & EU AI Act Readiness Desk",
        "deliverables": [
            "JSON + CSV Annex III high-risk AI system classification & Article 11 technical documentation checklist",
            "Article 43 Notified Body vs internal Annex VI conformity assessment & Article 17 QMS cost schedule",
            "Statutory penalty model (Article 99 ceilings: EUR 35M / 7% prohibited, EUR 15M / 3% high-risk turnover)",
            "Fundamental Rights Impact Assessment (Article 27) & post-market monitoring board budget workbook",
        ],
        "preferred_trend_ids": (
            "eu_ai_act_art43_notified_body_fee",
            "eu_ai_act_art99_high_risk_cap",
            "bls_soc_15_1212_infosec_wage",
            "iso_27006_stage2_auditor_days",
        ),
        "compliance_sentence": (
            "Formal EU AI Act third-party conformity assessments under Article 43 and Annex VII require a designated "
            "EU Notified Body where mandated or where harmonised standards are not applied in full."
        ),
        "statutory_disclaimer": (
            "EU AI Act Compliance Disclaimer: High-risk conformity assessment fees, QMS scoping, and Article 99 "
            "penalty exposure figures are deterministic computational models and do not constitute EU regulatory counsel "
            "or a Notified Body EU-type examination certificate."
        ),
        "quick_unlock_heading": "Get Your EU AI Act High-Risk Conformity &amp; Annex IV Worksheet",
        "quick_unlock_summary": (
            "Unlocks Annex III system inventory checklist, Article 43 Notified Body readiness schedule, "
            "and board budget model."
        ),
        "quick_btn_text": "Download EU AI Act Worksheet",
        "quote_heading_prefix": "EU AI Act Governance &amp; Conformity Quote Intake",
        "quote_sub_template": (
            "AI governance budgets at or above {threshold_fmt} qualify for direct GRC platform fee quotes, "
            "ISO/IEC 42001 &amp; Annex IV documentation workflow matching, and adversarial testing scoping. "
            "Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": (
            "matched AI governance, GRC automation, adversarial red-teaming, or cyber risk partners "
            "(including Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt)"
        ),
        "quote_btn_text": "Request Matched AI Governance Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "sec_8k": {
        "framework_key": "sec_8k",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm SEC Form 8-K Item 1.05 & Reg S-K Item 106 Materiality Workpaper Suite",
        "statutory_authority": "17 CFR 229.106 (Reg S-K Item 106), 17 CFR 249.308 (Form 8-K Item 1.05) & SEC Release 33-11216",
        "economic_dataset": "SEC EDGAR Item 1.05 Filing Benchmarks, Legal Counsel & DFIR Retainer Surveys",
        "regulator_name": "U.S. Securities and Exchange Commission (SEC)",
        "default_sku_slug": "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator",
        "vertical": "sec_cyber_disclosure",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Vanta SEC Reg S-K Item 106 & Cyber Governance Desk",
        "deliverables": [
            "JSON + CSV 4-business-day Form 8-K Item 1.05 materiality determination & Attorney General delay log",
            "Quantitative & qualitative materiality rubric, DFIR triage SLA tracker, and disclosure committee template",
            "Reg S-K Item 106(b)-(c) annual Form 10-K board oversight & CISO governance mapping schedule",
            "External securities counsel, DFIR retainer, and cyber insurance SIR board budget model",
        ],
        "preferred_trend_ids": (
            "sec_8k_item105_counsel_dfir_retainer",
            "sec_reg_sk_106_governance_cost",
            "bls_soc_15_1212_infosec_wage",
            "iso_27006_stage2_auditor_days",
        ),
        "compliance_sentence": (
            "Formal SEC Form 8-K Item 1.05 materiality determinations and Reg S-K Item 106 disclosures require "
            "qualified securities legal counsel and executive disclosure committee sign-off."
        ),
        "statutory_disclaimer": (
            "SEC Cybersecurity Disclosure Disclaimer: Form 8-K Item 1.05 timing, materiality scoring, and counsel/DFIR "
            "cost estimates are deterministic computational models and do not constitute federal securities legal advice, "
            "an official SEC determination, or forensic incident clearance."
        ),
        "quick_unlock_heading": "Get Your SEC Form 8-K Item 1.05 &amp; Reg S-K 106 Worksheet",
        "quick_unlock_summary": (
            "Unlocks 4-business-day materiality decision matrix, Item 106 board governance checklist, "
            "and disclosure budget schedule."
        ),
        "quick_btn_text": "Download SEC 8-K Worksheet",
        "quote_heading_prefix": "SEC Cyber Disclosure &amp; Governance Quote Intake",
        "quote_sub_template": (
            "SEC cyber governance and incident readiness budgets at or above {threshold_fmt} qualify for direct "
            "GRC monitoring fee quotes, disclosure readiness automation, and DFIR / cyber insurance matching. "
            "Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": (
            "matched GRC automation, cyber risk, penetration testing, or disclosure readiness partners "
            "(including Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt)"
        ),
        "quote_btn_text": "Request Matched SEC Readiness Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "gdpr": {
        "framework_key": "gdpr",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm GDPR Article 83 Privacy Governance & DPIA Workpaper Suite",
        "statutory_authority": "Regulation (EU) 2016/679 (GDPR Articles 30, 32, 35 & 83) & EDPB Fining Guidelines 04/2022",
        "economic_dataset": "EDPB Supervisory Enforcement Benchmarks & EU DPO Cost Surveys",
        "regulator_name": "European Data Protection Board (EDPB) & National DPAs",
        "default_sku_slug": "gdpr-data-privacy-compliance-and-article-83-fine-exposure-calculator",
        "vertical": "eu_gdpr_privacy",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/products/gdpr",
        "partner_rep_desk": "Vanta GDPR & EU Privacy Automation Desk",
        "deliverables": [
            "JSON + CSV Article 30 ROPA, Article 35 DPIA, and Standard Contractual Clauses scoping checklist",
            "Article 83 Tier 1 (EUR 10M / 2%) & Tier 2 (EUR 20M / 4%) supervisory exposure matrix",
            "72-hour Article 33 personal data breach notification runbook and DPO cost schedule",
            "Board privacy governance budget approval workbook",
        ],
        "preferred_trend_ids": ("iso_27006_stage2_auditor_days", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal EU GDPR compliance determinations and supervisory proceedings are governed by national Data Protection "
            "Authorities and EDPB consistency mechanisms."
        ),
        "statutory_disclaimer": (
            "EU GDPR Compliance Disclaimer: DPIA scoping and Article 83 administrative fine exposure models are "
            "deterministic computational estimates and do not constitute EU privacy legal counsel."
        ),
        "quick_unlock_heading": "Get Your GDPR ROPA, DPIA &amp; Article 83 Worksheet",
        "quick_unlock_summary": "Unlocks Article 30 ROPA checklist, 72-hour breach log, and privacy governance budget model.",
        "quick_btn_text": "Download GDPR Privacy Worksheet",
        "quote_heading_prefix": "GDPR Privacy Governance &amp; GRC Quote Intake",
        "quote_sub_template": (
            "GDPR privacy budgets at or above {threshold_fmt} qualify for direct GRC privacy automation quotes "
            "and cross-border transfer scoping. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched GRC automation, privacy governance, and security partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched GDPR GRC Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "ccpa": {
        "framework_key": "ccpa",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm CCPA/CPRA Privacy Compliance & Breach Liability Workpaper Suite",
        "statutory_authority": "Cal. Civ. Code 1798.100 et seq. (CCPA/CPRA) & 11 CCR 7000 et seq.",
        "economic_dataset": "CPPA Enforcement Benchmarks & California Privacy Compliance Surveys",
        "regulator_name": "California Privacy Protection Agency (CPPA) & CA Attorney General",
        "default_sku_slug": "ccpa-cpra-california-privacy-compliance-and-breach-liability-calculator",
        "vertical": "ccpa_cpra_privacy",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Vanta CCPA/CPRA & Consumer Privacy Automation Desk",
        "deliverables": [
            "JSON + CSV DSAR fulfillment SLA, opt-out preference signal & vendor DPA checklist",
            "Statutory administrative fine ($2,663-$7,988/violation) & breach statutory damages ($100-$750/consumer) schedule",
            "CPPA annual cybersecurity audit and risk assessment scoping log",
            "Executive privacy operations budget approval workbook",
        ],
        "preferred_trend_ids": ("bls_soc_15_1212_infosec_wage", "iso_27006_stage2_auditor_days"),
        "compliance_sentence": (
            "Formal CCPA/CPRA cybersecurity audit and risk assessment obligations are subject to CPPA regulations "
            "and qualified privacy legal review."
        ),
        "statutory_disclaimer": (
            "CCPA/CPRA Compliance Disclaimer: Consumer privacy compliance and statutory breach exposure estimates are "
            "deterministic computational models and do not constitute California legal advice."
        ),
        "quick_unlock_heading": "Get Your CCPA/CPRA Privacy &amp; Breach Scoping Worksheet",
        "quick_unlock_summary": "Unlocks DSAR workflow checklist, statutory penalty estimator, and privacy budget model.",
        "quick_btn_text": "Download CCPA/CPRA Worksheet",
        "quote_heading_prefix": "CCPA/CPRA Privacy &amp; GRC Quote Intake",
        "quote_sub_template": (
            "Privacy readiness budgets at or above {threshold_fmt} qualify for direct GRC automation quotes "
            "and cybersecurity audit matching. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched GRC automation, privacy, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched Privacy Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "nis2": {
        "framework_key": "nis2",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm EU NIS2 Directive Article 21 Compliance Workpaper Suite",
        "statutory_authority": "Directive (EU) 2022/2555 (NIS2 Articles 20, 21, 23 & 34) & National Member State Transpositions",
        "economic_dataset": "ENISA NIS2 Investment Surveys & National CSIRT Compliance Benchmarks",
        "regulator_name": "ENISA & EU Member State Competent Authorities",
        "default_sku_slug": "nis2-directive-cybersecurity-compliance-and-fine-calculator",
        "vertical": "eu_nis2_resilience",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Vanta EU NIS2 & Critical Infrastructure GRC Desk",
        "deliverables": [
            "JSON + CSV Article 21 10-measure security baseline & Article 23 24h/72h CSIRT reporting runbook",
            "Essential vs Important entity Article 34 penalty exposure model (EUR 10M / 2% or EUR 7M / 1.4%)",
            "Supply-chain risk & Article 20 management body accountability checklist",
            "Board cybersecurity budget approval workbook",
        ],
        "preferred_trend_ids": ("iso_27006_stage2_auditor_days", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "EU NIS2 supervisory reviews and incident reporting obligations are enforced by Member State Competent "
            "Authorities and national CSIRTs."
        ),
        "statutory_disclaimer": (
            "EU NIS2 Compliance Disclaimer: Article 21 control implementation costs and Article 34 penalty exposure figures "
            "are deterministic computational models and do not constitute EU Member State legal advice."
        ),
        "quick_unlock_heading": "Get Your EU NIS2 Article 21 Compliance Worksheet",
        "quick_unlock_summary": "Unlocks Article 21 control matrix, 24h/72h CSIRT reporting log, and budget model.",
        "quick_btn_text": "Download NIS2 Compliance Worksheet",
        "quote_heading_prefix": "EU NIS2 Governance &amp; GRC Quote Intake",
        "quote_sub_template": (
            "NIS2 readiness budgets at or above {threshold_fmt} qualify for direct GRC automation quotes "
            "and supply-chain security scoping. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched GRC automation, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched NIS2 Quote",
        "forbidden_leak_tokens": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
    },
    "iso_27001": {
        "framework_key": "iso_27001",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm ISO/IEC 27001:2022 Certification & Stage 1/2 Audit Workpaper Kit",
        "statutory_authority": "ISO/IEC 27001:2022, ISO/IEC 27006-1:2024 & IAF MD 5 Auditor-Day Rules",
        "economic_dataset": "IAF MD 5 Certification Body Audit-Day Tables & ANAB Accredited Registrar Surveys",
        "regulator_name": "ANAB / UKAS Accredited ISO/IEC 27001 Certification Bodies",
        "default_sku_slug": "iso-27001-certification-cost-calculator",
        "vertical": "iso27001_isms",
        "primary_partner_key": "thoropass_audit",
        "vanta_url": "https://www.vanta.com/products/iso-27001",
        "partner_rep_desk": "Thoropass & Vanta ISO/IEC 27001:2022 ISMS Desk",
        "deliverables": [
            "JSON + CSV ISO/IEC 27001:2022 Annex A 93-control Statement of Applicability (SoA) template",
            "ISO/IEC 27006-1:2024 Stage 1, Stage 2, and Year 2/3 surveillance audit-day calculator schedule",
            "ISMS internal audit & management review board sign-off workbook",
            "Risk treatment plan (RTP) and registrar quote comparison log",
        ],
        "preferred_trend_ids": ("iso_27006_stage2_auditor_days", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal ISO/IEC 27001:2022 certifications require Stage 1 and Stage 2 conformity audits by an accredited "
            "Certification Body (such as ANAB or UKAS)."
        ),
        "statutory_disclaimer": (
            "ISO 27001 Compliance Disclaimer: Stage 1/Stage 2 auditor-day and surveillance cost figures are "
            "deterministic computational models and do not constitute an accredited Certification Body audit certificate."
        ),
        "quick_unlock_heading": "Get Your ISO/IEC 27001:2022 SoA &amp; Audit-Day Worksheet",
        "quick_unlock_summary": "Unlocks Annex A 93-control SoA checklist, Stage 1/Stage 2 auditor-day estimator, and ISMS budget model.",
        "quick_btn_text": "Download ISO 27001 Worksheet",
        "quote_heading_prefix": "ISO/IEC 27001:2022 ISMS &amp; GRC Quote Intake",
        "quote_sub_template": (
            "ISO 27001 certification budgets at or above {threshold_fmt} qualify for direct GRC platform fee quotes "
            "and accredited Certification Body scheduling. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched ISMS GRC automation, certification body, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched ISO 27001 Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "hipaa", "aicpa"),
    },
    "hipaa": {
        "framework_key": "hipaa",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm HIPAA Penalty Tier, Security Rule & Breach Cost Workpaper Kit",
        "statutory_authority": "45 CFR 160.404 (HIPAA CMP Tiers 1-4), 45 CFR Part 164 & 45 CFR 102.3 Inflation Index",
        "economic_dataset": "HHS OCR Civil Monetary Penalty Schedules & Healthcare Breach Cost Benchmarks",
        "regulator_name": "HHS Office for Civil Rights (OCR)",
        "default_sku_slug": "hipaa-violation-penalty-breach-cost-calculator",
        "vertical": "hipaa_healthcare_security",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/products/hipaa",
        "partner_rep_desk": "Vanta HIPAA & Healthcare Security Compliance Desk",
        "deliverables": [
            "JSON + CSV 45 CFR 164.308-316 Administrative, Physical & Technical Safeguards readiness matrix",
            "HHS OCR Tier 1-4 statutory CMP inflation-indexed exposure & corrective action plan (CAP) log",
            "60-day HIPAA Breach Notification Rule triage & Business Associate Agreement (BAA) checklist",
            "Healthcare compliance board budget approval workbook",
        ],
        "preferred_trend_ids": ("hhs_hipaa_tier4_annual_cap", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal HIPAA Security Rule compliance determinations and enforcement resolutions are administered by the "
            "HHS Office for Civil Rights (OCR) and qualified healthcare privacy counsel."
        ),
        "statutory_disclaimer": (
            "HIPAA Compliance Disclaimer: Statutory CMP tier exposure and breach remediation figures are deterministic "
            "computational models and do not constitute legal advice or an HHS OCR compliance clearance."
        ),
        "quick_unlock_heading": "Get Your HIPAA Safeguards, SRA &amp; Penalty Worksheet",
        "quick_unlock_summary": "Unlocks HIPAA Security Risk Analysis (SRA) checklist, BAA inventory, and remediation budget schedule.",
        "quick_btn_text": "Download HIPAA Compliance Worksheet",
        "quote_heading_prefix": "HIPAA Security &amp; GRC Readiness Quote Intake",
        "quote_sub_template": (
            "HIPAA compliance budgets at or above {threshold_fmt} qualify for direct GRC platform fee quotes "
            "and Healthcare Security Risk Analysis matching. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched healthcare GRC automation, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched HIPAA Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "aicpa", "soc 2", "soc2"),
    },
    "pci_dss": {
        "framework_key": "pci_dss",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm PCI DSS 4.0.1 ROC / SAQ & QSA Audit Workpaper Kit",
        "statutory_authority": "PCI Security Standards Council PCI DSS v4.0.1 (Requirements 1-12, Req 11.4 & 12.10)",
        "economic_dataset": "PCI SSC QSA Assessment Benchmarks & Card-Brand Acquirer Fee Schedules",
        "regulator_name": "PCI Security Standards Council (PCI SSC) & Qualified Security Assessors (QSA)",
        "default_sku_slug": "pci-dss-4-0-compliance-cost-calculator",
        "vertical": "pci_dss_payments",
        "primary_partner_key": "cobalt_pentest",
        "vanta_url": "https://www.vanta.com/products/pci-dss",
        "partner_rep_desk": "Cobalt & Vanta PCI DSS v4.0.1 Readiness Desk",
        "deliverables": [
            "JSON + CSV PCI DSS v4.0.1 Requirements 1-12 scoping & CDE network segmentation checklist",
            "QSA Report on Compliance (ROC) vs SAQ A/D validation cost & ASV quarterly scan schedule",
            "Requirement 11.3/11.4 segmentation & penetration testing scoping workbook",
            "Card-brand non-compliance fine avoidance & payment compliance budget workbook",
        ],
        "preferred_trend_ids": ("pci_dss_qsa_roc_benchmark", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal PCI DSS 4.0.1 Level 1 Report on Compliance (ROC) validations require an independent PCI SSC "
            "Qualified Security Assessor (QSA) and quarterly Approved Scanning Vendor (ASV) scans."
        ),
        "statutory_disclaimer": (
            "PCI DSS Compliance Disclaimer: ROC, SAQ, and segmentation cost figures are deterministic computational "
            "models and do not constitute an official QSA Attestation of Compliance (AOC)."
        ),
        "quick_unlock_heading": "Get Your PCI DSS 4.0.1 CDE Scope &amp; QSA Worksheet",
        "quick_unlock_summary": "Unlocks Requirements 1-12 control checklist, CDE segmentation estimator, and QSA budget schedule.",
        "quick_btn_text": "Download PCI DSS 4.0.1 Worksheet",
        "quote_heading_prefix": "PCI DSS 4.0.1 &amp; QSA Readiness Quote Intake",
        "quote_sub_template": (
            "PCI DSS readiness budgets at or above {threshold_fmt} qualify for direct GRC automation quotes, "
            "QSA scoping, and Requirement 11.4 penetration testing matching. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched PCI GRC automation, QSA audit, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched PCI DSS Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "hipaa"),
    },
    "hitrust": {
        "framework_key": "hitrust",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm HITRUST CSF e1 / i1 / r2 Authorized Assessor Workpaper Kit",
        "statutory_authority": "HITRUST CSF v11 (e1, i1, and r2 Validated Assessment & MyCSF Licensing Framework)",
        "economic_dataset": "HITRUST Authorized External Assessor Pricing & MyCSF Subscription Benchmarks",
        "regulator_name": "HITRUST Alliance & Authorized External Assessors",
        "default_sku_slug": "hitrust-csf-e1-i1-r2-certification-cost-calculator",
        "vertical": "hitrust_csf_assurance",
        "primary_partner_key": "thoropass_audit",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Thoropass & Vanta HITRUST CSF e1/i1/r2 Assessment Desk",
        "deliverables": [
            "JSON + CSV HITRUST CSF v11 e1/i1/r2 control inheritance & MyCSF domain scoping schedule",
            "Authorized External Assessor fieldwork, QA review fee, and interim assessment budget model",
            "Readiness gap remediation hours & policy maturity scoring tracker",
            "Enterprise customer security assurance board budget workbook",
        ],
        "preferred_trend_ids": ("iso_27006_stage2_auditor_days", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal HITRUST CSF e1, i1, and r2 Validated Assessments require a HITRUST Authorized External Assessor "
            "and HITRUST Alliance MyCSF quality assurance sign-off."
        ),
        "statutory_disclaimer": (
            "HITRUST CSF Disclaimer: Assessment tier, MyCSF licensing, and assessor effort figures are deterministic "
            "computational models and do not constitute an official HITRUST Validated Report."
        ),
        "quick_unlock_heading": "Get Your HITRUST e1 / i1 / r2 Scoping &amp; Budget Worksheet",
        "quick_unlock_summary": "Unlocks e1 vs i1 vs r2 tier comparison, MyCSF licensing schedule, and assessor effort model.",
        "quick_btn_text": "Download HITRUST Worksheet",
        "quote_heading_prefix": "HITRUST CSF &amp; Enterprise GRC Quote Intake",
        "quote_sub_template": (
            "HITRUST readiness budgets at or above {threshold_fmt} qualify for direct GRC platform fee quotes "
            "and Authorized External Assessor scoping. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched GRC automation, HITRUST assessor, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched HITRUST Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "aicpa"),
    },
    "cyber_insurance": {
        "framework_key": "cyber_insurance",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm Cyber Liability Premium, SIR & Breach Exposure Workpaper Kit",
        "statutory_authority": "NAIC Cyber Insurance Market Data, State Breach Notification Statutes & IBM/Ponemon Cost Factors",
        "economic_dataset": "U.S. Cyber Insurance Rate-per-Million Underwriting & Breach Severity Benchmarks",
        "regulator_name": "Cyber Underwriting Carriers & State Insurance Departments",
        "default_sku_slug": "cyber-liability-insurance-breach-exposure-calculator",
        "vertical": "cyber_liability_underwriting",
        "primary_partner_key": "coalition_cyber_insurance",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Coalition Active Cyber Insurance & GRC Underwriting Desk",
        "deliverables": [
            "JSON + CSV cyber insurance limit sizing, retention (SIR) optimization & MFA/EDR discount matrix",
            "First-party DFIR, business interruption & third-party regulatory defense coverage schedule",
            "Underwriting security questionnaire readiness checklist (MFA, immutable backups, PAM)",
            "CFO risk transfer vs retention board budget workbook",
        ],
        "preferred_trend_ids": ("bls_soc_15_1212_infosec_wage", "iso_27006_stage2_auditor_days"),
        "compliance_sentence": (
            "Formal cyber liability policy terms, limits, and active risk credits require underwriting binding with a "
            "licensed surplus lines or admitted cyber insurance carrier."
        ),
        "statutory_disclaimer": (
            "Cyber Insurance & Breach Exposure Disclaimer: Premium benchmarks and breach loss figures are deterministic "
            "computational models and do not constitute an insurance binder, policy quote, or coverage guarantee."
        ),
        "quick_unlock_heading": "Get Your Cyber Liability Coverage &amp; Underwriting Worksheet",
        "quick_unlock_summary": "Unlocks limit/SIR tradeoff matrix, underwriting security control checklist, and premium budget model.",
        "quick_btn_text": "Download Cyber Insurance Worksheet",
        "quote_heading_prefix": "Active Cyber Insurance &amp; Security GRC Quote Intake",
        "quote_sub_template": (
            "Cyber risk budgets at or above {threshold_fmt} qualify for direct active cyber insurance quotes "
            "and underwriting security posture matching. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched active cyber insurance, GRC automation, and pentest partners (Coalition, Vanta, Drata, Sprinto, Thoropass, Cobalt)",
        "quote_btn_text": "Request Matched Cyber Policy Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "aicpa"),
    },
    "fedramp": {
        "framework_key": "fedramp",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm FedRAMP Moderate / High & 3PAO Authorization Workpaper Suite",
        "statutory_authority": "NIST SP 800-53 Rev 5, FedRAMP Rev 5 Baselines & OMB M-24-15 Authorization Policy",
        "economic_dataset": "FedRAMP PMO 3PAO Assessment Benchmarks & ConMon Engineering Cost Surveys",
        "regulator_name": "FedRAMP PMO & Accredited 3PAO Assessors",
        "default_sku_slug": "fedramp-authorization-3pao-cost-calculator",
        "vertical": "fedramp_3pao_ato",
        "primary_partner_key": "drata_compliance",
        "vanta_url": "https://www.vanta.com/solutions/fedramp",
        "partner_rep_desk": "Drata FedRAMP & 3PAO ATO Readiness Desk",
        "deliverables": [
            "JSON + CSV NIST SP 800-53 Rev 5 SSP, SAP, SAR & POA&M boundary scoping workbook",
            "3PAO Readiness Assessment Report (RAR), full security assessment & annual ConMon budget model",
            "FIPS 140-3 validated cryptography & federal boundary isolation engineering hours estimator",
            "Executive federal market entry & Agency ATO budget workbook",
        ],
        "preferred_trend_ids": ("fedramp_3pao_sar_benchmark", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal FedRAMP Authorizations to Operate (ATOs) require independent assessment by an accredited FedRAMP "
            "Third Party Assessment Organization (3PAO) and federal agency sponsorship."
        ),
        "statutory_disclaimer": (
            "FedRAMP ATO Disclaimer: 3PAO assessment fees, boundary engineering, and ConMon estimates are deterministic "
            "computational models and do not constitute a FedRAMP PMO or agency Authorization to Operate."
        ),
        "quick_unlock_heading": "Get Your FedRAMP SSP, 3PAO &amp; ConMon Budget Worksheet",
        "quick_unlock_summary": "Unlocks NIST 800-53 control boundary checklist, 3PAO SAR estimator, and ConMon budget model.",
        "quick_btn_text": "Download FedRAMP ATO Worksheet",
        "quote_heading_prefix": "FedRAMP ATO &amp; 3PAO GRC Readiness Quote Intake",
        "quote_sub_template": (
            "FedRAMP authorization budgets at or above {threshold_fmt} qualify for direct FedRAMP GRC automation quotes "
            "and accredited 3PAO / advisory matching. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched federal GRC automation, 3PAO readiness, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched FedRAMP Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "hipaa", "soc 2", "soc2", "aicpa"),
    },
    "pentest": {
        "framework_key": "pentest",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm CREST/OSCP Penetration Testing Scoping & RoE Workpaper Suite",
        "statutory_authority": "NIST SP 800-115, PTES Execution Standard, OWASP ASVS v4 & PCI Req 11.4",
        "economic_dataset": "CREST / PtaaS Penetration Testing Day-Rate & Retest Benchmarks",
        "regulator_name": "CREST / OSCP Accredited Penetration Testing Providers",
        "default_sku_slug": "penetration-testing-scoping-cost-calculator",
        "vertical": "offensive_security_pentest",
        "primary_partner_key": "cobalt_pentest",
        "vanta_url": "https://www.vanta.com/platform",
        "partner_rep_desk": "Cobalt CREST & OSCP PtaaS Scoping Desk",
        "deliverables": [
            "JSON + CSV Rules of Engagement (RoE), web/API/cloud asset scoping & credentialed test matrix",
            "Gray-box vs black-box tester-day rate estimator & free retest remediation schedule",
            "CVSS v3.1 finding SLA triage & board assurance report summary template",
            "Annual offensive security & continuous validation budget workbook",
        ],
        "preferred_trend_ids": ("bls_soc_15_1212_infosec_wage", "iso_27006_stage2_auditor_days"),
        "compliance_sentence": (
            "Formal compliance penetration test letters of attestation require execution by qualified CREST, OSCP, or "
            "GPEN certified offensive security testers with documented retesting."
        ),
        "statutory_disclaimer": (
            "Penetration Testing Scoping Disclaimer: Tester-day estimates and remediation timelines are deterministic "
            "computational models and do not constitute an executive Letter of Attestation."
        ),
        "quick_unlock_heading": "Get Your Penetration Testing RoE &amp; Scoping Worksheet",
        "quick_unlock_summary": "Unlocks web/API/cloud asset count estimator, RoE checklist, and PtaaS budget schedule.",
        "quick_btn_text": "Download Pentest Scoping Worksheet",
        "quote_heading_prefix": "Certified Penetration Testing &amp; GRC Quote Intake",
        "quote_sub_template": (
            "Security testing budgets at or above {threshold_fmt} qualify for direct PtaaS scoping quotes, "
            "CREST/OSCP tester matching, and compliance workflow automation. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched PtaaS, GRC automation, and cyber risk partners (Cobalt, Vanta, Drata, Sprinto, Thoropass, Coalition)",
        "quote_btn_text": "Request Matched Pentest Quote",
        "forbidden_leak_tokens": ("cmmc", "c3pao", "hipaa", "aicpa"),
    },
    "cmmc": {
        "framework_key": "cmmc",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm CMMC 2.0 Level 2 & NIST SP 800-171 SPRS Audit Workpaper Suite",
        "statutory_authority": "32 CFR Part 170 (CMMC 2.0), DFARS 252.204-7012/7021 & NIST SP 800-171 Rev 2",
        "economic_dataset": "DoD CIO 32 CFR Part 170 Regulatory Impact Analysis & Cyber-AB C3PAO Benchmarks",
        "regulator_name": "DoD CIO, Cyber-AB & Authorized C3PAO Assessors",
        "default_sku_slug": "cmmc-2-0-compliance-cost-calculator",
        "vertical": "cmmc_dod_defense",
        "primary_partner_key": "drata_compliance",
        "vanta_url": "https://www.vanta.com/solutions/cmmc",
        "partner_rep_desk": "Drata CMMC 2.0 & C3PAO Readiness Desk",
        "deliverables": [
            "JSON + CSV NIST SP 800-171 Rev 2 110-practice SPRS (-203 to 110) scoring & POA&M template",
            "Cyber-AB C3PAO triennial Level 2 assessment cost breakdown & FedRAMP Moderate enclave estimator",
            "32 CFR Part 170 SSP maturity & 180-day conditional certification POA&M closeout log",
            "Defense Industrial Base (DIB) executive CUI enclave budget workbook",
        ],
        "preferred_trend_ids": ("dod_cmmc_c3pao_assessment_base", "bls_soc_15_1212_infosec_wage"),
        "compliance_sentence": (
            "Formal CMMC Level 2 certifications under 32 CFR Part 170 require assessment by an accredited Cyber-AB "
            "Certified Third-Party Assessment Organization (C3PAO)."
        ),
        "statutory_disclaimer": (
            "CMMC 2.0 & NIST 800-171 Disclaimer: SPRS scores, enclave engineering, and C3PAO assessment estimates are "
            "deterministic computational models and do not constitute an official DoD CMMC certificate or SPRS filing."
        ),
        "quick_unlock_heading": "Get Your CMMC 2.0 SPRS, SSP &amp; POA&amp;M Worksheet",
        "quick_unlock_summary": "Unlocks 110-practice SPRS scoring checklist, CUI enclave estimator, and C3PAO budget schedule.",
        "quick_btn_text": "Download CMMC / SPRS Worksheet",
        "quote_heading_prefix": "CMMC 2.0 &amp; C3PAO Readiness Quote Intake",
        "quote_sub_template": (
            "Defense compliance budgets at or above {threshold_fmt} qualify for direct GRC automation quotes, "
            "C3PAO assessor matching, and CUI boundary scoping. Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": "matched CMMC GRC automation, C3PAO readiness, pentest, and cyber risk partners (Vanta, Drata, Sprinto, Thoropass, Coalition, Cobalt)",
        "quote_btn_text": "Request Matched CMMC Quote",
        "forbidden_leak_tokens": (),
    },
    "soc2": {
        "framework_key": "soc2",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "offer_price_usd": 0.0,  # Resolved from pseofactory.pricing
        "offer_price_cents": 0,
        "offer_title": "GainHelm SOC 2 Type II, CMMC 2.0 & NIST 800-171 Audit Scoping Workpaper Suite",
        "statutory_authority": "AICPA SSAE 18 (AT-C Section 205), Trust Services Criteria (TSP Section 100) & 32 CFR Part 170",
        "economic_dataset": "AICPA Peer Review & ISO/IEC 27006-1:2024 Auditor-Day Benchmarks",
        "regulator_name": "AICPA Auditing Standards Board, DoD CIO, and HHS OCR",
        "default_sku_slug": "soc-2-audit-cost-calculator",
        "vertical": "soc2_grc_automation",
        "primary_partner_key": "vanta_security",
        "vanta_url": "https://www.vanta.com/products/soc-2",
        "partner_rep_desk": "Vanta Trust Management & SOC 2 Audit Desk",
        "deliverables": [
            "JSON + CSV Control Scoping Matrix (AICPA Trust Services Criteria, NIST 800-171 & ISO 27001 Annex A)",
            "Auditor-Day Rate & Readiness Gap Worksheet (Type I vs Type II observation window sensitivity)",
            "CISO & CFO Board Budget Approval Template with GRC automation ROI comparison",
            "3-Year Audit, Penetration Testing & Compliance Staffing Total Cost of Ownership (TCO) Schedule",
        ],
        "preferred_trend_ids": (
            "aicpa_soc2_cpa_day_rate",
            "dod_cmmc_c3pao_assessment_base",
            "hhs_hipaa_tier4_annual_cap",
            "iso_27006_stage2_auditor_days",
            "fred_cpilfesl_inflation",
        ),
        "compliance_sentence": (
            "Formal SOC 2 attestations require an independent AICPA CPA firm, and CMMC Level 2 certifications require "
            "an authorized C3PAO."
        ),
        "statutory_disclaimer": GAINHELM_DISCLOSURES["statutory_compliance_disclaimer"],
        "quick_unlock_heading": "Get Your Auditor-Ready Control Scope, POA&amp;M &amp; Budget Worksheet",
        "quick_unlock_summary": (
            "Unlocks control-by-control evidence collection checklist, engineering remediation hour estimator, "
            "and board budget approval schedule."
        ),
        "quick_btn_text": "Download Audit Scope &amp; Budget Worksheet",
        "quote_heading_prefix": "Enterprise GRC Automation &amp; Audit Readiness Quote Intake",
        "quote_sub_template": (
            "Compliance and audit readiness budgets at or above {threshold_fmt} qualify for direct GRC automation "
            "platform fee quotes, AICPA CPA / C3PAO assessor matching, and multi-framework control scoping. "
            "Sub-threshold calculations stay 100% frictionless."
        ),
        "quote_consent_scope": (
            "matched GRC automation, CPA audit, penetration testing, or cyber insurance partners "
            "(including Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt)"
        ),
        "quote_btn_text": "Request Matched GRC &amp; Audit Quote",
        "forbidden_leak_tokens": (),
    },
}

GAINHELM_STRICT_ISOLATED_FRAMEWORKS: Tuple[str, ...] = (
    "dora",
    "eu_ai_act",
    "sec_8k",
    "gdpr",
    "ccpa",
    "nis2",
)
for _gh_fw_k, _gh_fw_v in GAINHELM_FRAMEWORK_PROFILES.items():
    _gh_fw_v["strict_isolated"] = _gh_fw_k in GAINHELM_STRICT_ISOLATED_FRAMEWORKS
    try:
        from pseofactory.pricing import resolve_offer_pricing as _gh_resolve_pricing

        _gh_priced = _gh_resolve_pricing(
            "gainhelm",
            tier_kind="full",
            slug=str(_gh_fw_v.get("default_sku_slug") or ""),
            sku=str(_gh_fw_v.get("offer_sku") or ""),
        )
        _gh_fw_v["offer_price_usd"] = float(_gh_priced["price_usd"])
        _gh_fw_v["offer_price_cents"] = int(_gh_priced["price_cents"])
    except Exception:
        _gh_fw_v["offer_price_usd"] = 29.0
        _gh_fw_v["offer_price_cents"] = 2900


GAINHELM_VANTA_URLS_BY_FRAMEWORK: Dict[str, str] = {
    fw_k: str(fw_v["vanta_url"])
    for fw_k, fw_v in GAINHELM_FRAMEWORK_PROFILES.items()
}


GAINHELM_PARTNER_ALIASES: Dict[str, str] = {
    "vanta": "vanta_security",
    "vanta_compliance": "vanta_security",
    "drata": "drata_compliance",
    "sprinto": "sprinto_compliance",
    "sprinto_grc": "sprinto_compliance",
    "thoropass": "thoropass_audit",
    "coalition": "coalition_cyber_insurance",
    "cobalt": "cobalt_pentest",
}

GAINHELM_PARTNER_REP_DESK_BY_KEY: Dict[str, str] = {
    "vanta_security": "Vanta Continuous Trust & Compliance Automation Desk",
    "drata_compliance": "Drata Enterprise GRC & Automated Audit Desk",
    "sprinto_compliance": "Sprinto Continuous Security & Cloud Compliance Desk",
    "thoropass_audit": "Thoropass Compliance Readiness & Advisory Desk",
    "coalition_cyber_insurance": "Coalition Active Cyber Insurance & GRC Underwriting Desk",
    "cobalt_pentest": "Cobalt CREST & OSCP PtaaS Scoping Desk",
}


def normalize_gainhelm_partner_key(partner_key: str) -> str:
    """Normalizes GainHelm partner key aliases to their canonical registry key."""
    pk_clean = (partner_key or "").strip().lower()
    return GAINHELM_PARTNER_ALIASES.get(pk_clean, pk_clean)


def resolve_gainhelm_partner_rep_desk(
    partner_key: str,
    slug: str = "",
    vertical: str = "",
) -> str:
    """
    Returns framework-matched rep desk copy for a GainHelm partner selection.
    Uses the resolved framework profile desk when partner_key matches its primary
    partner, and a framework-neutral partner desk otherwise. Zero em/en-dashes.
    """
    fw_prof = get_gainhelm_framework_profile(slug=slug or "", vertical=vertical or "")
    pk_norm = normalize_gainhelm_partner_key(partner_key)
    if not pk_norm or pk_norm == str(fw_prof.get("primary_partner_key") or ""):
        return str(fw_prof.get("partner_rep_desk") or GAINHELM_PARTNER_REP_DESK_BY_KEY["vanta_security"])
    return str(
        GAINHELM_PARTNER_REP_DESK_BY_KEY.get(pk_norm)
        or fw_prof.get("partner_rep_desk")
        or GAINHELM_PARTNER_REP_DESK_BY_KEY["vanta_security"]
    )


def resolve_gainhelm_partner_url(
    partner_key: str,
    tool_slug: str = "",
    default_url: str = "",
    vertical: str = "",
) -> str:
    """
    Returns the framework-matched default destination URL for a GainHelm partner.
    Shared by Python route helpers and Edge /r/:partner + /api/lead-capture codegen.
    Zero em-dashes. Zero en-dashes.
    """
    pk_clean = normalize_gainhelm_partner_key(partner_key)
    if pk_clean == "vanta_security":
        prof = get_gainhelm_framework_profile(slug=tool_slug or "", vertical=vertical or "")
        return str(prof.get("vanta_url") or GAINHELM_FRAMEWORK_PROFILES["soc2"]["vanta_url"])
    if not (default_url or "").strip() and pk_clean in GAINHELM_AFFILIATES:
        return str(GAINHELM_AFFILIATES[pk_clean].default_url or "")
    return (default_url or "").strip()


def get_gainhelm_framework_profile(slug: str = "", vertical: str = "") -> Dict[str, Any]:
    """Returns the canonical GainHelm framework profile for a calculator slug or vertical."""
    fw_key = classify_gainhelm_framework(slug=slug, vertical=vertical)
    return GAINHELM_FRAMEWORK_PROFILES.get(fw_key, GAINHELM_FRAMEWORK_PROFILES["soc2"])


def get_gainhelm_compliance_strip_text(slug: str = "") -> str:
    """Returns the GainHelm top-of-page YMYL + FTC 16 CFR Part 255 disclosure matched to the calculator framework."""
    prof = get_gainhelm_framework_profile(slug=slug)
    return (
        "Statutory & FTC Disclosure (16 CFR Part 255): Audit scoping and penalty models are provided for "
        "educational and informational purposes only and are not legal, tax, accounting, or certified audit advice. "
        f"{prof['compliance_sentence']} "
        "GainHelm may receive referral compensation from vetted compliance and security partners at no additional cost to your organization."
    )


def get_gainhelm_statutory_disclaimer(slug: str = "") -> str:
    """Returns the framework-specific GainHelm statutory disclaimer for a calculator slug."""
    return str(get_gainhelm_framework_profile(slug=slug).get("statutory_disclaimer", ""))


def has_gainhelm_cross_framework_leak(
    html_or_text: str,
    slug: str = "",
    vertical: str = "",
) -> bool:
    """
    Detects forbidden cross-framework tokens (such as SOC 2 / CMMC / C3PAO / AICPA / HIPAA)
    in visible copy or data-vertical attributes for non-owning GainHelm calculators while
    ignoring canonical SKU identifiers and sibling /tools/ navigation URLs.
    Zero em-dashes. Zero en-dashes.
    """
    prof = get_gainhelm_framework_profile(slug=slug, vertical=vertical)
    forbidden = tuple(prof.get("forbidden_leak_tokens", ()))
    if not forbidden or not html_or_text:
        return False
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_or_text, flags=re.S | re.I)
    cleaned = re.sub(r"<style\b[^>]*>.*?</style>", " ", cleaned, flags=re.S | re.I)
    # Extract non-SKU data-vertical attributes too so soc2_grc_automation leaks are flagged
    vertical_vals = " ".join(re.findall(r'data-vertical=["\']([^"\']+)["\']', cleaned, flags=re.I))
    visible = html_lib.unescape(re.sub(r"<[^>]+>", " ", cleaned))
    combined = f"{visible} {vertical_vals}".lower()
    for sku_tok in (
        "gh_soc2_cmmc_audit_workpapers",
        "gh_hipaa_iso27001_governance_kit",
        "gh_instant_compliance_worksheet_19",
    ):
        combined = combined.replace(sku_tok, " ")
    return any(tok in combined for tok in forbidden)


_GAINHELM_PARTNER_CONTEXTUAL_COPY: Dict[str, Dict[str, Tuple[str, str, str, str]]] = {
    "dora": {
        "vanta_security": (
            "EU DORA & Enterprise GRC Automation",
            "Vanta Trust Management & DORA Readiness Automation",
            "Automate EU DORA Article 5-30 ICT risk evidence collection, continuous cloud monitoring, and Article 28 third-party vendor oversight.",
            "Automate DORA Compliance with Vanta",
        ),
        "drata_compliance": (
            "EU DORA & Continuous Control Monitoring",
            "Drata Enterprise GRC & DORA ICT Risk Platform",
            "Streamline EU DORA ICT resilience controls, asset inventory mapping, and Competent Authority audit trail readiness.",
            "Launch DORA Readiness with Drata",
        ),
        "sprinto_compliance": (
            "Automated DORA Readiness",
            "Sprinto DORA Compliance & ICT Risk Automation",
            "Rapid compliance automation for European financial entities and ICT service providers managing DORA controls and Register of Information workflows.",
            "Compare DORA Pricing with Sprinto",
        ),
        "thoropass_audit": (
            "Integrated GRC & Independent Assurance",
            "Thoropass Enterprise Compliance & ICT Audit Readiness",
            "Unified compliance automation and accredited technical review workflows for EU DORA ICT risk and TLPT resilience controls.",
            "Scope DORA Controls with Thoropass",
        ),
        "coalition_cyber_insurance": (
            "Active Cyber Insurance & ICT Risk Protection",
            "Coalition Active Cyber Insurance & Incident Response",
            "Active attack-surface monitoring, pre-breach digital forensics readiness, and cyber risk transfer aligned with EU DORA operational resilience.",
            "Quote Active Cyber Coverage with Coalition",
        ),
        "cobalt_pentest": (
            "CREST & TLPT Penetration Testing (PtaaS)",
            "Cobalt Offensive Security & DORA Resilience Testing",
            "On-demand CREST, OSCP, and GPEN certified Penetration Testing as a Service (PtaaS) supporting DORA Article 25-26 resilience testing and remediation workflows.",
            "Scope DORA Resilience Testing with Cobalt",
        ),
    },
    "eu_ai_act": {
        "vanta_security": (
            "AI Governance & EU AI Act Automation",
            "Vanta Trust Management & EU AI Act Readiness",
            "Automate ISO/IEC 42001, EU AI Act Annex III risk management evidence, and continuous governance monitoring across high-risk AI pipelines.",
            "Automate AI Governance with Vanta",
        ),
        "drata_compliance": (
            "ISO 42001 & EU AI Act Control Monitoring",
            "Drata Enterprise GRC & AI Governance Automation",
            "Streamline EU AI Act Article 9-17 Quality Management System controls, model lineage evidence, and continuous governance audits.",
            "Launch EU AI Act Readiness with Drata",
        ),
        "sprinto_compliance": (
            "Fast-Track AI Governance & ISO 42001",
            "Sprinto Automated AI Risk & Conformity Readiness",
            "Structured compliance automation for AI providers preparing Annex IV technical documentation and ISO 42001 governance evidence.",
            "Compare AI Governance Pricing with Sprinto",
        ),
        "thoropass_audit": (
            "Conformity Readiness & Accredited Assurance",
            "Thoropass Enterprise Compliance & AI Governance Audit Prep",
            "Unified GRC platform and technical review workflows for ISO/IEC 42001 and EU AI Act high-risk QMS readiness.",
            "Scope AI Conformity Prep with Thoropass",
        ),
        "coalition_cyber_insurance": (
            "Active Cyber & AI Operational Risk Insurance",
            "Coalition Active Cyber Insurance & Incident Defense",
            "Continuous security monitoring, incident response retainers, and cyber liability coverage protecting AI-enabled enterprise deployments.",
            "Quote Active Cyber Coverage with Coalition",
        ),
        "cobalt_pentest": (
            "CREST & AI Adversarial Testing (PtaaS)",
            "Cobalt Offensive Security & AI System Pentesting",
            "On-demand CREST and OSCP certified Penetration Testing as a Service (PtaaS) covering EU AI Act Article 15 cybersecurity robustness testing.",
            "Scope AI Security Testing with Cobalt",
        ),
    },
    "sec_8k": {
        "vanta_security": (
            "SEC Reg S-K Item 106 & Cyber Governance",
            "Vanta Enterprise Security & SEC Cyber Disclosure Readiness",
            "Automate continuous control monitoring, CISO board reporting evidence, and Reg S-K Item 106 governance documentation.",
            "Automate SEC Cyber Governance with Vanta",
        ),
        "drata_compliance": (
            "Continuous Control Monitoring & Item 106",
            "Drata Enterprise GRC & Public-Company Cyber Governance",
            "Centralize cyber risk register evidence, incident escalation workflows, and annual Form 10-K Item 106 board oversight tracking.",
            "Launch Cyber Governance with Drata",
        ),
        "sprinto_compliance": (
            "Automated Cyber Governance & Risk Monitoring",
            "Sprinto Enterprise Security & SEC Readiness Automation",
            "Continuous control monitoring and automated evidence audit trails supporting public-company risk management and incident triage SLAs.",
            "Compare SEC Readiness Pricing with Sprinto",
        ),
        "thoropass_audit": (
            "Enterprise Governance & Technical Assurance",
            "Thoropass Cyber Governance & Readiness Assurance",
            "Unified security governance automation and technical control validation supporting board-level cyber risk oversight.",
            "Scope Cyber Governance with Thoropass",
        ),
        "coalition_cyber_insurance": (
            "Active Cyber Insurance & DFIR Breach Retainer",
            "Coalition Active Cyber Insurance & 4-Day Incident Defense",
            "Active cyber monitoring, rapid DFIR forensic triage, and breach cost coverage calibrated for Form 8-K Item 1.05 response timelines.",
            "Quote Active Cyber & DFIR Coverage with Coalition",
        ),
        "cobalt_pentest": (
            "CREST & OSCP Certified PtaaS Validation",
            "Cobalt Offensive Security & Material Risk Validation",
            "On-demand CREST, OSCP, and GPEN certified Penetration Testing as a Service (PtaaS) verifying remediation of high-severity vulnerabilities.",
            "Scope Security Validation with Cobalt",
        ),
    },
    "non_audit_generic": {
        "vanta_security": (
            "Enterprise GRC & Regulatory Automation",
            "Vanta Enterprise GRC & Continuous Security Automation",
            "Automate multi-framework evidence collection, continuous cloud security monitoring, and regulator-ready risk management workflows.",
            "Automate Security Compliance with Vanta",
        ),
        "drata_compliance": (
            "Continuous Security & GRC Monitoring",
            "Drata Enterprise GRC & Automated Control Monitoring",
            "Centralize risk registers, security policies, and automated technical control checks across cloud and corporate infrastructure.",
            "Automate Security Controls with Drata",
        ),
        "sprinto_compliance": (
            "Automated Risk & Compliance Workflows",
            "Sprinto Multi-Framework GRC Automation",
            "Rapid compliance automation with pre-mapped security controls, vendor risk tracking, and continuous audit trail logging.",
            "Compare GRC Pricing with Sprinto",
        ),
        "thoropass_audit": (
            "Integrated GRC & Technical Assurance",
            "Thoropass Enterprise Compliance & Audit Readiness",
            "Unified compliance workflow automation and independent technical assessment support.",
            "Scope Compliance Readiness with Thoropass",
        ),
        "coalition_cyber_insurance": (
            "Active Cyber Insurance & Breach Defense",
            "Coalition Active Cyber Insurance & Risk Transfer",
            "Active attack-surface monitoring, pre-breach security controls, and rapid DFIR breach coverage.",
            "Quote Active Cyber Coverage with Coalition",
        ),
        "cobalt_pentest": (
            "CREST & OSCP Certified PtaaS",
            "Cobalt Offensive Security & Pentest as a Service",
            "On-demand CREST, OSCP, and GPEN certified Penetration Testing as a Service (PtaaS) with Jira/GitHub remediation workflows and free retesting.",
            "Scope Certified PtaaS Engagement with Cobalt",
        ),
    },
}

LIENBOND_DISCLOSURES: Dict[str, str] = {
    "statutory_compliance_disclaimer": (
        "Statutory Surety, Workers Comp & Construction Lien Disclaimer: Bond premium, NCCI workers compensation "
        "EMR, mechanics lien deadline, retainage penalty, and Davis-Bacon WH-347 figures are deterministic "
        "computational models and do not constitute legal advice, a recorded mechanics lien, "
        "or an active surety binder from a Treasury Circular 570 carrier."
    ),
    "statutory_surety_disclaimer": (
        "Statutory Surety, Workers Comp & Construction Lien Disclaimer: Bond premium, NCCI workers compensation "
        "EMR, mechanics lien deadline, retainage penalty, and Davis-Bacon WH-347 figures are deterministic "
        "computational models and do not constitute legal advice, a recorded mechanics lien, "
        "or an active surety binder from a Treasury Circular 570 carrier."
    ),
    "ftc_disclosure": (
        "FTC Partner Compensation Disclosure: LienBond is an independent construction surety, workers compensation, "
        "and statutory lien compliance research publisher. We offer direct statutory underwriting and payroll audit "
        "packets and may receive referral compensation when active partner agreements are in force (such as Simply "
        "Business, SuretyBondsDirect.com, Thimble, Jobber, or Levelset) at no additional cost to you."
    ),
    "independent_publisher_disclaimer": (
        "Independent Publisher Disclaimer: LienBond is an independent construction compliance and surety calculation "
        "publisher and is not affiliated with NCCI, the U.S. Department of Labor, U.S. Treasury Circular 570, or state "
        "contractor licensing boards."
    ),
}

LIENBOND_MONETIZED_CALCULATOR_SLUGS: List[str] = [
    "workers-compensation-class-code-rate-calculator-by-state",
    "contractor-license-bond-cost-calculator-by-credit-score",
    "miller-act-performance-and-payment-bond-premium-calculator",
    "contractor-lien-release-statutory-matrix-by-state",
    "commercial-construction-retainage-interest-penalty-calculator-by-state",
    "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator",
    "erisa-fidelity-bond-coverage-amount-calculator",
    "contractor-overhead-and-profit-markup-vs-margin-calculator",
    "experience-modification-rate-emr-workers-comp-penalty-calculator",
    "california-texas-florida-preliminary-notice-deadline-calculator",
]

LIENBOND_AFFILIATES: Dict[str, AffiliatePartner] = {
    "simply_business": AffiliatePartner(
        key="simply_business",
        name="Simply Business Commercial Contractor Insurance & Bonding",
        category="Commercial Contractor Insurance & Workers Comp",
        property_id="lienbond",
        status="pending",
        env_var="AFFILIATE_SIMPLY_BUSINESS_URL",
        default_url="https://www.simplybusiness.com/",
        badge="Instant Multi-Carrier Workers Comp & GL Quotes",
        commission_est="$160-$210/qualified quote (pending approval)",
        bounty_est="$185",
        network="Impact.com",
        description="Compare instant multi-carrier workers compensation, general liability, and builder risk quotes across NCCI and state rating bureau trade class codes.",
        target_tools=list(LIENBOND_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Compare Instant Workers Comp & Contractor Quotes at Simply Business",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "suretybonds_direct": AffiliatePartner(
        key="suretybonds_direct",
        name="SuretyBondsDirect.com Nationwide Surety & License Bonding",
        category="Contractor License & Miller Act Surety Bonds",
        property_id="lienbond",
        status="pending",
        env_var="AFFILIATE_SURETYBONDS_DIRECT_URL",
        default_url="https://www.suretybondsdirect.com/",
        badge="Nationwide State License, Bid & Performance Bonds",
        commission_est="$150-$225/issued bond (pending approval)",
        bounty_est="$175-$230",
        network="In-House Direct",
        description="Instant online underwriting for state contractor license bonds (CSLB, TX, FL), Federal Miller Act performance/payment bonds, and ERISA Section 412 fidelity bonds.",
        target_tools=list(LIENBOND_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Get Your Instant State License or Performance Bond Quote at SuretyBondsDirect.com",
        partnership_model="HYBRID_CPA_REVSHARE",
    ),
    "next_insurance_b2b": AffiliatePartner(
        key="next_insurance_b2b",
        name="Next Insurance Commercial Contractor Policies",
        category="On-Demand Workers Comp & General Liability COI",
        property_id="lienbond",
        status="declined",
        env_var="AFFILIATE_NEXT_INSURANCE_B2B_URL",
        default_url="https://www.nextinsurance.com/",
        badge="Declined Application",
        commission_est="Declined on Impact",
        bounty_est="$0",
        network="Impact.com",
        description="Digital commercial insurance for general contractors and trade subcontractors with Certificates of Insurance (COI).",
        target_tools=[],
        supported_params=["ph_tier"],
        cta_text="Next Insurance Commercial Contractor Overview",
        partnership_model="QUALIFIED_LEAD_CPL",
    ),
    "thimble_contractor": AffiliatePartner(
        key="thimble_contractor",
        name="Thimble On-Demand Contractor Insurance",
        category="Instant Certificate of Insurance (COI)",
        property_id="lienbond",
        status="pending",
        env_var="AFFILIATE_THIMBLE_CONTRACTOR_URL",
        default_url="https://www.thimble.com/",
        badge="Instant Job-Site COI & Subcontractor Coverage",
        commission_est="$110-$145/bound policy (pending approval)",
        bounty_est="$125",
        network="Impact.com",
        description="Same-day general liability and commercial contractor policies designed for subcontractors who need an immediate compliant Certificate of Insurance to step onto a job site.",
        target_tools=list(LIENBOND_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Get an Instant Job-Site Certificate of Insurance via Thimble",
        partnership_model="CPA_BOUNTY",
    ),
    "jobber_field_service": AffiliatePartner(
        key="jobber_field_service",
        name="Jobber Contractor Estimating, Markup & Progress Billing",
        category="Construction Estimating & Invoicing SaaS",
        property_id="lienbond",
        status="pending",
        env_var="AFFILIATE_JOBBER_FIELD_SERVICE_URL",
        default_url="https://getjobber.com/",
        badge="Automated Contractor Markup & Progress Billing",
        commission_est="$150-$185/paid trial + revshare (pending approval)",
        bounty_est="$160-$195",
        network="PartnerStack",
        description="Automated contractor job costing, overhead/markup-to-margin bid templates, AIA-style progress invoicing, and automated client payment collection.",
        target_tools=list(LIENBOND_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="Automate Contractor Estimates & Progress Billing with Jobber",
        partnership_model="RECURRING_SAAS_REVSHARE",
    ),
    "levelset_lien_filing": AffiliatePartner(
        key="levelset_lien_filing",
        name="Levelset Construction Preliminary Notice & Lien Automation",
        category="50-State Mechanics Lien & Notice Recording",
        property_id="lienbond",
        status="pending",
        env_var="AFFILIATE_LEVELSET_LIEN_FILING_URL",
        default_url="https://www.levelset.com/mechanics-lien/",
        badge="50-State Certified Notice & Lien Recording",
        commission_est="$165-$215/recorded filing (pending approval)",
        bounty_est="$190",
        network="In-House Direct",
        description="Automated 50-state preliminary notice tracking, statutory conditional/unconditional lien waiver exchange, and county recorder mechanics lien filing.",
        target_tools=list(LIENBOND_MONETIZED_CALCULATOR_SLUGS),
        supported_params=["ph_tier"],
        cta_text="File Your State Preliminary Notice or Mechanics Lien via Levelset",
        partnership_model="USAGE_API_REFERRAL",
    ),
}

# Property-Isolated Master Registries (Zero Cross-Tenant Overwrites on Shared Keys)
AFFILIATE_REGISTRY_BY_PROPERTY: Dict[str, Dict[str, AffiliatePartner]] = {
    "profithelm": PROFITHELM_AFFILIATES,
    "prexvo": PREXVO_AFFILIATES,
    "gainhelm": GAINHELM_AFFILIATES,
    "lienbond": LIENBOND_AFFILIATES,
}

AFFILIATE_REGISTRY: Dict[str, AffiliatePartner] = {
    **LIENBOND_AFFILIATES,
    **PREXVO_AFFILIATES,
    **GAINHELM_AFFILIATES,
    **PROFITHELM_AFFILIATES,
    **{f"profithelm:{k}": v for k, v in PROFITHELM_AFFILIATES.items()},
    **{f"prexvo:{k}": v for k, v in PREXVO_AFFILIATES.items()},
    **{f"gainhelm:{k}": v for k, v in GAINHELM_AFFILIATES.items()},
    **{f"lienbond:{k}": v for k, v in LIENBOND_AFFILIATES.items()},
}
AFFILIATE_REGISTRY["equipment_macrs"] = PROFITHELM_AFFILIATES["crest_capital"]
AFFILIATE_REGISTRY["first_american_1031"] = PROFITHELM_AFFILIATES["first_american"]


def lookup_affiliate_partner(
    partner_key: str,
    property_id: Optional[str] = None,
) -> Optional[AffiliatePartner]:
    """
    Tenant-isolated affiliate partner lookup so shared partner keys
    (e.g., suretybonds_direct, simply_business, next_insurance_b2b)
    never bleed across profithelm and lienbond.
    """
    pk = (partner_key or "").strip().lower()
    if not pk:
        return None
    if ":" in pk:
        ns_prop, ns_pk = pk.split(":", 1)
        reg = AFFILIATE_REGISTRY_BY_PROPERTY.get(ns_prop.strip().lower())
        if reg and ns_pk in reg:
            return reg[ns_pk]
        pk = ns_pk
    if property_id:
        prop = property_id.strip().lower()
        reg = AFFILIATE_REGISTRY_BY_PROPERTY.get(prop)
        if reg is not None:
            return reg.get(pk)
    return AFFILIATE_REGISTRY.get(pk)


# Boundary Sets
B2B_PARTNER_KEYS: Set[str] = {
    "coinledger",
    "koinly",
    "mercury",
    "stripe",
    "ramp",
    "rho",
    "gusto",
    "rippling",
    "xendoo",
    "lawdepot",
    "wallethub",
    "efile_com",
    "eztaxreturn_com",
    "freetaxusa",
    "crest_capital",
    "ipx1031",
    "exeter1031",
    "first_american",
    "turbotax",
    "taxslayer",
    "kalshi",
    "interactive_brokers",
    "simply_business",
    "suretybonds_direct",
    "next_insurance_b2b",
    "invoice_simple",
    "national_funding_med",
    "otr_solutions_factoring",
    "freightos_marketplace",
}

STUDENT_LOAN_PARTNER_KEYS: Set[str] = {
    "splash_financial",
    "sofi",
    "credible",
    "earnest",
    "lendkey",
}

GAINHELM_PARTNER_KEYS: Set[str] = {
    "vanta_security",
    "drata_compliance",
    "sprinto_compliance",
    "thoropass_audit",
    "coalition_cyber_insurance",
    "cobalt_pentest",
}

LIENBOND_PARTNER_KEYS: Set[str] = {
    "simply_business",
    "suretybonds_direct",
    "next_insurance_b2b",
    "thimble_contractor",
    "jobber_field_service",
    "levelset_lien_filing",
}

LIENBOND_TOOL_PATTERNS: List[str] = [
    "workers-compensation",
    "workers-comp",
    "class-code",
    "emr",
    "license-bond",
    "miller-act",
    "performance-and-payment-bond",
    "performance-bond",
    "subcontractor-default-insurance",
    "sdi-vs-performance-bond",
    "lien-release",
    "preliminary-notice",
    "retainage",
    "davis-bacon",
    "erisa-fidelity-bond",
    "markup-vs-margin",
]

GAINHELM_TOOL_PATTERNS: List[str] = [
    "soc-2",
    "soc2",
    "cmmc",
    "nist-800-171",
    "sprs",
    "iso-27001",
    "hipaa",
    "pci-dss",
    "fedramp",
    "hitrust",
    "penetration-testing",
    "pentest",
    "cyber-liability",
]

PROFITHELM_TOOL_PATTERNS: List[str] = [
    "section-179",
    "179",
    "crypto",
    "staking",
    "token",
    "saas",
    "runway",
    "1031",
    "arbitrage",
    "prediction",
    "odds",
    "ev",
    "kelly",
    "implied-probability",
    "kalshi-fees",
    "vig-spread",
    "break-even",
    "treasury",
    "yield",
    "qsbs",
    "1202",
    "bracket",
    "tcja",
    "tax",
    "s-corp",
    "workers-comp",
    "surety-bond",
    "section-301",
    "invoice-factoring",
    "section-174",
]

PREXVO_TOOL_PATTERNS: List[str] = [
    "student-loan",
    "rap",
    "ibr",
    "save",
    "pslf",
    "icr",
    "paye",
    "consolidation",
    "refinance",
    "repayment",
]

ENTERPRISE_B2B_PARTNERS: Set[str] = {
    "mercury",
    "ramp",
    "rho",
    "gusto",
    "rippling",
    "xendoo",
    "lawdepot",
    "stripe",
    "crest_capital",
    "ipx1031",
    "exeter1031",
    "first_american",
    "equipment_macrs",
    "first_american_1031",
    "simply_business",
    "suretybonds_direct",
    "next_insurance_b2b",
    "invoice_simple",
    "national_funding_med",
    "otr_solutions_factoring",
    "freightos_marketplace",
}

RETAIL_TAX_PARTNERS: Set[str] = {
    "efile_com",
    "eztaxreturn_com",
    "freetaxusa",
    "turbotax",
    "taxslayer",
}

RETAIL_TAX_SLUGS: Set[str] = {
    "irs-2027-tax-brackets",
    "tcja-sunset-capital-gains",
    "crypto-tax-calculator",
    "tcja-sunset-bracket-calculator",
    "ca-tax-brackets-2026",
    "prediction-market-tax",
    "prediction-market-odds",
}

COMMERCIAL_B2B_SLUGS: Set[str] = {
    "section-179-calculator",
    "section-1031-calculator",
    "saas-runway-calculator",
    "qsbs-section-1202-tax-calculator",
    "treasury-yield-calculator",
    "s-corp-reasonable-salary-tax-calculator",
    "workers-comp-and-payroll-burden-calculator",
    "contractor-surety-bond-cost-calculator",
    "equipment-lease-vs-buy-section-179-calculator",
    "medical-and-dental-equipment-section-179-roi-calculator",
    "commercial-heavy-vehicle-section-179-weight-calculator",
    "section-301-tariff-landed-cost-calculator",
    "invoice-factoring-vs-business-line-of-credit-calculator",
    "r-and-d-tax-credit-section-174-amortization-calculator",
}

PREXVO_RESTRICTED_PUBLIC_SERVICE_SLUGS: Set[str] = {
    "pslf-qualifying-payment-calculator",
    "pslf-qualifying-payment-simulator",
    "pslf-employer-ein-eligibility",
    "save-plan-litigation-transition",
    "save-forbearance-interest-tracker",
    "borrower-defense-discharge-calculator",
    "total-permanent-disability-discharge-calculator",
    "teacher-loan-forgiveness-calculator",
    "closed-school-discharge-calculator",
    "federal-poverty-guideline-discretionary-income-calculator",
    "student-loan-default-rehabilitation-calculator",
}

PREXVO_RESTRICTED_PUBLIC_SERVICE_TOKENS: Tuple[str, ...] = (
    "pslf",
    "public-service",
    "public service",
    "save-plan-litigation",
    "save plan litigation",
    "save-forbearance",
    "forbearance",
    "deferment",
    "borrower-defense",
    "borrower defense",
    "disability-discharge",
    "disability discharge",
    "total-and-permanent-disability",
    "total and permanent disability",
    "total-permanent-disability",
    "teacher-loan-forgiveness",
    "teacher loan forgiveness",
    "closed-school",
    "closed school",
    "low-income",
    "low income",
    "poverty-guideline",
    "poverty guideline",
    "hardship",
    "default-rehabilitation",
    "default rehabilitation",
)

INTENT_ROUTING_TABLE: Dict[str, List[str]] = {
    "section-1031": ["ipx1031", "lawdepot", "xendoo", "mercury", "wallethub"],
    "1031": ["ipx1031", "lawdepot", "xendoo", "mercury", "wallethub"],
    "section-179": ["xendoo", "ramp", "mercury", "lawdepot"],
    "179": ["xendoo", "ramp", "mercury", "lawdepot"],
    "macrs": ["xendoo", "ramp", "mercury", "lawdepot"],
    "depreciation": ["xendoo", "ramp", "mercury", "lawdepot"],
    "equipment": ["xendoo", "ramp", "lawdepot", "mercury", "wallethub"],
    "medical-equipment": ["xendoo", "ramp", "mercury", "wallethub"],
    "workers-comp": ["rippling", "gusto", "xendoo", "mercury"],
    "surety-bond": ["rippling", "xendoo", "lawdepot", "wallethub", "mercury"],
    "tariff-landed-cost": ["rippling", "xendoo", "ramp", "mercury", "wallethub"],
    "invoice-factoring": ["xendoo", "rippling", "ramp", "mercury", "wallethub"],
    "s-corp-payroll": ["rippling", "gusto", "xendoo", "mercury", "lawdepot"],
    "treasury": ["mercury", "wallethub", "ramp", "kalshi"],
    "yield": ["mercury", "wallethub", "ramp", "kalshi"],
    "tbill": ["mercury", "wallethub", "ramp"],
    "qsbs": ["mercury", "xendoo", "lawdepot", "ramp"],
    "1202": ["mercury", "xendoo", "lawdepot", "ramp"],
    "corporate-amt": ["xendoo", "rippling", "mercury", "ramp"],
    "r-and-d": ["rippling", "xendoo", "gusto", "mercury", "ramp"],
    "runway": ["rippling", "gusto", "mercury", "ramp"],
    "burn": ["rippling", "xendoo", "mercury", "ramp"],
    "saas": ["rippling", "gusto", "mercury", "ramp"],
    "payroll": ["rippling", "gusto", "mercury", "ramp"],
    "crypto": ["coinledger", "koinly", "freetaxusa", "efile_com"],
    "capital-gains": ["coinledger", "koinly", "efile_com", "freetaxusa", "wallethub"],
    "tax": ["efile_com", "eztaxreturn_com", "freetaxusa"],
    "bracket": ["efile_com", "eztaxreturn_com", "freetaxusa"],
    "tcja": ["efile_com", "eztaxreturn_com", "freetaxusa"],
    "irs": ["efile_com", "eztaxreturn_com", "freetaxusa"],
    "prediction-market-tax": ["coinledger", "kalshi", "koinly", "freetaxusa"],
    "prediction": ["kalshi", "coinledger", "wallethub"],
    "student-loan": ["splash_financial", "credible", "lendkey"],
    "cyber-compliance": ["vanta_security", "drata_compliance", "thoropass_audit", "sprinto_compliance", "coalition_cyber_insurance", "cobalt_pentest"],
    "pentest": ["cobalt_pentest", "vanta_security", "drata_compliance", "thoropass_audit", "sprinto_compliance"],
    "cyber-insurance": ["coalition_cyber_insurance", "vanta_security", "drata_compliance", "sprinto_compliance", "cobalt_pentest"],
}


# ---------------------------------------------------------------------------
# URL Validation & Parameter Encoding Engine
# ---------------------------------------------------------------------------

def validate_affiliate_url(url: str) -> bool:
    """
    Validates an affiliate URL.
    Enforces:
    - Non-empty string
    - Scheme must be http or https
    - Netloc must be present
    - No javascript:, data:, or relative URLs
    - No localhost, loopback, or SSRF link-local metadata endpoints
    - Zero em-dashes and zero en-dashes
    """
    if not url or not isinstance(url, str):
        return False
    url_clean = url.strip()
    if not url_clean:
        return False
    # Check for forbidden dashes
    if "\u2014" in url_clean or "\u2013" in url_clean:
        return False
    try:
        parsed = urllib.parse.urlsplit(url_clean)
    except Exception:
        return False
    if parsed.scheme.lower() not in ("https", "http"):
        return False
    if not parsed.netloc:
        return False
    url_lower = url_clean.lower()
    if "javascript:" in url_lower or "data:" in url_lower:
        return False

    # SSRF protection: reject localhost, loopback, link-local metadata, cloud metadata DNS, and private IP addresses
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    if hostname in ("localhost", "127.0.0.1", "::1", "169.254.169.254"):
        return False
    if hostname.endswith(".local") or hostname.endswith(".localhost"):
        return False
    if hostname.startswith("127.") or hostname.startswith("169.254."):
        return False
    if hostname in ("metadata.google.internal", "instance-data", "metadata") or hostname.endswith(".metadata.google.internal"):
        return False

    try:
        import ipaddress
        ip = None
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            # Parse integer, hex, or octal IP encodings
            ip_int = None
            if hostname.isdigit():
                ip_int = int(hostname)
            elif hostname.startswith("0x") or hostname.startswith("0X"):
                try:
                    ip_int = int(hostname, 16)
                except ValueError:
                    pass
            elif hostname.startswith("0") and hostname[1:].isdigit():
                try:
                    ip_int = int(hostname, 8)
                except ValueError:
                    pass
            else:
                parts = hostname.split(".")
                if len(parts) == 4:
                    try:
                        octets = [int(p, 0) for p in parts]
                        if all(0 <= o <= 255 for o in octets):
                            ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
                    except (ValueError, TypeError):
                        pass
            if ip_int is not None and 0 <= ip_int <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(ip_int)

        if ip is not None and (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved):
            return False
    except (ValueError, OverflowError):
        pass

    return True


def resolve_partner_url(
    partner: AffiliatePartner,
    value_tier: str = "starter",
    extra_params: Optional[Dict[str, str]] = None,
    tenant: Optional[str] = None,
    source_tool: str = "",
) -> str:
    """
    Resolves destination URL for an affiliate partner.
    Supports environment variable overrides (AFFILIATE_<KEY>_URL).
    Appends supported vendor-namespaced tracking parameters (ph_tier) without clobbering base parameters.
    Rejects sub-affiliate aggregator redirect domains if property is prexvo.
    """
    prop = (tenant or partner.property_id or "").strip().lower()
    env_override = os.getenv(partner.env_var)
    if env_override and env_override.strip():
        raw_url = env_override.strip()
    elif prop == "gainhelm":
        eff_source_tool = (source_tool or ((extra_params or {}).get("source_tool", "")) or "").strip()
        raw_url = resolve_gainhelm_partner_url(
            partner.key,
            tool_slug=eff_source_tool,
            default_url=partner.default_url,
        )
    else:
        raw_url = partner.default_url.strip()

    if not validate_affiliate_url(raw_url):
        raise ValueError(
            f"Invalid affiliate URL '{raw_url}' for partner '{partner.key}' (env: {partner.env_var})"
        )

    parsed = urllib.parse.urlsplit(raw_url)

    if prop == "prexvo":
        netloc_lower = parsed.netloc.lower()
        if any(agg in netloc_lower for agg in ("sovrn", "skimlinks", "viglink")):
            raise ValueError(
                f"Sub-affiliate aggregator redirects are prohibited on Prexvo: '{raw_url}'"
            )

    existing_query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_params = list(existing_query)
    existing_keys = {k for k, _ in query_params}

    if extra_params:
        for k, v in extra_params.items():
            if k in partner.supported_params or not partner.supported_params:
                query_params = [(qk, qv) for qk, qv in query_params if qk != k]
                query_params.append((k, str(v)))

    # Only append ph_tier if supported and tier is escalated beyond starter
    if "ph_tier" in partner.supported_params and value_tier and value_tier != "starter":
        if "ph_tier" not in existing_keys:
            query_params.append(("ph_tier", value_tier))

    if query_params:
        new_query = urllib.parse.urlencode(query_params)
    else:
        new_query = ""

    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
    )


def get_affiliates_for_property(property_id: str) -> Dict[str, AffiliatePartner]:
    """Returns partner dictionary for a declared property."""
    prop_clean = (property_id or "").strip().lower()
    if prop_clean in ("profithelm", "exchange1031"):
        return dict(PROFITHELM_AFFILIATES)
    elif prop_clean == "prexvo":
        return dict(PREXVO_AFFILIATES)
    elif prop_clean == "gainhelm":
        return dict(GAINHELM_AFFILIATES)
    elif prop_clean == "lienbond":
        return dict(LIENBOND_AFFILIATES)
    raise ValueError(f"Unknown property_id: '{property_id}'")


# ---------------------------------------------------------------------------
# Yield Scoring & Dynamic Route Resolver
# ---------------------------------------------------------------------------

def parse_bounty_estimate(bounty_str: str) -> Dict[str, float]:
    """
    Parses a bounty estimate string into numeric min, max, midpoint, and revshare flag.
    If dollar amounts ($) are present, extracts numeric dollar values.
    If only percentage numbers (%) are present, computes expected dollar value by multiplying percentage points by 2.0.
    Zero em-dashes. Zero en-dashes.
    """
    s = str(bounty_str or "").strip()
    is_revshare = 1.0 if "revshare" in s.lower() else 0.0

    dollar_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"\$\s*([\d,]+(?:\.\d+)?)", s)
    ]
    if dollar_matches:
        min_val = float(min(dollar_matches))
        max_val = float(max(dollar_matches))
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    pct_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"([\d,]+(?:\.\d+)?)\s*%", s)
    ]
    if pct_matches:
        min_val = float(min(pct_matches)) * 2.0
        max_val = float(max(pct_matches)) * 2.0
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    plain_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"([\d,]+(?:\.\d+)?)", s)
    ]
    if plain_matches:
        min_val = float(min(plain_matches))
        max_val = float(max(plain_matches))
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    return {
        "min": 0.0,
        "max": 0.0,
        "midpoint": 0.0,
        "is_revshare": is_revshare,
    }


EXTENDED_PARTNER_BOUNTY_ESTIMATES: Dict[str, str] = {
    "flexport": "$200-$500",
    "wealthfront": "$100-$250",
    "bench": "$150-$300",
    "guideline": "$150-$350",
    "sofi_refi": "$120",
    "laurel_road": "$200-$300",
    "juno": "$100-$175",
    "freetaxusa": "$20-$45",
    "public_com": "$50-$150",
    "avalara": "$200-$350",
    "brex": "$250-$500",
    "stripe_tax": "$150-$250",
    "pilot": "$200-$400",
    "deel": "$200-$500",
    "taxbit": "$40-$100",
}


def get_partner_bounty_midpoint(partner_or_key: Any) -> float:
    """
    Returns numeric midpoint bounty in USD for an AffiliatePartner, partner dict, or partner_key string.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(partner_or_key, AffiliatePartner):
        return float(parse_bounty_estimate(partner_or_key.bounty_est)["midpoint"])
    if isinstance(partner_or_key, dict):
        b_str = str(partner_or_key.get("bounty_est") or partner_or_key.get("commission_est") or "")
        if b_str:
            return float(parse_bounty_estimate(b_str)["midpoint"])
        k = str(partner_or_key.get("key") or partner_or_key.get("partner_key") or "").strip().lower()
    else:
        k = str(partner_or_key or "").strip().lower()

    if k in AFFILIATE_REGISTRY:
        return float(parse_bounty_estimate(AFFILIATE_REGISTRY[k].bounty_est)["midpoint"])
    if k in EXTENDED_PARTNER_BOUNTY_ESTIMATES:
        return float(parse_bounty_estimate(EXTENDED_PARTNER_BOUNTY_ESTIMATES[k])["midpoint"])
    return 120.0


def _extract_partner_engagement_record(
    partner_key: str,
    engagement_metrics: Optional[Dict[str, Any]],
    slug: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Extracts empirical engagement telemetry for a partner_key (and optional slug)
    from a flexible engagement_metrics dictionary structure.
    """
    if not engagement_metrics or not isinstance(engagement_metrics, dict):
        return None
    pk = str(partner_key or "").strip().lower()
    pk_alias = "sofi" if pk == "sofi_refi" else ("sofi_refi" if pk == "sofi" else pk)
    s_clean = str(slug or "").strip().lower()

    # 1. Check slug-scoped partner breakdown: by_slug[slug]["partners"][pk]
    by_slug = engagement_metrics.get("by_slug")
    if s_clean and isinstance(by_slug, dict):
        slug_entry = by_slug.get(s_clean)
        if isinstance(slug_entry, dict):
            partners_map = slug_entry.get("partners")
            if isinstance(partners_map, dict):
                for cand_k in (pk, pk_alias):
                    if isinstance(partners_map.get(cand_k), dict):
                        return partners_map[cand_k]

    # 2. Check direct slug["partners"][pk]
    partners_direct = engagement_metrics.get("partners")
    if isinstance(partners_direct, dict):
        for cand_k in (pk, pk_alias):
            if isinstance(partners_direct.get(cand_k), dict):
                return partners_direct[cand_k]

    # 3. Check property-wide partner breakdown: by_partner[pk]
    by_partner = engagement_metrics.get("by_partner")
    if isinstance(by_partner, dict):
        for cand_k in (pk, pk_alias):
            if isinstance(by_partner.get(cand_k), dict):
                return by_partner[cand_k]

    # 4. Check top-level mapping {partner_key: {...}}
    for cand_k in (pk, pk_alias):
        if isinstance(engagement_metrics.get(cand_k), dict):
            return engagement_metrics[cand_k]

    return None


def score_partner_yield(
    partner: Any,
    vault_status: Optional[str] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    slug: Optional[str] = None,
) -> float:
    """
    Scores expected yield of an affiliate partner weighted by operational status
    and optional empirical outbound CTA engagement / conversion yield telemetry.
    When engagement_metrics is None, preserves exact baseline status-weighted bounty midpoint.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(partner, dict):
        p_status = str(partner.get("status") or "")
        p_key = str(partner.get("key") or partner.get("partner_key") or "")
        midpoint = get_partner_bounty_midpoint(partner)
    else:
        p_status = str(getattr(partner, "status", "") or "")
        p_key = str(getattr(partner, "key", "") or "")
        midpoint = parse_bounty_estimate(getattr(partner, "bounty_est", ""))["midpoint"]

    effective_status = (vault_status or p_status or "").strip().lower()
    if effective_status in ("live", "active_direct"):
        weight = 1.0
    elif effective_status == "pending":
        weight = 0.35
    elif effective_status == "pending_expansion":
        weight = 0.25
    elif effective_status == "pending_p2":
        weight = 0.15
    else:
        weight = 0.0
    base_score = round(midpoint * weight, 4)

    if not engagement_metrics:
        return base_score

    emp = _extract_partner_engagement_record(p_key, engagement_metrics, slug=slug)
    if not isinstance(emp, dict):
        return base_score

    outbound_clicks = int(float(emp.get("outbound_clicks", emp.get("affiliate_clicks", emp.get("clicks", 0))) or 0))
    calc_interactions = int(float(emp.get("calculator_interactions", emp.get("interactions", emp.get("calculations", 0))) or 0))
    views = int(float(emp.get("views_exposed", emp.get("page_views", emp.get("impressions", 0))) or 0))
    cta_ctr = float(emp.get("cta_ctr", emp.get("conversion_rate", emp.get("ctr", 0.0))) or 0.0)
    intent_rate = float(emp.get("intent_to_click_rate", 0.0) or 0.0)
    emp_erpm = float(emp.get("empirical_erpm_usd", emp.get("empirical_erpm", 0.0)) or 0.0)
    realized_rev = float(emp.get("realized_revenue_usd", emp.get("est_revenue_usd", 0.0)) or 0.0)

    traffic_basis = max(1, views, calc_interactions, outbound_clicks)
    if cta_ctr <= 0.0 and outbound_clicks > 0:
        cta_ctr = outbound_clicks / float(traffic_basis)
    if intent_rate <= 0.0 and outbound_clicks > 0 and calc_interactions > 0:
        intent_rate = outbound_clicks / float(calc_interactions)

    # If the partner was exposed to meaningful traffic (>= 20 views/interactions) with zero clicks, dampen score
    if outbound_clicks == 0 and cta_ctr <= 0.0 and emp_erpm <= 0.0 and realized_rev <= 0.0:
        if max(views, calc_interactions) >= 20:
            return round(base_score * 0.65, 4)
        return base_score

    # Combine base yield with empirical CTA conversion rate, calculator intent rate, and realized eRPM
    ctr_multiplier = 1.0 + min(2.5, (cta_ctr / 0.04) * 0.55) + min(1.5, (intent_rate / 0.08) * 0.35)
    click_confidence = 1.0 + min(0.60, outbound_clicks * 0.03)
    erpm_bonus = min(midpoint * 1.5, emp_erpm * 0.35) + (realized_rev * 1.65)
    empirical_score = (base_score * ctr_multiplier * click_confidence) + (erpm_bonus * max(weight, 0.25))
    return round(empirical_score, 4)


def is_commercial_b2b_slug(slug: str) -> bool:
    """Determines whether a calculator slug belongs to the commercial B2B cluster."""
    s = (slug or "").strip().lower()
    if not s:
        return False
    if s in COMMERCIAL_B2B_SLUGS:
        return True
    if s in RETAIL_TAX_SLUGS:
        return False
    b2b_tokens = (
        "section-1031",
        "1031",
        "section-179",
        "179",
        "macrs",
        "depreciation",
        "equipment",
        "treasury",
        "yield",
        "tbill",
        "qsbs",
        "1202",
        "corporate-amt",
        "r-and-d",
        "runway",
        "burn",
        "saas",
        "payroll",
    )
    return any(tok in s for tok in b2b_tokens)


def is_restricted_public_service_slug(slug: str, query: str = "") -> bool:
    """
    Determines whether a Prexvo slug or query targets a restricted public-service
    or statutory hardship page (such as PSLF, SAVE litigation/forbearance, disability
    discharge, borrower defense, teacher loan forgiveness, or poverty-guideline relief)
    where commercial private refinancing offers must be suppressed to preserve YMYL guardrails.
    Zero em-dashes. Zero en-dashes.
    """
    s = (slug or "").strip().lower()
    q = (query or "").strip().lower()
    if s in PREXVO_RESTRICTED_PUBLIC_SERVICE_SLUGS:
        return True
    combined = f"{s} {q}".strip()
    if not combined:
        return False
    return any(tok in combined for tok in PREXVO_RESTRICTED_PUBLIC_SERVICE_TOKENS)


def _strip_balanced_html_blocks(
    html_text: str,
    tag_name: str,
    open_tag_regex: str,
    replacement: str = "",
    replace_first_only: bool = False,
) -> str:
    """
    Removes or replaces balanced `<tag_name ...>...</tag_name>` blocks matching `open_tag_regex`
    without altering any bytes outside the matched elements (preserving HTML byte convergence).
    Zero em-dashes. Zero en-dashes.
    """
    if not html_text:
        return html_text
    open_pat = re.compile(open_tag_regex, flags=re.IGNORECASE | re.DOTALL)
    any_tag_pat = re.compile(
        rf"<(/?){re.escape(tag_name)}\b[^>]*>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    out: List[str] = []
    pos = 0
    replaced_count = 0
    while pos < len(html_text):
        m_open = open_pat.search(html_text, pos)
        if m_open is None:
            out.append(html_text[pos:])
            break
        start_idx = m_open.start()
        out.append(html_text[pos:start_idx])
        depth = 1
        scan_pos = m_open.end()
        end_idx = m_open.end()
        for m_tok in any_tag_pat.finditer(html_text, scan_pos):
            is_close = bool(m_tok.group(1))
            if is_close:
                depth -= 1
                if depth == 0:
                    end_idx = m_tok.end()
                    break
            else:
                if not m_tok.group(0).rstrip().endswith("/>"):
                    depth += 1
        if replacement and (not replace_first_only or replaced_count == 0):
            out.append(replacement)
            replaced_count += 1
        pos = end_idx
    return "".join(out)


def strip_commercial_affiliate_blocks_for_restricted_ymyl(html_content: str) -> str:
    """
    Deterministically strips all commercial affiliate /r/ links, inline CTAs, comparison
    table CTA bars, overlay partner offers, and commercial partner card sections from a
    restricted public-service YMYL page while preserving or inserting the compliant
    Title IV Public Service Protection guardrail section.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_content, str) or not html_content:
        return html_content

    guardrail_section = (
        '<section class="refinance-partner-section ymyl-public-service-guardrail" '
        'data-commercial-offers="none" data-restricted-public-service="true" '
        'data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">\n'
        '      <div class="partner-card" style="border: 1px solid var(--border-subtle);">\n'
        '        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Title IV Public Service Protection</span>\n'
        '        <h3 class="partner-title" style="margin-top: 0.25rem;">Title IV Loan Preservation</h3>\n'
        '        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">Direct consolidation and federal repayment plans maintain statutory interest subsidies and public service debt relief eligibility under 34 CFR Part 685.</p>\n'
        '        <span class="partner-status-note" style="display: inline-block; font-size: 0.8125rem; color: var(--text-muted);">\n'
        '          Commercial private lender offers are strictly suppressed on restricted public-service and statutory hardship pages.\n'
        '        </span>\n'
        '      </div>\n'
        '    </section>'
    )

    updated = html_content
    # 1. Remove commercial inline calculator CTAs and comparison table CTA bars
    updated = _strip_balanced_html_blocks(
        updated,
        "div",
        r'<div\b[^>]*class=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>',
        replacement="",
    )
    updated = _strip_balanced_html_blocks(
        updated,
        "div",
        r'<div\b[^>]*class=["\'][^"\']*\bcomparison-table-cta-bar\b[^"\']*["\'][^>]*>',
        replacement="",
    )
    # 2. Remove commercial overlay partner offers
    updated = _strip_balanced_html_blocks(
        updated,
        "section",
        r'<section\b[^>]*class=["\'][^"\']*\boverlay-partner-offer\b[^"\']*["\'][^>]*>',
        replacement="",
    )
    # 3. Replace commercial partner sections with the durable non-overlay guardrail section
    has_durable_guardrail = bool(
        re.search(
            r'<section\b[^>]*class=["\'][^"\']*\brefinance-partner-section\b[^"\']*\bymyl-public-service-guardrail\b[^"\']*["\']',
            updated,
            flags=re.IGNORECASE,
        )
    )
    updated = _strip_balanced_html_blocks(
        updated,
        "section",
        r'<section\b(?![^>]*ymyl-public-service-guardrail)[^>]*class=["\'][^"\']*\b(?:refinance-partner-section|partners-section|affiliates-section|affiliate-section)\b[^"\']*["\'][^>]*>',
        replacement="" if has_durable_guardrail else guardrail_section,
        replace_first_only=True,
    )
    if (
        not has_durable_guardrail
        and 'class="refinance-partner-section ymyl-public-service-guardrail"' not in updated
        and 'data-restricted-public-service="true"' not in updated
        and "</main>" in updated
    ):
        updated = updated.replace("</main>", f"\n    {guardrail_section}\n</main>", 1)
    # 4. Final fail-closed safety net: strip any stray <a href="/r/...">...</a> links
    if "/r/" in updated:
        updated = re.sub(
            r'<a\s+[^>]*href=["\']/r/[a-z0-9_]+[^"\']*["\'][^>]*>.*?</a>',
            "",
            updated,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return updated


MONETIZATION_VAULT_PATH = Path(__file__).resolve().parent / "monetization_vault.json"
_VAULT_LIVE_PARTNERS_CACHE: Dict[Tuple[str, int, int], Dict[str, Set[str]]] = {}
_PARTNER_KEY_CANONICAL_ALIASES: Dict[str, str] = {
    "efile": "efile_com",
    "eztaxreturn": "eztaxreturn_com",
}


def _normalize_vault_property_id(property_id: str) -> str:
    prop = str(property_id or "").strip().lower()
    if prop == "exchange1031":
        return "profithelm"
    return prop


def _load_all_live_partner_keys_by_property(
    vault_path: Optional[Any] = None,
    vault_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Set[str]]:
    """
    Loads the live partner key sets for every property defined in monetization_vault.json.
    Caches by (resolved_path, mtime_ns, size) so edits or monkeypatches take effect immediately
    without hardcoded tenant lists (designed for 50+ tenants).
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(vault_data, dict):
        props = vault_data.get("properties")
        out: Dict[str, Set[str]] = {}
        if isinstance(props, dict):
            for p_id, p_meta in props.items():
                p_clean = _normalize_vault_property_id(str(p_id))
                live_set: Set[str] = set()
                partners = (p_meta or {}).get("partners") if isinstance(p_meta, dict) else None
                if isinstance(partners, dict):
                    for pk, p_entry in partners.items():
                        if isinstance(p_entry, dict) and str(p_entry.get("status") or "").strip().lower() in ("live", "active_direct"):
                            norm_pk = str(pk).strip().lower().replace("-", "_")
                            live_set.add(norm_pk)
                out[p_clean] = live_set
        return out

    v_path = Path(vault_path) if vault_path is not None else Path(MONETIZATION_VAULT_PATH)
    try:
        st = v_path.stat()
    except OSError:
        return {}
    cache_key = (str(v_path.resolve()), int(st.st_mtime_ns), int(st.st_size))
    cached = _VAULT_LIVE_PARTNERS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        parsed = json.loads(v_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = _load_all_live_partner_keys_by_property(vault_data=parsed)
    _VAULT_LIVE_PARTNERS_CACHE.clear()
    _VAULT_LIVE_PARTNERS_CACHE[cache_key] = out
    return out


def load_live_partner_keys_from_vault(
    property_id: str,
    vault_path: Optional[Any] = None,
    vault_data: Optional[Dict[str, Any]] = None,
) -> Set[str]:
    """
    Returns the exact set of partner keys whose status in monetization_vault.json is 'live'
    for the requested property (fail-closed: empty set if property or vault is missing).
    Zero em-dashes. Zero en-dashes.
    """
    prop = _normalize_vault_property_id(property_id)
    if not prop:
        return set()
    by_prop = _load_all_live_partner_keys_by_property(vault_path=vault_path, vault_data=vault_data)
    live_keys = set(by_prop.get(prop) or ())
    for alias_k, canon_k in _PARTNER_KEY_CANONICAL_ALIASES.items():
        if canon_k in live_keys:
            live_keys.add(alias_k)
    return live_keys


def is_partner_live_in_vault(
    property_id: str,
    partner_key: str,
    vault_path: Optional[Any] = None,
    vault_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Returns True ONLY when partner_key has status == 'live' for property_id in monetization_vault.json.
    Zero em-dashes. Zero en-dashes.
    """
    pk_clean = str(partner_key or "").strip().lower().replace("-", "_")
    if not pk_clean:
        return False
    live_keys = load_live_partner_keys_from_vault(
        property_id=property_id,
        vault_path=vault_path,
        vault_data=vault_data,
    )
    if pk_clean in live_keys:
        return True
    canon = _PARTNER_KEY_CANONICAL_ALIASES.get(pk_clean)
    return bool(canon and canon in live_keys)


def _format_clean_usd_label(amount: float) -> str:
    """Formats a USD price cleanly without trailing .00 for whole-dollar amounts."""
    f = float(amount)
    return str(int(round(f))) if abs(f - round(f)) < 1e-6 else f"{f:.2f}"


def build_step1_preview_controls_html(
    property_id: str,
    slug: str = "",
    query: str = "",
    baseline_output: Optional[float] = None,
    display_output: str = "",
    statutory_authority: str = "",
) -> str:
    """
    Renders Step 1 (Free, On-Screen Only) inline 'Preview Workpaper' toggle button and
    expandable preview container (#workpaper-preview-panel). Zero email inputs, zero Turnstile.
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib

    prop = _normalize_vault_property_id(property_id) or "profithelm"
    clean_slug = str(slug or "").strip().strip("/").lower() or "index"
    if clean_slug.startswith("tools/"):
        clean_slug = clean_slug[len("tools/") :]
    is_restricted = is_restricted_public_service_slug(clean_slug, query)
    safe_slug = html_lib.escape(clean_slug)
    safe_prop = html_lib.escape(prop)
    safe_out = html_lib.escape(str(display_output or (f"{baseline_output:,.2f}" if baseline_output is not None else "Computed Live")))
    raw_preview_auth = str(statutory_authority or "").strip()
    if prop == "gainhelm" and (not raw_preview_auth or has_gainhelm_cross_framework_leak(raw_preview_auth, slug=clean_slug)):
        raw_preview_auth = str(get_gainhelm_framework_profile(slug=clean_slug).get("statutory_authority") or "").strip()
    safe_auth = html_lib.escape(raw_preview_auth or "Deterministic Statutory Model")
    locked_row = (
        ""
        if is_restricted
        else (
            '        <div class="workpaper-preview-row workpaper-preview-locked">'
            '<strong>Paid Schedules (Locked):</strong> Multi-row sensitivity schedule, CSV export, and JSON statutory data pack available in Step 2 below.'
            '</div>\n'
        )
    )
    return (
        f'      <div class="workpaper-preview-controls" data-step="1" data-property-id="{safe_prop}" data-tool-slug="{safe_slug}" style="margin-top: 12px;">\n'
        f'        <button type="button" id="btn-preview-workpaper" class="btn-secondary touch-target preview-workpaper-btn" '
        f'data-workpaper-preview="1" data-tool-slug="{safe_slug}" aria-expanded="false" aria-controls="workpaper-preview-panel">'
        f'Preview Workpaper</button>\n'
        f'        <div id="workpaper-preview-panel" class="workpaper-preview-panel" hidden data-tool-slug="{safe_slug}" '
        f'style="margin-top: 10px; padding: 12px 14px; border-radius: 8px; border: 1px dashed var(--border-strong); background: var(--bg-inset); font-size: 13px; line-height: 1.5;">\n'
        f'          <div class="workpaper-preview-row"><strong>On-Screen Headline Output:</strong> <span id="workpaper-preview-headline">{safe_out}</span></div>\n'
        f'          <div class="workpaper-preview-row"><strong>Statutory Basis:</strong> {safe_auth}</div>\n'
        f'{locked_row}'
        f'        </div>\n'
        f'      </div>'
    )


def build_workpaper_unlock_card_html(
    property_id: str,
    slug: str = "",
    query: str = "",
    topic_label: str = "",
    statutory_authority: str = "",
    baseline_amount: Optional[float] = None,
    repo_root: Optional[Any] = None,
) -> str:
    """
    Renders Step 2: a single full-width #workpaper-unlock-card directly below .calc-grid
    with Quick Worksheet and Full Workpaper & Data Pack buttons priced dynamically from pricing.py.
    Suppressed completely on restricted public-service YMYL pages (PSLF, SAVE litigation, buyback).
    Zero email inputs. Zero Turnstile. Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib
    from pseofactory.pricing import resolve_offer_pricing

    prop = _normalize_vault_property_id(property_id) or "profithelm"
    clean_slug = str(slug or "").strip().strip("/").lower()
    if clean_slug.startswith("tools/"):
        clean_slug = clean_slug[len("tools/") :]
    if is_restricted_public_service_slug(clean_slug, query):
        return ""
    if clean_slug in ("about", "privacy", "terms", "disclaimers", "methodology", "partners", "tools", "tools-directory", "404"):
        return ""

    eff_slug = clean_slug or "general"
    gh_prof: Dict[str, Any] = get_gainhelm_framework_profile(slug=eff_slug) if prop == "gainhelm" else {}
    gh_fw_sku = str(gh_prof.get("offer_sku") or "").strip() if gh_prof else ""
    quick_offer = resolve_offer_pricing(prop, tier_kind="quick", slug=eff_slug, repo_root=repo_root)
    full_offer = resolve_offer_pricing(prop, tier_kind="full", slug=eff_slug, sku=gh_fw_sku, repo_root=repo_root)

    quick_sku = str(quick_offer["sku"])
    full_sku = str(gh_fw_sku or full_offer["sku"])
    quick_price_usd = float(quick_offer["price_usd"])
    full_price_usd = float(full_offer["price_usd"])
    quick_price_int = int(round(quick_price_usd))
    full_price_int = int(round(full_price_usd))
    quick_price_str = _format_clean_usd_label(quick_price_usd)
    full_price_str = _format_clean_usd_label(full_price_usd)

    raw_auth = str(statutory_authority or "").strip()
    if gh_prof:
        if not raw_auth or has_gainhelm_cross_framework_leak(raw_auth, slug=eff_slug):
            raw_auth = str(gh_prof.get("statutory_authority") or "").strip()
    eff_auth = str(raw_auth or (gh_prof.get("statutory_authority") if gh_prof else "") or full_offer.get("statutory_authority") or "Deterministic Statutory Model").strip()
    amt_int = int(round(float(baseline_amount))) if baseline_amount is not None else 0
    amt_qs = f"&amp;amount={amt_int}" if amt_int > 0 else ""

    slug_param = html_lib.escape(eff_slug)
    quick_href = f"/api/lead-capture?checkout=1&amp;sku={html_lib.escape(quick_sku)}&amp;tool_slug={slug_param}{amt_qs}&amp;redirect=1"
    full_href = f"/api/lead-capture?checkout=1&amp;sku={html_lib.escape(full_sku)}&amp;tool_slug={slug_param}{amt_qs}&amp;redirect=1"

    safe_prop = html_lib.escape(prop)
    raw_topic = str(topic_label or "").strip()
    if gh_prof and (not raw_topic or has_gainhelm_cross_framework_leak(raw_topic, slug=eff_slug)):
        raw_topic = str(gh_prof.get("offer_title") or "").strip()
    raw_topic = str(raw_topic or (gh_prof.get("offer_title") if gh_prof else "") or full_offer.get("title") or "Calculation Workpaper").strip()
    safe_topic = html_lib.escape(raw_topic)
    unlock_heading = (
        f"Export {safe_topic}"
        if "workpaper" in raw_topic.lower()
        else f"Export {safe_topic} Workpaper &amp; Data Pack"
    )
    safe_auth = html_lib.escape(eff_auth)
    prexvo_refi_note = ""
    if prop == "prexvo" and any(tok in f"{clean_slug} {query}".lower() for tok in ("refinance", "refinancing")):
        prexvo_refi_note = (
            '      <p class="ymyl-refinance-warning" style="font-size: 12.5px; color: var(--text-muted); margin: 10px 0 0 0;">'
            'Federal Student Loan Notice: Refinancing federal student loans into private loans permanently eliminates federal protections '
            '(waives federal protections including Income-Driven Repayment and PSLF eligibility) under 34 CFR Part 685.'
            '</p>\n'
        )

    return (
        f'<section id="workpaper-unlock-card" class="workpaper-unlock-card card pseo-card" '
        f'data-mechanic="workpaper_unlock_funnel" data-first-party-checkout="true" '
        f'data-property="{safe_prop}" data-property-id="{safe_prop}" data-tool-slug="{slug_param}" '
        f'data-quick-sku="{html_lib.escape(quick_sku)}" data-quick-price="{quick_price_int}" '
        f'data-full-sku="{html_lib.escape(full_sku)}" data-full-price="{full_price_int}" '
        f'data-offer-sku="{html_lib.escape(full_sku)}" data-offer-price="{full_price_int}" '
        f'data-calculated-amount="{amt_int}">\n'
        f'      <div class="workpaper-unlock-header">\n'
        f'        <h3>{unlock_heading}</h3>\n'
        f'        <p class="workpaper-unlock-subtitle">Instant Stripe Checkout preserving your active calculator inputs and outputs under {safe_auth}.</p>\n'
        f'      </div>\n'
        f'      <div class="workpaper-unlock-actions">\n'
        f'        <a id="btn-workpaper-quick-checkout" rel="nofollow" href="{quick_href}" '
        f'class="btn-cta touch-target workpaper-cta-primary" data-checkout-trigger="1" '
        f'data-offer-sku="{html_lib.escape(quick_sku)}" data-offer-price="{quick_price_int}" '
        f'data-cta-slot="workpaper_quick_checkout_cta">Quick Worksheet (${quick_price_str})</a>\n'
        f'        <a id="btn-workpaper-full-checkout" rel="nofollow" href="{full_href}" '
        f'class="btn-secondary touch-target workpaper-cta-secondary" data-checkout-trigger="1" '
        f'data-offer-sku="{html_lib.escape(full_sku)}" data-offer-price="{full_price_int}" '
        f'data-cta-slot="workpaper_full_checkout_cta">Full Workpaper &amp; Data Pack (${full_price_str})</a>\n'
        f'      </div>\n'
        f'{prexvo_refi_note}'
        f'      <div id="workpaper-checkout-status" class="workpaper-checkout-status" role="status" aria-live="polite"></div>\n'
        f'    </section>'
    )


def build_contextual_referral_card_html(
    property_id: str,
    slug: str = "",
    query: str = "",
    gsc_metrics: Optional[Dict[str, Any]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    page_archetype: str = "",
    forced_partner_key: str = "",
    gsc_repositioned: bool = False,
    gsc_tier: str = "",
) -> str:
    """
    Renders Step 3: one compact <section class="contextual-referral-card"> below Step 2
    ONLY when an intent-matched partner has status == 'live' in monetization_vault.json,
    with inline FTC 16 CFR Part 255 disclosure.
    Returns '' (zero referral sections and zero placeholder boxes) when no live partner matches
    or on restricted public-service YMYL pages.
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib

    prop = _normalize_vault_property_id(property_id) or "profithelm"
    clean_slug = str(slug or "").strip().strip("/").lower()
    if clean_slug.startswith("tools/"):
        clean_slug = clean_slug[len("tools/") :]
    if is_restricted_public_service_slug(clean_slug, query):
        return ""
    if prop == "prexvo":
        combined_lower = f"{clean_slug} {query}".lower()
        if not any(tok in combined_lower for tok in ("refinance", "refinancing")):
            return ""

    live_keys = load_live_partner_keys_from_vault(property_id=prop)
    if not live_keys:
        return ""

    roster_info = bind_asset_partner_roster(
        property_id=prop,
        slug=clean_slug or "index",
        query=query,
        page_archetype=page_archetype,
        gsc_metrics=gsc_metrics,
        engagement_metrics=engagement_metrics,
    )
    roster_models = [
        str(o.get("partnership_model") or "")
        for o in (roster_info.get("roster_offers") or [])
        if isinstance(o, dict) and o.get("partnership_model")
    ]
    slot_plan_ref = roster_info.get("slot_plan") or {}
    promoted_pk_ref = str(slot_plan_ref.get("promoted_partner_key") or "").strip().lower()
    registry = _property_partner_registry(prop)

    p_key = ""
    p_obj = None
    if forced_partner_key and is_partner_live_in_vault(prop, forced_partner_key):
        p_key = str(forced_partner_key).strip().lower()
        p_obj = registry.get(p_key)
    elif (slot_plan_ref.get("gsc_repositioned") or engagement_metrics) and promoted_pk_ref and is_partner_live_in_vault(prop, promoted_pk_ref):
        p_key = promoted_pk_ref
        p_obj = registry.get(p_key)

    if not p_key:
        p_obj = resolve_optimal_partner_for_slug(
            prop,
            clean_slug or "index",
            engagement_metrics=engagement_metrics,
        )
        if p_obj is not None and is_partner_live_in_vault(prop, p_obj.key):
            p_key = p_obj.key
        else:
            live_offer = next(
                (
                    o
                    for o in (roster_info.get("roster_offers") or [])
                    if isinstance(o, dict) and is_partner_live_in_vault(prop, str(o.get("partner_key") or ""))
                ),
                None,
            )
            if not live_offer:
                return ""
            p_key = str(live_offer["partner_key"])
            p_obj = registry.get(p_key)

    if p_obj is not None:
        ctx_copy = resolve_contextual_partner_offer_copy(
            partner_key=p_key,
            p_obj=p_obj,
            slug=clean_slug or "index",
            property_id=prop,
        )
        partner_name = str(ctx_copy.get("name") or p_obj.name)
        partner_desc = str(ctx_copy.get("description") or p_obj.description)
        cta_text = str(ctx_copy.get("cta_text") or p_obj.cta_text or f"Explore {partner_name}")
        p_model = str(p_obj.partnership_model or "CPA_BOUNTY")
    else:
        partner_name = COMPANY_BRAND_BY_PARTNER_KEY.get(p_key, p_key.replace("_", " ").title())
        partner_desc = "Verified commercial partner matched to this calculation."
        cta_text = f"Explore {partner_name}"
        p_model = "CPA_BOUNTY"

    slug_id = (clean_slug or "index").replace("/", "-")
    brand_str = COMPANY_BRAND_BY_PARTNER_KEY.get(p_key, partner_name)
    href = f"/r/{html_lib.escape(p_key)}?source_tool={html_lib.escape(slug_id)}&amp;subid={html_lib.escape(slug_id)}_referral&amp;cta_slot=contextual_referral"
    disc_dict = (
        GAINHELM_DISCLOSURES
        if prop == "gainhelm"
        else (LIENBOND_DISCLOSURES if prop == "lienbond" else (PREXVO_DISCLOSURES if prop == "prexvo" else PROFITHELM_DISCLOSURES))
    )
    ftc_disc = str(
        disc_dict.get("ftc_disclosure")
        or "FTC 16 CFR Part 255 Disclosure: We may earn a referral fee if you engage a matched partner at no extra cost to you."
    ).strip()

    extra_attr = ""
    if prop == "prexvo" and any(tok in f"{clean_slug} {query}".lower() for tok in ("refinance", "refinancing")):
        extra_attr = ' data-commercial-offers="compliant-refinance"'
    if gsc_repositioned or slot_plan_ref.get("gsc_repositioned"):
        eff_gsc_tier = str(gsc_tier or slot_plan_ref.get("gsc_opportunity_tier") or "STRIKING_DISTANCE_PROMOTE")
        extra_attr += f' data-gsc-repositioned="true" data-gsc-tier="{html_lib.escape(eff_gsc_tier)}"'
    models_csv = ",".join(dict.fromkeys([m for m in ([p_model] + roster_models) if m]))

    return (
        f'<section class="contextual-referral-card card pseo-card" '
        f'data-mechanic="compliant_intent_monetization" data-property="{html_lib.escape(prop)}"{extra_attr} '
        f'data-partner="{html_lib.escape(p_key)}" data-company-brand="{html_lib.escape(brand_str)}" '
        f'data-partnership-model="{html_lib.escape(p_model)}" data-partner-models="{html_lib.escape(models_csv)}">\n'
        f'      <div class="contextual-referral-body">\n'
        f'        <div class="contextual-referral-copy">\n'
        f'          <span class="contextual-referral-badge">Optional Partner Resource</span>\n'
        f'          <div class="contextual-referral-title">{html_lib.escape(partner_name)}</div>\n'
        f'          <p class="contextual-referral-desc">{html_lib.escape(partner_desc)}</p>\n'
        f'        </div>\n'
        f'        <a href="{href}" rel="noopener sponsored nofollow" target="_blank" '
        f'data-partner="{html_lib.escape(p_key)}" data-company-brand="{html_lib.escape(brand_str)}" '
        f'data-partnership-model="{html_lib.escape(p_model)}" data-tool="{html_lib.escape(slug_id)}" '
        f'data-subid="{html_lib.escape(slug_id)}_referral" data-status="live" '
        f'data-cta-slot="contextual_referral" class="btn-secondary partner-cta affiliate-cta-link touch-target">'
        f'{html_lib.escape(cta_text)}</a>\n'
        f'      </div>\n'
        f'      <p class="affiliate-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 8px; margin-bottom: 0;">'
        f'{html_lib.escape(ftc_disc)}</p>\n'
        f'    </section>'
    )


def build_first_party_workpaper_cta_html(
    property_id: str,
    slug: str = "",
    query: str = "",
    slot: str = "section",
    reg_drawer_html: str = "",
    section_id_attr: str = "",
) -> str:
    """
    Delegates to build_workpaper_unlock_card_html so all callers emit the single canonical
    #workpaper-unlock-card priced from pricing.py with zero #partner-registration-drawer.
    Zero em-dashes. Zero en-dashes.
    """
    _ = slot, reg_drawer_html, section_id_attr
    return build_workpaper_unlock_card_html(
        property_id=property_id,
        slug=slug,
        query=query,
    )


def _strip_balanced_blocks_matching(
    html_text: str,
    tag_name: str,
    open_pattern: str,
    predicate: Any,
    replacer: Optional[Any] = None,
) -> str:
    """
    Scans balanced HTML blocks of `tag_name` whose opening tag matches `open_pattern`.
    For each block where `predicate(block_html)` is True, replaces it with `replacer(block_html)`
    (or empty string when `replacer` is None).
    """
    if not html_text:
        return html_text
    open_re = re.compile(open_pattern, flags=re.IGNORECASE)
    token_re = re.compile(rf"</?{tag_name}\b[^>]*>", flags=re.IGNORECASE)
    out: List[str] = []
    pos = 0
    while True:
        m = open_re.search(html_text, pos)
        if not m:
            out.append(html_text[pos:])
            break
        start = m.start()
        depth = 0
        end = -1
        for tok in token_re.finditer(html_text, start):
            tok_txt = tok.group(0).lower()
            if tok_txt.startswith(f"</{tag_name}"):
                depth -= 1
                if depth == 0:
                    end = tok.end()
                    break
            elif not tok_txt.endswith("/>"):
                depth += 1
        if end == -1:
            out.append(html_text[pos:])
            break
        block = html_text[start:end]
        out.append(html_text[pos:start])
        if predicate(block):
            out.append(replacer(block) if replacer is not None else "")
        else:
            out.append(block)
        pos = end
    return "".join(out)


def strip_unapproved_partner_ctas_from_html(
    html_content: str,
    property_id: str = "profithelm",
    slug: str = "",
    query: str = "",
    vault_path: Optional[Any] = None,
    vault_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Fail-closed HTML filter guaranteeing zero outbound /r/<partner> CTA links or cards
    for any partner whose status in monetization_vault.json is NOT 'live'.
    Replaces dead unapproved partner sections with the tenant's working 1st-party Stripe
    Checkout workpaper CTA (while preserving #partner-registration-drawer and strict
    Title IV YMYL guardrails on restricted pages).
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_content, str) or not html_content:
        return html_content
    if "/r/" not in html_content and "overlay-partner-offer" not in html_content:
        return html_content

    prop = _normalize_vault_property_id(property_id) or "profithelm"
    live_keys = load_live_partner_keys_from_vault(
        property_id=prop,
        vault_path=vault_path,
        vault_data=vault_data,
    )
    eff_slug = (slug or _extract_tool_slug_from_html_head(html_content) or "").strip().lower()
    r_href_re = re.compile(r'href=["\'](?:https?://[^/"\']+)?/r/([a-z0-9_-]+)', flags=re.IGNORECASE)
    r_anchor_re = re.compile(
        r'<a\b[^>]*href=["\'](?:https?://[^/"\']+)?/r/([a-z0-9_-]+)[^"\']*["\'][^>]*>.*?</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def _extract_r_keys(fragment: str) -> List[str]:
        return [m.group(1).strip().lower().replace("-", "_") for m in r_href_re.finditer(fragment)]

    def _is_key_live(pk: str) -> bool:
        norm = pk.strip().lower().replace("-", "_")
        if norm in live_keys:
            return True
        canon = _PARTNER_KEY_CANONICAL_ALIASES.get(norm)
        return bool(canon and canon in live_keys)

    def _has_unapproved_r(fragment: str) -> bool:
        keys = _extract_r_keys(fragment)
        return any(not _is_key_live(k) for k in keys)

    def _has_live_r(fragment: str) -> bool:
        keys = _extract_r_keys(fragment)
        return any(_is_key_live(k) for k in keys)

    def _is_suppressed_ymyl_fragment(fragment: str) -> bool:
        return (
            'data-restricted-public-service="true"' in fragment
            or 'data-commercial-offers="none"' in fragment
            or 'data-commercial-offers="suppressed-default"' in fragment
            or "ymyl-public-service-guardrail" in fragment
        )

    page_is_restricted_ymyl = _is_suppressed_ymyl_fragment(html_content) or is_restricted_public_service_slug(eff_slug, query)

    updated = html_content

    # 1. Strip unapproved inline calculator CTAs and comparison table CTA bars
    updated = _strip_balanced_blocks_matching(
        updated,
        "div",
        r'<div\b[^>]*class=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>',
        predicate=_has_unapproved_r,
    )
    updated = _strip_balanced_blocks_matching(
        updated,
        "div",
        r'<div\b[^>]*class=["\'][^"\']*\bcomparison-table-cta-bar\b[^"\']*["\'][^>]*>',
        predicate=_has_unapproved_r,
    )

    # 2. Strip unapproved overlay partner offers
    def _overlay_is_unapproved(block: str) -> bool:
        if _has_unapproved_r(block):
            return True
        if _has_live_r(block):
            return False
        dp_m = re.search(r'data-partner=["\']([a-z0-9_-]+)["\']', block, flags=re.IGNORECASE)
        if dp_m:
            return not _is_key_live(dp_m.group(1))
        return False

    updated = _strip_balanced_blocks_matching(
        updated,
        "section",
        r'<section\b[^>]*class=["\'][^"\']*\boverlay-partner-offer\b[^"\']*["\'][^>]*>',
        predicate=_overlay_is_unapproved,
    )

    # 3. Handle commercial partner sections (<section> and <aside>)
    first_party_section_emitted = 'data-first-party-checkout="true"' in updated

    def _clean_partner_section(sec_block: str) -> str:
        nonlocal first_party_section_emitted
        if _is_suppressed_ymyl_fragment(sec_block) or 'data-first-party-checkout="true"' in sec_block:
            return sec_block
        if not _has_unapproved_r(sec_block):
            return sec_block

        # Strip unapproved individual partner cards and table rows inside the section first
        cleaned = _strip_balanced_blocks_matching(
            sec_block,
            "div",
            r'<div\b[^>]*class=["\'][^"\']*\b(?:partner-card|affiliate-card)\b[^"\']*["\'][^>]*>',
            predicate=_has_unapproved_r,
        )
        cleaned = re.sub(
            r"<tr\b[^>]*>.*?</tr>",
            lambda tr_m: "" if _has_unapproved_r(tr_m.group(0)) else tr_m.group(0),
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Remove now-empty comparison tables inside partner sections
        cleaned = re.sub(
            r'<div\s+class=["\']table-wrap["\'][^>]*>\s*<table\b[^>]*>[\s\S]*?<tbody[^>]*>\s*</tbody>\s*</table>\s*</div>',
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"<table\b[^>]*>[\s\S]*?<tbody[^>]*>\s*</tbody>\s*</table>",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # Remove any remaining stray unapproved <a> inside this section
        cleaned = r_anchor_re.sub(
            lambda a_m: a_m.group(0) if _is_key_live(a_m.group(1)) else "",
            cleaned,
        )

        # If the section still contains live partner links, clean stale unapproved data-partner* attrs and keep it
        if _has_live_r(cleaned):
            remaining_live = list(dict.fromkeys(k for k in _extract_r_keys(cleaned) if _is_key_live(k)))
            lead_live = remaining_live[0] if remaining_live else ""
            sec_open_m2 = re.match(r"<(?:section|aside)\b[^>]*>", cleaned, flags=re.IGNORECASE)
            if sec_open_m2 and lead_live:
                open_tag = sec_open_m2.group(0)
                new_open = open_tag
                for attr_name in ("data-partner", "data-primary-partner"):
                    am = re.search(rf'{attr_name}=["\']([a-z0-9_-]+)["\']', new_open, flags=re.IGNORECASE)
                    if am and not _is_key_live(am.group(1)):
                        new_open = re.sub(
                            rf'{attr_name}=["\'][^"\']*["\']',
                            f'{attr_name}="{lead_live}"',
                            new_open,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                rm = re.search(r'data-partner-roster=["\']([^"\']+)["\']', new_open, flags=re.IGNORECASE)
                if rm:
                    kept_roster = [
                        rk.strip().lower()
                        for rk in rm.group(1).split(",")
                        if rk.strip() and _is_key_live(rk.strip())
                    ]
                    if not kept_roster:
                        kept_roster = remaining_live
                    new_open = re.sub(
                        r'data-partner-roster=["\'][^"\']*["\']',
                        f'data-partner-roster="{",".join(dict.fromkeys(kept_roster))}"',
                        new_open,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                if new_open != open_tag:
                    cleaned = new_open + cleaned[sec_open_m2.end() :]
            return cleaned

        # If this section ALREADY has first-party Stripe Checkout CTA links (e.g. LienBond homepage aside),
        # keep it cleanly without the dead partner table
        if "/api/lead-capture?checkout=1" in cleaned:
            return cleaned

        # Otherwise replace dead partner section with the tenant's 1st-party Stripe Checkout workpaper CTA
        if page_is_restricted_ymyl:
            return ""
        sec_open_m = re.match(r"<(?:section|aside)\b[^>]*>", sec_block, flags=re.IGNORECASE)
        sec_id_attr = _extract_section_id_attr(sec_open_m.group(0) if sec_open_m else "")
        reg_drawer = _extract_partner_registration_drawer(sec_block)
        if first_party_section_emitted:
            return reg_drawer
        first_party_section_emitted = True
        return build_first_party_workpaper_cta_html(
            property_id=prop,
            slug=eff_slug,
            query=query,
            slot="section",
            reg_drawer_html=reg_drawer,
            section_id_attr=sec_id_attr,
        )

    partner_sec_open_pat = (
        r'<section\b[^>]*class=["\'][^"\']*\b'
        r'(?:affiliate-cta-section|affiliates-section|affiliate-section|refinance-partner-section|partners-section|partner-cta-section)'
        r'\b[^"\']*["\'][^>]*>'
    )
    updated = _strip_balanced_blocks_matching(
        updated,
        "section",
        partner_sec_open_pat,
        predicate=_has_unapproved_r,
        replacer=_clean_partner_section,
    )
    partner_aside_open_pat = (
        r'<aside\b[^>]*class=["\'][^"\']*\b'
        r'(?:affiliate-cta-section|affiliates-section|affiliate-section|refinance-partner-section|partners-section|partner-cta-section)'
        r'\b[^"\']*["\'][^>]*>'
    )
    updated = _strip_balanced_blocks_matching(
        updated,
        "aside",
        partner_aside_open_pat,
        predicate=_has_unapproved_r,
        replacer=_clean_partner_section,
    )

    # 4. Strip any unapproved standalone partner cards or table rows outside partner sections
    if "/r/" in updated:
        updated = _strip_balanced_blocks_matching(
            updated,
            "div",
            r'<div\b[^>]*class=["\'][^"\']*\b(?:partner-card|affiliate-card)\b[^"\']*["\'][^>]*>',
            predicate=_has_unapproved_r,
        )
        updated = re.sub(
            r"<tr\b[^>]*>.*?</tr>",
            lambda tr_m: "" if _has_unapproved_r(tr_m.group(0)) else tr_m.group(0),
            updated,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # 5. Final fail-closed safety net: strip any stray unapproved <a href="[https://...]/r/<pk>">...</a>
        updated = r_anchor_re.sub(
            lambda a_m: a_m.group(0) if _is_key_live(a_m.group(1)) else "",
            updated,
        )

    return updated


def _extract_partner_vault_status(
    partner_key: str,
    vault_overrides: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not vault_overrides or not isinstance(vault_overrides, dict):
        return None
    direct_entry = vault_overrides.get(partner_key)
    if isinstance(direct_entry, dict):
        st = direct_entry.get("status") or direct_entry.get("state")
        if st:
            return str(st).strip().lower()
    categories = vault_overrides.get("categories")
    if isinstance(categories, dict):
        for cat_v in categories.values():
            if isinstance(cat_v, dict) and cat_v.get("primary_partner") == partner_key:
                st = cat_v.get("status") or cat_v.get("state")
                if st:
                    return str(st).strip().lower()
    for val in vault_overrides.values():
        if isinstance(val, dict) and val.get("primary_partner") == partner_key:
            st = val.get("status") or val.get("state")
            if st:
                return str(st).strip().lower()
    return None


def _resolve_profithelm_bucket(s: str) -> str:
    """Resolves the INTENT_ROUTING_TABLE bucket name for a ProfitHelm calculator slug."""
    if "section-1031" in s or "1031" in s:
        return "section-1031"
    if ("medical" in s or "dental" in s) and ("179" in s or "equipment" in s):
        return "medical-equipment"
    if any(t in s for t in ("section-179", "179", "macrs", "depreciation", "equipment")):
        return "section-179"
    if "workers-comp" in s:
        return "workers-comp"
    if "surety-bond" in s or ("surety" in s and "bond" in s):
        return "surety-bond"
    if "section-301" in s or ("tariff" in s and "landed-cost" in s):
        return "tariff-landed-cost"
    if "invoice-factoring" in s or "factoring" in s:
        return "invoice-factoring"
    if "s-corp" in s:
        return "s-corp-payroll"
    if any(t in s for t in ("treasury", "yield", "tbill")):
        return "treasury"
    if any(t in s for t in ("qsbs", "1202")):
        return "qsbs"
    if "corporate-amt" in s:
        return "corporate-amt"
    if "r-and-d" in s or "section-174" in s:
        return "r-and-d"
    if any(t in s for t in ("runway", "burn", "saas")):
        return "runway"
    if "payroll" in s:
        return "payroll"
    if any(t in s for t in ("crypto", "token", "staking")):
        return "crypto"
    if "capital-gains" in s:
        return "capital-gains"
    if "prediction" in s and "tax" in s:
        return "prediction-market-tax"
    if any(t in s for t in ("prediction", "odds", "arbitrage", "kalshi", "kelly", "ev", "vig", "break-even")):
        return "prediction"
    return "tax"


def resolve_optimal_partner_for_slug(
    property_id: str,
    slug: str,
    vault_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
) -> Optional[AffiliatePartner]:
    """
    Resolves the optimal affiliate partner for a property and calculator slug,
    enforcing domain boundaries and prioritizing highest-yielding live partners
    (incorporating empirical outbound partner engagement and conversion telemetry when present).
    Suppresses commercial refinance partners on restricted Prexvo public-service pages.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "").strip().lower()
    s = (slug or "").strip().lower()

    if prop == "prexvo":
        if is_restricted_public_service_slug(s):
            return None
        candidates: List[AffiliatePartner] = []
        for k, p in PREXVO_AFFILIATES.items():
            ov_st = _extract_partner_vault_status(p.key, vault_overrides)
            eff_st = (ov_st or p.status or "").strip().lower()
            if eff_st in ("declined", "rejected", "terminated", "inactive"):
                continue
            if k == p.key and k not in ENTERPRISE_B2B_PARTNERS and k not in B2B_PARTNER_KEYS:
                candidates.append(p)
        live_candidates: List[Tuple[AffiliatePartner, str]] = []
        for p in candidates:
            ov_status = _extract_partner_vault_status(p.key, vault_overrides)
            eff_status = (ov_status or p.status or "").strip().lower()
            if eff_status in ("live", "active_direct"):
                live_candidates.append((p, eff_status))
        if live_candidates:
            best = max(
                live_candidates,
                key=lambda item: score_partner_yield(
                    item[0],
                    item[1],
                    engagement_metrics=engagement_metrics,
                    slug=s,
                ),
            )
            return best[0]
        if engagement_metrics and candidates:
            best_pending = max(
                candidates,
                key=lambda p: score_partner_yield(
                    p,
                    p.status,
                    engagement_metrics=engagement_metrics,
                    slug=s,
                ),
            )
            return best_pending
        return PREXVO_AFFILIATES.get("splash_financial")

    if prop == "gainhelm":
        fw_prof = get_gainhelm_framework_profile(slug=s)
        primary_pk = str(fw_prof.get("primary_partner_key") or "vanta_security").strip().lower()
        if primary_pk == "cobalt_pentest":
            base_keys = INTENT_ROUTING_TABLE["pentest"]
        elif primary_pk == "coalition_cyber_insurance":
            base_keys = INTENT_ROUTING_TABLE["cyber-insurance"]
        else:
            base_keys = INTENT_ROUTING_TABLE["cyber-compliance"]
        bucket_keys = list(dict.fromkeys([primary_pk] + list(base_keys)))
        candidates = [
            GAINHELM_AFFILIATES[k]
            for k in bucket_keys
            if k in GAINHELM_AFFILIATES
            and (
                (_extract_partner_vault_status(k, vault_overrides) or GAINHELM_AFFILIATES[k].status or "")
                .strip()
                .lower()
                not in ("declined", "rejected", "terminated", "inactive")
            )
        ]
        if not candidates:
            candidates = [
                p
                for p in GAINHELM_AFFILIATES.values()
                if (p.status or "").strip().lower() not in ("declined", "rejected", "terminated", "inactive")
            ]
        if engagement_metrics and candidates:
            return max(
                candidates,
                key=lambda p: score_partner_yield(p, p.status, engagement_metrics=engagement_metrics, slug=s),
            )
        return candidates[0] if candidates else None

    if prop == "lienbond":
        if any(t in s for t in ("bond", "miller-act", "erisa", "fidelity")):
            lb_keys = ["suretybonds_direct", "simply_business", "thimble_contractor", "levelset_lien_filing"]
        elif any(t in s for t in ("lien", "preliminary-notice", "retainage", "waiver")):
            lb_keys = ["levelset_lien_filing", "jobber_field_service", "suretybonds_direct", "simply_business"]
        elif any(t in s for t in ("markup", "margin", "davis-bacon", "prevailing-wage")):
            lb_keys = ["jobber_field_service", "simply_business", "suretybonds_direct", "levelset_lien_filing"]
        else:
            lb_keys = ["simply_business", "thimble_contractor", "suretybonds_direct", "jobber_field_service"]
        candidates = [
            LIENBOND_AFFILIATES[k]
            for k in lb_keys
            if k in LIENBOND_AFFILIATES
            and (
                (_extract_partner_vault_status(k, vault_overrides) or LIENBOND_AFFILIATES[k].status or "")
                .strip()
                .lower()
                not in ("declined", "rejected", "terminated", "inactive")
            )
        ]
        if not candidates:
            candidates = [
                p
                for p in LIENBOND_AFFILIATES.values()
                if (p.status or "").strip().lower() not in ("declined", "rejected", "terminated", "inactive")
            ]
        if engagement_metrics and candidates:
            return max(
                candidates,
                key=lambda p: score_partner_yield(p, p.status, engagement_metrics=engagement_metrics, slug=s),
            )
        return candidates[0] if candidates else None

    if prop in ("profithelm", "exchange1031"):
        matched_bucket_name = _resolve_profithelm_bucket(s)
        greenfield_roster_used = False
        raw_keys = INTENT_ROUTING_TABLE.get(matched_bucket_name, ["efile_com", "eztaxreturn_com", "freetaxusa"])
        is_b2b = is_commercial_b2b_slug(s)
        is_retail = (s in RETAIL_TAX_SLUGS) or (not is_b2b)
        if matched_bucket_name == "tax" and s not in RETAIL_TAX_SLUGS:
            cls_info = classify_asset_archetype_and_intent(prop, s, s.replace("-", " "))
            vf = str(cls_info.get("vertical_family") or "")
            if vf and vf not in ("tax_compliance", "retail_tax", "federal_state_tax_brackets") and vf in VERTICAL_DIVERSIFIED_PARTNER_ROSTERS:
                raw_keys = list(VERTICAL_DIVERSIFIED_PARTNER_ROSTERS[vf])
                is_b2b = True
                is_retail = False
                greenfield_roster_used = True

        candidates = []
        seen_keys: Set[str] = set()
        for k in raw_keys:
            if k not in PROFITHELM_AFFILIATES:
                continue
            p = PROFITHELM_AFFILIATES[k]
            if p.key in seen_keys:
                continue
            ov_st = _extract_partner_vault_status(p.key, vault_overrides)
            eff_st = (ov_st or p.status or "").strip().lower()
            if eff_st in ("declined", "rejected", "terminated", "inactive"):
                continue
            if is_b2b and p.key in RETAIL_TAX_PARTNERS:
                continue
            if is_retail and p.key in ENTERPRISE_B2B_PARTNERS:
                continue
            seen_keys.add(p.key)
            candidates.append(p)

        if not candidates:
            fallback_key = "mercury" if is_b2b else "efile_com"
            return PROFITHELM_AFFILIATES.get(fallback_key)

        live_candidates = []
        explicit_vault_live_keys: Set[str] = set()
        for p in candidates:
            ov_status = _extract_partner_vault_status(p.key, vault_overrides)
            ov_entry = vault_overrides.get(p.key) if isinstance(vault_overrides, dict) else None
            if ov_status in ("live", "active_direct") and not (
                isinstance(ov_entry, dict) and ov_entry.get("is_fallback_partner")
            ):
                explicit_vault_live_keys.add(p.key)
            eff_status = (ov_status or p.status or "").strip().lower()
            if eff_status in ("live", "active_direct"):
                live_candidates.append((p, eff_status))

        if live_candidates:
            if greenfield_roster_used and not engagement_metrics:
                for p, _ in live_candidates:
                    if p.key == raw_keys[0]:
                        return p
            if matched_bucket_name in ("crypto", "prediction-market-tax") and not engagement_metrics:
                for p, eff_st in live_candidates:
                    if p.key == "coinledger" and not (explicit_vault_live_keys - {"coinledger"}):
                        return p
            if matched_bucket_name in ("section-1031", "1031", "llc-entity", "lease-agreement") and not engagement_metrics:
                for p, eff_st in live_candidates:
                    if p.key == "lawdepot" and not (explicit_vault_live_keys - {"lawdepot"}):
                        return p
            if matched_bucket_name in (
                "section-1031",
                "1031",
                "section-179",
                "179",
                "macrs",
                "depreciation",
                "equipment",
                "tariff-landed-cost",
                "invoice-factoring",
            ) and not explicit_vault_live_keys and not engagement_metrics:
                non_fallback_live = [
                    (p, eff_st) for p, eff_st in live_candidates if p.key != "mercury"
                ]
                if not non_fallback_live:
                    return candidates[0]
                live_candidates = non_fallback_live
            best = max(
                live_candidates,
                key=lambda item: score_partner_yield(
                    item[0],
                    item[1],
                    engagement_metrics=engagement_metrics,
                    slug=s,
                ),
            )
            return best[0]

        if engagement_metrics:
            best_cand = max(
                candidates,
                key=lambda p: score_partner_yield(
                    p,
                    p.status,
                    engagement_metrics=engagement_metrics,
                    slug=s,
                ),
            )
            return best_cand

        return candidates[0]

    return None


def record_outbound_partner_engagement(
    event: Dict[str, Any],
    ledger_path: Optional[Any] = None,
    property_id: str = "profithelm",
) -> Dict[str, Any]:
    """
    Appends an outbound partner engagement or calculator CTA interaction event
    to a tenant telemetry JSONL ledger with strict property isolation and zero dashes.
    Zero em-dashes. Zero en-dashes.
    """
    import json
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path

    prop_clean = str(event.get("property_id") or event.get("tenant_id") or property_id or "profithelm").strip().lower()
    event_type = str(event.get("event_type") or event.get("event") or "affiliate_click").strip().lower()
    tool_slug = str(event.get("tool_slug") or event.get("slug") or event.get("source_tool") or "general").strip().lower()
    props = dict(event.get("properties") or {})
    mon = dict(event.get("monetization") or {})

    partner_key = str(
        event.get("partner_key")
        or event.get("partner")
        or props.get("partner_key")
        or props.get("partner")
        or mon.get("partner_key")
        or mon.get("partner")
        or ""
    ).strip().lower()
    cta_slot = str(
        event.get("cta_slot")
        or event.get("cta_id")
        or props.get("cta_slot")
        or props.get("cta_id")
        or mon.get("cta_slot")
        or ("calculator_preset_cta" if "preset" in event_type else "primary_partner_cta")
    ).strip()
    value_tier = str(
        event.get("value_tier")
        or event.get("tier")
        or props.get("value_tier")
        or mon.get("value_tier")
        or "starter"
    ).strip().lower()

    if prop_clean == "prexvo" and (partner_key in B2B_PARTNER_KEYS or partner_key in GAINHELM_PARTNER_KEYS):
        raise ValueError(
            f"Strict isolation violation: B2B partner '{partner_key}' engagement cannot be recorded on Prexvo."
        )
    if prop_clean in ("profithelm", "exchange1031") and (partner_key in STUDENT_LOAN_PARTNER_KEYS or partner_key in GAINHELM_PARTNER_KEYS):
        raise ValueError(
            f"Strict isolation violation: Foreign tenant partner '{partner_key}' engagement cannot be recorded on ProfitHelm."
        )
    if prop_clean == "gainhelm" and (partner_key in STUDENT_LOAN_PARTNER_KEYS or partner_key in B2B_PARTNER_KEYS):
        raise ValueError(
            f"Strict isolation violation: Foreign tenant partner '{partner_key}' engagement cannot be recorded on GainHelm."
        )

    raw_payout = (
        event.get("payout_usd")
        if event.get("payout_usd") is not None
        else (
            event.get("revenue_usd")
            if event.get("revenue_usd") is not None
            else (props.get("payout_usd") if props.get("payout_usd") is not None else mon.get("payout_usd"))
        )
    )
    payout_val: Optional[float] = None
    if raw_payout is not None:
        try:
            payout_val = float(raw_payout)
        except Exception:
            payout_val = None

    merged_props = {
        **props,
        "partner_key": partner_key,
        "cta_slot": cta_slot,
        "value_tier": value_tier,
    }
    merged_mon = {
        **mon,
        "partner_key": partner_key,
        "cta_slot": cta_slot,
        "value_tier": value_tier,
    }
    if payout_val is not None:
        merged_props["payout_usd"] = payout_val
        merged_mon["payout_usd"] = payout_val

    rec: Dict[str, Any] = {
        "schema_version": f"{prop_clean}.telemetry.v1",
        "event_id": str(event.get("event_id") or uuid.uuid4()),
        "timestamp": str(event.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        "property_id": prop_clean,
        "tenant_id": prop_clean,
        "event_type": event_type,
        "tool_slug": tool_slug,
        "partner_key": partner_key,
        "cta_slot": cta_slot,
        "value_tier": value_tier,
        "properties": merged_props,
        "monetization": merged_mon,
    }
    if payout_val is not None:
        rec["payout_usd"] = payout_val
    if ledger_path is not None:
        p = Path(ledger_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return {"status": "SUCCESS", "event_id": rec["event_id"], "record": rec}


def aggregate_outbound_partner_engagement(
    events_or_path: Any = None,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregates calculator CTA interactions and outbound affiliate partner clicks
    into empirical conversion rates, EPC, eRPM, and revenue yield scores across
    tools, CTA slots, and partners.
    Accepts a list of telemetry event dicts, an existing summary dict, a Path/str to
    a JSONL/JSON telemetry file, or a tenant base_dir.
    Zero em-dashes. Zero en-dashes.
    """
    import json
    from pathlib import Path

    if isinstance(events_or_path, dict) and ("by_slug" in events_or_path or "by_partner" in events_or_path):
        return events_or_path

    raw_events: List[Dict[str, Any]] = []
    prop_filter = str(property_id or "").strip().lower() or None

    if isinstance(events_or_path, list):
        raw_events = [e for e in events_or_path if isinstance(e, dict)]
    elif isinstance(events_or_path, (str, Path)):
        p = Path(events_or_path)
        if p.is_dir():
            for cand_file in (
                p / ".agy" / "telemetry_events.jsonl",
                p / ".agy" / "outbound_partner_engagement.json",
                p / "telemetry_events.jsonl",
            ):
                if cand_file.is_file():
                    p = cand_file
                    break
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8").strip()
                if p.suffix == ".json" and content.startswith("{"):
                    loaded = json.loads(content)
                    if isinstance(loaded, dict) and ("by_slug" in loaded or "by_partner" in loaded):
                        return loaded
                    if isinstance(loaded, dict) and isinstance(loaded.get("events"), list):
                        raw_events = [e for e in loaded["events"] if isinstance(e, dict)]
                else:
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                            if isinstance(ev, dict):
                                raw_events.append(ev)
                        except Exception:
                            continue
            except Exception:
                pass

    by_slug: Dict[str, Dict[str, Any]] = {}
    by_partner: Dict[str, Dict[str, Any]] = {}
    by_cta_slot: Dict[str, Dict[str, Any]] = {}
    by_page_and_slot: Dict[str, Dict[str, Any]] = {}
    by_subid: Dict[str, Dict[str, Any]] = {}
    by_traffic_source: Dict[str, Dict[str, Any]] = {}

    def _ensure_traffic_source(ts_val: str) -> Dict[str, Any]:
        ts_clean = (ts_val or "direct_or_referral").strip().lower() or "direct_or_referral"
        if ts_clean not in by_traffic_source:
            by_traffic_source[ts_clean] = {
                "traffic_source": ts_clean,
                "views": 0,
                "calculator_interactions": 0,
                "deeplink_hydrations": 0,
                "outbound_clicks": 0,
                "estimated_revenue_yield_usd": 0.0,
                "slugs": {},
            }
        return by_traffic_source[ts_clean]

    def _ensure_slug(slug_val: str, prop_val: str) -> Dict[str, Any]:
        if slug_val not in by_slug:
            by_slug[slug_val] = {
                "tool_slug": slug_val,
                "property_id": prop_val,
                "page_views": 0,
                "calculator_interactions": 0,
                "workbench_interactions": 0,
                "scenario_pins": 0,
                "blueprint_saves": 0,
                "preset_clicks": 0,
                "outbound_clicks": 0,
                "verified_non_probe_outbound_clicks": 0,
                "synthetic_probe_clicks_filtered": 0,
                "cta_ctr": 0.0,
                "intent_to_click_rate": 0.0,
                "realized_revenue_usd": 0.0,
                "estimated_revenue_yield_usd": 0.0,
                "empirical_erpm_usd": 0.0,
                "top_converting_partner": "",
                "top_converting_cta_slot": "",
                "cta_slots": {},
                "partners": {},
                "traffic_sources": {},
            }
        return by_slug[slug_val]

    def _ensure_partner(pk_val: str, prop_val: str) -> Dict[str, Any]:
        if pk_val not in by_partner:
            by_partner[pk_val] = {
                "partner_key": pk_val,
                "property_id": prop_val,
                "bounty_midpoint_usd": get_partner_bounty_midpoint(pk_val),
                "views_exposed": 0,
                "calculator_interactions": 0,
                "outbound_clicks": 0,
                "cta_ctr": 0.0,
                "intent_to_click_rate": 0.0,
                "empirical_epc_usd": 0.0,
                "empirical_erpm_usd": 0.0,
                "realized_revenue_usd": 0.0,
                "estimated_revenue_yield_usd": 0.0,
                "composite_yield_score": 0.0,
                "cta_slots": {},
                "slugs": {},
            }
        return by_partner[pk_val]

    def _ensure_cta_slot(slot_val: str) -> Dict[str, Any]:
        if slot_val not in by_cta_slot:
            by_cta_slot[slot_val] = {
                "cta_slot": slot_val,
                "views_exposed": 0,
                "intent_interactions": 0,
                "outbound_clicks": 0,
                "cta_ctr": 0.0,
                "intent_to_click_rate": 0.0,
                "estimated_revenue_yield_usd": 0.0,
                "partners": {},
            }
        return by_cta_slot[slot_val]

    def _ensure_page_and_slot(slug_val: str, slot_val: str, prop_val: str) -> Dict[str, Any]:
        ps_key = f"{slug_val}:{slot_val}"
        if ps_key not in by_page_and_slot:
            by_page_and_slot[ps_key] = {
                "page_slot_key": ps_key,
                "tool_slug": slug_val,
                "cta_slot": slot_val,
                "property_id": prop_val,
                "views": 0,
                "intent_interactions": 0,
                "outbound_clicks": 0,
                "estimated_revenue_yield_usd": 0.0,
                "partners": {},
                "subids": {},
            }
        return by_page_and_slot[ps_key]

    for ev in raw_events:
        ev_prop = str(
            ev.get("property_id")
            or ev.get("tenant_id")
            or (ev.get("properties") or {}).get("property_id")
            or prop_filter
            or "profithelm"
        ).strip().lower()
        if prop_filter and ev_prop and ev_prop != prop_filter:
            continue

        etype = str(ev.get("event_type") or ev.get("event") or "").strip().lower()
        # Skip system failure events from pseofactory crash logger
        if etype in ("subprocess_crash", "systemd_failure", "unhandled_exception", "indexing_anomaly", "property_contamination", "lock_contention"):
            continue

        props = ev.get("properties") if isinstance(ev.get("properties"), dict) else {}
        mon = ev.get("monetization") if isinstance(ev.get("monetization"), dict) else {}

        slug = str(
            ev.get("tool_slug")
            or ev.get("slug")
            or ev.get("source_tool")
            or props.get("tool_slug")
            or props.get("source_tool")
            or ""
        ).strip().lower()
        if not slug:
            path_val = str(ev.get("path") or "").strip("/")
            parts = [pt for pt in path_val.split("/") if pt]
            if len(parts) >= 2 and parts[0] == "tools":
                slug = parts[1].lower()
            elif len(parts) == 1 and parts[0] != "tools":
                slug = parts[0].lower()
            else:
                slug = "general"

        partner_key = str(
            ev.get("partner_key")
            or ev.get("partner")
            or props.get("partner_key")
            or props.get("partner")
            or mon.get("partner_key")
            or mon.get("partner")
            or ""
        ).strip().lower()
        if not partner_key:
            href_or_path = str(ev.get("href") or props.get("href") or ev.get("path") or "")
            m_r = re.search(r"/r/([a-z0-9_]+)", href_or_path.lower())
            if m_r:
                partner_key = m_r.group(1)

        cta_slot = str(
            ev.get("cta_slot")
            or ev.get("cta_id")
            or props.get("cta_slot")
            or props.get("cta_id")
            or mon.get("cta_slot")
            or ("calculator_preset_cta" if "preset" in etype else "primary_partner_cta")
        ).strip()

        subid_val = str(
            ev.get("subid")
            or props.get("subid")
            or mon.get("subid")
            or f"{slug}_{cta_slot}"
        ).strip()

        value_tier = str(
            ev.get("value_tier")
            or ev.get("tier")
            or props.get("value_tier")
            or mon.get("value_tier")
            or "starter"
        ).strip().lower()

        traffic_source = str(
            ev.get("traffic_source")
            or props.get("traffic_source")
            or mon.get("traffic_source")
            or "direct_or_referral"
        ).strip().lower() or "direct_or_referral"

        payout = 0.0
        for p_src in (props, mon, ev):
            raw_pay = p_src.get("payout_usd") or p_src.get("revenue_usd") or p_src.get("revenue") or p_src.get("amount")
            if raw_pay is not None:
                try:
                    payout = float(raw_pay)
                    break
                except Exception:
                    pass

        s_rec = _ensure_slug(slug, ev_prop)
        slot_rec = _ensure_cta_slot(cta_slot)
        ps_rec = _ensure_page_and_slot(slug, cta_slot, ev_prop)
        ts_rec = _ensure_traffic_source(traffic_source)
        s_rec["traffic_sources"][traffic_source] = s_rec["traffic_sources"].get(traffic_source, 0) + 1
        s_slot = s_rec["cta_slots"].setdefault(
            cta_slot,
            {"cta_slot": cta_slot, "views": 0, "intent_interactions": 0, "outbound_clicks": 0, "estimated_revenue_yield_usd": 0.0},
        )

        interaction_type = str(ev.get("interaction_type") or props.get("interaction_type") or "").strip().lower()
        is_view = etype in ("page_view", "impression", "offer_impression")
        is_calc_intent = (
            etype
            in (
                "client_calculation",
                "calculation",
                "scenario_copy",
                "slider_drag",
                "input_change",
                "calculator_interaction",
                "workbench_interaction",
                "scenario_pin",
                "blueprint_save",
                "blueprint_share",
                "blueprint_export",
            )
            or etype.startswith("select_preset")
            or etype == "preset_click"
            or interaction_type.startswith(("scenario_pin", "blueprint_", "preset_hydration", "social_deeplink_hydrated"))
        )
        is_outbound_click = etype in ("affiliate_click", "click_conversion_cta", "outbound_redirect", "partner_cta_click")

        if is_view:
            s_rec["page_views"] += 1
            s_slot["views"] += 1
            slot_rec["views_exposed"] += 1
            ps_rec["views"] += 1
            ts_rec["views"] += 1
            if partner_key:
                p_rec = _ensure_partner(partner_key, ev_prop)
                p_rec["views_exposed"] += 1
                sp_entry = s_rec["partners"].setdefault(
                    partner_key,
                    {
                        "partner_key": partner_key,
                        "views_exposed": 0,
                        "calculator_interactions": 0,
                        "outbound_clicks": 0,
                        "realized_revenue_usd": 0.0,
                        "estimated_revenue_yield_usd": 0.0,
                        "cta_ctr": 0.0,
                        "intent_to_click_rate": 0.0,
                        "empirical_erpm_usd": 0.0,
                    },
                )
                sp_entry["views_exposed"] += 1

        if is_calc_intent:
            s_rec["calculator_interactions"] += 1
            ts_rec["calculator_interactions"] += 1
            ts_rec["slugs"][slug] = ts_rec["slugs"].get(slug, 0) + 1
            if interaction_type == "social_deeplink_hydrated":
                ts_rec["deeplink_hydrations"] += 1
            if (
                "workbench" in etype
                or etype in ("scenario_pin", "blueprint_save", "blueprint_share", "blueprint_export")
                or interaction_type.startswith(("scenario_pin", "blueprint_", "preset_hydration", "social_deeplink_hydrated"))
            ):
                s_rec["workbench_interactions"] = s_rec.get("workbench_interactions", 0) + 1
            if "scenario_pin" in etype or interaction_type.startswith("scenario_pin"):
                s_rec["scenario_pins"] = s_rec.get("scenario_pins", 0) + 1
            if "blueprint" in etype or interaction_type.startswith("blueprint_"):
                s_rec["blueprint_saves"] = s_rec.get("blueprint_saves", 0) + 1
            if "preset" in etype or interaction_type == "preset_hydration":
                s_rec["preset_clicks"] += 1
            s_slot["intent_interactions"] += 1
            slot_rec["intent_interactions"] += 1
            ps_rec["intent_interactions"] += 1
            if partner_key:
                p_rec = _ensure_partner(partner_key, ev_prop)
                p_rec["calculator_interactions"] += 1
                sp_entry = s_rec["partners"].setdefault(
                    partner_key,
                    {
                        "partner_key": partner_key,
                        "views_exposed": 0,
                        "calculator_interactions": 0,
                        "outbound_clicks": 0,
                        "realized_revenue_usd": 0.0,
                        "estimated_revenue_yield_usd": 0.0,
                        "cta_ctr": 0.0,
                        "intent_to_click_rate": 0.0,
                        "empirical_erpm_usd": 0.0,
                    },
                )
                sp_entry["calculator_interactions"] += 1

        if is_outbound_click:
            s_rec["outbound_clicks"] += 1
            ts_rec["outbound_clicks"] += 1
            ts_rec["slugs"][slug] = ts_rec["slugs"].get(slug, 0) + 1
            sub_low = subid_val.lower()
            is_synthetic_probe = any(
                tok in sub_low
                for tok in ("_oct19", "_test_", "_live_kv_", "_edge", "qa_", "probe_", "synthetic_")
            )
            if is_synthetic_probe:
                s_rec["synthetic_probe_clicks_filtered"] = s_rec.get("synthetic_probe_clicks_filtered", 0) + 1
            else:
                s_rec["verified_non_probe_outbound_clicks"] = s_rec.get("verified_non_probe_outbound_clicks", 0) + 1
            s_Slot_clicks = s_slot["outbound_clicks"] + 1
            s_slot["outbound_clicks"] = s_Slot_clicks
            slot_rec["outbound_clicks"] += 1
            ps_rec["outbound_clicks"] += 1

            eff_pk = partner_key or _select_partner_for_slug(ev_prop, slug) or "default_partner"
            p_rec = _ensure_partner(eff_pk, ev_prop)
            p_rec["outbound_clicks"] += 1
            p_rec["cta_slots"][cta_slot] = p_rec["cta_slots"].get(cta_slot, 0) + 1
            p_rec["slugs"][slug] = p_rec["slugs"].get(slug, 0) + 1
            slot_rec["partners"][eff_pk] = slot_rec["partners"].get(eff_pk, 0) + 1
            ps_rec["partners"][eff_pk] = ps_rec["partners"].get(eff_pk, 0) + 1
            ps_rec["subids"][subid_val] = ps_rec["subids"].get(subid_val, 0) + 1

            bounty_mid = p_rec["bounty_midpoint_usd"]
            is_b2b_partner = eff_pk in ENTERPRISE_B2B_PARTNERS or is_commercial_b2b_slug(slug)
            base_conv = 0.045 if is_b2b_partner else 0.035
            tier_mult = 1.25 if value_tier in ("premium", "tier_1") else 1.0
            click_yield = payout if payout > 0 else round(bounty_mid * base_conv * tier_mult, 4)

            s_rec["realized_revenue_usd"] = round(s_rec["realized_revenue_usd"] + payout, 4)
            s_rec["estimated_revenue_yield_usd"] = round(s_rec["estimated_revenue_yield_usd"] + click_yield, 4)
            s_slot["estimated_revenue_yield_usd"] = round(s_slot["estimated_revenue_yield_usd"] + click_yield, 4)
            slot_rec["estimated_revenue_yield_usd"] = round(slot_rec["estimated_revenue_yield_usd"] + click_yield, 4)
            ps_rec["estimated_revenue_yield_usd"] = round(ps_rec["estimated_revenue_yield_usd"] + click_yield, 4)
            ts_rec["estimated_revenue_yield_usd"] = round(ts_rec["estimated_revenue_yield_usd"] + click_yield, 4)

            if subid_val:
                sub_entry = by_subid.setdefault(
                    subid_val,
                    {
                        "subid": subid_val,
                        "property_id": ev_prop,
                        "partner_key": eff_pk,
                        "tool_slug": slug,
                        "cta_slot": cta_slot,
                        "outbound_clicks": 0,
                        "estimated_revenue_yield_usd": 0.0,
                    },
                )
                sub_entry["outbound_clicks"] += 1
                sub_entry["estimated_revenue_yield_usd"] = round(
                    sub_entry["estimated_revenue_yield_usd"] + click_yield, 4
                )

            p_rec["realized_revenue_usd"] = round(p_rec["realized_revenue_usd"] + payout, 4)
            p_rec["estimated_revenue_yield_usd"] = round(p_rec["estimated_revenue_yield_usd"] + click_yield, 4)

            sp_entry = s_rec["partners"].setdefault(
                eff_pk,
                {
                    "partner_key": eff_pk,
                    "views_exposed": 0,
                    "calculator_interactions": 0,
                    "outbound_clicks": 0,
                    "realized_revenue_usd": 0.0,
                    "estimated_revenue_yield_usd": 0.0,
                    "cta_ctr": 0.0,
                    "intent_to_click_rate": 0.0,
                    "empirical_erpm_usd": 0.0,
                },
            )
            sp_entry["outbound_clicks"] += 1
            sp_entry["realized_revenue_usd"] = round(sp_entry["realized_revenue_usd"] + payout, 4)
            sp_entry["estimated_revenue_yield_usd"] = round(sp_entry["estimated_revenue_yield_usd"] + click_yield, 4)

    # Finalize derived ratios and rankings
    for slug_k, s_rec in by_slug.items():
        t_basis = max(1, s_rec["page_views"], s_rec["calculator_interactions"], s_rec["outbound_clicks"])
        s_rec["cta_ctr"] = round(s_rec["outbound_clicks"] / float(t_basis), 4)
        s_rec["intent_to_click_rate"] = round(
            s_rec["outbound_clicks"] / float(max(1, s_rec["calculator_interactions"])),
            4,
        ) if s_rec["calculator_interactions"] > 0 else s_rec["cta_ctr"]
        s_rec["empirical_erpm_usd"] = round((s_rec["estimated_revenue_yield_usd"] / float(t_basis)) * 1000.0, 2)

        for sp_k, sp_data in s_rec["partners"].items():
            sp_basis = max(1, sp_data["views_exposed"], s_rec["page_views"], s_rec["calculator_interactions"], sp_data["outbound_clicks"])
            sp_data["cta_ctr"] = round(sp_data["outbound_clicks"] / float(sp_basis), 4)
            sp_calc_basis = max(1, sp_data["calculator_interactions"], s_rec["calculator_interactions"])
            sp_data["intent_to_click_rate"] = round(sp_data["outbound_clicks"] / float(sp_calc_basis), 4)
            sp_data["empirical_erpm_usd"] = round((sp_data["estimated_revenue_yield_usd"] / float(sp_basis)) * 1000.0, 2)

        if s_rec["partners"]:
            best_p = max(
                s_rec["partners"].values(),
                key=lambda x: (x.get("estimated_revenue_yield_usd", 0.0), x.get("outbound_clicks", 0)),
            )
            s_rec["top_converting_partner"] = best_p["partner_key"]
        if s_rec["cta_slots"]:
            best_slot = max(
                s_rec["cta_slots"].values(),
                key=lambda x: (x.get("estimated_revenue_yield_usd", 0.0), x.get("outbound_clicks", 0), x.get("intent_interactions", 0)),
            )
            s_rec["top_converting_cta_slot"] = best_slot["cta_slot"]

    for pk_k, p_rec in by_partner.items():
        p_basis = max(1, p_rec["views_exposed"], p_rec["calculator_interactions"], p_rec["outbound_clicks"])
        p_rec["cta_ctr"] = round(p_rec["outbound_clicks"] / float(p_basis), 4)
        p_rec["intent_to_click_rate"] = round(
            p_rec["outbound_clicks"] / float(max(1, p_rec["calculator_interactions"])),
            4,
        ) if p_rec["calculator_interactions"] > 0 else p_rec["cta_ctr"]
        p_rec["empirical_epc_usd"] = round(
            p_rec["estimated_revenue_yield_usd"] / float(max(1, p_rec["outbound_clicks"])),
            4,
        ) if p_rec["outbound_clicks"] > 0 else round(p_rec["bounty_midpoint_usd"] * 0.04, 4)
        p_rec["empirical_erpm_usd"] = round((p_rec["estimated_revenue_yield_usd"] / float(p_basis)) * 1000.0, 2)
        p_rec["composite_yield_score"] = round(
            p_rec["bounty_midpoint_usd"] * (1.0 + p_rec["cta_ctr"] * 8.0 + p_rec["intent_to_click_rate"] * 4.0)
            + p_rec["estimated_revenue_yield_usd"],
            4,
        )

    for slot_k, slot_rec in by_cta_slot.items():
        sl_basis = max(1, slot_rec["views_exposed"], slot_rec["intent_interactions"], slot_rec["outbound_clicks"])
        slot_rec["cta_ctr"] = round(slot_rec["outbound_clicks"] / float(sl_basis), 4)
        slot_rec["intent_to_click_rate"] = round(
            slot_rec["outbound_clicks"] / float(max(1, slot_rec["intent_interactions"])),
            4,
        ) if slot_rec["intent_interactions"] > 0 else slot_rec["cta_ctr"]

    return {
        "property_id": prop_filter or "all",
        "total_events_processed": len(raw_events),
        "total_outbound_clicks": sum(s["outbound_clicks"] for s in by_slug.values()),
        "verified_non_probe_outbound_clicks": sum(s.get("verified_non_probe_outbound_clicks", 0) for s in by_slug.values()),
        "synthetic_probe_clicks_filtered": sum(s.get("synthetic_probe_clicks_filtered", 0) for s in by_slug.values()),
        "total_calculator_interactions": sum(s["calculator_interactions"] for s in by_slug.values()),
        "total_workbench_interactions": sum(s.get("workbench_interactions", 0) for s in by_slug.values()),
        "total_scenario_pins": sum(s.get("scenario_pins", 0) for s in by_slug.values()),
        "total_blueprint_saves": sum(s.get("blueprint_saves", 0) for s in by_slug.values()),
        "total_estimated_revenue_yield_usd": round(sum(s["estimated_revenue_yield_usd"] for s in by_slug.values()), 2),
        "by_slug": by_slug,
        "by_page": by_slug,
        "by_partner": by_partner,
        "by_cta_slot": by_cta_slot,
        "by_page_and_slot": by_page_and_slot,
        "by_subid": by_subid,
        "by_traffic_source": by_traffic_source,
    }


def rank_partner_offers_by_revenue_yield(
    property_id: str,
    slug: str,
    candidate_keys: Optional[List[str]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    vault_overrides: Optional[Dict[str, Any]] = None,
    only_live: bool = False,
) -> List[Dict[str, Any]]:
    """
    Ranks compliant candidate partner offers for a (property_id, slug) pair by composite
    revenue yield (combining status-weighted bounty midpoint and empirical outbound CTA
    conversion rate / revenue yield).
    Enforces strict property boundaries and Prexvo YMYL public-service suppression.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "profithelm").strip().lower()
    s_clean = (slug or "").strip().lower()

    if prop == "prexvo" and is_restricted_public_service_slug(s_clean):
        return []

    agg = aggregate_outbound_partner_engagement(engagement_metrics, property_id=prop) if engagement_metrics else None

    if candidate_keys is None:
        if prop == "prexvo":
            candidate_keys = list(PREXVO_AFFILIATES.keys())
        elif prop == "gainhelm":
            candidate_keys = list(GAINHELM_AFFILIATES.keys())
        elif prop == "lienbond":
            candidate_keys = list(LIENBOND_AFFILIATES.keys())
        else:
            bucket = _resolve_profithelm_bucket(s_clean)
            candidate_keys = list(INTENT_ROUTING_TABLE.get(bucket, ["mercury", "ramp", "coinledger"]))

    ranked: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for idx, raw_k in enumerate(candidate_keys):
        k = str(raw_k or "").strip().lower()
        if not k or k in seen:
            continue
        if prop == "prexvo" and (k in B2B_PARTNER_KEYS or k in PROFITHELM_AFFILIATES or k in GAINHELM_AFFILIATES):
            continue
        if prop in ("profithelm", "exchange1031") and (k in STUDENT_LOAN_PARTNER_KEYS or k in PREXVO_AFFILIATES or k in GAINHELM_AFFILIATES):
            continue
        if prop == "gainhelm" and (k in STUDENT_LOAN_PARTNER_KEYS or k in PREXVO_AFFILIATES or k in B2B_PARTNER_KEYS):
            continue
        if prop == "lienbond" and (k in STUDENT_LOAN_PARTNER_KEYS or k in PREXVO_AFFILIATES or k in GAINHELM_AFFILIATES):
            continue
        seen.add(k)

        registry = (
            PREXVO_AFFILIATES
            if prop == "prexvo"
            else (
                GAINHELM_AFFILIATES
                if prop == "gainhelm"
                else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES)
            )
        )
        p_obj = registry.get(k) or (PREXVO_AFFILIATES.get("sofi") if k == "sofi_refi" else None)
        bounty_mid = get_partner_bounty_midpoint(p_obj if p_obj is not None else k)
        ov_status = _extract_partner_vault_status(k, vault_overrides)
        eff_status = (ov_status or (p_obj.status if p_obj else "pending")).strip().lower()
        if eff_status in ("declined", "rejected", "terminated", "inactive"):
            continue
        if only_live and eff_status not in ("live", "active_direct"):
            continue

        if p_obj is not None:
            y_score = score_partner_yield(p_obj, eff_status, engagement_metrics=agg or engagement_metrics, slug=s_clean)
        else:
            # Extended remediation partner (e.g. flexport, wealthfront, bench, guideline, laurel_road, juno)
            dummy_p = AffiliatePartner(
                key=k,
                name=k.replace("_", " ").title(),
                category="Commercial",
                property_id=prop,
                status=eff_status,
                env_var=f"AFFILIATE_{k.upper()}_URL",
                default_url=f"https://{k.replace('_', '')}.com/",
                badge="Featured",
                commission_est=f"${int(bounty_mid)}",
                bounty_est=f"${int(bounty_mid)}",
                network="Direct",
                description="Partner",
                target_tools=[s_clean],
                supported_params=[],
            )
            y_score = score_partner_yield(dummy_p, eff_status, engagement_metrics=agg or engagement_metrics, slug=s_clean)

        emp_rec = _extract_partner_engagement_record(k, agg or engagement_metrics, slug=s_clean) or {}
        outbound_clicks = int(float(emp_rec.get("outbound_clicks", emp_rec.get("affiliate_clicks", emp_rec.get("clicks", 0))) or 0))
        cta_ctr = float(emp_rec.get("cta_ctr", emp_rec.get("conversion_rate", emp_rec.get("ctr", 0.0))) or 0.0)
        emp_erpm = float(emp_rec.get("empirical_erpm_usd", emp_rec.get("empirical_erpm", 0.0)) or 0.0)
        est_yield = float(emp_rec.get("estimated_revenue_yield_usd", emp_rec.get("est_revenue_usd", 0.0)) or 0.0)

        ranked.append({
            "key": k,
            "partner_key": k,
            "partner_name": p_obj.name if p_obj else k.replace("_", " ").title(),
            "status": eff_status,
            "bounty_midpoint_usd": round(bounty_mid, 2),
            "yield_score": round(y_score, 4),
            "outbound_clicks": outbound_clicks,
            "cta_ctr": round(cta_ctr, 4),
            "empirical_erpm_usd": round(emp_erpm, 2),
            "estimated_revenue_yield_usd": round(est_yield, 2),
            "has_empirical_signal": bool(outbound_clicks > 0 or cta_ctr > 0.0 or emp_erpm > 0.0 or est_yield > 0.0),
            "default_order": idx,
        })

    # When empirical signal exists on any candidate, sort by (-has_empirical_signal, -yield_score, default_order);
    # otherwise preserve default_order or static yield_score.
    any_empirical = any(item["has_empirical_signal"] for item in ranked)
    if any_empirical:
        ranked.sort(key=lambda x: (-x["yield_score"], x["default_order"]))
    for rank_idx, item in enumerate(ranked, start=1):
        item["rank"] = rank_idx
    return ranked


GSC_EMPIRICAL_CLUSTER_TRAFFIC: Dict[str, Tuple[int, int]] = {
    # ProfitHelm (sc-domain:profithelm.com empirical GSC cluster traffic)
    "irs-2027-tax-brackets": (2566, 90),
    "tcja-sunset-bracket-calculator": (174, 6),
    "section-1031-calculator": (453, 0),
    "section-179-calculator": (305, 0),
    "crypto-tax-calculator": (248, 0),
    "prediction-market-tax": (39, 1),
    "treasury-yield-calculator": (26, 0),
    "saas-runway-calculator": (22, 0),
    "tcja-sunset-capital-gains": (16, 0),
    "prediction-market-odds": (12, 1),
    "commercial-heavy-vehicle-section-179-weight-calculator": (8, 0),
    "equipment-lease-vs-buy-section-179-calculator": (6, 0),
    "section-179-vehicle-equipment-deduction": (6, 0),
    "crypto-tax-form-1099-da-mandatory-reporting": (3, 0),
    "1031-exchange-rules-arizona": (2, 0),
    "prediction-market-arbitrage": (2, 0),
    "prediction-market-implied-probability": (1, 0),
    "prediction-market-kelly-criterion": (1, 0),
    "prediction-market-vig-spread": (1, 0),
    "qsbs-section-1202-tax-calculator": (2, 0),
    "s-corp-reasonable-salary-tax-calculator": (1, 0),
    "r-and-d-tax-credit-section-174-amortization-calculator": (1, 0),
    "invoice-factoring-vs-business-line-of-credit-calculator": (1, 0),
    "section-301-tariff-landed-cost-calculator": (1, 0),
    "workers-comp-and-payroll-burden-calculator": (1, 0),
    "contractor-surety-bond-cost-calculator": (1, 0),
    "medical-and-dental-equipment-section-179-roi-calculator": (1, 0),
    # Prexvo (sc-domain:prexvo.com empirical GSC cluster traffic)
    "student-loan-repayment-calculator": (133, 0),
    "rap-vs-ibr-calculator": (19, 0),
    "rap-payment-calculator": (18, 0),
    "icr-repayment-calculator": (12, 0),
    "paye-sunset-calculator": (8, 0),
    "student-loan-refinance-break-even-calculator": (6, 0),
    "parent-plus-double-consolidation": (5, 0),
    "tiered-standard-calculator": (4, 0),
    "married-filing-separately-student-loan-calculator": (2, 0),
    "grad-plus-borrowing-cap-calculator": (2, 0),
}


def estimate_partner_approval_revenue_impact(
    property_id: str,
    partner_key: str,
    affected_slugs: Optional[List[str]] = None,
    impressions: int = 0,
    outbound_clicks: int = 0,
    engagement_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculates the estimated monthly revenue impact (in USD) of approving/resolving
    a pending manual partner approval or integration gate for human review.
    Combines:
      1. Partner bounty midpoint and net uplift over current fallback/suppressed state.
      2. Affected calculator/guide search impressions across target tools.
      3. Empirical outbound CTA engagement clicks and user intent conversion rates.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "profithelm").strip().lower()
    pk = (partner_key or "").strip().lower()

    registry = PREXVO_AFFILIATES if prop == "prexvo" else (GAINHELM_AFFILIATES if prop == "gainhelm" else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES))
    p_obj = registry.get(pk)
    bounty_mid = get_partner_bounty_midpoint(p_obj if p_obj is not None else pk)

    # Determine net bounty uplift upon human operator approval
    if prop == "prexvo":
        # On Prexvo, pending_p2 offers are 100% suppressed until Gate 1 approval
        fallback_yield = 0.0
        bounty_uplift = bounty_mid
    elif prop in ("gainhelm", "lienbond"):
        # On GainHelm and LienBond, pending direct offers route to approved B2B contracts at the edge (~25% baseline yield)
        fallback_yield = round(bounty_mid * 0.25, 2)
        bounty_uplift = round(max(35.0, bounty_mid - fallback_yield), 2)
    else:
        # On ProfitHelm, pending offers fall back to Sovrn (~18% of direct bounty) or secondary partner
        fallback_yield = round(bounty_mid * 0.20, 2)
        bounty_uplift = round(max(25.0, bounty_mid - fallback_yield), 2)

    slugs_set: List[str] = []
    if p_obj and p_obj.target_tools:
        for t_slug in p_obj.target_tools:
            if t_slug and t_slug not in slugs_set:
                slugs_set.append(t_slug)
    for a_slug in (affected_slugs or []):
        clean_s = str(a_slug or "").strip().lower()
        if clean_s and clean_s not in slugs_set:
            slugs_set.append(clean_s)

    agg = aggregate_outbound_partner_engagement(engagement_metrics, property_id=prop) if engagement_metrics else None
    agg_impressions = 0
    agg_clicks = 0
    emp_calc_interactions = 0

    if agg and isinstance(agg.get("by_slug"), dict):
        for s in slugs_set:
            s_entry = agg["by_slug"].get(s)
            if isinstance(s_entry, dict):
                agg_impressions += int(s_entry.get("page_views", 0) or 0)
                agg_clicks += int(s_entry.get("outbound_clicks", 0) or 0)
                emp_calc_interactions += int(s_entry.get("calculator_interactions", 0) or 0)
    if agg and isinstance(agg.get("by_partner"), dict):
        p_entry = agg["by_partner"].get(pk)
        if isinstance(p_entry, dict):
            agg_impressions = max(agg_impressions, int(p_entry.get("views_exposed", 0) or 0))
            agg_clicks = max(agg_clicks, int(p_entry.get("outbound_clicks", 0) or 0))

    emp_impressions = max(int(impressions or 0), agg_impressions)
    emp_clicks = max(int(outbound_clicks or 0), agg_clicks)

    # When explicit impressions are not passed, check empirical GSC cluster traffic first
    gsc_impressions = 0
    gsc_clicks = 0
    if emp_impressions == 0 and slugs_set:
        for s in slugs_set:
            if s in GSC_EMPIRICAL_CLUSTER_TRAFFIC:
                imp_v, clk_v = GSC_EMPIRICAL_CLUSTER_TRAFFIC[s]
                gsc_impressions += imp_v
                gsc_clicks += clk_v

    # Baseline monthly impressions across affected tools when neither explicit nor GSC traffic is populated
    tool_count = max(1, len(slugs_set))
    baseline_impressions = tool_count * (650 if prop == "profithelm" else (700 if prop == "gainhelm" else 800))
    if emp_impressions > 0:
        effective_impressions = emp_impressions
    elif gsc_impressions > 0:
        effective_impressions = gsc_impressions
        emp_clicks = max(emp_clicks, gsc_clicks)
    else:
        effective_impressions = baseline_impressions

    # Estimate monthly outbound CTA clicks from impressions + empirical clicks
    expected_cta_ctr = 0.042 if prop == "profithelm" else (0.040 if prop == "gainhelm" else 0.038)
    projected_monthly_clicks = max(
        float(emp_clicks),
        (effective_impressions * expected_cta_ctr) + (emp_clicks * 1.5) + (emp_calc_interactions * 0.15),
    )

    lead_to_sale_rate = 0.045 if (pk in ENTERPRISE_B2B_PARTNERS or prop in ("profithelm", "gainhelm")) else 0.035
    est_monthly_conversions = projected_monthly_clicks * lead_to_sale_rate
    est_monthly_rev_impact = round(est_monthly_conversions * bounty_uplift, 2)

    return {
        "property_id": prop,
        "partner_key": pk,
        "bounty_midpoint_usd": round(bounty_mid, 2),
        "bounty_uplift_usd": round(bounty_uplift, 2),
        "affected_slugs": slugs_set,
        "affected_traffic_impressions": int(effective_impressions),
        "outbound_cta_intent_clicks": int(emp_clicks),
        "estimated_monthly_conversions": round(est_monthly_conversions, 2),
        "estimated_monthly_revenue_impact_usd": est_monthly_rev_impact,
    }



def get_profithelm_partner_for_slug(slug: str) -> Optional[AffiliatePartner]:
    """Resolves the optimal ProfitHelm AffiliatePartner for a calculator slug."""
    return resolve_optimal_partner_for_slug("profithelm", slug)


def _select_partner_for_slug(property_id: str, slug: str) -> str:
    """Internal helper to match a tool slug to default partner key."""
    partner = resolve_optimal_partner_for_slug(property_id, slug)
    return partner.key if partner else ""


def get_affiliate_route(
    property_id: str,
    tool_slug: str = "",
    value_tier: str = "starter",
    partner_key: Optional[str] = None,
    source_tool: str = "",
) -> Dict[str, Any]:
    """
    Returns programmatic affiliate route contracts with guaranteed link attributes.
    Enforces strict property isolation:
    - Raises ValueError if B2B partner requested for Prexvo.
    - Raises ValueError if commercial partner requested on a Prexvo restricted public-service page.
    - Raises ValueError if student loan partner requested for ProfitHelm.
    - Guarantees rel='noopener sponsored nofollow' and target='_blank'.
    """
    prop_clean = (property_id or "").strip().lower()
    if prop_clean not in ("profithelm", "prexvo", "exchange1031", "gainhelm", "lienbond"):
        raise ValueError(f"Unknown or unsupported property: '{property_id}'")

    catalog_preview = get_affiliates_for_property(prop_clean)
    eff_partner_arg = partner_key
    eff_slug_arg = tool_slug
    if not eff_partner_arg and source_tool and tool_slug and tool_slug.strip().lower() in catalog_preview:
        eff_partner_arg = tool_slug
        eff_slug_arg = source_tool
    elif source_tool and not eff_slug_arg:
        eff_slug_arg = source_tool

    selected_key = (eff_partner_arg or "").strip().lower()
    slug_clean = (eff_slug_arg or "").strip().lower()

    if prop_clean == "prexvo" and is_restricted_public_service_slug(slug_clean):
        raise ValueError(
            f"Prexvo YMYL guardrail violation: Commercial refinance offers are prohibited on restricted public-service page '{tool_slug}'."
        )

    # Property boundary checks when partner_key is provided
    if selected_key:
        if prop_clean == "prexvo":
            if selected_key in B2B_PARTNER_KEYS or selected_key in PROFITHELM_AFFILIATES or selected_key in GAINHELM_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: B2B partner '{selected_key}' is prohibited on Prexvo."
                )
            if selected_key not in PREXVO_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in Prexvo affiliate registry."
                )
        elif prop_clean in ("profithelm", "exchange1031"):
            if selected_key in STUDENT_LOAN_PARTNER_KEYS or selected_key in PREXVO_AFFILIATES or selected_key in GAINHELM_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: Foreign tenant partner '{selected_key}' is prohibited on ProfitHelm."
                )
            if selected_key not in PROFITHELM_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in ProfitHelm affiliate registry."
                )
        elif prop_clean == "gainhelm":
            if selected_key in STUDENT_LOAN_PARTNER_KEYS or selected_key in PREXVO_AFFILIATES or selected_key in B2B_PARTNER_KEYS:
                raise ValueError(
                    f"Strict isolation violation: Foreign tenant partner '{selected_key}' is prohibited on GainHelm."
                )
            if selected_key not in GAINHELM_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in GainHelm affiliate registry."
                )
        elif prop_clean == "lienbond":
            if selected_key in STUDENT_LOAN_PARTNER_KEYS or selected_key in PREXVO_AFFILIATES or selected_key in GAINHELM_PARTNER_KEYS:
                raise ValueError(
                    f"Strict isolation violation: Foreign tenant partner '{selected_key}' is prohibited on LienBond."
                )
            if selected_key not in LIENBOND_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in LienBond affiliate registry."
                )
    else:
        # Slug boundary validation and auto-selection
        if prop_clean == "prexvo":
            if slug_clean in COMMERCIAL_B2B_SLUGS or slug_clean in GAINHELM_MONETIZED_CALCULATOR_SLUGS or any(
                b2b_token in slug_clean
                for b2b_token in ("saas-runway", "section-179", "section-1031", "qsbs-section-1202", "soc-2", "cmmc", "hipaa")
            ):
                raise ValueError(
                    f"Strict isolation violation: Commercial tool '{tool_slug}' is prohibited on Prexvo."
                )
        elif prop_clean in ("profithelm", "exchange1031"):
            for sl_token in ("student-loan", "rap-vs-ibr", "pslf", "cmmc-2-0", "sprs-score"):
                if sl_token in slug_clean:
                    raise ValueError(
                        f"Strict isolation violation: Foreign tenant tool '{tool_slug}' is prohibited on ProfitHelm."
                    )
        elif prop_clean == "gainhelm":
            for foreign_tok in ("student-loan", "rap-vs-ibr", "pslf", "section-179", "section-1031", "qsbs-section-1202"):
                if foreign_tok in slug_clean:
                    raise ValueError(
                        f"Strict isolation violation: Foreign tenant tool '{tool_slug}' is prohibited on GainHelm."
                    )
        elif prop_clean == "lienbond":
            for foreign_tok in ("student-loan", "rap-vs-ibr", "pslf", "section-179", "section-1031", "qsbs-section-1202", "soc-2-audit", "cmmc-2-0"):
                if foreign_tok in slug_clean:
                    raise ValueError(
                        f"Strict isolation violation: Foreign tenant tool '{tool_slug}' is prohibited on LienBond."
                    )
        selected_key = _select_partner_for_slug(prop_clean, slug_clean)

    # Retrieve partner object
    catalog = get_affiliates_for_property(prop_clean)
    partner_obj = catalog.get(selected_key)
    if not partner_obj:
        raise ValueError(f"Partner '{selected_key}' could not be resolved for property '{property_id}'")

    # Resolve URL
    resolved_url = resolve_partner_url(
        partner_obj,
        value_tier=value_tier,
        tenant=prop_clean,
        source_tool=slug_clean,
    )

    # Escalated CTA text
    tier_clean = (value_tier or "starter").strip().lower()
    is_premium = (tier_clean == "premium")

    if partner_obj.key == "coinledger":
        cta_text = "Import 100+ Transactions to CoinLedger Pro" if is_premium else "Calculate & Export Crypto Taxes with CoinLedger"
    elif partner_obj.key == "koinly":
        cta_text = "Export Multi-Year Crypto Reports with Koinly Pro" if is_premium else "Track Crypto Portfolios with Koinly"
    elif partner_obj.key == "efile_com":
        cta_text = "E-File Complex Federal & State Schedules on E-file.com" if is_premium else "E-File Your Federal & State Tax Return on E-file.com"
    elif partner_obj.key == "eztaxreturn_com":
        cta_text = "File Priority Federal & State Returns on ezTaxReturn.com" if is_premium else "File Your Federal & State Return Fast with ezTaxReturn.com"
    elif partner_obj.key == "freetaxusa":
        cta_text = "File $0 Federal + Deluxe Audit Assist with FreeTaxUSA" if is_premium else "File Federal Taxes Free ($0 Fed) with FreeTaxUSA"
    elif partner_obj.key == "wallethub":
        cta_text = "Compare Institutional Credit & Yield Tiers on WalletHub" if is_premium else "Compare Credit Tiers & Monitor Scores on WalletHub"
    elif partner_obj.key == "lawdepot":
        cta_text = "Draft Custom Commercial & Holding Contracts at LawDepot" if is_premium else "Generate State-Specific LLC, Lease & Holding Agreements at LawDepot"
    elif partner_obj.key == "xendoo":
        cta_text = "Accelerate Section 179 & Business Tax Strategy with Xendoo CPA" if is_premium else "Optimize Business Bookkeeping & Taxes with Xendoo"
    elif partner_obj.key == "turbotax":
        cta_text = "Review TurboTax Live Full Service Options" if is_premium else "Review TurboTax Filing Options"
    elif partner_obj.key == "taxslayer":
        cta_text = "File Complex Schedules with TaxSlayer Self-Employed" if is_premium else "Review TaxSlayer Filing Options"
    elif partner_obj.key == "mercury":
        cta_text = "Open Mercury Treasury Yield Account" if is_premium else "Apply for Mercury Startup Banking"
    elif partner_obj.key == "stripe":
        cta_text = "Explore Stripe Enterprise Billing & Treasury" if is_premium else "Explore Stripe Billing & Payments"
    elif partner_obj.key == "ramp":
        cta_text = "Accelerate Spend Controls with Ramp Pro" if is_premium else "Compare Ramp Corporate Cards"
    elif partner_obj.key == "rho":
        cta_text = "Explore Rho Enterprise Treasury" if is_premium else "Explore Rho Corporate Treasury"
    elif partner_obj.key == "gusto":
        cta_text = "Scale Automated Payroll with Gusto Plus" if is_premium else "Automate S-Corp & Team Payroll with Gusto"
    elif partner_obj.key == "rippling":
        cta_text = "Deploy Global Workforce with Rippling" if is_premium else "Schedule Rippling Demo"
    elif partner_obj.key == "crest_capital":
        cta_text = "Review Commercial Equipment Financing at Crest Capital" if is_premium else "Review Crest Capital Equipment Financing"
    elif partner_obj.key == "ipx1031":
        cta_text = "Review Institutional 1031 Exchange Options at IPX1031" if is_premium else "Review IPX1031 Qualified Intermediary Overview"
    elif partner_obj.key == "exeter1031":
        cta_text = "Review Reverse & Build-to-Suit Exchanges at Exeter 1031" if is_premium else "Review Exeter 1031 Exchange Services"
    elif partner_obj.key == "first_american":
        cta_text = "Review Commercial 1031 Escrow at First American Exchange" if is_premium else "Review First American Exchange Overview"
    elif partner_obj.key == "kalshi":
        cta_text = "Trade Institutional Event Contracts on Kalshi" if is_premium else "Trade Regulated Event Contracts on Kalshi"
    elif partner_obj.key == "interactive_brokers":
        cta_text = "Review Institutional Treasury Desk at Interactive Brokers" if is_premium else "Review Interactive Brokers Treasury Access"
    elif partner_obj.key == "splash_financial":
        cta_text = "Lock In Refinance Terms with Splash Financial" if is_premium else "Compare Rates with Splash Financial"
    elif partner_obj.key == "sofi":
        cta_text = "Unlock Member Rate Discounts with SoFi" if is_premium else "Check Rates with SoFi"
    elif partner_obj.key == "credible":
        cta_text = "Lock In Prequalified Rates with Credible" if is_premium else "Compare Rates with Credible"
    elif partner_obj.key == "earnest":
        cta_text = "Customize Precision Schedule with Earnest" if is_premium else "Check Rates with Earnest"
    elif partner_obj.key == "lendkey":
        cta_text = "Access Relationship Rates with LendKey" if is_premium else "Explore Community Rates with LendKey"
    elif prop_clean == "gainhelm":
        ctx_gh = resolve_contextual_partner_offer_copy(
            partner_key=partner_obj.key,
            p_obj=partner_obj,
            slug=slug_clean,
            property_id="gainhelm",
        )
        cta_text = (
            f"Explore {ctx_gh['name']} Pro Solutions"
            if is_premium
            else (ctx_gh["cta_text"] or f"Explore {ctx_gh['name']} Solutions")
        )
    else:
        cta_text = (
            f"Explore {partner_obj.name} Pro Solutions" if is_premium else (partner_obj.cta_text or f"Explore {partner_obj.name} Solutions")
        )

    eff_name = ctx_gh["name"] if prop_clean == "gainhelm" else partner_obj.name
    eff_badge = ctx_gh["badge"] if prop_clean == "gainhelm" else partner_obj.badge

    # Validate output for forbidden dashes
    assert_no_forbidden_dashes(cta_text, context=f"CTA text for {partner_obj.key}")
    assert_no_forbidden_dashes(eff_name, context=f"Partner name for {partner_obj.key}")
    assert_no_forbidden_dashes(eff_badge, context=f"Badge for {partner_obj.key}")

    disclosure_text = (
        PREXVO_DISCLOSURES.get("ftc_disclosure", "")
        if prop_clean == "prexvo"
        else (
            GAINHELM_DISCLOSURES.get("ftc_disclosure", "")
            if prop_clean == "gainhelm"
            else (
                LIENBOND_DISCLOSURES.get("ftc_disclosure", "")
                if prop_clean == "lienbond"
                else PROFITHELM_DISCLOSURES.get("ftc_disclosure", "")
            )
        )
    )
    ymyl_warning = (
        PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")
        if prop_clean == "prexvo"
        else (
            get_gainhelm_statutory_disclaimer(slug_clean)
            if prop_clean == "gainhelm"
            else (
                LIENBOND_DISCLOSURES.get("statutory_compliance_disclaimer", "")
                if prop_clean == "lienbond"
                else ""
            )
        )
    )

    return {
        "property_id": prop_clean,
        "calculator_slug": slug_clean,
        "partner": partner_obj.key,
        "partner_key": partner_obj.key,
        "name": eff_name,
        "partner_name": eff_name,
        "url": resolved_url,
        "cta_text": cta_text,
        "rel": "noopener sponsored nofollow",
        "target": "_blank",
        "badge": eff_badge,
        "status": partner_obj.status,
        "partnership_model": partner_obj.partnership_model,
        "bounty_est": partner_obj.bounty_est,
        "bounty_score": score_partner_yield(partner_obj, partner_obj.status),
        "is_fallback": False,
        "tier": value_tier,
        "disclosure_required": True,
        "disclosure": disclosure_text,
        "ymyl_warning": ymyl_warning,
    }


UNMONETIZABLE_NOISE_TOKENS: Set[str] = {
    "celebrity",
    "gossip",
    "red carpet",
    "red-carpet",
    "concert",
    "movie trailer",
    "horoscope",
    "meme",
    "tiktok dance",
    "weather radar",
    "wordle",
    "crossword",
    "login page",
    "customer service number",
    "forgot password",
    "down detector",
    "box office",
    "super bowl halftime",
    "oscars",
    "grammys",
    "nfl score",
    "nba score",
    "funny video",
    "viral prank",
}

STUDENT_LOAN_INTENT_TOKENS: Tuple[str, ...] = (
    "student loan",
    "student-loan",
    "pslf",
    "ibr",
    "rap",
    "save plan",
    "save-plan",
    "fafsa",
    "nelnet",
    "mohela",
    "aidvantage",
    "edfinancial",
    "title iv",
    "title-iv",
    "forbearance",
    "deferment",
    "parent plus",
    "parent-plus",
    "borrower defense",
    "consolidation loan",
    "consolidation-loan",
    "loan repayment",
    "loan-repayment",
    "idr",
)

COMMERCIAL_B2B_INTENT_TOKENS: Tuple[str, ...] = (
    "section 179",
    "section-179",
    "179d",
    "cost segregation",
    "cost-segregation",
    "1031 exchange",
    "section 1031",
    "section-1031",
    "macrs",
    "bonus depreciation",
    "qsbs",
    "section 1202",
    "section-1202",
    "corporate amt",
    "corporate-amt",
    "camt",
    "saas runway",
    "saas-runway",
    "burn rate",
    "burn-rate",
    "r&d tax",
    "r-and-d",
    "section 174",
    "payroll tax",
    "equipment financing",
    "commercial real estate",
    "working capital",
    "venture debt",
    "treasury management",
    "s-corp payroll",
    "c-corp",
    "corporate card",
)

CONSUMER_FINANCIAL_INTENT_TOKENS: Tuple[str, ...] = (
    "tax bracket",
    "tax-bracket",
    "capital gains",
    "capital-gains",
    "crypto tax",
    "crypto-tax",
    "staking tax",
    "airdrop tax",
    "form 8949",
    "form 8829",
    "home office deduction",
    "1099-da",
    "tcja",
    "standard deduction",
    "child tax credit",
    "earned income",
    "marginal tax",
    "effective tax",
    "kalshi",
    "polymarket",
    "prediction market",
    "prediction-market",
    "implied probability",
    "kelly criterion",
    "no-vig",
    "event contract",
    "treasury bill",
    "t-bill",
    "tbill",
    "high yield savings",
    "apy calculator",
    "roth ira",
    "401k",
    "self employment tax",
    "quarterly estimated tax",
)

PROSPECTIVE_NICHE_TOOL_TOKENS: Tuple[str, ...] = (
    "calculator",
    "estimator",
    "matrix",
    "modeler",
    "simulator",
    "projection",
    "penalty",
    "compliance",
    "audit",
    "roi",
    "yield",
    "margin",
    "markup",
    "premium",
    "insurance",
    "financing",
    "factoring",
    "credit",
    "deduction",
    "subsidy",
    "tariff",
    "duty",
    "settlement",
    "valuation",
    "amortization",
    "lease",
    "buyout",
    "surety",
    "bond",
    "malpractice",
    "solar itc",
    "nem 3.0",
    "demand charge",
    "srec",
    "hipaa",
    "soc2",
    "soc 2",
    "cmmc",
    "sprs",
    "nmfc",
    "hts",
    "demurrage",
    "retainage",
    "lien",
    "wrvu",
    "rvu",
    "rate",
    "cost",
    "fee",
    "payback",
)


def verify_partner_domain_alignment(
    property_id: str,
    slug: str,
    partners: List[str],
) -> Dict[str, Any]:
    """
    Mechanically verifies that partner keys assigned to a property and slug
    never mix incompatible offers across domains or between B2B and retail tax tiers.
    """
    prop = (property_id or "").strip().lower()
    s_clean = (slug or "").strip().lower()
    clean_partners = [str(p).strip().lower() for p in (partners or []) if str(p).strip()]
    violations: List[str] = []

    if prop == "prexvo":
        if is_restricted_public_service_slug(s_clean) and clean_partners:
            violations.append(
                f"Prexvo YMYL public-service guardrail violation: commercial partners {clean_partners} are prohibited on restricted public-service slug '{s_clean}'."
            )
        for pk in clean_partners:
            if pk in B2B_PARTNER_KEYS or pk in PROFITHELM_AFFILIATES or pk in GAINHELM_AFFILIATES or pk == "sovrn_commerce":
                violations.append(
                    f"Prexvo isolation violation: prohibited commercial/aggregator partner '{pk}' on '{s_clean}'."
                )
            elif pk not in PREXVO_AFFILIATES and pk not in STUDENT_LOAN_PARTNER_KEYS:
                violations.append(
                    f"Prexvo registry violation: unapproved partner '{pk}' on '{s_clean}'."
                )
    elif prop == "gainhelm":
        for pk in clean_partners:
            if pk in STUDENT_LOAN_PARTNER_KEYS or pk in PREXVO_AFFILIATES or pk in B2B_PARTNER_KEYS or pk in PROFITHELM_AFFILIATES:
                violations.append(
                    f"GainHelm isolation violation: foreign tenant partner '{pk}' prohibited on '{s_clean}'."
                )
            elif pk not in GAINHELM_AFFILIATES and pk not in GAINHELM_PARTNER_KEYS:
                violations.append(
                    f"GainHelm registry violation: unapproved partner '{pk}' on '{s_clean}'."
                )
    elif prop == "lienbond":
        for pk in clean_partners:
            if (
                pk in STUDENT_LOAN_PARTNER_KEYS
                or pk in PREXVO_AFFILIATES
                or pk in GAINHELM_AFFILIATES
                or (pk in PROFITHELM_AFFILIATES and pk not in LIENBOND_AFFILIATES)
            ):
                violations.append(
                    f"LienBond isolation violation: foreign tenant partner '{pk}' prohibited on '{s_clean}'."
                )
            elif pk not in LIENBOND_AFFILIATES and pk not in LIENBOND_PARTNER_KEYS:
                violations.append(
                    f"LienBond registry violation: unapproved partner '{pk}' on '{s_clean}'."
                )
    elif prop in ("profithelm", "exchange1031"):
        is_b2b = is_commercial_b2b_slug(s_clean)
        is_retail = (s_clean in RETAIL_TAX_SLUGS) or (not is_b2b and any(
            t in s_clean for t in ("tax-bracket", "capital-gains", "crypto-tax", "tcja", "prediction-market-tax")
        ))
        for pk in clean_partners:
            if pk in STUDENT_LOAN_PARTNER_KEYS or pk in PREXVO_AFFILIATES or pk in GAINHELM_AFFILIATES:
                violations.append(
                    f"ProfitHelm isolation violation: foreign tenant partner '{pk}' prohibited on '{s_clean}'."
                )
            if is_b2b and pk in RETAIL_TAX_PARTNERS:
                violations.append(
                    f"Intent entanglement violation: retail tax partner '{pk}' mixed into commercial B2B slug '{s_clean}'."
                )
            if is_retail and pk in ENTERPRISE_B2B_PARTNERS:
                violations.append(
                    f"Intent entanglement violation: enterprise B2B partner '{pk}' mixed into consumer/retail slug '{s_clean}'."
                )

    return {
        "aligned": len(violations) == 0,
        "property_id": prop,
        "slug": s_clean,
        "partners": clean_partners,
        "violations": violations,
    }


def qualify_monetization_opportunity(
    query: str,
    slug: str = "",
    property_id: Optional[str] = None,
    search_volume: int = 0,
    cpc_usd: float = 0.0,
    jev_score: float = 1.25,
    durable_prob: float = 0.55,
    vault_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Canonical monetization qualification and niche expansion scoring model.
    Untangles commercial B2B, consumer financial, Title IV student loan YMYL,
    and prospective greenfield niche expansions without shadow evaluators.
    """
    q_clean = (query or "").strip()
    q_lower = q_clean.lower()
    s_clean = (slug or "").strip().lower()
    if not s_clean and q_lower:
        s_clean = re.sub(r"[^a-z0-9]+", "-", q_lower).strip("-")
    combined = f"{q_lower} {s_clean}".strip()
    prop_explicit = (property_id or "").strip().lower()

    vol = max(0, int(search_volume or 0))
    cpc = max(0.0, float(cpc_usd or 0.0))
    jev = max(0.0, float(jev_score or 0.0))
    dur = max(0.0, min(1.0, float(durable_prob or 0.0)))

    # 1. Reject transient/navigational noise immediately
    if not combined or any(noise in combined for noise in UNMONETIZABLE_NOISE_TOKENS):
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit or "unassigned",
            "intent_tier": "unmonetizable_noise",
            "monetization_qualified": False,
            "rejection_reason": "Unmonetizable transient or navigational noise signal",
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": True,
            "disclosures_required": {},
        }

    is_student_loan = any(
        (bool(re.search(rf"\b{re.escape(tok)}\b", combined)) if len(tok) <= 4 else (tok in combined))
        for tok in STUDENT_LOAN_INTENT_TOKENS
    )
    is_b2b = is_commercial_b2b_slug(s_clean) or any(tok in combined for tok in COMMERCIAL_B2B_INTENT_TOKENS)
    is_consumer_fin = (s_clean in RETAIL_TAX_SLUGS) or any(tok in combined for tok in CONSUMER_FINANCIAL_INTENT_TOKENS)
    has_tool_signal = any(tok in combined for tok in PROSPECTIVE_NICHE_TOOL_TOKENS)
    is_gainhelm = any(
        tok in combined
        for tok in (
            "ssae 18",
            "soc 2",
            "soc-2",
            "soc2",
            "cmmc",
            "c3pao",
            "32 cfr part 170",
            "nist 800-171",
            "nist-800-171",
            "sprs score",
            "sprs-score",
            "iso 27001",
            "iso-27001",
            "iso 27006",
            "45 cfr 160.404",
            "hipaa",
            "hitrust",
            "fedramp",
            "pci dss",
            "pci-dss",
            "penetration testing",
            "penetration-testing",
            "cyber liability insurance",
            "cyber-liability-insurance",
            "dora",
            "eu ai act",
            "eu-ai-act",
            "conformity assessment",
            "conformity-assessment",
            "sec cybersecurity",
            "sec-cybersecurity",
            "item 1.05",
            "item-105",
            "8-k",
        )
    )
    is_lienbond = any(
        tok in combined
        for tok in (
            "surety",
            "bond",
            "mechanics lien",
            "mechanics-lien",
            "lien release",
            "lien-release",
            "preliminary notice",
            "preliminary-notice",
            "retainage",
            "workers comp",
            "workers-comp",
            "workers compensation",
            "workers-compensation",
            "emr",
            "experience modification",
            "davis-bacon",
            "davis bacon",
            "wh-347",
            "subcontractor default insurance",
            "subcontractor-default-insurance",
            "sdi",
            "circular 570",
            "miller act",
            "miller-act",
            "erisa fidelity",
            "markup vs margin",
            "markup-vs-margin",
        )
    )

    # 2. Enforce strict cross-tenant isolation when property_id is explicitly bound
    if prop_explicit == "prexvo":
        if is_b2b or is_gainhelm or any(
            b2b_kw in combined
            for b2b_kw in ("section 179", "section-179", "1031", "saas", "runway", "burn rate", "qsbs", "corporate amt", "mercury", "ramp", "rippling", "gusto")
        ):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "prexvo",
                "intent_tier": "cross_tenant_contamination",
                "monetization_qualified": False,
                "rejection_reason": "Strict isolation violation: Commercial B2B intent is prohibited on Prexvo.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(PREXVO_DISCLOSURES),
            }
        if not (is_student_loan or is_restricted_public_service_slug(s_clean, q_lower)):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "prexvo",
                "intent_tier": "out_of_scope_prexvo",
                "monetization_qualified": False,
                "rejection_reason": "Prexvo requires Title IV or student loan repayment/refinance intent.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(PREXVO_DISCLOSURES),
            }

    if prop_explicit in ("profithelm", "exchange1031") and (is_student_loan or (is_gainhelm and not is_b2b)):
        rej_msg = (
            "Strict isolation violation: Student loan intent is prohibited on ProfitHelm."
            if is_student_loan
            else "Strict isolation violation: GainHelm cyber compliance intent is prohibited on ProfitHelm."
        )
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit,
            "intent_tier": "cross_tenant_contamination",
            "monetization_qualified": False,
            "rejection_reason": rej_msg,
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": False,
            "disclosures_required": dict(PROFITHELM_DISCLOSURES),
        }

    if prop_explicit == "gainhelm":
        if is_student_loan or is_b2b or any(
            k in combined
            for k in (
                "section 179",
                "section-179",
                "section 1031",
                "1031 exchange",
                "qsbs",
                "corporate amt",
                "section 174",
                "s-corp",
                "s corp",
                "macrs",
                "bonus depreciation",
            )
        ):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "gainhelm",
                "intent_tier": "cross_tenant_contamination",
                "monetization_qualified": False,
                "rejection_reason": "Strict isolation violation: Foreign tenant tax or student loan intent is prohibited on GainHelm.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(GAINHELM_DISCLOSURES),
            }
        if not is_gainhelm:
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "gainhelm",
                "intent_tier": "out_of_scope_gainhelm",
                "monetization_qualified": False,
                "rejection_reason": "GainHelm requires enterprise cybersecurity compliance, GRC audit, or statutory security governance intent.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(GAINHELM_DISCLOSURES),
            }

    if prop_explicit == "lienbond":
        if is_student_loan or is_gainhelm or any(
            k in combined
            for k in (
                "section 179",
                "section-179",
                "section 1031",
                "1031 exchange",
                "qsbs",
                "corporate amt",
                "section 174",
                "s-corp",
                "s corp",
                "macrs",
                "bonus depreciation",
            )
        ):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "lienbond",
                "intent_tier": "cross_tenant_contamination",
                "monetization_qualified": False,
                "rejection_reason": "Strict isolation violation: Foreign tenant tax, cyber, or student loan intent is prohibited on LienBond.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(LIENBOND_DISCLOSURES),
            }
        if not is_lienbond:
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "lienbond",
                "intent_tier": "out_of_scope_lienbond",
                "monetization_qualified": False,
                "rejection_reason": "LienBond requires construction surety bond, workers compensation, mechanics lien, or prevailing wage intent.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(LIENBOND_DISCLOSURES),
            }

    is_restricted_ps = False
    commercial_offers_allowed = True
    greenfield_meta: Dict[str, Any] = {}

    # 3. Route to canonical intent tier and property
    if prop_explicit == "lienbond" or (not prop_explicit and is_lienbond and not is_student_loan and not is_gainhelm and not is_b2b):
        resolved_prop = "lienbond"
        intent_tier = "construction_surety_workers_comp_lien"
        primary_obj = resolve_optimal_partner_for_slug("lienbond", s_clean, vault_overrides=vault_overrides)
        rec_partners = [k for k in LIENBOND_AFFILIATES.keys()]
        if primary_obj and primary_obj.key in rec_partners:
            rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
        bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 180.0)) if primary_obj else 180.0
        eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 180.0
        intent_weight = 1.35
        y_asset = round(min(1.85, max(0.95, (bounty_usd / 180.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
        disclosures = dict(LIENBOND_DISCLOSURES)
        alignment = verify_partner_domain_alignment("lienbond", s_clean, rec_partners)
        qualified = bool(alignment["aligned"] and len(rec_partners) > 0)
        rejection_reason = "" if qualified else "Failed LienBond partner alignment or monetization threshold"
    elif prop_explicit == "gainhelm" or (not prop_explicit and is_gainhelm and not is_student_loan):
        resolved_prop = "gainhelm"
        intent_tier = "enterprise_cyber_compliance_grc"
        primary_obj = resolve_optimal_partner_for_slug("gainhelm", s_clean, vault_overrides=vault_overrides)
        rec_partners = [k for k in GAINHELM_AFFILIATES.keys()]
        if primary_obj and primary_obj.key in rec_partners:
            rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
        bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 325.0)) if primary_obj else 325.0
        eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 325.0
        intent_weight = 1.40
        y_asset = round(min(1.85, max(0.95, (bounty_usd / 250.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
        disclosures = dict(GAINHELM_DISCLOSURES)
        alignment = verify_partner_domain_alignment("gainhelm", s_clean, rec_partners)
        qualified = bool(alignment["aligned"] and len(rec_partners) > 0)
        rejection_reason = "" if qualified else "Failed GainHelm partner alignment or monetization threshold"
    elif is_student_loan or prop_explicit == "prexvo":
        resolved_prop = "prexvo"
        intent_tier = "student_loan_ymyl"
        is_restricted_ps = is_restricted_public_service_slug(s_clean, q_lower)
        disclosures = dict(PREXVO_DISCLOSURES)
        disclosures["standing_restriction"] = PREXVO_STANDING_RESTRICTION
        if is_restricted_ps:
            commercial_offers_allowed = False
            primary_obj = None
            rec_partners = []
            bounty_usd = 0.0
            eff_yield = 0.0
            intent_weight = 1.05
            y_asset = round(min(1.25, max(0.70, (cpc / 5.0) * 0.45 + 0.65)), 4)
            alignment = verify_partner_domain_alignment("prexvo", s_clean, rec_partners)
            qualified = bool(alignment["aligned"] and (jev >= 1.0 or cpc >= 1.50 or vol >= 50))
            rejection_reason = "" if qualified else "Failed Prexvo public-service demand qualification threshold"
        else:
            primary_obj = resolve_optimal_partner_for_slug("prexvo", s_clean, vault_overrides=vault_overrides)
            rec_partners = [
                k for k in INTENT_ROUTING_TABLE["student-loan"]
                if k in PREXVO_AFFILIATES and k not in B2B_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key in rec_partners:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 325.0)) if primary_obj else 325.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 113.75
            intent_weight = 1.15
            y_asset = round(min(1.45, max(0.75, (bounty_usd / 300.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
            gate_1_passed = bounty_usd >= 45.0
            alignment = verify_partner_domain_alignment("prexvo", s_clean, rec_partners)
            qualified = bool(gate_1_passed and alignment["aligned"] and (jev >= 1.0 or cpc >= 1.50 or vol >= 50))
            rejection_reason = "" if qualified else "Failed Prexvo Gate 1 or demand qualification threshold"

    elif prop_explicit == "unassigned" or (not prop_explicit and not is_b2b and not is_consumer_fin and has_tool_signal):
        resolved_prop = "unassigned"
        intent_tier = "prospective_niche_expansion"
        from pseofactory.market_intel import (
            match_greenfield_vertical,
            score_active_commission_offers,
            score_buyer_intent,
        )
        v_match = match_greenfield_vertical(combined)
        comm_eval = score_active_commission_offers(
            v_match["vertical_id"] if v_match else combined,
            cpc_usd=cpc,
        )
        buyer_eval = score_buyer_intent(q_clean or s_clean, cpc_usd=cpc)

        is_comm_niche = bool(v_match is not None) or any(
            t in combined
            for t in (
                "commercial", "enterprise", "corporate", "b2b", "compliance",
                "hipaa", "soc2", "soc 2", "cmmc", "sprs", "freight", "factoring",
                "solar itc", "nem 3.0", "demand charge", "srec", "surety", "bond",
                "workers comp", "malpractice", "equipment", "lease", "buyout",
                "tariff", "hts", "nmfc", "lien", "retainage", "wrvu", "rvu",
            )
        )
        synth_bounty = round(max(120.0, cpc * 28.0) if (is_comm_niche or cpc >= 4.0) else max(45.0, cpc * 18.0), 2)
        if v_match is not None and comm_eval.primary_offer is not None:
            bounty_usd = round(max(synth_bounty, comm_eval.expected_bounty_usd), 2)
            eff_yield = round(max(bounty_usd * 0.38, comm_eval.effective_partner_yield), 2)
            all_offers = [comm_eval.primary_offer] + list(comm_eval.backup_offers)
            rec_partners = [o.partner_key for o in all_offers]
            intent_weight = round(1.25 + min(0.15, (comm_eval.commission_offer_score / 100.0) * 0.15), 4)
        else:
            bounty_usd = synth_bounty
            eff_yield = round(bounty_usd * 0.35, 2)
            rec_partners = ["direct_cpa_lead_gen"] if (is_comm_niche or cpc >= 4.0) else ["programmatic_affiliate_cpa"]
            intent_weight = 1.20 if (is_comm_niche or cpc >= 4.0) else 0.95

        y_asset = round(min(1.75, max(0.55, (bounty_usd / 200.0) * 0.55 + (cpc / 4.5) * 0.45)), 4)
        disclosures = dict(PROFITHELM_DISCLOSURES)
        alignment = {"aligned": True, "violations": []}
        qualified = bool(
            has_tool_signal
            and (cpc >= 1.50 or bounty_usd >= 75.0)
            and vol >= 100
            and jev >= 1.0
            and dur >= 0.45
        )
        rejection_reason = "" if qualified else "Prospective niche below minimum CPC/volume/durability monetization bar"
        primary_obj = None
        greenfield_meta = {
            "vertical_id": comm_eval.vertical_id,
            "recommended_tenant_id": v_match["tenant_id"] if v_match else "unassigned",
            "recommended_domain": v_match["recommended_domain"] if v_match else "",
            "buyer_intent_score": buyer_eval.buyer_intent_score,
            "commission_offer_score": comm_eval.commission_offer_score,
            "active_offers_count": comm_eval.active_offers_count,
            "instant_active_offers_count": comm_eval.instant_active_offers_count,
            "networks_represented": comm_eval.networks_represented,
            "min_approval_friction_days": comm_eval.min_approval_friction_days,
            "active_commission_offers": (
                ([comm_eval.primary_offer.to_dict()] if comm_eval.primary_offer else [])
                + [o.to_dict() for o in comm_eval.backup_offers]
            ),
        }

    elif is_b2b or is_consumer_fin or prop_explicit in ("profithelm", "exchange1031"):
        resolved_prop = "exchange1031" if (prop_explicit == "exchange1031" or "1031" in s_clean) and prop_explicit == "exchange1031" else "profithelm"
        if is_b2b and not (s_clean in RETAIL_TAX_SLUGS):
            intent_tier = "commercial_b2b"
            primary_obj = resolve_optimal_partner_for_slug(resolved_prop, s_clean, vault_overrides=vault_overrides)
            # Determine matching B2B routing bucket
            bucket = _resolve_profithelm_bucket(f"{s_clean}-{combined.replace(' ', '-')}")
            if bucket in ("tax", "crypto", "capital-gains", "prediction-market-tax", "prediction"):
                bucket = "runway"
            raw_partners = INTENT_ROUTING_TABLE.get(bucket, ["mercury", "ramp", "stripe"])
            rec_partners = [
                k for k in raw_partners
                if k in PROFITHELM_AFFILIATES
                and k not in RETAIL_TAX_PARTNERS
                and k not in STUDENT_LOAN_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key not in RETAIL_TAX_PARTNERS:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 250.0)) if primary_obj else 250.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 87.50
            intent_weight = 1.35
            y_asset = round(min(1.85, max(0.85, (bounty_usd / 250.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
        else:
            intent_tier = "consumer_financial"
            primary_obj = resolve_optimal_partner_for_slug("profithelm", s_clean, vault_overrides=vault_overrides)
            bucket = "tax"
            if any(t in combined for t in ("crypto", "token", "staking", "airdrop", "8949", "1099-da")):
                bucket = "crypto"
            elif "capital-gains" in combined or "capital gains" in combined:
                bucket = "capital-gains"
            elif "prediction" in combined and "tax" in combined:
                bucket = "prediction-market-tax"
            elif any(t in combined for t in ("prediction", "kalshi", "polymarket", "odds", "arbitrage", "kelly", "vig")):
                bucket = "prediction"
            elif any(t in combined for t in ("treasury", "tbill", "t-bill", "yield", "apy")):
                bucket = "treasury"
            raw_partners = INTENT_ROUTING_TABLE.get(bucket, ["turbotax", "taxslayer", "freetaxusa"])
            rec_partners = [
                k for k in raw_partners
                if k in PROFITHELM_AFFILIATES
                and k not in ENTERPRISE_B2B_PARTNERS
                and k not in STUDENT_LOAN_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key not in ENTERPRISE_B2B_PARTNERS:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 65.0)) if primary_obj else 65.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 22.75
            intent_weight = 1.05
            y_asset = round(min(1.35, max(0.60, (bounty_usd / 100.0) * 0.60 + (cpc / 4.0) * 0.40)), 4)

        disclosures = dict(PROFITHELM_DISCLOSURES)
        alignment = verify_partner_domain_alignment(resolved_prop, s_clean, rec_partners)
        qualified = bool(alignment["aligned"] and len(rec_partners) > 0 and (jev >= 1.0 or cpc >= 1.0 or bounty_usd >= 40.0))
        rejection_reason = "" if qualified else "Failed ProfitHelm partner alignment or monetization threshold"
    else:
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit or "unassigned",
            "intent_tier": "unmonetizable_noise",
            "monetization_qualified": False,
            "rejection_reason": "No commercial, consumer financial, student loan, or quantitative tool intent detected",
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": True,
            "disclosures_required": {},
        }

    est_clicks = max(10.0, float(vol)) * 0.12
    est_conversions = est_clicks * 0.018
    unit_rev = max(eff_yield, cpc * 2.5) if commercial_offers_allowed else 0.0
    est_monthly_rev = round(est_conversions * unit_rev * max(0.5, dur) * intent_weight, 2) if (qualified and commercial_offers_allowed) else 0.0

    primary_partner_key = (
        primary_obj.key
        if primary_obj is not None
        else (rec_partners[0] if rec_partners else "")
    )

    # Resolve 3-rail value ladder: Direct Stripe Digital Asset + B2B Quote Intake + Affiliate Bounty
    stripe_asset_meta: Dict[str, Any] = {
        "eligible": False,
        "offer_sku": "",
        "offer_title": "",
        "offer_price_usd": 0.0,
        "deliverables": [],
        "trend_timeseries_ids": [],
    }
    b2b_quote_meta: Dict[str, Any] = {
        "eligible": False,
        "threshold_usd": 0.0,
        "vertical": "none",
    }
    monetization_rail_mix = "unmonetized"
    est_stripe_asset_rev = 0.0

    if is_restricted_ps or not commercial_offers_allowed:
        monetization_rail_mix = "public_service_non_commercial"
    elif qualified:
        try:
            from pseofactory.partner_tracker import (
                evaluate_lead_quote_threshold,
                resolve_lead_monetization_offer,
            )
            eff_prop_for_offer = (
                "prexvo"
                if resolved_prop == "prexvo"
                else (
                    "gainhelm"
                    if resolved_prop == "gainhelm"
                    else ("lienbond" if resolved_prop == "lienbond" else "profithelm")
                )
            )
            quote_eval = evaluate_lead_quote_threshold(eff_prop_for_offer, s_clean or "general", 250000.0)
            b2b_quote_meta = {
                "eligible": bool(quote_eval.get("eligible")),
                "threshold_usd": float(quote_eval.get("threshold_usd") or 0.0),
                "vertical": str(quote_eval.get("vertical") or "general"),
            }
            offer_eval = resolve_lead_monetization_offer(
                property_id=eff_prop_for_offer,
                tool_slug=s_clean or "general",
                vertical=b2b_quote_meta["vertical"],
            )
            ts_ids = (
                ["ed_direct_undergrad_rate", "ed_idr_discretionary_levy", "ed_idr_fpl_multiplier", "hhs_fpl_single_base", "irs_sec108f_tax_free_forgiveness"]
                if eff_prop_for_offer == "prexvo"
                else (
                    ["dod_32cfr170_cmmc_controls", "nist_800_171_sprs_max", "hhs_ocr_hipaa_tier4_cap", "iso_27006_stage2_days"]
                    if eff_prop_for_offer == "gainhelm"
                    else (
                        ["fred_dgs10_yield", "fred_cpilfesl_inflation", "irs_sec199a_qbi"]
                        if offer_eval["offer_sku"] == "ph_1031_boot_replacement_workpapers"
                        else (
                            ["irs_sec179_cap", "irs_sec179_phaseout", "irs_sec168k_bonus", "cbp_sec301_tariff", "fred_dgs10_yield"]
                            if offer_eval["offer_sku"] == "ph_commercial_capital_audit_toolkit"
                            else ["irs_sec199a_qbi", "ssa_fica_wage_base", "irs_sec168k_bonus", "fred_cpilfesl_inflation"]
                        )
                    )
                )
            )
            stripe_asset_meta = {
                "eligible": True,
                "offer_sku": str(offer_eval["offer_sku"]),
                "offer_title": str(offer_eval["offer_title"]),
                "offer_price_usd": float(offer_eval["offer_price_usd"]),
                "deliverables": list(offer_eval.get("deliverables") or []),
                "trend_timeseries_ids": ts_ids,
            }
            est_stripe_asset_rev = round(
                est_clicks * 0.012 * float(offer_eval["offer_price_usd"]) * max(0.5, dur),
                2,
            )
            monetization_rail_mix = (
                "three_rail_b2b_quote_stripe_asset_and_affiliate"
                if b2b_quote_meta["eligible"]
                else "dual_rail_stripe_asset_and_affiliate"
            )
        except Exception:
            monetization_rail_mix = "affiliate_only"

    result_payload: Dict[str, Any] = {
        "query": q_clean,
        "slug": s_clean,
        "property_id": resolved_prop,
        "intent_tier": intent_tier,
        "monetization_qualified": qualified,
        "commercial_offers_allowed": commercial_offers_allowed,
        "restricted_public_service": is_restricted_ps,
        "monetization_rail_mix": monetization_rail_mix,
        "stripe_digital_asset": stripe_asset_meta,
        "b2b_quote_intake": b2b_quote_meta,
        "rejection_reason": rejection_reason,
        "primary_partner": primary_partner_key,
        "recommended_partners": rec_partners[:3],
        "expected_bounty_usd": round(bounty_usd, 2),
        "effective_partner_yield": round(eff_yield, 2),
        "intent_weight": round(intent_weight, 4),
        "y_asset": y_asset,
        "estimated_monthly_revenue_usd": est_monthly_rev,
        "estimated_stripe_asset_monthly_revenue_usd": est_stripe_asset_rev,
        "total_compounded_monthly_revenue_usd": round(est_monthly_rev + est_stripe_asset_rev, 2),
        "partner_alignment_verified": bool(alignment["aligned"]),
        "alignment_violations": alignment.get("violations", []),
        "disclosures_required": disclosures,
    }
    if greenfield_meta:
        result_payload.update(greenfield_meta)
    return result_payload


# Verified Approved Direct & Network Merchant Contracts (Brand-Honest, Zero Cross-Brand Swaps)
# Every entry here corresponds to a verified, active paying affiliate contract for ProfitHelm LLC
# across Impact.com (#7932737), CJ Affiliate (#101906407), PartnerStack, FirstPromoter, and Mercury Direct.
SOVRN_VERIFIED_PAYING_MERCHANTS: Dict[str, Dict[str, Any]] = {
    "coinledger": {
        "partner_key": "coinledger",
        "verified_merchant_name": "CoinLedger Crypto Tax",
        "verified_url": "https://coinledger.io/?fpr=arif-554004",
        "is_direct": True,
        "approved": True,
        "payout_rate": "25.0% recurring ($35-$90/sale)",
        "network": "FirstPromoter",
        "swapped_from_non_paying": False,
    },
    "koinly": {
        "partner_key": "koinly",
        "verified_merchant_name": "Koinly Crypto Tax Software",
        "verified_url": "https://koinly.io/?via=F0D55B86&utm_source=affiliate",
        "is_direct": True,
        "approved": True,
        "payout_rate": "20.0% one-time first purchase",
        "network": "Koinly Native Affiliate",
        "swapped_from_non_paying": False,
    },
    "mercury": {
        "partner_key": "mercury",
        "verified_merchant_name": "Mercury Startup Banking",
        "verified_url": "https://mercury.com/r/profithelm-llc",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$250.00 USD CPA",
        "network": "In-House Direct",
        "swapped_from_non_paying": False,
    },
    "rippling": {
        "partner_key": "rippling",
        "verified_merchant_name": "Rippling Unified Workforce Platform",
        "verified_url": "https://try.rippling.com/mcfo1m09qiwt",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$600.00 USD SQO + $1,000.00 USD Closed Won",
        "network": "PartnerStack",
        "swapped_from_non_paying": False,
    },
    "gusto": {
        "partner_key": "gusto",
        "verified_merchant_name": "Gusto Payroll, Benefits & HR Platform",
        "verified_url": "https://gusto.pxf.io/c/7932737/1226287/15154",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$200.00-$300.00 USD CPA per Sale",
        "network": "Impact.com",
        "swapped_from_non_paying": False,
    },
    "ramp": {
        "partner_key": "ramp",
        "verified_merchant_name": "Ramp Corporate Card & Spend Management",
        "verified_url": "https://join.ramp.com/c/7932737/3981015/51436",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$100-$4,000 Closed Won / $50-$2,000 SQL",
        "network": "Impact.com",
        "swapped_from_non_paying": False,
    },
    "xendoo": {
        "partner_key": "xendoo",
        "verified_merchant_name": "Xendoo Online Bookkeeping & CPA Tax Advisory",
        "verified_url": "https://xendoo.pxf.io/c/7932737/1357375/16354",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$500.00 USD Onboarded Client",
        "network": "Impact.com",
        "swapped_from_non_paying": False,
    },
    "kalshi": {
        "partner_key": "kalshi",
        "verified_merchant_name": "Kalshi CFTC-Regulated Event Contract Exchange",
        "verified_url": "https://kalshi.pxf.io/c/7932737/3078072/37770",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$40.00 USD CPA per Qualified Trade",
        "network": "Impact.com",
        "swapped_from_non_paying": False,
    },
    "efile_com": {
        "partner_key": "efile_com",
        "verified_merchant_name": "E-file.com IRS Authorized Online Tax Filing",
        "verified_url": "https://www.jdoqocy.com/click-101906407-11917161",
        "is_direct": True,
        "approved": True,
        "payout_rate": "30%-40% revshare",
        "network": "CJ Affiliate",
        "swapped_from_non_paying": False,
    },
    "eztaxreturn_com": {
        "partner_key": "eztaxreturn_com",
        "verified_merchant_name": "ezTaxReturn.com Fast Federal & State Online Tax Filing",
        "verified_url": "https://www.dpbolvw.net/click-101906407-15704796",
        "is_direct": True,
        "approved": True,
        "payout_rate": "15% new / 5% returning",
        "network": "CJ Affiliate",
        "swapped_from_non_paying": False,
    },
    "freetaxusa": {
        "partner_key": "freetaxusa",
        "verified_merchant_name": "FreeTaxUSA $0 Federal Online Tax Return Filing",
        "verified_url": "https://www.jdoqocy.com/click-101906407-12306188",
        "is_direct": True,
        "approved": True,
        "payout_rate": "10%-20% revshare",
        "network": "CJ Affiliate",
        "swapped_from_non_paying": False,
    },
    "wallethub": {
        "partner_key": "wallethub",
        "verified_merchant_name": "WalletHub Credit Score, Business Credit & Rate Comparison",
        "verified_url": "https://www.jdoqocy.com/click-101906407-16952385",
        "is_direct": True,
        "approved": True,
        "payout_rate": "$50.00 USD CPA",
        "network": "CJ Affiliate",
        "swapped_from_non_paying": False,
    },
    "lawdepot": {
        "partner_key": "lawdepot",
        "verified_merchant_name": "LawDepot Commercial Lease, LLC Operating & Holding Contracts",
        "verified_url": "https://www.jdoqocy.com/click-101906407-16985242",
        "is_direct": True,
        "approved": True,
        "payout_rate": "30% revshare ($45-$85)",
        "network": "CJ Affiliate",
        "swapped_from_non_paying": False,
    },
}


# Expected primary brand tokens per partner key for strict brand-honest callout verification
EXPECTED_PARTNER_BRAND_TOKENS: Dict[str, Tuple[str, ...]] = {
    "coinledger": ("coinledger",),
    "koinly": ("koinly",),
    "mercury": ("mercury",),
    "rippling": ("rippling",),
    "gusto": ("gusto",),
    "ramp": ("ramp",),
    "xendoo": ("xendoo",),
    "kalshi": ("kalshi",),
    "efile_com": ("e-file.com", "e-file", "efile"),
    "efile": ("e-file.com", "e-file", "efile"),
    "eztaxreturn_com": ("eztaxreturn",),
    "eztaxreturn": ("eztaxreturn",),
    "freetaxusa": ("freetaxusa",),
    "wallethub": ("wallethub",),
    "lawdepot": ("lawdepot",),
    "ipx1031": ("ipx1031",),
    "crest_capital": ("crest capital",),
    "equipment_macrs": ("crest capital", "equipment"),
    "stripe": ("stripe",),
    "rho": ("rho",),
    "turbotax": ("turbotax",),
    "taxslayer": ("taxslayer",),
    "interactive_brokers": ("interactive brokers",),
    "exeter1031": ("exeter",),
    "first_american": ("first american",),
    "first_american_1031": ("first american",),
    "simply_business": ("simply business",),
    "suretybonds_direct": ("suretybondsdirect", "suretybonds direct"),
    "next_insurance_b2b": ("next insurance",),
    "invoice_simple": ("invoice simple",),
    "national_funding_med": ("national funding",),
    "otr_solutions_factoring": ("otr solutions",),
    "freightos_marketplace": ("freightos",),
    "thimble_contractor": ("thimble",),
    "jobber_field_service": ("jobber",),
    "levelset_lien_filing": ("levelset",),
    "splash_financial": ("splash financial", "splash"),
    "sofi": ("sofi",),
    "sofi_refi": ("sofi",),
    "credible": ("credible",),
    "earnest": ("earnest",),
    "lendkey": ("lendkey",),
    "laurel_road": ("laurel road",),
    "juno": ("juno",),
    "vanta_security": ("vanta",),
    "drata_compliance": ("drata",),
    "sprinto_compliance": ("sprinto",),
    "thoropass_audit": ("thoropass",),
    "coalition_cyber_insurance": ("coalition",),
    "cobalt_pentest": ("cobalt",),
}

FORBIDDEN_REPLACED_BRAND_TOKENS: Dict[str, Tuple[str, ...]] = {
    "suretybonds_direct": ("lawdepot", "hiscox", "suretybonds.com"),
    "simply_business": ("lawdepot", "hiscox"),
    "next_insurance_b2b": ("lawdepot", "hiscox"),
    "crest_capital": ("xendoo", "alt lending", "taxact"),
    "equipment_macrs": ("xendoo", "alt lending", "taxact"),
    "stripe": ("stax", "ramp"),
    "rho": ("mercury",),
    "turbotax": ("taxact", "e-file.com"),
    "taxslayer": ("eztaxreturn",),
    "freetaxusa": ("eztaxreturn",),
    "interactive_brokers": ("zacks", "kalshi"),
    "exeter1031": ("dlp capital",),
    "first_american": ("groundfloor",),
    "first_american_1031": ("groundfloor",),
    "national_funding_med": ("stax",),
    "otr_solutions_factoring": ("invoice simple",),
    "freightos_marketplace": ("invoice simple",),
    "gusto": ("surepayroll", "paychex"),
    "kalshi": ("moby",),
}


def audit_merchant_coverage_and_yield(
    property_id: str = "profithelm",
    dist_dir: Optional[Any] = None,
    partner_overrides: Optional[Dict[str, AffiliatePartner]] = None,
) -> Dict[str, Any]:
    """
    Audits merchant commission coverage and offer-yield truth across all affiliate routes
    and first-party Stripe Checkout SKUs for a property.
    Enforces honest accounting:
      - Computes `non_paying_passthrough_count` honestly from pending/uncontracted routes
        (never hardcoded to 0 when uncontracted routes exist).
      - Fails closed if ANY partner claiming `status == "live"` lacks a verified brand-matched
        paying contract URL, uses dead CJ PID 101725461, or borrows another tenant's CJ/Impact/FirstPromoter account.
      - Fails closed if ANY declined partner is rendered in `dist_dir` HTML.
      - Allows 0-approved-affiliate properties (`prexvo`, `gainhelm`, `lienbond`) to pass ONLY via
        verified first-party Stripe Checkout SKUs when zero partners falsely claim `status == "live"`
        and zero declined partners are rendered.
    Zero em-dashes. Zero en-dashes.
    """
    import json
    from pathlib import Path
    from pseofactory.affiliate_intent import is_intent_matched

    prop = (property_id or "profithelm").strip().lower()
    base_registry = (
        PREXVO_AFFILIATES
        if prop == "prexvo"
        else (
            GAINHELM_AFFILIATES
            if prop == "gainhelm"
            else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES)
        )
    )
    registry = dict(partner_overrides) if partner_overrides is not None else base_registry

    sku_prefix_by_prop = {
        "profithelm": "ph_",
        "prexvo": "px_",
        "gainhelm": "gh_",
        "lienbond": "lb_",
    }
    sku_prefix = sku_prefix_by_prop.get(prop, f"{prop}_")
    verified_stripe_skus: List[str] = []
    try:
        vault_path = Path(__file__).resolve().parent / "monetization_vault.json"
        if vault_path.is_file():
            v_data = json.loads(vault_path.read_text(encoding="utf-8"))
            dig_prods = ((v_data.get("master_networks") or {}).get("stripe") or {}).get("digital_products") or {}
            for sku_k, sku_meta in dig_prods.items():
                if str(sku_k).startswith(sku_prefix) and isinstance(sku_meta, dict) and float(sku_meta.get("price_usd") or 0.0) > 0.0:
                    verified_stripe_skus.append(str(sku_k))
    except Exception:
        verified_stripe_skus = []

    tenant_hosts = ("profithelm.com", "prexvo.com", "gainhelm.com", "lienbond.com")
    routes_report: Dict[str, Dict[str, Any]] = {}
    violations: List[str] = []
    verified_paying_count = 0
    non_paying_passthrough_count = 0
    declined_suppressed_count = 0
    internal_loop_count = 0

    for k, p_obj in registry.items():
        if k != p_obj.key:
            continue
        url = str(p_obj.default_url or "").strip()
        url_low = url.lower()
        st = str(p_obj.status or "pending").strip().lower()
        is_live = st in ("live", "active_direct")
        is_declined = st in ("declined", "rejected", "terminated", "inactive")
        is_pending = not is_live and not is_declined

        internal_loop = (
            not url
            or url.startswith("/")
            or any(h in url_low for h in tenant_hosts)
        )
        if internal_loop:
            internal_loop_count += 1
            violations.append(f"Partner '{k}' points to an internal or empty loop URL: '{url}'")

        dead_cj_pid = "101725461" in url_low
        if dead_cj_pid:
            violations.append(f"Partner '{k}' uses retired CJ PID 101725461: '{url}'")

        foreign_account_leak = False
        if prop != "profithelm" and any(
            tok in url_low
            for tok in ("101906407", "/7932737/", "profithelm-llc", "fpr=arif-", "fp_ref=arif-", "mcfo1m09qiwt")
        ):
            foreign_account_leak = True
            violations.append(f"Partner '{k}' on '{prop}' leaks ProfitHelm network tracking credentials: '{url}'")

        has_tracking_contract = False
        if not internal_loop and not dead_cj_pid and not foreign_account_leak:
            if prop in ("profithelm", "exchange1031"):
                has_tracking_contract = bool(
                    k in SOVRN_VERIFIED_PAYING_MERCHANTS
                    and is_intent_matched(k, url)
                )
            else:
                # Non-ProfitHelm properties require their own property-scoped tracking parameters/redirect host
                parsed_u = urllib.parse.urlsplit(url)
                has_tracking_contract = bool(
                    is_intent_matched(k, url)
                    and (
                        any(
                            net_host in (parsed_u.hostname or "").lower()
                            for net_host in ("pxf.io", "imp.i", "jdoqocy.com", "dpbolvw.net", "tkqlhce.com", "anrdoezrs.net", "kqzyfj.com")
                        )
                        or any(
                            q_tok in (parsed_u.query or "").lower()
                            for q_tok in ("fpr=", "fp_ref=", "partner_id=", "aff_id=", "ref=")
                        )
                    )
                )

        approved_paying = bool(is_live and has_tracking_contract)
        if is_live and not has_tracking_contract:
            violations.append(
                f"Partner '{k}' on '{prop}' claims status='{st}' without a verified brand-matched paying contract URL: '{url}'"
            )

        if approved_paying:
            verified_paying_count += 1
        elif is_declined:
            declined_suppressed_count += 1
        else:
            non_paying_passthrough_count += 1

        routes_report[k] = {
            "partner_key": k,
            "verified_merchant_name": p_obj.name,
            "verified_url": url,
            "status": st,
            "approved": approved_paying,
            "is_direct": approved_paying,
            "payout_rate": p_obj.commission_est,
            "network": p_obj.network,
            "internal_calculator_loop": internal_loop,
            "foreign_account_leak": foreign_account_leak,
        }

    rendered_declined_partners: List[str] = []
    if dist_dir is not None:
        d_path = Path(dist_dir)
        if d_path.is_dir():
            declined_keys = {
                k for k, p_obj in registry.items()
                if str(p_obj.status or "").strip().lower() in ("declined", "rejected", "terminated", "inactive")
            }
            for hf in sorted(d_path.rglob("*.html")):
                rel_p = str(hf.relative_to(d_path))
                if rel_p == "404.html" or rel_p.startswith("embed/"):
                    continue
                try:
                    h_txt = hf.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for dk in sorted(declined_keys):
                    if f"/r/{dk}" in h_txt or f'data-partner="{dk}"' in h_txt:
                        rendered_declined_partners.append(f"{rel_p}:{dk}")
                        violations.append(f"Declined partner '{dk}' rendered in '{rel_p}'")
                for m_st in re.finditer(r'<a\s+[^>]*href=["\']/r/([a-z0-9_]+)[^"\']*["\'][^>]*>', h_txt, flags=re.I):
                    tag_s = m_st.group(0)
                    a_pk = m_st.group(1).lower()
                    if 'data-status="live"' in tag_s.lower() and not routes_report.get(a_pk, {}).get("approved"):
                        violations.append(f"Unapproved partner '{a_pk}' stamped data-status='live' in '{rel_p}'")

    has_monetization_rail = verified_paying_count > 0 or len(verified_stripe_skus) > 0
    if not has_monetization_rail:
        violations.append(f"Property '{prop}' has 0 verified affiliate contracts and 0 verified Stripe SKUs")

    monetization_mode = (
        "verified_affiliates_and_stripe"
        if verified_paying_count > 0 and len(verified_stripe_skus) > 0
        else (
            "verified_affiliates_only"
            if verified_paying_count > 0
            else ("first_party_stripe_checkout_only" if len(verified_stripe_skus) > 0 else "unmonetized")
        )
    )

    return {
        "status": "PASS" if (len(violations) == 0 and internal_loop_count == 0 and has_monetization_rail) else "FAIL",
        "property_id": prop,
        "monetization_mode": monetization_mode,
        "total_routes_audited": len(routes_report),
        "verified_paying_count": verified_paying_count,
        "non_paying_passthrough_count": non_paying_passthrough_count,
        "declined_suppressed_count": declined_suppressed_count,
        "swapped_non_paying_count": 0,
        "internal_loop_count": internal_loop_count,
        "verified_stripe_sku_count": len(verified_stripe_skus),
        "verified_stripe_skus": verified_stripe_skus,
        "rendered_declined_partners": rendered_declined_partners,
        "violations": violations,
        "routes": routes_report,
    }


def _extract_tool_slug_from_html_head(html_src: str) -> str:
    """Extracts canonical /tools/<slug>, data-slug, or title slug from HTML."""
    canon_m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html_src, re.I)
    if not canon_m:
        canon_m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', html_src, re.I)
    if canon_m:
        canon_u = canon_m.group(1).split("?")[0].rstrip("/")
        if "/tools/" in canon_u:
            return canon_u.split("/tools/", 1)[1].strip("/").replace("/", "-")
        return "tools-directory" if canon_u.endswith("/tools") else "homepage"
    data_slug_m = re.search(r'data-slug=["\']([^"\']+)["\']', html_src, re.I)
    if data_slug_m:
        return data_slug_m.group(1).strip("/").replace("/", "-")
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_src, re.S | re.I)
    if title_m:
        raw_t = re.sub(r"<[^>]+>", " ", title_m.group(1)).lower()
        raw_t = re.sub(r"[^a-z0-9]+", "-", raw_t).strip("-")
        return raw_t[:60].strip("-") or "calculator"
    return "calculator"


_COMPARISON_TABLE_CTA_BAR_RE = re.compile(
    r'<div\b[^>]*\bclass=["\']([^"\']*\bcomparison-table-cta-bar\b[^"\']*)["\'][^>]*>.*?</div>',
    flags=re.S | re.I,
)
_COMPARISON_TABLE_CTA_BAR_STRIP_RE = re.compile(
    r'\s*<div\b[^>]*\bclass=["\'][^"\']*\bcomparison-table-cta-bar\b[^"\']*["\'][^>]*>.*?</div>',
    flags=re.S | re.I,
)


def _extract_section_id_attr(open_tag: str) -> str:
    """Extracts an HTML id attribute from an opening tag, returning ' id="..."' or ''."""
    id_m = re.search(r'\bid=["\']([^"\']+)["\']', open_tag or "", flags=re.I)
    return f' id="{html_lib.escape(id_m.group(1))}"' if id_m else ""


def _extract_partner_registration_drawer(sec_html: str) -> str:
    """Extracts <div id="partner-registration-drawer">...</div> preserving balanced div nesting."""
    m_open = re.search(
        r'<div\b[^>]*\bid=["\']partner-registration-drawer["\'][^>]*>',
        sec_html or "",
        flags=re.I,
    )
    if not m_open:
        return ""
    div_start = m_open.start()
    depth = 0
    div_end = -1
    for tok in re.finditer(r"</?div\b[^>]*>", sec_html[div_start:], flags=re.I):
        tok_l = tok.group(0).lower()
        if tok_l.startswith("</div"):
            depth -= 1
            if depth == 0:
                div_end = div_start + tok.end()
                break
        elif not tok_l.endswith("/>"):
            depth += 1
    if div_end > div_start:
        return "\n      " + sec_html[div_start:div_end].strip()
    reg_m = re.search(
        r'\s*<div\b[^>]*id=["\']partner-registration-drawer["\'][^>]*>[\s\S]*?</form>\s*</div>',
        sec_html,
        flags=re.S | re.I,
    )
    return ("\n      " + reg_m.group(0).strip()) if reg_m else ""


def _render_comparison_table_cta_bar(
    pk: str,
    name: str,
    cta_text: str,
    brand: str,
    model: str,
    href: str,
    tool: str,
    subid: str,
    status: str,
    gsc_tier: str,
    tier_role: str = "primary",
    existing_class_attr: str = "",
) -> str:
    """Renders .comparison-table-cta-bar while preserving any existing extra classes such as card pseo-card."""
    cls_tokens = list(dict.fromkeys(existing_class_attr.split())) if existing_class_attr else []
    if "comparison-table-cta-bar" not in cls_tokens:
        cls_tokens.insert(0, "comparison-table-cta-bar")
    cls_attr = html_lib.escape(" ".join(cls_tokens))
    safe_pk = html_lib.escape(pk)
    safe_name = html_lib.escape(name)
    safe_cta = html_lib.escape(cta_text)
    safe_brand = html_lib.escape(brand)
    safe_model = html_lib.escape(model)
    safe_href = html_lib.escape(href)
    safe_tool = html_lib.escape(tool)
    safe_sub = html_lib.escape(subid)
    safe_status = html_lib.escape(status)
    safe_tier_role = html_lib.escape(tier_role)
    safe_gsc_tier = html_lib.escape(gsc_tier)
    bar_style = (
        "display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; margin-top: 0.875rem; border: 1px solid var(--border);"
        if "pseo-card" in cls_tokens
        else "display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; margin-top: 0.875rem; padding: 0.75rem 1rem; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px;"
    )
    return (
        f'<div class="{cls_attr}" data-mechanic="compliant_intent_monetization" '
        f'data-partner="{safe_pk}" data-company-brand="{safe_brand}" data-partner-tier="{safe_tier_role}" '
        f'data-partnership-model="{safe_model}" '
        f'data-cta-slot="comparison_table_cta" data-gsc-tier="{safe_gsc_tier}" '
        f'style="{bar_style}">\n'
        f'        <span style="font-size: 0.875rem; font-weight: 600; color: var(--text);">Scenario Execution Partner: <strong>{safe_name}</strong> ({safe_brand})</span>\n'
        f'        <a href="{safe_href}" target="_blank" rel="noopener sponsored nofollow" '
        f'data-partner="{safe_pk}" data-company-brand="{safe_brand}" data-partner-tier="{safe_tier_role}" '
        f'data-partnership-model="{safe_model}" '
        f'data-tool="{safe_tool}" data-subid="{safe_sub}" data-status="{safe_status}" '
        f'data-cta-slot="comparison_table_cta" class="btn-cta partner-cta touch-target" '
        f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent); color: var(--cta-fg); font-weight: 600; text-decoration: none;">{safe_cta} &rarr;</a>\n'
        f'      </div>'
    )


def _normalize_affiliates_section_h2(
    raw_sec: str,
    promoted_pk: str,
    registry: Dict[str, AffiliatePartner],
) -> str:
    """Preserves valid affiliates-section <h2> headings while normalizing headings that name a non-promoted partner."""
    default_h2 = '<h2 style="font-size: 1.375rem; font-weight: 700; margin-bottom: 1rem;">Recommended Partner Solutions</h2>'
    if (
        'data-partner-ctas-hidden="unapproved"' in raw_sec
        or "data-partner-ctas-hidden='unapproved'" in raw_sec
    ):
        return default_h2
    h2_m = re.search(r"<h2\b[^>]*>.*?</h2>", raw_sec, flags=re.S | re.I)
    if not h2_m:
        return default_h2
    h2_raw = h2_m.group(0)
    h2_low = re.sub(r"<[^>]+>", " ", html_lib.unescape(h2_raw)).lower()
    prom_clean = (promoted_pk or "").strip().lower()
    prom_brand = COMPANY_BRAND_BY_PARTNER_KEY.get(prom_clean, "").lower()
    prom_name = (registry[prom_clean].name.lower() if prom_clean in registry else "")
    other_tokens: List[str] = ["suretybonds.com", "next insurance"]
    for other_pk, other_obj in registry.items():
        if other_pk == prom_clean:
            continue
        other_brand = COMPANY_BRAND_BY_PARTNER_KEY.get(other_pk, "").lower()
        if other_brand:
            other_tokens.append(other_brand)
        if other_obj and other_obj.name:
            other_tokens.append(other_obj.name.lower())
    names_other = any(tok in h2_low for tok in other_tokens if tok)
    names_promoted = bool((prom_brand and prom_brand in h2_low) or (prom_name and prom_name in h2_low))
    if ("verified commercial execution partner:" in h2_low or names_other) and not names_promoted:
        return default_h2
    return h2_raw


def _replace_balanced_div_by_class(
    container_html: str,
    class_names: Tuple[str, ...],
    replacement: str,
) -> Optional[str]:
    """Replaces the first <div class="...">...</div> matching any class_names using balanced div depth."""
    cls_pat = "|".join(re.escape(c) for c in class_names)
    m_open = re.search(
        rf'<div\b[^>]*\bclass=["\'][^"\']*\b(?:{cls_pat})\b[^"\']*["\'][^>]*>',
        container_html or "",
        flags=re.I,
    )
    if not m_open:
        return None
    div_start = m_open.start()
    if m_open.group(0).rstrip().endswith("/>"):
        return container_html[:div_start] + replacement + container_html[m_open.end() :]
    depth = 0
    div_end = -1
    for tok in re.finditer(r"</?div\b[^>]*>", container_html[div_start:], flags=re.I):
        tok_l = tok.group(0).lower()
        if tok_l.startswith("</div"):
            depth -= 1
            if depth == 0:
                div_end = div_start + tok.end()
                break
        elif not tok_l.endswith("/>"):
            depth += 1
    if div_end <= div_start:
        return None
    return container_html[:div_start] + replacement + container_html[div_end:]


def _resolve_prexvo_promoted_partner(
    html_doc: str,
    gsc_inline_meta: Dict[str, str],
    preserve_promoted_primary: bool,
) -> Tuple[str, str, Tuple[str, ...]]:
    """Resolves any already-promoted valid Prexvo primary partner from DOM metadata."""
    valid_px_keys = {
        k
        for k in ("splash_financial", "credible", "lendkey")
        if PREXVO_AFFILIATES.get(k) and PREXVO_AFFILIATES[k].status not in ("declined", "rejected")
    }
    sec_m = re.search(
        r'<section\b[^>]*\bclass=["\'][^"\']*(?:refinance-partner-section|partners-section)[^"\']*["\'][^>]*>.*?</section>',
        html_doc or "",
        flags=re.S | re.I,
    )
    sec_html_probe = sec_m.group(0) if sec_m else ""
    sec_open_m = re.match(r"<section\b[^>]*>", sec_html_probe, flags=re.I) if sec_html_probe else None
    sec_open = sec_open_m.group(0) if sec_open_m else ""
    sec_pk_m = re.search(r'data-primary-partner=["\']([a-z0-9_]+)["\']', sec_open or sec_html_probe, flags=re.I) or re.search(
        r'data-partner=["\']([a-z0-9_]+)["\']', sec_open, flags=re.I
    )
    sec_pk = sec_pk_m.group(1).lower() if sec_pk_m else ""
    first_card_pk = ""
    if sec_html_probe:
        c_tag_m = re.search(
            r'<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b[^"\']*["\'][^>]*>',
            sec_html_probe,
            flags=re.I,
        )
        if c_tag_m:
            c_pk_m = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', c_tag_m.group(0), flags=re.I)
            if c_pk_m:
                first_card_pk = c_pk_m.group(1).lower()
    gsc_cand_probe = str(gsc_inline_meta.get("data-partner") or "").strip().lower()
    sec_repositioned = bool(re.search(r'data-gsc-repositioned=["\']true["\']', sec_open, flags=re.I))
    inline_repositioned = str(gsc_inline_meta.get("data-gsc-repositioned") or "").strip().lower() == "true"
    sec_tier_m = re.search(r'data-gsc-tier=["\']([^"\']+)["\']', sec_open, flags=re.I)
    sec_has_non_baseline_gsc = bool(
        sec_tier_m and sec_tier_m.group(1).strip().upper() not in ("", "BASELINE", "BASELINE_MULTI_SLOT")
    )

    promoted_cand = ""
    if sec_repositioned and sec_pk in valid_px_keys:
        promoted_cand = sec_pk
    elif inline_repositioned and gsc_cand_probe in valid_px_keys:
        promoted_cand = gsc_cand_probe
    elif preserve_promoted_primary:
        if sec_pk in valid_px_keys:
            promoted_cand = sec_pk
        elif gsc_cand_probe in valid_px_keys:
            promoted_cand = gsc_cand_probe
    elif sec_has_non_baseline_gsc and sec_pk in valid_px_keys:
        promoted_cand = sec_pk
    elif (
        sec_pk in valid_px_keys
        and sec_pk != "splash_financial"
        and sec_pk == first_card_pk
        and "sofi" not in sec_html_probe.lower()
        and "earnest" not in sec_html_probe.lower()
    ):
        promoted_cand = sec_pk

    eff_pk = promoted_cand or "splash_financial"
    ordered_keys = tuple(
        [eff_pk] + [k for k in ("splash_financial", "credible", "lendkey") if k != eff_pk and k in valid_px_keys]
    )
    return promoted_cand, eff_pk, ordered_keys


def _render_prexvo_partner_card(
    pk: str,
    idx: int,
    slug_id: str,
    page_v_fam: str,
    offer: Optional[Dict[str, Any]] = None,
) -> str:
    """Renders a single Prexvo .partner-card in deterministic slot/subid order."""
    p_obj = PREXVO_AFFILIATES.get(pk)
    if offer is None:
        if not p_obj or p_obj.status in ("declined", "rejected"):
            return ""
        ctx_px = resolve_contextual_partner_offer_copy(
            partner_key=pk,
            p_obj=p_obj,
            slug=slug_id,
            vertical_family=page_v_fam,
            property_id="prexvo",
        )
        badge = ctx_px["badge"]
        name = ctx_px["name"]
        desc = ctx_px["description"]
        cta_text = ctx_px["cta_text"]
        p_model = p_obj.partnership_model
        slot = "calculator_primary_cta" if idx == 1 else "partner_matrix_card"
        subid = f"{slug_id}_card_{idx}"
        href = f"/r/{pk}?source_tool={slug_id}&subid={subid}&cta_slot={slot}"
        status = "live" if is_partner_live_in_vault("prexvo", pk) else p_obj.status
    else:
        badge = str(offer.get("badge") or (p_obj.badge if p_obj else "Partner Option"))
        name = str(offer.get("name") or (p_obj.name if p_obj else pk))
        desc = str(offer.get("description") or (p_obj.description if p_obj else ""))
        cta_text = str(offer.get("cta_text") or (p_obj.cta_text if p_obj else "Explore Partner"))
        p_model = str(offer.get("partnership_model") or (p_obj.partnership_model if p_obj else "CPA_BOUNTY"))
        slot = str(offer.get("cta_slot") or ("calculator_primary_cta" if idx == 1 else "partner_matrix_card"))
        subid = str(offer.get("subid") or f"{slug_id}_card_{idx}")
        href = str(offer.get("attributed_href") or f"/r/{pk}?source_tool={slug_id}&subid={subid}&cta_slot={slot}")
        status = (
            "live"
            if is_partner_live_in_vault("prexvo", pk)
            else str(offer.get("status") or (p_obj.status if p_obj else "pending"))
        )

    safe_pk = html_lib.escape(pk)
    safe_model = html_lib.escape(p_model)
    safe_s = html_lib.escape(slug_id)
    safe_sub = html_lib.escape(subid)
    return (
        f'      <div class="partner-card" data-partner="{safe_pk}" data-partnership-model="{safe_model}" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">\n'
        f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--brand-primary); text-transform: uppercase;">{html_lib.escape(badge)}</span>\n'
        f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html_lib.escape(name)}</h3>\n'
        f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html_lib.escape(desc)}</p>\n'
        f'        <a href="{html_lib.escape(href)}" target="_blank" rel="noopener sponsored nofollow" class="partner-btn btn-cta touch-target" data-partner="{safe_pk}" data-partnership-model="{safe_model}" data-tool="{safe_s}" data-subid="{safe_sub}" data-status="{html_lib.escape(status)}" data-cta-slot="{html_lib.escape(slot)}">\n'
        f'          {html_lib.escape(cta_text)} &rarr;\n'
        f'        </a>\n'
        f'      </div>'
    )


def _build_prexvo_refinance_section_html(
    raw_sec: str,
    ordered_offers_or_keys: Sequence[Any],
    slug_id: str,
    page_v_fam: str,
    lead_pk: str,
    lead_model: str,
    models_csv: str,
    roster_keys_csv: str,
    companies_csv: str,
    gsc_tier: str = "",
    gsc_repositioned: Optional[bool] = None,
) -> str:
    """Rebuilds Prexvo's refinance partner section while preserving classes, id, YMYL copy, and drawers."""
    raw_open_m = re.match(r"<section\b[^>]*>", raw_sec, flags=re.I)
    raw_open = raw_open_m.group(0) if raw_open_m else ""
    sec_id_attr = _extract_section_id_attr(raw_open)
    cls_m = re.search(r'\bclass=["\']([^"\']*)["\']', raw_open, flags=re.I)
    cls_tokens = [c for c in (cls_m.group(1).split() if cls_m else []) if c]
    if "refinance-partner-section" not in cls_tokens:
        cls_tokens.append("refinance-partner-section")
    sec_cls_attr = html_lib.escape(" ".join(dict.fromkeys(cls_tokens)))

    extra_attrs = ""
    for attr_name in ("data-property", "data-commercial-offers", "data-restricted-public-service"):
        attr_m = re.search(rf'\b{attr_name}=["\']([^"\']+)["\']', raw_open, flags=re.I)
        if attr_m:
            extra_attrs += f' {attr_name}="{html_lib.escape(attr_m.group(1))}"'

    eff_tier = gsc_tier
    if not eff_tier:
        tier_m = re.search(r'\bdata-gsc-tier=["\']([^"\']+)["\']', raw_open, flags=re.I)
        if tier_m:
            eff_tier = tier_m.group(1)
    if eff_tier:
        extra_attrs += f' data-gsc-tier="{html_lib.escape(eff_tier)}"'

    if gsc_repositioned is not None:
        extra_attrs += f' data-gsc-repositioned="{"true" if gsc_repositioned else "false"}"'
    else:
        rep_m = re.search(r'\bdata-gsc-repositioned=["\']([^"\']+)["\']', raw_open, flags=re.I)
        if rep_m:
            extra_attrs += f' data-gsc-repositioned="{html_lib.escape(rep_m.group(1))}"'

    cards_html: List[str] = []
    for idx, item in enumerate(ordered_offers_or_keys, start=1):
        c_pk = str(item["partner_key"]) if isinstance(item, dict) else str(item)
        c_html = _render_prexvo_partner_card(
            pk=c_pk,
            idx=idx,
            slug_id=slug_id,
            page_v_fam=page_v_fam,
            offer=item if isinstance(item, dict) else None,
        )
        if c_html:
            cards_html.append(c_html)
    grid_inner = "\n".join(cards_html)
    grid_html = (
        '<div class="partner-matrix-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">\n'
        f"{grid_inner}\n"
        "      </div>"
    )
    open_tag = (
        f'<section{sec_id_attr} class="{sec_cls_attr}" data-mechanic="compliant_intent_monetization" '
        f'data-partner="{html_lib.escape(lead_pk)}" data-primary-partner="{html_lib.escape(lead_pk)}" '
        f'data-partnership-model="{html_lib.escape(lead_model)}" data-partner-models="{html_lib.escape(models_csv)}" '
        f'data-partner-roster="{html_lib.escape(roster_keys_csv)}" data-partner-companies="{html_lib.escape(companies_csv)}"'
        f'{extra_attrs} style="margin: 1.5rem 0;">'
    )

    close_idx = raw_sec.lower().rfind("</section>")
    inner_body = raw_sec[len(raw_open) : close_idx] if raw_open and close_idx >= len(raw_open) else ""
    replaced_inner = _replace_balanced_div_by_class(
        inner_body,
        ("partner-matrix-grid", "partner-roster-grid"),
        grid_html,
    )
    if replaced_inner is not None:
        lead_obj = PREXVO_AFFILIATES.get(lead_pk)
        if lead_obj:
            lead_ctx = resolve_contextual_partner_offer_copy(
                partner_key=lead_pk,
                p_obj=lead_obj,
                slug=slug_id,
                vertical_family=page_v_fam,
                property_id="prexvo",
            )
            replaced_inner = re.sub(
                r'(<h2\b[^>]*>\s*Private Student Loan Refinance Comparison:\s*)([^<]+)(</h2>)',
                rf"\g<1>{html_lib.escape(lead_obj.name)}\g<3>",
                replaced_inner,
                count=1,
                flags=re.I,
            )
            sa_href = html_lib.escape(
                f"/r/{lead_pk}?source_tool={slug_id}&subid={slug_id}_primary&cta_slot=standalone_primary_cta"
            )
            replaced_inner = re.sub(
                r'(<a\b[^>]*\bdata-cta-slot=["\']standalone_primary_cta["\'][^>]*>)(.*?)(</a>)',
                lambda m: (
                    re.sub(
                        r'data-partnership-model=["\'][^"\']*["\']',
                        f'data-partnership-model="{html_lib.escape(lead_model)}"',
                        re.sub(
                            r'data-partner=["\'][^"\']*["\']',
                            f'data-partner="{html_lib.escape(lead_pk)}"',
                            re.sub(
                                r'href=["\'][^"\']*["\']',
                                f'href="{sa_href}"',
                                m.group(1),
                                count=1,
                                flags=re.I,
                            ),
                            count=1,
                            flags=re.I,
                        ),
                        count=1,
                        flags=re.I,
                    )
                    + html_lib.escape(lead_ctx["cta_text"])
                    + m.group(3)
                ),
                replaced_inner,
                count=1,
                flags=re.S | re.I,
            )
        return f"{open_tag}{replaced_inner}</section>"

    reg_str = _extract_partner_registration_drawer(raw_sec)
    is_hidden_placeholder = (
        'data-partner-ctas-hidden="unapproved"' in raw_open
        or "data-partner-ctas-hidden='unapproved'" in raw_open
    )
    ymyl_warn_m = re.search(
        r'<p\b[^>]*\bclass=["\'][^"\']*\bymyl-statutory-warning\b[^"\']*["\'][^>]*>.*?</p>',
        raw_sec,
        flags=re.S | re.I,
    )
    ymyl_warn_block = f"\n      {ymyl_warn_m.group(0).strip()}" if ymyl_warn_m else ""
    if is_hidden_placeholder:
        heading_block = '\n      <h2 style="font-size: 1.375rem; font-weight: 700; margin-bottom: 1rem;">Private Student Loan Refinance Comparison</h2>'
        return f"{open_tag}{heading_block}{ymyl_warn_block}\n      {grid_html}{reg_str}\n    </section>"
    return f"{open_tag}{ymyl_warn_block}\n      {grid_html}{reg_str}\n    </section>"


def normalize_html_callout_message_match(
    html: str,
    property_id: str = "profithelm",
    preserve_promoted_primary: bool = False,
) -> str:
    """
    Normalizes rendered HTML partner callout cards and /r/<partner_key> CTA button labels
    so every visible partner callout matches its canonical destination merchant in
    PROFITHELM_AFFILIATES / PREXVO_AFFILIATES and contains zero stale replaced brand names.
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib

    if not html:
        return html

    prop = (property_id or "profithelm").strip().lower()
    has_lienbond_copy_drift = prop == "lienbond" and (
        "SuretyBonds.com" in html
        or "EMR Audit Packet ($89)" in html
        or "Next Insurance" in html
    )
    has_gainhelm_copy_drift = (
        prop == "gainhelm"
        and any(
            tok in html
            for tok in (
                "refinance-partner-section",
                "affiliates-section",
                "affiliate-section",
                "partners-section",
                "partner-badge",
            )
        )
        and has_gainhelm_cross_framework_leak(html, _extract_tool_slug_from_html_head(html))
    )
    if "/r/" not in html and "overlay-partner-offer" not in html and not has_lienbond_copy_drift and not has_gainhelm_copy_drift:
        return html
    registry = PREXVO_AFFILIATES if prop == "prexvo" else (GAINHELM_AFFILIATES if prop == "gainhelm" else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES))
    fallback_copy: Dict[str, Tuple[str, str, str]] = {}
    if prop == "profithelm":
        fallback_copy = {
            "efile": (
                "E-file.com IRS Authorized Federal & State Tax Filing",
                "E-File Federal & State Returns on E-file.com",
                "https://www.jdoqocy.com/click-101906407-11917161",
            ),
            "eztaxreturn": (
                "ezTaxReturn.com Fast Online Federal & State E-File",
                "File Your Tax Return Fast with ezTaxReturn.com",
                "https://www.dpbolvw.net/click-101906407-15704796",
            ),
        }

    def _resolve_copy(pk: str) -> Optional[Tuple[str, str, str]]:
        partner = registry.get(pk)
        if partner:
            ctx_copy = resolve_contextual_partner_offer_copy(
                partner_key=pk,
                p_obj=partner,
                slug=page_slug,
                vertical_family=page_v_fam,
                property_id=prop,
            )
            return (ctx_copy["name"], ctx_copy["cta_text"], partner.default_url)
        return fallback_copy.get(pk)

    def _resolve_desc(pk: str) -> str:
        partner = registry.get(pk)
        if not partner:
            return ""
        return resolve_contextual_partner_offer_copy(
            partner_key=pk,
            p_obj=partner,
            slug=page_slug,
            vertical_family=page_v_fam,
            property_id=prop,
        )["description"]

    live_partner_keys = load_live_partner_keys_from_vault(prop)

    def _effective_dom_status(pk: str, p_obj: Optional[AffiliatePartner]) -> str:
        pk_norm = str(pk or "").strip().lower().replace("-", "_")
        if pk_norm in live_partner_keys:
            return "live"
        if p_obj:
            return p_obj.status
        return "pending"

    # Extract page-level identity (title, canonical, h1) excluding footer/related links
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    canon_m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
    if not canon_m:
        canon_m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', html, re.I)
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    page_identity_lower = " ".join([
        (title_m.group(1) if title_m else ""),
        (canon_m.group(1) if canon_m else ""),
        re.sub(r"<[^>]+>", " ", h1_m.group(1) if h1_m else ""),
    ]).lower()

    page_slug = _extract_tool_slug_from_html_head(html)

    page_v_fam = ""
    try:
        page_v_fam = str(
            classify_asset_archetype_and_intent(
                property_id=prop,
                slug=page_slug,
                html_content=html,
            ).get("vertical_family")
            or ""
        )
    except Exception:
        page_v_fam = ""

    def _build_r_href(pk: str, subid_suffix: str, cta_slot: str) -> str:
        safe_s = html_lib.escape(page_slug)
        safe_sub = html_lib.escape(f"{page_slug}_{subid_suffix}")
        safe_slot = html_lib.escape(cta_slot)
        return f"/r/{pk}?source_tool={safe_s}&amp;subid={safe_sub}&amp;cta_slot={safe_slot}"

    has_estate_structure = bool(
        "affiliates-section" in html
        or "affiliate-section" in html
        or "refinance-partner-section" in html
        or "data-slug=" in html
        or 'id="calculation-manifest"' in html
        or 'class="calculation-manifest"' in html
    )

    is_prediction_page = any(
        tok in page_identity_lower
        for tok in ("prediction-market", "prediction market", "kalshi", "polymarket", "event-contract", "kelly", "arbitrage")
    )
    is_prediction_odds_page = is_prediction_page and "tax" not in page_identity_lower
    is_1031_page = "1031" in page_identity_lower
    is_crypto_page = (
        not is_1031_page
        and any(
            tok in page_identity_lower
            for tok in ("crypto", "1099-da", "8949", "staking", "token", "prediction-market-tax", "prediction market tax")
        )
    )
    is_general_tax_page = (
        not is_1031_page
        and not is_crypto_page
        and not is_prediction_page
        and any(
            tok in page_identity_lower
            for tok in ("tax-bracket", "tax bracket", "irs-2027", "ca-tax-brackets", "capital-gains", "capital gains", "tcja")
        )
    )
    is_capital_gains_page = any(tok in page_identity_lower for tok in ("capital-gains", "capital gains"))
    is_medical_page = any(
        tok in page_identity_lower
        for tok in ("medical", "dental", "healthcare", "practice")
    )
    is_s_corp_or_workers_comp = any(
        tok in page_identity_lower
        for tok in ("s-corp", "s corp", "reasonable-salary", "workers-comp", "payroll-burden")
    )
    is_treasury_page = any(
        tok in page_identity_lower
        for tok in ("treasury-yield", "treasury yield")
    )
    is_179_or_174_page = any(
        tok in page_identity_lower
        for tok in (
            "179",
            "equipment",
            "lease",
            "macrs",
            "depreciation",
            "vehicle",
            "gvwr",
            "truck",
            "suv",
            "section-174",
            "section 174",
            "r-and-d",
            "r&d",
        )
    )
    is_179_equipment_page = any(
        tok in page_identity_lower
        for tok in ("179", "equipment", "lease", "macrs", "depreciation", "vehicle", "gvwr", "truck", "suv")
    )
    is_174_page = any(
        tok in page_identity_lower
        for tok in ("section-174", "section 174", "r-and-d", "r&d")
    )

    is_spend_or_payment_page = any(
        tok in page_identity_lower
        for tok in ("saas", "burn", "runway", "spend", "expense", "payment-processing", "interchange", "merchant-fee", "stripe-fee", "card-processing")
    )
    is_credit_score_page = any(
        tok in page_identity_lower
        for tok in ("credit-score", "business-credit", "wallethub")
    )
    is_credit_or_capital_page = any(
        tok in page_identity_lower
        for tok in ("working-capital", "factoring", "line-of-credit", "dscr", "loan")
    )
    is_entity_or_contract_page = any(
        tok in page_identity_lower
        for tok in ("llc", "operating-agreement", "lease-agreement", "deed", "promissory-note", "entity", "surety", "contractor-lien", "mechanics-lien")
    )

    updated = html

    def _extract_balanced_inline_cta(doc_html: str) -> Tuple[str, str]:
        """Extracts and strips the first `<div class="...calc-inline-cta...">...</div>` using balanced div depth."""
        m_open = re.search(
            r'\n?[ \t]*<div\b[^>]*\bclass=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>',
            doc_html,
            flags=re.I,
        )
        if not m_open:
            return "", doc_html
        tag_start = m_open.group(0).lower().find("<div")
        if tag_start < 0:
            return "", doc_html
        if m_open.group(0).rstrip().endswith("/>"):
            return doc_html[m_open.start() : m_open.end()], doc_html[: m_open.start()] + doc_html[m_open.end() :]
        div_start = m_open.start() + tag_start
        depth = 0
        div_end = -1
        for tok in re.finditer(r"</?div\b[^>]*>", doc_html[div_start:], flags=re.I):
            tok_l = tok.group(0).lower()
            if tok_l.startswith("</div"):
                depth -= 1
                if depth == 0:
                    div_end = div_start + tok.end()
                    break
            elif not tok_l.endswith("/>"):
                depth += 1
        if div_end <= div_start:
            return "", doc_html
        block = doc_html[m_open.start() : div_end]
        stripped = doc_html[: m_open.start()] + doc_html[div_end:]
        return block, stripped

    gsc_inline_meta: Dict[str, str] = {}
    preserved_gsc_inline_block = ""
    while True:
        found_inline_block, updated_after_strip = _extract_balanced_inline_cta(updated)
        if not found_inline_block:
            break
        if not preserved_gsc_inline_block and (
            "data-gsc-tier=" in found_inline_block or "data-gsc-repositioned=" in found_inline_block
        ):
            preserved_gsc_inline_block = found_inline_block
            tag_str = found_inline_block.split(">", 1)[0] + ">"
            for attr_k in (
                "data-partner",
                "data-company-brand",
                "data-partner-tier",
                "data-gsc-tier",
                "data-gsc-repositioned",
                "data-yield-score",
            ):
                m_attr = re.search(rf'{attr_k}=["\']([^"\']+)["\']', tag_str, flags=re.I)
                if m_attr:
                    gsc_inline_meta[attr_k] = m_attr.group(1)
        updated = updated_after_strip

    # Strip any prior idempotent inline calculator fold compaction style
    updated = re.sub(
        r'[ \t]*<style\s+id=["\']pseo-inline-cta-fold["\'][^>]*>.*?</style>\n?',
        "",
        updated,
        flags=re.S | re.I,
    )

    # Upgrade homepage standalone affiliate-cta-section from pending turbotax/crest_capital to active approved xendoo
    if prop in ("profithelm", "exchange1031") and canon_m and "/tools/" not in canon_m.group(1).lower():
        if (
            'data-partner="turbotax"' in updated
            or "/r/turbotax" in updated
            or 'data-partner="crest_capital"' in updated
            or "/r/crest_capital" in updated
            or "Calculate & File Taxes Online with TaxAct" in updated
        ):
            updated = (
                updated.replace('data-partner="turbotax"', 'data-partner="xendoo"')
                .replace("/r/turbotax", "/r/xendoo")
                .replace('data-partner="crest_capital"', 'data-partner="xendoo"')
                .replace("/r/crest_capital", "/r/xendoo")
                .replace(
                    "Verified Commercial Execution Partner: TaxAct Online Tax Filing & Xpert Assist",
                    "Verified Commercial Execution Partner: Xendoo Section 179 & Business Tax Accounting",
                )
                .replace(
                    "Calculate & File Taxes Online with TaxAct",
                    "Optimize Section 179 Accounting with Xendoo",
                )
            )
    elif prop == "lienbond":
        if (
            'data-partner="next_insurance_b2b"' in updated
            or "/r/next_insurance_b2b" in updated
            or 'data-partner-key="next_insurance_b2b"' in updated
        ):
            updated = (
                updated.replace("<td><strong>Next Insurance</strong></td>", "<td><strong>Simply Business</strong></td>")
                .replace(
                    "Bind Workers Comp &amp; Download Live COI with Next Insurance",
                    "Compare Contractor Workers Comp &amp; GL Quotes via Simply Business",
                )
                .replace(
                    "Bind Workers Comp & Download Live COI with Next Insurance",
                    "Compare Contractor Workers Comp & GL Quotes via Simply Business",
                )
                .replace('data-partner="next_insurance_b2b"', 'data-partner="simply_business"')
                .replace('data-partner-key="next_insurance_b2b"', 'data-partner-key="simply_business"')
                .replace("/r/next_insurance_b2b", "/r/simply_business")
            )
        updated = (
            updated.replace("SuretyBonds.com", "SuretyBondsDirect.com")
            .replace("EMR Audit Packet ($89)", "EMR Audit Packet ($29)")
            .replace("Next Insurance, ", "")
            .replace(", Next Insurance", "")
        )
        if preserved_gsc_inline_block:
            preserved_gsc_inline_block = (
                preserved_gsc_inline_block.replace("SuretyBonds.com", "SuretyBondsDirect.com")
                .replace("EMR Audit Packet ($89)", "EMR Audit Packet ($29)")
                .replace("Next Insurance, ", "")
                .replace(", Next Insurance", "")
            )
        if "/r/" not in updated and "overlay-partner-offer" not in updated:
            return updated

    def _replace_overlay_section(match: re.Match) -> str:
        sec_html = match.group(0)
        pk_match = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', sec_html, re.I)
        if not pk_match:
            pk_match = re.search(r'href=["\']/r/([a-z0-9_]+)', sec_html, re.I)
        if not pk_match:
            return sec_html
        old_pk = pk_match.group(1).lower()
        pk = old_pk
        if prop == "lienbond" and pk == "next_insurance_b2b":
            pk = "simply_business"
        elif prop == "prexvo" and pk in ("sofi_refi", "sofi", "earnest"):
            pk = "splash_financial"
        elif has_estate_structure and not (
            ("data-gsc-tier=" in sec_html or 'data-gsc-repositioned="true"' in sec_html or preserve_promoted_primary)
            and old_pk in registry
            and getattr(registry.get(old_pk), "status", "") not in ("declined", "rejected")
            and (prop not in ("profithelm", "exchange1031") or old_pk in SOVRN_VERIFIED_PAYING_MERCHANTS)
        ):
            if prop == "prexvo":
                if (
                    'data-restricted-public-service="true"' not in sec_html
                    and 'data-commercial-offers="none"' not in sec_html
                    and 'data-commercial-offers="suppressed-default"' not in sec_html
                    and pk in ("sofi_refi", "sofi", "earnest", "credible", "lendkey")
                ):
                    pk = "splash_financial"
            elif prop in ("profithelm", "exchange1031"):
                if is_1031_page or is_entity_or_contract_page:
                    pk = "lawdepot"
                elif is_general_tax_page:
                    pk = "efile_com"
                elif is_179_or_174_page:
                    pk = "xendoo"
                elif is_s_corp_or_workers_comp:
                    pk = "rippling"
                elif is_prediction_odds_page:
                    pk = "kalshi"
                elif is_crypto_page:
                    pk = "coinledger"
                elif is_spend_or_payment_page:
                    pk = "ramp"
                elif is_credit_score_page:
                    pk = "wallethub"
                elif is_credit_or_capital_page:
                    pk = "xendoo"
                elif is_treasury_page:
                    pk = "mercury"
                else:
                    pk = "rippling"
        if pk not in live_partner_keys:
            return ""
        if pk != old_pk:
            sec_html = re.sub(
                rf'data-partner=["\']{re.escape(old_pk)}["\']',
                f'data-partner="{pk}"',
                sec_html,
                flags=re.I,
            )
            sec_html = re.sub(
                rf'href=["\']/r/{re.escape(old_pk)}(?=["\'\?])',
                f'href="/r/{pk}',
                sec_html,
                flags=re.I,
            )
            sec_html = re.sub(
                rf'(data-cta-id=["\'][^"\']*?)-{re.escape(old_pk)}(["\'])',
                rf'\g<1>-{pk}\g<2>',
                sec_html,
                flags=re.I,
            )
        ov_href = _build_r_href(pk, "overlay", "overlay_primary_cta")
        if has_estate_structure:
            sec_html = re.sub(
                r'(<a\s+[^>]*?)href=["\'][^"\']+["\']',
                rf'\g<1>href="{ov_href}"',
                sec_html,
                count=1,
                flags=re.I,
            )
        resolved = _resolve_copy(pk)
        if not resolved:
            return sec_html
        p_name, p_cta, p_url = resolved
        p_obj = registry.get(pk)
        p_status = _effective_dom_status(pk, p_obj)
        safe_url = html_lib.escape(p_url)
        sec_html = re.sub(
            r'data-partner-url=["\'][^"\']*["\']',
            f'data-partner-url="{safe_url}"',
            sec_html,
        )
        expected_tokens = EXPECTED_PARTNER_BRAND_TOKENS.get(pk, ())
        forbidden_tokens = FORBIDDEN_REPLACED_BRAND_TOKENS.get(pk, ())
        sec_text_lower = re.sub(r"<[^>]+>", " ", sec_html).lower()
        needs_fix = (
            pk != old_pk
            or p_name.lower() not in sec_text_lower
            or p_cta.lower() not in sec_text_lower
            or any(f_tok in sec_text_lower for f_tok in forbidden_tokens)
            or (bool(expected_tokens) and not any(tok in sec_text_lower for tok in expected_tokens))
            or (prop == "gainhelm" and has_gainhelm_cross_framework_leak(sec_html, page_slug))
        )
        if needs_fix:
            safe_name = html_lib.escape(p_name)
            safe_cta = html_lib.escape(p_cta)
            p_desc = _resolve_desc(pk) or (p_obj.description if p_obj else "")
            sec_html = re.sub(
                r'(<h3[^>]*>)(.*?)(</h3>)',
                rf"\g<1>Recommended Partner Solution: {safe_name}\g<3>",
                sec_html,
                count=1,
                flags=re.S | re.I,
            )
            if p_desc:
                sec_html = re.sub(
                    r'(<p\s+class=["\']overlay-partner-desc["\'][^>]*>)(.*?)(</p>)',
                    rf"\g<1>{html_lib.escape(p_desc)}\g<3>",
                    sec_html,
                    count=1,
                    flags=re.S | re.I,
                )
            sec_html = re.sub(
                r'(<a\s+[^>]*href=["\']/r/[a-z0-9_]+[^"\']*["\'][^>]*>)(.*?)(</a>)',
                rf"\g<1>{safe_cta}\g<3>",
                sec_html,
                count=1,
                flags=re.S | re.I,
            )
        if 'data-status=' not in sec_html:
            sec_html = re.sub(
                r'(<a\s+[^>]*href=["\']/r/[a-z0-9_]+[^"\']*["\'])',
                rf'\g<1> data-status="{html_lib.escape(p_status)}"',
                sec_html,
                count=1,
                flags=re.I,
            )
        else:
            sec_html = re.sub(
                r'data-status=["\'][^"\']*["\']',
                f'data-status="{html_lib.escape(p_status)}"',
                sec_html,
                flags=re.I,
            )
        return sec_html

    updated = re.sub(
        r'<section\s+class=["\'][^"\']*overlay-partner-offer[^"\']*["\'][^>]*>.*?</section>',
        _replace_overlay_section,
        updated,
        flags=re.S | re.I,
    )

    def _resolve_badge(pk: str) -> str:
        partner = registry.get(pk)
        if not partner:
            return ""
        return resolve_contextual_partner_offer_copy(
            partner_key=pk,
            p_obj=partner,
            slug=page_slug,
            vertical_family=page_v_fam,
            property_id=prop,
        )["badge"]

    def _replace_card_heading(match: re.Match) -> str:
        badge_open = match.group(1) or ""
        badge_text = match.group(2) or ""
        badge_close = match.group(3) or ""
        h_open = match.group(4)
        h_text = match.group(5)
        h_close = match.group(6)
        between = match.group(7)
        href_attr = match.group(8)
        pk = match.group(9).lower()
        resolved = _resolve_copy(pk)
        if not resolved:
            return match.group(0)
        p_name, _, _ = resolved
        forbidden_tokens = FORBIDDEN_REPLACED_BRAND_TOKENS.get(pk, ())
        expected_tokens = EXPECTED_PARTNER_BRAND_TOKENS.get(pk, ())
        combined_low = f"{h_text} {between}".lower()
        new_badge = badge_text
        badge_changed = False
        if badge_open:
            badge_low = badge_text.lower()
            badge_drift = (
                any(f_tok in badge_low for f_tok in forbidden_tokens)
                or (prop == "gainhelm" and has_gainhelm_cross_framework_leak(badge_text, page_slug))
            )
            if badge_drift:
                rep_badge = _resolve_badge(pk)
                if rep_badge:
                    new_badge = html_lib.escape(rep_badge)
                    badge_changed = True
        head_changed = (
            any(f_tok in combined_low for f_tok in forbidden_tokens)
            or (bool(expected_tokens) and not any(tok in combined_low for tok in expected_tokens))
            or (prop == "gainhelm" and has_gainhelm_cross_framework_leak(f"{h_text} {between}", page_slug))
        )
        if not head_changed and not badge_changed:
            return match.group(0)
        new_head = f"{h_open}{html_lib.escape(p_name)}{h_close}" if head_changed else f"{h_open}{h_text}{h_close}"
        if head_changed:
            p_desc = _resolve_desc(pk)
            if p_desc:
                between = re.sub(
                    r'(<p[^>]*>)(.*?)(</p>)',
                    rf"\g<1>{html_lib.escape(p_desc)}\g<3>",
                    between,
                    count=1,
                    flags=re.S | re.I,
                )
        prefix_badge = f"{badge_open}{new_badge}{badge_close}" if badge_open else ""
        return f"{prefix_badge}{new_head}{between}{href_attr}"

    updated = re.sub(
        r'(?:(<span\b[^>]*class=["\'][^"\']*\bpartner-badge\b[^"\']*["\'][^>]*>)([^<]*)(</span>\s*))?(<h[34][^>]*>)([^<]*)(</h[34]>)((?:(?!</a>).){0,400}?)(href=["\']/r/([a-z0-9_]+))',
        _replace_card_heading,
        updated,
        flags=re.S | re.I,
    )

    def _replace_anchor(match: re.Match) -> str:
        open_tag = match.group(1)
        pk = match.group(3).lower()
        inner_html = match.group(4)
        close_tag = match.group(5)
        resolved = _resolve_copy(pk)
        if not resolved:
            return match.group(0)
        _, p_cta, _ = resolved
        p_obj = registry.get(pk)
        p_status = _effective_dom_status(pk, p_obj)
        if 'data-status=' not in open_tag:
            open_tag = open_tag[:-1] + f' data-status="{html_lib.escape(p_status)}">'
        else:
            open_tag = re.sub(
                r'data-status=["\'][^"\']*["\']',
                f'data-status="{html_lib.escape(p_status)}"',
                open_tag,
                flags=re.I,
            )
        forbidden_tokens = FORBIDDEN_REPLACED_BRAND_TOKENS.get(pk, ())
        expected_tokens = EXPECTED_PARTNER_BRAND_TOKENS.get(pk, ())
        btn_text = re.sub(r"<[^>]+>", " ", inner_html)
        btn_text = re.sub(r"\s+", " ", btn_text).strip()
        start_ctx = max(0, match.start() - 450)
        ctx_window = re.sub(r"<[^>]+>", " ", updated[start_ctx : match.end()])
        ctx_window = re.sub(r"\s+", " ", ctx_window).strip().lower()
        has_forbidden = any(f_tok in btn_text.lower() for f_tok in forbidden_tokens) or (
            prop == "gainhelm" and has_gainhelm_cross_framework_leak(btn_text, page_slug)
        )
        missing_expected = bool(expected_tokens) and not any(tok in ctx_window for tok in expected_tokens)
        if has_forbidden or missing_expected:
            safe_cta = html_lib.escape(p_cta)
            if "&rarr;" in inner_html or "\u2192" in inner_html:
                return f"{open_tag}{safe_cta} &rarr;{close_tag}"
            return f"{open_tag}{safe_cta}{close_tag}"
        return f"{open_tag}{inner_html}{close_tag}"

    updated = re.sub(
        r'(<a\s+[^>]*href=["\'](/r/([a-z0-9_]+)[^"\']*)["\'][^>]*>)(.*?)(</a>)',
        _replace_anchor,
        updated,
        flags=re.S | re.I,
    )

    primary_inline_pk: Optional[str] = None
    eff_gh_pk: str = ""
    promoted_px_cand: str = ""

    if prop == "prexvo":
        promoted_px_cand, eff_px_pk, px_keys_ordered = _resolve_prexvo_promoted_partner(
            updated,
            gsc_inline_meta,
            preserve_promoted_primary,
        )
        px_keys_ordered = [k for k in px_keys_ordered if k in live_partner_keys]
        eff_px_pk = eff_px_pk if eff_px_pk in live_partner_keys else (px_keys_ordered[0] if px_keys_ordered else "")
        promoted_px_cand = promoted_px_cand if promoted_px_cand in live_partner_keys else ""
        px_roster_csv = ",".join(px_keys_ordered)
        px_companies_csv = ",".join(
            COMPANY_BRAND_BY_PARTNER_KEY.get(k, k) for k in px_keys_ordered
        )
        px_models_list = list(
            dict.fromkeys(
                PREXVO_AFFILIATES[k].partnership_model
                for k in px_keys_ordered
                if PREXVO_AFFILIATES.get(k)
            )
        )
        px_models_csv = ",".join(px_models_list) or "CPA_BOUNTY,QUALIFIED_LEAD_CPL"
        eff_px_obj = PREXVO_AFFILIATES.get(eff_px_pk) if eff_px_pk else None
        px_lead_model = (eff_px_obj.partnership_model if eff_px_obj else "CPA_BOUNTY")

        def _expand_prexvo_refinance_section(match: re.Match) -> str:
            sec_html = match.group(0)
            if not px_keys_ordered or not eff_px_pk:
                return sec_html
            has_any_px_route = any(
                f"/r/{k}" in sec_html
                for k in ("splash_financial", "credible", "lendkey", "sofi", "earnest")
            )
            first_card_m = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b[^"\']*["\'][^>]*>(.*?)</a>',
                sec_html,
                flags=re.S | re.I,
            )
            first_card_blob = first_card_m.group(0) if first_card_m else ""
            first_card_pk_m = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', first_card_blob, flags=re.I)
            first_card_pk = first_card_pk_m.group(1).lower() if first_card_pk_m else ""
            first_card_slot_m = re.search(r'data-cta-slot=["\']([^"\']+)["\']', first_card_blob, flags=re.I)
            first_card_slot = first_card_slot_m.group(1).lower() if first_card_slot_m else ""
            sec_card_pks = re.findall(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b[^"\']*["\'][^>]*\bdata-partner=["\']([a-z0-9_]+)["\']',
                sec_html,
                flags=re.I,
            )
            is_already_valid = (
                "data-partner-roster=" in sec_html
                and "sofi" not in sec_html.lower()
                and "earnest" not in sec_html.lower()
                and (
                    f'data-primary-partner="{eff_px_pk}"' in sec_html
                    or f"data-primary-partner='{eff_px_pk}'" in sec_html
                )
                and len(sec_card_pks) >= len(px_keys_ordered)
                and first_card_pk == eff_px_pk
                and first_card_slot == "calculator_primary_cta"
            )
            if (
                'data-restricted-public-service="true"' in sec_html
                or 'data-commercial-offers="none"' in sec_html
                or 'data-commercial-offers="suppressed-default"' in sec_html
                or "ymyl-public-service-guardrail" in sec_html
                or not has_any_px_route
                or is_already_valid
            ):
                return sec_html
            return _build_prexvo_refinance_section_html(
                raw_sec=sec_html,
                ordered_offers_or_keys=px_keys_ordered,
                slug_id=page_slug,
                page_v_fam=page_v_fam,
                lead_pk=eff_px_pk,
                lead_model=px_lead_model,
                models_csv=px_models_csv,
                roster_keys_csv=px_roster_csv,
                companies_csv=px_companies_csv,
            )

        if px_keys_ordered and eff_px_pk:
            updated = re.sub(
                r'<section\b[^>]*\bclass=["\'][^"\']*(?:refinance-partner-section|partners-section)[^"\']*["\'][^>]*>.*?</section>',
                _expand_prexvo_refinance_section,
                updated,
                flags=re.S | re.I,
            )
            updated = re.sub(
                r'<section\s+class=["\']partners-section["\'](?![^>]*data-partner-roster=)([^>]*)>',
                rf'<section class="partners-section"\g<1> data-partner="{eff_px_pk}" data-primary-partner="{eff_px_pk}" data-partnership-model="{html_lib.escape(px_lead_model)}" data-partner-models="{html_lib.escape(px_models_csv)}" data-partner-roster="{html_lib.escape(px_roster_csv)}" data-partner-companies="{html_lib.escape(px_companies_csv)}">',
                updated,
                count=1,
                flags=re.I,
            )
            updated = re.sub(
                r'(<section\s+class=["\']partners-section["\'][^>]*data-partner-roster=["\'][^"\']+["\'])(?![^>]*data-partnership-model=)([^>]*>)',
                rf'\g<1> data-partnership-model="{html_lib.escape(px_lead_model)}" data-partner-models="{html_lib.escape(px_models_csv)}"\g<2>',
                updated,
                count=1,
                flags=re.I,
            )
            if (
                "ymyl-public-service-guardrail" not in updated
                and 'data-restricted-public-service="true"' not in updated
                and 'data-commercial-offers="none"' not in updated
                and 'data-commercial-offers="suppressed-default"' not in updated
                and any(f"/r/{k}" in updated for k in px_keys_ordered)
            ):
                primary_inline_pk = eff_px_pk

    elif prop == "gainhelm":
        gh_fw_prof = get_gainhelm_framework_profile(slug=page_slug, vertical=page_v_fam)
        gh_primary_pk = str(gh_fw_prof.get("primary_partner_key") or "vanta_security")
        gh_base_roster = (
            "vanta_security",
            "drata_compliance",
            "sprinto_compliance",
            "thoropass_audit",
            "coalition_cyber_insurance",
            "cobalt_pentest",
        )
        valid_gh_keys = {
            k
            for k in gh_base_roster
            if GAINHELM_AFFILIATES.get(k) and k in live_partner_keys
        }
        if gh_primary_pk not in valid_gh_keys and gh_primary_pk in live_partner_keys and GAINHELM_AFFILIATES.get(gh_primary_pk):
            valid_gh_keys.add(gh_primary_pk)

        gh_sec_pat = (
            r'<section\b[^>]*\bclass=["\'][^"\']*'
            r'(?:refinance-partner-section|affiliates?-section|partners-section)'
            r'[^"\']*["\'][^>]*>.*?</section>'
        )
        gh_sec_m = re.search(gh_sec_pat, updated, flags=re.S | re.I)
        sec_html_probe = gh_sec_m.group(0) if gh_sec_m else ""
        sec_open_m = re.match(r"<section\b[^>]*>", sec_html_probe, flags=re.I) if sec_html_probe else None
        sec_open = sec_open_m.group(0) if sec_open_m else ""
        sec_pk_m = re.search(r'data-primary-partner=["\']([a-z0-9_]+)["\']', sec_open or sec_html_probe, flags=re.I)
        sec_pk = sec_pk_m.group(1).lower() if sec_pk_m else ""
        first_card_pk = ""
        if sec_html_probe:
            c_tag_m = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b[^"\']*["\'][^>]*>',
                sec_html_probe,
                flags=re.I,
            )
            if c_tag_m:
                c_pk_m = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', c_tag_m.group(0), flags=re.I)
                if c_pk_m:
                    first_card_pk = c_pk_m.group(1).lower()
        gsc_cand_probe = str(gsc_inline_meta.get("data-partner") or "").strip().lower()
        sec_repositioned = bool(re.search(r'data-gsc-repositioned=["\']true["\']', sec_open, flags=re.I))
        inline_repositioned = str(gsc_inline_meta.get("data-gsc-repositioned") or "").strip().lower() == "true"

        promoted_cand = ""
        if sec_repositioned and sec_pk in valid_gh_keys:
            promoted_cand = sec_pk
        elif inline_repositioned and gsc_cand_probe in valid_gh_keys:
            promoted_cand = gsc_cand_probe
        elif preserve_promoted_primary:
            if sec_pk in valid_gh_keys:
                promoted_cand = sec_pk
            elif gsc_cand_probe in valid_gh_keys:
                promoted_cand = gsc_cand_probe
        elif (
            sec_pk in valid_gh_keys
            and sec_pk != "vanta_security"
            and sec_pk == first_card_pk
            and not has_gainhelm_cross_framework_leak(sec_html_probe, page_slug)
        ):
            promoted_cand = sec_pk

        eff_gh_pk = promoted_cand if promoted_cand in valid_gh_keys else (gh_primary_pk if gh_primary_pk in valid_gh_keys else "")
        gainhelm_roster_keys = tuple(
            ([eff_gh_pk] if eff_gh_pk else [])
            + [k for k in gh_base_roster if k != eff_gh_pk and k in valid_gh_keys]
        )
        if not eff_gh_pk and gainhelm_roster_keys:
            eff_gh_pk = gainhelm_roster_keys[0]
        gainhelm_roster_csv = ",".join(gainhelm_roster_keys)
        gainhelm_companies_csv = ",".join(
            COMPANY_BRAND_BY_PARTNER_KEY.get(k, k) for k in gainhelm_roster_keys
        )
        gh_models_seen: List[str] = []
        for k in gainhelm_roster_keys:
            p_k = GAINHELM_AFFILIATES.get(k)
            if p_k and p_k.partnership_model not in gh_models_seen:
                gh_models_seen.append(p_k.partnership_model)
        gainhelm_models_csv = ",".join(gh_models_seen) or "QUALIFIED_LEAD_CPL,HYBRID_CPA_REVSHARE,CPA_BOUNTY"
        prim_p_obj = GAINHELM_AFFILIATES.get(eff_gh_pk) if eff_gh_pk else None
        gainhelm_primary_model = html_lib.escape(
            (prim_p_obj.partnership_model if prim_p_obj else None) or "QUALIFIED_LEAD_CPL"
        )

        def _expand_gainhelm_partner_section(match: re.Match) -> str:
            sec_html = match.group(0)
            if not gainhelm_roster_keys or not eff_gh_pk:
                return sec_html
            prim_obj = GAINHELM_AFFILIATES.get(eff_gh_pk)
            prim_badge = (
                resolve_contextual_partner_offer_copy(
                    partner_key=eff_gh_pk,
                    p_obj=prim_obj,
                    slug=page_slug,
                    vertical_family=page_v_fam,
                    property_id=prop,
                )["badge"]
                if prim_obj
                else ""
            )
            sec_has_leak = has_gainhelm_cross_framework_leak(sec_html, page_slug)
            first_card_m = re.search(
                r'<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b[^"\']*["\'][^>]*>.*?'
                r'(?=<div\b[^>]*\bclass=["\'][^"\']*\bpartner-card\b|</section>)',
                sec_html,
                flags=re.S | re.I,
            )
            first_card_scope = first_card_m.group(0) if first_card_m else sec_html
            if (
                'data-restricted-public-service="true"' in sec_html
                or 'data-commercial-offers="none"' in sec_html
                or 'data-commercial-offers="suppressed-default"' in sec_html
                or (
                    "partners-section" in sec_html
                    and "/r/" not in sec_html
                    and "partner-card" not in sec_html
                    and not sec_has_leak
                )
                or (
                    (
                        f'data-primary-partner="{eff_gh_pk}"' in sec_html
                        or f"data-primary-partner='{eff_gh_pk}'" in sec_html
                    )
                    and not sec_has_leak
                    and ("data-gsc-tier=" in sec_html or 'data-mechanic="compliant_intent_monetization"' in sec_html)
                    and "data-partner-roster=" in sec_html
                    and all(pk in sec_html for pk in gainhelm_roster_keys)
                    and (not prim_badge or html_lib.escape(prim_badge) in first_card_scope)
                )
            ):
                return sec_html
            sec_open_m = re.match(r"<section\b[^>]*>", sec_html, flags=re.I)
            sec_id_attr = _extract_section_id_attr(sec_open_m.group(0) if sec_open_m else "")
            gsc_tier_m = re.search(r'data-gsc-tier=["\']([^"\']+)["\']', sec_html, flags=re.I)
            gsc_tier_attr = f' data-gsc-tier="{html_lib.escape(gsc_tier_m.group(1))}"' if gsc_tier_m else ""
            gsc_rep_m = re.search(r'data-gsc-repositioned=["\']([^"\']+)["\']', sec_html, flags=re.I)
            gsc_rep_attr = f' data-gsc-repositioned="{html_lib.escape(gsc_rep_m.group(1))}"' if gsc_rep_m else ""
            h2_m = re.search(r"<h2\b[^>]*>.*?</h2>", sec_html, flags=re.S | re.I)
            h2_block = f"      {h2_m.group(0)}\n" if h2_m else ""
            reg_block = _extract_partner_registration_drawer(sec_html)
            cards_html: List[str] = []
            for idx, pk in enumerate(gainhelm_roster_keys, start=1):
                p_obj = GAINHELM_AFFILIATES.get(pk)
                if not p_obj:
                    continue
                ctx_gh = resolve_contextual_partner_offer_copy(
                    partner_key=pk,
                    p_obj=p_obj,
                    slug=page_slug,
                    vertical_family=page_v_fam,
                    property_id=prop,
                )
                slot = "calculator_primary_cta" if idx == 1 else "partner_matrix_card"
                card_href = _build_r_href(pk, f"card_{idx}", slot)
                safe_s = html_lib.escape(page_slug)
                safe_sub = html_lib.escape(f"{page_slug}_card_{idx}")
                safe_p_model = html_lib.escape(p_obj.partnership_model)
                c_brand = html_lib.escape(COMPANY_BRAND_BY_PARTNER_KEY.get(pk, pk))
                eff_card_st = html_lib.escape(_effective_dom_status(pk, p_obj))
                cards_html.append(
                    f'      <div class="partner-card" data-partner="{pk}" data-company-brand="{c_brand}" data-partnership-model="{safe_p_model}" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">\n'
                    f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--brand-primary); text-transform: uppercase;">{html_lib.escape(ctx_gh["badge"])}</span>\n'
                    f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html_lib.escape(ctx_gh["name"])}</h3>\n'
                    f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html_lib.escape(ctx_gh["description"])}</p>\n'
                    f'        <a href="{card_href}" target="_blank" rel="noopener sponsored nofollow" class="partner-btn btn-cta touch-target" data-partner="{pk}" data-company-brand="{c_brand}" data-partnership-model="{safe_p_model}" data-tool="{safe_s}" data-subid="{safe_sub}" data-status="{eff_card_st}" data-cta-slot="{slot}">\n'
                    f'          {html_lib.escape(ctx_gh["cta_text"])} &rarr;\n'
                    f'        </a>\n'
                    f'      </div>'
                )
            grid_inner = "\n".join(cards_html)
            sec_cls = (
                "partners-section refinance-partner-section affiliates-section"
                if "partners-section" in sec_html
                else "refinance-partner-section affiliates-section"
            )
            return (
                f'<section{sec_id_attr} class="{sec_cls}" data-mechanic="compliant_intent_monetization" '
                f'data-partner="{eff_gh_pk}" data-primary-partner="{eff_gh_pk}" '
                f'data-partnership-model="{gainhelm_primary_model}" '
                f'data-partner-models="{gainhelm_models_csv}" '
                f'data-partner-roster="{gainhelm_roster_csv}" '
                f'data-partner-companies="{gainhelm_companies_csv}"'
                f'{gsc_tier_attr}{gsc_rep_attr} '
                'style="margin: 1.5rem 0;">\n'
                f'{h2_block}'
                '      <div class="partner-matrix-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem;">\n'
                f'{grid_inner}\n'
                '      </div>'
                f'{reg_block}\n'
                '    </section>'
            )

        if gainhelm_roster_keys and eff_gh_pk:
            updated = re.sub(
                gh_sec_pat,
                _expand_gainhelm_partner_section,
                updated,
                flags=re.S | re.I,
            )
            updated = re.sub(
                r'<section\b[^>]*\bclass=["\']partners-section["\'](?![^>]*data-partner-roster=)([^>]*)>',
                rf'<section class="partners-section"\g<1> data-partner="{eff_gh_pk}" data-primary-partner="{eff_gh_pk}" data-partnership-model="{gainhelm_primary_model}" data-partner-models="{gainhelm_models_csv}" data-partner-roster="{gainhelm_roster_csv}" data-partner-companies="{gainhelm_companies_csv}">',
                updated,
                count=1,
                flags=re.I,
            )
            if (
                'data-restricted-public-service="true"' not in updated
                and 'data-commercial-offers="none"' not in updated
                and 'data-commercial-offers="suppressed-default"' not in updated
                and "/r/" in updated
            ):
                primary_inline_pk = eff_gh_pk

    elif prop == "lienbond":
        if (
            'data-restricted-public-service="true"' not in updated
            and 'data-commercial-offers="none"' not in updated
            and 'data-commercial-offers="suppressed-default"' not in updated
            and "/r/" in updated
        ):
            m_prim_lb = re.search(r'data-primary-partner=["\']([a-z0-9_]+)["\']', updated, re.I)
            cand_lb = m_prim_lb.group(1).lower() if m_prim_lb else ""
            if cand_lb in LIENBOND_AFFILIATES and cand_lb in live_partner_keys:
                primary_inline_pk = cand_lb
            else:
                live_lb = [k for k in LIENBOND_AFFILIATES if k in live_partner_keys]
                if live_lb:
                    primary_inline_pk = live_lb[0]

    elif prop in ("profithelm", "exchange1031"):
        def _build_profithelm_partner_card(pk: str, card_idx: int = 1) -> str:
            p_obj = PROFITHELM_AFFILIATES.get(pk)
            if not p_obj or pk not in live_partner_keys:
                return ""
            ctx_card = resolve_contextual_partner_offer_copy(
                partner_key=pk,
                p_obj=p_obj,
                slug=page_slug,
                vertical_family=page_v_fam,
                property_id=prop,
            )
            eff_st = _effective_dom_status(pk, p_obj)
            slot = "calculator_primary_cta" if card_idx == 1 else "partner_matrix_card"
            card_href = _build_r_href(pk, f"card_{card_idx}", slot)
            safe_s = html_lib.escape(page_slug)
            safe_sub = html_lib.escape(f"{page_slug}_card_{card_idx}")
            c_brand = html_lib.escape(COMPANY_BRAND_BY_PARTNER_KEY.get(pk, pk))
            c_role = "primary" if card_idx == 1 else "secondary"
            safe_p_model = html_lib.escape(p_obj.partnership_model)
            return (
                f'\n    <div class="affiliate-card partner-card" data-partner="{pk}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" data-partnership-model="{safe_p_model}">\n'
                f'      <div class="affiliate-info">\n'
                f'        <span class="affiliate-badge">{html_lib.escape(ctx_card["badge"])}</span>\n'
                f'        <span class="affiliate-disclosure-badge" style="font-size: 0.75rem; color: var(--text-secondary); margin-left: 0.5rem; font-weight: 500;">Sponsored / Partner</span>\n'
                f'        <h3 class="affiliate-title">{html_lib.escape(ctx_card["name"])}</h3>\n'
                f'        <p class="affiliate-desc">{html_lib.escape(ctx_card["description"])}</p>\n'
                f'      </div>\n'
                f'      <div>\n'
                f'        <a href="{card_href}" target="_blank" rel="noopener sponsored nofollow" data-partner="{pk}" data-status="{html_lib.escape(eff_st)}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" data-partnership-model="{safe_p_model}" data-tool="{safe_s}" data-subid="{safe_sub}" data-cta-slot="{slot}" data-tier="starter" class="btn-cta partner-cta touch-target">\n'
                f'          {html_lib.escape(ctx_card["cta_text"])} &rarr;\n'
                f'        </a>\n'
                f'      </div>\n'
                f'    </div>'
            )

        def _expand_profithelm_affiliates_section(match: re.Match) -> str:
            nonlocal primary_inline_pk
            sec_html = match.group(0)
            if (
                'data-partner-roster="' in sec_html
                and (gsc_inline_meta or 'data-gsc-tier="' in sec_html)
                and "crest_capital" not in sec_html
                and "ipx1031" not in sec_html
                and "suretybonds_direct" not in sec_html
                and "next_insurance_b2b" not in sec_html
                and "invoice_simple" not in sec_html
            ):
                m_prim = re.search(r'data-primary-partner=["\']([a-z0-9_]+)["\']', sec_html, re.I)
                if m_prim:
                    primary_inline_pk = m_prim.group(1).lower()
                if 'data-partnership-model="' not in sec_html and primary_inline_pk:
                    lead_mod = html_lib.escape(str(resolve_partnership_model_spec(primary_inline_pk)["partnership_model"]))
                    rost_m = re.search(r'data-partner-roster=["\']([^"\']+)["\']', sec_html, re.I)
                    rost_keys = [k.strip() for k in (rost_m.group(1).split(",") if rost_m else [primary_inline_pk]) if k.strip()]
                    mods_csv = html_lib.escape(
                        ",".join(dict.fromkeys(str(resolve_partnership_model_spec(rk)["partnership_model"]) for rk in rost_keys))
                    )
                    sec_html = re.sub(
                        r'(<section\s+[^>]*data-partner-roster=["\'][^"\']+["\'])',
                        rf'\g<1> data-partnership-model="{lead_mod}" data-partner-models="{mods_csv}"',
                        sec_html,
                        count=1,
                        flags=re.I,
                    )
                return sec_html
            if "affiliate-card" in sec_html:
                if is_general_tax_page:
                    sorted_keys = (
                        ["coinledger", "efile_com", "freetaxusa"]
                        if is_capital_gains_page
                        else ["efile_com", "eztaxreturn_com", "freetaxusa", "xendoo"]
                    )
                elif is_1031_page or is_entity_or_contract_page:
                    sorted_keys = ["lawdepot", "xendoo", "mercury"]
                elif is_179_equipment_page:
                    sorted_keys = ["xendoo", "ramp", "mercury"]
                elif is_174_page:
                    sorted_keys = ["xendoo", "rippling", "ramp"]
                elif is_prediction_odds_page:
                    sorted_keys = ["kalshi", "coinledger", "koinly"]
                elif is_crypto_page:
                    sorted_keys = (
                        ["coinledger", "koinly", "kalshi"]
                        if is_prediction_page
                        else ["coinledger", "koinly", "xendoo"]
                    )
                elif is_s_corp_or_workers_comp:
                    sorted_keys = ["rippling", "gusto", "xendoo"]
                elif is_spend_or_payment_page:
                    sorted_keys = ["ramp", "mercury", "rippling"]
                elif is_credit_score_page:
                    sorted_keys = ["wallethub", "ramp", "mercury"]
                elif is_credit_or_capital_page:
                    sorted_keys = ["xendoo", "ramp", "wallethub"]
                elif is_treasury_page:
                    sorted_keys = ["mercury", "ramp", "wallethub"]
                else:
                    sorted_keys = ["xendoo", "ramp", "rippling", "mercury"]
                primary_inline_pk = sorted_keys[0]
                lead_pk = html_lib.escape(sorted_keys[0])
                lead_mod = html_lib.escape(str(resolve_partnership_model_spec(sorted_keys[0])["partnership_model"]))
                roster_csv = html_lib.escape(",".join(sorted_keys))
                brands_list: List[str] = []
                models_list: List[str] = []
                for k_item in sorted_keys:
                    b_nm = COMPANY_BRAND_BY_PARTNER_KEY.get(k_item, k_item)
                    if b_nm not in brands_list:
                        brands_list.append(b_nm)
                    m_nm = str(resolve_partnership_model_spec(k_item)["partnership_model"])
                    if m_nm not in models_list:
                        models_list.append(m_nm)
                brands_csv = html_lib.escape(",".join(brands_list))
                models_csv = html_lib.escape(",".join(models_list))
                h2_m = re.search(r"<h2[^>]*>.*?</h2>", sec_html, re.S | re.I)
                h2_html = h2_m.group(0) if h2_m else '<h2 style="font-size: 1.375rem; font-weight: 700; margin-bottom: 1rem;">Recommended Partner Solutions</h2>'
                cards_joined = "\n".join(
                    _build_profithelm_partner_card(k, idx)
                    for idx, k in enumerate(sorted_keys, start=1)
                )
                return (
                    f'<section class="affiliate-section affiliates-section" data-mechanic="compliant_intent_monetization" '
                    f'data-partner="{lead_pk}" data-primary-partner="{lead_pk}" '
                    f'data-partnership-model="{lead_mod}" data-partner-models="{models_csv}" '
                    f'data-partner-roster="{roster_csv}" data-partner-companies="{brands_csv}">\n'
                    f'        {h2_html}'
                    f'{cards_joined}\n'
                    f'      </section>'
                )

            found_keys: List[str] = []
            for m_k in re.finditer(r'href=["\']/r/([a-z0-9_]+)', sec_html, re.I):
                k_val = m_k.group(1).lower()
                if (
                    k_val in PROFITHELM_AFFILIATES
                    and PROFITHELM_AFFILIATES[k_val].status == "live"
                    and k_val not in found_keys
                ):
                    found_keys.append(k_val)

            # Enrich with approved live direct sponsors matched to page vertical
            if is_prediction_page and "kalshi" not in found_keys:
                found_keys.append("kalshi")
            if (
                not is_1031_page
                and not is_general_tax_page
                and ("coinledger" in found_keys or is_crypto_page)
                and "koinly" not in found_keys
            ):
                if "coinledger" not in found_keys:
                    found_keys.append("coinledger")
                found_keys.append("koinly")
            if (
                "mercury" in found_keys
                and "rippling" not in found_keys
                and any(tok in page_identity_lower for tok in ("section-174", "section 174", "r-and-d", "r&d", "payroll", "s-corp", "workers-comp", "179", "runway", "burn", "factoring", "tariff", "surety"))
            ):
                found_keys.append("rippling")
            if (
                "rippling" in found_keys
                and "mercury" not in found_keys
                and any(tok in page_identity_lower for tok in ("workers-comp", "payroll", "s-corp"))
            ):
                found_keys.append("mercury")

            sorted_keys = list(found_keys)
            if not sorted_keys:
                if is_1031_page:
                    sorted_keys = ["lawdepot", "xendoo"]
                elif is_general_tax_page:
                    sorted_keys = ["efile_com", "eztaxreturn_com", "freetaxusa"]
                elif is_crypto_page:
                    sorted_keys = ["coinledger", "koinly"]
                elif is_prediction_page:
                    sorted_keys = ["kalshi"]
                else:
                    sorted_keys = ["xendoo", "ramp"]
            if sorted_keys:
                primary_inline_pk = sorted_keys[0]

            # Fallback for minimal unit-test snippets without .affiliate-card
            extra_cards = ""
            for idx, k in enumerate(sorted_keys, start=1):
                if f"/r/{k}" not in sec_html:
                    extra_cards += _build_profithelm_partner_card(k, idx)
            if not extra_cards:
                return sec_html
            return re.sub(
                r"(</section>\s*$)",
                rf"{extra_cards}\n  \g<1>",
                sec_html,
                count=1,
                flags=re.S | re.I,
            )

        updated = re.sub(
            r'<section\s+class=["\'][^"\']*affiliates?-section[^"\']*["\'][^>]*>.*?</section>',
            _expand_profithelm_affiliates_section,
            updated,
            flags=re.S | re.I,
        )

        # Ensure affiliates-section sits immediately before decision-framework-card when buried after it
        df_match = re.search(r'<section\s+class=["\'][^"\']*decision-framework-card[^"\']*["\'][^>]*>', updated, re.I)
        aff_sec_match = re.search(r'<section\s+class=["\'][^"\']*affiliates?-section[^"\']*["\'][^>]*>.*?</section>', updated, re.S | re.I)
        if df_match and aff_sec_match and aff_sec_match.start() > df_match.start():
            aff_block = aff_sec_match.group(0)
            updated = updated[:aff_sec_match.start()] + updated[aff_sec_match.end():]
            df_match_2 = re.search(r'<section\s+class=["\'][^"\']*decision-framework-card[^"\']*["\'][^>]*>', updated, re.I)
            if df_match_2:
                updated = updated[:df_match_2.start()] + aff_block + "\n\n      " + updated[df_match_2.start():]

    # Inject above-the-fold inline calculator result CTA into the calculator output panel
    is_suppressed_ymyl_page = (
        'data-restricted-public-service="true"' in updated
        or 'data-commercial-offers="none"' in updated
        or 'data-commercial-offers="suppressed-default"' in updated
    )
    gsc_cand_pk = str(gsc_inline_meta.get("data-partner") or "").strip().lower()
    if (
        not is_suppressed_ymyl_page
        and gsc_cand_pk in registry
        and gsc_cand_pk in live_partner_keys
        and (prop != "gainhelm" or not eff_gh_pk or gsc_cand_pk == eff_gh_pk)
        and (prop != "prexvo" or not promoted_px_cand or gsc_cand_pk == promoted_px_cand)
    ):
        primary_inline_pk = gsc_cand_pk
    if (
        not is_suppressed_ymyl_page
        and 'id="workpaper-unlock-card"' not in updated
        and primary_inline_pk
        and primary_inline_pk in registry
        and primary_inline_pk in live_partner_keys
    ):
        p_inline = registry[primary_inline_pk]
        ctx_in = resolve_contextual_partner_offer_copy(
            partner_key=primary_inline_pk,
            p_obj=p_inline,
            slug=page_slug,
            vertical_family=page_v_fam,
            property_id=prop,
        )
        safe_badge = html_lib.escape(ctx_in["badge"])
        safe_name = html_lib.escape(ctx_in["name"])
        safe_cta = html_lib.escape(ctx_in["cta_text"])
        safe_status = html_lib.escape(_effective_dom_status(primary_inline_pk, p_inline))
        safe_s = html_lib.escape(page_slug)
        safe_sub = html_lib.escape(f"{page_slug}_inline")
        safe_brand = html_lib.escape(COMPANY_BRAND_BY_PARTNER_KEY.get(primary_inline_pk, primary_inline_pk))
        safe_inline_model = html_lib.escape(p_inline.partnership_model)
        inline_href = _build_r_href(primary_inline_pk, "inline", "calculator_result_inline")
        gsc_extra_attrs = ""
        if gsc_inline_meta:
            gsc_t = html_lib.escape(gsc_inline_meta.get("data-gsc-tier", "baseline"))
            gsc_y = html_lib.escape(gsc_inline_meta.get("data-yield-score", "0"))
            default_rep = "false" if gsc_t.strip().lower() in ("baseline", "baseline_multi_slot") else "true"
            gsc_rep_val = html_lib.escape(gsc_inline_meta.get("data-gsc-repositioned", default_rep))
            gsc_extra_attrs = f'data-gsc-repositioned="{gsc_rep_val}" data-gsc-tier="{gsc_t}" data-yield-score="{gsc_y}" '
        used_preserved_gsc_inline = False
        if (
            preserved_gsc_inline_block
            and gsc_inline_meta.get("data-partner") == primary_inline_pk
            and safe_badge in preserved_gsc_inline_block
            and safe_name in preserved_gsc_inline_block
            and safe_cta in preserved_gsc_inline_block
            and f'data-status="{safe_status}"' in preserved_gsc_inline_block
            and not any(
                f_tok in preserved_gsc_inline_block.lower()
                for f_tok in FORBIDDEN_REPLACED_BRAND_TOKENS.get(primary_inline_pk, ())
            )
            and (prop != "gainhelm" or not has_gainhelm_cross_framework_leak(preserved_gsc_inline_block, page_slug))
        ):
            used_preserved_gsc_inline = True
            inline_cta_html = (
                preserved_gsc_inline_block
                if preserved_gsc_inline_block.startswith("\n")
                else f"\n{preserved_gsc_inline_block}"
            )
        else:
            inline_slot_tag = "Verified Offer" if safe_status == "live" else "Partner Option"
            inline_cta_html = (
                f'\n          <div class="calc-inline-cta" data-mechanic="compliant_intent_monetization" data-partner="{primary_inline_pk}" '
                f'data-company-brand="{safe_brand}" data-partnership-model="{safe_inline_model}" {gsc_extra_attrs}'
                f'style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.75rem 1rem; margin-bottom: 1rem; background: var(--bg-elevated); border: 1px solid var(--brand-border); border-left: 4px solid var(--brand-primary); border-radius: 8px;">\n'
                f'            <div class="calc-inline-cta-copy" style="flex: 1; min-width: 180px;">\n'
                f'              <div style="font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--brand-primary);">{safe_badge} &bull; {inline_slot_tag}</div>\n'
                f'              <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-primary); margin-top: 0.125rem;">{safe_name}</div>\n'
                f'            </div>\n'
                f'            <a href="{inline_href}" target="_blank" rel="noopener sponsored nofollow" data-partner="{primary_inline_pk}" data-company-brand="{safe_brand}" data-partnership-model="{safe_inline_model}" data-tool="{safe_s}" data-subid="{safe_sub}" data-status="{safe_status}" data-tier="starter" data-cta-slot="calculator_result_inline" class="btn-cta touch-target" style="white-space: nowrap;">\n'
                f'              {safe_cta} &rarr;\n'
                f'            </a>\n'
                f'          </div>'
            )
        injected_inline = False
        for pat in (
            r'(<div\s+class=["\'][^"\']*\bresult-card\b[^"\']*["\'][^>]*>\s*<div\s+class=["\'][^"\']*\bcard-header\b[^"\']*["\'][^>]*>.*?</div>)',
            r'(<div\s+class=["\']calculator-grid["\']>.*?<div\s+class=["\']card["\']>.*?<div\s+class=["\'][^"\']*\bcard\b[^"\']*["\'][^>]*>\s*<div\s+class=["\'][^"\']*\bcard-header\b[^"\']*["\'][^>]*>.*?</div>)',
            r'(<div\s+class=["\'][^"\']*calc-outputs-panel[^"\']*["\'][^>]*>\s*<div\s+class=["\']calc-panel-header["\'][^>]*>.*?</div>)',
            r'(<div\s+class=["\'][^"\']*calc-results-column[^"\']*["\'][^>]*>\s*<h3\s+class=["\']calc-column-title["\'][^>]*>.*?</h3>)',
            r'(<div\s+class=["\'][^"\']*\bresult-box\b[^"\']*["\'][^>]*>(?:(?!</div\b).)*?)(</div>)',
        ):
            if re.search(pat, updated, re.S | re.I):
                if "result-box" in pat:
                    if used_preserved_gsc_inline:
                        updated = re.sub(
                            pat,
                            lambda m: f"{m.group(1).rstrip(' \t\r\n')}\n          {preserved_gsc_inline_block.strip()}\n      {m.group(2)}",
                            updated,
                            count=1,
                            flags=re.S | re.I,
                        )
                    else:
                        updated = re.sub(pat, rf"\g<1>{inline_cta_html}\n      \g<2>", updated, count=1, flags=re.S | re.I)
                else:
                    updated = re.sub(pat, rf"\g<1>{inline_cta_html}", updated, count=1, flags=re.S | re.I)
                injected_inline = True
                break
        cta_pos = updated.find('<div class="calc-inline-cta"')
        kpi_pos = updated.find('<div class="kpi-block"')
        kpi_end_candidates = [
            pos
            for pos in (
                updated.find('<div class="calc-statutory-box"', kpi_pos if kpi_pos != -1 else 0),
                updated.find('<div class="share-pro-container"', kpi_pos if kpi_pos != -1 else 0),
                updated.find('<div style="margin-top: 1rem;">', kpi_pos if kpi_pos != -1 else 0),
                updated.find('<div class="lead-capture-card"', kpi_pos if kpi_pos != -1 else 0),
            )
            if pos != -1
        ]
        kpi_end = min(kpi_end_candidates) if kpi_end_candidates else -1
        if cta_pos != -1 and kpi_pos != -1 and kpi_end != -1 and cta_pos < kpi_pos < kpi_end:
            kpi_slice = updated[kpi_pos:kpi_end].strip()
            if kpi_slice and "calc-inline-cta" not in kpi_slice:
                updated = (
                    updated[:cta_pos]
                    + kpi_slice
                    + "\n          "
                    + updated[cta_pos:kpi_pos].rstrip()
                    + updated[kpi_end:]
                )
        rap_meter_m = re.search(
            r'<div\b[^>]*id=["\']rap-subsidy-meter["\'][^>]*>[\s\S]*?<div\s+class=["\']subsidy-meter-legend["\'][^>]*>[\s\S]*?</div>\s*</div>',
            updated,
            flags=re.I,
        )
        cta_pos2 = updated.find('<div class="calc-inline-cta"')
        if rap_meter_m and cta_pos2 != -1 and cta_pos2 < rap_meter_m.start():
            rap_slice = rap_meter_m.group(0).strip()
            updated = (
                updated[:cta_pos2]
                + rap_slice
                + "\n      "
                + updated[cta_pos2 : rap_meter_m.start()].rstrip()
                + updated[rap_meter_m.end() :]
            )
        gh_m1 = re.search(
            r'<div\b[^>]*class=["\'][^"\']*\b(?:calc-metrics-grid|metrics-grid)\b[^"\']*["\'][^>]*>',
            updated,
            flags=re.I,
        )
        cta_pos3 = updated.find('<div class="calc-inline-cta"')
        if gh_m1 and cta_pos3 != -1 and cta_pos3 < gh_m1.start():
            gm_s1 = gh_m1.start()
            gm_d1 = 0
            gm_e1 = -1
            for d_tok1 in re.finditer(r"</?div\b[^>]*>", updated[gm_s1:], flags=re.I):
                t_low1 = d_tok1.group(0).lower()
                if t_low1.startswith("</div"):
                    gm_d1 -= 1
                    if gm_d1 == 0:
                        gm_e1 = gm_s1 + d_tok1.end()
                        break
                elif not t_low1.endswith("/>"):
                    gm_d1 += 1
            if gm_e1 > gm_s1 and ('id="metric-' in updated[gm_s1:gm_e1] or "id='metric-" in updated[gm_s1:gm_e1]):
                updated = (
                    updated[:cta_pos3]
                    + updated[gm_s1:gm_e1].strip()
                    + "\n          "
                    + updated[cta_pos3:gm_s1].rstrip()
                    + updated[gm_e1:]
                )
        has_ext_porcelain_link = bool(
            re.search(
                r'<link\b[^>]*id=["\']pseo-visual-primitives["\']',
                updated,
                flags=re.I,
            )
        )
        if injected_inline and "</head>" in updated and not has_ext_porcelain_link:
            fold_css = (
                '  <style id="pseo-inline-cta-fold">\n'
                '    .hero-section, .tool-header.hero-section { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; margin-bottom: 0.5rem !important; }\n'
                '    .hero-section p, .tool-header.hero-section p { margin-top: 0.25rem !important; margin-bottom: 0.25rem !important; }\n'
                '    .byline-wrap, .breadcrumbs { margin-top: 0.25rem !important; margin-bottom: 0.375rem !important; padding-top: 0.125rem !important; padding-bottom: 0.125rem !important; }\n'
                '    .direct-answer-block, .quick-answer { padding: 0.5rem 0.875rem !important; margin-bottom: 0.5rem !important; font-size: 0.875rem !important; line-height: 1.45 !important; }\n'
                '    .ftc-disclosure-banner { padding: 0.375rem 0.75rem !important; margin-bottom: 0.5rem !important; }\n'
                '    .above-the-fold-compliance { margin-bottom: 0.5rem !important; display: grid !important; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)) !important; gap: 0.5rem !important; }\n'
                '    .ymyl-warning-card, .ftc-disclosure-card { margin-bottom: 0 !important; padding: 0.375rem 0.625rem !important; font-size: 0.7rem !important; line-height: 1.3 !important; }\n'
                '    .interactive-calculator-container { padding: 0.875rem 1.25rem !important; margin-top: 0.5rem !important; margin-bottom: 1rem !important; }\n'
                '    .calc-header { margin-bottom: 0.375rem !important; padding-bottom: 0.25rem !important; }\n'
                '    .calc-switcher-panel { padding: 0.375rem 0.75rem !important; margin-bottom: 0.5rem !important; }\n'
                '    .calc-switcher-header { margin-bottom: 0.25rem !important; }\n'
                '    .calc-column-title { margin-bottom: 0.5rem !important; font-size: 0.95rem !important; }\n'
                '    .calc-panel-header, .card-header { margin-bottom: 0.625rem !important; padding-bottom: 0.5rem !important; }\n'
                '  </style>\n'
            )
            vp_match = re.search(
                r'([ \t]*<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>)',
                updated,
                flags=re.I,
            )
            if vp_match:
                updated = (
                    updated[: vp_match.start()]
                    + fold_css
                    + updated[vp_match.start() :]
                )
            else:
                updated = updated.replace("</head>", f"{fold_css}</head>", 1)

        if _COMPARISON_TABLE_CTA_BAR_RE.search(updated):
            def _replace_comparison_table_cta_bar(tbl_m: re.Match) -> str:
                bar_raw = tbl_m.group(0)
                existing_cls = tbl_m.group(1) or ""
                pk_m = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', bar_raw, re.I)
                if not pk_m:
                    pk_m = re.search(r'href=["\']/r/([a-z0-9_]+)', bar_raw, re.I)
                cur_pk = pk_m.group(1).lower() if pk_m else ""
                cur_obj = registry.get(cur_pk)
                needs_tbl_upgrade = (
                    not cur_obj
                    or cur_pk not in live_partner_keys
                )
                if not needs_tbl_upgrade:
                    return bar_raw
                if primary_inline_pk not in live_partner_keys:
                    return ""
                tbl_href = f"/r/{primary_inline_pk}?source_tool={page_slug}&subid={page_slug}_table&cta_slot=comparison_table_cta"
                gsc_t_m = re.search(r'data-gsc-tier=["\']([^"\']+)["\']', bar_raw, re.I)
                gsc_t_val = gsc_t_m.group(1) if gsc_t_m else "baseline"
                return _render_comparison_table_cta_bar(
                    pk=primary_inline_pk,
                    name=ctx_in["name"],
                    cta_text=ctx_in["cta_text"],
                    brand=COMPANY_BRAND_BY_PARTNER_KEY.get(primary_inline_pk, primary_inline_pk),
                    model=p_inline.partnership_model,
                    href=tbl_href,
                    tool=page_slug,
                    subid=f"{page_slug}_table",
                    status=_effective_dom_status(primary_inline_pk, p_inline),
                    gsc_tier=gsc_t_val,
                    tier_role="primary",
                    existing_class_attr=existing_cls,
                )

            updated = _COMPARISON_TABLE_CTA_BAR_RE.sub(
                _replace_comparison_table_cta_bar,
                updated,
            )

    # Fail-closed pass: hide ALL unapproved/non-live /r/<partner> CTAs and feature 1st-party Stripe workpaper CTA
    updated = strip_unapproved_partner_ctas_from_html(
        updated,
        property_id=prop,
        slug=page_slug,
    )

    # Stamp any remaining bare /r/<partner> anchors with page (source_tool) and slot (subid, cta_slot) attribution
    def _stamp_attribution_on_r_anchor(match: re.Match) -> str:
        full_open = match.group(1)
        raw_href = match.group(2)
        pk = match.group(3).lower()
        start_ctx = max(0, match.start() - 350)
        ctx_before = updated[start_ctx : match.start()].lower()
        if "calc-inline-cta" in ctx_before:
            slot = "calculator_result_inline"
            suffix = "inline"
        elif "overlay-partner-offer" in ctx_before:
            slot = "overlay_primary_cta"
            suffix = "overlay"
        elif "affiliate-cta-section" in ctx_before:
            slot = "standalone_primary_cta"
            suffix = "cta"
        else:
            slot_m = re.search(r'data-cta-slot=["\']([^"\']+)["\']', full_open, re.I)
            slot = slot_m.group(1) if slot_m else "partner_matrix_card"
            suffix = "inline" if slot == "calculator_result_inline" else ("overlay" if "overlay" in slot else "card")

        safe_s = html_lib.escape(page_slug)
        sub_m = re.search(r'data-subid=["\']([^"\']+)["\']', full_open, re.I)
        safe_sub = sub_m.group(1) if sub_m else html_lib.escape(f"{page_slug}_{suffix}")

        if "source_tool=" not in raw_href:
            new_href = f"/r/{pk}?source_tool={safe_s}&amp;subid={safe_sub}&amp;cta_slot={html_lib.escape(slot)}"
            full_open = full_open.replace(f'href="{raw_href}"', f'href="{new_href}"', 1).replace(
                f"href='{raw_href}'", f'href="{new_href}"', 1
            )
        if "target=" not in full_open.lower():
            full_open = full_open[:-1] + ' target="_blank">'
        rel_m = re.search(r'rel=["\']([^"\']*)["\']', full_open, re.I)
        if not rel_m:
            full_open = full_open[:-1] + ' rel="noopener sponsored nofollow">'
        else:
            rel_tokens = [t.strip().lower() for t in rel_m.group(1).split() if t.strip()]
            for req_tok in ("noopener", "sponsored", "nofollow"):
                if req_tok not in rel_tokens:
                    rel_tokens.append(req_tok)
            norm_rel = " ".join(rel_tokens)
            if norm_rel != rel_m.group(1):
                full_open = re.sub(
                    r'rel=["\'][^"\']*["\']',
                    f'rel="{norm_rel}"',
                    full_open,
                    count=1,
                    flags=re.I,
                )
        if "data-partner=" not in full_open:
            full_open = full_open[:-1] + f' data-partner="{pk}">'
        if "data-tool=" not in full_open:
            full_open = full_open[:-1] + f' data-tool="{safe_s}">'
        if "data-subid=" not in full_open:
            full_open = full_open[:-1] + f' data-subid="{safe_sub}">'
        if "data-cta-slot=" not in full_open:
            full_open = full_open[:-1] + f' data-cta-slot="{html_lib.escape(slot)}">'
        p_mod = html_lib.escape(str(resolve_partnership_model_spec(pk)["partnership_model"]))
        if "data-partnership-model=" not in full_open:
            full_open = full_open[:-1] + f' data-partnership-model="{p_mod}">'
        else:
            full_open = re.sub(
                r'data-partnership-model=["\'][^"\']*["\']',
                f'data-partnership-model="{p_mod}"',
                full_open,
                flags=re.I,
            )
        return full_open

    updated = re.sub(
        r'(<a\s+[^>]*href=["\'](/r/([a-z0-9_]+)[^"\']*)["\'][^>]*>)',
        _stamp_attribution_on_r_anchor,
        updated,
        flags=re.S | re.I,
    )

    # Ensure every ProfitHelm page with outbound /r/ links has an above-the-fold .ftc-disclosure-banner with vertical-matched partner disclosure
    if prop in ("profithelm", "exchange1031") and re.search(r'href\s*=\s*["\']/r/', updated, flags=re.I):
        ctx_ftc_text = get_contextual_ftc_disclosure(prop, slug=page_slug)
        banner_inner = f"<strong>FTC Disclosure:</strong> {html_lib.escape(ctx_ftc_text)}"
        if 'class="ftc-disclosure-banner"' in updated:
            updated = re.sub(
                r'(<div\s+class=["\']ftc-disclosure-banner["\'][^>]*>)(.*?)(</div>)',
                rf"\g<1>{banner_inner}\g<3>",
                updated,
                count=1,
                flags=re.S | re.I,
            )
        elif (
            "ftc-disclosure-banner" not in updated
            and 'class="ftc-disclosure-card"' not in updated
            and "</section>" in updated
            and "<main" in updated
        ):
            banner_div = (
                f'\n      <div class="ftc-disclosure-banner" data-mechanic="compliant_intent_monetization" '
                f'style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 1.25rem; padding: 0.625rem 0.875rem; '
                f'background: var(--bg-subtle); border: 1px solid var(--border-hairline); border-radius: 6px; line-height: 1.4;">'
                f"{banner_inner}</div>"
            )
            hero_m = re.search(r'(<section\s+class=["\'][^"\']*hero-section[^"\']*["\'][^>]*>.*?</section>)', updated, re.S | re.I)
            if hero_m:
                updated = updated[: hero_m.end()] + banner_div + updated[hero_m.end() :]

    return updated


def audit_callout_destination_message_match(
    dist_dir: Optional[Any] = None,
    property_id: str = "profithelm",
) -> Dict[str, Any]:
    """
    Audits callout-to-destination brand and offer message-match across the affiliate
    registry and (optionally) rendered HTML pages in dist_dir.
    Verifies that every visible partner callout card title, description, and CTA button label
    matches its verified paying destination merchant and contains zero stale replaced brand names.
    Zero em-dashes. Zero en-dashes.
    """
    from pathlib import Path

    prop = (property_id or "profithelm").strip().lower()
    registry = PREXVO_AFFILIATES if prop == "prexvo" else (GAINHELM_AFFILIATES if prop == "gainhelm" else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES))

    mismatches: List[Dict[str, Any]] = []
    registry_checked = 0

    for pk, partner in registry.items():
        registry_checked += 1
        expected_tokens: Tuple[str, ...] = EXPECTED_PARTNER_BRAND_TOKENS.get(pk, (partner.name.lower(),))
        forbidden_tokens: Tuple[str, ...] = FORBIDDEN_REPLACED_BRAND_TOKENS.get(pk, ())
        combined_copy = f"{partner.name} {partner.cta_text}".lower()

        if not any(tok in combined_copy for tok in expected_tokens):
            mismatches.append({
                "source": "registry",
                "partner_key": pk,
                "reason": f"Registry copy '{partner.name} / {partner.cta_text}' missing expected destination brand {expected_tokens}",
            })
        for f_tok in forbidden_tokens:
            if f_tok in combined_copy or f_tok in partner.description.lower():
                mismatches.append({
                    "source": "registry",
                    "partner_key": pk,
                    "reason": f"Registry copy contains stale replaced brand '{f_tok}'",
                })

    pages_audited = 0
    callouts_audited = 0
    above_fold_verified_pages = 0

    if dist_dir is not None:
        d_path = Path(dist_dir)
        if d_path.is_dir():
            for html_file in sorted(d_path.rglob("*.html")):
                rel_p = str(html_file.relative_to(d_path))
                if rel_p.startswith("embed/") or rel_p in ("404.html",):
                    continue
                try:
                    html = html_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                pages_audited += 1

                # Check above-the-fold placement on calculator pages:
                # partner callout section should appear before faq-section/related-tools-section or immediately after calculator
                aff_pos = -1
                for sec_cls in ("affiliates-section", "affiliate-section", "partner-cta-section", "refinance-partner-section", "partners-section"):
                    idx = html.find(sec_cls)
                    if idx > 0 and (aff_pos < 0 or idx < aff_pos):
                        aff_pos = idx
                faq_pos = html.find('class="faq-section"')
                if faq_pos < 0:
                    faq_pos = html.find('class="related-tools-section"')
                if aff_pos > 0 and (faq_pos < 0 or aff_pos < faq_pos):
                    above_fold_verified_pages += 1

                for m in re.finditer(r'<a\s+[^>]*href="(/r/([a-z0-9_]+)[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
                    href = m.group(1)
                    pk = m.group(2).lower()
                    btn_text = re.sub(r"<[^>]+>", " ", m.group(3))
                    btn_text = re.sub(r"\s+", " ", btn_text).strip()
                    callouts_audited += 1

                    expected_tokens = EXPECTED_PARTNER_BRAND_TOKENS.get(pk, ())
                    forbidden_tokens = FORBIDDEN_REPLACED_BRAND_TOKENS.get(pk, ())

                    # Inspect surrounding 450 chars before link for card h3/h4 title
                    start_ctx = max(0, m.start() - 450)
                    ctx_window = re.sub(r"<[^>]+>", " ", html[start_ctx : m.end()])
                    ctx_window = re.sub(r"\s+", " ", ctx_window).strip().lower()

                    if expected_tokens and not any(tok in ctx_window for tok in expected_tokens):
                        mismatches.append({
                            "source": rel_p,
                            "partner_key": pk,
                            "href": href,
                            "button_text": btn_text,
                            "reason": f"Visible callout missing expected destination brand {expected_tokens}",
                        })
                    for f_tok in forbidden_tokens:
                        if f_tok in btn_text.lower():
                            mismatches.append({
                                "source": rel_p,
                                "partner_key": pk,
                                "href": href,
                                "button_text": btn_text,
                                "reason": f"Button label contains stale replaced brand '{f_tok}'",
                            })

    return {
        "status": "PASS" if len(mismatches) == 0 else "FAIL",
        "property_id": prop,
        "registry_partners_checked": registry_checked,
        "pages_audited": pages_audited,
        "total_pages": pages_audited,
        "callouts_audited": callouts_audited,
        "total_callouts_checked": callouts_audited,
        "above_fold_verified_pages": above_fold_verified_pages,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


COMPANY_BRAND_BY_PARTNER_KEY: Dict[str, str] = {
    "xendoo": "Xendoo",
    "gusto": "Gusto",
    "rippling": "Rippling",
    "mercury": "Mercury",
    "ramp": "Ramp",
    "coinledger": "CoinLedger",
    "koinly": "Koinly",
    "kalshi": "Kalshi",
    "efile_com": "E-file.com",
    "efile": "E-file.com",
    "eztaxreturn_com": "ezTaxReturn.com",
    "eztaxreturn": "ezTaxReturn.com",
    "freetaxusa": "FreeTaxUSA",
    "wallethub": "WalletHub",
    "lawdepot": "LawDepot",
    "deel": "Deel",
    "crest_capital": "Crest Capital",
    "bench": "Bench",
    "pilot": "Pilot",
    "brex": "Brex",
    "rho": "Rho",
    "taxslayer": "TaxSlayer",
    "turbotax": "TurboTax",
    "taxact": "TaxAct",
    "ipx1031": "IPX1031",
    "exeter1031": "Exeter 1031",
    "first_american": "First American 1031",
    "taxbit": "TaxBit",
    "moby": "Moby",
    "zacks": "Zacks",
    "interactive_brokers": "Interactive Brokers",
    "wealthfront": "Wealthfront",
    "guideline": "Guideline",
    "stripe_tax": "Stripe Tax",
    "flexport": "Flexport",
    "otr_solutions_factoring": "OTR Solutions",
    "freightos_marketplace": "Freightos",
    "national_funding": "National Funding",
    "stripe": "Stripe",
    "national_funding_med": "National Funding",
    "invoice_simple": "Invoice Simple",
    "suretybonds_direct": "SuretyBondsDirect.com",
    "splash_financial": "Splash Financial",
    "sofi": "SoFi",
    "sofi_refi": "SoFi",
    "earnest": "Earnest",
    "juno": "Juno",
    "credible": "Credible",
    "laurel_road": "Laurel Road",
    "lendkey": "LendKey",
    "edvestin": "EDvestinU",
    "vanta_security": "Vanta",
    "drata_compliance": "Drata",
    "sprinto_compliance": "Sprinto",
    "thoropass_audit": "Thoropass",
    "coalition_cyber_insurance": "Coalition",
    "cobalt_pentest": "Cobalt",
    "simply_business": "Simply Business",
    "next_insurance_b2b": "Next Insurance",
    "thimble_contractor": "Thimble",
    "jobber_field_service": "Jobber",
    "levelset_lien_filing": "Levelset",
}

VERTICAL_DIVERSIFIED_PARTNER_ROSTERS: Dict[str, List[str]] = {
    "1031_like_kind_exchange": ["lawdepot", "xendoo", "mercury", "ramp"],
    "section_179_equipment_capex": ["xendoo", "ramp", "mercury", "rippling"],
    "s_corp_payroll_reasonable_comp": ["gusto", "rippling", "xendoo", "mercury"],
    "workers_comp_labor_burden": ["rippling", "gusto", "xendoo", "mercury"],
    "prediction_market_event_contracts": ["kalshi", "coinledger", "koinly", "mercury"],
    "prediction_market_tax_1256": ["coinledger", "koinly", "kalshi", "efile_com"],
    "crypto_digital_asset_tax": ["coinledger", "koinly", "kalshi", "efile_com"],
    "rd_section_174_bookkeeping": ["xendoo", "ramp", "rippling", "mercury"],
    "tariff_customs_freight_trade": ["ramp", "mercury", "rippling", "xendoo"],
    "commercial_working_capital_factoring": ["xendoo", "ramp", "mercury", "wallethub"],
    "surety_bond_compliance": ["lawdepot", "xendoo", "mercury", "rippling"],
    "treasury_cash_runway": ["mercury", "ramp", "wallethub", "xendoo"],
    "retirement_401k_rollover": ["gusto", "rippling", "mercury", "xendoo"],
    "sales_tax_1099_nexus": ["xendoo", "efile_com", "rippling", "gusto"],
    "federal_state_tax_brackets": ["efile_com", "eztaxreturn_com", "freetaxusa", "xendoo"],
    "saas_unit_economics_spend": ["ramp", "mercury", "rippling", "xendoo"],
    "b2b_cyber_compliance": ["vanta_security", "drata_compliance", "sprinto_compliance", "thoropass_audit", "coalition_cyber_insurance", "cobalt_pentest", "rippling", "ramp", "mercury", "gusto"],
    "commercial_solar_energy": ["xendoo", "ramp", "mercury", "wallethub"],
    "construction_contractor_finance": ["lawdepot", "xendoo", "rippling", "mercury"],
    "medical_practice_capex": ["xendoo", "ramp", "mercury", "gusto"],
    "payment_processing_api_usage": ["ramp", "mercury", "wallethub", "xendoo"],
    "student_loan_refinancing": ["splash_financial", "credible", "lendkey"],
    "general_b2b_commercial_finance": ["xendoo", "ramp", "mercury", "wallethub"],
}


def classify_asset_archetype_and_intent(
    property_id: str,
    slug: str,
    query: str = "",
    page_archetype: str = "",
    html_content: str = "",
) -> Dict[str, Any]:
    """
    Deterministically classifies an asset's vertical family, page archetype,
    commercial intent, and Title IV YMYL restriction state.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "profithelm").strip().lower()
    s_norm = (slug or "tool").strip().strip("/").lower()
    q_norm = (query or "").strip().lower()
    comb = f"{s_norm} {q_norm}"

    restricted_ps = False
    if prop == "prexvo":
        is_concrete_slug = bool(s_norm and s_norm not in ("tool", "index"))
        restricted_ps = is_restricted_public_service_slug(s_norm, "" if is_concrete_slug else q_norm)

    if prop == "prexvo":
        vertical_family = "public_service_title_iv_ymyl" if restricted_ps else "student_loan_refinancing"
    elif prop == "gainhelm":
        vertical_family = "b2b_cyber_compliance"
    elif prop == "lienbond":
        if any(k in comb for k in ("surety", "miller-act", "performance-bond", "payment-bond", "license-bond", "contractor-bond")):
            vertical_family = "surety_bond_compliance"
        elif any(k in comb for k in ("workers-comp", "workers-compensation", "emr", "ncci", "class-code", "payroll-burden")):
            vertical_family = "workers_comp_labor_burden"
        else:
            vertical_family = "construction_contractor_finance"
    elif any(k in comb for k in ("1031", "like-kind", "like kind", "8824", "boot", "qi-fee", "ftb-3840", "3840", "exchange-property")):
        vertical_family = "1031_like_kind_exchange"
    elif any(k in comb for k in ("prediction-market-tax", "section-1256", "section 1256", "6781", "event-contract-tax")):
        vertical_family = "prediction_market_tax_1256"
    elif any(k in comb for k in ("prediction-market", "kalshi", "polymarket", "event-contract", "kelly-criterion", "binary-contract", "implied-probability", "vigorish", "arbitrage-hedging")):
        vertical_family = "prediction_market_event_contracts"
    elif any(k in comb for k in ("crypto", "8949", "1099-da", "harvesting", "digital-asset", "staking", "defi-tax")):
        vertical_family = "crypto_digital_asset_tax"
    elif any(k in comb for k in (
        "soc-2", "soc 2", "soc2", "iso-27001", "iso 27001", "hipaa", "cmmc",
        "sprs", "nist-800-171", "nist 800-171", "pentest", "penetration-test",
        "pci-dss", "pci dss", "gdpr-fine", "cybersecurity-audit",
    )):
        vertical_family = "b2b_cyber_compliance"
    elif any(k in comb for k in (
        "nem-3", "nem 3.0", "net-metering", "net metering", "demand-charge", "demand charge",
        "battery-storage", "battery storage", "peak-shaving", "srec", "trec",
        "renewable-energy-certificate", "solar-payback", "ev-fleet", "commercial-solar", "solar-itc",
    )):
        vertical_family = "commercial_solar_energy"
    elif any(k in comb for k in (
        "wrvu", "rvu", "physician-fee-schedule", "physician fee schedule", "gpci",
        "cpt-99490", "cpt 99490", "chronic-care-management", "cbct", "cone-beam",
        "medical-equipment", "dental-equipment", "credentialing-delay", "practice-reimbursement",
    )):
        vertical_family = "medical_practice_capex"
    elif any(k in comb for k in (
        "contractor-lien", "mechanics-lien", "lien-release", "preliminary-notice",
        "retainage", "progress-billing", "schedule-of-values", "davis-bacon",
        "prevailing-wage", "contractor-markup", "markup-vs-margin", "contractor-overhead",
        "prompt-payment",
    )):
        vertical_family = "construction_contractor_finance"
    elif any(k in comb for k in (
        "surety", "miller-act", "performance-bond", "payment-bond", "license-bond",
        "contractor-bond", "customs-bond", "fidelity-bond", "erisa-fidelity",
    )):
        vertical_family = "surety_bond_compliance"
    elif any(k in comb for k in ("workers-comp", "workers-compensation", "payroll-burden", "labor-burden", "emr-mod", "ncci", "class-code")):
        vertical_family = "workers_comp_labor_burden"
    elif any(k in comb for k in ("s-corp", "s corp", "1120-s", "reasonable-salary", "reasonable-compensation", "payroll", "gusto", "w-2-vs-1099")) or bool(re.search(r"\bfica\b", comb)):
        vertical_family = "s_corp_payroll_reasonable_comp"
    elif any(k in comb for k in ("174", "r-and-d", "r&d", "6765", "research-credit", "bookkeeping", "accounting")):
        vertical_family = "rd_section_174_bookkeeping"
    elif any(k in comb for k in ("179", "4562", "equipment", "depreciation", "macrs", "gvwr", "bonus-depreciation", "cost-segregation", "vehicle-deduction")):
        vertical_family = "section_179_equipment_capex"
    elif any(k in comb for k in ("factoring", "invoice-advance", "invoice-discount", "line-of-credit", "working-capital", "receivable", "dso")):
        vertical_family = "commercial_working_capital_factoring"
    elif any(k in comb for k in ("301", "tariff", "landed-cost", "customs", "htsus", "hts-code", "nmfc", "mpf", "hmf", "demurrage", "cbam", "freight", "duty")):
        vertical_family = "tariff_customs_freight_trade"
    elif any(k in comb for k in ("401k", "401-k", "solo-401k", "sep-ira", "rollover", "retirement", "erisa")):
        vertical_family = "retirement_401k_rollover"
    elif any(k in comb for k in (
        "payment-processing", "interchange", "merchant-fee", "card-processing",
        "stripe-fee", "payment-gateway", "api-usage", "api-pricing", "token-cost",
        "metered-billing", "usage-billing",
    )):
        vertical_family = "payment_processing_api_usage"
    elif any(k in comb for k in ("sales-tax", "economic-nexus", "1099-nec", "1099-misc", "vat", "avalara")):
        vertical_family = "sales_tax_1099_nexus"
    elif any(k in comb for k in ("treasury", "hysa", "tbill", "money-market", "3124", "yield-arbitrage", "sweep")):
        vertical_family = "treasury_cash_runway"
    elif any(k in comb for k in ("saas", "burn", "runway", "cac", "ltv", "arr", "nrr", "magic-number", "rule-of-40", "churn")):
        vertical_family = "saas_unit_economics_spend"
    elif any(k in comb for k in ("tax-bracket", "irs-2027", "ca-tax", "standard-deduction", "marginal-tax", "tcja", "capital-gains", "199a", "qsbs", "1202", "amt", "niit")):
        vertical_family = "federal_state_tax_brackets"
    else:
        vertical_family = "general_b2b_commercial_finance"

    arch_raw = (page_archetype or "").strip().lower()
    if arch_raw in ("interactive_calculator", "scenario_comparison_matrix", "statutory_spoke", "pillar_hub"):
        resolved_archetype = arch_raw
    elif "/" in s_norm or any(s_norm.startswith(pfx) for pfx in ("irs-2027-tax-brackets-", "section-1031-calculator-", "section-179-calculator-")):
        resolved_archetype = "statutory_spoke"
    elif any(k in comb for k in ("-vs-", " vs ", "comparison", "matrix", "brackets", "schedule")) and "calculator" not in s_norm:
        resolved_archetype = "scenario_comparison_matrix"
    elif any(k in s_norm for k in ("-hub", "directory", "index")) or s_norm in ("tools", "partners", "affiliates"):
        resolved_archetype = "pillar_hub"
    elif html_content and "<table" in html_content.lower() and "<form" not in html_content.lower() and 'class="calculator' not in html_content.lower():
        resolved_archetype = "scenario_comparison_matrix"
    else:
        resolved_archetype = "interactive_calculator"

    if restricted_ps:
        commercial_intent = "public_service_ymyl_restricted"
        intent_multiplier = 0.0
    elif prop == "prexvo":
        commercial_intent = "private_refinance_rate_shopping"
        intent_multiplier = 1.35
    elif resolved_archetype == "scenario_comparison_matrix" or any(k in comb for k in ("vs", "compare", "best", "alternative", "rates", "fees")):
        commercial_intent = "comparative_evaluation_matrix"
        intent_multiplier = 1.40
    elif resolved_archetype == "interactive_calculator" or any(k in comb for k in ("calculator", "estimator", "simulator", "model")):
        commercial_intent = "high_intent_transactional_calculator"
        intent_multiplier = 1.30
    else:
        commercial_intent = "statutory_compliance_modeling"
        intent_multiplier = 1.15

    return {
        "property_id": prop,
        "slug": s_norm,
        "vertical_family": vertical_family,
        "page_archetype": resolved_archetype,
        "commercial_intent": commercial_intent,
        "intent_multiplier": intent_multiplier,
        "restricted_public_service": restricted_ps,
        "commercial_offers_allowed": not restricted_ps,
    }


def _match_gsc_query_specialized_partner(
    property_id: str,
    vertical_family: str,
    query: str,
    roster_offers: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Inspects a live GSC search query for high-intent sub-topic signals that should
    dynamically promote a specific partner from the multi-company roster into the
    primary conversion slot.
    """
    q_low = (query or "").strip().lower()
    if not q_low or not roster_offers:
        return None
    available_keys = {str(o.get("partner_key") or "") for o in roster_offers}
    prop = (property_id or "profithelm").strip().lower()

    if prop == "prexvo":
        if any(k in q_low for k in ("medical", "resident", "doctor", "healthcare", "dental", "nurse")) and "laurel_road" in available_keys:
            return "laurel_road"
        if any(k in q_low for k in ("parent", "marketplace", "credible", "compare lenders")) and "credible" in available_keys:
            return "credible"
        if any(k in q_low for k in ("credit union", "community bank", "lendkey")) and "lendkey" in available_keys:
            return "lendkey"
        return None

    if prop == "lienbond":
        if any(k in q_low for k in ("surety", "miller act", "performance bond", "payment bond", "license bond")) and "suretybonds_direct" in available_keys:
            return "suretybonds_direct"
        if any(k in q_low for k in ("lien", "preliminary notice", "waiver", "levelset")) and "levelset_lien_filing" in available_keys:
            return "levelset_lien_filing"
        if any(k in q_low for k in ("jobber", "dispatch", "field service", "estimating")) and "jobber_field_service" in available_keys:
            return "jobber_field_service"
        if any(k in q_low for k in ("thimble", "short term", "certificate of insurance", "coi")) and "thimble_contractor" in available_keys:
            return "thimble_contractor"
        if any(k in q_low for k in ("workers comp", "emr", "ncci", "simply business")) and "simply_business" in available_keys:
            return "simply_business"
        return None

    if prop == "gainhelm":
        if any(k in q_low for k in ("pentest", "penetration test", "cobalt", "ptaaS", "owasp", "red team", "asv")) and "cobalt_pentest" in available_keys:
            return "cobalt_pentest"
        if any(k in q_low for k in ("cyber insurance", "coalition", "breach liability", "ransomware insurance", "e&o")) and "coalition_cyber_insurance" in available_keys:
            return "coalition_cyber_insurance"
        if any(k in q_low for k in ("thoropass", "hitrust", "pci dss", "qsa", "bundled audit", "mycsf")) and "thoropass_audit" in available_keys:
            return "thoropass_audit"
        if any(k in q_low for k in ("drata", "cmmc", "sprs", "nist 800-171", "fedramp", "3pao", "dfars")) and "drata_compliance" in available_keys:
            return "drata_compliance"
        if any(k in q_low for k in ("sprinto", "iso 27001", "iso 27006", "gdpr", "annex a")) and "sprinto_compliance" in available_keys:
            return "sprinto_compliance"
        if any(k in q_low for k in ("vanta", "soc 2", "soc2", "trust center", "continuous monitoring")) and "vanta_security" in available_keys:
            return "vanta_security"
        return None

    # ProfitHelm query-intent specialized promotion rules (strictly approved live partners)
    if any(k in q_low for k in ("koinly", "defi", "wallet sync", "uk", "canada", "australia")) and "koinly" in available_keys:
        return "koinly"
    if any(k in q_low for k in ("coinledger", "8949", "1099-da", "crypto tax")) and "coinledger" in available_keys:
        return "coinledger"
    if any(k in q_low for k in ("kalshi", "cftc", "event contract", "election odds", "fed rate odds")) and "kalshi" in available_keys:
        return "kalshi"
    if any(k in q_low for k in ("gusto", "s corp salary", "s-corp payroll", "reasonable salary payroll", "solo s corp", "w2 officer")) and "gusto" in available_keys:
        return "gusto"
    if any(k in q_low for k in ("rippling", "multi-state payroll", "global payroll", "eor", "hris", "workers comp audit")) and "rippling" in available_keys:
        return "rippling"
    if any(k in q_low for k in ("deed", "contract", "agreement", "operating agreement", "lease agreement", "promissory note", "lawdepot", "1031")) and "lawdepot" in available_keys:
        return "lawdepot"
    if any(k in q_low for k in ("ramp", "corporate card", "expense management", "saas spend", "ap automation", "merchant fee")) and "ramp" in available_keys:
        return "ramp"
    if any(k in q_low for k in ("wallethub", "credit score", "business credit", "working capital")) and "wallethub" in available_keys:
        return "wallethub"
    if any(k in q_low for k in ("freetaxusa", "free federal", "schedule c free")) and "freetaxusa" in available_keys:
        return "freetaxusa"
    if any(k in q_low for k in ("eztaxreturn", "fast refund")) and "eztaxreturn_com" in available_keys:
        return "eztaxreturn_com"
    if any(k in q_low for k in ("efile", "e-file", "tax bracket", "standard deduction")) and "efile_com" in available_keys:
        return "efile_com"
    if any(k in q_low for k in ("xendoo", "cpa", "bookkeeping", "form 4562", "form 1120-s", "form 6765", "section 179", "section 174")) and "xendoo" in available_keys:
        return "xendoo"
    if any(k in q_low for k in ("mercury", "treasury", "runway", "venture debt", "business checking", "sweep")) and "mercury" in available_keys:
        return "mercury"
    return None


def select_conversion_slot_plan(
    property_id: str,
    slug: str,
    roster_offers: List[Dict[str, Any]],
    page_archetype: str = "interactive_calculator",
    commercial_intent: str = "high_intent_transactional_calculator",
    vertical_family: str = "general_b2b_commercial_finance",
    gsc_metrics: Optional[Dict[str, Any]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministically selects which partner link and conversion slot
    (calculator_result_inline, comparison_table_cta, inline_callout_card, or partner_matrix_card)
    to deploy and prioritize based on page archetype, commercial intent, expected yield,
    and live GSC search performance signals.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "profithelm").strip().lower()
    s_norm = (slug or "tool").strip().strip("/").lower()
    slug_id = s_norm.replace("/", "-")

    if not roster_offers:
        return {
            "primary_slot": "ymyl_public_service_guardrail",
            "active_slots": ["ymyl_public_service_guardrail"],
            "slot_bindings": {},
            "slot_weights": {},
            "workbench_engagement": {
                "calculator_interactions": 0,
                "workbench_interactions": 0,
                "scenario_pins": 0,
                "blueprint_saves": 0,
            },
            "gsc_opportunity_tier": "RESTRICTED_PUBLIC_SERVICE",
            "gsc_repositioned": False,
            "reposition_reason": "Commercial offers suppressed under Title IV public-service guardrail.",
            "promoted_partner_key": "",
            "initial_partner_key": "",
        }

    gsc = dict(gsc_metrics) if isinstance(gsc_metrics, dict) else {}
    impressions = int(float(gsc.get("impressions", gsc.get("baseline_impressions", 0)) or 0))
    clicks = int(float(gsc.get("clicks", gsc.get("baseline_clicks", 0)) or 0))
    ctr = float(gsc.get("ctr", gsc.get("baseline_ctr", 0.0)) or 0.0)
    if ctr <= 0.0 and impressions > 0 and clicks > 0:
        ctr = clicks / float(impressions)
    position = float(gsc.get("position", gsc.get("baseline_position", 0.0)) or 0.0)
    gsc_query = str(gsc.get("query") or gsc.get("top_query") or "").strip()

    dev_splits = gsc.get("device_splits") if isinstance(gsc.get("device_splits"), dict) else {}
    mob_dict = dev_splits.get("MOBILE") if isinstance(dev_splits.get("MOBILE"), dict) else {}
    desk_dict = dev_splits.get("DESKTOP") if isinstance(dev_splits.get("DESKTOP"), dict) else {}
    mobile_impressions = int(float(gsc.get("mobile_impressions", mob_dict.get("impressions", 0)) or 0))
    desktop_impressions = int(float(gsc.get("desktop_impressions", desk_dict.get("impressions", 0)) or 0))
    mobile_ctr = float(gsc.get("mobile_ctr", mob_dict.get("ctr", 0.0)) or 0.0)
    desktop_ctr = float(gsc.get("desktop_ctr", desk_dict.get("ctr", 0.0)) or 0.0)
    mobile_ctr_gap = round(float(gsc.get("mobile_ctr_gap", desktop_ctr - mobile_ctr) or 0.0), 4)
    device_focus = str(
        gsc.get("device_focus")
        or (
            "MOBILE_CTR_DEFICIT"
            if (mobile_impressions >= 5 and mobile_ctr_gap >= 0.01)
            else ("MOBILE_DOMINANT" if mobile_impressions > desktop_impressions and mobile_impressions >= 5 else "BALANCED")
        )
    )
    search_appearances = [str(sa).upper() for sa in (gsc.get("search_appearances") or []) if sa]

    eng = dict(engagement_metrics) if isinstance(engagement_metrics, dict) else {}
    by_slug_eng = (
        eng.get("by_slug")
        if isinstance(eng.get("by_slug"), dict)
        else (eng.get("by_page") if isinstance(eng.get("by_page"), dict) else {})
    )
    slug_eng = (
        by_slug_eng.get(slug_id)
        or by_slug_eng.get(s_norm)
        or (
            eng
            if any(
                k in eng
                for k in (
                    "calculator_interactions",
                    "workbench_interactions",
                    "scenario_pins",
                    "blueprint_saves",
                    "cta_slots",
                )
            )
            else {}
        )
    )
    if not isinstance(slug_eng, dict):
        slug_eng = {}
    calc_interactions = int(slug_eng.get("calculator_interactions", 0) or 0)
    wb_interactions = int(slug_eng.get("workbench_interactions", 0) or 0)
    scenario_pins = int(slug_eng.get("scenario_pins", 0) or 0)
    blueprint_saves = int(slug_eng.get("blueprint_saves", 0) or 0)
    slug_cta_slots = slug_eng.get("cta_slots") if isinstance(slug_eng.get("cta_slots"), dict) else {}
    global_cta_slots = eng.get("by_cta_slot") if isinstance(eng.get("by_cta_slot"), dict) else {}
    top_conv_pk = str(slug_eng.get("top_converting_partner") or "").strip().lower()

    ordered_offers = [dict(o) for o in roster_offers]
    initial_primary_key = str(ordered_offers[0].get("partner_key") or "")

    # Check if live GSC query or empirical yield triggers a partner promotion/swap
    query_matched_pk = _match_gsc_query_specialized_partner(
        property_id=prop,
        vertical_family=vertical_family,
        query=gsc_query,
        roster_offers=ordered_offers,
    )

    highest_yield_offer = max(
        ordered_offers,
        key=lambda x: (
            float(x.get("estimated_revenue_yield_usd", 0.0) or 0.0),
            float(x.get("empirical_erpm_usd", 0.0) or 0.0),
            float(x.get("yield_score", 0.0) or 0.0),
            float(x.get("expected_epc_usd", 0.0) or 0.0),
        ),
    )
    highest_yield_pk = str(highest_yield_offer.get("partner_key") or "")

    gsc_repositioned = False
    gsc_opportunity_tier = "BASELINE_MULTI_SLOT"
    reposition_reason = "Deterministic archetype and expected-yield baseline slot selection."

    # 1. Query-intent specialized partner swap when GSC query signals a sharper offer match
    if query_matched_pk and query_matched_pk != initial_primary_key:
        ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == query_matched_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "QUERY_INTENT_PARTNER_SWAP"
        reposition_reason = (
            f"Live GSC query '{gsc_query}' matched specialized offer '{query_matched_pk}', "
            f"promoting it ahead of '{initial_primary_key}'."
        )
    # 2. High-impression CTR shortfall or striking-distance yield promotion
    elif impressions >= 50 and ctr < 0.03:
        if highest_yield_pk and highest_yield_pk != initial_primary_key:
            ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == highest_yield_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "HIGH_IMPRESSION_CTR_SHORTFALL"
        reposition_reason = (
            f"High search impressions ({impressions}) with low CTR ({ctr:.2%}) triggered above-the-fold "
            f"calculator_result_inline and comparison_table_cta slot promotion for '{ordered_offers[0]['partner_key']}'."
        )
    elif 4.0 <= position <= 20.0 and impressions >= 10:
        if highest_yield_pk and highest_yield_pk != initial_primary_key and float(highest_yield_offer.get("yield_score", 0.0)) > float(ordered_offers[0].get("yield_score", 0.0)):
            ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == highest_yield_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "STRIKING_DISTANCE_PROMOTION"
        reposition_reason = (
            f"Striking-distance GSC rank (position {position:.1f}, {impressions} impressions) activated "
            f"multi-slot inline result hook plus comparison table partner row for '{ordered_offers[0]['partner_key']}'."
        )
    elif mobile_impressions >= 5 and (mobile_ctr_gap >= 0.01 or device_focus in ("MOBILE_CTR_DEFICIT", "MOBILE_DOMINANT")):
        if highest_yield_pk and highest_yield_pk != initial_primary_key and float(highest_yield_offer.get("yield_score", 0.0)) > float(ordered_offers[0].get("yield_score", 0.0)):
            ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == highest_yield_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "MOBILE_CTR_DEFICIT_PROMOTION"
        reposition_reason = (
            f"Mobile GSC split ({mobile_impressions} mobile impr, mobile CTR {mobile_ctr:.2%} vs desktop {desktop_ctr:.2%}) "
            f"promoted above-the-fold touch calculator_result_inline CTA for '{ordered_offers[0]['partner_key']}'."
        )
    elif any(sa in ("REVIEW_SNIPPET", "PRODUCT_SNIPPETS") for sa in search_appearances) and impressions >= 3:
        gsc_repositioned = True
        gsc_opportunity_tier = "RICH_APPEARANCE_MATRIX_PROMOTION"
        reposition_reason = (
            f"Rich-result searchAppearance ({','.join(search_appearances)}) promoted structured "
            f"comparison_table_cta and inline conversion slots for '{ordered_offers[0]['partner_key']}'."
        )
    elif highest_yield_pk and highest_yield_pk != initial_primary_key and (
        float(highest_yield_offer.get("estimated_revenue_yield_usd", 0.0) or 0.0) > 0.0
        or float(highest_yield_offer.get("empirical_erpm_usd", 0.0) or 0.0) > 0.0
    ):
        ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == highest_yield_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "EMPIRICAL_YIELD_SWAP"
        reposition_reason = (
            f"Empirical outbound engagement promoted higher-yielding partner '{highest_yield_pk}' "
            f"over static default '{initial_primary_key}'."
        )
    elif top_conv_pk and top_conv_pk != initial_primary_key and any(o.get("partner_key") == top_conv_pk for o in ordered_offers):
        ordered_offers.sort(key=lambda x: (0 if x.get("partner_key") == top_conv_pk else 1))
        gsc_repositioned = True
        gsc_opportunity_tier = "EMPIRICAL_YIELD_SWAP"
        reposition_reason = (
            f"Closed-loop slug engagement promoted top-converting partner '{top_conv_pk}' "
            f"ahead of '{initial_primary_key}'."
        )

    # Re-stamp tier_role after any GSC promotion/reordering
    for idx, off in enumerate(ordered_offers):
        if idx == 0:
            off["tier_role"] = "primary"
        elif idx < len(ordered_offers) - 1:
            off["tier_role"] = "secondary"
        else:
            off["tier_role"] = "fallback"

    lead_offer = ordered_offers[0]
    secondary_offer = ordered_offers[1] if len(ordered_offers) > 1 else lead_offer

    # Deterministic archetype -> conversion slot selection
    if page_archetype == "scenario_comparison_matrix":
        primary_slot = "comparison_table_cta"
        active_slots = [
            "comparison_table_cta",
            "calculator_result_inline",
            "partner_matrix_card",
            "inline_callout_card",
        ]
    elif page_archetype == "statutory_spoke":
        primary_slot = "calculator_result_inline"
        active_slots = [
            "calculator_result_inline",
            "comparison_table_cta",
            "partner_matrix_card",
            "inline_callout_card",
        ]
    elif page_archetype == "pillar_hub":
        primary_slot = "partner_matrix_card"
        active_slots = [
            "partner_matrix_card",
            "comparison_table_cta",
            "inline_callout_card",
        ]
    else:
        # interactive_calculator
        primary_slot = "calculator_result_inline"
        active_slots = [
            "calculator_result_inline",
            "comparison_table_cta",
            "partner_matrix_card",
            "inline_callout_card",
        ]

    # Closed-loop workbench and slot engagement weighting
    slot_weights: Dict[str, float] = {
        "calculator_result_inline": 1.0,
        "comparison_table_cta": 0.9,
        "partner_matrix_card": 0.8,
        "inline_callout_card": 0.7,
    }
    if page_archetype == "scenario_comparison_matrix":
        slot_weights["comparison_table_cta"] += 0.25
    elif page_archetype == "pillar_hub":
        slot_weights["partner_matrix_card"] += 0.35

    if scenario_pins > 0:
        slot_weights["comparison_table_cta"] += min(0.65, scenario_pins * 0.22)
    if blueprint_saves > 0 or calc_interactions > 0:
        slot_weights["calculator_result_inline"] += min(0.60, blueprint_saves * 0.20 + calc_interactions * 0.08)

    for slot_k in list(slot_weights.keys()):
        s_slot_data = slug_cta_slots.get(slot_k) if isinstance(slug_cta_slots.get(slot_k), dict) else {}
        g_slot_data = global_cta_slots.get(slot_k) if isinstance(global_cta_slots.get(slot_k), dict) else {}
        s_clicks = int(s_slot_data.get("outbound_clicks", 0) or 0)
        s_intents = int(s_slot_data.get("intent_interactions", 0) or 0)
        g_clicks = int(g_slot_data.get("outbound_clicks", 0) or 0)
        slot_weights[slot_k] = round(
            slot_weights[slot_k] + min(0.50, s_clicks * 0.14 + s_intents * 0.06 + min(0.12, g_clicks * 0.01)),
            4,
        )

    if page_archetype != "pillar_hub":
        comp_clicks = int((slug_cta_slots.get("comparison_table_cta") or {}).get("outbound_clicks", 0) or 0)
        inline_clicks = int((slug_cta_slots.get("calculator_result_inline") or {}).get("outbound_clicks", 0) or 0)
        if (scenario_pins >= 1 or comp_clicks > inline_clicks) and slot_weights["comparison_table_cta"] > slot_weights[primary_slot]:
            primary_slot = "comparison_table_cta"
            active_slots = sorted(active_slots, key=lambda s_name: -slot_weights.get(s_name, 0.0))
            if not gsc_repositioned:
                gsc_repositioned = True
                gsc_opportunity_tier = "WORKBENCH_ENGAGEMENT_SLOT_PROMOTION"
                reposition_reason = (
                    f"Closed-loop workbench scenario comparator engagement (pins={scenario_pins}, "
                    f"table_clicks={comp_clicks}) promoted 'comparison_table_cta' (weight {slot_weights['comparison_table_cta']:.2f}) "
                    f"for '{lead_offer.get('partner_key')}'."
                )
        elif (blueprint_saves >= 1 or wb_interactions >= 1) and not gsc_repositioned:
            gsc_repositioned = True
            gsc_opportunity_tier = "WORKBENCH_ENGAGEMENT_SLOT_PROMOTION"
            reposition_reason = (
                f"Closed-loop workbench engagement (workbench={wb_interactions}, blueprint_saves={blueprint_saves}) "
                f"reinforced '{primary_slot}' (weight {slot_weights.get(primary_slot, 1.0):.2f}) for '{lead_offer.get('partner_key')}'."
            )

    def _bind_offer_to_slot(offer_dict: Dict[str, Any], slot_name: str, sub_suffix: str) -> Dict[str, Any]:
        pk = str(offer_dict.get("partner_key") or "")
        sub_val = f"{slug_id}_{sub_suffix}"
        attr_href = f"/r/{pk}?source_tool={slug_id}&subid={sub_val}&cta_slot={slot_name}"
        return {
            **offer_dict,
            "cta_slot": slot_name,
            "subid": sub_val,
            "slot_weight": slot_weights.get(slot_name, 0.8),
            "attributed_href": attr_href,
        }

    # Diversify slot assignments so comparison_table_cta can surface either lead_offer or top secondary_offer when appropriate
    table_offer_source = (
        lead_offer
        if (
            primary_slot == "comparison_table_cta"
            or gsc_opportunity_tier
            in (
                "QUERY_INTENT_PARTNER_SWAP",
                "HIGH_IMPRESSION_CTR_SHORTFALL",
                "STRIKING_DISTANCE_PROMOTION",
                "MOBILE_CTR_DEFICIT_PROMOTION",
                "RICH_APPEARANCE_MATRIX_PROMOTION",
                "EMPIRICAL_YIELD_SWAP",
                "WORKBENCH_ENGAGEMENT_SLOT_PROMOTION",
            )
        )
        else secondary_offer
    )

    slot_bindings: Dict[str, Any] = {
        "calculator_result_inline": _bind_offer_to_slot(lead_offer, "calculator_result_inline", "inline"),
        "comparison_table_cta": _bind_offer_to_slot(table_offer_source, "comparison_table_cta", "table"),
        "inline_callout_card": _bind_offer_to_slot(lead_offer, "inline_callout_card", "callout"),
        "partner_matrix_cards": [
            _bind_offer_to_slot(
                off,
                "calculator_primary_cta" if idx == 1 else "partner_matrix_card",
                f"card_{idx}",
            )
            for idx, off in enumerate(ordered_offers, start=1)
        ],
    }

    return {
        "primary_slot": primary_slot,
        "active_slots": active_slots,
        "slot_bindings": slot_bindings,
        "slot_weights": slot_weights,
        "workbench_engagement": {
            "calculator_interactions": calc_interactions,
            "workbench_interactions": wb_interactions,
            "scenario_pins": scenario_pins,
            "blueprint_saves": blueprint_saves,
        },
        "ordered_offers": ordered_offers,
        "gsc_opportunity_tier": gsc_opportunity_tier,
        "gsc_repositioned": gsc_repositioned,
        "reposition_reason": reposition_reason,
        "promoted_partner_key": str(lead_offer.get("partner_key") or ""),
        "initial_partner_key": initial_primary_key,
        "gsc_impressions": impressions,
        "gsc_clicks": clicks,
        "gsc_ctr": round(ctr, 4),
        "gsc_position": round(position, 2),
        "gsc_query": gsc_query,
        "gsc_mobile_impressions": mobile_impressions,
        "gsc_desktop_impressions": desktop_impressions,
        "gsc_mobile_ctr": round(mobile_ctr, 4),
        "gsc_desktop_ctr": round(desktop_ctr, 4),
        "gsc_mobile_ctr_gap": mobile_ctr_gap,
        "gsc_device_focus": device_focus,
        "gsc_search_appearances": search_appearances,
    }


def resolve_contextual_partner_offer_copy(
    partner_key: str,
    p_obj: AffiliatePartner,
    slug: str = "",
    vertical_family: str = "",
    property_id: str = "profithelm",
) -> Dict[str, str]:
    """
    Adapts partner badge, name, description, and CTA button text to the exact page intent
    and jurisdiction so non-Section-179 pages (such as state tax brackets, 1099-NEC, S-Corp,
    R&D Section 174, CAMT, surety bonds, or student loan tax-bomb/RAP pages) never display
    mismatched Section 179 copy.
    Zero em-dashes. Zero en-dashes.
    """
    pk = (partner_key or "").strip().lower()
    s_low = (slug or "").strip().lower().replace("_", "-")
    v_fam = (vertical_family or "").strip().lower()
    prop = (property_id or "profithelm").strip().lower()

    badge = p_obj.badge
    name = p_obj.name
    description = p_obj.description
    cta_text = p_obj.cta_text

    if pk == "xendoo":
        is_sec179 = (
            any(tok in s_low for tok in ("section-179", "179", "depreciation", "macrs", "equipment", "vehicle", "fleet"))
            or v_fam == "section_179_equipment_capex"
        )
        if is_sec179:
            badge = "Section 179 & Equipment Capex CPA"
            name = "Xendoo Section 179 & Business Tax CPA"
            description = (
                "Maximize IRC Section 179 expensing, Section 168(k) bonus depreciation, and Form 4562 "
                "fixed-asset schedules with dedicated monthly CPA bookkeeping and tax filing."
            )
            cta_text = "Optimize Section 179 Deductions with Xendoo CPA"
        else:
            state_label = ""
            try:
                from pseofactory.competitor import US_51_JURISDICTIONS, _SLUG_STATE_TOKEN_MAP

                s_padded = f"-{s_low.replace('/', '-')}-"
                for token, st_code in _SLUG_STATE_TOKEN_MAP:
                    if f"-{token}-" in s_padded:
                        for c_code, c_label in US_51_JURISDICTIONS:
                            if c_code == st_code:
                                state_label = c_label.split(" (")[0].strip()
                                break
                        break
            except Exception:
                state_label = ""

            if any(tok in s_low for tok in ("1099", "s-corp", "self-employment", "qbi", "199a", "estimated-tax", "quarterly", "pass-through")):
                badge = "1099 & S-Corp Tax Reduction CPA"
                name = "Xendoo S-Corp & 1099 CPA Tax Advisory"
                description = (
                    "Cut self-employment and pass-through taxes with S-Corp reasonable salary optimization, "
                    "IRC Section 199A QBI deduction tracking, and quarterly CPA filings."
                )
                cta_text = "Cut Your 1099 & S-Corp Taxes with Xendoo CPA"
            elif any(tok in s_low for tok in ("174", "r-and-d", "r-d-", "camt", "280g", "amt", "corporate", "saas", "runway", "qsbs", "1202")):
                badge = "Corporate & R&D Tax Compliance CPA"
                name = "Xendoo Corporate & R&D Tax CPA"
                description = (
                    "Automate IRC Section 174 R&D capitalization schedules, Form 6765 credit claims, "
                    "and corporate tax provision workpapers with a dedicated CPA team."
                )
                cta_text = "Review Your Corporate Tax Shield with Xendoo CPA"
            elif "tax-bracket" in s_low or "tax-rate" in s_low or v_fam == "federal_state_tax_brackets":
                loc = f"{state_label} & Federal" if state_label else "2027 Federal & State"
                short_loc = state_label if state_label else "Federal & State"
                badge = f"{loc} CPA Tax Shield"
                name = f"Xendoo {loc} CPA Tax Advisory"
                description = (
                    f"Lower your 2026-2027 {short_loc} marginal tax bill with dedicated CPA tax planning, "
                    "S-Corp and Notice 2020-75 PTET SALT shield elections, and monthly catch-up bookkeeping."
                )
                cta_text = f"Lower Your 2027 {short_loc} Tax Bill with Xendoo CPA"
            else:
                badge = "Commercial Financials & Business Tax CPA"
                name = "Xendoo Business Tax & CPA Bookkeeping"
                description = (
                    "Dedicated online bookkeeping, CPA-reviewed financial statements, and proactive "
                    "federal and state business tax reduction for growing businesses."
                )
                cta_text = "Optimize Business Taxes & Books with Xendoo CPA"
    elif pk == "efile_com" and ("tax-bracket" in s_low or "tax-rate" in s_low or v_fam == "federal_state_tax_brackets"):
        state_label = ""
        try:
            from pseofactory.competitor import US_51_JURISDICTIONS, _SLUG_STATE_TOKEN_MAP

            s_padded = f"-{s_low.replace('/', '-')}-"
            for token, st_code in _SLUG_STATE_TOKEN_MAP:
                if f"-{token}-" in s_padded:
                    for c_code, c_label in US_51_JURISDICTIONS:
                        if c_code == st_code:
                            state_label = c_label.split(" (")[0].strip()
                            break
                    break
        except Exception:
            state_label = ""
        if state_label:
            badge = f"{state_label} & Federal IRS E-File"
            name = f"E-file.com {state_label} & Federal Tax Return"
            description = (
                f"Authorized IRS e-file provider for 2026-2027 {state_label} and Form 1040 individual returns "
                "with automatic deduction checks and fast direct-deposit refunds."
            )
            cta_text = f"E-File Your {state_label} & Federal Return on E-file.com"
    elif pk == "lawdepot" and (any(tok in s_low for tok in ("1031", "like-kind", "8824", "exchange")) or v_fam == "1031_like_kind_exchange"):
        badge = "Real Estate Deed & Holding LLC Templates"
        name = "LawDepot Real Estate & LLC Legal Templates"
        description = (
            "Draft state-specific LLC operating agreements, commercial lease contracts, and real estate "
            "transfer deeds with LawDepot customizable legal templates."
        )
        cta_text = "Draft Real Estate & LLC Agreements on LawDepot"
    elif prop == "gainhelm":
        fw_key = classify_gainhelm_framework(slug=s_low, vertical=v_fam)
        fw_partner_map = _GAINHELM_PARTNER_CONTEXTUAL_COPY.get(fw_key)
        if fw_partner_map is None and fw_key not in ("soc2", "cmmc"):
            fw_partner_map = _GAINHELM_PARTNER_CONTEXTUAL_COPY.get("non_audit_generic")
        if fw_partner_map and pk in fw_partner_map:
            badge, name, description, cta_text = fw_partner_map[pk]
    elif prop == "prexvo" and pk == "splash_financial":
        if "tax-bomb" in s_low or "insolvency" in s_low:
            badge = "Skip the 2026 Forgiveness Tax Bomb (2-Min Soft Check)"
            name = "Splash Financial Multi-Lender Refinance (0 Credit Impact)"
            cta_text = "Check Lower Fixed Refi Rates with Splash Financial"
        else:
            badge = "Beat Federal IDR Interest (2-Min Soft Credit Check)"
            name = "Splash Financial Multi-Lender Refinance (0 Credit Impact)"
            cta_text = "Compare Lower Fixed Refi Rates with Splash Financial"

    return {
        "badge": badge,
        "name": name,
        "description": description,
        "cta_text": cta_text,
    }


def _build_roster_offer_entry(
    pk: str,
    p_obj: AffiliatePartner,
    idx: int,
    total_count: int,
    prop: str,
    s_norm: str,
    slug_id: str,
    vertical_family: str,
    commercial_intent: str,
    intent_multiplier: float,
    resolved_archetype: str,
    query: str,
    ftc_disc: str,
    r_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a single enriched partner offer dictionary for roster binding and slot assignment."""
    meta = r_meta or {}
    model_spec = resolve_partnership_model_spec(pk, p_obj)
    p_model = str(model_spec.get("partnership_model") or p_obj.partnership_model or "CPA_BOUNTY")
    model_fit_mult = score_partnership_model_intent_fit(
        partnership_model=p_model,
        vertical_family=vertical_family,
        commercial_intent=commercial_intent,
        query=query,
        page_archetype=resolved_archetype,
    )
    is_non_hr_rippling = pk == "rippling" and vertical_family in (
        "federal_state_tax_brackets",
        "section_179_equipment_capex",
        "1031_like_kind_exchange",
        "rd_section_174_bookkeeping",
    )
    if is_non_hr_rippling:
        model_fit_mult = round(model_fit_mult * 0.45, 4)
    emp_fit_scale = 0.0 if is_non_hr_rippling else 1.0
    bounty_mid = float(
        meta.get("bounty_midpoint_usd")
        or model_spec.get("ltv_bounty_equivalent_usd")
        or get_partner_bounty_midpoint(pk)
    )
    est_conv_rate = float(model_spec.get("click_to_conversion_rate") or (0.035 if prop != "prexvo" else 0.025))
    expected_epc = round(bounty_mid * est_conv_rate * intent_multiplier * model_fit_mult, 2)
    base_yield = float(meta.get("yield_score") or round(bounty_mid * 0.5 + (5.0 if idx == 0 else 0.0), 2))
    company_brand = COMPANY_BRAND_BY_PARTNER_KEY.get(pk, p_obj.name.split()[0])
    tier_role = "primary" if idx == 0 else ("secondary" if idx < total_count - 1 else "fallback")
    slot_default = "calculator_primary_cta" if idx == 0 else "partner_matrix_card"
    sub_default = f"{slug_id}_card_{idx + 1}"
    ctx_copy = resolve_contextual_partner_offer_copy(
        partner_key=pk,
        p_obj=p_obj,
        slug=s_norm,
        vertical_family=vertical_family,
        property_id=prop,
    )
    if is_partner_live_in_vault(prop, pk):
        offer_status = "live"
    else:
        raw_st = str(meta.get("status") or p_obj.status or "pending").strip().lower()
        offer_status = "pending" if raw_st == "live" else raw_st
    return {
        "partner_key": pk,
        "name": ctx_copy["name"],
        "partner_name": ctx_copy["name"],
        "company_brand": company_brand,
        "tier_role": tier_role,
        "status": offer_status,
        "partnership_model": p_model,
        "partnership_model_spec": model_spec,
        "intent_fit_multiplier": model_fit_mult,
        "commission_est": p_obj.commission_est,
        "bounty_est": p_obj.bounty_est,
        "bounty_midpoint_usd": round(bounty_mid, 2),
        "expected_epc_usd": expected_epc,
        "yield_score": round(base_yield * intent_multiplier * model_fit_mult, 2),
        "empirical_erpm_usd": round(float(meta.get("empirical_erpm_usd", 0.0) or 0.0) * emp_fit_scale, 2),
        "empirical_cta_ctr": float(meta.get("cta_ctr", 0.0) or 0.0),
        "outbound_clicks": int(meta.get("outbound_clicks", 0) or 0),
        "estimated_revenue_yield_usd": round(float(meta.get("estimated_revenue_yield_usd", 0.0) or 0.0) * emp_fit_scale, 2),
        "badge": ctx_copy["badge"],
        "description": ctx_copy["description"],
        "cta_text": ctx_copy["cta_text"],
        "default_url": p_obj.default_url,
        "redirect_path": f"/r/{pk}",
        "attributed_href": f"/r/{pk}?source_tool={slug_id}&subid={sub_default}&cta_slot={slot_default}",
        "rel_attributes": "noopener sponsored nofollow",
        "disclosure": ftc_disc,
    }


def _property_partner_registry(prop: str) -> Dict[str, AffiliatePartner]:
    if prop == "prexvo":
        return PREXVO_AFFILIATES
    if prop == "gainhelm":
        return GAINHELM_AFFILIATES
    if prop == "lienbond":
        return LIENBOND_AFFILIATES
    return PROFITHELM_AFFILIATES


def _extract_existing_gsc_promoted_placement(html_content: str) -> Tuple[bool, str, str]:
    """Reads existing data-gsc-repositioned, partner key, and data-gsc-tier from .calc-inline-cta or partner <section>."""
    inline_m = re.search(
        r'<div\b[^>]*\bclass=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>',
        html_content,
        flags=re.I,
    )
    sec_m = re.search(
        r'<section\b[^>]*\bclass=["\'][^"\']*(?:refinance-partner-section|partners-section|affiliates?-section)[^"\']*["\'][^>]*>',
        html_content,
        flags=re.I,
    )
    inline_tag = inline_m.group(0) if inline_m else ""
    sec_tag = sec_m.group(0) if sec_m else ""
    inline_rep = bool(re.search(r'data-gsc-repositioned=["\']true["\']', inline_tag, flags=re.I))
    sec_rep = bool(re.search(r'data-gsc-repositioned=["\']true["\']', sec_tag, flags=re.I))
    if not (inline_rep or sec_rep):
        return False, "", ""
    inline_pk_m = re.search(r'data-partner=["\']([a-z0-9_]+)["\']', inline_tag, flags=re.I)
    sec_pk_m = re.search(r'data-primary-partner=["\']([a-z0-9_]+)["\']', sec_tag, flags=re.I) or re.search(
        r'data-partner=["\']([a-z0-9_]+)["\']', sec_tag, flags=re.I
    )
    promoted_pk = (
        inline_pk_m.group(1).lower()
        if (inline_rep and inline_pk_m)
        else (sec_pk_m.group(1).lower() if (sec_rep and sec_pk_m) else (inline_pk_m.group(1).lower() if inline_pk_m else ""))
    )
    tier_m = re.search(r'data-gsc-tier=["\']([^"\']+)["\']', inline_tag, flags=re.I) or re.search(
        r'data-gsc-tier=["\']([^"\']+)["\']', sec_tag, flags=re.I
    )
    return True, promoted_pk, (tier_m.group(1).strip() if tier_m else "")


def _apply_preserved_promoted_partner_to_roster(
    roster: Dict[str, Any],
    promoted_pk: str,
    existing_tier: str,
    prop: str,
    slug_id: str,
    registry: Dict[str, AffiliatePartner],
) -> None:
    """Preserves a pre-existing valid GSC/empirical promoted partner on roster and slot_plan when gsc_metrics is None."""
    slot_plan = roster["slot_plan"]
    ordered_offers = [dict(o) for o in (slot_plan.get("ordered_offers") or roster.get("roster_offers") or [])]
    target_len = max(len(ordered_offers), 1)
    if any(str(o.get("partner_key") or "").lower() == promoted_pk for o in ordered_offers):
        ordered_offers = [o for o in ordered_offers if str(o.get("partner_key") or "").lower() == promoted_pk] + [
            o for o in ordered_offers if str(o.get("partner_key") or "").lower() != promoted_pk
        ]
    else:
        p_obj = registry[promoted_pk]
        ftc_disc = (
            PREXVO_DISCLOSURES.get("ftc_disclosure", "")
            if prop == "prexvo"
            else get_contextual_ftc_disclosure(prop, slug=roster["slug"])
        )
        new_entry = _build_roster_offer_entry(
            pk=promoted_pk,
            p_obj=p_obj,
            idx=0,
            total_count=target_len,
            prop=prop,
            s_norm=roster["slug"],
            slug_id=slug_id,
            vertical_family=roster["vertical_family"],
            commercial_intent=roster["commercial_intent"],
            intent_multiplier=roster["intent_multiplier"],
            resolved_archetype=roster["page_archetype"],
            query="",
            ftc_disc=ftc_disc,
        )
        ordered_offers = ([new_entry] + ordered_offers)[:target_len]

    for idx, off in enumerate(ordered_offers):
        off["tier_role"] = "primary" if idx == 0 else ("secondary" if idx < len(ordered_offers) - 1 else "fallback")

    lead_offer = ordered_offers[0]
    slot_weights = slot_plan.get("slot_weights") or {}

    def _bind(off: Dict[str, Any], slot_name: str, sub_suffix: str) -> Dict[str, Any]:
        pk = str(off.get("partner_key") or "")
        sub_val = f"{slug_id}_{sub_suffix}"
        return {
            **off,
            "cta_slot": slot_name,
            "subid": sub_val,
            "slot_weight": slot_weights.get(slot_name, 0.8),
            "attributed_href": f"/r/{pk}?source_tool={slug_id}&subid={sub_val}&cta_slot={slot_name}",
        }

    eff_tier = (
        existing_tier
        if existing_tier and existing_tier.upper() not in ("BASELINE", "BASELINE_MULTI_SLOT")
        else "PRESERVED_GSC_PLACEMENT"
    )
    slot_plan["ordered_offers"] = ordered_offers
    slot_plan["gsc_repositioned"] = True
    slot_plan["gsc_opportunity_tier"] = eff_tier
    slot_plan["promoted_partner_key"] = promoted_pk
    slot_plan["reposition_reason"] = f"Preserved existing promoted placement for '{promoted_pk}' ({eff_tier})."
    slot_plan["slot_bindings"] = {
        "calculator_result_inline": _bind(lead_offer, "calculator_result_inline", "inline"),
        "comparison_table_cta": _bind(lead_offer, "comparison_table_cta", "table"),
        "inline_callout_card": _bind(lead_offer, "inline_callout_card", "callout"),
        "partner_matrix_cards": [
            _bind(off, "calculator_primary_cta" if idx == 1 else "partner_matrix_card", f"card_{idx}")
            for idx, off in enumerate(ordered_offers, start=1)
        ],
    }
    roster["primary_offer"] = lead_offer
    roster["secondary_offers"] = (
        ordered_offers[1:-1] if len(ordered_offers) > 2 else (ordered_offers[1:] if len(ordered_offers) > 1 else [])
    )
    roster["fallback_offer"] = ordered_offers[-1] if len(ordered_offers) >= 2 else lead_offer
    roster["roster_offers"] = ordered_offers
    roster["roster_keys"] = [str(o.get("partner_key") or "") for o in ordered_offers]
    roster["distinct_companies"] = list(
        dict.fromkeys(str(o.get("company_brand") or "") for o in ordered_offers if o.get("company_brand"))
    )
    roster["distinct_companies_count"] = len(roster["distinct_companies"])
    roster["partnership_models_represented"] = list(
        dict.fromkeys(str(o.get("partnership_model") or "") for o in ordered_offers if o.get("partnership_model"))
    )
    roster["primary_partnership_model"] = str(lead_offer.get("partnership_model") or "")


def load_property_partner_engagement_metrics(
    agy_dir: Optional[Any],
    property_id: str = "",
) -> Dict[str, Any]:
    """Loads persisted outbound partner engagement metrics from a property's .agy directory."""
    if not agy_dir:
        return {}
    base_dir = Path(agy_dir)
    if not base_dir.is_dir():
        return {}
    prop_clean = (property_id or "").strip().lower()
    if prop_clean == "exchange1031":
        prop_clean = "profithelm"
    for eng_cand in (
        base_dir / "outbound_partner_engagement.json",
        base_dir / "partner_engagement_metrics.json",
    ):
        if not eng_cand.is_file():
            continue
        try:
            loaded = json.loads(eng_cand.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_prop = str(loaded.get("property_id") or "").strip().lower()
                if loaded_prop == "exchange1031":
                    loaded_prop = "profithelm"
                if not prop_clean or not loaded_prop or loaded_prop == prop_clean:
                    return loaded
        except Exception:
            continue
    return {}


def load_persisted_gsc_placement_metrics_by_slug(
    agy_dir: Optional[Any],
    property_id: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Loads per-slug GSC query, impression, CTR, position, and searchAppearance signals from .agy/gsc_affiliate_placement_ledger.json."""
    if not agy_dir:
        return {}
    ledger_path = Path(agy_dir) / "gsc_affiliate_placement_ledger.json"
    if not ledger_path.is_file():
        return {}
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(ledger, dict):
        return {}
    prop_clean = (property_id or "").strip().lower()
    if prop_clean == "exchange1031":
        prop_clean = "profithelm"
    ledger_prop = str(ledger.get("property_id") or "").strip().lower()
    if ledger_prop == "exchange1031":
        ledger_prop = "profithelm"
    if prop_clean and ledger_prop and ledger_prop != prop_clean:
        return {}
    by_slug: Dict[str, Dict[str, Any]] = {}
    for row in list(ledger.get("page_reports") or []) + list(ledger.get("repositioned_pages") or []):
        if not isinstance(row, dict):
            continue
        r_slug = str(row.get("slug") or "").strip().strip("/").lower()
        if not r_slug:
            continue
        impr = int(float(row.get("gsc_impressions", row.get("impressions", 0)) or 0))
        clicks = int(float(row.get("gsc_clicks", row.get("clicks", 0)) or 0))
        mob_impr = int(float(row.get("gsc_mobile_impressions", row.get("mobile_impressions", 0)) or 0))
        desk_impr = int(float(row.get("gsc_desktop_impressions", row.get("desktop_impressions", 0)) or 0))
        q_str = str(row.get("gsc_query") or row.get("query") or "").strip()
        sa_list = [str(sa) for sa in (row.get("gsc_search_appearances") or row.get("search_appearances") or []) if sa]
        if not (impr > 0 or mob_impr > 0 or desk_impr > 0 or q_str or sa_list):
            continue
        metrics = {
            "slug": r_slug,
            "impressions": impr,
            "clicks": clicks,
            "ctr": float(row.get("gsc_ctr", row.get("ctr", 0.0)) or 0.0),
            "position": float(row.get("gsc_position", row.get("position", 0.0)) or 0.0),
            "query": q_str,
            "mobile_impressions": mob_impr,
            "desktop_impressions": desk_impr,
            "mobile_ctr": float(row.get("gsc_mobile_ctr", row.get("mobile_ctr", 0.0)) or 0.0),
            "desktop_ctr": float(row.get("gsc_desktop_ctr", row.get("desktop_ctr", 0.0)) or 0.0),
            "mobile_ctr_gap": float(row.get("gsc_mobile_ctr_gap", row.get("mobile_ctr_gap", 0.0)) or 0.0),
            "device_focus": str(row.get("gsc_device_focus") or row.get("device_focus") or "BALANCED"),
            "search_appearances": sa_list,
        }
        by_slug[r_slug] = metrics
        by_slug.setdefault(r_slug.replace("/", "-"), metrics)
    return by_slug


def bind_asset_partner_roster(
    property_id: str,
    slug: str,
    query: str = "",
    page_archetype: str = "",
    gsc_metrics: Optional[Dict[str, Any]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    vault_overrides: Optional[Dict[str, Any]] = None,
    min_companies: int = 3,
    html_content: str = "",
) -> Dict[str, Any]:
    """
    Automatically binds a diversified multi-company partner roster (Primary, Secondary, Fallback)
    for any new or existing asset or vertical, and deterministically computes its conversion
    slot placement plan using page archetype, commercial intent, expected yield, and live GSC signals.
    Guarantees at least `min_companies` (>=3) distinct partner companies on every commercial page
    and strict 0-commercial-link YMYL compliance on restricted public-service pages.
    Zero em-dashes. Zero en-dashes.
    """
    cls_info = classify_asset_archetype_and_intent(
        property_id=property_id,
        slug=slug,
        query=query,
        page_archetype=page_archetype,
        html_content=html_content,
    )
    prop = cls_info["property_id"]
    s_norm = cls_info["slug"]
    vertical_family = cls_info["vertical_family"]
    resolved_archetype = cls_info["page_archetype"]
    commercial_intent = cls_info["commercial_intent"]
    intent_multiplier = cls_info["intent_multiplier"]
    restricted_ps = cls_info["restricted_public_service"]

    if restricted_ps:
        slot_plan = select_conversion_slot_plan(
            property_id=prop,
            slug=s_norm,
            roster_offers=[],
            page_archetype=resolved_archetype,
            commercial_intent=commercial_intent,
            vertical_family=vertical_family,
            gsc_metrics=gsc_metrics,
            engagement_metrics=engagement_metrics,
        )
        return {
            **cls_info,
            "primary_offer": None,
            "secondary_offers": [],
            "fallback_offer": None,
            "roster_offers": [],
            "roster_keys": [],
            "distinct_companies": [],
            "distinct_companies_count": 0,
            "primary_partnership_model": "",
            "partnership_models_represented": [],
            "slot_plan": slot_plan,
        }

    registry = (
        PREXVO_AFFILIATES
        if prop == "prexvo"
        else (
            GAINHELM_AFFILIATES
            if prop == "gainhelm"
            else (LIENBOND_AFFILIATES if prop == "lienbond" else PROFITHELM_AFFILIATES)
        )
    )

    # 1. Start with ranked tool affiliates from existing catalog + vertical diversified roster
    ranked_initial = rank_partner_offers_by_revenue_yield(
        property_id=prop,
        slug=s_norm,
        engagement_metrics=engagement_metrics,
        vault_overrides=vault_overrides,
    )
    ranked_by_key: Dict[str, Dict[str, Any]] = {
        str(r.get("partner_key") or ""): dict(r)
        for r in ranked_initial
        if isinstance(r, dict) and r.get("partner_key")
    }

    vertical_template_keys = list(
        VERTICAL_DIVERSIFIED_PARTNER_ROSTERS.get(
            vertical_family,
            VERTICAL_DIVERSIFIED_PARTNER_ROSTERS["general_b2b_commercial_finance"],
        )
    )

    def _is_roster_eligible(pk_cand: str) -> bool:
        p_cand = registry.get(pk_cand)
        if not p_cand:
            return False
        st_cand = str(p_cand.status or "").strip().lower()
        if st_cand in ("declined", "rejected", "terminated", "inactive"):
            return False
        if prop in ("profithelm", "exchange1031") and st_cand != "live":
            return False
        return True

    candidate_keys_ordered: List[str] = []
    if prop == "gainhelm":
        gh_prof = get_gainhelm_framework_profile(slug=s_norm, vertical=vertical_family)
        gh_prim_pk = str(gh_prof.get("primary_partner_key") or "vanta_security")
        if _is_roster_eligible(gh_prim_pk):
            candidate_keys_ordered.append(gh_prim_pk)
    for k in vertical_template_keys:
        if _is_roster_eligible(k) and k not in candidate_keys_ordered:
            candidate_keys_ordered.append(k)
    for r in ranked_initial:
        rk = str(r.get("partner_key") or "")
        if _is_roster_eligible(rk) and rk not in candidate_keys_ordered:
            candidate_keys_ordered.append(rk)
    # Fallback supplement pool so even greenfield verticals always reach >= min_companies distinct companies
    supplement_pool = (
        ["splash_financial", "credible", "lendkey", "laurel_road"]
        if prop == "prexvo"
        else (
            ["vanta_security", "drata_compliance", "sprinto_compliance", "thoropass_audit", "coalition_cyber_insurance", "cobalt_pentest"]
            if prop == "gainhelm"
            else (
                ["simply_business", "suretybonds_direct", "thimble_contractor", "jobber_field_service", "levelset_lien_filing"]
                if prop == "lienbond"
                else ["xendoo", "ramp", "mercury", "rippling", "gusto", "efile_com", "eztaxreturn_com", "freetaxusa", "wallethub", "coinledger", "koinly", "kalshi", "lawdepot"]
            )
        )
    )
    for sk in supplement_pool:
        if _is_roster_eligible(sk) and sk not in candidate_keys_ordered:
            candidate_keys_ordered.append(sk)

    # 2. Select diversified multi-company roster prioritizing distinct underlying company brands first
    selected_keys: List[str] = []
    seen_brands: Set[str] = set()
    target_roster_size = (
        3
        if prop == "prexvo"
        else (6 if prop == "gainhelm" else max(3, int(min_companies)))
    )

    for ck in candidate_keys_ordered:
        brand_name = COMPANY_BRAND_BY_PARTNER_KEY.get(ck, ck.replace("_", " ").title())
        if brand_name not in seen_brands:
            selected_keys.append(ck)
            seen_brands.add(brand_name)
        if len(selected_keys) >= target_roster_size:
            break

    # If still fewer than target_roster_size, append remaining distinct keys
    if len(selected_keys) < target_roster_size:
        for ck in candidate_keys_ordered:
            if ck not in selected_keys:
                selected_keys.append(ck)
            if len(selected_keys) >= target_roster_size:
                break

    # 3. Build enriched offer dicts for each selected partner key
    slug_id = s_norm.replace("/", "-")
    ftc_disc = (
        PREXVO_DISCLOSURES.get("ftc_disclosure", "")
        if prop == "prexvo"
        else get_contextual_ftc_disclosure(prop, slug=s_norm)
    )
    roster_offers: List[Dict[str, Any]] = [
        _build_roster_offer_entry(
            pk=pk,
            p_obj=registry[pk],
            idx=idx,
            total_count=len(selected_keys),
            prop=prop,
            s_norm=s_norm,
            slug_id=slug_id,
            vertical_family=vertical_family,
            commercial_intent=commercial_intent,
            intent_multiplier=intent_multiplier,
            resolved_archetype=resolved_archetype,
            query=query,
            ftc_disc=ftc_disc,
            r_meta=ranked_by_key.get(pk),
        )
        for idx, pk in enumerate(selected_keys)
    ]

    slot_plan = select_conversion_slot_plan(
        property_id=prop,
        slug=s_norm,
        roster_offers=roster_offers,
        page_archetype=resolved_archetype,
        commercial_intent=commercial_intent,
        vertical_family=vertical_family,
        gsc_metrics=gsc_metrics,
        engagement_metrics=engagement_metrics,
    )

    ordered_offers = slot_plan["ordered_offers"]
    primary_offer = ordered_offers[0] if ordered_offers else None
    secondary_offers = ordered_offers[1:-1] if len(ordered_offers) > 2 else (ordered_offers[1:] if len(ordered_offers) > 1 else [])
    fallback_offer = ordered_offers[-1] if len(ordered_offers) >= 2 else primary_offer
    distinct_companies = list(dict.fromkeys(str(o.get("company_brand") or "") for o in ordered_offers if o.get("company_brand")))
    partnership_models_represented = list(dict.fromkeys(str(o.get("partnership_model") or "") for o in ordered_offers if o.get("partnership_model")))
    primary_partnership_model = str(primary_offer.get("partnership_model") or "") if primary_offer else ""

    return {
        **cls_info,
        "primary_offer": primary_offer,
        "secondary_offers": secondary_offers,
        "fallback_offer": fallback_offer,
        "roster_offers": ordered_offers,
        "roster_keys": [str(o.get("partner_key") or "") for o in ordered_offers],
        "distinct_companies": distinct_companies,
        "distinct_companies_count": len(distinct_companies),
        "primary_partnership_model": primary_partnership_model,
        "partnership_models_represented": partnership_models_represented,
        "slot_plan": slot_plan,
    }


def reposition_affiliate_placements_from_gsc_signals(
    html_content: str,
    property_id: str = "profithelm",
    slug: str = "",
    query: str = "",
    gsc_metrics: Optional[Dict[str, Any]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    skip_callout_if_unchanged: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """
    Analyzes live GSC query, impression, CTR, and position signals alongside empirical
    click yield to dynamically reposition or swap affiliate placements on compiled HTML pages:
      1. Updates or injects the above-the-fold `calculator_result_inline` (.calc-inline-cta)
         hook inside `.result-box` / `.result-card` with the GSC-promoted primary partner.
      2. Injects or updates an actionable `comparison_table_cta` conversion slot inside or
         immediately beneath the scenario/statutory comparison table on high-opportunity pages.
      3. Expands or re-orders the multi-company partner roster cards (`primary`, `secondary`,
         `fallback`) so the highest-converting offer leads.
      4. Synchronizes `#gsc-striking-overlay` `.overlay-partner-offer` when present.
    Returns `(updated_html, placement_delta_report)`.
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib

    if not html_content or not isinstance(html_content, str):
        return html_content, {"repositioned": False, "status": "EMPTY_HTML"}

    prop = (property_id or "profithelm").strip().lower()
    page_slug = (slug or _extract_tool_slug_from_html_head(html_content)).strip().strip("/").lower()
    slug_id = page_slug.replace("/", "-")

    # Capture before state
    before_partners = re.findall(r'data-partner=["\']([a-z0-9_]+)["\']', html_content, flags=re.I)
    before_slots = list(dict.fromkeys(re.findall(r'data-cta-slot=["\']([^"\']+)["\']', html_content, flags=re.I)))
    before_inline_m = re.search(
        r'<div\s+class=["\'][^"\']*calc-inline-cta[^"\']*["\'][^>]*data-partner=["\']([a-z0-9_]+)["\']',
        html_content,
        flags=re.I,
    )
    before_primary = (
        before_inline_m.group(1).lower()
        if before_inline_m
        else (before_partners[0].lower() if before_partners else "")
    )

    existing_gsc_rep, existing_promoted_pk, existing_gsc_tier = _extract_existing_gsc_promoted_placement(html_content)
    gsc_dict = dict(gsc_metrics) if isinstance(gsc_metrics, dict) else {}
    eff_query = str(query or gsc_dict.get("query") or gsc_dict.get("top_query") or "").strip()

    roster = bind_asset_partner_roster(
        property_id=prop,
        slug=page_slug,
        query=eff_query,
        gsc_metrics=gsc_dict,
        engagement_metrics=engagement_metrics,
        html_content=html_content,
    )

    is_concrete_page_slug = bool(page_slug and page_slug not in ("tool", "index"))
    is_restricted_page = bool(
        roster["restricted_public_service"]
        or (
            prop == "prexvo"
            and (not is_concrete_page_slug or is_restricted_public_service_slug(page_slug))
            and (
                'data-restricted-public-service="true"' in html_content
                or 'data-commercial-offers="none"' in html_content
                or 'data-commercial-offers="suppressed-default"' in html_content
            )
        )
    )
    if is_restricted_page:
        cleaned_html = strip_commercial_affiliate_blocks_for_restricted_ymyl(html_content)
        return cleaned_html, {
            "slug": page_slug,
            "property_id": prop,
            "restricted_public_service": True,
            "callout_normalized": True,
            "repositioned": cleaned_html != html_content,
            "before_primary_partner": before_primary,
            "after_primary_partner": "",
            "before_slots": before_slots,
            "after_slots": ["ymyl_public_service_guardrail"],
            "gsc_opportunity_tier": "RESTRICTED_PUBLIC_SERVICE",
            "roster_keys": [],
            "distinct_companies": [],
        }

    registry = _property_partner_registry(prop)
    slot_plan = roster["slot_plan"]
    existing_pk_obj = registry.get(existing_promoted_pk) if existing_promoted_pk else None
    existing_pk_eligible = bool(
        existing_pk_obj is not None
        and str(existing_pk_obj.status or "").strip().lower() not in ("declined", "rejected", "terminated", "inactive")
        and (
            prop not in ("profithelm", "exchange1031")
            or (
                str(existing_pk_obj.status or "").strip().lower() == "live"
                and existing_promoted_pk in SOVRN_VERIFIED_PAYING_MERCHANTS
            )
        )
    )
    existing_tier_upper = (existing_gsc_tier or "").strip().upper()
    existing_is_non_empirical_gsc = existing_tier_upper not in (
        "",
        "BASELINE",
        "BASELINE_MULTI_SLOT",
        "EMPIRICAL_YIELD_SWAP",
    )
    if (
        gsc_metrics is None
        and not eff_query
        and existing_gsc_rep
        and existing_pk_eligible
        and (
            slot_plan.get("gsc_opportunity_tier") != "EMPIRICAL_YIELD_SWAP"
            or existing_is_non_empirical_gsc
        )
    ):
        _apply_preserved_promoted_partner_to_roster(
            roster=roster,
            promoted_pk=existing_promoted_pk,
            existing_tier=existing_gsc_tier,
            prop=prop,
            slug_id=slug_id,
            registry=registry,
        )

    live_vault_keys = load_live_partner_keys_from_vault(prop)
    bindings = slot_plan["slot_bindings"]
    inline_offer = bindings["calculator_result_inline"]
    if isinstance(inline_offer, dict) and str(inline_offer.get("partner_key") or "").strip().lower() not in live_vault_keys:
        inline_offer = None
    table_offer = bindings["comparison_table_cta"]
    if isinstance(table_offer, dict) and str(table_offer.get("partner_key") or "").strip().lower() not in live_vault_keys:
        table_offer = None
    matrix_cards = [
        c
        for c in (bindings["partner_matrix_cards"] or [])
        if isinstance(c, dict) and str(c.get("partner_key") or "").strip().lower() in live_vault_keys
    ]
    if inline_offer is None and matrix_cards:
        lead_card = dict(matrix_cards[0])
        lead_pk_fb = str(lead_card["partner_key"])
        lead_card["cta_slot"] = "calculator_result_inline"
        lead_card["subid"] = f"{slug_id}_inline"
        lead_card["attributed_href"] = (
            f"/r/{lead_pk_fb}?source_tool={slug_id}&subid={slug_id}_inline&cta_slot=calculator_result_inline"
        )
        lead_card["status"] = "live"
        inline_offer = lead_card
    if table_offer is None and matrix_cards and "comparison_table_cta" in (slot_plan.get("active_slots") or []):
        lead_tbl = dict(matrix_cards[0])
        lead_pk_fb = str(lead_tbl["partner_key"])
        lead_tbl["cta_slot"] = "comparison_table_cta"
        lead_tbl["subid"] = f"{slug_id}_table"
        lead_tbl["attributed_href"] = (
            f"/r/{lead_pk_fb}?source_tool={slug_id}&subid={slug_id}_table&cta_slot=comparison_table_cta"
        )
        lead_tbl["status"] = "live"
        table_offer = lead_tbl
    gsc_tier = str(slot_plan.get("gsc_opportunity_tier") or "BASELINE_MULTI_SLOT")
    updated = html_content

    # 1. Reposition / inject calculator_result_inline (.calc-inline-cta) only on legacy non-3-step pages
    if inline_offer and 'id="workpaper-unlock-card"' not in updated:
        pk_in = str(inline_offer["partner_key"])
        safe_badge = html_lib.escape(str(inline_offer.get("badge") or "Featured Offer"))
        safe_name = html_lib.escape(str(inline_offer.get("name") or pk_in))
        safe_cta = html_lib.escape(str(inline_offer.get("cta_text") or "Explore Partner"))
        safe_brand = html_lib.escape(str(inline_offer.get("company_brand") or pk_in))
        safe_in_model = html_lib.escape(str(inline_offer.get("partnership_model") or resolve_partnership_model_spec(pk_in)["partnership_model"]))
        safe_href = html_lib.escape(str(inline_offer.get("attributed_href") or f"/r/{pk_in}"))
        safe_sub = html_lib.escape(str(inline_offer.get("subid") or f"{slug_id}_inline"))
        safe_in_status = "live"
        safe_tool = html_lib.escape(slug_id)
        safe_gsc_tier = html_lib.escape(gsc_tier)
        yield_str = f"{float(inline_offer.get('yield_score', 0.0) or 0.0):.2f}"

        inline_offer_tag = "Verified Offer" if safe_in_status == "live" else "Partner Option"
        new_inline_div = (
            f'<div class="calc-inline-cta" data-mechanic="compliant_intent_monetization" '
            f'data-partner="{pk_in}" data-company-brand="{safe_brand}" data-partner-tier="primary" '
            f'data-partnership-model="{safe_in_model}" '
            f'data-gsc-tier="{safe_gsc_tier}" data-gsc-repositioned="{"true" if slot_plan.get("gsc_repositioned") else "false"}" '
            f'data-yield-score="{yield_str}" '
            f'style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.75rem 1rem; margin-top: 0.75rem; margin-bottom: 0.75rem; background: var(--bg-elevated); border: 1px solid var(--brand-border); border-left: 4px solid var(--brand-primary); border-radius: 8px;">\n'
            f'            <div class="calc-inline-cta-copy" style="flex: 1; min-width: 180px;">\n'
            f'              <div style="font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--brand-primary);">{safe_badge} &bull; {inline_offer_tag}</div>\n'
            f'              <div style="font-size: 0.875rem; font-weight: 700; color: var(--text-primary); margin-top: 0.125rem;">{safe_name}</div>\n'
            f'            </div>\n'
            f'            <a href="{safe_href}" target="_blank" rel="noopener sponsored nofollow" '
            f'data-partner="{pk_in}" data-company-brand="{safe_brand}" data-partner-tier="primary" '
            f'data-partnership-model="{safe_in_model}" '
            f'data-tool="{safe_tool}" data-subid="{safe_sub}" data-status="{safe_in_status}" data-tier="starter" '
            f'data-cta-slot="calculator_result_inline" class="btn-cta touch-target" '
            f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; white-space: nowrap; text-decoration: none;">\n'
            f'              {safe_cta} &rarr;\n'
            f'            </a>\n'
            f'          </div>'
        )

        if 'class="calc-inline-cta"' in updated:
            updated = re.sub(
                r'<div\s+class=["\']calc-inline-cta["\'][^>]*>.*?</div>\s*<a\s+[^>]*data-cta-slot=["\']calculator_result_inline["\'][^>]*>.*?</a>\s*</div>',
                new_inline_div,
                updated,
                count=1,
                flags=re.S | re.I,
            )
        else:
            for r_pat in (
                r'(<div\s+class=["\'][^"\']*\bresult-box\b[^"\']*["\'][^>]*>(?:(?!</div\b).)*?)(</div>)',
                r'(<div\s+class=["\'][^"\']*\bresult-card\b[^"\']*["\'][^>]*>\s*<div\s+class=["\'][^"\']*\bcard-header\b[^"\']*["\']>.*?</div>)',
                r'(<div\s+class=["\'][^"\']*calc-outputs-panel[^"\']*["\'][^>]*>\s*<div\s+class=["\'][^"\']*\bcalc-panel-header\b[^"\']*["\']>.*?</div>)',
                r'(<div\s+class=["\'][^"\']*\bcalc-results-column\b[^"\']*["\'][^>]*>.*?)(</div>)',
                r'(<div\s+class=["\'][^"\']*\bresults-panel\b[^"\']*["\'][^>]*>.*?)(</div>)',
                r'(<div\s+class=["\'][^"\']*\bcalc-results\b[^"\']*["\'][^>]*>.*?)(</div>)',
            ):
                if re.search(r_pat, updated, flags=re.S | re.I):
                    if "result-box" in r_pat:
                        updated = re.sub(
                            r_pat,
                            rf"\g<1>\n          {new_inline_div}\n      \g<2>",
                            updated,
                            count=1,
                            flags=re.S | re.I,
                        )
                    else:
                        updated = re.sub(r_pat, rf"\g<1>\n          {new_inline_div}", updated, count=1, flags=re.S | re.I)
                    break

        cta_pos_m = updated.find('<div class="calc-inline-cta"')
        kpi_pos_m = updated.find('<div class="kpi-block"')
        kpi_end_cands_m = [
            pos
            for pos in (
                updated.find('<div class="calc-statutory-box"', kpi_pos_m if kpi_pos_m != -1 else 0),
                updated.find('<div class="share-pro-container"', kpi_pos_m if kpi_pos_m != -1 else 0),
                updated.find('<div style="margin-top: 1rem;">', kpi_pos_m if kpi_pos_m != -1 else 0),
                updated.find('<div class="lead-capture-card"', kpi_pos_m if kpi_pos_m != -1 else 0),
            )
            if pos != -1
        ]
        kpi_end_m = min(kpi_end_cands_m) if kpi_end_cands_m else -1
        if cta_pos_m != -1 and kpi_pos_m != -1 and kpi_end_m != -1 and cta_pos_m < kpi_pos_m < kpi_end_m:
            kpi_slice_m = updated[kpi_pos_m:kpi_end_m].strip()
            if kpi_slice_m and "calc-inline-cta" not in kpi_slice_m:
                updated = (
                    updated[:cta_pos_m]
                    + kpi_slice_m
                    + "\n          "
                    + updated[cta_pos_m:kpi_pos_m].rstrip()
                    + updated[kpi_end_m:]
                )
        rap_meter_m2 = re.search(
            r'<div\b[^>]*id=["\']rap-subsidy-meter["\'][^>]*>[\s\S]*?<div\s+class=["\']subsidy-meter-legend["\'][^>]*>[\s\S]*?</div>\s*</div>',
            updated,
            flags=re.I,
        )
        cta_pos_m2 = updated.find('<div class="calc-inline-cta"')
        if rap_meter_m2 and cta_pos_m2 != -1 and cta_pos_m2 < rap_meter_m2.start():
            rap_slice_m2 = rap_meter_m2.group(0).strip()
            updated = (
                updated[:cta_pos_m2]
                + rap_slice_m2
                + "\n      "
                + updated[cta_pos_m2 : rap_meter_m2.start()].rstrip()
                + updated[rap_meter_m2.end() :]
            )
        gh_m2 = re.search(
            r'<div\b[^>]*class=["\'][^"\']*\b(?:calc-metrics-grid|metrics-grid)\b[^"\']*["\'][^>]*>',
            updated,
            flags=re.I,
        )
        cta_pos_m3 = updated.find('<div class="calc-inline-cta"')
        if gh_m2 and cta_pos_m3 != -1 and cta_pos_m3 < gh_m2.start():
            gm_s2 = gh_m2.start()
            gm_d2 = 0
            gm_e2 = -1
            for d_tok2 in re.finditer(r"</?div\b[^>]*>", updated[gm_s2:], flags=re.I):
                t_low2 = d_tok2.group(0).lower()
                if t_low2.startswith("</div"):
                    gm_d2 -= 1
                    if gm_d2 == 0:
                        gm_e2 = gm_s2 + d_tok2.end()
                        break
                elif not t_low2.endswith("/>"):
                    gm_d2 += 1
            if gm_e2 > gm_s2 and ('id="metric-' in updated[gm_s2:gm_e2] or "id='metric-" in updated[gm_s2:gm_e2]):
                updated = (
                    updated[:cta_pos_m3]
                    + updated[gm_s2:gm_e2].strip()
                    + "\n          "
                    + updated[cta_pos_m3:gm_s2].rstrip()
                    + updated[gm_e2:]
                )

    # 2. Inject or update comparison_table_cta when active in slot_plan (skip on 3-step #workpaper-unlock-card pages)
    has_existing_table_cta = bool(_COMPARISON_TABLE_CTA_BAR_RE.search(updated))
    if 'id="workpaper-unlock-card"' in updated:
        if has_existing_table_cta:
            updated = _COMPARISON_TABLE_CTA_BAR_STRIP_RE.sub("", updated)
    elif ("comparison_table_cta" in slot_plan["active_slots"] or has_existing_table_cta) and table_offer:
        pk_tbl = str(table_offer["partner_key"])

        def _build_table_cta_bar(existing_cls: str = "") -> str:
            return _render_comparison_table_cta_bar(
                pk=pk_tbl,
                name=str(table_offer.get("name") or pk_tbl),
                cta_text=str(table_offer.get("cta_text") or "Compare Offer"),
                brand=str(table_offer.get("company_brand") or pk_tbl),
                model=str(table_offer.get("partnership_model") or resolve_partnership_model_spec(pk_tbl)["partnership_model"]),
                href=str(table_offer.get("attributed_href") or f"/r/{pk_tbl}"),
                tool=slug_id,
                subid=f"{slug_id}_table",
                status="live",
                gsc_tier=gsc_tier,
                tier_role=str(table_offer.get("tier_role") or "primary"),
                existing_class_attr=existing_cls,
            )

        if has_existing_table_cta:
            updated = _COMPARISON_TABLE_CTA_BAR_RE.sub(
                lambda m: _build_table_cta_bar(m.group(1) or ""),
                updated,
            )
        else:
            new_table_cta_bar = _build_table_cta_bar("")
            for tbl_pat in (
                r'(<section\s+class=["\'][^"\']*scenario-comparison[^"\']*["\'][^>]*>.*?</table>\s*</div>)',
                r'(<section\s+class=["\'][^"\']*overlay-comparison[^"\']*["\'][^>]*>.*?</table>\s*</div>)',
                r'(<table\s+class=["\'][^"\']*(?:scenario-table|comparison-table|sensitivity-table)[^"\']*["\'][^>]*>.*?</table>\s*</div>)',
            ):
                if re.search(tbl_pat, updated, flags=re.S | re.I):
                    updated = re.sub(
                        tbl_pat,
                        lambda m: f"{m.group(1)}\n      {new_table_cta_bar}",
                        updated,
                        count=1,
                        flags=re.S | re.I,
                    )
                    break
    elif has_existing_table_cta and not table_offer:
        updated = _COMPARISON_TABLE_CTA_BAR_STRIP_RE.sub("", updated)

    # 3. Rebuild or expand .affiliates-section / .affiliate-cta-section with the diversified multi-company roster
    _hidden_unapproved_sec_re = re.compile(
        r'<section\b[^>]*\bdata-partner-ctas-hidden=["\']unapproved["\'][^>]*>.*?</section>',
        flags=re.S | re.I,
    )

    def _collect_secondary_hidden_unapproved_meta(
        doc_html: str,
        primary_start: int,
    ) -> Tuple[str, str, bool]:
        """Extracts inherited id= and #partner-registration-drawer from secondary hidden-unapproved sections."""
        other_spans: List[Tuple[int, int, str]] = [
            (hm.start(), hm.end(), hm.group(0))
            for hm in _hidden_unapproved_sec_re.finditer(doc_html)
            if hm.start() != primary_start
        ]
        if not other_spans:
            return "", "", False
        doc_without_other = doc_html
        for hs, he, _ in reversed(other_spans):
            doc_without_other = doc_without_other[:hs] + doc_without_other[he:]
        has_drawer_elsewhere = 'id="partner-registration-drawer"' in doc_without_other
        inh_id = ""
        inh_drawer = ""
        for _, _, h_blk in other_spans:
            if not inh_id:
                h_open_m = re.match(r"<section\b[^>]*>", h_blk, flags=re.I)
                inh_id = _extract_section_id_attr(h_open_m.group(0) if h_open_m else "")
            if not inh_drawer and not has_drawer_elsewhere:
                inh_drawer = _extract_partner_registration_drawer(h_blk)
        return inh_id, inh_drawer, True

    def _strip_remaining_hidden_unapproved_placeholders(doc_html: str, had_other_sections: bool) -> str:
        """Removes stale hidden-unapproved workpaper placeholders once live partner CTAs are restored."""
        cleaned_doc = _hidden_unapproved_sec_re.sub("", doc_html) if had_other_sections else doc_html
        if 'data-partner-ctas-hidden="unapproved"' in cleaned_doc:
            cleaned_doc = _strip_balanced_blocks_matching(
                cleaned_doc,
                "div",
                r'<div\b[^>]*\bdata-partner-ctas-hidden=["\']unapproved["\'][^>]*>',
                predicate=lambda _b: True,
            )
        return cleaned_doc

    if 'id="workpaper-unlock-card"' in updated:
        # 3-step funnel pages update their single compact .contextual-referral-card in place
        # (never re-injecting #partner-registration-drawer or multi-card .affiliates-section).
        target_pk = ""
        if isinstance(inline_offer, dict) and inline_offer.get("partner_key"):
            cand_pk = str(inline_offer["partner_key"]).strip().lower()
            if cand_pk in live_vault_keys:
                target_pk = cand_pk
        if not target_pk and matrix_cards:
            cand_pk = str(matrix_cards[0].get("partner_key") or "").strip().lower()
            if cand_pk in live_vault_keys:
                target_pk = cand_pk
        ref_sec_re = re.compile(
            r'<section\b[^>]*\bclass=["\'][^"\']*\bcontextual-referral-card\b[^"\']*["\'][^>]*>.*?</section>',
            flags=re.S | re.I,
        )
        if target_pk and not (prop == "prexvo" and not any(t in f"{page_slug} {eff_query}".lower() for t in ("refinance", "refinancing"))):
            new_ref_card = build_contextual_referral_card_html(
                property_id=prop,
                slug=page_slug,
                query=eff_query,
                gsc_metrics=gsc_metrics,
                engagement_metrics=engagement_metrics,
                page_archetype=roster["page_archetype"],
                forced_partner_key=target_pk,
                gsc_repositioned=bool(slot_plan.get("gsc_repositioned")),
                gsc_tier=gsc_tier,
            )
            if new_ref_card and ref_sec_re.search(updated):
                updated = ref_sec_re.sub(lambda _m: new_ref_card, updated, count=1)
    elif matrix_cards and prop != "prexvo":
        def _render_roster_card(card_offer: Dict[str, Any], idx: int) -> str:
            c_pk = str(card_offer["partner_key"])
            c_name = html_lib.escape(str(card_offer.get("name") or c_pk))
            c_desc = html_lib.escape(str(card_offer.get("description") or ""))
            c_badge = html_lib.escape(str(card_offer.get("badge") or "Verified Partner"))
            c_cta = html_lib.escape(str(card_offer.get("cta_text") or "Explore Partner"))
            c_brand = html_lib.escape(str(card_offer.get("company_brand") or c_pk))
            c_role = html_lib.escape(str(card_offer.get("tier_role") or ("primary" if idx == 1 else "secondary")))
            c_model = html_lib.escape(str(card_offer.get("partnership_model") or resolve_partnership_model_spec(c_pk)["partnership_model"]))
            c_slot = html_lib.escape(str(card_offer.get("cta_slot") or ("calculator_primary_cta" if idx == 1 else "partner_matrix_card")))
            c_href = html_lib.escape(str(card_offer.get("attributed_href") or f"/r/{c_pk}"))
            c_sub = html_lib.escape(str(card_offer.get("subid") or f"{slug_id}_card_{idx}"))
            c_status = "live"
            c_tool = html_lib.escape(slug_id)
            return (
                f'\n    <div class="affiliate-card partner-card" data-partner="{c_pk}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" data-partnership-model="{c_model}">\n'
                f'      <div class="affiliate-info">\n'
                f'        <span class="affiliate-badge">{c_badge} ({c_role.title()} Offer)</span>\n'
                f'        <span class="affiliate-disclosure-badge" style="font-size: 0.75rem; color: var(--text-secondary); margin-left: 0.5rem; font-weight: 500;">Sponsored / {c_brand}</span>\n'
                f'        <h3 class="affiliate-title">{c_name}</h3>\n'
                f'        <p class="affiliate-desc">{c_desc}</p>\n'
                f'      </div>\n'
                f'      <div>\n'
                f'        <a href="{c_href}" target="_blank" rel="noopener sponsored nofollow" '
                f'data-partner="{c_pk}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" '
                f'data-partnership-model="{c_model}" '
                f'data-status="{c_status}" data-tool="{c_tool}" data-subid="{c_sub}" data-cta-slot="{c_slot}" '
                f'data-tier="starter" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; text-decoration: none;">\n'
                f'          {c_cta} &rarr;\n'
                f'        </a>\n'
                f'      </div>\n'
                f'    </div>'
            )

        cards_html = "\n".join(_render_roster_card(c, idx) for idx, c in enumerate(matrix_cards, start=1))
        live_card_keys = [str(c["partner_key"]) for c in matrix_cards]
        live_card_companies = list(
            dict.fromkeys(
                str(c.get("company_brand") or COMPANY_BRAND_BY_PARTNER_KEY.get(str(c["partner_key"]), str(c["partner_key"])))
                for c in matrix_cards
            )
        )
        live_card_models = list(
            dict.fromkeys(
                str(c.get("partnership_model") or resolve_partnership_model_spec(str(c["partner_key"]))["partnership_model"])
                for c in matrix_cards
            )
        )
        roster_keys_csv = html_lib.escape(",".join(live_card_keys))
        companies_csv = html_lib.escape(",".join(live_card_companies))
        models_csv = html_lib.escape(",".join(live_card_models or (roster.get("partnership_models_represented") or [])))
        lead_pk_cand = str(slot_plan.get("promoted_partner_key") or "").strip().lower()
        effective_lead_pk = lead_pk_cand if lead_pk_cand in live_vault_keys else live_card_keys[0]
        lead_model_attr = html_lib.escape(
            str(
                matrix_cards[0].get("partnership_model")
                or roster.get("primary_partnership_model")
                or "HYBRID_CPA_REVSHARE"
            )
        )

        aff_sec_pat = (
            r'<section\b[^>]*\b(?:class=["\'][^"\']*(?:refinance-partner-section|partners-section|affiliates?-section)[^"\']*["\']|data-partner-ctas-hidden=["\']unapproved["\'])[^>]*>.*?</section>'
            if prop == "gainhelm"
            else r'<section\b[^>]*\b(?:class=["\'][^"\']*affiliates?-section[^"\']*["\']|data-partner-ctas-hidden=["\']unapproved["\'])[^>]*>.*?</section>'
        )
        m_primary_aff = re.search(aff_sec_pat, updated, flags=re.S | re.I)
        if m_primary_aff:
            inherited_id_attr, inherited_reg_drawer, has_other_hidden = _collect_secondary_hidden_unapproved_meta(
                updated, m_primary_aff.start()
            )

            def _replace_aff_sec(m_sec: re.Match) -> str:
                raw_sec = m_sec.group(0)
                raw_open_m = re.match(r"<section\b[^>]*>", raw_sec, flags=re.I)
                raw_open = raw_open_m.group(0) if raw_open_m else ""
                sec_id_attr = _extract_section_id_attr(raw_open) or inherited_id_attr
                sec_classes = ["affiliate-section", "affiliates-section"]
                for extra_cls in ("partners-section", "refinance-partner-section"):
                    if re.search(rf"\b{re.escape(extra_cls)}\b", raw_open):
                        sec_classes.append(extra_cls)
                sec_cls_attr = " ".join(sec_classes)
                lead_pk_str = effective_lead_pk
                h2_str = _normalize_affiliates_section_h2(raw_sec, lead_pk_str, registry)
                reg_str = _extract_partner_registration_drawer(raw_sec) or inherited_reg_drawer
                lead_pk_attr = html_lib.escape(lead_pk_str)
                sec_rep_val = "true" if slot_plan.get("gsc_repositioned") else "false"
                return (
                    f'<section{sec_id_attr} class="{sec_cls_attr}" data-mechanic="compliant_intent_monetization" '
                    f'data-partner="{lead_pk_attr}" data-primary-partner="{lead_pk_attr}" '
                    f'data-partnership-model="{lead_model_attr}" data-partner-models="{models_csv}" '
                    f'data-partner-roster="{roster_keys_csv}" data-partner-companies="{companies_csv}" '
                    f'data-gsc-tier="{html_lib.escape(gsc_tier)}" data-gsc-repositioned="{sec_rep_val}">\n'
                    f'        {h2_str}'
                    f'{cards_html}{reg_str}\n'
                    f'      </section>'
                )
            updated = re.sub(
                aff_sec_pat,
                _replace_aff_sec,
                updated,
                count=1,
                flags=re.S | re.I,
            )
            updated = _strip_remaining_hidden_unapproved_placeholders(updated, has_other_hidden)
    elif matrix_cards and prop == "prexvo":
        live_px_keys = [str(c["partner_key"]) for c in matrix_cards]
        live_px_companies = list(
            dict.fromkeys(
                str(c.get("company_brand") or COMPANY_BRAND_BY_PARTNER_KEY.get(str(c["partner_key"]), str(c["partner_key"])))
                for c in matrix_cards
            )
        )
        live_px_models = list(
            dict.fromkeys(
                str(c.get("partnership_model") or resolve_partnership_model_spec(str(c["partner_key"]))["partnership_model"])
                for c in matrix_cards
            )
        )
        roster_keys_csv = ",".join(live_px_keys)
        companies_csv = ",".join(live_px_companies)
        models_csv = ",".join(live_px_models or (roster.get("partnership_models_represented") or []))
        lead_pk_cand = str(slot_plan.get("promoted_partner_key") or "").strip().lower()
        lead_pk_val = lead_pk_cand if lead_pk_cand in live_vault_keys else live_px_keys[0]
        lead_model_val = str(
            matrix_cards[0].get("partnership_model")
            or roster.get("primary_partnership_model")
            or "CPA_BOUNTY"
        )
        px_sec_pat = r'<section\b[^>]*\b(?:class=["\'][^"\']*(?:refinance-partner-section|partners-section)[^"\']*["\']|data-partner-ctas-hidden=["\']unapproved["\'])[^>]*>.*?</section>'
        m_primary_px = re.search(px_sec_pat, updated, flags=re.S | re.I)
        px_inherited_id_attr, px_inherited_reg_drawer, px_has_other_hidden = (
            _collect_secondary_hidden_unapproved_meta(updated, m_primary_px.start())
            if m_primary_px
            else ("", "", False)
        )

        def _replace_prexvo_sec(m_sec: re.Match) -> str:
            raw_sec = m_sec.group(0)
            if (
                'data-restricted-public-service="true"' in raw_sec
                or 'data-commercial-offers="none"' in raw_sec
                or 'data-commercial-offers="suppressed-default"' in raw_sec
                or "ymyl-public-service-guardrail" in raw_sec
            ):
                return raw_sec
            eff_raw_sec = raw_sec
            if px_inherited_id_attr:
                raw_open_m = re.match(r"<section\b[^>]*>", eff_raw_sec, flags=re.I)
                if raw_open_m and not _extract_section_id_attr(raw_open_m.group(0)):
                    eff_raw_sec = eff_raw_sec.replace("<section", f"<section{px_inherited_id_attr}", 1)
            if px_inherited_reg_drawer and not _extract_partner_registration_drawer(eff_raw_sec):
                eff_raw_sec = re.sub(r"</section>\s*$", f"{px_inherited_reg_drawer}\n</section>", eff_raw_sec, count=1, flags=re.I)
            return _build_prexvo_refinance_section_html(
                raw_sec=eff_raw_sec,
                ordered_offers_or_keys=matrix_cards,
                slug_id=slug_id,
                page_v_fam=roster["vertical_family"],
                lead_pk=lead_pk_val,
                lead_model=lead_model_val,
                models_csv=models_csv,
                roster_keys_csv=roster_keys_csv,
                companies_csv=companies_csv,
                gsc_tier=gsc_tier,
                gsc_repositioned=bool(slot_plan.get("gsc_repositioned")),
            )

        updated = re.sub(
            px_sec_pat,
            _replace_prexvo_sec,
            updated,
            count=1,
            flags=re.S | re.I,
        )
        updated = _strip_remaining_hidden_unapproved_placeholders(updated, px_has_other_hidden)

    # 4. Update #gsc-striking-overlay .overlay-partner-offer if present (any class ordering)
    _ov_partner_sec_re = re.compile(
        r'<section\b[^>]*\bclass=["\'][^"\']*\boverlay-partner-offer\b[^"\']*["\'][^>]*>.*?</section>',
        flags=re.S | re.I,
    )
    if inline_offer and _ov_partner_sec_re.search(updated):
        pk_ov = str(inline_offer["partner_key"])
        safe_ov_name = html_lib.escape(str(inline_offer.get("name") or pk_ov))
        safe_ov_cta = html_lib.escape(str(inline_offer.get("cta_text") or "Explore Partner"))
        safe_ov_disc = html_lib.escape(str(inline_offer.get("disclosure") or ""))
        safe_ov_sub = html_lib.escape(f"{slug_id}_overlay")
        safe_ov_href = html_lib.escape(
            f"/r/{pk_ov}?source_tool={slug_id}&subid={safe_ov_href_sub if False else f'{slug_id}_overlay'}&cta_slot=overlay_primary_cta"
        )
        ov_markup = (
            f'<section class="overlay-section overlay-partner-offer affiliate-cta-section card" '
            f'data-property="{html_lib.escape(prop)}" data-partner="{pk_ov}" '
            f'data-partner-url="/r/{pk_ov}" data-cta-slot="overlay_primary_cta" '
            f'data-cta-id="cta-{html_lib.escape(prop)}-{html_lib.escape(slug_id)}-{pk_ov}" '
            f'data-gsc-tier="{html_lib.escape(gsc_tier)}" data-mechanic="compliant_intent_monetization">\n'
            f'  <h3 class="section-subtitle">Recommended Partner Solution: {safe_ov_name}</h3>\n'
            f'  <p class="affiliate-disclosure" style="font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.75rem;">{safe_ov_disc}</p>\n'
            f'  <a href="{safe_ov_href}" rel="noopener sponsored nofollow" target="_blank" '
            f'class="affiliate-cta affiliate-cta-link partner-btn btn-cta touch-target" data-partner="{pk_ov}" '
            f'data-tool="{html_lib.escape(slug_id)}" data-subid="{safe_ov_sub}" data-cta-slot="overlay_primary_cta" '
            f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 16px; border-radius: 8px; background: var(--accent); color: var(--cta-fg); font-weight: 600; text-decoration: none;">{safe_ov_cta}</a>\n'
            f'</section>'
        )
        updated = _ov_partner_sec_re.sub(ov_markup, updated, count=1)

    has_unapproved_r_in_dom = any(
        m.group(1).strip().lower().replace("-", "_") not in live_vault_keys
        for m in re.finditer(r'href=["\'](?:https?://[^/"\']+)?/r/([a-z0-9_-]+)', updated, flags=re.IGNORECASE)
    )
    callout_skipped = bool(
        skip_callout_if_unchanged
        and updated == html_content
        and not slot_plan.get("gsc_repositioned")
        and not has_unapproved_r_in_dom
    )
    if not callout_skipped:
        updated = normalize_html_callout_message_match(
            updated,
            property_id=prop,
            preserve_promoted_primary=bool(slot_plan.get("gsc_repositioned")),
        )
    elif has_unapproved_r_in_dom:
        updated = strip_unapproved_partner_ctas_from_html(
            updated,
            property_id=prop,
            slug=page_slug,
        )
    after_slots = list(dict.fromkeys(re.findall(r'data-cta-slot=["\']([^"\']+)["\']', updated, flags=re.I)))
    after_primary = str(slot_plan.get("promoted_partner_key") or "")
    if after_primary and after_primary.lower() not in live_vault_keys:
        after_primary = str(matrix_cards[0]["partner_key"]) if matrix_cards else ""

    return updated, {
        "slug": page_slug,
        "property_id": prop,
        "vertical_family": roster["vertical_family"],
        "page_archetype": roster["page_archetype"],
        "commercial_intent": roster["commercial_intent"],
        "restricted_public_service": False,
        "callout_normalized": not callout_skipped,
        "repositioned": bool(updated != html_content or slot_plan.get("gsc_repositioned")),
        "gsc_repositioned": bool(slot_plan.get("gsc_repositioned")),
        "gsc_opportunity_tier": gsc_tier,
        "reposition_reason": slot_plan["reposition_reason"],
        "before_primary_partner": before_primary,
        "after_primary_partner": after_primary,
        "before_slots": before_slots,
        "after_slots": after_slots,
        "roster_keys": roster["roster_keys"],
        "distinct_companies": roster["distinct_companies"],
        "distinct_companies_count": roster["distinct_companies_count"],
        "gsc_impressions": slot_plan["gsc_impressions"],
        "gsc_clicks": slot_plan["gsc_clicks"],
        "gsc_ctr": slot_plan["gsc_ctr"],
        "gsc_position": slot_plan["gsc_position"],
        "gsc_query": slot_plan["gsc_query"],
        "gsc_mobile_impressions": slot_plan.get("gsc_mobile_impressions", 0),
        "gsc_desktop_impressions": slot_plan.get("gsc_desktop_impressions", 0),
        "gsc_mobile_ctr": slot_plan.get("gsc_mobile_ctr", 0.0),
        "gsc_desktop_ctr": slot_plan.get("gsc_desktop_ctr", 0.0),
        "gsc_mobile_ctr_gap": slot_plan.get("gsc_mobile_ctr_gap", 0.0),
        "gsc_device_focus": slot_plan.get("gsc_device_focus", "BALANCED"),
        "gsc_search_appearances": slot_plan.get("gsc_search_appearances", []),
    }


def run_gsc_affiliate_placement_feedback_pass(
    property_id: str = "profithelm",
    dist_dir: Optional[Any] = None,
    repo_root: Optional[Any] = None,
    gsc_rows: Optional[List[Dict[str, Any]]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Executes a closed-loop GSC search signal to affiliate placement optimization pass
    across a tenant property's compiled tool pages.
    Aggregates live GSC query, impression, CTR, and position signals per page,
    binds diversified multi-company partner rosters, repositions conversion slots
    on high-opportunity pages, and writes `.agy/gsc_affiliate_placement_ledger.json`
    (unless `dry_run=True`).
    Zero em-dashes. Zero en-dashes.
    """
    import json
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    raw_prop = "profithelm" if property_id is None else str(property_id)
    prop = raw_prop.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", prop):
        raise ValueError(
            f"Invalid property_id '{property_id}': must match ^[a-z0-9][a-z0-9_-]*$"
        )
    if repo_root is not None:
        r_root = Path(repo_root).resolve()
    elif dist_dir is not None:
        r_root = Path(dist_dir).resolve().parent
    else:
        r_root = Path(
            f"/home/ubuntuadmin/projects/{'prexvo' if prop == 'prexvo' else ('gainhelm' if prop == 'gainhelm' else ('lienbond' if prop == 'lienbond' else 'profithelm-platform'))}"
        )
    d_dir = Path(dist_dir).resolve() if dist_dir is not None else (r_root / "dist")

    multidim_telemetry: Dict[str, Any] = {}
    existing_persisted_gsc: Dict[str, Dict[str, Any]] = {}
    if gsc_rows is None:
        existing_persisted_gsc = load_persisted_gsc_placement_metrics_by_slug(r_root / ".agy", prop)
        try:
            from pseofactory.seo_growth_loops import load_consolidated_gsc_query_rows
            gsc_bundle = load_consolidated_gsc_query_rows(prop, repo_root=r_root, live_gsc=False)
            if isinstance(gsc_bundle.get("multidimensional_telemetry"), dict):
                multidim_telemetry = dict(gsc_bundle.get("multidimensional_telemetry") or {})
            raw_rows = list(
                gsc_bundle.get("current_rows")
                or gsc_bundle.get("snapshot_latest_rows")
                or gsc_bundle.get("baseline_rows")
                or gsc_bundle.get("query_rows")
                or []
            )
            if not raw_rows:
                gsc_bundle_default = load_consolidated_gsc_query_rows(prop, live_gsc=False)
                if not multidim_telemetry and isinstance(gsc_bundle_default.get("multidimensional_telemetry"), dict):
                    multidim_telemetry = dict(gsc_bundle_default.get("multidimensional_telemetry") or {})
                raw_rows = list(
                    gsc_bundle_default.get("current_rows")
                    or gsc_bundle_default.get("snapshot_latest_rows")
                    or gsc_bundle_default.get("baseline_rows")
                    or gsc_bundle_default.get("query_rows")
                    or []
                )
        except Exception:
            raw_rows = []
    else:
        raw_rows = list(gsc_rows)

    if engagement_metrics is None:
        engagement_metrics = load_property_partner_engagement_metrics(r_root / ".agy", prop)

    # Aggregate GSC metrics per tool slug (retaining top query by impressions/striking-distance)
    gsc_by_slug: Dict[str, Dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        r_slug = str(row.get("slug") or "").strip().strip("/").lower()
        if not r_slug:
            r_url = str(row.get("target_url") or row.get("page") or row.get("url") or "").strip()
            if "/tools/" in r_url:
                r_slug = r_url.split("/tools/", 1)[1].split("?")[0].strip("/").lower()
        if not r_slug:
            continue
        impr = int(float(row.get("impressions", 0) or 0))
        clks = int(float(row.get("clicks", 0) or 0))
        pos = float(row.get("position", 0.0) or 0.0)
        q_str = str(row.get("query") or "").strip()
        mob_impr = int(float(row.get("mobile_impressions", 0) or 0))
        desk_impr = int(float(row.get("desktop_impressions", 0) or 0))
        mob_ctr = float(row.get("mobile_ctr", 0.0) or 0.0)
        desk_ctr = float(row.get("desktop_ctr", 0.0) or 0.0)
        sa_list = list(row.get("search_appearances") or [])

        bucket = gsc_by_slug.setdefault(
            r_slug,
            {
                "slug": r_slug,
                "impressions": 0,
                "clicks": 0,
                "mobile_impressions": 0,
                "desktop_impressions": 0,
                "_mob_weighted_ctr": 0.0,
                "_desk_weighted_ctr": 0.0,
                "_weighted_pos": 0.0,
                "_top_query_impr": -1,
                "query": "",
                "search_appearances": [],
            },
        )
        bucket["impressions"] += impr
        bucket["clicks"] += clks
        bucket["mobile_impressions"] += mob_impr
        bucket["desktop_impressions"] += desk_impr
        if mob_impr > 0:
            bucket["_mob_weighted_ctr"] += mob_ctr * mob_impr
        if desk_impr > 0:
            bucket["_desk_weighted_ctr"] += desk_ctr * desk_impr
        for sa in sa_list:
            if sa and sa not in bucket["search_appearances"]:
                bucket["search_appearances"].append(sa)
        if impr > 0 and pos > 0.0:
            bucket["_weighted_pos"] += pos * impr
        if q_str and impr > bucket["_top_query_impr"]:
            bucket["_top_query_impr"] = impr
            bucket["query"] = q_str

    for b in gsc_by_slug.values():
        tot_i = int(b["impressions"])
        tot_c = int(b["clicks"])
        m_i = int(b["mobile_impressions"])
        d_i = int(b["desktop_impressions"])
        b["ctr"] = round(tot_c / float(tot_i), 4) if tot_i > 0 else 0.0
        b["position"] = round(float(b["_weighted_pos"]) / float(tot_i), 2) if tot_i > 0 and b["_weighted_pos"] > 0 else 0.0
        b["mobile_ctr"] = round(float(b["_mob_weighted_ctr"]) / float(m_i), 4) if m_i > 0 else 0.0
        b["desktop_ctr"] = round(float(b["_desk_weighted_ctr"]) / float(d_i), 4) if d_i > 0 else 0.0
        b["mobile_ctr_gap"] = round(b["desktop_ctr"] - b["mobile_ctr"], 4)
        b["device_focus"] = (
            "MOBILE_CTR_DEFICIT"
            if (m_i >= 5 and b["mobile_ctr_gap"] >= 0.01)
            else ("MOBILE_DOMINANT" if (m_i > d_i and m_i >= 5) else "BALANCED")
        )
        b.pop("_weighted_pos", None)
        b.pop("_top_query_impr", None)
        b.pop("_mob_weighted_ctr", None)
        b.pop("_desk_weighted_ctr", None)

    if gsc_rows is None:
        # Hydrate slugs missing from query rows using locally persisted GSC multidimensional
        # telemetry (.agy/gsc_lifecycle_telemetry.json) so offline/worktree passes preserve real
        # page-level impressions, device splits, and top queries without requiring statutory.db.
        if multidim_telemetry:
            top_query_by_slug: Dict[str, Tuple[int, str]] = {}
            qpds = multidim_telemetry.get("query_page_device_splits")
            if isinstance(qpds, dict):
                for qp_key, dev_map in qpds.items():
                    if "::" not in str(qp_key) or not isinstance(dev_map, dict):
                        continue
                    p_part, q_part = str(qp_key).split("::", 1)
                    if "/tools/" not in p_part:
                        continue
                    q_slug = p_part.split("/tools/", 1)[1].split("?")[0].strip("/").lower()
                    if not q_slug:
                        continue
                    q_impr = sum(
                        int(float((dv or {}).get("impressions", 0) or 0))
                        for dv in dev_map.values()
                        if isinstance(dv, dict)
                    )
                    prev_best = top_query_by_slug.get(q_slug)
                    if q_part.strip() and (prev_best is None or q_impr > prev_best[0]):
                        top_query_by_slug[q_slug] = (q_impr, q_part.strip())

            p_windows = multidim_telemetry.get("page_windows_by_path")
            if isinstance(p_windows, dict):
                for p_path, w_map in p_windows.items():
                    if "/tools/" not in str(p_path) or not isinstance(w_map, dict):
                        continue
                    w_slug = str(p_path).split("/tools/", 1)[1].split("?")[0].strip("/").lower()
                    if not w_slug:
                        continue
                    win_block = w_map.get("recent_90d") or w_map.get("recent_28d") or {}
                    rolled = (
                        win_block.get("rolled_up")
                        or win_block.get("direct")
                        or (win_block if isinstance(win_block, dict) else {})
                    )
                    if not isinstance(rolled, dict):
                        continue
                    w_impr = int(float(rolled.get("impressions", 0) or 0))
                    w_clks = int(float(rolled.get("clicks", 0) or 0))
                    w_ctr = float(rolled.get("ctr", 0.0) or 0.0)
                    w_pos = float(rolled.get("position", 0.0) or 0.0)
                    if w_impr <= 0:
                        continue
                    cur = gsc_by_slug.get(w_slug)
                    if cur is None or int(cur.get("impressions", 0) or 0) < w_impr:
                        best_q = (cur or {}).get("query") or (top_query_by_slug.get(w_slug) or (0, ""))[1]
                        gsc_by_slug[w_slug] = {
                            "slug": w_slug,
                            "impressions": w_impr,
                            "clicks": max(w_clks, int((cur or {}).get("clicks", 0) or 0)),
                            "ctr": w_ctr if w_impr > 0 else float((cur or {}).get("ctr", 0.0) or 0.0),
                            "position": w_pos if w_pos > 0.0 else float((cur or {}).get("position", 0.0) or 0.0),
                            "query": best_q,
                            "mobile_impressions": int((cur or {}).get("mobile_impressions", 0) or 0),
                            "desktop_impressions": int((cur or {}).get("desktop_impressions", 0) or 0),
                            "mobile_ctr": float((cur or {}).get("mobile_ctr", 0.0) or 0.0),
                            "desktop_ctr": float((cur or {}).get("desktop_ctr", 0.0) or 0.0),
                            "mobile_ctr_gap": float((cur or {}).get("mobile_ctr_gap", 0.0) or 0.0),
                            "device_focus": str((cur or {}).get("device_focus") or "BALANCED"),
                            "search_appearances": list((cur or {}).get("search_appearances") or []),
                        }

            p_dev = multidim_telemetry.get("page_device_diagnostics")
            if isinstance(p_dev, dict):
                for p_path, d_info in p_dev.items():
                    if "/tools/" not in str(p_path) or not isinstance(d_info, dict):
                        continue
                    d_slug = str(p_path).split("/tools/", 1)[1].split("?")[0].strip("/").lower()
                    if not d_slug or d_slug not in gsc_by_slug:
                        continue
                    cur = gsc_by_slug[d_slug]
                    if int(cur.get("mobile_impressions", 0) or 0) == 0 and int(cur.get("desktop_impressions", 0) or 0) == 0:
                        m_im = int(float(d_info.get("mobile_impressions", 0) or 0))
                        d_im = int(float(d_info.get("desktop_impressions", 0) or 0))
                        cur["mobile_impressions"] = m_im
                        cur["desktop_impressions"] = d_im
                        cur["mobile_ctr"] = float(d_info.get("mobile_ctr", 0.0) or 0.0)
                        cur["desktop_ctr"] = float(d_info.get("desktop_ctr", 0.0) or 0.0)
                        cur["mobile_ctr_gap"] = float(d_info.get("mobile_ctr_gap", 0.0) or 0.0)
                        if d_info.get("device_focus"):
                            cur["device_focus"] = str(d_info["device_focus"])

        # Preserve prior persisted slug metrics for any slug still absent after offline hydration
        for p_slug, p_metrics in existing_persisted_gsc.items():
            if not isinstance(p_metrics, dict):
                continue
            p_impr = int(p_metrics.get("impressions", 0) or 0)
            if p_impr <= 0:
                continue
            cur = gsc_by_slug.get(p_slug)
            if cur is None or int(cur.get("impressions", 0) or 0) == 0:
                gsc_by_slug[p_slug] = dict(p_metrics)

    tools_dir = d_dir / "tools"
    page_reports: List[Dict[str, Any]] = []
    repositioned_pages: List[Dict[str, Any]] = []
    pages_scanned = 0
    pages_updated = 0

    if tools_dir.is_dir():
        for html_file in sorted(tools_dir.rglob("index.html")):
            rel_slug = html_file.parent.relative_to(tools_dir).as_posix().strip("/")
            if not rel_slug or rel_slug == ".":
                continue
            try:
                raw_html = html_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            pages_scanned += 1
            slug_gsc = gsc_by_slug.get(rel_slug) or gsc_by_slug.get(rel_slug.replace("/", "-")) or {}
            updated_html, rep = reposition_affiliate_placements_from_gsc_signals(
                raw_html,
                property_id=prop,
                slug=rel_slug,
                query=str(slug_gsc.get("query") or ""),
                gsc_metrics=slug_gsc,
                engagement_metrics=engagement_metrics,
            )
            if updated_html != raw_html:
                try:
                    from pseofactory.maintenance import normalize_html_visual_primitives
                    norm_h, _ = normalize_html_visual_primitives(updated_html, is_tenant_porcelain=True)
                    if norm_h:
                        updated_html = norm_h
                except Exception:
                    pass
            page_reports.append(rep)
            if rep.get("repositioned") or updated_html != raw_html:
                repositioned_pages.append(rep)
                if not dry_run and updated_html != raw_html:
                    html_file.write_text(updated_html, encoding="utf-8")
                    pages_updated += 1

    summary = {
        "workflow": "gsc_affiliate_placement_feedback_pass",
        "property_id": prop,
        "dry_run": bool(dry_run),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pages_scanned": pages_scanned,
        "pages_updated": pages_updated,
        "gsc_signal_slugs_count": len(gsc_by_slug),
        "repositioned_pages_count": len(repositioned_pages),
        "repositioned_pages": repositioned_pages,
        "page_reports": page_reports,
    }

    if not dry_run and r_root.is_dir():
        workspace_root = Path("/home/ubuntuadmin/projects").resolve()
        resolved_root = r_root.resolve()
        in_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        is_workspace_root = resolved_root == workspace_root
        is_under_workspace = (
            resolved_root == workspace_root
            or workspace_root in resolved_root.parents
        )
        if is_workspace_root:
            raise ValueError(
                f"Refusing to write gsc_affiliate_placement_ledger.json to workspace root: {resolved_root}"
            )
        if in_pytest and is_under_workspace:
            raise ValueError(
                f"Refusing to write gsc_affiliate_placement_ledger.json inside workspace during pytest: {resolved_root}"
            )
        ledger_path = resolved_root / ".agy" / "gsc_affiliate_placement_ledger.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return summary


def audit_partnership_model_coverage(
    property_id: Optional[str] = None,
    dist_dir: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Audits partnership model coverage across:
      1. Canonical partnership structures (`RECURRING_SAAS_REVSHARE`, `CPA_BOUNTY`,
         `QUALIFIED_LEAD_CPL`, `HYBRID_CPA_REVSHARE`, `USAGE_API_REFERRAL`).
      2. Registered partners in `PROFITHELM_AFFILIATES` and `PREXVO_AFFILIATES` plus
         `PARTNER_PARTNERSHIP_MODEL_SPECS` and `GREENFIELD_VERTICAL_CATALOG`.
      3. All 23 vertical families in `VERTICAL_DIVERSIFIED_PARTNER_ROSTERS`.
      4. Optionally, compiled HTML pages in `dist_dir` (checking `data-partnership-model`
         and `data-partner-models`).
    Zero em-dashes. Zero en-dashes.
    """
    from pathlib import Path

    prop_filter = (property_id or "").strip().lower()
    if prop_filter == "all":
        prop_filter = ""
    if prop_filter in ("profithelm", "exchange1031"):
        target_registries = [("profithelm", PROFITHELM_AFFILIATES)]
    elif prop_filter and prop_filter in AFFILIATE_REGISTRY_BY_PROPERTY:
        target_registries = [(prop_filter, AFFILIATE_REGISTRY_BY_PROPERTY[prop_filter])]
    else:
        target_registries = list(AFFILIATE_REGISTRY_BY_PROPERTY.items())

    models_to_partners: Dict[str, List[str]] = {m: [] for m in CANONICAL_PARTNERSHIP_MODELS}
    partner_model_map: Dict[str, str] = {}

    for _prop, reg_dict in target_registries:
        for pk, p_obj in reg_dict.items():
            if pk != p_obj.key:
                continue
            mod = str(p_obj.partnership_model or resolve_partnership_model_spec(pk, p_obj)["partnership_model"])
            partner_model_map[pk] = mod
            if mod in models_to_partners and pk not in models_to_partners[mod]:
                models_to_partners[mod].append(pk)

    if not prop_filter:
        for pk, spec in PARTNER_PARTNERSHIP_MODEL_SPECS.items():
            mod = str(spec.get("partnership_model") or "")
            if mod in models_to_partners and pk not in models_to_partners[mod]:
                models_to_partners[mod].append(pk)

    vertical_coverage: Dict[str, Dict[str, Any]] = {}
    for v_fam in VERTICAL_DIVERSIFIED_PARTNER_ROSTERS:
        if v_fam == "student_loan_refinancing":
            v_prop = "prexvo"
        elif v_fam in ("b2b_cyber_compliance", "cyber_compliance_grc") and prop_filter == "gainhelm":
            v_prop = "gainhelm"
        elif v_fam in (
            "surety_bond_compliance",
            "workers_comp_labor_burden",
            "construction_contractor_finance",
        ) and prop_filter == "lienbond":
            v_prop = "lienbond"
        else:
            v_prop = "profithelm"
        if prop_filter and prop_filter != v_prop:
            continue
        roster = bind_asset_partner_roster(
            property_id=v_prop,
            slug=f"{v_fam.replace('_', '-')}-calculator",
            query=v_fam.replace("_", " "),
        )
        vertical_coverage[v_fam] = {
            "property_id": v_prop,
            "primary_partner": roster["primary_offer"]["partner_key"] if roster.get("primary_offer") else "",
            "primary_partnership_model": roster.get("primary_partnership_model", ""),
            "partnership_models_represented": roster.get("partnership_models_represented", []),
            "roster_keys": roster.get("roster_keys", []),
            "distinct_companies_count": roster.get("distinct_companies_count", 0),
        }

    dom_pages_checked = 0
    dom_commercial_pages_with_model_attr = 0
    dom_models_observed: Set[str] = set()
    if dist_dir is not None:
        d_path = Path(dist_dir)
        tools_dir = d_path / "tools" if (d_path / "tools").is_dir() else d_path
        if tools_dir.is_dir():
            for hf in sorted(tools_dir.rglob("index.html")):
                try:
                    html = hf.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if 'data-restricted-public-service="true"' in html or "ymyl-public-service-guardrail" in html:
                    continue
                dom_pages_checked += 1
                mods = re.findall(r'data-partnership-model=["\']([A-Z0-9_]+)["\']', html)
                if mods:
                    dom_commercial_pages_with_model_attr += 1
                    dom_models_observed.update(mods)

    missing_canonical_models = [
        m for m in CANONICAL_PARTNERSHIP_MODELS if len(models_to_partners.get(m, [])) == 0
    ]

    return {
        "status": "PASS" if (not prop_filter and len(missing_canonical_models) == 0) or (prop_filter and len(partner_model_map) > 0) else "FAIL",
        "property_filter": prop_filter or "all",
        "canonical_partnership_models": list(CANONICAL_PARTNERSHIP_MODELS),
        "models_to_partners": models_to_partners,
        "missing_canonical_models": missing_canonical_models,
        "all_5_models_supported": len(missing_canonical_models) == 0,
        "verticals_audited_count": len(vertical_coverage),
        "vertical_coverage": vertical_coverage,
        "dom_pages_checked": dom_pages_checked,
        "dom_commercial_pages_with_model_attr": dom_commercial_pages_with_model_attr,
        "dom_models_observed": sorted(dom_models_observed),
    }



# Self-attestation on module import
for _p_dict in (PROFITHELM_AFFILIATES, PREXVO_AFFILIATES, GAINHELM_AFFILIATES, LIENBOND_AFFILIATES):
    for _p_key, _p_val in _p_dict.items():
        assert_no_forbidden_dashes(_p_val.name, context=f"Affiliate name {_p_key}")
        assert_no_forbidden_dashes(_p_val.description, context=f"Affiliate description {_p_key}")
        assert_no_forbidden_dashes(_p_val.badge, context=f"Affiliate badge {_p_key}")
        assert_no_forbidden_dashes(_p_val.commission_est, context=f"Affiliate commission_est {_p_key}")
        assert_no_forbidden_dashes(_p_val.bounty_est, context=f"Affiliate bounty_est {_p_key}")
        assert_no_forbidden_dashes(_p_val.cta_text, context=f"Affiliate cta_text {_p_key}")
        if not validate_affiliate_url(_p_val.default_url):
            raise ValueError(f"Default URL invalid for partner {_p_key}: {_p_val.default_url}")

for _d_dict in (PROFITHELM_DISCLOSURES, PREXVO_DISCLOSURES, GAINHELM_DISCLOSURES, LIENBOND_DISCLOSURES):
    for _d_key, _d_text in _d_dict.items():
        assert_no_forbidden_dashes(_d_text, context=f"Disclosure {_d_key}")

assert_no_forbidden_dashes(PREXVO_STANDING_RESTRICTION, context="Prexvo standing restriction")

