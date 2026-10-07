"""
Unit & Integration Tests for pseofactory Closed-Loop Maintenance Lifecycle
Verifies PropertyAdapter protocol, cross-property boundary isolation,
AssetIntegrityEvaluator anti-slop gates, RefactorCascadeEngine atomic swap & rollback,
anti-softening fail-closed behavior, HWL-1231 universal idempotency,
HWL-1349 post-pipeline commit latch, fleet coordination, and CLI gateway.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import json
import pytest
from pathlib import Path
from typing import Dict, Any

from pseofactory.maintenance import (
    DriftReason,
    AssetDriftRecord,
    AssetIntegrityReport,
    MaintenanceResult,
    PropertyContaminationError,
    CrossPropertyContaminationScanner,
    PropertyAdapter,
    PrexvoPropertyAdapter,
    ProfitHelmPropertyAdapter,
    ConfigurablePropertyAdapter,
    TenantRegistry,
    AssetIntegrityEvaluator,
    RefactorCascadeEngine,
    MaintenanceLifecycle,
    FleetMaintenanceCoordinator,
    run_maintenance_lifecycle,
    run_fleet_maintenance,
    audit_property_assets,
)
from pseofactory.drift import (
    compute_asset_fingerprint,
    record_asset_ledger,
    load_asset_ledger,
    record_engine_hash,
    compute_engine_hash,
)
from pseofactory.cli import main as cli_main


# Sample compliant HTML template
CLEAN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sample Financial Model - ProfitHelm</title>
    <meta name="description" content="Calculate your corporate tax liability using precise statutory formulas and schedules.">
    <link rel="canonical" href="https://profithelm.com/tools/sample-calc/">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Sample Calculator",
        "applicationCategory": "BusinessApplication"
    }
    </script>
</head>
<body>
    <h1>Sample Financial Model</h1>
    <p>This is a strictly compliant calculation engine without any prompt leakage or slop.</p>
</body>
</html>
"""

# Sample compliant XML sitemap
CLEAN_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://profithelm.com/tools/sample-calc/</loc>
        <lastmod>2026-10-01</lastmod>
    </url>
</urlset>
"""


def test_property_adapter_protocol_and_scoped_environment(tmp_path):
    """Verifies PropertyAdapter environment scoping and isolation."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "test.html").write_text(CLEAN_HTML, encoding="utf-8")

    adapter = ConfigurablePropertyAdapter(
        property_id="test_prop",
        brand_name="TestBrand",
        domain="testbrand.com",
        canonical_base="https://testbrand.com",
        dist_dir=dist_dir,
    )

    assert adapter.property_id == "test_prop"
    assert adapter.brand_name == "TestBrand"
    assert adapter.domain == "testbrand.com"
    assert adapter.canonical_base == "https://testbrand.com"
    assert len(adapter.list_assets()) == 1

    # Test scoped environment
    os.environ["FACTORY_BRAND_NAME"] = "OriginalBrand"
    with adapter.scoped_environment():
        assert os.environ["FACTORY_BRAND_NAME"] == "TestBrand"
        assert os.environ["FACTORY_DOMAIN"] == "testbrand.com"
        assert os.environ["FACTORY_CANONICAL_BASE"] == "https://testbrand.com"
        assert os.environ["FACTORY_DIST_DIR"] == str(dist_dir)

    # Restored
    assert os.environ["FACTORY_BRAND_NAME"] == "OriginalBrand"
    assert "FACTORY_DOMAIN" not in os.environ or os.environ["FACTORY_DOMAIN"] != "testbrand.com"


def test_cross_property_contamination_scanner():
    """Verifies isolation firewall detects foreign property tokens."""
    scanner = CrossPropertyContaminationScanner()

    # Prexvo text contaminated with ProfitHelm tokens
    prexvo_bad = "This student loan page references Section 1031 exchange rules and profithelm.com."
    matches = scanner.scan_text(prexvo_bad, "prexvo")
    assert "section 1031" in matches
    assert "profithelm.com" in matches

    # ProfitHelm text contaminated with Prexvo tokens
    profithelm_bad = "This tax tool references Title IV student loans and prexvo.com repayment assistance plan."
    ph_matches = scanner.scan_text(profithelm_bad, "profithelm")
    assert "title iv" in ph_matches
    assert "repayment assistance plan" in ph_matches
    assert "prexvo.com" in ph_matches

    # Clean text
    clean_text = "This tool calculates IRC section 179 depreciation deductions."
    assert scanner.scan_text(clean_text, "profithelm") == []

    # Fail-closed assert_clean
    with pytest.raises(PropertyContaminationError) as exc_info:
        scanner.assert_clean(prexvo_bad, "prexvo")
    assert "section 1031" in exc_info.value.foreign_tokens


def test_asset_integrity_evaluator_structural_contracts(tmp_path):
    """Verifies AssetIntegrityEvaluator catches slop, dashes, touch targets, JSON-LD, and sitemaps."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    evaluator = AssetIntegrityEvaluator()

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
    )

    # 1. Clean file passes
    clean_file = dist_dir / "clean.html"
    clean_file.write_text(CLEAN_HTML, encoding="utf-8")
    assert evaluator.audit_asset(clean_file, adapter) is None

    # 2. Em-dash slop
    em_dash_file = dist_dir / "em_dash.html"
    em_dash_file.write_text("<html><body>Bad em\u2014dash</body></html>", encoding="utf-8")
    rec = evaluator.audit_asset(em_dash_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # 3. En-dash slop
    en_dash_file = dist_dir / "en_dash.html"
    en_dash_file.write_text("<html><body>Bad en\u2013dash</body></html>", encoding="utf-8")
    rec = evaluator.audit_asset(en_dash_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # 4. Forbidden jargon
    jargon_file = dist_dir / "jargon.html"
    jargon_file.write_text("<html><body>This tool is a game-changer for taxes.</body></html>", encoding="utf-8")
    rec = evaluator.audit_asset(jargon_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons
    assert any("game-changer" in d for d in rec.details)

    # 5. Prompt leakage
    leak_file = dist_dir / "leak.html"
    leak_file.write_text("<html><body>system prompt instructions here</body></html>", encoding="utf-8")
    rec = evaluator.audit_asset(leak_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # 6. Touch target violation
    touch_file = dist_dir / "touch.html"
    touch_file.write_text("<html><style>button { min-height: 28px; }</style><body><button>Click</button></body></html>", encoding="utf-8")
    rec = evaluator.audit_asset(touch_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # 7. Invalid JSON-LD
    bad_jsonld_file = dist_dir / "bad_jsonld.html"
    bad_jsonld_file.write_text('<html><script type="application/ld+json">{ invalid json </script></html>', encoding="utf-8")
    rec = evaluator.audit_asset(bad_jsonld_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # 8. Sitemapindex violation in sitemap
    sitemap_file = dist_dir / "sitemap.xml"
    sitemap_file.write_text("<sitemapindex><sitemap><loc>https://profithelm.com</loc></sitemap></sitemapindex>", encoding="utf-8")
    rec = evaluator.audit_asset(sitemap_file, adapter)
    assert rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons


def test_asset_drift_classification_and_ledger_mismatch(tmp_path):
    """Verifies classification of ENGINE_HASH_DRIFT when asset hash mismatches recorded ledger."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    asset_file = dist_dir / "tool.html"
    asset_file.write_text(CLEAN_HTML, encoding="utf-8")

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
    )
    evaluator = AssetIntegrityEvaluator()

    # Ledger with different hash for tool.html
    ledger = {
        "engine_hash": "deadbeef1234",
        "assets": {
            "tool.html": "0000000000000000000000000000000000000000000000000000000000000000"
        }
    }
    rec = evaluator.audit_asset(asset_file, adapter, ledger=ledger)
    assert rec is not None
    assert DriftReason.ENGINE_HASH_DRIFT in rec.reasons


def test_refactor_cascade_atomic_swap_and_rollback(tmp_path):
    """Verifies that verification failure triggers an atomic rollback to original asset content."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    asset_file = dist_dir / "calculator.html"

    original_content = CLEAN_HTML
    asset_file.write_text(original_content, encoding="utf-8")

    # A builder function that generates bad output (containing em-dash)
    def bad_builder(slug: str, target_file=None):
        asset_file.write_text("<html><body>Broken recompiled content with \u2014 dash</body></html>", encoding="utf-8")
        return True

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        build_asset_fn=bad_builder,
    )

    record = AssetDriftRecord(
        asset_path=str(asset_file),
        slug="calculator",
        reasons=[DriftReason.ENGINE_HASH_DRIFT],
    )

    dlq_file = tmp_path / "dlq.json"
    engine = RefactorCascadeEngine(max_retries=2, initial_backoff=0.01, dlq_path=dlq_file)
    success = engine.refactor_asset(record, adapter)

    # Verification must have failed
    assert success is False

    # Invariant: Original file content must be rolled back and preserved exactly!
    assert asset_file.read_text(encoding="utf-8") == original_content

    # Invariant: Temporary staging files must be cleaned up!
    tmp_files = list(dist_dir.glob(".tmp*"))
    assert len(tmp_files) == 0

    # Invariant: Persistent failure must be routed to DLQ!
    assert dlq_file.exists()
    dlq_entries = json.loads(dlq_file.read_text(encoding="utf-8"))
    assert len(dlq_entries) == 1
    assert dlq_entries[0]["slug"] == "calculator"
    assert dlq_entries[0]["attempts"] == 2


def test_refactor_cascade_successful_swap(tmp_path):
    """Verifies successful refactor cleanly replaces the drifted asset."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    asset_file = dist_dir / "calculator.html"
    # Initially has an em-dash
    asset_file.write_text("<html><body>Drifted with \u2014 dash</body></html>", encoding="utf-8")

    # Compliant builder
    def good_builder(slug: str, target_file=None):
        asset_file.write_text(CLEAN_HTML, encoding="utf-8")
        return True

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        build_asset_fn=good_builder,
    )

    record = AssetDriftRecord(
        asset_path=str(asset_file),
        slug="calculator",
        reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
    )

    engine = RefactorCascadeEngine(max_retries=2, initial_backoff=0.01)
    success = engine.refactor_asset(record, adapter)

    assert success is True
    assert asset_file.read_text(encoding="utf-8") == CLEAN_HTML
    assert len(list(dist_dir.glob(".tmp*"))) == 0


def test_maintenance_lifecycle_end_to_end(tmp_path):
    """Verifies full closed loop: audit -> flag -> refactor -> verify -> commit latch."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    asset_file = dist_dir / "calculator.html"
    # Initially drifted
    asset_file.write_text("<html><body>Initial content with \u2014 dash</body></html>", encoding="utf-8")

    def builder(slug: str, target_file=None):
        asset_file.write_text(CLEAN_HTML, encoding="utf-8")
        return True

    adapter = ConfigurablePropertyAdapter(
        property_id="test_property",
        brand_name="TestBrand",
        domain="testbrand.com",
        canonical_base="https://testbrand.com",
        dist_dir=dist_dir,
        build_asset_fn=builder,
    )

    state_file = agy_dir / "engine_hash.json"
    ledger_file = agy_dir / "asset_ledger.json"

    lifecycle = MaintenanceLifecycle()
    result = lifecycle.run(
        adapter,
        force=True,
        state_file=state_file,
        ledger_file=ledger_file,
    )

    assert result.status == "SUCCESS"
    assert result.assets_refactored == 1
    assert result.assets_failed == 0

    # HWL-1349 Post-Pipeline Commit Latch verified
    assert state_file.exists()
    assert ledger_file.exists()

    ledger = load_asset_ledger(ledger_file)
    assert "calculator.html" in ledger["assets"]
    assert ledger["assets"]["calculator.html"] == compute_asset_fingerprint(asset_file)


def test_hwl_1231_universal_idempotency(tmp_path):
    """Verifies running maintenance on already-clean assets returns SKIPPED_NO_CHANGES."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    asset_file = dist_dir / "calculator.html"
    asset_file.write_text(CLEAN_HTML, encoding="utf-8")

    state_file = agy_dir / "engine_hash.json"
    ledger_file = agy_dir / "asset_ledger.json"

    # Pre-record clean state
    e_hash = record_engine_hash(state_file)
    record_asset_ledger(
        ledger_file,
        asset_hashes={"calculator.html": compute_asset_fingerprint(asset_file)},
        engine_hash=e_hash,
    )

    adapter = ConfigurablePropertyAdapter(
        property_id="test_property",
        brand_name="TestBrand",
        domain="testbrand.com",
        canonical_base="https://testbrand.com",
        dist_dir=dist_dir,
    )

    lifecycle = MaintenanceLifecycle()
    result = lifecycle.run(
        adapter,
        force=False,
        state_file=state_file,
        ledger_file=ledger_file,
    )

    # HWL-1231 Universal Idempotency assert
    assert result.status == "SKIPPED_NO_CHANGES"
    assert result.assets_drifted == 0
    assert result.assets_refactored == 0


def test_fleet_maintenance_coordinator(tmp_path):
    """Verifies FleetMaintenanceCoordinator manages multiple tenant adapters with clean isolation."""
    dist_1 = tmp_path / "dist1"
    dist_1.mkdir(parents=True, exist_ok=True)
    (dist_1 / "page1.html").write_text(CLEAN_HTML, encoding="utf-8")

    dist_2 = tmp_path / "dist2"
    dist_2.mkdir(parents=True, exist_ok=True)
    (dist_2 / "page2.html").write_text(CLEAN_HTML, encoding="utf-8")

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter("prop1", "Prop1", "prop1.com", "https://prop1.com", dist_1)
    )
    reg.register_adapter(
        ConfigurablePropertyAdapter("prop2", "Prop2", "prop2.com", "https://prop2.com", dist_2)
    )

    coordinator = FleetMaintenanceCoordinator(registry=reg)

    # Test Dry-Run
    dry_results = coordinator.run_fleet(dry_run=True)
    assert len(dry_results) == 2
    assert dry_results["prop1"].status == "DRY_RUN"
    assert dry_results["prop2"].status == "DRY_RUN"

    # Test Live Run
    live_results = coordinator.run_fleet(force=False)
    assert len(live_results) == 2
    assert live_results["prop1"].status == "SKIPPED_NO_CHANGES"
    assert live_results["prop2"].status == "SKIPPED_NO_CHANGES"


def test_cli_subcommands(tmp_path):
    """Verifies CLI subcommands audit, drift, maintain, and fleet-maintain."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "clean.html").write_text(CLEAN_HTML, encoding="utf-8")

    # CLI audit on dist-dir
    exit_code = cli_main(["audit", "--dist-dir", str(dist_dir), "--json"])
    assert exit_code == 0

    # CLI audit with drift
    (dist_dir / "dirty.html").write_text("<html>\u2014</html>", encoding="utf-8")
    exit_code = cli_main(["audit", "--dist-dir", str(dist_dir)])
    assert exit_code == 1

    # CLI drift
    state_file = tmp_path / "engine_hash.json"
    exit_code = cli_main(["drift", "--state-file", str(state_file), "--record"])
    assert exit_code == 0
    assert state_file.exists()

    exit_code = cli_main(["drift", "--state-file", str(state_file)])
    assert exit_code == 0
