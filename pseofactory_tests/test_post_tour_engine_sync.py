"""Tests for post-tour engine sync: per-tenant Impact & CJ meta tags, CJ PID map,
headless Impact v16 & CJ GraphQL live telemetry pollers, .env loader hygiene,
and updated monetization_vault.json baseline snapshot.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any, Dict
import urllib.error

import pytest

from pseofactory import affiliate_intent, compiler, maintenance
from pseofactory.action_bus import HumanActionBus
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.email_ingest import EmailIngestionEngine
from pseofactory.maintenance import CrossPropertyContaminationScanner, RetroReflectionEngine
from pseofactory.partner_tracker import PartnerTrackingEngine


REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_IMPACT_CHANNELS = {
    "profithelm": ("8980393", "d089d8b3-753e-46dc-9c12-653de16f710d"),
    "prexvo": ("9151905", "79393cd8-e7dd-49af-a934-f8515d299b19"),
    "gainhelm": ("9151929", "252d3e3c-d342-48fc-8359-eb3700e68b1f"),
    "lienbond": ("9151944", "5ce463de-dd46-4356-871d-e6d1214b5d57"),
}

EXPECTED_CJ_PIDS = {
    "profithelm": "101906407",
    "prexvo": "101927178",
    "gainhelm": "101927180",
    "lienbond": "101927181",
}


def test_affiliate_intent_per_tenant_cj_and_impact_maps() -> None:
    assert affiliate_intent.ACTIVE_CJ_PROPERTY_IDS == (
        "101906407",
        "101927178",
        "101927180",
        "101927181",
    )
    assert affiliate_intent.CJ_PROPERTY_ID_BY_TENANT == EXPECTED_CJ_PIDS
    assert affiliate_intent.IMPACT_CHANNEL_ID_BY_TENANT == {
        k: v[0] for k, v in EXPECTED_IMPACT_CHANNELS.items()
    }
    assert affiliate_intent.IMPACT_VERIFICATION_UUID_BY_TENANT == {
        k: v[1] for k, v in EXPECTED_IMPACT_CHANNELS.items()
    }

    # Brand-matched CJ links across all 4 active tenant PIDs pass intent check
    for pid in affiliate_intent.ACTIVE_CJ_PROPERTY_IDS:
        assert affiliate_intent.is_intent_matched(
            "lawdepot", f"https://www.jdoqocy.com/click-{pid}-16985242"
        )
        assert affiliate_intent.is_intent_matched(
            "efile_com", f"https://www.jdoqocy.com/links/{pid}/type/dlg/https://www.efile.com/"
        )
        # Cross-vertical bait-and-switch still fails closed on every PID
        assert not affiliate_intent.is_intent_matched(
            "suretybonds_direct", f"https://www.jdoqocy.com/click-{pid}-16985242"
        )
        assert not affiliate_intent.is_intent_matched(
            "suretybonds_direct",
            f"https://www.anrdoezrs.net/links/{pid}/type/dlg/https://www.lawdepot.com/",
        )
        assert not affiliate_intent.is_intent_matched(
            "vanta_security", f"https://www.jdoqocy.com/click-{pid}-16985242"
        )

    # Dead CJ PID 101725461 still fails closed even for matching brand
    assert not affiliate_intent.is_intent_matched(
        "lawdepot", "https://www.jdoqocy.com/click-101725461-16985242"
    )


def test_sync_tenant_publisher_prerequisites_emits_exact_impact_and_cj_meta_tags(
    tmp_path: Path,
) -> None:
    scanner = CrossPropertyContaminationScanner()
    canonical_bases = {
        "profithelm": "https://profithelm.com",
        "prexvo": "https://prexvo.com",
        "gainhelm": "https://gainhelm.com",
        "lienbond": "https://lienbond.com",
    }

    for prop_id, base_url in canonical_bases.items():
        _, expected_uuid = EXPECTED_IMPACT_CHANNELS[prop_id]
        expected_cj_pid = EXPECTED_CJ_PIDS[prop_id]
        # Pick a foreign tenant's UUID and CJ PID to prove sanitization replaces bleed
        foreign_prop = "prexvo" if prop_id == "profithelm" else "profithelm"
        _, foreign_uuid = EXPECTED_IMPACT_CHANNELS[foreign_prop]
        foreign_cj_pid = EXPECTED_CJ_PIDS[foreign_prop]

        dist_dir = tmp_path / prop_id / "dist"
        (dist_dir / "tools" / "sample-calc").mkdir(parents=True, exist_ok=True)
        poisoned_head = (
            "<!doctype html><html><head>"
            '<meta name="google-site-verification" content="google-site-verification-verified-2026">'
            f"<meta name='impact-site-verification' value='{foreign_uuid}'>"
            f'<meta name="cj-promotional-property-id" content="{foreign_cj_pid}">'
            '<meta name="cj-promotional-property-id" content="101725461">'
            '<meta name="ir-site-verification-token" content="7932737">'
            '<meta name="sovrn-commerce-domain-key" content="2987330">'
            "</head><body><h1>Test</h1></body></html>"
        )
        (dist_dir / "index.html").write_text(poisoned_head, encoding="utf-8")
        (dist_dir / "tools" / "index.html").write_text(poisoned_head, encoding="utf-8")
        (dist_dir / "tools" / "sample-calc" / "index.html").write_text(
            poisoned_head, encoding="utf-8"
        )

        RetroReflectionEngine.sync_tenant_publisher_prerequisites(dist_dir, prop_id, base_url)

        expected_impact_tag = f"<meta name='impact-site-verification' value='{expected_uuid}'>"
        expected_cj_tag = f'<meta name="cj-promotional-property-id" content="{expected_cj_pid}">'

        for rel_html in ("index.html", "tools/index.html", "tools/sample-calc/index.html"):
            rendered = (dist_dir / rel_html).read_text(encoding="utf-8")
            assert expected_impact_tag in rendered, f"{prop_id} {rel_html} missing {expected_impact_tag}"
            assert expected_cj_tag in rendered, f"{prop_id} {rel_html} missing {expected_cj_tag}"
            assert foreign_uuid not in rendered, f"{prop_id} {rel_html} leaked foreign Impact UUID"
            assert foreign_cj_pid not in rendered, f"{prop_id} {rel_html} leaked foreign CJ PID"
            assert "101725461" not in rendered
            if prop_id != "profithelm":
                assert "sovrn-commerce-domain-key" not in rendered
                assert "ir-site-verification-token" not in rendered
            else:
                assert 'content="0a5ac1bfe04034bff021b394f5e71d90"' in rendered

        assert scanner.scan_directory(dist_dir, prop_id) == {}


def test_compiler_emits_impact_and_cj_meta_tags_in_compiled_html(tmp_path: Path) -> None:
    # 1. Verify LienBond estate compiler emits LienBond's exact Impact UUID and CJ PID on dist/index.html & tools
    lb_out = tmp_path / "lienbond_compiled"
    compiler.compile_lienbond_estate(lb_out, run_retrofit=False)
    lb_dist = lb_out / "dist"
    lb_index = (lb_dist / "index.html").read_text(encoding="utf-8")
    assert "<meta name='impact-site-verification' value='5ce463de-dd46-4356-871d-e6d1214b5d57'>" in lb_index
    assert '<meta name="cj-promotional-property-id" content="101927181">' in lb_index
    assert "d089d8b3-753e-46dc-9c12-653de16f710d" not in lb_index
    assert "101906407" not in lb_index

    lb_tool_files = list((lb_dist / "tools").rglob("index.html"))
    assert len(lb_tool_files) >= 1
    sample_lb_tool = lb_tool_files[0].read_text(encoding="utf-8")
    assert "<meta name='impact-site-verification' value='5ce463de-dd46-4356-871d-e6d1214b5d57'>" in sample_lb_tool
    assert '<meta name="cj-promotional-property-id" content="101927181">' in sample_lb_tool

    # 2. Verify compile_high_effort_page across all 4 properties emits each tenant's own tags
    sample_specs = [
        ("profithelm", "https://profithelm.com", "26 U.S.C. Section 179", "section-179-equipment-deduction-calc"),
        ("prexvo", "https://prexvo.com", "34 CFR Part 685 Title IV", "rap-payment-discretionary-calc"),
        ("gainhelm", "https://gainhelm.com", "AICPA SSAE 18 (AT-C Section 205) and 32 CFR Part 170", "soc-2-audit-readiness-calc"),
        ("lienbond", "https://lienbond.com", "40 U.S.C. Section 3131 Miller Act", "surety-bond-penal-sum-calc"),
    ]
    for prop_id, base_url, stat_auth, slug in sample_specs:
        res = compiler.compile_high_effort_page(
            {
                "property_id": prop_id,
                "canonical_base": base_url,
                "slug": slug,
                "primary_keyword": slug.replace("-", " "),
                "statutory_authority": stat_auth,
                "economic_dataset": "BLS CPI-U & FRED DGS10 Benchmark Series",
                "model_name": f"StatutoryModel_{prop_id}",
                "formula": "round(amount * rate, 2)",
                "inputs": {"amount": 1000.0, "rate": 0.05},
                "published_output": 50.0,
                "sample_calculation": "round(1000.0 * 0.05, 2) = 50.0",
            }
        )
        html_out = res["html"]
        _, exp_uuid = EXPECTED_IMPACT_CHANNELS[prop_id]
        exp_pid = EXPECTED_CJ_PIDS[prop_id]
        assert f"<meta name='impact-site-verification' value='{exp_uuid}'>" in html_out
        assert f'<meta name="cj-promotional-property-id" content="{exp_pid}">' in html_out


def test_load_local_env_and_live_impact_cj_headless_pollers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pseofactory import partner_tracker

    dotenv_file = tmp_path / ".env"
    secret_impact_tok = "imp_secret_unit_test_token_999"
    secret_cj_tok = "cj_pat_unit_test_token_888"
    dotenv_file.write_text(
        "# Test env file\n"
        "IMPACT_ACCOUNT_SID=IR_TEST_SID_7932737\n"
        f'IMPACT_AUTH_TOKEN="{secret_impact_tok}"\n'
        "IMPACT_API_VERSION=16\n"
        f"CJ_PERSONAL_ACCESS_TOKEN='{secret_cj_tok}'\n"
        "CJ_PUBLISHER_ID=8101803\n"
        "CJ_COMPANY_CID=7792582\n"
        "PARTNERSTACK_API_KEY=ps_test_key_777\n",
        encoding="utf-8",
    )

    for k in (
        "IMPACT_ACCOUNT_SID",
        "IMPACT_AUTH_TOKEN",
        "IMPACT_API_VERSION",
        "CJ_PERSONAL_ACCESS_TOKEN",
        "CJ_PUBLISHER_ID",
        "CJ_COMPANY_CID",
        "PARTNERSTACK_API_KEY",
    ):
        # Prime monkeypatch undo stack even when key was originally absent from os.environ
        monkeypatch.setenv(k, "__sentinel__")
        monkeypatch.delenv(k, raising=False)

    loaded_keys = partner_tracker._load_local_env(dotenv_path=str(dotenv_file))
    assert "IMPACT_ACCOUNT_SID" in loaded_keys
    assert "CJ_PERSONAL_ACCESS_TOKEN" in loaded_keys
    assert os.environ["IMPACT_ACCOUNT_SID"] == "IR_TEST_SID_7932737"
    assert os.environ["IMPACT_AUTH_TOKEN"] == secret_impact_tok
    assert os.environ["CJ_PERSONAL_ACCESS_TOKEN"] == secret_cj_tok
    assert os.environ["CJ_PUBLISHER_ID"] == "8101803"

    # Existing env vars are never overwritten by _load_local_env
    monkeypatch.setenv("IMPACT_API_VERSION", "17")
    partner_tracker._load_local_env(dotenv_path=str(dotenv_file))
    assert os.environ["IMPACT_API_VERSION"] == "17"
    monkeypatch.setenv("IMPACT_API_VERSION", "16")

    # Mock urllib.request.urlopen to verify Impact v16 + CJ GraphQL live polling and CDP 9222 non-touch
    called_urls: list[str] = []

    class _FakeHTTPResponse:
        def __init__(self, payload: Dict[str, Any]) -> None:
            self._raw = json.dumps(payload).encode("utf-8")
            self.status = 200

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> "_FakeHTTPResponse":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: float = 10.0) -> _FakeHTTPResponse:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        called_urls.append(url)
        if "127.0.0.1:9222" in url or "localhost:9222" in url:
            raise AssertionError("Must NEVER touch Chrome port 9222 during headless telemetry sync")
        if "api.impact.com/Mediapartners/IR_TEST_SID_7932737/Reports/partner_performance_by_program" in url:
            headers_lc = {k.lower(): v for k, v in req.header_items()}
            assert headers_lc.get("ir-version") == "16"
            assert headers_lc.get("authorization", "").startswith("Basic ")
            return _FakeHTTPResponse(
                {
                    "Records": [
                        {
                            "Campaign": "Xendoo Online Accounting",
                            "campaign_id": "16354",
                            "Clicks": "299",
                            "Actions": "1",
                            "Action_Cost": "500.000000000000000000",
                            "Total_Cost": "500.000000000000000000",
                        },
                        {
                            "Campaign": "Gusto",
                            "campaign_id": "15154",
                            "Clicks": "77",
                            "Actions": "0",
                            "Action_Cost": "0.00",
                            "Total_Cost": "0.00",
                        },
                        {
                            "Campaign": "Kalshi",
                            "campaign_id": "37770",
                            "Clicks": "57",
                            "Actions": "0",
                            "Action_Cost": "0.00",
                            "Total_Cost": "0.00",
                        },
                        {
                            "Campaign": "Ramp",
                            "campaign_id": "51436",
                            "Clicks": "15",
                            "Actions": "0",
                            "Action_Cost": "0.00",
                            "Total_Cost": "0.00",
                        },
                    ]
                }
            )
        if "commissions.api.cj.com/query" in url:
            headers_lc = {k.lower(): v for k, v in req.header_items()}
            assert headers_lc.get("authorization") == f"Bearer {secret_cj_tok}"
            body = json.loads((req.data or b"{}").decode("utf-8"))
            assert "publisherCommissions" in body.get("query", "")
            assert "8101803" in body.get("query", "")
            return _FakeHTTPResponse(
                {
                    "data": {
                        "publisherCommissions": {
                            "count": 2,
                            "payloadComplete": True,
                            "records": [
                                {"pubCommissionAmountUsd": "12.50", "actionTrackerName": "Sale"},
                                {"pubCommissionAmountUsd": "7.25", "actionTrackerName": "Sale"},
                            ],
                        }
                    }
                }
            )
        if "api.partnerstack.com" in url:
            return _FakeHTTPResponse({"status": 200, "data": {"items": []}})
        raise urllib.error.URLError("simulated offline endpoint")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setenv("PSEUFACTORY_LIVE_NETWORK", "1")

    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))
    hub = MonetizationHub()
    tracker = PartnerTrackingEngine(hub=hub, email_engine=email_engine, action_bus=bus)

    ledger_out = tmp_path / "ledger.json"
    res = tracker.sync_partner_earnings_and_balances(
        ledger_path=str(ledger_out),
        fetch_live_api=True,
        persist=True,
    )

    impact_state = res["portals"]["impact"]
    assert impact_state["auth_status"] == "AUTHENTICATED_SYNCING"
    assert impact_state["is_authenticated_and_syncing"] is True
    assert impact_state["live_api_polled_in_current_run"] is True
    assert impact_state["uncollected_telemetry_reason"] is None
    assert impact_state["portal_verified_clicks"] == 448
    assert impact_state["conversions_count"] == 1
    assert impact_state["realized_commission_usd"] == pytest.approx(500.0)

    cj_state = res["portals"]["cj_affiliate"]
    assert cj_state["auth_status"] == "AUTHENTICATED_SYNCING"
    assert cj_state["is_authenticated_and_syncing"] is True
    assert cj_state["live_api_polled_in_current_run"] is True
    assert cj_state["uncollected_telemetry_reason"] is None
    assert cj_state["conversions_count"] == 2
    assert cj_state["realized_commission_usd"] == pytest.approx(19.75)

    # Secret hygiene: raw tokens never appear in serialized ledger
    serialized = json.dumps(res)
    assert secret_impact_tok not in serialized
    assert secret_cj_tok not in serialized
    assert not any("9222" in u for u in called_urls)

    # Offline / timeout resilience: when API calls fail, falls back cleanly without crashing
    def _offline_urlopen(req: Any, timeout: float = 10.0) -> _FakeHTTPResponse:
        raise urllib.error.URLError("network unreachable in CI")

    monkeypatch.setattr("urllib.request.urlopen", _offline_urlopen)
    offline_res = tracker.sync_partner_earnings_and_balances(
        ledger_path=str(tmp_path / "offline_ledger.json"),
        fetch_live_api=True,
        persist=False,
    )
    assert offline_res["portals"]["impact"]["live_api_polled_in_current_run"] is False
    assert offline_res["portals"]["impact"]["auth_status"] == "SESSION_EXPIRED_CACHED_SNAPSHOT"
    assert offline_res["portals"]["cj_affiliate"]["live_api_polled_in_current_run"] is False
    assert offline_res["portals"]["cj_affiliate"]["auth_status"] == "SESSION_EXPIRED_CACHED_SNAPSHOT"


def test_monetization_vault_post_tour_baseline_snapshot() -> None:
    vault_path = REPO_ROOT / "pseofactory" / "monetization_vault.json"
    raw = vault_path.read_text(encoding="utf-8")
    assert "\u2014" not in raw
    assert "\u2013" not in raw
    vault = json.loads(raw)

    # Stripe phone verification complete, Payments & Payouts Active
    stripe_net = vault["master_networks"]["stripe"]
    assert stripe_net["charges_enabled"] is True
    assert stripe_net["payouts_enabled"] is True
    assert stripe_net["phone_verification_status"] == "COMPLETE"

    # Impact: 4 active campaigns, 4 MediaProperties, 448 clicks (Xendoo 299, Gusto 77, Kalshi 57, Ramp 15)
    impact_net = vault["master_networks"]["impact"]
    assert impact_net["active_advertiser_contracts"] == 4
    assert impact_net["verified_clicks"] == 448
    media_props = impact_net["media_properties"]
    assert {mp["channel_id"] for mp in media_props.values()} == {
        "8980393",
        "9151905",
        "9151929",
        "9151944",
    }
    clicks_by_campaign = {
        c["campaign_id"]: c["verified_clicks"] for c in impact_net["live_active_contracts"]
    }
    assert clicks_by_campaign == {
        "16354": 299,
        "15154": 77,
        "37770": 57,
        "51436": 15,
    }

    # CJ: 4 active Promotional Properties, 5 active joined advertisers, 13 pending applications
    cj_net = vault["master_networks"]["cj_affiliate"]
    assert cj_net["live_promotional_property_id"] == "101906407"
    assert "promotional_property_id" not in cj_net
    assert cj_net["promotional_properties"] == EXPECTED_CJ_PIDS
    assert cj_net["active_joined_advertisers_count"] == 5
    assert cj_net["pending_advertiser_applications"] == 13
    assert cj_net["live_pending_advertiser_applications"] == 13

    # PartnerStack: 94% profile with all 4 domains, Marketplace in_review, 2578 clicks on Rippling
    ps_net = vault["master_networks"]["partnerstack"]
    assert ps_net["network_profile_completion_pct"] == 94
    assert ps_net["marketplace_application_status"] == "in_review"
    assert ps_net["verified_clicks"] == 2578
    ps_api = vault["properties"]["profithelm"]["agentic_api_programs"]["partnerstack_api_v2"]
    assert ps_api["live_verified_clicks"] == 2578

    # Cloudflare Workers Paid Standard active on account 8789c54bef2d281d4a8afb4df34f9878
    cf_net = vault["master_networks"]["cloudflare_edge"]
    assert cf_net["account_id"] == "8789c54bef2d281d4a8afb4df34f9878"
    assert cf_net["default_usage_model"] == "standard"
    assert cf_net["plan"] == "workers_paid"


def test_sync_tenant_test_isolation_guards_includes_wrangler_rate_limit_retry_backoff(
    tmp_path: Path,
) -> None:
    import os
    import subprocess
    import yaml
    from pseofactory.gitops import sync_tenant_test_isolation_guards

    fake_bin = tmp_path / "fake_bin"
    fake_bin.mkdir(parents=True)
    fake_npx = fake_bin / "npx"
    fake_npx.write_text(
        "#!/usr/bin/env bash\n"
        'count_file="${FAKE_NPX_COUNT_FILE:?}"\n'
        'succeed_on="${FAKE_NPX_SUCCEED_ON:-0}"\n'
        'cur=$(cat "$count_file" 2>/dev/null || echo 0)\n'
        "cur=$((cur + 1))\n"
        'echo "$cur" > "$count_file"\n'
        'echo "$*" >> "${FAKE_NPX_ARGS_FILE:?}"\n'
        'if [ "$succeed_on" -gt 0 ] && [ "$cur" -ge "$succeed_on" ]; then\n'
        '  echo "Deployment complete!"\n'
        "  exit 0\n"
        "fi\n"
        'echo "ERROR [code: 10429] Too Many Requests" >&2\n'
        "exit 1\n",
        encoding="utf-8",
    )
    fake_npx.chmod(0o755)

    fake_sleep = fake_bin / "sleep"
    fake_sleep.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "${FAKE_SLEEP_LOG:?}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake_sleep.chmod(0o755)

    for repo_name, pkg_name, prop_id in (
        ("profithelm-platform", "profithelm", "profithelm"),
        ("prexvo", "prexvo", "prexvo"),
        ("gainhelm", "gainhelm", "gainhelm"),
        ("lienbond", "lienbond", "lienbond"),
    ):
        repo_dir = tmp_path / repo_name
        (repo_dir / pkg_name).mkdir(parents=True)
        (repo_dir / ".github" / "workflows").mkdir(parents=True)
        (repo_dir / ".github" / "workflows" / "ci.yml").write_text("placeholder\n", encoding="utf-8")
        (repo_dir / ".pseofactory.json").write_text(
            json.dumps({"property_id": prop_id}), encoding="utf-8"
        )
        sync_tenant_test_isolation_guards(repo_dir, property_id=prop_id)
        ci_text = (repo_dir / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "npx wrangler pages deploy dist" in ci_text
        assert "for attempt in 1 2 3 4; do" in ci_text
        assert "sleep $((attempt * 12))" in ci_text
        assert "\u2014" not in ci_text
        assert "\u2013" not in ci_text

        parsed_ci = yaml.safe_load(ci_text)
        assert isinstance(parsed_ci, dict)
        jobs = parsed_ci.get("jobs") or {}
        deploy_run_script = None
        for job_spec in jobs.values():
            for step in job_spec.get("steps") or []:
                if step.get("name") == "Deploy to Cloudflare Pages Edge":
                    deploy_run_script = step.get("run")
        assert isinstance(deploy_run_script, str) and deploy_run_script.strip()
        assert "${{" not in deploy_run_script

        # Case (a): 3 rate-limit 10429 failures followed by 4th attempt success under bash -eo pipefail -> exits 0
        cnt_ok = tmp_path / f"{prop_id}_ok_count.txt"
        args_ok = tmp_path / f"{prop_id}_ok_args.txt"
        sleep_ok = tmp_path / f"{prop_id}_ok_sleep.txt"
        env_ok = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            "FAKE_NPX_COUNT_FILE": str(cnt_ok),
            "FAKE_NPX_ARGS_FILE": str(args_ok),
            "FAKE_NPX_SUCCEED_ON": "4",
            "FAKE_SLEEP_LOG": str(sleep_ok),
        }
        proc_ok = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", deploy_run_script],
            cwd=repo_dir,
            env=env_ok,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_ok.returncode == 0, f"{prop_id} 4th-attempt recovery failed: {proc_ok.stderr}"
        assert cnt_ok.read_text(encoding="utf-8").strip() == "4"
        assert sleep_ok.read_text(encoding="utf-8").splitlines() == ["12", "24", "36"]
        assert prop_id in args_ok.read_text(encoding="utf-8")

        # Case (b): 4 consecutive rate-limit 10429 failures under bash -eo pipefail -> fails closed (returncode != 0)
        cnt_fail = tmp_path / f"{prop_id}_fail_count.txt"
        args_fail = tmp_path / f"{prop_id}_fail_args.txt"
        sleep_fail = tmp_path / f"{prop_id}_fail_sleep.txt"
        env_fail = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            "FAKE_NPX_COUNT_FILE": str(cnt_fail),
            "FAKE_NPX_ARGS_FILE": str(args_fail),
            "FAKE_NPX_SUCCEED_ON": "0",
            "FAKE_SLEEP_LOG": str(sleep_fail),
        }
        proc_fail = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", deploy_run_script],
            cwd=repo_dir,
            env=env_fail,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_fail.returncode != 0
        assert cnt_fail.read_text(encoding="utf-8").strip() == "4"
        assert sleep_fail.read_text(encoding="utf-8").splitlines() == ["12", "24", "36"]


def test_legacy_duplicate_cloudflare_workflows_removed_and_reflect_no_gitops_syncs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import argparse
    from pseofactory import cli as cli_mod
    from pseofactory.gitops import sync_tenant_test_isolation_guards
    from pseofactory.maintenance import SubprocessPropertyAdapter

    ph_dir = tmp_path / "profithelm-platform"
    (ph_dir / "profithelm").mkdir(parents=True)
    ph_wf = ph_dir / ".github" / "workflows"
    ph_wf.mkdir(parents=True)
    (ph_wf / "ci.yml").write_text("name: old\n", encoding="utf-8")
    (ph_wf / "deploy-google.yml").write_text("name: old-google\n", encoding="utf-8")
    (ph_wf / "deploy-cloudflare.yml").write_text(
        "name: Legacy Duplicate Deploy\non: [push]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npx wrangler pages deploy dist\n",
        encoding="utf-8",
    )

    px_dir = tmp_path / "prexvo"
    (px_dir / "prexvo").mkdir(parents=True)
    px_wf = px_dir / ".github" / "workflows"
    px_wf.mkdir(parents=True)
    (px_wf / "ci.yml").write_text("name: old\n", encoding="utf-8")
    (px_wf / "deploy_cloudflare_pages.yml").write_text(
        "name: Legacy Prexvo Duplicate Deploy\non: [push]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npx wrangler pages deploy dist\n",
        encoding="utf-8",
    )

    # Prove cmd_reflect with --no-gitops (Stage 3b entrypoint before child release_pipeline.sh)
    # updates ci.yml AND removes legacy duplicate Cloudflare workflows deterministically.
    def _fake_reflect(**kwargs: Any) -> Dict[str, Any]:
        return {
            "status": "PASS",
            "properties_scanned": 2,
            "total_assets_checked": 2,
            "total_drifted": 0,
            "total_recompiled": 0,
            "total_retrofitted": 0,
            "property_reports": {
                "profithelm": {"final_status": "PASS", "recompiled": 0, "retrofitted": 0},
                "prexvo": {"final_status": "PASS", "recompiled": 0, "retrofitted": 0},
            },
        }

    class _DummyRegistry:
        def get_adapter(self, pid: str) -> SubprocessPropertyAdapter:
            if pid == "profithelm":
                return SubprocessPropertyAdapter(
                    property_id="profithelm",
                    brand_name="ProfitHelm",
                    domain="profithelm.com",
                    canonical_base="https://profithelm.com",
                    dist_dir=ph_dir / "dist",
                    repo_path=ph_dir,
                )
            return SubprocessPropertyAdapter(
                property_id="prexvo",
                brand_name="Prexvo",
                domain="prexvo.com",
                canonical_base="https://prexvo.com",
                dist_dir=px_dir / "dist",
                repo_path=px_dir,
            )

    monkeypatch.setattr(cli_mod, "reflect_and_recompile_all_assets", _fake_reflect)
    monkeypatch.setattr(cli_mod.TenantRegistry, "default", classmethod(lambda cls: _DummyRegistry()))

    rc = cli_mod.cmd_reflect(
        argparse.Namespace(property=None, force=True, verbose=False, no_gitops=True, json=True)
    )
    assert rc == 0
    assert not (ph_wf / "deploy-cloudflare.yml").exists()
    assert (ph_wf / "deploy-google.yml").is_file()
    assert "for attempt in 1 2 3 4; do" in (ph_wf / "ci.yml").read_text(encoding="utf-8")

    assert not (px_wf / "deploy_cloudflare_pages.yml").exists()
    assert "for attempt in 1 2 3 4; do" in (px_wf / "ci.yml").read_text(encoding="utf-8")

    # Idempotency check: second call reports 0 updated files
    assert sync_tenant_test_isolation_guards(ph_dir, "profithelm")["updated_files"] == 0
    assert sync_tenant_test_isolation_guards(px_dir, "prexvo")["updated_files"] == 0


def test_partner_tracker_cj_graphql_errors_fail_closed_and_non_json_resilience(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pseofactory import partner_tracker
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.affiliates_hub import MonetizationHub
    from pseofactory.email_ingest import EmailIngestionEngine
    from pseofactory.partner_tracker import PartnerTrackingEngine

    secret_impact_tok = "IR_SECRET_TOK_FAIL_CLOSED_99"
    secret_cj_tok = "CJ_SECRET_PAT_FAIL_CLOSED_88"
    monkeypatch.setenv("IMPACT_ACCOUNT_SID", "IR_TEST_SID_7932737")
    monkeypatch.setenv("IMPACT_AUTH_TOKEN", secret_impact_tok)
    monkeypatch.setenv("CJ_PERSONAL_ACCESS_TOKEN", secret_cj_tok)
    monkeypatch.setenv("CJ_PUBLISHER_ID", "8101803")
    monkeypatch.setenv("PSEUFACTORY_LIVE_NETWORK", "1")
    monkeypatch.delenv("PARTNERSTACK_API_KEY", raising=False)

    class _RawHTTPResponse:
        def __init__(self, body_bytes: bytes, status: int = 200) -> None:
            self._body = body_bytes
            self.status = status

        def read(self, _amt: int = -1) -> bytes:
            return self._body

        def __enter__(self) -> "_RawHTTPResponse":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    # 1. CJ HTTP 200 with GraphQL errors ({"data": null, "errors": [{"message": "Expired PAT"}]}) MUST fail closed
    def _gql_error_urlopen(req: Any, timeout: float = 10.0) -> _RawHTTPResponse:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "commissions.api.cj.com/query" in url:
            return _RawHTTPResponse(
                json.dumps({"data": None, "errors": [{"message": f"Expired PAT {secret_cj_tok}"}]}).encode("utf-8")
            )
        if "api.impact.com" in url:
            return _RawHTTPResponse(json.dumps({"Records": []}).encode("utf-8"))
        raise RuntimeError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _gql_error_urlopen)
    tracker = PartnerTrackingEngine(
        hub=MonetizationHub(),
        email_engine=EmailIngestionEngine(
            cache_path=str(tmp_path / "ec.json"),
            state_path=str(tmp_path / "es.json"),
        ),
        action_bus=HumanActionBus(bus_path=str(tmp_path / "bus.json")),
    )
    gql_res = tracker.sync_partner_earnings_and_balances(
        ledger_path=str(tmp_path / "gql_err_ledger.json"),
        fetch_live_api=True,
        persist=False,
    )
    cj_portal = gql_res["portals"]["cj_affiliate"]
    assert cj_portal["auth_status"] == "AUTH_FAILED"
    assert cj_portal["is_authenticated_and_syncing"] is False
    assert cj_portal["live_api_polled_in_current_run"] is False
    assert "Expired PAT" in (cj_portal["uncollected_telemetry_reason"] or "")
    assert secret_cj_tok not in json.dumps(gql_res)

    poll_cj_fn = getattr(partner_tracker, "_poll_cj_graphql_commissions", None)
    assert callable(poll_cj_fn)
    direct_cj = poll_cj_fn(secret_cj_tok, "8101803")
    assert direct_cj["ok"] is False
    assert direct_cj["status"] == "AUTH_FAILED"
    assert direct_cj["auth_status"] != "AUTHENTICATED_SYNCING"
    assert direct_cj["is_authenticated_and_syncing"] is False
    assert secret_cj_tok not in json.dumps(direct_cj)

    # 2. Non-JSON HTTP 200 HTML WAF payloads from both Impact and CJ must NOT raise JSONDecodeError
    def _html_waf_urlopen(req: Any, timeout: float = 10.0) -> _RawHTTPResponse:
        return _RawHTTPResponse(b"<!DOCTYPE html><html><body>502 Bad Gateway</body></html>", status=200)

    monkeypatch.setattr("urllib.request.urlopen", _html_waf_urlopen)
    waf_res = tracker.sync_partner_earnings_and_balances(
        ledger_path=str(tmp_path / "waf_ledger.json"),
        fetch_live_api=True,
        persist=False,
    )
    assert waf_res["portals"]["impact"]["auth_status"] == "API_ERROR"
    assert waf_res["portals"]["impact"]["is_authenticated_and_syncing"] is False
    assert waf_res["portals"]["impact"]["live_api_polled_in_current_run"] is False
    assert waf_res["portals"]["cj_affiliate"]["auth_status"] == "API_ERROR"
    assert waf_res["portals"]["cj_affiliate"]["is_authenticated_and_syncing"] is False
    assert waf_res["portals"]["cj_affiliate"]["live_api_polled_in_current_run"] is False

    poll_imp_fn = getattr(partner_tracker, "_poll_impact_api_v16", None)
    assert callable(poll_imp_fn)
    direct_imp_html = poll_imp_fn("IR_TEST_SID_7932737", secret_impact_tok)
    direct_cj_html = poll_cj_fn(secret_cj_tok, "8101803")
    assert direct_imp_html["ok"] is False
    assert direct_imp_html["status"] == "API_ERROR"
    assert direct_cj_html["ok"] is False
    assert direct_cj_html["status"] == "API_ERROR"


