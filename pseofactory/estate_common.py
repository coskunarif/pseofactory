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
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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

_LIENBOND_WC_FORBIDDEN_CITATION_RE = re.compile(
    r"(?:"
    r"(?:IRC|26\s*U\.S\.C\.?)\s*(?:Section|Sec\.?)?\s*3111\b"
    r"|40\s*U\.S\.C\.?\s*(?:Section|Sec\.?)?\s*3131(?:-\d+)?\b"
    r"|40\s*U\.S\.C\.?\s*(?:Section|Sec\.?)?\s*3133(?:\([a-zA-Z0-9]+\))?\b"
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


def _scrub_lienbond_wc_citations(val: Any) -> Any:
    """Recursively scrubs non-NCCI citations from LienBond workers-comp/EMR specs and overlays."""
    if isinstance(val, str):
        if _LIENBOND_WC_FORBIDDEN_CITATION_RE.search(val):
            return _LIENBOND_WC_FORBIDDEN_CITATION_RE.sub(_LIENBOND_WC_REPLACEMENT_AUTHORITY, val)
        return val
    if isinstance(val, list):
        return [_scrub_lienbond_wc_citations(item) for item in val]
    if isinstance(val, dict):
        return {k: _scrub_lienbond_wc_citations(v) for k, v in val.items()}
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


MANDATORY_ROBOTS_DISALLOW_PATHS: Tuple[str, ...] = ("/api/", "/cdn-cgi/", "/r/")


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
    named crawler such as Googlebot, Bingbot, PerplexityBot, ClaudeBot, GPTBot,
    OAI-SearchBot, etc.) explicitly disallows every mandatory path before any Allow
    directive in that group.

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


def write_sitemaps_and_robots(
    dist: Path,
    canonical_base: str,
    hub_specs: Sequence[Tuple[str, str, str]],
    leaf_tools: Sequence[Dict[str, Any]],
    ai_bots: Sequence[str],
    disallow_paths: Sequence[str],
    allow_paths: Sequence[str] = ("/",),
    include_changefreq_and_priority: bool = True,
    validate_governor: bool = True,
) -> None:
    """Writes sitemap.xml, sitemap-hubs.xml, sitemap-leaves.xml, and robots.txt."""
    base = canonical_base.rstrip("/")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

    def _entry_xml(url: str, lastmod: str, freq: Optional[str] = None, prio: Optional[str] = None) -> str:
        loc_esc = saxutils.escape(url)
        if not include_changefreq_and_priority:
            return f"  <url><loc>{loc_esc}</loc><lastmod>{lastmod}</lastmod></url>"
        parts = [
            "  <url>",
            f"    <loc>{loc_esc}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
        ]
        if freq:
            parts.append(f"    <changefreq>{freq}</changefreq>")
        if prio:
            parts.append(f"    <priority>{prio}</priority>")
        parts.append("  </url>")
        return "\n".join(parts)

    hub_entries = [
        _entry_xml(url, today_str, freq, prio)
        for url, prio, freq in hub_specs[:150]
        if url in allowed_hubs
    ]
    leaf_entries = [
        _entry_xml(
            f"{base}/tools/{t['slug']}/",
            str(t.get("updated_date") or today_str)[:10],
            "weekly",
            "0.8",
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
    sitemap_hubs_xml = _wrap_urlset(hub_entries)
    sitemap_leaves_xml = _wrap_urlset(leaf_entries)

    for xml_doc in (sitemap_xml, sitemap_hubs_xml, sitemap_leaves_xml):
        ET.fromstring(xml_doc)

    (dist / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    (dist / "sitemap-hubs.xml").write_text(sitemap_hubs_xml, encoding="utf-8")
    (dist / "sitemap-leaves.xml").write_text(sitemap_leaves_xml, encoding="utf-8")

    effective_bots: List[str] = []
    seen_bots: Set[str] = set()
    for bot in ai_bots:
        b_clean = str(bot or "").strip()
        if b_clean and b_clean.lower() not in seen_bots:
            seen_bots.add(b_clean.lower())
            effective_bots.append(b_clean)
    if "*" not in seen_bots:
        effective_bots.insert(0, "*")

    effective_disallows: List[str] = []
    seen_disallows: Set[str] = set()
    for p in list(MANDATORY_ROBOTS_DISALLOW_PATHS) + list(disallow_paths):
        p_clean = str(p or "").strip()
        if p_clean and p_clean.lower() not in seen_disallows:
            seen_disallows.add(p_clean.lower())
            effective_disallows.append(p_clean)

    disallow_lines = "\n".join(f"Disallow: {p}" for p in effective_disallows)
    allow_lines = "\n".join(f"Allow: {p}" for p in allow_paths if str(p or "").strip())
    bot_blocks: List[str] = []
    for bot in effective_bots:
        block_lines = [f"User-agent: {bot}"]
        if disallow_lines:
            block_lines.append(disallow_lines)
        if allow_lines:
            block_lines.append(allow_lines)
        bot_blocks.append("\n".join(block_lines) + "\n")
    sitemap_footer = (
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/sitemap-hubs.xml\n"
        f"Sitemap: {base}/sitemap-leaves.xml\n"
    )
    robots_txt = "\n".join(bot_blocks) + "\n" + sitemap_footer
    robots_txt = ensure_robots_txt_mandatory_disallows(robots_txt)
    assert_no_forbidden_dashes(robots_txt, context="robots.txt")
    (dist / "robots.txt").write_text(robots_txt, encoding="utf-8")


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
    """Writes feed.xml, IndexNow key, catalog.json, media-kit.json, _headers, _redirects, and ai-benchmarks."""
    from pseofactory.distributor import generate_ai_benchmark_nodes
    from pseofactory.edge import build_edge_headers

    base = canonical_base.rstrip("/")
    rss_rows = "\n".join(
        f"    <item>\n"
        f"      <title>{saxutils.escape(str(item.get('title') or ''))}</title>\n"
        f"      <link>{saxutils.escape(str(item.get('url') or ''))}</link>\n"
        f"      <guid>{saxutils.escape(str(item.get('url') or ''))}</guid>\n"
        f"      <description>{saxutils.escape(str(item.get('description') or ''))}</description>\n"
        f"    </item>"
        for item in feed_items
    )
    feed_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{saxutils.escape(feed_title)}</title>\n"
        f"    <link>{base}/</link>\n"
        f"    <description>{saxutils.escape(feed_description)}</description>\n"
        "    <language>en-US</language>\n"
        f'    <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        f"{rss_rows}\n"
        "  </channel>\n"
        "</rss>\n"
    )
    assert_no_forbidden_dashes(feed_xml, context=f"{property_id} feed.xml")
    (dist / "feed.xml").write_text(feed_xml, encoding="utf-8")

    (dist / f"{indexnow_key}.txt").write_text(f"{indexnow_key}\n", encoding="utf-8")

    catalog_doc = json.dumps(
        {"property_id": property_id, "domain": domain, "tools": list(catalog_tools)},
        indent=2,
    )
    assert_no_forbidden_dashes(catalog_doc, context=f"{property_id} catalog.json")
    (dist / "catalog.json").write_text(catalog_doc, encoding="utf-8")

    media_kit_doc = json.dumps(media_kit_payload, indent=2)
    assert_no_forbidden_dashes(media_kit_doc, context=f"{property_id} media-kit.json")
    (dist / "media-kit.json").write_text(media_kit_doc, encoding="utf-8")

    edge_kwargs: Dict[str, Any] = {"routes": list(header_routes)}
    if machine_endpoints is not None:
        edge_kwargs["machine_endpoints"] = list(machine_endpoints)
    if static_patterns is not None:
        edge_kwargs["static_patterns"] = list(static_patterns)
    (dist / "_headers").write_text(build_edge_headers(base, **edge_kwargs), encoding="utf-8")

    if redirects_content is not None:
        (dist / "_redirects").write_text(redirects_content, encoding="utf-8")
    elif not (dist / "_redirects").exists():
        (dist / "_redirects").write_text("", encoding="utf-8")

    ai_benchmarks_dir = dist / "ai-benchmarks"
    ai_benchmarks_dir.mkdir(parents=True, exist_ok=True)
    ai_res = generate_ai_benchmark_nodes(tenant=property_id)
    for fname, fcontent in (ai_res.get("files") or {}).items():
        (ai_benchmarks_dir / fname).write_text(fcontent, encoding="utf-8")


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


def sanitize_tenant_overlays(
    repo_root: Path,
    tools_dir: Path,
    extra_bad_tokens: Sequence[str] = (),
    property_id: str = "",
) -> None:
    """Removes orphaned, cross-tenant contaminated, or cross-framework leaked overlay JSON files."""
    norm_prop = str(property_id or "").strip().lower()
    is_gainhelm = norm_prop == "gainhelm"
    is_lienbond = norm_prop == "lienbond"
    for ov_dir in (repo_root / "content" / "overlays", repo_root / ".agy" / "overlays"):
        if not ov_dir.is_dir():
            continue
        for ov_file in list(ov_dir.glob("*.json")):
            if not (tools_dir / ov_file.stem / "index.html").is_file():
                ov_file.unlink(missing_ok=True)
                continue
            try:
                raw_text = ov_file.read_text(encoding="utf-8")
            except Exception:
                continue
            if extra_bad_tokens and any(bad_tok in raw_text.lower() for bad_tok in extra_bad_tokens):
                ov_file.unlink(missing_ok=True)
                continue
            if is_gainhelm:
                try:
                    ov_data = json.loads(raw_text)
                except Exception:
                    ov_file.unlink(missing_ok=True)
                    continue
                if not isinstance(ov_data, dict):
                    ov_file.unlink(missing_ok=True)
                    continue
                cleaned = strip_cross_framework_leaks_from_overlay(ov_data, ov_file.stem)
                has_content = any(bool(cleaned.get(k)) for k in _OVERLAY_CONTENT_KEYS)
                if not has_content:
                    ov_file.unlink(missing_ok=True)
                elif cleaned != ov_data:
                    ov_file.write_text(
                        json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
            elif is_lienbond and _is_lienbond_wc_slug(ov_file.stem):
                try:
                    ov_data = json.loads(raw_text)
                except Exception:
                    continue
                if not isinstance(ov_data, dict):
                    continue
                cleaned = _scrub_lienbond_wc_citations(ov_data)
                if cleaned != ov_data:
                    ov_file.write_text(
                        json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )


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

    dist_functions = dist / "functions"
    if dist_functions.exists():
        shutil.rmtree(dist_functions, ignore_errors=True)

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
        if starts_with_brand:
            default_pads = (
                f"{base} | Statutory Calculator",
                f"{base} | Modeling Engine",
                f"{base} Calculator Tool",
                f"{base} Cost Model",
            )
        else:
            default_pads = (
                f"{base} | {brand} Statutory Calculator",
                f"{base} | {brand} Modeling Engine",
                f"{base} Calculator Tool{brand_suffix}",
                f"{base} Cost Model{brand_suffix}",
            )
        for tmpl in tuple(pad_candidates) + default_pads:
            cand = (
                tmpl.format(base=base, brand=brand, brand_suffix=effective_suffix)
                if "{base}" in tmpl
                else tmpl
            )
            cand = re.sub(r"\s*\|\s*", " | ", re.sub(r"\|\s*\|+", "|", cand))
            if starts_with_brand and brand and cand.lower().count(brand.lower()) > 1:
                continue
            if min_len <= len(cand) <= max_len:
                return cand

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
            f'<li class="tool-link-item"><a href="/tools/{slug}/" class="tool-link touch-target">{t_title}</a> '
            f'<span class="tool-desc">- {t_desc}</span></li>'
        )
    steps_li = "".join(f"<li>{html.escape(st)}</li>" for st in procedure_steps)
    body = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/" class="touch-target">Home</a> / <span>Calculators</span></nav>
    <section class="hero-section">
      <h1 class="hero-title">{html.escape(hero_title)}</h1>
      <p class="hero-desc">{html.escape(hero_desc)}</p>
    </section>
    <aside class="quick-answer">
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
    """Writes llms.txt and llms-full.txt with zero forbidden dashes."""
    base = canonical_base.rstrip("/")
    tools_lines = "\n".join(f"- [{t['title']}]({base}/tools/{t['slug']}/): {t['description']}" for t in all_tools)
    llms_txt = f"""# {header_title}

> {header_tagline}

## Available Calculators
{tools_lines}

## Documentation
- [Statutory Calculation Methodology]({base}/methodology/)
- [Regulatory Notices and Disclaimers]({base}/disclaimers/)
"""
    assert_no_forbidden_dashes(llms_txt, context=f"{property_id} llms.txt")
    (dist / "llms.txt").write_text(llms_txt, encoding="utf-8")

    sections = []
    for idx, t in enumerate(all_tools, 1):
        slug = t["slug"]
        qa = (quick_answers.get(slug) or t.get("quick_answer") or t["description"]).replace("\u2014", "-").replace("\u2013", "-").strip()
        sections.append(
            f"## {idx}. {t['title']}\n"
            f"Canonical URL: {base}/tools/{slug}/\n"
            f"Query Syntax: {base}/tools/{slug}/{query_syntax_params}\n"
            f"Summary: {t['description']}\n"
            f"Princeton GEO Answer: {qa}\n"
        )
    llms_full = f"""# {header_title}: Complete Machine Knowledge Base & Statutory Manifest
Domain: {domain}
Base URL: {base}
Research Entity: {author}
Legal Entity: {legal_name}
Headquarters: {headquarters}

{chr(10).join(sections)}
{statutory_notes}
"""
    assert_no_forbidden_dashes(llms_full, context=f"{property_id} llms-full.txt")
    (dist / "llms-full.txt").write_text(llms_full, encoding="utf-8")


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
