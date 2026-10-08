"""
pseofactory Autonomous Monetization Hub & Fallback Routing Engine
Centralized, programmatic single-source-of-truth monetization router for pseofactory properties.

Key Invariants:
1. Loads monetization vault from JSON with dynamic environment variable overrides.
2. Direct high-bounty partner resolution via affiliates.py registry.
3. Server-side URL wrapping via Sovrn Commerce for ProfitHelm long-tail tools.
4. Strict prohibition of sub-affiliate fallback on Prexvo under PREXVO_STANDING_RESTRICTION (CFPB compliance).
5. Guaranteed outbound link attributes: rel="noopener sponsored nofollow", target="_blank".
6. Zero em-dashes and zero en-dashes across all partner entries, URLs, and disclosure copy.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
import os
from typing import Dict, Any, List, Optional, Set
import urllib.parse

from pseofactory.affiliates import (
    AffiliatePartner,
    AFFILIATE_REGISTRY,
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
    PREXVO_STANDING_RESTRICTION,
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    PROFITHELM_TOOL_PATTERNS,
    PREXVO_TOOL_PATTERNS,
    validate_affiliate_url,
    resolve_partner_url,
    get_affiliates_for_property,
    get_affiliate_route,
)
from pseofactory.contracts import assert_no_forbidden_dashes


DEFAULT_SOVRN_DOMAIN_KEY = "0a5ac1bfe04034bff021b394f5e71d90"
DEFAULT_SOVRN_API_KEY = "039f430e9e7cad0bd9ff3e6c8d1c54769d5847c3"
DEFAULT_PARTNERSTACK_API_KEY = "5ZyfW4zFohJwn2yY8fwc6atIYGIubHwPeATJTNQtqPDrJCIihDhds2dRPrHQJwMP"
DEFAULT_STRIPE_ACCOUNT_ID = "acct_1T6fSTIq0ckFsf5j"
SOVRN_REDIRECT_BASE = "https://redirect.viglink.com"

# Slugs and patterns recognized as direct high-bounty partner tools for ProfitHelm
PROFITHELM_DIRECT_SLUGS: Set[str] = {
    "crypto-tax-calculator",
    "prediction-market-tax",
    "saas-runway-calculator",
    "treasury-yield-calculator",
    "section-179-calculator",
    "qsbs-section-1202-calculator",
    "qsbs-section-1202-tax-calculator",
    "section-1031-calculator",
    "irs-2027-tax-brackets",
    "tcja-sunset-bracket-calculator",
    "prediction-market-odds",
}

# Slugs recognized as direct high-bounty student loan tools for Prexvo
PREXVO_DIRECT_SLUGS: Set[str] = {
    "student-loan-repayment-calculator",
    "rap-vs-ibr-calculator",
}


class MonetizationHub:
    """
    Unified programmatic monetization hub managing direct high-bounty partners,
    universal Sovrn Commerce server-side fallback, and master API credentials.
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        sovrn_domain_key: Optional[str] = None,
        sovrn_api_key: Optional[str] = None,
        partnerstack_api_key: Optional[str] = None,
        stripe_account_id: Optional[str] = None,
    ):
        self.vault_path = vault_path or os.path.join(
            os.path.dirname(__file__), "monetization_vault.json"
        )
        self._init_sovrn_domain_key = sovrn_domain_key
        self._init_sovrn_api_key = sovrn_api_key
        self._init_partnerstack_api_key = partnerstack_api_key
        self._init_stripe_account_id = stripe_account_id

        self.vault_data = self._load_vault()

    def _load_vault(self) -> Dict[str, Any]:
        """Loads vault JSON or provides fallback defaults."""
        if os.path.isfile(self.vault_path):
            try:
                with open(self.vault_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except Exception:
                pass

        # In-memory default structure if file not found or unreadable
        return {
            "hub_metadata": {
                "version": "1.0.0",
                "updated_at": "2026-10-08T15:50:00Z",
                "description": "Fallback in-memory monetization vault",
            },
            "master_networks": {
                "sovrn_commerce": {
                    "domain_key": DEFAULT_SOVRN_DOMAIN_KEY,
                    "api_key": DEFAULT_SOVRN_API_KEY,
                    "enabled": True,
                },
                "partnerstack": {
                    "api_key": DEFAULT_PARTNERSTACK_API_KEY,
                    "enabled": True,
                },
                "stripe": {
                    "account_id": DEFAULT_STRIPE_ACCOUNT_ID,
                    "enabled": True,
                },
            },
            "properties": {
                "profithelm": {
                    "fallback_enabled": True,
                    "fallback_provider": "sovrn_commerce",
                    "default_fallback_url": "https://profithelm.com",
                },
                "prexvo": {
                    "fallback_enabled": False,
                    "standing_restriction": PREXVO_STANDING_RESTRICTION,
                },
            },
        }

    @property
    def sovrn_domain_key(self) -> str:
        """Returns active Sovrn Commerce domain key with environment override."""
        env_val = os.getenv("SOVRN_COMMERCE_KEY") or os.getenv("SOVRN_COMMERCE_DOMAIN_KEY")
        if env_val and env_val.strip():
            return env_val.strip()
        if self._init_sovrn_domain_key:
            return self._init_sovrn_domain_key.strip()
        vault_key = (
            self.vault_data.get("master_networks", {})
            .get("sovrn_commerce", {})
            .get("domain_key")
        )
        if vault_key:
            return str(vault_key).strip()
        return DEFAULT_SOVRN_DOMAIN_KEY

    @property
    def sovrn_api_key(self) -> str:
        """Returns active Sovrn Commerce secret API key with environment override."""
        env_val = os.getenv("SOVRN_COMMERCE_API_KEY")
        if env_val and env_val.strip():
            return env_val.strip()
        if self._init_sovrn_api_key:
            return self._init_sovrn_api_key.strip()
        vault_key = (
            self.vault_data.get("master_networks", {})
            .get("sovrn_commerce", {})
            .get("api_key")
        )
        if vault_key:
            return str(vault_key).strip()
        return DEFAULT_SOVRN_API_KEY

    @property
    def partnerstack_api_key(self) -> str:
        """Returns active PartnerStack API key with environment override."""
        env_val = os.getenv("PARTNERSTACK_API_KEY")
        if env_val and env_val.strip():
            return env_val.strip()
        if self._init_partnerstack_api_key:
            return self._init_partnerstack_api_key.strip()
        vault_key = (
            self.vault_data.get("master_networks", {})
            .get("partnerstack", {})
            .get("api_key")
        )
        if vault_key:
            return str(vault_key).strip()
        return DEFAULT_PARTNERSTACK_API_KEY

    @property
    def stripe_account_id(self) -> str:
        """Returns active Stripe account ID with environment override."""
        env_val = os.getenv("STRIPE_ACCOUNT_ID")
        if env_val and env_val.strip():
            return env_val.strip()
        if self._init_stripe_account_id:
            return self._init_stripe_account_id.strip()
        vault_id = (
            self.vault_data.get("master_networks", {})
            .get("stripe", {})
            .get("account_id")
        )
        if vault_id:
            return str(vault_id).strip()
        return DEFAULT_STRIPE_ACCOUNT_ID

    def wrap_sovrn_url(self, target_url: str, custom_key: Optional[str] = None) -> str:
        """
        Wraps outbound URL via Sovrn Commerce redirect server-side link.
        Validates target_url (must be http/https) and generates clean redirect.viglink.com link.
        Enforces anti-slop typography invariant.
        """
        if not target_url or not isinstance(target_url, str):
            raise ValueError("Target URL must be a non-empty string.")

        target_clean = target_url.strip()
        if not target_clean:
            raise ValueError("Target URL cannot be empty or whitespace.")

        assert_no_forbidden_dashes(target_clean, context="wrap_sovrn_url target_url")

        try:
            parsed = urllib.parse.urlsplit(target_clean)
        except Exception as exc:
            raise ValueError(f"Malformed target URL for Sovrn wrapping: '{target_clean}'") from exc

        if target_clean.lower().startswith("javascript:") or target_clean.lower().startswith("data:"):
            raise ValueError(f"Unsafe URL scheme in target URL: '{target_clean}'")

        if parsed.scheme.lower() not in ("https", "http"):
            raise ValueError(
                f"Invalid target URL scheme '{parsed.scheme}'. Scheme must be http or https for Sovrn wrapping."
            )

        if not parsed.netloc:
            raise ValueError(f"Target URL must contain a valid host/netloc: '{target_clean}'")

        key = (custom_key or self.sovrn_domain_key or "").strip()
        if not key:
            raise ValueError("Sovrn Commerce domain key is required for URL wrapping.")

        assert_no_forbidden_dashes(key, context="wrap_sovrn_url domain key")

        encoded_u = urllib.parse.quote(target_clean, safe="")
        wrapped = f"{SOVRN_REDIRECT_BASE}?key={key}&u={encoded_u}"
        assert_no_forbidden_dashes(wrapped, context="wrap_sovrn_url output")
        return wrapped

    def get_vault_status(self) -> Dict[str, Any]:
        """
        Returns counts of active direct partners, pending partners, and master key availability.
        """
        active_count = sum(1 for p in AFFILIATE_REGISTRY.values() if p.status == "live")
        pending_count = sum(
            1 for p in AFFILIATE_REGISTRY.values()
            if p.status in ("pending", "pending_expansion", "pending_p2")
        )
        total_count = len(AFFILIATE_REGISTRY)

        sovrn_key = self.sovrn_domain_key
        sovrn_api = self.sovrn_api_key
        ps_key = self.partnerstack_api_key
        stripe_id = self.stripe_account_id

        status = {
            "direct_partners_total": total_count,
            "direct_partners_active": active_count,
            "direct_partners_pending": pending_count,
            "sovrn_commerce_key_configured": bool(sovrn_key),
            "sovrn_commerce_api_key_configured": bool(sovrn_api),
            "partnerstack_key_configured": bool(ps_key),
            "stripe_account_configured": bool(stripe_id),
            "master_keys": {
                "sovrn_commerce_domain_key_configured": bool(sovrn_key),
                "sovrn_commerce_api_key_configured": bool(sovrn_api),
                "partnerstack_api_key_configured": bool(ps_key),
                "stripe_account_id_configured": bool(stripe_id),
            },
            "properties": {
                "profithelm": {
                    "fallback_enabled": True,
                    "fallback_provider": "sovrn_commerce",
                },
                "prexvo": {
                    "fallback_enabled": False,
                    "standing_restriction": PREXVO_STANDING_RESTRICTION,
                },
            },
            "vault_version": self.vault_data.get("hub_metadata", {}).get("version", "1.0.0"),
        }

        assert_no_forbidden_dashes(
            status["properties"]["prexvo"]["standing_restriction"],
            context="vault_status standing restriction",
        )
        return status

    def _is_direct_profithelm_tool(self, tool_slug: str) -> bool:
        """Determines if a tool slug is explicitly mapped to a direct ProfitHelm partner."""
        s = (tool_slug or "").strip().lower()
        if not s:
            return False
        if s in PROFITHELM_DIRECT_SLUGS:
            return True
        for p in PROFITHELM_AFFILIATES.values():
            if s in p.target_tools:
                return True
        for pattern in (
            "section-179",
            "section-1031",
            "crypto-tax",
            "prediction-market",
            "treasury-yield",
            "saas-runway",
            "qsbs-section-1202",
            "tcja-sunset",
            "irs-2027",
        ):
            if pattern in s:
                return True
        return False

    def _is_direct_prexvo_tool(self, tool_slug: str) -> bool:
        """Determines if a tool slug is explicitly mapped to a direct Prexvo student loan partner."""
        s = (tool_slug or "").strip().lower()
        if not s:
            return False
        if s in PREXVO_DIRECT_SLUGS:
            return True
        for p in PREXVO_AFFILIATES.values():
            if s in p.target_tools:
                return True
        for pattern in PREXVO_TOOL_PATTERNS:
            if pattern in s:
                return True
        return False

    def get_route(
        self,
        property_id: str,
        tool_slug: str = "",
        partner_key: Optional[str] = None,
        value_tier: str = "starter",
        fallback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves affiliate route contract with guaranteed link attributes.
        Evaluates direct high-bounty partner first; provides Sovrn Commerce server-side fallback
        for ProfitHelm long-tail tools; strictly rejects sub-affiliate fallback on Prexvo.
        """
        prop_clean = (property_id or "").strip().lower()
        if prop_clean not in ("profithelm", "prexvo", "exchange1031"):
            raise ValueError(f"Unknown or unsupported property: '{property_id}'")

        key_clean = (partner_key or "").strip().lower()
        slug_clean = (tool_slug or "").strip().lower()

        # Strict isolation check for Prexvo
        if prop_clean == "prexvo":
            if fallback_url:
                raise ValueError(
                    f"Strict isolation violation: Sub-affiliate fallback is prohibited on Prexvo. "
                    f"{PREXVO_STANDING_RESTRICTION}"
                )
            if key_clean in ("sovrn_commerce", "sovrn", "viglink"):
                raise ValueError(
                    f"Strict isolation violation: Sub-affiliate fallback is prohibited on Prexvo. "
                    f"{PREXVO_STANDING_RESTRICTION}"
                )
            if key_clean in B2B_PARTNER_KEYS or key_clean in PROFITHELM_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: B2B partner '{key_clean}' is prohibited on Prexvo."
                )

            # Direct resolution for Prexvo
            if key_clean:
                route = get_affiliate_route(
                    "prexvo", tool_slug=slug_clean, partner_key=key_clean, value_tier=value_tier
                )
            else:
                for b2b_token in ("saas-runway", "section-179", "section-1031", "qsbs-section-1202"):
                    if b2b_token in slug_clean:
                        raise ValueError(
                            f"Strict isolation violation: Commercial tool '{tool_slug}' is prohibited on Prexvo."
                        )
                if not self._is_direct_prexvo_tool(slug_clean):
                    raise ValueError(
                        f"Strict isolation violation: Sub-affiliate fallback is prohibited on Prexvo for unmapped tool '{tool_slug}'. "
                        f"{PREXVO_STANDING_RESTRICTION}"
                    )
                route = get_affiliate_route(
                    "prexvo", tool_slug=slug_clean, value_tier=value_tier
                )

            assert_no_forbidden_dashes(route["cta_text"], context=f"CTA text for Prexvo route")
            assert_no_forbidden_dashes(route["name"], context=f"Name for Prexvo route")
            return route

        # ProfitHelm / Exchange1031 routing
        if key_clean in STUDENT_LOAN_PARTNER_KEYS or key_clean in PREXVO_AFFILIATES:
            raise ValueError(
                f"Strict isolation violation: Student loan partner '{key_clean}' is prohibited on ProfitHelm."
            )

        # Check for explicit student loan slug on ProfitHelm
        for sl_token in ("student-loan", "rap-vs-ibr", "pslf"):
            if sl_token in slug_clean:
                raise ValueError(
                    f"Strict isolation violation: Student loan tool '{tool_slug}' is prohibited on ProfitHelm."
                )

        # Explicit fallback request or unmapped / long-tail tool on ProfitHelm
        is_explicit_fallback = bool(fallback_url) or key_clean in ("sovrn_commerce", "sovrn", "viglink")
        is_direct_tool = False

        if not is_explicit_fallback:
            if key_clean and key_clean in PROFITHELM_AFFILIATES:
                is_direct_tool = True
            elif not key_clean and self._is_direct_profithelm_tool(slug_clean):
                is_direct_tool = True

        if is_direct_tool:
            # Direct high-bounty partner resolution
            route = get_affiliate_route(
                prop_clean,
                tool_slug=slug_clean,
                partner_key=key_clean if key_clean else None,
                value_tier=value_tier,
            )
            assert_no_forbidden_dashes(route["cta_text"], context=f"CTA text for {route['partner']}")
            assert_no_forbidden_dashes(route["name"], context=f"Name for {route['partner']}")
            assert_no_forbidden_dashes(route["badge"], context=f"Badge for {route['partner']}")
            return route

        # Unmapped / long-tail tool on ProfitHelm -> wrap via Sovrn Commerce
        if fallback_url:
            target_destination = fallback_url.strip()
        else:
            # Default partner target for ProfitHelm
            target_destination = (
                self.vault_data.get("properties", {})
                .get("profithelm", {})
                .get("default_fallback_url", "https://profithelm.com")
            )

        wrapped_url = self.wrap_sovrn_url(target_destination)
        is_premium = (value_tier or "starter").strip().lower() == "premium"
        cta_text = "Explore Premium Partner Solutions" if is_premium else "Explore Partner Solutions"
        partner_name = "Sovrn Commerce Partner Network"
        badge_text = "Verified Merchant Partner"

        assert_no_forbidden_dashes(cta_text, context="Fallback CTA text")
        assert_no_forbidden_dashes(partner_name, context="Fallback partner name")
        assert_no_forbidden_dashes(badge_text, context="Fallback badge")

        return {
            "property_id": prop_clean,
            "partner": "sovrn_commerce",
            "partner_key": "sovrn_commerce",
            "name": partner_name,
            "url": wrapped_url,
            "target_url": target_destination,
            "cta_text": cta_text,
            "rel": "noopener sponsored nofollow",
            "target": "_blank",
            "badge": badge_text,
            "status": "wrapped_fallback",
            "tier": value_tier,
            "provider": "sovrn_commerce",
            "disclosure_required": True,
        }
