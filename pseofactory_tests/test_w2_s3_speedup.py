"""
Wave 2 Lane S3 Speedup & Invariant Preservation Tests:
1. Batched CDP viewport evaluation round-trip reduction & full defect detection parity.
2. Streamlined _wait_for_layout_settle / _build_js_settle_prelude behavior.
3. compute_estate_shared_digest & BrowserVerifyReceiptStore coalesced batching & invalidation.
4. compute_auto_worker_count CPU/RAM scaling and safety caps.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

import pseofactory.browser_verifier as bv
from pseofactory.browser_verifier import (
    BrowserVerifyReceiptStore,
    UnifiedBrowserAuditor,
    compute_auto_worker_count,
    discover_headless_chrome_binary,
)
from pseofactory_tests.test_browser_cdp_nav_guard import _FakeCDPWebSocket


def test_batched_cdp_eval_reduces_roundtrips_without_weakening_fake_ws_checks(tmp_path: Path) -> None:
    """
    Verifies _audit_route_on_ws consolidates post-navigation viewport checks into batched
    Runtime.evaluate calls (far fewer than the legacy 14+ round-trips) while preserving
    all _FakeCDPWebSocket navigation barrier and E2E checks.
    """
    base_url = "http://127.0.0.1:45210"
    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path, fail_closed=True)
    fake_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=2,
        interactive_polls=1,
    )

    finding = asyncio.run(auditor.verify_route(base_url, "/tools/second/", ws=fake_ws))
    assert finding["widget_failures"] == []
    assert finding["interactive_surface"]["passed"] is True
    assert finding["overflow_1440"] is False
    assert finding["overflow_1280"] is False
    assert finding["overflow_375"] is False

    # Post-navigation evals should be strictly batched:
    # 1 (1440 batch) + 1 (1280 settle+overflow) + 1 (375 batch) + 1 (E2E) = 4 evals
    post_nav_evals = [item for item in fake_ws.eval_log if item[2] != "window.innerWidth"]
    assert len(post_nav_evals) <= 5, f"Expected <=5 batched post-nav evals, got {len(post_nav_evals)}: {post_nav_evals}"
    assert set(fake_ws.viewport_widths_seen) >= {1440, 1280, 375}


def test_layout_settle_prelude_contains_readiness_and_raf_guards() -> None:
    prelude = UnifiedBrowserAuditor._build_js_settle_prelude(1280, 800, include_equals_token=False)
    assert "document.readyState === 'complete'" in prelude
    assert "Number(window.innerWidth) == 1280" in prelude
    assert "Number(window.innerHeight) == 800" in prelude
    assert "requestAnimationFrame" in prelude
    assert "document.fonts" in prelude
    assert "innerWidth ===" not in prelude

    standalone_prelude = UnifiedBrowserAuditor._build_js_settle_prelude(1440, 900, include_equals_token=True)
    assert "window.innerWidth === 1440" in standalone_prelude
    assert "window.innerHeight === 900" in standalone_prelude


def test_receipt_store_batch_coalesces_writes_and_handles_eviction(tmp_path: Path) -> None:
    """
    Verifies BrowserVerifyReceiptStore.batch coalesces many route updates into periodic
    atomic disk writes (instead of rewriting JSON on every single route) and preserves
    pass-only + eviction semantics.
    """
    receipt_file = tmp_path / "receipts" / "tenant.json"
    store = BrowserVerifyReceiptStore(receipt_file)

    with store.batch(
        property_id="tenant",
        chrome_version="Chrome 130",
        estate_shared_digest="digest_abc",
        flush_every=4,
    ):
        for idx in range(10):
            route = f"/tools/calc-{idx}/"
            store.update_routes(
                property_id="tenant",
                chrome_version="Chrome 130",
                estate_shared_digest="digest_abc",
                passed_entries={
                    route: {
                        "verify_key": f"key_{idx}",
                        "status": "PASS",
                        "screen_archetype": "interactive_calculator",
                    }
                },
            )
        # Evict one previously buffered route and ensure eviction wins
        store.update_routes(
            property_id="tenant",
            chrome_version="Chrome 130",
            estate_shared_digest="digest_abc",
            passed_entries={},
            evict_routes=["/tools/calc-3/"],
        )

    # 10 passes + 1 evict with flush_every=4 -> at most 3 atomic disk writes (not 11!)
    assert store._write_count <= 3, f"Expected coalesced writes <= 3, got {store._write_count}"
    assert not list(receipt_file.parent.glob("*.tmp"))

    loaded = store.load_routes()
    assert len(loaded) == 9
    assert "/tools/calc-3/" not in loaded
    assert loaded["/tools/calc-9/"]["verify_key"] == "key_9"

    # Re-running identical update must be a no-op (0 extra writes)
    prev_writes = store._write_count
    store.update_routes(
        property_id="tenant",
        chrome_version="Chrome 130",
        estate_shared_digest="digest_abc",
        passed_entries={
            "/tools/calc-0/": {
                "verify_key": "key_0",
                "status": "PASS",
                "screen_archetype": "interactive_calculator",
            }
        },
    )
    assert store._write_count == prev_writes


def test_estate_shared_digest_prunes_syndication_and_detects_asset_mutations(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "css").mkdir(parents=True, exist_ok=True)
    (dist_dir / "syndication").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "alpha").mkdir(parents=True, exist_ok=True)

    css_file = dist_dir / "css" / "style.css"
    css_file.write_text("body { color: #0f172a; }\n", encoding="utf-8")
    (dist_dir / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")
    (dist_dir / "tools" / "alpha" / "index.html").write_text("<html><body>Alpha</body></html>", encoding="utf-8")
    # Syndication files must not affect estate_shared_digest
    (dist_dir / "syndication" / "feed.xml").write_text("<rss>v1</rss>", encoding="utf-8")

    opts = {"property_id": "test", "fail_closed": True}
    d1 = BrowserVerifyReceiptStore.compute_estate_shared_digest(dist_dir, "Chrome 130", opts, verifier_digest="v1")

    (dist_dir / "syndication" / "feed.xml").write_text("<rss>v2-changed</rss>", encoding="utf-8")
    d2 = BrowserVerifyReceiptStore.compute_estate_shared_digest(dist_dir, "Chrome 130", opts, verifier_digest="v1")
    assert d1 == d2

    # Same-size mutation in CSS must still change digest (full byte hashing, no mtime-only shortcut)
    orig_bytes = css_file.read_bytes()
    mutated_bytes = b"X" + orig_bytes[1:]
    assert len(mutated_bytes) == len(orig_bytes)
    css_file.write_bytes(mutated_bytes)
    d3 = BrowserVerifyReceiptStore.compute_estate_shared_digest(dist_dir, "Chrome 130", opts, verifier_digest="v1")
    assert d3 != d1


def test_compute_auto_worker_count_scaling_and_ram_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.delenv("PSEOFACTORY_BROWSER_WORKERS", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 10)
    monkeypatch.setattr(bv, "_get_available_ram_gb", lambda: 12.0)

    assert compute_auto_worker_count(1) == 1
    assert compute_auto_worker_count(2) == 2
    assert compute_auto_worker_count(4) == 2
    assert compute_auto_worker_count(22) == 6
    assert compute_auto_worker_count(168) == 6

    # Low RAM caps workers safely so concurrent tenants cannot OOM Chrome
    monkeypatch.setattr(bv, "_get_available_ram_gb", lambda: 2.1)
    assert compute_auto_worker_count(100) == 2
    assert compute_auto_worker_count(100, requested_workers=3) == 2

    # Under pytest-xdist, auto worker count stays 1 unless explicitly requested (with ample RAM)
    monkeypatch.setattr(bv, "_get_available_ram_gb", lambda: 12.0)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
    assert compute_auto_worker_count(100) == 1
    assert compute_auto_worker_count(100, requested_workers=3) == 3


@pytest.mark.host_estate
def test_batched_real_chrome_preserves_json_preset_failure_detection(tmp_path: Path) -> None:
    """
    Real Chrome test verifying smart JSON preset perturbation still catches a broken
    JSON data-calc-preset button while passing a working JSON preset button.
    """
    chrome_bin, _ = discover_headless_chrome_binary()
    if not chrome_bin:
        pytest.skip("No local headless Chromium binary installed")

    dist_dir = tmp_path / "preset_json_dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>JSON Preset Regression Probe</title></head>"
        "<body><main><h1>JSON Preset Probe</h1>"
        "<form class='calculator-form'>"
        "<label for='field-amount'>Amount</label>"
        "<input id='field-amount' type='number' value='100'>"
        "<button type='button' id='btn-good-preset' data-calc-preset='{\"amount\":100}'>Good</button>"
        "<button type='button' id='btn-broken-preset' data-calc-preset='{\"amount\":250}'>Broken</button>"
        "<div class='output-value' id='val-out'>$100</div>"
        "</form>"
        "<script>"
        "const inp = document.getElementById('field-amount');"
        "const out = document.getElementById('val-out');"
        "const render = () => { out.textContent = '$' + String(Number(inp.value) || 0); };"
        "inp.addEventListener('input', render);"
        "document.getElementById('btn-good-preset').addEventListener('click', () => {"
        "  inp.value = '100'; render();"
        "});"
        "const hydrate = () => {"
        "  const q = new URLSearchParams(window.location.search).get('amount');"
        "  if (q !== null) inp.value = q;"
        "  render();"
        "};"
        "window.addEventListener('popstate', hydrate);"
        "hydrate();"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )

    aud = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="profithelm", fail_closed=True, workers=1)
    rep = aud.run_audit()
    assert rep["passed"] is False
    calc = rep["findings"][0]["interactive_surface"]["calculator_and_presets"]
    assert calc["passed"] is False
    assert "btn-broken-preset" in calc["button_failures"]
    assert "btn-good-preset" not in calc["button_failures"]
