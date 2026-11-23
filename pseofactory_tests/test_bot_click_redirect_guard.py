"""
End-to-end verification of the /r/<partner> bot/method/prefetch edge redirect guard,
multi-group robots.txt Disallow: /r/ enforcement across all tenants (RFC 9309 + RobotFileParser),
and explicit live-network opt-in for MonetizationHub.verify_outbound_link_health.
Zero em-dashes. Zero en-dashes.
"""

import json
import subprocess
import urllib.request
import urllib.robotparser
from pathlib import Path

from pseofactory import compiler, edge, estate_common, gainhelm_estate
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.verifier import MasterSEOVerifier


def test_edge_redirect_bot_method_prefetch_guard_all_tenants(tmp_path: Path) -> None:
    """
    Executes the real compiled functions/r/[partner].js onRequest handler via Node.js
    for every tenant template (profithelm, prexvo, gainhelm, lienbond) and proves:
    - Non-GET methods (HEAD, POST, OPTIONS) return 405 with no Location and zero KV writes.
    - Automated bot/crawler/HTTP-client/headless/empty UAs (including Claude-Web, Claude-User,
      node, Deno, Bun) return 403 with no Location and zero KV writes.
    - Speculative prefetch/prerender/preview headers (Sec-Purpose, Purpose, X-Moz) return 204
      with no Location and zero KV writes.
    - Real human browser UAs (Desktop Chrome, Safari, iOS Safari, Firefox, Edge, Samsung Internet,
      Brave, Opera, DuckDuckGo, Yandex Browser, Instagram/Facebook/LinkedIn/GSA webviews, CUBOT)
      return 302 with expected Location and record telemetry.
    - GET synthetic probes (?synthetic_test=1 or X-Pseofactory-Test: 1) even with Python-urllib UA
      return 302 with expected Location and skip KV telemetry; HEAD synthetic probes still return 405.
    """
    tenants = [
        ("profithelm", "profithelm.com", "rippling", "try.rippling.com", "PROFITHELM_TELEMETRY_KV"),
        ("prexvo", "prexvo.com", "splash_financial", "www.splashfinancial.com", "PREXVO_TELEMETRY_KV"),
        ("gainhelm", "gainhelm.com", "vanta_security", "www.vanta.com", "GAINHELM_TELEMETRY_KV"),
        ("lienbond", "lienbond.com", "suretybonds_direct", "www.suretybondsdirect.com", "LIENBOND_TELEMETRY_KV"),
    ]

    for prop_id, _, _, _, _ in tenants:
        (tmp_path / f"{prop_id}_r.mjs").write_text(
            edge.generate_edge_redirect_function(prop_id),
            encoding="utf-8",
        )

    runner = tmp_path / "run_guard_checks.mjs"
    runner.write_text(
        """
import * as profithelm from "./profithelm_r.mjs";
import * as prexvo from "./prexvo_r.mjs";
import * as gainhelm from "./gainhelm_r.mjs";
import * as lienbond from "./lienbond_r.mjs";

const MODS = { profithelm, prexvo, gainhelm, lienbond };
const TENANTS = [
  { prop: "profithelm", domain: "profithelm.com", partner: "rippling", expectHost: "try.rippling.com", kvKey: "PROFITHELM_TELEMETRY_KV", envExtra: {} },
  { prop: "prexvo", domain: "prexvo.com", partner: "splash_financial", expectHost: "www.splashfinancial.com", kvKey: "PREXVO_TELEMETRY_KV", envExtra: { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" } },
  { prop: "gainhelm", domain: "gainhelm.com", partner: "vanta_security", expectHost: "www.vanta.com", kvKey: "GAINHELM_TELEMETRY_KV", envExtra: { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" } },
  { prop: "lienbond", domain: "lienbond.com", partner: "suretybonds_direct", expectHost: "www.suretybondsdirect.com", kvKey: "LIENBOND_TELEMETRY_KV", envExtra: { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" } },
];

const CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
const HUMAN_UAS = [
  CHROME_UA,
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
  "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Brave/130",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 OPR/114.0.0.0",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/605.1.15 DuckDuckGo/7",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21G80 Instagram 345.0.0.29.93",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21G80 [FBAN/FBIOS;FBAV/475.0.0.50.108]",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21G80 [LinkedInApp]/9.29.6870",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) GSA/330.0.665734759 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/AP2A.240805.005; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.106 Mobile Safari/537.36",
  "Mozilla/5.0 (Linux; Android 13; CUBOT NOTE 50) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
];
const BOT_UAS = [
  "",
  "   ",
  "Googlebot/2.1 (+http://www.google.com/bot.html)",
  "GPTBot/1.0 (+https://openai.com/gptbot)",
  "ClaudeBot/1.0; +claudebot@anthropic.com",
  "Claude-Web/1.0",
  "Claude-User/1.0",
  "PerplexityBot/1.0",
  "ChatGPT-User/1.0",
  "curl/8.5.0",
  "python-requests/2.31.0",
  "Python-urllib/3.12",
  "Go-http-client/2.0",
  "node",
  "Deno/2.0.4",
  "Bun/1.1.34",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0.0.0 Safari/537.36",
  "facebookexternalhit/1.1",
  "axios/1.7.2",
];

async function invoke(t, { method = "GET", query = "", headers = {} }) {
  let kvWrites = 0;
  const kv = { put: async () => { kvWrites += 1; } };
  const env = { ...t.envExtra, [t.kvKey]: kv };
  const req = new Request(`https://${t.domain}/r/${t.partner}${query}`, { method, headers });
  const res = await MODS[t.prop].onRequest({
    request: req,
    env,
    params: { partner: t.partner },
  });
  return {
    status: res.status,
    location: res.headers.get("Location"),
    blocked: res.headers.get("X-Edge-Redirect-Blocked"),
    robots: res.headers.get("X-Robots-Tag"),
    cache: res.headers.get("Cache-Control"),
    allow: res.headers.get("Allow"),
    telemetry: res.headers.get("X-Edge-Telemetry"),
    synth: res.headers.get("X-Edge-Synthetic-Test"),
    kvWrites,
  };
}

const failures = [];
for (const t of TENANTS) {
  // 1. Non-GET methods (HEAD, POST, OPTIONS, and HEAD with synthetic_test=1) -> 405
  for (const m of ["HEAD", "POST", "OPTIONS"]) {
    const r = await invoke(t, { method: m, headers: { "user-agent": CHROME_UA } });
    if (r.status !== 405 || r.location !== null || r.kvWrites !== 0 || r.blocked !== "method" || r.allow !== "GET" || r.robots !== "noindex, nofollow" || r.cache !== "no-store") {
      failures.push({ tenant: t.prop, case: `method_${m}`, r });
    }
  }
  const headSynth = await invoke(t, { method: "HEAD", query: "?synthetic_test=1", headers: { "x-pseofactory-test": "1", "user-agent": CHROME_UA } });
  if (headSynth.status !== 405 || headSynth.location !== null || headSynth.kvWrites !== 0) {
    failures.push({ tenant: t.prop, case: "head_synth_blocked", r: headSynth });
  }

  // 2. Speculative prefetch, prerender, and preview headers -> 204
  for (const [hdrName, hdrVal] of [
    ["Sec-Purpose", "prefetch"],
    ["Sec-Purpose", "prefetch;prerender"],
    ["Sec-Purpose", "prerender"],
    ["Purpose", "prefetch"],
    ["Purpose", "preview"],
    ["X-Moz", "prefetch"],
  ]) {
    const r = await invoke(t, { headers: { "user-agent": CHROME_UA, [hdrName]: hdrVal } });
    if (r.status !== 204 || r.location !== null || r.kvWrites !== 0 || r.blocked !== "prefetch" || r.robots !== "noindex, nofollow" || r.cache !== "no-store") {
      failures.push({ tenant: t.prop, case: `prefetch_${hdrName}_${hdrVal}`, r });
    }
  }

  // 3. Missing UA + bot/crawler/HTTP-client UAs -> 403
  const missingUa = await invoke(t, { headers: {} });
  if (missingUa.status !== 403 || missingUa.location !== null || missingUa.kvWrites !== 0 || missingUa.blocked !== "bot" || missingUa.robots !== "noindex, nofollow" || missingUa.cache !== "no-store") {
    failures.push({ tenant: t.prop, case: "missing_ua", r: missingUa });
  }
  for (const botUa of BOT_UAS) {
    const r = await invoke(t, { headers: { "user-agent": botUa } });
    if (r.status !== 403 || r.location !== null || r.kvWrites !== 0 || r.blocked !== "bot" || r.robots !== "noindex, nofollow" || r.cache !== "no-store") {
      failures.push({ tenant: t.prop, case: `bot_${botUa}`, r });
    }
  }

  // 4. Normal human browser UAs -> 302 + expected host + KV telemetry recorded
  for (const humanUa of HUMAN_UAS) {
    const r = await invoke(t, { headers: { "user-agent": humanUa } });
    const hostOk = r.location && new URL(r.location).hostname === t.expectHost;
    if (r.status !== 302 || !hostOk || r.kvWrites !== 1 || r.telemetry !== "recorded") {
      failures.push({ tenant: t.prop, case: `human_${humanUa.slice(0, 32)}`, r });
    }
  }

  // 5. Synthetic GET probes (query or header) even with Python-urllib UA -> 302 + telemetry skipped
  const synthQuery = await invoke(t, { query: "?synthetic_test=1", headers: { "user-agent": "Python-urllib/3.12" } });
  if (synthQuery.status !== 302 || !synthQuery.location || new URL(synthQuery.location).hostname !== t.expectHost || synthQuery.kvWrites !== 0 || synthQuery.telemetry !== "synthetic_suppressed" || synthQuery.synth !== "1") {
    failures.push({ tenant: t.prop, case: "synth_query", r: synthQuery });
  }
  const synthHdr = await invoke(t, { headers: { "user-agent": "pseofactory-live-edge-verifier/1.0", "x-pseofactory-test": "1" } });
  if (synthHdr.status !== 302 || !synthHdr.location || new URL(synthHdr.location).hostname !== t.expectHost || synthHdr.kvWrites !== 0 || synthHdr.telemetry !== "synthetic_suppressed" || synthHdr.synth !== "1") {
    failures.push({ tenant: t.prop, case: "synth_header", r: synthHdr });
  }
}

console.log(JSON.stringify({ ok: failures.length === 0, failures }));
if (failures.length > 0) process.exit(1);
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"Node guard harness failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    parsed = json.loads(proc.stdout.strip().splitlines()[-1])
    assert parsed["ok"] is True, parsed["failures"]


def test_robots_txt_disallows_r_across_all_generators_and_groups(tmp_path: Path) -> None:
    """
    Verifies Disallow: /r/ is emitted BEFORE Allow: / by default in:
    - estate_common.MANDATORY_ROBOTS_DISALLOW_PATHS and write_sitemaps_and_robots (50+-site default)
    - estate_common.ensure_robots_txt_mandatory_disallows (across EVERY User-agent group per RFC 9309
      AND urllib.robotparser.RobotFileParser first-match semantics)
    - compiler.compile_lienbond_estate
    - gainhelm_estate.compile_gainhelm_estate_impl
    - MasterSEOVerifier.check_robots_txt_gate catches missing Disallow: /r/ when functions/r exists
    """
    assert "/r/" in estate_common.MANDATORY_ROBOTS_DISALLOW_PATHS

    def _assert_robotparser_blocks_r(robots_text: str, bots: tuple[str, ...]) -> None:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(robots_text.splitlines())
        for bot in bots:
            assert rp.can_fetch(bot, "https://example.com/r/rippling") is False, (
                f"RobotFileParser allowed {bot} on /r/rippling"
            )
            assert rp.can_fetch(bot, "https://example.com/tools/sample-calc/") is True, (
                f"RobotFileParser unexpectedly blocked {bot} on /tools/sample-calc/"
            )

    # 1. Generic 50+-site write_sitemaps_and_robots default
    generic_dist = tmp_path / "generic_dist"
    generic_dist.mkdir(parents=True)
    estate_common.write_sitemaps_and_robots(
        dist=generic_dist,
        canonical_base="https://example.com",
        hub_specs=[("https://example.com/", "1.0", "daily")],
        leaf_tools=[{"slug": "sample-calc", "updated_date": "2026-11-23"}],
        ai_bots=["*", "Googlebot", "Bingbot", "GPTBot", "ClaudeBot", "PerplexityBot"],
        disallow_paths=["/signal/"],
        validate_governor=False,
    )
    gen_robots = (generic_dist / "robots.txt").read_text(encoding="utf-8")
    gen_sections = MasterSEOVerifier.parse_robots_txt_sections(gen_robots)
    for ua in ("*", "googlebot", "bingbot", "gptbot", "claudebot", "perplexitybot"):
        assert MasterSEOVerifier.is_bot_blocked(ua, "/r/rippling", gen_sections), f"{ua} not blocked on /r/"
        assert not MasterSEOVerifier.is_bot_blocked(ua, "/tools/sample-calc/", gen_sections)
    _assert_robotparser_blocks_r(gen_robots, ("*", "Googlebot", "Bingbot", "GPTBot", "ClaudeBot", "PerplexityBot"))

    # 2. Multi-User-agent retrofit helper (profithelm / prexvo / all porcelain tenants)
    multi_agent_robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "# Dedicated AI search engine crawler allowances\n"
        "User-agent: Googlebot\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "User-agent: Bingbot\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "Sitemap: https://profithelm.com/sitemap.xml\n"
    )
    patched = estate_common.ensure_robots_txt_mandatory_disallows(multi_agent_robots)
    assert estate_common.ensure_robots_txt_mandatory_disallows(patched) == patched
    patched_sections = MasterSEOVerifier.parse_robots_txt_sections(patched)
    for ua in ("*", "googlebot", "bingbot", "gptbot"):
        assert MasterSEOVerifier.is_bot_blocked(ua, "/r/rippling", patched_sections), f"{ua} not blocked on /r/"
        assert MasterSEOVerifier.is_bot_blocked(ua, "/api/lead-capture", patched_sections)
    _assert_robotparser_blocks_r(patched, ("*", "Googlebot", "Bingbot", "GPTBot"))

    # 3. LienBond estate generator
    lb_out = tmp_path / "lienbond_out"
    compiler.compile_lienbond_estate(lb_out, run_retrofit=False)
    lb_robots = (lb_out / "dist" / "robots.txt").read_text(encoding="utf-8")
    lb_sections = MasterSEOVerifier.parse_robots_txt_sections(lb_robots)
    for ua in ("*", "googlebot", "bingbot", "gptbot"):
        assert MasterSEOVerifier.is_bot_blocked(ua, "/r/suretybonds_direct", lb_sections)
    _assert_robotparser_blocks_r(lb_robots, ("*", "Googlebot", "Bingbot", "GPTBot"))

    # 4. GainHelm estate generator
    gh_out = tmp_path / "gainhelm_out"
    gainhelm_estate.compile_gainhelm_estate_impl(gh_out, run_retrofit=False)
    gh_robots = (gh_out / "dist" / "robots.txt").read_text(encoding="utf-8")
    gh_sections = MasterSEOVerifier.parse_robots_txt_sections(gh_robots)
    for ua in ("*", "googlebot", "bingbot", "gptbot"):
        assert MasterSEOVerifier.is_bot_blocked(ua, "/r/vanta_security", gh_sections)
    _assert_robotparser_blocks_r(gh_robots, ("*", "Googlebot", "Bingbot", "GPTBot"))

    # 5. Verifier check_robots_txt_gate flags missing Disallow: /r/ when functions/r exists
    v_repo = tmp_path / "v_repo"
    (v_repo / "dist").mkdir(parents=True)
    (v_repo / "functions" / "r").mkdir(parents=True)
    (v_repo / "dist" / "robots.txt").write_text(
        "User-agent: *\nDisallow: /api/\nDisallow: /cdn-cgi/\nAllow: /\nDisallow: /signal/\n\n"
        "User-agent: Googlebot\nDisallow: /api/\nDisallow: /cdn-cgi/\nAllow: /\nDisallow: /signal/\n\n"
        "Sitemap: https://example.com/sitemap.xml\n"
        "Sitemap: https://example.com/sitemap-hubs.xml\n"
        "Sitemap: https://example.com/sitemap-leaves.xml\n",
        encoding="utf-8",
    )
    verifier = MasterSEOVerifier(dist_dir=v_repo / "dist", strict_robots=False)
    fail_res = verifier.check_robots_txt_gate()
    assert fail_res["status"] == "FAIL"
    assert any("/r/" in issue for issue in fail_res["issues"])

    (v_repo / "dist" / "robots.txt").write_text(
        estate_common.ensure_robots_txt_mandatory_disallows(
            (v_repo / "dist" / "robots.txt").read_text(encoding="utf-8")
        ),
        encoding="utf-8",
    )
    pass_res = verifier.check_robots_txt_gate()
    assert pass_res["status"] == "PASS", pass_res["issues"]


def test_verify_outbound_link_health_requires_explicit_live_opt_in(monkeypatch) -> None:
    """
    Proves MonetizationHub.verify_outbound_link_health never makes live outbound HTTP
    requests to affiliate tracking URLs when PYTEST_CURRENT_TEST and PSEUFACTORY_LIVE_NETWORK
    are both unset, and only opens network connections on explicit opt-in (either
    PSEUFACTORY_LIVE_NETWORK=1 or live_network=True).
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PSEUFACTORY_LIVE_NETWORK", raising=False)

    opener_calls = []

    def _boom_build_opener(*args, **kwargs):
        opener_calls.append((args, kwargs))
        raise AssertionError("verify_outbound_link_health must not perform live HTTP requests without explicit opt-in")

    monkeypatch.setattr(urllib.request, "build_opener", _boom_build_opener)

    hub = MonetizationHub()
    report = hub.verify_outbound_link_health(property_id="profithelm")
    assert opener_calls == []
    assert report["healthy"] is True
    assert report["checked_count"] > 0

    class _FakeResp:
        status = 302
        headers = {"Location": "https://www.rippling.com/"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _FakeOpener:
        def open(self, req, timeout=6.0):
            opener_calls.append(req.full_url)
            return _FakeResp()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **kw: _FakeOpener())

    # Explicit opt-in via live_network=True with PSEUFACTORY_LIVE_NETWORK unset
    kwarg_report = hub.verify_outbound_link_health(property_id="profithelm", live_network=True)
    assert kwarg_report["healthy"] is True
    assert len(opener_calls) == kwarg_report["checked_count"] > 0

    # Explicit opt-in via PSEUFACTORY_LIVE_NETWORK=1
    opener_calls.clear()
    monkeypatch.setenv("PSEUFACTORY_LIVE_NETWORK", "1")
    live_report = hub.verify_outbound_link_health(property_id="profithelm")
    assert live_report["healthy"] is True
    assert len(opener_calls) == live_report["checked_count"] > 0
