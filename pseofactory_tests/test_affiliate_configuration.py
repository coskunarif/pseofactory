"""
Comprehensive Test Suite for pseofactory Unified Affiliate Configuration
Validates:
1. Registry Schema Validity: all required fields present, typed, and non-empty.
2. URL Protocol & Parsing Validity: https/http schemes, non-empty netlocs, rejection of invalid schemes.
3. Environment Variable Override Engine: AFFILIATE_<KEY>_URL overrides route output dynamically.
4. Strict Property Isolation Gate: Prexvo has 0 B2B partners, ProfitHelm has 0 student loan partners;
   cross-property requests raise ValueError.
5. Mandatory Disclosures Assertions: ProfitHelm FTC disclosure contains CoinLedger & Koinly;
   Prexvo YMYL disclaimer contains all 5 statutory phrases.
6. Link Attributes Compliance: rel="noopener sponsored nofollow", target="_blank".
7. Anti-Slop Typography Contracts: zero em-dashes and zero en-dashes across all partner entries.
8. Tool Route Coverage: every target tool across properties resolves a working route.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import urllib.parse
import pytest

from pseofactory.affiliates import (
    AffiliatePartner,
    AFFILIATE_REGISTRY,
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
    PROFITHELM_DISCLOSURES,
    PREXVO_DISCLOSURES,
    PREXVO_STANDING_RESTRICTION,
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    validate_affiliate_url,
    resolve_partner_url,
    get_affiliates_for_property,
    get_affiliate_route,
)
from pseofactory.contracts import assert_no_forbidden_dashes


REQUIRED_SCHEMA_FIELDS = [
    "key",
    "name",
    "category",
    "property_id",
    "status",
    "env_var",
    "default_url",
    "badge",
    "commission_est",
    "bounty_est",
    "network",
    "description",
    "target_tools",
    "supported_params",
    "cta_text",
]


def test_registry_schema_validity():
    """Verifies that all affiliate partners conform to the AffiliatePartner schema with required fields."""
    assert len(AFFILIATE_REGISTRY) >= 20, "Expected at least 20 registered affiliate partners"

    for key, partner in AFFILIATE_REGISTRY.items():
        assert isinstance(partner, AffiliatePartner), f"Partner '{key}' is not an AffiliatePartner instance"
        partner_dict = partner.to_dict()

        for field in REQUIRED_SCHEMA_FIELDS:
            assert field in partner_dict, f"Partner '{key}' missing required field: '{field}'"
            val = partner_dict[field]
            if field in ("target_tools", "supported_params"):
                assert isinstance(val, list), f"Field '{field}' in '{key}' must be a list"
            else:
                assert isinstance(val, str), f"Field '{field}' in '{key}' must be a string"
                assert len(val.strip()) > 0, f"Field '{field}' in '{key}' cannot be empty"

        assert partner.property_id in ("profithelm", "prexvo"), (
            f"Partner '{key}' has invalid property_id: '{partner.property_id}'"
        )
        assert partner.status in ("live", "pending", "pending_expansion", "pending_p2"), (
            f"Partner '{key}' has unrecognized status: '{partner.status}'"
        )
        assert partner.env_var.startswith("AFFILIATE_"), (
            f"Partner '{key}' env_var '{partner.env_var}' must start with 'AFFILIATE_'"
        )
        assert partner.env_var.endswith("_URL"), (
            f"Partner '{key}' env_var '{partner.env_var}' must end with '_URL'"
        )


def test_url_protocol_and_parsing_validity():
    """Verifies that all default affiliate URLs are syntactically valid and use secure protocols."""
    for key, partner in AFFILIATE_REGISTRY.items():
        url = partner.default_url
        assert validate_affiliate_url(url), f"Default URL failed validation for partner '{key}': '{url}'"

        parsed = urllib.parse.urlsplit(url)
        assert parsed.scheme in ("https", "http"), f"URL scheme must be http or https for '{key}': '{url}'"
        assert bool(parsed.netloc), f"URL must have non-empty netloc for '{key}': '{url}'"
        assert not url.startswith("/"), f"Relative URLs forbidden for '{key}': '{url}'"

    # Rejection of unsafe or malformed URLs
    assert not validate_affiliate_url("javascript:alert(1)")
    assert not validate_affiliate_url("javascript:void(0)")
    assert not validate_affiliate_url("data:text/html;base64,PHNjcmlwdD4=")
    assert not validate_affiliate_url("/relative/path/to/offer")
    assert not validate_affiliate_url("ftp://ftp.example.com/file")
    assert not validate_affiliate_url("")
    assert not validate_affiliate_url(None)


def test_environment_variable_override_mechanism(monkeypatch):
    """Verifies that AFFILIATE_<KEY>_URL overrides destination URL dynamically without code changes."""
    # Test ProfitHelm CoinLedger override
    custom_coinledger = "https://custom.coinledger.io/promotions/2026?partner_id=arif_vip"
    monkeypatch.setenv("AFFILIATE_COINLEDGER_URL", custom_coinledger)

    route_cl = get_affiliate_route("profithelm", "crypto-tax-calculator", partner_key="coinledger")
    assert route_cl["url"] == custom_coinledger, "Environment override did not update CoinLedger route URL"

    # Test Prexvo Splash Financial override
    custom_splash = "https://custom.splashfinancial.com/direct-apply?src=pseo"
    monkeypatch.setenv("AFFILIATE_SPLASH_FINANCIAL_URL", custom_splash)

    route_sf = get_affiliate_route("prexvo", "student-loan-repayment-calculator", partner_key="splash_financial")
    assert route_sf["url"] == custom_splash, "Environment override did not update Splash Financial route URL"

    # Test invalid override raises ValueError
    monkeypatch.setenv("AFFILIATE_MERCURY_URL", "javascript:stealCookies()")
    with pytest.raises(ValueError) as excinfo:
        get_affiliate_route("profithelm", "saas-runway-calculator", partner_key="mercury")
    assert "Invalid affiliate URL" in str(excinfo.value)

    # Revert override and verify fallback to default URL
    monkeypatch.delenv("AFFILIATE_COINLEDGER_URL", raising=False)
    route_reverted = get_affiliate_route("profithelm", "crypto-tax-calculator", partner_key="coinledger")
    assert route_reverted["url"] == PROFITHELM_AFFILIATES["coinledger"].default_url


def test_property_isolation_gate():
    """Enforces strict isolation: Prexvo has 0 B2B partners, ProfitHelm has 0 student loan partners."""
    # Prexvo isolation
    for p_key, partner in PREXVO_AFFILIATES.items():
        assert partner.property_id == "prexvo"
        assert p_key not in B2B_PARTNER_KEYS, f"Prexvo contains forbidden B2B partner '{p_key}'"
        assert partner.category == "Student Loan Refinance", (
            f"Prexvo partner '{p_key}' has unexpected category: '{partner.category}'"
        )

    # ProfitHelm isolation
    for p_key, partner in PROFITHELM_AFFILIATES.items():
        assert partner.property_id == "profithelm"
        assert p_key not in STUDENT_LOAN_PARTNER_KEYS, (
            f"ProfitHelm contains forbidden student loan partner '{p_key}'"
        )
        assert partner.category != "Student Loan Refinance", (
            f"ProfitHelm partner '{p_key}' cannot be in Student Loan Refinance category"
        )

    # Cross-property partner requests must raise ValueError
    for b2b_key in ("mercury", "stripe", "ramp", "rho", "gusto", "rippling"):
        with pytest.raises(ValueError) as exc:
            get_affiliate_route("prexvo", "student-loan-repayment-calculator", partner_key=b2b_key)
        assert "Strict isolation violation" in str(exc.value)

    for sl_key in ("splash_financial", "sofi", "credible", "earnest", "lendkey"):
        with pytest.raises(ValueError) as exc:
            get_affiliate_route("profithelm", "crypto-tax-calculator", partner_key=sl_key)
        assert "Strict isolation violation" in str(exc.value)

    # Cross-property commercial tool slugs on Prexvo must raise ValueError
    with pytest.raises(ValueError) as exc:
        get_affiliate_route("prexvo", "saas-runway-calculator")
    assert "Strict isolation violation" in str(exc.value)

    # Cross-property student loan tool slugs on ProfitHelm must raise ValueError
    with pytest.raises(ValueError) as exc:
        get_affiliate_route("profithelm", "student-loan-repayment-calculator")
    assert "Strict isolation violation" in str(exc.value)

    # Unknown property must raise ValueError
    with pytest.raises(ValueError) as exc:
        get_affiliate_route("unknown_property_xyz", "crypto-tax-calculator")
    assert "Unknown or unsupported property" in str(exc.value)


def test_mandatory_disclosures_validation():
    """Validates mandatory FTC publisher disclosures and Prexvo Title IV statutory forfeiture disclaimers."""
    # ProfitHelm FTC disclosure check
    ph_ftc = PROFITHELM_DISCLOSURES.get("ftc_disclosure", "")
    assert "CoinLedger" in ph_ftc, "ProfitHelm FTC disclosure missing approved partner CoinLedger"
    assert "Koinly" in ph_ftc, "ProfitHelm FTC disclosure missing approved partner Koinly"
    assert "commission" in ph_ftc.lower(), "ProfitHelm FTC disclosure must mention commission"
    assert_no_forbidden_dashes(ph_ftc, context="ProfitHelm FTC disclosure")

    # Prexvo YMYL statutory forfeiture disclaimer check
    px_ymyl = PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")
    assert_no_forbidden_dashes(px_ymyl, context="Prexvo YMYL disclaimer")

    required_ymyl_phrases = [
        "permanently eliminates",
        "income-driven repayment",
        "Public Service Loan Forgiveness",
        "deferment",
        "forbearance",
    ]
    for phrase in required_ymyl_phrases:
        assert phrase.lower() in px_ymyl.lower(), (
            f"Prexvo YMYL disclaimer missing mandatory statutory phrase: '{phrase}'"
        )

    # Prexvo FTC disclosure check
    px_ftc = PREXVO_DISCLOSURES.get("ftc_disclosure", "")
    assert_no_forbidden_dashes(px_ftc, context="Prexvo FTC disclosure")
    for partner_name in ("Splash Financial", "SoFi", "Credible", "Earnest", "LendKey"):
        assert partner_name in px_ftc, f"Prexvo FTC disclosure missing partner '{partner_name}'"

    # Prexvo legal disclaimer check
    px_advice = PREXVO_DISCLOSURES.get("disclaimer_no_advice", "")
    assert "does not provide personalized financial" in px_advice.lower()
    assert_no_forbidden_dashes(px_advice, context="Prexvo no-advice disclaimer")

    # Prexvo standing restriction check
    assert_no_forbidden_dashes(PREXVO_STANDING_RESTRICTION, context="Prexvo standing restriction")
    assert "prohibition on b2b monetization" in PREXVO_STANDING_RESTRICTION.lower()


def test_link_attributes_and_security_contracts():
    """Verifies that all affiliate routes enforce rel='noopener sponsored nofollow' and target='_blank'."""
    sample_queries = [
        ("profithelm", "crypto-tax-calculator", "coinledger"),
        ("profithelm", "saas-runway-calculator", "mercury"),
        ("profithelm", "section-179-calculator", "crest_capital"),
        ("profithelm", "section-1031-calculator", "ipx1031"),
        ("profithelm", "irs-2027-tax-brackets", "turbotax"),
        ("profithelm", "prediction-market-tax", "kalshi"),
        ("profithelm", "treasury-yield-calculator", "interactive_brokers"),
        ("prexvo", "student-loan-repayment-calculator", "splash_financial"),
        ("prexvo", "rap-vs-ibr-calculator", "sofi"),
    ]

    for prop, slug, partner_key in sample_queries:
        route = get_affiliate_route(prop, slug, partner_key=partner_key)
        assert route["rel"] == "noopener sponsored nofollow", (
            f"Route rel attribute must strictly be 'noopener sponsored nofollow' for {prop}/{partner_key}"
        )
        assert route["target"] == "_blank", (
            f"Route target attribute must strictly be '_blank' for {prop}/{partner_key}"
        )
        assert route["disclosure_required"] is True
        assert len(route["cta_text"]) > 0
        assert len(route["badge"]) > 0


def test_anti_slop_typography_invariants():
    """Strict anti-slop invariant: zero em-dashes (U+2014) and zero en-dashes (U+2013) across all content."""
    for key, partner in AFFILIATE_REGISTRY.items():
        assert_no_forbidden_dashes(partner.name, context=f"Partner name '{key}'")
        assert_no_forbidden_dashes(partner.category, context=f"Partner category '{key}'")
        assert_no_forbidden_dashes(partner.badge, context=f"Partner badge '{key}'")
        assert_no_forbidden_dashes(partner.commission_est, context=f"Partner commission_est '{key}'")
        assert_no_forbidden_dashes(partner.bounty_est, context=f"Partner bounty_est '{key}'")
        assert_no_forbidden_dashes(partner.network, context=f"Partner network '{key}'")
        assert_no_forbidden_dashes(partner.description, context=f"Partner description '{key}'")
        assert_no_forbidden_dashes(partner.cta_text, context=f"Partner cta_text '{key}'")

    for k, v in PROFITHELM_DISCLOSURES.items():
        assert_no_forbidden_dashes(v, context=f"ProfitHelm disclosure '{k}'")

    for k, v in PREXVO_DISCLOSURES.items():
        assert_no_forbidden_dashes(v, context=f"Prexvo disclosure '{k}'")

    assert_no_forbidden_dashes(PREXVO_STANDING_RESTRICTION, context="Prexvo standing restriction")


def test_tool_route_coverage():
    """Verifies that every target tool across both properties resolves a valid affiliate route."""
    # ProfitHelm tools
    profithelm_tools = [
        "crypto-tax-calculator",
        "prediction-market-tax",
        "saas-runway-calculator",
        "section-179-calculator",
        "treasury-yield-calculator",
        "section-1031-calculator",
        "qsbs-section-1202-tax-calculator",
        "irs-2027-tax-brackets",
        "tcja-sunset-bracket-calculator",
    ]
    for slug in profithelm_tools:
        route = get_affiliate_route("profithelm", slug)
        assert route["property_id"] == "profithelm"
        assert route["partner"] in PROFITHELM_AFFILIATES
        assert route["url"].startswith("http")
        assert route["rel"] == "noopener sponsored nofollow"
        assert len(route["cta_text"]) > 0

    # Prexvo tools
    prexvo_tools = [
        "student-loan-repayment-calculator",
        "rap-vs-ibr-calculator",
    ]
    for slug in prexvo_tools:
        route = get_affiliate_route("prexvo", slug)
        assert route["property_id"] == "prexvo"
        assert route["partner"] in PREXVO_AFFILIATES
        assert route["url"].startswith("http")
        assert route["rel"] == "noopener sponsored nofollow"
        assert len(route["cta_text"]) > 0


def test_value_tier_escalation_and_parameter_namespacing():
    """Verifies that premium value tier escalates CTA text and preserves vendor-namespaced parameters."""
    starter_route = get_affiliate_route("profithelm", "crypto-tax-calculator", value_tier="starter", partner_key="coinledger")
    premium_route = get_affiliate_route("profithelm", "crypto-tax-calculator", value_tier="premium", partner_key="coinledger")

    assert starter_route["cta_text"] != premium_route["cta_text"]
    assert "Pro" in premium_route["cta_text"]
    assert "ph_tier=premium" in premium_route["url"]
    assert "fpr=" in premium_route["url"]

    # Prexvo does not support ph_tier, so URL remains clean
    px_starter = get_affiliate_route("prexvo", "student-loan-repayment-calculator", value_tier="starter", partner_key="splash_financial")
    px_premium = get_affiliate_route("prexvo", "student-loan-repayment-calculator", value_tier="premium", partner_key="splash_financial")
    assert "ph_tier" not in px_premium["url"]
    assert px_starter["cta_text"] != px_premium["cta_text"]
