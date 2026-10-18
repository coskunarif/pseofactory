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
    "rates": "brackets",
    "rate": "brackets",
    "tables": "brackets",
    "table": "brackets",
    "schedule": "brackets",
    "schedules": "brackets",
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
        if act in ("PRUNE_PAGE", "PRUNE", "REJECT_SYNTHETIC"):
            return "PRUNE"
        return str(self.get("status") or act)


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


def check_search_intent_cannibalization(
    query: str,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    token_overlap_threshold: float = 0.50,
    sitemap_urls: Optional[List[str]] = None,
    candidate_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether a candidate query cannibalizes existing tool catalog intent,
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
                        is_1031_hub = "1031" in hub_tokens and "1031" in q_core and not (
                            len(q_core - {"1031", "exchange", "section", "like", "kind", "deferral", "tax", "property", "real", "estate"}) >= 2
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
                    if q_core == norm_slug["core_tokens"] or (
                        {"tax", "brackets"}.issubset(q_core)
                        and {"tax", "brackets"}.issubset(norm_slug["core_tokens"])
                        and q_core.issubset({"irs", "tax", "brackets"})
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_core_topic_modifier_variant",
                            "matched_tool": tool,
                        }
                    if tool_slug == "tcja-sunset-capital-gains" and {"capital", "gains"}.issubset(q_core) and q_core.issubset(
                        {"irs", "capital", "gains", "tax", "brackets", "tcja", "sunset", "long", "term", "short"}
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_core_topic_modifier_variant",
                            "matched_tool": tool,
                        }
                    if tool_slug == "prediction-market-odds" and {"prediction", "market"}.issubset(q_core) and q_core.issubset(
                        {"kalshi", "polymarket", "prediction", "market", "odds", "arbitrage", "strategy", "implied", "probability"}
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug,
                            "target_subroute": f"/tools/{tool_slug}/",
                            "reason": "matches_core_topic_modifier_variant",
                            "matched_tool": tool,
                        }

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


def qualify_search_intent(
    query_data: Optional[Dict[str, Any]] = None,
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
    1. CONSOLIDATE_PAGES: Multiple URLs competing for the same query.
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

    # 1. Check competing pages (Consolidation)
    competing = query_data.get("competing_pages") or query_data.get("urls") or []
    if len(competing) > 1:
        return SearchIntentVerdict({
            "action": "CONSOLIDATE_PAGES",
            "status": "CONSOLIDATE_PAGES",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "competing_pages": competing,
            "canonical_url": competing[0],
            "redirect_candidates": competing[1:],
            "reason": f"Multiple URLs ({len(competing)}) competing for query '{q_text}'",
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

    # 3. Match against existing tool catalog and cannibalization detection
    matching_tool = query_data.get("matching_tool")
    cannibal = check_search_intent_cannibalization(
        q_text,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        candidate_spec=query_data,
    )

    if matching_tool is None and cannibal.get("is_cannibalizing") and cannibal.get("parent_slug") != "none":
        matching_tool = cannibal.get("parent_slug")

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
            }

            return SearchIntentVerdict({
                "action": "REFACTOR_PAGE",
                "status": "REFACTOR_PAGE",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "matching_tool": matching_tool,
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

    # Qualified unserved void
    candidate_spec = {
        "query": q_text,
        "primary_keyword": q_text.lower(),
        "position": pos,
        "impressions": impr,
        "clicks": clicks,
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


def reconcile_void_candidates_queue(vc_path: Union[str, Path]) -> int:
    """
    Reconciles a void_candidates.jsonl topic queue against consolidated/retired slugs
    and synthetic/off-topic patterns so the autonomous pipeline never re-queues or resurrects
    retired duplicate pages.
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

        if is_synthetic_test_candidate(eff_slug or raw_query, rec_copy):
            if rec_copy.get("status") != "REJECTED" or rec_copy.get("action") != "REJECT":
                rec_copy["status"] = "REJECTED"
                rec_copy["action"] = "REJECT"
                rec_copy["status_reason"] = "Rejected synthetic or off-topic candidate"
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
            if act in ("REJECT", "MONITOR") and rec_copy.get("status") != "REJECTED":
                rec_copy["status"] = "REJECTED"
                rec_copy["status_reason"] = (
                    rec_copy.get("status_reason")
                    or f"Engine verdict {act}: {rec_copy.get('decision_reason') or 'not actionable'}"
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

    for synd_dir in synd_dirs:
        if not synd_dir.is_dir():
            continue
        for item in sorted(synd_dir.iterdir()):
            if item.name.startswith(".") or item.name == "ai_benchmarks":
                continue
            if item.is_dir():
                if item.name in slugs_to_purge or is_retired_or_consolidated_slug(item.name, prop):
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

    # Clean .agy/broadcast_ledger.json and .agy/facebook_groups_catalog*.json
    b_ledger = root / ".agy" / "broadcast_ledger.json"
    if b_ledger.is_file():
        try:
            b_data = json.loads(b_ledger.read_text(encoding="utf-8"))
            if isinstance(b_data, list):
                filtered_b = [
                    entry for entry in b_data
                    if isinstance(entry, dict)
                    and str(entry.get("slug") or "") not in slugs_to_purge
                    and not is_retired_or_consolidated_slug(str(entry.get("slug") or ""), prop)
                ]
                if len(filtered_b) != len(b_data):
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
        if agy_ov.is_dir() or cnt_ov.is_dir():
            agy_ov.mkdir(parents=True, exist_ok=True)
            cnt_ov.mkdir(parents=True, exist_ok=True)
            for src_dir, dst_dir in ((agy_ov, cnt_ov), (cnt_ov, agy_ov)):
                for ov_f in sorted(src_dir.glob("*.json")):
                    dst_f = dst_dir / ov_f.name
                    if not dst_f.is_file():
                        shutil.copyfile(ov_f, dst_f)
                        summary["overlays_synced"] += 1
        return summary

    grouped_queries_by_canonical: Dict[str, List[str]] = {}
    for clone_slug, info in clone_map.items():
        c_slug = info["canonical_slug"]
        q_default = clone_slug.replace("-scenario-comparison-model", "").replace("-", " ").strip()
        grouped_queries_by_canonical.setdefault(c_slug, [])
        if q_default and q_default not in grouped_queries_by_canonical[c_slug]:
            grouped_queries_by_canonical[c_slug].append(q_default)

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
    }
    for off_path in OFF_TOPIC_REDIRECT_CONSOLIDATION_MAP.keys():
        clean_off = off_path.strip("/")
        if clean_off.startswith("tools/"):
            slugs_to_purge.add(clean_off[len("tools/"):].strip("/"))
        elif "/" not in clean_off and clean_off:
            slugs_to_purge.add(clean_off)

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
    agy_ov_dir.mkdir(parents=True, exist_ok=True)
    cnt_ov_dir.mkdir(parents=True, exist_ok=True)

    for ov_dir in (agy_ov_dir, cnt_ov_dir):
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

    all_ov_names = sorted({f.name for f in agy_ov_dir.glob("*.json")} | {f.name for f in cnt_ov_dir.glob("*.json")})
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

        extra_queries = grouped_queries_by_canonical.get(slug, [])
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
        for target_f in (agy_f, cnt_f):
            old_txt = target_f.read_text(encoding="utf-8") if target_f.is_file() else ""
            if old_txt != serialized:
                target_f.write_text(serialized, encoding="utf-8")
                summary["overlays_synced"] += 1

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

    return summary
