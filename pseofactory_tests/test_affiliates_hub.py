"""
pseofactory Autonomous Monetization Hub Test Suite
Validates:
1. Vault schema loading and default fallback mechanism.
2. Direct high-bounty partner resolution across properties.
3. Sovrn Commerce server-side URL wrapping for ProfitHelm long-tail tools.
4. Strict rejection of sub-affiliate fallback on Prexvo under CFPB compliance.
5. Outbound link attributes: rel="noopener sponsored nofollow", target="_blank".
6. Anti-slop typography invariant (assert_no_forbidden_dashes).
7. Dynamic environment variable overrides for master network credentials.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
import os
import urllib.parse
import pytest

from pseofactory.affiliates_hub import (
    MonetizationHub,
    DEFAULT_SOVRN_DOMAIN_KEY,
    DEFAULT_SOVRN_API_KEY,
    DEFAULT_PARTNERSTACK_API_KEY,
    DEFAULT_STRIPE_ACCOUNT_ID,
)
from pseofactory.affiliates import (
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
    PREXVO_STANDING_RESTRICTION,
)
from pseofactory.contracts import assert_no_forbidden_dashes


def test_vault_schema_loading_and_default_fallback():
    """Verifies that the vault JSON loads properly with credentials and provides clean fallbacks."""
    hub = MonetizationHub()

    assert hub.vault_data is not None
    assert "master_networks" in hub.vault_data
    assert "properties" in hub.vault_data

    # Verify master credentials in loaded vault
    master = hub.vault_data["master_networks"]
    assert master["sovrn_commerce"]["domain_key"] == "0a5ac1bfe04034bff021b394f5e71d90"
    assert master["sovrn_commerce"]["api_key"] == "039f430e9e7cad0bd9ff3e6c8d1c54769d5847c3"
    assert master["partnerstack"]["api_key"] == "5ZyfW4zFohJwn2yY8fwc6atIYGIubHwPeATJTNQtqPDrJCIihDhds2dRPrHQJwMP"
    assert master["stripe"]["account_id"] == "acct_1T6fSTIq0ckFsf5j"

    # Property-level fallback configuration
    props = hub.vault_data["properties"]
    assert props["profithelm"]["fallback_enabled"] is True
    assert props["profithelm"]["fallback_provider"] == "sovrn_commerce"
    assert props["prexvo"]["fallback_enabled"] is False

    # Vault status reporting
    status = hub.get_vault_status()
    assert status["direct_partners_total"] >= 20
    assert status["direct_partners_active"] >= 2
    assert status["direct_partners_pending"] >= 17
    assert status["master_keys"]["sovrn_commerce_domain_key_configured"] is True
    assert status["master_keys"]["sovrn_commerce_api_key_configured"] is True
    assert status["master_keys"]["partnerstack_api_key_configured"] is True
    assert status["master_keys"]["stripe_account_id_configured"] is True
    assert status["properties"]["profithelm"]["fallback_enabled"] is True
    assert status["properties"]["prexvo"]["fallback_enabled"] is False

    # In-memory default fallback when path does not exist
    fallback_hub = MonetizationHub(vault_path="/nonexistent/path/monetization_vault.json")
    assert fallback_hub.sovrn_domain_key == DEFAULT_SOVRN_DOMAIN_KEY
    assert fallback_hub.sovrn_api_key == DEFAULT_SOVRN_API_KEY
    assert fallback_hub.partnerstack_api_key == DEFAULT_PARTNERSTACK_API_KEY
    assert fallback_hub.stripe_account_id == DEFAULT_STRIPE_ACCOUNT_ID


def test_direct_high_bounty_partner_resolution():
    """Verifies direct partner resolution for mapped high-bounty tools."""
    hub = MonetizationHub()

    # ProfitHelm direct partner via slug
    route_cl = hub.get_route("profithelm", "crypto-tax-calculator")
    assert route_cl["property_id"] == "profithelm"
    assert route_cl["partner"] == "coinledger"
    assert route_cl["status"] == "live"
    assert "coinledger.io" in route_cl["url"]

    # ProfitHelm direct partner via partner_key
    route_mercury = hub.get_route("profithelm", partner_key="mercury")
    assert route_mercury["property_id"] == "profithelm"
    assert route_mercury["partner"] == "mercury"
    assert route_mercury["status"] == "live"
    assert route_mercury["url"] == "https://mercury.com/r/profithelm-llc"

    route_ramp = hub.get_route("profithelm", partner_key="ramp")
    assert route_ramp["property_id"] == "profithelm"
    assert route_ramp["partner"] == "ramp"
    assert "mercury.com" in route_ramp["url"]

    # Prexvo direct partner via slug
    route_px = hub.get_route("prexvo", "student-loan-repayment-calculator")
    assert route_px["property_id"] == "prexvo"
    assert route_px["partner"] == "splash_financial"
    assert "splashfinancial.com" in route_px["url"]

    # Prexvo direct partner via partner_key
    route_sofi = hub.get_route("prexvo", partner_key="sofi")
    assert route_sofi["property_id"] == "prexvo"
    assert route_sofi["partner"] == "sofi"
    assert "sofi.com" in route_sofi["url"]


def test_sovrn_commerce_url_wrapping_profithelm_long_tail():
    """Verifies Sovrn Commerce redirect link wrapping for long-tail tools on ProfitHelm."""
    hub = MonetizationHub()

    # Basic wrapper validation
    target = "https://turbotax.intuit.com"
    wrapped = hub.wrap_sovrn_url(target)
    assert wrapped.startswith("https://redirect.viglink.com?key=")
    assert f"key={hub.sovrn_domain_key}" in wrapped
    assert "u=https%3A%2F%2Fturbotax.intuit.com" in wrapped

    # Custom domain key support
    custom_wrapped = hub.wrap_sovrn_url(target, custom_key="custom_domain_key_456")
    assert "key=custom_domain_key_456" in custom_wrapped

    # Invalid target URL rejection
    with pytest.raises(ValueError, match="Scheme must be http or https"):
        hub.wrap_sovrn_url("ftp://files.example.com")

    with pytest.raises(ValueError, match="Invalid target URL scheme"):
        hub.wrap_sovrn_url("/relative/path")

    with pytest.raises(ValueError, match="Unsafe URL scheme"):
        hub.wrap_sovrn_url("javascript:void(0)")

    # Unmapped long-tail tool on ProfitHelm routes to wrapped fallback
    long_tail_route = hub.get_route("profithelm", "notion-workspace-cost-calculator")
    assert long_tail_route["property_id"] == "profithelm"
    assert long_tail_route["status"] == "wrapped_fallback"
    assert long_tail_route["partner"] == "sovrn_commerce"
    assert long_tail_route["url"].startswith("https://redirect.viglink.com?key=")

    # Explicit fallback_url on ProfitHelm routes to wrapped target
    explicit_fallback = hub.get_route(
        "profithelm",
        "office-supplies-estimator",
        fallback_url="https://store.office.com/en-us/supplies",
    )
    assert explicit_fallback["status"] == "wrapped_fallback"
    assert explicit_fallback["target_url"] == "https://store.office.com/en-us/supplies"
    assert "store.office.com" in explicit_fallback["url"]


def test_strict_rejection_of_sub_affiliate_fallback_on_prexvo():
    """Verifies that Prexvo strictly prohibits sub-affiliate fallbacks and B2B monetization."""
    hub = MonetizationHub()

    # Reject fallback_url on Prexvo
    with pytest.raises(ValueError, match="Sub-affiliate fallback is prohibited on Prexvo"):
        hub.get_route("prexvo", fallback_url="https://example.com/fallback")

    # Reject sovrn_commerce partner_key on Prexvo
    with pytest.raises(ValueError, match="Sub-affiliate fallback is prohibited on Prexvo"):
        hub.get_route("prexvo", partner_key="sovrn_commerce")

    # Reject unmapped tool on Prexvo
    with pytest.raises(ValueError, match="Sub-affiliate fallback is prohibited on Prexvo"):
        hub.get_route("prexvo", tool_slug="unmapped-random-tool")

    # Reject B2B partner on Prexvo
    with pytest.raises(ValueError, match="Strict isolation violation: B2B partner"):
        hub.get_route("prexvo", partner_key="mercury")

    # Reject commercial tool on Prexvo
    with pytest.raises(ValueError, match="Strict isolation violation: Commercial tool"):
        hub.get_route("prexvo", tool_slug="saas-runway-calculator")

    # Reject student loan partner on ProfitHelm
    with pytest.raises(ValueError, match="Strict isolation violation: Student loan partner"):
        hub.get_route("profithelm", partner_key="splash_financial")

    # Reject student loan tool on ProfitHelm
    with pytest.raises(ValueError, match="Strict isolation violation: Student loan tool"):
        hub.get_route("profithelm", tool_slug="student-loan-repayment-calculator")


def test_link_attributes_and_disclosure_compliance():
    """Verifies guaranteed rel and target attributes on all output routes."""
    hub = MonetizationHub()

    # Direct route attributes
    direct_route = hub.get_route("profithelm", "crypto-tax-calculator")
    assert direct_route["rel"] == "noopener sponsored nofollow"
    assert direct_route["target"] == "_blank"
    assert direct_route["disclosure_required"] is True

    # Prexvo direct route attributes
    px_route = hub.get_route("prexvo", "student-loan-repayment-calculator")
    assert px_route["rel"] == "noopener sponsored nofollow"
    assert px_route["target"] == "_blank"
    assert px_route["disclosure_required"] is True

    # Fallback route attributes
    fallback_route = hub.get_route("profithelm", "long-tail-unmapped-calculator")
    assert fallback_route["rel"] == "noopener sponsored nofollow"
    assert fallback_route["target"] == "_blank"
    assert fallback_route["disclosure_required"] is True


def test_anti_slop_typography_invariant():
    """Verifies that zero em-dashes and zero en-dashes exist across vault and generated routes."""
    hub = MonetizationHub()

    def check_recursive_dashes(val, path=""):
        if isinstance(val, str):
            assert_no_forbidden_dashes(val, context=f"Vault path '{path}'")
        elif isinstance(val, dict):
            for k, v in val.items():
                check_recursive_dashes(v, path=f"{path}.{k}")
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                check_recursive_dashes(item, path=f"{path}[{idx}]")

    check_recursive_dashes(hub.vault_data, path="vault_data")

    # Check route outputs
    starter_route = hub.get_route("profithelm", "crypto-tax-calculator", value_tier="starter")
    premium_route = hub.get_route("profithelm", "crypto-tax-calculator", value_tier="premium")
    fallback_route = hub.get_route("profithelm", "long-tail-tool", value_tier="premium")

    for r in (starter_route, premium_route, fallback_route):
        assert_no_forbidden_dashes(r["cta_text"], context="CTA text")
        assert_no_forbidden_dashes(r["name"], context="Partner name")
        assert_no_forbidden_dashes(r["badge"], context="Badge")
        assert_no_forbidden_dashes(r["url"], context="Output URL")


def test_environment_variable_overrides_master_keys(monkeypatch):
    """Verifies dynamic environment variable overrides for master network credentials."""
    hub = MonetizationHub()

    # Override Sovrn Commerce domain key
    monkeypatch.setenv("SOVRN_COMMERCE_KEY", "env_override_sovrn_domain_key")
    assert hub.sovrn_domain_key == "env_override_sovrn_domain_key"
    wrapped = hub.wrap_sovrn_url("https://example.com")
    assert "key=env_override_sovrn_domain_key" in wrapped

    # Override Sovrn Commerce API key
    monkeypatch.setenv("SOVRN_COMMERCE_API_KEY", "env_override_sovrn_api_key")
    assert hub.sovrn_api_key == "env_override_sovrn_api_key"

    # Override PartnerStack API key
    monkeypatch.setenv("PARTNERSTACK_API_KEY", "env_override_ps_key")
    assert hub.partnerstack_api_key == "env_override_ps_key"

    # Override Stripe account ID
    monkeypatch.setenv("STRIPE_ACCOUNT_ID", "acct_override_stripe_123")
    assert hub.stripe_account_id == "acct_override_stripe_123"


def test_ipx1031_section_1031_calculator_route():
    """Verifies that section-1031-calculator returns ipx1031 with start-an-exchange URL and required link attributes."""
    hub = MonetizationHub()
    route = hub.get_route("profithelm", "section-1031-calculator")

    expected_url = (
        "https://www.ipx1031.com/start-an-exchange/"
        "?utm_source=profithelm&utm_medium=referral&utm_campaign=section_1031_calculator"
    )
    assert route["partner"] == "ipx1031"
    assert route["url"] == expected_url
    assert route["rel"] == "noopener sponsored nofollow"
    assert route["target"] == "_blank"


def test_monetization_vault_atomic_save(tmp_path):
    """Verifies atomic vault save with fsync, timestamp update, and dash rejection."""
    vault_file = tmp_path / "test_vault.json"
    hub = MonetizationHub(vault_path=str(vault_file))

    # Save vault to disk
    hub.save_vault()
    assert vault_file.is_file()

    # Read back and verify valid JSON with 2-space indentation
    content = vault_file.read_text(encoding="utf-8")
    assert '  "hub_metadata":' in content
    data = json.loads(content)
    assert "updated_at" in data["hub_metadata"]

    # Modify data and save again
    hub.vault_data["hub_metadata"]["description"] = "Updated test vault"
    hub.save_vault()
    data2 = json.loads(vault_file.read_text(encoding="utf-8"))
    assert data2["hub_metadata"]["description"] == "Updated test vault"

    # Verify dash violation in save_vault raises ValueError
    hub.vault_data["hub_metadata"]["description"] = "Invalid em\u2014dash description"
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        hub.save_vault()


def test_sync_partner_program_updates_vault(tmp_path):
    """Verifies sync_partner_program updates vault category and resolves direct active route."""
    vault_file = tmp_path / "vault.json"
    hub = MonetizationHub(vault_path=str(vault_file))
    hub.save_vault()

    program_data = {
        "program_key": "rippling",
        "category": "PAYROLL_HR",
        "direct_url": "https://rippling.grsm.io/profithelm",
        "status": "approved",
        "bounty": "$600-$1600",
    }
    res = hub.sync_partner_program("partnerstack", program_data, property_id="profithelm", save=True)
    assert res["status"] == "updated"
    assert res["program_key"] == "rippling"
    assert res["ledger_status"] == "active_direct"

    # Verify vault data updated
    payroll_cat = hub.vault_data["properties"]["profithelm"]["categories"]["PAYROLL_HR"]
    assert payroll_cat["primary_partner"] == "rippling"
    assert payroll_cat["direct_url"] == "https://rippling.grsm.io/profithelm"
    assert payroll_cat["status"] == "active_direct"

    # Verify get_route reflects direct active partner and bypasses Sovrn fallback
    route = hub.get_route("profithelm", "saas-runway-calculator", partner_key="rippling")
    assert route["status"] == "active_direct"
    assert route["url"] == "https://rippling.grsm.io/profithelm"
    assert "redirect.viglink.com" not in route["url"]
    assert route["rel"] == "noopener sponsored nofollow"
    assert route["target"] == "_blank"


def test_sync_from_network_payload_idempotency(tmp_path):
    """Verifies batch payload ingestion and idempotency across repeated runs."""
    vault_file = tmp_path / "vault.json"
    hub = MonetizationHub(vault_path=str(vault_file))
    hub.save_vault()

    payload = {
        "network": "partnerstack",
        "property_id": "profithelm",
        "programs": [
            {
                "program_key": "rippling",
                "category": "PAYROLL_HR",
                "direct_url": "https://rippling.grsm.io/profithelm",
                "status": "approved",
                "bounty": "$600-$1600",
            },
            {
                "program_key": "mercury",
                "category": "STARTUP_BANKING",
                "direct_url": "https://mercury.com/?ref=profithelm",
                "status": "approved",
                "bounty": "$250",
            },
            {
                "program_key": "ramp",
                "category": "CORPORATE_SPEND",
                "direct_url": "https://ramp.com/?ref=profithelm",
                "status": "pending",
                "bounty": "$500",
            },
        ],
    }

    report1 = hub.sync_from_network_payload("partnerstack", payload, property_id="profithelm", save=True)
    assert report1["total_received"] == 3
    assert report1["updated"] == 2
    assert report1["skipped"] == 1
    assert len(report1["errors"]) == 0

    state1 = json.loads(vault_file.read_text(encoding="utf-8"))
    # Replay same payload
    report2 = hub.sync_from_network_payload("partnerstack", payload, property_id="profithelm", save=True)
    assert report2["total_received"] == 3
    assert report2["updated"] == 2
    assert report2["skipped"] == 1

    state2 = json.loads(vault_file.read_text(encoding="utf-8"))
    # Categories state must remain identical
    assert state1["properties"]["profithelm"]["categories"] == state2["properties"]["profithelm"]["categories"]


def test_sync_partner_program_rejects_prexvo_b2b():
    """Verifies Prexvo student loan isolation strictly rejects commercial B2B partners and unapproved categories."""
    hub = MonetizationHub()

    # Reject commercial B2B partner on Prexvo
    with pytest.raises(ValueError, match="Strict isolation violation: Commercial B2B partner 'mercury'"):
        hub.sync_partner_program(
            "partnerstack",
            {
                "program_key": "mercury",
                "category": "STUDENT_LOAN_REFINANCE",
                "direct_url": "https://mercury.com/?ref=prexvo",
                "status": "approved",
            },
            property_id="prexvo",
            save=False,
        )

    with pytest.raises(ValueError, match="Strict isolation violation: Commercial B2B partner 'rippling'"):
        hub.sync_partner_program(
            "partnerstack",
            {
                "program_key": "rippling",
                "category": "STUDENT_LOAN_REFINANCE",
                "direct_url": "https://rippling.com/?ref=prexvo",
                "status": "approved",
            },
            property_id="prexvo",
            save=False,
        )

    # Reject unapproved category on Prexvo
    with pytest.raises(ValueError, match="Strict isolation violation: Unapproved category 'PAYROLL_HR'"):
        hub.sync_partner_program(
            "in_house",
            {
                "program_key": "splash_financial",
                "category": "PAYROLL_HR",
                "direct_url": "https://splashfinancial.com/",
                "status": "approved",
            },
            property_id="prexvo",
            save=False,
        )

    # Reject aggregator fallback on Prexvo
    with pytest.raises(ValueError, match="Strict isolation violation: Sub-affiliate aggregator fallback"):
        hub.sync_partner_program(
            "sovrn_commerce",
            {
                "program_key": "sovrn_commerce",
                "category": "STUDENT_LOAN_REFINANCE",
                "direct_url": "https://example.com/",
                "status": "approved",
            },
            property_id="prexvo",
            save=False,
        )


def test_sync_partner_program_preserves_1031_exchange(tmp_path):
    """Verifies that 1031 exchange links preserve direct start-an-exchange URL and reject Sovrn wrapping."""
    vault_file = tmp_path / "vault.json"
    hub = MonetizationHub(vault_path=str(vault_file))
    hub.save_vault()

    direct_exchange_url = "https://www.ipx1031.com/start-an-exchange/?utm_source=profithelm&utm_medium=referral"
    program_data = {
        "program_key": "ipx1031",
        "category": "SECTION_1031_EXCHANGE",
        "direct_url": direct_exchange_url,
        "status": "approved",
        "bounty": "$250-$750",
    }
    res = hub.sync_partner_program("in_house", program_data, property_id="profithelm", save=True)
    assert res["ledger_status"] == "active_direct"

    route = hub.get_route("profithelm", "section-1031-calculator")
    assert route["partner"] == "ipx1031"
    assert route["url"] == direct_exchange_url
    assert "redirect.viglink.com" not in route["url"]
    assert route["status"] == "active_direct"

    # Reject wrapping 1031 exchange with Viglink
    wrapped_exchange = "https://redirect.viglink.com?key=somekey&u=https%3A%2F%2Fwww.ipx1031.com"
    with pytest.raises(ValueError, match="1031 exchange direct link must not be wrapped with Sovrn Viglink redirect"):
        hub.sync_partner_program(
            "in_house",
            {
                "program_key": "ipx1031",
                "category": "SECTION_1031_EXCHANGE",
                "direct_url": wrapped_exchange,
                "status": "approved",
            },
            property_id="profithelm",
            save=False,
        )


def test_sync_partner_program_rejects_forbidden_dashes(tmp_path):
    """Verifies that partner metadata with em-dashes or en-dashes is rejected."""
    hub = MonetizationHub()

    # Reject em-dash in name
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        hub.sync_partner_program(
            "partnerstack",
            {
                "program_key": "mercury",
                "category": "STARTUP_BANKING",
                "direct_url": "https://mercury.com/",
                "status": "approved",
                "name": "Mercury \u2014 Startup Banking",
            },
            property_id="profithelm",
            save=False,
        )

    # Reject en-dash in bounty
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        hub.sync_partner_program(
            "partnerstack",
            {
                "program_key": "mercury",
                "category": "STARTUP_BANKING",
                "direct_url": "https://mercury.com/",
                "status": "approved",
                "bounty": "$150\u2013$300",
            },
            property_id="profithelm",
            save=False,
        )


def test_sync_partner_program_ssrf_and_url_validation():
    """Verifies that localhost, link-local, loopback, and unsafe schemes are rejected."""
    hub = MonetizationHub()

    unsafe_urls = [
        "javascript:alert(1)",
        "http://localhost:8080/hook",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "data:text/html;base64,PHNjcmlwdD4=",
        "ftp://ftp.example.com/",
    ]

    for bad_url in unsafe_urls:
        with pytest.raises(ValueError, match="Invalid or unsafe affiliate URL"):
            hub.sync_partner_program(
                "partnerstack",
                {
                    "program_key": "mercury",
                    "category": "STARTUP_BANKING",
                    "direct_url": bad_url,
                    "status": "approved",
                },
                property_id="profithelm",
                save=False,
            )


def test_cli_sync_monetization_execution(tmp_path):
    """Verifies CLI sync-monetization execution with fixtures, dry-run, and json mode."""
    from pseofactory.cli import main

    payload_file = tmp_path / "test_payload.json"
    payload = {
        "network": "partnerstack",
        "property_id": "profithelm",
        "programs": [
            {
                "program_key": "rippling",
                "category": "PAYROLL_HR",
                "direct_url": "https://rippling.grsm.io/profithelm",
                "status": "approved",
                "bounty": "$600-$1600",
            }
        ],
    }
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    # Dry-run with JSON output
    exit_code = main([
        "sync-monetization",
        "--payload", str(payload_file),
        "--dry-run",
        "--json",
    ])
    assert exit_code == 0

    # Inline JSON string payload with dry-run
    exit_code_inline = main([
        "sync-monetization",
        "--payload", json.dumps(payload),
        "--dry-run",
    ])
    assert exit_code_inline == 0

    # Missing payload should fail
    exit_code_missing = main(["sync-monetization", "--json"])
    assert exit_code_missing == 1

    # Invalid JSON payload should fail
    exit_code_invalid = main(["sync-monetization", "--payload", "not-a-json", "--json"])
    assert exit_code_invalid == 1


def test_merchant_coverage_and_yield_audit():
    """Verifies that all ProfitHelm and Prexvo partner keys map to verified paying destinations with zero circular redirects."""
    from pseofactory.affiliates import SOVRN_VERIFIED_PAYING_MERCHANTS, audit_merchant_coverage_and_yield

    hub = MonetizationHub()
    report = hub.audit_merchant_coverage()
    assert report == audit_merchant_coverage_and_yield()
    assert report["status"] == "PASS"
    assert report["non_paying_passthrough_count"] == 0
    assert report["internal_loop_count"] == 0
    assert report["verified_paying_count"] >= 45

    px_report = audit_merchant_coverage_and_yield("prexvo")
    assert px_report["status"] == "PASS"
    assert px_report["non_paying_passthrough_count"] == 0
    assert px_report["internal_loop_count"] == 0
    assert px_report["verified_paying_count"] == 5

    for pk, m_info in SOVRN_VERIFIED_PAYING_MERCHANTS.items():
        assert m_info["approved"] is True, f"Partner {pk} must be approved"
        assert m_info["payout_rate"], f"Partner {pk} must have positive commission rate"
        assert m_info["verified_url"].startswith("https://"), f"Partner {pk} must have https URL"


def test_edge_redirect_generation_profithelm_and_prexvo():
    """Verifies edge redirect function generation for both ProfitHelm and Prexvo."""
    from pseofactory.edge import generate_edge_redirect_function

    ph_js = generate_edge_redirect_function("profithelm")
    assert 'defaultUrl: "https://coinledger.io/?fpr=arif-554004"' in ph_js
    assert 'defaultUrl: "https://mercury.com/r/profithelm-llc"' in ph_js
    assert 'defaultUrl: "https://www.taxact.com/"' in ph_js
    assert 'defaultUrl: "https://www.surepayroll.com/"' in ph_js
    assert 'defaultUrl: "https://www.xendoo.com/?fp_ref=arif-4ac24e"' in ph_js
    assert 'defaultUrl: "https://www.invoicesimple.com/"' in ph_js
    assert 'defaultUrl: "https://dlpcapital.com/"' in ph_js
    assert 'defaultUrl: "https://kalshi.pxf.io/c/7932737/3078072/37770"' in ph_js

    px_js = generate_edge_redirect_function("prexvo")
    assert 'defaultUrl: "https://www.splashfinancial.com/"' in px_js
    assert 'defaultUrl: "https://www.sofi.com/"' in px_js
    assert 'defaultUrl: "https://www.credible.com/"' in px_js
    assert 'defaultUrl: "https://www.earnest.com/"' in px_js
    assert 'defaultUrl: "https://www.lendkey.com/"' in px_js
    assert 'defaultUrl: "https://www.sofi.com/refinance-student-loan/"' in px_js
    assert 'status: "live"' in px_js
    assert 'status: "pending_p2"' not in px_js


def test_callout_destination_message_match_audit(tmp_path):
    """Verifies that every ProfitHelm and Prexvo partner card title, description, and CTA button matches its destination merchant."""
    from pseofactory.affiliates import (
        audit_callout_destination_message_match,
        normalize_html_callout_message_match,
    )

    hub = MonetizationHub()
    ph_match = hub.audit_callout_message_match(property_id="profithelm")
    assert ph_match == audit_callout_destination_message_match(property_id="profithelm")
    assert ph_match["status"] == "PASS", f"ProfitHelm message-match mismatches: {ph_match['mismatches']}"
    assert ph_match["mismatch_count"] == 0

    px_match = hub.audit_callout_message_match(property_id="prexvo")
    assert px_match["status"] == "PASS", f"Prexvo message-match mismatches: {px_match['mismatches']}"
    assert px_match["mismatch_count"] == 0

    # Negative check: stale replaced brand copy inside rendered HTML must fail closed until normalized
    stale_html = """<!DOCTYPE html>
<html><body>
  <div class="calculator-grid">Calculator</div>
  <section class="affiliates-section">
    <div class="card">
      <h3>Crest Capital Equipment Financing</h3>
      <a href="/r/crest_capital" class="btn-cta">Finance Section 179 Equipment with Crest Capital</a>
    </div>
  </section>
  <section class="faq-section">FAQ</section>
</body></html>"""
    sample_page = tmp_path / "tools" / "section-179-calculator" / "index.html"
    sample_page.parent.mkdir(parents=True, exist_ok=True)
    sample_page.write_text(stale_html, encoding="utf-8")

    fail_audit = audit_callout_destination_message_match(dist_dir=str(tmp_path), property_id="profithelm")
    assert fail_audit["status"] == "FAIL"
    assert fail_audit["mismatch_count"] >= 1
    assert fail_audit["above_fold_verified_pages"] == 1

    repaired_html = normalize_html_callout_message_match(stale_html, property_id="profithelm")
    assert "Xendoo" in repaired_html
    assert "Crest Capital" not in repaired_html
    sample_page.write_text(repaired_html, encoding="utf-8")

    pass_audit = audit_callout_destination_message_match(dist_dir=str(tmp_path), property_id="profithelm")
    assert pass_audit["status"] == "PASS"
    assert pass_audit["mismatch_count"] == 0
    assert pass_audit["above_fold_verified_pages"] == 1


def test_callout_expansion_for_prexvo_and_profithelm_approved_partners():
    """Verifies that normalize_html_callout_message_match expands Prexvo non-restricted refinance grids to all 5 live partners and enriches ProfitHelm crypto/R&D sections with Koinly and Rippling."""
    from pseofactory.affiliates import normalize_html_callout_message_match

    prexvo_single_partner_html = """<!DOCTYPE html>
<html><body>
  <section class="refinance-partner-section" aria-label="Refinance Option">
    <div class="partner-matrix-grid">
      <div class="card">
        <h3>Splash Financial Student Loan Refinancing</h3>
        <a href="/r/splash_financial" class="btn-cta">Compare Rates at Splash Financial</a>
      </div>
    </div>
  </section>
</body></html>"""
    expanded_prexvo = normalize_html_callout_message_match(prexvo_single_partner_html, property_id="prexvo")
    for route in ("/r/splash_financial", "/r/sofi", "/r/credible", "/r/earnest", "/r/lendkey"):
        assert route in expanded_prexvo, f"Expected {route} in expanded Prexvo callout section"

    # Restricted public-service pages must never receive commercial partner cards
    restricted_prexvo_html = prexvo_single_partner_html.replace(
        '<section class="refinance-partner-section"',
        '<section class="refinance-partner-section" data-restricted-public-service="true"',
    )
    unchanged_restricted = normalize_html_callout_message_match(restricted_prexvo_html, property_id="prexvo")
    assert "/r/credible" not in unchanged_restricted
    assert "/r/earnest" not in unchanged_restricted

    # ProfitHelm crypto tool page with only CoinLedger should also render approved Koinly
    profithelm_crypto_html = """<!DOCTYPE html>
<html><head><title>Crypto Tax Form 1099-DA Calculator</title></head><body>
  <section class="affiliates-section">
    <div class="card">
      <h3>CoinLedger Crypto Tax Automation</h3>
      <a href="/r/coinledger" class="btn-cta">Generate IRS Form 8949 with CoinLedger</a>
    </div>
  </section>
</body></html>"""
    expanded_crypto = normalize_html_callout_message_match(profithelm_crypto_html, property_id="profithelm")
    assert "/r/coinledger" in expanded_crypto
    assert "/r/koinly" in expanded_crypto

    # ProfitHelm R&D Section 174 page with only Mercury should also render approved Rippling
    profithelm_rnd_html = """<!DOCTYPE html>
<html><head><title>R&D Tax Credit Section 174 Amortization Calculator</title></head><body>
  <section class="affiliates-section">
    <div class="card">
      <h3>Mercury Business Banking</h3>
      <a href="/r/mercury" class="btn-cta">Open a Mercury Account</a>
    </div>
  </section>
</body></html>"""
    expanded_rnd = normalize_html_callout_message_match(profithelm_rnd_html, property_id="profithelm")
    assert "/r/mercury" in expanded_rnd
    assert "/r/rippling" in expanded_rnd


def test_visitor_journey_cta_placement_and_live_first_ordering():
    """Verifies inline calculator result CTA injection, live-first ordering, and removal of pending/footer-polluted mismatches."""
    import re
    from pseofactory.affiliates import normalize_html_callout_message_match

    # 1. Prediction-market odds page replaces pending Interactive Brokers with active approved Kalshi, CoinLedger, and Koinly
    pred_odds_html = """<!DOCTYPE html>
<html><head><title>Prediction Market Odds & Arbitrage Calculator</title></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card"><div class="card-header"><h2>Arbitrage Outputs</h2></div><div class="metric-grid"></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Partners</h2>
    <div class="affiliate-card partner-card">
      <div class="affiliate-info"><h3>Zacks Quantitative Yield & Investment Research</h3></div>
      <div><a href="/r/interactive_brokers" class="btn-cta">Access Quantitative Yield Research on Zacks</a></div>
    </div>
    <div class="affiliate-card partner-card">
      <div class="affiliate-info"><h3>Kalshi CFTC-Regulated Event Contract Exchange</h3></div>
      <div><a href="/r/kalshi" class="btn-cta">Trade Regulated Event Contracts on Kalshi</a></div>
    </div>
  </section>
</body></html>"""
    norm_pred = normalize_html_callout_message_match(pred_odds_html, property_id="profithelm")
    assert 'class="calc-inline-cta"' in norm_pred
    assert 'data-cta-slot="calculator_result_inline"' in norm_pred
    r_links = re.findall(r'href="/r/([a-z0-9_]+)', norm_pred)
    assert r_links[0] == "kalshi"
    assert r_links[1] == "kalshi"
    assert "interactive_brokers" not in r_links
    assert "coinledger" in r_links
    assert "koinly" in r_links

    # 2. Section 179 / Equipment Lease page strips mismatched Kalshi/National Funding Med and orders live Section 179 specialist Xendoo (crest_capital) first, followed by Mercury and Rippling
    sec179_html = """<!DOCTYPE html>
<html><head><title>Section 179 Deduction Calculator</title><link rel="canonical" href="https://profithelm.com/tools/equipment-lease-vs-buy-section-179-calculator/" /></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card result-card"><div class="card-header"><h2>Projected First-Year Tax Savings</h2></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Partners</h2>
    <div class="affiliate-card partner-card"><a href="/r/crest_capital" class="btn-cta">Optimize Section 179 Accounting with Xendoo</a></div>
    <div class="affiliate-card partner-card"><a href="/r/national_funding_med" class="btn-cta">Upgrade Practice Billing & Payments with Stax</a></div>
    <div class="affiliate-card partner-card"><a href="/r/mercury" class="btn-cta">Apply for Mercury Startup Banking</a></div>
    <div class="affiliate-card partner-card"><a href="/r/kalshi" class="btn-cta">Trade Regulated Event Contracts on Kalshi</a></div>
  </section>
  <footer><a href="/tools/prediction-market-odds/">Kalshi Prediction Market Odds</a></footer>
</body></html>"""
    norm_179 = normalize_html_callout_message_match(sec179_html, property_id="profithelm")
    r_179 = re.findall(r'href="/r/([a-z0-9_]+)', norm_179)
    assert "kalshi" not in r_179
    assert "national_funding_med" not in r_179
    assert r_179[0] == "crest_capital"
    assert r_179[1] == "crest_capital"
    assert r_179.index("crest_capital") < r_179.index("mercury") < r_179.index("rippling")
    assert "source_tool=equipment-lease-vs-buy-section-179-calculator" in norm_179
    assert "subid=equipment-lease-vs-buy-section-179-calculator_inline" in norm_179
    assert 'data-tool="equipment-lease-vs-buy-section-179-calculator"' in norm_179


def test_gsc_traffic_weighted_ranking_and_xendoo_live_tax_bracket_alignment():
    """Verifies Xendoo FirstPromoter direct routing, general tax bracket CTA alignment, and GSC traffic-weighted revenue ranking."""
    import re
    from pseofactory.affiliates import (
        estimate_partner_approval_revenue_impact,
        normalize_html_callout_message_match,
    )
    from pseofactory.edge import generate_edge_redirect_function

    ph_js = generate_edge_redirect_function("profithelm")
    assert 'defaultUrl: "https://www.xendoo.com/?fp_ref=arif-4ac24e"' in ph_js

    tax_bracket_html = """<!DOCTYPE html>
<html><head><title>2027 California Tax Brackets & Marginal Tax Calculator</title></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card result-card"><div class="card-header"><h2>Combined 2027 Tax Projection</h2></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Verified Tax Execution Partners</h2>
    <div class="affiliate-card partner-card"><a href="/r/coinledger" class="btn-cta">Calculate & Export Crypto Taxes with CoinLedger</a></div>
    <div class="affiliate-card partner-card"><a href="/r/koinly" class="btn-cta">Track Crypto Portfolios with Koinly</a></div>
    <div class="affiliate-card partner-card"><a href="/r/taxslayer" class="btn-cta">Calculate & File with TaxSlayer</a></div>
    <div class="affiliate-card partner-card"><a href="/r/turbotax" class="btn-cta">Calculate & File Taxes Online with TaxAct</a></div>
  </section>
</body></html>"""
    norm_tax = normalize_html_callout_message_match(tax_bracket_html, property_id="profithelm")
    r_tax = re.findall(r'href="/r/([a-z0-9_]+)', norm_tax)
    assert "coinledger" not in r_tax
    assert "koinly" not in r_tax
    assert "turbotax" not in r_tax
    assert "taxslayer" not in r_tax
    assert r_tax[0] == "crest_capital"
    assert r_tax[1] == "crest_capital"
    assert r_tax.index("crest_capital") < r_tax.index("rippling") < r_tax.index("mercury")
    assert 'data-partner="crest_capital" data-status="live"' in norm_tax
    assert 'data-status="pending"' not in norm_tax

    imp_turbotax = estimate_partner_approval_revenue_impact("profithelm", "turbotax")
    imp_taxslayer = estimate_partner_approval_revenue_impact("profithelm", "taxslayer")
    imp_exeter = estimate_partner_approval_revenue_impact("profithelm", "exeter1031")
    imp_surety = estimate_partner_approval_revenue_impact("profithelm", "suretybonds_direct")

    assert imp_turbotax["affected_traffic_impressions"] == 2740
    assert imp_taxslayer["affected_traffic_impressions"] == 2566
    assert imp_turbotax["estimated_monthly_revenue_impact_usd"] > imp_taxslayer["estimated_monthly_revenue_impact_usd"]
    assert imp_taxslayer["estimated_monthly_revenue_impact_usd"] > imp_exeter["estimated_monthly_revenue_impact_usd"]
    assert imp_exeter["estimated_monthly_revenue_impact_usd"] > imp_surety["estimated_monthly_revenue_impact_usd"]

    # Verify #gsc-striking-overlay on tax bracket pages upgrades pending taxslayer to live crest_capital (Xendoo)
    tax_overlay_html = """<!DOCTYPE html>
<html><head><title>2027 IRS Tax Brackets & TCJA Sunset Calculator</title></head><body>
  <aside class="quick-answer">
    <div class="quick-answer-title">Key Finding: 2027 IRS Sunset Projection</div>
    <p>Original quick answer text.</p>
  </aside>
  <div id="gsc-striking-overlay" class="striking-distance-overlay" data-slug="irs-2027-tax-brackets">
    <section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="profithelm" data-partner="taxslayer" data-partner-url="https://www.taxslayer.com/">
      <h3 class="section-subtitle">Recommended Partner Solution: TaxSlayer Self-Employed Tax Filing</h3>
      <p class="overlay-partner-desc">File federal and state self-employed tax returns.</p>
      <a href="/r/taxslayer" class="btn-cta" rel="noopener sponsored nofollow" target="_blank">Calculate &amp; File with TaxSlayer</a>
    </section>
  </div>
</body></html>"""
    norm_overlay = normalize_html_callout_message_match(tax_overlay_html, property_id="profithelm")
    assert 'data-partner="crest_capital"' in norm_overlay
    assert 'data-status="live"' in norm_overlay
    assert 'data-partner-url="https://www.xendoo.com/?fp_ref=arif-4ac24e"' in norm_overlay
    assert 'href="/r/crest_capital' in norm_overlay
    assert "Optimize Section 179 Accounting with Xendoo" in norm_overlay


def test_full_estate_monetization_realignment_zero_unpaid_fallbacks():
    """Verifies that Section 1031, Section 174, Treasury Yield, Surety Bond, Homepage, and Prexvo overlays upgrade all pending/placeholder slots to active approved sponsors."""
    import re
    from pseofactory.affiliates import normalize_html_callout_message_match

    # 1. Section 1031 state spoke routes to live Qualified Intermediary ipx1031 first (inline, card #1, and overlay), followed by crest_capital and mercury
    sec1031_html = """<!DOCTYPE html>
<html><head><title>Alabama 1031 Exchange Calculator</title><link rel="canonical" href="https://profithelm.com/tools/section-1031-calculator/alabama/" /></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card result-card"><div class="card-header"><h2>Deferred Capital Gains</h2></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Recommended 1031 Partners</h2>
    <div class="affiliate-card partner-card"><a href="/r/ipx1031" class="btn-cta">Initiate Qualified 1031 Exchange with IPX1031</a></div>
    <div class="affiliate-card partner-card"><a href="/r/exeter1031" class="btn-cta" data-status="pending">Explore DLP Capital</a></div>
    <div class="affiliate-card partner-card"><a href="/r/first_american" class="btn-cta" data-status="pending">Invest on GROUNDFLOOR</a></div>
  </section>
  <div id="gsc-striking-overlay" class="gsc-overlay-container">
    <section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="profithelm" data-partner="ipx1031" data-partner-url="https://www.ipx1031.com/?utm_source=profithelm&amp;utm_medium=referral">
      <h3 class="section-subtitle">Recommended Partner Solution: IPX1031 Qualified Intermediary</h3>
      <a href="https://www.ipx1031.com/?utm_source=profithelm&amp;utm_medium=referral" class="btn-cta" rel="noopener sponsored nofollow" target="_blank">Open a Qualified 1031 Exchange Escrow Account</a>
    </section>
  </div>
</body></html>"""
    norm_1031 = normalize_html_callout_message_match(sec1031_html, property_id="profithelm")
    r_1031 = re.findall(r'href="/r/([a-z0-9_]+)', norm_1031)
    assert r_1031 == ["ipx1031", "ipx1031", "crest_capital", "mercury", "ipx1031"]
    assert 'data-status="pending"' not in norm_1031
    assert "source_tool=section-1031-calculator-alabama" in norm_1031
    assert "subid=section-1031-calculator-alabama_inline" in norm_1031
    assert "subid=section-1031-calculator-alabama_overlay" in norm_1031

    # 2. Prexvo calculator overlay upgrades legacy sofi_refi UTM placeholder to live splash_financial (/r/splash_financial)
    prexvo_ov_html = """<!DOCTYPE html>
<html><head><title>Student Loan Repayment Calculator</title><link rel="canonical" href="https://prexvo.com/tools/student-loan-repayment-calculator/" /></head><body>
  <div id="gsc-striking-overlay" class="gsc-overlay-container" data-slug="student-loan-repayment-calculator">
    <section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="prexvo" data-partner="sofi_refi" data-partner-url="https://www.sofi.com/refinance-student-loan/?utm_source=prexvo&amp;utm_medium=affiliate">
      <h3 class="section-subtitle">Recommended Partner Solution: SoFi Student Loan Refinancing</h3>
      <a href="https://www.sofi.com/refinance-student-loan/?utm_source=prexvo&amp;utm_medium=affiliate" class="btn-cta" rel="noopener sponsored nofollow" target="_blank">Check Refinance Rates Without Credit Impact</a>
    </section>
  </div>
</body></html>"""
    norm_px = normalize_html_callout_message_match(prexvo_ov_html, property_id="prexvo")
    assert 'data-partner="splash_financial"' in norm_px
    assert 'href="/r/splash_financial' in norm_px
    assert "source_tool=student-loan-repayment-calculator" in norm_px
    assert "subid=student-loan-repayment-calculator_overlay" in norm_px
    assert 'data-status="live"' in norm_px
    assert "utm_source=prexvo" not in norm_px

    # 3. Homepage standalone affiliate-cta-section replaces stale TaxAct button label with Xendoo and injects above-the-fold FTC disclosure banner
    homepage_html = """<!DOCTYPE html>
<html><head><title>ProfitHelm Tax & Capital Allocation Hub</title><link rel="canonical" href="https://profithelm.com/" /></head><body>
  <main class="main">
    <section class="hero-section"><h1>Precision Tax Models</h1></section>
    <section class="affiliate-cta-section card pseo-card" data-property="profithelm" data-partner="crest_capital" data-mechanic="compliant_intent_monetization">
      <h2>Verified Commercial Execution Partner: Xendoo Section 179 & Business Tax Accounting</h2>
      <p><a href="/r/crest_capital" rel="noopener sponsored nofollow" target="_blank" class="affiliate-cta-link touch-target" data-status="live">Calculate & File Taxes Online with TaxAct</a></p>
    </section>
  </main>
</body></html>"""
    norm_home = normalize_html_callout_message_match(homepage_html, property_id="profithelm")
    assert "Calculate & File Taxes Online with TaxAct" not in norm_home
    assert "Optimize Section 179 Accounting with Xendoo" in norm_home
    assert 'class="ftc-disclosure-banner"' in norm_home
    assert "source_tool=homepage" in norm_home
    assert "subid=homepage_cta" in norm_home


def test_edge_redirect_subid_forwarding_and_telemetry_persistence(tmp_path):
    """
    Verifies via Node.js and Python that:
    1. /r/:partner normalizes amp;-prefixed query params, forwards CJ sid, Impact subId1/sharedid,
       and UTM parameters, and records server-side click telemetry to KV and in-memory buffer.
    2. /api/telemetry persists and exports events across PROFITHELM_TELEMETRY_KV, PROFITHELM_LEADS,
       and the in-isolate buffer (for Prexvo).
    3. visual_primitives runtime synchronizer dispatches affiliate_click beacons unconditionally
       on both ProfitHelm and Prexvo without requiring /static/js/app.js.
    """
    import subprocess
    import pseofactory.edge as edge_mod
    from pseofactory.edge import (
        generate_edge_redirect_function,
        sync_tenant_edge_redirect_function,
    )
    from pseofactory.visual_primitives import (
        detect_visual_and_ux_contract_issues,
        normalize_html_visual_primitives,
        render_runtime_synchronizer_script,
    )

    # 1. Verify sync_tenant_edge_redirect_function writes both functions/r/[partner].js and functions/api/telemetry.js
    assert hasattr(edge_mod, "generate_edge_telemetry_function")
    for prop in ("profithelm", "prexvo"):
        repo_dir = tmp_path / prop
        (repo_dir / "functions" / "r").mkdir(parents=True, exist_ok=True)
        res = sync_tenant_edge_redirect_function(repo_dir, property_id=prop)
        assert res["status"] == "UPDATED"
        assert (repo_dir / "functions" / "r" / "[partner].js").is_file()
        assert (repo_dir / "functions" / "api" / "telemetry.js").is_file()

    # 2. Execute Node.js verification against generated ProfitHelm and Prexvo edge functions
    ph_r = tmp_path / "profithelm" / "functions" / "r" / "[partner].js"
    ph_tel = tmp_path / "profithelm" / "functions" / "api" / "telemetry.js"
    px_r = tmp_path / "prexvo" / "functions" / "r" / "[partner].js"
    px_tel = tmp_path / "prexvo" / "functions" / "api" / "telemetry.js"

    node_script = f"""
    (async () => {{
      const phRedirect = await import({json.dumps(ph_r.as_uri())});
      const phTelemetry = await import({json.dumps(ph_tel.as_uri())});
      const pxRedirect = await import({json.dumps(px_r.as_uri())});
      const pxTelemetry = await import({json.dumps(px_tel.as_uri())});

      // Test A: ProfitHelm /r/kalshi with HTML-encoded &amp; query params and PROFITHELM_LEADS KV fallback
      const leadsKV = {{}};
      const phEnv = {{
        PROFITHELM_LEADS: {{
          put: async (k, v) => {{ leadsKV[k] = v; }},
          list: async (opts) => ({{
            keys: Object.keys(leadsKV).filter(k => k.startsWith(opts.prefix || "evt_")).map(name => ({{ name }})),
            list_complete: true
          }}),
          get: async (k) => leadsKV[k]
        }}
      }};

      const kalshiReq = new Request("https://profithelm.com/r/kalshi?source_tool=prediction-market-odds&amp;cta_slot=calculator_result_inline&amp;ph_tier=enterprise");
      const kalshiRes = await phRedirect.onRequest({{
        request: kalshiReq,
        env: phEnv,
        params: {{ partner: "kalshi" }}
      }});
      if (kalshiRes.status !== 302) process.exit(10);
      const kalshiLoc = new URL(kalshiRes.headers.get("Location"));
      if (kalshiLoc.hostname !== "kalshi.pxf.io") process.exit(11);
      if (kalshiLoc.searchParams.get("subid") !== "prediction-market-odds_calculator_result_inline") process.exit(12);
      if (kalshiLoc.searchParams.get("subId1") !== "prediction-market-odds_calculator_result_inline") process.exit(13);
      if (kalshiLoc.searchParams.get("sharedid") !== "prediction-market-odds") process.exit(14);
      if (kalshiLoc.searchParams.get("ph_tier") !== "enterprise") process.exit(15);
      if (kalshiRes.headers.get("X-Edge-Telemetry") !== "recorded") process.exit(16);

      // Test B: ProfitHelm /r/efile CJ Affiliate link forwards sid parameter
      const cjReq = new Request("https://profithelm.com/r/efile?source_tool=irs-2027-tax-brackets&cta_slot=partner_card_1");
      const cjRes = await phRedirect.onRequest({{
        request: cjReq,
        env: phEnv,
        params: {{ partner: "efile" }}
      }});
      if (cjRes.status !== 302) process.exit(20);
      const cjLoc = new URL(cjRes.headers.get("Location"));
      if (cjLoc.hostname !== "www.jdoqocy.com") process.exit(21);
      if (cjLoc.searchParams.get("sid") !== "irs-2027-tax-brackets_partner_card_1") process.exit(22);
      if (cjLoc.searchParams.get("subid") !== "irs-2027-tax-brackets_partner_card_1") process.exit(23);

      // Verify server-side edge clicks were persisted to PROFITHELM_LEADS KV and are returned by GET /api/telemetry
      const getPhRes = await phTelemetry.onRequestGet({{
        request: new Request("https://profithelm.com/api/telemetry"),
        env: phEnv
      }});
      const getPhData = await getPhRes.json();
      if (!getPhData.ok || getPhData.count < 2) process.exit(30);
      const recordedPartners = getPhData.events.map(e => e.partner_key);
      if (!recordedPartners.includes("kalshi") || !recordedPartners.includes("efile")) process.exit(31);

      // Test C: Prexvo /r/splash_financial + POST /api/telemetry without KV binding uses in-isolate buffer
      globalThis.__PSEOFACTORY_TELEMETRY_BUFFER__ = [];
      const pxReq = new Request("https://prexvo.com/r/splash_financial?source_tool=student-loan-repayment-calculator&amp;cta_slot=calculator_result_inline&amp;ph_tier=high_balance");
      const pxRes = await pxRedirect.onRequest({{
        request: pxReq,
        env: {{}},
        params: {{ partner: "splash_financial" }}
      }});
      if (pxRes.status !== 302) process.exit(40);
      const pxLoc = new URL(pxRes.headers.get("Location"));
      if (pxLoc.hostname !== "www.splashfinancial.com") process.exit(41);
      if (pxLoc.searchParams.get("subid") !== "student-loan-repayment-calculator_calculator_result_inline") process.exit(42);
      if (pxLoc.searchParams.get("ref") !== "prexvo") process.exit(43);

      const beaconReq = new Request("https://prexvo.com/api/telemetry", {{
        method: "POST",
        headers: {{ "Content-Type": "text/plain;charset=UTF-8" }},
        body: JSON.stringify({{
          event_type: "affiliate_click",
          tool_slug: "rap-payment-calculator",
          partner_key: "sofi",
          cta_slot: "partner_card_2",
          subid: "rap-payment-calculator_card_2",
          value_tier: "standard"
        }})
      }});
      const beaconRes = await pxTelemetry.onRequestPost({{ request: beaconReq, env: {{}} }});
      const beaconData = await beaconRes.json();
      if (!beaconData.ok || beaconData.partner_key !== "sofi") process.exit(44);

      const getPxRes = await pxTelemetry.onRequestGet({{
        request: new Request("https://prexvo.com/api/telemetry"),
        env: {{}}
      }});
      const getPxData = await getPxRes.json();
      if (!getPxData.ok || getPxData.count !== 2) process.exit(45);
      process.exit(0);
    }})().catch(err => {{ console.error(err); process.exit(99); }});
    """
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node edge redirect & telemetry test failed (exit {proc.returncode}): {proc.stderr}"

    # 3. Verify visual_primitives runtime synchronizer script no longer gates sendBeacon on /static/js/app.js
    sync_js = render_runtime_synchronizer_script()
    assert 'document.querySelector(\'script[src*="/static/js/app.js"]\')' not in sync_js
    assert 'navigator.sendBeacon("/api/telemetry"' in sync_js
    assert 'window.fetch("/api/telemetry"' in sync_js

    stale_doc = (
        '<!DOCTYPE html><html><head></head><body>'
        '<form class="calculator-form"><input type="number" name="amount" value="1000" min="0" max="10000" step="100" aria-label="Amount"></form>'
        '<a href="/r/splash_financial?source_tool=rap-payment-calculator" data-partner="splash_financial">Refinance</a>'
        + sync_js.replace(
            "var sentBeacon = false;",
            'if (document.querySelector(\'script[src*="/static/js/app.js"]\')) {} var sentBeacon = false;',
        )
        + "</body></html>"
    )
    issues = detect_visual_and_ux_contract_issues(stale_doc, require_primitives=True)
    assert any("calculator synchronizer" in i for i in issues)
    healed_doc, repairs = normalize_html_visual_primitives(stale_doc, is_tenant_porcelain=True)
    assert "interactive_runtime_sync" in repairs
    assert 'document.querySelector(\'script[src*="/static/js/app.js"]\')' not in healed_doc


def test_direct_contract_yield_upgrades_and_b2b_fallback_realignment(tmp_path):
    """
    Verifies that:
    1. /r/crest_capital upgrades from $250 FirstPromoter to $500 Impact.com Xendoo (#16354)
       with subId1 and sharedid attribution and X-Edge-Contract-Tier: direct_contract_upgraded.
    2. /r/turbotax, /r/taxslayer, /r/freetaxusa, and /r/suretybonds_direct upgrade from
       Sovrn wrappers to direct approved CJ Affiliate contracts (E-file.com #4355234,
       ezTaxReturn.com #6874782, LawDepot #4544498) with sid attribution.
    3. /r/ipx1031 routes through Sovrn Commerce DLP Capital ($250/lead) with cuid attribution
       when env.AFFILIATE_IPX1031_URL is not set, eliminating $0 unmonetized UTM leaks.
    4. Section 174 R&D and B2B commercial calculators prioritize highest-CPA live contracts
       (crest_capital $500 CPA and rippling $600-$1,600 CPA ahead of mercury $250 CPA).
    """
    import re
    import subprocess
    from pseofactory.affiliates import (
        INTENT_ROUTING_TABLE,
        normalize_html_callout_message_match,
    )
    from pseofactory.edge import sync_tenant_edge_redirect_function

    repo_dir = tmp_path / "profithelm"
    (repo_dir / "functions" / "r").mkdir(parents=True, exist_ok=True)
    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    ph_r = repo_dir / "functions" / "r" / "[partner].js"

    node_script = f"""
    (async () => {{
      const phRedirect = await import({json.dumps(ph_r.as_uri())});

      // 1. crest_capital -> Impact Xendoo #16354 ($500 CPA)
      const crestRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/crest_capital?source_tool=equipment-lease-calculator&cta_slot=calculator_result_inline&subid=equipment-lease-calculator_inline&ph_tier=enterprise"),
        env: {{}},
        params: {{ partner: "crest_capital" }}
      }});
      if (crestRes.status !== 302) process.exit(10);
      const crestLoc = new URL(crestRes.headers.get("Location"));
      if (crestLoc.hostname !== "xendoo.pxf.io" || !crestLoc.pathname.includes("/16354")) process.exit(11);
      if (crestLoc.searchParams.get("subId1") !== "equipment-lease-calculator_inline") process.exit(12);
      if (crestLoc.searchParams.get("sharedid") !== "equipment-lease-calculator") process.exit(13);
      if (crestRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(14);

      // 2. turbotax -> CJ E-file.com #4355234 (30%-40% commission)
      const ttRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/turbotax?source_tool=irs-2027-tax-brackets-tcja-sunset-calculator&cta_slot=partner_card_1"),
        env: {{}},
        params: {{ partner: "turbotax" }}
      }});
      const ttLoc = new URL(ttRes.headers.get("Location"));
      if (ttLoc.hostname !== "www.jdoqocy.com" || !ttLoc.pathname.includes("click-101906407-11917161")) process.exit(20);
      if (ttLoc.searchParams.get("sid") !== "irs-2027-tax-brackets-tcja-sunset-calculator_partner_card_1") process.exit(21);
      if (ttRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(22);

      // 3. taxslayer -> CJ ezTaxReturn.com #6874782 (15% commission)
      const tsRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/taxslayer?source_tool=california-tax-brackets-calculator&cta_slot=partner_card_2"),
        env: {{}},
        params: {{ partner: "taxslayer" }}
      }});
      const tsLoc = new URL(tsRes.headers.get("Location"));
      if (tsLoc.hostname !== "www.dpbolvw.net" || !tsLoc.pathname.includes("click-101906407-15704796")) process.exit(30);
      if (tsLoc.searchParams.get("sid") !== "california-tax-brackets-calculator_partner_card_2") process.exit(31);

      // 4. suretybonds_direct -> CJ LawDepot #4544498 (30% + $6.50 Free Trial)
      const sbRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/suretybonds_direct?source_tool=contractor-surety-bond-cost-calculator&cta_slot=partner_card_1"),
        env: {{}},
        params: {{ partner: "suretybonds_direct" }}
      }});
      const sbLoc = new URL(sbRes.headers.get("Location"));
      if (sbLoc.hostname !== "www.jdoqocy.com" || !sbLoc.pathname.includes("click-101906407-16985242")) process.exit(40);
      if (sbLoc.searchParams.get("sid") !== "contractor-surety-bond-cost-calculator_partner_card_1") process.exit(41);

      // 5. ipx1031 -> Impact Xendoo #16354 ($500 CPA) by default while Sovrn Commerce is Denied and Impact DLP Capital is pending
      const ipxDirectRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/ipx1031?source_tool=1031-exchange-boot-calculator-california&cta_slot=calculator_result_inline&subid=1031-exchange-boot-calculator-california_inline"),
        env: {{}},
        params: {{ partner: "ipx1031" }}
      }});
      const ipxDirectLoc = new URL(ipxDirectRes.headers.get("Location"));
      if (ipxDirectLoc.hostname !== "xendoo.pxf.io" || !ipxDirectLoc.pathname.includes("/16354")) process.exit(48);
      if (ipxDirectLoc.searchParams.get("subId1") !== "1031-exchange-boot-calculator-california_inline") process.exit(49);
      if (ipxDirectRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(54);

      // 6. ipx1031 -> Sovrn Commerce DLP Capital ($250/lead) when SOVRN_COMMERCE_APPROVED=true and env.AFFILIATE_IPX1031_URL is unset
      const ipxRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/ipx1031?source_tool=1031-exchange-boot-calculator-california&cta_slot=calculator_result_inline&subid=1031-exchange-boot-calculator-california_inline"),
        env: {{ SOVRN_COMMERCE_APPROVED: "true" }},
        params: {{ partner: "ipx1031" }}
      }});
      const ipxLoc = new URL(ipxRes.headers.get("Location"));
      if (ipxLoc.hostname !== "redirect.viglink.com") process.exit(50);
      if (!ipxLoc.searchParams.get("u").startsWith("https://dlpcapital.com/")) process.exit(51);
      if (ipxLoc.searchParams.get("cuid") !== "1031-exchange-boot-calculator-california_inline") process.exit(52);
      if (ipxRes.headers.get("X-Edge-Contract-Tier") !== "sovrn_fallback") process.exit(53);

      process.exit(0);
    }})().catch(err => {{ console.error(err); process.exit(99); }});
    """
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Direct contract upgrade Node test failed (exit {proc.returncode}): {proc.stderr}"

    # Verify Section 174 R&D calculator aligns inline, card 1, and overlay to crest_capital ($500 CPA) then rippling ($600-$1,600 CPA)
    sec174_html = """<!DOCTYPE html>
<html><head><title>R&D Tax Credit & Section 174 Amortization Calculator</title><link rel="canonical" href="https://profithelm.com/tools/r-and-d-tax-credit-section-174-amortization-calculator/" /></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card result-card"><div class="card-header"><h2>Section 174 Amortization Schedule</h2></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Partners</h2>
    <div class="affiliate-card partner-card"><a href="/r/mercury" class="btn-cta">Apply for Mercury</a></div>
  </section>
  <div id="gsc-striking-overlay" class="gsc-overlay-container">
    <section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="profithelm" data-partner="mercury">
      <a href="/r/mercury" class="btn-cta">Apply for Mercury</a>
    </section>
  </div>
</body></html>"""
    norm_174 = normalize_html_callout_message_match(sec174_html, property_id="profithelm")
    r_174 = re.findall(r'href="/r/([a-z0-9_]+)', norm_174)
    assert r_174 == ["crest_capital", "crest_capital", "rippling", "mercury", "crest_capital"]

    # Verify B2B commercial calculators prioritize rippling ($600-$1,600 CPA) then crest_capital ($500 CPA) ahead of mercury ($250 CPA)
    b2b_html = """<!DOCTYPE html>
<html><head><title>Invoice Factoring vs Business Line of Credit Calculator</title><link rel="canonical" href="https://profithelm.com/tools/invoice-factoring-vs-business-line-of-credit-calculator/" /></head><body>
  <div class="calculator-grid">
    <div class="card"><div class="card-header"><h2>Inputs</h2></div></div>
    <div class="card result-card"><div class="card-header"><h2>Effective APR Comparison</h2></div></div>
  </div>
  <section class="affiliate-section affiliates-section">
    <h2>Partners</h2>
    <div class="affiliate-card partner-card"><a href="/r/mercury" class="btn-cta">Apply for Mercury</a></div>
  </section>
  <div id="gsc-striking-overlay" class="gsc-overlay-container">
    <section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="profithelm" data-partner="mercury">
      <a href="/r/mercury" class="btn-cta">Apply for Mercury</a>
    </section>
  </div>
</body></html>"""
    norm_b2b = normalize_html_callout_message_match(b2b_html, property_id="profithelm")
    r_b2b = re.findall(r'href="/r/([a-z0-9_]+)', norm_b2b)
    assert r_b2b == ["rippling", "rippling", "crest_capital", "mercury", "rippling"]
    assert INTENT_ROUTING_TABLE["workers-comp"][0] == "rippling"
    assert INTENT_ROUTING_TABLE["invoice-factoring"][0] == "crest_capital"
    assert INTENT_ROUTING_TABLE["tariff-landed-cost"][0] == "rippling"


def test_automatic_multi_company_partner_roster_binding_across_new_and_existing_verticals():
    """Verifies that any new or existing asset automatically binds a diversified multi-company partner roster (Primary, Secondary, Fallback)."""
    from pseofactory.affiliates import bind_asset_partner_roster

    hub = MonetizationHub()

    greenfield_assets = [
        ("profithelm", "autonomous-warehouse-robotics-roi-calculator", "warehouse robotics capex equipment lease section 179 calculator", "section_179_equipment_capex", 3),
        ("profithelm", "multi-state-remote-payroll-burden-estimator", "multi state remote employee payroll burden gusto rippling calculator", "workers_comp_labor_burden", 3),
        ("profithelm", "commercial-triple-net-1031-boot-simulator", "triple net lease 1031 exchange boot tax deferral calculator", "1031_like_kind_exchange", 3),
        ("profithelm", "defi-validator-yield-8949-tax-calculator", "crypto staking validator form 8949 tax reconciliation calculator", "crypto_digital_asset_tax", 3),
        ("profithelm", "pass-through-qbi-199a-phaseout-estimator", "irs section 199a qbi deduction tax filing calculator", "federal_state_tax_brackets", 3),
        ("profithelm", "municipal-bid-performance-bond-premium-calculator", "contractor performance surety bond cost calculator", "surety_bond_compliance", 3),
        ("profithelm", "fomc-rate-cut-event-contract-kelly-calculator", "kalshi fomc rate cut event contract probability kelly calculator", "prediction_market_event_contracts", 3),
        ("prexvo", "medical-residency-private-student-loan-refinance-calculator", "private student loan refinance interest rate comparison calculator", "student_loan_refinancing", 5),
    ]

    for prop_id, slug, query, expected_vertical, min_companies in greenfield_assets:
        roster = hub.bind_partner_roster(property_id=prop_id, slug=slug, query=query)
        assert roster["vertical_family"] == expected_vertical, f"Unexpected vertical for {slug}: {roster['vertical_family']}"
        assert roster["restricted_public_service"] is False
        assert roster["distinct_companies_count"] >= min_companies, (
            f"Expected >= {min_companies} distinct companies for {slug}, got {roster['distinct_companies']}"
        )
        assert isinstance(roster["primary_offer"], dict) and roster["primary_offer"].get("partner_key")
        assert isinstance(roster["secondary_offers"], list) and len(roster["secondary_offers"]) >= 1
        assert isinstance(roster["fallback_offer"], dict) and roster["fallback_offer"].get("partner_key")

        # Primary, first secondary, and fallback must represent distinct company brands
        primary_brand = roster["primary_offer"]["company_brand"]
        sec_brand = roster["secondary_offers"][0]["company_brand"]
        fallback_brand = roster["fallback_offer"]["company_brand"]
        assert len({primary_brand, sec_brand, fallback_brand}) == 3

    # Verify YMYL statutory Prexvo asset suppresses all commercial partner offers
    ymyl_roster = bind_asset_partner_roster(
        property_id="prexvo",
        slug="pslf-qualifying-payment-buyback-estimator",
        query="pslf buyback qualifying payment statutory forgiveness calculator",
    )
    assert ymyl_roster["restricted_public_service"] is True
    assert ymyl_roster["distinct_companies_count"] == 0
    assert ymyl_roster["primary_offer"] is None
    assert ymyl_roster["secondary_offers"] == []
    assert ymyl_roster["fallback_offer"] is None
    assert ymyl_roster["slot_plan"]["active_slots"] == ["ymyl_public_service_guardrail"]


def test_deterministic_conversion_slot_selection_across_archetypes_and_intents():
    """Verifies deterministic slot selection across page archetypes, commercial intents, and compiled HTML output."""
    from pseofactory.affiliates import bind_asset_partner_roster
    from pseofactory.compiler import compile_high_effort_page

    calc_roster = bind_asset_partner_roster(
        property_id="profithelm",
        slug="saas-burn-multiple-runway-calculator",
        query="saas burn multiple runway calculator",
        page_archetype="interactive_calculator",
    )
    assert calc_roster["page_archetype"] == "interactive_calculator"
    assert calc_roster["slot_plan"]["primary_slot"] == "calculator_result_inline"
    assert calc_roster["slot_plan"]["active_slots"][0] == "calculator_result_inline"
    assert "comparison_table_cta" in calc_roster["slot_plan"]["slot_bindings"]

    matrix_roster = bind_asset_partner_roster(
        property_id="profithelm",
        slug="rippling-vs-gusto-payroll-cost-comparison-matrix",
        query="rippling vs gusto payroll cost comparison matrix",
        page_archetype="scenario_comparison_matrix",
    )
    assert matrix_roster["page_archetype"] == "scenario_comparison_matrix"
    assert matrix_roster["slot_plan"]["primary_slot"] == "comparison_table_cta"

    spoke_roster = bind_asset_partner_roster(
        property_id="profithelm",
        slug="irc-section-174-software-capitalization-statutory-guide",
        query="irc section 174 software r&d capitalization statutory rules",
        page_archetype="statutory_spoke",
    )
    assert spoke_roster["page_archetype"] == "statutory_spoke"
    assert spoke_roster["slot_plan"]["primary_slot"] == "calculator_result_inline"

    hub_roster = bind_asset_partner_roster(
        property_id="profithelm",
        slug="b2b-commercial-finance-calculators-hub",
        query="b2b commercial finance directory hub",
        page_archetype="pillar_hub",
    )
    assert hub_roster["page_archetype"] == "pillar_hub"
    assert hub_roster["slot_plan"]["primary_slot"] == "partner_matrix_card"

    # Compile a greenfield asset via compile_high_effort_page and verify all conversion slots render
    compiled = compile_high_effort_page(
        {
            "query": "multi state remote payroll tax burden calculator",
            "slug": "multi-state-remote-payroll-tax-burden-calculator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 3111 & FUTA Section 3301",
            "economic_dataset": "BLS ECEC Employer Costs for Employee Compensation",
            "model_name": "Multi-State Employer Payroll Burden Model",
            "formula": "gross_payroll * (1 + fica_rate + suta_rate)",
            "inputs": {"gross_payroll": 500000, "fica_rate": 0.0765, "suta_rate": 0.027},
            "published_output": 551750.0,
            "sample_calculation": "500,000 gross payroll at 10.35% combined statutory tax rate yields 551,750 total employer cost",
            "canonical_base": "https://profithelm.com",
        }
    )
    html_out = compiled["html"]
    assert 'data-cta-slot="calculator_result_inline"' in html_out
    assert 'data-cta-slot="comparison_table_cta"' in html_out
    assert 'data-cta-slot="calculator_primary_cta"' in html_out
    assert 'data-cta-slot="partner_matrix_card"' in html_out
    assert compiled["partner_roster"]["distinct_companies_count"] >= 3


def test_gsc_driven_dynamic_placement_repositioning_and_swap_loop(tmp_path):
    """Verifies GSC query, impression, CTR, and position signals dynamically reposition and swap affiliate placements."""
    from pseofactory.affiliates import (
        reposition_affiliate_placements_from_gsc_signals,
        run_gsc_affiliate_placement_feedback_pass,
    )
    from pseofactory.compiler import compile_high_effort_page

    compiled = compile_high_effort_page(
        {
            "query": "b2b payroll cost estimator",
            "slug": "b2b-payroll-cost-estimator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 3111",
            "economic_dataset": "BLS ECEC Series",
            "model_name": "B2B Payroll Cost Model",
            "formula": "headcount * avg_salary * 1.12",
            "inputs": {"headcount": 25, "avg_salary": 85000},
            "published_output": 2380000.0,
            "sample_calculation": "25 employees at 85,000 salary with 12% burden yields 2,380,000",
            "canonical_base": "https://profithelm.com",
        }
    )

    # 1. Striking-distance + query-specific partner intent ("rippling global eor payroll") on a B2B payroll tool
    updated_html, rep_report = reposition_affiliate_placements_from_gsc_signals(
        compiled["html"],
        property_id="profithelm",
        slug="b2b-payroll-cost-estimator",
        query="rippling global eor multi state payroll calculator",
        gsc_metrics={
            "query": "rippling global eor multi state payroll calculator",
            "impressions": 420,
            "clicks": 3,
            "ctr": 0.0071,
            "position": 8.4,
        },
    )
    assert rep_report["repositioned"] is True
    assert rep_report["gsc_repositioned"] is True
    assert rep_report["after_primary_partner"] == "rippling"
    assert rep_report["distinct_companies_count"] >= 3
    assert 'data-gsc-repositioned="true"' in updated_html

    # 2. End-to-end HTML feedback pass on a compiled page directory
    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "b2b-payroll-cost-estimator"
    tool_dir.mkdir(parents=True, exist_ok=True)
    index_file = tool_dir / "index.html"
    index_file.write_text(compiled["html"], encoding="utf-8")

    gsc_rows = [
        {
            "slug": "b2b-payroll-cost-estimator",
            "query": "rippling global eor multi state payroll calculator",
            "impressions": 680,
            "clicks": 4,
            "ctr": 0.0058,
            "position": 6.2,
        }
    ]
    dry_report = run_gsc_affiliate_placement_feedback_pass(
        property_id="profithelm",
        dist_dir=dist_dir,
        repo_root=tmp_path,
        gsc_rows=gsc_rows,
        dry_run=True,
    )
    assert dry_report["pages_scanned"] == 1
    assert dry_report["repositioned_pages_count"] == 1
    assert dry_report["repositioned_pages"][0]["after_primary_partner"] == "rippling"

    live_report = run_gsc_affiliate_placement_feedback_pass(
        property_id="profithelm",
        dist_dir=dist_dir,
        repo_root=tmp_path,
        gsc_rows=gsc_rows,
        dry_run=False,
    )
    assert live_report["pages_updated"] == 1
    final_html = index_file.read_text(encoding="utf-8")
    assert 'data-gsc-repositioned="true"' in final_html
    assert 'data-primary-partner="rippling"' in final_html
    assert '/r/rippling?source_tool=b2b-payroll-cost-estimator&amp;subid=b2b-payroll-cost-estimator_inline&amp;cta_slot=calculator_result_inline' in final_html


def test_contract_and_verifier_assertions_enforce_partner_roster_and_compliance(tmp_path):
    """Verifies contract and verifier gates enforce multi-company partner coverage, link integrity, and YMYL isolation."""
    from pseofactory.compiler import compile_high_effort_page
    from pseofactory.contracts import (
        assert_asset_partner_roster_and_slot_integrity,
        detect_asset_partner_roster_and_slot_issues,
    )
    from pseofactory.verifier import (
        audit_estate_partner_roster_and_compliance,
        verify_html_partner_roster_and_slot_contract,
    )

    ph_page = compile_high_effort_page(
        {
            "query": "section 179 equipment deduction calculator",
            "slug": "section-179-equipment-deduction-calculator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 179",
            "economic_dataset": "FRED CPILFESL Series",
            "model_name": "Section 179 Deduction Model",
            "formula": "min(cost, cap)",
            "inputs": {"cost": 350000, "cap": 1220000},
            "published_output": 350000.0,
            "sample_calculation": "350,000 equipment cost under 1,220,000 cap yields 350,000 deduction",
            "canonical_base": "https://profithelm.com",
        }
    )
    assert_asset_partner_roster_and_slot_integrity(
        ph_page["html"],
        property_id="profithelm",
        slug="section-179-equipment-deduction-calculator",
        require_multi_company=True,
    )
    v_res = verify_html_partner_roster_and_slot_contract(
        ph_page["html"],
        property_id="profithelm",
        slug="section-179-equipment-deduction-calculator",
        require_multi_company=True,
    )
    assert v_res["passed"] is True
    assert len(v_res["partner_keys"]) >= 3

    # Negative check: stripping sponsored attribute triggers contract violation
    broken_html = ph_page["html"].replace('rel="noopener sponsored nofollow"', 'rel="noopener"')
    issues = detect_asset_partner_roster_and_slot_issues(
        broken_html,
        property_id="profithelm",
        slug="section-179-equipment-deduction-calculator",
    )
    assert any("sponsored" in issue.lower() for issue in issues)
    with pytest.raises(ValueError):
        assert_asset_partner_roster_and_slot_integrity(
            broken_html,
            property_id="profithelm",
            slug="section-179-equipment-deduction-calculator",
        )

    # Estate-level audit check
    dist_dir = tmp_path / "dist"
    p_dir = dist_dir / "tools" / "section-179-equipment-deduction-calculator"
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "index.html").write_text(ph_page["html"], encoding="utf-8")

    estate_audit = audit_estate_partner_roster_and_compliance(
        dist_dir=dist_dir,
        property_id="profithelm",
        require_multi_company=True,
    )
    assert estate_audit["passed"] is True
    assert estate_audit["commercial_pages"] == 1




