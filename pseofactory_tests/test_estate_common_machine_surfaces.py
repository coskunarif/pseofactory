"""
Regression tests for Batch 1B deterministic engine upgrades:
- Split robots.txt bot governance and removal of Disallow: /r/
- Purge of dist/llms-full.txt and dist/ai-benchmarks/ (including maintenance & seo_growth_loops)
- Capped dist/llms.txt (<= 5 hub links, no dollar outputs/formulas/answers, X-Robots-Tag: noindex, nofollow)
- Sanitized dist/catalog.json (slug, title, url, category, updated_at only) and noindex, nofollow header
- Single clean sitemap.xml (<500 URLs) without changefreq/priority/hub lastmod
- Clean feed.xml with RFC 822 pubDate and 1-sentence non-answer scope teaser
- ISO 8601 dates with timezone in compiler.py JSON-LD (no hardcoded 2026-01-15 / 2026-10-31)
- Zero-invocation static edge _routes.json, Content-Signal, HTML Link canonical stripping,
  410 Gone rules, and Stripe Checkout Sessions omitting payment_method_types / automatic_payment_methods.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import email.utils
import json
import re
import subprocess
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pseofactory import compiler
from pseofactory.edge import (
    build_edge_headers,
    build_edge_routes_json,
    compact_edge_headers_to_cloudflare_cap,
    generate_edge_lead_capture_function,
    sync_tenant_edge_redirect_function,
    validate_edge_headers_file,
    validate_edge_redirects_file,
)
from pseofactory.estate_common import (
    GOOGLE_EXTENDED_BOT,
    LIVE_SEARCH_ALLOW_BOTS,
    TRAINING_DISALLOW_BOTS,
    write_llms_files,
    write_machine_endpoints_and_headers,
    write_sitemaps_and_robots,
)


def _assert_no_forbidden_dashes(text: str, ctx: str) -> None:
    assert "\u2014" not in text, f"Em-dash found in {ctx}"
    assert "\u2013" not in text, f"En-dash found in {ctx}"


def test_edge_routes_headers_content_signal_canonical_stripping_and_stripe(tmp_path: Path) -> None:
    routes_data = json.loads(build_edge_routes_json())
    assert routes_data["version"] == 1
    assert routes_data["include"] == ["/api/*", "/r/*", "/llms-full.txt", "/ai-benchmarks/*"]
    assert routes_data["exclude"] == []

    headers_txt = build_edge_headers(
        "https://example.com",
        routes=["/", "/tools/", "/tools/demo-calc/", "/downloads/pack.pdf", "/exports/table.csv"],
    )
    _assert_no_forbidden_dashes(headers_txt, "_headers")
    assert "Content-Signal: ai-train=no, search=yes, ai-input=yes" in headers_txt

    # HTML routes must NOT have Link: ...; rel="canonical"
    assert "/tools/demo-calc/" not in headers_txt
    assert 'Link: <https://example.com/>; rel="canonical"' not in headers_txt
    assert 'Link: <https://example.com/tools/>; rel="canonical"' not in headers_txt
    # Non-HTML downloads & machine endpoints keep RFC 8288 canonical Link headers
    assert 'Link: <https://example.com/downloads/pack.pdf>; rel="canonical"' in headers_txt
    assert 'Link: <https://example.com/exports/table.csv>; rel="canonical"' in headers_txt
    assert 'Link: <https://example.com/feed.xml>; rel="canonical"' in headers_txt

    # /catalog.json and /llms.txt carry X-Robots-Tag: noindex, nofollow
    cat_m = re.search(r"^/catalog\.json\n((?:  .*\n)+)", headers_txt, flags=re.M)
    assert cat_m and "X-Robots-Tag: noindex, nofollow" in cat_m.group(1)
    llms_m = re.search(r"^/llms\.txt\n((?:  .*\n)+)", headers_txt, flags=re.M)
    assert llms_m and "X-Robots-Tag: noindex, nofollow" in llms_m.group(1)

    hp = tmp_path / "_headers"
    hp.write_text(headers_txt, encoding="utf-8")
    val_res = validate_edge_headers_file(hp)
    assert val_res["status"] == "PASS", val_res["issues"]

    # compact_edge_headers_to_cloudflare_cap strips legacy HTML Link canonicals
    legacy_hdr = (
        "/*\n"
        "  Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800\n\n"
        "/tools/legacy-page/\n"
        '  Link: <https://example.com/tools/legacy-page/>; rel="canonical"\n\n'
        "/downloads/report.pdf\n"
        '  Link: <https://example.com/downloads/report.pdf>; rel="canonical"\n'
    )
    compacted = compact_edge_headers_to_cloudflare_cap(legacy_hdr)
    assert "/tools/legacy-page/" not in compacted
    assert "/downloads/report.pdf" in compacted

    # Stripe Checkout Sessions must omit BOTH payment_method_types and automatic_payment_methods
    # so Stripe Dashboard dynamic payment methods apply cleanly (automatic_payment_methods is PaymentIntent-only)
    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond", "customfifth"):
        js_src = generate_edge_lead_capture_function(property_id=prop)
        assert "payment_method_types" not in js_src
        assert "automatic_payment_methods" not in js_src

    from pseofactory.partner_tracker import create_stripe_checkout_session

    session_res = create_stripe_checkout_session(
        property_id="profithelm",
        tool_slug="qbi-deduction-calculator",
        execute_live=False,
    )
    payload_keys = set(session_res["request_payload"].keys())
    assert not any("payment_method_types" in k for k in payload_keys)
    assert not any("automatic_payment_methods" in k for k in payload_keys)


def test_edge_middleware_strips_html_canonical_link_and_serves_410_for_retired_dumps(tmp_path: Path) -> None:
    repo = tmp_path / "tenant"
    (repo / "functions" / "r").mkdir(parents=True)
    dist = repo / "dist"
    dist.mkdir()
    (dist / "_redirects").write_text("/llms-full.txt / 410\n/ai-benchmarks/* / 410\n", encoding="utf-8")

    # Seed legacy middleware containing HTML canonical Link injection
    mw_path = repo / "functions" / "_middleware.js"
    mw_path.write_text(
        "export async function onRequest(context) {\n"
        "  const url = new URL(context.request.url);\n"
        "  const hostname = url.hostname.toLowerCase();\n"
        "  const pathname = url.pathname;\n\n"
        "  const edgeRedirects = {};\n\n"
        "  const response = await context.next();\n"
        '  if (response.status === 200 && !response.headers.get("Link")) {\n'
        '    const ct = (response.headers.get("Content-Type") || "").toLowerCase();\n'
        '    if (ct.includes("text/html") || pathname.endsWith("/")) {\n'
        "      const apexHdrs = new Headers(response.headers);\n"
        '      apexHdrs.set("Link", `<https://example.com${pathname}>; rel=\\"canonical\\"`);\n'
        "      return new Response(response.body, { status: response.status, statusText: response.statusText, headers: apexHdrs });\n"
        "    }\n"
        "  }\n\n"
        "  return response;\n"
        "}\n",
        encoding="utf-8",
    )

    sync_tenant_edge_redirect_function(repo, property_id="lienbond")
    mw_txt = mw_path.read_text(encoding="utf-8")
    assert 'rel=\\"canonical\\"' not in mw_txt
    assert '"/llms-full.txt"' in mw_txt
    assert '"/ai-benchmarks/"' in mw_txt
    assert "status: 410" in mw_txt
    # Invalid 410 lines are stripped from dist/_redirects; _routes.json routes retired dumps to middleware
    redirects_cleaned = (dist / "_redirects").read_text(encoding="utf-8")
    assert "410" not in redirects_cleaned
    routes_obj = json.loads((dist / "_routes.json").read_text(encoding="utf-8"))
    assert routes_obj["include"] == ["/api/*", "/r/*", "/llms-full.txt", "/ai-benchmarks/*"]
    assert routes_obj["exclude"] == []
    assert validate_edge_redirects_file(dist / "_redirects")["status"] == "PASS"

    # Execute generated functions/_middleware.js via Node.js to prove HTTP 410 Gone for /llms-full.txt & /ai-benchmarks/*
    runner = tmp_path / "run_410_check.mjs"
    runner.write_text(
        f"""
import {{ onRequest }} from {json.dumps(str(mw_path.resolve()))};

const paths = ["/llms-full.txt", "/ai-benchmarks/", "/ai-benchmarks/summary.json"];
for (const p of paths) {{
  const res = await onRequest({{
    request: new Request(`https://lienbond.com${{p}}`),
    next: async () => new Response("OK", {{ status: 200 }}),
  }});
  if (res.status !== 410) {{
    console.error("Expected 410 for", p, "got", res.status);
    process.exit(1);
  }}
}}
console.log("OK_410");
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"Node 410 check failed: {proc.stderr}\n{proc.stdout}"
    assert "OK_410" in proc.stdout


def test_single_sitemap_split_robots_clean_feed_and_dump_purge(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    # Pre-seed stale files that MUST be actively deleted
    (dist / "sitemap-hubs.xml").write_text("<urlset/>", encoding="utf-8")
    (dist / "sitemap-leaves.xml").write_text("<urlset/>", encoding="utf-8")
    (dist / "llms-full.txt").write_text("# Stale dump\n", encoding="utf-8")
    (dist / "ai-benchmarks").mkdir()
    (dist / "ai-benchmarks" / "stale.json").write_text("{}", encoding="utf-8")

    hub_specs = [
        ("https://example.com/", "1.0", "daily"),
        ("https://example.com/tools/", "0.9", "daily"),
    ]
    leaf_tools = [
        {"slug": "alpha-calc", "title": "Alpha Calculator", "description": "Calculates alpha margin ratios.", "updated_date": "2026-11-24"},
        {"slug": "beta-calc", "title": "Beta Calculator", "description": "Models beta risk schedules.", "updated_date": "2026-11-24"},
    ]
    write_sitemaps_and_robots(
        dist=dist,
        canonical_base="https://example.com",
        hub_specs=hub_specs,
        leaf_tools=leaf_tools,
        disallow_paths=["/r/", "/signal/", "/staging/"],
    )

    # Single sitemap for <500 URLs; stale hub/leaf split files deleted
    assert (dist / "sitemap.xml").is_file()
    assert not (dist / "sitemap-hubs.xml").exists()
    assert not (dist / "sitemap-leaves.xml").exists()

    sm_text = (dist / "sitemap.xml").read_text(encoding="utf-8")
    assert "<changefreq>" not in sm_text
    assert "<priority>" not in sm_text
    root = ET.fromstring(sm_text)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for url_el in root.findall("s:url", ns):
        loc = url_el.findtext("s:loc", default="", namespaces=ns)
        lastmod = url_el.find("s:lastmod", ns)
        if loc in ("https://example.com/", "https://example.com/tools/"):
            assert lastmod is None, f"Hub URL {loc} must omit <lastmod>"
        else:
            assert lastmod is not None and lastmod.text == "2026-11-24"

    # Split robots.txt governance and zero Disallow: /r/
    robots_txt = (dist / "robots.txt").read_text(encoding="utf-8")
    _assert_no_forbidden_dashes(robots_txt, "robots.txt")
    assert "Disallow: /r/" not in robots_txt
    assert "Sitemap: https://example.com/sitemap-hubs.xml" not in robots_txt
    assert "Sitemap: https://example.com/sitemap.xml" in robots_txt

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    for bot in LIVE_SEARCH_ALLOW_BOTS:
        assert rp.can_fetch(bot, "https://example.com/") is True
        assert rp.can_fetch(bot, "https://example.com/r/partner") is True
        assert rp.can_fetch(bot, "https://example.com/api/lead-capture") is False
        assert rp.can_fetch(bot, "https://example.com/signal/x") is False
    for bot in TRAINING_DISALLOW_BOTS:
        assert rp.can_fetch(bot, "https://example.com/") is False
    assert rp.can_fetch(GOOGLE_EXTENDED_BOT, "https://example.com/") is True
    assert rp.can_fetch(GOOGLE_EXTENDED_BOT, "https://example.com/workpapers/foo") is False
    assert rp.can_fetch(GOOGLE_EXTENDED_BOT, "https://example.com/datasets/bar") is False

    # Machine endpoints + feed.xml + catalog.json + llms.txt + dump purge
    write_machine_endpoints_and_headers(
        dist=dist,
        property_id="gainhelm",
        domain="example.com",
        canonical_base="https://example.com",
        feed_title="Example Feed",
        feed_description="Deterministic modeling calculators.",
        feed_items=[
            {
                "title": "Alpha Calculator",
                "url": "https://example.com/tools/alpha-calc/",
                "description": "Evaluating $100,000 yields $12,345.00 in savings. Second sentence.",
                "updated_date": "2026-11-24",
            },
            {
                "title": "Beta Calculator",
                "url": "https://example.com/tools/beta-calc/",
                "description": "Evaluates compliance readiness scope under NIST controls. Second sentence ignored.",
                "updated_date": "2026-11-24",
            },
        ],
        indexnow_key="abcd1234",
        catalog_tools=[
            {
                "slug": "alpha-calc",
                "title": "Alpha Calculator",
                "url": "https://example.com/tools/alpha-calc/",
                "category": "compliance",
                "updated_date": "2026-11-24",
                "inputs": {"x": 1},
                "formula": "x * 2",
                "published_output": 2.0,
                "quick_answer": "Yields $2.00.",
                "query_syntax": "?x=1",
            }
        ],
        media_kit_payload={"property_id": "gainhelm", "domain": "example.com"},
        header_routes=["/", "/tools/"],
    )
    write_llms_files(
        dist=dist,
        property_id="gainhelm",
        domain="example.com",
        canonical_base="https://example.com",
        header_title="Example Engine",
        header_tagline="Deterministic modeling with $50,000 baseline.",
        author="Research",
        legal_name="Example LLC",
        headquarters="USA",
        query_syntax_params="?x=1",
        statutory_notes="Formula notes",
        all_tools=[
            {"slug": f"tool-{i}", "title": f"Tool {i}", "description": f"Scope for tool {i} ($100 output)."}
            for i in range(10)
        ],
        quick_answers={},
    )

    assert not (dist / "llms-full.txt").exists()
    assert not (dist / "ai-benchmarks").exists()

    # feed.xml: valid RFC 822 pubDate and 1-sentence non-answer teaser
    feed_txt = (dist / "feed.xml").read_text(encoding="utf-8")
    _assert_no_forbidden_dashes(feed_txt, "feed.xml")
    feed_root = ET.fromstring(feed_txt)
    items = feed_root.findall("./channel/item")
    assert len(items) == 2
    for it in items:
        pub_raw = it.findtext("pubDate", default="")
        parsed_dt = email.utils.parsedate_to_datetime(pub_raw)
        assert parsed_dt.year == 2026
        desc = it.findtext("description", default="")
        assert "$" not in desc
        assert "Second sentence" not in desc
        assert desc.count(".") == 1

    # catalog.json: lightweight schema only
    cat_obj = json.loads((dist / "catalog.json").read_text(encoding="utf-8"))
    assert len(cat_obj["tools"]) == 1
    tool_entry = cat_obj["tools"][0]
    assert set(tool_entry.keys()) == {"slug", "title", "url", "category", "updated_at"}

    # llms.txt: <= 5 links, zero dollars/formulas/answers
    llms_txt = (dist / "llms.txt").read_text(encoding="utf-8")
    _assert_no_forbidden_dashes(llms_txt, "llms.txt")
    links = re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", llms_txt)
    assert len(links) <= 5
    assert "$" not in llms_txt

    # _redirects must NOT contain invalid Cloudflare Pages 410 syntax; _routes.json handles retired dumps
    redirects_txt = (dist / "_redirects").read_text(encoding="utf-8")
    assert "410" not in redirects_txt
    routes_obj = json.loads((dist / "_routes.json").read_text(encoding="utf-8"))
    assert routes_obj["include"] == ["/api/*", "/r/*", "/llms-full.txt", "/ai-benchmarks/*"]
    assert routes_obj["exclude"] == []


def test_compiled_estates_purge_dumps_and_emit_iso8601_tz_dates(tmp_path: Path) -> None:
    gh_root = tmp_path / "gainhelm"
    compiler.compile_gainhelm_estate(gh_root, run_retrofit=False)
    gh_dist = gh_root / "dist"
    assert not (gh_dist / "llms-full.txt").exists()
    assert not (gh_dist / "ai-benchmarks").exists()
    assert not (gh_dist / "sitemap-hubs.xml").exists()
    assert not (gh_dist / "sitemap-leaves.xml").exists()
    assert (gh_dist / "sitemap.xml").is_file()

    gh_cat = json.loads((gh_dist / "catalog.json").read_text(encoding="utf-8"))
    for entry in gh_cat["tools"]:
        assert set(entry.keys()) == {"slug", "title", "url", "category", "updated_at"}

    gh_llms = (gh_dist / "llms.txt").read_text(encoding="utf-8")
    assert len(re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", gh_llms)) <= 5
    assert "$" not in gh_llms

    lb_root = tmp_path / "lienbond"
    compiler.compile_lienbond_estate(lb_root, run_retrofit=False)
    lb_dist = lb_root / "dist"
    assert not (lb_dist / "llms-full.txt").exists()
    assert not (lb_dist / "ai-benchmarks").exists()
    assert (lb_dist / "sitemap.xml").is_file()
    assert not (lb_dist / "sitemap-hubs.xml").exists()

    # Check compiler.py JSON-LD uses ISO 8601 dates with timezone (no 2026-01-15 or 2026-10-31)
    lb_tools_idx = (lb_dist / "tools" / "index.html").read_text(encoding="utf-8")
    assert '"2026-01-15"' not in lb_tools_idx
    assert '"2026-10-31"' not in lb_tools_idx
    assert re.search(r'"datePublished":\s*"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})"', lb_tools_idx)
    assert re.search(r'"dateModified":\s*"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})"', lb_tools_idx)

    # feed.xml on LienBond must never leak sample_calculation
    lb_feed = (lb_dist / "feed.xml").read_text(encoding="utf-8")
    assert "$" not in lb_feed
    assert "yields" not in lb_feed.lower()
    assert "<pubDate>" in lb_feed

    # Prexvo estate compile
    from pseofactory.prexvo_estate import compile_prexvo_estate_impl

    px_dist = compile_prexvo_estate_impl(tmp_path / "prexvo" / "dist", run_retrofit=False)
    assert not (px_dist / "llms-full.txt").exists()
    assert not (px_dist / "ai-benchmarks").exists()
    assert (px_dist / "sitemap.xml").is_file()
    assert not (px_dist / "sitemap-hubs.xml").exists()
    px_robots = (px_dist / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /r/" not in px_robots
    assert "User-agent: GPTBot\nDisallow: /api/\nDisallow: /cdn-cgi/\nDisallow: /" in px_robots
    px_llms = (px_dist / "llms.txt").read_text(encoding="utf-8")
    assert len(re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", px_llms)) <= 5
    assert "$" not in px_llms
    px_cat = json.loads((px_dist / "catalog.json").read_text(encoding="utf-8"))
    for entry in px_cat["tools"]:
        assert set(entry.keys()) == {"slug", "title", "url", "category", "updated_at"}

    # ProfitHelm machine endpoints
    from pseofactory.profithelm_estate import build_machine_endpoints

    ph_dist = tmp_path / "profithelm" / "dist"
    build_machine_endpoints(dist_dir=ph_dist)
    assert not (ph_dist / "llms-full.txt").exists()
    assert not (ph_dist / "ai-benchmarks").exists()
    assert (ph_dist / "sitemap.xml").is_file()
    assert not (ph_dist / "sitemap-hubs.xml").exists()
    ph_robots = (ph_dist / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /r/" not in ph_robots
    ph_llms = (ph_dist / "llms.txt").read_text(encoding="utf-8")
    assert len(re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", ph_llms)) <= 5
    assert "$" not in ph_llms
    ph_cat = json.loads((ph_dist / "catalog.json").read_text(encoding="utf-8"))
    for entry in ph_cat["tools"]:
        assert set(entry.keys()) == {"slug", "title", "url", "category", "updated_at"}


def test_maintenance_and_growth_loops_purge_llms_full_and_ai_benchmarks(tmp_path: Path) -> None:
    from pseofactory.maintenance import (
        RetroReflectionEngine,
        _ensure_llms_noindex_in_headers,
        _headers_missing_llms_noindex,
    )

    # _headers_missing_llms_noindex & _ensure_llms_noindex_in_headers do not inject /llms-full.txt
    hdr_only_llms = build_edge_headers("https://example.com", routes=["/"])
    assert "/llms-full.txt" not in hdr_only_llms
    assert _headers_missing_llms_noindex(hdr_only_llms) is False
    ensured = _ensure_llms_noindex_in_headers(hdr_only_llms, "https://example.com")
    assert "/llms-full.txt" not in ensured

    dist = tmp_path / "dist"
    (dist / "tools" / "soc-2-audit-cost-calculator").mkdir(parents=True)
    (dist / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(
        "<!doctype html><html><head><title>SOC 2</title></head><body><h1>SOC 2</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "llms-full.txt").write_text("# Stale\n", encoding="utf-8")
    (dist / "ai-benchmarks").mkdir()
    (dist / "ai-benchmarks" / "stale.json").write_text("{}", encoding="utf-8")
    assert RetroReflectionEngine._has_stale_llms_manifests(dist, "gainhelm") is True
    RetroReflectionEngine.sync_tenant_llms_manifests(dist, "gainhelm", canonical_base="https://gainhelm.com")
    assert not (dist / "llms-full.txt").exists()
    assert not (dist / "ai-benchmarks").exists()
