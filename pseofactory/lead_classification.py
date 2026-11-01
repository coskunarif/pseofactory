"""Single source of truth for separating synthetic / internal probe leads from real users.

The same lists are embedded into the compiled edge `functions/api/lead-capture.js`
(see `edge.generate_edge_lead_capture_function`) so Python ledgers and the live edge
summary classify leads identically.

Revenue rule: only a lead with `stripe_payment_verified is True` (a live `cs_live_...`
Checkout Session verified as `payment_status == "paid"` directly against the Stripe API)
may ever count as settled revenue. Classification below only decides whether a lead is a
real prospect or an internal fixture, it never creates revenue.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple

OWN_TENANT_DOMAINS: Tuple[str, ...] = ("profithelm.com", "prexvo.com", "gainhelm.com")

# Fixture / documentation domains used by self-tests, batch fixtures and probes.
SYNTHETIC_DOMAINS: Tuple[str, ...] = (
    "example.com",
    "example.org",
    "example.net",
    "example.invalid",
    "synthetic.pseofactory.test",
    "freightfleet-logistics.com",
    "medcenter-cohort.org",
    "cre-exchange-holdings.com",
    "precision-manufacturing.io",
)

# Local-part prefixes used by operator self-tests and audits.
SYNTHETIC_LOCAL_PREFIXES: Tuple[str, ...] = (
    "arif.coskun",
    "coskun.arf",
    "audit",
    "support",
    "ciso",
    "cfo",
    "borrower",
    "treasury.audit",
    "grc-",
    "test",
    "probe",
    "noreply",
    "no-reply",
)

_SYNTH_TLD_SUFFIXES: Tuple[str, ...] = (".invalid", ".test", ".example", ".localhost")

REAL_PAYMENT_SESSION_RE = re.compile(r"^cs_live_[A-Za-z0-9_]+$")


def classify_lead_email(email: Any) -> str:
    """Return ``"synthetic"`` for internal/fixture addresses, otherwise ``"real"``."""
    value = str(email or "").strip().lower()
    if "@" not in value:
        return "synthetic"
    local, _, domain = value.rpartition("@")
    if not local or not domain:
        return "synthetic"
    if domain in OWN_TENANT_DOMAINS or domain.endswith(tuple("." + d for d in OWN_TENANT_DOMAINS)):
        return "synthetic"
    if domain in SYNTHETIC_DOMAINS or domain.endswith(_SYNTH_TLD_SUFFIXES):
        return "synthetic"
    if local.startswith(SYNTHETIC_LOCAL_PREFIXES):
        return "synthetic"
    return "real"


def is_verified_stripe_payment(record: Mapping[str, Any]) -> bool:
    """True only when the record carries edge-verified live Stripe payment proof."""
    if not isinstance(record, Mapping):
        return False
    session_id = str(record.get("stripe_checkout_session_id") or "")
    return (
        record.get("stripe_payment_verified") is True
        and record.get("stripe_payment_status") == "paid"
        and bool(REAL_PAYMENT_SESSION_RE.match(session_id))
    )


def verified_revenue_usd(record: Mapping[str, Any]) -> float:
    """Cash actually collected for a lead: 0.0 unless Stripe payment proof is present."""
    if not is_verified_stripe_payment(record):
        return 0.0
    try:
        return round(float(record.get("attributed_revenue_usd") or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def split_leads(rows: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Partition lead rows into ``real`` and ``synthetic`` buckets (synthetic wins)."""
    buckets: Dict[str, List[Dict[str, Any]]] = {"real": [], "synthetic": []}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        origin = str(row.get("lead_origin") or "")
        kind = "synthetic" if (origin == "internal_probe" or classify_lead_email(row.get("email")) == "synthetic") else "real"
        buckets[kind].append(dict(row))
    return buckets


def revenue_summary(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Truthful revenue rollup: verified Stripe cash vs legacy/unverified 'settled' claims."""
    rows = [r for r in rows if isinstance(r, Mapping)]
    parts = split_leads(rows)
    verified = [r for r in rows if is_verified_stripe_payment(r)]
    claimed = [r for r in rows if r.get("settlement_status") == "settled"]
    unverified_claims = [r for r in claimed if not is_verified_stripe_payment(r)]
    return {
        "total_leads": len(rows),
        "real_leads": len(parts["real"]),
        "synthetic_probe_leads": len(parts["synthetic"]),
        "verified_paid_upgrades": len(verified),
        "verified_cash_usd": round(sum(verified_revenue_usd(r) for r in verified), 2),
        "unverified_settled_claims": len(unverified_claims),
        "unverified_settled_claims_usd": round(
            sum(float(r.get("attributed_revenue_usd") or 0.0) for r in unverified_claims), 2
        ),
    }


def edge_classifier_json(property_id: str) -> str:
    """JSON blob embedded into a tenant's edge JS so it classifies like this module.

    Only the tenant's own domain is embedded (tenant isolation: a tenant's compiled edge
    code must never name another tenant). Cross-tenant operator addresses are still caught
    on the edge by the shared local-part prefixes and fully by the Python classifier.
    """
    own = f"{str(property_id or '').strip().lower()}.com"
    return json.dumps(
        {
            "own_domains": [own] if own in OWN_TENANT_DOMAINS else [],
            "synthetic_domains": list(SYNTHETIC_DOMAINS),
            "local_prefixes": list(SYNTHETIC_LOCAL_PREFIXES),
            "synthetic_tld_suffixes": list(_SYNTH_TLD_SUFFIXES),
        },
        separators=(",", ":"),
    )
