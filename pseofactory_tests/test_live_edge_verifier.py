"""
Comprehensive Unit Tests for Edge Standards & LiveEdgeVerifier.
Validates:
1. EdgeConfigStandards & build_edge_headers syntax.
2. HostHygieneAuditor detecting firebase.json noindex.
3. LiveEdgeVerifier multi-bot simulation matrix.
4. LiveEdgeVerifier two-phase cache hit verification.
5. LiveEdgeVerifier bot challenge wall fail-closed detection.
6. LiveEdgeVerifier machine-extractable content structure parsing.
7. MasterSEOVerifier Gates 29 & 30 execution.
Zero em-dashes. Zero en-dashes.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, List
import pytest

from pseofactory.edge import (
    EdgeConfigStandards,
    HostHygieneAuditor,
    build_edge_headers,
    validate_edge_headers_file,
)
from pseofactory.gitops import LiveEdgeVerifier
from pseofactory.verifier import MasterSEOVerifier


def test_edge_config_standards_emits_valid_headers():
    """1. EdgeConfigStandards and build_edge_headers produce valid Cloudflare headers."""
    canonical = "https://example.com"
    routes = ["/", "/tools/", "/tools/calc/"]
    headers_text = build_edge_headers(canonical, routes=routes)

    # Static caching directives
    assert "Cache-Control: public, max-age=31536000, immutable" in headers_text
    # Root HTML caching directives
    assert "/*" in headers_text
    assert "s-maxage=86400" in headers_text
    assert "stale-while-revalidate=604800" in headers_text
    # Security headers
    assert "X-Content-Type-Options: nosniff" in headers_text
    assert "X-Frame-Options: SAMEORIGIN" in headers_text
    # 404 error caching
    assert "/404.html" in headers_text
    assert "no-store" in headers_text
    # Machine endpoints canonical links and content types
    assert '/feed.xml' in headers_text
    assert 'Link: <https://example.com/feed.xml>; rel="canonical"' in headers_text
    assert 'Content-Type: application/xml; charset=utf-8' in headers_text
    assert '/llms.txt' in headers_text
    assert 'Link: <https://example.com/llms.txt>; rel="canonical"' in headers_text
    assert 'Content-Type: text/plain; charset=utf-8' in headers_text


def test_host_hygiene_auditor_detects_firebase_noindex(tmp_path: Path):
    """2. HostHygieneAuditor detects lethal noindex on wildcard in firebase.json."""
    # Lethal configuration
    bad_config = {
        "hosting": {
            "headers": [
                {
                    "source": "**",
                    "headers": [
                        {"key": "X-Robots-Tag", "value": "noindex, nofollow"}
                    ],
                }
            ]
        }
    }
    fb_file = tmp_path / "firebase.json"
    fb_file.write_text(json.dumps(bad_config), encoding="utf-8")

    res_fail = HostHygieneAuditor.audit_repo_host_configs(tmp_path)
    assert res_fail["status"] == "FAIL"
    assert any("lethal X-Robots-Tag" in issue for issue in res_fail["issues"])

    # Clean configuration with edge cache retention
    clean_config = {
        "hosting": {
            "headers": [
                {
                    "source": "**/*.@(html|xml|txt|json)",
                    "headers": [
                        {
                            "key": "Cache-Control",
                            "value": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
                        }
                    ],
                }
            ]
        }
    }
    fb_file.write_text(json.dumps(clean_config), encoding="utf-8")

    res_pass = HostHygieneAuditor.audit_repo_host_configs(tmp_path)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0


def test_live_edge_verifier_multi_bot_matrix_simulation():
    """3. LiveEdgeVerifier probes with all 7 bot user-agents in AI_BOT_PROBE_MATRIX."""
    captured_uas: List[str] = []

    class MultiBotHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            ua = self.headers.get("User-Agent", "")
            captured_uas.append(ua)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>OK</h1></body></html>")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), MultiBotHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        verifier = LiveEdgeVerifier(timeout=5.0)
        url = f"http://127.0.0.1:{port}/"
        audit = verifier.simulate_multi_bot_crawl([url])

        assert audit["status"] == "PASS"
        assert audit["total_probes"] == 7
        assert audit["passed_probes"] == 7
        for bot_name, ua in LiveEdgeVerifier.AI_BOT_PROBE_MATRIX.items():
            assert ua in captured_uas
    finally:
        server.shutdown()
        server.server_close()


def test_live_edge_verifier_two_phase_probe_cache_hit():
    """4. LiveEdgeVerifier two-phase probe validates cold MISS and warm repeat HIT."""
    request_count = 0

    class CacheHitHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal request_count
            request_count += 1
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800")
            if request_count == 1:
                self.send_header("cf-cache-status", "MISS")
            else:
                self.send_header("cf-cache-status", "HIT")
                self.send_header("Age", "12")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Cache Test</h1></body></html>")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), CacheHitHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        verifier = LiveEdgeVerifier(timeout=5.0)
        url = f"http://127.0.0.1:{port}/"
        res = verifier.probe_two_phase(url)

        assert res["status"] == "PASS"
        assert res["cache_hit"] is True
        assert res["cold_phase"]["status"] == "PASS"
        assert res["warm_phase"]["cache_hit"] is True
        assert res["warm_phase"]["status"] == "PASS"
    finally:
        server.shutdown()
        server.server_close()


def test_live_edge_verifier_fails_on_bot_challenge_wall():
    """5. LiveEdgeVerifier detects cf-mitigated: challenge and fails closed."""
    class ChallengeWallHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(403)
            self.send_header("cf-mitigated", "challenge")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body>Cloudflare Challenge Platform Turnstile</body></html>")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), ChallengeWallHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        verifier = LiveEdgeVerifier(timeout=5.0)
        url = f"http://127.0.0.1:{port}/"
        res = verifier.probe_two_phase(url)

        assert res["status"] == "FAIL"
        assert res["error"] == "BOT_CHALLENGE_WALL_DETECTED"
        assert "BOT_CHALLENGE_WALL_DETECTED" in res["issues"]
    finally:
        server.shutdown()
        server.server_close()


def test_live_edge_verifier_content_structure_parser():
    """6. LiveEdgeVerifier.verify_content_structure validates headings, quick-answer, table scope, and JSON-LD."""
    verifier = LiveEdgeVerifier()

    # Valid HTML document
    valid_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Valid Document</title>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "WebApplication", "name": "Tax Calculator"}
        </script>
    </head>
    <body>
        <h1>Federal Tax Calculator 2027</h1>
        <aside class="quick-answer">
            The federal tax bracket for 2027 establishes a 22 percent rate on median statutory income.
        </aside>
        <h2>Methodology and Assumptions</h2>
        <p>Detailed description here.</p>
        <h3>Calculation Parameters</h3>
        <table>
            <thead>
                <tr>
                    <th scope="col">Filing Status</th>
                    <th scope="col">Statutory Rate</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Single</td>
                    <td>22%</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    res_valid = verifier.verify_content_structure(valid_html)
    assert res_valid["status"] == "PASS"
    assert res_valid["violations_count"] == 0

    # 1. Skipped heading level (H1 followed directly by H3)
    skip_heading_html = "<html><body><h1>Apex</h1><h3>Skipped Subhead</h3></body></html>"
    res_skip = verifier.verify_content_structure(skip_heading_html)
    assert res_skip["status"] == "FAIL"
    assert any("Heading level skip" in issue for issue in res_skip["issues"])

    # 2. Quick-answer with lethal data-nosnippet directive
    nosnippet_html = """
    <html><body>
        <h1>Apex Title</h1>
        <aside class="quick-answer" data-nosnippet="true">
            This quick answer is shielded from AI crawlers.
        </aside>
    </body></html>
    """
    res_nosnippet = verifier.verify_content_structure(nosnippet_html)
    assert res_nosnippet["status"] == "FAIL"
    assert any("data-nosnippet" in issue for issue in res_nosnippet["issues"])

    # 3. Data table with missing scope attribute on <th>
    unscoped_table_html = """
    <html><body>
        <h1>Apex Title</h1>
        <table>
            <tr><th>Header Without Scope</th></tr>
            <tr><td>Data Cell</td></tr>
        </table>
    </body></html>
    """
    res_table = verifier.verify_content_structure(unscoped_table_html)
    assert res_table["status"] == "FAIL"
    assert any("scope attribute" in issue for issue in res_table["issues"])

    # 4. Invalid JSON-LD syntax
    invalid_jsonld_html = """
    <html><head>
        <h1>Apex Title</h1>
        <script type="application/ld+json">
        {invalid: json ld syntax, missing quotes}
        </script>
    </head></html>
    """
    res_jsonld = verifier.verify_content_structure(invalid_jsonld_html)
    assert res_jsonld["status"] == "FAIL"
    assert any("JSON-LD" in issue for issue in res_jsonld["issues"])


def test_master_seo_verifier_gates_29_and_30(tmp_path: Path):
    """7. MasterSEOVerifier Gates 29 & 30 execution on host hygiene and edge cache policy."""
    verifier = MasterSEOVerifier(dist_dir=tmp_path / "dist")

    # Gate 29: Host hygiene defect detection
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    fb_file = repo_dir / "firebase.json"
    fb_file.write_text(json.dumps({
        "hosting": {
            "headers": [
                {
                    "source": "**",
                    "headers": [{"key": "X-Robots-Tag", "value": "noindex"}]
                }
            ]
        }
    }), encoding="utf-8")

    gate_29_fail = verifier.check_host_hygiene_gate(repo_dir)
    assert gate_29_fail["status"] == "FAIL"
    assert gate_29_fail["gate"] == "check_host_hygiene_gate"

    # Fix firebase.json
    fb_file.write_text(json.dumps({
        "hosting": {
            "headers": [
                {
                    "source": "**/*.@(html|xml|txt|json)",
                    "headers": [{"key": "Cache-Control", "value": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800"}]
                }
            ]
        }
    }), encoding="utf-8")
    gate_29_pass = verifier.check_host_hygiene_gate(repo_dir)
    assert gate_29_pass["status"] == "PASS"

    # Gate 30: Edge cache policy check in dist/_headers
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    headers_file = dist_dir / "_headers"

    # Missing s-maxage on /*
    headers_file.write_text("/*\n  Cache-Control: public, max-age=3600\n", encoding="utf-8")
    gate_30_fail = verifier.check_edge_cache_policy_gate(dist_dir)
    assert gate_30_fail["status"] == "FAIL"
    assert gate_30_fail["gate"] == "check_edge_cache_policy_gate"

    # Compliant _headers generated via build_edge_headers
    valid_headers_text = build_edge_headers("https://example.com", routes=["/"])
    headers_file.write_text(valid_headers_text, encoding="utf-8")
    gate_30_pass = verifier.check_edge_cache_policy_gate(dist_dir)
    assert gate_30_pass["status"] == "PASS"


def test_live_edge_verifier_rejects_stale_figures_and_local_dist_divergence(tmp_path: Path):
    """8. LiveEdgeVerifier.verify_edge_deployment fails closed on stale live HTML figures and dateModified mismatch."""
    dist_dir = tmp_path / "gainhelm_dist"
    soc2_dir = dist_dir / "tools" / "soc-2-audit-cost-calculator"
    hipaa_dir = dist_dir / "tools" / "hipaa-violation-penalty-breach-cost-calculator"
    soc2_dir.mkdir(parents=True)
    hipaa_dir.mkdir(parents=True)

    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (dist_dir / "sitemap.xml").write_text("<urlset><url><loc>https://gainhelm.com/</loc></url></urlset>", encoding="utf-8")
    (dist_dir / "llms.txt").write_text("# GainHelm\n", encoding="utf-8")

    fresh_index = (
        '<!doctype html><html><head><title>GainHelm</title>'
        '<link rel="canonical" href="https://gainhelm.com/">'
        '<style id="pseo-visual-primitives">.card{contain: layout style}</style>'
        '<script type="application/ld+json">{"@context":"https://schema.org","dateModified":"2026-10-31"}</script>'
        '</head><body><p>4 penalty tiers ($141 to $2,067,813 annual cap per identical provision)</p></body></html>'
    )
    fresh_soc2 = (
        '<!doctype html><html><head><title>SOC 2 Audit Cost Calculator</title>'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '<style id="pseo-visual-primitives">.card{contain: layout style}</style>'
        '<script type="application/ld+json">{"@context":"https://schema.org","dateModified":"2026-10-31"}</script>'
        '</head><body>'
        '<p class="calc-geo-answer-text">For a 75-employee enterprise, total first-year compliance investment totals $78,100.40.</p>'
        '<span id="metric-soc2_total_cost">$78,100.40</span>'
        '<script type="application/json" class="calculation-manifest">'
        '{"published_output": 78100.4, "formula": "cpa_fee + grc_cost + pentest + labor", "inputs": {"cpa_fee": 35000, "grc_cost": 16500, "pentest": 12000, "labor": 14600.4}}'
        '</script></body></html>'
    )
    fresh_hipaa = (
        '<!doctype html><html><head><title>HIPAA Violation Penalty Calculator</title>'
        '<link rel="canonical" href="https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/">'
        '<style id="pseo-visual-primitives">.card{contain: layout style}</style>'
        '<script type="application/ld+json">{"@context":"https://schema.org","dateModified":"2026-10-31"}</script>'
        '</head><body><p>Annual cap $2,067,813 under 45 CFR 160.404.</p>'
        '<script type="application/json" class="calculation-manifest">'
        '{"published_output": 2455313.0, "formula": "min(records * per_violation, 2067813.0) + forensics", "inputs": {"records": 500, "per_violation": 68928.0, "forensics": 387500.0}}'
        '</script></body></html>'
    )
    (dist_dir / "index.html").write_text(fresh_index, encoding="utf-8")
    (soc2_dir / "index.html").write_text(fresh_soc2, encoding="utf-8")
    (hipaa_dir / "index.html").write_text(fresh_hipaa, encoding="utf-8")

    verifier = LiveEdgeVerifier(timeout=2, retries=1)
    stale_index = fresh_index.replace('"2026-10-31"', '"2026-10-27"').replace("$2,067,813", "$2,134,831")
    stale_soc2 = fresh_soc2.replace('"2026-10-31"', '"2026-10-27"').replace(
        "totals $78,100.40.", "totals $78,100.00."
    )
    stale_hipaa = fresh_hipaa.replace('"2026-10-31"', '"2026-10-27"').replace(
        "$2,067,813", "$2,134,831"
    ).replace("2067813.0", "2134831.0")

    idx_issues = verifier.audit_live_versus_local_html(
        live_html=stale_index, local_html=fresh_index, property_id="gainhelm", rel_path="index.html"
    )
    assert any("$2,134,831" in v for v in idx_issues)
    assert any("dateModified mismatch" in v for v in idx_issues)

    soc2_issues = verifier.audit_live_versus_local_html(
        live_html=stale_soc2,
        local_html=fresh_soc2,
        property_id="gainhelm",
        rel_path="tools/soc-2-audit-cost-calculator/index.html",
    )
    assert any("78,100.00" in v and "78,100.40" in v for v in soc2_issues)

    hipaa_issues = verifier.audit_live_versus_local_html(
        live_html=stale_hipaa,
        local_html=fresh_hipaa,
        property_id="gainhelm",
        rel_path="tools/hipaa-violation-penalty-breach-cost-calculator/index.html",
    )
    assert any("2134831" in v or "$2,134,831" in v for v in hipaa_issues)

    assert verifier.audit_live_versus_local_html(
        live_html=fresh_soc2,
        local_html=fresh_soc2,
        property_id="gainhelm",
        rel_path="tools/soc-2-audit-cost-calculator/index.html",
    ) == []


def test_live_edge_verifier_full_monetization_checkout_and_partner_slot_matrix(tmp_path: Path):
    """9. LiveEdgeVerifier.verify_edge_functions validates checkout session creation, $299 partner slot, partner_registration POST, 402 gate, and multi-partner 302 redirects."""
    from pseofactory.browser_verifier import LienBondBrowserAdapter, RouteManifestExtractor
    from pseofactory.server import EphemeralDistServer

    for idx, slug in enumerate(("alpha-calc", "beta-calc", "gamma-calc", "delta-calc")):
        d = tmp_path / "tools" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(f"<html><body><h1>{slug}</h1></body></html>", encoding="utf-8")
    (tmp_path / "index.html").write_text("<html><body><h1>Home</h1></body></html>", encoding="utf-8")

    extractor = RouteManifestExtractor(tmp_path)
    all_routes = extractor.extract_routes()
    smart_routes = extractor.select_smart_routes(all_routes, 3)
    assert len(smart_routes) == 3
    assert "/" in smart_routes
    assert any(r.startswith("/tools/") and r != "/tools/" for r in smart_routes)

    lb_adapter = LienBondBrowserAdapter()
    assert lb_adapter.tenant_id == "lienbond"
    assert len(lb_adapter.get_widget_specs()) >= 2

    verifier = LiveEdgeVerifier(timeout=5.0, retries=1)
    for prop_id in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        with EphemeralDistServer(tmp_path, property_id=prop_id) as srv:
            res = verifier.verify_edge_functions(srv.base_url, property_id=prop_id)
            assert res["status"] == "PASS", f"verify_edge_functions failed for {prop_id}: {res}"
            assert res["issues"] == []
            routes_map = res["routes"]
            assert routes_map["GET /api/lead-capture?checkout=1&format=json"]["status"] == "PASS"
            assert routes_map["POST /api/lead-capture (partner_registration)"]["status"] == "PASS"
            assert routes_map["GET /api/lead-fulfillment"]["status"] == "PASS"
            assert routes_map["GET /api/lead-fulfillment"]["status_code"] == 402
            redir_keys = [k for k in routes_map if k.startswith("GET /r/")]
            assert len(redir_keys) >= 2
            assert all(routes_map[rk]["status"] == "PASS" for rk in redir_keys)


def test_verify_edge_functions_accepts_canonical_operator_mailbox_and_auth_required_health_while_failing_foreign_domain_leaks():
    import http.server
    import json
    import threading
    from urllib.parse import parse_qs, urlparse

    leak_mode = {"inject_foreign_url": False}

    class _HardenedPrexvoHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_json(self, code: int, body: dict):
            raw = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path.startswith("/r/"):
                self.send_response(302)
                self.send_header("Location", "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/")
                self.end_headers()
                return
            if parsed.path == "/api/lead-fulfillment":
                self._send_json(402, {"ok": False, "status": "payment_required", "settled": False})
                return
            if parsed.path == "/api/checkout":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "checkout_session_ready",
                        "property_id": "prexvo",
                        "stripe_merchant_email": "arif.coskun@profithelm.com",
                    },
                )
                return
            if parsed.path == "/api/lead-capture":
                if qs.get("playbook") == ["1"]:
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "status": "playbook_ready",
                            "property_id": "prexvo",
                            "reconciliation_schedule": [1, 2, 3],
                        },
                    )
                    return
                if qs.get("checkout") == ["1"]:
                    sku = (qs.get("sku") or ["px_refi_amortization_decision_audit"])[0]
                    price = 299.0 if sku == "px_verified_partner_slot" else 39.0
                    cancel_url = (
                        "https://profithelm.com/leak/"
                        if leak_mode["inject_foreign_url"]
                        else "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/"
                    )
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "status": "checkout_session_ready",
                            "checkout_mode": "stripe_live_session",
                            "checkout_url": "https://checkout.stripe.com/c/pay/cs_live_test",
                            "cancel_url": cancel_url,
                            "property_id": "prexvo",
                            "offer_sku": sku,
                            "offer_price_usd": price,
                            "stripe_display_name": "Prexvo",
                            "stripe_merchant_email": "arif.coskun@profithelm.com",
                        },
                    )
                    return
                # Hardened unauthenticated synthetic health response (no property_id)
                self._send_json(200, {"ok": True, "auth_required": True})
                return
            self._send_json(404, {"ok": False})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if body.get("intent") == "partner_registration":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "partner_registered",
                        "offer_sku": "px_verified_partner_slot",
                        "offer_price_usd": 299.0,
                        "stripe_merchant_email": "arif.coskun@profithelm.com",
                    },
                )
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "synthetic_test": True,
                    "persisted": False,
                    "property_id": "prexvo",
                    "stripe_merchant_email": "arif.coskun@profithelm.com",
                },
            )

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _HardenedPrexvoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        verifier = LiveEdgeVerifier(timeout=5.0, retries=1)
        res_ok = verifier.verify_edge_functions(base_url, property_id="prexvo")
        assert res_ok["status"] == "PASS", res_ok
        assert res_ok["issues"] == []

        leak_mode["inject_foreign_url"] = True
        res_leak = verifier.verify_edge_functions(base_url, property_id="prexvo")
        assert res_leak["status"] == "FAIL"
        assert any("GET /api/lead-capture?checkout=1&format=json failed" in i for i in res_leak["issues"])
    finally:
        server.shutdown()
        server.server_close()


def test_live_edge_verifier_tenant_partner_route_selection_and_synthetic_telemetry_suppression(tmp_path: Path):
    """10. LiveEdgeVerifier selects tenant-isolated non-declined partner routes across all 4 tenants and sends synthetic_test=1 + X-Pseofactory-Test: 1."""
    import http.server
    import json
    import threading
    from urllib.parse import parse_qs, urlparse
    from pseofactory.edge import generate_edge_redirect_function

    expected_cohorts = {
        "profithelm": ("mercury", "xendoo", "lawdepot"),
        "prexvo": ("splash_financial", "credible", "lendkey"),
        "gainhelm": ("vanta_security", "drata_compliance", "sprinto_compliance"),
        "lienbond": ("suretybonds_direct", "simply_business", "thimble_contractor"),
    }
    for prop_id, exp_cohort in expected_cohorts.items():
        assert LiveEdgeVerifier.resolve_tenant_partner_probe_cohort(prop_id) == exp_cohort
        if prop_id != "profithelm":
            assert "lawdepot" not in exp_cohort
        assert "sofi_refi" not in exp_cohort
        assert "earnest" not in exp_cohort
        assert "next_insurance_b2b" not in exp_cohort

        # Also verify against compiled functions/r/[partner].js inside a tenant dist_dir
        prop_dist = tmp_path / prop_id / "dist"
        r_dir = prop_dist / "functions" / "r"
        r_dir.mkdir(parents=True, exist_ok=True)
        (r_dir / "[partner].js").write_text(generate_edge_redirect_function(prop_id), encoding="utf-8")
        assert LiveEdgeVerifier.resolve_tenant_partner_probe_cohort(prop_id, dist_dir=prop_dist) == exp_cohort

    # Verify dynamic extraction from functions/r/[[partner]].js filters out declined partners
    custom_dist = tmp_path / "custom_tenant" / "dist"
    custom_r_dir = custom_dist / "functions" / "r"
    custom_r_dir.mkdir(parents=True, exist_ok=True)
    (custom_r_dir / "[[partner]].js").write_text(
        """
        const CATALOG = {
          declined_offer: {
            defaultUrl: "https://example.com/declined",
            status: "declined",
          },
          suretybonds_direct: {
            defaultUrl: "https://www.suretybondsdirect.com/",
            status: "pending",
          },
          simply_business: {
            defaultUrl: "https://www.simplybusiness.com/",
            status: "pending",
          },
        };
        """,
        encoding="utf-8",
    )
    resolved_custom = LiveEdgeVerifier.resolve_tenant_partner_probe_cohort("custom_tenant", dist_dir=custom_dist)
    assert resolved_custom == ("suretybonds_direct", "simply_business")
    assert "declined_offer" not in resolved_custom
    assert "lawdepot" not in resolved_custom

    # Verify LienBond edge function probing passes when /r/lawdepot is 404 and enforces synthetic_test=1 + X-Pseofactory-Test: 1
    captured_redirects = []

    class _IsolatedLienBondHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_json(self, code: int, body: dict):
            raw = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path.startswith("/r/"):
                slug = parsed.path[len("/r/") :].strip("/")
                captured_redirects.append(
                    {
                        "slug": slug,
                        "synthetic_query": qs.get("synthetic_test"),
                        "synthetic_header": self.headers.get("X-Pseofactory-Test"),
                    }
                )
                if slug in ("suretybonds_direct", "simply_business", "thimble_contractor"):
                    self.send_response(302)
                    self.send_header("Location", f"https://lienbond.com/tools/bond-calc/?p={slug}")
                    self.end_headers()
                    return
                self._send_json(404, {"ok": False, "error": "foreign_or_unknown_partner"})
                return
            if parsed.path == "/api/lead-fulfillment":
                self._send_json(402, {"ok": False, "status": "payment_required", "settled": False})
                return
            if parsed.path == "/api/checkout":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "checkout_session_ready",
                        "property_id": "lienbond",
                        "stripe_merchant_email": "arif.coskun@profithelm.com",
                    },
                )
                return
            if parsed.path == "/api/lead-capture":
                if qs.get("playbook") == ["1"]:
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "status": "playbook_ready",
                            "property_id": "lienbond",
                            "reconciliation_schedule": [1, 2, 3],
                        },
                    )
                    return
                if qs.get("checkout") == ["1"]:
                    sku = (qs.get("sku") or ["lb_surety_bond_underwriting_kit"])[0]
                    price = 299.0 if sku == "lb_verified_partner_slot" else 49.0
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "status": "checkout_session_ready",
                            "checkout_mode": "stripe_live_session",
                            "checkout_url": "https://checkout.stripe.com/c/pay/cs_live_lb",
                            "property_id": "lienbond",
                            "offer_sku": sku,
                            "offer_price_usd": price,
                            "stripe_display_name": "LienBond",
                            "stripe_merchant_email": "arif.coskun@profithelm.com",
                        },
                    )
                    return
                self._send_json(200, {"ok": True, "auth_required": True})
                return
            self._send_json(404, {"ok": False})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if body.get("intent") == "partner_registration":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "partner_registered",
                        "offer_sku": "lb_verified_partner_slot",
                        "offer_price_usd": 299.0,
                        "stripe_merchant_email": "arif.coskun@profithelm.com",
                    },
                )
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "synthetic_test": True,
                    "persisted": False,
                    "property_id": "lienbond",
                    "stripe_merchant_email": "arif.coskun@profithelm.com",
                },
            )

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _IsolatedLienBondHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        verifier = LiveEdgeVerifier(timeout=5.0, retries=1)
        res = verifier.verify_edge_functions(base_url, property_id="lienbond", dist_dir=tmp_path / "lienbond" / "dist")
        assert res["status"] == "PASS", res
        assert res["issues"] == []
        assert [c["slug"] for c in captured_redirects] == ["suretybonds_direct", "simply_business", "thimble_contractor"]
        for c in captured_redirects:
            assert c["synthetic_query"] == ["1"]
            assert c["synthetic_header"] == "1"
    finally:
        server.shutdown()
        server.server_close()



