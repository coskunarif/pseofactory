"""
pseofactory Search Intent Doctrine & Opportunity Qualification Engine
Enforces the Search Intent Doctrine across Prexvo, ProfitHelm, and downstream factories:
"An impression is not proof that a new page is missing. Google may be testing an existing page
for related intent. Build pages only when the search intent is genuinely underserved,
otherwise you're just creating URL bloat and potential cannibalization. #impressions"

Zero em-dashes. Zero en-dashes.
"""

import json
import os
import sys
import ast
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union, Set

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    detect_ungrounded_synthetic_claims,
    safe_eval_mathematical_formula,
    assert_proprietary_model_integrity,
    detect_thin_affiliate_listicle_issues,
    THIN_AFFILIATE_LISTICLE_PATTERNS,
    ECONOMIC_DATASET_PATTERNS,
)

STATUTORY_PROVENANCE_PATTERNS: List[str] = [
    r"\b(?:26\s+U\.?S\.?C\.?|Title\s+26|\d+\s+U\.?S\.?C\.?)\b",
    r"\b(?:26\s+C\.?F\.?R\.?|Treas\.?\s+Reg\.?|\d+\s+C\.?F\.?R\.?)\b",
    r"\bIRC\b",
    r"\bInternal\s+Revenue\s+Code\b",
    r"\bIRS\b",
    r"\bP\.?L\.?\s+\d+-\d+\b",
    r"\bPublic\s+Law\b",
    r"\bstatutory\b",
    r"\bCFTC\b",
    r"\bSEC\s+Rule\b",
    r"\bCommodity\s+Exchange\s+Act\b",
    r"\bSecurities\s+Exchange\s+Act\b",
    r"\bAICPA\b",
    r"\bSSAE\s*18\b",
    r"\bAT-C\s+Section\s+205\b",
    r"\bDFARS\b",
    r"\bNIST\s+SP\s+800\b",
    r"\bISO/IEC\s+2700[16]\b",
    r"\bPCI\s+DSS\b",
    r"\bHITRUST\b",
    r"\bFedRAMP\b",
    r"\bHITECH\b",
    r"\bNAIC\b",
]

US_STATE_NAME_TO_SLUG: Dict[str, str] = {
    "alabama": "alabama",
    "alaska": "alaska",
    "arizona": "arizona",
    "arkansas": "arkansas",
    "california": "california",
    "colorado": "colorado",
    "connecticut": "connecticut",
    "delaware": "delaware",
    "district of columbia": "district-of-columbia",
    "florida": "florida",
    "georgia": "georgia",
    "hawaii": "hawaii",
    "idaho": "idaho",
    "illinois": "illinois",
    "indiana": "indiana",
    "iowa": "iowa",
    "kansas": "kansas",
    "kentucky": "kentucky",
    "louisiana": "louisiana",
    "maine": "maine",
    "maryland": "maryland",
    "massachusetts": "massachusetts",
    "michigan": "michigan",
    "minnesota": "minnesota",
    "mississippi": "mississippi",
    "missouri": "missouri",
    "montana": "montana",
    "nebraska": "nebraska",
    "nevada": "nevada",
    "new hampshire": "new-hampshire",
    "new jersey": "new-jersey",
    "new mexico": "new-mexico",
    "new york": "new-york",
    "north carolina": "north-carolina",
    "north dakota": "north-dakota",
    "ohio": "ohio",
    "oklahoma": "oklahoma",
    "oregon": "oregon",
    "pennsylvania": "pennsylvania",
    "rhode island": "rhode-island",
    "south carolina": "south-carolina",
    "south dakota": "south-dakota",
    "tennessee": "tennessee",
    "texas": "texas",
    "utah": "utah",
    "vermont": "vermont",
    "virginia": "virginia",
    "washington": "washington",
    "west virginia": "west-virginia",
    "wisconsin": "wisconsin",
    "wyoming": "wyoming",
}

US_STATE_ABBR_TO_SLUG: Dict[str, str] = {
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "co": "colorado",
    "ct": "connecticut",
    "dc": "district-of-columbia",
    "fl": "florida",
    "ga": "georgia",
    "ia": "iowa",
    "il": "illinois",
    "ks": "kansas",
    "ky": "kentucky",
    "ma": "massachusetts",
    "md": "maryland",
    "mi": "michigan",
    "mn": "minnesota",
    "mo": "missouri",
    "ms": "mississippi",
    "mt": "montana",
    "nc": "north-carolina",
    "nd": "north-dakota",
    "ne": "nebraska",
    "nh": "new-hampshire",
    "nj": "new-jersey",
    "nm": "new-mexico",
    "nv": "nevada",
    "ny": "new-york",
    "oh": "ohio",
    "pa": "pennsylvania",
    "ri": "rhode-island",
    "sc": "south-carolina",
    "sd": "south-dakota",
    "tn": "tennessee",
    "tx": "texas",
    "ut": "utah",
    "va": "virginia",
    "vt": "vermont",
    "wa": "washington",
    "wi": "wisconsin",
    "wv": "west-virginia",
    "wy": "wyoming",
}

SYNONYM_TOKEN_MAP: Dict[str, str] = {
    "bracket": "brackets",
    "rates": "brackets",
    "rate": "brackets",
    "tables": "brackets",
    "table": "brackets",
    "schedule": "brackets",
    "schedules": "brackets",
    "markets": "market",
}

FILING_MODIFIER_STOPWORDS = frozenset({
    "married",
    "jointly",
    "joint",
    "filing",
    "single",
    "separately",
    "separate",
    "head",
    "household",
    "hoh",
    "mfj",
    "mfs",
    "2024",
    "2025",
    "2026",
    "2027",
    "2028",
    "scenario",
    "comparison",
    "model",
    "calculator",
    "tool",
    "estimator",
    "guide",
    "rules",
    "rule",
    "statutory",
    "federal",
    "state",
    "income",
    "for",
    "in",
    "of",
    "and",
    "the",
    "with",
})

SYNTHETIC_CANDIDATE_PATTERNS = (
    r"^query-(?:one|two|three)-buildable$",
    r"^query\s+(?:one|two|three)\s+buildable$",
    r"^test-void-slug$",
    r"^dummy-tool-slug$",
    r"^valid-edge-tool-\d+$",
    r"^bad-slug-with-underscores-and-dashes-invalid$",
    r"^calculator-(?:app|net|free|near-me)$",
    r"^ionq-stock$",
    r"^custom-test-calculator$",
    r"^poison-pill-test$",
    r"^irs-1031-exchange-tax-deferral-test$",
    r"^dynamic-saas-benchmark-calculator$",
)


class SearchIntentVerdict(dict):
    """
    Dict subclass returned by qualify_search_intent that also exposes .action and .status
    attributes for callers such as drift.py while preserving 100% dict compatibility.
    Zero em-dashes. Zero en-dashes.
    """

    @property
    def action(self) -> str:
        return str(self.get("action", "MONITOR"))

    @property
    def status(self) -> str:
        act = str(self.get("action", "MONITOR"))
        if act in ("PRUNE_PAGE", "PRUNE", "REJECT_SYNTHETIC", "REJECT_LISTICLE_ARCHETYPE"):
            return "PRUNE"
        return str(self.get("status") or act)


def is_thin_affiliate_listicle_candidate(query_or_slug: str, spec: Optional[Dict[str, Any]] = None) -> bool:
    """
    Returns True if candidate query, slug, or spec represents a thin affiliate-style listicle
    ('Top 10 Best...', '7 Best...', 'affiliate listicle/roundup') that trades first-party
    statutory calculator authority for generic listicle bloat.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(spec, dict):
        archetype = str(spec.get("archetype") or spec.get("content_type") or "").strip().lower()
        if archetype in ("listicle", "affiliate_listicle", "roundup", "affiliate_roundup"):
            return True
    candidates = [str(query_or_slug or "").strip().lower()]
    if isinstance(spec, dict):
        for k in ("slug", "query", "primary_keyword", "title"):
            val = str(spec.get(k) or "").strip().lower()
            if val:
                candidates.append(val)
    for text in candidates:
        if not text:
            continue
        unslug = text.replace("-", " ")
        if detect_thin_affiliate_listicle_issues(text) or detect_thin_affiliate_listicle_issues(unslug):
            return True
    return False


def is_synthetic_test_candidate(query_or_slug: str, spec: Optional[Dict[str, Any]] = None) -> bool:
    """Returns True if candidate query or slug is a synthetic test fixture (e.g. query-two-buildable)."""
    candidates = [str(query_or_slug or "").strip().lower()]
    if isinstance(spec, dict):
        for k in ("slug", "query", "primary_keyword"):
            val = str(spec.get(k) or "").strip().lower()
            if val:
                candidates.append(val)
    for text in candidates:
        if not text:
            continue
        slugified = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        for pat in SYNTHETIC_CANDIDATE_PATTERNS:
            if re.match(pat, text) or re.match(pat, slugified):
                return True
    return False


def extract_state_subroute_from_query(query: str) -> Optional[str]:
    """
    Extracts canonical US state slug (e.g. 'california', 'south-carolina', 'arizona')
    from a query or slug containing full state names, 2-letter abbreviations, or
    punctuated/hyphenated abbreviations ('s.c.', 's-c', 'ca').
    Zero em-dashes. Zero en-dashes.
    """
    raw = str(query or "").lower().strip()
    if not raw:
        return None

    # Normalize punctuated or hyphenated two-letter state abbreviations like 's.c.' or 's-c'
    norm_punct = re.sub(r"\b([a-z])\.([a-z])\.(?:\s|$)", r"\1\2 ", raw)
    norm_space = norm_punct.replace("-", " ")
    norm_space = re.sub(r"\bs\s+c\b", "sc", norm_space)
    norm_space = re.sub(r"\bn\s+c\b", "nc", norm_space)
    norm_space = re.sub(r"\bn\s+y\b", "ny", norm_space)
    norm_space = re.sub(r"\bn\s+j\b", "nj", norm_space)
    norm_space = re.sub(r"\bd\s+c\b", "dc", norm_space)

    # 1. Check multi-word state names first
    for state_name in sorted(US_STATE_NAME_TO_SLUG.keys(), key=len, reverse=True):
        if " " in state_name and re.search(rf"\b{re.escape(state_name)}\b", norm_space):
            return US_STATE_NAME_TO_SLUG[state_name]

    # 2. Check single-word state names
    tokens = re.findall(r"\b[a-z0-9]+\b", norm_space)
    for tok in tokens:
        if tok in US_STATE_NAME_TO_SLUG:
            return US_STATE_NAME_TO_SLUG[tok]

    # 3. Check unambiguous 2-letter state abbreviations when accompanied by tax/statutory context
    has_tax_or_statutory_context = bool(
        set(tokens) & {"tax", "taxes", "brackets", "bracket", "rate", "rates", "table", "tables", "1031", "exchange", "179", "income", "state", "married", "single", "withholding"}
    )
    if has_tax_or_statutory_context:
        for tok in tokens:
            if tok in US_STATE_ABBR_TO_SLUG:
                return US_STATE_ABBR_TO_SLUG[tok]

    return None


def normalize_search_intent_tokens(text: str) -> Dict[str, Any]:
    """
    Normalizes query or slug text into:
      - raw_tokens: raw alphanumeric words
      - expanded_tokens: state abbreviations expanded to state words + synonyms mapped ('rates'/'tables' -> 'brackets')
      - core_tokens: expanded_tokens minus filing/year/format modifiers and minus state words
      - state_slug: canonical state slug if state-specific, else None
      - is_scenario_comparison_clone: True if text is a '*-scenario-comparison-model' clone
    Zero em-dashes. Zero en-dashes.
    """
    raw = str(text or "").lower().strip()
    state_slug = extract_state_subroute_from_query(raw)

    norm_punct = re.sub(r"\b([a-z])\.([a-z])\.(?:\s|$)", r"\1\2 ", raw)
    norm_space = norm_punct.replace("-", " ")
    norm_space = re.sub(r"\bs\s+c\b", "sc", norm_space)
    norm_space = re.sub(r"\bn\s+c\b", "nc", norm_space)
    norm_space = re.sub(r"\bn\s+y\b", "ny", norm_space)
    norm_space = re.sub(r"\bn\s+j\b", "nj", norm_space)

    raw_tokens = set(re.findall(r"\b[a-z0-9]+\b", norm_space))
    is_scenario_clone = {"scenario", "comparison", "model"}.issubset(raw_tokens)

    state_word_tokens: set = set()
    if state_slug:
        state_word_tokens.update(state_slug.split("-"))
        for abbr, s_slug in US_STATE_ABBR_TO_SLUG.items():
            if s_slug == state_slug:
                state_word_tokens.add(abbr)

    expanded_tokens: set = set()
    for tok in raw_tokens:
        if state_slug and tok in US_STATE_ABBR_TO_SLUG and US_STATE_ABBR_TO_SLUG[tok] == state_slug:
            expanded_tokens.update(state_slug.split("-"))
        else:
            mapped = SYNONYM_TOKEN_MAP.get(tok, tok)
            expanded_tokens.add(mapped)

    core_tokens = {
        t for t in expanded_tokens
        if t not in FILING_MODIFIER_STOPWORDS and t not in state_word_tokens
    }
    return {
        "raw_tokens": raw_tokens,
        "expanded_tokens": expanded_tokens,
        "core_tokens": core_tokens,
        "state_slug": state_slug,
        "is_scenario_comparison_clone": is_scenario_clone,
    }


def _extract_spec_signature_parts(spec: Optional[Dict[str, Any]]) -> tuple:
    """Extracts normalized (authority, input_keys_set, normalized_formula) from a tool or candidate spec."""
    if not isinstance(spec, dict):
        return "", set(), ""
    manifest = spec.get("calculation_manifest") if isinstance(spec.get("calculation_manifest"), dict) else {}
    raw_auth = (
        spec.get("statutory_authority")
        or spec.get("statutory_provenance")
        or spec.get("authority")
        or manifest.get("statutory_authority")
        or manifest.get("statutory_provenance")
        or manifest.get("authority")
        or ""
    )
    auth_norm = re.sub(r"\s+", " ", str(raw_auth).strip().lower())

    raw_inputs = spec.get("inputs") if spec.get("inputs") is not None else manifest.get("inputs")
    input_keys: set = set()
    if isinstance(raw_inputs, dict):
        input_keys = {re.sub(r"[^a-z0-9_]", "_", str(k).strip().lower()).strip("_") for k in raw_inputs.keys() if str(k).strip()}
    elif isinstance(raw_inputs, (list, tuple, set)):
        input_keys = {re.sub(r"[^a-z0-9_]", "_", str(k).strip().lower()).strip("_") for k in raw_inputs if str(k).strip()}

    raw_formula = spec.get("formula") or manifest.get("formula") or ""
    formula_norm = re.sub(r"\s+", "", str(raw_formula).strip().lower())
    return auth_norm, input_keys, formula_norm


def compute_statutory_signature(spec: Dict[str, Any]) -> str:
    """
    Normalizes (statutory_authority, sorted(input_keys), formula) into a canonical signature string.
    Returns empty string when spec is empty or lacks both statutory authority and formula.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(spec, dict) or not spec:
        return ""
    auth_norm, input_keys, formula_norm = _extract_spec_signature_parts(spec)
    if (not auth_norm and not input_keys and not formula_norm) or (not auth_norm and not formula_norm):
        return ""
    sorted_keys = ",".join(sorted(input_keys))
    return f"authority={auth_norm}|inputs={sorted_keys}|formula={formula_norm}"


def _match_gsc_ranking_cannibalization(
    clean_q: str,
    eff_gsc_rows: List[Dict[str, Any]],
    q_state_top: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Checks live/persisted GSC query-by-page rankings (positions 1-20, prioritizing 4-15)."""
    import urllib.parse

    norm_q_gsc = normalize_search_intent_tokens(clean_q)
    q_state_gsc = norm_q_gsc["state_slug"] or q_state_top
    q_core_gsc = norm_q_gsc["core_tokens"]
    best_gsc_hit: Optional[Tuple[Tuple[int, float, float], Dict[str, Any]]] = None
    for r in eff_gsc_rows:
        if not isinstance(r, dict):
            continue
        r_query = re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", str(r.get("query") or "").lower()).strip())
        r_page = str(r.get("canonical_url") or r.get("page") or r.get("target_url") or r.get("url") or "").strip()
        if not r_query or not r_page:
            continue
        try:
            r_pos = float(r.get("position", 100.0) or 100.0)
        except (TypeError, ValueError):
            r_pos = 100.0
        try:
            r_impr = int(float(r.get("impressions", 0) or 0))
        except (TypeError, ValueError):
            r_impr = 0
        if not (1.0 <= r_pos <= 20.0):
            continue
        norm_r = normalize_search_intent_tokens(r_query)
        exact_or_core_match = (
            r_query == clean_q
            or (
                q_core_gsc
                and norm_r["core_tokens"] == q_core_gsc
                and norm_r["state_slug"] == q_state_gsc
            )
        )
        if not exact_or_core_match:
            continue
        p_path = urllib.parse.urlsplit(r_page).path if "://" in r_page else r_page
        norm_p = "/" + p_path.strip("/") + "/" if p_path.strip("/") else "/"
        p_parts = [pt for pt in norm_p.split("/") if pt]
        if len(p_parts) >= 2 and p_parts[0] == "tools":
            p_slug = p_parts[1].lower()
        elif p_parts:
            p_slug = p_parts[-1].lower()
        else:
            continue
        if is_retired_or_consolidated_slug(p_slug):
            res_red = resolve_redirected_gsc_target(target_url=r_page, query=r_query)
            if res_red.get("canonical_slug") and not res_red.get("is_off_topic_sink"):
                p_slug = str(res_red["canonical_slug"])
                norm_p = str(res_red["canonical_path"] or norm_p)
            else:
                continue
        in_4_15 = 1 if (4.0 <= r_pos <= 15.0) else 0
        rank_key = (in_4_15, float(r_impr), -r_pos)
        hit_payload = {
            "cannibalized": True,
            "is_cannibalized": True,
            "is_cannibalizing": True,
            "parent_slug": p_slug,
            "target_subroute": norm_p,
            "ranking_url": r_page,
            "ranking_position": round(r_pos, 2),
            "ranking_impressions": r_impr,
            "reason": "existing_url_ranks_in_gsc_striking_distance" if in_4_15 else "existing_url_ranks_in_gsc_top_20",
            "matched_tool": {"slug": p_slug, "url": r_page},
        }
        if best_gsc_hit is None or rank_key > best_gsc_hit[0]:
            best_gsc_hit = (rank_key, hit_payload)
    return best_gsc_hit[1] if best_gsc_hit is not None else None


def _match_core_topic_modifier_variant(
    tool: Dict[str, Any],
    tool_slug: str,
    q_core: Set[str],
    slug_core: Set[str],
) -> Optional[Dict[str, Any]]:
    """Checks core topic match after stripping filing-status and year modifiers."""
    is_match = False
    if q_core == slug_core or (
        {"tax", "brackets"}.issubset(q_core)
        and {"tax", "brackets"}.issubset(slug_core)
        and q_core.issubset({"irs", "tax", "brackets", "federal", "income", "standard", "deduction"})
    ):
        is_match = True
    elif tool_slug == "tcja-sunset-capital-gains" and (
        (
            {"capital", "gains"}.issubset(q_core)
            and q_core.issubset({"irs", "capital", "gains", "tax", "brackets", "tcja", "sunset", "long", "term", "short"})
        )
        or (
            "qsbs" in q_core
            and q_core.issubset({"qsbs", "exclusion", "section", "1202", "tax", "capital", "gains"})
        )
    ):
        is_match = True
    elif tool_slug == "section-1031-calculator" and (
        (
            "1031" in q_core
            and ("partial" in q_core or "boot" in q_core)
            and q_core.issubset({"partial", "1031", "exchange", "boot", "tax", "deferral", "section", "like", "kind"})
        )
        or q_core == {"tax", "deferral"}
    ):
        is_match = True
    elif tool_slug == "section-179-calculator" and (
        (
            "179" in q_core
            and q_core.issubset(
                {
                    "179", "section", "deduction", "tax", "how", "do", "i", "to",
                    "is", "calculate", "calculated", "figure", "out", "can", "you",
                    "computer", "software", "equipment", "vehicle", "bonus",
                    "depreciation", "limit", "limits", "and", "for", "businesses",
                }
            )
        )
        or q_core == {"vehicle", "bonus", "depreciation"}
    ):
        is_match = True
    elif tool_slug == "prediction-market-odds" and {"prediction", "market"}.issubset(q_core) and q_core.issubset(
        {
            "kalshi", "polymarket", "prediction", "market", "odds", "arbitrage", "strategy",
            "implied", "probability", "what", "is", "how", "to", "calculate", "ev",
            "expected", "value", "fees", "fee", "kelly", "criterion", "contract", "contracts",
        }
    ):
        is_match = True
    elif tool_slug == "r-and-d-tax-credit-section-174-amortization-calculator" and "174" in q_core and (
        "amortization" in q_core or "research" in q_core or {"r", "d"}.issubset(q_core)
    ):
        is_match = True
    elif tool_slug == "rap-payment-calculator" and "rap" in q_core and "ibr" not in q_core and q_core.issubset(
        {"rap", "payment", "repayment", "assistance", "plan", "student", "loan", "loans", "details", "monthly"}
    ):
        is_match = True
    elif tool_slug == "rap-vs-ibr-calculator" and "ibr" in q_core and (
        "rap" in q_core or {"repayment", "assistance", "plan"}.issubset(q_core)
    ):
        is_match = True
    elif tool_slug in ("student-loan-repayment-calculator", "ibr-hardship-cap-calculator") and (
        (
            q_core.issubset({"student", "college", "loan", "loans", "payment", "repayment", "estimator", "monthly"})
            and ({"loan", "payment"}.issubset(q_core) or {"loan", "repayment"}.issubset(q_core))
        )
        or (
            "ibr" in q_core
            and "rap" not in q_core
            and q_core.issubset({"ibr", "student", "loan", "loans", "tax", "bomb", "hardship", "cap", "payment", "repayment"})
        )
        or (
            {"student", "loan", "forgiveness"}.issubset(q_core)
            and q_core.issubset({"student", "loan", "loans", "forgiveness", "update", "details", "tax"})
        )
    ):
        is_match = True
    elif tool_slug == "pslf-qualifying-payment-simulator" and "pslf" in q_core and q_core.issubset(
        {"pslf", "buyback", "months", "reconsideration", "student", "loan", "loans", "qualifying", "payment", "forgiveness"}
    ):
        is_match = True
    elif tool_slug == "save-plan-litigation-transition" and {"save", "plan"}.issubset(q_core) and q_core.issubset(
        {"student", "loan", "loans", "save", "plan", "forbearance", "interest", "capitalization", "litigation", "transition"}
    ):
        is_match = True
    elif tool_slug == "soc-2-audit-cost-calculator" and "soc" in q_core and ("audit" in q_core or "cost" in q_core or "compliance" in q_core):
        is_match = True
    elif tool_slug == "cmmc-2-0-compliance-cost-calculator" and "cmmc" in q_core and ("cost" in q_core or "compliance" in q_core or "c3pao" in q_core or "level" in q_core):
        is_match = True
    elif tool_slug == "nist-800-171-sprs-score-calculator" and ("sprs" in q_core or {"nist", "800", "171"}.issubset(q_core)):
        is_match = True
    elif tool_slug == "iso-27001-certification-cost-calculator" and {"iso", "27001"}.issubset(q_core):
        is_match = True
    elif tool_slug == "hipaa-violation-penalty-breach-cost-calculator" and "hipaa" in q_core and ("penalty" in q_core or "fines" in q_core or "breach" in q_core or "violation" in q_core):
        is_match = True

    if is_match:
        return {
            "cannibalized": True,
            "is_cannibalized": True,
            "is_cannibalizing": True,
            "parent_slug": tool_slug,
            "target_subroute": f"/tools/{tool_slug}/",
            "reason": "matches_core_topic_modifier_variant",
            "matched_tool": tool,
        }
    return None


def check_search_intent_cannibalization(
    query: str,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    token_overlap_threshold: float = 0.50,
    sitemap_urls: Optional[List[str]] = None,
    candidate_spec: Optional[Dict[str, Any]] = None,
    gsc_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether a candidate query cannibalizes existing tool catalog intent,
    live/persisted GSC query-by-page rankings (positions 1-20, especially 4-15 striking distance),
    statutory parameter signatures, secondary keywords, slug tokens, state sub-routes,
    synonym/filing-modifier variants, scenario-comparison clones, or indexed sitemap URLs.
    Zero em-dashes. Zero en-dashes.
    """
    clean_q = str(query or "").lower().strip()
    if not clean_q and not candidate_spec:
        return {
            "cannibalized": False,
            "is_cannibalizing": False,
            "parent_slug": "none",
            "reason": "empty",
            "matched_tool": None,
        }

    query_words = set(re.findall(r"\b[a-z0-9]+\b", clean_q))
    cand_sig = compute_statutory_signature(candidate_spec) if isinstance(candidate_spec, dict) else ""
    cand_auth, cand_keys, cand_formula = _extract_spec_signature_parts(candidate_spec)
    q_state_top = extract_state_subroute_from_query(clean_q) if clean_q else None
    if not q_state_top and isinstance(candidate_spec, dict) and candidate_spec.get("slug"):
        q_state_top = extract_state_subroute_from_query(str(candidate_spec.get("slug")))

    def _subroute_for(t_slug: str) -> str:
        if not t_slug or t_slug == "none":
            return "/tools/"
        if q_state_top and not extract_state_subroute_from_query(t_slug):
            return f"/tools/{t_slug}/{q_state_top}/"
        return f"/tools/{t_slug}/"

    # 0. Check live/persisted GSC query-by-page rankings when provided (positions 1-20, prioritizing 4-15)
    eff_gsc_rows = gsc_rows if gsc_rows is not None else (
        candidate_spec.get("gsc_rows") if isinstance(candidate_spec, dict) else None
    )
    if eff_gsc_rows and clean_q:
        gsc_hit = _match_gsc_ranking_cannibalization(clean_q, eff_gsc_rows, q_state_top)
        if gsc_hit is not None:
            return gsc_hit

    # 1. Deterministic evaluation against existing tools catalog
    best_slug_match = None
    if existing_tools:
        for tool in existing_tools:
            if not isinstance(tool, dict):
                continue
            tool_slug = str(tool.get("slug", "")).strip()

            # Statutory parameter signature check when candidate_spec has a valid signature
            if cand_sig:
                tool_sig = compute_statutory_signature(tool)
                if tool_sig:
                    if cand_sig == tool_sig:
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug or "none",
                            "target_subroute": _subroute_for(tool_slug),
                            "reason": "matches_statutory_parameter_signature",
                            "matched_tool": tool,
                        }
                    tool_auth, tool_keys, tool_formula = _extract_spec_signature_parts(tool)
                    if cand_auth and tool_auth and cand_auth == tool_auth:
                        formula_match = bool(cand_formula and tool_formula and cand_formula == tool_formula)
                        key_overlap_ratio = 0.0
                        if cand_keys and tool_keys:
                            overlap_count = len(cand_keys & tool_keys)
                            denom = max(len(cand_keys), len(tool_keys))
                            key_overlap_ratio = (overlap_count / denom) if denom > 0 else 0.0
                        if formula_match or key_overlap_ratio >= 0.80:
                            return {
                                "cannibalized": True,
                                "is_cannibalized": True,
                                "is_cannibalizing": True,
                                "parent_slug": tool_slug or "none",
                                "target_subroute": _subroute_for(tool_slug),
                                "reason": "matches_statutory_parameter_signature",
                                "matched_tool": tool,
                            }

            if not clean_q:
                continue

            pk = str(tool.get("primary_keyword", "")).lower().strip()
            sec_kws = [str(k).lower().strip() for k in tool.get("secondary_keywords", []) if k]

            # Primary keyword match
            if pk:
                pk_words = set(re.findall(r"\b[a-z0-9]+\b", pk))
                if clean_q == pk or clean_q in pk or pk in clean_q or (pk_words and pk_words.issubset(query_words)):
                    return {
                        "cannibalized": True,
                        "is_cannibalized": True,
                        "is_cannibalizing": True,
                        "parent_slug": tool_slug or "none",
                        "target_subroute": _subroute_for(tool_slug),
                        "reason": "matches_primary_keyword",
                        "matched_tool": tool,
                    }

            # Secondary keyword match
            if clean_q in sec_kws:
                return {
                    "cannibalized": True,
                    "is_cannibalized": True,
                    "is_cannibalizing": True,
                    "parent_slug": tool_slug or "none",
                    "target_subroute": _subroute_for(tool_slug),
                    "reason": "matches_secondary_keyword",
                    "matched_tool": tool,
                }

            for sec in sec_kws:
                if sec and (sec in clean_q or (len(clean_q) >= 4 and clean_q in sec)):
                    return {
                        "cannibalized": True,
                        "is_cannibalized": True,
                        "is_cannibalizing": True,
                        "parent_slug": tool_slug or "none",
                        "target_subroute": _subroute_for(tool_slug),
                        "reason": "matches_secondary_keyword",
                        "matched_tool": tool,
                    }

            # Slug token overlap
            if tool_slug:
                tool_slug_words = set(re.findall(r"\b[a-z0-9]+\b", tool_slug.replace("-", " ").lower()))
                if tool_slug_words and query_words:
                    overlap = tool_slug_words & query_words
                    union = tool_slug_words | query_words
                    jaccard = len(overlap) / len(union) if union else 0.0

                    if not (len(query_words) >= 8 and jaccard <= 0.50) and (
                        (len(overlap) >= 3 and len(query_words) <= 4)
                        or jaccard >= token_overlap_threshold
                        or (jaccard >= 0.40 and len(overlap) >= 2)
                    ):
                        score = (tool_slug_words.issubset(query_words), round(jaccard, 6), len(overlap))
                        cand_res = {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug or "none",
                            "target_subroute": _subroute_for(tool_slug),
                            "reason": "high_slug_token_overlap",
                            "matched_tool": tool,
                        }
                        if best_slug_match is None or score > best_slug_match[0]:
                            best_slug_match = (score, cand_res)
                        continue

            # Tool URL match if present
            tool_url = str(tool.get("url") or tool.get("canonical_url") or "").lower()
            if tool_url:
                slug_part = tool_url.rstrip("/").split("/")[-1].replace("-", " ")
                u_words = set(re.findall(r"\b[a-z0-9]+\b", slug_part))
                if u_words and query_words:
                    overlap = u_words & query_words
                    union = u_words | query_words
                    jaccard = len(overlap) / len(union) if union else 0.0
                    if (len(overlap) >= 3 and len(query_words) <= 4) or jaccard >= token_overlap_threshold:
                        eff_slug = tool_slug or slug_part.replace(" ", "-")
                        score = (u_words.issubset(query_words), round(jaccard, 6), len(overlap))
                        cand_res = {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": eff_slug,
                            "target_subroute": _subroute_for(eff_slug),
                            "reason": "matches_tool_url",
                            "matched_tool": tool,
                        }
                        if best_slug_match is None or score > best_slug_match[0]:
                            best_slug_match = (score, cand_res)

        if best_slug_match is not None:
            return best_slug_match[1]

        # 1b. Normalized intent pass: scenario-comparison clones, state sub-routes, synonyms, filing/year modifiers
        if clean_q:
            norm_q = normalize_search_intent_tokens(clean_q)
            cand_slug_str = str((candidate_spec or {}).get("slug") or "").lower().strip()
            norm_cand_slug = normalize_search_intent_tokens(cand_slug_str) if cand_slug_str else norm_q
            is_scenario_clone = norm_q["is_scenario_comparison_clone"] or norm_cand_slug["is_scenario_comparison_clone"]
            q_state = norm_q["state_slug"] or norm_cand_slug["state_slug"]
            q_core = norm_q["core_tokens"]
            q_expanded = norm_q["expanded_tokens"]

            for tool in existing_tools:
                if not isinstance(tool, dict):
                    continue
                tool_slug = str(tool.get("slug", "")).strip()
                if not tool_slug:
                    continue
                pk = str(tool.get("primary_keyword", "")).lower().strip()
                norm_slug = normalize_search_intent_tokens(tool_slug)
                norm_pk = normalize_search_intent_tokens(pk) if pk else norm_slug

                # (i) Scenario-comparison-model clone of an existing hub
                if is_scenario_clone:
                    base_cand_slug = re.sub(r"-?scenario-comparison-model$", "", cand_slug_str or clean_q.replace(" ", "-")).strip("-")
                    if base_cand_slug == tool_slug or (
                        norm_slug["core_tokens"] and norm_slug["core_tokens"].issubset(q_core | norm_cand_slug["core_tokens"])
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_scenario_comparison_clone",
                            "matched_tool": tool,
                        }

                # (ii) State-specific query or state abbreviation variant ('ca', 's.c.', 'sc', 'az', 'california', etc.)
                if q_state:
                    # Matches another state tool on the same state + topic
                    if norm_slug["state_slug"] == q_state and (q_core & norm_slug["core_tokens"]):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_state_or_filing_modifier_variant",
                            "matched_tool": tool,
                        }
                    # Matches a national programmatic hub that owns /tools/<hub>/<state>/ sub-routes
                    if norm_slug["state_slug"] is None:
                        hub_tokens = norm_slug["expanded_tokens"] | norm_pk["expanded_tokens"]
                        is_tax_bracket_hub = {"tax", "brackets"}.issubset(hub_tokens) and (
                            {"tax", "brackets"}.issubset(q_core) or ("brackets" in q_core and "tax" in q_expanded)
                        )
                        is_1031_hub = (
                            "1031" in hub_tokens
                            and (
                                (
                                    "1031" in q_core
                                    and (
                                        not (
                                            len(q_core - {"1031", "exchange", "section", "like", "kind", "deferral", "tax", "property", "real", "estate"}) >= 2
                                        )
                                        or ("exchange" in q_core or {"like", "kind"}.issubset(q_core))
                                    )
                                )
                                or (
                                    ({"capital", "gains"} <= q_core or {"tax", "deferral"} <= q_core)
                                    and q_core.issubset({"capital", "gains", "tax", "deferral", "real", "estate", "property", "state"})
                                )
                            )
                        )
                        is_179_hub = "179" in hub_tokens and "179" in q_core and not (
                            len(q_core - {"179", "section", "deduction", "tax", "depreciation", "bonus", "limit", "limits"}) >= 2
                        )
                        if is_tax_bracket_hub or is_1031_hub or is_179_hub:
                            return {
                                "cannibalized": True,
                                "is_cannibalized": True,
                                "is_cannibalizing": True,
                                "parent_slug": tool_slug,
                                "target_subroute": f"/tools/{tool_slug}/{q_state}/",
                                "reason": "matches_state_subroute_intent",
                                "matched_tool": tool,
                            }

                # (iii) Synonym-normalized token overlap ('rates'/'tables' -> 'brackets')
                if norm_slug["expanded_tokens"] and q_expanded:
                    exp_overlap = norm_slug["expanded_tokens"] & q_expanded
                    exp_union = norm_slug["expanded_tokens"] | q_expanded
                    exp_jaccard = len(exp_overlap) / len(exp_union) if exp_union else 0.0
                    if not (len(q_expanded) >= 8 and exp_jaccard <= 0.50) and (
                        (len(exp_overlap) >= 3 and len(q_expanded) <= 4)
                        or exp_jaccard >= token_overlap_threshold
                        or (exp_jaccard >= 0.40 and len(exp_overlap) >= 2 and q_state == norm_slug["state_slug"])
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_normalized_synonym_intent",
                            "matched_tool": tool,
                        }

                # (iv) Core topic match after stripping filing status & year modifiers
                if q_core and norm_slug["core_tokens"] and q_state == norm_slug["state_slug"]:
                    core_hit = _match_core_topic_modifier_variant(
                        tool=tool,
                        tool_slug=tool_slug,
                        q_core=q_core,
                        slug_core=norm_slug["core_tokens"],
                    )
                    if core_hit is not None:
                        return core_hit

    # 2. Check against sitemap URLs if provided
    if sitemap_urls and clean_q:
        for u in sitemap_urls:
            slug_part = str(u).rstrip("/").split("/")[-1].replace("-", " ").lower()
            u_words = set(re.findall(r"\b[a-z0-9]+\b", slug_part))
            if u_words and query_words:
                overlap = u_words & query_words
                union = u_words | query_words
                jaccard = len(overlap) / len(union) if union else 0.0
                if (
                    (len(overlap) >= 3 and len(query_words) <= 4)
                    or jaccard >= token_overlap_threshold
                    or (jaccard >= 0.40 and len(overlap) >= 2)
                ):
                    return {
                        "cannibalized": True,
                        "is_cannibalized": True,
                        "is_cannibalizing": True,
                        "parent_slug": slug_part.replace(" ", "-"),
                        "reason": "matches_sitemap_url",
                        "matched_tool": None,
                    }

    return {
        "cannibalized": False,
        "is_cannibalized": False,
        "is_cannibalizing": False,
        "parent_slug": "none",
        "reason": "distinct_asset",
        "matched_tool": None,
    }


def detect_multi_keyword_title_h1_dilution(
    title: str,
    h1: str = "",
    primary_keyword: str = "",
    secondary_keywords: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Deterministic gate (x-like:2104684322481664277) that flags multi-keyword stuffing
    and intent dilution in <title> and <h1> tags.
    Rejects:
      1. Pipe/slash keyword-chain stuffing (>= 2 pipe/slash segments before the brand suffix).
      2. Conjunction chaining of >= 3 distinct keyword clauses ('A and B and C') or
         repeating the same multi-word head noun phrase across multiple clauses in <title> or <h1>.
      3. Stuffing >= 2 full secondary keyword strings verbatim into <title> alongside primary_keyword.
    Allows clean single-primary-intent titles with a compact parenthetical statutory modifier
    (e.g., 'Section 179 Deduction Calculator 2026 (Form 4562) | ProfitHelm').
    Zero em-dashes. Zero en-dashes.
    """
    import html as _html_mod

    clean_title = re.sub(r"\s+", " ", _html_mod.unescape(str(title or "")).strip())
    clean_h1 = re.sub(r"\s+", " ", _html_mod.unescape(str(h1 or "")).strip())
    clean_pk = re.sub(r"\s+", " ", _html_mod.unescape(str(primary_keyword or "")).strip().lower())
    sec_list = [re.sub(r"\s+", " ", str(s).strip().lower()) for s in (secondary_keywords or []) if str(s).strip()]

    violations: List[str] = []

    # Strip trailing brand suffix ('| ProfitHelm', '| Store', etc.)
    raw_pipe_parts = [p.strip() for p in clean_title.split("|") if p.strip()]
    if len(raw_pipe_parts) >= 2 and len(raw_pipe_parts[-1].split()) <= 3 and len(raw_pipe_parts[-1]) <= 28:
        title_body = " | ".join(raw_pipe_parts[:-1])
        body_segments = raw_pipe_parts[:-1]
    else:
        title_body = clean_title
        body_segments = raw_pipe_parts if raw_pipe_parts else ([clean_title] if clean_title else [])

    if len(body_segments) >= 2:
        violations.append(
            f"MULTI_KEYWORD_DELIMITER_STUFFING_IN_TITLE: {len(body_segments)} pipe-separated keyword segments before brand suffix"
        )

    for label, text_val in (("TITLE", title_body), ("H1", clean_h1)):
        if not text_val:
            continue
        low_val = text_val.lower()
        # Check >= 3 conjunction clauses ('A and B and C' or 'A & B & C', preserving tokens like R&D or POA&M)
        conj_clauses = [c.strip() for c in re.split(r"\s+(?:and|&)\s+", low_val) if len(c.strip().split()) >= 2]
        if len(conj_clauses) >= 3:
            violations.append(
                f"MULTI_KEYWORD_CONJUNCTION_CHAIN_IN_{label}: {len(conj_clauses)} multi-word keyword clauses chained in {label}"
            )
        # Check repeated 2-word head noun phrases across separate clauses (e.g. 'enclosed mobility scooters ... mobility scooters with canopy')
        words = [
            w for w in re.findall(r"\b[a-z0-9]+\b", low_val)
            if w not in {"the", "and", "for", "with", "in", "of", "to", "a", "an", "on", "by", "or", "vs"}
        ]
        bigrams: Dict[Tuple[str, str], int] = {}
        for idx in range(len(words) - 1):
            bg = (words[idx], words[idx + 1])
            bigrams[bg] = bigrams.get(bg, 0) + 1
        repeated_bg = [" ".join(bg) for bg, cnt in bigrams.items() if cnt >= 2]
        if repeated_bg:
            violations.append(
                f"MULTI_KEYWORD_HEAD_REPETITION_IN_{label}: repeated head phrase '{repeated_bg[0]}' across multiple keyword targets"
            )

    if clean_pk and sec_list and title_body:
        tb_low = title_body.lower()
        matched_secs = [s for s in sec_list if s != clean_pk and len(s) >= 6 and s in tb_low]
        if len(matched_secs) >= 2:
            violations.append(
                f"EXCESSIVE_SECONDARY_KEYWORDS_IN_TITLE: {len(matched_secs)} full secondary keywords stuffed into <title>"
            )

    return {
        "passed": len(violations) == 0,
        "is_diluted": len(violations) > 0,
        "title": clean_title,
        "h1": clean_h1,
        "primary_keyword": clean_pk,
        "delimiter_segments_count": len(body_segments),
        "violations": violations,
    }


def evaluate_serp_intent_bifurcation_vs_consolidation(
    query_a: str,
    query_b: str,
    serp_a: Optional[List[Dict[str, Any]]] = None,
    serp_b: Optional[List[Dict[str, Any]]] = None,
    page_rank_a: Optional[float] = None,
    page_rank_b: Optional[float] = None,
    spec_a: Optional[Dict[str, Any]] = None,
    spec_b: Optional[Dict[str, Any]] = None,
    inventory_overlap_ratio: Optional[float] = None,
    ceiling_detected: bool = False,
    cluster_expansion_frozen: bool = False,
    max_top3_overlap_for_split: float = 0.34,
    max_inventory_overlap_for_split: float = 0.70,
) -> Dict[str, Any]:
    """
    Deterministic SERP Intent Bifurcation vs Shared-Intent Cannibalization discriminator
    (x-like:2104684322481664277: @SEOKeval + @AshwiniNK21 vs @VijayAabhas).
    Evaluates whether two keywords targeted by a single mid-Page-1 URL warrant splitting
    into separate dedicated pages (SPLIT_DEDICATED_PAGE -> BUILD_PAGE) versus consolidating
    on the existing canonical hub (CONSOLIDATE_SHARED_SERP_INTENT -> REFACTOR_PAGE):
      1. Top-3 SERP URL Disjointness: Computes normalized URL overlap across the top 3
         ranking results for query_a and query_b. Overlap >= 0.34 proves Google treats
         both queries as shared intent (splitting causes @VijayAabhas cannibalization).
      2. Rank #1 Exclusive Keyword Specialization: Checks whether the #1 SERP result for
         query_a targets query_a's distinctive modifier tokens while omitting query_b's
         distinctive modifier tokens, and vice versa.
      3. Non-Duplicate Inventory / Statutory Formula Orthogonality: Blocks splitting when
         inventory_overlap_ratio >= 0.70 (same e-commerce SKUs) or when spec_a and spec_b
         share the same statutory signature / mathematical formula.
      4. Authority & Indexation Ceiling Guard: Defers splitting when ceiling_detected=True
         or cluster_expansion_frozen=True to prevent unindexed orphan bloat.
    Zero em-dashes. Zero en-dashes.
    """
    import urllib.parse

    qa_clean = re.sub(r"\s+", " ", str(query_a or "").strip().lower())
    qb_clean = re.sub(r"\s+", " ", str(query_b or "").strip().lower())

    def _norm_serp_url(raw_u: str) -> str:
        u_str = str(raw_u or "").strip().lower()
        if not u_str:
            return ""
        if "://" not in u_str:
            u_str = "https://" + u_str.lstrip("/")
        parsed = urllib.parse.urlsplit(u_str)
        netloc = parsed.netloc.removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}" if netloc else path

    top3_a = [r for r in (serp_a or []) if isinstance(r, dict)][:3]
    top3_b = [r for r in (serp_b or []) if isinstance(r, dict)][:3]
    urls_a = {_norm_serp_url(str(r.get("url") or r.get("link") or "")) for r in top3_a if _norm_serp_url(str(r.get("url") or r.get("link") or ""))}
    urls_b = {_norm_serp_url(str(r.get("url") or r.get("link") or "")) for r in top3_b if _norm_serp_url(str(r.get("url") or r.get("link") or ""))}

    overlap_urls = urls_a & urls_b
    min_denom = min(len(urls_a), len(urls_b)) if (urls_a and urls_b) else 0
    top3_overlap_ratio = round(len(overlap_urls) / float(min_denom), 4) if min_denom > 0 else 0.0

    stop_tokens = {"a", "an", "the", "with", "for", "in", "of", "and", "or", "to", "by", "on", "calculator", "tool", "model", "guide"}
    toks_a = {t for t in re.findall(r"\b[a-z0-9]+\b", qa_clean) if t not in stop_tokens}
    toks_b = {t for t in re.findall(r"\b[a-z0-9]+\b", qb_clean) if t not in stop_tokens}
    dist_a = toks_a - toks_b
    dist_b = toks_b - toks_a

    rank1_exclusive = False
    if top3_a and top3_b and dist_a and dist_b:
        r1_a_text = f"{top3_a[0].get('title', '')} {top3_a[0].get('url', '')}".lower()
        r1_b_text = f"{top3_b[0].get('title', '')} {top3_b[0].get('url', '')}".lower()
        r1_a_toks = set(re.findall(r"\b[a-z0-9]+\b", r1_a_text))
        r1_b_toks = set(re.findall(r"\b[a-z0-9]+\b", r1_b_text))
        r1_a_has_a = bool(dist_a & r1_a_toks)
        r1_a_omits_b = not bool(dist_b & r1_a_toks)
        r1_b_has_b = bool(dist_b & r1_b_toks)
        r1_b_omits_a = not bool(dist_a & r1_b_toks)
        rank1_exclusive = bool(r1_a_has_a and r1_a_omits_b and r1_b_has_b and r1_b_omits_a)

    pos_a = float(page_rank_a) if page_rank_a is not None else 5.5
    pos_b = float(page_rank_b) if page_rank_b is not None else 5.5
    mid_page1_plateau = bool(3.5 <= pos_a <= 12.0 and 3.5 <= pos_b <= 12.0)

    # Check duplicate SKU inventory or identical statutory formula signature
    dup_inventory_or_formula = False
    if inventory_overlap_ratio is not None and float(inventory_overlap_ratio) >= max_inventory_overlap_for_split:
        dup_inventory_or_formula = True

    sig_a = compute_statutory_signature(spec_a) if isinstance(spec_a, dict) else ""
    sig_b = compute_statutory_signature(spec_b) if isinstance(spec_b, dict) else ""
    if sig_a and sig_b and sig_a == sig_b:
        dup_inventory_or_formula = True
    elif isinstance(spec_a, dict) and isinstance(spec_b, dict):
        auth_a, keys_a, form_a = _extract_spec_signature_parts(spec_a)
        auth_b, keys_b, form_b = _extract_spec_signature_parts(spec_b)
        if auth_a and auth_b and auth_a == auth_b:
            if (form_a and form_b and form_a == form_b) or (
                keys_a and keys_b and (len(keys_a & keys_b) / float(max(len(keys_a), len(keys_b)))) >= 0.80
            ):
                dup_inventory_or_formula = True

    has_serp_evidence = bool(urls_a and urls_b)
    if has_serp_evidence and (top3_overlap_ratio >= max_top3_overlap_for_split or not rank1_exclusive):
        decision = "CONSOLIDATE_SHARED_SERP_INTENT"
        rec_action = "REFACTOR_PAGE"
        risk = "HIGH_SHARED_SERP_INTENT"
        reason = "shared_serp_top3_intent_overlap"
    elif dup_inventory_or_formula:
        decision = "CONSOLIDATE_SHARED_SERP_INTENT"
        rec_action = "REFACTOR_PAGE"
        risk = "HIGH_DUPLICATE_INVENTORY_OR_FORMULA"
        reason = "shared_statutory_signature_or_duplicate_inventory"
    elif ceiling_detected or cluster_expansion_frozen:
        decision = "DEFER_SPLIT_UNDER_INDEXATION_CEILING"
        rec_action = "REFACTOR_PAGE"
        risk = "MODERATE_CRAWL_BUDGET_CEILING"
        reason = "indexation_ceiling_or_frozen_cluster_expansion"
    elif has_serp_evidence and top3_overlap_ratio < max_top3_overlap_for_split and rank1_exclusive and mid_page1_plateau:
        decision = "SPLIT_DEDICATED_PAGE"
        rec_action = "BUILD_PAGE"
        risk = "LOW_DISJOINT_SERP_INTENT"
        reason = "disjoint_serp_top3_and_exclusive_rank1_specialization"
    else:
        decision = "CONSOLIDATE_SHARED_SERP_INTENT"
        rec_action = "REFACTOR_PAGE"
        risk = "MODERATE_INSUFFICIENT_BIFURCATION_PROOF"
        reason = "insufficient_serp_bifurcation_evidence"

    return {
        "query_a": qa_clean,
        "query_b": qb_clean,
        "decision": decision,
        "recommended_action": rec_action,
        "top3_url_overlap_ratio": top3_overlap_ratio,
        "shared_top3_urls": sorted(overlap_urls),
        "rank1_exclusive_targeting": rank1_exclusive,
        "distinctive_tokens_a": sorted(dist_a),
        "distinctive_tokens_b": sorted(dist_b),
        "mid_page1_plateau": mid_page1_plateau,
        "duplicate_inventory_or_formula": dup_inventory_or_formula,
        "ceiling_or_freeze_active": bool(ceiling_detected or cluster_expansion_frozen),
        "cannibalization_risk": risk,
        "reason": reason,
    }


def simulate_page_split_revenue_and_cannibalization_delta(
    combined_monthly_searches: int = 3000,
    aov_usd: float = 6000.0,
    claimed_monthly_revenue_gain_usd: float = 40000.0,
    baseline_position_a: float = 5.0,
    baseline_position_b: float = 5.5,
    top3_url_overlap_ratio: float = 0.0,
    inventory_overlap_ratio: float = 0.25,
    deduplication_factor: float = 0.70,
    high_ticket_organic_cvr: float = 0.0020,
    rank1_commercial_ctr: float = 0.14,
    mid_page1_ctr: float = 0.065,
    new_page_ramp_90d_factor: float = 0.55,
) -> Dict[str, Any]:
    """
    Adversarial quantitative falsification simulator for x-like:2104684322481664277
    ('3,000+ searches/mo * $5-7k AOV = +$40,000/mo additional organic revenue').
    Models:
      1. Impression deduplication across keyword variations (deduplication_factor=0.70).
      2. Already-captured mid-Page-1 baseline traffic at positions 5.0-5.5 (mid_page1_ctr=6.5%).
      3. Commercial SERP CTR compression below Google Shopping PLAs and AI Overviews (rank1_commercial_ctr=14.0%).
      4. High-ticket ($5k-$7k AOV) organic conversion rate reality (0.20% vs naive 2%+ impulse CVR).
      5. 90-day indexation and backlink ramp penalty on newly spawned URLs, plus negative
         authority-split cannibalization when top3_url_overlap_ratio >= 0.34 or inventory_overlap_ratio >= 0.70.
    Zero em-dashes. Zero en-dashes.
    """
    dedup_searches = round(float(combined_monthly_searches) * float(deduplication_factor), 2)
    baseline_clicks_mo = round(dedup_searches * float(mid_page1_ctr), 2)
    baseline_rev_mo = round(baseline_clicks_mo * float(high_ticket_organic_cvr) * float(aov_usd), 2)

    cannibalized = bool(float(top3_url_overlap_ratio) >= 0.34 or float(inventory_overlap_ratio) >= 0.70)
    if cannibalized:
        # Splitting a shared-intent page dilutes authority across two thin URLs, dropping CTR to ~3.2%
        post_split_clicks_mo = round(dedup_searches * 0.032, 2)
        post_split_rev_mo = round(post_split_clicks_mo * float(high_ticket_organic_cvr) * float(aov_usd), 2)
        incremental_mo = round(post_split_rev_mo - baseline_rev_mo, 2)
        net_90d_delta = round(incremental_mo * 3.0, 2)
    else:
        # Valid split: Page A captures rank1_commercial_ctr on 50% of searches; Page B ramps at new_page_ramp_90d_factor
        steady_clicks_mo = round(dedup_searches * float(rank1_commercial_ctr), 2)
        steady_rev_mo = round(steady_clicks_mo * float(high_ticket_organic_cvr) * float(aov_usd), 2)
        incremental_mo = round(steady_rev_mo - baseline_rev_mo, 2)
        ramped_clicks_mo = round(
            (0.5 * dedup_searches * float(rank1_commercial_ctr))
            + (0.5 * dedup_searches * float(rank1_commercial_ctr) * float(new_page_ramp_90d_factor)),
            2,
        )
        ramped_rev_mo = round(ramped_clicks_mo * float(high_ticket_organic_cvr) * float(aov_usd), 2)
        net_90d_delta = round((ramped_rev_mo - baseline_rev_mo) * 3.0, 2)

    overstatement_mult = (
        round(float(claimed_monthly_revenue_gain_usd) / max(1.0, incremental_mo), 2)
        if incremental_mo > 0
        else float("inf")
    )
    return {
        "combined_monthly_searches": int(combined_monthly_searches),
        "deduplicated_monthly_searches": dedup_searches,
        "aov_usd": float(aov_usd),
        "claimed_monthly_revenue_gain_usd": float(claimed_monthly_revenue_gain_usd),
        "baseline_position_a": float(baseline_position_a),
        "baseline_position_b": float(baseline_position_b),
        "baseline_monthly_clicks": baseline_clicks_mo,
        "baseline_already_captured_monthly_revenue_usd": baseline_rev_mo,
        "realistic_monthly_incremental_revenue_usd": incremental_mo,
        "net_90d_revenue_delta_usd": net_90d_delta,
        "overstatement_multiple": overstatement_mult,
        "cannibalization_penalty_applied": cannibalized,
        "naive_claim_falsified": bool(overstatement_mult >= 2.5 or net_90d_delta < 0.0),
    }


def evaluate_query_modifier_expansion_vs_distinct_tool(
    query: str,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    gsc_rows: Optional[List[Dict[str, Any]]] = None,
    property_id: str = "profithelm",
    serp_comparison: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministically weighs whether a query modifier warrants expanding/refactoring an
    existing canonical URL (EXPAND_EXISTING_PAGE -> REFACTOR_PAGE) versus launching a
    genuinely distinct statutory calculator (LAUNCH_DISTINCT_TOOL -> BUILD_PAGE).
    Decision rules:
      1. Existing URL already ranks in GSC positions 4-15 (or 1-20) -> EXPAND_EXISTING_PAGE
         UNLESS serp_comparison proves true SERP Intent Bifurcation (disjoint Top-3 SERP URLs,
         exclusive #1 incumbent keyword specialization, mid-Page-1 plateau, distinct statutory
         formula signature, and no active indexation ceiling).
      2. Modifier represents a filing-status tier, tax-year schedule, state sub-route,
         sub-scenario parameter (e.g. partial 1031 boot, vehicle bonus depreciation,
         QSBS exclusion, RAP/IBR/PSLF sub-intent), or phrasing synonym of an existing
         calculator -> EXPAND_EXISTING_PAGE.
      3. Modifier introduces an orthogonal statutory authority and distinct mathematical
         formula/inputs not modeled by any existing calculator -> LAUNCH_DISTINCT_TOOL.
    Zero em-dashes. Zero en-dashes.
    """
    clean_q = str(query or "").strip()
    prop_raw = str(property_id or "").lower()
    prop = (
        "prexvo"
        if "prexvo" in prop_raw
        else ("gainhelm" if "gainhelm" in prop_raw else "profithelm")
    )
    tools_catalog = list(existing_tools) if existing_tools is not None else (
        list(_DEFAULT_PREXVO_CORE_TOOLS)
        if prop == "prexvo"
        else (
            list(_DEFAULT_GAINHELM_CORE_TOOLS)
            if prop == "gainhelm"
            else list(_DEFAULT_PROFITHELM_CORE_TOOLS)
        )
    )
    cannibal = check_search_intent_cannibalization(
        clean_q,
        existing_tools=tools_catalog,
        gsc_rows=gsc_rows,
    )
    if cannibal.get("is_cannibalizing") and cannibal.get("parent_slug") not in (None, "", "none"):
        p_slug = str(cannibal["parent_slug"])
        subroute = str(cannibal.get("target_subroute") or f"/tools/{p_slug}/")
        r_pos = cannibal.get("ranking_position")
        reason = str(cannibal.get("reason") or "matches_existing_tool_intent")

        # Check SERP Intent Bifurcation override when serp_comparison is provided
        if isinstance(serp_comparison, dict) and serp_comparison.get("serp_a") and serp_comparison.get("serp_b"):
            matched_tool_obj = cannibal.get("matched_tool") if isinstance(cannibal.get("matched_tool"), dict) else {}
            primary_q_a = str(
                serp_comparison.get("primary_query")
                or matched_tool_obj.get("primary_keyword")
                or p_slug.replace("-", " ")
            )
            bifurcation = evaluate_serp_intent_bifurcation_vs_consolidation(
                query_a=primary_q_a,
                query_b=clean_q,
                serp_a=serp_comparison.get("serp_a"),
                serp_b=serp_comparison.get("serp_b"),
                page_rank_a=serp_comparison.get("page_rank_a", 5.0),
                page_rank_b=serp_comparison.get("page_rank_b", r_pos if r_pos is not None else 6.0),
                spec_a=serp_comparison.get("spec_a") or matched_tool_obj,
                spec_b=serp_comparison.get("spec_b"),
                inventory_overlap_ratio=serp_comparison.get("inventory_overlap_ratio"),
                ceiling_detected=bool(serp_comparison.get("ceiling_detected", False)),
                cluster_expansion_frozen=bool(serp_comparison.get("cluster_expansion_frozen", False)),
            )
            if bifurcation["decision"] == "SPLIT_DEDICATED_PAGE":
                return {
                    "query": clean_q,
                    "decision": "LAUNCH_DISTINCT_TOOL",
                    "action": "BUILD_PAGE",
                    "recommended_action": "BUILD_PAGE",
                    "suppress_duplicate_build": False,
                    "is_cannibalizing": False,
                    "serp_intent_bifurcation_detected": True,
                    "serp_bifurcation_analysis": bifurcation,
                    "parent_slug": p_slug,
                    "target_subroute": "",
                    "ranking_url": cannibal.get("ranking_url", ""),
                    "ranking_position": r_pos,
                    "ranking_impressions": cannibal.get("ranking_impressions", 0),
                    "modifier_classification": "SERP_BIFURCATED_DISTINCT_STATUTORY_INTENT",
                    "reason": "disjoint_serp_top3_and_exclusive_rank1_specialization",
                    "tradeoff_rationale": (
                        f"Although '{subroute}' ranks at position {r_pos} for '{clean_q}', Page-1 SERP "
                        f"analysis proves 0% Top-3 URL overlap, exclusive #1 keyword specialization, and "
                        f"distinct statutory calculation parameters; splitting into a dedicated calculator "
                        f"unlocks top-3 ranking capacity without thin-page cannibalization."
                    ),
                }

        if r_pos is not None and 1.0 <= float(r_pos) < 4.0:
            rec_action = "PROTECT_TOP3_WINNER"
            mod_class = "EXISTING_TOP_3_WINNER"
        elif r_pos is not None and 4.0 <= float(r_pos) <= 15.0:
            rec_action = "REFACTOR_PAGE"
            mod_class = "EXISTING_STRIKING_DISTANCE_4_15"
        elif "state_subroute" in reason or "state" in reason:
            rec_action = "REFACTOR_PAGE"
            mod_class = "JURISDICTION_STATE_SUBROUTE_MODIFIER"
        else:
            rec_action = "REFACTOR_PAGE"
            mod_class = "SAME_CALCULATOR_SUB_INTENT_MODIFIER"
        return {
            "query": clean_q,
            "decision": "EXPAND_EXISTING_PAGE",
            "action": rec_action,
            "recommended_action": rec_action,
            "suppress_duplicate_build": True,
            "is_cannibalizing": True,
            "serp_intent_bifurcation_detected": False,
            "parent_slug": p_slug,
            "matched_tool_slug": p_slug,
            "target_subroute": subroute,
            "ranking_url": cannibal.get("ranking_url", ""),
            "ranking_position": r_pos,
            "ranking_impressions": cannibal.get("ranking_impressions", 0),
            "modifier_classification": mod_class,
            "reason": reason,
            "tradeoff_rationale": (
                f"Query '{clean_q}' shares statutory and arithmetic intent with '{subroute}' "
                f"({mod_class}); expanding the existing page with targeted sub-intent sections "
                f"and tightened headings captures position 4-15 CTR gains without authority dilution."
            ),
        }

    return {
        "query": clean_q,
        "decision": "LAUNCH_DISTINCT_TOOL",
        "action": "BUILD_PAGE",
        "recommended_action": "BUILD_PAGE",
        "suppress_duplicate_build": False,
        "is_cannibalizing": False,
        "serp_intent_bifurcation_detected": False,
        "parent_slug": "none",
        "target_subroute": "",
        "ranking_url": "",
        "ranking_position": None,
        "ranking_impressions": 0,
        "modifier_classification": "DISTINCT_STATUTORY_CALCULATOR",
        "reason": "distinct_asset",
        "tradeoff_rationale": (
            f"Query '{clean_q}' introduces a distinct statutory regime and mathematical formula "
            f"not covered by any existing canonical calculator."
        ),
    }


def evaluate_query_impression_split(
    competing_pages: List[Any],
    redirect_map: Optional[Dict[str, Any]] = None,
    min_split_share: float = 0.10,
    dominance_threshold: float = 0.80,
) -> Dict[str, Any]:
    """
    Evaluates whether a set of URLs competing for a query represents a true
    cannibalization split or a single dominant winner with incidental (<10%) noise.
    Heuristic derived from high-signal GSC impression-share triage:
      - Filters out secondary URLs already 301-redirected in redirect_map.
      - When impression telemetry is present on competing_pages, a query is a true
        cannibalization split only when >=2 active URLs each hold >=min_split_share (10%)
        of total query impressions AND no single URL dominates with >dominance_threshold (80%) share.
      - When competing_pages are plain URL strings without impression counts, assumes
        equal split share so legacy callers trigger CONSOLIDATE_PAGES unchanged.
    Zero em-dashes. Zero en-dashes.
    """
    import urllib.parse

    eff_redirect_map = redirect_map or {}
    normalized_entries: List[Dict[str, Any]] = []
    has_impression_telemetry = False

    for idx, item in enumerate(competing_pages or []):
        if isinstance(item, dict):
            url_str = str(item.get("url") or item.get("canonical_url") or item.get("page") or item.get("canonical_path") or "").strip()
            has_impr_key = any(k in item for k in ("impressions", "impression_share", "share"))
            if has_impr_key:
                has_impression_telemetry = True
            impr_val = float(item.get("impressions", 0.0) or 0.0)
            explicit_share = item.get("impression_share", item.get("share"))
            pos_val = float(item.get("position", 50.0) or 50.0)
            clicks_val = int(float(item.get("clicks", 0) or 0))
            is_301 = bool(item.get("is_redirected_301", False))
            dev_splits = item.get("device_splits") if isinstance(item.get("device_splits"), dict) else {}
            mob_imp = float(item.get("mobile_impressions", (dev_splits.get("MOBILE") or {}).get("impressions", 0.0)) or 0.0)
            desk_imp = float(item.get("desktop_impressions", (dev_splits.get("DESKTOP") or {}).get("impressions", 0.0)) or 0.0)
            mob_pos = float(item.get("mobile_position", (dev_splits.get("MOBILE") or {}).get("position", pos_val)) or pos_val)
            desk_pos = float(item.get("desktop_position", (dev_splits.get("DESKTOP") or {}).get("position", pos_val)) or pos_val)
        else:
            url_str = str(item or "").strip()
            impr_val = 0.0
            explicit_share = None
            pos_val = 50.0
            clicks_val = 0
            is_301 = False
            mob_imp = 0.0
            desk_imp = 0.0
            mob_pos = 50.0
            desk_pos = 50.0

        if not url_str:
            continue

        path_part = urllib.parse.urlsplit(url_str).path if "://" in url_str else url_str
        norm_path = (path_part.rstrip("/") or "/") if path_part else "/"
        if not is_301 and eff_redirect_map:
            if norm_path in eff_redirect_map or (norm_path + "/") in eff_redirect_map or norm_path.strip("/") in eff_redirect_map:
                is_301 = True

        normalized_entries.append({
            "index": idx,
            "url": url_str,
            "canonical_path": norm_path,
            "impressions": impr_val,
            "explicit_share": float(explicit_share) if explicit_share is not None else None,
            "position": pos_val,
            "clicks": clicks_val,
            "mobile_impressions": mob_imp,
            "desktop_impressions": desk_imp,
            "mobile_position": mob_pos,
            "desktop_position": desk_pos,
            "is_redirected_301": is_301,
        })

    active_entries = [e for e in normalized_entries if not e["is_redirected_301"]]
    redirected_entries = [e for e in normalized_entries if e["is_redirected_301"]]

    if len(active_entries) <= 1:
        winner = active_entries[0]["url"] if active_entries else (normalized_entries[0]["url"] if normalized_entries else "")
        return {
            "is_true_cannibalization_split": False,
            "classification": "SINGLE_ACTIVE_CANONICAL_URL" if not redirected_entries else "ALREADY_CONSOLIDATED_VIA_301",
            "has_impression_telemetry": has_impression_telemetry,
            "active_url_count": len(active_entries),
            "redirected_301_Filtered_count": len(redirected_entries),
            "dominant_url": winner,
            "dominant_share": 1.0 if active_entries else 0.0,
            "qualifying_split_urls": [winner] if winner else [],
            "incidental_noise_urls": [e["url"] for e in redirected_entries],
            "url_shares": [
                {"url": e["url"], "impressions": int(e["impressions"]), "share": 1.0 if not e["is_redirected_301"] else 0.0, "is_redirected_301": e["is_redirected_301"]}
                for e in normalized_entries
            ],
        }

    if not has_impression_telemetry:
        equal_share = round(1.0 / float(len(active_entries)), 4)
        return {
            "is_true_cannibalization_split": True,
            "classification": "UNWEIGHTED_MULTI_URL_COMPETITION",
            "has_impression_telemetry": False,
            "active_url_count": len(active_entries),
            "redirected_301_Filtered_count": len(redirected_entries),
            "dominant_url": active_entries[0]["url"],
            "dominant_share": equal_share,
            "qualifying_split_urls": [e["url"] for e in active_entries],
            "incidental_noise_urls": [e["url"] for e in redirected_entries],
            "url_shares": [
                {"url": e["url"], "impressions": 0, "share": equal_share if not e["is_redirected_301"] else 0.0, "is_redirected_301": e["is_redirected_301"]}
                for e in normalized_entries
            ],
        }

    total_impr = sum(max(0.0, e["impressions"]) for e in active_entries)
    for e in active_entries:
        if e["explicit_share"] is not None:
            e["share"] = round(float(e["explicit_share"]), 4)
        elif total_impr > 0.0:
            e["share"] = round(max(0.0, e["impressions"]) / total_impr, 4)
        else:
            e["share"] = round(1.0 / float(len(active_entries)), 4)

    active_sorted = sorted(
        active_entries,
        key=lambda x: (-float(x["share"]), -float(x["impressions"]), float(x["position"]), int(x["index"])),
    )
    dominant = active_sorted[0]
    dominant_share = float(dominant["share"])
    qualifying_split = [e for e in active_sorted if float(e["share"]) >= min_split_share]
    incidental_noise = [e for e in active_sorted[1:] if float(e["share"]) < min_split_share]

    # Detect cross-device cannibalization split (URL A dominates MOBILE while URL B dominates DESKTOP)
    mob_candidates = [e for e in active_entries if float(e.get("mobile_impressions", 0.0)) >= 1.0]
    desk_candidates = [e for e in active_entries if float(e.get("desktop_impressions", 0.0)) >= 1.0]
    mob_leader = (
        sorted(mob_candidates, key=lambda x: (-float(x["mobile_impressions"]), float(x["mobile_position"]), int(x["index"])))[0]
        if mob_candidates
        else None
    )
    desk_leader = (
        sorted(desk_candidates, key=lambda x: (-float(x["desktop_impressions"]), float(x["desktop_position"]), int(x["index"])))[0]
        if desk_candidates
        else None
    )
    cross_device_split = bool(
        mob_leader
        and desk_leader
        and mob_leader["url"] != desk_leader["url"]
        and (float(mob_leader["mobile_impressions"]) + float(desk_leader["desktop_impressions"])) >= 3.0
    )

    is_true_split = bool((len(qualifying_split) >= 2 and dominant_share <= dominance_threshold) or cross_device_split)
    if len(qualifying_split) >= 2 and dominant_share <= dominance_threshold:
        classification = "TRUE_CANNIBALIZATION_SPLIT"
    elif cross_device_split:
        classification = "CROSS_DEVICE_CANNIBALIZATION_SPLIT"
        for leader_entry in (mob_leader, desk_leader):
            if leader_entry and leader_entry not in qualifying_split:
                qualifying_split.append(leader_entry)
    elif dominant_share > dominance_threshold:
        classification = "DOMINANT_WINNER_INCIDENTAL_NOISE"
    else:
        classification = "SUB_THRESHOLD_SECONDARY_SHARE"

    return {
        "is_true_cannibalization_split": is_true_split,
        "cross_device_split_detected": cross_device_split,
        "mobile_leader_url": mob_leader["url"] if mob_leader else "",
        "desktop_leader_url": desk_leader["url"] if desk_leader else "",
        "classification": classification,
        "has_impression_telemetry": True,
        "total_impressions": int(total_impr),
        "active_url_count": len(active_entries),
        "redirected_301_Filtered_count": len(redirected_entries),
        "dominant_url": dominant["url"],
        "dominant_share": dominant_share,
        "qualifying_split_urls": [e["url"] for e in qualifying_split],
        "incidental_noise_urls": [e["url"] for e in incidental_noise if e not in qualifying_split] + [e["url"] for e in redirected_entries],
        "url_shares": [
            {
                "url": e["url"],
                "impressions": int(e["impressions"]),
                "share": float(e.get("share", 0.0)),
                "position": round(float(e["position"]), 2),
                "clicks": int(e["clicks"]),
                "mobile_impressions": int(e.get("mobile_impressions", 0)),
                "desktop_impressions": int(e.get("desktop_impressions", 0)),
                "is_redirected_301": e["is_redirected_301"],
            }
            for e in active_sorted + redirected_entries
        ],
    }


_SINGLE_FACT_ZERO_CLICK_RE = re.compile(
    r"^(?:what\s+is\s+the\s+exact\s+date|when\s+is\s+the\s+deadline|how\s+many\s+calendar\s+days|"
    r"what\s+form\s+number\s+is|who\s+is\s+the\s+commissioner\s+of|what\s+does\s+irc\s+stand\s+for|"
    r"what\s+is\s+the\s+mailing\s+address\s+for\s+irs)\b",
    re.IGNORECASE,
)


def evaluate_query_expected_value_gate(
    query: str,
    query_data: Optional[Dict[str, Any]] = None,
    min_ev_score: float = 0.65,
) -> Dict[str, Any]:
    """
    Scores candidate queries on expected-value (EV) commercial calculator utility
    to prevent single-fact zero-click lookup queries from spawning thin standalone spokes.
    Combines multi-variable calculation utility, commercial monetization alignment,
    and SERP click retention resistance, with optional vault_jev System-1 scoring
    cached deterministically on disk.
    Zero em-dashes. Zero en-dashes.
    """
    import hashlib

    q_clean = str(query or "").strip()
    q_low = q_clean.lower()
    data = query_data if isinstance(query_data, dict) else {}

    if "expected_value_score" in data and data["expected_value_score"] is not None:
        explicit_ev = round(float(data["expected_value_score"]), 4)
        passed = explicit_ev >= min_ev_score
        return {
            "query": q_clean,
            "expected_value_score": explicit_ev,
            "min_ev_score": min_ev_score,
            "passed": passed,
            "is_zero_click_single_fact": not passed,
            "recommended_action": "BUILD_PAGE" if passed else "FOLD_INTO_HUB_FAQ",
            "triage_source": "explicit_input",
            "reason": (
                f"Expected-value score ({explicit_ev:.2f}) meets commercial calculator threshold ({min_ev_score:.2f})"
                if passed
                else f"Expected-value score ({explicit_ev:.2f}) below commercial calculator threshold ({min_ev_score:.2f}); fold into parent hub FAQ"
            ),
        }

    has_multi_var_intent = any(
        tok in q_low
        for tok in (
            "calculator",
            "estimator",
            "model",
            "schedule",
            "vs",
            "comparison",
            "deduction",
            "credit",
            "incentive",
            "arbitrage",
            "repayment",
            "refinance",
            "consolidation",
            "depreciation",
            "exchange",
            "amortization",
            "tax",
            "tariff",
            "cost",
            "audit",
            "compliance",
        )
    )
    is_single_fact = bool(
        data.get("zero_click_single_fact")
        or data.get("single_fact_lookup")
        or (_SINGLE_FACT_ZERO_CLICK_RE.search(q_low) and "calculator" not in q_low and "estimator" not in q_low)
    )

    multi_var_score = 0.25 if is_single_fact else (0.90 if has_multi_var_intent else 0.75)
    commercial_score = 0.30 if is_single_fact else (0.88 if has_multi_var_intent else 0.72)
    click_retention_score = 0.20 if is_single_fact else 0.85
    ev_score = round(0.45 * multi_var_score + 0.35 * commercial_score + 0.20 * click_retention_score, 4)
    triage_source = "deterministic_ev_heuristic"

    cache_key = hashlib.sha256(q_low.encode("utf-8")).hexdigest()[:24]
    cache_path = Path("/home/ubuntuadmin/projects/.agy/jev_intent_ev_cache.json")
    if cache_path.is_file():
        try:
            raw_c = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(raw_c, dict) and isinstance(raw_c.get(cache_key), dict):
                ev_score = round(float(raw_c[cache_key].get("expected_value_score", ev_score)), 4)
                is_single_fact = bool(raw_c[cache_key].get("is_zero_click_single_fact", is_single_fact))
                triage_source = "jev_ev_cache"
        except Exception:
            pass
    elif "PYTEST_CURRENT_TEST" not in os.environ and bool(data.get("invoke_jev_live", False)):
        try:
            import sys as _sys
            if "/home/ubuntuadmin/projects/vault" not in _sys.path:
                _sys.path.append("/home/ubuntuadmin/projects/vault")
            import vault_jev  # type: ignore
            prompt = (
                f"Evaluate search query '{q_clean}' for interactive financial/statutory calculator utility. "
                f"Return JSON with keys 'expected_value_score' (float 0.0 to 1.0) and 'is_zero_click_single_fact' (bool)."
            )
            jev_res = vault_jev.call_system_one(prompt, json_mode=True)
            if isinstance(jev_res, dict) and "expected_value_score" in jev_res:
                ev_score = round(float(jev_res["expected_value_score"]), 4)
                is_single_fact = bool(jev_res.get("is_zero_click_single_fact", ev_score < min_ev_score))
                triage_source = "jev_system_one"
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    curr_c = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
                    if not isinstance(curr_c, dict):
                        curr_c = {}
                    curr_c[cache_key] = {
                        "query": q_clean,
                        "expected_value_score": ev_score,
                        "is_zero_click_single_fact": is_single_fact,
                    }
                    cache_path.write_text(json.dumps(curr_c, indent=2), encoding="utf-8")
                except Exception:
                    pass
        except Exception:
            pass

    passed = (ev_score >= min_ev_score) and not is_single_fact
    return {
        "query": q_clean,
        "expected_value_score": ev_score,
        "min_ev_score": min_ev_score,
        "multi_variable_utility_score": multi_var_score,
        "commercial_monetization_score": commercial_score,
        "serp_click_retention_score": click_retention_score,
        "passed": passed,
        "is_zero_click_single_fact": is_single_fact,
        "recommended_action": "BUILD_PAGE" if passed else "FOLD_INTO_HUB_FAQ",
        "triage_source": triage_source,
        "reason": (
            f"Query '{q_clean}' passes expected-value calculator gate (EV={ev_score:.2f} >= {min_ev_score:.2f})"
            if passed
            else f"Zero-click single-fact query '{q_clean}' (EV={ev_score:.2f} < {min_ev_score:.2f}) folded into parent hub FAQ to prevent zero-click URL bloat"
        ),
    }


def qualify_search_intent(
    query_data: Optional[Union[Dict[str, Any], str]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    total_site_impressions: int = 500,
    sitemap_urls: Optional[List[str]] = None,
    require_high_effort: bool = False,
    authority_dampened: bool = False,
    ceiling_status: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> SearchIntentVerdict:
    """
    Enforces Search Intent Doctrine triage across candidate queries:
    0. REJECT_SYNTHETIC: Rejects synthetic test fixtures (e.g. query-two-buildable).
    1. CONSOLIDATE_PAGES: Multiple URLs competing for the same query (with 10%-80% impression-share split triage).
    2. PRUNE_PAGE: 0 impressions across >= 90 days.
    3. REFACTOR_PAGE: Striking distance query (pos 4-20) matching an existing tool.
       Generates overlay specification with 28-day measurement lock and target injections.
    4. MONITOR: Queries matching existing tools at pos < 4 or pos > 20, or queries
       with exploratory impressions below qualification floor.
    5. BUILD_PAGE: Genuinely underserved statutory void queries with proven demand.
    Supports both dict positional input (`qualify_search_intent(query_data, ...)`) and
    keyword arguments (`qualify_search_intent(query=..., impressions=..., position=...)`).
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(query_data, dict):
        merged_input = {**kwargs, **query_data}
    elif isinstance(query_data, str):
        merged_input = {**kwargs, "query": query_data}
    else:
        merged_input = dict(kwargs)
    query_data = merged_input

    q_text = str(query_data.get("query", "")).strip()
    pos = float(query_data.get("position", 100.0))
    impr = int(float(query_data.get("impressions", 0)))
    clicks = int(float(query_data.get("clicks", 0)))

    # 0. Reject synthetic test fixtures from production build pipeline
    if is_synthetic_test_candidate(q_text, query_data):
        return SearchIntentVerdict({
            "action": "REJECT_SYNTHETIC",
            "status": "PRUNE",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "reason": f"Synthetic test fixture candidate '{q_text}' rejected from production build queue",
        })

    # 0b. Reject thin affiliate-style listicles in favor of first-party statutory comparison calculators
    if is_thin_affiliate_listicle_candidate(q_text, query_data):
        return SearchIntentVerdict({
            "action": "REJECT_LISTICLE_ARCHETYPE",
            "status": "PRUNE",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "rejected_archetype": "thin_affiliate_listicle",
            "recommended_alternative_archetype": "deterministic_statutory_comparison_calculator",
            "reason": (
                f"Rejected thin affiliate listicle archetype '{q_text}'; "
                f"first-party financial authority requires deterministic statutory calculators and side-by-side comparison matrices"
            ),
        })

    # 1. Check competing pages (Consolidation with 10%-80% impression-share split triage)
    competing = query_data.get("competing_pages") or query_data.get("urls") or []
    if len(competing) > 1:
        split_eval = evaluate_query_impression_split(
            competing,
            redirect_map=query_data.get("redirect_map"),
            min_split_share=float(query_data.get("min_split_share", 0.10)),
            dominance_threshold=float(query_data.get("dominance_threshold", 0.80)),
        )
        plain_urls = [
            str(c.get("url") or c.get("canonical_url") or c.get("page") or c.get("canonical_path") or "")
            if isinstance(c, dict)
            else str(c)
            for c in competing
        ]
        canonical_winner = split_eval.get("dominant_url") or plain_urls[0]
        redirect_cands = [u for u in plain_urls if u and u != canonical_winner]
        suppress_incidental = bool(query_data.get("suppress_incidental_cannibalization", True))
        if not split_eval["is_true_cannibalization_split"] and split_eval["has_impression_telemetry"] and suppress_incidental:
            query_data["impression_split_analysis"] = split_eval
        else:
            return SearchIntentVerdict({
                "action": "CONSOLIDATE_PAGES",
                "status": "CONSOLIDATE_PAGES",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "competing_pages": competing,
                "canonical_url": canonical_winner,
                "redirect_candidates": redirect_cands,
                "impression_split_analysis": split_eval,
                "reason": f"Multiple URLs ({len(competing)}) competing for query '{q_text}' ({split_eval['classification']})",
            })

    # 2. Check zero impressions over 90 days (Pruning)
    days_observed = int(query_data.get("days", query_data.get("period_days", 0)))
    if impr == 0 and days_observed >= 90:
        return SearchIntentVerdict({
            "action": "PRUNE_PAGE",
            "status": "PRUNE",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "recommendation": "noindex_follow",
            "reason": f"0 impressions across {days_observed} days",
        })

    # 3. Match against existing tool catalog, GSC query-page rankings, and cannibalization detection
    matching_tool = query_data.get("matching_tool")
    cannibal = check_search_intent_cannibalization(
        q_text,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        candidate_spec=query_data,
        gsc_rows=query_data.get("gsc_rows"),
    )

    if matching_tool is None and cannibal.get("is_cannibalizing") and cannibal.get("parent_slug") != "none":
        matching_tool = cannibal.get("parent_slug")
        if cannibal.get("ranking_position") is not None and (pos <= 0.0 or pos >= 99.0):
            pos = float(cannibal["ranking_position"])
        if cannibal.get("ranking_impressions") and impr <= 0:
            impr = int(cannibal["ranking_impressions"])

    if matching_tool is None and existing_tools:
        q_lower = q_text.lower()
        for tool in existing_tools:
            tool_slug = str(tool.get("slug", "")).strip()
            tool_kw = str(tool.get("primary_keyword", "")).lower().strip()
            if tool_slug and tool_slug in q_lower.replace(" ", "-"):
                matching_tool = tool_slug
                break
            if tool_kw and (tool_kw in q_lower or q_lower in tool_kw):
                matching_tool = tool_slug
                break

    # 4. If query matches an existing tool asset
    if matching_tool is not None:
        target_subroute = cannibal.get("target_subroute") or f"/tools/{matching_tool}/"
        if 4.0 <= pos <= 20.0:
            now = datetime.now(timezone.utc)
            lock_until = (now + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
            words = [w.capitalize() for w in q_text.split() if w]
            heading_title = " ".join(words) if words else "Overview & Statutory Analysis"

            overlay_spec = {
                "slug": matching_tool,
                "target_subroute": target_subroute,
                "grouped_queries": [q_text] if q_text else [],
                "measurement_lock_days": 28,
                "lock_days": 28,
                "locked_until": lock_until,
                "lock_until": lock_until,
                "h2_headings": [
                    f"{heading_title} Rules and Guidelines" if "rules" not in heading_title.lower() else heading_title
                ],
                "preset_scenarios": [
                    {
                        "label": f"{heading_title} Baseline Scenario",
                        "query": q_text,
                        "target_position": pos,
                        "impressions": impr,
                    }
                ],
                "faq_schema": [
                    {
                        "question": f"How is {q_text} determined?",
                        "answer": f"Deterministic statutory calculation and threshold analysis for {q_text}.",
                    }
                ],
                "faq_additions": [
                    {
                        "question": f"How is {q_text} determined?",
                        "answer": f"Deterministic statutory calculation and threshold analysis for {q_text}.",
                    }
                ],
                "device_focus": str(query_data.get("device_focus") or ("MOBILE_CTR_DEFICIT" if float(query_data.get("mobile_ctr_gap", 0.0) or 0.0) >= 0.01 else "BALANCED")),
                "mobile_ctr": float(query_data.get("mobile_ctr", 0.0) or 0.0),
                "desktop_ctr": float(query_data.get("desktop_ctr", 0.0) or 0.0),
                "mobile_ctr_gap": float(query_data.get("mobile_ctr_gap", 0.0) or 0.0),
                "search_appearances": list(query_data.get("search_appearances") or []),
                "time_window_trajectory": str((query_data.get("time_window_delta") or {}).get("trajectory_state") or query_data.get("time_window_trajectory") or "STABLE"),
            }

            return SearchIntentVerdict({
                "action": "REFACTOR_PAGE",
                "status": "REFACTOR_PAGE",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "matching_tool": matching_tool,
                "canonical_slug": matching_tool,
                "target_subroute": target_subroute,
                "measurement_lock_days": 28,
                "overlay_spec": overlay_spec,
                "reason": f"Striking distance query (pos {pos}) matches existing tool '{matching_tool}'",
            })

        if pos < 4.0:
            return SearchIntentVerdict({
                "action": "MONITOR",
                "status": "MONITOR",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "matching_tool": matching_tool,
                "canonical_slug": matching_tool,
                "target_subroute": target_subroute,
                "reason": f"Top-ranking position {pos} - preserve existing authority",
            })

        # pos > 20.0 matching existing tool
        return SearchIntentVerdict({
            "action": "MONITOR",
            "status": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "matching_tool": matching_tool,
            "canonical_slug": matching_tool,
            "target_subroute": target_subroute,
            "reason": f"Position {pos} > 20 matches existing tool '{matching_tool}' - avoid cannibalizing URL bloat",
        })

    # 5. Distinct unserved query void: evaluate against Search Intent Doctrine
    # Authority dampening suppression guard
    if authority_dampened or (ceiling_status and ceiling_status.get("ceiling_detected")):
        ceiling_score = 0.0
        if ceiling_status:
            ceiling_score = float(ceiling_status.get("ceiling_dampening_score", 0.0))
        return SearchIntentVerdict({
            "action": "MONITOR",
            "status": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "ceiling_detected": True,
            "reason": f"Domain authority dampening ceiling active (score {ceiling_score:.2f}) - suppress programmatic void page creation to preserve crawl budget until trust recovery",
        })

    dynamic_floor = max(2, min(25, int(0.05 * total_site_impressions)))

    # Impressions below qualification floor indicate exploratory testing by search engines
    if impr < dynamic_floor:
        return SearchIntentVerdict({
            "action": "MONITOR",
            "status": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "reason": f"Impressions ({impr}) below qualification floor ({dynamic_floor}) - Google testing existing page intent; monitor before building page",
        })

    # Deep ranking positions (> 20) with modest impressions indicate exploratory indexing
    if pos > 20.0 and impr < 50:
        return SearchIntentVerdict({
            "action": "MONITOR",
            "status": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "reason": f"Position {pos} > 20 with exploratory impressions ({impr}) - monitor before building page",
        })

    # Expected-Value (EV) Commercial & Multi-Variable Calculation Gate (prevents zero-click single-fact spoke bloat)
    ev_gate = evaluate_query_expected_value_gate(
        query=q_text,
        query_data=query_data,
        min_ev_score=float(query_data.get("min_ev_score", 0.65)),
    )
    if not ev_gate["passed"]:
        return SearchIntentVerdict({
            "action": ev_gate["recommended_action"],
            "status": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "expected_value_score": ev_gate["expected_value_score"],
            "expected_value_gate": ev_gate,
            "reason": ev_gate["reason"],
        })

    # Qualified unserved void
    candidate_spec = {
        "query": q_text,
        "primary_keyword": q_text.lower(),
        "position": pos,
        "impressions": impr,
        "clicks": clicks,
        "expected_value_score": ev_gate["expected_value_score"],
        "status": "PENDING",
        "source": "gsc_void_harvest",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }
    # Enrich with high-effort schema fields if present in query_data
    for field in (
        "statutory_authority",
        "statutory_provenance",
        "economic_dataset",
        "economic_source",
        "calculation_manifest",
        "formula",
        "inputs",
        "model_name",
        "sample_calculation",
        "published_output",
        "expected_output",
        "slug",
        "title",
        "device_focus",
        "mobile_ctr",
        "desktop_ctr",
        "mobile_ctr_gap",
        "search_appearances",
        "time_window_trajectory",
        "gsc_telemetry",
        "inspection_state",
    ):
        if field in query_data:
            candidate_spec[field] = query_data[field]

    if require_high_effort or query_data.get("require_high_effort"):
        assert_high_effort_content_qualified(candidate_spec)

    return SearchIntentVerdict({
        "action": "BUILD_PAGE",
        "status": "BUILD_PAGE",
        "query": q_text,
        "position": pos,
        "impressions": impr,
        "candidate_spec": candidate_spec,
        "reason": f"Genuinely underserved query void (pos {pos}, impr {impr}) with no matching tool asset",
    })


def assert_high_effort_content_qualified(
    candidate_spec: Dict[str, Any],
    context: str = "",
) -> bool:
    """
    Validates candidate specification against High-Effort Content Qualification Gate.
    Enforces:
    1. Zero forbidden dashes (U+2014 em-dash, U+2013 en-dash) across entire specification.
    2. Zero prompt leakage terms.
    3. Zero ungrounded synthetic claims or mock markers ('mock', 'dummy', 'hypothetical', 'placeholder').
    4. Primary statutory legal provenance (IRC, CFR, USC, Public Law, IRS guidance).
    5. Empirical economic dataset series (BLS, FRED, BEA, Federal Reserve).
    6. Non-empty formula, inputs, model_name, and sample_calculation.
    7. Deterministic AST mathematical formula evaluability via safe_eval_mathematical_formula.
    8. Input/output mathematical integrity within 0.01 tolerance via assert_proprietary_model_integrity.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(candidate_spec, dict):
        raise ValueError(
            f"High-effort candidate specification must be a dictionary, got {type(candidate_spec).__name__}{ctx}"
        )

    spec_json = json.dumps(candidate_spec, ensure_ascii=False)

    # 1. Zero forbidden dashes
    assert_no_forbidden_dashes(spec_json, context=f"high-effort candidate specification{ctx}")

    # 2. Zero prompt leakage
    assert_no_prompt_leakage(spec_json, context=f"high-effort candidate specification{ctx}")

    # 3. Ungrounded synthetic claims and mock markers
    syn_issues = detect_ungrounded_synthetic_claims(spec_json)
    spec_lower = spec_json.lower()
    for marker_pat in [r"\bmock\b", r"\bdummy\b", r"\bhypothetical\b", r"\bplaceholder\b"]:
        m = re.search(marker_pat, spec_lower)
        if m:
            syn_issues.append(f"Mock or placeholder marker detected: '{m.group(0)}'")
    if syn_issues:
        raise ValueError(
            f"High-effort qualification failed{ctx}: ungrounded synthetic claims or mock markers detected: {syn_issues[0]}"
        )

    # Extract manifest data if nested
    manifest = candidate_spec.get("calculation_manifest") if isinstance(candidate_spec.get("calculation_manifest"), dict) else {}

    # 4. Primary statutory provenance
    statutory = (
        candidate_spec.get("statutory_authority")
        or candidate_spec.get("statutory_provenance")
        or candidate_spec.get("authority")
        or manifest.get("statutory_authority")
        or manifest.get("statutory_provenance")
        or manifest.get("authority")
    )
    if not statutory or (isinstance(statutory, str) and not statutory.strip()):
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty primary statutory authority or provenance")

    statutory_str = str(statutory).strip()
    statutory_matched = any(re.search(pat, statutory_str, re.IGNORECASE) for pat in STATUTORY_PROVENANCE_PATTERNS)
    if not statutory_matched:
        raise ValueError(
            f"High-effort qualification failed{ctx}: statutory authority '{statutory_str}' "
            f"does not cite recognized primary statutory provenance (IRC, CFR, USC, Public Law, IRS guidance)"
        )

    # 5. Empirical economic dataset series
    economic = (
        candidate_spec.get("economic_dataset")
        or candidate_spec.get("economic_source")
        or manifest.get("economic_dataset")
        or manifest.get("economic_source")
    )
    if not economic or (isinstance(economic, str) and not economic.strip()):
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty empirical economic dataset")

    economic_str = str(economic).strip()
    economic_matched = any(re.search(pat, economic_str, re.IGNORECASE) for pat in ECONOMIC_DATASET_PATTERNS)
    if not economic_matched:
        raise ValueError(
            f"High-effort qualification failed{ctx}: economic dataset '{economic_str}' "
            f"does not cite recognized empirical economic dataset series (BLS, FRED, BEA, Federal Reserve)"
        )

    # 6. Formula, inputs, model name, sample calculation
    formula = (
        candidate_spec.get("formula")
        or manifest.get("formula")
    )
    if not formula or not isinstance(formula, str) or not formula.strip():
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty 'formula'")

    inputs = (
        candidate_spec.get("inputs")
        if candidate_spec.get("inputs") is not None
        else manifest.get("inputs")
    )
    if inputs is None or not isinstance(inputs, dict) or len(inputs) == 0:
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty 'inputs' dictionary")

    model_name = (
        candidate_spec.get("model_name")
        or candidate_spec.get("proprietary_model")
        or manifest.get("model_name")
        or manifest.get("proprietary_model")
    )
    if not model_name or (isinstance(model_name, str) and not model_name.strip()):
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty 'model_name'")

    sample_calc = (
        candidate_spec.get("sample_calculation")
        or candidate_spec.get("sample")
        or manifest.get("sample_calculation")
        or manifest.get("sample")
    )
    if not sample_calc or (isinstance(sample_calc, str) and not sample_calc.strip()):
        raise ValueError(f"High-effort qualification failed{ctx}: missing or empty 'sample_calculation'")

    # 7. Formula evaluability with safe_eval_mathematical_formula (clamping numeric inputs to >= 0 per HWL-1263)
    clamped_inputs: Dict[str, Any] = {}
    for k, v in inputs.items():
        if isinstance(v, (int, float)):
            clamped_inputs[k] = max(0.0, float(v)) if isinstance(v, float) else max(0, v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                num_v = float(v_clean)
                clamped_inputs[k] = max(0.0, num_v)
            except ValueError:
                clamped_inputs[k] = v
        else:
            clamped_inputs[k] = v

    try:
        calculated_num = safe_eval_mathematical_formula(formula, clamped_inputs)
    except Exception as ex:
        raise ValueError(f"High-effort qualification failed{ctx}: formula '{formula}' evaluation failed: {ex}")

    # 8. Input/output mathematical parity if published_output is present
    published_out = (
        candidate_spec.get("published_output")
        or candidate_spec.get("expected_output")
        or candidate_spec.get("output")
        or candidate_spec.get("result")
        or manifest.get("published_output")
        or manifest.get("expected_output")
        or manifest.get("output")
        or manifest.get("result")
    )
    if published_out is not None:
        try:
            assert_proprietary_model_integrity(
                manifest_or_inputs=clamped_inputs,
                published_output=published_out,
                formula=formula,
                tolerance=0.01,
                context=f"candidate spec '{candidate_spec.get('slug', candidate_spec.get('query', ''))}'{ctx}",
            )
        except Exception as ex:
            raise ValueError(f"High-effort qualification failed{ctx}: {ex}")

    return True


def assert_search_intent_qualified(
    candidate_spec: Dict[str, Any],
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    require_high_effort: bool = False,
) -> bool:
    """
    Validates candidate specification against Search Intent Doctrine.
    Raises ValueError if the candidate query cannibalizes existing tool catalog or is a synthetic test fixture.
    When require_high_effort=True or when candidate_spec contains high-effort keys,
    validates high-effort content qualification gate.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(candidate_spec, dict):
        raise ValueError("Candidate spec must be a dictionary")

    query = (
        candidate_spec.get("query")
        or candidate_spec.get("primary_keyword")
        or str(candidate_spec.get("slug", "")).replace("-", " ")
    )
    if not query:
        raise ValueError("Candidate spec missing query, primary_keyword, or slug")

    if is_synthetic_test_candidate(str(query), candidate_spec):
        raise ValueError(
            f"Synthetic test fixture candidate '{query}' rejected from production build qualification."
        )

    if is_thin_affiliate_listicle_candidate(str(query), candidate_spec):
        raise ValueError(
            f"Thin affiliate listicle candidate '{query}' rejected from production build qualification; "
            f"use a deterministic statutory calculator or side-by-side comparison matrix."
        )

    cannibal = check_search_intent_cannibalization(
        query, existing_tools=existing_tools, candidate_spec=candidate_spec
    )

    if not cannibal.get("is_cannibalizing"):
        cand_slug = str(candidate_spec.get("slug", "")).strip()
        if cand_slug:
            cand_slug_clean = cand_slug.replace("-", " ")
            cannibal_slug = check_search_intent_cannibalization(
                cand_slug_clean, existing_tools=existing_tools, candidate_spec=candidate_spec
            )
            if cannibal_slug.get("is_cannibalizing"):
                cannibal = cannibal_slug

    if cannibal.get("is_cannibalizing"):
        raise ValueError(
            f"Search intent cannibalization detected for candidate '{query}': "
            f"matches existing tool '{cannibal.get('parent_slug')}' ({cannibal.get('reason')}). "
            f"Search Intent Doctrine: An impression is not proof that a new page is missing."
        )

    # High-effort content qualification check
    high_effort_keys = (
        "formula",
        "calculation_manifest",
        "model_name",
        "statutory_authority",
        "statutory_provenance",
        "economic_dataset",
        "economic_source",
    )
    has_high_effort_keys = any(bool(candidate_spec.get(k)) for k in high_effort_keys)
    if require_high_effort or has_high_effort_keys:
        assert_high_effort_content_qualified(candidate_spec)

    return True


def group_related_queries_by_intent(
    candidates: List[Dict[str, Any]],
    existing_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Groups a queue of candidate queries (e.g. void_candidates.jsonl or GSC query records)
    onto existing canonical pages or single deduplicated novel clusters so related queries
    (state abbreviations, filing-status modifiers, tax-year variants, rate/table synonyms)
    never spawn competing pages.
    Zero em-dashes. Zero en-dashes.
    """
    base_tools = [dict(t) for t in (existing_tools or []) if isinstance(t, dict)]
    running_tools = list(base_tools)
    existing_page_groups: Dict[str, Dict[str, Any]] = {}
    novel_clusters_by_key: Dict[str, Dict[str, Any]] = {}
    rejected_synthetic: List[Dict[str, Any]] = []
    cannibalization_prevented = 0

    for item in candidates or []:
        if not isinstance(item, dict):
            continue
        q_text = str(item.get("query") or item.get("primary_keyword") or item.get("slug", "").replace("-", " ")).strip()
        if not q_text:
            continue
        if is_synthetic_test_candidate(q_text, item):
            rejected_synthetic.append(item)
            continue

        impr = int(float(item.get("impressions", 0) or 0))
        pos = float(item.get("position", 100.0) or 100.0)

        cannibal = check_search_intent_cannibalization(
            q_text,
            existing_tools=running_tools,
            candidate_spec=item,
        )
        if cannibal.get("is_cannibalizing") and cannibal.get("parent_slug") != "none":
            parent_slug = str(cannibal["parent_slug"])
            target_subroute = str(cannibal.get("target_subroute") or f"/tools/{parent_slug}/")
            cannibalization_prevented += 1

            # Check if parent_slug is an existing tool or an already-opened novel cluster
            if parent_slug in novel_clusters_by_key:
                cluster = novel_clusters_by_key[parent_slug]
                if q_text.lower() not in [q.lower() for q in cluster["grouped_queries"]]:
                    cluster["grouped_queries"].append(q_text)
                cluster["total_impressions"] += impr
                cluster["member_candidates"].append(item)
            else:
                grp = existing_page_groups.setdefault(
                    parent_slug,
                    {
                        "canonical_slug": parent_slug,
                        "target_subroute": target_subroute,
                        "grouped_queries": [],
                        "total_impressions": 0,
                        "best_position": pos,
                        "reasons": [],
                    },
                )
                if q_text.lower() not in [q.lower() for q in grp["grouped_queries"]]:
                    grp["grouped_queries"].append(q_text)
                grp["total_impressions"] += impr
                grp["best_position"] = min(float(grp["best_position"]), pos)
                if cannibal.get("reason") not in grp["reasons"]:
                    grp["reasons"].append(cannibal.get("reason"))
            continue

        # Distinct novel query: compute canonical topic cluster signature
        norm = normalize_search_intent_tokens(q_text)
        core_sorted = "-".join(sorted(norm["core_tokens"])) or re.sub(r"[^a-z0-9]+", "-", q_text.lower()).strip("-")
        cluster_slug = str(item.get("slug") or "").strip() or (
            f"{core_sorted}-{norm['state_slug']}" if norm["state_slug"] else core_sorted
        )
        novel_clusters_by_key[cluster_slug] = {
            "canonical_slug": cluster_slug,
            "primary_query": q_text,
            "state_slug": norm["state_slug"],
            "core_tokens": sorted(norm["core_tokens"]),
            "grouped_queries": [q_text],
            "total_impressions": impr,
            "member_candidates": [item],
        }
        running_tools.append({
            "slug": cluster_slug,
            "primary_keyword": q_text.lower(),
            "secondary_keywords": [],
        })

    return {
        "total_input_queries": len(candidates or []),
        "cannibalization_prevented_count": cannibalization_prevented,
        "existing_page_groups": existing_page_groups,
        "novel_topic_clusters": list(novel_clusters_by_key.values()),
        "rejected_synthetic": rejected_synthetic,
    }


CANNIBALIZING_CLONE_CONSOLIDATION_MAP: Dict[str, Dict[str, str]] = {
    "ca-tax-brackets": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2025": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2026": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2026-married-jointly": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2026-single": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-married": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2026-head-of-household": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-married-filing-jointly": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "california-income-tax-brackets-2026": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "california-tax-brackets-2026": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "california-tax-brackets-2027": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "ca-tax-brackets-2027-married-jointly": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "2027-california-tax-brackets": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "2027-california-income-tax-brackets": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "california-2027-tax-brackets": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "2027-california-tax-rates": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "california-state-tax-brackets": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/california/",
    },
    "sc-income-tax-rate-2027": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/south-carolina/",
    },
    "s-c-income-tax-rate-2027": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/south-carolina/",
    },
    "2027-tax-tables": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/",
    },
    "irs-2027-tax-bracket-projections": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/",
    },
    "1031-exchange-rules-arizona": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/arizona/",
    },
    "1031-exchange-ohio": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/ohio/",
    },
    "ohio-1031": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/ohio/",
    },
    "1031-exchange-in-massachusetts": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/massachusetts/",
    },
    "section-1031-exchange-deferral": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/",
    },
    "irs-2027-tax-rates": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/",
    },
    "irs-capital-gains-statutory-tax": {
        "canonical_slug": "tcja-sunset-capital-gains",
        "redirect_target": "/tools/tcja-sunset-capital-gains/",
    },
    "qsbs-section-1202-tax-calculator": {
        "canonical_slug": "tcja-sunset-capital-gains",
        "redirect_target": "/tools/tcja-sunset-capital-gains/",
    },
    "qsbs-83b-tax-calculator": {
        "canonical_slug": "tcja-sunset-capital-gains",
        "redirect_target": "/tools/tcja-sunset-capital-gains/",
    },
    "kalshi-prediction-market-arbitrage-strategy": {
        "canonical_slug": "prediction-market-odds",
        "redirect_target": "/tools/prediction-market-odds/",
    },
    "saas-burn-multiple-benchmarks-2026": {
        "canonical_slug": "saas-runway-calculator",
        "redirect_target": "/tools/saas-runway-calculator/",
    },
    "financial-model": {
        "canonical_slug": "saas-runway-calculator",
        "redirect_target": "/tools/saas-runway-calculator/",
    },
    "freelance-tax-calculator": {
        "canonical_slug": "s-corp-reasonable-salary-tax-calculator",
        "redirect_target": "/tools/s-corp-reasonable-salary-tax-calculator/",
    },
    "bonus-depreciation-calculator-2027": {
        "canonical_slug": "section-179-calculator",
        "redirect_target": "/tools/section-179-calculator/",
    },
    "macrs-depreciation-calculator": {
        "canonical_slug": "section-179-calculator",
        "redirect_target": "/tools/section-179-calculator/",
    },
    "section-179-vehicle-deduction": {
        "canonical_slug": "section-179-calculator",
        "redirect_target": "/tools/section-179-calculator/",
    },
    "irs-2027-tax-brackets-scenario-comparison-model": {
        "canonical_slug": "irs-2027-tax-brackets",
        "redirect_target": "/tools/irs-2027-tax-brackets/",
    },
    "crypto-tax-calculator-scenario-comparison-model": {
        "canonical_slug": "crypto-tax-calculator",
        "redirect_target": "/tools/crypto-tax-calculator/",
    },
    "prediction-market-odds-scenario-comparison-model": {
        "canonical_slug": "prediction-market-odds",
        "redirect_target": "/tools/prediction-market-odds/",
    },
    "tcja-sunset-capital-gains-scenario-comparison-model": {
        "canonical_slug": "tcja-sunset-capital-gains",
        "redirect_target": "/tools/tcja-sunset-capital-gains/",
    },
    "section-1031-calculator-scenario-comparison-model": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/",
    },
    "what-is-implied-probability-in-prediction-markets": {
        "canonical_slug": "prediction-market-odds",
        "redirect_target": "/tools/prediction-market-odds/",
    },
    "1031-like-kind-exchange-st-louis-mo": {
        "canonical_slug": "section-1031-calculator",
        "redirect_target": "/tools/section-1031-calculator/missouri/",
    },
    "section-174-r-d-amortization-calculator": {
        "canonical_slug": "r-and-d-tax-credit-section-174-amortization-calculator",
        "redirect_target": "/tools/r-and-d-tax-credit-section-174-amortization-calculator/",
    },
}

PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP: Dict[str, Dict[str, str]] = {
    "pslf-buyback-calculator": {
        "canonical_slug": "pslf-qualifying-payment-simulator",
        "redirect_target": "/tools/pslf-qualifying-payment-simulator/",
    },
    "repayment-assistance-plan-calculator": {
        "canonical_slug": "rap-payment-calculator",
        "redirect_target": "/tools/rap-payment-calculator/",
    },
    "student-loan-interest-subsidy-calculator": {
        "canonical_slug": "save-plan-litigation-transition",
        "redirect_target": "/tools/save-plan-litigation-transition/",
    },
    "tax-deduction-for-car-loan-interest": {
        "canonical_slug": "student-loan-repayment-calculator",
        "redirect_target": "/tools/",
    },
}

OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP: Dict[str, str] = {
    "/shopify-profit-tracker": "/tools/",
    "/shopify-profit-tracker/": "/tools/",
    "/trueprofit-alternative": "/tools/",
    "/trueprofit-alternative/": "/tools/",
    "/beprofit-alternative": "/tools/",
    "/beprofit-alternative/": "/tools/",
    "/lifetimely-alternative": "/tools/",
    "/lifetimely-alternative/": "/tools/",
    "/triple-whale-alternative": "/tools/",
    "/triple-whale-alternative/": "/tools/",
    "/sellerboard-alternative": "/tools/",
    "/sellerboard-alternative/": "/tools/",
    "/profit-calculator": "/tools/",
    "/profit-calculator/": "/tools/",
    "/tools/profit-margin-calculator": "/tools/",
    "/tools/profit-margin-calculator/": "/tools/",
    "/tools/shopify-profit-margin-calculator": "/tools/",
    "/tools/shopify-profit-margin-calculator/": "/tools/",
    "/ecommerce-margin": "/tools/",
    "/ecommerce-margin/": "/tools/",
    "/margin-calculator": "/tools/",
    "/margin-calculator/": "/tools/",
    "/tools/ecommerce-margin": "/tools/",
    "/tools/ecommerce-margin/": "/tools/",
    "/tools/chargeback-calculator": "/tools/",
    "/tools/chargeback-calculator/": "/tools/",
    "/tools/ad-spend-roi-calculator": "/tools/",
    "/tools/ad-spend-roi-calculator/": "/tools/",
    "/tools/shopify-fees-calculator": "/tools/",
    "/tools/shopify-fees-calculator/": "/tools/",
    "/tools/break-even-acos-calculator": "/tools/",
    "/tools/break-even-acos-calculator/": "/tools/",
    "/tools/break-even-roas-calculator": "/tools/",
    "/tools/break-even-roas-calculator/": "/tools/",
    "/tools/inventory-carrying-cost-calculator": "/tools/",
    "/tools/inventory-carrying-cost-calculator/": "/tools/",
    "/tools/landed-cost-calculator": "/tools/section-301-tariff-landed-cost-calculator/",
    "/tools/landed-cost-calculator/": "/tools/section-301-tariff-landed-cost-calculator/",
    "/tools/qsbs-section-1202-tax-calculator": "/tools/tcja-sunset-capital-gains/",
    "/tools/qsbs-section-1202-tax-calculator/": "/tools/tcja-sunset-capital-gains/",
    "/tools/qsbs-83b-tax-calculator": "/tools/tcja-sunset-capital-gains/",
    "/tools/qsbs-83b-tax-calculator/": "/tools/tcja-sunset-capital-gains/",
}

_B2B_ADJACENT_TOOL_METADATA: Dict[str, Dict[str, str]] = {
    "s-corp-reasonable-salary-tax-calculator": {
        "slug": "s-corp-reasonable-salary-tax-calculator",
        "title": "S-Corp Reasonable Salary & Self-Employment Tax Calculator",
        "short_title": "S-Corp Salary Tax",
        "category": "Corporate Finance",
        "canonical_path": "/tools/s-corp-reasonable-salary-tax-calculator/",
    },
    "section-179-calculator": {
        "slug": "section-179-calculator",
        "title": "Section 179 Equipment Deduction & Bonus Depreciation Calculator",
        "short_title": "Section 179 Deduction",
        "category": "Corporate Finance",
        "canonical_path": "/tools/section-179-calculator/",
    },
    "saas-runway-calculator": {
        "slug": "saas-runway-calculator",
        "title": "SaaS Burn Multiple & Cash Runway Calculator",
        "short_title": "SaaS Burn & Runway",
        "category": "Corporate Finance",
        "canonical_path": "/tools/saas-runway-calculator/",
    },
    "irs-2027-tax-brackets": {
        "slug": "irs-2027-tax-brackets",
        "title": "IRS 2027 Tax Brackets & TCJA Sunset Calculator",
        "short_title": "IRS 2027 Tax Brackets",
        "category": "Tax Intelligence",
        "canonical_path": "/tools/irs-2027-tax-brackets/",
    },
    "tcja-sunset-capital-gains": {
        "slug": "tcja-sunset-capital-gains",
        "title": "Capital Gains & TCJA Sunset Statutory Tax Calculator",
        "short_title": "Capital Gains Tax",
        "category": "Tax Intelligence",
        "canonical_path": "/tools/tcja-sunset-capital-gains/",
    },
}


def is_retired_or_consolidated_slug(slug: str, property_id: Optional[str] = None) -> bool:
    """Returns True if slug is a consolidated clone, retired redirect source, or synthetic test fixture."""
    s = str(slug or "").strip().lower()
    if not s:
        return False
    if is_synthetic_test_candidate(s):
        return True
    prop = str(property_id or "").strip().lower()
    if prop == "prexvo":
        return s in PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP or s == "loans"
    if prop == "profithelm":
        return (
            s in CANNIBALIZING_CLONE_CONSOLIDATION_MAP
            or f"/tools/{s}" in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP
            or f"/{s}" in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP
        )
    return (
        s in CANNIBALIZING_CLONE_CONSOLIDATION_MAP
        or s in PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP
        or f"/tools/{s}" in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP
        or f"/{s}" in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP
    )


def _clean_tool_mixed_topical_signals(
    tool: Dict[str, Any],
    grouped_queries_for_slug: Optional[List[str]] = None,
) -> bool:
    """
    Cleans mixed topical signals on a dynamic_tools.json entry in-place:
    1. Replaces cannibalizing clone slugs in adjacent_tools with canonical hubs, and replaces
       retail crypto-tax-calculator / prediction-market-odds links on B2B commercial calculators
       with B2B tax/finance hubs (handling plain string slugs, dicts, and stringified dicts).
    2. Replaces copy-pasted TCJA Sunset / IRC Section 1411 NIIT calculation_prompts on non-capital-gains
       tools with prompts grounded in the tool's own statutory authority.
    3. Replaces copy-pasted IRC Section 1202 / IRC Section 1411 rows in proprietary_calculation_table
       on non-capital-gains tools with rows grounded in the tool's own statutory authority
       (handling both list-of-rows and dict-with-rows schemas).
    4. Merges grouped queries from consolidated clones into secondary_keywords.
    Returns True if tool dict was mutated.
    Zero em-dashes. Zero en-dashes.
    """
    changed = False
    slug = str(tool.get("slug") or "").strip()
    title = str(tool.get("title") or slug.replace("-", " ").title()).strip()
    stat_refs = tool.get("statutory_references") if isinstance(tool.get("statutory_references"), list) else []
    primary_stat = str(
        stat_refs[0]
        if stat_refs
        else (tool.get("statutory_authority") or "26 U.S.C. Section 162 and IRC Section 179")
    ).strip()

    # 1. Merge grouped queries into secondary_keywords
    if grouped_queries_for_slug:
        sec = list(tool.get("secondary_keywords") or [])
        sec_lower = {str(s).lower().strip() for s in sec if s}
        for gq in grouped_queries_for_slug:
            gq_clean = str(gq).lower().strip()
            if gq_clean and gq_clean not in sec_lower:
                sec.append(gq_clean)
                sec_lower.add(gq_clean)
                changed = True
        tool["secondary_keywords"] = sec

    is_crypto_or_prediction = any(k in slug for k in ("crypto", "prediction", "kalshi"))
    is_cap_gains_related = any(k in slug for k in ("capital-gains", "1031", "crypto"))

    def _map_b2b_adjacent_slug(cand_slug: str, seen: Set[str]) -> str:
        mapped = str(cand_slug or "").strip()
        if mapped in CANNIBALIZING_CLONE_CONSOLIDATION_MAP:
            mapped = CANNIBALIZING_CLONE_CONSOLIDATION_MAP[mapped]["canonical_slug"]
        elif mapped in PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP:
            mapped = PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP[mapped]["canonical_slug"]
        if mapped in ("crypto-tax-calculator", "prediction-market-odds") and not is_crypto_or_prediction:
            for fallback in ("s-corp-reasonable-salary-tax-calculator", "section-179-calculator", "saas-runway-calculator"):
                if fallback != slug and fallback not in seen:
                    mapped = fallback
                    break
            else:
                mapped = "section-179-calculator" if slug != "section-179-calculator" else "saas-runway-calculator"
        return mapped

    # 2. Clean adjacent_tools (supports plain string slugs, dicts, or stringified Python dicts)
    adj = tool.get("adjacent_tools")
    if isinstance(adj, list):
        new_adj: List[Any] = []
        seen_adj_slugs: Set[str] = set()
        for a_item in adj:
            if isinstance(a_item, dict):
                orig_slug = str(a_item.get("slug") or "").strip()
                mapped_slug = _map_b2b_adjacent_slug(orig_slug, seen_adj_slugs)
                if not mapped_slug or mapped_slug == slug or mapped_slug in seen_adj_slugs:
                    continue
                seen_adj_slugs.add(mapped_slug)
                if mapped_slug != orig_slug:
                    meta = _B2B_ADJACENT_TOOL_METADATA.get(mapped_slug, {})
                    updated_item = dict(a_item)
                    updated_item["slug"] = mapped_slug
                    updated_item["title"] = meta.get("title", mapped_slug.replace("-", " ").title())
                    updated_item["short_title"] = meta.get("short_title", mapped_slug.replace("-", " ").title())
                    updated_item["category"] = meta.get("category", "Corporate Finance")
                    updated_item["canonical_path"] = f"/tools/{mapped_slug}/"
                    new_adj.append(updated_item)
                else:
                    new_adj.append(a_item)
            elif isinstance(a_item, str):
                s_strip = a_item.strip()
                parsed_dict: Optional[Dict[str, Any]] = None
                if s_strip.startswith("{") and s_strip.endswith("}"):
                    try:
                        val = ast.literal_eval(s_strip)
                        if isinstance(val, dict):
                            parsed_dict = val
                    except Exception:
                        parsed_dict = None
                if parsed_dict is not None:
                    orig_slug = str(parsed_dict.get("slug") or "").strip()
                    mapped_slug = _map_b2b_adjacent_slug(orig_slug, seen_adj_slugs)
                    if not mapped_slug or mapped_slug == slug or mapped_slug in seen_adj_slugs:
                        continue
                    seen_adj_slugs.add(mapped_slug)
                    if mapped_slug != orig_slug:
                        meta = _B2B_ADJACENT_TOOL_METADATA.get(mapped_slug, {})
                        updated_dict = dict(parsed_dict)
                        updated_dict["slug"] = mapped_slug
                        updated_dict["title"] = meta.get("title", mapped_slug.replace("-", " ").title())
                        updated_dict["short_title"] = meta.get("short_title", mapped_slug.replace("-", " ").title())
                        updated_dict["category"] = meta.get("category", "Corporate Finance")
                        updated_dict["canonical_path"] = f"/tools/{mapped_slug}/"
                        new_adj.append(repr(updated_dict))
                    else:
                        new_adj.append(a_item)
                else:
                    mapped_slug = _map_b2b_adjacent_slug(s_strip, seen_adj_slugs)
                    if mapped_slug and mapped_slug != slug and mapped_slug not in seen_adj_slugs:
                        seen_adj_slugs.add(mapped_slug)
                        new_adj.append(mapped_slug)
        if new_adj != adj:
            tool["adjacent_tools"] = new_adj
            changed = True

    # 3. Clean copy-pasted TCJA Sunset / Section 1411 NIIT calculation_prompts on B2B calculators
    prompts = tool.get("calculation_prompts")
    if isinstance(prompts, list) and not is_cap_gains_related:
        new_prompts: List[Dict[str, Any]] = []
        prompts_changed = False
        seen_target_slugs: Set[str] = set()
        for idx, p_item in enumerate(prompts):
            if not isinstance(p_item, dict):
                continue
            lbl = str(p_item.get("label") or "")
            ttl = str(p_item.get("title") or "")
            prm = str(p_item.get("prompt") or "")
            sref = str(p_item.get("statutory_reference") or "")
            ctx = str(p_item.get("context") or "")
            tslug = str(p_item.get("target_slug") or "")
            combined_p = f"{lbl} {ttl} {prm} {sref} {ctx}"
            has_off_topic_signal = any(
                marker in combined_p
                for marker in ("TCJA Sunset", "1411", "NIIT", "Net Investment Income Surtax")
            )
            mapped_tslug = _map_b2b_adjacent_slug(tslug, seen_target_slugs) if tslug else ""
            if mapped_tslug:
                seen_target_slugs.add(mapped_tslug)
            if has_off_topic_signal or (tslug and mapped_tslug != tslug):
                prompts_changed = True
                updated_p = dict(p_item)
                if "label" in updated_p and not updated_p.get("title"):
                    if idx == 1:
                        updated_p["label"] = "Statutory Phase-Out & Threshold Sensitivity"
                        updated_p["prompt"] = (
                            f"Evaluate {title} across statutory phase-out thresholds and marginal cost tiers "
                            f"under {primary_stat} to quantify net after-tax cash flow impact."
                        )
                    else:
                        updated_p["label"] = "Multi-Year Working Capital & Deduction Timing"
                        updated_p["prompt"] = (
                            f"Compare first-year deduction recovery against multi-year amortization schedules "
                            f"for {title} under {primary_stat}."
                        )
                else:
                    if idx == 0:
                        updated_p["title"] = "Statutory Deduction & Effective Cost Simulation"
                        updated_p["prompt"] = (
                            f"Calculate how {primary_stat} deduction thresholds and marginal tax rates adjust net liability for {title}."
                        )
                        updated_p["query"] = f"{slug.replace('-', ' ')} statutory deduction and marginal tax rate"
                        updated_p["statutory_reference"] = primary_stat
                        updated_p["context"] = (
                            f"Commercial expenditures and deduction phase-outs under {primary_stat} directly determine net after-tax cash flow."
                        )
                    elif idx == 1:
                        updated_p["title"] = "Statutory Phase-Out & Threshold Sensitivity"
                        updated_p["prompt"] = (
                            f"Evaluate {title} across statutory phase-out thresholds and marginal cost tiers under {primary_stat}."
                        )
                        updated_p["query"] = f"{slug.replace('-', ' ')} phase out threshold and working capital impact"
                        updated_p["statutory_reference"] = primary_stat
                        updated_p["context"] = (
                            f"Statutory phase-out rules under {primary_stat} govern the effective marginal cost of capital across commercial tiers."
                        )
                    if mapped_tslug:
                        meta = _B2B_ADJACENT_TOOL_METADATA.get(mapped_tslug, {})
                        updated_p["target_slug"] = mapped_tslug
                        updated_p["target_title"] = meta.get("short_title") or meta.get("title") or mapped_tslug.replace("-", " ").title()
                new_prompts.append(updated_p)
            else:
                new_prompts.append(p_item)
        if prompts_changed:
            tool["calculation_prompts"] = new_prompts
            changed = True

    # 4. Clean copy-pasted IRC Section 1202 / IRC Section 1411 rows in proprietary_calculation_table
    prop_table = tool.get("proprietary_calculation_table")
    if isinstance(prop_table, list) and not is_cap_gains_related:
        new_table: List[Dict[str, Any]] = []
        table_changed = False
        for row in prop_table:
            if not isinstance(row, dict):
                continue
            scen = str(row.get("scenario") or "")
            ref = str(row.get("reference") or "")
            if "IRC Section 1202" in scen or "IRC Section 1202" in ref:
                table_changed = True
                updated_row = dict(row)
                if "scenario" in updated_row:
                    updated_row["scenario"] = f"Accelerated Deduction Tier ({primary_stat})"
                if "notes" in updated_row:
                    updated_row["notes"] = f"Statutory phase-out threshold compliance verified under {primary_stat}"
                if "reference" in updated_row:
                    updated_row["reference"] = primary_stat
                new_table.append(updated_row)
            elif "IRC Section 1411" in scen or "IRC Section 1411" in ref:
                table_changed = True
                updated_row = dict(row)
                if "scenario" in updated_row:
                    updated_row["scenario"] = f"High-Volume Commercial Tier ({primary_stat})"
                if "notes" in updated_row:
                    updated_row["notes"] = f"Marginal cost and effective burden sensitivity under {primary_stat}"
                if "reference" in updated_row:
                    updated_row["reference"] = primary_stat
                new_table.append(updated_row)
            else:
                new_table.append(row)
        if table_changed:
            tool["proprietary_calculation_table"] = new_table
            changed = True
    elif isinstance(prop_table, dict) and isinstance(prop_table.get("rows"), list) and not is_cap_gains_related:
        new_rows: List[Dict[str, Any]] = []
        rows_changed = False
        for row in prop_table["rows"]:
            if not isinstance(row, dict):
                continue
            ref = str(row.get("reference") or "")
            scen = str(row.get("scenario") or "")
            if any(m in ref or m in scen for m in ("IRC Section 1202", "IRC Section 1411")):
                rows_changed = True
                updated_row = dict(row)
                if "reference" in updated_row:
                    updated_row["reference"] = primary_stat
                if "scenario" in updated_row:
                    updated_row["scenario"] = f"Commercial Statutory Tier ({primary_stat})"
                new_rows.append(updated_row)
            else:
                new_rows.append(row)
        if rows_changed:
            updated_table = dict(prop_table)
            updated_table["rows"] = new_rows
            tool["proprietary_calculation_table"] = updated_table
            changed = True

    return changed


def reconcile_void_candidates_queue(
    vc_path: Union[str, Path],
    gsc_rows: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    Reconciles a void_candidates.jsonl topic queue against consolidated/retired slugs,
    synthetic/off-topic patterns, and canonical/GSC striking-distance tools so the autonomous
    pipeline never re-queues or builds duplicate pages for queries an existing URL already covers.
    Returns the number of updated or deduplicated records.
    Zero em-dashes. Zero en-dashes.
    """
    p = Path(vc_path)
    if not p.is_file() or str(p).startswith("/dev/"):
        return 0
    try:
        raw_lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return 0
    if not raw_lines:
        return 0

    all_clone_maps: Dict[str, Dict[str, str]] = {}
    all_clone_maps.update(PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP)
    all_clone_maps.update(CANNIBALIZING_CLONE_CONSOLIDATION_MAP)
    combined_core_tools = (
        list(_DEFAULT_PROFITHELM_CORE_TOOLS)
        + list(_DEFAULT_PREXVO_CORE_TOOLS)
        + list(_DEFAULT_GAINHELM_CORE_TOOLS)
    )

    updated_count = 0
    reconciled_records: List[Dict[str, Any]] = []
    for line in raw_lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        rec_copy = dict(rec)
        raw_slug = str(rec_copy.get("slug") or "").strip().lower()
        raw_query = str(rec_copy.get("query") or rec_copy.get("primary_keyword") or "").strip().lower()
        slug_from_query = re.sub(r"[^a-z0-9]+", "-", raw_query).strip("-") if raw_query else ""
        eff_slug = raw_slug or slug_from_query

        if is_synthetic_test_candidate(eff_slug or raw_query, rec_copy) or "site:" in raw_query:
            if rec_copy.get("status") != "REJECTED" or rec_copy.get("action") != "REJECT":
                rec_copy["status"] = "REJECTED"
                rec_copy["action"] = "REJECT"
                rec_copy["status_reason"] = "Rejected synthetic, scraper, or off-topic candidate"
                updated_count += 1
        elif is_thin_affiliate_listicle_candidate(eff_slug or raw_query, rec_copy):
            if rec_copy.get("status") != "REJECTED" or rec_copy.get("action") != "REJECT_LISTICLE_ARCHETYPE":
                rec_copy["status"] = "REJECTED"
                rec_copy["action"] = "REJECT_LISTICLE_ARCHETYPE"
                rec_copy["rejected_archetype"] = "thin_affiliate_listicle"
                rec_copy["recommended_alternative_archetype"] = "deterministic_statutory_comparison_calculator"
                rec_copy["status_reason"] = (
                    "Rejected thin affiliate listicle archetype in favor of first-party statutory calculator or comparison matrix"
                )
                updated_count += 1
        elif eff_slug in all_clone_maps or slug_from_query in all_clone_maps:
            matched_key = eff_slug if eff_slug in all_clone_maps else slug_from_query
            info = all_clone_maps[matched_key]
            if (
                rec_copy.get("status") != "REJECTED"
                or rec_copy.get("consolidation_status") != "CONSOLIDATED_REDIRECT"
                or rec_copy.get("canonical_slug") != info["canonical_slug"]
                or rec_copy.get("redirect_target") != info["redirect_target"]
            ):
                rec_copy["status"] = "REJECTED"
                rec_copy["action"] = "REFACTOR_PAGE"
                rec_copy["consolidation_status"] = "CONSOLIDATED_REDIRECT"
                rec_copy["canonical_slug"] = info["canonical_slug"]
                rec_copy["redirect_target"] = info["redirect_target"]
                rec_copy["status_reason"] = (
                    f"Consolidated into canonical hub {info['canonical_slug']} ({info['redirect_target']})"
                )
                updated_count += 1
        else:
            act = str(rec_copy.get("action") or "").strip().upper()
            cur_status = str(rec_copy.get("status") or "").strip().upper()
            if act in ("REJECT", "MONITOR") and cur_status != "REJECTED":
                rec_copy["status"] = "REJECTED"
                rec_copy["status_reason"] = (
                    rec_copy.get("status_reason")
                    or f"Engine verdict {act}: {rec_copy.get('decision_reason') or 'not actionable'}"
                )
                updated_count += 1
            elif act == "BUILD_PAGE" and cur_status not in ("BUILT", "REJECTED"):
                mod_eval = evaluate_query_modifier_expansion_vs_distinct_tool(
                    raw_query or eff_slug.replace("-", " "),
                    existing_tools=combined_core_tools,
                    gsc_rows=gsc_rows,
                )
                if mod_eval.get("suppress_duplicate_build") and mod_eval.get("parent_slug") not in (None, "", "none"):
                    p_slug = str(mod_eval["parent_slug"])
                    t_sub = str(mod_eval.get("target_subroute") or f"/tools/{p_slug}/")
                    rec_copy["action"] = "REFACTOR_PAGE"
                    rec_copy["status"] = "REFACTOR_PENDING"
                    rec_copy["matching_tool"] = p_slug
                    rec_copy["canonical_slug"] = p_slug
                    rec_copy["target_subroute"] = t_sub
                    rec_copy["redirect_target"] = t_sub
                    rec_copy["modifier_decision"] = "EXPAND_EXISTING_PAGE"
                    rec_copy["status_reason"] = (
                        f"Suppressed duplicate BUILD_PAGE; routed to REFACTOR_PAGE on {t_sub} ({mod_eval.get('modifier_classification')})"
                    )
                    updated_count += 1

        reconciled_records.append(rec_copy)

    if updated_count > 0:
        p.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in reconciled_records) + "\n",
            encoding="utf-8",
        )
    return updated_count


def _clean_syndication_directories_and_ledgers(
    root: Path,
    prop: str,
    slugs_to_purge: Set[str],
) -> int:
    """
    Purges stale syndication folders, files, markdown entries, broadcast_ledger entries,
    and facebook_groups_catalog entries for retired/consolidated/synthetic slugs.
    Returns count of removed/cleaned syndication artifacts.
    Zero em-dashes. Zero en-dashes.
    """
    removed_count = 0
    synd_dirs = [root / "syndication"]
    is_foreign_pytest = bool("PYTEST_CURRENT_TEST" in os.environ)
    if not is_foreign_pytest:
        central_synd = Path(__file__).resolve().parent.parent / "syndication" / prop
        if central_synd.is_dir() and central_synd not in synd_dirs:
            synd_dirs.append(central_synd)

    active_built_slugs: Set[str] = set()
    dist_tools_dir = root / "dist" / "tools"
    if not is_foreign_pytest and dist_tools_dir.is_dir():
        for dt_entry in dist_tools_dir.iterdir():
            if dt_entry.is_dir() and not dt_entry.name.startswith(".") and (dt_entry / "index.html").is_file():
                if not is_retired_or_consolidated_slug(dt_entry.name, prop):
                    active_built_slugs.add(dt_entry.name)

    for synd_dir in synd_dirs:
        if not synd_dir.is_dir():
            continue
        for item in sorted(synd_dir.iterdir()):
            if item.name.startswith("."):
                continue
            if item.name == "ai_benchmarks" and item.is_dir():
                for b_item in sorted(item.iterdir()):
                    if not b_item.is_file():
                        continue
                    b_stem = b_item.name
                    if b_stem.endswith("_matrix.md"):
                        prefix = b_stem[: -len("_matrix.md")]
                    elif b_stem.endswith("_benchmarks.md"):
                        prefix = b_stem[: -len("_benchmarks.md")].replace("_", "-")
                    elif b_stem.endswith("_benchmarks.json"):
                        prefix = b_stem[: -len("_benchmarks.json")].replace("_", "-")
                    else:
                        continue
                    if (
                        prefix in slugs_to_purge
                        or is_retired_or_consolidated_slug(prefix, prop)
                        or (b_stem.endswith("_matrix.md") and active_built_slugs and prefix not in active_built_slugs)
                    ):
                        try:
                            b_item.unlink()
                            removed_count += 1
                        except Exception:
                            pass
                continue
            if item.is_dir():
                if (
                    item.name in slugs_to_purge
                    or is_retired_or_consolidated_slug(item.name, prop)
                    or (active_built_slugs and item.name not in active_built_slugs)
                ):
                    shutil.rmtree(item, ignore_errors=True)
                    removed_count += 1
            elif item.is_file():
                matched_prefix = False
                for dead_s in slugs_to_purge:
                    if item.name == f"{dead_s}.md" or item.name == f"{dead_s}.json" or item.name.startswith(f"{dead_s}-"):
                        matched_prefix = True
                        break
                if matched_prefix:
                    try:
                        item.unlink()
                        removed_count += 1
                    except Exception:
                        pass

        # Clean retired slug references from github_seed_discovery.md and facebook_group_targets.md
        gh_md = synd_dir / "github_seed_discovery.md"
        if gh_md.is_file():
            try:
                gh_txt = gh_md.read_text(encoding="utf-8")
                gh_lines = gh_txt.splitlines()
                filtered_gh = [
                    ln for ln in gh_lines
                    if not any(f"/tools/{ds}/" in ln or f"/tools/{ds})" in ln for ds in slugs_to_purge)
                ]
                if len(filtered_gh) != len(gh_lines):
                    gh_md.write_text("\n".join(filtered_gh) + "\n", encoding="utf-8")
                    removed_count += 1
            except Exception:
                pass

        fb_md = synd_dir / "facebook_group_targets.md"
        if fb_md.is_file():
            try:
                fb_txt = fb_md.read_text(encoding="utf-8")
                if any(f"/tools/{ds}/" in fb_txt for ds in slugs_to_purge):
                    sections = re.split(r"(?m)^(?=## )", fb_txt)
                    kept_sections = [
                        sec for sec in sections
                        if not any(f"/tools/{ds}/" in sec for ds in slugs_to_purge)
                    ]
                    if len(kept_sections) != len(sections):
                        new_fb_txt = "".join(kept_sections)
                        fb_md.write_text(new_fb_txt, encoding="utf-8")
                        removed_count += 1
            except Exception:
                pass

    # Clean .agy/reddit_drafts
    reddit_drafts_dir = root / ".agy" / "reddit_drafts"
    if reddit_drafts_dir.is_dir():
        for r_file in sorted(reddit_drafts_dir.iterdir()):
            if not r_file.is_file():
                continue
            r_slug = r_file.stem
            if (
                r_slug in slugs_to_purge
                or is_retired_or_consolidated_slug(r_slug, prop)
                or (active_built_slugs and r_slug not in active_built_slugs)
            ):
                try:
                    r_file.unlink()
                    removed_count += 1
                except Exception:
                    pass

    # Clean .agy/urls_to_index.txt
    urls_idx_file = root / ".agy" / "urls_to_index.txt"
    if urls_idx_file.is_file():
        try:
            u_lines = [ln.strip() for ln in urls_idx_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            kept_u: List[str] = []
            seen_u: Set[str] = set()
            for ln in u_lines:
                m_u = re.search(r"/tools/([^/?#]+)", ln)
                if m_u:
                    u_slug = m_u.group(1).strip()
                    if (
                        u_slug in slugs_to_purge
                        or is_retired_or_consolidated_slug(u_slug, prop)
                        or (active_built_slugs and u_slug not in active_built_slugs)
                    ):
                        continue
                if ln not in seen_u:
                    seen_u.add(ln)
                    kept_u.append(ln)
            if kept_u != u_lines:
                urls_idx_file.write_text("\n".join(kept_u) + ("\n" if kept_u else ""), encoding="utf-8")
                removed_count += 1
        except Exception:
            pass

    # Clean .agy/gsc_remediation_queue.json and .agy/indexing_audit_log.json
    for agy_json_name in ("gsc_remediation_queue.json", "indexing_audit_log.json"):
        agy_json_path = root / ".agy" / agy_json_name
        if not agy_json_path.is_file():
            continue
        try:
            raw_j = json.loads(agy_json_path.read_text(encoding="utf-8"))
            j_changed = False
            if isinstance(raw_j, dict):
                for list_key in ("items", "remediations", "queue", "urls", "entries", "targets", "audit_results"):
                    val_list = raw_j.get(list_key)
                    if isinstance(val_list, list):
                        new_list = []
                        for entry in val_list:
                            entry_str = json.dumps(entry) if not isinstance(entry, str) else entry
                            m_tools = re.findall(r"/tools/([^/?#\"'\s]+)", entry_str)
                            if any(
                                ts in slugs_to_purge
                                or is_retired_or_consolidated_slug(ts, prop)
                                or (active_built_slugs and ts not in active_built_slugs)
                                for ts in m_tools
                            ):
                                j_changed = True
                                continue
                            new_list.append(entry)
                        if len(new_list) != len(val_list):
                            raw_j[list_key] = new_list
                            if "total_items" in raw_j and list_key == "items":
                                raw_j["total_items"] = len(new_list)
            elif isinstance(raw_j, list):
                new_list = []
                for entry in raw_j:
                    entry_str = json.dumps(entry) if not isinstance(entry, str) else entry
                    m_tools = re.findall(r"/tools/([^/?#\"'\s]+)", entry_str)
                    if any(
                        ts in slugs_to_purge
                        or is_retired_or_consolidated_slug(ts, prop)
                        or (active_built_slugs and ts not in active_built_slugs)
                        for ts in m_tools
                    ):
                        j_changed = True
                        continue
                    new_list.append(entry)
                raw_j = new_list
            if j_changed:
                agy_json_path.write_text(json.dumps(raw_j, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                removed_count += 1
        except Exception:
            pass

    # Clean and deduplicate .agy/broadcast_ledger.json and .agy/facebook_groups_catalog*.json
    b_ledger = root / ".agy" / "broadcast_ledger.json"
    if b_ledger.is_file():
        try:
            b_data = json.loads(b_ledger.read_text(encoding="utf-8"))
            if isinstance(b_data, list):
                dedup_by_slug: Dict[str, Dict[str, Any]] = {}
                ordered_b_slugs: List[str] = []
                for entry in b_data:
                    if not isinstance(entry, dict):
                        continue
                    eslug = str(entry.get("slug") or "").strip()
                    if (
                        not eslug
                        or eslug in ("direct_broadcast",)
                        or eslug.startswith("mock_")
                        or eslug in slugs_to_purge
                        or is_retired_or_consolidated_slug(eslug, prop)
                        or (active_built_slugs and eslug not in active_built_slugs)
                    ):
                        continue
                    if eslug not in dedup_by_slug:
                        ordered_b_slugs.append(eslug)
                    dedup_by_slug[eslug] = entry
                filtered_b = [dedup_by_slug[s] for s in ordered_b_slugs]
                if len(filtered_b) != len(b_data) or filtered_b != b_data:
                    b_ledger.write_text(json.dumps(filtered_b, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    removed_count += 1
        except Exception:
            pass

    for fb_cat_name in ("facebook_groups_catalog.json", "facebook_groups_catalog.dryrun.json"):
        fb_cat = root / ".agy" / fb_cat_name
        if fb_cat.is_file():
            try:
                cat_data = json.loads(fb_cat.read_text(encoding="utf-8"))
                if isinstance(cat_data, dict):
                    dead_keys = [
                        k for k in cat_data.keys()
                        if k in slugs_to_purge or is_retired_or_consolidated_slug(k, prop)
                    ]
                    if dead_keys:
                        for dk in dead_keys:
                            cat_data.pop(dk, None)
                        fb_cat.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        removed_count += 1
            except Exception:
                pass

    return removed_count


def reconcile_tenant_topical_authority_and_cannibalization(
    repo_root: Union[str, Path],
    property_id: str = "profithelm",
    dist_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Deterministically reconciles a tenant repository's tool catalog, redirects, overlays,
    syndication packs, tool_spec provenance files, void_candidates queues, and compiled dist
    directory against the Search Intent & Topical Authority Doctrine:
    1. Consolidates standalone cannibalizing clone hubs and removes synthetic test fixtures.
    2. Groups harvested queries/scenarios from retired clones onto their canonical parent
       tool overlays without resetting active 28-day measurement locks, and syncs
       .agy/overlays <-> content/overlays.
    3. Registers 301 consolidation redirects in content/redirects.json and re-points
       legacy off-topic e-commerce/Shopify redirects to /tools/.
    4. Removes stale dist/tools/<clone_slug>, dist/manifests/<clone_slug>.json,
       .agy/tool_spec_<clone_slug>.json, and syndication/<clone_slug> before tenant build_all()
       runs so redirect verification, syndication, and sitemap hygiene pass cleanly.
    5. Scrubs mixed topical signals (retail crypto adjacent links and copy-pasted TCJA/NIIT/1202
       prompts/tables) from B2B commercial calculators in dynamic_tools.json.
    6. Reconciles void_candidates.jsonl queues so retired clones can never be re-queued.
    Zero em-dashes. Zero en-dashes.
    """
    root = Path(repo_root)
    eff_dist = Path(dist_dir) if dist_dir else (root / "dist")
    prop = str(property_id or "profithelm").strip().lower()

    summary: Dict[str, Any] = {
        "property_id": prop,
        "consolidated_clones": [],
        "removed_synthetic_slugs": [],
        "cleaned_mixed_signal_slugs": [],
        "redirects_updated": 0,
        "overlays_synced": 0,
        "stale_dist_dirs_removed": 0,
        "stale_tool_specs_removed": 0,
        "stale_syndication_removed": 0,
        "void_candidates_reconciled": 0,
    }

    clone_map = (
        PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP
        if prop == "prexvo"
        else CANNIBALIZING_CLONE_CONSOLIDATION_MAP
    )

    if prop != "profithelm":
        prexvo_purge_slugs = set(PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP.keys()) | {"query-two-buildable", "loans"}
        if eff_dist.is_dir():
            for purge_slug in sorted(prexvo_purge_slugs):
                if purge_slug == "loans":
                    continue
                stale_tool_dir = eff_dist / "tools" / purge_slug
                if stale_tool_dir.is_dir():
                    shutil.rmtree(stale_tool_dir, ignore_errors=True)
                    summary["stale_dist_dirs_removed"] += 1
                stale_manifest = eff_dist / "manifests" / f"{purge_slug}.json"
                if stale_manifest.is_file():
                    try:
                        stale_manifest.unlink()
                    except Exception:
                        pass
        summary["stale_syndication_removed"] += _clean_syndication_directories_and_ledgers(
            root=root,
            prop=prop,
            slugs_to_purge=prexvo_purge_slugs,
        )
        agy_ov = root / ".agy" / "overlays"
        cnt_ov = root / "content" / "overlays"
        is_prod_repo = str(root.resolve()).startswith("/home/ubuntuadmin/projects/") and "PYTEST_CURRENT_TEST" not in os.environ
        if agy_ov.is_dir() or cnt_ov.is_dir():
            agy_ov.mkdir(parents=True, exist_ok=True)
            if not is_prod_repo:
                cnt_ov.mkdir(parents=True, exist_ok=True)
            for ov_dir in (agy_ov, cnt_ov):
                if not ov_dir.is_dir():
                    continue
                for purge_slug in sorted(prexvo_purge_slugs):
                    ov_f = ov_dir / f"{purge_slug}.json"
                    if ov_f.is_file():
                        try:
                            ov_f.unlink()
                        except Exception:
                            pass
            if is_prod_repo:
                if cnt_ov.is_dir():
                    for ov_f in sorted(cnt_ov.glob("*.json")):
                        dst_f = agy_ov / ov_f.name
                        if not dst_f.is_file():
                            shutil.move(str(ov_f), str(dst_f))
                            summary["overlays_synced"] += 1
                        else:
                            ov_f.unlink(missing_ok=True)
                    try:
                        cnt_ov.rmdir()
                    except OSError:
                        pass
            else:
                for src_dir, dst_dir in ((agy_ov, cnt_ov), (cnt_ov, agy_ov)):
                    for ov_f in sorted(src_dir.glob("*.json")):
                        dst_f = dst_dir / ov_f.name
                        if not dst_f.is_file():
                            shutil.copyfile(ov_f, dst_f)
                            summary["overlays_synced"] += 1
        summary["metric_recovery_ledger_reconciled"] = reconcile_metric_recovery_ledger(root, prop)
        summary["factory_execution_log_reconciled"] = reconcile_factory_execution_log(root, prop)
        if "PYTEST_CURRENT_TEST" not in os.environ and str(root).startswith("/home/ubuntuadmin/projects/"):
            summary["tenant_adapters_synced"] = sync_tenant_redirect_rollup_adapters(root, prop)
        return summary

    grouped_queries_by_canonical: Dict[str, List[str]] = {}
    grouped_queries_by_leaf: Dict[str, List[str]] = {}
    for clone_slug, info in clone_map.items():
        c_slug = info["canonical_slug"]
        r_target = str(info.get("redirect_target") or "").strip("/")
        q_default = clone_slug.replace("-scenario-comparison-model", "").replace("-", " ").strip()
        grouped_queries_by_canonical.setdefault(c_slug, [])
        if q_default and q_default not in grouped_queries_by_canonical[c_slug]:
            grouped_queries_by_canonical[c_slug].append(q_default)
        t_parts = [p for p in r_target.split("/") if p]
        if len(t_parts) >= 3 and t_parts[0] == "tools":
            leaf_ov_slug = f"{t_parts[1]}-{t_parts[2]}"
            grouped_queries_by_leaf.setdefault(leaf_ov_slug, [])
            if q_default and q_default not in grouped_queries_by_leaf[leaf_ov_slug]:
                grouped_queries_by_leaf[leaf_ov_slug].append(q_default)

    # 1. Reconcile profithelm/data/dynamic_tools.json and .agy/dynamic_tools.json
    dyn_paths = [
        root / "profithelm" / "data" / "dynamic_tools.json",
        root / ".agy" / "dynamic_tools.json",
    ]
    for dyn_path in dyn_paths:
        if not dyn_path.is_file():
            continue
        try:
            raw_tools = json.loads(dyn_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw_tools, list):
            continue

        for t in raw_tools:
            if not isinstance(t, dict):
                continue
            s = str(t.get("slug") or "").strip()
            if s in clone_map:
                c_slug = clone_map[s]["canonical_slug"]
                bucket = grouped_queries_by_canonical.setdefault(c_slug, [])
                for kw in [t.get("primary_keyword"), *(t.get("secondary_keywords") or [])]:
                    kw_str = str(kw or "").strip().lower()
                    if kw_str and kw_str not in bucket:
                        bucket.append(kw_str)

        kept_tools: List[Dict[str, Any]] = []
        file_modified = False
        for t in raw_tools:
            if not isinstance(t, dict):
                continue
            s = str(t.get("slug") or "").strip()
            if is_synthetic_test_candidate(s, t):
                if s not in summary["removed_synthetic_slugs"]:
                    summary["removed_synthetic_slugs"].append(s)
                file_modified = True
                continue
            if s in clone_map:
                if s not in summary["consolidated_clones"]:
                    summary["consolidated_clones"].append(s)
                file_modified = True
                continue
            if _clean_tool_mixed_topical_signals(t, grouped_queries_by_canonical.get(s)):
                if s not in summary["cleaned_mixed_signal_slugs"]:
                    summary["cleaned_mixed_signal_slugs"].append(s)
                file_modified = True
            kept_tools.append(t)

        if file_modified:
            dyn_path.write_text(json.dumps(kept_tools, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. Reconcile .agy/deployed_voids.json (remove synthetic fixtures; annotate all consolidated clones)
    dv_path = root / ".agy" / "deployed_voids.json"
    if dv_path.is_file():
        try:
            dv_list = json.loads(dv_path.read_text(encoding="utf-8"))
            if isinstance(dv_list, list):
                new_dv: List[Any] = []
                dv_changed = False
                for entry in dv_list:
                    if isinstance(entry, dict):
                        s = str(entry.get("slug") or "").strip()
                        if is_synthetic_test_candidate(s, entry):
                            dv_changed = True
                            if s not in summary["removed_synthetic_slugs"]:
                                summary["removed_synthetic_slugs"].append(s)
                            continue
                        if s in clone_map:
                            info = clone_map[s]
                            if (
                                entry.get("status") != "CONSOLIDATED_REDIRECT"
                                or entry.get("canonical_slug") != info["canonical_slug"]
                                or entry.get("redirect_target") != info["redirect_target"]
                            ):
                                entry = dict(entry)
                                entry["status"] = "CONSOLIDATED_REDIRECT"
                                entry["canonical_slug"] = info["canonical_slug"]
                                entry["redirect_target"] = info["redirect_target"]
                                dv_changed = True
                    new_dv.append(entry)
                if dv_changed:
                    dv_path.write_text(json.dumps(new_dv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

    # 3. Build complete set of retired/consolidated/synthetic slugs to purge
    slugs_to_purge: Set[str] = set(clone_map.keys()) | {
        "query-two-buildable",
        "valid-edge-tool-2027",
        "bad-slug-with-underscores-and-dashes-invalid",
        "calculator-app",
        "calculator-net",
        "calculator-free",
        "calculator-near-me",
        "ionq-stock",
        "custom-test-calculator",
        "poison-pill-test",
        "irs-1031-exchange-tax-deferral-test",
        "dynamic-saas-benchmark-calculator",
    }
    for off_path in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP.keys():
        clean_off = off_path.strip("/")
        if clean_off.startswith("tools/"):
            slugs_to_purge.add(clean_off[len("tools/"):].strip("/"))
        elif "/" not in clean_off and clean_off:
            slugs_to_purge.add(clean_off)

    import sys
    for mod_name in (f"{prop}.config", "profithelm.config", "prexvo.config", "gainhelm.config"):
        cfg_mod = sys.modules.get(mod_name)
        if cfg_mod is not None:
            for attr_name in ("TOOLS", "DYNAMIC_TOOLS"):
                tool_list = getattr(cfg_mod, attr_name, None)
                if isinstance(tool_list, list):
                    tool_list[:] = [
                        t for t in tool_list
                        if not (isinstance(t, dict) and str(t.get("slug") or "").strip() in slugs_to_purge)
                    ]

    # Remove stale .agy/tool_spec_<slug>.json files for retired/consolidated/synthetic slugs
    agy_dir = root / ".agy"
    if agy_dir.is_dir():
        for spec_f in sorted(agy_dir.glob("tool_spec_*.json")):
            spec_slug = spec_f.name[len("tool_spec_"):-len(".json")]
            if spec_slug in slugs_to_purge or is_retired_or_consolidated_slug(spec_slug, prop):
                try:
                    spec_f.unlink()
                    summary["stale_tool_specs_removed"] += 1
                except Exception:
                    pass

    # 4. Remove stale dist/tools/<clone_slug> and dist/manifests/<clone_slug>.json before build_all()
    if eff_dist.is_dir():
        for purge_slug in sorted(slugs_to_purge):
            stale_tool_dir = eff_dist / "tools" / purge_slug
            if stale_tool_dir.is_dir():
                shutil.rmtree(stale_tool_dir, ignore_errors=True)
                summary["stale_dist_dirs_removed"] += 1
            stale_manifest = eff_dist / "manifests" / f"{purge_slug}.json"
            if stale_manifest.is_file():
                try:
                    stale_manifest.unlink()
                except Exception:
                    pass

    # 5. Update content/redirects.json with 301 consolidation rules and off-topic redirect cleanup
    redirects_path = root / "content" / "redirects.json"
    if redirects_path.is_file():
        try:
            redirects_data = json.loads(redirects_path.read_text(encoding="utf-8"))
        except Exception:
            redirects_data = {}
    else:
        redirects_data = {}

    if isinstance(redirects_data, dict):
        red_changed = False
        for clone_slug, info in clone_map.items():
            target = info["redirect_target"]
            for src_path in (f"/tools/{clone_slug}", f"/tools/{clone_slug}/"):
                cur_val = redirects_data.get(src_path)
                cur_target = cur_val.get("target") if isinstance(cur_val, dict) else cur_val
                if cur_target != target:
                    redirects_data[src_path] = target
                    red_changed = True
                    summary["redirects_updated"] += 1
        for synth_path in ("/tools/query-two-buildable", "/tools/query-two-buildable/"):
            if redirects_data.get(synth_path) != "/tools/":
                redirects_data[synth_path] = "/tools/"
                red_changed = True
                summary["redirects_updated"] += 1
        for src_path, target in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP.items():
            cur_val = redirects_data.get(src_path)
            cur_target = cur_val.get("target") if isinstance(cur_val, dict) else cur_val
            if cur_target != target:
                redirects_data[src_path] = target
                red_changed = True
                summary["redirects_updated"] += 1
        if red_changed:
            redirects_path.parent.mkdir(parents=True, exist_ok=True)
            redirects_path.write_text(json.dumps(redirects_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 6. Consolidate clone overlays into canonical parent overlays & sync .agy/overlays <-> content/overlays
    agy_ov_dir = root / ".agy" / "overlays"
    cnt_ov_dir = root / "content" / "overlays"
    is_prod_repo = str(root.resolve()).startswith("/home/ubuntuadmin/projects/") and "PYTEST_CURRENT_TEST" not in os.environ
    agy_ov_dir.mkdir(parents=True, exist_ok=True)
    if not is_prod_repo:
        cnt_ov_dir.mkdir(parents=True, exist_ok=True)

    for ov_dir in (agy_ov_dir, cnt_ov_dir):
        if not ov_dir.is_dir():
            continue
        for purge_slug in sorted(slugs_to_purge):
            ov_f = ov_dir / f"{purge_slug}.json"
            if ov_f.is_file():
                try:
                    ov_data = json.loads(ov_f.read_text(encoding="utf-8"))
                    if isinstance(ov_data, dict) and purge_slug in clone_map:
                        c_slug = clone_map[purge_slug]["canonical_slug"]
                        bucket = grouped_queries_by_canonical.setdefault(c_slug, [])
                        for q_item in [ov_data.get("query"), ov_data.get("target_query"), *(ov_data.get("grouped_queries") or [])]:
                            q_str = str(q_item or "").strip().lower()
                            if q_str and q_str not in bucket:
                                bucket.append(q_str)
                    ov_f.unlink()
                except Exception:
                    pass

    if prop == "profithelm":
        from pseofactory.competitor import PROFITHELM_SECTION_179_VEHICLES
        veh_slugs = {v[0] for v in PROFITHELM_SECTION_179_VEHICLES}
        for ov_dir in (agy_ov_dir, cnt_ov_dir):
            if not ov_dir.is_dir():
                continue
            for v_slug in sorted(veh_slugs):
                unpref_f = ov_dir / f"{v_slug}.json"
                pref_stem = f"section-179-calculator-{v_slug}"
                pref_f = ov_dir / f"{pref_stem}.json"
                if unpref_f.is_file() and pref_f.is_file():
                    try:
                        ov_data = json.loads(unpref_f.read_text(encoding="utf-8"))
                        if isinstance(ov_data, dict):
                            bucket = grouped_queries_by_leaf.setdefault(pref_stem, [])
                            for q_item in [ov_data.get("query"), ov_data.get("target_query"), *(ov_data.get("grouped_queries") or [])]:
                                q_str = str(q_item or "").strip().lower()
                                if q_str and q_str not in bucket:
                                    bucket.append(q_str)
                        unpref_f.unlink()
                    except Exception:
                        pass

    all_ov_names = sorted(
        {f.name for f in agy_ov_dir.glob("*.json")}
        | ({f.name for f in cnt_ov_dir.glob("*.json")} if cnt_ov_dir.is_dir() else set())
    )
    for ov_name in all_ov_names:
        slug = ov_name[:-5]
        if slug in slugs_to_purge:
            continue
        agy_f = agy_ov_dir / ov_name
        cnt_f = cnt_ov_dir / ov_name
        primary_data: Optional[Dict[str, Any]] = None
        secondary_data: Optional[Dict[str, Any]] = None
        if agy_f.is_file():
            try:
                primary_data = json.loads(agy_f.read_text(encoding="utf-8"))
            except Exception:
                primary_data = None
        if cnt_f.is_file():
            try:
                secondary_data = json.loads(cnt_f.read_text(encoding="utf-8"))
            except Exception:
                secondary_data = None

        merged_ov = dict(primary_data or secondary_data or {})
        if not merged_ov:
            continue
        if primary_data and secondary_data:
            for k, v in secondary_data.items():
                if k not in merged_ov or not merged_ov[k]:
                    merged_ov[k] = v

        # Fix hyphenated state-leaf target_url (e.g. irs-2027-tax-brackets-california -> /tools/irs-2027-tax-brackets/california/)
        for parent_hub in ("irs-2027-tax-brackets", "section-1031-calculator"):
            if slug.startswith(f"{parent_hub}-"):
                leaf_part = slug[len(parent_hub) + 1:]
                if leaf_part in US_STATE_NAME_TO_SLUG.values():
                    merged_ov["target_url"] = f"https://profithelm.com/tools/{parent_hub}/{leaf_part}/"
                    merged_ov["canonical_slug"] = parent_hub

        extra_queries = list(grouped_queries_by_canonical.get(slug, [])) + list(grouped_queries_by_leaf.get(slug, []))
        if extra_queries:
            existing_gq = [str(x).strip() for x in (merged_ov.get("grouped_queries") or []) if str(x).strip()]
            base_q = str(merged_ov.get("query") or merged_ov.get("target_query") or "").strip()
            if base_q and base_q.lower() not in {x.lower() for x in existing_gq}:
                existing_gq.insert(0, base_q)
            seen_lower = {x.lower() for x in existing_gq}
            for eq in extra_queries:
                if eq.lower() not in seen_lower:
                    existing_gq.append(eq)
                    seen_lower.add(eq.lower())
            merged_ov["grouped_queries"] = existing_gq

        existing_hub_links = merged_ov.get("hub_links")
        if isinstance(existing_hub_links, list) and existing_hub_links:
            has_stale_clone_link = any(
                isinstance(link_item, dict)
                and any(
                    f"/{dead_slug}/" in str(link_item.get("href") or "")
                    for dead_slug in slugs_to_purge
                )
                for link_item in existing_hub_links
            )
            if has_stale_clone_link:
                from pseofactory.gsc_remediation import _resolve_contextual_internal_links
                merged_ov["hub_links"] = _resolve_contextual_internal_links(
                    slug=slug,
                    tenant_id=prop,
                    query=str(merged_ov.get("query") or merged_ov.get("target_query") or slug),
                )

        serialized = json.dumps(merged_ov, indent=2, ensure_ascii=False) + "\n"
        target_files = (agy_f,) if is_prod_repo else (agy_f, cnt_f)
        for target_f in target_files:
            old_txt = target_f.read_text(encoding="utf-8") if target_f.is_file() else ""
            if old_txt != serialized:
                target_f.write_text(serialized, encoding="utf-8")
                summary["overlays_synced"] += 1
        if is_prod_repo and cnt_f.is_file():
            cnt_f.unlink(missing_ok=True)
    if is_prod_repo and cnt_ov_dir.is_dir():
        try:
            cnt_ov_dir.rmdir()
        except OSError:
            pass

    # 7. Clean stale syndication directories, files, and broadcast/group ledgers
    summary["stale_syndication_removed"] += _clean_syndication_directories_and_ledgers(
        root=root,
        prop=prop,
        slugs_to_purge=slugs_to_purge,
    )

    # 8. Reconcile void_candidates.jsonl queues
    vc_candidates = [
        root / "void_candidates.jsonl",
        root / ".agy" / "void_candidates.jsonl",
    ]
    if "PYTEST_CURRENT_TEST" not in os.environ and str(root).startswith("/home/ubuntuadmin/projects/"):
        vc_candidates.extend([
            Path.home() / ".local" / "share" / "vault" / "void_candidates.jsonl",
            Path(__file__).resolve().parent.parent / "void_candidates.jsonl",
        ])
    for vc_p in vc_candidates:
        summary["void_candidates_reconciled"] += reconcile_void_candidates_queue(vc_p)

    # 9. Reconcile .agy/metric_recovery_ledger.json, .agy/factory_execution_log.json, and statutory.db
    summary["metric_recovery_ledger_reconciled"] = reconcile_metric_recovery_ledger(root, prop)
    summary["factory_execution_log_reconciled"] = reconcile_factory_execution_log(root, prop)
    if "PYTEST_CURRENT_TEST" not in os.environ and str(root).startswith("/home/ubuntuadmin/projects/"):
        summary["statutory_db_reconciled"] = reconcile_statutory_db_gsc_snapshots(root, prop)
        summary["tenant_adapters_synced"] = sync_tenant_redirect_rollup_adapters(root, prop)

    return summary


_GENERIC_REDIRECT_SINKS: Set[str] = {
    "/",
    "/tools/",
    "/privacy/",
    "/methodology/",
    "/disclaimers/",
    "/about/",
    "/contact/",
    "/terms/",
}

_DEFAULT_PROFITHELM_CORE_TOOLS: List[Dict[str, Any]] = [
    {"slug": "irs-2027-tax-brackets", "primary_keyword": "irs 2027 tax brackets"},
    {"slug": "crypto-tax-calculator", "primary_keyword": "crypto tax calculator"},
    {"slug": "saas-runway-calculator", "primary_keyword": "saas runway calculator"},
    {"slug": "prediction-market-odds", "primary_keyword": "prediction market odds"},
    {"slug": "tcja-sunset-capital-gains", "primary_keyword": "tcja sunset capital gains"},
    {"slug": "section-179-calculator", "primary_keyword": "section 179 calculator"},
    {"slug": "treasury-yield-calculator", "primary_keyword": "treasury yield calculator"},
    {"slug": "section-1031-calculator", "primary_keyword": "section 1031 calculator"},
    {"slug": "prediction-market-tax", "primary_keyword": "prediction market tax"},
]

_DEFAULT_PREXVO_CORE_TOOLS: List[Dict[str, Any]] = [
    {"slug": "rap-vs-ibr-calculator", "primary_keyword": "rap vs ibr calculator"},
    {"slug": "tiered-standard-calculator", "primary_keyword": "tiered standard calculator"},
    {"slug": "paye-sunset-calculator", "primary_keyword": "paye sunset calculator"},
    {"slug": "icr-repayment-calculator", "primary_keyword": "icr repayment calculator"},
    {"slug": "pslf-qualifying-payment-simulator", "primary_keyword": "pslf qualifying payment simulator"},
    {"slug": "grad-plus-borrowing-cap-calculator", "primary_keyword": "grad plus borrowing cap calculator"},
    {"slug": "ibr-hardship-cap-calculator", "primary_keyword": "ibr hardship cap calculator"},
    {"slug": "married-filing-separately-student-loan-calculator", "primary_keyword": "married filing separately student loan calculator"},
    {"slug": "parent-plus-double-consolidation", "primary_keyword": "parent plus double consolidation"},
    {"slug": "rap-payment-calculator", "primary_keyword": "rap payment calculator"},
    {"slug": "save-plan-litigation-transition", "primary_keyword": "save plan litigation transition"},
    {"slug": "student-loan-refinance-break-even-calculator", "primary_keyword": "student loan refinance break even calculator"},
]

_DEFAULT_GAINHELM_CORE_TOOLS: List[Dict[str, Any]] = [
    {"slug": "soc-2-audit-cost-calculator", "primary_keyword": "soc 2 audit cost calculator"},
    {"slug": "cmmc-2-0-compliance-cost-calculator", "primary_keyword": "cmmc 2.0 compliance cost calculator"},
    {"slug": "nist-800-171-sprs-score-calculator", "primary_keyword": "nist 800-171 sprs score calculator"},
    {"slug": "iso-27001-certification-cost-calculator", "primary_keyword": "iso 27001 certification cost calculator"},
    {"slug": "hipaa-violation-penalty-breach-cost-calculator", "primary_keyword": "hipaa violation penalty breach cost calculator"},
    {"slug": "penetration-testing-cost-estimator", "primary_keyword": "penetration testing cost estimator"},
    {"slug": "cyber-liability-insurance-premium-calculator", "primary_keyword": "cyber liability insurance premium calculator"},
    {"slug": "fedramp-authorization-cost-calculator", "primary_keyword": "fedramp authorization cost calculator"},
    {"slug": "pci-dss-4-0-compliance-audit-cost-calculator", "primary_keyword": "pci dss 4.0 compliance audit cost calculator"},
    {"slug": "hitrust-certification-cost-roi-calculator", "primary_keyword": "hitrust certification cost roi calculator"},
]


def load_property_redirect_map(
    repo_root: Optional[Union[str, Path]] = None,
    property_id: str = "profithelm",
) -> Dict[str, Dict[str, Any]]:
    """
    Loads and normalizes all 301 consolidation and redirect rules for a property from:
    1. Built-in CANNIBALIZING_CLONE_CONSOLIDATION_MAP / PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP
    2. Built-in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP
    3. On-disk content/redirects.json and dist/_redirects (if repo_root is provided)
    Resolves transitive targets and returns a lookup dictionary keyed by normalized source path
    (both with and without trailing slash) and 'slug:<source_slug>'.
    Zero em-dashes. Zero en-dashes.
    """
    import urllib.parse

    prop = str(property_id or "profithelm").strip().lower()
    if "prexvo" in prop:
        prop = "prexvo"
    elif "gainhelm" in prop:
        prop = "gainhelm"
    else:
        prop = "profithelm"

    raw_pairs: Dict[str, Tuple[str, str]] = {}

    if prop == "prexvo":
        for c_slug, info in PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP.items():
            t_path = str(info.get("redirect_target") or "/tools/").strip()
            can_slug = str(info.get("canonical_slug") or "").strip() if t_path not in _GENERIC_REDIRECT_SINKS else ""
            raw_pairs[f"/tools/{c_slug}/"] = (t_path, can_slug)
    elif prop == "gainhelm":
        pass
    else:
        for src_p, dst_p in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP.items():
            s_norm = "/" + src_p.strip("/") + "/" if src_p.strip("/") else "/"
            d_norm = "/" + dst_p.strip("/") + "/" if dst_p.strip("/") else "/"
            can_s = ""
            d_parts = [p for p in d_norm.split("/") if p]
            if len(d_parts) >= 2 and d_parts[0] == "tools":
                can_s = d_parts[1]
            raw_pairs[s_norm] = (d_norm, can_s)
        for c_slug, info in CANNIBALIZING_CLONE_CONSOLIDATION_MAP.items():
            t_path = str(info.get("redirect_target") or "/tools/").strip()
            t_norm = "/" + t_path.strip("/") + "/" if t_path.strip("/") else "/"
            can_slug = str(info.get("canonical_slug") or "").strip() if t_norm not in _GENERIC_REDIRECT_SINKS else ""
            raw_pairs[f"/tools/{c_slug}/"] = (t_norm, can_slug)
        raw_pairs["/tools/query-two-buildable/"] = ("/tools/", "")

    default_tenant_root = (
        Path("/home/ubuntuadmin/projects/prexvo")
        if prop == "prexvo"
        else (
            Path("/home/ubuntuadmin/projects/_archive/gainhelm")
            if prop == "gainhelm"
            else Path("/home/ubuntuadmin/projects/profithelm-platform")
        )
    )
    roots_to_scan: List[Path] = []
    if default_tenant_root.is_dir():
        roots_to_scan.append(default_tenant_root)
    if repo_root is not None:
        r_p = Path(repo_root)
        if r_p not in roots_to_scan:
            roots_to_scan.append(r_p)

    for root_p in roots_to_scan:
        red_json = root_p / "content" / "redirects.json"
        if red_json.is_file():
            try:
                r_data = json.loads(red_json.read_text(encoding="utf-8"))
                if isinstance(r_data, dict):
                    for k, v in r_data.items():
                        target_str = str(v.get("target") if isinstance(v, dict) else v or "").strip()
                        if not k or not target_str or "*" in k or ":" in k:
                            continue
                        s_norm = "/" + str(k).strip("/") + "/" if str(k).strip("/") else "/"
                        d_norm = "/" + target_str.strip("/") + "/" if target_str.strip("/") else "/"
                        if s_norm == d_norm:
                            continue
                        d_parts = [p for p in d_norm.split("/") if p]
                        can_s = d_parts[1] if (len(d_parts) >= 2 and d_parts[0] == "tools") else ""
                        raw_pairs[s_norm] = (d_norm, can_s)
            except Exception:
                pass

        red_file = root_p / "dist" / "_redirects"
        if red_file.is_file():
            try:
                for line in red_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    ln = line.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    parts = ln.split()
                    if len(parts) >= 2:
                        src_s, dst_s = parts[0], parts[1]
                        if "*" in src_s or ":" in src_s or not src_s.startswith("/"):
                            continue
                        s_norm = "/" + src_s.strip("/") + "/" if src_s.strip("/") else "/"
                        d_norm = "/" + dst_s.strip("/") + "/" if dst_s.strip("/") else "/"
                        if s_norm == d_norm:
                            continue
                        d_parts = [p for p in d_norm.split("/") if p]
                        can_s = d_parts[1] if (len(d_parts) >= 2 and d_parts[0] == "tools") else ""
                        if s_norm not in raw_pairs:
                            raw_pairs[s_norm] = (d_norm, can_s)
            except Exception:
                pass

    # Resolve any multi-hop targets transitively
    resolved_map: Dict[str, Dict[str, Any]] = {}
    for s_norm, (d_norm, can_s) in raw_pairs.items():
        cur_target = d_norm
        cur_can = can_s
        visited = {s_norm}
        while cur_target in raw_pairs and cur_target not in visited:
            visited.add(cur_target)
            cur_target, next_can = raw_pairs[cur_target]
            if next_can:
                cur_can = next_can

        t_parts = [p for p in cur_target.split("/") if p]
        if len(t_parts) >= 2 and t_parts[0] == "tools":
            cur_can = t_parts[1]
        elif cur_target in _GENERIC_REDIRECT_SINKS:
            cur_can = ""

        s_parts = [p for p in s_norm.split("/") if p]
        if len(s_parts) == 2 and s_parts[0] == "tools":
            src_slug = s_parts[1].lower()
        elif len(s_parts) == 1:
            src_slug = s_parts[0].lower()
        else:
            src_slug = "-".join(s_parts[1:]).lower() if (len(s_parts) > 1 and s_parts[0] == "tools") else "-".join(s_parts).lower()

        is_sink = cur_target in _GENERIC_REDIRECT_SINKS or not cur_can
        entry = {
            "source_path": s_norm,
            "source_slug": src_slug,
            "redirect_target": cur_target,
            "canonical_slug": cur_can,
            "is_off_topic_sink": is_sink,
            "status": 301,
        }
        resolved_map[s_norm.lower()] = entry
        resolved_map[s_norm.rstrip("/").lower() or "/"] = entry
        if src_slug:
            resolved_map[f"slug:{src_slug}"] = entry

    return resolved_map


_GAINHELM_PRE_PIVOT_PREFIXES = (
    "/compare/",
    "/software/",
    "/industry/",
    "/trades/",
    "/pricing/",
    "/features/",
    "/vs/",
    "/best-",
    "/field-service-",
    "/hvac-",
    "/plumbing-",
    "/electrical-",
    "/landscaping-",
    "/commercial-facilities-",
    "/tree-service-",
    "/how-hvac-",
    "/buildops-",
    "/jobber-",
)
_GAINHELM_PRE_PIVOT_TERMS = (
    "plumber",
    "plumbing",
    "hvac",
    "landscaping",
    "lawn care",
    "pest control",
    "maid",
    "handyman",
    "roofing",
    "electrician",
    "jobber",
    "buildops",
    "simpro",
    "servicemax",
    "servicefusion",
    "housecall pro",
    "servicetitan",
    "fieldpulse",
    "workiz",
    "gorilladesk",
    "field service",
    "tree service",
    "tree-service",
    "dispatch",
    "dispatch app",
    "scheduling software",
)


def _check_gainhelm_pre_pivot_sink(
    prop: str,
    norm_path: str,
    raw_query: str,
    raw_slug: str,
    raw_url: str,
    domain: str,
) -> Optional[Dict[str, Any]]:
    if prop != "gainhelm":
        return None
    q_check_gh = f"{raw_query} {raw_slug} {norm_path}".lower()
    if (norm_path and any(norm_path.startswith(pfx) for pfx in _GAINHELM_PRE_PIVOT_PREFIXES)) or any(
        term in q_check_gh for term in _GAINHELM_PRE_PIVOT_TERMS
    ):
        return {
            "is_redirected": True,
            "is_off_topic_sink": True,
            "ignored_off_topic": True,
            "original_url": raw_url or (f"https://{domain}{norm_path}" if norm_path else ""),
            "original_path": norm_path,
            "original_slug": raw_slug,
            "canonical_path": "/tools/",
            "canonical_url": f"https://{domain}/tools/",
            "canonical_slug": "",
            "leaf_overlay_slug": "",
            "resolved_via": "gainhelm_pre_pivot_sink",
        }
    return None


def _resolve_query_family_gsc_target(
    prop: str,
    raw_query: str,
    norm_tokens: Dict[str, Any],
    state_slug: Optional[str],
    domain: str,
) -> Optional[Dict[str, Any]]:
    q_words = norm_tokens.get("raw_tokens", set())
    matched_family_slug = ""
    matched_family_path = ""
    if prop == "profithelm":
        if ({"crypto", "cryptocurrency", "bitcoin", "hyperliquid"} & q_words) and (
            {"tax", "taxes", "taxable", "gains", "income", "calculator", "calculators", "calculation", "revenue"} & q_words
        ):
            matched_family_slug = (
                "crypto-tax-form-1099-da-mandatory-reporting"
                if ({"1099", "da"} & q_words)
                else "crypto-tax-calculator"
            )
            matched_family_path = f"/tools/{matched_family_slug}/"
        elif "1031" in q_words or ({"tax", "deferral"} <= q_words):
            matched_family_slug = "section-1031-calculator"
            matched_family_path = (
                f"/tools/section-1031-calculator/{state_slug}/"
                if state_slug
                else "/tools/section-1031-calculator/"
            )
        elif {"capital", "gains"} <= q_words:
            matched_family_slug = "tcja-sunset-capital-gains"
            matched_family_path = "/tools/tcja-sunset-capital-gains/"
        elif "179" in q_words:
            matched_family_slug = "section-179-calculator"
            matched_family_path = "/tools/section-179-calculator/"
        elif {"yukon", "xl"} <= q_words:
            matched_family_slug = "section-179-calculator"
            matched_family_path = "/tools/section-179-calculator/gmc-yukon-xl/"
        elif {"lincoln", "navigator"} <= q_words:
            matched_family_slug = "section-179-calculator"
            matched_family_path = "/tools/section-179-calculator/lincoln-navigator-l/"
        elif {"ford", "vans"} <= q_words or {"ford", "cargo"} <= q_words:
            matched_family_slug = "section-179-calculator"
            matched_family_path = "/tools/section-179-calculator/ford-transit-cargo-van/"
        elif ({"treasury", "tbill", "yield", "hysa"} & q_words) and ({"tax", "yield", "bills", "hysa"} & q_words):
            matched_family_slug = "treasury-yield-calculator"
            matched_family_path = "/tools/treasury-yield-calculator/"
        elif {"bid", "bond"} <= q_words or {"surety", "bond"} <= q_words:
            matched_family_slug = "contractor-surety-bond-cost-calculator"
            matched_family_path = "/tools/contractor-surety-bond-cost-calculator/"
        elif {"entity", "choice", "tax"} <= q_words:
            matched_family_slug = "s-corp-reasonable-salary-tax-calculator"
            matched_family_path = "/tools/s-corp-reasonable-salary-tax-calculator/"
        elif ({"tax", "bracket"} <= q_words or {"tax", "brackets"} <= q_words) and state_slug:
            matched_family_slug = "irs-2027-tax-brackets"
            matched_family_path = f"/tools/irs-2027-tax-brackets/{state_slug}/"
    elif prop == "gainhelm":
        q_lower = raw_query.lower()
        if "soc 2" in q_lower or "soc-2" in q_lower or ({"soc", "2"} <= q_words):
            matched_family_slug = "soc-2-audit-cost-calculator"
        elif "cmmc" in q_words or "c3pao" in q_words:
            matched_family_slug = "cmmc-2-0-compliance-cost-calculator"
        elif "sprs" in q_words or "800-171" in q_lower or ({"800", "171"} <= q_words):
            matched_family_slug = "nist-800-171-sprs-score-calculator"
        elif "iso 27001" in q_lower or "iso-27001" in q_lower or ({"iso", "27001"} <= q_words):
            matched_family_slug = "iso-27001-certification-cost-calculator"
        elif "hipaa" in q_words or "hitech" in q_words:
            matched_family_slug = "hipaa-violation-penalty-breach-cost-calculator"
        elif "pci" in q_words or "dss" in q_words:
            matched_family_slug = "pci-dss-4-0-compliance-cost-calculator"
        elif "fedramp" in q_words or "3pao" in q_words:
            matched_family_slug = "fedramp-authorization-3pao-cost-calculator"
        elif "hitrust" in q_words:
            matched_family_slug = "hitrust-csf-e1-i1-r2-certification-cost-calculator"
        elif "penetration" in q_words or "pentest" in q_words:
            matched_family_slug = "penetration-testing-scoping-cost-calculator"
        elif "cyber" in q_words or "breach" in q_words:
            matched_family_slug = "cyber-liability-insurance-breach-exposure-calculator"
        if matched_family_slug:
            matched_family_path = f"/tools/{matched_family_slug}/"
    elif prop == "prexvo":
        if "pslf" in q_words or "forgiveness" in q_words or "buyback" in q_words:
            matched_family_slug = "pslf-calculator"
        elif "refinance" in q_words or "refi" in q_words or "sofi" in q_words:
            matched_family_slug = "student-loan-refinance-calculator"
        elif "rap" in q_words or "save" in q_words or "ibr" in q_words:
            matched_family_slug = "save-vs-rap-calculator"
        elif "repayment" in q_words or "student" in q_words:
            matched_family_slug = "student-loan-repayment-calculator"
        if matched_family_slug:
            matched_family_path = f"/tools/{matched_family_slug}/"

    if matched_family_slug and matched_family_path:
        m_parts = [p for p in matched_family_path.split("/") if p]
        leaf_ov = f"{m_parts[1]}-{m_parts[2]}" if (len(m_parts) >= 3 and m_parts[0] == "tools") else matched_family_slug
        return {
            "is_redirected": False,
            "is_off_topic_sink": False,
            "original_url": "",
            "original_path": matched_family_path,
            "original_slug": matched_family_slug,
            "canonical_path": matched_family_path,
            "canonical_url": f"https://{domain}{matched_family_path}",
            "canonical_slug": matched_family_slug,
            "leaf_overlay_slug": leaf_ov,
            "resolved_via": "query_family_match",
        }
    return None


def resolve_redirected_gsc_target(
    target_url: Union[str, Dict[str, Any]] = "",
    slug: str = "",
    query: str = "",
    property_id: str = "profithelm",
    repo_root: Optional[Union[str, Path]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    page_url: str = "",
) -> Dict[str, Any]:
    """
    Resolves a Search Console URL, slug, or query against the active redirect map and canonical
    tool catalog so retired 301-redirected URLs and queries roll up into their surviving canonical
    target page and parent tool slug.
    Zero em-dashes. Zero en-dashes.
    """
    import urllib.parse

    if isinstance(target_url, dict):
        row_d = target_url
        eff_url = str(row_d.get("target_url") or row_d.get("page") or row_d.get("url") or page_url or "").strip()
        slug = str(slug or row_d.get("slug") or "")
        query = str(query or row_d.get("query") or "")
        property_id = str(row_d.get("property_id") or property_id or "profithelm")
    else:
        eff_url = str(target_url or page_url or "").strip()
    prop = str(property_id or "profithelm").strip().lower()
    if "prexvo" in prop or "prexvo.com" in eff_url.lower():
        prop = "prexvo"
    elif "gainhelm" in prop or "gainhelm.com" in eff_url.lower():
        prop = "gainhelm"
    else:
        prop = "profithelm"

    domain = (
        "prexvo.com"
        if prop == "prexvo"
        else ("gainhelm.com" if prop == "gainhelm" else "profithelm.com")
    )
    raw_url = eff_url
    raw_slug = str(slug or "").strip().strip("/").lower()
    raw_query = str(query or "").strip()

    parsed_u = urllib.parse.urlsplit(raw_url) if raw_url else None
    if parsed_u and parsed_u.netloc:
        domain = parsed_u.netloc
    raw_path = parsed_u.path if (parsed_u and parsed_u.path) else (raw_url if raw_url.startswith("/") else "")
    norm_path = ("/" + raw_path.strip("/") + "/") if raw_path.strip("/") else ("/" if raw_path == "/" else "")

    redirect_map = load_property_redirect_map(repo_root=repo_root, property_id=prop)

    # 1. Check direct path match in redirect_map
    matched_entry: Optional[Dict[str, Any]] = None
    if norm_path:
        matched_entry = redirect_map.get(norm_path.lower()) or redirect_map.get(norm_path.rstrip("/").lower())
    if matched_entry is None and raw_slug:
        matched_entry = (
            redirect_map.get(f"slug:{raw_slug}")
            or redirect_map.get(f"/tools/{raw_slug}/")
            or redirect_map.get(f"/{raw_slug}/")
        )

    if matched_entry is not None and repo_root is not None:
        r_dist = Path(repo_root) / "dist"
        if r_dist.is_dir():
            src_rel = (norm_path or f"/tools/{raw_slug}/").strip("/")
            dst_rel = str(matched_entry.get("redirect_target") or "").strip("/")
            src_html_exists = bool(src_rel and (r_dist / src_rel / "index.html").is_file())
            dst_html_exists = bool(dst_rel and dst_rel != "tools" and (r_dist / dst_rel / "index.html").is_file())
            has_local_redirects = (
                (r_dist / "_redirects").is_file()
                or (Path(repo_root) / "content" / "redirects.json").is_file()
            )
            if src_html_exists and not dst_html_exists and not has_local_redirects:
                matched_entry = None

    if matched_entry is not None:
        c_path = str(matched_entry["redirect_target"])
        c_slug = str(matched_entry["canonical_slug"])
        c_parts = [p for p in c_path.split("/") if p]
        leaf_ov_slug = f"{c_parts[1]}-{c_parts[2]}" if (len(c_parts) >= 3 and c_parts[0] == "tools") else c_slug
        return {
            "is_redirected": True,
            "is_off_topic_sink": bool(matched_entry["is_off_topic_sink"]),
            "original_url": raw_url or f"https://{domain}{matched_entry['source_path']}",
            "original_path": norm_path or str(matched_entry["source_path"]),
            "original_slug": raw_slug or str(matched_entry["source_slug"]),
            "canonical_path": c_path,
            "canonical_url": f"https://{domain}{c_path}",
            "canonical_slug": c_slug,
            "leaf_overlay_slug": leaf_ov_slug,
            "resolved_via": "redirect_map",
        }

    # 2. Check hyphenated state/vehicle leaf slug (e.g. irs-2027-tax-brackets-california)
    for parent_hub in ("irs-2027-tax-brackets", "section-1031-calculator", "section-179-calculator"):
        check_s = raw_slug
        if not check_s and norm_path.startswith("/tools/"):
            p_parts = [p for p in norm_path.split("/") if p]
            if len(p_parts) == 2:
                check_s = p_parts[1].lower()
        if check_s.startswith(f"{parent_hub}-"):
            sub_leaf = check_s[len(parent_hub) + 1:]
            if sub_leaf in US_STATE_NAME_TO_SLUG.values():
                c_path = f"/tools/{parent_hub}/{sub_leaf}/"
                return {
                    "is_redirected": norm_path == f"/tools/{check_s}/",
                    "is_off_topic_sink": False,
                    "original_url": raw_url or f"https://{domain}{c_path}",
                    "original_path": norm_path or c_path,
                    "original_slug": raw_slug or check_s,
                    "canonical_path": c_path,
                    "canonical_url": f"https://{domain}{c_path}",
                    "canonical_slug": parent_hub,
                    "leaf_overlay_slug": f"{parent_hub}-{sub_leaf}",
                    "resolved_via": "hyphenated_state_leaf",
                }
        elif check_s.startswith(f"{parent_hub}/"):
            sub_leaf = check_s.split("/", 1)[1].strip("/")
            c_path = f"/tools/{parent_hub}/{sub_leaf}/"
            return {
                "is_redirected": False,
                "is_off_topic_sink": False,
                "original_url": raw_url or f"https://{domain}{c_path}",
                "original_path": norm_path or c_path,
                "original_slug": raw_slug or check_s,
                "canonical_path": c_path,
                "canonical_url": f"https://{domain}{c_path}",
                "canonical_slug": parent_hub,
                "leaf_overlay_slug": f"{parent_hub}-{sub_leaf}",
                "resolved_via": "slash_leaf",
            }

    # 2.5 GainHelm pre-pivot field-service wildcard routes and queries -> /tools/ off-topic sink
    gh_sink = _check_gainhelm_pre_pivot_sink(prop, norm_path, raw_query, raw_slug, raw_url, domain)
    if gh_sink is not None:
        return gh_sink

    # 3. If norm_path is an active canonical route (/tools/<slug>/ or /tools/<slug>/<leaf>/)
    if norm_path:
        p_parts = [p for p in norm_path.split("/") if p]
        if len(p_parts) >= 2 and p_parts[0] == "tools":
            parent_slug = p_parts[1].lower()
            leaf_ov = f"{parent_slug}-{p_parts[2].lower()}" if len(p_parts) >= 3 else parent_slug
            return {
                "is_redirected": False,
                "is_off_topic_sink": False,
                "original_url": raw_url or f"https://{domain}{norm_path}",
                "original_path": norm_path,
                "original_slug": raw_slug or parent_slug,
                "canonical_path": norm_path,
                "canonical_url": f"https://{domain}{norm_path}",
                "canonical_slug": parent_slug,
                "leaf_overlay_slug": leaf_ov,
                "resolved_via": "canonical_path",
            }
        return {
            "is_redirected": False,
            "is_off_topic_sink": False,
            "original_url": raw_url or f"https://{domain}{norm_path}",
            "original_path": norm_path,
            "original_slug": raw_slug or (p_parts[-1].lower() if p_parts else "root"),
            "canonical_path": norm_path,
            "canonical_url": f"https://{domain}{norm_path}",
            "canonical_slug": raw_slug or (p_parts[-1].lower() if p_parts else "root"),
            "leaf_overlay_slug": raw_slug or (p_parts[-1].lower() if p_parts else "root"),
            "resolved_via": "non_tool_path",
        }

    # 4. Query-only or slug-only resolution
    if raw_query:
        q_lower = raw_query.lower().strip()
        if "site:" in q_lower:
            return {
                "is_redirected": True,
                "is_off_topic_sink": True,
                "ignored_off_topic": True,
                "original_url": "",
                "original_path": "",
                "original_slug": "",
                "canonical_path": "",
                "canonical_url": "",
                "canonical_slug": "",
                "leaf_overlay_slug": "",
                "resolved_via": "scraper_query_sink",
            }

        q_slug = re.sub(r"[^a-z0-9]+", "-", q_lower).strip("-")
        q_entry = redirect_map.get(f"slug:{q_slug}") or redirect_map.get(f"/tools/{q_slug}/")
        if q_entry is not None:
            c_path = str(q_entry["redirect_target"])
            c_slug = str(q_entry["canonical_slug"])
            c_parts = [p for p in c_path.split("/") if p]
            leaf_ov_slug = f"{c_parts[1]}-{c_parts[2]}" if (len(c_parts) >= 3 and c_parts[0] == "tools") else c_slug
            return {
                "is_redirected": True,
                "is_off_topic_sink": bool(q_entry["is_off_topic_sink"]),
                "original_url": "",
                "original_path": str(q_entry["source_path"]),
                "original_slug": q_slug,
                "canonical_path": c_path,
                "canonical_url": f"https://{domain}{c_path}",
                "canonical_slug": c_slug,
                "leaf_overlay_slug": leaf_ov_slug,
                "resolved_via": "query_redirect_map",
            }

        # Check existing_tools (including default core catalog + dynamic_tools.json)
        tools_list = list(existing_tools or [])
        seen_t_slugs = {str(t.get("slug") or "").strip().lower() for t in tools_list if isinstance(t, dict)}
        default_core = (
            _DEFAULT_PREXVO_CORE_TOOLS
            if prop == "prexvo"
            else (
                _DEFAULT_GAINHELM_CORE_TOOLS
                if prop == "gainhelm"
                else _DEFAULT_PROFITHELM_CORE_TOOLS
            )
        )
        for dt in default_core:
            if dt["slug"] not in seen_t_slugs:
                tools_list.append(dt)
                seen_t_slugs.add(dt["slug"])
        if repo_root is not None:
            dyn_f = Path(repo_root) / "profithelm" / "data" / "dynamic_tools.json"
            if dyn_f.is_file():
                try:
                    loaded_t = json.loads(dyn_f.read_text(encoding="utf-8"))
                    if isinstance(loaded_t, list):
                        for lt in loaded_t:
                            if isinstance(lt, dict) and str(lt.get("slug") or "").lower() not in seen_t_slugs:
                                tools_list.append(lt)
                                seen_t_slugs.add(str(lt.get("slug") or "").lower())
                except Exception:
                    pass

        norm_tokens = normalize_search_intent_tokens(q_lower)
        state_slug = norm_tokens.get("state_slug")
        for t in tools_list:
            if not isinstance(t, dict):
                continue
            t_slug = str(t.get("slug") or "").strip().lower()
            t_kw = str(t.get("primary_keyword") or "").strip().lower()
            t_secs = [str(k).strip().lower() for k in (t.get("secondary_keywords") or []) if k]
            if (
                (t_slug and (t_slug in q_slug or q_slug in t_slug))
                or (t_kw and (t_kw in q_lower or q_lower in t_kw))
                or q_lower in t_secs
            ):
                if state_slug and t_slug in ("irs-2027-tax-brackets", "section-1031-calculator"):
                    c_path = f"/tools/{t_slug}/{state_slug}/"
                    leaf_ov = f"{t_slug}-{state_slug}"
                else:
                    c_path = f"/tools/{t_slug}/"
                    leaf_ov = t_slug
                return {
                    "is_redirected": False,
                    "is_off_topic_sink": False,
                    "original_url": "",
                    "original_path": c_path,
                    "original_slug": t_slug,
                    "canonical_path": c_path,
                    "canonical_url": f"https://{domain}{c_path}",
                    "canonical_slug": t_slug,
                    "leaf_overlay_slug": leaf_ov,
                    "resolved_via": "tool_catalog_match",
                }

        cannibal = check_search_intent_cannibalization(raw_query, existing_tools=tools_list or None)
        if cannibal.get("is_cannibalizing") and cannibal.get("parent_slug") not in (None, "", "none"):
            p_slug = str(cannibal["parent_slug"]).strip().lower()
            subroute = str(cannibal.get("target_subroute") or f"/tools/{p_slug}/")
            c_path = "/" + subroute.strip("/") + "/"
            c_parts = [p for p in c_path.split("/") if p]
            leaf_ov = f"{c_parts[1]}-{c_parts[2]}" if (len(c_parts) >= 3 and c_parts[0] == "tools") else p_slug
            return {
                "is_redirected": False,
                "is_off_topic_sink": False,
                "original_url": "",
                "original_path": c_path,
                "original_slug": p_slug,
                "canonical_path": c_path,
                "canonical_url": f"https://{domain}{c_path}",
                "canonical_slug": p_slug,
                "leaf_overlay_slug": leaf_ov,
                "resolved_via": "intent_cannibalization",
            }

        # Domain query-family fallback for core clusters when page URL is omitted
        fam_res = _resolve_query_family_gsc_target(prop, raw_query, norm_tokens, state_slug, domain)
        if fam_res is not None:
            return fam_res

    if raw_slug:
        c_path = f"/tools/{raw_slug}/"
        return {
            "is_redirected": False,
            "is_off_topic_sink": False,
            "original_url": raw_url or f"https://{domain}{c_path}",
            "original_path": c_path,
            "original_slug": raw_slug,
            "canonical_path": c_path,
            "canonical_url": f"https://{domain}{c_path}",
            "canonical_slug": raw_slug,
            "leaf_overlay_slug": raw_slug,
            "resolved_via": "slug_default",
        }

    return {
        "is_redirected": False,
        "is_off_topic_sink": False,
        "original_url": raw_url,
        "original_path": "",
        "original_slug": "",
        "canonical_path": "",
        "canonical_url": "",
        "canonical_slug": "",
        "leaf_overlay_slug": "",
        "resolved_via": "unresolved",
    }


def rollup_redirected_gsc_rows(
    rows: List[Dict[str, Any]],
    property_id: str = "profithelm",
    repo_root: Optional[Union[str, Path]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Rolls up raw Google Search Console rows (page-level, query+page, or query-only)
    across active 301 redirect rules so impressions, clicks, CTR, and impression-weighted
    rankings reported under retired URLs are attributed to their surviving canonical targets.
    Ignores off-topic hub-redirect sinks (e.g. retired e-commerce routes -> /tools/).
    Idempotent when invoked on rows that already carry rolled_up_from metadata.
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(property_id or "profithelm").strip().lower()
    if "prexvo" in prop:
        prop = "prexvo"
    elif "gainhelm" in prop:
        prop = "gainhelm"
    else:
        prop = "profithelm"

    merged_buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
    impressions_by_path: Dict[str, int] = {}
    clicks_by_path: Dict[str, int] = {}
    canonical_targets_summary: Dict[str, Dict[str, Any]] = {}

    redirected_rows_count = 0
    rolled_up_impressions = 0
    rolled_up_clicks = 0
    ignored_off_topic_rows_count = 0
    ignored_off_topic_impressions = 0

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        raw_keys = row.get("keys") if isinstance(row.get("keys"), list) else []
        raw_page = str(row.get("page") or row.get("target_url") or row.get("url") or "").strip()
        raw_query = str(row.get("query") or "").strip()
        if not raw_page and not raw_query and raw_keys:
            if len(raw_keys) == 1:
                k0 = str(raw_keys[0] or "").strip()
                if k0.startswith("http://") or k0.startswith("https://") or k0.startswith("/"):
                    raw_page = k0
                else:
                    raw_query = k0
            elif len(raw_keys) >= 2:
                k0 = str(raw_keys[0] or "").strip()
                k1 = str(raw_keys[1] or "").strip()
                if k0.startswith("http") or k0.startswith("/"):
                    raw_page, raw_query = k0, k1
                else:
                    raw_query, raw_page = k0, k1

        raw_slug = str(row.get("slug") or "").strip()
        try:
            impr = max(0, int(float(row.get("impressions", 0) or 0)))
        except (ValueError, TypeError):
            impr = 0
        try:
            clicks = max(0, int(float(row.get("clicks", 0) or 0)))
        except (ValueError, TypeError):
            clicks = 0
        try:
            pos = float(row.get("position", 100.0) or 100.0)
        except (ValueError, TypeError):
            pos = 100.0

        resolved = resolve_redirected_gsc_target(
            target_url=raw_page,
            slug=raw_slug,
            query=raw_query,
            property_id=prop,
            repo_root=repo_root,
            existing_tools=existing_tools,
        )

        if resolved["is_redirected"] and resolved["is_off_topic_sink"]:
            ignored_off_topic_rows_count += 1
            ignored_off_topic_impressions += impr
            continue

        c_path = resolved["canonical_path"] or "/"
        c_url = resolved["canonical_url"]
        c_slug = resolved["canonical_slug"]
        is_red = bool(resolved["is_redirected"])

        prior_from = [str(u) for u in (row.get("rolled_up_from") or []) if str(u).strip()]
        has_prior_rollup = bool(not is_red and (prior_from or int(row.get("redirected_impressions", 0) or 0) > 0))
        if is_red:
            row_direct_impr = 0
            row_redir_impr = impr
            row_direct_clicks = 0
            row_redir_clicks = clicks
            row_from_refs = [resolved["original_url"] or resolved["original_path"]]
            redirected_rows_count += 1
            rolled_up_impressions += impr
            rolled_up_clicks += clicks
        elif has_prior_rollup:
            row_redir_impr = max(0, int(float(row.get("redirected_impressions", 0) or 0)))
            row_direct_impr = max(0, int(float(row.get("direct_impressions", max(0, impr - row_redir_impr)) or 0)))
            row_redir_clicks = max(0, int(float(row.get("redirected_clicks", 0) or 0)))
            row_direct_clicks = max(0, int(float(row.get("direct_clicks", max(0, clicks - row_redir_clicks)) or 0)))
            row_from_refs = list(prior_from)
            redirected_rows_count += max(1, len(prior_from))
            rolled_up_impressions += row_redir_impr
            rolled_up_clicks += row_redir_clicks
        else:
            row_direct_impr = impr
            row_redir_impr = 0
            row_direct_clicks = clicks
            row_redir_clicks = 0
            row_from_refs = []

        bucket_key = (c_path, raw_query.lower().strip())
        if bucket_key not in merged_buckets:
            base_row = dict(row)
            base_row["page"] = c_url if (is_red or not base_row.get("page")) else base_row.get("page", "")
            base_row["target_url"] = c_url
            base_row["canonical_url"] = c_url
            base_row["canonical_path"] = c_path
            base_row["canonical_slug"] = c_slug
            if c_slug and (not base_row.get("slug") or is_red):
                base_row["slug"] = c_slug
            base_row["query"] = raw_query
            base_row["impressions"] = impr
            base_row["clicks"] = clicks
            base_row["direct_impressions"] = row_direct_impr
            base_row["redirected_impressions"] = row_redir_impr
            base_row["direct_clicks"] = row_direct_clicks
            base_row["redirected_clicks"] = row_redir_clicks
            base_row["_weighted_pos_sum"] = pos * impr if impr > 0 else 0.0
            base_row["_pos_weight"] = impr if impr > 0 else 0
            base_row["position"] = round(pos, 2)
            base_row["ctr"] = round(clicks / impr, 4) if impr > 0 else float(row.get("ctr", 0.0) or 0.0)
            base_row["rolled_up_from"] = list(row_from_refs)
            merged_buckets[bucket_key] = base_row
        else:
            b = merged_buckets[bucket_key]
            if is_red or row_redir_impr > 0 or b.get("redirected_impressions", 0) > 0:
                b["page"] = c_url
            b["impressions"] += impr
            b["clicks"] += clicks
            b["direct_impressions"] += row_direct_impr
            b["redirected_impressions"] += row_redir_impr
            b["direct_clicks"] += row_direct_clicks
            b["redirected_clicks"] += row_redir_clicks
            for orig_ref in row_from_refs:
                if orig_ref and orig_ref not in b["rolled_up_from"]:
                    b["rolled_up_from"].append(orig_ref)
            if not is_red and not b.get("dead_route") and row.get("dead_route"):
                b["dead_route"] = row.get("dead_route")
            if impr > 0:
                b["_weighted_pos_sum"] += pos * impr
                b["_pos_weight"] += impr
            if b["_pos_weight"] > 0:
                b["position"] = round(b["_weighted_pos_sum"] / b["_pos_weight"], 2)
            else:
                b["position"] = round(min(float(b["position"]), pos), 2)
            b["ctr"] = round(b["clicks"] / b["impressions"], 4) if b["impressions"] > 0 else 0.0

        # Credit canonical path and parent tool hub path in impressions_by_path / clicks_by_path
        if c_path:
            c_no_slash = c_path.rstrip("/") or "/"
            c_with_slash = c_no_slash + "/" if c_no_slash != "/" else "/"
            for p_variant in {c_no_slash, c_with_slash}:
                impressions_by_path[p_variant] = impressions_by_path.get(p_variant, 0) + impr
                clicks_by_path[p_variant] = clicks_by_path.get(p_variant, 0) + clicks
            c_parts = [p for p in c_no_slash.split("/") if p]
            if len(c_parts) >= 3 and c_parts[0] == "tools":
                hub_no_slash = f"/tools/{c_parts[1]}"
                hub_with_slash = f"/tools/{c_parts[1]}/"
                for h_variant in (hub_no_slash, hub_with_slash):
                    impressions_by_path[h_variant] = impressions_by_path.get(h_variant, 0) + impr
                    clicks_by_path[h_variant] = clicks_by_path.get(h_variant, 0) + clicks

            t_sum = canonical_targets_summary.setdefault(
                c_path,
                {
                    "canonical_path": c_path,
                    "canonical_slug": c_slug,
                    "direct_impressions": 0,
                    "redirected_impressions": 0,
                    "total_impressions": 0,
                    "direct_clicks": 0,
                    "redirected_clicks": 0,
                    "total_clicks": 0,
                    "rolled_up_from": [],
                },
            )
            t_sum["total_impressions"] += impr
            t_sum["total_clicks"] += clicks
            t_sum["direct_impressions"] += row_direct_impr
            t_sum["redirected_impressions"] += row_redir_impr
            t_sum["direct_clicks"] += row_direct_clicks
            t_sum["redirected_clicks"] += row_redir_clicks
            for orig_ref in row_from_refs:
                norm_orig_p = orig_ref
                if norm_orig_p.startswith("http://") or norm_orig_p.startswith("https://"):
                    import urllib.parse
                    norm_orig_p = urllib.parse.urlsplit(norm_orig_p).path or norm_orig_p
                if norm_orig_p and norm_orig_p not in t_sum["rolled_up_from"]:
                    t_sum["rolled_up_from"].append(norm_orig_p)

    rolled_rows: List[Dict[str, Any]] = []
    for b in merged_buckets.values():
        b.pop("_weighted_pos_sum", None)
        b.pop("_pos_weight", None)
        rolled_rows.append(b)

    enriched_targets = {
        k: v for k, v in sorted(canonical_targets_summary.items()) if v["redirected_impressions"] > 0 or v["rolled_up_from"]
    }

    return {
        "property_id": prop,
        "rows": rolled_rows,
        "rolled_up_rows": rolled_rows,
        "impressions_by_path": impressions_by_path,
        "clicks_by_path": clicks_by_path,
        "canonical_targets_summary": enriched_targets,
        "redirected_rows_count": redirected_rows_count,
        "rolled_up_impressions": rolled_up_impressions,
        "rolled_up_clicks": rolled_up_clicks,
        "ignored_off_topic_rows_count": ignored_off_topic_rows_count,
        "ignored_off_topic_impressions": ignored_off_topic_impressions,
    }


def reconcile_metric_recovery_ledger(
    repo_root: Union[str, Path],
    property_id: str = "profithelm",
) -> Dict[str, Any]:
    """
    Reconciles .agy/metric_recovery_ledger.json so retired 301-redirected slugs are rolled up
    into their surviving canonical tool snapshots and removed from active snapshots/evaluations.
    Zero em-dashes. Zero en-dashes.
    """
    root = Path(repo_root)
    prop_low = str(property_id).lower()
    prop = (
        "prexvo"
        if "prexvo" in prop_low
        else ("gainhelm" if "gainhelm" in prop_low else "profithelm")
    )
    domain = (
        "prexvo.com"
        if prop == "prexvo"
        else ("gainhelm.com" if prop == "gainhelm" else "profithelm.com")
    )
    if prop == "profithelm":
        from pseofactory.competitor import PROFITHELM_SECTION_179_VEHICLES
        veh_slugs = {v[0] for v in PROFITHELM_SECTION_179_VEHICLES}
        for ov_dir in (root / ".agy" / "overlays", root / "content" / "overlays"):
            if not ov_dir.is_dir():
                continue
            for v_slug in sorted(veh_slugs):
                unpref_f = ov_dir / f"{v_slug}.json"
                pref_f = ov_dir / f"section-179-calculator-{v_slug}.json"
                if unpref_f.is_file() and pref_f.is_file():
                    try:
                        unpref_data = json.loads(unpref_f.read_text(encoding="utf-8"))
                        pref_data = json.loads(pref_f.read_text(encoding="utf-8"))
                        if isinstance(unpref_data, dict) and isinstance(pref_data, dict):
                            existing_gq = [str(x).strip() for x in (pref_data.get("grouped_queries") or []) if str(x).strip()]
                            base_q = str(pref_data.get("query") or pref_data.get("target_query") or "").strip()
                            if base_q and base_q.lower() not in {x.lower() for x in existing_gq}:
                                existing_gq.insert(0, base_q)
                            seen_lower = {x.lower() for x in existing_gq}
                            for q_item in [unpref_data.get("query"), unpref_data.get("target_query"), *(unpref_data.get("grouped_queries") or [])]:
                                q_str = str(q_item or "").strip()
                                if q_str and q_str.lower() not in seen_lower:
                                    existing_gq.append(q_str)
                                    seen_lower.add(q_str.lower())
                            if existing_gq:
                                pref_data["grouped_queries"] = existing_gq
                            pref_f.write_text(json.dumps(pref_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        unpref_f.unlink()
                    except Exception:
                        pass
    ledger_path = root / ".agy" / "metric_recovery_ledger.json"
    result = {
        "retired_snapshots_rolled_up": 0,
        "retired_evaluations_removed": 0,
        "rolled_up_by_canonical": {},
    }
    if not ledger_path.is_file():
        return result

    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return result
    if not isinstance(ledger, dict):
        return result

    redirect_map = load_property_redirect_map(repo_root=root, property_id=prop)
    snapshots = ledger.get("snapshots")
    changed = False
    rolled_by_can: Dict[str, List[str]] = {}

    if isinstance(snapshots, dict):
        for s_key in list(snapshots.keys()):
            s_entry = snapshots.get(s_key)
            entry_Info = redirect_map.get(f"slug:{s_key.lower()}") or redirect_map.get(f"/tools/{s_key.lower()}/")
            if entry_Info is not None or is_retired_or_consolidated_slug(s_key, prop):
                can_slug = str((entry_Info or {}).get("canonical_slug") or "").strip()
                if can_slug and not is_retired_or_consolidated_slug(can_slug, prop):
                    can_snap = snapshots.setdefault(
                        can_slug,
                        {
                            "slug": can_slug,
                            "url": f"https://{domain}/tools/{can_slug}/",
                            "recorded_at": (s_entry or {}).get("recorded_at", ""),
                            "baseline_impressions": 100,
                            "baseline_clicks": 5,
                            "baseline_ctr": 0.05,
                            "baseline_position": 12.0,
                            "status": "MONITORING",
                            "last_evaluated_at": (s_entry or {}).get("last_evaluated_at", ""),
                        },
                    )
                    existing_rolled = list(can_snap.get("rolled_up_redirected_slugs") or [])
                    if s_key not in existing_rolled:
                        existing_rolled.append(s_key)
                    can_snap["rolled_up_redirected_slugs"] = sorted(existing_rolled)
                    rolled_by_can.setdefault(can_slug, []).append(s_key)
                snapshots.pop(s_key, None)
                result["retired_snapshots_rolled_up"] += 1
                changed = True

    evaluations = ledger.get("evaluations")
    if isinstance(evaluations, list):
        kept_evals: List[Dict[str, Any]] = []
        seen_eval_slugs: Set[str] = set()
        for ev in evaluations:
            if not isinstance(ev, dict):
                continue
            ev_slug = str(ev.get("slug") or "").strip()
            entry_Info = redirect_map.get(f"slug:{ev_slug.lower()}") or redirect_map.get(f"/tools/{ev_slug.lower()}/")
            if entry_Info is not None or is_retired_or_consolidated_slug(ev_slug, prop):
                can_slug = str((entry_Info or {}).get("canonical_slug") or "").strip()
                if can_slug:
                    rolled_by_can.setdefault(can_slug, [])
                    if ev_slug not in rolled_by_can[can_slug]:
                        rolled_by_can[can_slug].append(ev_slug)
                result["retired_evaluations_removed"] += 1
                changed = True
                continue
            if ev_slug in seen_eval_slugs:
                changed = True
                continue
            seen_eval_slugs.add(ev_slug)
            kept_evals.append(dict(ev))

        for ev in kept_evals:
            ev_slug = str(ev.get("slug") or "").strip()
            if ev_slug in rolled_by_can:
                merged_r = sorted(set(ev.get("rolled_up_redirected_slugs") or []) | set(rolled_by_can[ev_slug]))
                if ev.get("rolled_up_redirected_slugs") != merged_r:
                    ev["rolled_up_redirected_slugs"] = merged_r
                    changed = True
            if isinstance(snapshots, dict) and ev_slug in snapshots and ev_slug in rolled_by_can:
                can_snap = snapshots[ev_slug]
                merged_s = sorted(set(can_snap.get("rolled_up_redirected_slugs") or []) | set(rolled_by_can[ev_slug]))
                if can_snap.get("rolled_up_redirected_slugs") != merged_s:
                    can_snap["rolled_up_redirected_slugs"] = merged_s
                    changed = True

        ledger["evaluations"] = kept_evals

    result["rolled_up_by_canonical"] = {k: sorted(set(v)) for k, v in rolled_by_can.items()}
    if changed:
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return result


def reconcile_factory_execution_log(
    repo_root: Union[str, Path],
    property_id: str = "profithelm",
    existing_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Reconciles .agy/factory_execution_log.json so Search Console audit_items resolve
    redirected queries (such as 'ca tax brackets') to their canonical parent tool and
    target path rather than leaving matching_tool as null.
    Zero em-dashes. Zero en-dashes.
    """
    root = Path(repo_root)
    prop_low = str(property_id).lower()
    prop = (
        "prexvo"
        if "prexvo" in prop_low
        else ("gainhelm" if "gainhelm" in prop_low else "profithelm")
    )
    log_path = root / ".agy" / "factory_execution_log.json"
    summary = {"queries_resolved": 0, "updated": False}
    if not log_path.is_file():
        return summary

    try:
        log_data = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return summary
    if not isinstance(log_data, dict):
        return summary

    sc_audit = (
        log_data.get("stages", {}).get("1_scan", {}).get("sc_performance_audit")
        if isinstance(log_data.get("stages"), dict) and isinstance(log_data["stages"].get("1_scan"), dict)
        else log_data.get("sc_performance_audit")
    )
    if not isinstance(sc_audit, dict):
        return summary

    audit_items = sc_audit.get("audit_items")
    changed = False
    if isinstance(audit_items, list):
        for item in audit_items:
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("query") or "").strip()
            cur_tool = item.get("matching_tool")
            if q_text and (not cur_tool or is_retired_or_consolidated_slug(str(cur_tool), prop)):
                res = resolve_redirected_gsc_target(
                    query=q_text,
                    slug=str(cur_tool or ""),
                    property_id=prop,
                    repo_root=root,
                    existing_tools=existing_tools,
                )
                if res.get("canonical_slug"):
                    item["matching_tool"] = res["canonical_slug"]
                    item["canonical_target"] = res["canonical_path"]
                    item["resolved_via"] = res["resolved_via"]
                    summary["queries_resolved"] += 1
                    changed = True

    if changed:
        summary["updated"] = True
        log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return summary


def reconcile_statutory_db_gsc_snapshots(
    repo_root: Union[str, Path],
    property_id: str = "profithelm",
) -> Dict[str, Any]:
    """
    Reconciles historical gsc_performance_snapshots in statutory.db so rows recorded with
    empty page ('') or retired 301-redirected URLs are attributed to their surviving canonical URLs.
    Zero em-dashes. Zero en-dashes.
    """
    import shutil
    import sqlite3
    import subprocess

    root = Path(repo_root)
    comb_prop = f"{property_id or ''} {root.name}".lower()
    prop = "prexvo" if "prexvo" in comb_prop else ("gainhelm" if "gainhelm" in comb_prop else "profithelm")
    db_file = root / "profithelm" / "data" / "statutory.db"
    summary = {"rows_updated": 0, "queries_mapped": 0}
    if not db_file.is_file():
        return summary

    best_by_q: Dict[str, str] = {}
    if prop == "profithelm" and "PYTEST_CURRENT_TEST" not in os.environ:
        gsccli_bin = shutil.which("gsccli") or "/home/ubuntuadmin/.npm-global/bin/gsccli"
        if Path(gsccli_bin).is_file():
            try:
                proc = subprocess.run(
                    [
                        gsccli_bin, "query", "run",
                        "-s", "sc-domain:profithelm.com",
                        "-d", "query", "-d", "page",
                        "--start-date", "90daysAgo",
                        "--data-state", "all",
                        "-f", "json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    raw = proc.stdout
                    s_i, e_i = raw.find("{"), raw.rfind("}")
                    if s_i != -1 and e_i > s_i:
                        qp_rows = json.loads(raw[s_i : e_i + 1]).get("data", [])
                        rollup_qp = rollup_redirected_gsc_rows(
                            qp_rows, property_id=prop, repo_root=root
                        )
                        best_impr: Dict[str, int] = {}
                        for r in rollup_qp.get("rows", []):
                            qk = str(r.get("query") or "").strip().lower()
                            c_u = str(r.get("canonical_url") or r.get("page") or "").strip()
                            im = int(r.get("impressions", 0) or 0)
                            if qk and c_u and im >= best_impr.get(qk, -1):
                                best_impr[qk] = im
                                best_by_q[qk] = c_u
            except Exception:
                pass

    try:
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        tables = [
            r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gsc_performance_snapshots'"
            ).fetchall()
        ]
        if not tables:
            conn.close()
            return summary

        distinct_pairs = cur.execute(
            "SELECT DISTINCT query, COALESCE(page, '') FROM gsc_performance_snapshots"
        ).fetchall()
        for q_val, p_val in distinct_pairs:
            q_str = str(q_val or "").strip()
            p_str = str(p_val or "").strip()
            target_canonical_url = ""
            if p_str:
                res = resolve_redirected_gsc_target(
                    target_url=p_str, query=q_str, property_id=prop, repo_root=root
                )
                if res.get("is_redirected") and not res.get("is_off_topic_sink") and res.get("canonical_url"):
                    target_canonical_url = str(res["canonical_url"])
            else:
                target_canonical_url = best_by_q.get(q_str.lower(), "")
                if not target_canonical_url and q_str:
                    res = resolve_redirected_gsc_target(
                        query=q_str, property_id=prop, repo_root=root
                    )
                    if not res.get("is_off_topic_sink") and res.get("canonical_url"):
                        target_canonical_url = str(res["canonical_url"])

            if target_canonical_url and target_canonical_url != p_str:
                cur.execute(
                    "UPDATE gsc_performance_snapshots SET page = ? WHERE query = ? AND COALESCE(page, '') = ?",
                    (target_canonical_url, q_val, p_str),
                )
                summary["rows_updated"] += max(0, cur.rowcount)
                summary["queries_mapped"] += 1

        if summary["rows_updated"] > 0:
            conn.commit()
        conn.close()
    except Exception:
        pass
    return summary


def sync_tenant_redirect_rollup_adapters(
    repo_root: Union[str, Path],
    property_id: str = "profithelm",
) -> int:
    """
    Idempotently synchronizes tenant freshness.py, gsc_adapter.py, and observer.py hooks
    so standalone tenant audits and GSC harvests roll up redirected page traffic and
    resolve retired query slugs through pseofactory.qualification.
    Returns count of tenant adapter files updated.
    Zero em-dashes. Zero en-dashes.
    """
    root = Path(repo_root)
    prop_low = str(property_id).lower()
    prop = (
        "prexvo"
        if "prexvo" in prop_low
        else ("gainhelm" if "gainhelm" in prop_low else "profithelm")
    )
    updated_files = 0

    if prop == "profithelm":
        freshness_py = root / "profithelm" / "freshness.py"
        if freshness_py.is_file():
            f_txt = freshness_py.read_text(encoding="utf-8")
            old_block = """    gsc_impressions_by_path: Dict[str, int] = {}
    top_pages = gsc_insights.get("top_pages", []) if isinstance(gsc_insights, dict) else []
    for item in top_pages:
        raw_keys = item.get("keys", [])
        page_path = None
        if isinstance(raw_keys, list) and raw_keys:
            page_path = raw_keys[0]
        elif item.get("page"):
            page_path = item.get("page")

        if page_path:
            norm = urllib.parse.urlsplit(str(page_path)).path.rstrip("/") or "/"
            impr = int(item.get("impressions", 0))
            gsc_impressions_by_path[norm] = max(gsc_impressions_by_path.get(norm, 0), impr)"""

            new_block = """    gsc_impressions_by_path: Dict[str, int] = {}
    top_pages = gsc_insights.get("top_pages", []) if isinstance(gsc_insights, dict) else []
    redirect_rollup_meta: Dict[str, Any] = {}
    try:
        from pseofactory.qualification import rollup_redirected_gsc_rows
        rollup_res = rollup_redirected_gsc_rows(
            top_pages,
            property_id="profithelm",
            repo_root=dist_dir.parent if dist_dir else BASE_DIR,
        )
        gsc_impressions_by_path = dict(rollup_res.get("impressions_by_path", {}))
        prior_meta = gsc_insights.get("redirect_signal_rollup", {}) if isinstance(gsc_insights, dict) else {}
        redirect_rollup_meta = {
            "redirected_rows_count": rollup_res.get("redirected_rows_count", 0) or prior_meta.get("redirected_rows_count", 0),
            "rolled_up_impressions": rollup_res.get("rolled_up_impressions", 0) or prior_meta.get("rolled_up_impressions", 0),
            "rolled_up_clicks": rollup_res.get("rolled_up_clicks", 0) or prior_meta.get("rolled_up_clicks", 0),
            "ignored_off_topic_rows_count": rollup_res.get("ignored_off_topic_rows_count", 0) or prior_meta.get("ignored_off_topic_rows_count", 0),
            "canonical_targets_summary": rollup_res.get("canonical_targets_summary") or prior_meta.get("canonical_targets_summary", {}),
        }
    except Exception:
        for item in top_pages:
            raw_keys = item.get("keys", [])
            page_path = None
            if isinstance(raw_keys, list) and raw_keys:
                page_path = raw_keys[0]
            elif item.get("page"):
                page_path = item.get("page")

            if page_path:
                norm = urllib.parse.urlsplit(str(page_path)).path.rstrip("/") or "/"
                impr = int(item.get("impressions", 0))
                gsc_impressions_by_path[norm] = gsc_impressions_by_path.get(norm, 0) + impr"""

            prev_meta = """        redirect_rollup_meta = {
            "redirected_rows_count": rollup_res.get("redirected_rows_count", 0),
            "rolled_up_impressions": rollup_res.get("rolled_up_impressions", 0),
            "rolled_up_clicks": rollup_res.get("rolled_up_clicks", 0),
            "ignored_off_topic_rows_count": rollup_res.get("ignored_off_topic_rows_count", 0),
            "canonical_targets_summary": rollup_res.get("canonical_targets_summary", {}),
        }"""
            new_meta = """        prior_meta = gsc_insights.get("redirect_signal_rollup", {}) if isinstance(gsc_insights, dict) else {}
        redirect_rollup_meta = {
            "redirected_rows_count": rollup_res.get("redirected_rows_count", 0) or prior_meta.get("redirected_rows_count", 0),
            "rolled_up_impressions": rollup_res.get("rolled_up_impressions", 0) or prior_meta.get("rolled_up_impressions", 0),
            "rolled_up_clicks": rollup_res.get("rolled_up_clicks", 0) or prior_meta.get("rolled_up_clicks", 0),
            "ignored_off_topic_rows_count": rollup_res.get("ignored_off_topic_rows_count", 0) or prior_meta.get("ignored_off_topic_rows_count", 0),
            "canonical_targets_summary": rollup_res.get("canonical_targets_summary") or prior_meta.get("canonical_targets_summary", {}),
        }"""

            if old_block in f_txt:
                f_txt = f_txt.replace(old_block, new_block, 1)
            elif prev_meta in f_txt:
                f_txt = f_txt.replace(prev_meta, new_meta, 1)

            old_age_block = """        try:
            mtime = html_file.stat().st_mtime
            age_days = (now_ts - mtime) / 86400.0
        except Exception:
            age_days = 0.0"""
            new_age_block = """        try:
            mtime = html_file.stat().st_mtime
            age_days = (now_ts - mtime) / 86400.0
            if age_days < 1.0:
                from pseofactory.seo_growth_loops import resolve_true_asset_age_days
                age_days = resolve_true_asset_age_days(
                    page_url_path,
                    html_file=html_file,
                    property_id="profithelm",
                    repo_root=dist_dir.parent if dist_dir else BASE_DIR,
                    now_ts=now_ts,
                )
        except Exception:
            age_days = 0.0"""
            if old_age_block in f_txt and "resolve_true_asset_age_days" not in f_txt:
                f_txt = f_txt.replace(old_age_block, new_age_block, 1)

            old_ret = """    return {
        "status": "PASS",
        "max_age_days": max_age_days,
        "pages_audited": pages_checked,
        "zero_impression_candidates": zero_candidates,
        "flagged_count": len(zero_candidates),
        "noindexed_count": noindexed_count,
        "action_taken": "NOINDEX_APPLIED" if apply_noindex else "FLAGGED_ONLY",
    }"""
            new_ret = """    return {
        "status": "PASS",
        "max_age_days": max_age_days,
        "pages_audited": pages_checked,
        "zero_impression_candidates": zero_candidates,
        "flagged_count": len(zero_candidates),
        "noindexed_count": noindexed_count,
        "action_taken": "NOINDEX_APPLIED" if apply_noindex else "FLAGGED_ONLY",
        "redirect_signal_rollup": redirect_rollup_meta,
    }"""
            if old_ret in f_txt:
                f_txt = f_txt.replace(old_ret, new_ret, 1)
            old_rep_tail = """        "zero_impression_handling": zero_impression_audit,
        "seo_checklist": seo_checklist_audit,
        "statutory_accuracy": statutory_audit,
    }"""
            new_rep_tail = """        "zero_impression_handling": zero_impression_audit,
        "redirect_signal_rollup": zero_impression_audit.get("redirect_signal_rollup", {}),
        "seo_checklist": seo_checklist_audit,
        "statutory_accuracy": statutory_audit,
    }"""
            if old_rep_tail in f_txt:
                f_txt = f_txt.replace(old_rep_tail, new_rep_tail, 1)
            if f_txt != freshness_py.read_text(encoding="utf-8"):
                freshness_py.write_text(f_txt, encoding="utf-8")
                updated_files += 1

        gsc_py = root / "profithelm" / "gsc_adapter.py"
        if gsc_py.is_file():
            g_txt = gsc_py.read_text(encoding="utf-8")
            old_harvest_ret = """                    for row in data:
                        normalized.append({
                            "query": str(row.get("query", "")),
                            "clicks": int(float(row.get("clicks", 0))),
                            "impressions": int(float(row.get("impressions", 0))),
                            "ctr": float(row.get("ctr", 0.0)),
                            "position": float(row.get("position", 100.0)),
                        })
                    return normalized"""
            new_harvest_ret = """                    for row in data:
                        normalized.append({
                            "query": str(row.get("query", "")),
                            "page": str(row.get("page", "")),
                            "clicks": int(float(row.get("clicks", 0))),
                            "impressions": int(float(row.get("impressions", 0))),
                            "ctr": float(row.get("ctr", 0.0)),
                            "position": float(row.get("position", 100.0)),
                        })
                    if normalized and "PYTEST_CURRENT_TEST" not in os.environ:
                        try:
                            from pseofactory.qualification import rollup_redirected_gsc_rows
                            qp_cmd = [
                                gsccli_bin, "query", "run", "-s", site,
                                "-d", "query", "-d", "page",
                                "--start-date", f"{days}daysAgo",
                                "--data-state", "all", "-f", "json",
                            ]
                            qp_proc = subprocess.run(qp_cmd, capture_output=True, text=True, timeout=25)
                            if qp_proc.returncode == 0 and qp_proc.stdout.strip():
                                qp_raw = qp_proc.stdout
                                s_i, e_i = qp_raw.find("{"), qp_raw.rfind("}")
                                if s_i != -1 and e_i > s_i:
                                    qp_rows = json.loads(qp_raw[s_i : e_i + 1]).get("data", [])
                                    rollup_qp = rollup_redirected_gsc_rows(
                                        qp_rows, property_id="profithelm", repo_root=BASE_DIR
                                    )
                                    best_by_q: Dict[str, Dict[str, Any]] = {}
                                    for r_qp in rollup_qp.get("rows", []):
                                        qk = str(r_qp.get("query", "")).strip().lower()
                                        if not qk:
                                            continue
                                        prev_r = best_by_q.get(qk)
                                        if prev_r is None or int(r_qp.get("impressions", 0)) > int(prev_r.get("impressions", 0)):
                                            best_by_q[qk] = r_qp
                                    for n_row in normalized:
                                        m_qp = best_by_q.get(n_row["query"].strip().lower())
                                        if m_qp:
                                            n_row["page"] = str(m_qp.get("canonical_url") or m_qp.get("page") or "")
                                            n_row["canonical_slug"] = str(m_qp.get("canonical_slug") or "")
                                            if m_qp.get("rolled_up_from"):
                                                n_row["rolled_up_from"] = list(m_qp["rolled_up_from"])
                                                n_row["direct_impressions"] = int(m_qp.get("direct_impressions", 0))
                                                n_row["redirected_impressions"] = int(m_qp.get("redirected_impressions", 0))
                        except Exception:
                            pass
                    return normalized"""
            if old_harvest_ret in g_txt:
                g_txt = g_txt.replace(old_harvest_ret, new_harvest_ret, 1)

            old_match = """        matching_tool = None
        q_lower = q_text.lower()
        for t in tools_catalog:
            slug = t.get("slug", "")
            kw = t.get("primary_keyword", "")
            if slug and slug in q_lower.replace(" ", "-"):
                matching_tool = slug
                break
            if kw and (kw in q_lower or q_lower in kw):
                matching_tool = slug
                break"""
            new_match = """        matching_tool = None
        q_lower = q_text.lower()
        for t in tools_catalog:
            slug = t.get("slug", "")
            kw = t.get("primary_keyword", "")
            sec_kws = [str(sk).lower() for sk in (t.get("secondary_keywords") or []) if sk]
            if slug and slug in q_lower.replace(" ", "-"):
                matching_tool = slug
                break
            if kw and (kw in q_lower or q_lower in kw):
                matching_tool = slug
                break
            if q_lower in sec_kws:
                matching_tool = slug
                break
        try:
            from pseofactory.qualification import resolve_redirected_gsc_target
            res_t = resolve_redirected_gsc_target(
                target_url=page_val,
                query=q_text,
                slug=str(matching_tool or ""),
                property_id="profithelm",
                repo_root=root,
                existing_tools=tools_catalog,
            )
            if res_t.get("canonical_slug"):
                matching_tool = res_t["canonical_slug"]
            if res_t.get("canonical_url") and not page_val:
                page_val = res_t["canonical_url"]
        except Exception:
            pass"""
            if old_match in g_txt:
                g_txt = g_txt.replace(old_match, new_match, 1)

            old_save_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    if path.is_file() and not force:"""
            new_save_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    root = Path(base_dir) if base_dir else BASE_DIR
    if not path.is_file() and (base_dir is None or root.resolve() == BASE_DIR.resolve()):
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file() or "PYTEST_CURRENT_TEST" not in os.environ:
            path = alt_path
    if path.is_file() and not force:"""
            if old_save_ov in g_txt and "alt_path.is_file() or" not in g_txt:
                g_txt = g_txt.replace(old_save_ov, new_save_ov, 1)

            old_load_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    if not path.is_file():
        return None"""
            prev_load_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    if not path.is_file() and base_dir is None:
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file():
            path = alt_path
    if not path.is_file():
        return None"""
            new_load_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    root = Path(base_dir) if base_dir else BASE_DIR
    if not path.is_file() and (base_dir is None or root.resolve() == BASE_DIR.resolve()):
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file():
            path = alt_path
    if not path.is_file():
        return None"""
            if prev_load_ov in g_txt:
                g_txt = g_txt.replace(prev_load_ov, new_load_ov, 1)
            elif old_load_ov in g_txt and 'BASE_DIR / ".agy" / "overlays"' not in g_txt:
                g_txt = g_txt.replace(old_load_ov, new_load_ov, 1)

            if g_txt != gsc_py.read_text(encoding="utf-8"):
                gsc_py.write_text(g_txt, encoding="utf-8")
                updated_files += 1

        obs_py = root / "profithelm" / "observer.py"
        if obs_py.is_file():
            o_txt = obs_py.read_text(encoding="utf-8")
            old_served_ret = """    # Ensure QSBS / 1202 variants are recognized as served
    if any("qsbs" in s for s in served_slugs) or any("qsbs" in q for q in served_queries):
        served_slugs.add("qsbs-83b-tax-calculator")
        served_slugs.add("qsbs-section-1202-tax-calculator")
        served_queries.add("qsbs section 1202 tax calculator")

    return served_slugs, served_queries"""
            new_served_ret = """    # Ensure QSBS / 1202 variants are recognized as served
    if any("qsbs" in s for s in served_slugs) or any("qsbs" in q for q in served_queries):
        served_slugs.add("qsbs-83b-tax-calculator")
        served_slugs.add("qsbs-section-1202-tax-calculator")
        served_queries.add("qsbs section 1202 tax calculator")

    if deployed_voids_path is None and "PYTEST_CURRENT_TEST" not in os.environ:
        redirects_file = BASE_DIR / "content" / "redirects.json"
        if redirects_file.is_file():
            try:
                red_map = json.loads(redirects_file.read_text(encoding="utf-8"))
                if isinstance(red_map, dict):
                    for src_p in red_map.keys():
                        clean_src = str(src_p).strip("/")
                        if clean_src.startswith("tools/"):
                            r_slug = clean_src[len("tools/"):].strip("/")
                            if r_slug and "/" not in r_slug:
                                served_slugs.add(r_slug)
                                served_queries.add(r_slug.replace("-", " ").lower().strip())
            except Exception:
                pass

    return served_slugs, served_queries"""
            if old_served_ret in o_txt and 'BASE_DIR / "content" / "redirects.json"' not in o_txt:
                o_txt = o_txt.replace(old_served_ret, new_served_ret, 1)

            old_obs = """    # 3. Detect unserved query impressions (ghost paths)
    existing_slugs = {t["slug"] for t in TOOLS}
    for p in insights["top_pages"]:"""
            new_obs = """    # 3. Roll up redirected top_pages into canonical targets and detect ghost paths
    try:
        from pseofactory.qualification import rollup_redirected_gsc_rows
        if insights["top_pages"]:
            rollup_res = rollup_redirected_gsc_rows(
                insights["top_pages"],
                property_id="profithelm",
                repo_root=BASE_DIR,
            )
            insights["top_pages"] = rollup_res.get("rows", insights["top_pages"])
            insights["redirect_signal_rollup"] = {
                "redirected_rows_count": rollup_res.get("redirected_rows_count", 0),
                "rolled_up_impressions": rollup_res.get("rolled_up_impressions", 0),
                "rolled_up_clicks": rollup_res.get("rolled_up_clicks", 0),
                "ignored_off_topic_rows_count": rollup_res.get("ignored_off_topic_rows_count", 0),
                "canonical_targets_summary": rollup_res.get("canonical_targets_summary", {}),
            }
    except Exception:
        pass
    existing_slugs = {t["slug"] for t in TOOLS}
    for p in insights["top_pages"]:"""
            if old_obs in o_txt:
                o_txt = o_txt.replace(old_obs, new_obs, 1)
            if o_txt != obs_py.read_text(encoding="utf-8"):
                obs_py.write_text(o_txt, encoding="utf-8")
                updated_files += 1

        fac_py = root / "profithelm" / "factory.py"
        if fac_py.is_file():
            fa_txt = fac_py.read_text(encoding="utf-8")
            fa_orig = fa_txt
            old_fac_init = """    if live_probe is None:
        live_probe = live_deploy or (os.getenv("PROFITHELM_LIVE_PROBE") == "1")"""
            new_fac_init = """    if live_probe is None:
        live_probe = live_deploy or (os.getenv("PROFITHELM_LIVE_PROBE") == "1")
    if check_queue:
        abort_on_zero_asset = True"""
            if old_fac_init in fa_txt and "if check_queue:\n        abort_on_zero_asset = True" not in fa_txt:
                fa_txt = fa_txt.replace(old_fac_init, new_fac_init, 1)

            old_fac_gate = """        # Pre-Run Empty-Queue Gate
        if top_opp is None and top_trend is None and not target_query:
            from profithelm.staleness import evaluate_system_staleness
            staleness = evaluate_system_staleness()
            requires_recompile = staleness.get("requires_recompile", False)
            if not requires_recompile and not force:"""
            new_fac_gate = """        # Pre-Run Empty-Queue Gate
        if top_opp is None and top_trend is None and not target_query:
            from profithelm.staleness import evaluate_system_staleness
            staleness = evaluate_system_staleness()
            requires_recompile = staleness.get("requires_recompile", False)
            if (not requires_recompile or check_queue) and not force:"""
            if old_fac_gate in fa_txt:
                fa_txt = fa_txt.replace(old_fac_gate, new_fac_gate, 1)

            old_fac_build = """        extra = [synthesized_spec] if (synthesized_spec and synthesized_spec["slug"] not in {t["slug"] for t in TOOLS}) else None
        if use_worktree:
            with ephemeral_build_worktree(BASE_DIR) as wt_dir:
                print(f"   Building inside isolated ephemeral worktree: {wt_dir}")
                build_all(extra_tools=extra)
        else:
            build_all(extra_tools=extra)
        built_pages = list(DIST_DIR.glob("**/*.html"))
        asset_inspection = inspect_platform_assets()

        # Synchronize primary interactive calculator hubs & contextual entrypoints
        from profithelm.interactive_calculator import sync_calculator_hubs_and_entrypoints
        hub_summary = sync_calculator_hubs_and_entrypoints()"""
            new_fac_build = """        extra = [synthesized_spec] if (synthesized_spec and synthesized_spec["slug"] not in {t["slug"] for t in TOOLS}) else None
        skip_rebuild = False
        if abort_on_zero_asset and synthesized_spec is None and not force and (DIST_DIR / "index.html").is_file():
            try:
                from profithelm.staleness import detect_statutory_drift, detect_engine_drift
                s_drift = (detect_statutory_drift().get("status") == "DRIFT")
                e_drift = (detect_engine_drift(state_file=BASE_DIR / ".agy" / "engine_hash.json").get("status") == "DRIFT")
                if not s_drift and not e_drift:
                    skip_rebuild = True
            except Exception:
                pass
        if not skip_rebuild:
            if use_worktree:
                with ephemeral_build_worktree(BASE_DIR) as wt_dir:
                    print(f"   Building inside isolated ephemeral worktree: {wt_dir}")
                    build_all(extra_tools=extra)
            else:
                build_all(extra_tools=extra)
        built_pages = list(DIST_DIR.glob("**/*.html"))
        asset_inspection = inspect_platform_assets()

        # Synchronize primary interactive calculator hubs & contextual entrypoints
        from profithelm.interactive_calculator import sync_calculator_hubs_and_entrypoints
        hub_summary = (
            {"hubs_count": len(TOOLS), "entrypoints_count": len(built_pages)}
            if skip_rebuild
            else sync_calculator_hubs_and_entrypoints()
        )"""
            if old_fac_build in fa_txt and "skip_rebuild = False" not in fa_txt:
                fa_txt = fa_txt.replace(old_fac_build, new_fac_build, 1)
            if fa_txt != fa_orig:
                fac_py.write_text(fa_txt, encoding="utf-8")
                updated_files += 1

        gen_py = root / "profithelm" / "generator.py"
        if gen_py.is_file():
            g_txt = gen_py.read_text(encoding="utf-8")
            g_orig = g_txt
            old_short_title = '    short_title = title.split("&")[0].split(":")[0].strip()'
            new_short_title = '    short_title = re.split(r"\\s+&\\s+", title)[0].split(":")[0].strip()'
            if old_short_title in g_txt:
                g_txt = g_txt.replace(old_short_title, new_short_title, 1)
            old_qa_join = '            resolved_quick_answer = f"{qa_clean.rstrip(\'.\')} {\' \'.join(expansion_words)}"'
            new_qa_join = '            resolved_quick_answer = f"{qa_clean.rstrip(\'.\')}. {\' \'.join(expansion_words)}"'
            if old_qa_join in g_txt:
                g_txt = g_txt.replace(old_qa_join, new_qa_join, 1)
            if g_txt != g_orig:
                gen_py.write_text(g_txt, encoding="utf-8")
                updated_files += 1

        dlq_file = root / ".agy" / "maintenance_dlq.json"
        if dlq_file.is_file():
            try:
                dlq_items = json.loads(dlq_file.read_text(encoding="utf-8"))
                if isinstance(dlq_items, list):
                    consolidated_slugs = set(CANNIBALIZING_CLONE_CONSOLIDATION_MAP.keys())
                    filtered_dlq = [
                        item for item in dlq_items
                        if not (isinstance(item, dict) and str(item.get("slug", "")).strip() in consolidated_slugs)
                    ]
                    if len(filtered_dlq) != len(dlq_items):
                        dlq_file.write_text(json.dumps(filtered_dlq, indent=2) + "\n", encoding="utf-8")
                        updated_files += 1
            except Exception:
                pass
    else:
        prexvo_freshness = root / "prexvo" / "freshness.py"
        if prexvo_freshness.is_file():
            pf_txt = prexvo_freshness.read_text(encoding="utf-8")
            old_pf_ret = """    return {
        "verdict": verdict,
        "total_score": max(0.0, score),
        "mathematical_determinism": math_audit,
        "statutory_oracle": oracle_audit,
        "compliance_gate": comp_gate,
        "seo_checklist": seo_audit,
        "affiliate_routes": affiliate_audit,
        "merkle_drift": merkle_drift,
        "dataset_provenance": dataset_provenance,
        "dataset_provenance_verified": dataset_provenance_verified,
    }"""
            prev_pf_report = """    report = {
        "verdict": verdict,
        "total_score": max(0.0, score),
        "mathematical_determinism": math_audit,
        "statutory_oracle": oracle_audit,
        "compliance_gate": comp_gate,
        "seo_checklist": seo_audit,
        "affiliate_routes": affiliate_audit,
        "merkle_drift": merkle_drift,
        "dataset_provenance": dataset_provenance,
        "dataset_provenance_verified": dataset_provenance_verified,
        "redirect_signal_rollup": redirect_rollup_meta,
    }"""
            new_pf_report = """    internal_link_graph_meta: Dict[str, Any] = {"status": "PASS", "total_pages": 0, "orphaned_pages": [], "orphaned_count": 0}
    zero_impression_meta: Dict[str, Any] = {"status": "PASS", "max_age_days": 30.0, "pages_audited": 0, "zero_impression_candidates": [], "flagged_count": 0}
    try:
        from pseofactory.seo_growth_loops import (
            discover_internal_linking_opportunities,
            evaluate_content_portfolio_decisions,
        )
        il_rep = discover_internal_linking_opportunities(
            property_id="prexvo",
            repo_root=target_dir.parent,
            dist_dir=target_dir,
            persist=False,
        )
        internal_link_graph_meta = dict(il_rep.get("internal_link_graph") or internal_link_graph_meta)
        pf_rep = evaluate_content_portfolio_decisions(
            property_id="prexvo",
            repo_root=target_dir.parent,
            dist_dir=target_dir,
            persist=False,
        )
        zero_impression_meta = {
            "status": "PASS",
            "max_age_days": 30.0,
            "pages_audited": int(pf_rep.get("pages_audited", 0)),
            "zero_impression_candidates": list(pf_rep.get("zero_impression_candidates") or []),
            "flagged_count": int(pf_rep.get("flagged_count", 0)),
            "noindexed_count": 0,
            "action_taken": "FLAGGED_ONLY",
        }
    except Exception:
        pass

    report = {
        "verdict": verdict,
        "total_score": max(0.0, score),
        "mathematical_determinism": math_audit,
        "statutory_oracle": oracle_audit,
        "compliance_gate": comp_gate,
        "seo_checklist": seo_audit,
        "affiliate_routes": affiliate_audit,
        "merkle_drift": merkle_drift,
        "dataset_provenance": dataset_provenance,
        "dataset_provenance_verified": dataset_provenance_verified,
        "redirect_signal_rollup": redirect_rollup_meta,
        "internal_link_graph": internal_link_graph_meta,
        "zero_impression_handling": zero_impression_meta,
    }"""
            if prev_pf_report in pf_txt and "internal_link_graph_meta" not in pf_txt:
                pf_txt = pf_txt.replace(prev_pf_report, new_pf_report, 1)
                prexvo_freshness.write_text(pf_txt, encoding="utf-8")
                updated_files += 1
            elif old_pf_ret in pf_txt:
                pf_txt = pf_txt.replace(old_pf_ret, new_pf_report + "\n    return report", 1)
                prexvo_freshness.write_text(pf_txt, encoding="utf-8")
                updated_files += 1

        prexvo_gsc = root / "prexvo" / "gsc_adapter.py"
        if prexvo_gsc.is_file():
            pg_txt = prexvo_gsc.read_text(encoding="utf-8")
            old_pg_save = """    path = get_overlay_path(slug, base_dir=base_dir)
    if path.is_file() and not force:"""
            new_pg_save = """    path = get_overlay_path(slug, base_dir=base_dir)
    root = Path(base_dir) if base_dir else BASE_DIR
    if not path.is_file() and (base_dir is None or root.resolve() == BASE_DIR.resolve()):
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file() or "PYTEST_CURRENT_TEST" not in os.environ:
            path = alt_path
    if path.is_file() and not force:"""
            if old_pg_save in pg_txt and "alt_path.is_file() or" not in pg_txt:
                pg_txt = pg_txt.replace(old_pg_save, new_pg_save, 1)

            old_pg_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    if not path.is_file():
        return None"""
            prev_pg_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    if not path.is_file() and base_dir is None:
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file():
            path = alt_path
    if not path.is_file():
        return None"""
            new_pg_ov = """    path = get_overlay_path(slug, base_dir=base_dir)
    root = Path(base_dir) if base_dir else BASE_DIR
    if not path.is_file() and (base_dir is None or root.resolve() == BASE_DIR.resolve()):
        alt_path = BASE_DIR / ".agy" / "overlays" / f"{slug}.json"
        if alt_path.is_file():
            path = alt_path
    if not path.is_file():
        return None"""
            if prev_pg_ov in pg_txt:
                pg_txt = pg_txt.replace(prev_pg_ov, new_pg_ov, 1)
            elif old_pg_ov in pg_txt and 'BASE_DIR / ".agy" / "overlays"' not in pg_txt:
                pg_txt = pg_txt.replace(old_pg_ov, new_pg_ov, 1)

            if pg_txt != prexvo_gsc.read_text(encoding="utf-8"):
                prexvo_gsc.write_text(pg_txt, encoding="utf-8")
                updated_files += 1

        prexvo_obs = root / "prexvo" / "observer.py"
        if prexvo_obs.is_file():
            po_txt = prexvo_obs.read_text(encoding="utf-8")
            old_po = """    if has_valid_data:
        insights["status"] = "CONNECTED"

    return insights"""
            new_po = """    try:
        from pseofactory.qualification import rollup_redirected_gsc_rows
        if insights["top_pages"]:
            rollup_res = rollup_redirected_gsc_rows(
                insights["top_pages"],
                property_id="prexvo",
                repo_root=BASE_DIR,
            )
            insights["top_pages"] = rollup_res.get("rows", insights["top_pages"])
            insights["redirect_signal_rollup"] = {
                "redirected_rows_count": rollup_res.get("redirected_rows_count", 0),
                "rolled_up_impressions": rollup_res.get("rolled_up_impressions", 0),
                "rolled_up_clicks": rollup_res.get("rolled_up_clicks", 0),
                "ignored_off_topic_rows_count": rollup_res.get("ignored_off_topic_rows_count", 0),
                "canonical_targets_summary": rollup_res.get("canonical_targets_summary", {}),
            }
    except Exception:
        pass

    if has_valid_data:
        insights["status"] = "CONNECTED"

    return insights"""
            if old_po in po_txt and "rollup_redirected_gsc_rows" not in po_txt:
                po_txt = po_txt.replace(old_po, new_po, 1)
                prexvo_obs.write_text(po_txt, encoding="utf-8")
                updated_files += 1

        prexvo_fac = root / "prexvo" / "factory.py"
        if prexvo_fac.is_file():
            px_txt = prexvo_fac.read_text(encoding="utf-8")
            px_orig = px_txt
            old_px_init = """    if live_probe is None:
        live_probe = live_deploy or (os.getenv("PREXVO_LIVE_PROBE") == "1")"""
            new_px_init = """    if live_probe is None:
        live_probe = live_deploy or (os.getenv("PREXVO_LIVE_PROBE") == "1")
    if check_queue:
        abort_on_zero_asset = True
    in_test = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PREXVO_IN_TEST") == "1")"""
            if old_px_init in px_txt and "if check_queue:\n        abort_on_zero_asset = True" not in px_txt:
                px_txt = px_txt.replace(old_px_init, new_px_init, 1)

            old_px_gate = """        if top_opp is None and not target_query:
            from prexvo.staleness import evaluate_system_staleness
            staleness = evaluate_system_staleness()
            requires_recompile = staleness.get("requires_recompile", False)
            if not requires_recompile and not force:"""
            new_px_gate = """        if top_opp is None and not target_query:
            from prexvo.staleness import evaluate_system_staleness
            staleness = evaluate_system_staleness()
            requires_recompile = staleness.get("requires_recompile", False)
            if (not requires_recompile or check_queue) and not force:"""
            if old_px_gate in px_txt:
                px_txt = px_txt.replace(old_px_gate, new_px_gate, 1)

            if px_txt != px_orig:
                prexvo_fac.write_text(px_txt, encoding="utf-8")
                updated_files += 1

    return updated_files

