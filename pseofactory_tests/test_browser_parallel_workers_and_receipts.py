"""
Integration and negative invalidation tests for parallel isolated headless Chromium workers,
deterministic sharding, CLS source diagnostics, and closed SHA-256 verification receipts.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
from typing import Dict, List
import zlib

import pytest

import pseofactory.cli as pseo_cli
from pseofactory.browser_verifier import (
    BrowserVerifyReceiptStore,
    UnifiedBrowserAuditor,
    compute_auto_worker_count,
    discover_headless_chrome_binary,
    parse_and_apply_shard,
)
from pseofactory.porcelain_shell import compile_tenant_porcelain_estate


def _build_clean_porcelain_fixture(dist_dir: Path, slug_names: List[str]) -> None:
    """Creates a minimal valid multi-route porcelain dist tree for real headless Chromium tests."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='Deterministic fixture hub.'>"
        "<title>Fixture Hub | ProfitHelm</title></head>"
        "<body><main><h1>Fixture Hub</h1><p>Deterministic statutory financial models.</p></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='Deterministic tools index.'>"
        "<title>Tools Directory | ProfitHelm</title></head>"
        "<body><main><h1>Tools Directory</h1><p>Directory of deterministic models.</p></main></body></html>",
        encoding="utf-8",
    )
    for slug in slug_names:
        tool_dir = dist_dir / "tools" / slug
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            f"<meta name='description' content='Deterministic model for {slug}.'>"
            f"<title>{slug} Guide | ProfitHelm</title></head>"
            f"<body><main><h1>{slug} Guide</h1><p>Statutory calculation reference for {slug}.</p></main></body></html>",
            encoding="utf-8",
        )
    (dist_dir / "_redirects").write_text("/legacy-guide /tools/ 301\n", encoding="utf-8")
    compile_tenant_porcelain_estate(dist_dir, "profithelm")


def test_shard_partition_exact_union_zero_overlap_and_validation() -> None:
    routes = ["/", "/tools/", "/404.html"] + [f"/tools/calc-{i:02d}/" for i in range(17)]
    sh1 = parse_and_apply_shard(routes, "1/3")
    sh2 = parse_and_apply_shard(routes, "2/3")
    sh3 = parse_and_apply_shard(routes, "3/3")

    assert set(sh1).isdisjoint(sh2)
    assert set(sh1).isdisjoint(sh3)
    assert set(sh2).isdisjoint(sh3)
    assert sorted(sh1 + sh2 + sh3) == sorted(routes)
    assert abs(len(sh1) - len(sh3)) <= 1

    for bad_spec in ("0/3", "4/3", "1/0", "abc", "1-3", ""):
        if bad_spec == "":
            assert parse_and_apply_shard(routes, bad_spec) == list(routes)
        else:
            with pytest.raises(ValueError):
                parse_and_apply_shard(routes, bad_spec)


def test_pytest_isolation_blocks_default_receipt_path() -> None:
    assert "PYTEST_CURRENT_TEST" in os.environ
    assert BrowserVerifyReceiptStore.default_receipt_path("profithelm") is None
    assert compute_auto_worker_count(1) == 1
    assert compute_auto_worker_count(20, requested_workers=2) == 2


def test_cls_sources_summary_formatting() -> None:
    finding = {
        "route": "/tools/cls-demo/",
        "cls_value": 0.042,
        "cls_sources": [
            {"node": "div.hero-banner", "prev": [0, 0, 1440, 200], "curr": [0, 80, 1440, 200]},
        ],
    }
    reasons = pseo_cli._summarize_browser_finding_failures(finding)
    assert any("CLS 0.042" in r and "div.hero-banner" in r for r in reasons), reasons


@pytest.mark.xdist_group("ephemeral_chrome_workers")
def test_parallel_workers_and_four_mandatory_negative_invalidations(tmp_path: Path) -> None:
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "dist"
    receipt_file = tmp_path / "receipts" / "profithelm.json"
    _build_clean_porcelain_fixture(dist_dir, ["alpha-model", "beta-model", "gamma-model"])

    # Run 1 (cold): 2 parallel isolated headless Chromium workers verify all routes live
    aud_cold = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=2,
        receipt_path=receipt_file,
    )
    rep1 = aud_cold.run_audit()
    assert rep1["passed"] is True, f"Cold parallel audit failed: {rep1['findings']}"
    assert rep1["failed_count"] == 0
    total_routes = rep1["routes_audited"]
    assert total_routes >= 5
    assert rep1["live_audited_routes"] == total_routes
    assert rep1["cached_receipt_routes"] == 0
    assert rep1["workers_used"] == 2
    assert receipt_file.is_file()
    # Lexicographical route determinism
    routes_order = [f["route"] for f in rep1["findings"]]
    assert routes_order == sorted(routes_order)

    # Run 2 (warm): 100% receipt hits, 0 live Chrome routes, 0 workers spawned
    rep2 = aud_cold.run_audit()
    assert rep2["passed"] is True
    assert rep2["routes_audited"] == total_routes
    assert rep2["live_audited_routes"] == 0
    assert rep2["cached_receipt_routes"] == total_routes
    assert rep2["workers_used"] == 0

    # --no-verify-cache bypasses reads and runs all routes live
    rep_nocache = aud_cold.run_audit(no_verify_cache=True)
    assert rep_nocache["passed"] is True, f"no-verify-cache audit failed: {[f for f in rep_nocache['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_nocache["live_audited_routes"] == total_routes
    assert rep_nocache["cached_receipt_routes"] == 0

    # Negative Invalidation (a): flip 1 byte in a single page HTML -> ONLY that 1 route misses cache
    alpha_html_path = dist_dir / "tools" / "alpha-model" / "index.html"
    orig_alpha_html = alpha_html_path.read_text(encoding="utf-8")
    alpha_html_path.write_text(orig_alpha_html + "\n<!-- 1-byte-delta -->", encoding="utf-8")
    rep_html_flip = aud_cold.run_audit()
    assert rep_html_flip["passed"] is True, f"html-flip audit failed: {[f for f in rep_html_flip['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_html_flip["live_audited_routes"] == 1
    assert rep_html_flip["cached_receipt_routes"] == total_routes - 1
    alpha_finding = next(f for f in rep_html_flip["findings"] if f["route"] == "/tools/alpha-model/")
    assert not alpha_finding.get("verified_by_receipt")

    # Negative Invalidation (b): flip 1 byte in dist/css/style.css -> 100% cache miss
    css_path = dist_dir / "css" / "style.css"
    assert css_path.is_file(), "Expected compiled dist/css/style.css"
    css_orig = css_path.read_text(encoding="utf-8")
    css_path.write_text(css_orig + "\n/* 1-byte-css-delta */\n", encoding="utf-8")
    rep_css_flip = aud_cold.run_audit()
    assert rep_css_flip["passed"] is True, f"css-flip audit failed: {[f for f in rep_css_flip['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_css_flip["live_audited_routes"] == total_routes
    assert rep_css_flip["cached_receipt_routes"] == 0

    # Negative Invalidation (c): flip 1 byte in dist/_redirects -> 100% cache miss
    redir_path = dist_dir / "_redirects"
    redir_orig = redir_path.read_text(encoding="utf-8")
    redir_path.write_text(redir_orig + "# 1-byte-redir-delta\n", encoding="utf-8")
    rep_redir_flip = aud_cold.run_audit()
    assert rep_redir_flip["passed"] is True, f"redir-flip audit failed: {[f for f in rep_redir_flip['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_redir_flip["live_audited_routes"] == total_routes
    assert rep_redir_flip["cached_receipt_routes"] == 0

    # Negative Invalidation (d1): simulated Chrome version change -> 100% cache miss
    aud_new_chrome = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=2,
        receipt_path=receipt_file,
    )
    aud_new_chrome._chrome_version_override = "Google Chrome for Testing 999.0.0.1"
    rep_chrome_flip = aud_new_chrome.run_audit()
    assert rep_chrome_flip["passed"] is True, f"chrome-flip audit failed: {[f for f in rep_chrome_flip['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_chrome_flip["live_audited_routes"] == total_routes
    assert rep_chrome_flip["cached_receipt_routes"] == 0

    # Negative Invalidation (d2): simulated verifier source digest change -> 100% cache miss
    aud_new_verifier = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=2,
        receipt_path=receipt_file,
    )
    aud_new_verifier._chrome_version_override = "Google Chrome for Testing 999.0.0.1"
    aud_new_verifier._verifier_digest_override = "deadbeef" * 8
    rep_verifier_flip = aud_new_verifier.run_audit()
    assert rep_verifier_flip["passed"] is True, f"verifier-flip audit failed: {[f for f in rep_verifier_flip['findings'] if UnifiedBrowserAuditor._is_finding_failed(f)]}"
    assert rep_verifier_flip["live_audited_routes"] == total_routes
    assert rep_verifier_flip["cached_receipt_routes"] == 0


def test_isolated_chrome_detects_all_defects_and_never_caches_failures(tmp_path: Path) -> None:
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "failing_dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = tmp_path / "receipts" / "failing.json"

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Broken Fixture</title>"
        "<style>"
        "body { background: #07090e; color: #334155; margin: 0; }"
        ".wide-box { width: 1800px; height: 40px; }"
        "a.tiny { display: inline-block; width: 12px; height: 12px; outline: none; }"
        "</style>"
        "<script>"
        "window.addEventListener('load', () => {"
        "  console.error('synthetic_boom_error');"
        "  setTimeout(() => {"
        "    const banner = document.createElement('div');"
        "    banner.id = 'late-cls-banner';"
        "    banner.style.height = '180px';"
        "    document.body.prepend(banner);"
        "  }, 40);"
        "});"
        "</script>"
        "</head><body>"
        "<div class='wide-box'>Overflow content</div>"
        "<img src='/missing-asset.png' alt='missing'>"
        "<a class='tiny' href='/does-not-exist/'>x</a>"
        "</body></html>",
        encoding="utf-8",
    )

    aud = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=1,
        receipt_path=receipt_file,
    )
    rep1 = aud.run_audit()
    assert rep1["passed"] is False
    assert rep1["status"] == "FAIL"
    assert rep1["failed_count"] == 1
    assert rep1["failed_routes"] == ["/"]
    f = rep1["findings"][0]
    assert f["overflow_375"] is True
    assert f["overflow_1280"] is True
    assert f["overflow_1440"] is True
    assert f["cls_value"] > 0.0
    assert f.get("cls_sources"), f"Expected cls_sources diagnostics on CLS > 0, got: {f}"
    assert len(f["broken_assets"]) >= 1
    assert len(f["targets_under_44"]) >= 1
    assert "synthetic_boom_error" in f["interactive_surface"]["console_errors"]
    assert "/does-not-exist/" in f["interactive_surface"]["links_audit"]["invalid_links"]

    # Strict pass-only rule: failure must NEVER be cached, so Run 2 still runs live and fails
    if receipt_file.is_file():
        data = json.loads(receipt_file.read_text(encoding="utf-8"))
        assert "/" not in (data.get("routes") or {})
    rep2 = aud.run_audit()
    assert rep2["passed"] is False
    assert rep2["live_audited_routes"] == 1
    assert rep2["cached_receipt_routes"] == 0


def _make_solid_png(width: int, height: int, textured: bool = False) -> bytes:
    """Generates a valid minimal RGB PNG of exact dimensions using stdlib zlib + struct."""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    if textured:
        # Deterministic textured image (~150 KiB compressed for 1200x600) so decoding realistically
        # occurs after first paint on loopback, matching production hero images.
        rows = bytearray()
        for y in range(height):
            rows.append(0)
            for x in range(width):
                rows.append((x * 3 + y * 7) & 0xFF)
                rows.append((x * 5 ^ y * 11) & 0xFF)
                rows.append((x + y * 13) & 0xFF)
        compressed = zlib.compress(bytes(rows), level=1)
    else:
        raw_row = b"\x00" + (b"\x20\x60\xa0" * width)
        compressed = zlib.compress(raw_row * height, level=1)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


def test_cold_load_unsized_image_cls_not_silenced_by_reload_or_shared_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Blocker #1 reproducer: an unsized 1200x600 <img> above <p> causes genuine cold-load CLS.
    Adding deterministic 80ms network latency to hero.png proves BOTH / and /page2/ (sharing
    the same image in the same worker) observe cold-load CLS > 0 and are never silenced by
    HTTP caching or reload confirmation.
    """
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    import time
    from pseofactory.server import QuietHTTPRequestHandler

    orig_do_get = QuietHTTPRequestHandler.do_GET

    def _delayed_hero_get(self):
        if "hero.png" in (getattr(self, "path", "") or ""):
            time.sleep(0.08)
        return orig_do_get(self)

    monkeypatch.setattr(QuietHTTPRequestHandler, "do_GET", _delayed_hero_get)

    dist_dir = tmp_path / "cls_img_dist"
    (dist_dir / "static" / "img").mkdir(parents=True, exist_ok=True)
    (dist_dir / "page2").mkdir(parents=True, exist_ok=True)
    (dist_dir / "static" / "img" / "hero.png").write_bytes(_make_solid_png(1200, 600))

    def _page_html(title: str) -> str:
        return (
            "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            f"<title>{title}</title></head>"
            "<body><main>"
            f"<h1>{title}</h1>"
            "<img src='/static/img/hero.png' alt='Unsized hero graphic'>"
            "<p>Paragraph pushed down when the unsized hero image decodes after first paint.</p>"
            "</main></body></html>"
        )

    (dist_dir / "index.html").write_text(_page_html("Unsized Image CLS Home"), encoding="utf-8")
    (dist_dir / "page2" / "index.html").write_text(_page_html("Unsized Image CLS Page 2"), encoding="utf-8")

    receipt_file = tmp_path / "receipts" / "cls_img.json"
    aud = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=1,
        receipt_path=receipt_file,
    )
    rep = aud.run_audit()
    by_route = {f["route"]: f for f in rep["findings"]}
    assert rep["passed"] is False, f"Expected unsized image CLS failure, got: {rep}"
    assert by_route["/"]["cls_value"] > 0.0, f"Route / silenced unsized image CLS: {by_route['/']}"
    assert by_route["/page2/"]["cls_value"] > 0.0, f"Route /page2/ silenced unsized image CLS: {by_route['/page2/']}"


@pytest.mark.xdist_group("ephemeral_chrome_workers")
def test_receipt_invalidation_same_size_corrupt_png_and_deleted_llms_txt(tmp_path: Path) -> None:
    """
    Blocker #2 reproducers:
    (a) Corrupting a .png with identical byte length must invalidate receipts and fail broken_image.
    (b) Deleting dist/llms.txt must invalidate receipts and fail invalid_links.
    """
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "dist"
    (dist_dir / "static" / "img").mkdir(parents=True, exist_ok=True)
    valid_png = _make_solid_png(64, 64)
    logo_path = dist_dir / "static" / "img" / "logo.png"
    logo_path.write_bytes(valid_png)
    llms_path = dist_dir / "custom-llms.txt"
    llms_path.write_text("# ProfitHelm\nDeterministic statutory models.\n", encoding="utf-8")

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='Asset integrity fixture.'>"
        "<title>Asset Fixture | ProfitHelm</title></head>"
        "<body><main><h1>Asset Fixture</h1>"
        "<img src='/static/img/logo.png' width='64' height='64' alt='Logo'>"
        "<p>See <a href='/custom-llms.txt'>custom-llms.txt</a> for machine index.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='Tools fixture.'>"
        "<title>Tools | ProfitHelm</title></head>"
        "<body><main><h1>Tools</h1><p>Directory of deterministic models.</p></main></body></html>",
        encoding="utf-8",
    )
    compile_tenant_porcelain_estate(dist_dir, "profithelm")

    receipt_file = tmp_path / "receipts" / "asset_inval.json"
    aud = UnifiedBrowserAuditor(
        dist_dir=dist_dir,
        property_id="profithelm",
        fail_closed=True,
        workers=2,
        receipt_path=receipt_file,
    )
    rep1 = aud.run_audit()
    assert rep1["passed"] is True, f"Initial clean run failed: {rep1['findings']}"
    total_routes = rep1["routes_audited"]

    # Warm hit sanity check
    rep_warm = aud.run_audit()
    assert rep_warm["live_audited_routes"] == 0
    assert rep_warm["cached_receipt_routes"] == total_routes

    # (a) Corrupt logo.png with IDENTICAL byte count -> 100% cache miss + broken_image detected!
    corrupt_bytes = b"X" * len(valid_png)
    assert len(corrupt_bytes) == len(valid_png)
    logo_path.write_bytes(corrupt_bytes)
    rep_corrupt_png = aud.run_audit()
    assert rep_corrupt_png["live_audited_routes"] == total_routes
    assert rep_corrupt_png["cached_receipt_routes"] == 0
    assert rep_corrupt_png["passed"] is False
    home_f = next(f for f in rep_corrupt_png["findings"] if f["route"] == "/")
    assert any(a.get("type") == "broken_image" for a in home_f.get("broken_assets", []))

    # Restore valid logo.png and re-warm receipts
    logo_path.write_bytes(valid_png)
    rep_restored = aud.run_audit()
    assert rep_restored["passed"] is True
    assert aud.run_audit()["cached_receipt_routes"] == total_routes

    # (b) Delete dist/custom-llms.txt -> 100% cache miss + invalid_links detected!
    llms_path.unlink()
    rep_del_llms = aud.run_audit()
    assert rep_del_llms["live_audited_routes"] == total_routes
    assert rep_del_llms["cached_receipt_routes"] == 0
    assert rep_del_llms["passed"] is False
    home_f2 = next(f for f in rep_del_llms["findings"] if f["route"] == "/")
    assert "/custom-llms.txt" in (home_f2.get("interactive_surface") or {}).get("links_audit", {}).get("invalid_links", [])


def test_hidden_output_cannot_mask_frozen_visible_calculator(tmp_path: Path) -> None:
    """
    Blocker #3 reproducer: a display:none .output-value that updates must NOT mask a frozen visible output.
    """
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "hidden_out_dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Hidden Output Trap</title></head>"
        "<body><main><h1>Hidden Output Trap</h1>"
        "<form class='calculator-form'>"
        "<label for='field-amount'>Amount</label>"
        "<input id='field-amount' type='number' value='100'>"
        "<div class='output-value' id='val-visible'>$100</div>"
        "<div class='output-value' id='val-hidden' style='display:none'>$100</div>"
        "</form>"
        "<script>"
        "document.getElementById('field-amount').addEventListener('input', (e) => {"
        "  document.getElementById('val-hidden').textContent = '$' + String(e.target.value);"
        "});"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )
    compile_tenant_porcelain_estate(dist_dir, "profithelm")

    aud = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="profithelm", fail_closed=True, workers=1)
    rep = aud.run_audit()
    home_f = next(f for f in rep["findings"] if f["route"] == "/")
    calc = home_f["interactive_surface"]["calculator_and_presets"]
    assert calc["passed"] is False, f"Hidden output masked frozen visible UI: {calc}"
    assert "field-amount" in calc["input_failures"]


def test_preset_restore_syncs_select_and_missing_href_partner_link_fails(tmp_path: Path) -> None:
    """
    Blocker #4 & Minor #7 reproducers:
    (a) Preset test loop must dispatch input+change on EVERY control including <select> during
        perturbation and restore so JS state returns to exact baseline ($100000).
    (b) An <a data-partner='acme'> missing href must fail unrouted_affiliate_links.
    """
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "preset_select_dist"
    (dist_dir / "tools" / "demo-calc").mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Hub</title></head>"
        "<body><main><h1>Hub</h1>"
        "<p><a data-partner='acme' id='broken-partner-no-href'>Missing Href Partner</a></p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "demo-calc" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Select Preset Calc</title></head>"
        "<body><main><h1>Select Preset Calc</h1>"
        "<form class='calculator-form'>"
        "<label for='field-income'>Income</label>"
        "<input id='field-income' type='number' value='100000'>"
        "<label for='field-mult'>Multiplier</label>"
        "<select id='field-mult'><option value='1' selected>1x</option><option value='2'>2x</option></select>"
        "<button type='button' id='btn-preset-2x' data-calc-preset='2x'>Double Tier</button>"
        "<div class='output-value' id='val-total'>$100000</div>"
        "</form>"
        "<script>"
        "let multState = 1;"
        "const incEl = document.getElementById('field-income');"
        "const selEl = document.getElementById('field-mult');"
        "const outEl = document.getElementById('val-total');"
        "const render = () => { outEl.textContent = '$' + String(Math.round((Number(incEl.value) || 0) * multState)); };"
        "incEl.addEventListener('input', render);"
        "selEl.addEventListener('change', () => { multState = Number(selEl.value) || 1; render(); });"
        "document.getElementById('btn-preset-2x').addEventListener('click', () => {"
        "  incEl.value = '100000'; selEl.value = '2'; selEl.dispatchEvent(new Event('change', { bubbles: true }));"
        "});"
        "const hydrate = () => {"
        "  const q = new URLSearchParams(window.location.search).get('income');"
        "  if (q !== null) { incEl.value = q; }"
        "  render();"
        "};"
        "window.addEventListener('popstate', hydrate);"
        "hydrate();"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )
    compile_tenant_porcelain_estate(dist_dir, "profithelm")

    aud = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="profithelm", fail_closed=True, workers=2)
    rep = aud.run_audit()
    by_route = {f["route"]: f for f in rep["findings"]}

    # Blocker #4: select JS state must be fully restored to $100000 before primary calc snapshot runs
    calc_rep = by_route["/tools/demo-calc/"]["interactive_surface"]["calculator_and_presets"]
    assert calc_rep["passed"] is True, f"Calculator preset/select check failed: {calc_rep}"
    assert calc_rep["before_snapshot"] == "$100000", (
        f"Expected restored baseline '$100000' after preset test, got {calc_rep['before_snapshot']!r}"
    )

    # Minor #7: <a data-partner="acme"> without href must be flagged as unrouted_affiliate_links
    home_links = by_route["/"]["interactive_surface"]["links_audit"]
    assert any(item.get("id") == "broken-partner-no-href" for item in home_links["unrouted_affiliate_links"]), (
        f"Missing-href partner anchor was not flagged: {home_links}"
    )

