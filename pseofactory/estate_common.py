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
    """Loads content/deployed_voids.json entries not already compiled and enriches them."""
    dv_file = repo_root / "content" / "deployed_voids.json"
    if not dv_file.is_file():
        return []
    try:
        loaded_dv = json.loads(dv_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(loaded_dv, list):
        return []

    from pseofactory.pipeline import CompetitorGapEngine, TenantFactStore

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
        dv_query = str(dv.get("query") or dv.get("primary_keyword") or dv_slug.replace("-", " ")).strip()
        dv_title = str(dv.get("title") or dv_query.title()).strip()
        dv_spec: Dict[str, Any] = {
            "slug": dv_slug,
            "query": dv_query,
            "primary_keyword": str(dv.get("primary_keyword") or dv_query).strip(),
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
        enriched_voids.append(dv_spec)
        known_slugs.add(dv_slug)

    return enriched_voids


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

    allow_lines = "\n".join(f"Allow: {p}" for p in allow_paths)
    disallow_lines = "\n".join(f"Disallow: {p}" for p in disallow_paths)
    bot_blocks = [
        f"User-agent: {bot}\n{allow_lines}\n{disallow_lines}\n"
        for bot in ai_bots
    ]
    sitemap_footer = (
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/sitemap-hubs.xml\n"
        f"Sitemap: {base}/sitemap-leaves.xml\n"
    )
    robots_txt = "\n".join(bot_blocks) + sitemap_footer
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
    from pseofactory.edge import sync_tenant_edge_redirect_function

    dist_functions = dist / "functions"
    if dist_functions.exists():
        shutil.rmtree(dist_functions, ignore_errors=True)

    (root / "functions" / "r").mkdir(parents=True, exist_ok=True)
    api_dir = root / "functions" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    sync_res = sync_tenant_edge_redirect_function(root, property_id=property_id)
    (api_dir / "checkout.js").write_text(build_edge_checkout_wrapper_js("checkout"), encoding="utf-8")
    (api_dir / "lead-fulfillment.js").write_text(build_edge_checkout_wrapper_js("fulfill"), encoding="utf-8")
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
        ("45 cfr 160", "hipaa", "2,455,313"),
    ),
)


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
        "preset_scenarios",
        "faq_entries",
        "faq_additions",
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
        cleaned_offer = dict(partner_offer)
        if not any(k in slug_low for k in ("soc-2", "soc2")):
            if "/products/soc-2" in str(cleaned_offer.get("url") or "").lower():
                cleaned_offer["url"] = "https://www.vanta.com/"
            if _has_leak(cleaned_offer.get("description") or ""):
                cleaned_offer["description"] = (
                    "Automate continuous control evidence collection, vendor risk tracking, and audit readiness workflows."
                )
            if _has_leak(cleaned_offer.get("cta_text") or ""):
                cleaned_offer["cta_text"] = "Explore Automated GRC Platforms"
        for offer_txt_key in ("name", "badge", "description", "cta_text", "disclosure"):
            if isinstance(cleaned_offer.get(offer_txt_key), str):
                cleaned_offer[offer_txt_key] = normalize_statutory_acronym_casing(cleaned_offer[offer_txt_key])
        cleaned["partner_offer"] = cleaned_offer

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
        "preset_scenarios",
        "faq_entries",
        "faq_additions",
        "faq_schema",
    ):
        if norm_key in cleaned:
            cleaned[norm_key] = _normalize_overlay_statutory_casing(cleaned[norm_key])

    return cleaned


def sanitize_tenant_overlays(
    repo_root: Path,
    tools_dir: Path,
    extra_bad_tokens: Sequence[str] = (),
) -> None:
    """Removes orphaned or cross-tenant contaminated overlay JSON files."""
    for ov_dir in (repo_root / "content" / "overlays", repo_root / ".agy" / "overlays"):
        if not ov_dir.is_dir():
            continue
        for ov_file in list(ov_dir.glob("*.json")):
            if not (tools_dir / ov_file.stem / "index.html").is_file():
                ov_file.unlink(missing_ok=True)
                continue
            if extra_bad_tokens:
                try:
                    raw_ov = ov_file.read_text(encoding="utf-8").lower()
                    if any(bad_tok in raw_ov for bad_tok in extra_bad_tokens):
                        ov_file.unlink(missing_ok=True)
                except Exception:
                    pass


def finalize_estate_build(
    root: Path,
    dist: Path,
    property_id: str,
    canonical_base: str,
    run_retrofit: bool = True,
    bad_overlay_tokens: Sequence[str] = ("profithelm", "section-179-calculator", "section-301-tariff", "coinledger"),
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

    sanitize_tenant_overlays(root, tools_dir, extra_bad_tokens=bad_overlay_tokens)

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
    raw = re.sub(rf"(\s*\|\s*{re.escape(brand)})+", f" | {brand}", raw)

    brand_suffix = f" | {brand}"
    base = raw
    for suffix in (f"| {brand}", f"- {brand}", brand):
        if base.endswith(suffix):
            base = base[: -len(suffix)].strip()
            break
    base = base.rstrip(" |-").strip()

    normalized = f"{base}{brand_suffix}" if base else f"{brand} {default_tagline}"
    if min_len <= len(normalized) <= max_len and "| |" not in normalized:
        return normalized
    if min_len <= len(raw) <= max_len and "| |" not in raw and not raw.endswith((" |", " -")):
        return raw

    if len(normalized) < min_len:
        default_pads = (
            f"{base} | {brand} Statutory Calculator",
            f"{base} | {brand} Modeling Engine",
            f"{base} Calculator Tool{brand_suffix}",
            f"{base} Cost Model{brand_suffix}",
        )
        for tmpl in tuple(pad_candidates) + default_pads:
            cand = tmpl.format(base=base, brand=brand, brand_suffix=brand_suffix) if "{base}" in tmpl else tmpl
            cand = re.sub(r"\s*\|\s*", " | ", re.sub(r"\|\s*\|+", "|", cand))
            if min_len <= len(cand) <= max_len:
                return cand

    stopwords = {"and", "or", "for", "with", "in", "to", "of", "&", "-"}
    if len(normalized) > max_len:
        max_base = max_len - len(brand_suffix)
        min_base = min_len - len(brand_suffix)
        trimmed = base[:max_base]
        while " " in trimmed:
            words = trimmed.rsplit(" ", 1)[0].rstrip(" |-&")
            w_list = words.split()
            while w_list and w_list[-1].lower() in stopwords and " " in words:
                words = words.rsplit(" ", 1)[0].rstrip(" |-&")
                w_list = words.split()
            if len(words) >= min_base and min_len <= len(f"{words}{brand_suffix}") <= max_len:
                return f"{words}{brand_suffix}"
            for pad_w in ("Models", "Engine", "Suite", "Tools", "Guide"):
                padded = f"{words} {pad_w}"
                if min_base <= len(padded) <= max_base:
                    cand = f"{padded}{brand_suffix}"
                    if min_len <= len(cand) <= max_len:
                        return cand
            trimmed = words
        cand = f"{base[:max_base].rstrip(' |-&')}{brand_suffix}"
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
    localbiz_schema: Dict[str, Any],
    title: Optional[str] = None,
    meta_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Assembles a deduplicated JSON-LD @graph linking Organization, WebSite, WebPage, and apps."""
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

    if not any("Organization" in _types(n) or n.get("@id") == org_id for n in raw_nodes):
        raw_nodes.append(copy.deepcopy(org_schema))
    if not any("LocalBusiness" in _types(n) or n.get("@id") == localbiz_id for n in raw_nodes):
        raw_nodes.append(copy.deepcopy(localbiz_schema))
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
    priority = {"Organization": 1, "LocalBusiness": 2, "FinancialService": 2, "WebSite": 3, "WebPage": 4, "BreadcrumbList": 5, "SoftwareApplication": 6, "WebApplication": 7, "FAQPage": 8, "HowTo": 9, "Dataset": 10}
    normalized: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    for node in raw_nodes:
        node.pop("@context", None)
        types = _types(node)
        if "Organization" in types or node.get("@id") == org_id:
            node.setdefault("@id", org_id)
        if "LocalBusiness" in types or node.get("@id") == localbiz_id:
            node.setdefault("@id", localbiz_id)
            node["parentOrganization"] = {"@id": org_id}
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
    from pseofactory.affiliates import resolve_contextual_partner_offer_copy, score_partner_yield

    live_items = [
        (p_id, p_info)
        for p_id, p_info in affiliates.items()
        if getattr(p_info, "status", "") == "live"
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
        return (
            '\n    <section class="partners-section" data-mechanic="compliant_intent_monetization">\n'
            f'      <h2 class="section-title">{html.escape(section_title)}</h2>\n'
            f'      <p class="partners-desc">{html.escape(section_desc_empty)}</p>\n'
            "    </section>"
        )
    return (
        '\n    <section class="partners-section" data-mechanic="compliant_intent_monetization">\n'
        f'      <h2 class="section-title">{html.escape(section_title)}</h2>\n'
        f'      <p class="partners-desc">{html.escape(section_desc_with_cards)}</p>\n'
        f'      <div class="card-grid">{"".join(cards)}</div>\n'
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
    from pseofactory.affiliates import is_restricted_public_service_slug, resolve_contextual_partner_offer_copy

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
    if getattr(ref_partner, "status", "pending") != "live":
        return (
            '\n    <section class="refinance-partner-section" data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">\n'
            '      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">\n'
            f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">{html.escape(fallback_badge)}</span>\n'
            f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html.escape(fallback_title)}</h3>\n'
            f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html.escape(fallback_body)}</p>\n'
            "      </div>\n    </section>"
        )
    p_key = ref_partner.key
    ctx_copy = resolve_contextual_partner_offer_copy(
        partner_key=p_key,
        p_obj=ref_partner,
        slug=slug,
        property_id=getattr(ref_partner, "property_id", "profithelm"),
    )
    return (
        '\n    <section class="refinance-partner-section" data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">\n'
        '      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">\n'
        f'        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--brand-primary); text-transform: uppercase;">{html.escape(ctx_copy.get("badge") or ref_partner.badge or default_featured_badge)}</span>\n'
        f'        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html.escape(ctx_copy.get("name") or ref_partner.name)}</h3>\n'
        f'        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html.escape(ctx_copy.get("description") or ref_partner.description)}</p>\n'
        f'        <a href="/r/{html.escape(p_key)}" target="_blank" rel="noopener sponsored nofollow" class="partner-btn btn-cta touch-target" data-partner="{html.escape(p_key)}" data-cta-slot="calculator_primary_cta" style="display: inline-block; padding: 0.625rem 1.25rem; background: var(--brand-primary); color: #fff; border-radius: 6px; text-decoration: none; font-weight: 600;">\n'
        f'          {html.escape(ctx_copy.get("cta_text") or ref_partner.cta_text or default_cta_text)} &rarr;\n'
        "        </a>\n      </div>\n    </section>"
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

    base_href = canonical_url.split("?")[0]
    preset_links = []
    for label, mult, p_key in (("Conservative (0.8x)", 0.8, "conservative"), ("Baseline (1.0x)", 1.0, "baseline"), ("Aggressive (1.2x)", 1.2, "aggressive")):
        params = [
            f"{k}={int(round(float(v) * mult, 2)) if round(float(v) * mult, 2).is_integer() else round(float(v) * mult, 2)}"
            for k, v in spec_payload["inputs"].items()
            if isinstance(v, (int, float))
        ]
        href = f"{base_href}?{'&amp;'.join(params)}" if params else base_href
        preset_links.append(
            f'        <a href="{href}" data-preset="{p_key}" class="touch-target scenario-preset-link" '
            'style="display: inline-flex; align-items: center; justify-content: center; '
            'min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; '
            f'text-decoration: none; font-size: 14px; font-weight: 600;">{label}</a>'
        )
    manifest_json = json.dumps(spec_payload, ensure_ascii=False, indent=2)
    return f"""
    <section class="multi-dataset-join" data-statutory-source="{stat_auth}" data-economic-source="{econ_ds}" style="margin: 1.5rem 0; padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
      <h2 class="section-title">Dual Dataset Provenance &amp; Statutory Corroboration</h2>
      <p>Primary statutory authority: <strong>{stat_auth}</strong> defines {html.escape(statutory_detail_label)}.</p>
      <p>Empirical economic dataset: <strong>{econ_ds}</strong> provides {html.escape(economic_detail_label)}.</p>
    </section>

    <section class="scenario-presets-section" style="margin: 1.5rem 0; padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
      <h2 class="section-title">Parameterized Scenario Presets &amp; Baseline Verification</h2>
      <p>Verified baseline model calculation output: <strong class="output-value" data-baseline-output="{pub_out}">{display_out}</strong>. Select a parameterized preset below:</p>
      <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets" style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px;">
{chr(10).join(preset_links)}
      </div>
    </section>

    <section class="comparison-table-section" data-entity-type="scenario" data-mechanic="server_rendered_sensitivity_grid" style="margin: 1.5rem 0;">
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
    localbiz_schema: Dict[str, Any],
    footer_tagline: str,
    normalize_title_fn: Optional[Any] = None,
    jsonld_schemas: Optional[Sequence[Dict[str, Any]]] = None,
    css_text: str = "",
) -> str:
    """Renders a complete Porcelain-CSS-compliant HTML shell document for a tenant page."""
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
            localbiz_schema=localbiz_schema,
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
    }
    brand_label = brand_map.get(norm_pkg, norm_pkg.title())
    compile_fn = compile_map.get(norm_pkg, f"compile_{norm_pkg}_estate")
    extra_exports = (
        "\nfrom pseofactory.gainhelm_estate import (\n"
        "    GAINHELM_CALCULATION_MANIFESTS as CALCULATION_MANIFESTS,\n"
        "    GAINHELM_TOOL_QUICK_ANSWERS as TOOL_QUICK_ANSWERS,\n"
        ")\n"
        if norm_pkg == "gainhelm"
        else ""
    )
    extra_sig = ", extra_tools: Any = None" if norm_pkg == "gainhelm" else ""
    extra_call_kw = ", extra_tools=extra_tools" if norm_pkg == "gainhelm" else ""
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
        f"            for rel_src in ('content/deployed_voids.json', '{norm_pkg}/engine/compliance_formulas.py'):\n"
        "                src_f = repo_root / rel_src\n"
        "                if src_f.is_file():\n"
        "                    dst_f = tmp_root / rel_src\n"
        "                    dst_f.parent.mkdir(parents=True, exist_ok=True)\n"
        "                    shutil.copy2(src_f, dst_f)\n"
        f"            for rel_dir in ('content/overlays', '.agy/overlays', '{norm_pkg}/static'):\n"
        "                src_d = repo_root / rel_dir\n"
        "                if src_d.is_dir():\n"
        "                    shutil.copytree(src_d, tmp_root / rel_dir, dirs_exist_ok=True)\n"
        f"            build_estate(tmp_root{extra_call_kw})\n"
        "            if target_dist.exists():\n"
        "                shutil.rmtree(target_dist)\n"
        "            shutil.copytree(tmp_root / 'dist', target_dist)\n"
        "    return target_dist\n"
    )
