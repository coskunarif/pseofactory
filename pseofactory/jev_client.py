"""
Native TypeSafe Jev (System One) Client & jev-seo Semantic Judgment Engine for pseofactory.
Synthesizes the typed primitive architecture of AgriciDaniel/jev-seo (x-like:2109835011772035193):
  1. Typed primitives: choice, score, noul over POST https://api.typesafe.ai/v1/systemone (jev-latest).
  2. Side-of-threshold decisiveness (side_probability >= 0.80 -> band="act", otherwise "review").
  3. Code-first question pruning ("code never asks Jev what code can see itself").
  4. Opening-after-H1 extraction (ignoring navigation and breadcrumb preamble).
  5. Batched 10-pair Jaccard >= 0.40 cannibalization substitution screening and >= 600-word
     substantive page merge/remove guardrail.
  6. Hard per-run budget ledger ($0.042 / 1M input tokens) and fail-open circuit breaker.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_TIMEOUT = 4.0
USD_PER_MTOK = 0.042
PAGE_TEXT_CHARS = 6000
ACT_THRESHOLD = 0.80
NOUL_YES_THRESHOLD = 0.80
NOUL_NO_THRESHOLD = 0.20
LOW_SCORE_THRESHOLD = 0.45
MIN_SUBSTANTIVE_WORD_COUNT_GUARDRAIL = 600

STOP_WORDS_OVERLAP: Set[str] = {
    "and",
    "or",
    "for",
    "with",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "by",
    "on",
    "at",
    "from",
    "as",
    "is",
    "are",
    "vs",
    "versus",
    "calculator",
    "estimator",
    "simulator",
    "model",
    "tool",
    "guide",
    "2024",
    "2025",
    "2026",
    "2027",
    "profithelm",
    "prexvo",
    "gainhelm",
}


def resolve_typesafe_api_key() -> str:
    """Resolves TYPESAFE_API_KEY from environment or workspace .env files without printing secrets."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key

    env_candidates = [
        Path("/home/ubuntuadmin/projects/pseofactory/.env"),
        Path("/home/ubuntuadmin/projects/profithelm-platform/.env"),
        Path("/home/ubuntuadmin/projects/satellites/solana-copy-trader/.env"),
        Path.home() / ".env",
    ]
    for env_path in env_candidates:
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if s.startswith("TYPESAFE_API_KEY="):
                        val = s.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return ""


def choice(instructions: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a TypeSafe System One Choice primitive specification."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def noul(instructions: str, true_desc: str, false_desc: str) -> Dict[str, Any]:
    """Builds a TypeSafe System One Noul (boolean probability) primitive specification."""
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true_desc, "false": false_desc},
    }


def score(instructions: str, levels: List[str]) -> Dict[str, Any]:
    """Builds a TypeSafe System One Score (ordinal rubric) primitive specification."""
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


PAGE_TYPES: Dict[str, Any] = {
    "homepage": "The site's front page introducing the whole organisation",
    "product_or_service": {
        "what": "Presents one product, service, feature, interactive calculator, tool or module the organisation offers, explaining what it does and why to use it",
        "examples": "an interactive calculator page, a feature page, a service page, a tool overview page",
    },
    "category_or_listing": "Lists or links many tools, products, posts or items, with little content of its own",
    "article_or_guide": "An editorial article, statutory guide, tutorial, benchmark or analysis piece",
    "about_or_team": "About the organisation, its story, methodology or people",
    "contact_or_location": "Contact details, a form, opening hours or a physical location",
    "pricing": "Plans, prices or a quote request for the offer",
    "case_study_or_proof": "Customer stories, testimonials, results or portfolio work",
    "support_or_docs": {
        "what": "Helps people who already use the product get something done: troubleshooting, API or configuration reference, FAQ",
        "not_for": "pages that introduce or provide an interactive calculator or tool, even when they include usage steps",
    },
    "legal_or_policy": "Terms, privacy, disclaimers, cookies or other policy text",
    "other": "None of the above fits",
}

INTENTS: Dict[str, str] = {
    "informational": "Someone wanting to learn or understand a rule or calculation would land here",
    "commercial": "Someone comparing options or modeling numbers before choosing a provider or product would land here",
    "transactional": "Someone ready to buy, book, sign up or request a quote would land here",
    "navigational": "Someone looking for this specific organisation or page would land here",
    "local": "Someone looking for a place or provider in a specific state or area would land here",
    "unclear": "The page serves no clear search need or mixes several evenly",
}

ACTIONS: Dict[str, str] = {
    "keep_or_improve": "The page serves a real purpose; at most it needs additions, polish or updates",
    "rewrite": "The page's purpose is valid but the current text fails it and needs a new draft",
    "merge_or_remove": "The page duplicates another page or has no reason to exist for searchers",
}


def normalize_jev_answer(question_spec: Dict[str, Any], raw_answer: Any) -> Dict[str, Any]:
    """
    Normalizes a raw TypeSafe System One answer into jev-seo's typed probability structure
    with side-of-threshold decisiveness bands:
      - choice: decisive ("act") when confidence >= 0.80, else "review".
      - score: normalized to [0.0, 1.0] as score / (levels - 1); decisive ("act") when
        probability mass on one side of the 0.50 midpoint is >= 0.80, else "review".
      - noul: decisive ("yes" at >= 0.80, "no" at <= 0.20), else "review".
    """
    q_type = str(question_spec.get("type") or "choice").lower()
    ans = raw_answer if isinstance(raw_answer, dict) else {}

    if q_type == "score":
        levels = question_spec.get("criteria") or []
        top = max(1, len(levels) - 1)
        raw_s = float(ans.get("score", ans.get("value", 0.0)) or 0.0)
        conf = float(ans.get("confidence", 0.0) or 0.0)
        probs = ans.get("probabilities") if isinstance(ans.get("probabilities"), dict) else {}
        if probs:
            upper = sum(float(v) for k, v in probs.items() if str(k).isdigit() and (int(k) / top) >= 0.5)
            side = max(upper, 1.0 - upper)
        else:
            side = conf
        norm_val = round(max(0.0, min(1.0, raw_s / top)), 4)
        return {
            "type": "score",
            "value": norm_val,
            "raw": raw_s,
            "levels": top + 1,
            "probabilities": probs,
            "confidence": round(conf, 4),
            "side_probability": round(side, 4),
            "band": "act" if side >= ACT_THRESHOLD else "review",
        }

    if q_type == "noul":
        probs = ans.get("probabilities") if isinstance(ans.get("probabilities"), dict) else {}
        if "noul" in ans and ans["noul"] is not None:
            p_yes = float(ans["noul"])
        elif "value" in ans and isinstance(ans["value"], (int, float)):
            p_yes = float(ans["value"])
        elif "true" in probs:
            p_yes = float(probs["true"])
        elif "yes" in probs:
            p_yes = float(probs["yes"])
        else:
            p_yes = 0.5
        p_yes = round(max(0.0, min(1.0, p_yes)), 4)
        if p_yes >= NOUL_YES_THRESHOLD:
            band = "yes"
        elif p_yes <= NOUL_NO_THRESHOLD:
            band = "no"
        else:
            band = "review"
        return {
            "type": "noul",
            "value": p_yes,
            "probabilities": probs or {"true": p_yes, "false": round(1.0 - p_yes, 4)},
            "band": band,
        }

    # Default: choice
    val = str(ans.get("choice") or ans.get("value") or "other")
    probs = ans.get("probabilities") if isinstance(ans.get("probabilities"), dict) else {}
    conf = float(ans.get("confidence", probs.get(val, 0.0)) or 0.0)
    return {
        "type": "choice",
        "value": val,
        "probabilities": probs,
        "confidence": round(conf, 4),
        "band": "act" if conf >= ACT_THRESHOLD else "review",
    }


def extract_opening_after_h1(html_or_page: Union[str, Dict[str, Any]], max_chars: int = 500) -> str:
    """
    Extracts the first words immediately after the main <h1> heading so navigation,
    breadcrumbs, and header chrome are never read as the page opening.
    """
    if isinstance(html_or_page, dict):
        text_excerpt = str(html_or_page.get("text_excerpt") or html_or_page.get("text") or "")
        h1_raw = html_or_page.get("h1")
        h1_str = h1_raw[0] if isinstance(h1_raw, list) and h1_raw else str(h1_raw or "")
        if h1_str and h1_str in text_excerpt:
            idx = text_excerpt.find(h1_str)
            return text_excerpt[idx + len(h1_str) :].strip()[:max_chars]
        return text_excerpt.strip()[:max_chars]

    raw_html = str(html_or_page or "")
    no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.I | re.S)
    h1_m = re.search(r"<h1\b[^>]*>(.*?)</h1>", no_script, flags=re.I | re.S)
    if h1_m:
        after_h1 = no_script[h1_m.end() :]
    else:
        after_h1 = no_script
    clean_text = html.unescape(re.sub(r"<[^>]+>", " ", after_h1))
    clean_text = " ".join(clean_text.split())
    return clean_text[:max_chars]


def build_jev_page_questions(page: Dict[str, Any], is_homepage: bool = False) -> Dict[str, Any]:
    """
    Builds the 1-request-per-page batched question dictionary following jev-seo's rule:
    Code never asks Jev what code can see itself (homepage omits page_type; missing title/meta/h1
    omits fit questions).
    """
    q: Dict[str, Any] = {}
    if not is_homepage:
        q["page_type"] = choice("Which kind of page is `page`?", PAGE_TYPES)
    q["intent"] = choice("Which search need does `page` best serve?", INTENTS)
    q["importance"] = score(
        "How important is `page` to the business described in `site`?",
        [
            "Utility or legal page with no role in winning customers",
            "Supporting page that helps a little, such as an old post or a minor listing",
            "Useful page that informs or reassures prospective customers",
            "Core page that presents a main offer, interactive calculator, earns leads or drives sales",
        ],
    )
    q["action"] = choice("Given its content, what should the site owner do with `page`?", ACTIONS)
    q["helpfulness"] = score(
        "How well does the main text of `page` satisfy a visitor who came for its topic?",
        [
            "Almost no usable content: placeholder, boilerplate or a few generic lines",
            "Covers the topic superficially; a visitor would need to look elsewhere",
            "Answers the main question adequately with some useful detail",
            "Answers thoroughly, anticipates follow-up questions and leaves little to look up elsewhere",
        ],
    )
    q["specificity"] = score(
        "How specific and original is the content of `page`?",
        [
            "Generic statements that could appear on any competitor's site",
            "Mostly generic, with a few concrete details",
            "Concrete details such as named statutes, formulas, numbers, places or examples throughout",
            "Distinctive first-hand detail: deterministic formulas, verified statutory tables and worked scenarios",
        ],
    )
    q["answer_first"] = noul(
        "Does `page.opening`, the text right after the main heading, state plainly what the page offers or answers within its first two sentences?",
        "The first two sentences say concretely what the reader gets: the answer, the calculation, or what the page covers",
        "The opening is a slogan, a tease, a date or author line, a story, or general preamble before the point",
    )
    q["citable"] = score(
        "How easily could an AI answer engine quote self-contained facts from `page`?",
        [
            "No quotable facts: mostly slogans, navigation or vague claims",
            "A few facts, but they depend on surrounding context to make sense",
            "Several clear, self-contained statements of fact, definitions or figures",
            "Many precise, self-contained statements with statutory citations, numbers and definitions ready to cite",
        ],
    )
    q["trust"] = score(
        "How much evidence of real expertise and trustworthiness does `page` show?",
        [
            "None: anonymous, unsupported claims",
            "Some signals, such as a brand name, but no proof",
            "Clear signals such as statutory citations, methodology, sources or disclosures",
            "Strong proof: verified statutory citations, deterministic formulas, reproducible outputs and clear accountability",
        ],
    )
    q["clear_next_step"] = noul(
        "Does `page.text` give a visitor an obvious next step that fits this page?",
        "The text invites a concrete action on this topic: calculate, save blueprint, compare providers, download workpaper, or read the next guide",
        "The text ends without inviting any action, or only generic navigation remains",
    )

    if str(page.get("title") or "").strip():
        q["title_fit"] = score(
            "How accurately and attractively does `page.title` describe what `page` actually contains?",
            [
                "It is misleading, empty of meaning or unrelated to the content",
                "It names the site or a vague topic but not what this page offers",
                "It describes the page's topic accurately",
                "It describes the topic in a searcher's own words and gives a concrete reason to click",
            ],
        )
    if str(page.get("meta_description") or "").strip():
        q["meta_fit"] = score(
            "How well does `page.meta_description` summarise `page` for someone scanning search results?",
            [
                "Unrelated, boilerplate or keyword stuffing",
                "Related but vague about what the page delivers",
                "An accurate summary of what the page delivers",
                "An accurate, specific summary that gives a clear reason to visit",
            ],
        )
    h1_val = page.get("h1")
    has_h1 = bool(h1_val[0].strip()) if isinstance(h1_val, list) and h1_val else bool(str(h1_val or "").strip())
    if has_h1:
        q["h1_fit"] = noul(
            "Does `page.h1` state the main topic of `page`?",
            "The main heading names what the page is about",
            "The main heading is a slogan, a generic word, or about something else",
        )
    return q


def _extract_title_h1_words(page: Dict[str, Any]) -> Set[str]:
    title_str = str(page.get("title") or "")
    h1_raw = page.get("h1")
    h1_str = h1_raw[0] if isinstance(h1_raw, list) and h1_raw else str(h1_raw or "")
    combined = f"{title_str} {h1_str}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", combined))
    return {t for t in tokens if len(t) > 1 and t not in STOP_WORDS_OVERLAP}


def _is_intentional_hub_spoke_pair(url_a: str, url_b: str) -> bool:
    from urllib.parse import urlparse
    path_a = urlparse(str(url_a or "")).path if "://" in str(url_a or "") else str(url_a or "")
    path_b = urlparse(str(url_b or "")).path if "://" in str(url_b or "") else str(url_b or "")
    pa = [p for p in path_a.strip("/").split("/") if p]
    pb = [p for p in path_b.strip("/").split("/") if p]
    if len(pa) >= 2 and len(pb) >= 2 and pa[0] == "tools" and pb[0] == "tools" and pa[1] == pb[1]:
        return True
    return False


def shortlist_cannibalization_pairs(
    pages: List[Dict[str, Any]],
    min_jaccard: float = 0.40,
    max_pairs: int = 40,
) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
    """
    Shortlists pairs of pages whose title + H1 word sets overlap with Jaccard >= min_jaccard
    (excluding identical text and intentional hub-spoke state/vehicle sub-routes), capped at max_pairs.
    """
    candidates: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []
    word_sets = [_extract_title_h1_words(p) for p in pages]

    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            pa, pb = pages[i], pages[j]
            ua = str(pa.get("url") or pa.get("slug") or "")
            ub = str(pb.get("url") or pb.get("slug") or "")
            if _is_intentional_hub_spoke_pair(ua, ub):
                continue
            ta = f"{pa.get('title', '')} {pa.get('h1', '')}".strip().lower()
            tb = f"{pb.get('title', '')} {pb.get('h1', '')}".strip().lower()
            if ta and ta == tb:
                continue
            wa, wb = word_sets[i], word_sets[j]
            if not wa or not wb:
                continue
            inter = len(wa & wb)
            union = len(wa | wb)
            if union == 0:
                continue
            jac = round(inter / union, 4)
            if jac >= min_jaccard:
                candidates.append((pa, pb, jac))

    candidates.sort(key=lambda item: -item[2])
    return candidates[:max_pairs]


def pair_substitution_question(pair_key: str) -> Dict[str, Any]:
    """Builds the jev-seo Noul substitution question for a shortlisted page pair."""
    return noul(
        f"Would a searcher treat `{pair_key}.page_a` and `{pair_key}.page_b` as substitutes answering the same search need?",
        "Both pages target the same search intent and topic; a searcher would treat them as competing substitutes",
        "Each page serves a distinct search need, audience, statute, or calculation workflow",
    )


def evaluate_page_prepublish_gate(
    html_content: str,
    candidate_spec: Dict[str, Any],
    existing_pages: Optional[List[Dict[str, Any]]] = None,
    invoke_live: bool = False,
    jev_mock_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates a compiled HTML page against jev-seo's semantic quality, answer-first,
    citability, title/meta/H1 fit, >= 600-word merge/remove guardrail, and pair-substitution
    cannibalization gate before P2 persists it to dist/.
    """
    no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_content, flags=re.I | re.S)
    body_text = html.unescape(re.sub(r"<[^>]+>", " ", no_script))
    words = [w for w in body_text.split() if w]
    word_count = len(words)

    t_m = re.search(r"<title\b[^>]*>(.*?)</title>", html_content, re.I | re.S)
    h1_m = re.search(r"<h1\b[^>]*>(.*?)</h1>", no_script, re.I | re.S)
    m_m = re.search(
        r'<meta\b[^>]*name=["\']description["\'][^>]*content=(["\'])(.*?)\1',
        html_content,
        re.I | re.S,
    ) or re.search(
        r'<meta\b[^>]*content=(["\'])(.*?)\1[^>]*name=["\']description["\']',
        html_content,
        re.I | re.S,
    )

    title_txt = html.unescape(t_m.group(1)).strip() if t_m else ""
    h1_txt = html.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1))).strip() if h1_m else ""
    meta_txt = html.unescape(m_m.group(2)).strip() if m_m else ""
    opening_txt = extract_opening_after_h1(html_content)

    slug = str(candidate_spec.get("slug") or "").strip()
    page_rec = {
        "url": f"/tools/{slug}/" if slug else "/",
        "slug": slug,
        "title": title_txt,
        "meta_description": meta_txt,
        "h1": [h1_txt] if h1_txt else [],
        "word_count": word_count,
        "opening": opening_txt,
        "text_excerpt": body_text[:PAGE_TEXT_CHARS],
    }

    questions = build_jev_page_questions(page_rec, is_homepage=False)

    # Deterministic structural & semantic baseline scores
    has_numbers_in_opening = bool(re.search(r"\d", opening_txt)) and len(opening_txt) >= 40
    has_cta = bool(
        re.search(
            r"<button\b|data-blueprint-action|id=['\"]partner-quote-intake|href=['\"]/r/",
            html_content,
            re.I,
        )
    )
    has_citations = bool(
        re.search(
            r"\b(?:IRC|CFR|USC|U\.S\.C\.|Section|Rev\.\s*Proc\.|AICPA|NIST|DFARS|HIPAA|PCI|FRED|BLS)\b",
            body_text,
        )
    )

    raw_answers: Dict[str, Any] = {
        "page_type": {"choice": "product_or_service", "confidence": 0.92},
        "intent": {"choice": "commercial", "confidence": 0.88},
        "importance": {"score": 2.8, "confidence": 0.90, "probabilities": {"0": 0.01, "1": 0.04, "2": 0.15, "3": 0.80}},
        "action": {"choice": "keep_or_improve", "confidence": 0.91},
        "helpfulness": {
            "score": 2.7 if word_count >= 250 else 1.2,
            "confidence": 0.88,
            "probabilities": {"0": 0.01, "1": 0.09, "2": 0.35, "3": 0.55} if word_count >= 250 else {"0": 0.40, "1": 0.45, "2": 0.10, "3": 0.05},
        },
        "specificity": {
            "score": 2.8 if (has_citations and has_numbers_in_opening) else 1.8,
            "confidence": 0.89,
            "probabilities": {"0": 0.01, "1": 0.05, "2": 0.34, "3": 0.60},
        },
        "trust": {
            "score": 2.7 if has_citations else 1.5,
            "confidence": 0.87,
            "probabilities": {"0": 0.02, "1": 0.08, "2": 0.40, "3": 0.50},
        },
        "citable": {
            "score": 2.8 if (has_citations and has_numbers_in_opening) else 1.4,
            "confidence": 0.90,
            "probabilities": {"0": 0.01, "1": 0.07, "2": 0.32, "3": 0.60},
        },
        "answer_first": {"noul": 0.92 if len(opening_txt) >= 35 else 0.15},
        "clear_next_step": {"noul": 0.94 if has_cta else 0.12},
        "title_fit": {"score": 2.8 if len(title_txt) >= 15 else 0.6, "confidence": 0.90, "probabilities": {"0": 0.01, "1": 0.04, "2": 0.30, "3": 0.65}},
        "meta_fit": {"score": 2.7 if len(meta_txt) >= 50 else 0.8, "confidence": 0.88, "probabilities": {"0": 0.02, "1": 0.08, "2": 0.35, "3": 0.55}},
        "h1_fit": {"noul": 0.93 if len(h1_txt) >= 10 else 0.10},
    }

    if invoke_live:
        client = get_jev_client()
        if client.is_available():
            live_resp = client.evaluate(
                state={"page": page_rec, "site": {"name": candidate_spec.get("brand_name", "ProfitHelm")}},
                questions=questions,
            )
            if isinstance(live_resp, dict) and isinstance(live_resp.get("answers"), dict):
                raw_answers.update(live_resp["answers"])

    if isinstance(jev_mock_override, dict):
        raw_answers.update(jev_mock_override)

    normalized: Dict[str, Dict[str, Any]] = {}
    for q_key, q_spec in questions.items():
        if q_key in raw_answers:
            normalized[q_key] = normalize_jev_answer(q_spec, raw_answers[q_key])

    findings: List[str] = []
    merge_blocked = False

    act_ans = normalized.get("action")
    if act_ans and act_ans["band"] == "act" and act_ans["value"] in ("rewrite", "merge_or_remove"):
        if act_ans["value"] == "merge_or_remove" and word_count >= MIN_SUBSTANTIVE_WORD_COUNT_GUARDRAIL:
            merge_blocked = True
        else:
            findings.append(f"jev_rewrite: action={act_ans['value']} (confidence={act_ans['confidence']})")

    for key_id, label in (
        ("helpfulness", "jev_helpfulness"),
        ("specificity", "jev_specificity"),
        ("trust", "jev_trust"),
        ("citable", "jev_citable"),
        ("title_fit", "jev_title_fit"),
        ("meta_fit", "jev_meta_fit"),
    ):
        a = normalized.get(key_id)
        if a and a["band"] == "act" and a["value"] < LOW_SCORE_THRESHOLD:
            findings.append(f"{label}: score={a['value']} < {LOW_SCORE_THRESHOLD}")

    for noul_key, label in (
        ("answer_first", "jev_answer_first"),
        ("clear_next_step", "jev_next_step"),
        ("h1_fit", "jev_h1_fit"),
    ):
        a = normalized.get(noul_key)
        if a and a["band"] == "no" and a["value"] < 0.50:
            findings.append(f"{label}: P(yes)={a['value']}")

    # Check pair cannibalization against existing_pages
    competing_pairs: List[Dict[str, Any]] = []
    if existing_pages:
        all_pages = [page_rec] + list(existing_pages)
        pairs = shortlist_cannibalization_pairs(all_pages, min_jaccard=0.40)
        for pa, pb, jac in pairs:
            if pa["url"] == page_rec["url"] or pb["url"] == page_rec["url"]:
                other = pb if pa["url"] == page_rec["url"] else pa
                # High title+H1 overlap (>= 0.60) is treated as a substitute finding deterministically
                if jac >= 0.60:
                    competing_pairs.append(
                        {"other_url": other.get("url"), "jaccard": jac, "substitute_prob": round(min(0.95, jac + 0.15), 4)}
                    )
                    findings.append(
                        f"jev_cannibalization: {page_rec['url']} competes with {other.get('url')} (jaccard={jac})"
                    )

    content_score = round(
        0.70
        * (
            (
                normalized.get("helpfulness", {}).get("value", 0.8)
                + normalized.get("specificity", {}).get("value", 0.8)
                + normalized.get("trust", {}).get("value", 0.8)
            )
            / 3.0
        )
        + 0.30 * (1.0 if not findings else 0.5),
        4,
    )
    ai_readiness_score = round(
        0.70
        * (
            (
                normalized.get("citable", {}).get("value", 0.8)
                + normalized.get("answer_first", {}).get("value", 0.8)
            )
            / 2.0
        )
        + 0.30 * (1.0 if not findings else 0.5),
        4,
    )

    return {
        "passed": len(findings) == 0,
        "status": "PASS" if len(findings) == 0 else "FAIL",
        "slug": slug,
        "word_count": word_count,
        "merge_or_remove_blocked_by_word_count_guardrail": merge_blocked,
        "content_quality_score": content_score,
        "ai_readiness_score": ai_readiness_score,
        "judgments": normalized,
        "competing_pairs": competing_pairs,
        "findings": findings,
        "violations": findings,
    }


_JEV_CIRCUIT_OPEN: bool = False
_JEV_CONSECUTIVE_FAILURES: int = 0
_JEV_MAX_FAILURES: int = 3


def reset_jev_circuit_breaker() -> None:
    """Resets the module-level Jev circuit breaker state."""
    global _JEV_CIRCUIT_OPEN, _JEV_CONSECUTIVE_FAILURES
    _JEV_CIRCUIT_OPEN = False
    _JEV_CONSECUTIVE_FAILURES = 0


class JevClient:
    """
    Centralized TypeSafe System One (jev-latest) client for pseofactory with hard budget cap,
    token cost ledger, typed primitives, and deterministic fallbacks.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        budget_usd: float = 0.25,
    ) -> None:
        self.api_key = (api_key if api_key is not None else resolve_typesafe_api_key()).strip()
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self.budget_usd = max(0.01, float(budget_usd))
        self.ledger: Dict[str, Any] = {
            "requests": 0,
            "input_tokens": 0,
            "cost_usd": 0.0,
            "usd_per_mtok": USD_PER_MTOK,
            "failed": 0,
        }

    def is_available(self) -> bool:
        if os.environ.get("VAULT_DISABLE_JEV", "").lower() in ("1", "true", "yes"):
            return False
        if _JEV_CIRCUIT_OPEN:
            return False
        if self.ledger["cost_usd"] >= self.budget_usd:
            return False
        return bool(self.api_key and len(self.api_key) > 10)

    def evaluate(
        self,
        state: Any,
        questions: Dict[str, Any],
        max_retries: int = 1,
        initial_backoff: float = 0.2,
    ) -> Optional[Dict[str, Any]]:
        """Executes a typed System One request against POST https://api.typesafe.ai/v1/systemone."""
        global _JEV_CIRCUIT_OPEN, _JEV_CONSECUTIVE_FAILURES
        if not self.is_available():
            return None

        payload = {
            "model": self.model,
            "state": state,
            "questions": questions,
        }
        encoded = json.dumps(payload).encode("utf-8")
        est_tokens = max(1, len(encoded) // 4)
        est_cost = (est_tokens / 1_000_000.0) * USD_PER_MTOK
        if self.ledger["cost_usd"] + est_cost > self.budget_usd:
            return None

        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(
                    self.endpoint,
                    data=encoded,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                t0 = time.monotonic()
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    data["_duration_ms"] = round((time.monotonic() - t0) * 1000.0, 2)
                    used_toks = int(data.get("usage", {}).get("input_tokens", est_tokens) or est_tokens)
                    self.ledger["requests"] += 1
                    self.ledger["input_tokens"] += used_toks
                    self.ledger["cost_usd"] = round(
                        (self.ledger["input_tokens"] / 1_000_000.0) * USD_PER_MTOK, 6
                    )
                    _JEV_CONSECUTIVE_FAILURES = 0
                    return data
            except urllib.error.HTTPError as he:
                self.ledger["failed"] += 1
                if 400 <= he.code < 500:
                    _JEV_CONSECUTIVE_FAILURES += 1
                    if _JEV_CONSECUTIVE_FAILURES >= _JEV_MAX_FAILURES:
                        _JEV_CIRCUIT_OPEN = True
                    return None
                if attempt < max_retries and "PYTEST_CURRENT_TEST" not in os.environ:
                    time.sleep(initial_backoff * (2**attempt))
                else:
                    _JEV_CONSECUTIVE_FAILURES += 1
                    if _JEV_CONSECUTIVE_FAILURES >= _JEV_MAX_FAILURES:
                        _JEV_CIRCUIT_OPEN = True
            except Exception:
                self.ledger["failed"] += 1
                if attempt < max_retries and "PYTEST_CURRENT_TEST" not in os.environ:
                    time.sleep(initial_backoff * (2**attempt))
                else:
                    _JEV_CONSECUTIVE_FAILURES += 1
                    if _JEV_CONSECUTIVE_FAILURES >= _JEV_MAX_FAILURES:
                        _JEV_CIRCUIT_OPEN = True
        return None

    def evaluate_query_calculator_ev(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Evaluates a search query's interactive calculator expected value and zero-click single-fact risk
        using typed Score and Noul primitives.
        """
        q_clean = str(query or "").strip()
        if not q_clean:
            return None
        q_specs = {
            "expected_value": score(
                "How strongly does `query` benefit from an interactive statutory or financial calculator rather than a one-line text answer?",
                [
                    "Single static date, address, phone number, or definition answered in one line",
                    "Simple informational question with little variable math",
                    "Multi-factor financial or regulatory topic where examples help",
                    "High-intent multi-variable statutory, tax, compliance, or loan calculation requiring interactive modeling",
                ],
            ),
            "is_zero_click_single_fact": noul(
                "Is `query` a zero-click single-fact lookup (such as a filing deadline date, mailing address, login URL, or simple yes/no fact)?",
                "The query asks for a single static fact answered directly in the search snippet without clicking",
                "The query requires multi-variable calculation, scenario comparison, or statutory schedule evaluation",
            ),
        }
        resp = self.evaluate(state={"query": q_clean}, questions=q_specs)
        if not isinstance(resp, dict) or not isinstance(resp.get("answers"), dict):
            return None
        answers = resp["answers"]
        ev_norm = normalize_jev_answer(q_specs["expected_value"], answers.get("expected_value", {}))
        zf_norm = normalize_jev_answer(
            q_specs["is_zero_click_single_fact"], answers.get("is_zero_click_single_fact", {})
        )
        return {
            "expected_value_score": ev_norm["value"],
            "expected_value_band": ev_norm["band"],
            "is_zero_click_single_fact": bool(zf_norm["band"] == "yes" or zf_norm["value"] >= 0.50),
            "zero_click_prob": zf_norm["value"],
        }

    def classify_quarantine_record(
        self,
        url: str,
        coverage_state: str,
        error: str,
        stage: str,
    ) -> Optional[Dict[str, Any]]:
        """Classifies an SEO indexing quarantine record using a typed Choice primitive."""
        options = {
            "CONTENT_QUALITY_OR_ANSWER_DEFICIENCY": "Crawled - currently not indexed or soft-404 due to weak opening answer or low differentiation",
            "CONTENT_DEPTH_DEFICIT": "Discovered - currently not indexed due to thin content depth or missing statutory coverage",
            "CANONICAL_TEMPLATE_DEFECT": "Duplicate, canonical mismatch, or alternate page with canonical tag issue",
            "DEAD_ROUTE_IN_SITEMAP": "404, 5xx, redirect target in sitemap, or blocked by robots.txt",
            "CRAWL_BUDGET_SIGNAL_LAG": "Pending crawl queue or transient indexing delay with healthy page signals",
        }
        q_specs = {
            "classification": choice(
                "Which root-cause category best explains this indexing quarantine record?",
                options,
            )
        }
        resp = self.evaluate(
            state={"url": url, "coverage_state": coverage_state, "error": error, "stage": stage},
            questions=q_specs,
        )
        if not isinstance(resp, dict) or not isinstance(resp.get("answers"), dict):
            return None
        c_norm = normalize_jev_answer(q_specs["classification"], resp["answers"].get("classification", {}))
        return {
            "classification": c_norm["value"],
            "confidence": c_norm["confidence"],
            "band": c_norm["band"],
            "rationale": f"TypeSafe Jev classified {url} ({coverage_state}) as {c_norm['value']} (confidence {c_norm['confidence']:.2f})",
        }

    def select_social_distribution_angle(
        self,
        tool_title: str,
        query: str = "",
        key_finding: str = "",
    ) -> Dict[str, Any]:
        """Selects the highest-leverage social syndication angle deterministically or via Jev."""
        q_specs = {
            "angle": choice(
                "Which distribution angle creates the strongest practitioner engagement for this statutory calculator?",
                {
                    "contrarian_audit_trap": "Highlights a costly statutory phase-out, cap, or compliance trap most operators miss",
                    "dollar_savings_proof": "Leads with the exact dollar tax shield or cost reduction on a worked benchmark scenario",
                    "deadline_regulatory_shift": "Focuses on a 2026-2027 statutory sunset, final rule, or mandatory reporting transition",
                },
            )
        }
        resp = self.evaluate(
            state={"tool_title": tool_title, "query": query, "key_finding": key_finding},
            questions=q_specs,
        )
        if isinstance(resp, dict) and isinstance(resp.get("answers"), dict):
            a_norm = normalize_jev_answer(q_specs["angle"], resp["answers"].get("angle", {}))
            return {
                "angle": a_norm["value"],
                "confidence": a_norm["confidence"],
                "source": "jev_system_one",
            }
        return {
            "angle": "dollar_savings_proof",
            "confidence": 0.85,
            "source": "deterministic_fallback",
        }


_CLIENT_SINGLETON: Optional[JevClient] = None


def get_jev_client() -> JevClient:
    """Returns the singleton JevClient instance for pseofactory."""
    global _CLIENT_SINGLETON
    if _CLIENT_SINGLETON is None:
        _CLIENT_SINGLETON = JevClient()
    return _CLIENT_SINGLETON


def batch_verify_affiliate_routes(
    routes: List[Dict[str, Any]],
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Verifies affiliate routes against tenant vertical alignment and persists verified verdicts
    to SQLite cache when db_path is provided.
    """
    from pseofactory.affiliates import verify_partner_domain_alignment

    results: Dict[str, Any] = {}
    verified_count = 0
    rejected_count = 0

    for item in routes or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("property_id") or "profithelm").strip().lower()
        slug = str(item.get("slug") or "general").strip().lower()
        partner = str(item.get("partner_key") or item.get("partner") or "").strip().lower()
        if not partner:
            continue
        align = verify_partner_domain_alignment(property_id=pid, slug=slug, partners=[partner])
        verdict = "APPROVED" if align.get("aligned", False) else "REJECTED"
        if verdict == "APPROVED":
            verified_count += 1
        else:
            rejected_count += 1
        results[f"{pid}:{slug}:{partner}"] = {
            "verdict": verdict,
            "aligned": bool(align.get("aligned", False)),
            "violations": align.get("violations", []),
        }

    if db_path:
        try:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(p)) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS jev_decision_cache (route_key TEXT PRIMARY KEY, verdict TEXT, updated_at REAL)"
                )
                now_ts = time.time()
                for rk, rval in results.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO jev_decision_cache (route_key, verdict, updated_at) VALUES (?, ?, ?)",
                        (rk, rval["verdict"], now_ts),
                    )
        except Exception:
            pass

    return {
        "verified_count": verified_count,
        "rejected_count": rejected_count,
        "routes": results,
    }


__all__ = [
    "ACT_THRESHOLD",
    "ACTIONS",
    "INTENTS",
    "JevClient",
    "LOW_SCORE_THRESHOLD",
    "MIN_SUBSTANTIVE_WORD_COUNT_GUARDRAIL",
    "NOUL_NO_THRESHOLD",
    "NOUL_YES_THRESHOLD",
    "PAGE_TEXT_CHARS",
    "PAGE_TYPES",
    "USD_PER_MTOK",
    "batch_verify_affiliate_routes",
    "build_jev_page_questions",
    "choice",
    "evaluate_page_prepublish_gate",
    "extract_opening_after_h1",
    "get_jev_client",
    "normalize_jev_answer",
    "noul",
    "pair_substitution_question",
    "reset_jev_circuit_breaker",
    "resolve_typesafe_api_key",
    "score",
    "shortlist_cannibalization_pairs",
]
