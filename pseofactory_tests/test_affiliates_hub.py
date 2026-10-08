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
