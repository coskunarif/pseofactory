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
import re
from typing import Dict, Any, List, Optional, Set, Tuple
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

    @property
    def url(self) -> str:
        return resolve_partner_url(self)

    @property
    def estimated_bounty(self) -> str:
        return self.bounty_est

    def __getitem__(self, item: str) -> Any:
        if not isinstance(item, str):
            raise KeyError(item)
        if item == "url":
            return self.url
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "url":
            return self.url
        return getattr(self, item, default)

    def __contains__(self, item: Any) -> bool:
        if not isinstance(item, str):
            return False
        if item == "url":
            return True
        return hasattr(self, item)

    def keys(self) -> List[str]:
        return list(asdict(self).keys()) + ["url"]

    def values(self) -> List[Any]:
        return [getattr(self, k) if k != "url" else self.url for k in self.keys()]

    def items(self) -> List[Tuple[str, Any]]:
        return [(k, self[k]) for k in self.keys()]

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

    # Live Business Banking Slots
    "mercury": AffiliatePartner(
        key="mercury",
        name="Mercury Startup Banking",
        category="Business Banking",
        property_id="profithelm",
        status="live",
        env_var="AFFILIATE_MERCURY_URL",
        default_url="https://mercury.com/r/profithelm-llc",
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
        status="live",
        env_var="AFFILIATE_RIPPLING_URL",
        default_url="https://try.rippling.com/mcfo1m09qiwt",
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
        status="live",
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
        target_tools=[
            "prediction-market-tax",
            "prediction-market-odds",
            "prediction-market-ev",
            "prediction-market-kelly-criterion",
            "prediction-market-implied-probability",
            "prediction-market-kalshi-fees",
            "prediction-market-arbitrage",
            "prediction-market-vig-spread",
            "prediction-market-break-even",
        ],
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
    "simply_business": AffiliatePartner(
        key="simply_business",
        name="Simply Business Commercial Insurance",
        category="Commercial Insurance & Workers Comp",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_SIMPLY_BUSINESS_URL",
        default_url="https://www.simplybusiness.com/",
        badge="Instant Multi-Carrier Quotes",
        commission_est="$35-$100/bound policy",
        bounty_est="$35-$100",
        network="CJ Affiliate / Impact",
        description="Compare instant workers compensation, general liability, and commercial contractor insurance quotes across top carriers.",
        target_tools=[
            "workers-comp-and-payroll-burden-calculator",
            "contractor-surety-bond-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Compare Commercial Workers Comp Quotes",
    ),
    "suretybonds_direct": AffiliatePartner(
        key="suretybonds_direct",
        name="SuretyBonds.com Instant Bond Underwriting",
        category="Commercial Surety & Bonds",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_SURETYBONDS_DIRECT_URL",
        default_url="https://www.suretybonds.com/",
        badge="Nationwide Statutory Bonds",
        commission_est="20% premium share ($75-$300)",
        bounty_est="$75-$300",
        network="In-House Direct",
        description="Instant online underwriting for contractor license bonds, performance bonds, freight broker BMC-84 bonds, and ERISA fidelity bonds.",
        target_tools=["contractor-surety-bond-cost-calculator"],
        supported_params=["ph_tier"],
        cta_text="Get Instant Contractor Surety Bond Quote",
    ),
    "next_insurance_b2b": AffiliatePartner(
        key="next_insurance_b2b",
        name="Next Insurance Commercial Coverage",
        category="Commercial Insurance & Workers Comp",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_NEXT_INSURANCE_B2B_URL",
        default_url="https://www.nextinsurance.com/",
        badge="Instant Certificate of Insurance",
        commission_est="$25-$150/qualified quote",
        bounty_est="$25-$150",
        network="Impact.com",
        description="Digital commercial insurance providing instant certificates of insurance for workers compensation, general liability, and commercial auto.",
        target_tools=[
            "workers-comp-and-payroll-burden-calculator",
            "contractor-surety-bond-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Get Instant Commercial Coverage with Next Insurance",
    ),
    "national_funding_med": AffiliatePartner(
        key="national_funding_med",
        name="National Funding Equipment & Practice Finance",
        category="Equipment Financing",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_NATIONAL_FUNDING_MED_URL",
        default_url="https://www.nationalfunding.com/",
        badge="Up to $500K Equipment Financing",
        commission_est="$200-$750/funded deal",
        bounty_est="$200-$750",
        network="Impact.com",
        description="Fast equipment leasing and commercial working capital loans for medical practices, dental clinics, and heavy commercial operators.",
        target_tools=[
            "medical-and-dental-equipment-section-179-roi-calculator",
            "equipment-lease-vs-buy-section-179-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Check Equipment Financing Rates with National Funding",
    ),
    "otr_solutions_factoring": AffiliatePartner(
        key="otr_solutions_factoring",
        name="OTR Solutions Commercial Factoring & Working Capital",
        category="Corporate Finance",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_OTR_SOLUTIONS_FACTORING_URL",
        default_url="https://www.otrsolutions.com/",
        badge="Same-Day Non-Recourse Factoring",
        commission_est="$150-$450/funded client",
        bounty_est="$150-$450",
        network="In-House Direct",
        description="Non-recourse invoice factoring, working capital advances, and customs liquidity solutions for commercial supply chains and fleets.",
        target_tools=[
            "invoice-factoring-vs-business-line-of-credit-calculator",
            "section-301-tariff-landed-cost-calculator",
        ],
        supported_params=["ph_tier"],
        cta_text="Unlock Same-Day Invoice Factoring with OTR Solutions",
    ),
    "freightos_marketplace": AffiliatePartner(
        key="freightos_marketplace",
        name="Freightos Global Freight & Customs Marketplace",
        category="Customs & Trade Finance",
        property_id="profithelm",
        status="pending",
        env_var="AFFILIATE_FREIGHTOS_MARKETPLACE_URL",
        default_url="https://www.freightos.com/",
        badge="Instant Ocean, Air & Customs Quotes",
        commission_est="$50-$200/qualified shipper",
        bounty_est="$50-$200",
        network="Impact.com",
        description="Digital international freight marketplace comparing ocean, air, and customs brokerage quotes with Section 301 duty transparency.",
        target_tools=["section-301-tariff-landed-cost-calculator"],
        supported_params=["ph_tier"],
        cta_text="Compare International Freight & Customs Rates on Freightos",
    ),
}

# Legacy Aliases
PROFITHELM_AFFILIATES["equipment_macrs"] = PROFITHELM_AFFILIATES["crest_capital"]
PROFITHELM_AFFILIATES["first_american_1031"] = PROFITHELM_AFFILIATES["first_american"]


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
    "public_service_non_commercial_notice": (
        "Public Service Protection Notice: Commercial private lender offers are strictly suppressed "
        "on Public Service Loan Forgiveness (PSLF), statutory hardship, and federal discharge pages "
        "to protect borrower eligibility under Title IV 34 CFR Part 685."
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
AFFILIATE_REGISTRY["equipment_macrs"] = PROFITHELM_AFFILIATES["crest_capital"]
AFFILIATE_REGISTRY["first_american_1031"] = PROFITHELM_AFFILIATES["first_american"]

# Boundary Sets
B2B_PARTNER_KEYS: Set[str] = {
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
    "simply_business",
    "suretybonds_direct",
    "next_insurance_b2b",
    "national_funding_med",
    "otr_solutions_factoring",
    "freightos_marketplace",
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
    "ev",
    "kelly",
    "implied-probability",
    "kalshi-fees",
    "vig-spread",
    "break-even",
    "treasury",
    "yield",
    "qsbs",
    "1202",
    "bracket",
    "tcja",
    "tax",
    "s-corp",
    "workers-comp",
    "surety-bond",
    "section-301",
    "invoice-factoring",
    "section-174",
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

ENTERPRISE_B2B_PARTNERS: Set[str] = {
    "mercury",
    "ramp",
    "rho",
    "gusto",
    "rippling",
    "stripe",
    "crest_capital",
    "ipx1031",
    "exeter1031",
    "first_american",
    "equipment_macrs",
    "first_american_1031",
    "simply_business",
    "suretybonds_direct",
    "next_insurance_b2b",
    "national_funding_med",
    "otr_solutions_factoring",
    "freightos_marketplace",
}

RETAIL_TAX_PARTNERS: Set[str] = {
    "turbotax",
    "taxslayer",
    "freetaxusa",
}

RETAIL_TAX_SLUGS: Set[str] = {
    "irs-2027-tax-brackets",
    "tcja-sunset-capital-gains",
    "crypto-tax-calculator",
    "tcja-sunset-bracket-calculator",
    "ca-tax-brackets-2026",
    "prediction-market-tax",
    "prediction-market-odds",
}

COMMERCIAL_B2B_SLUGS: Set[str] = {
    "section-179-calculator",
    "section-1031-calculator",
    "saas-runway-calculator",
    "qsbs-section-1202-tax-calculator",
    "treasury-yield-calculator",
    "s-corp-reasonable-salary-tax-calculator",
    "workers-comp-and-payroll-burden-calculator",
    "contractor-surety-bond-cost-calculator",
    "equipment-lease-vs-buy-section-179-calculator",
    "medical-and-dental-equipment-section-179-roi-calculator",
    "commercial-heavy-vehicle-section-179-weight-calculator",
    "section-301-tariff-landed-cost-calculator",
    "invoice-factoring-vs-business-line-of-credit-calculator",
    "r-and-d-tax-credit-section-174-amortization-calculator",
}

PREXVO_RESTRICTED_PUBLIC_SERVICE_SLUGS: Set[str] = {
    "pslf-qualifying-payment-calculator",
    "pslf-qualifying-payment-simulator",
    "pslf-employer-ein-eligibility",
    "save-plan-litigation-transition",
    "save-forbearance-interest-tracker",
    "borrower-defense-discharge-calculator",
    "total-permanent-disability-discharge-calculator",
    "teacher-loan-forgiveness-calculator",
    "closed-school-discharge-calculator",
    "federal-poverty-guideline-discretionary-income-calculator",
}

PREXVO_RESTRICTED_PUBLIC_SERVICE_TOKENS: Tuple[str, ...] = (
    "pslf",
    "public-service",
    "public service",
    "save-plan-litigation",
    "save plan litigation",
    "save-forbearance",
    "forbearance",
    "deferment",
    "borrower-defense",
    "borrower defense",
    "disability-discharge",
    "disability discharge",
    "total-and-permanent-disability",
    "total and permanent disability",
    "total-permanent-disability",
    "teacher-loan-forgiveness",
    "teacher loan forgiveness",
    "closed-school",
    "closed school",
    "low-income",
    "low income",
    "poverty-guideline",
    "poverty guideline",
    "hardship",
)

INTENT_ROUTING_TABLE: Dict[str, List[str]] = {
    "section-1031": ["ipx1031", "exeter1031", "first_american", "mercury"],
    "1031": ["ipx1031", "exeter1031", "first_american", "mercury"],
    "section-179": ["crest_capital", "ramp", "mercury"],
    "179": ["crest_capital", "ramp", "mercury"],
    "macrs": ["crest_capital", "ramp", "mercury"],
    "depreciation": ["crest_capital", "ramp", "mercury"],
    "equipment": ["crest_capital", "ramp", "mercury"],
    "medical-equipment": ["national_funding_med", "crest_capital", "ramp"],
    "workers-comp": ["simply_business", "next_insurance_b2b", "suretybonds_direct"],
    "surety-bond": ["suretybonds_direct", "simply_business", "next_insurance_b2b"],
    "tariff-landed-cost": ["freightos_marketplace", "otr_solutions_factoring", "mercury", "ramp"],
    "invoice-factoring": ["otr_solutions_factoring", "mercury", "ramp", "rho"],
    "s-corp-payroll": ["rippling", "gusto", "mercury", "ramp"],
    "treasury": ["interactive_brokers", "public_com", "wealthfront", "mercury"],
    "yield": ["interactive_brokers", "public_com", "wealthfront", "mercury"],
    "tbill": ["interactive_brokers", "public_com", "wealthfront"],
    "qsbs": ["mercury", "interactive_brokers", "wealthfront", "stripe"],
    "1202": ["mercury", "interactive_brokers", "wealthfront", "stripe"],
    "corporate-amt": ["mercury", "ramp", "rho", "stripe"],
    "r-and-d": ["mercury", "ramp", "gusto", "rippling", "stripe"],
    "runway": ["mercury", "ramp", "rho", "gusto", "rippling", "stripe"],
    "burn": ["mercury", "ramp", "rho", "stripe"],
    "saas": ["mercury", "ramp", "rho", "gusto", "rippling", "stripe"],
    "payroll": ["gusto", "rippling", "mercury", "ramp"],
    "crypto": ["coinledger", "koinly", "turbotax", "taxslayer"],
    "capital-gains": ["wealthfront", "interactive_brokers", "turbotax", "taxslayer"],
    "tax": ["turbotax", "taxslayer", "freetaxusa"],
    "bracket": ["turbotax", "taxslayer", "freetaxusa"],
    "tcja": ["turbotax", "taxslayer", "freetaxusa"],
    "irs": ["turbotax", "taxslayer", "freetaxusa"],
    "prediction-market-tax": ["coinledger", "kalshi", "turbotax"],
    "prediction": ["kalshi", "interactive_brokers", "turbotax"],
    "student-loan": ["splash_financial", "sofi_refi", "earnest", "credible", "laurel_road", "juno"],
}


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
    - No localhost, loopback, or SSRF link-local metadata endpoints
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

    # SSRF protection: reject localhost, loopback, link-local metadata, cloud metadata DNS, and private IP addresses
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    if hostname in ("localhost", "127.0.0.1", "::1", "169.254.169.254"):
        return False
    if hostname.endswith(".local") or hostname.endswith(".localhost"):
        return False
    if hostname.startswith("127.") or hostname.startswith("169.254."):
        return False
    if hostname in ("metadata.google.internal", "instance-data", "metadata") or hostname.endswith(".metadata.google.internal"):
        return False

    try:
        import ipaddress
        ip = None
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            # Parse integer, hex, or octal IP encodings
            ip_int = None
            if hostname.isdigit():
                ip_int = int(hostname)
            elif hostname.startswith("0x") or hostname.startswith("0X"):
                try:
                    ip_int = int(hostname, 16)
                except ValueError:
                    pass
            elif hostname.startswith("0") and hostname[1:].isdigit():
                try:
                    ip_int = int(hostname, 8)
                except ValueError:
                    pass
            else:
                parts = hostname.split(".")
                if len(parts) == 4:
                    try:
                        octets = [int(p, 0) for p in parts]
                        if all(0 <= o <= 255 for o in octets):
                            ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
                    except (ValueError, TypeError):
                        pass
            if ip_int is not None and 0 <= ip_int <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(ip_int)

        if ip is not None and (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved):
            return False
    except (ValueError, OverflowError):
        pass

    return True


def resolve_partner_url(
    partner: AffiliatePartner,
    value_tier: str = "starter",
    extra_params: Optional[Dict[str, str]] = None,
    tenant: Optional[str] = None,
) -> str:
    """
    Resolves destination URL for an affiliate partner.
    Supports environment variable overrides (AFFILIATE_<KEY>_URL).
    Appends supported vendor-namespaced tracking parameters (ph_tier) without clobbering base parameters.
    Rejects sub-affiliate aggregator redirect domains if property is prexvo.
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

    prop = (tenant or partner.property_id or "").strip().lower()
    if prop == "prexvo":
        netloc_lower = parsed.netloc.lower()
        if any(agg in netloc_lower for agg in ("sovrn", "skimlinks", "viglink")):
            raise ValueError(
                f"Sub-affiliate aggregator redirects are prohibited on Prexvo: '{raw_url}'"
            )

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
# Yield Scoring & Dynamic Route Resolver
# ---------------------------------------------------------------------------

def parse_bounty_estimate(bounty_str: str) -> Dict[str, float]:
    """
    Parses a bounty estimate string into numeric min, max, midpoint, and revshare flag.
    If dollar amounts ($) are present, extracts numeric dollar values.
    If only percentage numbers (%) are present, computes expected dollar value by multiplying percentage points by 2.0.
    Zero em-dashes. Zero en-dashes.
    """
    s = str(bounty_str or "").strip()
    is_revshare = 1.0 if "revshare" in s.lower() else 0.0

    dollar_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"\$\s*([\d,]+(?:\.\d+)?)", s)
    ]
    if dollar_matches:
        min_val = float(min(dollar_matches))
        max_val = float(max(dollar_matches))
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    pct_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"([\d,]+(?:\.\d+)?)\s*%", s)
    ]
    if pct_matches:
        min_val = float(min(pct_matches)) * 2.0
        max_val = float(max(pct_matches)) * 2.0
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    plain_matches = [
        float(m.replace(",", ""))
        for m in re.findall(r"([\d,]+(?:\.\d+)?)", s)
    ]
    if plain_matches:
        min_val = float(min(plain_matches))
        max_val = float(max(plain_matches))
        midpoint = (min_val + max_val) / 2.0
        return {
            "min": min_val,
            "max": max_val,
            "midpoint": midpoint,
            "is_revshare": is_revshare,
        }

    return {
        "min": 0.0,
        "max": 0.0,
        "midpoint": 0.0,
        "is_revshare": is_revshare,
    }


def score_partner_yield(partner: AffiliatePartner, vault_status: Optional[str] = None) -> float:
    """
    Scores expected yield of an affiliate partner weighted by operational status.
    Zero em-dashes. Zero en-dashes.
    """
    effective_status = (vault_status or partner.status or "").strip().lower()
    if effective_status in ("live", "active_direct"):
        weight = 1.0
    elif effective_status == "pending":
        weight = 0.35
    elif effective_status == "pending_expansion":
        weight = 0.25
    elif effective_status == "pending_p2":
        weight = 0.15
    else:
        weight = 0.0
    midpoint = parse_bounty_estimate(partner.bounty_est)["midpoint"]
    return round(midpoint * weight, 4)


def is_commercial_b2b_slug(slug: str) -> bool:
    """Determines whether a calculator slug belongs to the commercial B2B cluster."""
    s = (slug or "").strip().lower()
    if not s:
        return False
    if s in COMMERCIAL_B2B_SLUGS:
        return True
    if s in RETAIL_TAX_SLUGS:
        return False
    b2b_tokens = (
        "section-1031",
        "1031",
        "section-179",
        "179",
        "macrs",
        "depreciation",
        "equipment",
        "treasury",
        "yield",
        "tbill",
        "qsbs",
        "1202",
        "corporate-amt",
        "r-and-d",
        "runway",
        "burn",
        "saas",
        "payroll",
    )
    return any(tok in s for tok in b2b_tokens)


def is_restricted_public_service_slug(slug: str, query: str = "") -> bool:
    """
    Determines whether a Prexvo slug or query targets a restricted public-service
    or statutory hardship page (such as PSLF, SAVE litigation/forbearance, disability
    discharge, borrower defense, teacher loan forgiveness, or poverty-guideline relief)
    where commercial private refinancing offers must be suppressed to preserve YMYL guardrails.
    Zero em-dashes. Zero en-dashes.
    """
    s = (slug or "").strip().lower()
    q = (query or "").strip().lower()
    if s in PREXVO_RESTRICTED_PUBLIC_SERVICE_SLUGS:
        return True
    combined = f"{s} {q}".strip()
    if not combined:
        return False
    return any(tok in combined for tok in PREXVO_RESTRICTED_PUBLIC_SERVICE_TOKENS)


def _extract_partner_vault_status(
    partner_key: str,
    vault_overrides: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not vault_overrides or not isinstance(vault_overrides, dict):
        return None
    direct_entry = vault_overrides.get(partner_key)
    if isinstance(direct_entry, dict):
        st = direct_entry.get("status") or direct_entry.get("state")
        if st:
            return str(st).strip().lower()
    categories = vault_overrides.get("categories")
    if isinstance(categories, dict):
        for cat_v in categories.values():
            if isinstance(cat_v, dict) and cat_v.get("primary_partner") == partner_key:
                st = cat_v.get("status") or cat_v.get("state")
                if st:
                    return str(st).strip().lower()
    for val in vault_overrides.values():
        if isinstance(val, dict) and val.get("primary_partner") == partner_key:
            st = val.get("status") or val.get("state")
            if st:
                return str(st).strip().lower()
    return None


def _resolve_profithelm_bucket(s: str) -> str:
    """Resolves the INTENT_ROUTING_TABLE bucket name for a ProfitHelm calculator slug."""
    if "section-1031" in s or "1031" in s:
        return "section-1031"
    if ("medical" in s or "dental" in s) and ("179" in s or "equipment" in s):
        return "medical-equipment"
    if any(t in s for t in ("section-179", "179", "macrs", "depreciation", "equipment")):
        return "section-179"
    if "workers-comp" in s:
        return "workers-comp"
    if "surety-bond" in s or ("surety" in s and "bond" in s):
        return "surety-bond"
    if "section-301" in s or ("tariff" in s and "landed-cost" in s):
        return "tariff-landed-cost"
    if "invoice-factoring" in s or "factoring" in s:
        return "invoice-factoring"
    if "s-corp" in s:
        return "s-corp-payroll"
    if any(t in s for t in ("treasury", "yield", "tbill")):
        return "treasury"
    if any(t in s for t in ("qsbs", "1202")):
        return "qsbs"
    if "corporate-amt" in s:
        return "corporate-amt"
    if "r-and-d" in s or "section-174" in s:
        return "r-and-d"
    if any(t in s for t in ("runway", "burn", "saas")):
        return "runway"
    if "payroll" in s:
        return "payroll"
    if any(t in s for t in ("crypto", "token", "staking")):
        return "crypto"
    if "capital-gains" in s:
        return "capital-gains"
    if "prediction" in s and "tax" in s:
        return "prediction-market-tax"
    if any(t in s for t in ("prediction", "odds", "arbitrage", "kalshi", "kelly", "ev", "vig", "break-even")):
        return "prediction"
    return "tax"


def resolve_optimal_partner_for_slug(
    property_id: str,
    slug: str,
    vault_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[AffiliatePartner]:
    """
    Resolves the optimal affiliate partner for a property and calculator slug,
    enforcing domain boundaries and prioritizing highest-yielding live partners.
    Suppresses commercial refinance partners on restricted Prexvo public-service pages.
    Zero em-dashes. Zero en-dashes.
    """
    prop = (property_id or "").strip().lower()
    s = (slug or "").strip().lower()

    if prop == "prexvo":
        if is_restricted_public_service_slug(s):
            return None
        candidates: List[AffiliatePartner] = []
        for k, p in PREXVO_AFFILIATES.items():
            if k == p.key and k not in ENTERPRISE_B2B_PARTNERS and k not in B2B_PARTNER_KEYS:
                candidates.append(p)
        live_candidates: List[Tuple[AffiliatePartner, str]] = []
        for p in candidates:
            ov_status = _extract_partner_vault_status(p.key, vault_overrides)
            eff_status = (ov_status or p.status or "").strip().lower()
            if eff_status in ("live", "active_direct"):
                live_candidates.append((p, eff_status))
        if live_candidates:
            best = max(live_candidates, key=lambda item: score_partner_yield(item[0], item[1]))
            return best[0]
        return PREXVO_AFFILIATES.get("splash_financial")

    if prop in ("profithelm", "exchange1031"):
        matched_bucket_name = _resolve_profithelm_bucket(s)
        raw_keys = INTENT_ROUTING_TABLE.get(matched_bucket_name, ["turbotax", "taxslayer", "freetaxusa"])
        is_b2b = is_commercial_b2b_slug(s)
        is_retail = (s in RETAIL_TAX_SLUGS) or (not is_b2b)

        candidates = []
        seen_keys: Set[str] = set()
        for k in raw_keys:
            if k not in PROFITHELM_AFFILIATES:
                continue
            p = PROFITHELM_AFFILIATES[k]
            if p.key in seen_keys:
                continue
            if is_b2b and p.key in RETAIL_TAX_PARTNERS:
                continue
            if is_retail and p.key in ENTERPRISE_B2B_PARTNERS:
                continue
            seen_keys.add(p.key)
            candidates.append(p)

        if not candidates:
            fallback_key = "mercury" if is_b2b else "turbotax"
            return PROFITHELM_AFFILIATES.get(fallback_key)

        live_candidates = []
        explicit_vault_live_keys: Set[str] = set()
        for p in candidates:
            ov_status = _extract_partner_vault_status(p.key, vault_overrides)
            ov_entry = vault_overrides.get(p.key) if isinstance(vault_overrides, dict) else None
            if ov_status in ("live", "active_direct") and not (
                isinstance(ov_entry, dict) and ov_entry.get("is_fallback_partner")
            ):
                explicit_vault_live_keys.add(p.key)
            eff_status = (ov_status or p.status or "").strip().lower()
            if eff_status in ("live", "active_direct"):
                live_candidates.append((p, eff_status))

        if live_candidates:
            if matched_bucket_name == "crypto":
                for p, eff_st in live_candidates:
                    if p.key == "coinledger" and not (explicit_vault_live_keys - {"coinledger"}):
                        return p
            if matched_bucket_name in (
                "section-179",
                "179",
                "macrs",
                "depreciation",
                "equipment",
                "tariff-landed-cost",
                "invoice-factoring",
            ) and not explicit_vault_live_keys:
                non_fallback_live = [
                    (p, eff_st) for p, eff_st in live_candidates if p.key != "mercury"
                ]
                if not non_fallback_live:
                    return candidates[0]
                live_candidates = non_fallback_live
            best = max(live_candidates, key=lambda item: score_partner_yield(item[0], item[1]))
            return best[0]

        return candidates[0]

    return None


def get_profithelm_partner_for_slug(slug: str) -> Optional[AffiliatePartner]:
    """Resolves the optimal ProfitHelm AffiliatePartner for a calculator slug."""
    return resolve_optimal_partner_for_slug("profithelm", slug)


def _select_partner_for_slug(property_id: str, slug: str) -> str:
    """Internal helper to match a tool slug to default partner key."""
    partner = resolve_optimal_partner_for_slug(property_id, slug)
    return partner.key if partner else ""


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
    - Raises ValueError if commercial partner requested on a Prexvo restricted public-service page.
    - Raises ValueError if student loan partner requested for ProfitHelm.
    - Guarantees rel='noopener sponsored nofollow' and target='_blank'.
    """
    prop_clean = (property_id or "").strip().lower()
    if prop_clean not in ("profithelm", "prexvo", "exchange1031"):
        raise ValueError(f"Unknown or unsupported property: '{property_id}'")

    selected_key = (partner_key or "").strip().lower()
    slug_clean = (tool_slug or "").strip().lower()

    if prop_clean == "prexvo" and is_restricted_public_service_slug(slug_clean):
        raise ValueError(
            f"Prexvo YMYL guardrail violation: Commercial refinance offers are prohibited on restricted public-service page '{tool_slug}'."
        )

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
        if prop_clean == "prexvo":
            if slug_clean in COMMERCIAL_B2B_SLUGS or any(
                b2b_token in slug_clean
                for b2b_token in ("saas-runway", "section-179", "section-1031", "qsbs-section-1202")
            ):
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

    disclosure_text = (
        PREXVO_DISCLOSURES.get("ftc_disclosure", "")
        if prop_clean == "prexvo"
        else PROFITHELM_DISCLOSURES.get("ftc_disclosure", "")
    )
    ymyl_warning = (
        PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")
        if prop_clean == "prexvo"
        else ""
    )

    return {
        "property_id": prop_clean,
        "calculator_slug": slug_clean,
        "partner": partner_obj.key,
        "partner_key": partner_obj.key,
        "name": partner_obj.name,
        "partner_name": partner_obj.name,
        "url": resolved_url,
        "cta_text": cta_text,
        "rel": "noopener sponsored nofollow",
        "target": "_blank",
        "badge": partner_obj.badge,
        "status": partner_obj.status,
        "bounty_est": partner_obj.bounty_est,
        "bounty_score": score_partner_yield(partner_obj, partner_obj.status),
        "is_fallback": False,
        "tier": value_tier,
        "disclosure_required": True,
        "disclosure": disclosure_text,
        "ymyl_warning": ymyl_warning,
    }


UNMONETIZABLE_NOISE_TOKENS: Set[str] = {
    "celebrity",
    "gossip",
    "red carpet",
    "red-carpet",
    "concert",
    "movie trailer",
    "horoscope",
    "meme",
    "tiktok dance",
    "weather radar",
    "wordle",
    "crossword",
    "login page",
    "customer service number",
    "forgot password",
    "down detector",
    "box office",
    "super bowl halftime",
    "oscars",
    "grammys",
    "nfl score",
    "nba score",
    "funny video",
    "viral prank",
}

STUDENT_LOAN_INTENT_TOKENS: Tuple[str, ...] = (
    "student loan",
    "student-loan",
    "pslf",
    "ibr",
    "rap",
    "save plan",
    "save-plan",
    "fafsa",
    "nelnet",
    "mohela",
    "aidvantage",
    "edfinancial",
    "title iv",
    "title-iv",
    "forbearance",
    "deferment",
    "parent plus",
    "parent-plus",
    "borrower defense",
    "consolidation loan",
    "consolidation-loan",
    "loan repayment",
    "loan-repayment",
    "idr",
)

COMMERCIAL_B2B_INTENT_TOKENS: Tuple[str, ...] = (
    "section 179",
    "section-179",
    "179d",
    "cost segregation",
    "cost-segregation",
    "1031 exchange",
    "section 1031",
    "section-1031",
    "macrs",
    "bonus depreciation",
    "qsbs",
    "section 1202",
    "section-1202",
    "corporate amt",
    "corporate-amt",
    "camt",
    "saas runway",
    "saas-runway",
    "burn rate",
    "burn-rate",
    "r&d tax",
    "r-and-d",
    "section 174",
    "payroll tax",
    "equipment financing",
    "commercial real estate",
    "working capital",
    "venture debt",
    "treasury management",
    "s-corp payroll",
    "c-corp",
    "corporate card",
)

CONSUMER_FINANCIAL_INTENT_TOKENS: Tuple[str, ...] = (
    "tax bracket",
    "tax-bracket",
    "capital gains",
    "capital-gains",
    "crypto tax",
    "crypto-tax",
    "staking tax",
    "airdrop tax",
    "form 8949",
    "form 8829",
    "home office deduction",
    "1099-da",
    "tcja",
    "standard deduction",
    "child tax credit",
    "earned income",
    "marginal tax",
    "effective tax",
    "kalshi",
    "polymarket",
    "prediction market",
    "prediction-market",
    "implied probability",
    "kelly criterion",
    "no-vig",
    "event contract",
    "treasury bill",
    "t-bill",
    "tbill",
    "high yield savings",
    "apy calculator",
    "roth ira",
    "401k",
    "self employment tax",
    "quarterly estimated tax",
)

PROSPECTIVE_NICHE_TOOL_TOKENS: Tuple[str, ...] = (
    "calculator",
    "estimator",
    "matrix",
    "modeler",
    "simulator",
    "projection",
    "penalty",
    "compliance",
    "audit",
    "roi",
    "yield",
    "margin",
    "markup",
    "premium",
    "insurance",
    "financing",
    "factoring",
    "credit",
    "deduction",
    "subsidy",
    "tariff",
    "duty",
    "settlement",
    "valuation",
    "amortization",
    "lease",
    "buyout",
    "surety",
    "bond",
    "malpractice",
    "solar itc",
    "nem 3.0",
    "demand charge",
    "srec",
    "hipaa",
    "soc2",
    "soc 2",
    "cmmc",
    "sprs",
    "nmfc",
    "hts",
    "demurrage",
    "retainage",
    "lien",
    "wrvu",
    "rvu",
    "rate",
    "cost",
    "fee",
    "payback",
)


def verify_partner_domain_alignment(
    property_id: str,
    slug: str,
    partners: List[str],
) -> Dict[str, Any]:
    """
    Mechanically verifies that partner keys assigned to a property and slug
    never mix incompatible offers across domains or between B2B and retail tax tiers.
    """
    prop = (property_id or "").strip().lower()
    s_clean = (slug or "").strip().lower()
    clean_partners = [str(p).strip().lower() for p in (partners or []) if str(p).strip()]
    violations: List[str] = []

    if prop == "prexvo":
        if is_restricted_public_service_slug(s_clean) and clean_partners:
            violations.append(
                f"Prexvo YMYL public-service guardrail violation: commercial partners {clean_partners} are prohibited on restricted public-service slug '{s_clean}'."
            )
        for pk in clean_partners:
            if pk in B2B_PARTNER_KEYS or pk in PROFITHELM_AFFILIATES or pk == "sovrn_commerce":
                violations.append(
                    f"Prexvo isolation violation: prohibited commercial/aggregator partner '{pk}' on '{s_clean}'."
                )
            elif pk not in PREXVO_AFFILIATES and pk not in STUDENT_LOAN_PARTNER_KEYS:
                violations.append(
                    f"Prexvo registry violation: unapproved partner '{pk}' on '{s_clean}'."
                )
    elif prop in ("profithelm", "exchange1031"):
        is_b2b = is_commercial_b2b_slug(s_clean)
        is_retail = (s_clean in RETAIL_TAX_SLUGS) or (not is_b2b and any(
            t in s_clean for t in ("tax-bracket", "capital-gains", "crypto-tax", "tcja", "prediction-market-tax")
        ))
        for pk in clean_partners:
            if pk in STUDENT_LOAN_PARTNER_KEYS or pk in PREXVO_AFFILIATES:
                violations.append(
                    f"ProfitHelm isolation violation: student loan partner '{pk}' prohibited on '{s_clean}'."
                )
            if is_b2b and pk in RETAIL_TAX_PARTNERS:
                violations.append(
                    f"Intent entanglement violation: retail tax partner '{pk}' mixed into commercial B2B slug '{s_clean}'."
                )
            if is_retail and pk in ENTERPRISE_B2B_PARTNERS:
                violations.append(
                    f"Intent entanglement violation: enterprise B2B partner '{pk}' mixed into consumer/retail slug '{s_clean}'."
                )

    return {
        "aligned": len(violations) == 0,
        "property_id": prop,
        "slug": s_clean,
        "partners": clean_partners,
        "violations": violations,
    }


def qualify_monetization_opportunity(
    query: str,
    slug: str = "",
    property_id: Optional[str] = None,
    search_volume: int = 0,
    cpc_usd: float = 0.0,
    jev_score: float = 1.25,
    durable_prob: float = 0.55,
    vault_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Canonical monetization qualification and niche expansion scoring model.
    Untangles commercial B2B, consumer financial, Title IV student loan YMYL,
    and prospective greenfield niche expansions without shadow evaluators.
    """
    q_clean = (query or "").strip()
    q_lower = q_clean.lower()
    s_clean = (slug or "").strip().lower()
    if not s_clean and q_lower:
        s_clean = re.sub(r"[^a-z0-9]+", "-", q_lower).strip("-")
    combined = f"{q_lower} {s_clean}".strip()
    prop_explicit = (property_id or "").strip().lower()

    vol = max(0, int(search_volume or 0))
    cpc = max(0.0, float(cpc_usd or 0.0))
    jev = max(0.0, float(jev_score or 0.0))
    dur = max(0.0, min(1.0, float(durable_prob or 0.0)))

    # 1. Reject transient/navigational noise immediately
    if not combined or any(noise in combined for noise in UNMONETIZABLE_NOISE_TOKENS):
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit or "unassigned",
            "intent_tier": "unmonetizable_noise",
            "monetization_qualified": False,
            "rejection_reason": "Unmonetizable transient or navigational noise signal",
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": True,
            "disclosures_required": {},
        }

    is_student_loan = any(tok in combined for tok in STUDENT_LOAN_INTENT_TOKENS)
    is_b2b = is_commercial_b2b_slug(s_clean) or any(tok in combined for tok in COMMERCIAL_B2B_INTENT_TOKENS)
    is_consumer_fin = (s_clean in RETAIL_TAX_SLUGS) or any(tok in combined for tok in CONSUMER_FINANCIAL_INTENT_TOKENS)
    has_tool_signal = any(tok in combined for tok in PROSPECTIVE_NICHE_TOOL_TOKENS)

    # 2. Enforce strict cross-tenant isolation when property_id is explicitly bound
    if prop_explicit == "prexvo":
        if is_b2b or any(
            b2b_kw in combined
            for b2b_kw in ("section 179", "section-179", "1031", "saas", "runway", "burn rate", "qsbs", "corporate amt", "mercury", "ramp", "rippling", "gusto")
        ):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "prexvo",
                "intent_tier": "cross_tenant_contamination",
                "monetization_qualified": False,
                "rejection_reason": "Strict isolation violation: Commercial B2B intent is prohibited on Prexvo.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(PREXVO_DISCLOSURES),
            }
        if not (is_student_loan or is_restricted_public_service_slug(s_clean, q_lower)):
            return {
                "query": q_clean,
                "slug": s_clean,
                "property_id": "prexvo",
                "intent_tier": "out_of_scope_prexvo",
                "monetization_qualified": False,
                "rejection_reason": "Prexvo requires Title IV or student loan repayment/refinance intent.",
                "primary_partner": "",
                "recommended_partners": [],
                "expected_bounty_usd": 0.0,
                "effective_partner_yield": 0.0,
                "intent_weight": 0.0,
                "y_asset": 0.0,
                "estimated_monthly_revenue_usd": 0.0,
                "partner_alignment_verified": False,
                "disclosures_required": dict(PREXVO_DISCLOSURES),
            }

    if prop_explicit in ("profithelm", "exchange1031") and is_student_loan:
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit,
            "intent_tier": "cross_tenant_contamination",
            "monetization_qualified": False,
            "rejection_reason": "Strict isolation violation: Student loan intent is prohibited on ProfitHelm.",
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": False,
            "disclosures_required": dict(PROFITHELM_DISCLOSURES),
        }

    is_restricted_ps = False
    commercial_offers_allowed = True
    greenfield_meta: Dict[str, Any] = {}

    # 3. Route to canonical intent tier and property
    if is_student_loan or prop_explicit == "prexvo":
        resolved_prop = "prexvo"
        intent_tier = "student_loan_ymyl"
        is_restricted_ps = is_restricted_public_service_slug(s_clean, q_lower)
        disclosures = dict(PREXVO_DISCLOSURES)
        disclosures["standing_restriction"] = PREXVO_STANDING_RESTRICTION
        if is_restricted_ps:
            commercial_offers_allowed = False
            primary_obj = None
            rec_partners = []
            bounty_usd = 0.0
            eff_yield = 0.0
            intent_weight = 1.05
            y_asset = round(min(1.25, max(0.70, (cpc / 5.0) * 0.45 + 0.65)), 4)
            alignment = verify_partner_domain_alignment("prexvo", s_clean, rec_partners)
            qualified = bool(alignment["aligned"] and (jev >= 1.0 or cpc >= 1.50 or vol >= 50))
            rejection_reason = "" if qualified else "Failed Prexvo public-service demand qualification threshold"
        else:
            primary_obj = resolve_optimal_partner_for_slug("prexvo", s_clean, vault_overrides=vault_overrides)
            rec_partners = [
                k for k in INTENT_ROUTING_TABLE["student-loan"]
                if k in PREXVO_AFFILIATES and k not in B2B_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key in rec_partners:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 325.0)) if primary_obj else 325.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 113.75
            intent_weight = 1.15
            y_asset = round(min(1.45, max(0.75, (bounty_usd / 300.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
            gate_1_passed = bounty_usd >= 45.0
            alignment = verify_partner_domain_alignment("prexvo", s_clean, rec_partners)
            qualified = bool(gate_1_passed and alignment["aligned"] and (jev >= 1.0 or cpc >= 1.50 or vol >= 50))
            rejection_reason = "" if qualified else "Failed Prexvo Gate 1 or demand qualification threshold"

    elif prop_explicit == "unassigned" or (not prop_explicit and not is_b2b and not is_consumer_fin and has_tool_signal):
        resolved_prop = "unassigned"
        intent_tier = "prospective_niche_expansion"
        from pseofactory.market_intel import (
            match_greenfield_vertical,
            score_active_commission_offers,
            score_buyer_intent,
        )
        v_match = match_greenfield_vertical(combined)
        comm_eval = score_active_commission_offers(
            v_match["vertical_id"] if v_match else combined,
            cpc_usd=cpc,
        )
        buyer_eval = score_buyer_intent(q_clean or s_clean, cpc_usd=cpc)

        is_comm_niche = bool(v_match is not None) or any(
            t in combined
            for t in (
                "commercial", "enterprise", "corporate", "b2b", "compliance",
                "hipaa", "soc2", "soc 2", "cmmc", "sprs", "freight", "factoring",
                "solar itc", "nem 3.0", "demand charge", "srec", "surety", "bond",
                "workers comp", "malpractice", "equipment", "lease", "buyout",
                "tariff", "hts", "nmfc", "lien", "retainage", "wrvu", "rvu",
            )
        )
        synth_bounty = round(max(120.0, cpc * 28.0) if (is_comm_niche or cpc >= 4.0) else max(45.0, cpc * 18.0), 2)
        if v_match is not None and comm_eval.primary_offer is not None:
            bounty_usd = round(max(synth_bounty, comm_eval.expected_bounty_usd), 2)
            eff_yield = round(max(bounty_usd * 0.38, comm_eval.effective_partner_yield), 2)
            all_offers = [comm_eval.primary_offer] + list(comm_eval.backup_offers)
            rec_partners = [o.partner_key for o in all_offers]
            intent_weight = round(1.25 + min(0.15, (comm_eval.commission_offer_score / 100.0) * 0.15), 4)
        else:
            bounty_usd = synth_bounty
            eff_yield = round(bounty_usd * 0.35, 2)
            rec_partners = ["direct_cpa_lead_gen"] if (is_comm_niche or cpc >= 4.0) else ["programmatic_affiliate_cpa"]
            intent_weight = 1.20 if (is_comm_niche or cpc >= 4.0) else 0.95

        y_asset = round(min(1.75, max(0.55, (bounty_usd / 200.0) * 0.55 + (cpc / 4.5) * 0.45)), 4)
        disclosures = dict(PROFITHELM_DISCLOSURES)
        alignment = {"aligned": True, "violations": []}
        qualified = bool(
            has_tool_signal
            and (cpc >= 1.50 or bounty_usd >= 75.0)
            and vol >= 100
            and jev >= 1.0
            and dur >= 0.45
        )
        rejection_reason = "" if qualified else "Prospective niche below minimum CPC/volume/durability monetization bar"
        primary_obj = None
        greenfield_meta = {
            "vertical_id": comm_eval.vertical_id,
            "recommended_tenant_id": v_match["tenant_id"] if v_match else "unassigned",
            "recommended_domain": v_match["recommended_domain"] if v_match else "",
            "buyer_intent_score": buyer_eval.buyer_intent_score,
            "commission_offer_score": comm_eval.commission_offer_score,
            "active_offers_count": comm_eval.active_offers_count,
            "instant_active_offers_count": comm_eval.instant_active_offers_count,
            "networks_represented": comm_eval.networks_represented,
            "min_approval_friction_days": comm_eval.min_approval_friction_days,
            "active_commission_offers": (
                ([comm_eval.primary_offer.to_dict()] if comm_eval.primary_offer else [])
                + [o.to_dict() for o in comm_eval.backup_offers]
            ),
        }

    elif is_b2b or is_consumer_fin or prop_explicit in ("profithelm", "exchange1031"):
        resolved_prop = "exchange1031" if (prop_explicit == "exchange1031" or "1031" in s_clean) and prop_explicit == "exchange1031" else "profithelm"
        if is_b2b and not (s_clean in RETAIL_TAX_SLUGS):
            intent_tier = "commercial_b2b"
            primary_obj = resolve_optimal_partner_for_slug(resolved_prop, s_clean, vault_overrides=vault_overrides)
            # Determine matching B2B routing bucket
            bucket = _resolve_profithelm_bucket(f"{s_clean}-{combined.replace(' ', '-')}")
            if bucket in ("tax", "crypto", "capital-gains", "prediction-market-tax", "prediction"):
                bucket = "runway"
            raw_partners = INTENT_ROUTING_TABLE.get(bucket, ["mercury", "ramp", "stripe"])
            rec_partners = [
                k for k in raw_partners
                if k in PROFITHELM_AFFILIATES
                and k not in RETAIL_TAX_PARTNERS
                and k not in STUDENT_LOAN_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key not in RETAIL_TAX_PARTNERS:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 250.0)) if primary_obj else 250.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 87.50
            intent_weight = 1.35
            y_asset = round(min(1.85, max(0.85, (bounty_usd / 250.0) * 0.65 + (cpc / 5.0) * 0.35)), 4)
        else:
            intent_tier = "consumer_financial"
            primary_obj = resolve_optimal_partner_for_slug("profithelm", s_clean, vault_overrides=vault_overrides)
            bucket = "tax"
            if any(t in combined for t in ("crypto", "token", "staking", "airdrop", "8949", "1099-da")):
                bucket = "crypto"
            elif "capital-gains" in combined or "capital gains" in combined:
                bucket = "capital-gains"
            elif "prediction" in combined and "tax" in combined:
                bucket = "prediction-market-tax"
            elif any(t in combined for t in ("prediction", "kalshi", "polymarket", "odds", "arbitrage", "kelly", "vig")):
                bucket = "prediction"
            elif any(t in combined for t in ("treasury", "tbill", "t-bill", "yield", "apy")):
                bucket = "treasury"
            raw_partners = INTENT_ROUTING_TABLE.get(bucket, ["turbotax", "taxslayer", "freetaxusa"])
            rec_partners = [
                k for k in raw_partners
                if k in PROFITHELM_AFFILIATES
                and k not in ENTERPRISE_B2B_PARTNERS
                and k not in STUDENT_LOAN_PARTNER_KEYS
            ]
            if primary_obj and primary_obj.key not in ENTERPRISE_B2B_PARTNERS:
                rec_partners = [primary_obj.key] + [k for k in rec_partners if k != primary_obj.key]
            bounty_usd = float(parse_bounty_estimate(primary_obj.bounty_est).get("midpoint", 65.0)) if primary_obj else 65.0
            eff_yield = score_partner_yield(primary_obj, primary_obj.status) if primary_obj else 22.75
            intent_weight = 1.05
            y_asset = round(min(1.35, max(0.60, (bounty_usd / 100.0) * 0.60 + (cpc / 4.0) * 0.40)), 4)

        disclosures = dict(PROFITHELM_DISCLOSURES)
        alignment = verify_partner_domain_alignment(resolved_prop, s_clean, rec_partners)
        qualified = bool(alignment["aligned"] and len(rec_partners) > 0 and (jev >= 1.0 or cpc >= 1.0 or bounty_usd >= 40.0))
        rejection_reason = "" if qualified else "Failed ProfitHelm partner alignment or monetization threshold"
    else:
        return {
            "query": q_clean,
            "slug": s_clean,
            "property_id": prop_explicit or "unassigned",
            "intent_tier": "unmonetizable_noise",
            "monetization_qualified": False,
            "rejection_reason": "No commercial, consumer financial, student loan, or quantitative tool intent detected",
            "primary_partner": "",
            "recommended_partners": [],
            "expected_bounty_usd": 0.0,
            "effective_partner_yield": 0.0,
            "intent_weight": 0.0,
            "y_asset": 0.0,
            "estimated_monthly_revenue_usd": 0.0,
            "partner_alignment_verified": True,
            "disclosures_required": {},
        }

    est_clicks = max(10.0, float(vol)) * 0.12
    est_conversions = est_clicks * 0.018
    unit_rev = max(eff_yield, cpc * 2.5) if commercial_offers_allowed else 0.0
    est_monthly_rev = round(est_conversions * unit_rev * max(0.5, dur) * intent_weight, 2) if (qualified and commercial_offers_allowed) else 0.0

    primary_partner_key = (
        primary_obj.key
        if primary_obj is not None
        else (rec_partners[0] if rec_partners else "")
    )

    result_payload: Dict[str, Any] = {
        "query": q_clean,
        "slug": s_clean,
        "property_id": resolved_prop,
        "intent_tier": intent_tier,
        "monetization_qualified": qualified,
        "commercial_offers_allowed": commercial_offers_allowed,
        "restricted_public_service": is_restricted_ps,
        "rejection_reason": rejection_reason,
        "primary_partner": primary_partner_key,
        "recommended_partners": rec_partners[:3],
        "expected_bounty_usd": round(bounty_usd, 2),
        "effective_partner_yield": round(eff_yield, 2),
        "intent_weight": round(intent_weight, 4),
        "y_asset": y_asset,
        "estimated_monthly_revenue_usd": est_monthly_rev,
        "partner_alignment_verified": bool(alignment["aligned"]),
        "alignment_violations": alignment.get("violations", []),
        "disclosures_required": disclosures,
    }
    if greenfield_meta:
        result_payload.update(greenfield_meta)
    return result_payload


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
