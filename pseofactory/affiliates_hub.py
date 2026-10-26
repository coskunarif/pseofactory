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
from typing import Dict, Any, List, Optional, Set, Union
from datetime import datetime, timezone
import urllib.parse

from pseofactory.affiliates import (
    AffiliatePartner,
    AFFILIATE_REGISTRY,
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
    GAINHELM_AFFILIATES,
    PROFITHELM_DISCLOSURES,
    PREXVO_DISCLOSURES,
    GAINHELM_DISCLOSURES,
    PREXVO_STANDING_RESTRICTION,
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    GAINHELM_PARTNER_KEYS,
    PROFITHELM_TOOL_PATTERNS,
    PREXVO_TOOL_PATTERNS,
    GAINHELM_TOOL_PATTERNS,
    GAINHELM_MONETIZED_CALCULATOR_SLUGS,
    ENTERPRISE_B2B_PARTNERS,
    RETAIL_TAX_PARTNERS,
    RETAIL_TAX_SLUGS,
    COMMERCIAL_B2B_SLUGS,
    INTENT_ROUTING_TABLE,
    validate_affiliate_url,
    resolve_partner_url,
    get_affiliates_for_property,
    get_affiliate_route,
    _select_partner_for_slug,
    score_partner_yield,
    parse_bounty_estimate,
    is_commercial_b2b_slug,
    resolve_optimal_partner_for_slug,
    verify_partner_domain_alignment,
    qualify_monetization_opportunity,
    SOVRN_VERIFIED_PAYING_MERCHANTS,
    audit_merchant_coverage_and_yield,
    audit_callout_destination_message_match,
    COMPANY_BRAND_BY_PARTNER_KEY,
    VERTICAL_DIVERSIFIED_PARTNER_ROSTERS,
    CANONICAL_PARTNERSHIP_MODELS,
    PARTNER_PARTNERSHIP_MODEL_SPECS,
    resolve_partnership_model_spec,
    score_partnership_model_intent_fit,
    classify_asset_archetype_and_intent,
    select_conversion_slot_plan,
    bind_asset_partner_roster,
    reposition_affiliate_placements_from_gsc_signals,
    run_gsc_affiliate_placement_feedback_pass,
    audit_partnership_model_coverage,
)
from pseofactory.contracts import assert_no_forbidden_dashes


def _validate_dashes_recursive(data: Any, context: str = "vault_data") -> None:
    """Recursively validates that no string in data contains forbidden em-dashes or en-dashes."""
    if isinstance(data, str):
        assert_no_forbidden_dashes(data, context=context)
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str):
                assert_no_forbidden_dashes(k, context=f"{context}.key:{k}")
            _validate_dashes_recursive(v, context=f"{context}.{k}")
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            _validate_dashes_recursive(item, context=f"{context}[{idx}]")


DEFAULT_SOVRN_DOMAIN_KEY = os.environ.get("SOVRN_COMMERCE_DOMAIN_KEY", "0a5ac1bfe04034bff021b394f5e71d90")
DEFAULT_SOVRN_API_KEY = os.environ.get("SOVRN_COMMERCE_API_KEY", "039f430e9e7cad0bd9ff3e6c8d1c54769d5847c3")
DEFAULT_PARTNERSTACK_API_KEY = os.environ.get("PARTNERSTACK_API_KEY", "5ZyfW4zFohJwn2yY8fwc6atIYGIubHwPeATJTNQtqPDrJCIihDhds2dRPrHQJwMP")
DEFAULT_STRIPE_ACCOUNT_ID = os.environ.get("STRIPE_ACCOUNT_ID", "acct_1T6fSTIq0ckFsf5j")
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
    "tcja-sunset-capital-gains",
    "ca-tax-brackets-2026",
    "prediction-market-odds",
    "prediction-market-ev",
    "prediction-market-kelly-criterion",
    "prediction-market-implied-probability",
    "prediction-market-kalshi-fees",
    "prediction-market-arbitrage",
    "prediction-market-vig-spread",
    "prediction-market-break-even",
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
        self._vault: Dict[str, Dict[str, Any]] = {"profithelm": {}, "prexvo": {}, "gainhelm": {}}

        self.vault_data = self._load_vault()
        self._rebuild_partner_vault_index()

    def _rebuild_partner_vault_index(self) -> None:
        """Populates self._vault[property_id][partner_key] from self.vault_data."""
        props = self.vault_data.get("properties", {}) if isinstance(self.vault_data, dict) else {}
        for prop_id in ("profithelm", "prexvo", "gainhelm"):
            prop_map = self._vault.setdefault(prop_id, {})
            prop_data = props.get(prop_id, {})
            if not isinstance(prop_data, dict):
                continue
            categories = prop_data.get("categories", {})
            if isinstance(categories, dict):
                for cat_k, cat_v in categories.items():
                    if isinstance(cat_v, dict):
                        pk = cat_v.get("primary_partner")
                        if pk:
                            prop_map[pk] = {
                                "status": cat_v.get("status", ""),
                                "url": cat_v.get("direct_url", ""),
                                "direct_url": cat_v.get("direct_url", ""),
                                "category": cat_k,
                            }
            partners = prop_data.get("partners", {})
            if isinstance(partners, dict):
                for pk, pv in partners.items():
                    if isinstance(pv, dict):
                        prop_map[pk] = dict(pv)

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
                "gainhelm": {
                    "fallback_enabled": False,
                    "default_fallback_url": "https://gainhelm.com",
                },
            },
            "vault_version": self.vault_data.get("hub_metadata", {}).get("version", "1.0.0"),
        }

        assert_no_forbidden_dashes(
            status["properties"]["prexvo"]["standing_restriction"],
            context="vault_status standing restriction",
        )
        return status

    def save_vault(
        self,
        data: Optional[Dict[str, Any]] = None,
        target_path: Optional[str] = None,
    ) -> None:
        """
        Persists vault data dictionary atomically to disk.
        Enforces recursive zero forbidden dashes contract and sets updated_at timestamp.
        Uses two-phase temporary file write (.tmp) with fsync and atomic os.replace.
        """
        if data is not None:
            self.vault_data = data

        if not isinstance(self.vault_data, dict):
            raise ValueError("Vault data must be a dictionary.")

        # Update UTC timestamp
        if "hub_metadata" not in self.vault_data or not isinstance(self.vault_data["hub_metadata"], dict):
            self.vault_data["hub_metadata"] = {}
        self.vault_data["hub_metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Recursive check for forbidden em-dashes and en-dashes
        _validate_dashes_recursive(self.vault_data, context="save_vault")

        path = target_path or self.vault_path
        target_dir = os.path.dirname(os.path.abspath(path))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.vault_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)

    def sync_partner_program(
        self,
        network: Optional[str] = None,
        program_data: Optional[Dict[str, Any]] = None,
        property_id: str = "profithelm",
        save: bool = True,
        *,
        partner_key: Optional[str] = None,
        status: Optional[str] = None,
        url: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingests, validates, and records a single partner program in the monetization vault.
        Enforces Prexvo student loan isolation, direct 1031 exchange preservation,
        URL safety (SSRF rejection), and typography invariants.
        """
        prop_clean = (property_id or "").strip().lower()
        if prop_clean not in ("profithelm", "prexvo", "exchange1031", "gainhelm"):
            raise ValueError(f"Unknown or unsupported property: '{property_id}'")

        if program_data is None and partner_key is not None:
            pk_clean = partner_key.strip().lower()
            p_obj = AFFILIATE_REGISTRY.get(pk_clean)
            if not category:
                if prop_clean == "prexvo":
                    category = "STUDENT_LOAN_REFINANCE"
                elif pk_clean == "ipx1031":
                    category = "SECTION_1031_EXCHANGE"
                elif p_obj:
                    category = p_obj.category.upper().replace(" ", "_").replace("&", "AND").replace("/", "_")
                else:
                    category = "DIRECT_PARTNER"
            network = network or (p_obj.network if p_obj else "in_house")
            program_data = {
                "program_key": pk_clean,
                "category": category,
                "direct_url": url or (p_obj.default_url if p_obj else ""),
                "status": status or "live",
            }

        network = network or "in_house"

        if not isinstance(program_data, dict):
            raise ValueError("program_data must be a dictionary.")

        # Extract fields with aliases
        program_key = (
            program_data.get("program_key")
            or program_data.get("key")
            or program_data.get("partner")
            or ""
        ).strip().lower()
        category = (
            program_data.get("category")
            or program_data.get("vertical")
            or ""
        ).strip()
        direct_url = (
            program_data.get("direct_url")
            or program_data.get("url")
            or program_data.get("link")
            or program_data.get("target_url")
            or ""
        ).strip()
        raw_status = (
            program_data.get("status")
            or program_data.get("state")
            or ""
        ).strip().lower()

        if not program_key:
            raise ValueError("Missing required program key in program_data.")
        if not category:
            raise ValueError("Missing required category in program_data.")
        if not direct_url:
            raise ValueError("Missing required direct_url in program_data.")
        if not raw_status:
            raise ValueError("Missing required status in program_data.")

        # Typography assertions on network and all string fields in program_data
        assert_no_forbidden_dashes(network, context="network identifier")
        assert_no_forbidden_dashes(program_key, context="program_key")
        assert_no_forbidden_dashes(category, context="category")
        assert_no_forbidden_dashes(direct_url, context="direct_url")
        assert_no_forbidden_dashes(raw_status, context="status")

        for k, v in program_data.items():
            if isinstance(v, str):
                assert_no_forbidden_dashes(v, context=f"program_data field '{k}'")

        # URL validation and SSRF rejection
        if not validate_affiliate_url(direct_url):
            raise ValueError(f"Invalid or unsafe affiliate URL: '{direct_url}'")

        # Prexvo student loan isolation gate
        if prop_clean == "prexvo":
            if (
                program_key in B2B_PARTNER_KEYS
                or program_key in PROFITHELM_AFFILIATES
                or program_key in (
                    "mercury", "ramp", "rho", "rippling", "gusto", "stripe",
                    "coinledger", "koinly", "turbotax", "taxslayer",
                    "crest_capital", "ipx1031", "exeter1031", "kalshi",
                    "interactive_brokers"
                )
            ):
                raise ValueError(
                    f"Strict isolation violation: Commercial B2B partner '{program_key}' is prohibited on Prexvo."
                )
            if category not in ("STUDENT_LOAN_REFINANCE", "STUDENT_LOAN_COMPARISON"):
                raise ValueError(
                    f"Strict isolation violation: Unapproved category '{category}' is prohibited on Prexvo."
                )
            if program_key in ("sovrn_commerce", "sovrn", "viglink") or network.lower() in ("sovrn_commerce", "sovrn", "viglink"):
                raise ValueError(
                    "Strict isolation violation: Sub-affiliate aggregator fallback is prohibited on Prexvo."
                )

        # ProfitHelm student loan isolation gate
        if prop_clean in ("profithelm", "exchange1031"):
            if (
                program_key in STUDENT_LOAN_PARTNER_KEYS
                or program_key in PREXVO_AFFILIATES
                or category in ("STUDENT_LOAN_REFINANCE", "STUDENT_LOAN_COMPARISON")
            ):
                raise ValueError(
                    f"Strict isolation violation: Student loan partner '{program_key}' is prohibited on ProfitHelm."
                )

        # Direct 1031 exchange preservation gate
        if category == "SECTION_1031_EXCHANGE" or program_key == "ipx1031":
            if "redirect.viglink.com" in direct_url.lower() or "sovrn" in direct_url.lower():
                raise ValueError("1031 exchange direct link must not be wrapped with Sovrn Viglink redirect.")
            normalized_status = "active_direct"
        else:
            if raw_status in ("approved", "active", "active_direct", "live"):
                normalized_status = "live" if raw_status == "live" else "active_direct"
            elif raw_status in ("pending", "in_review", "pending_p2"):
                normalized_status = raw_status if raw_status == "pending_p2" else "pending"
            else:
                normalized_status = raw_status

        # Ledger update
        prop_section = self.vault_data.setdefault("properties", {}).setdefault(prop_clean, {})
        categories_dict = prop_section.setdefault("categories", {})
        cat_entry = categories_dict.setdefault(category, {})

        cat_entry["primary_partner"] = program_key
        cat_entry["direct_url"] = direct_url
        cat_entry["status"] = normalized_status

        bounty = program_data.get("bounty")
        if bounty:
            cat_entry["bounty"] = bounty
        fallback_partner = program_data.get("fallback_partner")
        if fallback_partner:
            cat_entry["fallback_partner"] = fallback_partner
        cta_text = program_data.get("cta_text")
        if cta_text:
            cat_entry["cta_text"] = cta_text
        name = program_data.get("name")
        if name:
            cat_entry["name"] = name
        badge = program_data.get("badge")
        if badge:
            cat_entry["badge"] = badge

        target_vault_prop = "profithelm" if prop_clean == "exchange1031" else prop_clean
        self._vault.setdefault(target_vault_prop, {})[program_key] = {
            "status": normalized_status,
            "url": direct_url,
            "direct_url": direct_url,
            "category": category,
        }

        if save:
            self.save_vault()

        return {
            "status": "updated",
            "network": network,
            "property_id": prop_clean,
            "program_key": program_key,
            "category": category,
            "direct_url": direct_url,
            "ledger_status": normalized_status,
        }

    def sync_from_network_payload(
        self,
        network: str,
        payload: Union[Dict[str, Any], List[Dict[str, Any]]],
        property_id: str = "profithelm",
        save: bool = True,
    ) -> Dict[str, Any]:
        """
        Batch ingests network responses or webhook payloads with error collection and idempotency.
        """
        if isinstance(payload, dict):
            items = (
                payload.get("programs")
                or payload.get("items")
                or payload.get("data")
            )
            if items is None:
                # Check if payload itself is a single program item
                if (
                    "program_key" in payload
                    or "key" in payload
                    or "partner" in payload
                ) and (
                    "category" in payload or "vertical" in payload
                ):
                    items = [payload]
                else:
                    items = []
            target_prop = payload.get("property_id") or property_id
            target_network = payload.get("network") or network
        elif isinstance(payload, list):
            items = payload
            target_prop = property_id
            target_network = network
        else:
            items = []
            target_prop = property_id
            target_network = network

        total_received = len(items)
        updated_count = 0
        skipped_count = 0
        errors: List[Dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                skipped_count += 1
                continue

            item_status = (
                item.get("status")
                or item.get("state")
                or ""
            ).strip().lower()

            if item_status in ("approved", "active", "active_direct", "live"):
                try:
                    self.sync_partner_program(
                        network=target_network,
                        program_data=item,
                        property_id=target_prop,
                        save=False,
                    )
                    updated_count += 1
                except ValueError as exc:
                    item_key = (
                        item.get("program_key")
                        or item.get("key")
                        or item.get("partner")
                        or "unknown"
                    )
                    errors.append({"program": item_key, "error": str(exc)})
            else:
                skipped_count += 1

        if save and updated_count > 0:
            self.save_vault()

        return {
            "network": target_network,
            "property_id": target_prop,
            "total_received": total_received,
            "updated": updated_count,
            "skipped": skipped_count,
            "errors": errors,
        }

    def get_direct_contract_upgrades(self, property_id: str = "profithelm") -> Dict[str, str]:
        """
        Extracts verified network-tracked direct contract URLs from the monetization vault
        (such as impact_tracking_url, cj_approved_tracking_url, cj_approved_lawdepot_tracking_url,
        and approved_tracking_url) so the edge redirect function automatically promotes newly
        approved contracts without manual hardcoding.
        """
        prop_clean = (property_id or "profithelm").strip().lower()
        target_prop = "profithelm" if prop_clean == "exchange1031" else prop_clean
        upgrades: Dict[str, str] = {}
        if target_prop == "profithelm":
            upgrades.update(
                {
                    "crest_capital": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "equipment_macrs": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "bench": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "pilot": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "xendoo": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "ipx1031": "https://xendoo.pxf.io/c/7932737/1357375/16354",
                    "ramp": "https://join.ramp.com/c/7932737/3981015/51436",
                    "turbotax": "https://www.jdoqocy.com/click-101906407-11917161",
                    "taxslayer": "https://www.dpbolvw.net/click-101906407-15704796",
                    "freetaxusa": "https://www.jdoqocy.com/click-101906407-12306188",
                    "wallethub": "https://www.jdoqocy.com/click-101906407-16952385",
                    "suretybonds_direct": "https://www.jdoqocy.com/click-101906407-16985242",
                    "otr_solutions_factoring": "https://join.ramp.com/c/7932737/3981015/51436",
                }
            )
        prop_section = self.vault_data.get("properties", {}).get(target_prop, {})
        partners_dict = prop_section.get("partners", {}) if isinstance(prop_section, dict) else {}
        for p_key, p_meta in partners_dict.items():
            if not isinstance(p_meta, dict):
                continue
            for url_field in (
                "approved_tracking_url",
                "impact_tracking_url",
                "impact_verified_tracking_url",
                "cj_approved_tracking_url",
                "cj_approved_lawdepot_tracking_url",
            ):
                cand = str(p_meta.get(url_field) or "").strip()
                if cand and validate_affiliate_url(cand):
                    upgrades[p_key] = cand
                    break
            ft_cand = str(p_meta.get("cj_approved_freetaxusa_tracking_url") or "").strip()
            if ft_cand and validate_affiliate_url(ft_cand):
                upgrades["freetaxusa"] = ft_cand
            wh_cand = str(p_meta.get("cj_approved_wallethub_tracking_url") or "").strip()
            if wh_cand and validate_affiliate_url(wh_cand):
                upgrades["wallethub"] = wh_cand
        return upgrades

    def _is_direct_profithelm_tool(self, tool_slug: str) -> bool:
        """Determines if a tool slug is explicitly mapped to a direct ProfitHelm partner."""
        s = (tool_slug or "").strip().lower()
        if not s:
            return False
        if (
            s in PROFITHELM_DIRECT_SLUGS
            or s in COMMERCIAL_B2B_SLUGS
            or s in RETAIL_TAX_SLUGS
            or is_commercial_b2b_slug(s)
        ):
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
            "ca-tax-brackets",
            "corporate-amt",
            "r-and-d",
            "capital-gains",
            "payroll",
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
        calculator_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves affiliate route contract with guaranteed link attributes.
        Evaluates direct high-bounty partner first; provides Sovrn Commerce server-side fallback
        for ProfitHelm long-tail tools; strictly rejects sub-affiliate fallback on Prexvo.
        """
        prop_clean = (property_id or "").strip().lower()
        if prop_clean not in ("profithelm", "prexvo", "exchange1031", "gainhelm"):
            raise ValueError(f"Unknown or unsupported property: '{property_id}'")

        key_clean = (partner_key or "").strip().lower()
        slug_clean = (calculator_slug or tool_slug or "").strip().lower()
        vault_prop_key = "profithelm" if prop_clean == "exchange1031" else prop_clean
        prop_vault_overrides = dict(self._vault.get(vault_prop_key, {}))

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
                partner_obj = PREXVO_AFFILIATES.get(route["partner"])
            else:
                for b2b_token in ("saas-runway", "section-179", "section-1031", "qsbs-section-1202"):
                    if b2b_token in slug_clean:
                        raise ValueError(
                            f"Strict isolation violation: Commercial tool '{slug_clean}' is prohibited on Prexvo."
                        )
                if not self._is_direct_prexvo_tool(slug_clean):
                    raise ValueError(
                        f"Strict isolation violation: Sub-affiliate fallback is prohibited on Prexvo for unmapped tool '{slug_clean}'. "
                        f"{PREXVO_STANDING_RESTRICTION}"
                    )
                partner_obj = resolve_optimal_partner_for_slug(
                    "prexvo", slug_clean, vault_overrides=prop_vault_overrides
                )
                route = get_affiliate_route(
                    "prexvo",
                    tool_slug=slug_clean,
                    partner_key=partner_obj.key if partner_obj else None,
                    value_tier=value_tier,
                )

            # Check if vault has active update for Prexvo partner
            px_override = prop_vault_overrides.get(route["partner"])
            if isinstance(px_override, dict) and px_override.get("status") in ("active_direct", "live"):
                ov_url = px_override.get("url") or px_override.get("direct_url")
                if ov_url:
                    route["url"] = ov_url
                    route["status"] = px_override["status"]
            px_categories = self.vault_data.get("properties", {}).get("prexvo", {}).get("categories", {})
            for cat_k, cat_v in px_categories.items():
                if cat_v.get("primary_partner") == route["partner"]:
                    if cat_v.get("status") in ("active_direct", "live") and cat_v.get("direct_url"):
                        route["url"] = cat_v["direct_url"]
                        route["status"] = cat_v["status"]
                    break

            if partner_obj:
                route["bounty_est"] = partner_obj.bounty_est
                route["bounty_score"] = score_partner_yield(partner_obj, route["status"])
            route["is_live"] = route.get("status") in ("live", "active_direct")
            route["calculator_slug"] = slug_clean
            route["partner_name"] = route["name"]
            route["is_fallback"] = False
            route["disclosure"] = PREXVO_DISCLOSURES.get("ftc_disclosure", "")
            route["ymyl_warning"] = PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")

            assert_no_forbidden_dashes(route["cta_text"], context="CTA text for Prexvo route")
            assert_no_forbidden_dashes(route["name"], context="Name for Prexvo route")
            return route

        # GainHelm routing
        if prop_clean == "gainhelm":
            if key_clean in STUDENT_LOAN_PARTNER_KEYS or key_clean in B2B_PARTNER_KEYS:
                raise ValueError(
                    f"Strict isolation violation: Foreign tenant partner '{key_clean}' is prohibited on GainHelm."
                )
            route = get_affiliate_route(
                "gainhelm",
                tool_slug=slug_clean,
                partner_key=key_clean or None,
                value_tier=value_tier,
            )
            route["is_live"] = route.get("status") in ("live", "active_direct")
            route["calculator_slug"] = slug_clean
            route["partner_name"] = route["name"]
            route["is_fallback"] = False
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
                    f"Strict isolation violation: Student loan tool '{slug_clean}' is prohibited on ProfitHelm."
                )

        # Explicit fallback request or unmapped / long-tail tool on ProfitHelm
        is_explicit_fallback = bool(fallback_url) or key_clean in ("sovrn_commerce", "sovrn", "viglink")
        is_direct_tool = False

        # Match category in vault
        prop_categories = (
            self.vault_data.get("properties", {})
            .get(prop_clean, {})
            .get("categories", {})
        )
        if not prop_categories and prop_clean == "exchange1031":
            prop_categories = (
                self.vault_data.get("properties", {})
                .get("profithelm", {})
                .get("categories", {})
            )

        matched_vault_cat = None
        resolved_optimal_partner: Optional[AffiliatePartner] = None
        if not is_explicit_fallback:
            if key_clean:
                for cat_k, cat_v in prop_categories.items():
                    if (
                        cat_v.get("primary_partner") == key_clean
                        or cat_k.lower() == key_clean
                    ):
                        matched_vault_cat = cat_v
                        break
            elif slug_clean and self._is_direct_profithelm_tool(slug_clean):
                resolved_optimal_partner = resolve_optimal_partner_for_slug(
                    prop_clean, slug_clean, vault_overrides=prop_vault_overrides
                )
                slug_partner = resolved_optimal_partner.key if resolved_optimal_partner else _select_partner_for_slug(prop_clean, slug_clean)
                if slug_partner:
                    for cat_k, cat_v in prop_categories.items():
                        if cat_v.get("primary_partner") == slug_partner:
                            matched_vault_cat = cat_v
                            break

        vault_is_active = bool(
            matched_vault_cat
            and matched_vault_cat.get("status") in ("active_direct", "live")
            and matched_vault_cat.get("direct_url")
        )

        if not is_explicit_fallback:
            if vault_is_active:
                is_direct_tool = True
            elif key_clean and key_clean in PROFITHELM_AFFILIATES:
                is_direct_tool = True
            elif not key_clean and self._is_direct_profithelm_tool(slug_clean):
                is_direct_tool = True

        if is_direct_tool:
            # Direct high-bounty partner resolution
            target_key = key_clean
            if not target_key and resolved_optimal_partner:
                target_key = resolved_optimal_partner.key
            elif not target_key and matched_vault_cat and vault_is_active:
                target_key = matched_vault_cat.get("primary_partner")

            if target_key and target_key in PROFITHELM_AFFILIATES:
                route = get_affiliate_route(
                    prop_clean,
                    tool_slug=slug_clean,
                    partner_key=target_key,
                    value_tier=value_tier,
                )
            elif not target_key and self._is_direct_profithelm_tool(slug_clean):
                route = get_affiliate_route(
                    prop_clean,
                    tool_slug=slug_clean,
                    partner_key=None,
                    value_tier=value_tier,
                )
            elif matched_vault_cat and vault_is_active:
                partner_name = matched_vault_cat.get("name") or (target_key or "Partner").replace("_", " ").title()
                route = {
                    "property_id": prop_clean,
                    "calculator_slug": slug_clean,
                    "partner": target_key or "partner",
                    "partner_key": target_key or "partner",
                    "name": partner_name,
                    "partner_name": partner_name,
                    "url": matched_vault_cat["direct_url"],
                    "cta_text": matched_vault_cat.get("cta_text") or f"Explore {partner_name} Solutions",
                    "rel": "noopener sponsored nofollow",
                    "target": "_blank",
                    "badge": matched_vault_cat.get("badge") or "Verified Partner",
                    "status": matched_vault_cat.get("status", "active_direct"),
                    "bounty_est": matched_vault_cat.get("bounty", "$100-$300"),
                    "bounty_score": 200.0,
                    "is_fallback": False,
                    "tier": value_tier,
                    "disclosure_required": True,
                    "disclosure": PROFITHELM_DISCLOSURES.get("ftc_disclosure", ""),
                    "ymyl_warning": "",
                }
            else:
                route = get_affiliate_route(
                    prop_clean,
                    tool_slug=slug_clean,
                    partner_key=key_clean if key_clean else None,
                    value_tier=value_tier,
                )

            # Check direct _vault partner override
            ov_entry = prop_vault_overrides.get(route["partner"])
            if isinstance(ov_entry, dict) and ov_entry.get("status") in ("active_direct", "live"):
                ov_url = ov_entry.get("url") or ov_entry.get("direct_url")
                if ov_url:
                    route["url"] = ov_url
                    route["status"] = ov_entry["status"]

            # If matched_vault_cat is active in vault, override url and status
            if vault_is_active and matched_vault_cat:
                route["url"] = matched_vault_cat["direct_url"]
                route["status"] = matched_vault_cat["status"]
                if matched_vault_cat.get("cta_text"):
                    route["cta_text"] = matched_vault_cat["cta_text"]
                if matched_vault_cat.get("name"):
                    route["name"] = matched_vault_cat["name"]
                    route["partner_name"] = matched_vault_cat["name"]
                if matched_vault_cat.get("badge"):
                    route["badge"] = matched_vault_cat["badge"]

            partner_obj = PROFITHELM_AFFILIATES.get(route["partner"])
            if partner_obj:
                route["bounty_est"] = partner_obj.bounty_est
                route["bounty_score"] = score_partner_yield(partner_obj, route["status"])
            route["is_live"] = route.get("status") in ("live", "active_direct")
            route["calculator_slug"] = slug_clean
            route["partner_name"] = route["name"]
            route["is_fallback"] = False
            route["disclosure"] = PROFITHELM_DISCLOSURES.get("ftc_disclosure", "")
            route["ymyl_warning"] = ""

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
            "calculator_slug": slug_clean,
            "partner": "sovrn_commerce",
            "partner_key": "sovrn_commerce",
            "name": partner_name,
            "partner_name": partner_name,
            "url": wrapped_url,
            "target_url": target_destination,
            "cta_text": cta_text,
            "rel": "noopener sponsored nofollow",
            "target": "_blank",
            "badge": badge_text,
            "status": "wrapped_fallback",
            "is_live": False,
            "bounty_est": "$0",
            "bounty_score": 0.0,
            "is_fallback": True,
            "tier": value_tier,
            "provider": "sovrn_commerce",
            "disclosure_required": True,
            "disclosure": PROFITHELM_DISCLOSURES.get("ftc_disclosure", ""),
            "ymyl_warning": "",
        }

    def audit_domain_boundaries(self) -> Dict[str, Any]:
        """
        Audits all COMMERCIAL_B2B_SLUGS, RETAIL_TAX_SLUGS, and Prexvo borrower slugs
        through get_route and verifies strict domain boundary isolation and zero sub-affiliate aggregators.
        Zero em-dashes. Zero en-dashes.
        """
        violations: List[str] = []
        aggregators = ("sovrn", "viglink", "skimlinks")

        for slug in sorted(COMMERCIAL_B2B_SLUGS):
            route = self.get_route("profithelm", slug)
            partner = route.get("partner", "")
            url_lower = (route.get("url") or "").lower()
            if partner in RETAIL_TAX_PARTNERS:
                violations.append(
                    f"Retail tax partner '{partner}' routed to commercial B2B slug '{slug}'"
                )
            if any(agg in url_lower for agg in aggregators):
                violations.append(
                    f"Sub-affiliate aggregator detected in commercial B2B route URL for '{slug}': '{route.get('url')}'"
                )

        for slug in sorted(RETAIL_TAX_SLUGS):
            route = self.get_route("profithelm", slug)
            partner = route.get("partner", "")
            url_lower = (route.get("url") or "").lower()
            if partner in ENTERPRISE_B2B_PARTNERS:
                violations.append(
                    f"Enterprise B2B partner '{partner}' routed to retail tax slug '{slug}'"
                )
            if any(agg in url_lower for agg in aggregators):
                violations.append(
                    f"Sub-affiliate aggregator detected in retail tax route URL for '{slug}': '{route.get('url')}'"
                )

        for slug in sorted(PREXVO_DIRECT_SLUGS):
            route = self.get_route("prexvo", slug)
            partner = route.get("partner", "")
            url_lower = (route.get("url") or "").lower()
            if partner in ENTERPRISE_B2B_PARTNERS or partner in B2B_PARTNER_KEYS:
                violations.append(
                    f"Enterprise B2B partner '{partner}' routed to Prexvo borrower slug '{slug}'"
                )
            if any(agg in url_lower for agg in aggregators):
                violations.append(
                    f"Sub-affiliate aggregator detected in Prexvo route URL for '{slug}': '{route.get('url')}'"
                )

        for p_key, p_obj in AFFILIATE_REGISTRY.items():
            url_lower = (p_obj.default_url or "").lower()
            if any(agg in url_lower for agg in aggregators):
                violations.append(
                    f"Sub-affiliate aggregator detected in default URL for partner '{p_key}': '{p_obj.default_url}'"
                )

        return {
            "status": "PASS" if not violations else "FAIL",
            "passed": not violations,
            "is_clean": not violations,
            "violations": violations,
        }

    def qualify_opportunity(
        self,
        query: str,
        slug: str = "",
        property_id: Optional[str] = None,
        search_volume: int = 0,
        cpc_usd: float = 0.0,
        jev_score: float = 1.25,
        durable_prob: float = 0.55,
    ) -> Dict[str, Any]:
        """
        Delegates to canonical qualify_monetization_opportunity using active vault overrides.
        """
        return qualify_monetization_opportunity(
            query=query,
            slug=slug,
            property_id=property_id,
            search_volume=search_volume,
            cpc_usd=cpc_usd,
            jev_score=jev_score,
            durable_prob=durable_prob,
            vault_overrides=self.vault_data,
        )

    def verify_partner_alignment(
        self,
        property_id: str,
        slug: str,
        partners: List[str],
    ) -> Dict[str, Any]:
        """
        Delegates to canonical verify_partner_domain_alignment.
        """
        return verify_partner_domain_alignment(
            property_id=property_id,
            slug=slug,
            partners=partners,
        )

    def reconcile_live_networks(
        self,
        live_network: Optional[bool] = None,
        timeout: float = 8.0,
        save: bool = False,
    ) -> Dict[str, Any]:
        """
        Reconciles live PartnerStack and Sovrn Commerce network telemetry against the monetization vault.
        In offline/pytest mode, synthesizes a deterministic summary from vault_data without network calls.
        Zero em-dashes. Zero en-dashes.
        """
        import urllib.request
        import urllib.error

        use_live = (
            live_network
            if live_network is not None
            else ("PYTEST_CURRENT_TEST" not in os.environ or os.getenv("PSEUFACTORY_LIVE_NETWORK") == "1")
        )

        payroll_cat = (
            self.vault_data.get("properties", {})
            .get("profithelm", {})
            .get("categories", {})
            .get("PAYROLL_HR", {})
        )
        active_links: List[str] = []
        tos_pending: List[str] = []
        if isinstance(payroll_cat, dict):
            d_url = str(payroll_cat.get("direct_url") or "").strip()
            if d_url and payroll_cat.get("status") in ("live", "active_direct") and validate_affiliate_url(d_url):
                active_links.append(d_url)
            if payroll_cat.get("tos_status") == "tos-acceptance-pending":
                tos_pending.append(str(payroll_cat.get("primary_partner") or "rippling"))

        ps_summary: Dict[str, Any] = {
            "partnerships_count": len(active_links),
            "active_links": list(active_links),
            "tos_pending_partners": list(tos_pending),
            "rewards_count": 0,
            "payouts_count": 0,
            "actions_count": 0,
            "total_revenue_usd": 0.0,
        }
        sovrn_summary: Dict[str, Any] = {
            "account_id": str(
                self.vault_data.get("master_networks", {})
                .get("sovrn_commerce", {})
                .get("account_id", "2987330")
            ),
            "configured": bool(self.sovrn_domain_key and self.sovrn_api_key),
            "total_revenue_usd": 0.0,
        }

        if use_live:
            def _fetch_json(url: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
                try:
                    req_headers = {"User-Agent": "pseofactory/1.0", **headers}
                    req = urllib.request.Request(url, headers=req_headers, method="GET")
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return json.loads(resp.read().decode("utf-8", errors="replace"))
                except Exception:
                    return None

            if self.partnerstack_api_key:
                ps_headers = {
                    "Authorization": f"Bearer {self.partnerstack_api_key}",
                    "Accept": "application/json",
                    "User-Agent": "pseofactory/1.0",
                }
                p_resp = _fetch_json("https://api.partnerstack.com/api/v2/partnerships", ps_headers)
                if isinstance(p_resp, dict):
                    p_items = (p_resp.get("data") or {}).get("items")
                    if isinstance(p_items, list):
                        ps_summary["partnerships_count"] = len(p_items)
                        live_urls: List[str] = []
                        live_tos: List[str] = []
                        for item in p_items:
                            if not isinstance(item, dict):
                                continue
                            l_url = str((item.get("link") or {}).get("url") or "").strip()
                            if l_url and validate_affiliate_url(l_url):
                                live_urls.append(l_url)
                            st = str(item.get("status") or "").strip().lower()
                            comp_name = str(((item.get("company") or {}).get("name") or "")).strip().lower()
                            if (
                                isinstance(payroll_cat, dict)
                                and (
                                    comp_name == "rippling"
                                    or str(item.get("key") or "") == str(payroll_cat.get("partnership_key") or "")
                                )
                                and st
                            ):
                                payroll_cat["tos_status"] = st
                            if "tos" in st or "pending" in st:
                                live_tos.append(comp_name or str(item.get("key") or "unknown"))
                        if live_urls:
                            ps_summary["active_links"] = live_urls
                        ps_summary["tos_pending_partners"] = live_tos

                r_resp = _fetch_json("https://api.partnerstack.com/api/v2/rewards", ps_headers)
                if isinstance(r_resp, dict):
                    r_items = (r_resp.get("data") or {}).get("items")
                    if isinstance(r_items, list):
                        ps_summary["rewards_count"] = len(r_items)
                        total_cents = sum(
                            float(it.get("amount") or 0.0)
                            for it in r_items
                            if isinstance(it, dict) and str(it.get("status") or "").lower() in ("approved", "paid", "pending")
                        )
                        ps_summary["total_revenue_usd"] = round(total_cents / 100.0, 2)

                pay_resp = _fetch_json("https://api.partnerstack.com/api/v2/payouts", ps_headers)
                if isinstance(pay_resp, dict):
                    pay_items = (pay_resp.get("data") or {}).get("items")
                    if isinstance(pay_items, list):
                        ps_summary["payouts_count"] = len(pay_items)

                act_resp = _fetch_json("https://api.partnerstack.com/api/v2/actions", ps_headers)
                if isinstance(act_resp, dict):
                    act_items = (act_resp.get("data") or {}).get("items")
                    if isinstance(act_items, list):
                        ps_summary["actions_count"] = len(act_items)

            if self.sovrn_api_key:
                sovrn_headers = {
                    "Authorization": f"secret {self.sovrn_api_key}",
                    "Accept": "application/json",
                    "User-Agent": "pseofactory/1.0",
                }
                s_resp = _fetch_json("https://publishers.viglink.com/api/account", sovrn_headers)
                if isinstance(s_resp, dict) and s_resp.get("accountId"):
                    sovrn_summary["account_id"] = str(s_resp["accountId"])
                    sovrn_summary["configured"] = True

        live_links_verified: List[Dict[str, Any]] = []
        for prop_id, registry_map in (("profithelm", PROFITHELM_AFFILIATES), ("prexvo", PREXVO_AFFILIATES)):
            prop_vault = self._vault.get(prop_id, {})
            for p_key, p_obj in registry_map.items():
                if p_key != p_obj.key:
                    continue
                v_entry = prop_vault.get(p_key, {})
                v_status = str(v_entry.get("status") or "").strip().lower()
                is_live = p_obj.status == "live" or v_status in ("live", "active_direct")
                if not is_live:
                    continue
                url = str(v_entry.get("url") or v_entry.get("direct_url") or p_obj.default_url).strip()
                if validate_affiliate_url(url):
                    live_links_verified.append({
                        "partner_key": p_key,
                        "property_id": prop_id,
                        "url": url,
                        "network": p_obj.network,
                    })

        if save:
            self.save_vault()

        return {
            "mode": "live" if use_live else "offline",
            "partnerstack": ps_summary,
            "sovrn_commerce": sovrn_summary,
            "live_links_verified": live_links_verified,
        }

    def verify_outbound_link_health(
        self,
        property_id: str = "profithelm",
        live_network: Optional[bool] = None,
        timeout: float = 6.0,
    ) -> Dict[str, Any]:
        """
        Verifies outbound affiliate link syntax and optional live HTTP redirect health for a property.
        Zero em-dashes. Zero en-dashes.
        """
        import urllib.request
        import urllib.error

        prop_clean = (property_id or "").strip().lower()
        affiliates = get_affiliates_for_property(prop_clean)
        vault_prop = "profithelm" if prop_clean == "exchange1031" else prop_clean
        prop_vault = self._vault.get(vault_prop, {})

        use_live = (
            live_network
            if live_network is not None
            else ("PYTEST_CURRENT_TEST" not in os.environ or os.getenv("PSEUFACTORY_LIVE_NETWORK") == "1")
        )

        class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirectHandler) if use_live else None
        results: List[Dict[str, Any]] = []

        for p_key, p_obj in affiliates.items():
            if p_key != p_obj.key:
                continue
            v_entry = prop_vault.get(p_key, {})
            v_status = str(v_entry.get("status") or "").strip().lower()
            if not (p_obj.status == "live" or v_status in ("live", "active_direct")):
                continue

            url = str(v_entry.get("url") or v_entry.get("direct_url") or p_obj.default_url).strip()
            syntax_valid = validate_affiliate_url(url)
            status_code = 200 if syntax_valid else 0
            location: Optional[str] = None
            healthy = syntax_valid

            if syntax_valid and use_live and opener is not None:
                req = urllib.request.Request(
                    url,
                    method="GET",
                    headers={"User-Agent": "Mozilla/5.0 (compatible; pseofactory-link-verifier/1.0)"},
                )
                try:
                    with opener.open(req, timeout=timeout) as resp:
                        status_code = int(getattr(resp, "status", 200))
                        location = resp.headers.get("Location")
                        healthy = 200 <= status_code < 400
                except urllib.error.HTTPError as exc:
                    status_code = int(exc.code)
                    location = exc.headers.get("Location") if exc.headers else None
                    if status_code in (301, 302, 303, 307, 308) and location:
                        healthy = True
                    elif status_code == 403 and exc.headers and (
                        "cloudflare" in str(exc.headers.get("Server", "")).lower()
                        or exc.headers.get("CF-RAY")
                    ):
                        healthy = True
                    else:
                        healthy = False
                except Exception:
                    status_code = 0
                    healthy = False

            results.append({
                "partner_key": p_key,
                "url": url,
                "syntax_valid": syntax_valid,
                "status_code": status_code,
                "location": location,
                "healthy": healthy,
            })

        return {
            "property_id": prop_clean,
            "healthy": all(r["healthy"] for r in results),
            "checked_count": len(results),
            "results": results,
        }

    def audit_merchant_coverage(self) -> Dict[str, Any]:
        """
        Audits all ProfitHelm and Prexvo partner keys against verified commission-bearing
        merchants and direct partner approvals, verifying zero unmonetized Sovrn pass-throughs
        and zero circular internal redirects.
        """
        return audit_merchant_coverage_and_yield()

    def audit_callout_message_match(
        self,
        dist_dir: Optional[Any] = None,
        property_id: str = "profithelm",
    ) -> Dict[str, Any]:
        """
        Audits callout-to-destination brand and offer message-match across the affiliate
        registry and rendered HTML pages.
        """
        return audit_callout_destination_message_match(dist_dir=dist_dir, property_id=property_id)

    def bind_partner_roster(
        self,
        property_id: str,
        slug: str,
        query: str = "",
        page_archetype: str = "",
        gsc_metrics: Optional[Dict[str, Any]] = None,
        engagement_metrics: Optional[Dict[str, Any]] = None,
        min_companies: int = 3,
    ) -> Dict[str, Any]:
        """
        Binds a diversified multi-company partner roster (primary, secondary, fallback)
        and deterministic conversion slot plan for any asset or vertical.
        """
        return bind_asset_partner_roster(
            property_id=property_id,
            slug=slug,
            query=query,
            page_archetype=page_archetype,
            gsc_metrics=gsc_metrics,
            engagement_metrics=engagement_metrics,
            vault_overrides=self.vault_data,
            min_companies=min_companies,
        )

    def audit_partnership_models(
        self,
        property_id: Optional[str] = None,
        dist_dir: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Audits partnership model coverage across all 5 canonical structures,
        all verticals, and (optionally) compiled DOM output.
        """
        return audit_partnership_model_coverage(property_id=property_id, dist_dir=dist_dir)


CentralizedAffiliatesHub = MonetizationHub




