"""
pseofactory Search Intent Doctrine & Opportunity Qualification Engine
Enforces the Search Intent Doctrine across Prexvo, ProfitHelm, and downstream factories:
"An impression is not proof that a new page is missing. Google may be testing an existing page
for related intent. Build pages only when the search intent is genuinely underserved,
otherwise you're just creating URL bloat and potential cannibalization. #impressions"

Zero em-dashes. Zero en-dashes.
"""

import json
import ast
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

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


def check_search_intent_cannibalization(
    query: str,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    token_overlap_threshold: float = 0.50,
    sitemap_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether a candidate query cannibalizes existing tool catalog intent,
    secondary keywords, slug tokens, or indexed sitemap URLs.
    Zero em-dashes. Zero en-dashes.
    """
    clean_q = str(query or "").lower().strip()
    if not clean_q:
        return {
            "cannibalized": False,
            "is_cannibalizing": False,
            "parent_slug": "none",
            "reason": "empty",
            "matched_tool": None,
        }

    query_words = set(re.findall(r"\b[a-z0-9]+\b", clean_q))

    # 1. Deterministic evaluation against existing tools catalog
    if existing_tools:
        for tool in existing_tools:
            tool_slug = str(tool.get("slug", "")).strip()
            pk = str(tool.get("primary_keyword", "")).lower().strip()
            sec_kws = [str(k).lower().strip() for k in tool.get("secondary_keywords", []) if k]

            # Primary keyword match
            if pk:
                pk_words = set(re.findall(r"\b[a-z0-9]+\b", pk))
                if clean_q == pk or clean_q in pk or pk in clean_q or (pk_words and pk_words.issubset(query_words)):
                    return {
                        "cannibalized": True,
                        "is_cannibalizing": True,
                        "parent_slug": tool_slug or "none",
                        "reason": "matches_primary_keyword",
                        "matched_tool": tool,
                    }

            # Secondary keyword match
            if clean_q in sec_kws:
                return {
                    "cannibalized": True,
                    "is_cannibalizing": True,
                    "parent_slug": tool_slug or "none",
                    "reason": "matches_secondary_keyword",
                    "matched_tool": tool,
                }

            for sec in sec_kws:
                if sec and (sec in clean_q or (len(clean_q) >= 4 and clean_q in sec)):
                    return {
                        "cannibalized": True,
                        "is_cannibalizing": True,
                        "parent_slug": tool_slug or "none",
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

                    if (
                        (len(overlap) >= 3 and len(query_words) <= 4)
                        or jaccard >= token_overlap_threshold
                        or (jaccard >= 0.40 and len(overlap) >= 2)
                    ):
                        return {
                            "cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug or "none",
                            "reason": "high_slug_token_overlap",
                            "matched_tool": tool,
                        }

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
                        return {
                            "cannibalized": True,
                            "is_cannibalizing": True,
                            "parent_slug": tool_slug or slug_part.replace(" ", "-"),
                            "reason": "matches_tool_url",
                            "matched_tool": tool,
                        }

    # 2. Check against sitemap URLs if provided
    if sitemap_urls:
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
                        "is_cannibalizing": True,
                        "parent_slug": slug_part.replace(" ", "-"),
                        "reason": "matches_sitemap_url",
                        "matched_tool": None,
                    }

    return {
        "cannibalized": False,
        "is_cannibalizing": False,
        "parent_slug": "none",
        "reason": "distinct_asset",
        "matched_tool": None,
    }


def qualify_search_intent(
    query_data: Dict[str, Any],
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    total_site_impressions: int = 500,
    sitemap_urls: Optional[List[str]] = None,
    require_high_effort: bool = False,
) -> Dict[str, Any]:
    """
    Enforces Search Intent Doctrine triage across candidate queries:
    1. CONSOLIDATE_PAGES: Multiple URLs competing for the same query.
    2. PRUNE_PAGE: 0 impressions across >= 90 days.
    3. REFACTOR_PAGE: Striking distance query (pos 4-20) matching an existing tool.
       Generates overlay specification with 28-day measurement lock and target injections.
    4. MONITOR: Queries matching existing tools at pos < 4 or pos > 20, or queries
       with exploratory impressions below qualification floor.
    5. BUILD_PAGE: Genuinely underserved statutory void queries with proven demand.
    Zero em-dashes. Zero en-dashes.
    """
    q_text = str(query_data.get("query", "")).strip()
    pos = float(query_data.get("position", 100.0))
    impr = int(float(query_data.get("impressions", 0)))
    clicks = int(float(query_data.get("clicks", 0)))

    # 1. Check competing pages (Consolidation)
    competing = query_data.get("competing_pages") or query_data.get("urls") or []
    if len(competing) > 1:
        return {
            "action": "CONSOLIDATE_PAGES",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "competing_pages": competing,
            "canonical_url": competing[0],
            "redirect_candidates": competing[1:],
            "reason": f"Multiple URLs ({len(competing)}) competing for query '{q_text}'",
        }

    # 2. Check zero impressions over 90 days (Pruning)
    days_observed = int(query_data.get("days", query_data.get("period_days", 0)))
    if impr == 0 and days_observed >= 90:
        return {
            "action": "PRUNE_PAGE",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "recommendation": "noindex_follow",
            "reason": f"0 impressions across {days_observed} days",
        }

    # 3. Match against existing tool catalog and cannibalization detection
    matching_tool = query_data.get("matching_tool")
    cannibal = check_search_intent_cannibalization(
        q_text,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
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
        if 4.0 <= pos <= 20.0:
            now = datetime.now(timezone.utc)
            lock_until = (now + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
            words = [w.capitalize() for w in q_text.split() if w]
            heading_title = " ".join(words) if words else "Overview & Statutory Analysis"

            overlay_spec = {
                "slug": matching_tool,
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

            return {
                "action": "REFACTOR_PAGE",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "matching_tool": matching_tool,
                "measurement_lock_days": 28,
                "overlay_spec": overlay_spec,
                "reason": f"Striking distance query (pos {pos}) matches existing tool '{matching_tool}'",
            }

        if pos < 4.0:
            return {
                "action": "MONITOR",
                "query": q_text,
                "position": pos,
                "impressions": impr,
                "matching_tool": matching_tool,
                "reason": f"Top-ranking position {pos} - preserve existing authority",
            }

        # pos > 20.0 matching existing tool
        return {
            "action": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "matching_tool": matching_tool,
            "reason": f"Position {pos} > 20 matches existing tool '{matching_tool}' - avoid cannibalizing URL bloat",
        }

    # 5. Distinct unserved query void: evaluate against Search Intent Doctrine
    dynamic_floor = max(2, min(25, int(0.05 * total_site_impressions)))

    # Impressions below qualification floor indicate exploratory testing by search engines
    if impr < dynamic_floor:
        return {
            "action": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "reason": f"Impressions ({impr}) below qualification floor ({dynamic_floor}) - Google testing existing page intent; monitor before building page",
        }

    # Deep ranking positions (> 20) with modest impressions indicate exploratory indexing
    if pos > 20.0 and impr < 50:
        return {
            "action": "MONITOR",
            "query": q_text,
            "position": pos,
            "impressions": impr,
            "reason": f"Position {pos} > 20 with exploratory impressions ({impr}) - monitor before building page",
        }

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

    return {
        "action": "BUILD_PAGE",
        "query": q_text,
        "position": pos,
        "impressions": impr,
        "candidate_spec": candidate_spec,
        "reason": f"Genuinely underserved query void (pos {pos}, impr {impr}) with no matching tool asset",
    }


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
    Raises ValueError if the candidate query cannibalizes existing tool catalog.
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

    cannibal = check_search_intent_cannibalization(query, existing_tools=existing_tools)

    if not cannibal.get("is_cannibalizing"):
        cand_slug = str(candidate_spec.get("slug", "")).strip()
        if cand_slug:
            cand_slug_clean = cand_slug.replace("-", " ")
            cannibal_slug = check_search_intent_cannibalization(cand_slug_clean, existing_tools=existing_tools)
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
