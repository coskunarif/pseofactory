"""Intent-matching policy for approved affiliate tracking links.

A click on `/r/<partner>` must land on that partner (or an explicit alias of that exact brand).
Approved network tracking links for a different brand or vertical (for example a SuretyBondsDirect
or Simply Business click landing on LawDepot, a Crest Capital or IPX1031 click landing on Xendoo,
a Stripe click landing on Ramp, an Interactive Brokers click landing on Kalshi, a TurboTax click
landing on E-file.com, or a TaxSlayer click landing on ezTaxReturn.com) are bait-and-switch
redirects and are strictly rejected.

Each entry in `ALLOWED_PARTNER_KEYS_BY_TRACKING_URL` maps an approved tracking URL to the ONLY
partner keys that may resolve to it.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit

XENDOO_IMPACT_URL = "https://xendoo.pxf.io/c/7932737/1357375/16354"
XENDOO_SHORT_IMPACT_URL = "https://xendoo.pxf.io/2Rq2rg"
XENDOO_FIRSTPROMOTER_URL = "https://www.xendoo.com?fp_ref=arif-4ac24e"
RAMP_IMPACT_URL = "https://join.ramp.com/c/7932737/3981015/51436"
RAMP_PORTAL_IMPACT_URL = "https://join.ramp.com/c/7932737/3861852/51436"
GUSTO_IMPACT_URL = "https://gusto.pxf.io/c/7932737/1226287/15154"
KALSHI_IMPACT_URL = "https://kalshi.pxf.io/c/7932737/3078072/37770"
LAWDEPOT_CJ_URL = "https://www.jdoqocy.com/click-101906407-16985242"
EFILE_CJ_URL = "https://www.jdoqocy.com/click-101906407-11917161"
EZTAXRETURN_CJ_URL = "https://www.dpbolvw.net/click-101906407-15704796"
FREETAXUSA_CJ_URL = "https://www.jdoqocy.com/click-101906407-12306188"
WALLETHUB_CJ_URL = "https://www.jdoqocy.com/click-101906407-16952385"
MERCURY_PARTNERSTACK_URL = "https://mercury.com/r/profithelm-llc"
RIPPLING_PARTNERSTACK_URL = "https://try.rippling.com/mcfo1m09qiwt"
COINLEDGER_FIRSTPROMOTER_URL = "https://coinledger.io/?fpr=arif-554004"
KOINLY_FIRSTPROMOTER_URL = "https://koinly.io/?fpr=arif-4c0b88"

# Active CJ publisher properties across all 4 tenants. Legacy PID 101725461 returns HTTP 400 and must never be used.
ACTIVE_CJ_PROPERTY_ID = "101906407"
CJ_PROPERTY_ID_BY_TENANT: Dict[str, str] = {
    "profithelm": "101906407",
    "prexvo": "101927178",
    "gainhelm": "101927180",
    "lienbond": "101927181",
}
ACTIVE_CJ_PROPERTY_IDS: Tuple[str, ...] = (
    "101906407",
    "101927178",
    "101927180",
    "101927181",
)
DEAD_CJ_PROPERTY_IDS: Tuple[str, ...] = ("101725461",)

# Per-tenant Impact Promotional Channels (MediaProperties) and homepage verification UUIDs.
IMPACT_CHANNEL_ID_BY_TENANT: Dict[str, str] = {
    "profithelm": "8980393",
    "prexvo": "9151905",
    "gainhelm": "9151929",
    "lienbond": "9151944",
}
IMPACT_VERIFICATION_UUID_BY_TENANT: Dict[str, str] = {
    "profithelm": "d089d8b3-753e-46dc-9c12-653de16f710d",
    "prexvo": "79393cd8-e7dd-49af-a934-f8515d299b19",
    "gainhelm": "252d3e3c-d342-48fc-8359-eb3700e68b1f",
    "lienbond": "5ce463de-dd46-4356-871d-e6d1214b5d57",
}


def _norm(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    fp_pairs = [
        (k.lower(), v.lower())
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() in ("fpr", "fp_ref")
    ]
    base = f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/").lower()
    if fp_pairs:
        return f"{base}?{urlencode(sorted(fp_pairs))}"
    return base


def _norm_base(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/").lower()


# GainHelm GRC / security-audit vendors. None has an approved affiliate contract, so they must
# never resolve to any unrelated approved B2B tracking link.
GRC_PARTNER_KEYS: FrozenSet[str] = frozenset(
    {
        "vanta_security",
        "vanta",
        "vanta_compliance",
        "drata_compliance",
        "drata",
        "sprinto_compliance",
        "sprinto",
        "sprinto_grc",
        "thoropass_audit",
        "thoropass",
        "coalition_cyber_insurance",
        "coalition",
        "cobalt_pentest",
        "cobalt",
        "secureframe_grc",
    }
)

# Strict brand-honest allowlist: each approved tracking URL may ONLY be attached to partner keys
# representing that exact merchant brand.
ALLOWED_PARTNER_KEYS_BY_TRACKING_URL: Dict[str, FrozenSet[str]] = {
    _norm(XENDOO_IMPACT_URL): frozenset({"xendoo", "xendoo_impact"}),
    _norm(XENDOO_SHORT_IMPACT_URL): frozenset({"xendoo", "xendoo_impact"}),
    _norm(XENDOO_FIRSTPROMOTER_URL): frozenset({"xendoo", "xendoo_impact"}),
    _norm(RAMP_IMPACT_URL): frozenset({"ramp", "ramp_impact"}),
    _norm(RAMP_PORTAL_IMPACT_URL): frozenset({"ramp", "ramp_impact"}),
    _norm(GUSTO_IMPACT_URL): frozenset({"gusto", "gusto_payroll"}),
    _norm(KALSHI_IMPACT_URL): frozenset({"kalshi", "kalshi_markets"}),
    _norm(LAWDEPOT_CJ_URL): frozenset({"lawdepot", "lawdepot_legal"}),
    _norm(EFILE_CJ_URL): frozenset({"efile", "efile_com"}),
    _norm(EZTAXRETURN_CJ_URL): frozenset({"eztaxreturn", "eztaxreturn_com"}),
    _norm(FREETAXUSA_CJ_URL): frozenset({"freetaxusa"}),
    _norm(WALLETHUB_CJ_URL): frozenset({"wallethub"}),
    _norm(MERCURY_PARTNERSTACK_URL): frozenset({"mercury", "mercury_treasury"}),
    _norm(RIPPLING_PARTNERSTACK_URL): frozenset({"rippling", "rippling_hr"}),
    _norm(COINLEDGER_FIRSTPROMOTER_URL): frozenset({"coinledger", "coinledger_tax"}),
    _norm(KOINLY_FIRSTPROMOTER_URL): frozenset({"koinly", "koinly_tax"}),
}

# Retained for backward-compatible imports; `is_intent_matched` enforces strict brand allowlisting
# via ALLOWED_PARTNER_KEYS_BY_TRACKING_URL above, which subsumes all blocked swap sets.
BLOCKED_CROSS_VERTICAL_SWAPS: Dict[str, FrozenSet[str]] = {
    _norm(XENDOO_IMPACT_URL): frozenset(
        {
            "crest_capital",
            "equipment_macrs",
            "ipx1031",
            "exeter1031",
            "first_american",
            "first_american_1031",
            "avaliable_1031",
            "madison_specs_cost_seg",
            "dlp_capital",
            "groundfloor",
            "national_funding",
            "national_funding_med",
        }
    ),
    _norm(RAMP_IMPACT_URL): frozenset(
        {
            "stripe",
            "otr_solutions_factoring",
            "freightos_marketplace",
            "flexport",
            "alt_lending",
            "viva_finance",
            "invoice_simple",
        }
    ),
    _norm(LAWDEPOT_CJ_URL): frozenset(
        {
            "suretybonds_direct",
            "simply_business",
            "hiscox",
            "next_insurance_b2b",
            "legalzoom",
            "thimble_contractor",
            "jobber_field_service",
            "levelset_lien_filing",
        }
    ),
    _norm(KALSHI_IMPACT_URL): frozenset(
        {
            "interactive_brokers",
            "zacks",
            "moby",
        }
    ),
    _norm(EFILE_CJ_URL): frozenset(
        {
            "turbotax",
            "taxact",
            "taxslayer",
        }
    ),
    _norm(EZTAXRETURN_CJ_URL): frozenset(
        {
            "taxslayer",
            "turbotax",
            "taxact",
        }
    ),
}

# Uncontracted partners that must never be wrapped onto a different merchant via Sovrn fallback.
BLOCKED_SOVRN_FALLBACK_KEYS: FrozenSet[str] = frozenset(
    {
        "ipx1031",
        "suretybonds_direct",
    }
)

KNOWN_TRACKING_URLS: FrozenSet[str] = frozenset(ALLOWED_PARTNER_KEYS_BY_TRACKING_URL.keys())


def contains_dead_cj_property(text: str) -> bool:
    return any(pid in str(text or "") for pid in DEAD_CJ_PROPERTY_IDS)


def is_intent_matched(partner_key: str, tracking_url: str) -> bool:
    """True when ``partner_key`` may legitimately resolve to ``tracking_url``."""
    key = str(partner_key or "").strip().lower()
    raw_url = str(tracking_url or "").strip()
    if not raw_url:
        return True
    if contains_dead_cj_property(raw_url):
        return False

    norm = _norm(raw_url)
    base = _norm_base(raw_url)
    if not norm:
        return True

    if key in GRC_PARTNER_KEYS:
        if norm in KNOWN_TRACKING_URLS or base in KNOWN_TRACKING_URLS:
            return False
        if any(
            net_tok in raw_url.lower()
            for net_tok in (
                "pxf.io/",
                "join.ramp.com/c/",
                "jdoqocy.com/click-",
                "dpbolvw.net/click-",
                "anrdoezrs.net/click-",
                "tkqlhce.com/click-",
                "kqzyfj.com/click-",
                "mercury.com/r/",
                "try.rippling.com/",
                "fpr=",
                "fp_ref=",
            )
        ):
            return False

    allowed = ALLOWED_PARTNER_KEYS_BY_TRACKING_URL.get(norm)
    if allowed is None:
        allowed = ALLOWED_PARTNER_KEYS_BY_TRACKING_URL.get(base)
    if allowed is not None:
        return key in allowed

    # Catch CJ alternative tracking domains (dpbolvw / jdoqocy / anrdoezrs / tkqlhce / kqzyfj)
    # carrying one of our known advertiser link IDs or /links/<pid>/type/dlg/<dest> deep links.
    cj_hosts = ("jdoqocy.com", "dpbolvw.net", "anrdoezrs.net", "tkqlhce.com", "kqzyfj.com")
    url_host = urlsplit(raw_url).netloc.lower()
    is_cj_host = any(url_host == h or url_host.endswith(f".{h}") for h in cj_hosts)

    cj_link_brand_allowlist: Tuple[Tuple[str, FrozenSet[str]], ...] = (
        ("-16985242", frozenset({"lawdepot", "lawdepot_legal"})),
        ("-13784628", frozenset({"lawdepot", "lawdepot_legal"})),
        ("-11917161", frozenset({"efile", "efile_com"})),
        ("-15704796", frozenset({"eztaxreturn", "eztaxreturn_com"})),
        ("-12306188", frozenset({"freetaxusa"})),
        ("-16952385", frozenset({"wallethub"})),
    )
    for active_pid in ACTIVE_CJ_PROPERTY_IDS:
        for link_suffix, brand_keys in cj_link_brand_allowlist:
            if f"click-{active_pid}{link_suffix}" in base:
                return key in brand_keys

    if is_cj_host:
        if any(f"/links/{active_pid}/" in base for active_pid in ACTIVE_CJ_PROPERTY_IDS):
            cj_dlg_domain_allowlist: Tuple[Tuple[str, FrozenSet[str]], ...] = (
                ("lawdepot.com", frozenset({"lawdepot", "lawdepot_legal"})),
                ("efile.com", frozenset({"efile", "efile_com"})),
                ("eztaxreturn.com", frozenset({"eztaxreturn", "eztaxreturn_com"})),
                ("freetaxusa.com", frozenset({"freetaxusa"})),
                ("wallethub.com", frozenset({"wallethub"})),
            )
            for dest_domain, brand_keys in cj_dlg_domain_allowlist:
                if dest_domain in base:
                    return key in brand_keys
        return False

    return key not in BLOCKED_CROSS_VERTICAL_SWAPS.get(norm, frozenset())


def filter_intent_matched_contracts(upgrades: Mapping[str, str]) -> Dict[str, str]:
    """Drop every cross-vertical or competitor swap from a ``{partner_key: tracking_url}`` map."""
    return {k: v for k, v in upgrades.items() if is_intent_matched(k, v)}


def removed_cross_vertical_swaps(upgrades: Mapping[str, str]) -> Dict[str, str]:
    """The swaps that `filter_intent_matched_contracts` would drop (for audit reports)."""
    return {k: v for k, v in upgrades.items() if not is_intent_matched(k, v)}
