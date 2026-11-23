"""
Regression tests for GSC/SEO config fixes across maintenance, porcelain_shell,
compiler, gsc_remediation, estate_common, and tenant_facts.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pseofactory import compiler, maintenance
from pseofactory.estate_common import normalize_tenant_seo_title
from pseofactory.gsc_remediation import _normalize_meta_120_155, _normalize_title_50_60
from pseofactory.indexer import PushIndexer
from pseofactory.porcelain_shell import (
    _discover_estate_tools_and_gsc_token,
    _fit_seo_title,
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
)
from pseofactory.tenant_facts import (
    CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER,
    TenantFactStore,
)


def test_deferred_reflect_does_not_poison_index_push_ledger(tmp_path: Path, monkeypatch) -> None:
    """Deferred reflect mode must not pre-populate unpushed sitemap URLs into index_push_ledger.json."""
    repo_dir = tmp_path / "prexvo"
    dist_dir = repo_dir / "dist"
    tool_dir = dist_dir / "tools" / "brand-new-rap-calc"
    tool_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Prexvo Student Loan Engine</title></head><body><h1>Home</h1></body></html>",
        encoding="utf-8",
    )
    (tool_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Brand New RAP Calc | Prexvo</title></head><body><h1>RAP</h1></body></html>",
        encoding="utf-8",
    )
    new_url = "https://prexvo.com/tools/brand-new-rap-calc/"
    (dist_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>https://prexvo.com/</loc></url>\n"
        f"  <url><loc>{new_url}</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )

    adapter = maintenance.SubprocessPropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
    )
    reg = maintenance.TenantRegistry()
    reg.register_adapter(adapter)

    clean_report = maintenance.AssetIntegrityReport(
        property_id="prexvo",
        total_assets_checked=2,
        compliant_assets_count=2,
        drifted_assets_count=0,
        drifted_assets=[],
        status="PASS",
    )
    monkeypatch.setattr(maintenance.AssetIntegrityEvaluator, "audit_all", lambda self, *a, **k: clean_report)
    monkeypatch.setattr(
        maintenance.RetroReflectionEngine,
        "audit_estate",
        classmethod(lambda cls, *a, **k: {"stale_count": 0, "stale_pages": []}),
    )
    monkeypatch.setattr(
        maintenance.RetroReflectionEngine,
        "retrofit_estate",
        classmethod(lambda cls, *a, **k: {"retrofitted_count": 0, "retrofitted_paths": []}),
    )

    maintenance.reflect_and_recompile_all_assets(
        properties=["prexvo"],
        force=True,
        latch_state=True,
        run_downstream=False,
        defer_live_indexing=True,
        registry=reg,
        workspace_root=tmp_path,
        verbose=False,
    )

    ledger_path = repo_dir / ".agy" / "index_push_ledger.json"
    if ledger_path.is_file():
        ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
        assert new_url not in ledger_data, f"Deferred reflect poisoned push ledger with {new_url}"

    idx = PushIndexer(
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=repo_dir,
        dist_dir=dist_dir,
        tenant_id="prexvo",
    )
    inspected = idx.inspect_platform_assets()
    assert new_url in inspected["new_urls"]


def test_downstream_chain_reconciles_actual_inspect_platform_assets_keys(tmp_path: Path) -> None:
    """_execute_autonomous_downstream_chain reads new_urls/existing_urls and get_url_content_hash cleanly."""
    from pseofactory.action_bus import HumanActionBus

    repo_dir = tmp_path / "prexvo"
    dist_dir = repo_dir / "dist"
    tool_dir = dist_dir / "tools" / "rap-payment-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Prexvo</title></head><body><h1>Prexvo</h1></body></html>",
        encoding="utf-8",
    )
    (tool_dir / "index.html").write_text(
        "<!doctype html><html><head><title>RAP Calculator | Prexvo</title></head><body><h1>RAP</h1></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    tool_url = "https://prexvo.com/tools/rap-payment-calculator/"
    blocked_url = "https://prexvo.com/tools/blocked-tool/"
    (dist_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>https://prexvo.com/</loc></url>\n"
        f"  <url><loc>{tool_url}</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )

    adapter = maintenance.SubprocessPropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))

    with patch("pseofactory.distributor.dispatch_to_distribution_lead", return_value={"status": "SKIPPED"}), patch(
        "pseofactory.indexer.PushIndexer.dispatch_automated_indexing",
        return_value={"status": "SUCCESS", "blocked_urls": [blocked_url], "indexnow": {"status": "DISPATCHED"}},
    ):
        maintenance._execute_autonomous_downstream_chain(
            adapter,
            dry_run=False,
            defer_live_indexing=False,
            run_id="test-live-ledger",
            action_bus=bus,
        )

    ledger_path = repo_dir / ".agy" / "index_push_ledger.json"
    assert ledger_path.is_file()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert tool_url in ledger
    assert ledger[tool_url]["hash"]
    assert "https://prexvo.com/robots.txt" not in ledger
    assert blocked_url not in ledger


def test_canonical_gsc_verification_meta_enforced_across_maintenance_and_porcelain(
    tmp_path: Path, monkeypatch
) -> None:
    """Fake/mismatched GSC verification tokens (including Prexvo rX8v...) are replaced with canonical token."""
    fake_prexvo = "rX8vK2mP9nQ4wL7tB5zC3jF6hG1dS0eV4kM8pY2uA9q"
    canonical_prexvo = "At5f9a2APEkZhsFx0LICFC5R-TNKsXxzNsbG5YhUoIA"
    monkeypatch.delenv("GSC_VERIFICATION_TOKEN", raising=False)
    monkeypatch.delenv("PREXVO_GSC_VERIFICATION_TOKEN", raising=False)

    px_dist = tmp_path / "prexvo" / "dist"
    (px_dist / "tools" / "rap-calc").mkdir(parents=True, exist_ok=True)
    poisoned_html = (
        "<!doctype html><html><head>"
        f'<meta name="google-site-verification" content="{fake_prexvo}">'
        '<title>Prexvo | Student Loan Calculators | Prexvo</title>'
        "</head><body><main><h1>Prexvo</h1></main></body></html>"
    )
    (px_dist / "index.html").write_text(poisoned_html, encoding="utf-8")
    (px_dist / "tools" / "index.html").write_text(poisoned_html, encoding="utf-8")
    (px_dist / "tools" / "rap-calc" / "index.html").write_text(poisoned_html, encoding="utf-8")

    # _discover_estate_tools_and_gsc_token must prefer canonical token over poisoned index.html
    profile_px = get_porcelain_tenant_profile("prexvo")
    _, discovered_tok = _discover_estate_tools_and_gsc_token(px_dist, profile_px)
    assert discovered_tok == canonical_prexvo

    # normalize_html_to_porcelain_shell must replace fake_prexvo AND strip duplicate brand in <title>
    norm_html, _ = normalize_html_to_porcelain_shell(poisoned_html, "index.html", profile_px)
    assert fake_prexvo not in norm_html
    assert f'content="{canonical_prexvo}"' in norm_html
    assert "<title>Prexvo | Student Loan Calculators</title>" in norm_html

    # sync_tenant_publisher_prerequisites must replace fake_prexvo on disk
    maintenance.RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        px_dist, "prexvo", "https://prexvo.com"
    )
    for rel in ("index.html", "tools/index.html", "tools/rap-calc/index.html"):
        txt = (px_dist / rel).read_text(encoding="utf-8")
        assert fake_prexvo not in txt
        assert canonical_prexvo in txt

    # Env override must be respected when explicitly set
    monkeypatch.setenv("PREXVO_GSC_VERIFICATION_TOKEN", "custom-env-override-token-123")
    norm_env, _ = normalize_html_to_porcelain_shell(poisoned_html, "index.html", profile_px)
    assert 'content="custom-env-override-token-123"' in norm_env
    assert fake_prexvo not in norm_env


def test_indexnow_key_sync_per_domain_for_all_tenants(tmp_path: Path, monkeypatch) -> None:
    """sync_tenant_publisher_prerequisites writes exact deterministic per-domain IndexNow <key>.txt."""
    monkeypatch.delenv("GAINHELM_INDEXNOW_STEM", raising=False)
    cases = [
        ("profithelm", "https://profithelm.com", hashlib.sha256(b"profithelm.com:indexnow:v2").hexdigest()[:32]),
        ("gainhelm", "https://gainhelm.com", "c5430f81d11340a6bda3162725e24a03"),
        ("prexvo", "https://prexvo.com", hashlib.sha256(b"prexvo.com:indexnow:v1").hexdigest()[:32]),
        ("lienbond", "https://lienbond.com", hashlib.sha256(b"lienbond.com:indexnow:v1").hexdigest()[:32]),
        ("acmecorp", "https://acmecorp.com", hashlib.sha256(b"acmecorp.com:indexnow:v1").hexdigest()[:32]),
    ]
    for prop_id, canon, expected_key in cases:
        d = tmp_path / prop_id / "dist"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text("<!doctype html><html><head></head><body>Hi</body></html>", encoding="utf-8")
        maintenance.RetroReflectionEngine.sync_tenant_publisher_prerequisites(d, prop_id, canon)
        kf = d / f"{expected_key}.txt"
        assert kf.is_file(), f"Missing IndexNow key file for {prop_id}: {kf}"
        assert kf.read_text(encoding="utf-8").strip() == expected_key


def test_lienbond_registries_robots_dynamic_count_and_erisa_copy(tmp_path: Path) -> None:
    """Verifies LienBond runner_dist_map, registrar ledger, robots.txt bots, dynamic count, and ERISA non-leak."""
    runner_map = maintenance._build_runner_dist_map()
    assert Path("/home/ubuntuadmin/projects/lienbond/dist") in runner_map
    assert "lienbond.com" in CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER
    ok_reg, msg_reg, _ = TenantFactStore.verify_registrar_ledger_integrity()
    assert ok_reg is True, msg_reg

    out_dir = tmp_path / "lienbond_out"
    res = compiler.compile_lienbond_estate(out_dir, run_retrofit=False)
    dist = out_dir / "dist"
    total_tools = res["compiled_count"]
    assert total_tools >= 10

    robots_txt = (dist / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: Googlebot" in robots_txt
    assert "User-agent: Bingbot" in robots_txt
    assert "/_astro/" not in robots_txt

    home_html = (dist / "index.html").read_text(encoding="utf-8")
    tools_html = (dist / "tools" / "index.html").read_text(encoding="utf-8")
    assert f"({total_tools} Models)" in home_html
    assert f"All {total_tools} LienBond Quantitative Calculators" in tools_html
    assert f"Browse all {total_tools} LienBond calculators" in tools_html
    assert "ten deterministic calculators" not in tools_html.lower()

    erisa_html = (dist / "tools" / "erisa-fidelity-bond-coverage-amount-calculator" / "index.html").read_text(
        encoding="utf-8"
    )
    md_m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', erisa_html)
    assert md_m is not None
    erisa_desc = md_m.group(1)
    assert 120 <= len(erisa_desc) <= 155, f"Unexpected ERISA desc length {len(erisa_desc)}: {erisa_desc}"
    assert "29 U.S.C. Section 1112" in erisa_desc
    assert "3131" not in erisa_desc
    assert "NCCI" not in erisa_desc

    gsc_erisa_desc = _normalize_meta_120_155(
        "short",
        "lienbond",
        "ERISA Section 412 Fidelity Bond Coverage Amount Calculator",
        slug="erisa-fidelity-bond-coverage-amount-calculator",
    )
    assert 120 <= len(gsc_erisa_desc) <= 155
    assert "29 U.S.C. Section 1112" in gsc_erisa_desc
    assert "3131" not in gsc_erisa_desc
    assert "NCCI" not in gsc_erisa_desc


def test_duplicate_brand_prevention_and_cleaning_across_title_normalizers() -> None:
    """Title normalizers never emit ProfitHelm: ... | ProfitHelm or Prexvo | ... | Prexvo."""
    t_ph = normalize_tenant_seo_title(
        "ProfitHelm: 2026 Financial & Tax Modeling Engine | ProfitHelm",
        "ProfitHelm",
    )
    assert t_ph.lower().count("profithelm") == 1, t_ph

    t_px = normalize_tenant_seo_title(
        "Prexvo | Student Loan Repayment Calculators | Prexvo",
        "Prexvo",
    )
    assert t_px.lower().count("prexvo") == 1, t_px

    t_gsc_ph = _normalize_title_50_60(
        "ProfitHelm: 2026 Commercial Tax & Financial Engine | ProfitHelm",
        "ProfitHelm",
        "profithelm",
        secondary_modifier="non_tool",
    )
    assert t_gsc_ph.lower().count("profithelm") == 1, t_gsc_ph
    assert 50 <= len(t_gsc_ph) <= 60, t_gsc_ph

    t_gsc_px = _normalize_title_50_60(
        "Prexvo | Federal Student Loan Repayment Tools | Prexvo",
        "Prexvo",
        "prexvo",
        secondary_modifier="non_tool",
    )
    assert t_gsc_px.lower().count("prexvo") == 1, t_gsc_px
    assert 50 <= len(t_gsc_px) <= 60, t_gsc_px

    t_fit_px = _fit_seo_title("Prexvo | Student Loan Calculators | Prexvo", "Prexvo")
    assert t_fit_px.lower().count("prexvo") == 1, t_fit_px
    assert 50 <= len(t_fit_px) <= 60, t_fit_px

    raw_hp = (
        "<!doctype html><html><head>"
        "<title>ProfitHelm: 2026 Financial &amp; Tax Modeling Engine | ProfitHelm</title>"
        '<meta property="og:title" content="ProfitHelm: 2026 Financial &amp; Tax Modeling Engine | ProfitHelm">'
        "</head><body><main><h1>ProfitHelm</h1></main></body></html>"
    )
    profile_ph = get_porcelain_tenant_profile("profithelm")
    norm_hp, _ = normalize_html_to_porcelain_shell(raw_hp, "index.html", profile_ph)
    title_m = re.search(r"<title>(.*?)</title>", norm_hp, flags=re.IGNORECASE)
    assert title_m is not None
    assert title_m.group(1).lower().count("profithelm") == 1, title_m.group(1)
    assert 'property="og:title" content="ProfitHelm: 2026 Financial &amp; Tax Modeling Engine"' in norm_hp


def test_indexnow_key_sync_matches_indexer_for_www_and_custom_domains(tmp_path: Path, monkeypatch) -> None:
    """maintenance IndexNow key file sync must match derive_deterministic_indexnow_key for www. and 50+ domains."""
    from pseofactory.indexer import derive_deterministic_indexnow_key

    monkeypatch.delenv("GAINHELM_INDEXNOW_STEM", raising=False)
    for prop_id, canon in (
        ("profithelm", "https://www.profithelm.com"),
        ("gainhelm", "https://www.gainhelm.com"),
        ("prexvo", "https://www.prexvo.com"),
        ("lienbond", "https://www.lienbond.com"),
        ("newtenant55", "https://www.newtenant55.io"),
    ):
        d = tmp_path / prop_id / "dist"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text("<!doctype html><html><head></head><body>Hi</body></html>", encoding="utf-8")
        maintenance.RetroReflectionEngine.sync_tenant_publisher_prerequisites(d, prop_id, canon)
        expected_key = derive_deterministic_indexnow_key(canon)
        kf = d / f"{expected_key}.txt"
        assert kf.is_file(), f"Missing unified IndexNow key file for {canon}: {kf}"
        assert kf.read_text(encoding="utf-8").strip() == expected_key


def test_downstream_and_reflect_ledger_failure_guard_metadata_preservation_and_leaf_skip(
    tmp_path: Path, monkeypatch
) -> None:
    """Downstream and reflect must not backfill failed indexing, must preserve extra metadata, and must skip leaf URLs."""
    from pseofactory.action_bus import HumanActionBus

    repo_dir = tmp_path / "prexvo"
    dist_dir = repo_dir / "dist"
    hub_dir = dist_dir / "tools" / "rap-payment-calculator"
    leaf_dir = hub_dir / "california"
    leaf_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Prexvo</title></head><body><h1>Prexvo</h1></body></html>",
        encoding="utf-8",
    )
    (hub_dir / "index.html").write_text(
        "<!doctype html><html><head><title>RAP Hub | Prexvo</title></head><body><h1>Hub</h1></body></html>",
        encoding="utf-8",
    )
    (leaf_dir / "index.html").write_text(
        "<!doctype html><html><head><title>RAP CA | Prexvo</title></head><body><h1>Leaf</h1></body></html>",
        encoding="utf-8",
    )
    hub_url = "https://prexvo.com/tools/rap-payment-calculator/"
    leaf_url = "https://prexvo.com/tools/rap-payment-calculator/california/"
    (dist_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url><loc>https://prexvo.com/</loc></url>\n"
        f"  <url><loc>{hub_url}</loc></url>\n"
        f"  <url><loc>{leaf_url}</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )

    ledger_path = repo_dir / ".agy" / "index_push_ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    seed_entry = {
        "hash": "stale-hash",
        "last_pushed": "2026-01-01T00:00:00+00:00",
        "push_count": 2,
        "tenant_id": "prexvo",
        "google_rollover_queued": True,
        "custom_meta": "keep-me",
        "engines": {"indexnow": {"hash": "stale-hash"}},
    }
    ledger_path.write_text(json.dumps({hub_url: seed_entry}, indent=2), encoding="utf-8")

    adapter = maintenance.SubprocessPropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))

    # 1. Downstream success: preserve tenant_id and custom metadata, and skip leaf URL
    with patch("pseofactory.distributor.dispatch_to_distribution_lead", return_value={"status": "SKIPPED"}), patch(
        "pseofactory.indexer.PushIndexer.dispatch_automated_indexing",
        return_value={"status": "SUCCESS", "blocked_urls": [], "urls_submitted": [hub_url], "indexnow": {"status": "DISPATCHED"}},
    ):
        ds_ok = maintenance._execute_autonomous_downstream_chain(
            adapter,
            dry_run=False,
            defer_live_indexing=False,
            run_id="test-meta-leaf",
            action_bus=bus,
        )
    assert ds_ok["indexing_indexnow_status"] == "DISPATCHED"
    ledger_after = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger_after[hub_url]["tenant_id"] == "prexvo"
    assert ledger_after[hub_url]["google_rollover_queued"] is True
    assert ledger_after[hub_url]["custom_meta"] == "keep-me"
    assert leaf_url not in ledger_after

    # 2. Reflect must NOT backfill ledger when downstream indexing failed / quarantined / errored
    reg = maintenance.TenantRegistry()
    reg.register_adapter(adapter)
    clean_report = maintenance.AssetIntegrityReport(
        property_id="prexvo",
        total_assets_checked=3,
        compliant_assets_count=3,
        drifted_assets_count=0,
        drifted_assets=[],
        status="PASS",
    )
    monkeypatch.setattr(maintenance.AssetIntegrityEvaluator, "audit_all", lambda self, *a, **k: clean_report)
    monkeypatch.setattr(
        maintenance.RetroReflectionEngine,
        "audit_estate",
        classmethod(lambda cls, *a, **k: {"stale_count": 0, "stale_pages": []}),
    )
    monkeypatch.setattr(
        maintenance.RetroReflectionEngine,
        "retrofit_estate",
        classmethod(lambda cls, *a, **k: {"pages_retrofitted": 1, "retrofitted_count": 1, "retrofitted_paths": []}),
    )

    for failure_summary in (
        {"indexing_status": "QUARANTINED_ALL"},
        {"indexing_status": "EXCEPTION_ROUTED"},
        {"indexing_status": "SUCCESS", "indexnow": {"status": "FAILED"}},
    ):
        ledger_path.write_text("{}", encoding="utf-8")
        with patch.object(maintenance, "_execute_autonomous_downstream_chain", return_value=failure_summary) as mock_ds:
            maintenance.reflect_and_recompile_all_assets(
                properties=["prexvo"],
                force=True,
                latch_state=True,
                run_downstream=True,
                defer_live_indexing=False,
                registry=reg,
                workspace_root=tmp_path,
                verbose=False,
            )
            mock_ds.assert_called_once()
        assert json.loads(ledger_path.read_text(encoding="utf-8")) == {}, f"Backfilled on {failure_summary}"

    # 3. Reflect success updates hash while preserving existing extra metadata keys
    ledger_path.write_text(json.dumps({hub_url: seed_entry}, indent=2), encoding="utf-8")
    with patch.object(
        maintenance,
        "_execute_autonomous_downstream_chain",
        return_value={"indexing_status": "SUCCESS", "indexing_indexnow_status": "DISPATCHED", "indexing_urls_submitted": [hub_url]},
    ) as mock_ds_ok:
        maintenance.reflect_and_recompile_all_assets(
            properties=["prexvo"],
            force=True,
            latch_state=True,
            run_downstream=True,
            defer_live_indexing=False,
            registry=reg,
            workspace_root=tmp_path,
            verbose=False,
        )
        mock_ds_ok.assert_called_once()
    reflected_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert reflected_ledger[hub_url]["hash"] != "stale-hash"
    assert reflected_ledger[hub_url]["tenant_id"] == "prexvo"
    assert reflected_ledger[hub_url]["google_rollover_queued"] is True
    assert reflected_ledger[hub_url]["custom_meta"] == "keep-me"
    assert leaf_url not in reflected_ledger


def test_lienbond_tools_directory_quick_answer_is_idempotent_across_tool_counts() -> None:
    """lb_stale_qa must trigger on mismatch/stale wording and be idempotent for 10, 11, 13, and 50 tools."""
    for tool_count in (10, 11, 13, 50):
        links = "".join(f'<a href="/tools/bond-calc-{i}/">Calc {i}</a>' for i in range(tool_count))
        stale_html = (
            "<!doctype html><html><head><title>Tools | LienBond</title></head><body>"
            '<aside class="quick-answer"><div class="quick-answer-body">'
            "<p>LienBond provides ten deterministic calculators for surety bonds.</p>"
            f"</div></aside><main>{links}</main></body></html>"
        )
        fixed_html, changed_1 = maintenance._normalize_spoke_and_synthesized_body_bloat(
            stale_html,
            property_id="lienbond",
            slug="tools-directory",
            topic_label="LienBond Tools",
            stat_auth="40 U.S.C. 3131",
            econ_ds="Treasury Circular 570",
        )
        assert changed_1 is True
        assert f"{tool_count} institutional" in fixed_html
        fixed_html_2, changed_2 = maintenance._normalize_spoke_and_synthesized_body_bloat(
            fixed_html,
            property_id="lienbond",
            slug="tools-directory",
            topic_label="LienBond Tools",
            stat_auth="40 U.S.C. 3131",
            econ_ds="Treasury Circular 570",
        )
        assert changed_2 is False, f"Non-idempotent for {tool_count} tools"
        assert fixed_html_2 == fixed_html


def test_edge_gone_safe_js_quoting_and_recreated_route_removal(tmp_path: Path) -> None:
    """_sync_middleware_redirect_table must quote edgeGone safely and drop routes recreated on disk."""
    from pseofactory.edge import _sync_middleware_redirect_table

    dist_dir = tmp_path / "dist"
    (dist_dir / "recreated-page").mkdir(parents=True, exist_ok=True)
    (dist_dir / "recreated-page" / "index.html").write_text("<html>Live</html>", encoding="utf-8")

    mw_seed = (
        "export async function onRequest(context) {\n"
        "  const url = new URL(context.request.url);\n"
        "  const hostname = url.hostname.toLowerCase();\n"
        "  const pathname = url.pathname;\n\n"
        "  const edgeRedirects = {\n"
        "  };\n"
        "  // [BEGIN_EDGE_REDIRECT_DISPATCH]\n"
        "  const edgeGone = new Set([\n"
        '    "/recreated-page",\n'
        '    "/recreated-page/",\n'
        '    "/still-gone",\n'
        '    "/still-gone/",\n'
        "  ]);\n"
        "  // [END_EDGE_REDIRECT_DISPATCH]\n"
        "  return await context.next();\n"
        "}\n"
    )
    quoted_path = '/weird"quote\\slug'
    mw_out = _sync_middleware_redirect_table(
        mw_seed,
        {},
        apex_domain="example.com",
        extra_gone_paths=[quoted_path],
        dist_dir=dist_dir,
    )
    assert '"/recreated-page"' not in mw_out
    assert '"/recreated-page/"' not in mw_out
    assert '"/still-gone"' in mw_out
    assert json.dumps(quoted_path) in mw_out
    assert json.dumps(quoted_path + "/") in mw_out
    # Second pass must be idempotent even with escaped quotes/backslashes
    mw_out_2 = _sync_middleware_redirect_table(
        mw_out,
        {},
        apex_domain="example.com",
        extra_gone_paths=[quoted_path],
        dist_dir=dist_dir,
    )
    assert mw_out_2 == mw_out


def test_lienbond_legacy_poisoned_meta_healed_and_all_13_slugs_clean() -> None:
    """maintenance.py heals legacy poisoned LienBond meta descriptions and all 13 slugs emit clean topic-accurate copy."""
    from pseofactory.contracts import detect_sentence_truncation_issues

    poisoned_erisa = (
        "Calculate Erisa Fidelity premiums, NCCI class code rates, and statutory deadlines "
        "under 40 U.S.C. Section 3131, NCCI manuals, and 50-state construction."
    )
    stale_og = (
        "Deterministic quantitative calculator for erisa fidelity bond coverage amount calculator "
        "under 40 U.S.C. Section 3131 (Miller."
    )
    html_in = (
        "<!doctype html><html><head>"
        "<title>ERISA Section 412 Fidelity Bond Calculator | LienBond</title>"
        f'<meta name="description" content="{poisoned_erisa}">'
        f'<meta property="og:description" content="{stale_og}">'
        f'<meta name="twitter:description" content="{stale_og}">'
        "</head><body><main><h1>ERISA Section 412 Fidelity Bond Calculator</h1></main></body></html>"
    )
    healed_html, changed_1 = maintenance._normalize_page_structure_and_geo_parity(
        html_in,
        property_id="lienbond",
        slug="erisa-fidelity-bond-coverage-amount-calculator",
        topic_label="ERISA Section 412 Fidelity Bond Coverage Amount Calculator",
        canonical_url="https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
        stat_auth="29 U.S.C. Section 1112",
        econ_ds="DOL Form 5500 Series",
    )
    assert changed_1 is True
    md_m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', healed_html)
    og_m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', healed_html)
    tw_m = re.search(r'<meta[^>]+name="twitter:description"[^>]+content="([^"]+)"', healed_html)
    assert md_m and og_m and tw_m
    assert md_m.group(1) == og_m.group(1) == tw_m.group(1)
    assert "29 U.S.C. Section 1112" in md_m.group(1)
    assert "3131" not in md_m.group(1)
    assert "NCCI" not in md_m.group(1)
    assert 120 <= len(md_m.group(1)) <= 155

    # Second pass must leave the healed meta description untouched (idempotent)
    healed_html_2, _ = maintenance._normalize_page_structure_and_geo_parity(
        healed_html,
        property_id="lienbond",
        slug="erisa-fidelity-bond-coverage-amount-calculator",
        topic_label="ERISA Section 412 Fidelity Bond Coverage Amount Calculator",
        canonical_url="https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
        stat_auth="29 U.S.C. Section 1112",
        econ_ds="DOL Form 5500 Series",
    )
    md_m2 = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', healed_html_2)
    assert md_m2 and md_m2.group(1) == md_m.group(1)

    # Direct _normalize_meta_120_155 call must also reject and heal the legacy poisoned string
    direct_healed = _normalize_meta_120_155(
        poisoned_erisa,
        "lienbond",
        "erisa fidelity bond coverage amount calculator",
        slug="erisa-fidelity-bond-coverage-amount-calculator",
    )
    assert direct_healed == md_m.group(1)

    expected_slug_tokens = {
        "bid-bond-calculator": "FAR 28.101",
        "california-texas-florida-preliminary-notice-deadline-calculator": "California 20-day",
        "commercial-construction-retainage-interest-penalty-calculator-by-state": "31 U.S.C. Section 3903",
        "contractor-license-bond-cost-calculator-by-credit-score": "31 CFR Part 223",
        "contractor-lien-release-statutory-matrix-by-state": "50-state statutory mechanics lien waiver",
        "contractor-overhead-and-profit-markup-vs-margin-calculator": "48 CFR Part 31",
        "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator": "40 U.S.C. Section 3141",
        "erisa-fidelity-bond-coverage-amount-calculator": "29 U.S.C. Section 1112",
        "experience-modification-rate-emr-workers-comp-penalty-calculator": "EMR",
        "miller-act-performance-and-payment-bond-premium-calculator": "40 U.S.C. Section 3131",
        "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator": "AIA A312",
        "texas-chapter-53-statutory-retainage-and-fund-trapping-notice-calculator": "Texas Property Code Chapter 53",
        "workers-compensation-class-code-rate-calculator-by-state": "NCCI Basic Manual",
    }
    workers_comp_slugs = {
        "experience-modification-rate-emr-workers-comp-penalty-calculator",
        "workers-compensation-class-code-rate-calculator-by-state",
    }
    seen_descriptions: dict[str, str] = {}
    for slug, required_token in expected_slug_tokens.items():
        desc = _normalize_meta_120_155("", "lienbond", slug.replace("-", " "), slug=slug)
        assert 120 <= len(desc) <= 155, f"{slug} len={len(desc)}: {desc}"
        assert not detect_sentence_truncation_issues(desc), f"{slug} truncated: {desc}"
        assert "\u2014" not in desc and "\u2013" not in desc, f"{slug} forbidden dash: {desc}"
        assert required_token in desc, f"{slug} missing '{required_token}': {desc}"
        if slug not in workers_comp_slugs:
            assert "ncci" not in desc.lower(), f"{slug} leaked NCCI: {desc}"
        if slug != "miller-act-performance-and-payment-bond-premium-calculator":
            assert "3131" not in desc.lower(), f"{slug} leaked 3131: {desc}"
        assert desc not in seen_descriptions, f"Duplicate meta for {slug} and {seen_descriptions[desc]}: {desc}"
        seen_descriptions[desc] = slug


def test_lienbond_poisoned_meta_detector_overlay_and_retrofit_idempotency(tmp_path: Path) -> None:
    """Detector, audit_page, overlay heal detector, and retrofit_estate detect and heal poisoned LienBond metas idempotently."""
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec

    poisoned_erisa_md = (
        "Calculate Erisa Fidelity premiums, NCCI class code rates, and statutory deadlines "
        "under 40 U.S.C. Section 3131, NCCI manuals, and 50-state construction."
    )
    poisoned_miller_md = (
        "Calculate Miller Act premiums, NCCI class code rates, and statutory deadlines "
        "under 40 U.S.C. Section 3131, NCCI manuals, and 50-state construction lien."
    )
    poisoned_wc_md = (
        "Calculate Workers Compensation premiums, NCCI class code rates, and statutory deadlines "
        "under 40 U.S.C. Section 3131, NCCI manuals, and 50-state."
    )

    # 1. Shared helper distinguishes poisoned vs clean across routes and tenants
    assert maintenance._has_lienbond_poisoned_meta(
        poisoned_erisa_md,
        slug_or_url="https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
        canonical_url="https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
    )
    assert maintenance._has_lienbond_poisoned_meta(
        poisoned_wc_md,
        slug_or_url="https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/",
        canonical_url="https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/",
    )
    assert maintenance._has_lienbond_poisoned_meta(
        "Calculate ERISA fidelity bond coverage using NCCI manuals and state rules.",
        slug_or_url="erisa-fidelity-bond-coverage-amount-calculator",
        property_id="lienbond",
    )
    assert not maintenance._has_lienbond_poisoned_meta(
        "Calculate contractor surety bond premiums, NCCI workers comp class code and EMR rates, 50-state mechanics lien deadlines, and WH-347 payroll.",
        slug_or_url="https://lienbond.com/",
        canonical_url="https://lienbond.com/",
    )
    assert not maintenance._has_lienbond_poisoned_meta(
        "Browse all 13 LienBond calculators for contractor license bonds, AIA A312 performance bonds, NCCI workers comp, EMR, ERISA bonds, and state liens.",
        slug_or_url="https://lienbond.com/tools/",
        is_non_tool=True,
        canonical_url="https://lienbond.com/tools/",
    )
    assert not maintenance._has_lienbond_poisoned_meta(
        "Calculate state contractor workers compensation premiums using NCCI Basic Manual class code rates per $100 of payroll, EMR multipliers, and credits.",
        slug_or_url="https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/",
        canonical_url="https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/",
    )
    assert not maintenance._has_lienbond_poisoned_meta(
        "Calculate Miller Act performance and payment bond premiums using SFAA sliding-scale contract rate tiers under 40 U.S.C. Section 3131 and FAR 28.102-2.",
        slug_or_url="https://lienbond.com/tools/miller-act-performance-and-payment-bond-premium-calculator/",
        canonical_url="https://lienbond.com/tools/miller-act-performance-and-payment-bond-premium-calculator/",
    )
    assert not maintenance._has_lienbond_poisoned_meta(
        poisoned_erisa_md,
        slug_or_url="https://prexvo.com/tools/rap-payment-calculator/",
        property_id="prexvo",
        canonical_url="https://prexvo.com/tools/rap-payment-calculator/",
    )

    # 2. Stale overlay detector catches poisoned LienBond overlay JSON and clears healed overlay
    poisoned_ov = {
        "property_id": "lienbond",
        "tenant_id": "lienbond",
        "slug": "erisa-fidelity-bond-coverage-amount-calculator",
        "target_url": "https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
        "query": "erisa fidelity bond coverage amount calculator",
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "ERISA Section 412 Fidelity Bond Calculator | LienBond",
        "meta_description": poisoned_erisa_md,
        "quick_answer": (
            "ERISA Section 412 requires fiduciaries handling qualifying employee benefit plan assets to maintain "
            "a fidelity bond equal to at least 10 percent of funds handled, subject to a $1,000 statutory floor "
            "and a $500,000 standard maximum cap per plan under 29 U.S.C. Section 1112."
        ),
    }
    assert maintenance.RetroReflectionEngine._overlay_spec_needs_heal(
        "erisa-fidelity-bond-coverage-amount-calculator",
        poisoned_ov,
    )
    healed_ov = compile_remediation_overlay_spec(
        {
            "slug": "erisa-fidelity-bond-coverage-amount-calculator",
            "target_url": "https://lienbond.com/tools/erisa-fidelity-bond-coverage-amount-calculator/",
            "query": "erisa fidelity bond coverage amount calculator",
            "position": 12.0,
            "impressions": 50,
        },
        tenant_id="lienbond",
    )
    assert not maintenance.RetroReflectionEngine._overlay_spec_needs_heal(
        "erisa-fidelity-bond-coverage-amount-calculator",
        healed_ov,
    )

    # 3. End-to-end audit_page / audit_estate -> retrofit_estate -> clean second audit_estate pass
    repo_dir = tmp_path / "lienbond"
    compiler.compile_lienbond_estate(repo_dir, run_retrofit=True)
    dist_dir = repo_dir / "dist"
    assert maintenance.RetroReflectionEngine.audit_estate(dist_dir, "lienbond")["stale_count"] == 0

    poison_targets = {
        "erisa-fidelity-bond-coverage-amount-calculator": poisoned_erisa_md,
        "miller-act-performance-and-payment-bond-premium-calculator": poisoned_miller_md,
        "workers-compensation-class-code-rate-calculator-by-state": poisoned_wc_md,
    }
    ov_dir = repo_dir / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    for slug, bad_md in poison_targets.items():
        page_path = dist_dir / "tools" / slug / "index.html"
        html_raw = page_path.read_text(encoding="utf-8")
        poisoned_html = re.sub(
            r'(<meta[^>]+name=["\']description["\'][^>]+content=["\'])([^"\']+)(["\'])',
            lambda m, _v=bad_md: f"{m.group(1)}{_v}{m.group(3)}",
            html_raw,
            count=1,
            flags=re.IGNORECASE,
        )
        poisoned_html = re.sub(
            r'(<meta\b[^>]*(?:property|name)=["\'](?:og|twitter):description["\'][^>]*content=["\'])([^"\']*)(["\'])',
            lambda m, _v=bad_md: f"{m.group(1)}{_v}{m.group(3)}",
            poisoned_html,
            flags=re.IGNORECASE,
        )
        page_path.write_text(poisoned_html, encoding="utf-8")
        assert maintenance._needs_page_structure_geo_normalization(poisoned_html) is True
        missing = maintenance.RetroReflectionEngine.audit_html_mechanics(poisoned_html)
        assert "deterministic_visual_primitives" in missing

        ov_payload = dict(poisoned_ov)
        ov_payload["slug"] = slug
        ov_payload["target_url"] = f"https://lienbond.com/tools/{slug}/"
        ov_payload["query"] = slug.replace("-", " ")
        ov_payload["meta_description"] = bad_md
        (ov_dir / f"{slug}.json").write_text(json.dumps(ov_payload, indent=2), encoding="utf-8")

    audit_before = maintenance.RetroReflectionEngine.audit_estate(dist_dir, "lienbond")
    for slug in poison_targets:
        rel = f"tools/{slug}/index.html"
        assert rel in audit_before["stale_pages"], f"{rel} not detected before retrofit"
    assert "index.html" not in audit_before["stale_pages"]
    assert "tools/index.html" not in audit_before["stale_pages"]

    retrofit_res = maintenance.RetroReflectionEngine.retrofit_estate(
        dist_dir,
        "lienbond",
        canonical_base="https://lienbond.com",
    )
    assert retrofit_res["pages_retrofitted"] >= len(poison_targets)

    for slug in poison_targets:
        healed_html = (dist_dir / "tools" / slug / "index.html").read_text(encoding="utf-8")
        md_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', healed_html, re.I)
        og_m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', healed_html, re.I)
        tw_m = re.search(r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']', healed_html, re.I)
        assert md_m and og_m and tw_m
        healed_md = md_m.group(1)
        assert healed_md == og_m.group(1) == tw_m.group(1)
        assert 120 <= len(healed_md) <= 155
        assert "premiums, ncci class code rates, and statutory deadlines under 40 u.s.c. section 3131" not in healed_md.lower()
        assert maintenance._needs_page_structure_geo_normalization(healed_html) is False
        ov_after = json.loads((ov_dir / f"{slug}.json").read_text(encoding="utf-8"))
        assert ov_after["meta_description"] == healed_md
        assert maintenance.RetroReflectionEngine._overlay_spec_needs_heal(slug, ov_after) is False

    audit_after = maintenance.RetroReflectionEngine.audit_estate(dist_dir, "lienbond")
    assert audit_after["stale_count"] == 0, f"Not idempotent: {audit_after}"
