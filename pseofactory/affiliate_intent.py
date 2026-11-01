"""Intent-matching policy for approved affiliate tracking links.

A click on `/r/<partner>` must land on that partner (or an explicit alias of it). Approved
network tracking links for a *different* brand or vertical (for example a Brex click
landing on Mercury, an IPX1031 click landing on Xendoo bookkeeping, or a Vanta click
landing on Ramp) are bait-and-switch redirects, so they are never attached as
`directContractUrl` for keys that are not that brand.

Each entry maps an approved tracking URL (query string ignored) to the only partner keys
that may resolve to it.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, Mapping, Tuple
from urllib.parse import urlsplit

XENDOO_IMPACT_URL = "https://xendoo.pxf.io/c/7932737/1357375/16354"
RAMP_IMPACT_URL = "https://join.ramp.com/c/7932737/3981015/51436"
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

# Active CJ publisher property. The legacy PID 101725461 returns HTTP 400 and must not be used.
ACTIVE_CJ_PROPERTY_ID = "101906407"
DEAD_CJ_PROPERTY_IDS: Tuple[str, ...] = ("101725461",)


def _norm(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    # Tracking identity for FirstPromoter style links lives in the query string.
    if "fpr=" in parts.query:
        return f"{parts.scheme}://{parts.netloc}{parts.path}?{parts.query}".rstrip("/").lower()
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

# Approved tracking URL (query ignored) -> partner keys that must NOT resolve to it because the
# destination is a different vertical than the partner the visitor clicked.
BLOCKED_CROSS_VERTICAL_SWAPS: Dict[str, FrozenSet[str]] = {
    # Xendoo is bookkeeping: never the destination for 1031 qualified intermediaries, real-estate
    # lenders, cost segregation or business-loan brokers.
    _norm(XENDOO_IMPACT_URL): frozenset(
        {
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
    # Ramp is corporate cards / spend: never the destination for factoring, freight or invoicing.
    _norm(RAMP_IMPACT_URL): frozenset(
        {
            "otr_solutions_factoring",
            "freightos_marketplace",
            "flexport",
            "alt_lending",
            "viva_finance",
            "invoice_simple",
        }
    ),
}

# The IPX1031 qualified intermediary must not be wrapped onto DLP Capital (a fund, not a QI).
BLOCKED_SOVRN_FALLBACK_KEYS: FrozenSet[str] = frozenset({"ipx1031"})

KNOWN_TRACKING_URLS: FrozenSet[str] = frozenset(
    {
        _norm(u)
        for u in (
            XENDOO_IMPACT_URL,
            RAMP_IMPACT_URL,
            GUSTO_IMPACT_URL,
            KALSHI_IMPACT_URL,
            LAWDEPOT_CJ_URL,
            EFILE_CJ_URL,
            EZTAXRETURN_CJ_URL,
            FREETAXUSA_CJ_URL,
            WALLETHUB_CJ_URL,
            MERCURY_PARTNERSTACK_URL,
            RIPPLING_PARTNERSTACK_URL,
            COINLEDGER_FIRSTPROMOTER_URL,
            KOINLY_FIRSTPROMOTER_URL,
        )
    }
)


def is_intent_matched(partner_key: str, tracking_url: str) -> bool:
    """True when ``partner_key`` may legitimately resolve to ``tracking_url``."""
    key = str(partner_key or "").strip().lower()
    norm = _norm(tracking_url)
    if not norm:
        return True
    if key in GRC_PARTNER_KEYS and norm in KNOWN_TRACKING_URLS:
        return False
    return key not in BLOCKED_CROSS_VERTICAL_SWAPS.get(norm, frozenset())


def filter_intent_matched_contracts(upgrades: Mapping[str, str]) -> Dict[str, str]:
    """Drop every cross-vertical swap from a ``{partner_key: tracking_url}`` map."""
    return {k: v for k, v in upgrades.items() if is_intent_matched(k, v)}


def removed_cross_vertical_swaps(upgrades: Mapping[str, str]) -> Dict[str, str]:
    """The swaps that `filter_intent_matched_contracts` would drop (for audit reports)."""
    return {k: v for k, v in upgrades.items() if not is_intent_matched(k, v)}


def contains_dead_cj_property(text: str) -> bool:
    return any(pid in str(text or "") for pid in DEAD_CJ_PROPERTY_IDS)
