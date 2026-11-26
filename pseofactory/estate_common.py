"""
Shared estate compilation utilities for consolidated pseofactory tenants.
Provides deterministic directory scaffolding, deployed void enrichment, sitemaps,
robots.txt, machine endpoints, Cloudflare edge functions, overlay hygiene,
Porcelain shell finalization, and substrate lock ledger updates.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import copy
import html
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from pseofactory.contracts import assert_no_forbidden_dashes, normalize_statutory_acronym_casing


def _normalize_overlay_statutory_casing(val: Any) -> Any:
    """Normalizes statutory acronym casing across overlay string, list, and dict values."""
    if isinstance(val, str):
        return normalize_statutory_acronym_casing(val)
    if isinstance(val, list):
        return [_normalize_overlay_statutory_casing(item) for item in val]
    if isinstance(val, dict):
        return {k: _normalize_overlay_statutory_casing(v) for k, v in val.items()}
    return val


def prepare_estate_dirs(output_dir: Any, property_id: str) -> Tuple[Path, Path, Path]:
    """Creates dist/, tools/, manifests/, governance, and CSS output folders."""
    from pseofactory.porcelain_shell import generate_porcelain_stylesheet

    root = Path(output_dir).resolve()
    dist = root / "dist"
    tools_dir = dist / "tools"
    manifests_dir = dist / "manifests"
    disclaimers_dir = dist / "disclaimers"
    methodology_dir = dist / "methodology"
    css_dir = dist / "css"
    static_css_dir = dist / "static" / "css"
    for d in (dist, tools_dir, manifests_dir, disclaimers_dir, methodology_dir, css_dir, static_css_dir):
        d.mkdir(parents=True, exist_ok=True)

    style_css_content = generate_porcelain_stylesheet(property_id)
    (css_dir / "style.css").write_text(style_css_content, encoding="utf-8")
    (static_css_dir / "style.css").write_text(style_css_content, encoding="utf-8")
    return root, dist, tools_dir


_LIENBOND_WC_REPLACEMENT_AUTHORITY = (
    "NCCI Basic Manual Class Codes, NCCI Experience Rating Plan Manual, "
    "and State Workers Compensation Rating Bureaus"
)

_LIENBOND_WC_CONCISE_AUTHORITY = "NCCI Basic Manual"

_LIENBOND_WC_FORBIDDEN_CITATION_RE = re.compile(
    r"(?:"
    r"(?:IRC|26\s*U\.S\.C\.?)\s*(?:Section|Sec\.?)?\s*3111\b"
    r"|40\s*U\.S\.C\.?\s*(?:Section|Sec\.?)?\s*3131(?:-\d+)?\b"
    r"|40\s*U\.S\.C\.?\s*(?:Section|Sec\.?)?\s*3133\b(?:\([a-zA-Z0-9]+\))?"
    r"|29\s*CFR\s*(?:Part\s*)?1904\b"
    r"|FAR\s*28\.102(?:-2|-1)?\b"
    r"|FAR\s*28\.101\b"
    r"|(?:Federal\s+)?Miller\s+Act(?:\s*\([^)]*\))?"
    r")",
    re.IGNORECASE,
)


def _is_lienbond_wc_slug(slug: str) -> bool:
    """Returns True for LienBond workers compensation, EMR, or class-code tool slugs."""
    s_low = str(slug or "").strip().lower()
    return any(tok in s_low for tok in ("workers-comp", "emr", "class-code"))


def _scrub_lienbond_wc_citations(val: Any, *, key_name: str = "") -> Any:
    """Recursively scrubs non-NCCI citations from LienBond workers-comp/EMR specs and overlays."""
    if isinstance(val, str):
        if key_name in ("href", "target_url", "slug", "canonical_url", "url", "anchor"):
            return val
        if _LIENBOND_WC_FORBIDDEN_CITATION_RE.search(val):
            if key_name in ("meta_description", "description"):
                scrubbed = _LIENBOND_WC_FORBIDDEN_CITATION_RE.sub(_LIENBOND_WC_CONCISE_AUTHORITY, val)
                if len(scrubbed) > 155:
                    scrubbed = _LIENBOND_WC_FORBIDDEN_CITATION_RE.sub("NCCI rules", val)
                if len(scrubbed) > 155:
                    scrubbed = scrubbed[:152].rsplit(" ", 1)[0].rstrip(".,;:") + "."
                return scrubbed
            return _LIENBOND_WC_FORBIDDEN_CITATION_RE.sub(_LIENBOND_WC_REPLACEMENT_AUTHORITY, val)
        return val
    if isinstance(val, list):
        return [_scrub_lienbond_wc_citations(item, key_name=key_name) for item in val]
    if isinstance(val, dict):
        return {k: _scrub_lienbond_wc_citations(v, key_name=k) for k, v in val.items()}
    return val


def _normalize_lienbond_bid_bond_void(
    dv: Dict[str, Any],
    cm: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalizes stale license-bond Bid Bond void entries to canonical FAR 28.101 Bid Guarantees."""
    raw_formula = str(dv.get("formula") or cm.get("formula") or "")
    raw_inputs = dict(dv.get("inputs") or cm.get("inputs") or {})
    needs_fix = (
        "bond_amount" in raw_inputs
        or "credit_tier_rate_pct" in raw_inputs
        or "bond_amount" in raw_formula
        or "credit_tier_rate_pct" in raw_formula
        or "contract_bid_amount" not in raw_inputs
        or "penal_sum_pct" not in raw_inputs
    )
    if not needs_fix:
        return dv, cm

    expr = "round(contract_bid_amount * (min(20.0, max(5.0, penal_sum_pct)) / 100.0), 2)"
    try:
        from pseofactory.truth_pack import load_truth_pack

        tp = load_truth_pack("lienbond", allow_expired=True)
        bb_spec = tp.formulas.get("bid_bond")
        if bb_spec is not None and bb_spec.expression:
            expr = bb_spec.expression
    except Exception:
        pass

    canon_inputs = {"contract_bid_amount": 1000000.0, "penal_sum_pct": 10.0}
    canon_output = 100000.0
    canon_authority = "48 CFR 28.101 (FAR 28.101 Bid Guarantees)"
    canon_model = "Federal / Commercial Bid Bond Penal Sum (FAR 28.101)"
    canon_sample = (
        "$1,000,000.00 contract bid amount * 10.0% FAR 28.101 bid guarantee penal sum "
        "= $100,000.00 bid bond penal sum."
    )
    canon_desc = (
        "Calculate construction bid bond penal sums (5% to 20% of bid) and surety bid "
        "guarantee exposure under 48 CFR 28.101 (FAR 28.101 Bid Guarantees)."
    )

    dv_clean = dict(dv)
    cm_clean = dict(cm)
    for target in (dv_clean, cm_clean):
        target["formula"] = expr
        target["inputs"] = dict(canon_inputs)
        target["published_output"] = canon_output
        target["statutory_authority"] = canon_authority
        target["model_name"] = canon_model
        target["sample_calculation"] = canon_sample
    dv_clean["description"] = canon_desc
    dv_clean.pop("quick_answer", None)
    dv_clean.pop("faqs", None)
    return dv_clean, cm_clean


def load_and_enrich_deployed_voids(
    repo_root: Path,
    property_id: str,
    domain: str,
    brand_name: str,
    canonical_base: str,
    known_slugs: Set[str],
    default_authority: str,
    default_dataset: str,
) -> List[Dict[str, Any]]:
    """Loads content/deployed_voids.json (or .agy/deployed_voids.json) entries not already compiled and enriches them."""
    dv_file = repo_root / "content" / "deployed_voids.json"
    if not dv_file.is_file():
        agy_dv_file = repo_root / ".agy" / "deployed_voids.json"
        if agy_dv_file.is_file():
            dv_file = agy_dv_file
        else:
            return []
    try:
        loaded_dv = json.loads(dv_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(loaded_dv, list):
        return []

    from pseofactory.pipeline import CompetitorGapEngine, TenantFactStore
    from pseofactory.qualification import detect_non_us_jurisdiction

    norm_prop = str(property_id or "").strip().lower()
    profile = TenantFactStore.get_instance().get_profile(property_id)
    gap_engine = CompetitorGapEngine(tenant_profile=profile)
    enriched_voids: List[Dict[str, Any]] = []

    for dv in loaded_dv:
        if not isinstance(dv, dict):
            continue
        dv_slug = str(dv.get("slug") or "").strip().lower()
        if not dv_slug or dv_slug in known_slugs:
            continue
        cm = dv.get("calculation_manifest") if isinstance(dv.get("calculation_manifest"), dict) else {}
        if norm_prop == "lienbond":
            if "bid-bond" in dv_slug:
                dv, cm = _normalize_lienbond_bid_bond_void(dv, cm)
            elif _is_lienbond_wc_slug(dv_slug):
                dv = _scrub_lienbond_wc_citations(dv)
                cm = _scrub_lienbond_wc_citations(cm)
        dv_query = str(dv.get("query") or dv.get("primary_keyword") or dv_slug.replace("-", " ")).strip()
        dv_title = str(dv.get("title") or dv_query.title()).strip()
        dv_primary_kw = str(dv.get("primary_keyword") or dv_query).strip()
        if detect_non_us_jurisdiction(
            dv_query,
            property_id=property_id,
            spec={
                "slug": dv_slug,
                "query": dv_query,
                "primary_keyword": dv_primary_kw,
                "title": dv_title,
            },
        ):
            continue
        dv_spec: Dict[str, Any] = {
            "slug": dv_slug,
            "query": dv_query,
            "primary_keyword": dv_primary_kw,
            "title": dv_title,
            "short_title": str(dv.get("short_title") or dv_title[:24]).strip(),
            "description": str(dv.get("description") or "").strip(),
            "property_id": property_id,
            "tenant": property_id,
            "domain": domain,
            "brand_name": brand_name,
            "canonical_base": canonical_base,
            "statutory_authority": str(
                dv.get("statutory_authority") or cm.get("statutory_authority") or default_authority
            ),
            "economic_dataset": str(
                dv.get("economic_dataset") or cm.get("economic_dataset") or default_dataset
            ),
            "model_name": str(
                dv.get("model_name") or cm.get("model_name") or f"{dv_title} Underwriting Model"
            ),
            "formula": str(dv.get("formula") or cm.get("formula") or ""),
            "inputs": dict(dv.get("inputs") or cm.get("inputs") or {}),
            "published_output": dv.get("published_output", cm.get("published_output", 0.0)),
            "sample_calculation": str(
                dv.get("sample_calculation") or cm.get("sample_calculation") or ""
            ),
        }
        if dv.get("updated_date"):
            dv_spec["updated_date"] = str(dv["updated_date"])
        dv_spec = gap_engine.enrich_candidate_spec(dv_spec)
        if norm_prop == "lienbond" and _is_lienbond_wc_slug(dv_slug):
            dv_spec = _scrub_lienbond_wc_citations(dv_spec)
        enriched_voids.append(dv_spec)
        known_slugs.add(dv_slug)

    return enriched_voids


MANDATORY_ROBOTS_DISALLOW_PATHS: Tuple[str, ...] = ("/api/", "/cdn-cgi/")

LIVE_SEARCH_ALLOW_BOTS: Tuple[str, ...] = (
    "Googlebot",
    "Bingbot",
    "Applebot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
)

TRAINING_DISALLOW_BOTS: Tuple[str, ...] = (
    "GPTBot",
    "ClaudeBot",
    "anthropic-ai",
    "Claude-Web",
    "CCBot",
    "Bytespider",
    "Meta-ExternalAgent",
    "Applebot-Extended",
    "GoogleOther",
    "__usage_ai-training",
)

GOOGLE_EXTENDED_BOT: str = "Google-Extended"
GOOGLE_EXTENDED_DISALLOW_PATHS: Tuple[str, ...] = ("/workpapers/", "/datasets/")
_SITEMAP_SINGLE_FILE_THRESHOLD: int = 500


def _parse_robots_directive(raw_line: str) -> Tuple[str, str]:
    """Extracts normalized (directive_key_lower, value) from a robots.txt line, stripping comments."""
    code = raw_line.split("#", 1)[0].strip()
    if ":" not in code:
        return ("", "")
    key, val = code.split(":", 1)
    return (key.strip().lower(), val.strip())


def ensure_robots_txt_mandatory_disallows(
    robots_content: str,
    mandatory_disallows: Sequence[str] = MANDATORY_ROBOTS_DISALLOW_PATHS,
) -> str:
    """
    Ensures every User-agent group in robots.txt (including User-agent: * and every
    named crawler) explicitly disallows every mandatory path (/api/ and /cdn-cgi/)
    before any Allow directive in that group, while removing legacy Disallow: /r/ rules.

    Per RFC 9309, a named User-agent group completely overrides User-agent: * instead
    of inheriting wildcard disallows. Placing mandatory Disallow directives ahead of
    Allow directives also ensures consistent blocking in both RFC 9309 longest-match
    crawlers (Googlebot, Bingbot) and first-match parsers (urllib.robotparser).
    """
    mandatory_list: List[str] = []
    seen_mandatory: Set[str] = set()
    for p in mandatory_disallows:
        p_clean = str(p or "").strip()
        if p_clean and p_clean.lower() not in seen_mandatory:
            seen_mandatory.add(p_clean.lower())
            mandatory_list.append(p_clean)
    clean_content = robots_content.lstrip("\ufeff")
    if not mandatory_list:
        return clean_content

    lines = clean_content.splitlines()
    out_lines: List[str] = []
    has_wildcard_group = False
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        key, _val = _parse_robots_directive(raw)
        if key != "user-agent":
            out_lines.append(raw)
            i += 1
            continue

        header_lines: List[str] = []
        body_lines: List[str] = []
        seen_rule = False

        while i < n:
            cur = lines[i]
            cur_stripped = cur.strip()
            if not cur_stripped:
                break
            ck, cv = _parse_robots_directive(cur)
            if ck == "sitemap":
                break
            if ck == "user-agent":
                if seen_rule:
                    break
                header_lines.append(cur)
                if cv.lower() == "*":
                    has_wildcard_group = True
                i += 1
                continue
            if cur_stripped.startswith("#") and not seen_rule:
                # Attach comment between consecutive User-agent lines to header; otherwise body.
                j = i + 1
                while j < n and lines[j].strip().startswith("#"):
                    j += 1
                next_k = _parse_robots_directive(lines[j])[0] if j < n else ""
                if next_k == "user-agent":
                    header_lines.append(cur)
                else:
                    body_lines.append(cur)
                i += 1
                continue
            seen_rule = True
            body_lines.append(cur)
            i += 1

        remaining_body: List[str] = []
        for bl in body_lines:
            bk, bv = _parse_robots_directive(bl)
            if bk == "disallow" and bv.lower() in seen_mandatory:
                continue
            if bk == "disallow" and bv.lower() in ("/r/", "/r") and bv.lower() not in seen_mandatory:
                continue
            remaining_body.append(bl)

        out_lines.extend(header_lines)
        for m_path in mandatory_list:
            out_lines.append(f"Disallow: {m_path}")
        out_lines.extend(remaining_body)

    if not has_wildcard_group:
        prefix_block = ["User-agent: *"] + [f"Disallow: {m_path}" for m_path in mandatory_list]
        if any(l.strip() for l in out_lines):
            out_lines = prefix_block + [""] + out_lines
        else:
            out_lines = prefix_block

    result = "\n".join(out_lines).rstrip() + "\n"
    assert_no_forbidden_dashes(result, context="robots.txt")
    return result


def build_split_robots_txt(
    canonical_base: str,
    disallow_paths: Sequence[str] = ("/signal/", "/syndication/", "/staging/", "/test/", "/tests/"),
    allow_paths: Sequence[str] = ("/", "/tools/"),
    extra_bots: Optional[Sequence[str]] = None,
    sitemap_paths: Sequence[str] = ("/sitemap.xml",),
) -> str:
    """
    Builds split AI/search governance robots.txt:
    - User-agent: * and LIVE_SEARCH_ALLOW_BOTS -> Allow: / + standard Disallow (/api/, /cdn-cgi/, /signal/, etc.)
    - Google-Extended -> Disallow: /workpapers/, Disallow: /datasets/, Allow: / + standard Disallow
    - TRAINING_DISALLOW_BOTS -> Disallow: / (plus mandatory /api/, /cdn-cgi/, no Allow: /)
    Never emits Disallow: /r/.
    """
    base = canonical_base.rstrip("/")
    training_lower = {b.lower() for b in TRAINING_DISALLOW_BOTS}
    live_lower = {b.lower() for b in LIVE_SEARCH_ALLOW_BOTS}

    standard_disallows: List[str] = []
    seen_disallows: Set[str] = set()
    for p in list(MANDATORY_ROBOTS_DISALLOW_PATHS) + ["/signal/"] + list(disallow_paths):
        p_clean = str(p or "").strip()
        if not p_clean or p_clean.lower() in ("/r/", "/r"):
            continue
        if p_clean.lower() not in seen_disallows:
            seen_disallows.add(p_clean.lower())
            standard_disallows.append(p_clean)

    effective_allows: List[str] = []
    seen_allows: Set[str] = set()
    base_allows = ["/"] + (["/tools/"] if "/tools/" not in seen_disallows else [])
    for p in base_allows + list(allow_paths):
        p_clean = str(p or "").strip()
        if p_clean and p_clean.lower() not in seen_allows:
            seen_allows.add(p_clean.lower())
            effective_allows.append(p_clean)

    bot_blocks: List[str] = []

    def _emit_allow_block(agent: str, extra_disallows: Sequence[str] = ()) -> None:
        lines = [f"User-agent: {agent}"]
        block_disallows = list(standard_disallows)
        seen_bd = {d.lower() for d in block_disallows}
        for ed in extra_disallows:
            ed_clean = str(ed or "").strip()
            if ed_clean and ed_clean.lower() not in seen_bd:
                seen_bd.add(ed_clean.lower())
                block_disallows.append(ed_clean)
        for d_path in block_disallows:
            lines.append(f"Disallow: {d_path}")
        for a_path in effective_allows:
            lines.append(f"Allow: {a_path}")
        bot_blocks.append("\n".join(lines) + "\n")

    def _emit_training_disallow_block(agent: str) -> None:
        lines = [f"User-agent: {agent}"]
        for m_path in MANDATORY_ROBOTS_DISALLOW_PATHS:
            lines.append(f"Disallow: {m_path}")
        lines.append("Disallow: /")
        bot_blocks.append("\n".join(lines) + "\n")

    emitted_agents: Set[str] = set()
    _emit_allow_block("*")
    emitted_agents.add("*")

    # Emit more-specific disallow/extended tokens (e.g., Applebot-Extended, Google-Extended)
    # before shorter search tokens (e.g., Applebot) so both RFC 9309 longest-match and
    # first-match parsers (urllib.robotparser) resolve Applebot-Extended to Disallow: /.
    for bot in TRAINING_DISALLOW_BOTS:
        if bot.lower() not in emitted_agents:
            emitted_agents.add(bot.lower())
            _emit_training_disallow_block(bot)

    if GOOGLE_EXTENDED_BOT.lower() not in emitted_agents:
        emitted_agents.add(GOOGLE_EXTENDED_BOT.lower())
        _emit_allow_block(GOOGLE_EXTENDED_BOT, extra_disallows=GOOGLE_EXTENDED_DISALLOW_PATHS)

    for bot in LIVE_SEARCH_ALLOW_BOTS:
        if bot.lower() not in emitted_agents:
            emitted_agents.add(bot.lower())
            _emit_allow_block(bot)

    for raw_bot in extra_bots or ():
        b_clean = str(raw_bot or "").strip()
        if not b_clean or b_clean.lower() in emitted_agents:
            continue
        emitted_agents.add(b_clean.lower())
        if b_clean.lower() in training_lower:
            _emit_training_disallow_block(b_clean)
        elif b_clean.lower() == GOOGLE_EXTENDED_BOT.lower():
            _emit_allow_block(b_clean, extra_disallows=GOOGLE_EXTENDED_DISALLOW_PATHS)
        elif b_clean.lower() in live_lower:
            _emit_allow_block(b_clean)
        else:
            _emit_allow_block(b_clean)

    sitemap_lines: List[str] = []
    seen_sm: Set[str] = set()
    for sm in sitemap_paths:
        sm_clean = str(sm or "").strip()
        if not sm_clean:
            continue
        sm_path = sm_clean if sm_clean.startswith("/") else f"/{sm_clean}"
        if sm_path.lower() not in seen_sm:
            seen_sm.add(sm_path.lower())
            sitemap_lines.append(f"Sitemap: {base}{sm_path}")
    if not sitemap_lines:
        sitemap_lines.append(f"Sitemap: {base}/sitemap.xml")

    robots_txt = "\n".join(bot_blocks) + "\n" + "\n".join(sitemap_lines) + "\n"
    robots_txt = ensure_robots_txt_mandatory_disallows(robots_txt)
    assert_no_forbidden_dashes(robots_txt, context="robots.txt")
    return robots_txt


def write_sitemaps_and_robots(
    dist: Path,
    canonical_base: str,
    hub_specs: Sequence[Tuple[str, str, str]],
    leaf_tools: Sequence[Dict[str, Any]],
    ai_bots: Optional[Sequence[str]] = None,
    disallow_paths: Sequence[str] = ("/signal/", "/syndication/", "/staging/", "/test/", "/tests/"),
    allow_paths: Sequence[str] = ("/", "/tools/"),
    include_changefreq_and_priority: bool = False,
    validate_governor: bool = True,
) -> None:
    """
    Writes clean sitemap.xml (plus split hub/leaf sitemaps only when >=500 URLs, deleting
    stale split files for <500 URLs) and split governance robots.txt.
    Never emits <changefreq>, <priority>, or synthetic hub <lastmod> stamps.
    """
    _ = include_changefreq_and_priority  # Stripped globally per sitemap hygiene policy
    base = canonical_base.rstrip("/")

    hub_urls = [u for u, _, _ in hub_specs]
    leaf_urls = [f"{base}/tools/{t['slug']}/" for t in leaf_tools]
    all_urls = hub_urls + leaf_urls

    if len(all_urls) >= 10000:
        raise ValueError(f"Sitemap URL count {len(all_urls)} exceeds <10k cap.")

    allowed_hubs = set(hub_urls)
    if validate_governor:
        try:
            from pseofactory.indexer import SitemapGovernor

            SitemapGovernor.validate_batch(all_urls, max_batch_size=2000)
            gov_hubs, _ = SitemapGovernor.partition_batch(hub_urls, max_hub_cap=150)
            allowed_hubs = set(gov_hubs)
        except Exception:
            pass

    def _entry_xml(url: str, lastmod: Optional[str] = None) -> str:
        loc_esc = saxutils.escape(url)
        if lastmod:
            return f"  <url><loc>{loc_esc}</loc><lastmod>{saxutils.escape(lastmod[:10])}</lastmod></url>"
        return f"  <url><loc>{loc_esc}</loc></url>"

    hub_entries = [
        _entry_xml(url, lastmod=None)
        for url, _prio, _freq in hub_specs[:150]
        if url in allowed_hubs
    ]
    leaf_entries = [
        _entry_xml(
            f"{base}/tools/{t['slug']}/",
            lastmod=str(t.get("updated_date") or t.get("updated_at") or "").strip()[:10] or None,
        )
        for t in leaf_tools
    ]

    def _wrap_urlset(rows: List[str]) -> str:
        body = "\n".join(rows)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n"
            "</urlset>\n"
        )

    sitemap_xml = _wrap_urlset(hub_entries + leaf_entries)
    ET.fromstring(sitemap_xml)
    (dist / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")

    sitemap_paths: List[str] = ["/sitemap.xml"]
    if len(all_urls) >= _SITEMAP_SINGLE_FILE_THRESHOLD:
        sitemap_hubs_xml = _wrap_urlset(hub_entries)
        sitemap_leaves_xml = _wrap_urlset(leaf_entries)
        ET.fromstring(sitemap_hubs_xml)
        ET.fromstring(sitemap_leaves_xml)
        (dist / "sitemap-hubs.xml").write_text(sitemap_hubs_xml, encoding="utf-8")
        (dist / "sitemap-leaves.xml").write_text(sitemap_leaves_xml, encoding="utf-8")
        sitemap_paths.extend(["/sitemap-hubs.xml", "/sitemap-leaves.xml"])
    else:
        for stale_sm in ("sitemap-hubs.xml", "sitemap-leaves.xml"):
            (dist / stale_sm).unlink(missing_ok=True)

    robots_txt = build_split_robots_txt(
        canonical_base=base,
        disallow_paths=disallow_paths,
        allow_paths=allow_paths,
        extra_bots=ai_bots,
        sitemap_paths=sitemap_paths,
    )
    (dist / "robots.txt").write_text(robots_txt, encoding="utf-8")


_CATALOG_ALLOWED_KEYS: Tuple[str, ...] = ("slug", "title", "url", "category", "updated_at")
_CATALOG_DISALLOWED_KEYS: FrozenSet[str] = frozenset({
    "inputs",
    "formula",
    "published_output",
    "quick_answer",
    "query_syntax",
    "sample_calculation",
})


def _resolve_truthpack_modified_date(property_id: Optional[str]) -> str:
    """Resolves verified_at / data_modified_date ISO date from TruthPack, or today's UTC date."""
    pid = str(property_id or "").strip().lower()
    if pid:
        try:
            from pseofactory.truth_pack import load_truth_pack

            tp = load_truth_pack(pid, allow_expired=True)
            explicit_mod = str(getattr(tp, "data_modified_date", "") or "").strip()
            if explicit_mod:
                return explicit_mod[:10]
            dates = [
                str(getattr(ent, "verified_at", "") or "").strip()[:10]
                for ent in (getattr(tp, "entries", {}) or {}).values()
                if str(getattr(ent, "verified_at", "") or "").strip()
            ]
            if dates:
                return max(dates)
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize_iso_date_str(raw_date: Any, fallback_date: str) -> str:
    txt = str(raw_date or "").strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", txt)
    if m:
        return m.group(1)
    m_fb = re.match(r"^(\d{4}-\d{2}-\d{2})", str(fallback_date or ""))
    return m_fb.group(1) if m_fb else datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _format_rfc822_pub_date(raw_date: Any, fallback_date: str) -> str:
    iso_day = _normalize_iso_date_str(raw_date, fallback_date)
    try:
        dt = datetime.strptime(iso_day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return format_datetime(dt, usegmt=True)


def build_feed_scope_teaser(title: str, description: str, max_len: int = 220) -> str:
    """
    Produces a clean 1-sentence non-answer scope teaser for feed.xml (never sample_calculation,
    dollar outputs, or calculation results).
    """
    clean_title = str(title or "Interactive Calculator").replace("\u2014", "-").replace("\u2013", "-").strip()
    raw = str(description or "").replace("\u2014", "-").replace("\u2013", "-").strip()
    raw = re.sub(r"\s+", " ", raw)

    # Reject calculation dumps / dollar-output answers / yields clauses
    is_calc_dump = (
        not raw
        or "$" in raw
        or bool(re.search(r"\b(?:yields|produces|equals|saves|totals|generates)\b", raw, re.IGNORECASE))
    )
    if is_calc_dump:
        return f"Interactive modeling scope and statutory parameter inputs for {clean_title}."

    # Keep strictly 1 sentence
    sent_m = re.match(r"^(.+?[.!?])(?:\s+|$)", raw)
    sentence = sent_m.group(1).strip() if sent_m else raw
    if not sentence.endswith((".", "!", "?")):
        sentence = sentence.rstrip(",;:") + "."
    if len(sentence) > max_len:
        sentence = sentence[: max_len - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return sentence


def sanitize_public_catalog_tools(
    catalog_tools: Sequence[Dict[str, Any]],
    default_category: str = "calculator",
    default_updated_at: Optional[str] = None,
    property_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Sanitizes public catalog.json tool entries by stripping inputs, formula,
    published_output, quick_answer, and query_syntax and retaining only lightweight
    slug, title, url, category, updated_at fields.
    """
    fallback_date = default_updated_at or _resolve_truthpack_modified_date(property_id)
    cleaned: List[Dict[str, str]] = []
    for raw_tool in catalog_tools:
        if not isinstance(raw_tool, dict):
            continue
        slug = str(raw_tool.get("slug") or "").strip()
        if not slug:
            continue
        title = str(raw_tool.get("title") or slug.replace("-", " ").title()).replace("\u2014", "-").replace("\u2013", "-").strip()
        url = str(raw_tool.get("url") or "").strip()
        cat_raw = str(raw_tool.get("category") or raw_tool.get("cluster") or default_category or "calculator").strip()
        upd_raw = raw_tool.get("updated_at") or raw_tool.get("updated_date") or raw_tool.get("dateModified")
        updated_at = _normalize_iso_date_str(upd_raw, fallback_date)
        cleaned.append(
            {
                "slug": slug,
                "title": title,
                "url": url,
                "category": cat_raw,
                "updated_at": updated_at,
            }
        )
    return cleaned


def sanitize_public_catalog_file(dist: Path, property_id: Optional[str] = None) -> None:
    """In-place sanitizer guaranteeing dist/catalog.json exposes only lightweight metadata."""
    cat_path = dist / "catalog.json"
    if not cat_path.is_file():
        return
    try:
        raw_obj = json.loads(cat_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return
    if not isinstance(raw_obj, dict):
        return
    pid = str(raw_obj.get("property_id") or property_id or "").strip().lower()
    raw_tools = raw_obj.get("tools")
    if isinstance(raw_tools, list):
        clean_tools = sanitize_public_catalog_tools(
            raw_tools,
            default_category=pid or "calculator",
            property_id=pid or property_id,
        )
    else:
        clean_tools = []
    out_obj: Dict[str, Any] = {
        "property_id": raw_obj.get("property_id") or pid,
        "domain": raw_obj.get("domain") or "",
        "tools": clean_tools,
    }
    if pid == "prexvo":
        out_obj["disclosure"] = (
            "Refinancing federal student loans into a private loan permanently forfeits federal protections."
        )
    doc = json.dumps(out_obj, indent=2) + "\n"
    assert_no_forbidden_dashes(doc, context=f"{pid or 'tenant'} catalog.json")
    cat_path.write_text(doc, encoding="utf-8")


def write_machine_endpoints_and_headers(
    dist: Path,
    property_id: str,
    domain: str,
    canonical_base: str,
    feed_title: str,
    feed_description: str,
    feed_items: Sequence[Dict[str, str]],
    indexnow_key: str,
    catalog_tools: Sequence[Dict[str, Any]],
    media_kit_payload: Dict[str, Any],
    header_routes: Sequence[str],
    machine_endpoints: Optional[Sequence[str]] = None,
    static_patterns: Optional[Sequence[str]] = None,
    redirects_content: Optional[str] = None,
) -> None:
    """Writes feed.xml, IndexNow key, lightweight catalog.json, media-kit.json, _routes.json, _headers, and _redirects."""
    from pseofactory.edge import build_edge_headers, build_edge_routes_json, ensure_gone_rules_in_redirects

    base = canonical_base.rstrip("/")
    fallback_date = _resolve_truthpack_modified_date(property_id)
    channel_pub_date = _format_rfc822_pub_date(fallback_date, fallback_date)
    eff_feed_desc = str(feed_description or "").replace("\u2014", "-").replace("\u2013", "-").strip()
    if str(property_id or "").strip().lower() == "prexvo" and "permanently forfeits" not in eff_feed_desc.lower():
        eff_feed_desc = (
            f"{eff_feed_desc.rstrip('. ')}. Refinancing federal student loans into a private loan "
            "permanently forfeits federal protections."
        )

    rss_rows = "\n".join(
        f"    <item>\n"
        f"      <title>{saxutils.escape(str(item.get('title') or ''))}</title>\n"
        f"      <link>{saxutils.escape(str(item.get('url') or ''))}</link>\n"
        f"      <guid>{saxutils.escape(str(item.get('url') or ''))}</guid>\n"
        f"      <pubDate>{_format_rfc822_pub_date(item.get('pub_date') or item.get('updated_at') or item.get('updated_date'), fallback_date)}</pubDate>\n"
        f"      <description>{saxutils.escape(build_feed_scope_teaser(str(item.get('title') or ''), str(item.get('description') or '')))}</description>\n"
        f"    </item>"
        for item in feed_items
    )
    feed_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{saxutils.escape(feed_title)}</title>\n"
        f"    <link>{base}/</link>\n"
        f"    <description>{saxutils.escape(eff_feed_desc)}</description>\n"
        "    <language>en-US</language>\n"
        f"    <pubDate>{channel_pub_date}</pubDate>\n"
        f'    <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        f"{rss_rows}\n"
        "  </channel>\n"
        "</rss>\n"
    )
    assert_no_forbidden_dashes(feed_xml, context=f"{property_id} feed.xml")
    (dist / "feed.xml").write_text(feed_xml, encoding="utf-8")

    (dist / f"{indexnow_key}.txt").write_text(f"{indexnow_key}\n", encoding="utf-8")

    lightweight_tools = sanitize_public_catalog_tools(
        catalog_tools,
        default_category=str(property_id or "calculator").strip().lower(),
        default_updated_at=fallback_date,
        property_id=property_id,
    )
    catalog_payload: Dict[str, Any] = {
        "property_id": property_id,
        "domain": domain,
        "tools": lightweight_tools,
    }
    if str(property_id or "").strip().lower() == "prexvo":
        catalog_payload["disclosure"] = (
            "Refinancing federal student loans into a private loan permanently forfeits federal protections."
        )
    catalog_doc = json.dumps(catalog_payload, indent=2) + "\n"
    assert_no_forbidden_dashes(catalog_doc, context=f"{property_id} catalog.json")
    (dist / "catalog.json").write_text(catalog_doc, encoding="utf-8")

    media_kit_doc = json.dumps(media_kit_payload, indent=2)
    assert_no_forbidden_dashes(media_kit_doc, context=f"{property_id} media-kit.json")
    (dist / "media-kit.json").write_text(media_kit_doc, encoding="utf-8")

    edge_kwargs: Dict[str, Any] = {"routes": list(header_routes)}
    if machine_endpoints is not None:
        filtered_eps = []
        for ep in machine_endpoints:
            ep_norm = ep if ep.startswith("/") else f"/{ep}"
            if ep_norm == "/llms-full.txt":
                continue
            if ep_norm in ("/sitemap-hubs.xml", "/sitemap-leaves.xml") and not (dist / ep_norm.lstrip("/")).is_file():
                continue
            filtered_eps.append(ep)
        edge_kwargs["machine_endpoints"] = filtered_eps
    if static_patterns is not None:
        edge_kwargs["static_patterns"] = list(static_patterns)
    (dist / "_headers").write_text(build_edge_headers(base, **edge_kwargs), encoding="utf-8")
    (dist / "_routes.json").write_text(build_edge_routes_json(), encoding="utf-8")

    base_redirects = (
        redirects_content
        if redirects_content is not None
        else ((dist / "_redirects").read_text(encoding="utf-8", errors="ignore") if (dist / "_redirects").is_file() else "")
    )
    final_redirects = ensure_gone_rules_in_redirects(base_redirects)
    (dist / "_redirects").write_text(final_redirects, encoding="utf-8")

    # Purge zero-click leaking machine dumps
    (dist / "llms-full.txt").unlink(missing_ok=True)
    ai_benchmarks_dir = dist / "ai-benchmarks"
    if ai_benchmarks_dir.exists():
        shutil.rmtree(ai_benchmarks_dir, ignore_errors=True)


def build_edge_checkout_wrapper_js(query_flag: str) -> str:
    """Generates thin checkout.js or lead-fulfillment.js Cloudflare Function wrappers."""
    fn_name = "withCheckoutFlag" if query_flag == "checkout" else "withFulfillFlag"
    return (
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n\n'
        f"function {fn_name}(context) {{\n"
        "  const url = new URL(context.request.url);\n"
        f'  if (!url.searchParams.has("{query_flag}")) url.searchParams.set("{query_flag}", "1");\n'
        "  const req = new Request(url.toString(), context.request);\n"
        "  return { ...context, request: req };\n"
        "}\n\n"
        "export async function onRequestGet(context) {\n"
        f"  return lcGet({fn_name}(context));\n"
        "}\n\n"
        "export async function onRequestPost(context) {\n"
        f"  return lcPost({fn_name}(context));\n"
        "}\n\n"
        "export async function onRequestOptions(context) {\n"
        "  return lcOpt(context);\n"
        "}\n"
    )


def write_tenant_edge_functions(root: Path, dist: Path, property_id: str) -> Dict[str, Any]:
    """Syncs Cloudflare Pages Functions to root/functions and ensures dist/functions never leaks."""
    from pseofactory.edge import (
        generate_edge_stripe_webhook_function,
        sync_tenant_edge_redirect_function,
    )

    dist_functions = dist / "functions"
    if dist_functions.exists():
        shutil.rmtree(dist_functions, ignore_errors=True)

    (root / "functions" / "r").mkdir(parents=True, exist_ok=True)
    api_dir = root / "functions" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    sync_res = sync_tenant_edge_redirect_function(root, property_id=property_id)
    (api_dir / "checkout.js").write_text(build_edge_checkout_wrapper_js("checkout"), encoding="utf-8")
    (api_dir / "lead-fulfillment.js").write_text(build_edge_checkout_wrapper_js("fulfill"), encoding="utf-8")
    (api_dir / "stripe-webhook.js").write_text(
        generate_edge_stripe_webhook_function(property_id=property_id), encoding="utf-8"
    )
    return sync_res


_GAINHELM_FRAMEWORK_LEAK_GROUPS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (
        ("soc-2", "soc2", "ssae"),
        (
            "aicpa",
            "ssae 18",
            "at-c section",
            "at-c 205",
            "tsp section 100",
            "trust services criteria",
            "soc 2",
            "soc2",
            "78,100",
            "78100.40",
            "cpa attestation",
            "cpa or c3pao",
            "cpa firm",
        ),
    ),
    (
        ("cmmc", "sprs", "800-171"),
        (
            "32 cfr part 170",
            "dfars",
            "cmmc",
            "c3pao",
            "nist sp 800-171",
            "$132,000",
            "132,000.00",
            "132000",
        ),
    ),
    (
        ("hipaa", "hitech"),
        ("45 cfr 160", "hipaa", "2,190,294", "2,577,794"),
    ),
)


_OVERLAY_CONTENT_KEYS: Tuple[str, ...] = (
    "meta_description",
    "description",
    "title_rewrite",
    "title",
    "h1",
    "quick_answer",
    "methodology_notes",
    "summary",
    "h2_headings",
    "h2_blocks",
    "autonomous_citation_assertions",
    "ai_mode_decision_matrix",
    "comparison_rows",
    "preset_scenarios",
    "faq_entries",
    "faq_additions",
    "faq_schema",
    "partner_offer",
)


def _clean_gainhelm_offer_entry(
    entry: Dict[str, Any],
    slug_low: str,
    has_leak_fn: Any,
    fw_prof: Dict[str, Any],
    affiliates_mod: Any,
) -> Dict[str, Any]:
    """Rewrites cross-framework leaked copy inside a GainHelm partner offer or slot binding dict."""
    cleaned_entry = dict(entry)
    pk = str(cleaned_entry.get("partner_key") or "").strip().lower()
    is_soc2 = any(k in slug_low for k in ("soc-2", "soc2"))
    ctx_copy: Dict[str, Any] = {}
    if pk and affiliates_mod is not None:
        p_obj = affiliates_mod.GAINHELM_AFFILIATES.get(pk)
        if p_obj is not None:
            ctx_copy = affiliates_mod.resolve_contextual_partner_offer_copy(
                partner_key=pk,
                p_obj=p_obj,
                slug=slug_low,
                property_id="gainhelm",
            )
    if not is_soc2:
        for url_key in ("url", "default_url"):
            if "/products/soc-2" in str(cleaned_entry.get(url_key) or "").lower():
                cleaned_entry[url_key] = str(fw_prof.get("vanta_url") or "https://www.vanta.com/")
        fallback_map = {
            "name": str(ctx_copy.get("name") or "Automated GRC & Compliance Platform"),
            "partner_name": str(ctx_copy.get("name") or "Automated GRC & Compliance Platform"),
            "title": str(ctx_copy.get("badge") or ctx_copy.get("name") or "Automated GRC & Compliance Readiness"),
            "badge": str(ctx_copy.get("badge") or "Automated Compliance Readiness"),
            "description": str(
                ctx_copy.get("description")
                or "Automate continuous control evidence collection, vendor risk tracking, and audit readiness workflows."
            ),
            "cta_text": str(ctx_copy.get("cta_text") or "Explore Automated GRC Platforms"),
        }
        for txt_key, rep_val in fallback_map.items():
            cur_val = cleaned_entry.get(txt_key)
            if isinstance(cur_val, str) and cur_val and has_leak_fn(cur_val):
                cleaned_entry[txt_key] = rep_val
        disc_val = cleaned_entry.get("disclosure")
        if isinstance(disc_val, str) and disc_val and (has_leak_fn(disc_val) or "cpa/c3pao" in disc_val.lower()):
            cleaned_entry["disclosure"] = (
                "FTC Partner Compensation Disclosure: GainHelm is an independent security compliance "
                "research publisher and may receive referral compensation from vetted commercial partners "
                "at no additional cost to you."
            )
    for norm_txt_key in ("name", "partner_name", "title", "badge", "description", "cta_text", "disclosure"):
        if isinstance(cleaned_entry.get(norm_txt_key), str):
            cleaned_entry[norm_txt_key] = normalize_statutory_acronym_casing(cleaned_entry[norm_txt_key])
    for nested_list_key in ("secondary_offers", "ranked_partner_candidates", "roster_offers", "ordered_offers"):
        nested_list = cleaned_entry.get(nested_list_key)
        if isinstance(nested_list, list):
            cleaned_list: List[Any] = []
            for item in nested_list:
                if isinstance(item, dict):
                    cleaned_list.append(_clean_gainhelm_offer_entry(item, slug_low, has_leak_fn, fw_prof, affiliates_mod))
                elif isinstance(item, str) and not is_soc2 and (has_leak_fn(item) or "cpa/c3pao" in item.lower()):
                    continue
                else:
                    cleaned_list.append(item)
            cleaned_entry[nested_list_key] = cleaned_list
    return cleaned_entry


def _clean_gainhelm_partner_roster(
    roster: Any,
    slug_low: str,
    has_leak_fn: Any,
    fw_prof: Dict[str, Any],
    affiliates_mod: Any,
) -> Any:
    is_soc2 = any(k in slug_low for k in ("soc-2", "soc2"))
    if isinstance(roster, dict):
        cleaned_roster = _clean_gainhelm_offer_entry(roster, slug_low, has_leak_fn, fw_prof, affiliates_mod)
        if isinstance(cleaned_roster.get("primary_offer"), dict):
            cleaned_roster["primary_offer"] = _clean_gainhelm_offer_entry(
                cleaned_roster["primary_offer"], slug_low, has_leak_fn, fw_prof, affiliates_mod
            )
        return cleaned_roster
    if isinstance(roster, list):
        cleaned_items: List[Any] = []
        for item in roster:
            if isinstance(item, dict):
                cleaned_items.append(_clean_gainhelm_offer_entry(item, slug_low, has_leak_fn, fw_prof, affiliates_mod))
            elif isinstance(item, str) and not is_soc2 and (has_leak_fn(item) or "cpa/c3pao" in item.lower()):
                continue
            else:
                cleaned_items.append(item)
        return cleaned_items
    return roster


def strip_cross_framework_leaks_from_overlay(overlay_data: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """
    Removes cross-framework SOC 2, CMMC, and HIPAA copy from GainHelm GSC overlays
    across all text and structured fields when rendering non-owning framework tools.
    """
    if not isinstance(overlay_data, dict):
        return overlay_data
    slug_low = str(slug or "").strip().lower()

    active_markers: List[str] = []
    for owner_tokens, markers in _GAINHELM_FRAMEWORK_LEAK_GROUPS:
        if not any(tok in slug_low for tok in owner_tokens):
            active_markers.extend(markers)
    fw_prof: Dict[str, Any] = {}
    affiliates_mod: Any = None
    try:
        from pseofactory import affiliates as _aff_mod

        affiliates_mod = _aff_mod
        fw_prof = _aff_mod.get_gainhelm_framework_profile(slug=slug_low)
        for tok in fw_prof.get("forbidden_leak_tokens") or ():
            tok_l = str(tok).strip().lower()
            if tok_l and tok_l not in active_markers:
                active_markers.append(tok_l)
    except Exception:
        pass
    if not active_markers:
        return overlay_data
    leak_markers = tuple(active_markers)

    def _has_leak(val: Any) -> bool:
        raw = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        low = raw.lower()
        return any(m in low for m in leak_markers)

    cleaned = dict(overlay_data)
    for scalar_key in (
        "meta_description",
        "description",
        "title_rewrite",
        "title",
        "h1",
        "quick_answer",
        "methodology_notes",
        "summary",
        "ai_repair_prompt",
    ):
        val = cleaned.get(scalar_key)
        if isinstance(val, str) and _has_leak(val):
            cleaned.pop(scalar_key, None)

    for list_key in (
        "h2_headings",
        "h2_blocks",
        "autonomous_citation_assertions",
        "ai_mode_decision_matrix",
        "comparison_rows",
        "comparison_matrix",
        "preset_scenarios",
        "scenario_presets",
        "faq_entries",
        "faq_additions",
        "faq",
        "hub_links",
    ):
        raw_list = cleaned.get(list_key)
        if isinstance(raw_list, list):
            kept = [item for item in raw_list if not _has_leak(item)]
            if kept:
                cleaned[list_key] = kept
            else:
                cleaned.pop(list_key, None)

    faq_schema = cleaned.get("faq_schema")
    if isinstance(faq_schema, dict) and isinstance(faq_schema.get("mainEntity"), list):
        kept_entities = [ent for ent in faq_schema["mainEntity"] if not _has_leak(ent)]
        if kept_entities:
            updated_schema = dict(faq_schema)
            updated_schema["mainEntity"] = kept_entities
            cleaned["faq_schema"] = updated_schema
        else:
            cleaned.pop("faq_schema", None)

    partner_offer = cleaned.get("partner_offer")
    if isinstance(partner_offer, dict):
        cleaned_offer = _clean_gainhelm_offer_entry(partner_offer, slug_low, _has_leak, fw_prof, affiliates_mod)
        if "partner_roster" in cleaned_offer:
            cleaned_offer["partner_roster"] = _clean_gainhelm_partner_roster(
                cleaned_offer["partner_roster"], slug_low, _has_leak, fw_prof, affiliates_mod
            )
        cleaned["partner_offer"] = cleaned_offer

    if "partner_roster" in cleaned:
        cleaned["partner_roster"] = _clean_gainhelm_partner_roster(
            cleaned["partner_roster"], slug_low, _has_leak, fw_prof, affiliates_mod
        )

    slot_plan = cleaned.get("slot_plan")
    if isinstance(slot_plan, dict):
        cleaned_slot_plan = _clean_gainhelm_offer_entry(slot_plan, slug_low, _has_leak, fw_prof, affiliates_mod)
        if isinstance(cleaned_slot_plan.get("slot_bindings"), dict):
            cleaned_slot_plan["slot_bindings"] = {
                sk: (
                    _clean_gainhelm_offer_entry(sv, slug_low, _has_leak, fw_prof, affiliates_mod)
                    if isinstance(sv, dict)
                    else sv
                )
                for sk, sv in cleaned_slot_plan["slot_bindings"].items()
            }
        rep_reason = cleaned_slot_plan.get("reposition_reason")
        if isinstance(rep_reason, str) and _has_leak(rep_reason):
            cleaned_slot_plan["reposition_reason"] = "Framework-matched partner placement preserved."
        cleaned["slot_plan"] = cleaned_slot_plan

    for norm_key in (
        "meta_description",
        "description",
        "title_rewrite",
        "title",
        "h1",
        "quick_answer",
        "methodology_notes",
        "summary",
        "h2_headings",
        "h2_blocks",
        "autonomous_citation_assertions",
        "ai_mode_decision_matrix",
        "comparison_rows",
        "comparison_matrix",
        "preset_scenarios",
        "scenario_presets",
        "faq_entries",
        "faq_additions",
        "faq",
        "faq_schema",
    ):
        if norm_key in cleaned:
            cleaned[norm_key] = _normalize_overlay_statutory_casing(cleaned[norm_key])

    return cleaned


def _build_truth_pack_overlay_replacements(pack: Any) -> Tuple[List[Tuple[re.Pattern, str]], Dict[str, str]]:
    """Builds dynamic string replacement rules from a TruthPack's superseded_values."""
    if pack is None:
        return [], {}
    entries = getattr(pack, "entries", None) or {}
    current_year = datetime.now(timezone.utc).year
    canonical_nums: Set[str] = set()
    for entry in entries.values():
        eff_y = getattr(entry, "effective_year", None)
        if eff_y is not None and int(eff_y) < current_year:
            continue
        c_val = getattr(entry, "value", getattr(entry, "canonical_value", None))
        if isinstance(c_val, (int, float)) and not isinstance(c_val, bool):
            canonical_nums.add(str(int(c_val)) if float(c_val).is_integer() else f"{float(c_val):.2f}")

    regex_rules: List[Tuple[re.Pattern, str]] = []
    exact_float_rules: Dict[str, str] = {}

    for entry_id, entry in entries.items():
        c_val = getattr(entry, "value", getattr(entry, "canonical_value", None))
        unit = str(getattr(entry, "unit", "") or "").lower()
        sup_list = getattr(entry, "superseded_values", None) or []
        if not sup_list:
            continue

        if unit == "usd" and isinstance(c_val, (int, float)) and not isinstance(c_val, bool):
            c_is_int = float(c_val).is_integer()
            c_int = int(round(float(c_val)))
            c_fmt = f"{c_int:,}" if c_is_int else f"{float(c_val):,.2f}"
            c_plain = str(c_int) if c_is_int else f"{float(c_val):.2f}"
            for sup in sup_list:
                s_val = sup.get("value") if isinstance(sup, dict) else getattr(sup, "value", None)
                if not isinstance(s_val, (int, float)) or isinstance(s_val, bool):
                    continue
                s_is_int = float(s_val).is_integer()
                s_plain = str(int(round(float(s_val)))) if s_is_int else f"{float(s_val):.2f}"
                if s_plain in canonical_nums:
                    continue
                if not s_is_int:
                    s_fmt = f"{float(s_val):,.2f}"
                    regex_rules.append((re.compile(rf"\${re.escape(s_fmt)}(?!\d)"), f"${c_fmt}"))
                    regex_rules.append((re.compile(rf"(?<!\d){re.escape(s_plain)}(?!\d)"), c_plain))
                elif int(round(float(s_val))) >= 1000:
                    s_int = int(round(float(s_val)))
                    s_fmt = f"{s_int:,}"
                    regex_rules.append((re.compile(rf"\${re.escape(s_fmt)}(?!\d)"), f"${c_fmt}"))
                    regex_rules.append((re.compile(rf"(?<![\d.]){re.escape(s_fmt)}(?!\d)"), c_fmt))
                    regex_rules.append((re.compile(rf"(?<![\d.]){re.escape(str(s_int))}(?!\d)"), c_plain))

        elif unit == "percent" and isinstance(c_val, (int, float)) and not isinstance(c_val, bool):
            c_pct = int(round(float(c_val))) if float(c_val).is_integer() else float(c_val)
            eid_low = str(entry_id).lower()
            if "bonus" in eid_low and int(round(float(c_val))) == 100:
                regex_rules.append(
                    (
                        re.compile(r"\b(?:20|40|60)%\s*(first-year\s+)?bonus\s+depreciation\b", re.IGNORECASE),
                        f"{c_pct}% \\1bonus depreciation",
                    )
                )
                regex_rules.append(
                    (re.compile(r"\b(?:20|40|60)%\s+Bonus\b"), f"{c_pct}% Bonus")
                )
            for sup in sup_list:
                s_val = sup.get("value") if isinstance(sup, dict) else getattr(sup, "value", None)
                if isinstance(s_val, (int, float)) and not isinstance(s_val, bool) and not float(s_val).is_integer():
                    s_str = str(s_val)
                    if s_str not in canonical_nums:
                        regex_rules.append((re.compile(rf"(?<!\d){re.escape(s_str)}%"), f"{c_pct}%"))
                        regex_rules.append((re.compile(rf"(?<![\d.]){re.escape(s_str)}(?![\d.])"), str(c_pct)))

        elif unit == "months" and "rap" in str(entry_id).lower() and isinstance(c_val, (int, float)):
            c_mo = int(round(float(c_val)))
            regex_rules.append(
                (
                    re.compile(r"\b120\s+to\s+240\s+certified\s+monthly\s+payments\b", re.IGNORECASE),
                    f"{c_mo} qualifying monthly payments",
                )
            )
            regex_rules.append(
                (
                    re.compile(r"(RAP[^.]{0,80}?)\b240\b(\s*(?:monthly payments|months))", re.IGNORECASE),
                    rf"\g<1>{c_mo}\g<2>",
                )
            )

    return regex_rules, exact_float_rules


def _apply_truth_text_rules(val: Any, regex_rules: Sequence[Tuple[re.Pattern, str]]) -> Any:
    """Recursively normalizes dashes and TruthPack superseded constants across overlay JSON."""
    if isinstance(val, str):
        out = val.replace("\u2014", " - ").replace("\u2013", "-")
        for pat, repl in regex_rules:
            if callable(repl):
                out = pat.sub(repl, out)
            else:
                out = pat.sub(lambda m, r=repl: m.expand(r) if "\\" in r else r, out)
        return out
    if isinstance(val, list):
        return [_apply_truth_text_rules(item, regex_rules) for item in val]
    if isinstance(val, dict):
        return {k: _apply_truth_text_rules(v, regex_rules) for k, v in val.items()}
    return val


def _extract_flagged_tokens_from_violations(violations: Sequence[Any]) -> Tuple[Set[str], Set[str], List[str]]:
    """Extracts unlisted citations, quoted offenders, and excerpts from UnifiedTruthGate violations."""
    unlisted_citations: Set[str] = set()
    quoted_tokens: Set[str] = set()
    excerpts: List[str] = []
    for v in violations:
        code = str(getattr(v, "code", "") or "")
        msg = str(getattr(v, "message", "") or "")
        exc = str(getattr(v, "excerpt", "") or "").strip()
        if exc:
            excerpts.append(exc)
        for m in re.finditer(r"'([^']{2,140})'", msg):
            tok = m.group(1).strip()
            if not tok:
                continue
            if code == "UNLISTED_CITATION":
                unlisted_citations.add(tok)
            else:
                quoted_tokens.add(tok)
        if code == "UNGROUNDED_STATISTIC":
            for pm in re.finditer(r"\b\d+(?:\.\d+)?%", exc or msg):
                quoted_tokens.add(pm.group(0))
    return unlisted_citations, quoted_tokens, excerpts


def _strip_offending_tokens_or_sentences(
    text: str,
    unlisted_citations: Set[str],
    quoted_tokens: Set[str],
    excerpts: Sequence[str],
    needs_benchmark_qualifier: bool,
) -> str:
    """Heals a prose string in-place by removing unlisted citations or offending sentences."""
    out = text
    if needs_benchmark_qualifier and "$121.67" in out and not re.search(
        r"\b(estimate|benchmark|loaded|average|typical)\b", out, re.IGNORECASE
    ):
        out = out.replace("$121.67", "$121.67 BLS benchmark estimate")

    for cit in sorted(unlisted_citations, key=len, reverse=True):
        if cit in out:
            out = re.sub(
                rf"(?:,\s*)?(?:under|per|pursuant to)?\s*{re.escape(cit)}(?:\s*\([^)]{{1,60}}\))?",
                "",
                out,
                flags=re.IGNORECASE,
            )

    offenders = [t for t in quoted_tokens if t and t.lower() in out.lower()]
    if not offenders and excerpts:
        for exc in excerpts:
            if len(exc) >= 12 and exc in out:
                offenders.append(exc)

    if offenders:
        sentences = re.split(r"(?<=[.!?])\s+", out.strip())
        if len(sentences) > 1:
            kept = [
                s for s in sentences
                if not any(off.lower() in s.lower() for off in offenders)
            ]
            out = " ".join(kept).strip()
        else:
            for off in sorted(offenders, key=len, reverse=True):
                if re.search(re.escape(off), out, re.IGNORECASE):
                    out = ""
                    break

    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    return out


def _prune_or_heal_overlay_node(
    node: Any,
    unlisted_citations: Set[str],
    quoted_tokens: Set[str],
    excerpts: Sequence[str],
    needs_benchmark_qualifier: bool,
    key_name: str = "",
) -> Any:
    """Recursively heals or prunes overlay nodes flagged by UnifiedTruthGate."""
    if isinstance(node, str):
        return _strip_offending_tokens_or_sentences(
            node, unlisted_citations, quoted_tokens, excerpts, needs_benchmark_qualifier
        )
    if isinstance(node, list):
        kept_items = []
        for item in node:
            item_dump = json.dumps(item, ensure_ascii=False)
            healed = _prune_or_heal_overlay_node(
                item, unlisted_citations, quoted_tokens, excerpts, needs_benchmark_qualifier
            )
            if isinstance(healed, str) and not healed.strip():
                continue
            if isinstance(healed, dict):
                # Drop FAQ / structured row if any mandatory string field became empty
                had_nonempty = any(isinstance(v, str) and bool(v.strip()) for v in item.values()) if isinstance(item, dict) else False
                has_empty_cleared = isinstance(item, dict) and any(
                    isinstance(item.get(k), str) and bool(item.get(k, "").strip()) and not str(healed.get(k, "")).strip()
                    for k in item
                )
                if had_nonempty and has_empty_cleared:
                    continue
            # Also drop item if raw serialized form still hits an unrepairable quoted offender
            healed_dump = json.dumps(healed, ensure_ascii=False).lower()
            if any(tok.lower() in healed_dump for tok in quoted_tokens) and item_dump:
                continue
            kept_items.append(healed)
        return kept_items
    if isinstance(node, dict):
        new_dict: Dict[str, Any] = {}
        for k, v in node.items():
            if k == "slug":
                new_dict[k] = v
                continue
            healed_v = _prune_or_heal_overlay_node(
                v, unlisted_citations, quoted_tokens, excerpts, needs_benchmark_qualifier, key_name=k
            )
            if isinstance(healed_v, str) and not healed_v.strip():
                if k in ("title", "short_title"):
                    new_dict[k] = v
                continue
            if isinstance(healed_v, list) and isinstance(v, list) and not healed_v:
                continue
            new_dict[k] = healed_v
        return new_dict
    return node


def _reconcile_and_heal_overlay_against_truth_pack(
    ov_data: Dict[str, Any],
    ov_file: Path,
    property_id: str,
    gate: Any = None,
    pack: Any = None,
    regex_rules: Sequence[Tuple[re.Pattern, str]] = (),
) -> Optional[Dict[str, Any]]:
    """Applies TruthPack replacements and UnifiedTruthGate healing to one overlay dict."""
    cleaned = copy.deepcopy(ov_data)
    if regex_rules:
        cleaned = _apply_truth_text_rules(cleaned, regex_rules)
    else:
        cleaned = _apply_truth_text_rules(cleaned, ())

    if gate is None or pack is None:
        return cleaned

    for _ in range(4):
        cand_json = json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n"
        rep = gate.audit_non_html_file(
            ov_file,
            property_id,
            content=cand_json,
            truth_pack=pack,
        )
        if rep.passed:
            return cleaned

        non_pack_violations = [
            v for v in rep.violations
            if str(getattr(v, "gate", "")) != "GATE_TRUTH_PACK"
        ]
        if not non_pack_violations:
            return cleaned

        unlisted_cits, quoted_toks, excerpts = _extract_flagged_tokens_from_violations(non_pack_violations)
        needs_bench = any(
            str(getattr(v, "code", "")) == "MISSING_BENCHMARK_QUALIFIER"
            for v in non_pack_violations
        )

        # Strip unrepairable ai_repair_prompt metadata immediately if flagged
        if "ai_repair_prompt" in cleaned:
            prompt_str = str(cleaned.get("ai_repair_prompt") or "")
            if any(c in prompt_str for c in unlisted_cits) or any(
                t.lower() in prompt_str.lower() for t in quoted_toks
            ):
                cleaned.pop("ai_repair_prompt", None)
                continue

        next_cleaned = _prune_or_heal_overlay_node(
            cleaned, unlisted_cits, quoted_toks, excerpts, needs_bench
        )
        if not isinstance(next_cleaned, dict) or next_cleaned == cleaned:
            break
        cleaned = next_cleaned

    final_json = json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n"
    final_rep = gate.audit_non_html_file(
        ov_file,
        property_id,
        content=final_json,
        truth_pack=pack,
    )
    if any(str(getattr(v, "gate", "")) != "GATE_TRUTH_PACK" for v in final_rep.violations):
        return None
    return cleaned


def _scrub_tenant_specific_overlay_defects(
    ov_data: Dict[str, Any],
    property_id: str,
    slug: str,
) -> Dict[str, Any]:
    """
    Deterministically scrubs legacy query stubs, superseded 225% RAP / PSLF overlay claims,
    and cross-topic ProfitHelm Form 8824 / Miller Act / 20% bonus depreciation leaks on disk.
    """
    norm_prop = str(property_id or "").strip().lower()
    slug_low = str(slug or "").strip().lower()
    is_1031_slug = any(k in slug_low for k in ("1031", "like-kind", "exchange", "ftb-3840"))

    def _scrub_str(val: str) -> str:
        out = val.replace("\u2014", " - ").replace("\u2013", "-")
        if norm_prop == "prexvo":
            out = out.replace(
                "Calculate How Do You obligations under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
                "Calculate Title IV student loan repayment obligations under 34 CFR Part 685, P.L. 119-21 Section 82001 RAP, and 91 FR 1797 $15,960 guidelines.",
            )
            out = re.sub(r"\bCalculate\s+How\s+Do\s+You\b", "Calculate Title IV", out, flags=re.IGNORECASE)
            out = re.sub(
                r"\bHow\s+Do\s+You\s+Calculate\s+Student\s+Loan\s+2026\s+Calculator\b",
                "Student Loan Repayment Calculation Guide 2026",
                out,
                flags=re.IGNORECASE,
            )
            out = re.sub(r"\bHow\s+Do\s+You\s+Calculate\b", "Calculate", out, flags=re.IGNORECASE)
            out = re.sub(r"\bHow\s+Do\s+You\b", "Student Loan Repayment", out, flags=re.IGNORECASE)
            out = out.replace(
                "36 remaining RAP payments at $273.23/mo unlocking $65,164 tax-free principal forgiveness.",
                "36 remaining RAP payments at $340.00/mo toward $62,760 tax-free PSLF discharge under 34 CFR 685.219.",
            )
            out = out.replace(
                "$9,836 Remaining RAP Outflow + $65,164 Forgiven",
                "$12,240 Remaining RAP Outflow + $62,760 Forgiven",
            )
            out = out.replace(
                "$80,794 Net Tax-Free Statutory Relief",
                "$78,390 Net Tax-Free Statutory Relief",
            )
            out = re.sub(r"\$273\.23/mo\s+unlocking\b", "$340.00/mo toward", out, flags=re.IGNORECASE)
            out = out.replace("$273.23", "$340.00").replace("273.23", "340.00")
            out = re.sub(r"unlocking\s+\$65,164\b", "toward $62,760", out, flags=re.IGNORECASE)
            out = out.replace("$65,164", "$62,760")
            out = out.replace(
                "Single borrower at $65,000 AGI with 225% HHS poverty exemption ($248.23/mo RAP payment).",
                "Single borrower at $65,000 AGI in the 6% P.L. 119-21 Section 82001 tier ($325.00/mo RAP payment, 100% unpaid interest waived).",
            )
            out = out.replace("$248.23 / mo (225% Poverty Exemption)", "$325.00 / mo (P.L. 119-21 6% AGI Tier)")
            out = out.replace("$248.23 / mo Separate RAP Payment ($2,979 / yr)", "$325.00 / mo Separate RAP Payment ($3,900 / yr)")
            out = out.replace("$1,105.73 / mo Joint RAP Payment ($13,269 / yr)", "$1,500.00 / mo Joint RAP Payment ($18,000 / yr)")
            out = out.replace("$306.56 / mo (10% RAP 225% Poverty Exemption)", "$433.33 / mo (P.L. 119-21 Section 82001 RAP)")
            out = out.replace("$35,212.50 Single RAP Baseline", "P.L. 119-21 Section 82001 Tiered AGI")
            out = out.replace("$35,212.50", "$23,940.00")
            out = out.replace("$248.23", "$325.00").replace("248.23", "325.00")
            out = out.replace("$242.42", "$325.00").replace("242.42", "325.00")
            if "685.209(f)" not in out.lower() and "2024 save plan" not in out.lower():
                out = re.sub(
                    r"\b150%\s+to\s+225%\s+of\s+the\s+federal\s+poverty\s+guideline\b",
                    "150% of the 2026 federal poverty guideline (IBR) and P.L. 119-21 Section 82001 tiered AGI percentages (RAP)",
                    out,
                    flags=re.IGNORECASE,
                )
                out = re.sub(
                    r"\b225%\s*(?:of\s+the\s+|HHS\s*)?(?:Federal\s*)?(?:Poverty\s*)?(?:Guidelines?|Exemption|FPL(?:\s+Exemption)?|Floor)\b",
                    "P.L. 119-21 Section 82001 Tiered AGI RAP",
                    out,
                    flags=re.IGNORECASE,
                )
                out = re.sub(
                    r"\b225\s+percent\s+of\s+(?:the\s+)?(?:applicable\s+)?(?:HHS\s+|Federal\s+)?Poverty\s+Guidelines?\b",
                    "P.L. 119-21 Section 82001 tiered AGI percentages (1% to 10%)",
                    out,
                    flags=re.IGNORECASE,
                )
                out = out.replace("225%", "P.L. 119-21 6% AGI tier").replace("225 percent", "P.L. 119-21 6% AGI tier")
        elif norm_prop == "profithelm":
            out = re.sub(
                r"\b20%\s*(first-year\s+)?bonus\s+depreciation\b",
                r"100% \1bonus depreciation",
                out,
                flags=re.IGNORECASE,
            )
            out = re.sub(
                r"\b(?:Federal\s+)?Miller\s+Act\s*\(40\s*U\.S\.C\.?\s*(?:Section\s*|Sec\.?\s*)?3131\)\s*(?:and|&)\s*(?:FAR\s*Part\s*28|48\s*CFR\s*Part\s*28)",
                "31 U.S.C. Section 9304 and IRC Section 162(a)",
                out,
                flags=re.IGNORECASE,
            )
            out = re.sub(
                r"\bfederal\s+Miller\s+Act\s+40\s*U\.S\.C\.?\s*(?:Section\s*|Sec\.?\s*)?3131\b",
                "31 U.S.C. Section 9304 commercial surety rules",
                out,
                flags=re.IGNORECASE,
            )
            out = re.sub(
                r"\b40\s*U\.S\.C\.?\s*(?:Section\s*|Sec\.?\s*)?3131\s*\(Miller\s+Act\)",
                "31 U.S.C. Section 9304",
                out,
                flags=re.IGNORECASE,
            )
            out = re.sub(r"\b40\s*U\.S\.C\.?\s*(?:Section\s*|Sec\.?\s*)?3131\b", "31 U.S.C. Section 9304", out, flags=re.IGNORECASE)
            out = re.sub(r"\b(?:FAR\s*Part\s*28|FAR\s*28\.102-2|48\s*CFR\s*Part\s*28)\b", "IRC Section 162(a)", out, flags=re.IGNORECASE)
            out = re.sub(r"\b(?:Federal\s+)?Miller\s+Act\b", "Commercial Surety Bond", out, flags=re.IGNORECASE)
            if not is_1031_slug:
                if "crypto" in slug_low or "1099-da" in slug_low or "8949" in slug_low:
                    sched_repl = "reconciled federal schedules (Form 8949 and Form 1099-DA) for audit verification."
                elif any(k in slug_low for k in ("179", "vehicle", "equipment", "4562", "gmc", "porsche", "tesla", "ford", "chevy", "chevrolet", "cadillac", "lincoln", "bmw", "mercedes", "rivian", "ram", "audi", "lexus", "land-rover", "jeep", "toyota", "nissan", "volvo", "sprinter", "transit", "yukon", "escalade", "tahoe", "suburban", "navigator", "cayenne", "cybertruck", "defender", "wagoneer")):
                    sched_repl = "reconciled federal Form 4562 depreciation schedules and placed-in-service invoices for audit verification."
                else:
                    sched_repl = "contemporaneous business accounting logs and reconciled IRS statutory schedules for audit verification."
                out = out.replace(
                    "reconciled federal schedules (Form 4562, Form 8824, or Form 8949) for audit verification.",
                    sched_repl,
                )
                out = re.sub(r",?\s*Form\s*8824\b", "", out, flags=re.IGNORECASE)
                out = re.sub(r"\b(?:IRC\s*)?Section\s*1031\b(?:\([a-z0-9]+\))?", "Internal Revenue Code", out, flags=re.IGNORECASE)
        return out

    def _walk(node: Any, key_name: str = "") -> Any:
        if isinstance(node, str):
            return _scrub_str(node)
        if isinstance(node, list):
            new_list = []
            for item in node:
                if (
                    norm_prop == "profithelm"
                    and not is_1031_slug
                    and key_name == "internal_links"
                    and isinstance(item, dict)
                ):
                    href_low = str(item.get("href") or "").lower()
                    anch_low = str(item.get("anchor") or "").lower()
                    if "1031" in href_low or "1031" in anch_low or "8824" in anch_low:
                        continue
                new_list.append(_walk(item))
            return new_list
        if isinstance(node, dict):
            return {k: _walk(v, key_name=k) for k, v in node.items()}
        return node

    return _walk(ov_data)


def sanitize_tenant_overlays(
    repo_root: Path,
    tools_dir: Optional[Path],
    extra_bad_tokens: Sequence[str] = (),
    property_id: str = "",
) -> None:
    """Removes orphaned, cross-tenant contaminated, or TruthPack-violating overlay JSON files."""
    norm_prop = str(property_id or "").strip().lower()
    if norm_prop:
        try:
            from pseofactory.contracts import resolve_canonical_property_id
            norm_prop = resolve_canonical_property_id(norm_prop, default=norm_prop).lower()
        except Exception:
            pass
    is_gainhelm = norm_prop == "gainhelm"
    is_lienbond = norm_prop == "lienbond"

    pack = None
    gate = None
    regex_rules: List[Tuple[re.Pattern, str]] = []
    if norm_prop:
        try:
            from pseofactory.truth_pack import load_truth_pack
            from pseofactory.truth_gate import UnifiedTruthGate
            pack = load_truth_pack(norm_prop, allow_expired=True)
            regex_rules, _ = _build_truth_pack_overlay_replacements(pack)
            gate = UnifiedTruthGate()
        except Exception:
            pack = None
            gate = None

    has_built_tools = bool(tools_dir is not None and Path(tools_dir).is_dir())
    for ov_dir in (repo_root / "content" / "overlays", repo_root / ".agy" / "overlays"):
        if not ov_dir.is_dir():
            continue
        for ov_file in list(ov_dir.glob("*.json")):
            if has_built_tools and not (Path(tools_dir) / ov_file.stem / "index.html").is_file():
                ov_file.unlink(missing_ok=True)
                continue
            try:
                raw_text = ov_file.read_text(encoding="utf-8")
            except Exception:
                continue
            if extra_bad_tokens and any(bad_tok in raw_text.lower() for bad_tok in extra_bad_tokens):
                ov_file.unlink(missing_ok=True)
                continue
            try:
                ov_data = json.loads(raw_text)
            except Exception:
                ov_file.unlink(missing_ok=True)
                continue
            if not isinstance(ov_data, dict):
                ov_file.unlink(missing_ok=True)
                continue

            ov_status = str(ov_data.get("status") or "").strip().upper()
            is_rollback_tombstone = (
                ov_status in {"DEGRADED_ROLLED_BACK", "ROLLED_BACK", "EXPIRED", "REVERTED"}
                or bool(ov_data.get("rolled_back"))
                or any(
                    bool(ov_data.get(k))
                    for k in (
                        "rolled_back_at",
                        "rolled_back_title_rewrite",
                        "rolled_back_modifier",
                        "rolled_back_secondary_title_modifier",
                        "rollback_reason",
                    )
                )
                or any(str(k).startswith("rolled_back_") and bool(ov_data.get(k)) for k in ov_data)
            )
            if is_rollback_tombstone:
                continue

            cleaned = ov_data
            if is_gainhelm:
                cleaned = strip_cross_framework_leaks_from_overlay(cleaned, ov_file.stem)
            elif is_lienbond and _is_lienbond_wc_slug(ov_file.stem):
                cleaned = _scrub_lienbond_wc_citations(cleaned)

            if norm_prop:
                cleaned = _scrub_tenant_specific_overlay_defects(cleaned, norm_prop, ov_file.stem)
                reconciled = _reconcile_and_heal_overlay_against_truth_pack(
                    cleaned,
                    ov_file,
                    norm_prop,
                    gate=gate,
                    pack=pack,
                    regex_rules=regex_rules,
                )
                if reconciled is None:
                    ov_file.unlink(missing_ok=True)
                    continue
                cleaned = reconciled

            has_content = any(bool(cleaned.get(k)) for k in _OVERLAY_CONTENT_KEYS)
            if not has_content and not is_rollback_tombstone:
                ov_file.unlink(missing_ok=True)
            elif cleaned != ov_data:
                out_text = json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n"
                assert_no_forbidden_dashes(out_text, context=f"overlay {ov_file.name}")
                ov_file.write_text(out_text, encoding="utf-8")


def finalize_estate_build(
    root: Path,
    dist: Path,
    property_id: str,
    canonical_base: str,
    run_retrofit: bool = True,
    bad_overlay_tokens: Sequence[str] = ("profithelm", "section-179-calculator", "section-301-tariff", "coinledger"),
    strict_truth_gate: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Runs overlay sanitization, optional RetroReflectionEngine retrofit, manifest pruning,
    Porcelain shell sync & estate compile, dist/functions removal, and substrate_lock/ledger writes.
    """
    from pseofactory.porcelain_shell import (
        compile_tenant_porcelain_estate,
        get_porcelain_tenant_profile,
        sync_tenant_porcelain_shell,
        wire_tenant_substrate_bootstraps,
    )
    from pseofactory.maintenance import RetroReflectionEngine

    tools_dir = dist / "tools"
    manifests_dir = dist / "manifests"

    sanitize_tenant_overlays(
        root,
        tools_dir,
        extra_bad_tokens=bad_overlay_tokens,
        property_id=property_id,
    )

    retrofit_report: Dict[str, Any] = {}
    if run_retrofit:
        retrofit_report = RetroReflectionEngine.retrofit_estate(
            dist,
            property_id,
            canonical_base=canonical_base,
        )
        if manifests_dir.is_dir():
            for mf_file in list(manifests_dir.glob("*.json")):
                if not (tools_dir / mf_file.stem / "index.html").is_file():
                    mf_file.unlink(missing_ok=True)
    else:
        RetroReflectionEngine.sync_tenant_llms_manifests(
            dist,
            property_id=property_id,
            canonical_base=canonical_base,
        )
        RetroReflectionEngine.sync_tenant_publisher_prerequisites(
            dist,
            property_id=property_id,
            canonical_base=canonical_base,
        )

    in_synced_substrate = "_pseo_substrate" in Path(__file__).resolve().parts
    if not in_synced_substrate and not (
        "/.agy/worktrees/" in Path(__file__).resolve().as_posix()
        and str(root.resolve()).startswith("/home/ubuntuadmin/projects/")
    ):
        sync_tenant_porcelain_shell(root, property_id)
    elif in_synced_substrate:
        prof = get_porcelain_tenant_profile(property_id)
        wire_tenant_substrate_bootstraps(root, prof["package_name"], prof["brand_name"])
    compile_tenant_porcelain_estate(dist, property_id, repo_root=root)

    from pseofactory.compiler import write_static_embed_widget_assets
    from pseofactory.porcelain_shell import _discover_estate_tools_and_gsc_token

    widget_profile = get_porcelain_tenant_profile(property_id)
    widget_tools_raw, _ = _discover_estate_tools_and_gsc_token(dist, widget_profile)
    widget_tools = [{"slug": s, "title": t} for s, t in widget_tools_raw]
    write_static_embed_widget_assets(
        dist_dir=dist,
        domain=str(widget_profile.get("domain") or f"{property_id}.com"),
        brand_name=str(widget_profile.get("brand_name") or property_id.capitalize()),
        tools=widget_tools,
    )

    dist_functions = dist / "functions"
    if dist_functions.exists():
        shutil.rmtree(dist_functions, ignore_errors=True)

    # Enforce post-compile purge of zero-click dumps, lightweight catalog.json, capped llms.txt, and 410 redirects
    (dist / "llms-full.txt").unlink(missing_ok=True)
    dist_ai_bench = dist / "ai-benchmarks"
    if dist_ai_bench.exists():
        shutil.rmtree(dist_ai_bench, ignore_errors=True)
    sanitize_public_catalog_file(dist, property_id=property_id)
    cap_llms_txt_file(dist, property_id=property_id, canonical_base=canonical_base)
    from pseofactory.edge import build_edge_routes_json, ensure_gone_rules_in_redirects

    routes_p = dist / "_routes.json"
    expected_routes = build_edge_routes_json()
    if not routes_p.is_file() or routes_p.read_text(encoding="utf-8", errors="ignore") != expected_routes:
        routes_p.write_text(expected_routes, encoding="utf-8")
    redirects_p = dist / "_redirects"
    if redirects_p.is_file():
        cur_red = redirects_p.read_text(encoding="utf-8", errors="ignore")
        new_red = ensure_gone_rules_in_redirects(cur_red)
        if new_red != cur_red:
            redirects_p.write_text(new_red, encoding="utf-8")

    if os.environ.get("PSEO_IN_REFLECT") != "1":
        try:
            from pseofactory.drift import (
                compute_asset_fingerprint,
                compute_engine_hash,
                record_asset_ledger,
                record_engine_hash,
                write_substrate_lock,
            )

            eng_hash = compute_engine_hash()
            resolved_engine_hash = eng_hash
            synced_sub_hash: Optional[str] = eng_hash if in_synced_substrate else None
            if in_synced_substrate:
                lock_file = root / "substrate_lock.json"
                if lock_file.is_file():
                    try:
                        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
                        cand_full = str((lock_data or {}).get("engine_hash") or "").strip()
                        if (
                            isinstance(lock_data, dict)
                            and lock_data.get("synced_substrate_hash") == eng_hash
                            and re.fullmatch(r"[0-9a-f]{64}", cand_full)
                        ):
                            resolved_engine_hash = cand_full
                            synced_sub_hash = eng_hash
                    except Exception:
                        pass

            lock_payload = write_substrate_lock(
                root,
                property_id=property_id,
                expected_hash=resolved_engine_hash,
                dist_dir=dist,
                sync_ledgers=False,
            )
            synced_sub_hash = str(lock_payload.get("synced_substrate_hash") or "") or synced_sub_hash
            agy_dir = root / ".agy"
            agy_dir.mkdir(parents=True, exist_ok=True)
            record_engine_hash(
                agy_dir / "engine_hash.json",
                hash_value=resolved_engine_hash,
                synced_substrate_hash=synced_sub_hash,
            )
            html_assets = sorted(
                p
                for p in dist.glob("**/*")
                if p.is_file()
                and "syndication" not in p.relative_to(dist).parts
                and p.suffix.lower() in (".html", ".xml", ".txt", ".json", ".md")
                and not any(p.name.endswith(ext) for ext in (".tmp", ".orig", ".backup"))
            )
            asset_hashes = {
                p.relative_to(dist).as_posix(): compute_asset_fingerprint(p)
                for p in html_assets
            }
            record_asset_ledger(
                agy_dir / "asset_ledger.json",
                asset_hashes=asset_hashes,
                engine_hash=resolved_engine_hash,
            )
        except Exception:
            pass

    # Re-enforce dump purge after write_substrate_lock/record_asset_ledger in case drift.py regenerated ai-benchmarks
    (dist / "llms-full.txt").unlink(missing_ok=True)
    if (dist / "ai-benchmarks").exists():
        shutil.rmtree(dist / "ai-benchmarks", ignore_errors=True)

    is_strict_truth_gate = (
        strict_truth_gate is True
        or os.environ.get("PSEO_STRICT_TRUTH_GATE") == "1"
        or (
            strict_truth_gate is None
            and os.environ.get("PSEO_PRODUCTION_MODE") == "1"
            and "PYTEST_CURRENT_TEST" not in os.environ
        )
    )
    if is_strict_truth_gate and strict_truth_gate is not False:
        from pseofactory.truth_gate import UnifiedTruthGate

        truth_report = UnifiedTruthGate().audit_estate(
            dist,
            property_id,
            repo_root=root,
        )
        if isinstance(retrofit_report, dict):
            retrofit_report["truth_gate"] = {
                "passed": bool(truth_report.passed),
                "summary": truth_report.summary(),
                "violation_count": len(truth_report.violations),
            }
        if not truth_report.passed:
            raise RuntimeError(
                f"UnifiedTruthGate failed for '{property_id}': {truth_report.summary()}"
            )

    return retrofit_report


def normalize_tenant_seo_title(
    title: str,
    brand: str,
    default_tagline: str = "Enterprise Modeling Engine",
    pad_candidates: Sequence[str] = (),
    min_len: int = 50,
    max_len: int = 60,
) -> str:
    """Normalizes HTML title length within [min_len, max_len] with zero dangling dividers."""
    raw = html.unescape((title or "").strip())
    raw = re.sub(r"\s+", " ", raw).replace("\u2014", "-").replace("\u2013", "-")
    raw = re.sub(r"\|\s*\|+", "|", raw)
    raw = re.sub(r"\s*\|\s*", " | ", raw)
    if brand:
        raw = re.sub(rf"(?:\s*\|\s*{re.escape(brand)})+", f" | {brand}", raw, flags=re.IGNORECASE)

    brand_suffix = f" | {brand}" if brand else ""
    base = raw
    while brand:
        stripped = False
        for suffix in (f"| {brand}", f"- {brand}", f": {brand}", brand):
            if base.lower().endswith(suffix.lower()) and len(base) > len(suffix):
                base = base[: -len(suffix)].strip(" |-:")
                stripped = True
                break
        if not stripped:
            break
    base = base.rstrip(" |-").strip()

    starts_with_brand = bool(
        brand and re.match(rf"^{re.escape(brand)}\s*[:|\-]\s*", base, flags=re.IGNORECASE)
    )
    if starts_with_brand:
        raw = base
        effective_suffix = ""
        normalized = base
    else:
        effective_suffix = brand_suffix
        normalized = f"{base}{effective_suffix}" if base else f"{brand} {default_tagline}"

    if min_len <= len(normalized) <= max_len and "| |" not in normalized:
        return normalized
    if min_len <= len(raw) <= max_len and "| |" not in raw and not raw.endswith((" |", " -")):
        return raw

    if len(normalized) < min_len:
        pad_base = base if base else (f"{brand} {default_tagline}".strip() if brand else default_tagline)
        pad_starts_with_brand = starts_with_brand or (not base and bool(brand))
        pad_suffix = "" if pad_starts_with_brand else effective_suffix
        if pad_starts_with_brand:
            default_pads = (
                f"{pad_base} | Statutory Calculator",
                f"{pad_base} | Modeling Engine",
                f"{pad_base} Calculator Tool",
                f"{pad_base} Cost Model",
                f"{pad_base} | Deterministic Modeling Engine",
                f"{pad_base} | Statutory Calculation Engine",
                f"{pad_base} | Deterministic Statutory Modeling Engine",
            )
        else:
            default_pads = (
                f"{pad_base} Tool{pad_suffix}",
                f"{pad_base} Planning Engine{pad_suffix}",
                f"{pad_base} Statutory Calculator{pad_suffix}",
                f"{pad_base} | {default_tagline}{pad_suffix}",
                f"{pad_base} | Statutory Modeling Engine{pad_suffix}",
                f"{pad_base} | Deterministic Statutory Calculator{pad_suffix}",
                f"{pad_base} | Deterministic Statutory Modeling Engine{pad_suffix}",
                f"{pad_base} | Authoritative Statutory Modeling Engine{pad_suffix}",
            )
        rendered_cands: List[str] = []
        for tmpl in tuple(pad_candidates) + default_pads:
            cand = (
                tmpl.format(base=pad_base, brand=brand, brand_suffix=pad_suffix)
                if "{base}" in tmpl
                else tmpl
            )
            cand = re.sub(r"\s*\|\s*", " | ", re.sub(r"\|\s*\|+", "|", cand))
            if pad_starts_with_brand and brand and cand.lower().count(brand.lower()) > 1:
                continue
            rendered_cands.append(cand)
            if min_len <= len(cand) <= max_len:
                return cand

        # Deterministic word-trimming / descriptor-padding fallback so any short title down to
        # 1 char lands inside [min_len, max_len] and preserves the trailing brand suffix.
        for cand in rendered_cands:
            if len(cand) > max_len and (not pad_suffix or cand.endswith(pad_suffix)):
                mid = cand[: len(cand) - len(pad_suffix)].rstrip(" |-") if pad_suffix else cand
                while len(mid) + len(pad_suffix) > max_len and " " in mid:
                    next_mid = mid.rsplit(" ", 1)[0].rstrip(" |-&")
                    if len(next_mid) < len(pad_base):
                        break
                    mid = next_mid
                    if min_len <= len(mid) + len(pad_suffix) <= max_len:
                        return f"{mid}{pad_suffix}"

        filler_words = (
            "Statutory",
            "Financial",
            "Modeling",
            "Analysis",
            "Planning",
            "Calculation",
            "Comparison",
            "Reference",
            "Engine",
            "Calculator",
            "Suite",
            "Guide",
        )
        built = pad_base if ("|" in pad_base or not pad_base) else f"{pad_base} | Statutory"
        if len(built) + len(pad_suffix) > max_len:
            built = pad_base
        existing_lower = set(built.lower().split())
        for word in filler_words:
            if word.lower() in existing_lower:
                continue
            nxt = f"{built} {word}" if ("|" in built or pad_starts_with_brand) else f"{built} | {word}"
            if len(nxt) + len(pad_suffix) <= max_len:
                built = nxt
                existing_lower.add(word.lower())
                if min_len <= len(built) + len(pad_suffix) <= max_len:
                    return f"{built}{pad_suffix}"
        if min_len <= len(built) + len(pad_suffix) <= max_len:
            return f"{built}{pad_suffix}"

    stopwords = {"and", "or", "for", "with", "in", "to", "of", "&", "-"}
    if len(normalized) > max_len:
        max_base = max_len - len(effective_suffix)
        min_base = min_len - len(effective_suffix)
        trimmed = base[:max_base]
        while " " in trimmed:
            words = trimmed.rsplit(" ", 1)[0].rstrip(" |-&")
            w_list = words.split()
            while w_list and w_list[-1].lower() in stopwords and " " in words:
                words = words.rsplit(" ", 1)[0].rstrip(" |-&")
                w_list = words.split()
            if len(words) >= min_base and min_len <= len(f"{words}{effective_suffix}") <= max_len:
                return f"{words}{effective_suffix}"
            for pad_w in ("Models", "Engine", "Suite", "Tools", "Guide"):
                padded = f"{words} {pad_w}"
                if min_base <= len(padded) <= max_base:
                    cand = f"{padded}{effective_suffix}"
                    if min_len <= len(cand) <= max_len:
                        return cand
            trimmed = words
        cand = f"{base[:max_base].rstrip(' |-&')}{effective_suffix}"
        if len(cand) <= max_len:
            return cand

    return normalized[:max_len].rstrip(" |-")


def build_organization_schema(
    canonical_base: str,
    site_name: str,
    site_description: str,
    same_as: Sequence[str],
) -> Dict[str, Any]:
    """Builds the canonical Organization JSON-LD node for a tenant."""
    base = canonical_base.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": site_name,
        "url": base,
        "description": site_description,
        "publishingPrinciples": f"{base}/methodology/",
        "sameAs": list(same_as),
    }


def build_local_business_schema(
    canonical_base: str,
    legal_name: str,
    contact_email: str,
    telephone: str,
    price_range: str,
    address: Dict[str, str],
    geo: Dict[str, float],
    same_as: Sequence[str],
    catalog_name: str,
    offers: Sequence[Any],
) -> Dict[str, Any]:
    """Builds the canonical LocalBusiness + FinancialService JSON-LD node for a tenant."""
    base = canonical_base.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": ["LocalBusiness", "FinancialService", "ProfessionalService"],
        "@id": f"{base}/#localbusiness",
        "name": legal_name,
        "legalName": legal_name,
        "url": base,
        "logo": f"{base}/favicon.ico",
        "email": contact_email,
        "telephone": telephone,
        "priceRange": price_range,
        "parentOrganization": {"@id": f"{base}/#organization"},
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address["street"],
            "addressLocality": address["city"],
            "addressRegion": address["state"],
            "postalCode": address["zip"],
            "addressCountry": address["country"],
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": geo["lat"],
            "longitude": geo["lng"],
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "opens": "09:00",
                "closes": "17:00",
            }
        ],
        "sameAs": list(same_as),
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": catalog_name,
            "itemListElement": [
                {
                    "@type": "Offer",
                    "itemOffered": {
                        "@type": "Service",
                        "name": p.name,
                        "description": p.description,
                        "url": p.default_url,
                    },
                }
                for p in offers
            ],
        },
    }


def compile_schema_graph(
    schemas: Sequence[Dict[str, Any]],
    canonical_url: str,
    canonical_base: str,
    site_name: str,
    org_schema: Dict[str, Any],
    localbiz_schema: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    meta_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Assembles a deduplicated JSON-LD @graph linking Organization, WebSite, WebPage, and apps."""
    _ = localbiz_schema  # Deprecated: national calculator estates standardize on Organization (no LocalBusiness).
    base = canonical_base.rstrip("/")
    clean_canonical = canonical_url.split("#")[0]
    if clean_canonical == base:
        clean_canonical = f"{base}/"
    org_id = f"{base}/#organization"
    website_id = f"{base}/#website"
    localbiz_id = f"{base}/#localbusiness"
    webpage_id = f"{clean_canonical}#webpage"

    raw_nodes: List[Dict[str, Any]] = []
    for s in schemas or []:
        if not isinstance(s, dict):
            continue
        if "@graph" in s and isinstance(s["@graph"], list):
            raw_nodes.extend(copy.deepcopy(c) for c in s["@graph"] if isinstance(c, dict))
        else:
            raw_nodes.append(copy.deepcopy(s))

    def _types(n: Dict[str, Any]) -> List[str]:
        t = n.get("@type")
        if isinstance(t, str):
            return [t]
        return [str(x) for x in t] if isinstance(t, list) else []

    def _rewrite_localbusiness_id_refs(val: Any) -> Any:
        if isinstance(val, dict):
            out: Dict[str, Any] = {}
            for k, v in val.items():
                if k == "@id" and isinstance(v, str) and (
                    v.strip().lower().endswith("#localbusiness") or v.strip().lower() == localbiz_id.lower()
                ):
                    out[k] = org_id
                else:
                    out[k] = _rewrite_localbusiness_id_refs(v)
            return out
        if isinstance(val, list):
            return [_rewrite_localbusiness_id_refs(v) for v in val]
        return val

    filtered_nodes: List[Dict[str, Any]] = []
    for n in raw_nodes:
        t_list = _types(n)
        nid = str(n.get("@id") or "").strip().lower()
        if "LocalBusiness" in t_list or nid.endswith("#localbusiness") or nid == localbiz_id.lower():
            if "Organization" in t_list:
                cleaned_types = [t for t in t_list if t != "LocalBusiness"]
                n["@type"] = cleaned_types[0] if len(cleaned_types) == 1 else cleaned_types
                if nid.endswith("#localbusiness") or nid == localbiz_id.lower():
                    n["@id"] = org_id
                filtered_nodes.append(_rewrite_localbusiness_id_refs(n))
            continue
        filtered_nodes.append(_rewrite_localbusiness_id_refs(n))
    raw_nodes = filtered_nodes

    if not any("Organization" in _types(n) or n.get("@id") == org_id for n in raw_nodes):
        raw_nodes.append(copy.deepcopy(org_schema))
    if not any("WebSite" in _types(n) or n.get("@id") == website_id for n in raw_nodes):
        raw_nodes.append({"@type": "WebSite", "@id": website_id, "url": base, "name": site_name, "publisher": {"@id": org_id}})
    if not any("WebPage" in _types(n) or n.get("@id") == webpage_id for n in raw_nodes):
        wp: Dict[str, Any] = {"@type": "WebPage", "@id": webpage_id, "url": clean_canonical, "isPartOf": {"@id": website_id}, "about": {"@id": org_id}}
        if title:
            wp["name"] = title
        if meta_description:
            wp["description"] = meta_description
        raw_nodes.append(wp)

    has_app = any("SoftwareApplication" in _types(n) or "WebApplication" in _types(n) for n in raw_nodes)
    priority = {"Organization": 1, "WebSite": 3, "WebPage": 4, "CollectionPage": 4, "BreadcrumbList": 5, "SoftwareApplication": 6, "WebApplication": 7, "FAQPage": 8, "HowTo": 9, "Dataset": 10}
    normalized: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    for node in raw_nodes:
        node.pop("@context", None)
        types = _types(node)
        if "Organization" in types or node.get("@id") == org_id:
            node.setdefault("@id", org_id)
        if "WebSite" in types or node.get("@id") == website_id:
            node.setdefault("@id", website_id)
            node.setdefault("publisher", {"@id": org_id})
        if "WebPage" in types or node.get("@id") == webpage_id:
            node.setdefault("@id", webpage_id)
            node.setdefault("isPartOf", {"@id": website_id})
            node["about"] = {"@id": f"{clean_canonical}#softwareapplication"} if has_app else {"@id": org_id}
            node.setdefault("url", clean_canonical)
            if title and "name" not in node:
                node["name"] = title
            if meta_description and "description" not in node:
                node["description"] = meta_description
        if "SoftwareApplication" in types or "WebApplication" in types:
            node.setdefault("@id", f"{clean_canonical}#softwareapplication")
            node["author"] = {"@type": "Organization", "@id": org_id, "name": site_name, "url": base}
            node["publisher"] = {"@type": "Organization", "@id": org_id, "name": site_name, "url": base}
        if "FAQPage" in types:
            node.setdefault("@id", f"{clean_canonical}#faq")
            node.setdefault("name", f"{site_name} Frequently Asked Questions")
            node["isPartOf"] = {"@id": webpage_id}
        if "HowTo" in types or "BreadcrumbList" in types:
            node.setdefault("@id", f"{clean_canonical}#{'howto' if 'HowTo' in types else 'breadcrumb'}")
            node["isPartOf"] = {"@id": webpage_id}
        if "Dataset" in types:
            node.setdefault("@id", f"{clean_canonical}#dataset")
            node.pop("isPartOf", None)
            node["mainEntityOfPage"] = {"@id": webpage_id}
        if "@id" not in node and types:
            node["@id"] = f"{clean_canonical}#{types[0].lower()}"
        nid = node.get("@id")
        if nid and nid in seen_ids:
            continue
        if nid:
            seen_ids.add(nid)
        normalized.append(node)

    normalized.sort(key=lambda n: min((priority.get(t, 99) for t in _types(n)), default=99))
    return {"@context": "https://schema.org", "@graph": normalized}


def build_partners_matrix_section(
    affiliates: Dict[str, Any],
    section_title: str,
    section_desc_with_cards: str,
    section_desc_empty: str,
    default_cta_text: str = "Compare Partners",
    slug: str = "",
    engagement_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """Renders the vetted partner matrix cards sorted by estimated partner yield."""
    from pseofactory.affiliates import (
        is_partner_live_in_vault,
        resolve_contextual_partner_offer_copy,
        score_partner_yield,
    )

    live_items = [
        (p_id, p_info)
        for p_id, p_info in affiliates.items()
        if is_partner_live_in_vault(getattr(p_info, "property_id", "profithelm"), p_id)
    ]
    if len(live_items) > 1:
        try:
            live_items.sort(
                key=lambda item: -score_partner_yield(
                    item[1], slug=slug, engagement_metrics=engagement_metrics
                )
            )
        except Exception:
            pass
    cards = []
    for p_id, p_info in live_items:
        ctx_copy = resolve_contextual_partner_offer_copy(
            partner_key=p_id,
            p_obj=p_info,
            slug=slug,
            property_id=getattr(p_info, "property_id", "profithelm"),
        )
        badge_val = ctx_copy.get("badge") or getattr(p_info, "badge", "")
        badge_html = (
            f'  <span class="partner-badge">{html.escape(badge_val)}</span>\n'
            if badge_val
            else ""
        )
        cta_text = ctx_copy.get("cta_text") or getattr(p_info, "cta_text", "") or default_cta_text
        cards.append(
            f'<div class="partner-card" data-partner="{html.escape(p_id)}">\n'
            f"{badge_html}"
            f'  <h3 class="partner-title">{html.escape(ctx_copy.get("name") or p_info.name)}</h3>\n'
            f'  <p>{html.escape(ctx_copy.get("description") or p_info.description)}</p>\n'
            f'  <a href="/r/{html.escape(p_id)}" target="_blank" rel="noopener sponsored nofollow" '
            f'class="partner-btn touch-target" data-partner="{html.escape(p_id)}" '
            f'data-cta-slot="partner_matrix_card">{html.escape(cta_text)}</a>\n'
            "</div>"
        )
    if not cards:
        return ""
    # Step 3: single compact contextual referral section rendered ONLY when live partner(s) exist.
    ftc_default = "FTC 16 CFR Part 255 Disclosure: We may earn a referral fee from matched partners at no additional cost to you."
    return (
        '\n    <section class="contextual-referral-card partners-section card" data-mechanic="compliant_intent_monetization">\n'
        f'      <h3 class="section-title">{html.escape(section_title)}</h3>\n'
        f'      <p class="partners-desc">{html.escape(section_desc_with_cards)}</p>\n'
        f'      <div class="card-grid">{"".join(cards[:2])}</div>\n'
        f'      <p class="affiliate-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 8px; margin-bottom: 0;">{ftc_default}</p>\n'
        "    </section>"
    )


def build_partner_cta(
    affiliates: Dict[str, Any],
    preferred_key: str,
    restricted_badge: str,
    restricted_title: str,
    restricted_body: str,
    fallback_badge: str,
    fallback_title: str,
    fallback_body: str,
    default_featured_badge: str = "Featured Partner",
    default_cta_text: str = "Explore Partner",
    slug: str = "",
) -> str:
    """Renders the primary partner callout card or public-service statutory guardrail."""
    from pseofactory.affiliates import (
        is_partner_live_in_vault,
        is_restricted_public_service_slug,
        resolve_contextual_partner_offer_copy,
    )

    if slug and is_restricted_public_service_slug(slug):
        return (
            '\n    <section class="refinance-partner-section ymyl-public-service-guardrail" '
            'data-commercial-offers="none" data-restricted-public-service="true" '
            'data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">\n'
            '      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">\n'
            f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">{html.escape(restricted_badge)}</span>\n'
            f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html.escape(restricted_title)}</h3>\n'
            f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html.escape(restricted_body)}</p>\n'
            "      </div>\n    </section>"
        )
    ref_partner = affiliates.get(preferred_key) or next(iter(affiliates.values()))
    ref_prop = getattr(ref_partner, "property_id", "profithelm")
    if not is_partner_live_in_vault(ref_prop, ref_partner.key):
        live_fallback = next(
            (p for k, p in affiliates.items() if is_partner_live_in_vault(getattr(p, "property_id", ref_prop), k)),
            None,
        )
        if live_fallback is not None:
            ref_partner = live_fallback
        else:
            return ""
    p_key = ref_partner.key
    ctx_copy = resolve_contextual_partner_offer_copy(
        partner_key=p_key,
        p_obj=ref_partner,
        slug=slug,
        property_id=getattr(ref_partner, "property_id", "profithelm"),
    )
    ftc_default = "FTC 16 CFR Part 255 Disclosure: We may earn a referral fee when you engage a matched partner at no additional cost to you."
    return (
        f'\n    <section class="contextual-referral-card refinance-partner-section card" data-mechanic="compliant_intent_monetization" data-partner="{html.escape(p_key)}" style="margin: 1.25rem 0;">\n'
        '      <div class="partner-card">\n'
        f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--brand-primary); text-transform: uppercase;">{html.escape(ctx_copy.get("badge") or ref_partner.badge or default_featured_badge)}</span>\n'
        f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html.escape(ctx_copy.get("name") or ref_partner.name)}</h3>\n'
        f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 0.75rem 0;">{html.escape(ctx_copy.get("description") or ref_partner.description)}</p>\n'
        f'        <a href="/r/{html.escape(p_key)}" target="_blank" rel="noopener sponsored nofollow" class="partner-btn btn-secondary touch-target" data-partner="{html.escape(p_key)}" data-cta-slot="contextual_referral">\n'
        f'          {html.escape(ctx_copy.get("cta_text") or ref_partner.cta_text or default_cta_text)} &rarr;\n'
        "        </a>\n"
        f'        <p class="affiliate-disclosure" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.625rem; margin-bottom: 0;">{ftc_default}</p>\n'
        "      </div>\n    </section>"
    )


def build_retro_reflection_block(
    slug: str,
    canonical_url: str,
    manifest_spec: Dict[str, Any],
    statutory_detail_label: str = "governing statutory attestation rules and fee schedules",
    economic_detail_label: str = "empirical wage and benchmark cost series",
) -> str:
    """Renders dual-dataset provenance, preset deep links, 5-point sensitivity table, and manifest JSON."""
    spec_payload = {
        "manifest_id": f"{slug}-manifest",
        "slug": slug,
        "model_name": manifest_spec["model_name"],
        "statutory_authority": manifest_spec["statutory_authority"],
        "economic_dataset": manifest_spec["economic_dataset"],
        "formula": manifest_spec["formula"],
        "inputs": manifest_spec["inputs"],
        "published_output": float(manifest_spec["published_output"]),
        "sample_calculation": manifest_spec["sample_calculation"],
        "entity_type": manifest_spec.get("entity_type", "FinancialProductOrService"),
    }
    pub_out = float(spec_payload["published_output"])
    display_out = f"{pub_out:,.2f}" if not pub_out.is_integer() else f"{pub_out:,.0f}"
    stat_auth = html.escape(str(spec_payload["statutory_authority"]))
    econ_ds = html.escape(str(spec_payload["economic_dataset"]))

    def _fmt(v: float) -> str:
        r = round(float(v), 2)
        return f"{r:,.0f}" if r.is_integer() else f"{r:,.2f}"

    _ = canonical_url
    manifest_json = json.dumps(spec_payload, ensure_ascii=False, indent=2)
    return f"""
    <section class="multi-dataset-join" data-statutory-source="{stat_auth}" data-economic-source="{econ_ds}" style="margin: 1.25rem 0; padding: 1rem 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
      <h2 class="section-title">Dual Dataset Provenance &amp; Statutory Corroboration</h2>
      <p>Primary statutory authority: <strong>{stat_auth}</strong> defines {html.escape(statutory_detail_label)}.</p>
      <p>Empirical economic dataset: <strong>{econ_ds}</strong> provides {html.escape(economic_detail_label)}.</p>
    </section>

    <section class="comparison-table-section" data-entity-type="scenario" data-mechanic="server_rendered_sensitivity_grid" style="margin: 1.25rem 0;">
      <h2 class="section-title">Sensitivity Scenario Modeling (5-Point SSR Matrix)</h2>
      <p class="section-lead">SSR 5-point sensitivity matrix comparing baseline model projections against parameter variations:</p>
      <div class="table-wrap">
        <table class="scenario-table calculation-table" data-entity-type="scenario" data-statutory-source="{stat_auth}" data-economic-source="{econ_ds}">
          <thead>
            <tr>
              <th scope="col">Scenario Analysis</th>
              <th scope="col">Variance Assumption</th>
              <th scope="col">Statutory Basis</th>
              <th scope="col">Economic Series</th>
              <th scope="col">Projected Outcome</th>
            </tr>
          </thead>
          <tbody>
            <tr data-entity-type="scenario"><td><strong>Baseline Scenario</strong></td><td>Standard published parameters (1.0x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-baseline">{display_out}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Conservative Scenario</strong></td><td>20% Parameter contraction (0.8x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-conservative">{_fmt(pub_out * 0.8)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Moderate Contraction Scenario</strong></td><td>10% Parameter contraction (0.9x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-moderate-contraction">{_fmt(pub_out * 0.9)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Moderate Expansion Scenario</strong></td><td>10% Parameter expansion (1.1x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-moderate-expansion">{_fmt(pub_out * 1.1)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Aggressive Scenario</strong></td><td>20% Parameter expansion (1.2x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-aggressive">{_fmt(pub_out * 1.2)}</strong></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <script type="application/json" id="calculation-manifest" class="calculation-manifest">
{manifest_json}
    </script>"""


def render_base_html(
    title: str,
    meta_description: str,
    canonical_url: str,
    body_content: str,
    canonical_base: str,
    site_name: str,
    brand_mark: str,
    author: str,
    og_image_url: str,
    gsc_meta_val: str,
    disclaimers: Dict[str, str],
    linkedin_url: str,
    editorial_policy_text: str,
    org_schema: Dict[str, Any],
    localbiz_schema: Optional[Dict[str, Any]] = None,
    footer_tagline: str = "",
    normalize_title_fn: Optional[Any] = None,
    jsonld_schemas: Optional[Sequence[Dict[str, Any]]] = None,
    css_text: str = "",
) -> str:
    """Renders a complete Porcelain-CSS-compliant HTML shell document for a tenant page."""
    _ = localbiz_schema  # Deprecated: national calculator estates standardize on Organization (no LocalBusiness).
    base = canonical_base.rstrip("/")
    is_404 = "404" in canonical_url or "404" in title or title.strip().startswith("404")
    if is_404:
        clean_title = title
    elif normalize_title_fn is not None:
        clean_title = normalize_title_fn(title)
    else:
        clean_title = normalize_tenant_seo_title(title, brand=site_name)
    robots_meta = "noindex, follow" if ("404" in canonical_url or "404" in title) else "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
    active_schemas = list(jsonld_schemas or [])
    if not active_schemas:
        active_schemas.append(copy.deepcopy(org_schema))
        active_schemas.append({"@type": "WebPage", "@id": f"{canonical_url.split('#')[0]}#webpage", "name": clean_title, "description": meta_description, "url": canonical_url.split("#")[0]})
    schema_json = json.dumps(
        compile_schema_graph(
            active_schemas,
            canonical_url=canonical_url,
            canonical_base=base,
            site_name=site_name,
            org_schema=org_schema,
            title=clean_title,
            meta_description=meta_description,
        ),
        indent=2,
    )
    style_tag = f"\n  <style>\n{css_text}\n  </style>" if css_text else ""
    stat_disc = html.escape(disclaimers["statutory_compliance_disclaimer"])
    aff_disc = html.escape(disclaimers["ftc_disclosure"])
    no_adv = html.escape(disclaimers["independent_publisher_disclaimer"])

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(clean_title)}</title>
  <meta name="description" content="{html.escape(meta_description)}">
  <meta name="google-site-verification" content="{html.escape(gsc_meta_val)}">
  <meta http-equiv="content-language" content="en-US">
  <link rel="canonical" href="{html.escape(canonical_url)}">
  <link rel="alternate" hreflang="en-US" href="{html.escape(canonical_url)}">
  <link rel="alternate" hreflang="x-default" href="{html.escape(canonical_url)}">
  <meta name="robots" content="{robots_meta}">
  <meta name="author" content="{html.escape(author)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{html.escape(site_name)}">
  <meta property="og:title" content="{html.escape(clean_title)}">
  <meta property="og:description" content="{html.escape(meta_description)}">
  <meta property="og:image" content="{html.escape(og_image_url)}">
  <meta property="og:url" content="{html.escape(canonical_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(clean_title)}">
  <meta name="twitter:description" content="{html.escape(meta_description)}">
  <meta name="twitter:image" content="{html.escape(og_image_url)}">
  <link rel="stylesheet" href="/css/style.css">{style_tag}
  <link rel="alternate" type="application/rss+xml" title="{html.escape(site_name)} RSS Feed" href="/feed.xml">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" href="/favicon.ico">
  <script type="application/ld+json">
{schema_json}
  </script>
</head>
<body>
  <header class="header">
    <div class="container nav-bar">
      <a href="/" class="brand-logo touch-target"><span class="brand-mark">{html.escape(brand_mark)}</span><span class="brand-name">{html.escape(site_name)}</span></a>
      <nav class="nav-links">
        <a href="/tools/" class="nav-link touch-target">Calculators</a>
        <a href="/methodology/" class="nav-link touch-target">Methodology</a>
        <a href="/disclaimers/" class="nav-link touch-target">Disclaimers</a>
      </nav>
    </div>
  </header>

  <main class="container">
    {body_content}

    <div class="ymyl-disclaimer-banner">
      <strong>Important Statutory Warning:</strong> {stat_disc}
    </div>

    <div class="card">
      <strong>Regulatory &amp; Affiliate Disclosure:</strong> {aff_disc}
    </div>
  </main>

  <footer class="footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col">
          <a href="/" class="brand-logo touch-target"><span class="brand-mark">{html.escape(brand_mark)}</span><span class="brand-name">{html.escape(site_name)}</span></a>
          <p>&copy; 2026 {html.escape(site_name)}. {html.escape(footer_tagline)}</p>
          <p>{no_adv}</p>
        </div>
        <div class="footer-col">
          <h3>Platform</h3>
          <ul class="footer-links">
            <li><a href="/tools/" class="touch-target">Calculators</a></li>
            <li><a href="/methodology/" class="touch-target">Statutory Methodology</a></li>
            <li><a href="/disclaimers/" class="touch-target">Regulatory Notices &amp; Disclaimers</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h3>Research &amp; Authority</h3>
          <ul class="footer-links">
            <li><a href="{html.escape(linkedin_url)}" target="_blank" rel="noopener" class="touch-target">{html.escape(site_name)} on LinkedIn</a></li>
            <li><a href="/sitemap.xml" class="touch-target">XML Sitemap</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <div class="footer-entity-meta">
          <p>{html.escape(editorial_policy_text)}</p>
        </div>
      </div>
    </div>
  </footer>
</body>
</html>"""
    assert_no_forbidden_dashes(full_html, context=f"{site_name} rendered HTML")
    return full_html


def build_tools_directory_html(
    all_tools: Sequence[Dict[str, Any]],
    canonical_base: str,
    title: str,
    meta_description: str,
    hero_title: str,
    hero_desc: str,
    quick_answer_text: str,
    procedure_heading: str,
    procedure_steps: Sequence[str],
    table_heading: str,
    grid_heading: str,
    default_authority_col: str,
    org_schema: Dict[str, Any],
    render_base_fn: Any,
) -> str:
    """Renders a tenant's /tools/ directory HTML page with CollectionPage & ItemList JSON-LD."""
    base = canonical_base.rstrip("/")
    canonical_url = f"{base}/tools/"
    schemas = [
        copy.deepcopy(org_schema),
        {
            "@type": "CollectionPage",
            "name": title,
            "url": canonical_url,
            "description": meta_description,
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {"@type": "ListItem", "position": idx + 1, "name": t["title"], "url": f"{base}/tools/{t['slug']}/"}
                    for idx, t in enumerate(all_tools)
                ],
            },
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base}/"},
                {"@type": "ListItem", "position": 2, "name": "Calculators", "item": canonical_url},
            ],
        },
    ]
    rows = []
    cards = []
    for t in all_tools:
        slug = t["slug"]
        t_title = html.escape(t["title"])
        t_desc = html.escape(t["description"])
        auth_col = html.escape(str(t.get("statutory_authority") or default_authority_col))
        rows.append(
            f"<tr><td><strong><a href=\"/tools/{slug}/\" class=\"touch-target\">{t_title}</a></strong></td>"
            f"<td>{t_desc}</td><td>{auth_col}</td>"
            f"<td><a href=\"/tools/{slug}/\" class=\"touch-target\">Open &rarr;</a></td></tr>"
        )
        cards.append(
            f'<li class="tool-link-item"><a href="/tools/{slug}/" class="tool-link touch-target">{t_title}</a>: '
            f'<span class="tool-desc">{t_desc}</span></li>'
        )
    steps_li = "".join(f"<li>{html.escape(st)}</li>" for st in procedure_steps)
    body = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/" class="touch-target">Home</a> / <span>Tools</span></nav>
    <section class="hero-section">
      <h1 class="hero-title">{html.escape(hero_title)}</h1>
      <p class="hero-desc">{html.escape(hero_desc)}</p>
    </section>
    <aside class="quick-answer" role="region" aria-label="Quick Answer Summary">
      <p>{html.escape(quick_answer_text)}</p>
    </aside>
    <section class="card">
      <h2 class="section-title">{html.escape(procedure_heading)}</h2>
      <ol>{steps_li}</ol>
    </section>
    <section class="comparison-table-section">
      <h2 class="section-title">{html.escape(table_heading)}</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th scope="col">Calculator Name</th><th scope="col">Description</th><th scope="col">Statutory / Standard Authority</th><th scope="col">Access</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    <section class="tools-directory-grid-section">
      <h2 class="section-title">{html.escape(grid_heading)}</h2>
      <ul class="tools-list">{''.join(cards)}</ul>
    </section>"""
    return render_base_fn(title, meta_description, canonical_url, body, jsonld_schemas=schemas)


def _strip_llms_monetary_and_formula_leaks(text: str) -> str:
    """Strips dollar figures and formula expressions so llms.txt never leaks pre-computed outputs."""
    clean = str(text or "").replace("\u2014", "-").replace("\u2013", "-").strip()
    clean = re.sub(r"\$[0-9][0-9,]*(?:\.[0-9]+)?", "statutory benchmark", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def cap_llms_txt_content(
    raw_llms: str,
    property_id: str,
    canonical_base: str,
    max_hub_links: int = 5,
) -> str:
    """
    Caps an existing llms.txt document to <= max_hub_links (default 5) top hub links
    with zero dollar outputs, zero formulas, and zero pre-computed answers.
    """
    base = canonical_base.rstrip("/")
    pid = str(property_id or "").strip().lower()
    lines = str(raw_llms or "").replace("\u2014", "-").replace("\u2013", "-").splitlines()
    title_line = next((ln.strip() for ln in lines if ln.strip().startswith("# ")), f"# {pid.title() or 'Site'}")
    tagline_line = next((ln.strip() for ln in lines if ln.strip().startswith("> ")), "")
    if tagline_line:
        tagline_line = "> " + _strip_llms_monetary_and_formula_leaks(tagline_line[2:])

    link_rx = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\)(?::\s*(.*))?$")
    hub_candidates: List[Tuple[str, str, str]] = []
    seen_urls: Set[str] = set()
    for ln in lines:
        m = link_rx.match(ln.strip())
        if not m:
            continue
        lbl, url, desc = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
        if url in seen_urls:
            continue
        # Prefer top-level hub links and top flagship non-spoke tool hubs
        if "/tools/" in url:
            tail = url.split("/tools/", 1)[1].strip("/")
            if "/" in tail:
                continue
        seen_urls.add(url)
        hub_candidates.append((lbl, url, build_feed_scope_teaser(lbl, _strip_llms_monetary_and_formula_leaks(desc))))

    # Ensure core hubs exist and total links <= max_hub_links
    core_hubs: List[Tuple[str, str, str]] = [
        ("Calculators Directory", f"{base}/tools/", f"Interactive calculator directory on {base}."),
    ]
    tool_hubs = [c for c in hub_candidates if "/tools/" in c[1] and c[1].rstrip("/") != f"{base}/tools"]
    doc_hubs = [
        ("Statutory Calculation Methodology", f"{base}/methodology/", "Primary statutory authorities and dataset sources."),
        ("Regulatory Notices and Disclaimers", f"{base}/disclaimers/", "Regulatory disclosures and methodology scope."),
    ]
    selected: List[Tuple[str, str, str]] = []
    used_u: Set[str] = set()
    # Reserve up to 2 slots for doc hubs and 1 for directory, leaving 2 for top flagship tools (total 5)
    for item in core_hubs + tool_hubs[: max(0, max_hub_links - 3)] + doc_hubs:
        if len(selected) >= max_hub_links:
            break
        if item[1] not in used_u:
            used_u.add(item[1])
            selected.append(item)

    bullet_lines = [f"- [{lbl}]({url}): {desc}" for lbl, url, desc in selected]
    out_parts = [title_line]
    if tagline_line:
        out_parts.extend(["", tagline_line])
    out_parts.extend(["", "## Top Hub Links", *bullet_lines])
    if pid == "prexvo":
        out_parts.extend([
            "",
            "## Regulatory Notice",
            "Refinancing federal student loans into a private loan permanently forfeits federal protections.",
        ])
    elif pid == "profithelm":
        out_parts.extend([
            "",
            "## Statutory Disclosure",
            "Circular 230 Notice: Published calculators provide educational modeling only and do not constitute formal tax or legal advice.",
        ])
    result = "\n".join(out_parts).rstrip() + "\n"
    assert_no_forbidden_dashes(result, context=f"{property_id} llms.txt")
    return result


def cap_llms_txt_file(dist: Path, property_id: str, canonical_base: str, max_hub_links: int = 5) -> None:
    """Caps dist/llms.txt in place to <= max_hub_links top hub links."""
    llms_path = dist / "llms.txt"
    if not llms_path.is_file():
        return
    raw = llms_path.read_text(encoding="utf-8", errors="ignore")
    capped = cap_llms_txt_content(raw, property_id=property_id, canonical_base=canonical_base, max_hub_links=max_hub_links)
    if capped != raw:
        llms_path.write_text(capped, encoding="utf-8")


def write_llms_files(
    dist: Path,
    property_id: str,
    domain: str,
    canonical_base: str,
    header_title: str,
    header_tagline: str,
    author: str,
    legal_name: str,
    headquarters: str,
    query_syntax_params: str,
    statutory_notes: str,
    all_tools: Sequence[Dict[str, Any]],
    quick_answers: Dict[str, str],
) -> None:
    """
    Writes lightweight dist/llms.txt capped at <= 5 top hub links (no pre-computed answers,
    no dollar outputs, no formulas) and actively purges dist/llms-full.txt and dist/ai-benchmarks/.
    """
    _ = (domain, author, legal_name, headquarters, query_syntax_params, statutory_notes, quick_answers)
    base = canonical_base.rstrip("/")
    clean_tagline = _strip_llms_monetary_and_formula_leaks(header_tagline)
    non_spoke_tools = [t for t in all_tools if "/" not in str(t.get("slug") or "").strip("/")]
    top_tools = non_spoke_tools[:2]
    tools_lines = "\n".join(
        f"- [{t['title']}]({base}/tools/{t['slug']}/): {build_feed_scope_teaser(str(t.get('title') or ''), _strip_llms_monetary_and_formula_leaks(str(t.get('description') or '')))}"
        for t in top_tools
    )
    seed_txt = (
        f"# {header_title}\n\n"
        f"> {clean_tagline}\n\n"
        "## Top Hub Links\n"
        f"- [Calculators Directory]({base}/tools/): Interactive calculator directory on {base}.\n"
        f"{tools_lines}\n"
        f"- [Statutory Calculation Methodology]({base}/methodology/): Primary statutory authorities and dataset sources.\n"
        f"- [Regulatory Notices and Disclaimers]({base}/disclaimers/): Regulatory disclosures and methodology scope.\n"
    )
    llms_txt = cap_llms_txt_content(seed_txt, property_id=property_id, canonical_base=base, max_hub_links=5)
    (dist / "llms.txt").write_text(llms_txt, encoding="utf-8")

    # Purge zero-click machine dumps
    (dist / "llms-full.txt").unlink(missing_ok=True)
    ai_bench = dist / "ai-benchmarks"
    if ai_bench.exists():
        shutil.rmtree(ai_bench, ignore_errors=True)


def build_thin_estate_builder_source(pkg_name: str) -> str:
    """
    Returns the canonical thin builder.py source emitted into tenant repos during Porcelain shell sync.
    Eliminates duplicate builder scaffolding between sync_tenant_porcelain_shell and tenant compilers.
    """
    norm_pkg = str(pkg_name or "").strip().lower()
    brand_map = {
        "gainhelm": "GainHelm",
        "lienbond": "LienBond",
        "prexvo": "Prexvo",
        "profithelm": "ProfitHelm",
    }
    compile_map = {
        "gainhelm": "compile_gainhelm_estate",
        "lienbond": "compile_lienbond_estate",
        "profithelm": "compile_profithelm_estate",
        "prexvo": "compile_prexvo_estate",
    }
    compat_reexports: Dict[str, Tuple[str, Tuple[str, ...]]] = {
        "gainhelm": (
            "pseofactory.gainhelm_estate",
            (
                "GAINHELM_CALCULATION_MANIFESTS as CALCULATION_MANIFESTS",
                "GAINHELM_TOOL_QUICK_ANSWERS as TOOL_QUICK_ANSWERS",
            ),
        ),
        "profithelm": (
            "pseofactory.profithelm_estate",
            (
                "AFFILIATES",
                "CANONICAL_BASE",
                "CORE_TOOLS",
                "DIST_DIR",
                "PROFITHELM_DOMAIN",
                "PROFITHELM_PROPERTY_ID",
                "REPO_ROOT",
                "SITE_DESCRIPTION",
                "SITE_NAME",
                "SITE_TITLE",
                "TOOL_MULTI_DATASET_REGISTRY",
                "TOOLS",
                "TRUTH_CONSTANTS",
                "CalculatorField",
                "CalculatorMetric",
                "InteractiveCalculatorSpec",
                "build_404_page",
                "build_about_page",
                "build_capital_gains_page",
                "build_crypto_tax_page",
                "build_home_page",
                "build_machine_endpoints",
                "build_prediction_market_page",
                "build_prediction_market_tax_page",
                "build_privacy_page",
                "build_saas_runway_page",
                "build_section_1031_page",
                "build_section_179_page",
                "build_tax_brackets_page",
                "build_tools_directory_page",
                "build_treasury_yield_page",
                "cleanup_orphan_tools",
                "compile_profithelm_estate_impl",
                "compile_schema_graph",
                "enrich_quick_answer_with_statutory_benchmarks",
                "generate_tool_calculation_manifest",
                "get_affiliates_for_category",
                "get_dataset_schema",
                "get_howto_schema",
                "get_organization_schema",
                "get_software_application_schema",
                "get_tech_article_schema",
                "get_web_application_schema",
                "load_profithelm_truth_pack",
                "normalize_html_seo_invariants",
                "reflexive_geo_citability_gate",
                "render_above_the_fold_ftc_disclosure",
                "render_affiliate_card",
                "render_byline",
                "render_calculator_widget",
                "render_contextual_lead_capture",
                "render_footer",
                "render_generic_tool_page",
                "render_head",
                "render_header",
                "render_regulatory_alert_lead_magnet",
                "render_share_and_pro_card",
                "validate_multi_dataset_enrichment",
            ),
        ),
        "prexvo": (
            "pseofactory.prexvo_estate",
            (
                "AFFILIATE_DISCLOSURE",
                "CALCULATION_MANIFESTS",
                "CalculatorField",
                "CalculatorMetric",
                "DISCLAIMER_NO_ADVICE",
                "HHS_POVERTY_GUIDELINES",
                "InteractiveCalculatorSpec",
                "PREXVO_CANONICAL_BASE",
                "PREXVO_CORE_TOOLS",
                "PREXVO_DOMAIN",
                "PREXVO_SITE_DESCRIPTION",
                "PREXVO_SITE_NAME",
                "PREXVO_SITE_TITLE",
                "PREXVO_STATUTORY_VOIDS",
                "PSLF_QUALIFYING_PAYMENTS",
                "RAP_FORGIVENESS_MONTHS",
                "RAP_FORGIVENESS_YEARS",
                "RAP_PRINCIPAL_MATCH_CAP",
                "RAP_UNPAID_INTEREST_SUBSIDY_PCT",
                "REPAYMENT_CALCULATOR_SPEC",
                "YMYL_FORFEITURE_DISCLOSURE",
                "amortize_monthly_payment",
                "build_partners_matrix_section",
                "build_refinance_partner_cta",
                "build_tool_page",
                "calculate_discretionary_income",
                "calculate_ibr_payment",
                "calculate_icr_payment",
                "calculate_paye_payment",
                "calculate_rap_payment",
                "calculate_standard_10yr_payment",
                "calculate_tiered_standard_payment",
                "compare_all_repayment_plans",
                "compile_prexvo_estate_impl",
                "get_calculator_schemas",
                "get_hhs_poverty_guideline",
                "get_tiered_term_years",
                "normalize_interest_rate",
                "normalize_seo_title",
                "normalize_state_group",
                "render_calculator_widget",
            ),
        ),
    }
    copy_files_map: Dict[str, Tuple[str, ...]] = {
        "profithelm": (
            "content/deployed_voids.json",
            ".agy/deployed_voids.json",
            "content/redirects.json",
        ),
        "prexvo": ("content/deployed_voids.json",),
    }
    copy_dirs_map: Dict[str, Tuple[str, ...]] = {
        "profithelm": (
            "content/overlays",
            ".agy/overlays",
            "profithelm/static",
            "profithelm/data",
            "profithelm/datasets",
            "profithelm/engine",
        ),
        "prexvo": (
            "content/overlays",
            ".agy/overlays",
            "prexvo/static",
            "prexvo/datasets",
            "prexvo/engine",
        ),
    }

    brand_label = brand_map.get(norm_pkg, norm_pkg.title())
    compile_fn = compile_map.get(norm_pkg, f"compile_{norm_pkg}_estate")
    extra_exports = ""
    if norm_pkg in compat_reexports:
        mod_path, syms = compat_reexports[norm_pkg]
        joined = ",\n    ".join(syms)
        extra_exports = f"\nfrom {mod_path} import (\n    {joined},\n)\n"

    supports_extra_tools = norm_pkg in ("gainhelm", "profithelm", "prexvo")
    extra_sig = ", extra_tools: Any = None" if supports_extra_tools else ""
    extra_call_kw = ", extra_tools=extra_tools" if supports_extra_tools else ""
    copy_files = copy_files_map.get(
        norm_pkg,
        ("content/deployed_voids.json", f"{norm_pkg}/engine/compliance_formulas.py"),
    )
    copy_dirs = copy_dirs_map.get(
        norm_pkg,
        ("content/overlays", ".agy/overlays", f"{norm_pkg}/static"),
    )
    copy_files_repr = "(" + ", ".join(repr(p) for p in copy_files) + (",)" if len(copy_files) == 1 else ")")
    copy_dirs_repr = "(" + ", ".join(repr(p) for p in copy_dirs) + (",)" if len(copy_dirs) == 1 else ")")

    return (
        f'"""Deterministic {brand_label} estate builder backed by pseofactory compiler."""\n\n'
        "import shutil\n"
        "import tempfile\n"
        "from pathlib import Path\n"
        "from typing import Any, Dict\n\n"
        f"import {norm_pkg}  # noqa: F401\n"
        f"{extra_exports}\n\n"
        f"def build_estate(output_dir: Any = None{extra_sig}) -> Dict[str, Any]:\n"
        f"    from pseofactory.compiler import {compile_fn}\n\n"
        "    target = Path(output_dir).resolve() if output_dir else Path(__file__).resolve().parent.parent\n"
        f"    return {compile_fn}(target, run_retrofit=True{extra_call_kw})\n\n\n"
        f"def build_all(dist_dir: Any = None{extra_sig}) -> Path:\n"
        "    repo_root = Path(__file__).resolve().parent.parent\n"
        "    target_dist = Path(dist_dir).resolve() if dist_dir else (repo_root / 'dist')\n"
        "    if target_dist == (repo_root / 'dist'):\n"
        f"        build_estate(repo_root{extra_call_kw})\n"
        "    else:\n"
        "        with tempfile.TemporaryDirectory() as tmp_d:\n"
        "            tmp_root = Path(tmp_d)\n"
        f"            for rel_src in {copy_files_repr}:\n"
        "                src_f = repo_root / rel_src\n"
        "                if src_f.is_file():\n"
        "                    dst_f = tmp_root / rel_src\n"
        "                    dst_f.parent.mkdir(parents=True, exist_ok=True)\n"
        "                    shutil.copy2(src_f, dst_f)\n"
        f"            for rel_dir in {copy_dirs_repr}:\n"
        "                src_d = repo_root / rel_dir\n"
        "                if src_d.is_dir():\n"
        "                    shutil.copytree(src_d, tmp_root / rel_dir, dirs_exist_ok=True)\n"
        f"            build_estate(tmp_root{extra_call_kw})\n"
        "            if target_dist.exists():\n"
        "                shutil.rmtree(target_dist)\n"
        "            shutil.copytree(tmp_root / 'dist', target_dist)\n"
        "    return target_dist\n"
    )


_TITLE_CORE_STOPWORDS: FrozenSet[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "by", "for", "from",
        "how", "in", "is", "it", "of", "on", "or", "the", "to",
        "with", "your", "this", "that",
    }
)


def _extract_clean_core_title(title_text: str, brand_name: str = "") -> str:
    """Strips leading/trailing 'Brand | ...' or '... | Brand' / '... - Brand' suffix from a page <title>."""
    core_title = re.sub(r"\s+", " ", str(title_text or "")).strip()
    if not core_title:
        return ""
    if brand_name:
        core_title = re.sub(
            rf"\s*(?:\||-)\s*{re.escape(brand_name)}\s*$",
            "",
            core_title,
            flags=re.IGNORECASE,
        ).strip()
        core_title = re.sub(
            rf"^{re.escape(brand_name)}\s*(?:\||-)\s*",
            "",
            core_title,
            flags=re.IGNORECASE,
        ).strip()
    if "|" in core_title:
        head_part, tail_part = core_title.rsplit("|", 1)
        head_part = head_part.strip()
        tail_part = tail_part.strip()
        if head_part and len(tail_part) <= 40:
            if brand_name and head_part.lower() == brand_name.lower():
                core_title = tail_part
            elif not brand_name or tail_part.lower() == brand_name.lower() or " " not in tail_part:
                core_title = head_part
    return core_title


def sync_h1_to_title_core_coverage(
    html_content: str,
    rel_path: str = "",
    brand_name: str = "",
    page_title: Optional[str] = None,
    min_coverage: float = 0.60,
) -> str:
    """
    Computes <h1>-to-<title> core token coverage using the exact same token rule as
    MasterSEOVerifier.check_page_titles_gate and deterministically syncs <h1> text
    to the clean core <title> whenever coverage < required threshold (0.60 on tool leaves,
    0.30 on non-tool pages). Idempotent.
    """
    if not html_content:
        return html_content

    if page_title is not None:
        title_raw = str(page_title)
    else:
        title_m = re.search(r"<title\b[^>]*>(.*?)</title>", html_content, flags=re.IGNORECASE | re.DOTALL)
        if not title_m:
            return html_content
        title_raw = title_m.group(1)

    title_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", title_raw))).strip()
    if not title_text:
        return html_content

    h1_m = re.search(r"(<h1\b[^>]*>)([\s\S]*?)(</h1>)", html_content, flags=re.IGNORECASE)
    if not h1_m:
        return html_content

    h1_text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h1_m.group(2)))).strip()
    if not h1_text:
        return html_content

    h1_tokens = [
        t for t in re.findall(r"[a-z0-9]+", h1_text.lower())
        if len(t) >= 2 and t not in _TITLE_CORE_STOPWORDS
    ]
    seen_h1: Set[str] = set()
    h1_core: List[str] = []
    for tok in h1_tokens:
        if tok not in seen_h1:
            seen_h1.add(tok)
            h1_core.append(tok)

    rel_norm = str(rel_path or "").strip().lstrip("/").lower()
    is_calc_leaf = rel_norm.startswith("tools/") and rel_norm.endswith("/index.html") and rel_norm.count("/") >= 2
    min_tokens = 2 if is_calc_leaf else 3
    if len(h1_core) < min_tokens:
        return html_content

    title_tokens = set(re.findall(r"[a-z0-9]+", title_text.lower()))
    matched = [tok for tok in h1_core if tok in title_tokens]
    coverage = len(matched) / float(len(h1_core))
    eff_min_cov = min_coverage if is_calc_leaf else min(min_coverage, 0.30)
    if coverage >= eff_min_cov:
        return html_content

    core_title = _extract_clean_core_title(title_text, brand_name=brand_name)
    if not core_title or core_title == h1_text:
        return html_content

    escaped_h1 = html.escape(core_title, quote=False)
    return html_content[: h1_m.start(2)] + escaped_h1 + html_content[h1_m.end(2) :]


_PROFITHELM_GONE_TOOL_SLUG_RE = re.compile(
    r"/tools/(?:"
    r"contractor-surety-bond-cost-calculator"
    r"|workers-comp-and-payroll-burden-calculator"
    r"|prediction-market-odds"
    r"|prediction-market-tax"
    r")/?(?:[?#]|$)",
    re.IGNORECASE,
)

_PREXVO_GONE_TOOL_SLUG_RE = re.compile(
    r"/tools/student-loans-gov/?(?:[?#]|$)",
    re.IGNORECASE,
)

_PROFITHELM_RETIRED_URL_REWRITES: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/tools/irs-2027-tax-brackets(?:/[^\"'?#\s<)]*)?/?", re.IGNORECASE), "/tools/irs-tax-brackets/"),
    (re.compile(r"/tools/irs-interest-calculator-2027/?", re.IGNORECASE), "/tools/irs-interest-calculator/"),
    (re.compile(r"/tools/capital-gains-tax-rate-2021-calculator/?", re.IGNORECASE), "/tools/capital-gains-calculator/"),
    (re.compile(r"/tools/1031-exchange-capital-gains-calculator/?", re.IGNORECASE), "/tools/section-1031-calculator/"),
    (re.compile(r"/tools/section-1031-calculator/[a-z0-9-]+/?", re.IGNORECASE), "/tools/section-1031-calculator/"),
    (re.compile(r"/tools/section-179-calculator/[a-z0-9-]+/?", re.IGNORECASE), "/tools/section-179-calculator/"),
)

_PREXVO_RETIRED_URL_REWRITES: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"/tools/parent-plus-double-consolidation-loophole-2026-calculator/?", re.IGNORECASE),
        "/tools/parent-plus-double-consolidation/",
    ),
    (
        re.compile(r"/tools/student-loan-forgiveness-2026/?", re.IGNORECASE),
        "/tools/student-loan-forgiveness/",
    ),
)


def _infer_estate_property_id(html_or_url: str, property_id: str = "") -> str:
    prop_low = str(property_id or "").strip().lower()
    if prop_low:
        return prop_low
    low = str(html_or_url or "").lower()
    if (
        "prexvo.com" in low
        or "/tools/student-loans-gov" in low
        or "/tools/student-loan-forgiveness-2026" in low
        or "parent-plus-double-consolidation-loophole" in low
    ):
        return "prexvo"
    if (
        "profithelm.com" in low
        or "/tools/irs-2027-tax-brackets" in low
        or "/tools/contractor-surety-bond-cost-calculator" in low
    ):
        return "profithelm"
    return ""


def sanitize_retired_estate_url(url: str, property_id: str = "") -> Optional[str]:
    """
    Rewrites retired ProfitHelm/Prexvo internal URLs to canonical active destinations,
    or returns None if the URL targets a 410-decommissioned off-vertical/retired route.
    """
    raw = str(url or "").strip()
    if not raw:
        return raw
    eff_prop = _infer_estate_property_id(raw, property_id)
    if eff_prop not in ("profithelm", "prexvo"):
        return raw

    m_url = re.match(r"^(https?://[^/?#]+)?(/[^?#]*)(.*)$", raw, flags=re.IGNORECASE)
    if not m_url:
        return raw
    origin = m_url.group(1) or ""
    path_part = m_url.group(2) or ""
    tail = m_url.group(3) or ""

    if eff_prop == "profithelm":
        if _PROFITHELM_GONE_TOOL_SLUG_RE.match(path_part):
            return None
        for pat, repl in _PROFITHELM_RETIRED_URL_REWRITES:
            if pat.fullmatch(path_part):
                return f"{origin}{repl}{tail}"
    elif eff_prop == "prexvo":
        if _PREXVO_GONE_TOOL_SLUG_RE.match(path_part):
            return None
        for pat, repl in _PREXVO_RETIRED_URL_REWRITES:
            if pat.fullmatch(path_part):
                return f"{origin}{repl}{tail}"
    return raw


def sanitize_overlay_hub_links(hub_links: Any, property_id: str = "") -> Any:
    """Sanitizes and deduplicates persisted overlay hub_links against retired/410 routes."""
    if not isinstance(hub_links, list):
        return hub_links
    cleaned: List[Dict[str, Any]] = []
    seen_hrefs: Set[str] = set()
    for item in hub_links:
        if not isinstance(item, dict):
            continue
        href = str(item.get("href") or "").strip()
        if not href:
            continue
        new_href = sanitize_retired_estate_url(href, property_id=property_id)
        if new_href is None:
            continue
        norm_key = re.sub(r"^https?://[^/]+", "", new_href).rstrip("/").lower()
        if norm_key in seen_hrefs:
            continue
        seen_hrefs.add(norm_key)
        if new_href != href:
            updated_item = dict(item)
            updated_item["href"] = new_href
            cleaned.append(updated_item)
        else:
            cleaned.append(item)
    return cleaned


def _sanitize_is_related_to_items(rel_val: Any, property_id: str = "") -> Tuple[Any, bool]:
    """Rewrites retired URLs, drops 410-decommissioned URLs, and deduplicates JSON-LD isRelatedTo."""
    if isinstance(rel_val, list):
        out_list: List[Any] = []
        seen_urls: Set[str] = set()
        changed = False
        for item in rel_val:
            if isinstance(item, dict):
                raw_u = item.get("url") or item.get("@id")
                if isinstance(raw_u, str) and "/tools/" in raw_u:
                    new_u = sanitize_retired_estate_url(raw_u, property_id=property_id)
                    if new_u is None:
                        changed = True
                        continue
                    if new_u != raw_u:
                        item = dict(item)
                        if "url" in item:
                            item["url"] = new_u
                        if "@id" in item:
                            item["@id"] = new_u
                        changed = True
                u_key = str(item.get("url") or item.get("@id") or item.get("name") or "").rstrip("/").lower()
                if u_key and u_key in seen_urls:
                    changed = True
                    continue
                if u_key:
                    seen_urls.add(u_key)
                out_list.append(item)
            elif isinstance(item, str) and "/tools/" in item:
                new_u = sanitize_retired_estate_url(item, property_id=property_id)
                if new_u is None:
                    changed = True
                    continue
                if new_u != item:
                    changed = True
                u_key = new_u.rstrip("/").lower()
                if u_key in seen_urls:
                    changed = True
                    continue
                seen_urls.add(u_key)
                out_list.append(new_u)
            else:
                out_list.append(item)
        return out_list, changed

    if isinstance(rel_val, dict):
        raw_u = rel_val.get("url") or rel_val.get("@id")
        if isinstance(raw_u, str) and "/tools/" in raw_u:
            new_u = sanitize_retired_estate_url(raw_u, property_id=property_id)
            if new_u is None:
                return None, True
            if new_u != raw_u:
                out_item = dict(rel_val)
                if "url" in out_item:
                    out_item["url"] = new_u
                if "@id" in out_item:
                    out_item["@id"] = new_u
                return out_item, True
        return rel_val, False

    if isinstance(rel_val, str) and "/tools/" in rel_val:
        new_u = sanitize_retired_estate_url(rel_val, property_id=property_id)
        if new_u is None:
            return None, True
        if new_u != rel_val:
            return new_u, True
    return rel_val, False


def _sanitize_jsonld_node_retired_links(node: Any, property_id: str = "") -> Tuple[Any, bool]:
    """Recursively cleans JSON-LD isRelatedTo references and 410-decommissioned list items."""
    changed = False
    if isinstance(node, list):
        out_list: List[Any] = []
        for elem in node:
            cleaned_elem, elem_changed = _sanitize_jsonld_node_retired_links(elem, property_id=property_id)
            if elem_changed:
                changed = True
            if cleaned_elem is None:
                changed = True
                continue
            out_list.append(cleaned_elem)
        return out_list, changed

    if isinstance(node, dict):
        out_dict = dict(node)
        if "isRelatedTo" in out_dict:
            new_rel, rel_changed = _sanitize_is_related_to_items(out_dict["isRelatedTo"], property_id=property_id)
            if rel_changed:
                changed = True
                if new_rel:
                    out_dict["isRelatedTo"] = new_rel
                else:
                    out_dict.pop("isRelatedTo", None)
        if isinstance(out_dict.get("itemListElement"), list):
            new_ile: List[Any] = []
            ile_changed = False
            for ile_item in out_dict["itemListElement"]:
                if isinstance(ile_item, dict):
                    raw_iu = ile_item.get("item") if isinstance(ile_item.get("item"), str) else ile_item.get("url")
                    if isinstance(raw_iu, str) and "/tools/" in raw_iu:
                        if sanitize_retired_estate_url(raw_iu, property_id=property_id) is None:
                            ile_changed = True
                            continue
                new_ile.append(ile_item)
            if ile_changed:
                changed = True
                for idx_i, ile_obj in enumerate(new_ile, start=1):
                    if isinstance(ile_obj, dict) and "position" in ile_obj:
                        ile_obj["position"] = idx_i
                out_dict["itemListElement"] = new_ile
        if isinstance(out_dict.get("@graph"), list):
            new_g, g_changed = _sanitize_jsonld_node_retired_links(out_dict["@graph"], property_id=property_id)
            if g_changed:
                changed = True
                out_dict["@graph"] = [g for g in new_g if g is not None]
        return out_dict, changed

    return node, False


def sanitize_retired_estate_links_in_html(html_content: str, property_id: str = "") -> str:
    """
    Deterministically rewrites retired ProfitHelm/Prexvo internal links to canonical
    destinations and strips any <a>, <li>, or JSON-LD isRelatedTo references to
    decommissioned 410 off-vertical/retired slugs. Idempotent.
    """
    if not html_content:
        return html_content
    eff_prop = _infer_estate_property_id(html_content, property_id)
    if eff_prop not in ("profithelm", "prexvo"):
        return html_content

    updated = html_content
    gone_re = _PROFITHELM_GONE_TOOL_SLUG_RE if eff_prop == "profithelm" else _PREXVO_GONE_TOOL_SLUG_RE

    def _is_gone_href(href_val: str) -> bool:
        m = re.match(r"^(?:https?://[^/?#]+)?(/[^?#]*)", href_val.strip(), flags=re.IGNORECASE)
        if not m:
            return False
        return bool(gone_re.match(m.group(1)))

    # 1. Strip <li>...</li> wrapping any 410-decommissioned <a>
    def _strip_gone_li(m: re.Match[str]) -> str:
        block = m.group(0)
        for hm in re.finditer(r'\bhref\s*=\s*(["\'])([^"\']+)\1', block, flags=re.IGNORECASE):
            if _is_gone_href(hm.group(2)):
                return ""
        return block

    updated = re.sub(
        r"<li\b[^>]*>(?:(?!</?li\b)[\s\S])*?</li>\s*",
        _strip_gone_li,
        updated,
        flags=re.IGNORECASE,
    )

    # 2. Strip standalone <a href="...">...</a> targeting a 410-decommissioned slug
    def _strip_gone_anchor(m: re.Match[str]) -> str:
        attrs = m.group(1)
        hm = re.search(r'\bhref\s*=\s*(["\'])([^"\']+)\1', attrs, flags=re.IGNORECASE)
        if hm and _is_gone_href(hm.group(2)):
            return ""
        return m.group(0)

    updated = re.sub(
        r"<a\b([^>]*)>[\s\S]*?</a>",
        _strip_gone_anchor,
        updated,
        flags=re.IGNORECASE,
    )

    # 3. Rewrite retired href targets inside <a ...> tags (never mutate <link rel="canonical">)
    def _rewrite_anchor_tag(m: re.Match[str]) -> str:
        tag_open = m.group(0)
        if "/tools/" not in tag_open:
            return tag_open

        def _rewrite_attr(hm: re.Match[str]) -> str:
            prefix, q, raw_href = hm.group(1), hm.group(2), hm.group(3)
            if "/tools/" not in raw_href:
                return hm.group(0)
            new_href = sanitize_retired_estate_url(raw_href, property_id=eff_prop)
            if new_href is None or new_href == raw_href:
                return hm.group(0)
            return f"{prefix}{q}{new_href}{q}"

        return re.sub(
            r'(\bhref\s*=\s*)(["\'])([^"\']+)\2',
            _rewrite_attr,
            tag_open,
            flags=re.IGNORECASE,
        )

    updated = re.sub(
        r"<a\b[^>]*>",
        _rewrite_anchor_tag,
        updated,
        flags=re.IGNORECASE,
    )

    # 4. Deduplicate consecutive or repeated <li><a href="..."> inside <ul> lists when collapsed
    def _dedup_ul_links(m: re.Match[str]) -> str:
        ul_open, ul_inner, ul_close = m.group(1), m.group(2), m.group(3)
        if "/tools/" not in ul_inner or "<ul" in ul_inner.lower():
            return m.group(0)
        seen_hrefs: Set[str] = set()
        changed_ul = False

        def _check_li(li_m: re.Match[str]) -> str:
            nonlocal changed_ul
            li_txt = li_m.group(0)
            hm = re.search(r'\bhref\s*=\s*(["\'])([^"\']+)\1', li_txt, flags=re.IGNORECASE)
            if hm and "/tools/" in hm.group(2):
                h_key = re.sub(r"^https?://[^/]+", "", hm.group(2)).rstrip("/").lower()
                if h_key in seen_hrefs:
                    changed_ul = True
                    return ""
                seen_hrefs.add(h_key)
            return li_txt

        new_inner = re.sub(r"[ \t]*<li\b[^>]*>(?:(?!</?li\b)[\s\S])*?</li>\s*", _check_li, ul_inner, flags=re.IGNORECASE)
        if changed_ul:
            return f"{ul_open}{new_inner}{ul_close}"
        return m.group(0)

    updated = re.sub(
        r"(<ul\b[^>]*>)([\s\S]*?)(</ul>)",
        _dedup_ul_links,
        updated,
        flags=re.IGNORECASE,
    )

    # 5. Clean JSON-LD <script type="application/ld+json"> isRelatedTo / itemListElement
    def _clean_ld_json(m: re.Match[str]) -> str:
        open_t, raw_j, close_t = m.group(1), m.group(2), m.group(3)
        if "/tools/" not in raw_j:
            return m.group(0)
        try:
            parsed = json.loads(raw_j.strip())
        except Exception:
            return m.group(0)
        cleaned_obj, did_change = _sanitize_jsonld_node_retired_links(parsed, property_id=eff_prop)
        if not did_change or cleaned_obj is None:
            return m.group(0)
        return f"{open_t}\n{json.dumps(cleaned_obj, indent=2)}\n{close_t}"

    updated = re.sub(
        r'(<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>)([\s\S]*?)(</script>)',
        _clean_ld_json,
        updated,
        flags=re.IGNORECASE,
    )
    return updated
