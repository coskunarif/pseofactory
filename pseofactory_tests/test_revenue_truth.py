"""
Tests for Portfolio Revenue and Attribution Truth Board (pseofactory/revenue_truth.py)
and property-scoped edge telemetry filtering (pseofactory/edge.py).
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pseofactory.cli import main as cli_main
from pseofactory.edge import generate_edge_telemetry_function
from pseofactory.revenue_truth import (
    build_portfolio_revenue_truth_report,
    classify_captured_lead,
    classify_telemetry_event,
    collect_local_arbitrage_truth,
    collect_solana_copy_trader_truth,
    format_portfolio_revenue_truth_table,
)
from pseofactory.contracts import assert_no_forbidden_dashes


def test_classify_captured_lead_separates_human_test_and_probe() -> None:
    assert (
        classify_captured_lead(
            {
                "lead_id": "probe_1776296993663_abc",
                "email_masked": "c***@gmail.com",
                "lead_origin": "internal_probe",
            }
        )
        == "synthetic_probe"
    )
    assert (
        classify_captured_lead(
            {
                "lead_id": "lead_1775869784391_xyz",
                "email_masked": "a***@profithelm.com",
                "lead_origin": "organic_user",
            }
        )
        == "internal_operator_test"
    )
    assert (
        classify_captured_lead(
            {
                "lead_id": "lead_1775938559568_ext",
                "email_masked": "c***@gmail.com",
                "lead_origin": "organic_user",
                "tool_slug": "irs-2027-tax-brackets-alaska",
            }
        )
        == "external_human"
    )


def test_classify_telemetry_event_detects_cross_tenant_and_synthetic() -> None:
    assert (
        classify_telemetry_event(
            {"event_id": "evt_1", "property_id": "gainhelm", "event": "affiliate_click"},
            expected_property_id="lienbond",
        )
        == "cross_tenant_bleed"
    )
    assert (
        classify_telemetry_event(
            {
                "event_id": "evt_2",
                "property_id": "profithelm",
                "event": "affiliate_click",
                "subid": "smoke_verify_1",
            },
            expected_property_id="profithelm",
        )
        == "synthetic_probe"
    )
    assert (
        classify_telemetry_event(
            {
                "event_id": "evt_3",
                "property_id": "profithelm",
                "event": "affiliate_click",
                "subid": "section-179-calculator_hero",
            },
            expected_property_id="profithelm",
        )
        == "organic_candidate"
    )


def test_collect_local_arbitrage_truth_deduplicates_settlement_and_excludes_fixtures(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "arbitrage.db"
    con = sqlite3.connect(str(db_file))
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE catalog_settlement_ledger (
            ledger_id TEXT PRIMARY KEY,
            product_id TEXT,
            sku_code TEXT,
            venue TEXT,
            event_type TEXT,
            sale_amount_cents INTEGER,
            buyer_handle TEXT,
            settled_at TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO catalog_settlement_ledger VALUES
        ('led_1', 'prod_ou_desk_zinus55', 'OU-DESK-ZINUS55', 'offerup', 'SOLD_SETTLED', 3500, 'MarcusOU', '2026-10-29T18:10:00Z'),
        ('led_2', 'prod_ou_desk_zinus55', 'OU-DESK-ZINUS55', 'offerup', 'SOLD_SETTLED', 3250, 'MarcusOU', '2026-10-30T14:22:18Z')
        """
    )
    cur.execute(
        """
        CREATE TABLE listing_drafts (
            sku_code TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            ask_price_cents INTEGER,
            floor_price_cents INTEGER
        )
        """
    )
    cur.execute(
        """
        INSERT INTO listing_drafts VALUES
        ('SKU-1', 'Ride1Up Portola', 'ACTIVE', 99500, 95000),
        ('OU-DESK-ZINUS55', 'Zinus Desk', 'SOLD', 3500, 3000)
        """
    )
    cur.execute(
        """
        CREATE TABLE buyer_conversations (
            conversation_id TEXT PRIMARY KEY,
            sku_code TEXT,
            venue TEXT,
            buyer_handle TEXT,
            state TEXT,
            agreed_price_cents INTEGER,
            last_offer_cents INTEGER,
            qualification_reason TEXT,
            turn_count INTEGER,
            updated_at TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO buyer_conversations VALUES
        ('c_fix', 'SKU-1', 'facebook', 'FixtureUser', 'HOLD_PENDING', 95000, 95000, 'SEEDED_TEST_FIXTURE', 3, '2026-10-01T00:00:00Z'),
        ('c_real_1', 'SKU-1', 'facebook', 'DevonFB', 'HOLD_PENDING', 20500, 20500, 'VALID_PICKUP_AND_CASH_INTENT', 3, '2026-10-30T00:00:00Z'),
        ('c_real_2', 'SKU-1', 'facebook', 'Andy Mariano Primo', 'QUALIFIED', NULL, NULL, 'LIVE_DOM_SYNC_ACTIVE_THREAD', 9, '2026-11-09T00:50:06Z')
        """
    )
    con.commit()
    con.close()

    res = collect_local_arbitrage_truth(db_path=db_file)
    assert res["deduplicated_realized_revenue_usd"] == 35.0
    assert res["raw_settlement_rows_sum_usd"] == 67.5
    assert res["unique_items_sold_count"] == 1
    assert len(res["duplicate_settlement_rows_excluded"]) == 1
    assert res["active_inventory_count"] == 1
    assert res["active_inventory_ask_usd"] == 995.0
    assert res["real_live_conversations_count"] == 2
    assert res["seeded_test_fixture_conversations_count"] == 1
    assert res["active_hold_pending_offers_usd"] == 205.0


def test_collect_solana_copy_trader_truth_computes_pnl_and_win_rate(tmp_path: Path) -> None:
    db_file = tmp_path / "trades.db"
    con = sqlite3.connect(str(db_file))
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE positions (
            id TEXT PRIMARY KEY,
            status TEXT,
            investedSol REAL,
            recoveredSol REAL
        )
        """
    )
    cur.execute(
        """
        INSERT INTO positions VALUES
        ('p1', 'CLOSED', 0.10, 0.15),
        ('p2', 'CLOSED', 0.10, 0.02),
        ('p3', 'OPEN', 0.05, 0.00)
        """
    )
    cur.execute(
        """
        CREATE TABLE ledger_runtime_context (
            Id INTEGER PRIMARY KEY,
            WalletBalanceSol REAL,
            RuntimeState TEXT,
            HaltReason TEXT,
            UpdatedAt TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO ledger_runtime_context VALUES
        (1, 0.53414, 'DEFENSIVE_HALT', 'DAILY_HARD_STOP_REACHED', '2026-11-08T00:00:00Z')
        """
    )
    con.commit()
    con.close()

    sol = collect_solana_copy_trader_truth(
        trades_db_path=db_file,
        sol_price_usd=100.0,
        live_network=False,
    )
    assert sol["closed_positions_count"] == 2
    assert sol["open_positions_count"] == 1
    assert sol["wins_count"] == 1
    assert sol["losses_count"] == 1
    assert sol["win_rate_pct"] == 50.0
    assert sol["realized_pnl_sol"] == -0.03
    assert sol["realized_pnl_usd"] == -3.0
    assert sol["live_wallet_balance_sol"] == 0.53414
    assert sol["runtime_state"] == "DEFENSIVE_HALT"


def test_edge_telemetry_function_filters_cross_tenant_events() -> None:
    js_src = generate_edge_telemetry_function("lienbond")
    assert 'url.searchParams.get("property_id") || "lienbond"' in js_src
    assert "matchesProperty" in js_src
    assert "HeadlessChrome" in js_src
    assert_no_forbidden_dashes(js_src, "test_edge_telemetry_function")


def test_cli_revenue_truth_offline_json_and_table(capsys) -> None:
    rc = cli_main(["revenue-truth", "--offline", "--no-persist", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["question"] == "Does it make money?"
    assert "portfolio_bottom_line" in parsed
    assert "pseofactory" in parsed["engines"]
    assert "local_marketplace_arbitrage" in parsed["engines"]
    assert "solana_copy_trader" in parsed["engines"]

    table_str = format_portfolio_revenue_truth_table(parsed)
    assert "PORTFOLIO REVENUE & ATTRIBUTION TRUTH BOARD" in table_str
    assert_no_forbidden_dashes(table_str, "test_cli_revenue_truth_table")


def test_collect_pseofactory_truth_merges_local_captured_leads_ledger_and_lienbond_summary(
    tmp_path: Path,
) -> None:
    from pseofactory.partner_tracker import get_lead_monitoring_summary
    from pseofactory.revenue_truth import collect_pseofactory_truth

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    leads_file = agy_dir / "captured_leads.jsonl"
    sample_leads = [
        {
            "lead_id": "lead_profithelm_real_1",
            "property_id": "profithelm",
            "tool_slug": "irs-2027-tax-brackets-alaska",
            "email": "c***@gmail.com",
            "captured_at": "2026-10-26T09:29:08.795Z",
            "lead_origin": "real",
            "stripe_payment_verified": False,
        },
        {
            "lead_id": "lead_profithelm_test_1",
            "property_id": "profithelm",
            "tool_slug": "section-1031-calculator",
            "email": "a***@profithelm.com",
            "captured_at": "2026-10-23T09:46:48.305Z",
            "lead_origin": "organic_user",
            "stripe_payment_verified": False,
        },
        {
            "lead_id": "probe_prexvo_1",
            "property_id": "prexvo",
            "tool_slug": "student-loan-refinance-break-even-calculator",
            "email": "a***@medcenter-cohort.org",
            "captured_at": "2026-10-22T18:58:24.170Z",
            "lead_origin": "internal_probe",
            "stripe_payment_verified": False,
        },
    ]
    leads_file.write_text(
        "\n".join(json.dumps(r) for r in sample_leads) + "\n",
        encoding="utf-8",
    )

    pseo = collect_pseofactory_truth(package_root=tmp_path, live_network=False)
    lc = pseo["lead_capture_totals"]
    assert lc["external_human_leads"] == 1
    assert lc["internal_operator_test_leads"] == 1
    assert lc["synthetic_probe_leads"] == 1
    assert len(lc["external_human_lead_records"]) == 1
    ext_rec = lc["external_human_lead_records"][0]
    assert ext_rec["lead_id"] == "lead_profithelm_real_1"
    assert ext_rec["email_masked"] == "c***@gmail.com"
    assert ext_rec["created_at"] == "2026-10-26T09:29:08.795Z"
    assert pseo["properties"]["profithelm"]["lead_capture"]["total_records"] == 2
    assert pseo["properties"]["prexvo"]["lead_capture"]["total_records"] == 1
    assert pseo["properties"]["lienbond"]["lead_capture"]["total_records"] == 0

    mon = get_lead_monitoring_summary(
        leads_ledger_path=str(leads_file),
        verify_live_providers=False,
    )
    assert "lienbond" in mon["by_property"]
    assert mon["by_property"]["lienbond"] == 0
    assert mon["by_property"]["profithelm"] == 2
    assert mon["by_property"]["prexvo"] == 1

    from pseofactory.competitor import run_agentic_free_tool_keyword_pipeline

    lb_pipeline = run_agentic_free_tool_keyword_pipeline(
        tenant_id="lienbond",
        repo_root=tmp_path,
    )
    assert lb_pipeline["status"] == "PASS"
    assert lb_pipeline["property_id"] == "lienbond"
    assert len(lb_pipeline["ranked_clusters"]) >= 3


