"""
pseofactory Centralized Tenant Fact & Statutory Truth Store
Stateless immutable profiles for ProfitHelm and Prexvo with strict tenant boundary isolation.
Enforces:
1. Canonical pricing tier verification ($0, $49, $199 for ProfitHelm; $0, $19 for Prexvo).
2. Grounded feature matrix contract verification.
3. Statutory tax citations (IRS Rev Proc 2024-40) and student loan citations (34 CFR Part 685).
4. Banned marketing claims rejection.
5. Mandatory regulatory disclosures (Circular 230, YMYL forfeiture disclaimer, FTC disclosure).
6. Strict cross-tenant boundary isolation.

Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Any, Optional, Set, Tuple

from pseofactory.contracts import assert_no_forbidden_dashes


class PropertyContaminationError(ValueError):
    """
    Raised when foreign cross-property tokens or claims bleed into a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    pass


@dataclass(frozen=True)
class PricingTier:
    """
    Canonical subscription or product pricing tier for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    name: str
    price_usd: float
    billing_period: str
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "price_usd": self.price_usd,
            "billing_period": self.billing_period,
            "features": list(self.features),
        }


@dataclass(frozen=True)
class FeatureContract:
    """
    Verified feature contract for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    name: str
    enabled: bool
    tier_availability: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "tier_availability": list(self.tier_availability),
            "description": self.description,
        }


@dataclass(frozen=True)
class TenantStatutoryTruth:
    """
    Primary statutory citations and empirical limits for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    tenant_id: str
    statutory_citations: Dict[str, str] = field(default_factory=dict)
    limits_and_thresholds: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "statutory_citations": dict(self.statutory_citations),
            "limits_and_thresholds": dict(self.limits_and_thresholds),
        }


@dataclass(frozen=True)
class TenantTruthProfile:
    """
    Complete immutable truth profile for a tenant property.
    Zero em-dashes. Zero en-dashes.
    """
    tenant_id: str
    brand_name: str
    canonical_domain: str
    pricing_tiers: Dict[str, PricingTier] = field(default_factory=dict)
    features: Dict[str, FeatureContract] = field(default_factory=dict)
    statutory_truth: TenantStatutoryTruth = field(
        default_factory=lambda: TenantStatutoryTruth(tenant_id="default")
    )
    claims_allowlist: List[str] = field(default_factory=list)
    claims_banned: List[str] = field(default_factory=list)
    mandatory_disclosures: List[str] = field(default_factory=list)
    cross_tenant_forbidden_tokens: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "canonical_domain": self.canonical_domain,
            "pricing_tiers": {k: v.to_dict() for k, v in self.pricing_tiers.items()},
            "features": {k: v.to_dict() for k, v in self.features.items()},
            "statutory_truth": self.statutory_truth.to_dict(),
            "claims_allowlist": list(self.claims_allowlist),
            "claims_banned": list(self.claims_banned),
            "mandatory_disclosures": list(self.mandatory_disclosures),
            "cross_tenant_forbidden_tokens": list(sorted(self.cross_tenant_forbidden_tokens)),
        }


def _build_profithelm_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for ProfitHelm."""
    pricing = {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="month",
            features=["Core Calculators", "Section 179 Optimizer"],
        ),
        "pro": PricingTier(
            name="Pro",
            price_usd=49.0,
            billing_period="month",
            features=[
                "Entity Tax Modeling",
                "Section 1031 Exchange Matching",
                "Section 179 Optimizer",
                "QSBS Stacking Analysis",
                "Data Export",
            ],
        ),
        "enterprise": PricingTier(
            name="Enterprise",
            price_usd=199.0,
            billing_period="month",
            features=[
                "Entity Tax Modeling",
                "Section 1031 Exchange Matching",
                "Section 179 Optimizer",
                "QSBS Stacking Analysis",
                "Multi-Entity Consolidation",
                "Priority API",
            ],
        ),
    }

    features = {
        "Entity Tax Modeling": FeatureContract(
            name="Entity Tax Modeling",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Comprehensive pass-through and C-corp entity tax scenario modeling.",
        ),
        "Section 1031 Exchange Matching": FeatureContract(
            name="Section 1031 Exchange Matching",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Section 1031 like-kind exchange identification and timeline tracking.",
        ),
        "Section 179 Optimizer": FeatureContract(
            name="Section 179 Optimizer",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Asset depreciation and first-year expense deduction maximization.",
        ),
        "QSBS Stacking Analysis": FeatureContract(
            name="QSBS Stacking Analysis",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Section 1202 Qualified Small Business Stock tax exemption analysis.",
        ),
        "Multi-Entity Consolidation": FeatureContract(
            name="Multi-Entity Consolidation",
            enabled=True,
            tier_availability=["enterprise"],
            description="Multi-entity corporate structure tax consolidation and reporting.",
        ),
    }

    statutory = TenantStatutoryTruth(
        tenant_id="profithelm",
        statutory_citations={
            "irs_rev_proc_2024_40": "IRS Rev Proc 2024-40",
            "irs_rev_proc_2023_34": "IRS Rev Proc 2023-34",
            "section_179": "IRC Section 179",
            "section_1202": "IRC Section 1202 (QSBS)",
            "circular_230": "Treasury Department Circular No. 230",
            "section_1031": "IRC Section 1031",
        },
        limits_and_thresholds={
            "section_179_expense_limit_2024": 1220000.0,
            "section_179_expense_limit_2025": 1250000.0,
            "section_179_heavy_vehicle_2024": 30500.0,
            "section_179_heavy_vehicle_2025": 31300.0,
            "section_1202_qsbs_asset_ceiling": 50000000.0,
            "section_1202_qsbs_exclusion_cap": 10000000.0,
            "section_1202_qsbs_exclusion_multiple": 10.0,
            "section_1202_qsbs_holding_period_years": 5,
            "retirement_401k_elective_deferral_2024": 23000.0,
            "retirement_401k_elective_deferral_2025": 23500.0,
            "hsa_single_2024": 4150.0,
            "hsa_single_2025": 4300.0,
            "hsa_family_2024": 8300.0,
            "hsa_family_2025": 8550.0,
        },
    )

    claims_allowlist = [
        "Entity Tax Modeling",
        "Section 1031 Exchange Matching",
        "Section 179 Optimizer",
        "QSBS Stacking Analysis",
        "Multi-Entity Consolidation",
    ]

    claims_banned = [
        "automated irs filing",
        "automated irs tax filing",
        "legal representation",
        "guaranteed tax audit immunity",
        "guaranteed tax shelter",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
    ]

    mandatory_disclosures = [
        "Circular 230 tax modeling disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "title iv",
        "34 cfr",
        "pslf",
        "paye sunset",
        "student loan",
        "repayment assistance plan",
        "income-contingent repayment",
        "direct consolidation",
        "prexvo.com",
        "prexvo",
        "106482194",
        # Prexvo student loan refinance partner keys
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
    }

    return TenantTruthProfile(
        tenant_id="profithelm",
        brand_name="ProfitHelm",
        canonical_domain="https://profithelm.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


def _build_prexvo_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for Prexvo."""
    pricing = {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="month",
            features=["RAP vs IBR Modeling", "Tiered Standard Calculation", "ICR Repayment Modeling"],
        ),
        "pro": PricingTier(
            name="Pro",
            price_usd=19.0,
            billing_period="month",
            features=[
                "RAP vs IBR Modeling",
                "Tiered Standard Calculation",
                "PAYE Sunset Analysis",
                "ICR Repayment Modeling",
                "PSLF Buyback Estimator",
                "Scenario Export",
            ],
        ),
        "enterprise": PricingTier(
            name="Enterprise",
            price_usd=0.0,
            billing_period="custom",
            features=[
                "RAP vs IBR Modeling",
                "Tiered Standard Calculation",
                "PAYE Sunset Analysis",
                "ICR Repayment Modeling",
                "PSLF Buyback Estimator",
                "Institutional Analytics",
            ],
        ),
    }

    features = {
        "RAP vs IBR Modeling": FeatureContract(
            name="RAP vs IBR Modeling",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Repayment Assistance Plan vs Income-Based Repayment schedule comparison.",
        ),
        "Tiered Standard Calculation": FeatureContract(
            name="Tiered Standard Calculation",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Tiered fixed repayment schedule calculation for direct loans.",
        ),
        "PAYE Sunset Analysis": FeatureContract(
            name="PAYE Sunset Analysis",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Analysis of Pay As You Earn plan phasing out pursuant to 34 CFR 685.209.",
        ),
        "ICR Repayment Modeling": FeatureContract(
            name="ICR Repayment Modeling",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Income-Contingent Repayment plan calculation and discretionary income modeling.",
        ),
        "PSLF Buyback Estimator": FeatureContract(
            name="PSLF Buyback Estimator",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Public Service Loan Forgiveness buyback payment estimation under 34 CFR 685.219.",
        ),
    }

    statutory = TenantStatutoryTruth(
        tenant_id="prexvo",
        statutory_citations={
            "title_iv": "Title IV Higher Education Act",
            "34_cfr_685": "34 CFR Part 685",
            "paye_regulations": "34 CFR 685.209",
            "pslf_regulations": "34 CFR 685.219",
        },
        limits_and_thresholds={
            "rap_discretionary_percentage": 0.10,
            "rap_poverty_guideline_threshold": 2.25,
            "ibr_pre_2014_percentage": 0.15,
            "ibr_post_2014_percentage": 0.10,
            "ibr_poverty_guideline_threshold": 1.50,
            "pslf_qualifying_payments": 120,
            "poverty_guidelines": {
                2024: {"individual": 15060.0, "additional_person": 5380.0},
                2025: {"individual": 15650.0, "additional_person": 5440.0},
                2026: {"individual": 16200.0, "additional_person": 5500.0},
            },
        },
    )

    claims_allowlist = [
        "RAP vs IBR Modeling",
        "Tiered Standard Calculation",
        "PAYE Sunset Analysis",
        "ICR Repayment Modeling",
        "PSLF Buyback Estimator",
    ]

    claims_banned = [
        "official federal loan servicer",
        "direct federal student loan consolidation processing",
        "guaranteed debt cancellation",
        "guaranteed debt forgiveness",
        "guaranteed loan forgiveness",
        "b2b corporate tax",
        "1031 exchange",
        "section 179",
        "section 1031",
        "mercury",
        "turbotax",
        "coinledger",
        "crest_capital",
    ]

    mandatory_disclosures = [
        "Refinancing federal student loans permanently waives federal protections",
        "FTC Partner Compensation Disclosure",
        "Independent Publisher Disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "section 1031",
        "1031 exchange",
        "exchange 1031",
        "exchange1031",
        "section 179",
        "qsbs",
        "section 1202",
        "corporate tax",
        "pass-through entity",
        "tcja",
        "profithelm.com",
        "profithelm",
        "143884102",
        # ProfitHelm B2B affiliate partner keys
        "coinledger",
        "koinly",
        "mercury",
        "stripe",
        "ramp",
        "rho",
        "gusto",
        "rippling",
        "crest_capital",
        "ipx1031",
        "exeter1031",
        "first_american",
        "turbotax",
        "taxslayer",
        "kalshi",
        "interactive_brokers",
    }

    return TenantTruthProfile(
        tenant_id="prexvo",
        brand_name="Prexvo",
        canonical_domain="https://prexvo.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


class TenantFactStore:
    """
    Centralized singleton store for tenant truth profiles.
    Enforces truth assertions, claim verification, and tenant isolation boundaries.
    Zero em-dashes. Zero en-dashes.
    """

    _instance: Optional["TenantFactStore"] = None

    def __init__(self):
        self._profiles: Dict[str, TenantTruthProfile] = {
            "profithelm": _build_profithelm_profile(),
            "prexvo": _build_prexvo_profile(),
        }

    @classmethod
    def get_instance(cls) -> "TenantFactStore":
        """Returns singleton instance of TenantFactStore."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets singleton instance for test isolation."""
        cls._instance = None

    def get_profile(self, tenant: str) -> Optional[TenantTruthProfile]:
        """Retrieves tenant profile by identifier (case-insensitive)."""
        if not tenant:
            return None
        return self._profiles.get(str(tenant).lower().strip())

    def verify_price(self, tenant: str, price_usd: float) -> bool:
        """
        Verifies if price_usd matches an official pricing tier for the tenant.
        Zero em-dashes. Zero en-dashes.
        """
        profile = self.get_profile(tenant)
        if not profile:
            return False
        valid_prices = {tier.price_usd for tier in profile.pricing_tiers.values()}
        return float(price_usd) in valid_prices

    def verify_feature(self, tenant: str, feature_name: str) -> bool:
        """
        Verifies if feature_name is recognized and enabled for the tenant.
        Zero em-dashes. Zero en-dashes.
        """
        profile = self.get_profile(tenant)
        if not profile:
            return False
        for f_key, f_val in profile.features.items():
            if f_key.lower() == feature_name.lower().strip() or f_val.name.lower() == feature_name.lower().strip():
                return f_val.enabled
        return False

    def verify_claim(
        self,
        tenant: str,
        text: str,
        context: Optional[str] = None,
        spec_disclosures: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Inspects text against tenant truth profile:
        1. Banned marketing claims
        2. Unverified pricing numbers ($XX/mo)
        3. Cross-tenant boundary contamination
        4. Mandatory regulatory disclosures
        5. Statutory threshold limit boundaries
        Returns (is_valid, violations_list).
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(text, context=context or f"verify_claim({tenant})")
        profile = self.get_profile(tenant)
        if not profile:
            return False, [f"Unknown tenant '{tenant}'"]

        violations: List[str] = []
        text_lower = text.lower()
        tenant_norm = str(tenant).lower().strip()

        # 1. Banned claims check
        for banned in profile.claims_banned:
            if banned.lower() in text_lower:
                violations.append(
                    f"Banned claim detected for {profile.brand_name}: '{banned}'"
                )

        # 2. Pricing verification
        pricing_matches = re.findall(
            r'\$(\d+(?:\.\d{2})?)\s*(?:/|\s*per\s*)(?:mo|month)',
            text,
            re.IGNORECASE,
        )
        valid_prices = {tier.price_usd for tier in profile.pricing_tiers.values()}
        for price_str in pricing_matches:
            price_val = float(price_str)
            if price_val not in valid_prices:
                violations.append(
                    f"Unverified price claim '${price_val}' contradicts {profile.brand_name} pricing tiers {valid_prices}"
                )

        # 3. Cross-tenant boundary isolation
        for token in sorted(profile.cross_tenant_forbidden_tokens):
            if token.lower() in text_lower:
                violations.append(
                    f"Cross-tenant contamination on {profile.brand_name}: found forbidden boundary token '{token}'"
                )

        # 4. Mandatory regulatory disclosures
        if tenant_norm == "profithelm":
            has_tax_modeling = (
                "tax scenario modeling" in text_lower
                or "entity tax modeling" in text_lower
                or "tax modeling scenarios" in text_lower
            )
            if has_tax_modeling:
                has_c230 = (
                    "circular 230" in text_lower
                    or "treasury department circular no. 230" in text_lower
                )
                if not has_c230:
                    violations.append(
                        "Missing mandatory Circular 230 regulatory disclosure: 'Circular 230 tax modeling disclaimer: Information generated is for deterministic computational modeling purposes and does not constitute formal tax, legal, or investment advice under Treasury Department Circular No. 230.'"
                    )
        elif tenant_norm == "prexvo":
            if "refinance" in text_lower or "refinancing" in text_lower:
                has_ymyl = (
                    "waives federal protections" in text_lower
                    or "eliminates federal protections" in text_lower
                    or "waive federal protections" in text_lower
                )
                if not has_ymyl:
                    violations.append(
                        "Missing mandatory YMYL forfeiture disclaimer: 'Refinancing federal student loans permanently waives federal protections'"
                    )

        if spec_disclosures:
            for disclosure_phrase in spec_disclosures:
                if disclosure_phrase and disclosure_phrase.lower() not in text_lower:
                    violations.append(
                        f"Missing mandatory disclosure containing '{disclosure_phrase}'"
                    )

        # 5. Statutory threshold limit boundaries
        if tenant_norm == "profithelm":
            # Section 179 SUV / heavy vehicle cap ($30,500 for 2024 / $31,300 for 2025)
            if "suv" in text_lower or "heavy vehicle" in text_lower:
                suv_matches = re.findall(
                    r'(?:(?:suv|heavy\s*vehicle)[^\.\n]*?(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)[^\.\n]*?(?:suv|heavy\s*vehicle))',
                    text,
                    re.IGNORECASE,
                )
                for m in suv_matches:
                    raw_val = m[0] or m[1]
                    try:
                        val = float(raw_val.replace(",", ""))
                        suv_cap = 31300.0 if "2025" in text_lower else 30500.0
                        if val > suv_cap:
                            violations.append(
                                f"Section 179 heavy vehicle/SUV limit contradiction: claimed ${val:,.0f} exceeds statutory cap of $30,500 for 2024 ($31,300 for 2025)"
                            )
                    except ValueError:
                        pass

            # Section 179 overall expense limit ($1,220,000 for 2024 / $1,250,000 for 2025)
            s179_matches = re.findall(
                r'(?:section\s*179[^\.\n]*?(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)[^\.\n]*?section\s*179)',
                text,
                re.IGNORECASE,
            )
            for m in s179_matches:
                raw_val = m[0] or m[1]
                try:
                    val = float(raw_val.replace(",", ""))
                    s179_cap = 1250000.0 if "2025" in text_lower else 1220000.0
                    if val > s179_cap:
                        violations.append(
                            f"Section 179 expense limit contradiction: claimed ${val:,.0f} exceeds statutory limit of $1,220,000 for 2024 ($1,250,000 for 2025)"
                        )
                except ValueError:
                    pass

        elif tenant_norm == "prexvo":
            # PSLF qualifying payments: strictly 120 payments
            pslf_matches = re.findall(
                r'(?:(?:pslf|public\s+service\s+loan\s+forgiveness)[^\.\n]*?(\d+)\s*(?:qualifying\s*)?(?:monthly\s*)?payments?|(\d+)\s*(?:qualifying\s*)?(?:monthly\s*)?payments?[^\.\n]*?(?:pslf|public\s+service\s+loan\s+forgiveness))',
                text,
                re.IGNORECASE,
            )
            for m in pslf_matches:
                p_str = m[0] or m[1]
                try:
                    payments = int(p_str)
                    if payments != 120:
                        violations.append(
                            f"PSLF payment requirement contradiction: claimed {payments} payments contradicts statutory requirement of 120 qualifying monthly payments under 34 CFR 685.219"
                        )
                except ValueError:
                    pass

        is_valid = len(violations) == 0
        return is_valid, violations

    def assert_tenant_isolation(self, tenant: str, text: str) -> None:
        """
        Asserts strict tenant boundary isolation.
        Raises PropertyContaminationError if foreign tokens or banned claims bleed across tenants.
        Zero em-dashes. Zero en-dashes.
        """
        is_valid, violations = self.verify_claim(tenant=tenant, text=text)
        if not is_valid:
            raise PropertyContaminationError(
                f"Tenant isolation assertion failed for '{tenant}': {violations[0]}"
            )


__all__ = [
    "PricingTier",
    "FeatureContract",
    "TenantStatutoryTruth",
    "TenantTruthProfile",
    "TenantFactStore",
    "PropertyContaminationError",
]
