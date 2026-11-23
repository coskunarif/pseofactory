"""
Regression tests verifying that robots.txt generators, porcelain sync, and audit
gates disallow /api/ and /cdn-cgi/ for EVERY User-agent block (not just User-agent: *)
so RFC 9309 named-crawler blocks such as Googlebot never override wildcard disallows.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import urllib.robotparser
from pathlib import Path
from typing import Dict, Iterable, List

import pytest

from pseofactory import compiler
from pseofactory.contracts import assert_robots_txt_crawler_policy
from pseofactory.estate_common import write_sitemaps_and_robots
from pseofactory.porcelain_shell import _sync_sitemaps_headers_and_redirects
from pseofactory.verifier import MasterSEOVerifier


def _extract_explicit_user_agents(robots_txt: str) -> List[str]:
    """Returns every distinct User-agent value declared in robots.txt in order."""
    agents: List[str] = []
    seen = set()
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = [part.strip() for part in line.split(":", 1)]
        if key.lower() == "user-agent" and val and val.lower() not in seen:
            seen.add(val.lower())
            agents.append(val)
    return agents


def _assert_robots_blocks_api_and_cf_for_all_bots(
    robots_txt: str,
    domain: str,
    extra_probe_agents: Iterable[str] = ("*", "Googlebot", "Googlebot-Mobile", "Bingbot"),
) -> None:
    """
    Validates robots.txt using BOTH explicit block parsing and urllib.robotparser.RobotFileParser.
    Every User-agent block must explicitly disallow /api/ and /cdn-cgi/ while keeping
    / and /tools/example/ crawlable.
    """
    assert "\u2014" not in robots_txt, "Forbidden em-dash found in robots.txt"
    assert "\u2013" not in robots_txt, "Forbidden en-dash found in robots.txt"

    sections: Dict[str, Dict[str, List[str]]] = MasterSEOVerifier.parse_robots_txt_sections(robots_txt)
    assert "*" in sections, "robots.txt must include a User-agent: * block"

    # Explicit block parsing check: EVERY declared User-agent group must disallow /api/ and /cdn-cgi/
    for agent_key, rules in sections.items():
        disallows_lower = {d.strip().lower() for d in rules["disallow"]}
        assert "/api/" in disallows_lower, (
            f"[{domain}] User-agent '{agent_key}' block missing explicit 'Disallow: /api/'"
        )
        assert "/cdn-cgi/" in disallows_lower, (
            f"[{domain}] User-agent '{agent_key}' block missing explicit 'Disallow: /cdn-cgi/'"
        )
        assert MasterSEOVerifier.is_path_disallowed(
            "/api/lead-capture", rules["allow"], rules["disallow"]
        ), f"[{domain}] User-agent '{agent_key}' does not disallow /api/lead-capture"
        assert MasterSEOVerifier.is_path_disallowed(
            "/cdn-cgi/l/email-protection", rules["allow"], rules["disallow"]
        ), f"[{domain}] User-agent '{agent_key}' does not disallow /cdn-cgi/l/email-protection"

    # urllib.robotparser check across EVERY declared User-agent plus mandatory probe UAs
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())

    probe_agents: List[str] = list(_extract_explicit_user_agents(robots_txt))
    seen_lower = {a.lower() for a in probe_agents}
    for ua in extra_probe_agents:
        if ua.lower() not in seen_lower:
            seen_lower.add(ua.lower())
            probe_agents.append(ua)

    base = f"https://{domain}"
    for ua in probe_agents:
        assert rp.can_fetch(ua, f"{base}/api/lead-capture") is False, (
            f"[{domain}] RobotFileParser allowed '{ua}' to fetch /api/lead-capture"
        )
        assert rp.can_fetch(ua, f"{base}/api/lead-capture?fulfill=1&sku=foo") is False, (
            f"[{domain}] RobotFileParser allowed '{ua}' to fetch /api/lead-capture?fulfill=1&sku=foo"
        )
        assert rp.can_fetch(ua, f"{base}/api/telemetry") is False, (
            f"[{domain}] RobotFileParser allowed '{ua}' to fetch /api/telemetry"
        )
        assert rp.can_fetch(ua, f"{base}/cdn-cgi/l/email-protection") is False, (
            f"[{domain}] RobotFileParser allowed '{ua}' to fetch /cdn-cgi/l/email-protection"
        )
        assert rp.can_fetch(ua, f"{base}/") is True, (
            f"[{domain}] RobotFileParser blocked '{ua}' on /"
        )
        assert rp.can_fetch(ua, f"{base}/tools/example/") is True, (
            f"[{domain}] RobotFileParser blocked '{ua}' on /tools/example/"
        )


def test_write_sitemaps_and_robots_enforces_api_and_cdn_cgi_for_every_bot(tmp_path: Path) -> None:
    """
    Even if a tenant caller omits /api/ and /cdn-cgi/ from disallow_paths,
    write_sitemaps_and_robots must emit Disallow: /api/ and Disallow: /cdn-cgi/
    for EVERY User-agent block before Allow: /.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    bots = [
        "*",
        "Googlebot",
        "Bingbot",
        "PerplexityBot",
        "ClaudeBot",
        "GPTBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "Meta-ExternalAgent",
        "Applebot-Extended",
    ]
    write_sitemaps_and_robots(
        dist=dist,
        canonical_base="https://example-tenant.com",
        hub_specs=[("https://example-tenant.com/", "1.0", "daily")],
        leaf_tools=[{"slug": "example", "updated_date": "2026-11-23"}],
        ai_bots=bots,
        disallow_paths=["/signal/", "/syndication/", "/staging/"],
        allow_paths=["/", "/tools/"],
        validate_governor=False,
    )
    robots_txt = (dist / "robots.txt").read_text(encoding="utf-8")
    _assert_robots_blocks_api_and_cf_for_all_bots(robots_txt, "example-tenant.com")


@pytest.mark.parametrize(
    ("property_id", "domain", "buggy_robots"),
    [
        (
            "prexvo",
            "prexvo.com",
            (
                "User-agent: *\n"
                "Disallow: /api/\n"
                "Disallow: /cdn-cgi/\n"
                "Allow: /\n"
                "Allow: /tools/\n"
                "Disallow: /signal/\n\n"
                "User-agent: Googlebot\n"
                "Allow: /\n"
                "Allow: /tools/\n"
                "Disallow: /signal/\n\n"
                "User-agent: Bingbot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "User-agent: GPTBot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "User-agent: OAI-SearchBot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "User-agent: ClaudeBot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "User-agent: PerplexityBot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "Sitemap: https://prexvo.com/sitemap.xml\n"
            ),
        ),
        (
            "profithelm",
            "profithelm.com",
            (
                "User-agent: *\n"
                "Disallow: /api/\n"
                "Disallow: /cdn-cgi/\n"
                "Allow: /\n"
                "Allow: /about/\n"
                "Disallow: /signal/\n\n"
                "# Dedicated AI search engine crawler allowances\n"
                "User-agent: Googlebot\n"
                "Allow: /\n"
                "Allow: /about/\n"
                "Disallow: /signal/\n\n"
                "User-agent: Bingbot\n"
                "Allow: /\n"
                "Disallow: /signal/\n\n"
                "Sitemap: https://profithelm.com/sitemap.xml\n"
            ),
        ),
        (
            "lienbond",
            "lienbond.com",
            (
                "User-agent: *\n"
                "Allow: /\n"
                "Disallow: /api/\n"
                "Disallow: /cdn-cgi/\n"
                "Disallow: /signal/\n\n"
                "User-agent: Googlebot\n"
                "Allow: /\n"
                "Disallow: /api/\n"
                "Disallow: /cdn-cgi/\n"
                "Disallow: /signal/\n\n"
                "Sitemap: https://lienbond.com/sitemap.xml\n"
            ),
        ),
    ],
)
def test_porcelain_sync_patches_every_named_user_agent_block(
    tmp_path: Path,
    property_id: str,
    domain: str,
    buggy_robots: str,
) -> None:
    """
    Verifies _sync_sitemaps_headers_and_redirects repairs robots.txt across every
    tenant pattern:
    - Wildcard already has /api/ and /cdn-cgi/ while Googlebot/Bingbot/AI bots omit them
    - Allow: / precedes Disallow: /api/ (which breaks first-match RobotFileParser)
    - Re-running sync is idempotent
    """
    dist = tmp_path / "dist"
    (dist / "tools" / "example").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Home</title></head><body><h1>Home</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "tools" / "example" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Tool</title></head><body><h1>Tool</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "robots.txt").write_text(buggy_robots, encoding="utf-8")

    profile = {
        "property_id": property_id,
        "domain": domain,
        "canonical_base": f"https://{domain}",
        "brand_name": property_id.title(),
        "badge_letter": property_id[0].upper(),
        "brand_primary": "#1d4ed8",
    }
    mutated = _sync_sitemaps_headers_and_redirects(dist, profile)
    assert "robots.txt" in mutated

    patched = (dist / "robots.txt").read_text(encoding="utf-8")
    _assert_robots_blocks_api_and_cf_for_all_bots(patched, domain)
    if "# Dedicated AI search engine crawler allowances" in buggy_robots:
        assert "# Dedicated AI search engine crawler allowances" in patched

    # Second run must be idempotent for robots.txt
    mutated_second = _sync_sitemaps_headers_and_redirects(dist, profile)
    assert "robots.txt" not in mutated_second
    assert (dist / "robots.txt").read_text(encoding="utf-8") == patched


def test_compiled_gainhelm_and_lienbond_estates_disallow_api_and_cdn_cgi_all_bots(
    tmp_path: Path,
) -> None:
    """
    Compiles GainHelm and LienBond into isolated temp directories and verifies
    their generated robots.txt files block /api/ and /cdn-cgi/ for every crawler.
    """
    gh_root = tmp_path / "gainhelm_out"
    compiler.compile_gainhelm_estate(gh_root, run_retrofit=False)
    gh_robots = (gh_root / "dist" / "robots.txt").read_text(encoding="utf-8")
    _assert_robots_blocks_api_and_cf_for_all_bots(gh_robots, "gainhelm.com")

    lb_root = tmp_path / "lienbond_out"
    compiler.compile_lienbond_estate(lb_root, run_retrofit=False)
    lb_robots = (lb_root / "dist" / "robots.txt").read_text(encoding="utf-8")
    _assert_robots_blocks_api_and_cf_for_all_bots(lb_robots, "lienbond.com")


def test_ensure_robots_txt_handles_edge_cases_and_rfc9309_shared_groups(tmp_path: Path) -> None:
    """Tests RFC 9309 multi-agent shared groups, compact blocks, and missing wildcard."""
    import pseofactory.estate_common as estate_common_mod

    shared_and_compact = (
        "User-agent: Googlebot\n"
        "User-agent: Bingbot\n"
        "Allow: /\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n"
        "Sitemap: https://multi.example.com/sitemap.xml\n"
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Home</title></head><body><h1>Home</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "robots.txt").write_text(shared_and_compact, encoding="utf-8")
    profile = {
        "property_id": "multi",
        "domain": "multi.example.com",
        "canonical_base": "https://multi.example.com",
        "brand_name": "Multi",
        "badge_letter": "M",
        "brand_primary": "#1d4ed8",
    }
    _sync_sitemaps_headers_and_redirects(dist, profile)
    out = (dist / "robots.txt").read_text(encoding="utf-8")
    _assert_robots_blocks_api_and_cf_for_all_bots(out, "multi.example.com")

    helper = getattr(estate_common_mod, "ensure_robots_txt_mandatory_disallows", None)
    assert helper is not None, "estate_common.ensure_robots_txt_mandatory_disallows helper missing"
    assert helper(out) == out


def test_verifier_and_contracts_flag_named_bot_override_missing_api_disallow(
    tmp_path: Path,
) -> None:
    """
    MasterSEOVerifier.check_robots_txt_gate, assert_robots_txt_crawler_policy, and
    assert_robots_txt_mandatory_disallows must reject any robots.txt where a named
    User-agent block (e.g. Googlebot) omits Disallow: /api/ or /cdn-cgi/ or places
    Allow: / ahead of Disallow: /api/.
    """
    import pseofactory.contracts as contracts_mod
    import pseofactory.estate_common as estate_common_mod

    buggy_override = (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Disallow: /cdn-cgi/\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "Sitemap: https://prexvo.com/sitemap.xml\n"
        "Sitemap: https://prexvo.com/sitemap-hubs.xml\n"
        "Sitemap: https://prexvo.com/sitemap-leaves.xml\n"
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "robots.txt").write_text(buggy_override, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist, strict_robots=False)
    gate_fail = verifier.check_robots_txt_gate(dist)
    assert gate_fail["status"] == "FAIL", (
        "check_robots_txt_gate must FAIL when Googlebot overrides User-agent: * without Disallow: /api/"
    )
    assert any("googlebot" in issue.lower() and "/api/" in issue for issue in gate_fail["issues"])
    assert any("googlebot" in issue.lower() and "/cdn-cgi/" in issue for issue in gate_fail["issues"])

    with pytest.raises(ValueError, match="googlebot"):
        assert_robots_txt_crawler_policy(buggy_override)

    assert_mandatory = getattr(contracts_mod, "assert_robots_txt_mandatory_disallows", None)
    assert assert_mandatory is not None, "contracts.assert_robots_txt_mandatory_disallows missing"
    with pytest.raises(ValueError, match="googlebot"):
        assert_mandatory(buggy_override)

    # Late Disallow after Allow: / must also fail RobotFileParser check
    allow_before_disallow = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /cdn-cgi/\n"
        "Disallow: /signal/\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /cdn-cgi/\n"
        "Disallow: /signal/\n\n"
        "Sitemap: https://lienbond.com/sitemap.xml\n"
        "Sitemap: https://lienbond.com/sitemap-hubs.xml\n"
        "Sitemap: https://lienbond.com/sitemap-leaves.xml\n"
    )
    with pytest.raises(ValueError, match="RobotFileParser"):
        assert_mandatory(allow_before_disallow)

    # Fixed version must pass all checks
    ensure_fn = getattr(estate_common_mod, "ensure_robots_txt_mandatory_disallows", None)
    assert ensure_fn is not None
    fixed = ensure_fn(buggy_override)
    (dist / "robots.txt").write_text(fixed, encoding="utf-8")
    gate_pass = verifier.check_robots_txt_gate(dist)
    assert gate_pass["status"] == "PASS", gate_pass["issues"]
    assert assert_robots_txt_crawler_policy(fixed) is True
    assert assert_mandatory(fixed) is True


def test_parse_and_ensure_preserve_in_group_comments_and_strip_utf8_bom() -> None:
    """
    Comment-only lines inside a User-agent group (both between grouped User-agent lines
    and between User-agent and Disallow/Allow lines) must never terminate the group in
    parse_robots_txt_sections, and a leading UTF-8 BOM must not corrupt line-1 parsing.
    """
    import pseofactory.estate_common as estate_common_mod

    commented_bom_robots = (
        "\ufeffUser-agent: *\n"
        "# comment between User-agent and Disallow\n"
        "Disallow: /api/\n"
        "Disallow: /cdn-cgi/\n"
        "Allow: /\n\n"
        "User-agent: Googlebot\n"
        "# comment between grouped User-agent headers\n"
        "User-agent: Bingbot\n"
        "# comment before rules\n"
        "Disallow: /api/\n"
        "Disallow: /cdn-cgi/\n"
        "Allow: /\n\n"
        "Sitemap: https://bom.example.com/sitemap.xml\n"
    )
    sections = MasterSEOVerifier.parse_robots_txt_sections(commented_bom_robots)
    assert "*" in sections, f"UTF-8 BOM broke wildcard User-agent parsing: {list(sections)}"
    for agent in ("*", "googlebot", "bingbot"):
        assert agent in sections, f"Missing parsed agent '{agent}' in {list(sections)}"
        assert "/api/" in [d.lower() for d in sections[agent]["disallow"]], (
            f"Comment inside group dropped Disallow: /api/ for '{agent}': {sections[agent]}"
        )
        assert "/cdn-cgi/" in [d.lower() for d in sections[agent]["disallow"]], (
            f"Comment inside group dropped Disallow: /cdn-cgi/ for '{agent}': {sections[agent]}"
        )
        assert "/" in sections[agent]["allow"], (
            f"Comment inside group dropped Allow: / for '{agent}': {sections[agent]}"
        )

    ensure_fn = getattr(estate_common_mod, "ensure_robots_txt_mandatory_disallows", None)
    assert ensure_fn is not None, "ensure_robots_txt_mandatory_disallows helper missing"
    bom_missing_disallows = (
        "\ufeffUser-agent: *\n"
        "# wildcard comment\n"
        "Allow: /\n\n"
        "User-agent: Googlebot\n"
        "# grouped header comment\n"
        "User-agent: Bingbot\n"
        "# rule comment\n"
        "Allow: /\n"
    )
    normalized = ensure_fn(bom_missing_disallows)
    assert not normalized.startswith("\ufeff"), "Output robots.txt must not retain leading UTF-8 BOM"
    assert normalized.startswith("User-agent: *\n"), f"Unexpected BOM output start: {normalized[:40]!r}"
    assert "# grouped header comment" in normalized
    assert "# rule comment" in normalized
    _assert_robots_blocks_api_and_cf_for_all_bots(normalized, "bom.example.com")
    assert ensure_fn(normalized) == normalized
