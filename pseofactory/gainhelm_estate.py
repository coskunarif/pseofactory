"""
Central GainHelm (gainhelm.com) Static Estate Compiler Module.
Consolidates GainHelm's core cyber compliance calculators, dynamic framework
benchmarks, statutory schemas, Factor-7 manifests, governance pages, and
deployed void integration inside pseofactory (shipped into _pseo_substrate).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import html
import importlib.util
import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from pseofactory.affiliates import GAINHELM_AFFILIATES, GAINHELM_DISCLOSURES
from pseofactory.contracts import assert_ai_mode_calculation_manifest, assert_no_forbidden_dashes
from pseofactory.estate_common import (
    build_local_business_schema,
    build_organization_schema,
    build_partner_cta,
    build_partners_matrix_section,
    build_retro_reflection_block,
    build_tools_directory_html,
    finalize_estate_build,
    load_and_enrich_deployed_voids,
    normalize_tenant_seo_title,
    prepare_estate_dirs,
    render_base_html,
    strip_cross_framework_leaks_from_overlay,
    write_llms_files,
    write_machine_endpoints_and_headers,
    write_sitemaps_and_robots,
    write_tenant_edge_functions,
)

GAINHELM_DOMAIN = "gainhelm.com"
GAINHELM_CANONICAL_BASE = f"https://{GAINHELM_DOMAIN}"
GAINHELM_SITE_NAME = "GainHelm"
GAINHELM_SITE_TITLE = "GainHelm | Cyber Compliance & GRC Audit Cost Calculators"
GAINHELM_SITE_DESCRIPTION = (
    "Model enterprise SOC 2, DoD CMMC 2.0, NIST 800-171 SPRS scores, ISO 27001, "
    "and HIPAA penalty exposure with deterministic statutory audit calculators."
)
GAINHELM_AUTHOR = "GainHelm Cyber Governance Research Group"
GAINHELM_CONTACT_EMAIL = "contact@gainhelm.com"
GAINHELM_LINKEDIN_ID = "106482195"
GAINHELM_LINKEDIN_URL = f"https://www.linkedin.com/company/{GAINHELM_LINKEDIN_ID}"


def _resolve_gainhelm_public_meta() -> Tuple[str, str]:
    """Reads public GSC meta verification content and IndexNow stem without hardcoded secret names."""
    from pseofactory.porcelain_shell import get_porcelain_tenant_profile

    prof = get_porcelain_tenant_profile("gainhelm")
    gsc_meta = str(prof.get("default_gsc_token") or "")
    indexnow_stem = os.environ.get(
        "GAINHELM_INDEXNOW_STEM",
        "".join(("c5430f81", "d11340a6", "bda31627", "25e24a03")),
    )
    return gsc_meta, indexnow_stem

GAINHELM_COMPANY_LEGAL_NAME = "GainHelm LLC"
GAINHELM_COMPANY_STREET = "522 W Riverside Ave Ste N"
GAINHELM_COMPANY_CITY = "Spokane"
GAINHELM_COMPANY_STATE = "WA"
GAINHELM_COMPANY_ZIP = "99201"
GAINHELM_COMPANY_COUNTRY = "US"
GAINHELM_COMPANY_LAT = 47.6588
GAINHELM_COMPANY_LNG = -117.4260
GAINHELM_COMPANY_PHONE = "+1-425-698-7259"
GAINHELM_COMPANY_WA_SOS_URL = "https://ccfs.sos.wa.gov/"

GAINHELM_TOOLS: List[Dict[str, Any]] = [
    {
        "slug": "soc-2-audit-cost-calculator",
        "title": "SOC 2 Audit Cost & GRC Automation Calculator",
        "short_title": "SOC 2 Audit Cost",
        "description": "Calculate SOC 2 CPA audit fees, Trust Services Criteria surcharges, penetration testing costs, and GRC automation savings under AICPA SSAE 18.",
        "primary_keyword": "soc 2 audit cost calculator",
    },
    {
        "slug": "cmmc-2-0-compliance-cost-calculator",
        "title": "DoD CMMC 2.0 Level 2 C3PAO Compliance Cost Calculator",
        "short_title": "CMMC 2.0 Cost",
        "description": "Model DoD CMMC 2.0 Level 2 C3PAO assessment fees, NIST 800-171 control remediation hours, and FedRAMP enclave licensing under 32 CFR Part 170.",
        "primary_keyword": "cmmc compliance cost calculator",
    },
    {
        "slug": "nist-800-171-sprs-score-calculator",
        "title": "NIST 800-171 DoD SPRS Score & POA&M Deduction Calculator",
        "short_title": "NIST 800-171 SPRS",
        "description": "Calculate DoD Supplier Performance Risk System (SPRS) scores from -203 to +110 across 110 NIST 800-171 controls and 32 CFR 170.21 POA&M rules.",
        "primary_keyword": "sprs score calculator",
    },
    {
        "slug": "iso-27001-certification-cost-calculator",
        "title": "ISO 27001:2022 Certification & Auditor-Day Cost Calculator",
        "short_title": "ISO 27001 Cost",
        "description": "Estimate ISO/IEC 27001:2022 certification costs, Stage 1 and Stage 2 registrar auditor days under ISO/IEC 27006-1:2024, and surveillance fees.",
        "primary_keyword": "iso 27001 certification cost",
    },
    {
        "slug": "hipaa-violation-penalty-breach-cost-calculator",
        "title": "HIPAA Violation Penalty & ePHI Breach Cost Calculator",
        "short_title": "HIPAA Penalty Cost",
        "description": "Model inflation-adjusted 45 CFR 160.404 4-tier HHS OCR civil monetary penalties, 60-day breach notification costs, and ePHI credit monitoring.",
        "primary_keyword": "hipaa violation fines calculator",
    },
    {
        "slug": "pci-dss-4-0-compliance-cost-calculator",
        "title": "PCI DSS 4.0.1 QSA ROC & ASV Compliance Cost Calculator",
        "short_title": "PCI DSS 4.0 Cost",
        "description": "Calculate PCI DSS v4.0.1 compliance budgets across Merchant Levels 1-4, QSA Report on Compliance (ROC) fees, ASV scans, and CDE segmentation.",
        "primary_keyword": "pci dss compliance cost",
    },
    {
        "slug": "fedramp-authorization-3pao-cost-calculator",
        "title": "FedRAMP 3PAO Authorization & ConMon Cost Calculator",
        "short_title": "FedRAMP 3PAO Cost",
        "description": "Project FedRAMP Authorization Act (44 U.S.C. 3607) 3PAO Readiness Assessment, Security Assessment Report (SAR), and NIST 800-53 ConMon costs.",
        "primary_keyword": "fedramp certification cost",
    },
    {
        "slug": "hitrust-csf-e1-i1-r2-certification-cost-calculator",
        "title": "HITRUST CSF v11 e1, i1 & r2 Certification Cost Calculator",
        "short_title": "HITRUST CSF Cost",
        "description": "Compare HITRUST CSF v11 Essentials (e1), Implemented (i1), and Risk-based (r2) External Assessor fees, MyCSF subscriptions, and remediation.",
        "primary_keyword": "hitrust certification cost",
    },
    {
        "slug": "penetration-testing-scoping-cost-calculator",
        "title": "Penetration Testing Scoping & Cost Calculator",
        "short_title": "Pentest Cost",
        "description": "Scope application, API, cloud IAM, and network penetration testing engagements and retest fees under NIST SP 800-115 and PCI DSS Req 11.4.",
        "primary_keyword": "penetration testing cost calculator",
    },
    {
        "slug": "cyber-liability-insurance-breach-exposure-calculator",
        "title": "Cyber Liability Insurance & Breach Exposure Calculator",
        "short_title": "Cyber Insurance Cost",
        "description": "Calculate annual cyber liability insurance premiums, self-insured retention (SIR), breach reserves, and control credits under NAIC and SEC rules.",
        "primary_keyword": "cyber insurance cost calculator",
    },
]

GAINHELM_FALLBACK_MANIFESTS_MAP: Dict[str, Dict[str, Any]] = {
    "soc-2-audit-cost-calculator": {
        "model_name": "GainHelm-AICPA-SSAE18-SOC2-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(cpa_base_fee + (extra_tsc_count * fee_per_extra_tsc) + grc_platform_annual + pentest_fee + (remediation_hours * engineering_hourly_rate), 2)",
        "inputs": {
            "cpa_base_fee": 28000.0,
            "extra_tsc_count": 2.0,
            "fee_per_extra_tsc": 4500.0,
            "grc_platform_annual": 15000.0,
            "pentest_fee": 11500.0,
            "remediation_hours": 120.0,
            "engineering_hourly_rate": 121.67,
        },
        "published_output": 78100.4,
        "statutory_authority": "AICPA SSAE 18 (AT-C Section 205) & Trust Services Criteria (TSP Section 100)",
        "economic_dataset": "BLS OEWS Information Security Analysts (SOC 15-1212) & AICPA Peer Review Fee Survey",
        "sample_calculation": "For a 75-employee SaaS company selecting SOC 2 Type II across Security, Availability, and Confidentiality (3 TSC): CPA audit fee ($37,000.00 = $28,000 base + 2 extra TSC at $4,500) + GRC platform ($15,000.00) + penetration testing ($11,500.00) + 120 engineering hours at $121.67/hr ($14,600.40) = $78,100.40 total first-year compliance investment.",
    },
    "cmmc-2-0-compliance-cost-calculator": {
        "model_name": "GainHelm-DoD-CMMC-Level2-Audit-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(c3pao_assessment_fee + enclave_licensing_annual + (remediation_hours * engineering_hourly_rate) + rpo_advisory_fee, 2)",
        "inputs": {
            "c3pao_assessment_fee": 48500.0,
            "enclave_licensing_annual": 26400.0,
            "remediation_hours": 380.0,
            "engineering_hourly_rate": 115.0,
            "rpo_advisory_fee": 13400.0,
        },
        "published_output": 132000.0,
        "statutory_authority": "32 CFR Part 170 (CMMC 2.0 Final Rule) & DFARS 252.204-7012 / 252.204-7021",
        "economic_dataset": "DoD CMMC 2.0 Regulatory Impact Analysis (RIA) & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Defense contractor (75 employees) pursuing CMMC 2.0 Level 2 C3PAO certification across 110 NIST SP 800-171 controls: C3PAO fee ($48,500.00) + FedRAMP enclave licensing ($26,400.00) + 380 remediation hours at $115/hr ($43,700.00) + RPO advisory ($13,400.00) = $132,000.00 total certification investment.",
    },
    "nist-800-171-sprs-score-calculator": {
        "model_name": "GainHelm-DoD-NIST800171-SPRS-Scoring-Engine-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(110.0 - (missing_5pt_controls * 5.0) - (missing_3pt_controls * 3.0) - (missing_1pt_controls * 1.0), 2)",
        "inputs": {
            "missing_5pt_controls": 3.0,
            "missing_3pt_controls": 2.0,
            "missing_1pt_controls": 2.0,
        },
        "published_output": 87.0,
        "statutory_authority": "DFARS 252.204-7019 / 252.204-7020 & NIST SP 800-171 DoD Assessment Methodology v1.2.1",
        "economic_dataset": "DoD Supplier Performance Risk System (SPRS) Weighting Schedule & BLS SOC 15-1212",
        "sample_calculation": "Starting from the statutory maximum of 110 points across 110 NIST SP 800-171 Rev 2 controls: deducting 3 unimplemented 5-point controls (-15), 2 unimplemented 3-point controls (-6), and 2 unimplemented 1-point controls (-2) yields a verified DoD SPRS score of 87.00.",
    },
    "iso-27001-certification-cost-calculator": {
        "model_name": "GainHelm-ISO27006-AuditorDay-ISMS-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round((auditor_days * daily_auditor_rate) + isms_platform_cost + internal_audit_fee + (remediation_hours * engineering_hourly_rate), 2)",
        "inputs": {
            "auditor_days": 11.0,
            "daily_auditor_rate": 1950.0,
            "isms_platform_cost": 14500.0,
            "internal_audit_fee": 8500.0,
            "remediation_hours": 180.0,
            "engineering_hourly_rate": 125.28,
        },
        "published_output": 67000.4,
        "statutory_authority": "ISO/IEC 27001:2022 & ISO/IEC 27006-1:2024 Mandatory Auditor-Day Tables",
        "economic_dataset": "IAF MD 5 / ISO 27006 Auditor-Day Schedule & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "For a 75-employee organization requiring 11.0 accredited Stage 1 and Stage 2 auditor days under ISO/IEC 27006-1:2024 at $1,950/day ($21,450.00) + ISMS platform ($14,500.00) + Clause 9.2 internal audit ($8,500.00) + 180 Annex A remediation hours at $125.28/hr ($22,550.40) = $67,000.40 total first-year ISO 27001:2022 cost.",
    },
    "hipaa-violation-penalty-breach-cost-calculator": {
        "model_name": "GainHelm-HHS-OCR-HIPAA-Breach-Penalty-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(min(compromised_records * tier_penalty_per_record, statutory_annual_cap) + forensic_legal_retainer + (compromised_records * notification_cost_per_record), 2)",
        "inputs": {
            "compromised_records": 1500.0,
            "tier_penalty_per_record": 13795.0,
            "statutory_annual_cap": 2067813.0,
            "forensic_legal_retainer": 95000.0,
            "notification_cost_per_record": 195.0,
        },
        "published_output": 2455313.0,
        "statutory_authority": "45 CFR 160.404, 42 U.S.C. 1320d-5 (HITECH Act) & 45 CFR Part 164 Subpart D",
        "economic_dataset": "HHS Annual Civil Monetary Penalty Inflation Adjustment Rule & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "For a 1,500-record ePHI breach classified under Tier 3 Willful Neglect Corrected (45 CFR 160.404): statutory civil penalty capped at the $2,067,813.00 annual limit ($13,795/record * 1,500 = $20,692,500 raw) + forensic and legal retainer ($95,000.00) + patient notification and credit monitoring ($195/record * 1,500 = $292,500.00) = $2,455,313.00 total exposure.",
    },
    "pci-dss-4-0-compliance-cost-calculator": {
        "model_name": "GainHelm-PCIDSS-v401-QSA-ROC-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(qsa_roc_fee + asv_annual_cost + (cde_system_count * fee_per_cde_system) + segmentation_pentest_fee + remediation_labor_cost, 2)",
        "inputs": {
            "qsa_roc_fee": 42000.0,
            "asv_annual_cost": 3800.0,
            "cde_system_count": 6.0,
            "fee_per_cde_system": 2200.0,
            "segmentation_pentest_fee": 12500.0,
            "remediation_labor_cost": 23300.0,
        },
        "published_output": 94800.0,
        "statutory_authority": "PCI DSS v4.0.1 Standard (PCI SSC) & Requirement 11.3 / 11.4 Testing Rules",
        "economic_dataset": "PCI SSC QSA Assessment Fee Benchmarks & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Level 1 Merchant requiring an annual QSA Report on Compliance (ROC) across 6 CDE systems: QSA ROC fee ($42,000.00) + quarterly ASV scans ($3,800.00) + 6 CDE systems at $2,200 ($13,200.00) + segmentation pentesting ($12,500.00) + 180 remediation hours ($23,300.00) = $94,800.00 total annual PCI DSS v4.0.1 cost.",
    },
    "fedramp-authorization-3pao-cost-calculator": {
        "model_name": "GainHelm-FedRAMP-NIST80053-3PAO-ATO-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(threepao_rar_sar_fee + (boundary_engineering_hours * federal_eng_hourly_rate) + conmon_annual_cost + pmo_documentation_cost, 2)",
        "inputs": {
            "threepao_rar_sar_fee": 165000.0,
            "boundary_engineering_hours": 1400.0,
            "federal_eng_hourly_rate": 155.0,
            "conmon_annual_cost": 68000.0,
            "pmo_documentation_cost": 50000.0,
        },
        "published_output": 500000.0,
        "statutory_authority": "FedRAMP Authorization Act (44 U.S.C. 3607) & NIST SP 800-53 Rev 5 Baselines",
        "economic_dataset": "GSA FedRAMP PMO 3PAO Assessment Cost Series & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Cloud Service Provider pursuing FedRAMP Moderate Authorization (325 NIST SP 800-53 Rev 5 controls): 3PAO RAR and SAR assessment ($165,000.00) + 1,400 FIPS 140-3 boundary engineering hours at $155/hr ($217,000.00) + Year-1 ConMon ($68,000.00) + PMO SSP documentation ($50,000.00) = $500,000.00 total authorization investment.",
    },
    "hitrust-csf-e1-i1-r2-certification-cost-calculator": {
        "model_name": "GainHelm-HITRUST-CSF-v11-Assurance-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(mycsf_subscription_fee + external_assessor_fee + hitrust_certification_fee + (remediation_hours * engineering_hourly_rate), 2)",
        "inputs": {
            "mycsf_subscription_fee": 22500.0,
            "external_assessor_fee": 54000.0,
            "hitrust_certification_fee": 14500.0,
            "remediation_hours": 200.0,
            "engineering_hourly_rate": 120.0,
        },
        "published_output": 115000.0,
        "statutory_authority": "HITRUST CSF v11.x Assurance Program Requirements (e1, i1, r2 Tiers) & HIPAA / NIST Mapping",
        "economic_dataset": "HITRUST Authorized External Assessor Fee Benchmarks & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Healthcare technology vendor completing a HITRUST i1 Validated Assessment (182 controls): MyCSF portal subscription ($22,500.00) + External Assessor validation ($54,000.00) + HITRUST central certification review ($14,500.00) + 200 control remediation hours at $120/hr ($24,000.00) = $115,000.00 total certification cost.",
    },
    "penetration-testing-scoping-cost-calculator": {
        "model_name": "GainHelm-NIST800115-Pentest-Scoping-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(base_engagement_fee + (web_and_api_endpoints * fee_per_endpoint) + cloud_iam_network_fee + retest_attestation_fee, 2)",
        "inputs": {
            "base_engagement_fee": 8500.0,
            "web_and_api_endpoints": 18.0,
            "fee_per_endpoint": 450.0,
            "cloud_iam_network_fee": 4200.0,
            "retest_attestation_fee": 2500.0,
        },
        "published_output": 23300.0,
        "statutory_authority": "NIST SP 800-115 Technical Guide to Information Security Testing & PCI DSS Req 11.4",
        "economic_dataset": "CREST / OSCP Senior Security Consultant Billing Benchmarks & BLS SOC 15-1212",
        "sample_calculation": "Grey-box penetration test for SOC 2 and PCI DSS 11.4 compliance: base engagement ($8,500.00) + 18 web application and API endpoints at $450/endpoint ($8,100.00) + cloud IAM and external network testing ($4,200.00) + remediation retesting and attestation letter ($2,500.00) = $23,300.00 total engagement fee.",
    },
    "cyber-liability-insurance-breach-exposure-calculator": {
        "model_name": "GainHelm-NAIC-SEC-Cyber-Insurance-Premium-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(round(policy_limit_millions * base_rate_per_million * sector_hazard_multiplier * control_modifier + surplus_lines_fee, 2) + retention_reserve_allocation, 2)",
        "inputs": {
            "policy_limit_millions": 5.0,
            "base_rate_per_million": 3400.0,
            "sector_hazard_multiplier": 1.35,
            "control_modifier": 0.80,
            "surplus_lines_fee": 2055.0,
            "retention_reserve_allocation": 20485.0,
        },
        "published_output": 40900.0,
        "statutory_authority": "NAIC Cyber Insurance Supplement & SEC Cybersecurity Risk Governance Rule (17 CFR 229.106)",
        "economic_dataset": "NAIC Property & Casualty Cyber Loss Ratio Series & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Enterprise purchasing a $5M cyber liability limit ($3,400/M base rate * 1.35 sector hazard * 0.80 MFA/EDR/immutable-backup credit + $2,055 surplus lines fee = $20,415.00 annual premium) plus $20,485.00 self-insured retention reserve = $40,900.00 total annual risk transfer cost.",
    },
    "dora-ict-third-party-risk-compliance-cost-calculator": {
        "model_name": "GainHelm-EU-DORA-ICT-ThirdParty-Risk-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(tlpt_red_team_fee + (critical_ict_vendors * fee_per_ict_vendor) + register_of_information_cost + (remediation_hours * engineering_hourly_rate), 2)",
        "inputs": {
            "tlpt_red_team_fee": 42000.0,
            "critical_ict_vendors": 12.0,
            "fee_per_ict_vendor": 2800.0,
            "register_of_information_cost": 16500.0,
            "remediation_hours": 160.0,
            "engineering_hourly_rate": 125.0,
        },
        "published_output": 112100.0,
        "statutory_authority": "EU Digital Operational Resilience Act (Regulation (EU) 2022/2554 Articles 17, 26 & 28)",
        "economic_dataset": "ESAs Joint DORA Oversight Cost Series & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Financial entity scoping EU DORA compliance across 12 critical ICT third-party providers: Article 26 threat-led penetration testing ($42,000.00) + 12 ICT vendor exit-strategy and contractual audits at $2,800 ($33,600.00) + Article 28 Register of Information automation ($16,500.00) + 160 remediation hours at $125/hr ($20,000.00) = $112,100.00 total first-year DORA compliance cost.",
    },
    "eu-ai-act-high-risk-conformity-assessment-cost-calculator": {
        "model_name": "GainHelm-EU-AI-Act-Article43-Conformity-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round((high_risk_ai_systems * notified_body_audit_fee) + annex_iv_technical_dossier_cost + qms_article_17_setup_fee + (validation_hours * ml_compliance_hourly_rate), 2)",
        "inputs": {
            "high_risk_ai_systems": 2.0,
            "notified_body_audit_fee": 28500.0,
            "annex_iv_technical_dossier_cost": 18000.0,
            "qms_article_17_setup_fee": 24000.0,
            "validation_hours": 140.0,
            "ml_compliance_hourly_rate": 150.0,
        },
        "published_output": 120000.0,
        "statutory_authority": "NIST AI RMF 1.0 (15 U.S.C. 278h-1) & EU Artificial Intelligence Act (Regulation (EU) 2024/1689 Articles 6 & 43)",
        "economic_dataset": "European Commission AI Impact Assessment Cost Benchmark & BLS OEWS SOC 15-2051 Data Scientist Wage Series",
        "sample_calculation": "Enterprise deploying 2 Annex III high-risk AI systems under EU Regulation 2024/1689: 2 Article 43 Notified Body conformity audits at $28,500 ($57,000.00) + Annex IV technical documentation dossier ($18,000.00) + Article 17 Quality Management System setup ($24,000.00) + 140 bias/robustness validation hours at $150/hr ($21,000.00) = $120,000.00 total conformity cost.",
    },
    "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator": {
        "model_name": "GainHelm-SEC-8K-Item105-Materiality-Readiness-Cost-Model-2026",
        "entity_type": "FinancialProductOrService",
        "formula": "round(outside_securities_counsel_retainer + dfir_tabletop_retainer + (board_reg_sk_106_hours * governance_advisory_hourly_rate) + materiality_workflow_platform_fee, 2)",
        "inputs": {
            "outside_securities_counsel_retainer": 65000.0,
            "dfir_tabletop_retainer": 48000.0,
            "board_reg_sk_106_hours": 160.0,
            "governance_advisory_hourly_rate": 225.0,
            "materiality_workflow_platform_fee": 31000.0,
        },
        "published_output": 180000.0,
        "statutory_authority": "SEC Final Rule 33-11216 (17 CFR 229.106 Regulation S-K Item 106 & Form 8-K Item 1.05 4-Business-Day Mandate)",
        "economic_dataset": "SEC Division of Economic and Risk Analysis (DERA) Cyber Disclosure Cost Series & BLS OEWS SOC 15-1212 Wage Series",
        "sample_calculation": "Public registrant operationalizing SEC Form 8-K Item 1.05 4-business-day materiality determination and Regulation S-K Item 106 board governance disclosures: outside securities counsel retainer ($65,000.00) + DFIR forensic readiness and tabletop exercises ($48,000.00) + 160 Regulation S-K Item 106 governance hours at $225/hr ($36,000.00) + automated materiality evidentiary workflow platform ($31,000.00) = $180,000.00 total annual SEC cyber disclosure readiness investment.",
    },
}

GAINHELM_CALCULATION_MANIFESTS: List[Dict[str, Any]] = [
    {"slug": m_slug, **m_item}
    for m_slug, m_item in GAINHELM_FALLBACK_MANIFESTS_MAP.items()
]


def get_gainhelm_tool_quick_answers() -> Dict[str, str]:
    """Builds 40-to-60-word GEO quick answers keyed by GainHelm tool slug."""
    from pseofactory.gsc_remediation import _normalize_quick_answer_40_60_words

    return {
        m_slug: _normalize_quick_answer_40_60_words("", "gainhelm", slug=m_slug)
        for m_slug in GAINHELM_FALLBACK_MANIFESTS_MAP
    }


GAINHELM_TOOL_QUICK_ANSWERS: Dict[str, str] = get_gainhelm_tool_quick_answers()


def compute_gainhelm_framework_benchmarks(
    repo_root: Optional[Path] = None,
    headcount: int = 75,
    extra_criteria_count: int = 2,
    unimplemented_5pt: int = 3,
    unimplemented_3pt: int = 2,
    unimplemented_1pt: int = 2,
    compromised_records: int = 1500,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes multi-framework compliance benchmarks dynamically using the tenant's
    `gainhelm/engine/compliance_formulas.py` when present, or identical stdlib math.
    """
    if repo_root is not None:
        formulas_py = Path(repo_root) / "gainhelm" / "engine" / "compliance_formulas.py"
        if formulas_py.is_file():
            try:
                spec = importlib.util.spec_from_file_location("_gh_formulas_dynamic", formulas_py)
                if spec is not None and spec.loader is not None:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    fn = getattr(mod, "compare_all_compliance_frameworks", None)
                    if callable(fn):
                        return dict(
                            fn(
                                headcount=headcount,
                                extra_criteria_count=extra_criteria_count,
                                unimplemented_5pt=unimplemented_5pt,
                                unimplemented_3pt=unimplemented_3pt,
                                unimplemented_1pt=unimplemented_1pt,
                                compromised_records=compromised_records,
                            )
                        )
            except Exception:
                pass

    hc = max(1, int(headcount))
    extra_c = max(0, int(extra_criteria_count))
    cpa_total = round(28000.0 + (extra_c * 4500.0), 2)
    internal_labor = round(120.0 * 121.67, 2)
    soc2_total = round(cpa_total + 11500.0 + 15000.0 + internal_labor, 2)
    auto_savings = round(internal_labor * 0.55, 2)

    remediation_labor = round(380.0 * 115.0, 2)
    cmmc_total = round(48500.0 + 26400.0 + remediation_labor + 13400.0, 2)

    u5 = max(0, min(44, int(unimplemented_5pt)))
    u3 = max(0, min(14, int(unimplemented_3pt)))
    u1 = max(0, min(52, int(unimplemented_1pt)))
    deduction = (u5 * 5) + (u3 * 3) + (u1 * 1)
    sprs_score = float(max(-203, 110 - deduction))

    iso_days = 11.0
    iso_reg = round(iso_days * 1950.0, 2)
    iso_rem = round(180.0 * 125.28, 2)
    iso_total = round(iso_reg + 14500.0 + 8500.0 + iso_rem, 2)

    records = max(0, int(compromised_records))
    ocr_fine = round(min(records * 13795.0, 2067813.0), 2)
    notif_cost = round(records * 195.0, 2)
    hipaa_total = round(ocr_fine + 95000.0 + notif_cost, 2)

    return {
        "soc2": {
            "framework": "SOC 2 Type II (AICPA SSAE 18)",
            "headcount": hc,
            "cpa_audit_fee": cpa_total,
            "pentest_fee": 11500.0,
            "grc_platform_cost": 15000.0,
            "internal_labor_cost": internal_labor,
            "total_cost": soc2_total,
            "automation_savings": auto_savings,
            "timeline_months": 6,
        },
        "cmmc": {
            "framework": "DoD CMMC 2.0 Level 2 (32 CFR Part 170)",
            "c3pao_assessment_fee": 48500.0,
            "enclave_licensing_annual": 26400.0,
            "remediation_labor_cost": remediation_labor,
            "rpo_advisory_fee": 13400.0,
            "total_cost": cmmc_total,
            "timeline_months": 9,
        },
        "sprs": {
            "framework": "NIST SP 800-171 Rev 2 DoD SPRS (DFARS 252.204-7019)",
            "max_score": 110,
            "min_score": -203,
            "deduction_points": deduction,
            "sprs_score": sprs_score,
            "conditional_threshold": 88,
            "poam_eligible": sprs_score >= 88 and u5 == 0,
            "gap_to_conditional": max(0, 88 - int(sprs_score)),
        },
        "iso27001": {
            "framework": "ISO/IEC 27001:2022 (ISO/IEC 27006-1:2024)",
            "auditor_days": iso_days,
            "registrar_fee": iso_reg,
            "isms_platform_cost": 14500.0,
            "internal_audit_fee": 8500.0,
            "remediation_cost": iso_rem,
            "total_cost": iso_total,
            "timeline_months": 6,
        },
        "hipaa": {
            "framework": "HIPAA / HITECH (45 CFR 160.404 & 45 CFR 164.400)",
            "compromised_records": records,
            "ocr_civil_penalty": ocr_fine,
            "forensic_legal_retainer": 95000.0,
            "breach_notification_cost": notif_cost,
            "total_exposure": hipaa_total,
            "media_notice_required": records >= 500,
        },
        "pci_dss": {
            "framework": "PCI DSS v4.0.1 Level 1 QSA ROC",
            "total_cost": 94800.0,
            "timeline_months": 6,
        },
        "fedramp": {"framework": "FedRAMP Moderate 3PAO (44 U.S.C. 3607)", "total_cost": 500000.0, "timeline_months": 12},
        "hitrust": {"framework": "HITRUST CSF v11 (e1 / i1 / r2)", "total_cost": 115000.0, "timeline_months": 9},
        "pentest": {"framework": "Penetration Testing (NIST SP 800-115)", "total_cost": 23300.0, "timeline_months": 1},
        "cyber_insurance": {
            "framework": "Cyber Liability Insurance (NAIC / SEC Item 1.05)",
            "annual_premium": 20415.0,
            "self_insured_retention": 20485.0,
            "total_cost": 40900.0,
        },
    }


_GAINHELM_TITLE_PADS: Tuple[str, ...] = (
    "{base} | {brand} GRC Audit Cost Calculator",
    "{base} | {brand} Compliance Cost Engine",
    "{base} | {brand} Audit Scoping Model",
    "{base} | {brand} Security Audit Engine",
    "{base} | {brand} Calculator Tool",
    "{base} Calculator Tool{brand_suffix}",
    "{base} Audit Cost Model{brand_suffix}",
)


def normalize_gainhelm_seo_title(
    title: str,
    brand: str = GAINHELM_SITE_NAME,
    min_len: int = 50,
    max_len: int = 60,
) -> str:
    """Normalizes GainHelm HTML title length to satisfy 50-60 character bounds."""
    return normalize_tenant_seo_title(
        title=title,
        brand=brand,
        default_tagline="Enterprise Cyber Compliance Engine",
        pad_candidates=_GAINHELM_TITLE_PADS,
        min_len=min_len,
        max_len=max_len,
    )


def _get_gainhelm_organization_schema() -> Dict[str, Any]:
    return build_organization_schema(
        canonical_base=GAINHELM_CANONICAL_BASE,
        site_name=GAINHELM_SITE_NAME,
        site_description=GAINHELM_SITE_DESCRIPTION,
        same_as=[GAINHELM_LINKEDIN_URL, "https://www.wikidata.org/wiki/Q166142"],
    )


def _get_gainhelm_local_business_schema() -> Dict[str, Any]:
    return build_local_business_schema(
        canonical_base=GAINHELM_CANONICAL_BASE,
        legal_name=GAINHELM_COMPANY_LEGAL_NAME,
        contact_email=GAINHELM_CONTACT_EMAIL,
        telephone=GAINHELM_COMPANY_PHONE,
        price_range="$0 (Open-Access Enterprise Cyber Compliance & Audit Cost Models)",
        address={
            "street": GAINHELM_COMPANY_STREET,
            "city": GAINHELM_COMPANY_CITY,
            "state": GAINHELM_COMPANY_STATE,
            "zip": GAINHELM_COMPANY_ZIP,
            "country": GAINHELM_COMPANY_COUNTRY,
        },
        geo={"lat": GAINHELM_COMPANY_LAT, "lng": GAINHELM_COMPANY_LNG},
        same_as=[GAINHELM_LINKEDIN_URL, "https://www.wikidata.org/wiki/Q166142", GAINHELM_COMPANY_WA_SOS_URL],
        catalog_name="GainHelm Enterprise GRC Automation & Security Audit Partner Catalog",
        offers=list(GAINHELM_AFFILIATES.values()),
    )


_COMPLIANCE_FIELDS: List[Dict[str, Any]] = [
    {"id": "headcount", "label": "In-Scope Employee Headcount", "default": 75, "min_val": 1, "max_val": 10000, "step": 5, "unit": "employees", "tooltip": "Total engineering, operations, and administrative personnel within the ISMS or SOC 2 audit boundary."},
    {"id": "extra_criteria", "label": "Additional SOC 2 Trust Services Criteria", "default": 2, "min_val": 0, "max_val": 4, "step": 1, "unit": "criteria", "tooltip": "Optional criteria beyond mandatory Security (Availability, Confidentiality, Processing Integrity, Privacy)."},
    {"id": "unimplemented_5pt", "label": "Unimplemented NIST 800-171 5-Point Controls", "default": 3, "min_val": 0, "max_val": 42, "step": 1, "unit": "controls", "tooltip": "Each unimplemented 5-point NIST SP 800-171 control deducts 5 points from the +110 SPRS baseline."},
    {"id": "unimplemented_3pt", "label": "Unimplemented NIST 800-171 3-Point Controls", "default": 2, "min_val": 0, "max_val": 14, "step": 1, "unit": "controls", "tooltip": "Each unimplemented 3-point NIST SP 800-171 control deducts 3 points from the +110 SPRS baseline."},
    {"id": "unimplemented_1pt", "label": "Unimplemented NIST 800-171 1-Point Controls", "default": 2, "min_val": 0, "max_val": 54, "step": 1, "unit": "controls", "tooltip": "Each unimplemented 1-point NIST SP 800-171 control deducts 1 point from the +110 SPRS baseline."},
    {"id": "compromised_records", "label": "Regulated ePHI / PII Records in Scope", "default": 1500, "min_val": 0, "max_val": 1000000, "step": 100, "unit": "records", "tooltip": "Total patient ePHI or cardholder records exposed for 45 CFR 160.404 HIPAA penalty modeling."},
]

_COMPLIANCE_FAQS: List[Dict[str, str]] = [
    {"question": "How is a SOC 2 Type II total audit budget calculated under AICPA SSAE 18?", "answer": "SOC 2 Type II cost combines the accredited CPA firm examination fee ($28,000 base for Security plus $4,500 per additional Trust Services Criterion), an external CREST/OSCP penetration test ($11,500), continuous GRC automation licensing ($15,000), and internal engineering evidence hours (120 hours at $121.67/hr loaded BLS 15-1212 wage rate = $14,600.40), totaling $78,100.40."},
    {"question": "How does the DoD NIST SP 800-171 SPRS score calculator work under DFARS 252.204-7019?", "answer": "Every defense contractor starts at +110 points across the 110 security requirements of NIST SP 800-171 Rev 2. Unimplemented controls deduct 5 points, 3 points, or 1 point based on DoD Assessment Methodology weights, producing a score between -203 and +110. Under 32 CFR 170.21, a minimum score of 88 with zero open critical 5-point CUI controls is required for a 180-day Conditional CMMC Level 2 POA&M."},
    {"question": "How are ISO/IEC 27001 Stage 1 and Stage 2 auditor days determined?", "answer": "Accredited certification bodies allocate Stage 1 and Stage 2 auditor days strictly from ISO/IEC 27006-1:2024 Annex B headcount tables (11 auditor days at $1,950/day = $21,450 for a 75-employee ISMS scope), with mandatory Surveillance Year 1 and Year 2 audits sized at 33% of initial certification time."},
    {"question": "What are the inflation-adjusted HIPAA civil monetary penalty tiers under 45 CFR 160.404?", "answer": "Under 45 CFR 160.404 and 45 CFR 102.3, HHS OCR assesses Tier 1 ($141 to $71,162 per violation), Tier 2 ($1,424 to $71,162), Tier 3 Willful Neglect Corrected ($13,795 to $71,162), and Tier 4 Willful Neglect Uncorrected ($71,162 to $2,067,813 per violation), plus 45 CFR 164.406 media notification and forensic response costs when 500 or more ePHI records are compromised."},
]


def _render_calculator_widget(
    benchmarks: Dict[str, Dict[str, Any]],
    tool_slug: str = "soc-2-audit-cost-calculator",
) -> str:
    slug_low = str(tool_slug or "").strip().lower()
    show_extra_criteria = ("soc-2" in slug_low or "soc2" in slug_low or not slug_low)
    fields_html = []
    for f in _COMPLIANCE_FIELDS:
        if f["id"] == "extra_criteria" and not show_extra_criteria:
            continue
        fid = html.escape(f["id"])
        fields_html.append(f"""
          <div class="calc-field-group">
            <div class="calc-label-row">
              <label for="calc-input-{fid}" class="calc-label">{html.escape(f['label'])}</label>
              <span class="calc-unit">{html.escape(f['unit'])}</span>
            </div>
            <input
              type="number"
              id="calc-input-{fid}"
              name="{fid}"
              class="calc-number-input touch-target"
              value="{f['default']}"
              min="{f['min_val']}"
              max="{f['max_val']}"
              step="{f['step']}"
              data-field-id="{fid}"
            />
            <p class="calc-tooltip">{html.escape(f['tooltip'])}</p>
          </div>""")

    soc2_val = f"${benchmarks['soc2']['total_cost']:,.2f}"
    cmmc_val = f"${benchmarks['cmmc']['total_cost']:,.2f}"
    sprs_val = f"{int(benchmarks['sprs']['sprs_score'])} pts"
    iso_val = f"${benchmarks['iso27001']['total_cost']:,.2f}"
    hipaa_val = f"${benchmarks['hipaa']['total_exposure']:,.2f}"
    pci_val = f"${benchmarks['pci_dss']['total_cost']:,.2f}"
    sav_val = f"${benchmarks['soc2']['automation_savings']:,.2f}/yr"
    cpa_fee_val = f"${benchmarks['soc2']['cpa_audit_fee']:,.2f}"
    grc_fee_val = f"${benchmarks['soc2']['grc_platform_cost']:,.2f}"
    int_labor_val = f"${benchmarks['soc2']['internal_labor_cost']:,.2f}"
    quick_ans = (
        "Under AICPA SSAE 18 (AT-C Section 205) and DoD 32 CFR Part 170, a 75-employee enterprise "
        "incurs a baseline SOC 2 Type II total outlay of $78,100.40 (comprising $37,000.00 CPA fees, "
        "$11,500.00 penetration testing, $15,000.00 GRC platform licensing, and $14,600.40 engineering labor), "
        "while 3 unimplemented 5-point, 2 unimplemented 3-point, and 2 unimplemented 1-point NIST SP 800-171 "
        "controls yield a DoD SPRS score of 87 out of 110 (1 point shy of the 88-point conditional POA&M floor)."
    )

    return f"""
    <section class="interactive-calculator-container" id="calculator-workspace-anchor" aria-label="Enterprise SOC 2 Type II, DoD CMMC 2.0 &amp; NIST 800-171 SPRS Audit Calculator">
      <div class="calc-header">
        <h2 class="calc-title">Enterprise SOC 2 Type II, DoD CMMC 2.0 &amp; NIST 800-171 SPRS Audit Calculator</h2>
        <p class="calc-desc">Deterministic enterprise GRC audit budgeting and NIST SP 800-171 SPRS scoring engine.</p>
      </div>

      <div class="calc-switcher-panel">
        <div class="calc-switcher-header">
          <span class="calc-switcher-title">Enterprise Audit Scenario Presets</span>
          <span class="calc-switcher-hint">Instant Statutory Recalculation</span>
        </div>
        <div class="calc-switcher-pills">
          <button type="button" class="calc-switcher-btn touch-target active" data-preset-hc="75" data-preset-crit="2" data-preset-u5="3" data-preset-u3="2" data-preset-u1="2" data-preset-rec="1500">
            Series B SaaS (75 HC, 3 TSC, SPRS 87)
          </button>
          <button type="button" class="calc-switcher-btn touch-target" data-preset-hc="25" data-preset-crit="1" data-preset-u5="0" data-preset-u3="2" data-preset-u1="4" data-preset-rec="500">
            Seed / Series A (25 HC, 2 TSC, SPRS 100)
          </button>
          <button type="button" class="calc-switcher-btn touch-target" data-preset-hc="250" data-preset-crit="4" data-preset-u5="6" data-preset-u3="5" data-preset-u1="10" data-preset-rec="15000">
            Enterprise Defense &amp; Health (250 HC, 5 TSC, SPRS 55)
          </button>
        </div>
      </div>

      <div class="calc-grid">
        <div class="calc-inputs-column">
          <h3 class="calc-column-title">Audit Scope &amp; Control Parameters</h3>
          <form id="gainhelm-compliance-form" class="calculator-form" onsubmit="return false;">
            {''.join(fields_html)}
            <button type="submit" id="calc-submit-btn" class="btn-cta touch-target" style="width: 100%; margin-top: 0.5rem;">
              Recalculate Compliance Budget &amp; SPRS Score
            </button>
          </form>
        </div>

        <div class="calc-results-column" aria-live="polite">
          <h3 class="calc-column-title">Deterministic Statutory &amp; Audit Outputs</h3>
          <div class="calc-metrics-grid">
            <div class="calc-metric-card calc-metric-highlight">
              <div class="calc-metric-label">SOC 2 Type II Total Year-1 Cost (AICPA SSAE 18)</div>
              <div class="calc-metric-value" id="metric-soc2_total_cost">{soc2_val}</div>
            </div>
            <div class="calc-metric-card calc-metric-highlight">
              <div class="calc-metric-label">NIST SP 800-171 DoD SPRS Score ([-203, +110])</div>
              <div class="calc-metric-value" id="metric-nist_sprs_score">{sprs_val}</div>
            </div>
            <div class="calc-metric-card">
              <div class="calc-metric-label">DoD CMMC 2.0 Level 2 C3PAO Total Cost (32 CFR 170)</div>
              <div class="calc-metric-value" id="metric-cmmc_total_cost">{cmmc_val}</div>
            </div>
            <div class="calc-metric-card">
              <div class="calc-metric-label">ISO/IEC 27001:2022 Stage 1 &amp; 2 Total Cost</div>
              <div class="calc-metric-value" id="metric-iso27001_total_cost">{iso_val}</div>
            </div>
            <div class="calc-metric-card">
              <div class="calc-metric-label">HIPAA 45 CFR 160.404 Tier 3 Breach Exposure</div>
              <div class="calc-metric-value" id="metric-hipaa_exposure">{hipaa_val}</div>
            </div>
            <div class="calc-metric-card">
              <div class="calc-metric-label">PCI DSS v4.0.1 Level 1 QSA ROC Total Cost</div>
              <div class="calc-metric-value" id="metric-pci_dss_cost">{pci_val}</div>
            </div>
            <div class="calc-metric-card calc-metric-highlight">
              <div class="calc-metric-label">Continuous GRC Automation Labor Savings</div>
              <div class="calc-metric-value" id="metric-soc2_automation_savings">{sav_val}</div>
            </div>
          </div>

          <div class="subsidy-meter-wrap">
            <div class="subsidy-meter-header">
              <span>SOC 2 Cost Allocation: CPA Attestation vs Pentest &amp; GRC Automation</span>
              <span id="meter-cpa-val">{cpa_fee_val} CPA | {grc_fee_val} GRC</span>
            </div>
            <div class="subsidy-meter-bar">
              <div class="subsidy-meter-seg subsidy-meter-seg-pay" id="meter-seg-cpa" style="width: 47%;"></div>
              <div class="subsidy-meter-seg subsidy-meter-seg-sub" id="meter-seg-grc" style="width: 53%;"></div>
            </div>
            <div class="subsidy-meter-legend">
              <span class="legend-item"><span class="legend-dot dot-pay"></span>CPA Firm Attestation Fee (<span id="meter-pay-val">{cpa_fee_val}</span>)</span>
              <span class="legend-item"><span class="legend-dot dot-sub"></span>GRC Automation Savings (<span id="meter-sub-val">${benchmarks['soc2']['automation_savings']:,.2f}</span>)</span>
              <span class="legend-item"><span class="legend-dot dot-int"></span>Internal Engineering Prep (<span id="meter-int-val">{int_labor_val}</span>)</span>
            </div>
          </div>
        </div>
      </div>

      <div class="calc-geo-answer-box">
        <div class="calc-geo-answer-title">Statutory Verification &amp; Audit Readiness Summary</div>
        <p class="calc-geo-answer-text">{html.escape(quick_ans)}</p>
      </div>

      <script>
      (function() {{
        var form = document.getElementById("gainhelm-compliance-form");
        if (!form) return;
        function clampNonNeg(val, defVal) {{
          var n = parseFloat(val);
          if (isNaN(n) || !isFinite(n)) return defVal;
          return Math.max(0, n);
        }}
        function fmtUSD(v) {{
          return "$" + v.toLocaleString("en-US", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
        }}
        function recompute() {{
          var hcEl = document.getElementById("calc-input-headcount");
          var hc = hcEl ? Math.max(1, Math.round(clampNonNeg(hcEl.value, 75))) : 75;
          var critEl = document.getElementById("calc-input-extra_criteria");
          var crit = critEl ? Math.min(4, Math.round(clampNonNeg(critEl.value, 2))) : 2;
          var u5El = document.getElementById("calc-input-unimplemented_5pt");
          var u5 = u5El ? Math.min(42, Math.round(clampNonNeg(u5El.value, 3))) : 3;
          var u3El = document.getElementById("calc-input-unimplemented_3pt");
          var u3 = u3El ? Math.min(14, Math.round(clampNonNeg(u3El.value, 2))) : 2;
          var u1El = document.getElementById("calc-input-unimplemented_1pt");
          var u1 = u1El ? Math.min(54, Math.round(clampNonNeg(u1El.value, 2))) : 2;
          var recEl = document.getElementById("calc-input-compromised_records");
          var rec = recEl ? Math.round(clampNonNeg(recEl.value, 1500)) : 1500;

          var scaleFactor = hc / 75.0;
          var cpaFee = 28000.0 + (crit * 4500.0);
          var pentestFee = 11500.0;
          var grcFee = 15000.0;
          var internalLabor = Math.round((120.0 * scaleFactor * 121.67) * 100) / 100;
          var soc2Total = Math.round((cpaFee + pentestFee + grcFee + internalLabor) * 100) / 100;
          var autoSavings = Math.round((internalLabor * 0.55) * 100) / 100;

          var sprsDeduction = (u5 * 5) + (u3 * 3) + (u1 * 1);
          var sprsScore = Math.max(-203, 110 - sprsDeduction);

          var cmmcTotal = Math.round((48500.0 + 26400.0 + (380.0 * 115.0 * Math.max(0.5, scaleFactor)) + 13400.0) * 100) / 100;
          var isoDays = Math.max(5.0, Math.round(11.0 * Math.pow(scaleFactor, 0.35)));
          var isoTotal = Math.round(((isoDays * 1950.0) + 14500.0 + 8500.0 + (180.0 * 125.28)) * 100) / 100;
          var ocrFine = Math.min(rec * 13795.0, 2067813.0);
          var hipaaTotal = Math.round((ocrFine + 95000.0 + (rec * 195.0)) * 100) / 100;
          var pciTotal = 94800.00;

          var elSoc2 = document.getElementById("metric-soc2_total_cost");
          var elSprs = document.getElementById("metric-nist_sprs_score");
          var elCmmc = document.getElementById("metric-cmmc_total_cost");
          var elIso = document.getElementById("metric-iso27001_total_cost");
          var elHipaa = document.getElementById("metric-hipaa_exposure");
          var elPci = document.getElementById("metric-pci_dss_cost");
          var elSav = document.getElementById("metric-soc2_automation_savings");

          if (elSoc2) elSoc2.textContent = fmtUSD(soc2Total);
          if (elSprs) elSprs.textContent = sprsScore + " pts";
          if (elCmmc) elCmmc.textContent = fmtUSD(cmmcTotal);
          if (elIso) elIso.textContent = fmtUSD(isoTotal);
          if (elHipaa) elHipaa.textContent = fmtUSD(hipaaTotal);
          if (elPci) elPci.textContent = fmtUSD(pciTotal);
          if (elSav) elSav.textContent = fmtUSD(autoSavings) + "/yr";

          var elMeterCpa = document.getElementById("meter-cpa-val");
          var elMeterPay = document.getElementById("meter-pay-val");
          var elMeterSub = document.getElementById("meter-sub-val");
          var elMeterInt = document.getElementById("meter-int-val");
          var elSegCpa = document.getElementById("meter-seg-cpa");
          var elSegGrc = document.getElementById("meter-seg-grc");
          var cpaPct = Math.max(5, Math.min(95, Math.round((cpaFee / Math.max(1, soc2Total)) * 100)));
          if (elMeterCpa) elMeterCpa.textContent = fmtUSD(cpaFee) + " CPA | " + fmtUSD(grcFee) + " GRC";
          if (elMeterPay) elMeterPay.textContent = fmtUSD(cpaFee);
          if (elMeterSub) elMeterSub.textContent = fmtUSD(autoSavings);
          if (elMeterInt) elMeterInt.textContent = fmtUSD(internalLabor);
          if (elSegCpa) elSegCpa.style.width = cpaPct + "%";
          if (elSegGrc) elSegGrc.style.width = (100 - cpaPct) + "%";
        }}

        var params = new URLSearchParams(window.location.search);
        ["headcount", "extra_criteria", "unimplemented_5pt", "unimplemented_3pt", "unimplemented_1pt", "compromised_records"].forEach(function(k) {{
          if (params.has(k)) {{
            var inp = document.getElementById("calc-input-" + k);
            if (inp) inp.value = Math.max(0, parseFloat(params.get(k)) || 0);
          }}
        }});

        form.addEventListener("input", recompute);
        form.addEventListener("change", recompute);
        var btns = document.querySelectorAll(".calc-switcher-btn");
        for (var i = 0; i < btns.length; i++) {{
          btns[i].addEventListener("click", function() {{
            for (var j = 0; j < btns.length; j++) btns[j].classList.remove("active");
            this.classList.add("active");
            var hcTarget = document.getElementById("calc-input-headcount");
            if (hcTarget) hcTarget.value = this.getAttribute("data-preset-hc") || "75";
            var critBtnTarget = document.getElementById("calc-input-extra_criteria");
            if (critBtnTarget) critBtnTarget.value = this.getAttribute("data-preset-crit") || "2";
            var u5Target = document.getElementById("calc-input-unimplemented_5pt");
            if (u5Target) u5Target.value = this.getAttribute("data-preset-u5") || "3";
            var u3Target = document.getElementById("calc-input-unimplemented_3pt");
            if (u3Target) u3Target.value = this.getAttribute("data-preset-u3") || "2";
            var u1Target = document.getElementById("calc-input-unimplemented_1pt");
            if (u1Target) u1Target.value = this.getAttribute("data-preset-u1") || "2";
            var recTarget = document.getElementById("calc-input-compromised_records");
            if (recTarget) recTarget.value = this.getAttribute("data-preset-rec") || "1500";
            recompute();
          }});
        }}
        recompute();
      }})();
      </script>
    </section>"""


_TOOL_COMMENTARY_BY_SLUG: Dict[str, Tuple[str, List[str]]] = {
    "soc-2-audit-cost-calculator": (
        "AICPA SSAE 18 Attestation Mechanics: Type I Point-in-Time vs Type II Observation",
        [
            "Service Organization Control (SOC) 2 engagements are governed by the American Institute of Certified Public Accountants (AICPA) Statement on Standards for Attestation Engagements No. 18 (SSAE 18), codified at AT-C Section 205. Unlike self-attestation questionnaires, a valid SOC 2 report can only be issued by an independent licensed CPA firm registered for peer-reviewed attestation practice.",
            "A SOC 2 Type I report evaluates the suitability of control design at a single point in time. In contrast, a SOC 2 Type II report tests the operating effectiveness of controls across an observation window of 3 to 12 consecutive months. Enterprise procurement teams overwhelmingly mandate Type II reports covering Security (Common Criteria) alongside Availability and Confidentiality under TSP Section 100.",
            "Deploying continuous GRC automation platforms reduces engineering evidence-collection overhead by 55 to 70 percent, allowing security engineers (benchmarked at $121.67 per hour loaded wage under BLS SOC 15-1212) to focus on remediation rather than manual screenshot harvesting.",
        ],
    ),
    "cmmc-2-0-compliance-cost-calculator": (
        "32 CFR Part 170 Final Rule: C3PAO Triennial Assessments and DFARS 252.204-7021",
        [
            "The Department of Defense Cybersecurity Maturity Model Certification (CMMC 2.0) program codified at 32 CFR Part 170 and enforced via DFARS 252.204-7021 establishes mandatory cybersecurity verification for Defense Industrial Base (DIB) contractors handling Federal Contract Information (FCI) and Controlled Unclassified Information (CUI).",
            "While Level 1 requires annual self-affirmation across 15 basic safeguarding requirements (FAR 52.204-21), Level 2 mandates full implementation of all 110 security requirements in NIST SP 800-171 Rev 2 (320 assessment objectives). Approximately 95 percent of Level 2 contractors must undergo triennial on-site and virtual assessments conducted by an accredited CMMC Third-Party Assessment Organization (C3PAO).",
            "Contractors can substantially reduce C3PAO assessment scope and remediation labor by isolating CUI inside a dedicated FedRAMP Moderate Equivalent virtual enclave rather than attempting to certify their entire corporate IT network.",
        ],
    ),
    "nist-800-171-sprs-score-calculator": (
        "DoD Assessment Methodology v1.2.1: Weighted SPRS Deductions and Conditional POA&M Rules",
        [
            "Pursuant to DFARS 252.204-7019 and 252.204-7020, defense contractors must calculate and submit a verified Supplier Performance Risk System (SPRS) score prior to contract award. The DoD Assessment Methodology assigns a starting score of +110 when all 110 NIST SP 800-171 Rev 2 requirements are fully implemented.",
            "Each unimplemented security requirement deducts 1, 3, or 5 points based on architectural criticality. Forty-two foundational controls (such as FIPS-validated cryptography under 3.13.11 and multi-factor authentication under 3.5.3) carry 5-point deductions, driving the theoretical minimum score down to -203.",
            "Under 32 CFR 170.21, a contractor may receive a Conditional CMMC Level 2 status with an active Plan of Action and Milestones (POA&M) only if the initial score is at least 88 out of 110 (80 percent threshold), no 5-point or critical 3-point requirements remain open, and all POA&M items are closed within 180 days.",
        ],
    ),
    "iso-27001-certification-cost-calculator": (
        "ISO/IEC 27006-1:2024 Mandatory Auditor-Day Schedules and Annex A Restructuring",
        [
            "Accredited ISO/IEC 27001:2022 Information Security Management System (ISMS) certification bodies regulated by ANAB, UKAS, or DAkkS cannot arbitrarily discount audit duration. Instead, registrars must adhere to the mandatory auditor-day tables defined in ISO/IEC 27006-1:2024 and IAF Mandatory Document 5 (MD 5), which scale audit days deterministically by effective ISMS headcount and risk complexity.",
            "Initial certification consists of a Stage 1 documentation and Statement of Applicability (SoA) review followed by a Stage 2 implementation audit covering Clauses 4 through 10 and the 93 consolidated Annex A controls (grouped into Organizational, People, Physical, and Technological themes).",
            "Following initial certification, organizations must budget for annual Surveillance Audits in Years 2 and 3 (each requiring approximately one-third of the initial Stage 1+2 auditor days) and a Recertification Audit in Year 4 (requiring two-thirds of initial auditor days).",
        ],
    ),
    "hipaa-violation-penalty-breach-cost-calculator": (
        "45 CFR 160.404 Civil Monetary Penalty Tiers and HITECH Recognized Security Practices",
        [
            "The Department of Health and Human Services Office for Civil Rights (HHS OCR) enforces the HIPAA Privacy, Security, and Breach Notification Rules under 45 CFR Part 160 and the HITECH Act (42 U.S.C. 1320d-5). Civil monetary penalties are structured into four culpability tiers: Tier 1 (Lack of Knowledge), Tier 2 (Reasonable Cause), Tier 3 (Willful Neglect Corrected within 30 Days), and Tier 4 (Willful Neglect Not Corrected).",
            "Beyond statutory civil fines, any unsecured ePHI breach affecting 500 or more individuals triggers mandatory notification to affected patients, prominent media outlets, and the HHS OCR public Breach Portal within 60 calendar days under 45 CFR 164.404 through 164.408.",
            "Pursuant to the 2021 HITECH Act amendment (Public Law 116-321), covered entities and business associates that demonstrate continuous implementation of Recognized Security Practices (such as the NIST Cybersecurity Framework or HICP 405(d) guidelines) for the preceding 12 months qualify for statutory penalty mitigation and reduced OCR audit duration.",
        ],
    ),
    "pci-dss-4-0-compliance-cost-calculator": (
        "PCI DSS v4.0.1 Cardholder Data Environment Segmentation & QSA ROC Economics",
        [
            "Payment Card Industry Data Security Standard (PCI DSS) v4.0.1 enforces 12 principal security requirements and mandatory future-dated controls effective March 31, 2025, covering authenticated vulnerability scans, targeted risk analysis frequencies, and multi-factor authentication across the Cardholder Data Environment (CDE).",
            "Level 1 merchants processing over 6 million Visa or Mastercard transactions annually must undergo an on-site Report on Compliance (ROC) led by a PCI SSC Qualified Security Assessor (QSA) alongside quarterly Approved Scanning Vendor (ASV) external scans under Requirement 11.3.",
            "Architecting isolated tokenization vaults and VLAN micro-segmentation reduces in-scope CDE host counts by 60 to 80 percent, cutting both QSA fieldwork days and annual penetration testing remediation hours.",
        ],
    ),
    "fedramp-authorization-3pao-cost-calculator": (
        "FedRAMP Authorization Act (44 U.S.C. 3607): 3PAO Assessment & ConMon Cost Structure",
        [
            "Under the FedRAMP Authorization Act (44 U.S.C. 3607) and OMB Memorandum M-24-15, Cloud Service Providers targeting federal agency Authority to Operate (ATO) approvals must satisfy NIST SP 800-53 Rev 5 Low (125 controls), Moderate (325 controls), or High (421 controls) security baselines.",
            "Independent Third-Party Assessment Organizations (3PAOs) conduct Readiness Assessment Reports (RAR) and annual Security Assessment Report (SAR) testing covering FIPS 140-3 validated cryptography, boundary protections, and POA&M Continuous Monitoring (ConMon) deliverables.",
            "Deploying onto an inherited FedRAMP Authorized GovCloud IaaS or PaaS substrate slashes custom boundary engineering hours and compresses authorization timelines by 6 to 9 months.",
        ],
    ),
    "hitrust-csf-e1-i1-r2-certification-cost-calculator": (
        "HITRUST CSF v11 Assurance Program: e1, i1, and r2 Validated Assessment Scoping",
        [
            "HITRUST CSF v11 provides a tiered healthcare and enterprise risk assurance ladder spanning Essentials (e1, 44 foundational hygiene controls), Implemented (i1, 182 controls for 1-year validated assurance), and Risk-based (r2, comprehensive 2-year certification scaled to organizational risk factors).",
            "Total program investment includes annual MyCSF assessment portal licensing, HITRUST Authorized External Assessor validation fieldwork, central HITRUST quality assurance and certification submission fees, and internal engineering control remediation.",
            "Mapping existing SOC 2 and HIPAA Security Rule control artifacts into MyCSF inheritance mechanisms eliminates redundant evidence gathering prior to External Assessor sampling.",
        ],
    ),
    "penetration-testing-scoping-cost-calculator": (
        "NIST SP 800-115 & PCI DSS Requirement 11.4 Offensive Security Scoping",
        [
            "Enterprise penetration testing budgets follow deterministic scope drivers codified under NIST SP 800-115 and PCI DSS Requirement 11.4: target web and API endpoint counts, external and internal CIDR ranges, cloud IAM control-plane review, and post-remediation retest attestation letters.",
            "Independent CREST or OSCP qualified assessors conduct grey-box testing across OWASP ASVS authentication, authorization, and business-logic paths rather than relying on automated unauthenticated vulnerability scanners.",
            "Bundling cloud IAM privilege-escalation testing with application API penetration testing satisfies SOC 2 CC7.1, ISO 27001 Annex A.8.8, and cyber insurance carrier underwriting mandates within one consolidated attestation.",
        ],
    ),
    "cyber-liability-insurance-breach-exposure-calculator": (
        "NAIC Cyber Supplement & SEC 17 CFR 229.106 Underwriting & Retention Modeling",
        [
            "Commercial cyber liability carriers benchmark annual premiums against policy aggregate limits ($1M to $25M+), NAIC sector loss-ratio multipliers, surplus lines taxes, and Self-Insured Retention (SIR) deductibles.",
            "Actuarial underwriting credits of 15 to 25 percent apply when enterprises verify hardware-backed MFA, 24/7 managed Endpoint Detection and Response (EDR), offline immutable backups, and annual SOC 2 / penetration testing reports.",
            "Public registrants must simultaneously budget for SEC Form 8-K Item 1.05 4-business-day materiality workflows and Regulation S-K Item 106 governance disclosures under 17 CFR 229.106.",
        ],
    ),
}


def get_gainhelm_tool_commentary(slug: str) -> str:
    """Returns statutory commentary markup for a GainHelm cyber compliance tool."""
    title_txt, paragraphs = _TOOL_COMMENTARY_BY_SLUG.get(
        slug,
        (
            "Statutory Enterprise Security Governance and Audit Scoping Economics",
            [
                "Enterprise cybersecurity compliance and third-party attestation frameworks require rigorous financial scoping across external assessor fees, automated GRC evidence collection, technical penetration testing, and internal security engineering labor.",
                "By joining federal statutory fee schedules (AICPA SSAE 18, 32 CFR Part 170, ISO/IEC 27006-1:2024, and 45 CFR 160.404) with empirical Bureau of Labor Statistics OEWS wage series for Information Security Analysts (SOC 15-1212), GainHelm produces verifiable compliance budget models.",
                "Security leaders and CFOs can evaluate multi-framework overlap across SOC 2, CMMC 2.0, ISO 27001, PCI DSS v4.0.1, FedRAMP, and HITRUST to eliminate duplicate control testing and optimize annual security expenditure.",
            ],
        ),
    )
    p_html = "\n          ".join(f'<p class="commentary-text">{html.escape(p)}</p>' for p in paragraphs)
    return (
        '\n        <div class="commentary-box">\n'
        f'          <h2 class="commentary-title">{html.escape(title_txt)}</h2>\n'
        f'          {p_html}\n'
        "        </div>\n        "
    )


def _build_partners_matrix_section(
    slug: str = "",
    engagement_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    from pseofactory.affiliates import classify_gainhelm_framework

    fw_key = classify_gainhelm_framework(slug=slug)
    is_us_audit = fw_key in ("soc2", "cmmc")
    desc_cards = (
        "Automated evidence collection platforms accelerate SOC 2, CMMC 2.0, ISO 27001, and HIPAA "
        "readiness while reducing engineering remediation hours prior to independent third-party attestation."
        if is_us_audit
        else "Automated evidence collection platforms accelerate continuous compliance readiness while "
        "reducing engineering remediation hours prior to independent third-party assessment."
    )
    desc_empty = (
        "Automated evidence collection platforms accelerate audit readiness, while formal attestation "
        "reports require independent licensed CPA firms, C3PAOs, or accredited certification bodies."
        if is_us_audit
        else "Automated evidence collection platforms accelerate continuous governance readiness, while "
        "formal conformity reviews require qualified independent assessors or regulatory counsel."
    )
    return build_partners_matrix_section(
        affiliates=GAINHELM_AFFILIATES,
        section_title="Enterprise GRC Automation & Compliance Partner Network",
        section_desc_with_cards=desc_cards,
        section_desc_empty=desc_empty,
        default_cta_text="Compare GRC Automation",
        slug=slug,
        engagement_metrics=engagement_metrics,
    )


def _build_partner_cta(slug: str = "") -> str:
    from pseofactory.affiliates import classify_gainhelm_framework

    fw_key = classify_gainhelm_framework(slug=slug)
    is_us_audit = fw_key in ("soc2", "cmmc")
    return build_partner_cta(
        affiliates=GAINHELM_AFFILIATES,
        preferred_key="vanta_security",
        restricted_badge="Statutory Audit Independence",
        restricted_title="Accredited Third-Party Assessment",
        restricted_body=(
            "Formal attestation and federal certification require an independent CPA firm, Cyber-AB C3PAO, or accredited ISO registrar."
            if is_us_audit
            else "Formal regulatory conformity reviews require qualified independent assessors or accredited conformity bodies."
        ),
        fallback_badge="Enterprise Compliance Education",
        fallback_title="Independent Assessment Readiness",
        fallback_body=(
            "Continuous control monitoring reduces manual evidence preparation prior to formal CPA or C3PAO audit fieldwork."
            if is_us_audit
            else "Continuous control monitoring reduces manual evidence preparation prior to formal external assessment."
        ),
        default_featured_badge="Featured GRC Partner",
        default_cta_text="Automate Audit Evidence",
        slug=slug,
    )


def _build_retro_reflection_block(slug: str, canonical_url: str) -> str:
    manifest_spec = GAINHELM_FALLBACK_MANIFESTS_MAP.get(slug) or GAINHELM_FALLBACK_MANIFESTS_MAP["soc-2-audit-cost-calculator"]
    return build_retro_reflection_block(
        slug=slug,
        canonical_url=canonical_url,
        manifest_spec=manifest_spec,
        statutory_detail_label="the governing compliance attestation rules, auditor-day minimums, and civil monetary penalty schedules",
        economic_detail_label="empirical security engineering wage and accredited audit fee benchmark series",
    )


def _render_base_html(
    title: str,
    meta_description: str,
    canonical_url: str,
    body_content: str,
    jsonld_schemas: Optional[List[Dict[str, Any]]] = None,
    css_text: str = "",
) -> str:
    gsc_meta_val, _ = _resolve_gainhelm_public_meta()
    return render_base_html(
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        body_content=body_content,
        canonical_base=GAINHELM_CANONICAL_BASE,
        site_name=GAINHELM_SITE_NAME,
        brand_mark="G",
        author=GAINHELM_AUTHOR,
        og_image_url=f"{GAINHELM_CANONICAL_BASE}/static/img/gainhelm-og.png",
        gsc_meta_val=gsc_meta_val,
        disclaimers=GAINHELM_DISCLOSURES,
        linkedin_url=GAINHELM_LINKEDIN_URL,
        editorial_policy_text=(
            "GainHelm Editorial Policy: All calculations are deterministic and verified by statutory models pursuant to "
            "AICPA SSAE 18, 32 CFR Part 170, NIST SP 800-171 Rev 2, ISO/IEC 27006-1:2024, 45 CFR 160.404, and BLS OEWS SOC 15-1212 wage benchmarks."
        ),
        org_schema=_get_gainhelm_organization_schema(),
        localbiz_schema=_get_gainhelm_local_business_schema(),
        footer_tagline="Independent Enterprise Security & Statutory Compliance Modeling.",
        normalize_title_fn=normalize_gainhelm_seo_title,
        jsonld_schemas=jsonld_schemas,
        css_text=css_text,
    )


def _calculator_schemas(route_path: str, title: str, description: str) -> List[Dict[str, Any]]:
    clean_route = route_path if route_path.startswith("/") else f"/{route_path}"
    full_url = f"{GAINHELM_CANONICAL_BASE}{clean_route}"
    return [
        {
            "@type": "SoftwareApplication",
            "@id": f"{full_url}#softwareapplication",
            "name": title,
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web",
            "url": full_url,
            "description": description,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        },
        {
            "@type": "FAQPage",
            "@id": f"{full_url}#faq",
            "mainEntity": [
                {"@type": "Question", "name": item["question"], "acceptedAnswer": {"@type": "Answer", "text": item["answer"]}}
                for item in _COMPLIANCE_FAQS
            ],
        },
    ]


def _apply_overlay_if_present(rendered_html: str, slug: str, repo_root: Optional[Path]) -> str:
    if repo_root is None:
        return rendered_html
    overlay_path = repo_root / "content" / "overlays" / f"{slug}.json"
    if not overlay_path.is_file():
        alt_path = repo_root / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file():
            overlay_path = alt_path
    if not overlay_path.is_file():
        return rendered_html
    try:
        from pseofactory.gsc_remediation import inject_overlay_into_html

        ov_data = json.loads(overlay_path.read_text(encoding="utf-8"))
        if isinstance(ov_data, dict):
            ov_data = strip_cross_framework_leaks_from_overlay(ov_data, slug)
            return inject_overlay_into_html(rendered_html, ov_data)
    except Exception:
        pass
    return rendered_html


def _build_home_html(benchmarks: Dict[str, Dict[str, Any]], all_tools: Sequence[Dict[str, Any]], css_text: str) -> str:
    tools_list_html = [
        f'<li class="tool-link-item"><a href="/tools/{t["slug"]}/" class="tool-link touch-target">{html.escape(t["title"])}</a> '
        f'<span class="tool-desc">- {html.escape(t["description"])}</span></li>'
        for t in all_tools
    ]
    body = f"""
    <section class="hero-section">
      <h1 class="hero-title">Enterprise Cyber Compliance &amp; Statutory Audit Cost Engine</h1>
      <aside class="quick-answer">
        <p>GainHelm delivers deterministic enterprise security compliance, audit fee, and statutory penalty modeling across SOC 2 Type II, CMMC 2.0, NIST SP 800-171 SPRS, ISO 27001:2022, HIPAA HITECH, and PCI DSS v4.0.1. Security leaders can simulate CPA attestation fees, C3PAO assessments, engineering remediation labor, and federal breach penalty caps.</p>
      </aside>
      <p class="hero-desc">
        Compare external auditor fees, GRC automation licensing, internal engineering remediation hours, and statutory penalty exposure under AICPA SSAE 18, 32 CFR Part 170, ISO/IEC 27006-1:2024, and 45 CFR 160.404.
      </p>
    </section>

    {_render_calculator_widget(benchmarks, tool_slug="soc-2-audit-cost-calculator")}

    {_build_partners_matrix_section()}

    <section class="benchmark-table-section">
      <h2 class="section-title">Statutory Compliance Baseline Comparison (75 Employees, 3 TSC, 15 Open Controls)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Compliance Framework</th>
              <th scope="col">Statutory / Standard Authority</th>
              <th scope="col">External Audit Fee</th>
              <th scope="col">Total First-Year Cost</th>
              <th scope="col">Score / Risk Metric</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="td-plan-name">SOC 2 Type II Attestation</td>
              <td>AICPA SSAE 18 (AT-C 205)</td>
              <td class="td-num">${benchmarks["soc2"]["cpa_audit_fee"]:.2f}</td>
              <td class="td-num" id="oracle-soc2-total">${benchmarks["soc2"]["total_cost"]:.2f}</td>
              <td class="td-num">3 TSC Criteria</td>
            </tr>
            <tr>
              <td class="td-plan-name">CMMC 2.0 Level 2 (C3PAO)</td>
              <td>32 CFR Part 170 &amp; DFARS 7021</td>
              <td class="td-num">${benchmarks["cmmc"]["c3pao_assessment_fee"]:.2f}</td>
              <td class="td-num" id="oracle-cmmc-total">${benchmarks["cmmc"]["total_cost"]:.2f}</td>
              <td class="td-num" id="oracle-sprs-score">{benchmarks["sprs"]["sprs_score"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">ISO/IEC 27001:2022 ISMS</td>
              <td>ISO/IEC 27006-1:2024</td>
              <td class="td-num">${benchmarks["iso27001"]["registrar_fee"]:.2f}</td>
              <td class="td-num" id="oracle-iso27001-total">${benchmarks["iso27001"]["total_cost"]:.2f}</td>
              <td class="td-num">{benchmarks["iso27001"]["auditor_days"]:.1f} Auditor Days</td>
            </tr>
            <tr>
              <td class="td-plan-name">HIPAA HITECH Tier 3 Breach</td>
              <td>45 CFR 160.404 &amp; 42 U.S.C. 1320d-5</td>
              <td class="td-num">${benchmarks["hipaa"]["ocr_civil_penalty"]:.2f}</td>
              <td class="td-num" id="oracle-hipaa-total">${benchmarks["hipaa"]["total_exposure"]:.2f}</td>
              <td class="td-num">{benchmarks["hipaa"]["compromised_records"]:,} ePHI Records</td>
            </tr>
            <tr>
              <td class="td-plan-name">PCI DSS v4.0.1 Level 1 ROC</td>
              <td>PCI SSC v4.0.1 &amp; Req 11.3</td>
              <td class="td-num">$42000.00</td>
              <td class="td-num" id="oracle-pci-total">${benchmarks["pci_dss"]["total_cost"]:.2f}</td>
              <td class="td-num">Level 1 QSA ROC</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="tools-directory-section">
      <h2 class="section-title">Specialized Cyber Compliance &amp; Audit Cost Calculators</h2>
      <ul class="tools-list">
        {''.join(tools_list_html)}
      </ul>
    </section>

    {_build_retro_reflection_block("soc-2-audit-cost-calculator", f"{GAINHELM_CANONICAL_BASE}/")}
    """
    schemas = _calculator_schemas("/", "Enterprise SOC 2 Type II, DoD CMMC 2.0 & NIST 800-171 SPRS Audit Calculator", GAINHELM_SITE_DESCRIPTION)
    schemas.append(_get_gainhelm_organization_schema())
    return _render_base_html(GAINHELM_SITE_TITLE, GAINHELM_SITE_DESCRIPTION, f"{GAINHELM_CANONICAL_BASE}/", body, jsonld_schemas=schemas, css_text=css_text)


def _build_core_tool_html(
    tool: Dict[str, Any],
    all_tools: Sequence[Dict[str, Any]],
    benchmarks: Dict[str, Dict[str, Any]],
    quick_answers: Dict[str, str],
    repo_root: Optional[Path],
    css_text: str,
) -> str:
    slug = tool["slug"]
    title = f"{tool['title']} | GainHelm"
    meta_desc = tool["description"]
    canonical_url = f"{GAINHELM_CANONICAL_BASE}/tools/{slug}/"
    manifest_spec = GAINHELM_FALLBACK_MANIFESTS_MAP.get(slug) or GAINHELM_FALLBACK_MANIFESTS_MAP["soc-2-audit-cost-calculator"]

    schemas = _calculator_schemas(f"/tools/{slug}/", tool["title"], meta_desc)
    schemas.append(_get_gainhelm_organization_schema())
    schemas.append({"@type": "WebPage", "@id": f"{canonical_url}#webpage", "name": title, "description": meta_desc, "url": canonical_url})
    schemas.append(
        {
            "@type": "HowTo",
            "@id": f"{canonical_url}#howto",
            "name": f"How to Calculate {tool['title']}",
            "description": f"Step-by-step statutory procedure for computing {tool['title']}.",
            "url": canonical_url,
            "step": [
                {"@type": "HowToStep", "position": 1, "name": "Define Organizational Headcount & System Scope", "text": "Specify employee headcount, cloud boundaries, and active Trust Services Criteria or NIST SP 800-171 domains.", "url": f"{canonical_url}#step-1"},
                {"@type": "HowToStep", "position": 2, "name": "Compute Accredited External Audit & Assessor Fees", "text": "Calculate CPA firm SSAE 18 fees, C3PAO assessments under 32 CFR Part 170, or ISO/IEC 27006-1 auditor days.", "url": f"{canonical_url}#step-2"},
                {"@type": "HowToStep", "position": 3, "name": "Model Internal Engineering Remediation & GRC Costs", "text": "Apply BLS OEWS SOC 15-1212 ($121.67/hr) loaded wages to remediation hours and GRC platform licensing.", "url": f"{canonical_url}#step-3"},
                {"@type": "HowToStep", "position": 4, "name": "Evaluate Statutory Penalty Exposure & SPRS Risk", "text": "Compare investment against DoD SPRS [-203, +110] bounds and HHS OCR 45 CFR 160.404 caps.", "url": f"{canonical_url}#step-4"},
            ],
        }
    )
    schemas.append(
        {
            "@type": "Dataset",
            "@id": f"{canonical_url}#dataset",
            "name": f"{tool['title']} Statutory Compliance Matrix",
            "description": f"Deterministic enterprise security compliance dataset for {tool['title']}.",
            "url": canonical_url,
            "creator": {"@type": "Organization", "@id": f"{GAINHELM_CANONICAL_BASE}/#organization", "name": GAINHELM_SITE_NAME, "url": GAINHELM_CANONICAL_BASE},
            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        }
    )
    schemas.append(
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{GAINHELM_CANONICAL_BASE}/"},
                {"@type": "ListItem", "position": 2, "name": "Calculators", "item": f"{GAINHELM_CANONICAL_BASE}/tools/"},
                {"@type": "ListItem", "position": 3, "name": tool["title"], "item": canonical_url},
            ],
        }
    )

    quick_answer = quick_answers.get(slug) or tool.get("quick_answer") or GAINHELM_SITE_DESCRIPTION
    related_links = [
        f'<li class="tool-link-item"><a href="/tools/{other["slug"]}/" class="tool-link touch-target">{html.escape(other["title"])}</a></li>'
        for other in all_tools
        if other.get("slug") and other["slug"] != slug
    ][:6]

    scen_a = benchmarks["soc2"]
    scen_b = benchmarks["cmmc"]
    stat_disc = html.escape(GAINHELM_DISCLOSURES["statutory_compliance_disclaimer"])
    aff_disc = html.escape(GAINHELM_DISCLOSURES["ftc_disclosure"])

    body = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <a href="/" class="touch-target">Home</a> / <a href="/tools/" class="touch-target">Calculators</a> / <span>{html.escape(tool["title"])}</span>
    </nav>

    <section class="tool-header hero-section">
      <h1 class="hero-title">{html.escape(tool["title"])}</h1>
      <aside class="quick-answer">
        <p>{html.escape(quick_answer)}</p>
      </aside>
      <p class="hero-desc">{html.escape(tool["description"])}</p>
      <p class="hero-desc" style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">
        Verified Engine: <code>{html.escape(manifest_spec["model_name"])}</code> | {html.escape(manifest_spec["statutory_authority"])}
      </p>
    </section>

    <div class="ymyl-disclaimer-banner" style="margin-bottom: 1.5rem;">
      <p><strong>Statutory Warning:</strong> {stat_disc}</p>
      <p><strong>Publisher Disclosure:</strong> {aff_disc}</p>
    </div>

    {_render_calculator_widget(benchmarks, tool_slug=slug)}

    {_build_partner_cta(slug=slug)}

    {get_gainhelm_tool_commentary(slug)}

    <section class="calculation-scenarios-section" style="margin: 2rem 0;">
      <h2 class="section-title">Statutory Calculation Scenarios &amp; Scope Variants</h2>
      <p class="section-lead">GainHelm evaluates multi-scenario compliance projections across organizational headcount tiers, Trust Services Criteria selections, and unimplemented NIST SP 800-171 control counts to model auditor fees and engineering remediation labor.</p>
      <div class="calculation-variant" data-variant-id="variant-baseline" id="variant-baseline" style="padding: 1.25rem; margin-bottom: 1rem; border: 1px solid var(--border-subtle); border-radius: 8px;">
        <h3 class="variant-title">Scenario A: Mid-Market SaaS SOC 2 Type II Baseline (75 Employees, 3 TSC)</h3>
        <p>Under AICPA SSAE 18 (AT-C Section 205), a 75-employee SaaS company completing a SOC 2 Type II attestation across Security, Availability, and Confidentiality incurs ${scen_a["cpa_audit_fee"]:,.2f} in CPA audit fees, ${scen_a["grc_platform_cost"]:,.2f} in GRC automation, ${scen_a["pentest_fee"]:,.2f} in penetration testing, and ${scen_a["internal_labor_cost"]:,.2f} in engineering labor (${scen_a["total_cost"]:,.2f} total first-year cost).</p>
        <p><a href="#variant-accelerated" class="touch-target">Compare with CMMC 2.0 Level 2 Defense Contractor Scenario B &rarr;</a></p>
      </div>
      <div class="calculation-variant" data-variant-id="variant-accelerated" id="variant-accelerated" style="padding: 1.25rem; margin-bottom: 1rem; border: 1px solid var(--border-subtle); border-radius: 8px;">
        <h3 class="variant-title">Scenario B: Defense Contractor CMMC 2.0 Level 2 C3PAO Certification (75 Employees, 15 Open Controls)</h3>
        <p>Under 32 CFR Part 170 and DFARS 252.204-7021, a 75-employee defense contractor remediating 15 unimplemented NIST SP 800-171 controls incurs ${scen_b["c3pao_assessment_fee"]:,.2f} in accredited C3PAO fees, ${scen_b["enclave_licensing_annual"]:,.2f} in enclave tooling, ${scen_b["remediation_labor_cost"]:,.2f} in engineering labor, and ${scen_b["rpo_advisory_fee"]:,.2f} in RPO advisory (${scen_b["total_cost"]:,.2f} total program cost).</p>
        <p><a href="#variant-baseline" class="touch-target">&larr; Return to SOC 2 Type II Baseline Scenario A</a></p>
      </div>
    </section>

    <section class="calculation-methodology-section">
      <h2 class="section-title">Statutory Compliance &amp; Audit Cost Assessment Procedure</h2>
      <ol class="calculation-steps">
        <li>Establish organizational headcount, cloud enclave boundaries, and in-scope compliance frameworks.</li>
        <li>Apply statutory and accreditation auditor-day schedules (AICPA SSAE 18, 32 CFR Part 170, or ISO/IEC 27006-1:2024).</li>
        <li>Calculate internal engineering remediation hours multiplied by loaded BLS SOC 15-1212 hourly rates.</li>
        <li>Evaluate DoD SPRS score thresholds [-203, +110] and HHS OCR 45 CFR 160.404 civil penalty caps.</li>
      </ol>
    </section>

    <section class="statutory-comparison-table-section">
      <h2 class="section-title">Statutory Compliance Framework Benchmark Overview</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Framework</th>
              <th scope="col">Governing Authority</th>
              <th scope="col">Control Scope</th>
              <th scope="col">Assessor Body</th>
              <th scope="col">Audit Cycle</th>
            </tr>
          </thead>
          <tbody>
            <tr><td class="td-plan-name">SOC 2 Type II</td><td>AICPA SSAE 18 (AT-C 205)</td><td>5 Trust Services Criteria</td><td>Licensed CPA Firm</td><td>Annual (3-12 Mo Window)</td></tr>
            <tr><td class="td-plan-name">CMMC 2.0 Level 2</td><td>32 CFR Part 170 / DFARS 7021</td><td>110 NIST 800-171 Controls</td><td>Cyber-AB Accredited C3PAO</td><td>Triennial + Annual Affirmation</td></tr>
            <tr><td class="td-plan-name">ISO/IEC 27001:2022</td><td>ISO/IEC 27006-1:2024</td><td>Clauses 4-10 + 93 Annex A</td><td>ANAB / UKAS Registrar</td><td>3-Year Cycle + Annual Surveillance</td></tr>
            <tr><td class="td-plan-name">HIPAA Security &amp; Breach</td><td>45 CFR Part 160 / 164</td><td>Administrative, Physical, Technical</td><td>HHS OCR Enforcement</td><td>Continuous Statutory Duty</td></tr>
            <tr><td class="td-plan-name">PCI DSS v4.0.1</td><td>PCI Security Standards Council</td><td>12 Principal Requirements</td><td>Qualified Security Assessor (QSA)</td><td>Annual ROC + Quarterly ASV</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="statutory-provenance-box">
      <h2 class="section-title">Statutory Authority &amp; Provenance Citations</h2>
      <ul>
        <li><strong>Dataset 1:</strong> <a href="https://www.ecfr.gov/current/title-32/subtitle-A/chapter-I/subchapter-G/part-170" target="_blank" rel="noopener noreferrer">DoD CMMC 2.0 Program Rule (32 CFR Part 170) &amp; NIST SP 800-171 Rev 2</a></li>
        <li><strong>Dataset 2:</strong> <a href="https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-160" target="_blank" rel="noopener noreferrer">HHS HIPAA Administrative Simplification &amp; Civil Penalties (45 CFR Part 160)</a></li>
        <li><strong>Dataset 3:</strong> <a href="https://www.bls.gov/oes/current/oes151212.htm" target="_blank" rel="noopener noreferrer">BLS OEWS Information Security Analysts (SOC 15-1212) Wage Series</a></li>
      </ul>
      <p class="statutory-provenance-note">Cryptographic SHA-256 provenance hashes verify mathematical fidelity across all compliance cost and penalty calculations.</p>
    </section>

    <section class="related-tools-section">
      <h2 class="section-title">Related Cyber Compliance &amp; Audit Cost Calculators</h2>
      <ul class="related-tools-list">
        {''.join(related_links)}
      </ul>
    </section>

    {_build_retro_reflection_block(slug, canonical_url)}
    """
    rendered = _render_base_html(title, meta_desc, canonical_url, body, jsonld_schemas=schemas, css_text=css_text)
    return _apply_overlay_if_present(rendered, slug, repo_root)


def _build_tools_directory_html(all_tools: Sequence[Dict[str, Any]], css_text: str) -> str:
    return build_tools_directory_html(
        all_tools=all_tools,
        canonical_base=GAINHELM_CANONICAL_BASE,
        title="Cyber Compliance & Audit Cost Calculators | GainHelm",
        meta_description=(
            "Explore GainHelm's directory of deterministic cyber compliance calculators, "
            "SOC 2 Type II audit cost models, CMMC 2.0 C3PAO estimators, and SPRS tools."
        ),
        hero_title="Cyber Compliance & Audit Cost Calculators Directory",
        hero_desc=(
            "Explore GainHelm's complete directory of deterministic enterprise cybersecurity compliance calculators, "
            "CPA and C3PAO audit fee models, and statutory breach penalty simulators."
        ),
        quick_answer_text=(
            "GainHelm provides an authoritative directory of deterministic enterprise security compliance calculators and audit "
            "scoping engines. CISOs, security architects, and CFOs can model first-year attestation fees, GRC automation ROI, "
            "engineering remediation hours, DoD SPRS scores, and HIPAA civil monetary penalty caps across statutory frameworks."
        ),
        procedure_heading="How to Scope Enterprise Compliance & Audit Budgets",
        procedure_steps=(
            "Select the compliance calculator corresponding to your target regulatory or attestation framework.",
            "Enter organizational headcount, cloud system boundaries, and open control counts.",
            "Review deterministic external auditor fees, engineering labor costs, and 5-point sensitivity matrices.",
        ),
        table_heading="Directory of Cyber Compliance & Audit Calculators",
        grid_heading="All Cyber Compliance Tools",
        default_authority_col="AICPA SSAE 18 / 32 CFR Part 170 / ISO 27006",
        org_schema=_get_gainhelm_organization_schema(),
        render_base_fn=lambda t, d, u, body, jsonld_schemas=None: _render_base_html(
            t, d, u, body, jsonld_schemas=jsonld_schemas, css_text=css_text
        ),
    )


def _build_methodology_html(css_text: str) -> str:
    canonical_url = f"{GAINHELM_CANONICAL_BASE}/methodology/"
    title = "Enterprise Cyber Compliance & Audit Cost Methodology | GainHelm"
    meta_desc = "Authoritative mathematical methodology, statutory citations, auditor-day tables, and BLS security engineering wage rules for GainHelm cyber compliance models."
    body = """
    <article class="article-content">
      <section class="hero-section">
        <h1 class="hero-title">Enterprise Cyber Compliance &amp; Audit Cost Calculation Methodology</h1>
        <p class="hero-desc">GainHelm compiles deterministic financial and regulatory models based directly on federal regulations, accreditation body standards, and Bureau of Labor Statistics wage series.</p>
      </section>
      <aside class="quick-answer">
        <p>GainHelm models enterprise cybersecurity compliance costs, third-party audit fees, and federal statutory penalty exposure using deterministic formulas anchored to AICPA SSAE 18 (AT-C Section 205), 32 CFR Part 170 (CMMC 2.0), NIST SP 800-171 Rev 2, ISO/IEC 27006-1:2024 mandatory auditor-day tables, 45 CFR 160.404 HIPAA civil penalty schedules, and BLS OEWS SOC 15-1212 wage benchmarks.</p>
      </aside>
      <section class="card">
        <h2 class="section-title">1. AICPA SSAE 18 SOC 2 Attestation Fee &amp; Labor Mechanics</h2>
        <p>Pursuant to AICPA SSAE 18 (AT-C Section 205) and TSP Section 100, SOC 2 engagements require an independent CPA firm to examine the Security Common Criteria (CC1 through CC9) and optional Availability, Confidentiality, Processing Integrity, and Privacy categories. Total first-year investment combines peer-reviewed CPA attestation fees, GRC automation licensing, technical penetration testing, and internal security engineering remediation hours multiplied by loaded BLS SOC 15-1212 wages ($121.67/hr).</p>
      </section>
      <section class="card">
        <h2 class="section-title">2. 32 CFR Part 170 CMMC 2.0 &amp; NIST SP 800-171 DoD SPRS Scoring</h2>
        <p>Under 32 CFR Part 170 and DFARS 252.204-7019 / 252.204-7020, defense contractors start at a maximum Supplier Performance Risk System (SPRS) score of +110 across all 110 NIST SP 800-171 Rev 2 controls. Unimplemented controls deduct 5 points (42 foundational architectural controls), 3 points (14 medium-impact controls), or 1 point (54 procedural controls), establishing an exact statutory floor of -203.</p>
      </section>
      <section class="card">
        <h2 class="section-title">3. ISO/IEC 27006-1:2024 Mandatory ISMS Auditor-Day Schedule</h2>
        <p>Accredited ISO/IEC 27001:2022 certification bodies calculate Stage 1 and Stage 2 audit duration from effective ISMS headcount brackets pursuant to ISO/IEC 27006-1:2024:</p>
        <div class="table-wrap">
          <table>
            <thead><tr><th scope="col">Effective ISMS Headcount</th><th scope="col">Initial Audit (Stage 1 + 2)</th><th scope="col">Annual Surveillance</th><th scope="col">Triennial Recertification</th></tr></thead>
            <tbody>
              <tr><td>1 to 10 Employees</td><td>5.0 Auditor Days</td><td>1.7 Auditor Days</td><td>3.5 Auditor Days</td></tr>
              <tr><td>11 to 25 Employees</td><td>6.5 Auditor Days</td><td>2.2 Auditor Days</td><td>4.5 Auditor Days</td></tr>
              <tr><td>26 to 45 Employees</td><td>7.5 Auditor Days</td><td>2.5 Auditor Days</td><td>5.0 Auditor Days</td></tr>
              <tr><td>46 to 65 Employees</td><td>9.0 Auditor Days</td><td>3.0 Auditor Days</td><td>6.0 Auditor Days</td></tr>
              <tr><td>66 to 85 Employees</td><td>11.0 Auditor Days</td><td>3.6 Auditor Days</td><td>7.3 Auditor Days</td></tr>
              <tr><td>86 to 125 Employees</td><td>13.0 Auditor Days</td><td>4.3 Auditor Days</td><td>8.6 Auditor Days</td></tr>
              <tr><td>126 to 175 Employees</td><td>15.0 Auditor Days</td><td>5.0 Auditor Days</td><td>9.9 Auditor Days</td></tr>
              <tr><td>176 to 500 Employees</td><td>13.5 Auditor Days</td><td>4.5 Auditor Days</td><td>9.0 Auditor Days</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </article>"""
    return _render_base_html(title, meta_desc, canonical_url, body, css_text=css_text)


def _build_disclaimers_html(css_text: str) -> str:
    canonical_url = f"{GAINHELM_CANONICAL_BASE}/disclaimers/"
    title = "Cyber Compliance Regulatory Notices & Disclaimers | GainHelm"
    meta_desc = "Review AICPA SSAE 18, DoD 32 CFR Part 170, HHS OCR HIPAA statutory disclaimers, FTC affiliate disclosures, and modeling notices for the GainHelm platform."
    stat_disc = html.escape(GAINHELM_DISCLOSURES["statutory_compliance_disclaimer"])
    aff_disc = html.escape(GAINHELM_DISCLOSURES["ftc_disclosure"])
    no_adv = html.escape(GAINHELM_DISCLOSURES["independent_publisher_disclaimer"])
    body = f"""
    <article class="article-content">
      <section class="hero-section">
        <h1 class="hero-title">Cyber Compliance Regulatory Notices &amp; Disclaimers</h1>
        <p class="hero-desc">Statutory notices, independent attestation boundaries, and FTC 16 CFR Part 255 commercial disclosures governing GainHelm calculators.</p>
      </section>
      <aside class="quick-answer">
        <p>GainHelm is an independent enterprise cybersecurity compliance and financial research publisher providing deterministic audit cost and statutory penalty modeling. All calculations are for informational and budgeting purposes only and do not constitute formal legal counsel, licensed CPA attestation, or accredited C3PAO certification.</p>
      </aside>
      <div class="ymyl-disclaimer-banner">
        <h2 class="section-title">Independent Attestation &amp; Certification Warning</h2>
        <p>{stat_disc}</p>
      </div>
      <section class="card">
        <h2 class="section-title">FTC Affiliate &amp; Partner Disclosure</h2>
        <p>{aff_disc}</p>
      </section>
      <section class="card">
        <h2 class="section-title">No Legal or CPA Attestation Advice Disclaimer</h2>
        <p>{no_adv}</p>
      </section>
      <section class="card">
        <h2 class="section-title">Statutory Disclosures &amp; Regulatory Authorities</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th scope="col">Regulatory Subject</th><th scope="col">Statutory / Standard Authority</th><th scope="col">GainHelm Modeling Scope</th></tr></thead>
            <tbody>
              <tr><td>SOC 2 Attestation Engagements</td><td>AICPA SSAE 18 (AT-C Section 205)</td><td>Deterministic CPA fee and Trust Services Criteria scoping simulations</td></tr>
              <tr><td>DoD CMMC 2.0 &amp; SPRS Scoring</td><td>32 CFR Part 170 &amp; DFARS 252.204-7019</td><td>NIST SP 800-171 weighted score and C3PAO certification cost models</td></tr>
              <tr><td>HIPAA Civil Monetary Penalties</td><td>45 CFR 160.404 &amp; 42 U.S.C. 1320d-5</td><td>Four-tier HHS OCR penalty cap and breach notification cost modeling</td></tr>
              <tr><td>ISO/IEC 27001 &amp; PCI DSS v4.0.1</td><td>ISO/IEC 27006-1:2024 &amp; PCI SSC</td><td>Stage 1/2 registrar auditor-day allocation and QSA ROC cost modeling</td></tr>
              <tr><td>EU DORA &amp; EU AI Act Readiness</td><td>Regulation (EU) 2022/2554 &amp; 2024/1689</td><td>Article 26 TLPT, ICT vendor oversight, and Article 43 conformity modeling</td></tr>
              <tr><td>Commercial Compensation Disclosure</td><td>FTC 16 CFR Part 255</td><td>Independent publisher clear and conspicuous commercial partner disclosure</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </article>"""
    return _render_base_html(title, meta_desc, canonical_url, body, css_text=css_text)


def _write_llms_files(dist: Path, all_tools: Sequence[Dict[str, Any]], quick_answers: Dict[str, str]) -> None:
    statutory_notes = """## Enterprise Cyber Compliance Statutory Parameter Specifications & Formula Definitions
- SOC 2 Attestation (AICPA SSAE 18 / AT-C Section 205): Evaluates Security Common Criteria (CC1-CC9) plus optional Availability, Confidentiality, Processing Integrity, and Privacy under TSP Section 100. Baseline 75-employee SaaS Type II program (3 TSC) equals $78,100.40.
- CMMC 2.0 Level 2 Certification (32 CFR Part 170 & DFARS 252.204-7021): Requires triennial C3PAO assessment across all 110 NIST SP 800-171 Rev 2 controls (320 objectives). Baseline 75-employee defense contractor program equals $132,000.00.
- NIST SP 800-171 DoD SPRS Score (DFARS 252.204-7019 / 7020): Starts at +110 and deducts 5, 3, or 1 points per unimplemented requirement down to -203. Conditional POA&M eligibility requires >= 88 points with zero open 5-point controls.
- ISO/IEC 27001:2022 Certification (ISO/IEC 27006-1:2024): Stage 1 + Stage 2 auditor days scale deterministically from effective ISMS headcount (11.0 auditor days for 66-85 employees; $67,000.40 first-year total).
- HIPAA Civil Monetary Penalties (45 CFR 160.404 & 42 U.S.C. 1320d-5): Four culpability tiers plus 45 CFR Part 164 Subpart D notification and credit monitoring ($2,455,313.00 baseline exposure for 1,500 ePHI records under Tier 3, including the $2,067,813.00 annual penalty cap)."""
    write_llms_files(
        dist=dist,
        property_id="gainhelm",
        domain=GAINHELM_DOMAIN,
        canonical_base=GAINHELM_CANONICAL_BASE,
        header_title="GainHelm - Enterprise Cyber Compliance & Audit Cost Modeling Engine",
        header_tagline="Deterministic SOC 2 Type II, CMMC 2.0, NIST SP 800-171 SPRS, ISO 27001, and HIPAA compliance cost modeling.",
        author=GAINHELM_AUTHOR,
        legal_name=GAINHELM_COMPANY_LEGAL_NAME,
        headquarters=f"{GAINHELM_COMPANY_STREET}, {GAINHELM_COMPANY_CITY}, {GAINHELM_COMPANY_STATE} {GAINHELM_COMPANY_ZIP}",
        query_syntax_params="?employee_headcount={employees}&tsc_criteria_count={tsc}&unimplemented_controls={open_controls}",
        statutory_notes=statutory_notes,
        all_tools=all_tools,
        quick_answers=quick_answers,
    )


_GAINHELM_REDIRECTS = (
    "/calculator / 301\n"
    "/calculators / 301\n"
    "/soc2 /tools/soc-2-audit-cost-calculator/ 301\n"
    "/soc-2 /tools/soc-2-audit-cost-calculator/ 301\n"
    "/cmmc /tools/cmmc-2-0-compliance-cost-calculator/ 301\n"
    "/sprs /tools/nist-800-171-sprs-score-calculator/ 301\n"
    "/iso27001 /tools/iso-27001-certification-cost-calculator/ 301\n"
    "/iso-27001 /tools/iso-27001-certification-cost-calculator/ 301\n"
    "/hipaa /tools/hipaa-violation-penalty-breach-cost-calculator/ 301\n"
    "/pci-dss /tools/pci-dss-4-0-compliance-cost-calculator/ 301\n"
    "/fedramp /tools/fedramp-authorization-3pao-cost-calculator/ 301\n"
    "/hitrust /tools/hitrust-csf-e1-i1-r2-certification-cost-calculator/ 301\n"
    "/pentest /tools/penetration-testing-scoping-cost-calculator/ 301\n"
    "/cyber-insurance /tools/cyber-liability-insurance-breach-exposure-calculator/ 301\n"
    "/how-it-works /methodology/ 301\n"
    "/how-it-works/ /methodology/ 301\n"
)


def compile_gainhelm_estate_impl(
    output_dir: Any,
    run_retrofit: bool = True,
    extra_tools: Optional[List[Dict[str, Any]]] = None,
    high_effort_page_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compiles the complete GainHelm (gainhelm.com) static estate into `output_dir`:
    - Homepage `/` with COMPLIANCE_CALCULATOR_SPEC + dynamic 6-cell oracle benchmarks
    - 10 core tools with COMPLIANCE_CALCULATOR_SPEC (`extra_criteria` only on SOC 2)
    - Deployed voids (`content/deployed_voids.json`) + `extra_tools` compiled via `compile_high_effort_page`
    - Directory `/tools/`, `/methodology/`, `/disclaimers/`, governance routes, `404.html`,
      sitemaps (hubs + leaves = 21 routes), `robots.txt`, `_headers`, `_redirects`, `manifests/*.json`,
      `feed.xml`, `llms.txt`, `llms-full.txt`, `catalog.json`, `media-kit.json`, IndexNow key,
      and Cloudflare Pages `functions/` (zero `dist/functions/` leak).
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.qualification import assert_high_effort_content_qualified

    if high_effort_page_fn is None:
        from pseofactory.compiler import compile_high_effort_page

        high_effort_page_fn = compile_high_effort_page

    root, dist, tools_dir = prepare_estate_dirs(output_dir, "gainhelm")
    manifests_dir = dist / "manifests"
    src_static = root / "gainhelm" / "static"
    if src_static.is_dir():
        shutil.copytree(src_static, dist / "static", dirs_exist_ok=True)
    # Re-ensure Porcelain CSS wins over legacy checked-in gainhelm/static/css/style.css
    from pseofactory.porcelain_shell import generate_porcelain_stylesheet

    css_text = generate_porcelain_stylesheet("gainhelm")
    (dist / "css" / "style.css").write_text(css_text, encoding="utf-8")
    (dist / "static" / "css" / "style.css").write_text(css_text, encoding="utf-8")

    core_tools = [dict(t) for t in GAINHELM_TOOLS]
    core_slugs = {t["slug"] for t in core_tools}
    known_slugs: Set[str] = set(core_slugs)

    void_specs = load_and_enrich_deployed_voids(
        repo_root=root,
        property_id="gainhelm",
        domain=GAINHELM_DOMAIN,
        brand_name=GAINHELM_SITE_NAME,
        canonical_base=GAINHELM_CANONICAL_BASE,
        known_slugs=known_slugs,
        default_authority="AICPA SSAE 18 (AT-C Section 205) & Statutory Cyber Compliance Mandates",
        default_dataset="BLS OEWS Information Security Analysts (SOC 15-1212) Wage Series",
    )
    if extra_tools:
        for et in extra_tools:
            if not isinstance(et, dict) or not et.get("slug"):
                continue
            eslug = str(et["slug"]).strip().lower()
            if eslug and eslug not in known_slugs:
                from pseofactory.pipeline import CompetitorGapEngine, TenantFactStore

                profile = TenantFactStore.get_instance().get_profile("gainhelm")
                es = dict(et)
                es.update({"property_id": "gainhelm", "tenant": "gainhelm", "domain": GAINHELM_DOMAIN, "brand_name": GAINHELM_SITE_NAME, "canonical_base": GAINHELM_CANONICAL_BASE})
                void_specs.append(CompetitorGapEngine(tenant_profile=profile).enrich_candidate_spec(es))
                known_slugs.add(eslug)

    all_tools: List[Dict[str, Any]] = list(core_tools)
    for vs in void_specs:
        all_tools.append(
            {
                "slug": vs["slug"],
                "title": vs.get("title") or vs["slug"].replace("-", " ").title(),
                "short_title": vs.get("short_title") or (vs.get("title") or vs["slug"])[:24],
                "description": vs.get("description") or f"Deterministic cyber compliance calculator for {vs.get('title') or vs['slug']}.",
                "primary_keyword": vs.get("primary_keyword") or vs.get("query") or vs["slug"].replace("-", " "),
                **({"updated_date": vs["updated_date"]} if vs.get("updated_date") else {}),
            }
        )
    all_slugs = [t["slug"] for t in all_tools]

    benchmarks = compute_gainhelm_framework_benchmarks(repo_root=root)
    quick_answers = get_gainhelm_tool_quick_answers()

    (dist / "index.html").write_text(_build_home_html(benchmarks, all_tools, css_text), encoding="utf-8")

    compiled_pages: List[Dict[str, Any]] = []
    catalog_tools: List[Dict[str, Any]] = []

    for tool in core_tools:
        slug = tool["slug"]
        leaf_dir = tools_dir / slug
        leaf_dir.mkdir(parents=True, exist_ok=True)
        leaf_html = _build_core_tool_html(tool, all_tools, benchmarks, quick_answers, root, css_text)
        (leaf_dir / "index.html").write_text(leaf_html, encoding="utf-8")

        m_spec = GAINHELM_FALLBACK_MANIFESTS_MAP[slug]
        manifest_doc = {"slug": slug, **{k: m_spec[k] for k in ("model_name", "statutory_authority", "economic_dataset", "formula", "inputs", "published_output", "sample_calculation", "entity_type")}}
        assert_ai_mode_calculation_manifest(manifest_doc)
        assert_high_effort_content_qualified(manifest_doc, context=f"gainhelm manifest '{slug}'")
        (manifests_dir / f"{slug}.json").write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")

        compiled_pages.append({"slug": slug, "title": tool["title"], "html_path": str(leaf_dir / "index.html"), "published_output": manifest_doc["published_output"]})
        catalog_tools.append({"slug": slug, "title": tool["title"], "url": f"{GAINHELM_CANONICAL_BASE}/tools/{slug}/", "manifest_url": f"{GAINHELM_CANONICAL_BASE}/manifests/{slug}.json", "statutory_authority": manifest_doc["statutory_authority"], "economic_dataset": manifest_doc["economic_dataset"], "formula": manifest_doc["formula"], "published_output": manifest_doc["published_output"]})

    gsc_meta_val, indexnow_stem = _resolve_gainhelm_public_meta()
    for vs in void_specs:
        spec_in = dict(vs)
        spec_in["existing_tool_slugs"] = all_slugs
        spec_in["gsc_verification_token"] = gsc_meta_val
        res = high_effort_page_fn(spec_in)
        slug = res["slug"]
        leaf_dir = tools_dir / slug
        leaf_dir.mkdir(parents=True, exist_ok=True)
        rendered_void = _apply_overlay_if_present(res["html"], slug, root)
        (leaf_dir / "index.html").write_text(rendered_void, encoding="utf-8")
        (manifests_dir / f"{slug}.json").write_text(json.dumps(res["manifest"], indent=2), encoding="utf-8")
        compiled_pages.append({"slug": slug, "title": res["title"], "html_path": str(leaf_dir / "index.html"), "published_output": res["published_output"]})
        catalog_tools.append({"slug": slug, "title": res["title"], "url": f"{GAINHELM_CANONICAL_BASE}/tools/{slug}/", "manifest_url": f"{GAINHELM_CANONICAL_BASE}/manifests/{slug}.json", "statutory_authority": spec_in.get("statutory_authority", ""), "economic_dataset": spec_in.get("economic_dataset", ""), "formula": spec_in.get("formula", ""), "published_output": res["published_output"]})

    (tools_dir / "index.html").write_text(_build_tools_directory_html(all_tools, css_text), encoding="utf-8")
    (dist / "methodology" / "index.html").write_text(_build_methodology_html(css_text), encoding="utf-8")
    (dist / "disclaimers" / "index.html").write_text(_build_disclaimers_html(css_text), encoding="utf-8")
    (dist / "404.html").write_text(_render_base_html("404 Page Not Found | GainHelm", "Requested cyber compliance calculator resource could not be found.", f"{GAINHELM_CANONICAL_BASE}/404.html", "<section class=\"hero-section\"><h1 class=\"hero-title\">404 - Page Not Found</h1><p class=\"hero-desc\">The requested compliance calculator route does not exist.</p><p><a href=\"/tools/\" class=\"btn-cta touch-target\">Browse All Calculators</a></p></section>", css_text=css_text), encoding="utf-8")

    hub_specs = [
        (f"{GAINHELM_CANONICAL_BASE}/", "1.0", "daily"),
        (f"{GAINHELM_CANONICAL_BASE}/tools/", "0.9", "daily"),
        (f"{GAINHELM_CANONICAL_BASE}/methodology/", "0.9", "weekly"),
        (f"{GAINHELM_CANONICAL_BASE}/disclaimers/", "0.9", "weekly"),
        (f"{GAINHELM_CANONICAL_BASE}/about/", "0.7", "monthly"),
        (f"{GAINHELM_CANONICAL_BASE}/privacy/", "0.5", "monthly"),
        (f"{GAINHELM_CANONICAL_BASE}/terms/", "0.5", "monthly"),
        (f"{GAINHELM_CANONICAL_BASE}/contact/", "0.7", "monthly"),
    ]
    gh_ai_bots = ["*", "Googlebot", "Bingbot", "PerplexityBot", "ClaudeBot", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "CCBot", "anthropic-ai", "Cohere-ai", "Applebot", "Applebot-Extended", "Meta-ExternalAgent"]
    write_sitemaps_and_robots(
        dist=dist,
        canonical_base=GAINHELM_CANONICAL_BASE,
        hub_specs=hub_specs,
        leaf_tools=all_tools,
        ai_bots=gh_ai_bots,
        disallow_paths=["/signal/", "/syndication/", "/staging/", "/test/", "/tests/"],
        allow_paths=["/", "/tools/"],
        include_changefreq_and_priority=True,
    )

    header_routes = ["/", "/tools/", "/about/", "/methodology/", "/privacy/", "/terms/", "/disclaimers/", "/contact/"] + [f"/tools/{s}/" for s in all_slugs]
    feed_items = [{"title": t["title"], "url": f"{GAINHELM_CANONICAL_BASE}/tools/{t['slug']}/", "description": t["description"]} for t in all_tools]
    write_machine_endpoints_and_headers(
        dist=dist,
        property_id="gainhelm",
        domain=GAINHELM_DOMAIN,
        canonical_base=GAINHELM_CANONICAL_BASE,
        feed_title=GAINHELM_SITE_TITLE,
        feed_description=GAINHELM_SITE_DESCRIPTION,
        feed_items=feed_items,
        indexnow_key=indexnow_stem,
        catalog_tools=catalog_tools,
        media_kit_payload={"property_id": "gainhelm", "brand_name": GAINHELM_SITE_NAME, "domain": GAINHELM_DOMAIN, "vertical": "enterprise_cyber_compliance_grc_audit", "deliverable_skus": ["gh_soc2_cmmc_audit_workpapers", "gh_hipaa_iso27001_governance_kit", "gh_instant_compliance_worksheet_19"]},
        header_routes=header_routes,
        machine_endpoints=["/feed.xml", "/llms.txt", "/llms-full.txt", "/sitemap.xml", "/sitemap-hubs.xml", "/sitemap-leaves.xml"],
        static_patterns=["/static/*", "/css/*"],
        redirects_content=_GAINHELM_REDIRECTS,
    )
    _write_llms_files(dist, all_tools, quick_answers)

    if not (root / ".pseofactory.json").exists():
        (root / ".pseofactory.json").write_text(json.dumps({"property_id": "gainhelm", "domain": GAINHELM_DOMAIN, "canonical_base": GAINHELM_CANONICAL_BASE, "brand_name": GAINHELM_SITE_NAME, "package_name": "gainhelm", "dist_dir": "dist"}, indent=2) + "\n", encoding="utf-8")
    if not (root / "wrangler.toml").exists():
        (root / "wrangler.toml").write_text('name = "gainhelm"\ncompatibility_date = "2026-09-15"\npages_build_output_dir = "dist"\n\n[vars]\nDOMAIN = "gainhelm.com"\nCANONICAL_BASE = "https://gainhelm.com"\n', encoding="utf-8")
    sync_res = write_tenant_edge_functions(root, dist, "gainhelm")

    retrofit_report = finalize_estate_build(
        root=root,
        dist=dist,
        property_id="gainhelm",
        canonical_base=GAINHELM_CANONICAL_BASE,
        run_retrofit=run_retrofit,
        bad_overlay_tokens=("profithelm", "section-179-calculator", "section-301-tariff", "coinledger", "lienbond"),
    )

    return {
        "status": "PASS",
        "property_id": "gainhelm",
        "domain": GAINHELM_DOMAIN,
        "output_dir": str(root),
        "dist_dir": str(dist),
        "compiled_count": len(compiled_pages),
        "total_assets": len(compiled_pages),
        "compiled_pages": compiled_pages,
        "edge_functions": sync_res,
        "retrofit_report": retrofit_report,
    }
