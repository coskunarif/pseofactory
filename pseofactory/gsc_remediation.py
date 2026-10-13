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
    Calculates expected click lift, CTR deficit, and composite ROI score for a
    GSC query signal or unindexed page diagnosis.
    Ranks:
      1. High-impression CTR shortfall (pos 1-5, high impressions, low CTR)
      2. Striking-distance query (pos 4-20, moderate-high impressions)
      3. Content quality / canonical / depth unindexed defects
      4. Crawl budget signal lag / dead routes
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

    anomaly_type = str(
        data.get("anomaly_type")
        or data.get("classification")
        or data.get("signal_class")
        or ""
    ).strip().upper()

    if not anomaly_type:
        if 1.0 <= position <= 5.0 and actual_ctr < expected_ctr_for_position(position) - 0.005:
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
        if "STRIKING" in anomaly_type:
            # Target top-4 CTR benchmark upon striking-distance overlay lift
            exp_ctr = max(0.08, expected_ctr_for_position(position) + 0.035)
        elif 1.0 <= position <= 10.0:
            exp_ctr = expected_ctr_for_position(position)
        else:
            exp_ctr = 0.045

    ctr_deficit = round(max(0.015, exp_ctr - actual_ctr), 4)

    if "CTR_SHORTFALL" in anomaly_type:
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
    erpm_usd = float(data.get("erpm_usd", default_erpm) or default_erpm)

    commercial_weight = round(1.0 + (cpc / 20.0) + (erpm_usd / 200.0), 4)
    roi_score = round(expected_click_lift * commercial_weight, 4)

    return {
        "tenant_id": resolved_tenant,
        "anomaly_type": anomaly_type,
        "action_type": action_type,
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

    cand = f"{base}{suffix}"
    if 50 <= len(cand) <= 60:
        return cand

    # Pad if shorter than 50 chars
    pad_tokens = (
        ["2026", "Model", "Tool", "Guide", "Rules", "Engine"]
        if tenant_id == "prexvo"
        else ["2026", "Tax", "Model", "Tool", "Guide", "Engine"]
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

    words = [w.upper() if w.lower() in ("irc", "irs", "rap", "ibr", "pslf", "paye", "icr", "agi", "saas", "gaap") else w.capitalize() for w in query_clean.split() if w]
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
        hub_links = [
            {"anchor": "Title IV Student Loan Calculators Directory", "href": "/tools/"},
            {"anchor": "RAP vs IBR Monthly Payment Calculator", "href": "/tools/rap-vs-ibr-calculator/"},
            {"anchor": "PSLF 120 Qualifying Payment Simulator", "href": "/tools/pslf-qualifying-payment-simulator/"},
        ]
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
        hub_links = [
            {"anchor": "Statutory Tax & Financial Calculators Directory", "href": "/tools/"},
            {"anchor": "Section 179 Equipment Deduction Calculator", "href": "/tools/section-179-calculator/"},
            {"anchor": "Section 1031 Like-Kind Exchange Calculator", "href": "/tools/section-1031-calculator/"},
        ]

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

    return {
        "slug": slug,
        "property_id": resolved_tenant,
        "tenant_id": resolved_tenant,
        "target_url": target_url,
        "query": query_clean,
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
    Returns candidates sorted by (-roi_score, target_url).
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

    prioritized: List[Dict[str, Any]] = []
    for item in raw_items:
        if hasattr(item, "to_dict"):
            rec = dict(item.to_dict())
        elif isinstance(item, dict):
            rec = dict(item)
        else:
            continue

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

    prioritized.sort(key=lambda x: (-float(x.get("roi_score", 0.0)), str(x.get("target_url", ""))))
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

    # 3. Upgrade .quick-answer if quick_answer is present
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

    injected_sections: List[str] = []

    # 4a. Injected H2 Headings
    h2_headings = overlay_data.get("h2_headings", [])
    if h2_headings:
        h2_parts = ['<section class="overlay-section overlay-headings" style="margin-top: 2rem; margin-bottom: 2rem;">']
        for h2 in h2_headings:
            clean_h2 = html_lib.escape(_strip_forbidden_dashes(str(h2)))
            h2_parts.append(f'  <h2 class="section-title" style="font-size: 1.5rem; font-weight: 700; margin-bottom: 0.75rem;">{clean_h2}</h2>')
            h2_parts.append(f'  <p class="section-desc" style="color: var(--text-secondary, #64748b); margin-bottom: 1.5rem;">Statutory analysis and compliance guidelines for {clean_h2}.</p>')
        h2_parts.append("</section>")
        injected_sections.append("\n".join(h2_parts))

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
    if hub_links:
        hl_parts = [
            '<section class="overlay-section overlay-hub-links" style="margin-top: 1.5rem; margin-bottom: 1.5rem;">',
            '  <h3 class="section-subtitle" style="font-size: 1.15rem; font-weight: 600; margin-bottom: 0.75rem;">Related Statutory Hubs</h3>',
            '  <ul class="overlay-hub-list">',
        ]
        for hl in hub_links:
            if isinstance(hl, dict) and hl.get("href") and hl.get("anchor"):
                href = html_lib.escape(str(hl["href"]))
                anchor = html_lib.escape(_strip_forbidden_dashes(str(hl["anchor"])))
                hl_parts.append(f'    <li><a href="{href}" class="touch-target">{anchor}</a></li>')
        hl_parts.extend(["  </ul>", "</section>"])
        injected_sections.append("\n".join(hl_parts))

    # 5. Injected FAQ Additions & FAQPage Schema
    raw_faqs = overlay_data.get("faq_entries") or overlay_data.get("faq_additions") or overlay_data.get("faq_schema") or []
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
        if "</main>" in html:
            html = html.replace("</main>", f"{overlay_markup}\n</main>", 1)
        else:
            html = f"{html}\n{overlay_markup}"

    return _strip_forbidden_dashes(html)


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
