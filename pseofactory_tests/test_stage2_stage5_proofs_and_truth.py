"""
Targeted tests for:
  - Fix 1: Stage 7 outbound click telemetry sanitization (subid + contract_tier + unapproved partner exclusion)
  - Fix 2: Honest lead-monitor separation of human_leads vs synthetic_probe_leads
  - Fix 3: Honest north-star status/exit code, fail-closed single-property audit --browser,
           and non-destructive supervisor --verify-handoffs default persist=False
  - Fix 4: Stage 2 (earn-proof) and Stage 5 (syndicate-proof) read-only CLI proof commands

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from pseofactory.cli import build_parser, cmd_audit, cmd_earn_proof, cmd_lead_monitor, cmd_north_star, cmd_supervisor, cmd_syndicate_proof
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.partner_tracker import (
    aggregate_verified_outbound_partner_engagement,
    get_lead_monitoring_summary,
)
from pseofactory.seo_growth_loops import evaluate_north_star_targets


def test_verified_outbound_engagement_excludes_test_subids_and_unmonetized_routes(tmp_path: Path) -> None:
    """Fix 1: gh_test_01, native_unmonetized_destination, and unapproved partners drop verified clicks & yield to $0.00."""
    tel_file = tmp_path / "telemetry_events.jsonl"
    events = [
        {
            "event_id": "evt_gh_test",
            "event_type": "affiliate_click",
            "property_id": "gainhelm",
            "partner_key": "cobalt_pentest",
            "tool_slug": "soc-2-audit-cost-calculator",
            "cta_slot": "hero_primary",
            "subid": "gh_test_01",
        },
        {
            "event_id": "evt_gh_unmon",
            "event_type": "affiliate_click",
            "property_id": "gainhelm",
            "partner_key": "vanta_security",
            "tool_slug": "iso-27001-certification-cost-calculator",
            "cta_slot": "partner_matrix_card",
            "subid": "iso-27001-certification-cost-calculator_card_1",
            "contract_tier": "native_unmonetized_destination",
        },
        {
            "event_id": "evt_lb_unmon",
            "event_type": "affiliate_click",
            "property_id": "lienbond",
            "partner_key": "suretybonds_direct",
            "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "cta_slot": "calculator_primary_cta",
            "subid": "contractor-license-bond-cost-calculator-by-credit-score_card_1",
            "contract_tier": "native_unmonetized_destination",
        },
    ]
    tel_file.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

    gh_agg = aggregate_verified_outbound_partner_engagement(tel_file, property_id="gainhelm")
    assert gh_agg["verified_non_probe_outbound_clicks"] == 0
    assert gh_agg["synthetic_probe_clicks_filtered"] == 1
    assert gh_agg["unmonetized_destination_clicks_filtered"] == 1
    assert gh_agg["total_estimated_revenue_yield_usd"] == 0.0

    lb_agg = aggregate_verified_outbound_partner_engagement(tel_file, property_id="lienbond")
    assert lb_agg["verified_non_probe_outbound_clicks"] == 0
    assert lb_agg["unmonetized_destination_clicks_filtered"] == 1
    assert lb_agg["total_estimated_revenue_yield_usd"] == 0.0

    # Real approved live partner click on profithelm with organic subid (including 'penetration-testing' non-probe token) IS counted
    ph_events = [
        {
            "event_id": "evt_ph_real",
            "event_type": "affiliate_click",
            "property_id": "profithelm",
            "partner_key": "mercury",
            "tool_slug": "saas-runway-calculator",
            "cta_slot": "calculator_primary_cta",
            "subid": "saas-runway-calculator_primary_cta",
        },
        {
            "event_id": "evt_ph_test",
            "event_type": "affiliate_click",
            "property_id": "profithelm",
            "partner_key": "mercury",
            "tool_slug": "saas-runway-calculator",
            "cta_slot": "calculator_primary_cta",
            "subid": "smoke_verify_01",
        },
    ]
    ph_agg = aggregate_verified_outbound_partner_engagement(ph_events, property_id="profithelm")
    assert ph_agg["verified_non_probe_outbound_clicks"] == 1
    assert ph_agg["synthetic_probe_clicks_filtered"] == 1
    assert ph_agg["total_estimated_revenue_yield_usd"] > 0.0


def test_lead_monitor_separates_human_leads_from_synthetic_probes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fix 2: synthetic probe leads report human_leads=0, pipeline_usd=$0.00, checkout_offers_usd=$0.00."""
    leads_file = tmp_path / "captured_leads.jsonl"
    leads_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "lead_id": "probe_profithelm_smoke_1",
                        "property_id": "profithelm",
                        "tool_slug": "section-1031-calculator",
                        "email": "smoke@freightfleet-logistics.com",
                        "lead_origin": "internal_probe",
                        "calculated_amount": 450000.0,
                        "offer_price_usd": 79.0,
                        "lifecycle_stage": "fulfilled",
                    }
                ),
                json.dumps(
                    {
                        "lead_id": "lead_profithelm_real_1",
                        "property_id": "profithelm",
                        "tool_slug": "section-179-calculator",
                        "email": "controller@acme-mfg.com",
                        "lead_origin": "organic_user",
                        "calculated_amount": 120000.0,
                        "offer_price_usd": 49.0,
                        "lifecycle_stage": "captured",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Probe-only ledger returns $0.00 human pipeline
    probe_only = tmp_path / "probes_only.jsonl"
    probe_only.write_text(
        json.dumps(
            {
                "lead_id": "probe_ph_1",
                "property_id": "profithelm",
                "email": "test@freightfleet-logistics.com",
                "lead_origin": "internal_probe",
                "calculated_amount": 3351600.0,
                "offer_price_usd": 2005.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    probe_summary = get_lead_monitoring_summary(leads_ledger_path=str(probe_only))
    assert probe_summary["total_leads"] == 1
    assert probe_summary["human_leads"] == 0
    assert probe_summary["synthetic_probe_leads"] == 1
    assert probe_summary["total_pipeline_calculated_usd"] == 0.0
    assert probe_summary["total_checkout_offer_pipeline_usd"] == 0.0
    assert probe_summary["synthetic_probe_pipeline_calculated_usd"] == 3351600.0

    # Mixed ledger only counts the real external human lead in pipeline totals
    mixed_summary = get_lead_monitoring_summary(leads_ledger_path=str(leads_file))
    assert mixed_summary["total_leads"] == 2
    assert mixed_summary["human_leads"] == 1
    assert mixed_summary["synthetic_probe_leads"] == 1
    assert mixed_summary["total_pipeline_calculated_usd"] == 120000.0
    assert mixed_summary["total_checkout_offer_pipeline_usd"] == 49.0

    with patch("pseofactory.partner_tracker.get_lead_monitoring_summary", return_value=probe_summary):
        rc = cmd_lead_monitor(argparse.Namespace(property="all", json=False))
    out = capsys.readouterr().out
    assert rc == 0
    assert "[WARN] Lead Monitor: human_leads=0 | synthetic_probe_leads=1" in out
    assert "pipeline_usd=$0.00" in out
    assert "checkout_offers_usd=$0.00" in out
    assert_no_forbidden_dashes(out, "test_lead_monitor_output")


def test_north_star_audit_browser_and_supervisor_verify_handoffs_fixes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fix 3: north-star reflects target attainment, single-property audit --browser fails closed, supervisor --verify-handoffs defaults persist=False."""
    # 1. evaluate_north_star_targets marks 0-click / 14-impr tenant as FAIL (not PASS)
    repo = tmp_path / "lienbond"
    (repo / "dist").mkdir(parents=True)
    sc = evaluate_north_star_targets(
        property_id="lienbond",
        repo_root=repo,
        dist_dir=repo / "dist",
        consolidated_gsc={"current_rows": [{"query": "surety bond", "impressions": 14, "clicks": 0, "position": 18.0}]},
        daily_records=[],
        persist=False,
    )
    assert sc["status"] == "FAIL"
    assert sc["target_attainment"]["targets_met"] is False

    # cmd_north_star does not hardcode PASS or return 0 when tenant fails
    with patch("pseofactory.seo_growth_loops.evaluate_north_star_targets", return_value=sc):
        rc_ns = cmd_north_star(argparse.Namespace(property="lienbond", dry_run=True, json=True))
    out_ns = json.loads(capsys.readouterr().out)
    assert rc_ns == 1
    assert out_ns["status"] == "FAIL"

    # 2. Single-property audit --browser fails closed on SKIPPED_CDP_OFFLINE
    import pseofactory.browser_verifier as bv_mod

    class _OfflineAuditor:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def run_audit(self, sample_size: Any = None) -> Dict[str, Any]:
            return {"status": "SKIPPED_CDP_OFFLINE", "passed": False, "routes_audited": 0, "failed_count": 0, "findings": []}

    monkeypatch.setattr(bv_mod, "UnifiedBrowserAuditor", _OfflineAuditor)
    rc_aud = cmd_audit(
        argparse.Namespace(
            property="profithelm",
            browser=True,
            dist_dir=str(repo / "dist"),
            json=True,
        )
    )
    capsys.readouterr()
    assert rc_aud == 1

    # 3. supervisor --verify-handoffs defaults persist=False unless --persist is passed
    import pseofactory.supervisor as sup_mod

    seen_persist: List[bool] = []

    def _fake_verify(**kwargs: Any) -> Dict[str, Any]:
        seen_persist.append(bool(kwargs.get("persist")))
        return {
            "status": "PASS",
            "stages_passed": 6,
            "stages_total": 6,
            "tenants_verified": ["profithelm"],
            "failing_stages_count": 0,
            "stages": {},
            "failures": [],
        }

    monkeypatch.setattr(sup_mod, "verify_department_handoff_chain", _fake_verify)
    parser = build_parser()
    args_default = parser.parse_args(["supervisor", "--verify-handoffs", "--json"])
    assert cmd_supervisor(args_default) == 0
    capsys.readouterr()
    args_persist = parser.parse_args(["supervisor", "--verify-handoffs", "--persist", "--json"])
    assert cmd_supervisor(args_persist) == 0
    capsys.readouterr()
    assert seen_persist == [False, True]


def test_earn_proof_and_syndicate_proof_cli_fail_closed_and_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fix 4: earn-proof and syndicate-proof run read-only and fail closed on real Stage 2 / Stage 5 gaps."""
    ws = tmp_path / "workspace"
    tenant_dir = ws / "acme"
    (tenant_dir / "dist").mkdir(parents=True)
    (tenant_dir / ".pseofactory.json").write_text(
        json.dumps({"property_id": "acme", "domain": "acme.com", "canonical_base": "https://acme.com", "dist_dir": "dist"}),
        encoding="utf-8",
    )
    (tenant_dir / "dist" / ("a" * 32 + ".txt")).write_text("a" * 32, encoding="utf-8")

    agy = ws / "pseofactory" / ".agy"
    agy.mkdir(parents=True)
    (agy / "partner_earnings_ledger.json").write_text(
        json.dumps(
            {
                "synced_at": "2026-11-28T06:00:00+00:00",
                "live_polled_portals_count": 1,
                "uncollected_portals_count": 1,
                "cashflow_summary": {"realized_commission_usd": 0.0, "modeled_epc_pipeline_usd": 0.0},
                "portals": {"coinledger": {"auth_status": "SESSION_EXPIRED_CACHED_SNAPSHOT", "is_authenticated_and_syncing": False}},
            }
        ),
        encoding="utf-8",
    )
    (agy / "captured_leads.jsonl").write_text(
        json.dumps({"lead_id": "probe_acme_1", "property_id": "acme", "email": "smoke@acme.com", "lead_origin": "internal_probe"}) + "\n",
        encoding="utf-8",
    )
    (agy / "portfolio_revenue_truth.json").write_text(
        json.dumps({"generated_at": "2020-01-01T00:00:00Z", "portfolio_bottom_line": {"pseofactory_realized_revenue_usd": 0.0, "gross_realized_revenue_usd": 0.0}}),
        encoding="utf-8",
    )

    tdb = ws / "pseofactory" / "pseofactory" / "trends" / "data" / "trend_history.db"
    tdb.parent.mkdir(parents=True)
    conn = sqlite3.connect(tdb)
    conn.execute(
        "CREATE TABLE gsc_url_inspection_states (property_id TEXT, page_url TEXT, verdict TEXT, coverage_state TEXT, recorded_at TEXT)"
    )
    for i in range(10):
        conn.execute(
            "INSERT INTO gsc_url_inspection_states VALUES (?, ?, ?, ?, ?)",
            ("acme", f"https://acme.com/tools/t{i}/", "NEUTRAL" if i < 9 else "PASS", "Discovered - currently not indexed" if i < 9 else "Submitted and indexed", "2026-11-27T00:00:00Z"),
        )
    conn.commit()
    conn.close()

    aio_db = ws / ".agy" / "runs" / "aio_observatory.db"
    aio_db.parent.mkdir(parents=True)
    aconn = sqlite3.connect(aio_db)
    aconn.execute(
        "CREATE TABLE aio_snapshots (snapshot_id TEXT, tenant TEXT, query TEXT, sampled_at TEXT, found INTEGER, answer TEXT, citations TEXT, provider TEXT, cost_usd REAL, error TEXT, intent TEXT)"
    )
    aconn.commit()
    aconn.close()

    class _PassCommerce:
        passed = True
        status = "PASS"
        issues: List[str] = []

    with (
        patch("pseofactory.commerce_gate.audit_tenant_commerce_fail_closed", return_value=_PassCommerce()),
        patch("pseofactory.cli._resolve_trend_db_path", return_value=tdb),
    ):
        rc_earn = cmd_earn_proof(
            argparse.Namespace(property="all", max_age_hours=72.0, workspace_root=str(ws), skip_live=True, json=True)
        )
        earn_out = json.loads(capsys.readouterr().out)
        assert rc_earn == 1
        assert earn_out["status"] == "FAIL"
        assert earn_out["leads_health"]["human_leads"] == 0
        assert earn_out["leads_health"]["synthetic_probe_leads"] == 1
        assert any("approved affiliate partners" in f for f in earn_out["failures"])
        assert any("real external human leads" in f for f in earn_out["failures"])
        assert any("stale" in f for f in earn_out["failures"])

        monkeypatch.delenv("PSEUFACTORY_ENABLE_YOUTUBE_UPLOAD", raising=False)
        rc_syn = cmd_syndicate_proof(
            argparse.Namespace(property="all", max_age_days=7, min_indexed_pct=50.0, workspace_root=str(ws), skip_live=True, json=True)
        )
        syn_out = json.loads(capsys.readouterr().out)
        assert rc_syn == 1
        assert syn_out["status"] == "FAIL"
        assert syn_out["properties"]["acme"]["gsc_indexation"]["indexed_count"] == 1
        assert syn_out["properties"]["acme"]["gsc_indexation"]["total_inspected"] == 10
        assert any("GSC indexation ratio critically low" in f for f in syn_out["failures"])
        assert any("parasite-ledger" in f for f in syn_out["failures"])
        assert any("YouTube uploads disabled" in f for f in syn_out["failures"])
