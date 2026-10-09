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
    assert status["direct_partners_pending"] >= 18
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
    assert route_mercury["status"] == "pending"
    assert "mercury.com" in route_mercury["url"]

    route_ramp = hub.get_route("profithelm", partner_key="ramp")
    assert route_ramp["property_id"] == "profithelm"
    assert route_ramp["partner"] == "ramp"
    assert "ramp.com" in route_ramp["url"]

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

