"""
pseofactory Unified Affiliate Partner Registry & Dynamic Routing Engine
Centralized, single-source-of-truth affiliate configuration for pseofactory
properties (ProfitHelm and Prexvo).

Key Invariants:
1. Unified partner registry conforming to AffiliatePartner schema.
2. Property isolation: strict boundary enforcement preventing B2B monetization
   on Prexvo and student loan monetization on ProfitHelm.
3. Dynamic environment variable override engine (AFFILIATE_<KEY>_URL) with
   strict URL syntax validation (http/https only, no javascript/relative URLs).
4. Outbound link attributes: rel="noopener sponsored nofollow", target="_blank".
5. Mandatory FTC publisher disclosures and Prexvo Title IV statutory forfeiture disclaimers.
6. Zero em-dashes and zero en-dashes across all partner entries and disclosure copy.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, asdict
import os
from typing import Dict, Any, List, Optional, Set
import urllib.parse

from pseofactory.contracts import assert_no_forbidden_dashes


@dataclass
class AffiliatePartner:
    """
    Unified Affiliate Partner Schema.
    Represents an authorized affiliate monetization partner across pseofactory properties.
    """
    key: str
    name: str
    category: str
    property_id: str
    status: str
    env_var: str
    default_url: str
    badge: str
    commission_est: str
    bounty_est: str
    network: str
    description: str
    target_tools: List[str]
    supported_params: List[str]
    cta_text: str = ""

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ProfitHelm Disclosures & Monetization Registry
# ---------------------------------------------------------------------------

PROFITHELM_DISCLOSURES: Dict[str, str] = {
    "ftc_disclosure": (
        "ProfitHelm is an independent financial research publisher. We may earn a commission "
        "when you register or subscribe through approved affiliate links on this site (CoinLedger, Koinly) "
        "at no additional cost to you. Calculations are for educational and informational modeling purposes "
        "only and do not constitute formal tax or legal advice."
    ),
}

PROFITHELM_AFFILIATES: Dict[str, AffiliatePartner] = {
    # Live Crypto Partners
    "coinledger": AffiliatePartner(
        key="coinledger",
        name="CoinLedger Crypto Tax",
        category="Digital Assets",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_COINLEDGER_URL",
        default_url="https://coinledger.io/?fpr=arif-554004",
        badge="Recommended for Digital Assets",
        commission_est="$35-$90/sale",
        bounty_est="$35-$90",
        network="FirstPromoter",
        description="Automated import for 500+ exchanges, DeFi protocols, and NFT marketplaces to generate IRS Form 8949.",
        target_tools=["crypto-tax-calculator", "prediction-market-tax"],
        supported_params=["fpr", "ph_tier"],
        cta_text="Calculate & Export Crypto Taxes with CoinLedger",
    ),
    "koinly": AffiliatePartner(
        key="koinly",
        name="Koinly Crypto Tax Software",
        category="Digital Assets",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_KOINLY_URL",
        default_url="https://koinly.io/?via=A4FABF09&utm_source=affiliate",
        badge="Multi-Country Support",
        commission_est="$40-$100/sale",
        bounty_est="$40-$100",
        network="FirstPromoter",
        description="Track cryptocurrency portfolios and generate country-specific tax reports in minutes.",
        target_tools=["crypto-tax-calculator"],
        supported_params=["via", "ph_tier"],
        cta_text="Track Crypto Portfolios with Koinly",
    ),

    # Pending Business Banking Slots
    "mercury": AffiliatePartner(
        key="mercury",
        name="Mercury Startup Banking",
        category="Business Banking",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_MERCURY_URL",
        default_url="https://mercury.com/",
        badge="Built for High-Growth Startups",
        commission_est="$150-$300/approval",
        bounty_est="$250 bonus / $150-$300",
        network="In-House Direct",
        description="FDIC-insured business checking, treasury yield, and automated runway management for founders.",
        target_tools=["saas-runway-calculator", "treasury-yield-calculator"],
        supported_params=["ph_tier"],
        cta_text="Apply for Mercury Startup Banking",
    ),
    "stripe": AffiliatePartner(
        key="stripe",
        name="Stripe Treasury & Payments",
        category="B2B Treasury / Commercial Banking",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_STRIPE_URL",
        default_url="https://stripe.com/",
        badge="Enterprise Financial Infrastructure",
        commission_est="$150-$300/account",
        bounty_est="$150-$300",
        network="In-House Direct",
        description="Global financial infrastructure and embedded banking platform for internet businesses, SaaS startups, and enterprises.",
        target_tools=["saas-runway-calculator"],
        supported_params=["ph_tier"],
        cta_text="Explore Stripe Financial Infrastructure",
    ),

    # High-Bounty B2B Opportunities
    "ramp": AffiliatePartner(
        key="ramp",
        name="Ramp Corporate Card & Spend Management",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending_expansion",
        env_var="AFFILIATE_RAMP_URL",
        default_url="https://ramp.com/",
        badge="Automated Founder Spend Control",
        commission_est="$500 flat",
        bounty_est="$500 flat",
        network="In-House Direct",
        description="Automated expense controls, spend limits, and 1.5% cashback corporate cards to stretch startup runway.",
        target_tools=["saas-runway-calculator", "section-179-calculator"],
        supported_params=["ph_tier"],
        cta_text="Apply for Ramp Corporate Card",
    ),
    "rho": AffiliatePartner(
        key="rho",
        name="Rho Commercial Banking & Treasury",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending_expansion",
        env_var="AFFILIATE_RHO_URL",
        default_url="https://rho.co/",
        badge="Enterprise Treasury Yield",
        commission_est="$500-$1000",
        bounty_est="$500-$1000",
        network="In-House Direct",
        description="Automated treasury yield and commercial banking for funded startups and scaling entities.",
        target_tools=["saas-runway-calculator", "qsbs-section-1202-tax-calculator"],
        supported_params=["ph_tier"],
        cta_text="Explore Rho Commercial Treasury",
    ),
    "gusto": AffiliatePartner(
        key="gusto",
        name="Gusto Payroll & HR",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending_expansion",
        env_var="AFFILIATE_GUSTO_URL",
        default_url="https://gusto.com/",
        badge="Modern Team Payroll",
        commission_est="$300 flat",
        bounty_est="$300 flat",
        network="PartnerStack",
        description="Modern payroll, benefits, and HR management built for growing teams and startups.",
        target_tools=["saas-runway-calculator"],
        supported_params=["ph_tier"],
        cta_text="Optimize Payroll with Gusto",
    ),
    "rippling": AffiliatePartner(
        key="rippling",
        name="Rippling Unified Workforce Platform",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending_expansion",
        env_var="AFFILIATE_RIPPLING_URL",
        default_url="https://rippling.com/",
        badge="Global Workforce Management",
        commission_est="Up to $1600",
        bounty_est="Up to $1600",
        network="PartnerStack",
        description="Unified HR, IT, and payroll infrastructure for scaling tech companies and distributed teams.",
        target_tools=["saas-runway-calculator"],
        supported_params=["ph_tier"],
        cta_text="Schedule Rippling Demo",
    ),

    # Supporting Partners
    "crest_capital": AffiliatePartner(
        key="crest_capital",
        name="Crest Capital Equipment Financing",
        category="Equipment Financing",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_CREST_CAPITAL_URL",
        default_url="https://www.crestcapital.com/",
        badge="Section 179 & MACRS Specialist",
        commission_est="$100-$300/funded deal",
        bounty_est="$100-$300",
        network="In-House Direct",
        description="Direct lender providing Section 179 and MACRS equipment financing, vehicle leasing, and capital write-off solutions.",
        target_tools=["section-179-calculator"],
        supported_params=["ph_tier"],
        cta_text="Finance Section 179 Equipment with Crest Capital",
    ),
    "ipx1031": AffiliatePartner(
        key="ipx1031",
        name="IPX1031 Qualified Intermediary",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_IPX1031_URL",
        default_url="https://www.ipx1031.com/start-an-exchange/?utm_source=profithelm&utm_medium=referral&utm_campaign=section_1031_calculator",
        badge="Fidelity Backed / $100M Insured",
        commission_est="$250-$750/qualified exchange",
        bounty_est="$250-$750",
        network="In-House Direct",
        description="Nation's leading qualified intermediary backed by Fidelity National Financial with $100M bond protection.",
        target_tools=["section-1031-calculator"],
        supported_params=["ph_tier"],
        cta_text="Initiate Qualified 1031 Exchange",
    ),
    "turbotax": AffiliatePartner(
        key="turbotax",
        name="TurboTax Premier & Live CPA",
        category="Tax Intelligence",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_TURBOTAX_URL",
        default_url="https://turbotax.intuit.com/",
        badge="Top Rated for 2026/2027 Returns",
        commission_est="$45-$120/sale",
        bounty_est="$45-$120",
        network="Commission Junction",
        description="File complex investments, crypto gains, and small business returns with dedicated CPA review.",
        target_tools=["irs-2027-tax-brackets", "tcja-sunset-bracket-calculator"],
        supported_params=["ph_tier"],
        cta_text="Calculate & File with TurboTax",
    ),
    "taxslayer": AffiliatePartner(
        key="taxslayer",
        name="TaxSlayer Pro",
        category="Tax Intelligence",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_TAXSLAYER_URL",
        default_url="https://www.taxslayer.com/",
        badge="Best Value",
        commission_est="$30-$60/sale",
        bounty_est="$30-$60",
        network="Commission Junction",
        description="Low-cost electronic filing with comprehensive support for investment and self-employment schedules.",
        target_tools=["irs-2027-tax-brackets"],
        supported_params=["ph_tier"],
        cta_text="Calculate & File with TaxSlayer",
    ),
    "kalshi": AffiliatePartner(
        key="kalshi",
        name="Kalshi Prediction Markets",
        category="Market Arbitrage",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_KALSHI_URL",
        default_url="https://kalshi.com/",
        badge="CFTC Regulated",
        commission_est="$80-$150/funded account",
        bounty_est="$80-$150",
        network="In-House Direct",
        description="CFTC-regulated exchange to trade event contracts on interest rates, inflation, and political milestones.",
        target_tools=["prediction-market-tax", "prediction-market-odds"],
        supported_params=["ph_tier"],
        cta_text="Trade Regulated Event Contracts on Kalshi",
    ),
    "interactive_brokers": AffiliatePartner(
        key="interactive_brokers",
        name="Interactive Brokers (IBKR)",
        category="Yield Arbitrage",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_IBKR_URL",
        default_url="https://www.interactivebrokers.com/",
        badge="Institutional Execution",
        commission_est="$100-$200/account",
        bounty_est="$100-$200",
        network="In-House Direct",
        description="Global multi-asset brokerage with industry-leading margin rates and professional order routing.",
        target_tools=["treasury-yield-calculator"],
        supported_params=["ph_tier"],
        cta_text="Explore Interactive Brokers Yield",
    ),
    "exeter1031": AffiliatePartner(
        key="exeter1031",
        name="The Exeter 1031 Exchange",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_EXETER1031_URL",
        default_url="https://www.exeterco.com/",
        badge="Reverse & Improvement Specialist",
        commission_est="$300-$800/exchange",
        bounty_est="$300-$800",
        network="In-House Direct",
        description="Nationwide qualified intermediary, exchange accommodation titleholder, and reverse exchange specialist.",
        target_tools=["section-1031-calculator"],
        supported_params=["ph_tier"],
        cta_text="Initiate Qualified 1031 Exchange",
    ),
    "first_american": AffiliatePartner(
        key="first_american",
        name="First American Exchange Company",
        category="Commercial Real Estate",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_FIRST_AMERICAN_URL",
        default_url="https://www.firstexchange.com/",
        badge="Institutional Qualified Intermediary",
        commission_est="$300-$800/exchange",
        bounty_est="$300-$800",
        network="In-House Direct",
        description="Leading Qualified Intermediary facilitating Section 1031 tax-deferred property exchanges nationwide.",
        target_tools=["section-1031-calculator"],
        supported_params=["ph_tier"],
        cta_text="Initiate Qualified 1031 Exchange",
    ),
}


# ---------------------------------------------------------------------------
# Prexvo Disclosures, Standing Restriction & Monetization Registry
# ---------------------------------------------------------------------------

PREXVO_STANDING_RESTRICTION: str = (
    "Strict prohibition on B2B monetization on Prexvo student loan pages. "
    "Prexvo visitors seek defensive relief from federal student debt (RAP, IBR, SAVE, PSLF) "
    "and possess zero corporate spending authority. Student loan refinance hypothesis remains "
    "conditional pending Gate 1 (written payout >= $45) and requires mandatory YMYL warning "
    "that refinancing federal loans permanently forfeits federal protections."
)

PREXVO_DISCLOSURES: Dict[str, str] = {
    "ymyl_forfeiture_disclaimer": (
        "Refinancing federal student loans permanently eliminates federal protections, "
        "including income-driven repayment (IDR), Public Service Loan Forgiveness (PSLF), "
        "federal interest subsidies, mandatory deferment, and forbearance options."
    ),
    "ftc_disclosure": (
        "Prexvo is an independent financial education and research publisher. "
        "We may receive compensation from partner networks (such as Splash Financial, SoFi, Credible, Earnest, or LendKey) "
        "when you click or qualify for loan offers at no additional cost to you. "
        "Prexvo does not provide personalized financial, investment, or legal advice."
    ),
    "disclaimer_no_advice": (
        "Prexvo does not provide personalized financial, investment, or legal advice. "
        "All calculations, comparisons, and schedules are provided strictly for educational "
        "and informational modeling purposes pursuant to Title IV statutory formulas."
    ),
}

PREXVO_AFFILIATES: Dict[str, AffiliatePartner] = {
    "splash_financial": AffiliatePartner(
        key="splash_financial",
        name="Splash Financial",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending_p2",
        env_var="AFFILIATE_SPLASH_FINANCIAL_URL",
        default_url="https://www.splashfinancial.com/",
        badge="Multi-Lender Comparison",
        commission_est="$200-$240/funded loan",
        bounty_est="$200-$240",
        network="Impact.com",
        description="Compare competing fixed and variable rate refinancing offers across multiple lenders with a single soft inquiry.",
        target_tools=["student-loan-repayment-calculator", "rap-vs-ibr-calculator"],
        supported_params=[],
        cta_text="Compare Rates with Splash Financial",
    ),
    "sofi": AffiliatePartner(
        key="sofi",
        name="SoFi",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending_p2",
        env_var="AFFILIATE_SOFI_URL",
        default_url="https://www.sofi.com/",
        badge="Zero Origination Fee",
        commission_est="$120/funded loan",
        bounty_est="$120",
        network="In-House Direct",
        description="Zero origination fee refinancing with unemployment protection, career coaching, and member rate discounts.",
        target_tools=["student-loan-repayment-calculator"],
        supported_params=[],
        cta_text="Check Rates with SoFi",
    ),
    "credible": AffiliatePartner(
        key="credible",
        name="Credible",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending_p2",
        env_var="AFFILIATE_CREDIBLE_URL",
        default_url="https://www.credible.com/",
        badge="Prequalified Rate Engine",
        commission_est="$100-$150/lead",
        bounty_est="$100-$150",
        network="Impact.com",
        description="Multi-lender comparison engine showing prequalified rates and monthly payment projections in two minutes.",
        target_tools=["student-loan-repayment-calculator"],
        supported_params=[],
        cta_text="Compare Rates with Credible",
    ),
    "earnest": AffiliatePartner(
        key="earnest",
        name="Earnest",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending_p2",
        env_var="AFFILIATE_EARNEST_URL",
        default_url="https://www.earnest.com/",
        badge="Custom Term Matching",
        commission_est="$150-$200/funded loan",
        bounty_est="$150-$200",
        network="In-House Direct",
        description="Customizable repayment terms, precision monthly payment matching, and biweekly autopay interest rate discounts.",
        target_tools=["student-loan-repayment-calculator"],
        supported_params=[],
        cta_text="Check Rates with Earnest",
    ),
    "lendkey": AffiliatePartner(
        key="lendkey",
        name="LendKey",
        category="Student Loan Refinance",
        property_id="prexvo",
        status="pending_p2",
        env_var="AFFILIATE_LENDKEY_URL",
        default_url="https://www.lendkey.com/",
        badge="Credit Union Network",
        commission_est="$100-$150/funded loan",
        bounty_est="$100-$150",
        network="In-House Direct",
        description="Community bank and credit union network offering relationship-based student refinancing terms.",
        target_tools=["student-loan-repayment-calculator"],
        supported_params=[],
        cta_text="Explore Community Rates with LendKey",
    ),
}

# Unified Master Registry
AFFILIATE_REGISTRY: Dict[str, AffiliatePartner] = {
    **PROFITHELM_AFFILIATES,
    **PREXVO_AFFILIATES,
}

# Boundary Sets
B2B_PARTNER_KEYS: Set[str] = {
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

STUDENT_LOAN_PARTNER_KEYS: Set[str] = {
    "splash_financial",
    "sofi",
    "credible",
    "earnest",
    "lendkey",
}

PROFITHELM_TOOL_PATTERNS: List[str] = [
    "section-179",
    "179",
    "crypto",
    "staking",
    "token",
    "saas",
    "runway",
    "1031",
    "arbitrage",
    "prediction",
    "odds",
    "treasury",
    "yield",
    "qsbs",
    "1202",
    "bracket",
    "tcja",
    "tax",
]

PREXVO_TOOL_PATTERNS: List[str] = [
    "student-loan",
    "rap",
    "ibr",
    "save",
    "pslf",
    "icr",
    "paye",
    "consolidation",
    "refinance",
    "repayment",
]


# ---------------------------------------------------------------------------
# URL Validation & Parameter Encoding Engine
# ---------------------------------------------------------------------------

def validate_affiliate_url(url: str) -> bool:
    """
    Validates an affiliate URL.
    Enforces:
    - Non-empty string
    - Scheme must be http or https
    - Netloc must be present
    - No javascript:, data:, or relative URLs
    - Zero em-dashes and zero en-dashes
    """
    if not url or not isinstance(url, str):
        return False
    url_clean = url.strip()
    if not url_clean:
        return False
    # Check for forbidden dashes
    if "\u2014" in url_clean or "\u2013" in url_clean:
        return False
    try:
        parsed = urllib.parse.urlsplit(url_clean)
    except Exception:
        return False
    if parsed.scheme.lower() not in ("https", "http"):
        return False
    if not parsed.netloc:
        return False
    url_lower = url_clean.lower()
    if "javascript:" in url_lower or "data:" in url_lower:
        return False
    return True


def resolve_partner_url(
    partner: AffiliatePartner,
    value_tier: str = "starter",
    extra_params: Optional[Dict[str, str]] = None,
) -> str:
    """
    Resolves destination URL for an affiliate partner.
    Supports environment variable overrides (AFFILIATE_<KEY>_URL).
    Appends supported vendor-namespaced tracking parameters (ph_tier) without clobbering base parameters.
    """
    env_override = os.getenv(partner.env_var)
    if env_override and env_override.strip():
        raw_url = env_override.strip()
    else:
        raw_url = partner.default_url.strip()

    if not validate_affiliate_url(raw_url):
        raise ValueError(
            f"Invalid affiliate URL '{raw_url}' for partner '{partner.key}' (env: {partner.env_var})"
        )

    parsed = urllib.parse.urlsplit(raw_url)
    existing_query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_params = list(existing_query)
    existing_keys = {k for k, _ in query_params}

    if extra_params:
        for k, v in extra_params.items():
            if k in partner.supported_params or not partner.supported_params:
                query_params = [(qk, qv) for qk, qv in query_params if qk != k]
                query_params.append((k, str(v)))

    # Only append ph_tier if supported and tier is escalated beyond starter
    if "ph_tier" in partner.supported_params and value_tier and value_tier != "starter":
        if "ph_tier" not in existing_keys:
            query_params.append(("ph_tier", value_tier))

    if query_params:
        new_query = urllib.parse.urlencode(query_params)
    else:
        new_query = ""

    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
    )


def get_affiliates_for_property(property_id: str) -> Dict[str, AffiliatePartner]:
    """Returns partner dictionary for a declared property."""
    prop_clean = (property_id or "").strip().lower()
    if prop_clean in ("profithelm", "exchange1031"):
        return dict(PROFITHELM_AFFILIATES)
    elif prop_clean == "prexvo":
        return dict(PREXVO_AFFILIATES)
    raise ValueError(f"Unknown property_id: '{property_id}'")


# ---------------------------------------------------------------------------
# Dynamic Route Resolver
# ---------------------------------------------------------------------------

def _select_partner_for_slug(property_id: str, slug: str) -> str:
    """Internal helper to match a tool slug to default partner key."""
    s = (slug or "").lower().strip()
    if property_id in ("profithelm", "exchange1031"):
        if "179" in s or "macrs" in s:
            return "crest_capital"
        if "crypto" in s or "token" in s or "staking" in s:
            return "coinledger"
        if "saas" in s or "runway" in s:
            return "mercury"
        if "1031" in s:
            return "ipx1031"
        if "arbitrage" in s or "prediction" in s or "odds" in s:
            return "kalshi"
        if "treasury" in s or "yield" in s:
            return "interactive_brokers"
        if "qsbs" in s or "1202" in s:
            return "rho"
        if "tax" in s or "tcja" in s or "bracket" in s:
            return "turbotax"
        return "turbotax"
    elif property_id == "prexvo":
        return "splash_financial"
    return ""


def get_affiliate_route(
    property_id: str,
    tool_slug: str = "",
    value_tier: str = "starter",
    partner_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns programmatic affiliate route contracts with guaranteed link attributes.
    Enforces strict property isolation:
    - Raises ValueError if B2B partner requested for Prexvo.
    - Raises ValueError if student loan partner requested for ProfitHelm.
    - Guarantees rel='noopener sponsored nofollow' and target='_blank'.
    """
    prop_clean = (property_id or "").strip().lower()
    if prop_clean not in ("profithelm", "prexvo", "exchange1031"):
        raise ValueError(f"Unknown or unsupported property: '{property_id}'")

    selected_key = (partner_key or "").strip().lower()

    # Property boundary checks when partner_key is provided
    if selected_key:
        if prop_clean == "prexvo":
            if selected_key in B2B_PARTNER_KEYS or selected_key in PROFITHELM_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: B2B partner '{selected_key}' is prohibited on Prexvo."
                )
            if selected_key not in PREXVO_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in Prexvo affiliate registry."
                )
        elif prop_clean in ("profithelm", "exchange1031"):
            if selected_key in STUDENT_LOAN_PARTNER_KEYS or selected_key in PREXVO_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: Student loan partner '{selected_key}' is prohibited on ProfitHelm."
                )
            if selected_key not in PROFITHELM_AFFILIATES:
                raise ValueError(
                    f"Partner '{selected_key}' not found in ProfitHelm affiliate registry."
                )
    else:
        # Slug boundary validation and auto-selection
        slug_clean = (tool_slug or "").strip().lower()
        if prop_clean == "prexvo":
            for b2b_token in ("saas-runway", "section-179", "section-1031", "qsbs-section-1202"):
                if b2b_token in slug_clean:
                    raise ValueError(
                        f"Strict isolation violation: Commercial tool '{tool_slug}' is prohibited on Prexvo."
                    )
        elif prop_clean in ("profithelm", "exchange1031"):
            for sl_token in ("student-loan", "rap-vs-ibr", "pslf"):
                if sl_token in slug_clean:
                    raise ValueError(
                        f"Strict isolation violation: Student loan tool '{tool_slug}' is prohibited on ProfitHelm."
                    )
        selected_key = _select_partner_for_slug(prop_clean, slug_clean)

    # Retrieve partner object
    catalog = get_affiliates_for_property(prop_clean)
    partner_obj = catalog.get(selected_key)
    if not partner_obj:
        raise ValueError(f"Partner '{selected_key}' could not be resolved for property '{property_id}'")

    # Resolve URL
    resolved_url = resolve_partner_url(partner_obj, value_tier=value_tier)

    # Escalated CTA text
    tier_clean = (value_tier or "starter").strip().lower()
    is_premium = (tier_clean == "premium")

    if partner_obj.key == "coinledger":
        cta_text = "Import 100+ Transactions to CoinLedger Pro" if is_premium else "Calculate & Export Crypto Taxes with CoinLedger"
    elif partner_obj.key == "koinly":
        cta_text = "Export Multi-Year Crypto Reports with Koinly Pro" if is_premium else "Track Crypto Portfolios with Koinly"
    elif partner_obj.key == "turbotax":
        cta_text = "Connect with TurboTax Live CPA" if is_premium else "Calculate & File with TurboTax"
    elif partner_obj.key == "taxslayer":
        cta_text = "File Complex Schedules with TaxSlayer Pro" if is_premium else "Calculate & File with TaxSlayer"
    elif partner_obj.key == "mercury":
        cta_text = "Open Mercury Treasury Yield Account" if is_premium else "Apply for Mercury Startup Banking"
    elif partner_obj.key == "stripe":
        cta_text = "Launch Stripe Treasury & Payments Infrastructure" if is_premium else "Explore Stripe Financial Infrastructure"
    elif partner_obj.key == "ramp":
        cta_text = "Accelerate Spend Controls with Ramp Corporate Card" if is_premium else "Apply for Ramp Corporate Card"
    elif partner_obj.key == "rho":
        cta_text = "Maximize Yield with Rho Commercial Treasury" if is_premium else "Explore Rho Commercial Treasury"
    elif partner_obj.key == "gusto":
        cta_text = "Scale Automated Payroll with Gusto Pro" if is_premium else "Optimize Payroll with Gusto"
    elif partner_obj.key == "rippling":
        cta_text = "Deploy Global Workforce with Rippling" if is_premium else "Schedule Rippling Demo"
    elif partner_obj.key == "crest_capital":
        cta_text = "Accelerate Deductions with Crest Capital Pro" if is_premium else "Finance Section 179 Equipment with Crest Capital"
    elif partner_obj.key in ("ipx1031", "exeter1031", "first_american"):
        cta_text = "Initiate Institutional 1031 Exchange" if is_premium else "Initiate Qualified 1031 Exchange"
    elif partner_obj.key == "kalshi":
        cta_text = "Trade Institutional Event Contracts on Kalshi" if is_premium else "Trade Regulated Event Contracts on Kalshi"
    elif partner_obj.key == "interactive_brokers":
        cta_text = "Trade Institutional Fixed Income on IBKR" if is_premium else "Explore Interactive Brokers Yield"
    elif partner_obj.key == "splash_financial":
        cta_text = "Lock In Refinance Terms with Splash Financial" if is_premium else "Compare Rates with Splash Financial"
    elif partner_obj.key == "sofi":
        cta_text = "Unlock Member Rate Discounts with SoFi" if is_premium else "Check Rates with SoFi"
    elif partner_obj.key == "credible":
        cta_text = "Lock In Prequalified Rates with Credible" if is_premium else "Compare Rates with Credible"
    elif partner_obj.key == "earnest":
        cta_text = "Customize Precision Schedule with Earnest" if is_premium else "Check Rates with Earnest"
    elif partner_obj.key == "lendkey":
        cta_text = "Access Relationship Rates with LendKey" if is_premium else "Explore Community Rates with LendKey"
    else:
        cta_text = partner_obj.cta_text or (
            f"Explore {partner_obj.name} Pro Solutions" if is_premium else f"Explore {partner_obj.name} Solutions"
        )

    # Validate output for forbidden dashes
    assert_no_forbidden_dashes(cta_text, context=f"CTA text for {partner_obj.key}")
    assert_no_forbidden_dashes(partner_obj.name, context=f"Partner name for {partner_obj.key}")
    assert_no_forbidden_dashes(partner_obj.badge, context=f"Badge for {partner_obj.key}")

    return {
        "property_id": prop_clean,
        "partner": partner_obj.key,
        "partner_key": partner_obj.key,
        "name": partner_obj.name,
        "url": resolved_url,
        "cta_text": cta_text,
        "rel": "noopener sponsored nofollow",
        "target": "_blank",
        "badge": partner_obj.badge,
        "status": partner_obj.status,
        "tier": value_tier,
        "disclosure_required": True,
    }


# Self-attestation on module import
for _p_dict in (PROFITHELM_AFFILIATES, PREXVO_AFFILIATES):
    for _p_key, _p_val in _p_dict.items():
        assert_no_forbidden_dashes(_p_val.name, context=f"Affiliate name {_p_key}")
        assert_no_forbidden_dashes(_p_val.description, context=f"Affiliate description {_p_key}")
        assert_no_forbidden_dashes(_p_val.badge, context=f"Affiliate badge {_p_key}")
        assert_no_forbidden_dashes(_p_val.commission_est, context=f"Affiliate commission_est {_p_key}")
        assert_no_forbidden_dashes(_p_val.bounty_est, context=f"Affiliate bounty_est {_p_key}")
        assert_no_forbidden_dashes(_p_val.cta_text, context=f"Affiliate cta_text {_p_key}")
        if not validate_affiliate_url(_p_val.default_url):
            raise ValueError(f"Default URL invalid for partner {_p_key}: {_p_val.default_url}")

for _d_dict in (PROFITHELM_DISCLOSURES, PREXVO_DISCLOSURES):
    for _d_key, _d_text in _d_dict.items():
        assert_no_forbidden_dashes(_d_text, context=f"Disclosure {_d_key}")

assert_no_forbidden_dashes(PREXVO_STANDING_RESTRICTION, context="Prexvo standing restriction")
