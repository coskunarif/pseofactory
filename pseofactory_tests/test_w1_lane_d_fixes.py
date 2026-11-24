"""
Regression tests for Wave 1 Lane D fixes:
- Item 17: revenue_truth.py verified Stripe & $299 partner-slot revenue, table strings, no 6->37 rewrite, dynamic tenants
- Item 18: partner_tracker.py FirstPromoter V2 session header/cookie attachment
- Item 19: email_ingest.py FirstPromoter sender classification (CoinLedger, alerts, future partners)
- Item 20: affiliates.py + partner_tracker.py LienBond parity across coverage, edge click recon, playbooks, cluster gaps, telemetry/scenarios
- Item 21: affiliates_hub.py + partner_tracker.py PartnerStack pending rewards separated from realized revenue

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pseofactory.affiliates import LIENBOND_AFFILIATES, audit_partnership_model_coverage
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.email_ingest import EmailIngestionEngine, EmailMessage
from pseofactory.partner_tracker import (
    HumanActionBus,
    PartnerTrackingEngine,
    compute_scenario_demand_and_conversion_metrics,
    resolve_candidate_realized_revenue_signal,
)
from pseofactory.revenue_truth import (
    build_portfolio_revenue_truth_report,
    collect_pseofactory_truth,
    format_portfolio_revenue_truth_table,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Length": str(len(self._body))}

    def read(self, n: int = -1) -> bytes:
        return self._body if n is None or n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_item_17_revenue_truth_realized_stripe_slots_no_6_to_37_and_dynamic_tenants(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "ws"
    pkg_root = ws / "pseofactory"
    agy_dir = pkg_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    # Create 4 canonical + 1 dynamic 5th tenant marker
    for tid, folder, domain in (
        ("profithelm", "profithelm-platform", "profithelm.com"),
        ("prexvo", "prexvo", "prexvo.com"),
        ("gainhelm", "gainhelm", "gainhelm.com"),
        ("lienbond", "lienbond", "lienbond.com"),
        ("fleetforge", "fleetforge", "fleetforge.com"),
    ):
        tdir = ws / folder
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / ".pseofactory.json").write_text(
            json.dumps({"property_id": tid, "domain": domain, "canonical_base": f"https://{domain}"}),
            encoding="utf-8",
        )

    # CoinLedger cached clicks=6 must NOT be rewritten to 37
    (agy_dir / "partner_earnings_ledger.json").write_text(
        json.dumps(
            {
                "portals": {
                    "firstpromoter_coinledger": {
                        "portal_verified_clicks": 6,
                        "conversions_count": 0,
                        "realized_commission_usd": 12.5,
                        "pending_commission_usd": 0.0,
                        "live_api_polled_in_current_run": False,
                        "auth_status": "SESSION_EXPIRED_CACHED_SNAPSHOT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    leads = [
        # Verified standard Stripe checkout ($79)
        {
            "lead_id": "lead_gh_paid_1",
            "property_id": "gainhelm",
            "tool_slug": "soc-2-audit-cost-calculator",
            "email_masked": "buyer1@acme-corp.com",
            "offer_sku": "gh_soc2_cmmc_audit_workpapers",
            "offer_price_usd": 79.0,
            "attributed_revenue_usd": 79.0,
            "stripe_payment_verified": True,
            "stripe_payment_status": "paid",
            "stripe_checkout_session_id": "cs_live_testpaid001",
            "captured_at": "2026-11-01T10:00:00Z",
        },
        # Verified $299 partner slot checkout
        {
            "lead_id": "lead_lb_slot_1",
            "property_id": "lienbond",
            "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "email_masked": "partner@surety-co.com",
            "offer_sku": "lb_verified_partner_slot",
            "offer_price_usd": 299.0,
            "attributed_revenue_usd": 299.0,
            "stripe_payment_verified": True,
            "stripe_payment_status": "paid",
            "stripe_checkout_session_id": "cs_live_testslot299",
            "captured_at": "2026-11-01T11:00:00Z",
        },
        # Unverified edge session must NOT count as realized Stripe revenue
        {
            "lead_id": "lead_ph_unpaid_1",
            "property_id": "profithelm",
            "tool_slug": "section-1031-calculator",
            "email_masked": "visitor@acme-corp.com",
            "offer_sku": "ph_1031_boot_replacement_workpapers",
            "offer_price_usd": 79.0,
            "attributed_revenue_usd": 79.0,
            "stripe_payment_verified": False,
            "stripe_payment_status": "unpaid",
            "stripe_checkout_session_id": "cs_edge_fake123",
            "captured_at": "2026-11-01T12:00:00Z",
        },
    ]
    (agy_dir / "captured_leads.jsonl").write_text(
        "\n".join(json.dumps(r) for r in leads) + "\n",
        encoding="utf-8",
    )

    pseo = collect_pseofactory_truth(package_root=pkg_root, live_network=False)
    assert pseo["affiliate_networks"]["firstpromoter_coinledger"]["clicks"] == 6
    assert pseo["realized_stripe_revenue_usd"] == pytest.approx(79.0)
    assert pseo["realized_partner_slot_revenue_usd"] == pytest.approx(299.0)
    assert pseo["realized_affiliate_revenue_usd"] == pytest.approx(12.5)
    assert pseo["total_realized_revenue_usd"] == pytest.approx(390.5)
    assert pseo["lead_capture_totals"]["stripe_paid_checkouts"] == 2
    assert "fleetforge" in pseo["properties"]
    assert pseo["properties"]["fleetforge"]["domain"] == "fleetforge.com"

    report = build_portfolio_revenue_truth_report(
        live_network=False,
        persist=False,
        package_root=pkg_root,
        arbitrage_db_path=tmp_path / "missing_arb.db",
        solana_trades_db_path=tmp_path / "missing_sol.db",
    )
    table = format_portfolio_revenue_truth_table(report)
    assert "pseofactory (5 domains):" in table
    assert "Stripe: $79.00 | Affiliates: $12.50 | $299 Slots: $299.00" in table
    assert_no_forbidden_dashes(table, "test_item_17_table")


def test_item_18_firstpromoter_v2_attaches_session_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cl_session_val = "fprom_cl_session_fixture_xyz"
    xn_cookie_val = "_fprom_session=fprom_xn_cookie_fixture_abc"
    monkeypatch.setenv("FIRSTPROMOTER_COINLEDGER_SESSION", cl_session_val)
    monkeypatch.setenv("FIRSTPROMOTER_XENDOO_SESSION", xn_cookie_val)
    monkeypatch.setenv("PSEUFACTORY_LIVE_NETWORK", "1")
    monkeypatch.delenv("PARTNERSTACK_API_KEY", raising=False)
    monkeypatch.delenv("IMPACT_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("IMPACT_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CJ_PERSONAL_ACCESS_TOKEN", raising=False)

    captured_requests: list[tuple[str, dict[str, str]]] = []

    def _fake_urlopen(req, timeout=8.0):
        url = req.full_url
        hdrs = {k.lower(): v for k, v in req.header_items()}
        captured_requests.append((url, hdrs))
        if "api.fprom.io/api/affiliate/v1/me" in url:
            host = hdrs.get("company_host", "")
            if host == "affiliates.coinledger.io":
                assert cl_session_val in hdrs.get("cookie", "")
                assert hdrs.get("authorization") == f"Bearer {cl_session_val}"
                return _FakeHTTPResponse(
                    {"promoter": {"stats": {"clicks_count": 42, "referrals_count": 3, "customers_count": 1}}}
                )
            if host == "xendoo.firstpromoter.com":
                assert hdrs.get("cookie") == xn_cookie_val
                return _FakeHTTPResponse(
                    {"promoter": {"stats": {"clicks_count": 9, "referrals_count": 2, "sales_count": 1}}}
                )
        raise RuntimeError(f"unexpected url: {url}")

    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))
    tracker = PartnerTrackingEngine(hub=MonetizationHub(), email_engine=email_engine, action_bus=bus)

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        ledger = tracker.sync_partner_earnings_and_balances(
            ledger_path=str(tmp_path / "ledger.json"),
            fetch_live_api=True,
            persist=False,
        )

    assert len(captured_requests) == 2
    cl_state = ledger["portals"]["firstpromoter_coinledger"]
    assert cl_state["live_api_polled_in_current_run"] is True
    assert cl_state["auth_status"] == "AUTHENTICATED_SYNCING"
    assert cl_state["portal_verified_clicks"] == 42
    assert cl_state["qualified_leads_count"] == 3
    assert cl_state["conversions_count"] == 1

    xn_state = ledger["portals"]["firstpromoter_xendoo"]
    assert xn_state["live_api_polled_in_current_run"] is True
    assert xn_state["portal_verified_clicks"] == 9

    serialized = json.dumps(ledger)
    assert cl_session_val not in serialized
    assert xn_cookie_val not in serialized


def test_item_19_email_ingest_firstpromoter_routing(tmp_path: Path) -> None:
    engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    msgs = [
        EmailMessage(
            id="fp_cl_welcome",
            message_id="<fp1@firstpromoter.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-10T10:00:00Z",
            subject="Welcome to CoinLedger Affiliate Program!",
            sender_name="CoinLedger",
            sender_email="promoter@firstpromoter.com",
            body_snippet="Welcome to CoinLedger! Your referral link is https://coinledger.io/?fpr=arif-554004",
        ),
        EmailMessage(
            id="fp_cl_comm",
            message_id="<fp2@firstpromoter.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-11T10:00:00Z",
            subject="You earned a commission on CoinLedger",
            sender_name="CoinLedger",
            sender_email="promoter@firstpromoter.com",
            body_snippet="You earned a commission of $22.50 USD from CoinLedger.",
        ),
        EmailMessage(
            id="fp_future_partner",
            message_id="<fp3@firstpromoter.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-12T10:00:00Z",
            subject="Welcome to AcmeSaaS Affiliate Program!",
            sender_name="AcmeSaaS",
            sender_email="promoter@firstpromoter.com",
            body_snippet="Welcome to AcmeSaaS! Your FirstPromoter portal is ready.",
        ),
        EmailMessage(
            id="fp_xendoo_welcome",
            message_id="<fp4@firstpromoter.com>",
            account="zoho",
            mailbox="Newsletter",
            date="2026-10-17T02:51:53-07:00",
            subject="Welcome to Xendoo Referral Partner Program!",
            sender_name="Xendoo Referral Partner Program",
            sender_email="promoter@firstpromoter.com",
            body_snippet="Welcome to Xendoo Referral Partner Program! https://www.xendoo.com/?fp_ref=arif-4ac24e",
        ),
    ]
    cls_map = {c.email_id: c for c in engine.classify_partner_emails(msgs)}

    assert cls_map["fp_cl_welcome"].partner_key == "coinledger"
    assert cls_map["fp_cl_welcome"].property_id == "profithelm"
    assert cls_map["fp_cl_welcome"].classification_type == "APPLICATION_APPROVED"

    assert cls_map["fp_cl_comm"].partner_key == "coinledger"
    assert cls_map["fp_cl_comm"].classification_type == "COMMISSION_EARNED"
    assert cls_map["fp_cl_comm"].commission_amount_usd == pytest.approx(22.50)

    if "fp_future_partner" in cls_map:
        assert cls_map["fp_future_partner"].partner_key != "xendoo"

    assert cls_map["fp_xendoo_welcome"].partner_key == "xendoo"
    assert cls_map["fp_xendoo_welcome"].classification_type == "APPLICATION_APPROVED"


def test_item_20_lienbond_parity_across_coverage_recon_playbooks_gaps_and_telemetry(
    tmp_path: Path,
) -> None:
    # 1. affiliates.audit_partnership_model_coverage(property_id="lienbond")
    lb_cov = audit_partnership_model_coverage(property_id="lienbond")
    assert lb_cov["status"] == "PASS"
    assert lb_cov["verticals_audited_count"] == 3
    for v_fam, v_data in lb_cov["vertical_coverage"].items():
        assert v_data["property_id"] == "lienbond"
        assert v_data["primary_partner"] in LIENBOND_AFFILIATES, f"{v_fam} bound non-LienBond partner"

    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))
    tracker = PartnerTrackingEngine(hub=MonetizationHub(), email_engine=email_engine, action_bus=bus)

    # 2. reconcile_edge_clicks_with_portals includes lienbond
    ledger_dir = tmp_path / "tel_ledgers"
    sync_res = tracker.sync_edge_click_telemetry(
        injected_events={
            "lienbond": [
                {
                    "event_id": "evt_lb_1",
                    "event_type": "affiliate_click",
                    "event": "affiliate_click",
                    "property_id": "lienbond",
                    "partner_key": "simply_business",
                    "tool_slug": "workers-compensation-class-code-rate-calculator-by-state",
                    "cta_slot": "calculator_primary_cta",
                    "subid": "wc_hero",
                    "timestamp": "2026-11-06T10:00:00.000Z",
                }
            ]
        },
        ledger_dir=ledger_dir,
    )
    recon = tracker.reconcile_edge_clicks_with_portals(
        engagement_by_property={"lienbond": sync_res["lienbond"]["aggregation"]}
    )
    assert "lienbond" in recon["properties"]
    assert recon["properties"]["lienbond"]["total_edge_outbound_clicks"] == 1

    # 3. ingest_playbook_subscription for lienbond/general must NOT fall back to profithelm/turbotax/section-1031
    pb = tracker.ingest_playbook_subscription(
        property_id="lienbond",
        tool_slug="general",
        email="contractor@acme-builders.com",
        calculated_amount=120000.0,
        leads_ledger_path=str(tmp_path / "leads.jsonl"),
        auto_dispatch_email=False,
    )
    assert pb["property_id"] == "lienbond"
    assert pb["partner_key"] in LIENBOND_AFFILIATES
    assert pb["partner_key"] != "turbotax"
    assert pb["offer_sku"].startswith("lb_")

    # 4. analyze_cluster_monetization_gaps includes lienbond with 0 uncovered
    gaps = tracker.analyze_cluster_monetization_gaps()
    assert "lienbond" in gaps["properties"]
    assert gaps["properties"]["lienbond"]["clusters_count"] >= 3
    assert gaps["properties"]["lienbond"]["uncovered_count"] == 0

    # 5. compute_scenario_demand_and_conversion_metrics + resolve_candidate_realized_revenue_signal
    lb_ledger = tmp_path / "lb_verified_leads.jsonl"
    lb_row = {
        "lead_id": "lead_lienbond_verified_1",
        "property_id": "lienbond",
        "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
        "email": "contractor@acme-builders.com",
        "lead_type": "playbook_subscription",
        "lifecycle_stage": "fulfilled",
        "offer_sku": "lb_surety_bond_underwriting_kit",
        "offer_price_usd": 49.0,
        "settlement_status": "settled",
        "stripe_payment_verified": True,
        "stripe_payment_status": "paid",
        "stripe_checkout_session_id": "cs_live_LBFIX1",
        "attributed_revenue_usd": 49.0,
        "net_settled_revenue_usd": 47.28,
        "captured_at": "2026-11-05T00:00:00Z",
    }
    lb_ledger.write_text(json.dumps(lb_row) + "\n", encoding="utf-8")

    polled_urls: list[str] = []

    def _fake_tel_urlopen(req, timeout=5):
        polled_urls.append(req.full_url)
        return _FakeHTTPResponse(
            {"summary": {"by_source": {"miller-act-performance-and-payment-bond-premium-calculator": 4}}}
        )

    with patch("urllib.request.urlopen", side_effect=_fake_tel_urlopen):
        scen = compute_scenario_demand_and_conversion_metrics(
            property_id="lienbond",
            leads_ledger_path=lb_ledger,
            include_live_edge_telemetry=True,
        )
    assert any("lienbond.com/api/telemetry" in u for u in polled_urls)
    assert scen["fleet_conversion_totals"]["total_attributed_revenue_usd"] == pytest.approx(49.0)
    assert all(m["property_id"] == "lienbond" for m in scen["per_calculator_metrics"])
    assert all(
        m["scenario_id"].startswith("lienbond_") for m in scen["per_calculator_metrics"]
    )

    sig = resolve_candidate_realized_revenue_signal(
        "lienbond",
        "texas-contractor-license-surety-bond-cost-calculator",
        leads_ledger_path=lb_ledger,
    )
    assert sig["property_id"] == "lienbond"
    assert sig["scenario_id"] == "lienbond_surety_miller_act_underwriting"
    assert sig["realized_calculator_revenue_usd"] >= 49.0
    assert sig["revenue_priority_bonus"] > 0.0


def test_item_21_partnerstack_pending_rewards_excluded_from_realized_revenue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PARTNERSTACK_API_KEY", "test_ps_key_123")
    monkeypatch.setenv("PSEUFACTORY_LIVE_NETWORK", "1")
    monkeypatch.delenv("FIRSTPROMOTER_COINLEDGER_SESSION", raising=False)
    monkeypatch.delenv("FIRSTPROMOTER_XENDOO_SESSION", raising=False)
    monkeypatch.delenv("IMPACT_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("IMPACT_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CJ_PERSONAL_ACCESS_TOKEN", raising=False)

    def _fake_urlopen(req, timeout=8.0):
        url = req.full_url
        if "api.partnerstack.com/api/v2/partnerships" in url:
            return _FakeHTTPResponse({"data": {"items": []}})
        if "api.partnerstack.com/api/v2/rewards" in url:
            return _FakeHTTPResponse(
                {
                    "data": {
                        "items": [
                            {"amount": 10000, "status": "approved"},
                            {"amount": 5000, "status": "paid"},
                            {"amount": 25000, "status": "pending"},
                        ]
                    }
                }
            )
        if "api.partnerstack.com/api/v2/payouts" in url:
            return _FakeHTTPResponse({"data": {"items": []}})
        if "api.partnerstack.com/api/v2/actions" in url:
            return _FakeHTTPResponse({"data": {"items": []}})
        raise RuntimeError(f"unexpected url: {url}")

    hub = MonetizationHub()
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        live_res = hub.reconcile_live_networks(live_network=True, save=False)

    ps = live_res["partnerstack"]
    assert ps["total_revenue_usd"] == pytest.approx(150.0)
    assert ps["pending_revenue_usd"] == pytest.approx(250.0)

    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))
    tracker = PartnerTrackingEngine(hub=hub, email_engine=email_engine, action_bus=bus)

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        ledger = tracker.sync_partner_earnings_and_balances(
            ledger_path=str(tmp_path / "ledger.json"),
            fetch_live_api=True,
            persist=False,
        )

    ps_portal = ledger["portals"]["partnerstack"]
    assert ps_portal["realized_commission_usd"] == pytest.approx(150.0)
    assert ps_portal["pending_commission_usd"] == pytest.approx(250.0)
    assert ledger["cashflow_summary"]["realized_commission_usd"] == pytest.approx(150.0)
    assert ledger["cashflow_summary"]["pending_commission_usd"] == pytest.approx(250.0)
