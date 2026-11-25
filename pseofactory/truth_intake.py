"""
pseofactory AI Reasoning + Deterministic Proof Intake & Semantic Audit Engine.

Guards the intake boundary when enacted laws expire or a new site launches,
and provides an optional structured semantic claim critic.
Never trusts an LLM alone and always freezes the site on doubt (fail-closed).
Works dynamically for any property_id (50+ sites, zero hardcoded tenant lists).

Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, field, is_dataclass
from datetime import date, datetime, timezone
import hashlib
import ipaddress
import json
import math
import re
import socket
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from pseofactory.content_angles import call_stateless_vertex_json


VALID_CLAIM_CLASSES = frozenset({"enacted_law", "market_benchmark"})

PRIMARY_ENACTED_LAW_SUFFIXES = (".gov",)

PRIMARY_ENACTED_LAW_DOMAINS = frozenset(
    {
        "congress.gov",
        "irs.gov",
        "federalregister.gov",
        "acquisition.gov",
        "ed.gov",
        "studentaid.gov",
        "acq.osd.mil",
        "hhs.gov",
        "aspe.hhs.gov",
        "bls.gov",
        "census.gov",
        "treasury.gov",
        "dol.gov",
        "sba.gov",
        "sec.gov",
    }
)

BENCHMARK_AUTHORITY_DOMAINS = frozenset(
    {
        "ncci.com",
        "sfaa.org",
        "aicpa-cima.com",
        "pcisecuritystandards.org",
        "iso.org",
    }
)

MIN_VERBATIM_QUOTE_CHARS = 12
MIN_EXCERPT_CHARS = 5
NUMERIC_TOLERANCE = 1e-9
DEFAULT_FETCH_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_FETCH_BYTES = 5 * 1024 * 1024
MAX_PROMPT_DOC_CHARS = 120000

_HOSTNAME_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_SSRF_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata",
        "instance-data",
        "metadata.google.internal",
    }
)


@dataclass(frozen=True)
class FreshnessReport:
    """
    Deterministic freshness and expiry audit result for a TruthPack.
    Zero em-dashes. Zero en-dashes.
    """

    status: str
    expired_keys: List[str] = field(default_factory=list)
    expiring_soon_keys: List[str] = field(default_factory=list)
    as_of: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    checked_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "expired_keys": list(self.expired_keys),
            "expiring_soon_keys": list(self.expiring_soon_keys),
            "as_of": self.as_of.isoformat(),
            "checked_count": self.checked_count,
        }


@dataclass(frozen=True)
class IntakeDecision:
    """
    Fail-closed intake verification decision for official-source claims.
    Zero em-dashes. Zero en-dashes.
    """

    status: str
    property_id: str
    approved_entries: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    raw_doc_sha256: str = ""
    verified_at: date = field(default_factory=lambda: datetime.now(timezone.utc).date())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "property_id": self.property_id,
            "approved_entries": [dict(item) for item in self.approved_entries],
            "reasons": list(self.reasons),
            "raw_doc_sha256": self.raw_doc_sha256,
            "verified_at": self.verified_at.isoformat(),
        }


@dataclass(frozen=True)
class SemanticViolation:
    """
    Verified semantic contradiction backed by a verbatim offending_excerpt in page_text.
    Zero em-dashes. Zero en-dashes.
    """

    rule_id: str
    truth_key: str
    offending_excerpt: str
    explanation: str
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "truth_key": self.truth_key,
            "offending_excerpt": self.offending_excerpt,
            "explanation": self.explanation,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class SemanticCriticReport:
    """
    Result of the optional AI semantic claim critic with deterministic excerpt gating.
    Zero em-dashes. Zero en-dashes.
    """

    status: str
    property_id: str
    page_slug: str
    verified_violations: List[SemanticViolation] = field(default_factory=list)
    rejected_hallucinated_violations: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "property_id": self.property_id,
            "page_slug": self.page_slug,
            "verified_violations": [v.to_dict() for v in self.verified_violations],
            "rejected_hallucinated_violations": [dict(v) for v in self.rejected_hallucinated_violations],
            "reasons": list(self.reasons),
        }


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_iso_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return date.fromisoformat(raw)
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _is_blocked_ip_literal(hostname: str) -> bool:
    """Returns True if hostname is any IP literal or numeric IP encoding."""
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass

    ip_int: Optional[int] = None
    if hostname.isdigit():
        ip_int = int(hostname)
    elif hostname.startswith(("0x", "0X")):
        try:
            ip_int = int(hostname, 16)
        except ValueError:
            ip_int = None
    elif hostname.startswith("0") and len(hostname) > 1 and hostname[1:].isdigit():
        try:
            ip_int = int(hostname, 8)
        except ValueError:
            ip_int = None
    else:
        parts = hostname.split(".")
        if len(parts) == 4:
            try:
                octets = [int(p, 0) for p in parts]
                if all(0 <= o <= 255 for o in octets):
                    ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
            except (ValueError, TypeError):
                ip_int = None

    if ip_int is not None and 0 <= ip_int <= 0xFFFFFFFF:
        return True
    return False


def _is_public_ip(ip_obj: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    ):
        return False
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        return _is_public_ip(ip_obj.ipv4_mapped)
    return True


def _domain_matches(hostname: str, allowed_domain: str) -> bool:
    return hostname == allowed_domain or hostname.endswith(f".{allowed_domain}")


def is_official_primary_url(url: str, claim_class: str = "enacted_law") -> bool:
    """
    Validates that a source URL is a strict HTTPS official primary source
    for the requested claim_class, with SSRF protection.

    - enacted_law: allows valid .gov domains and curated primary authorities
      (including acq.osd.mil). Never allows market benchmark authorities.
    - market_benchmark: allows enacted_law sources plus curated benchmark authorities
      (ncci.com, sfaa.org, aicpa-cima.com, pcisecuritystandards.org, iso.org).
    """
    if not isinstance(url, str) or not url.strip():
        return False
    if any(ch.isspace() or ord(ch) < 32 for ch in url.strip()):
        return False

    normalized_class = (claim_class or "").strip().lower()
    if normalized_class not in VALID_CLAIM_CLASSES:
        return False

    try:
        parsed = urllib.parse.urlparse(url.strip())
        _ = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() != "https":
        return False
    if not parsed.netloc or parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        return False

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return False

    if hostname in _SSRF_BLOCKED_HOSTNAMES:
        return False
    if (
        hostname.endswith(".local")
        or hostname.endswith(".localhost")
        or hostname.endswith(".internal")
        or hostname.endswith(".metadata.google.internal")
        or hostname.startswith("127.")
        or hostname.startswith("169.254.")
    ):
        return False

    if _is_blocked_ip_literal(hostname):
        return False

    labels = hostname.split(".")
    if len(labels) < 2 or not all(_HOSTNAME_LABEL_RE.match(label) for label in labels):
        return False

    is_gov_suffix = any(hostname.endswith(suffix) and len(hostname) > len(suffix) for suffix in PRIMARY_ENACTED_LAW_SUFFIXES)
    is_primary_domain = any(_domain_matches(hostname, dom) for dom in PRIMARY_ENACTED_LAW_DOMAINS)
    if is_gov_suffix or is_primary_domain:
        return True

    if normalized_class == "market_benchmark":
        return any(_domain_matches(hostname, dom) for dom in BENCHMARK_AUTHORITY_DOMAINS)

    return False


def _extract_truth_pack_entries(truth_pack: Any) -> Tuple[List[Tuple[str, Dict[str, Any]]], Optional[Any]]:
    """
    Normalizes a TruthPack dataclass/object or dict into ([(key, entry_dict), ...], pack_expires_at).
    """
    pack_obj = truth_pack
    if hasattr(truth_pack, "to_dict") and callable(truth_pack.to_dict):
        pack_obj = truth_pack.to_dict()
    elif is_dataclass(truth_pack):
        pack_obj = {f: getattr(truth_pack, f) for f in truth_pack.__dataclass_fields__}
    elif hasattr(truth_pack, "__dict__") and not isinstance(truth_pack, dict):
        pack_obj = vars(truth_pack)

    if not isinstance(pack_obj, dict):
        return [], None

    pack_expires_at = pack_obj.get("expires_at")
    raw_entries = None
    for container_key in ("entries", "facts", "claims", "items"):
        if container_key in pack_obj:
            raw_entries = pack_obj[container_key]
            break

    normalized: List[Tuple[str, Dict[str, Any]]] = []
    if raw_entries is None:
        # Support bare dict mapping key -> entry dict when wrapper key is omitted
        for k, v in pack_obj.items():
            if isinstance(v, dict) and ("expires_at" in v or "value" in v):
                normalized.append((str(k), v))
        return normalized, pack_expires_at

    if isinstance(raw_entries, dict):
        for k, v in raw_entries.items():
            if hasattr(v, "to_dict") and callable(v.to_dict):
                v_dict = v.to_dict()
            elif is_dataclass(v):
                v_dict = {f: getattr(v, f) for f in v.__dataclass_fields__}
            elif hasattr(v, "__dict__") and not isinstance(v, dict):
                v_dict = vars(v)
            elif isinstance(v, dict):
                v_dict = v
            else:
                v_dict = {"value": v}
            normalized.append((str(k), v_dict))
    elif isinstance(raw_entries, (list, tuple)):
        for idx, item in enumerate(raw_entries):
            if hasattr(item, "to_dict") and callable(item.to_dict):
                item_dict = item.to_dict()
            elif is_dataclass(item):
                item_dict = {f: getattr(item, f) for f in item.__dataclass_fields__}
            elif hasattr(item, "__dict__") and not isinstance(item, dict):
                item_dict = vars(item)
            elif isinstance(item, dict):
                item_dict = item
            else:
                item_dict = {"value": item}
            key = str(item_dict.get("key") or item_dict.get("fact_key") or item_dict.get("id") or f"entry_{idx}")
            normalized.append((key, item_dict))

    return normalized, pack_expires_at


def check_truth_pack_freshness(
    truth_pack: Any,
    as_of: Optional[Union[date, datetime, str]] = None,
    warning_days: int = 30,
) -> FreshnessReport:
    """
    Pure deterministic date-math freshness check on a TruthPack or schema dict.
    Never issues fake freshness stamps: empty or missing-expiry packs fail closed.
    """
    ref_date = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
    if ref_date is None:
        raise ValueError(f"Invalid as_of date: {as_of!r}")
    if isinstance(warning_days, bool) or not isinstance(warning_days, int) or warning_days < 0:
        raise ValueError(f"warning_days must be a non-negative int, got {warning_days!r}")

    entries, pack_expires_at = _extract_truth_pack_entries(truth_pack)
    expired_keys: List[str] = []
    expiring_soon_keys: List[str] = []

    if entries:
        for key, entry in entries:
            exp_raw = entry.get("expires_at") if entry.get("expires_at") is not None else pack_expires_at
            exp_date = _parse_iso_date(exp_raw)
            if exp_date is None:
                expired_keys.append(key)
                continue
            days_left = (exp_date - ref_date).days
            if days_left <= 0:
                expired_keys.append(key)
            elif days_left <= warning_days:
                expiring_soon_keys.append(key)
        checked_count = len(entries)
    elif pack_expires_at is not None:
        checked_count = 1
        exp_date = _parse_iso_date(pack_expires_at)
        if exp_date is None or (exp_date - ref_date).days <= 0:
            expired_keys.append("__pack__")
        elif (exp_date - ref_date).days <= warning_days:
            expiring_soon_keys.append("__pack__")
    else:
        return FreshnessReport(
            status="FREEZE_EXPIRED",
            expired_keys=["__empty_truth_pack__"],
            expiring_soon_keys=[],
            as_of=ref_date,
            checked_count=0,
        )

    if expired_keys:
        status = "FREEZE_EXPIRED"
    elif expiring_soon_keys:
        status = "EXPIRING_SOON"
    else:
        status = "FRESH"

    return FreshnessReport(
        status=status,
        expired_keys=expired_keys,
        expiring_soon_keys=expiring_soon_keys,
        as_of=ref_date,
        checked_count=checked_count,
    )


def _normalize_candidate_entries(raw_fields: Any, label: str) -> Tuple[Optional[Dict[str, Dict[str, Any]]], List[str]]:
    """
    Normalizes extracted pass fields (list of dicts, {'entries': ...}, or {key: dict})
    into {key: entry_dict}. Fails closed on invalid structure or duplicate keys.
    """
    reasons: List[str] = []
    container = raw_fields
    if isinstance(container, dict) and "entries" in container and not ("value" in container and "key" in container):
        container = container["entries"]

    result: Dict[str, Dict[str, Any]] = {}
    if isinstance(container, list):
        if not container:
            reasons.append(f"{label} produced zero candidate entries.")
            return None, reasons
        for idx, item in enumerate(container):
            if not isinstance(item, dict):
                reasons.append(f"{label} entry[{idx}] is not a dict.")
                return None, reasons
            key = item.get("key")
            if not isinstance(key, str) or not key.strip():
                reasons.append(f"{label} entry[{idx}] missing non-empty 'key'.")
                return None, reasons
            clean_key = key.strip()
            if clean_key in result:
                reasons.append(f"{label} contains duplicate key '{clean_key}'.")
                return None, reasons
            copy_item = dict(item)
            copy_item["key"] = clean_key
            result[clean_key] = copy_item
        return result, reasons

    if isinstance(container, dict):
        if not container:
            reasons.append(f"{label} produced zero candidate entries.")
            return None, reasons
        for k, v in container.items():
            if not isinstance(k, str) or not k.strip():
                reasons.append(f"{label} contains empty key.")
                return None, reasons
            if not isinstance(v, dict):
                reasons.append(f"{label} entry '{k}' is not a dict.")
                return None, reasons
            clean_key = k.strip()
            copy_item = dict(v)
            copy_item.setdefault("key", clean_key)
            if str(copy_item["key"]).strip() != clean_key:
                reasons.append(f"{label} entry key mismatch: '{k}' vs '{copy_item['key']}'.")
                return None, reasons
            copy_item["key"] = clean_key
            result[clean_key] = copy_item
        return result, reasons

    reasons.append(f"{label} must be a list or dict of entries, got {type(raw_fields).__name__}.")
    return None, reasons


def _values_match(v1: Any, v2: Any, path: str = "value") -> Tuple[bool, str]:
    """
    Deep deterministic comparison supporting exact matches and float tolerance (1e-9).
    """
    if isinstance(v1, bool) or isinstance(v2, bool):
        if isinstance(v1, bool) and isinstance(v2, bool) and v1 is v2:
            return True, ""
        return False, f"{path}: pass_1={v1!r} vs pass_2={v2!r}"

    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        if not (_is_finite_number(v1) and _is_finite_number(v2)):
            return False, f"{path}: non-finite number pass_1={v1!r} vs pass_2={v2!r}"
        if abs(float(v1) - float(v2)) <= NUMERIC_TOLERANCE:
            return True, ""
        return False, f"{path}: pass_1={v1!r} vs pass_2={v2!r}"

    if isinstance(v1, list) and isinstance(v2, list):
        if len(v1) != len(v2):
            return False, f"{path}: list length pass_1={len(v1)} vs pass_2={len(v2)}"
        for idx, (item1, item2) in enumerate(zip(v1, v2)):
            ok, diff = _values_match(item1, item2, f"{path}[{idx}]")
            if not ok:
                return False, diff
        return True, ""

    if isinstance(v1, dict) and isinstance(v2, dict):
        if set(v1.keys()) != set(v2.keys()):
            missing = sorted(set(v1.keys()) - set(v2.keys()))
            extra = sorted(set(v2.keys()) - set(v1.keys()))
            return False, f"{path}: dict keys differ missing_in_pass_2={missing} extra_in_pass_2={extra}"
        for k in sorted(v1.keys()):
            ok, diff = _values_match(v1[k], v2[k], f"{path}.{k}")
            if not ok:
                return False, diff
        return True, ""

    if type(v1) is type(v2) and v1 == v2:
        return True, ""
    return False, f"{path}: pass_1={v1!r} vs pass_2={v2!r}"


def _validate_brackets_value(key: str, value: Any) -> List[str]:
    reasons: List[str] = []
    if not isinstance(value, list) or not value:
        return [f"Entry '{key}' with unit='brackets' must have a non-empty list of brackets."]

    prev_max: Optional[float] = None
    prev_rate: Optional[float] = None
    for idx, bracket in enumerate(value):
        if not isinstance(bracket, dict):
            reasons.append(f"Entry '{key}' bracket[{idx}] must be a dict.")
            continue
        if "min" not in bracket or "max" not in bracket or "rate" not in bracket:
            reasons.append(f"Entry '{key}' bracket[{idx}] missing required keys ('min', 'max', 'rate').")
            continue

        b_min = bracket["min"]
        b_max = bracket["max"]
        b_rate = bracket["rate"]

        if not _is_finite_number(b_min) or float(b_min) < 0.0:
            reasons.append(f"Entry '{key}' bracket[{idx}] invalid min={b_min!r}.")
            continue
        min_f = float(b_min)

        if not _is_finite_number(b_rate):
            reasons.append(f"Entry '{key}' bracket[{idx}] invalid rate={b_rate!r}.")
            continue
        rate_f = float(b_rate)
        if rate_f < 0.0 or rate_f > 100.0:
            reasons.append(f"Entry '{key}' bracket[{idx}] rate={rate_f} out of [0, 100].")

        if prev_rate is not None and rate_f <= prev_rate:
            reasons.append(
                f"Entry '{key}' bracket[{idx}] rate={rate_f} is not strictly ascending after {prev_rate}."
            )
        prev_rate = rate_f

        if prev_max is not None and abs(min_f - prev_max) > NUMERIC_TOLERANCE:
            reasons.append(
                f"Entry '{key}' bracket[{idx}] min={min_f} is not contiguous with previous max={prev_max}."
            )

        if b_max is None:
            if idx != len(value) - 1:
                reasons.append(f"Entry '{key}' bracket[{idx}] has max=None before the final bracket.")
            prev_max = None
        else:
            if not _is_finite_number(b_max):
                reasons.append(f"Entry '{key}' bracket[{idx}] invalid max={b_max!r}.")
                continue
            max_f = float(b_max)
            if max_f <= min_f:
                reasons.append(f"Entry '{key}' bracket[{idx}] max={max_f} must be > min={min_f}.")
            if prev_max is not None and max_f <= prev_max:
                reasons.append(
                    f"Entry '{key}' bracket[{idx}] max={max_f} is not strictly ascending after {prev_max}."
                )
            prev_max = max_f

    return reasons


def _validate_entry_invariants(key: str, entry: Dict[str, Any], ref_date: date) -> List[str]:
    reasons: List[str] = []
    if "value" not in entry:
        reasons.append(f"Entry '{key}' missing required 'value'.")
    value = entry.get("value")

    unit = entry.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        reasons.append(f"Entry '{key}' missing required 'unit'.")
        unit_clean = ""
    else:
        unit_clean = unit.strip().lower()

    if unit_clean == "brackets":
        reasons.extend(_validate_brackets_value(key, value))
    elif unit_clean == "pct":
        if not _is_finite_number(value):
            reasons.append(f"Entry '{key}' with unit='pct' must be a finite number, got {value!r}.")
        else:
            val_f = float(value)
            if val_f < 0.0 or val_f > 100.0:
                reasons.append(f"Entry '{key}' with unit='pct' value={val_f} out of [0, 100].")
    elif unit_clean == "usd":
        if not _is_finite_number(value):
            reasons.append(f"Entry '{key}' with unit='usd' must be a finite number, got {value!r}.")
        else:
            val_f = float(value)
            allow_negative = bool(entry.get("allow_negative") or entry.get("signed"))
            if not allow_negative and val_f < 0.0:
                reasons.append(f"Entry '{key}' with unit='usd' cannot be negative ({val_f}).")

    eff_year = entry.get("effective_year")
    if isinstance(eff_year, bool) or not isinstance(eff_year, int) or not (2000 <= eff_year <= 2100):
        reasons.append(f"Entry '{key}' effective_year={eff_year!r} must be an integer in 2000..2100.")

    exp_raw = entry.get("expires_at")
    exp_date = _parse_iso_date(exp_raw)
    if exp_date is None:
        reasons.append(f"Entry '{key}' expires_at={exp_raw!r} is not a valid ISO date.")
    elif exp_date <= ref_date:
        reasons.append(
            f"Entry '{key}' expires_at={exp_date.isoformat()} must be strictly after verified_at={ref_date.isoformat()}."
        )

    return reasons


def verify_extracted_candidate(
    source_url: str,
    raw_document_text: str,
    extracted_fields_pass_1: Any,
    extracted_fields_pass_2: Any,
    claim_class: str = "enacted_law",
    property_id: str = "",
    verified_at: Optional[Union[date, datetime, str]] = None,
) -> IntakeDecision:
    """
    Deterministic proof gate verifying:
    1. Official primary domain allowlist + HTTPS + SSRF guard.
    2. Verbatim-quote existence (>= 12 chars after whitespace normalization) + sha256.
    3. 100% dual-pass agreement between independent extractions (numeric within 1e-9).
    4. Structural mathematical and temporal invariants.
    Always fails closed with FREEZE_SITE on any violation or ambiguity.
    """
    ref_date = _parse_iso_date(verified_at) if verified_at is not None else datetime.now(timezone.utc).date()
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).date()

    doc_text = raw_document_text if isinstance(raw_document_text, str) else ""
    raw_doc_sha256 = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()
    reasons: List[str] = []

    if not is_official_primary_url(source_url, claim_class=claim_class):
        reasons.append(f"Rejected non-official or unsafe source_url for claim_class={claim_class!r}: {source_url!r}")

    norm_doc = _normalize_whitespace(doc_text)
    if not norm_doc:
        reasons.append("raw_document_text is empty.")

    map1, errs1 = _normalize_candidate_entries(extracted_fields_pass_1, "pass_1")
    map2, errs2 = _normalize_candidate_entries(extracted_fields_pass_2, "pass_2")
    reasons.extend(errs1)
    reasons.extend(errs2)

    if map1 is None or map2 is None:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=property_id,
            approved_entries=[],
            reasons=reasons,
            raw_doc_sha256=raw_doc_sha256,
            verified_at=ref_date,
        )

    keys1 = set(map1.keys())
    keys2 = set(map2.keys())
    if keys1 != keys2:
        missing_in_2 = sorted(keys1 - keys2)
        extra_in_2 = sorted(keys2 - keys1)
        reasons.append(
            f"Dual-pass key mismatch: missing_in_pass_2={missing_in_2}, extra_in_pass_2={extra_in_2}."
        )

    approved_candidates: List[Dict[str, Any]] = []
    for key in sorted(keys1 & keys2):
        e1 = map1[key]
        e2 = map2[key]

        # Dual-pass agreement on value and core structural metadata
        ok_val, diff_val = _values_match(e1.get("value"), e2.get("value"), path="value")
        if not ok_val:
            reasons.append(f"Dual-pass disagreement for key '{key}' {diff_val}")

        for meta_field in ("unit", "effective_year", "expires_at"):
            if meta_field in e1 or meta_field in e2:
                ok_meta, diff_meta = _values_match(e1.get(meta_field), e2.get(meta_field), path=meta_field)
                if not ok_meta:
                    reasons.append(f"Dual-pass disagreement for key '{key}' {diff_meta}")

        # Verbatim quote proof on pass 1 (mandatory) and pass 2 (when supplied)
        quote1_raw = e1.get("verbatim_quote")
        if not isinstance(quote1_raw, str):
            reasons.append(f"Entry '{key}' missing string 'verbatim_quote'.")
            norm_quote1 = ""
        else:
            norm_quote1 = _normalize_whitespace(quote1_raw)
            if len(norm_quote1) < MIN_VERBATIM_QUOTE_CHARS:
                reasons.append(
                    f"Entry '{key}' verbatim_quote too short ({len(norm_quote1)} < {MIN_VERBATIM_QUOTE_CHARS} chars)."
                )
            elif norm_doc and norm_quote1 not in norm_doc:
                reasons.append(
                    f"Entry '{key}' verbatim_quote not found verbatim in raw_document_text: {norm_quote1!r}."
                )

        if "verbatim_quote" in e2:
            quote2_raw = e2.get("verbatim_quote")
            if not isinstance(quote2_raw, str):
                reasons.append(f"Entry '{key}' pass_2 invalid 'verbatim_quote'.")
            else:
                norm_quote2 = _normalize_whitespace(quote2_raw)
                if len(norm_quote2) < MIN_VERBATIM_QUOTE_CHARS:
                    reasons.append(
                        f"Entry '{key}' pass_2 verbatim_quote too short ({len(norm_quote2)} < {MIN_VERBATIM_QUOTE_CHARS} chars)."
                    )
                elif norm_doc and norm_quote2 not in norm_doc:
                    reasons.append(
                        f"Entry '{key}' pass_2 verbatim_quote not found verbatim in raw_document_text: {norm_quote2!r}."
                    )

        # Structural math and temporal invariants
        reasons.extend(_validate_entry_invariants(key, e1, ref_date))

        source_quote_sha256 = hashlib.sha256(norm_quote1.encode("utf-8")).hexdigest() if norm_quote1 else ""
        enriched = dict(e1)
        enriched["source_quote_sha256"] = source_quote_sha256
        enriched["raw_doc_sha256"] = raw_doc_sha256
        enriched["source_url"] = source_url
        enriched["claim_class"] = (claim_class or "").strip().lower()
        enriched["verified_at"] = ref_date.isoformat()
        approved_candidates.append(enriched)

    if reasons:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=property_id,
            approved_entries=[],
            reasons=reasons,
            raw_doc_sha256=raw_doc_sha256,
            verified_at=ref_date,
        )

    return IntakeDecision(
        status="APPROVED",
        property_id=property_id,
        approved_entries=approved_candidates,
        reasons=[],
        raw_doc_sha256=raw_doc_sha256,
        verified_at=ref_date,
    )


def _assert_dns_resolves_public(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    port = parsed.port or 443
    infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    if not infos:
        raise ValueError(f"DNS returned no addresses for {hostname}")
    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0].split("%")[0]
        ip_obj = ipaddress.ip_address(ip_str)
        if not _is_public_ip(ip_obj):
            raise ValueError(f"SSRF blocked non-public resolved IP {ip_str} for {hostname}")


def safe_https_fetch(
    url: str,
    claim_class: str = "enacted_law",
    timeout_seconds: float = DEFAULT_FETCH_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_FETCH_BYTES,
) -> str:
    """
    Fetches an official HTTPS URL with strict domain allowlist, DNS SSRF check,
    redirect allowlist validation, timeout, and bounded response size.
    """
    if not is_official_primary_url(url, claim_class=claim_class):
        raise ValueError(f"Blocked untrusted URL before fetch: {url!r}")
    _assert_dns_resolves_public(url)

    class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            abs_url = urllib.parse.urljoin(req.full_url, newurl)
            if not is_official_primary_url(abs_url, claim_class=claim_class):
                raise urllib.error.HTTPError(
                    abs_url, code, f"Blocked redirect to untrusted URL: {abs_url}", headers, fp
                )
            _assert_dns_resolves_public(abs_url)
            return super().redirect_request(req, fp, code, msg, headers, abs_url)

    opener = urllib.request.build_opener(_SafeRedirectHandler())
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pseofactory-truth-intake/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json",
        },
        method="GET",
    )
    with opener.open(req, timeout=timeout_seconds) as resp:
        final_url = resp.geturl()
        if not is_official_primary_url(final_url, claim_class=claim_class):
            raise ValueError(f"Final URL after fetch failed official domain allowlist: {final_url!r}")
        raw_bytes = resp.read(max_bytes + 1)
        if len(raw_bytes) > max_bytes:
            raise ValueError(f"Response exceeded max_bytes={max_bytes}")
        return raw_bytes.decode("utf-8", errors="replace")


def _build_intake_pass_1_prompt(
    property_id: str,
    source_url: str,
    claim_class: str,
    target_keys: Sequence[str],
    doc_text: str,
) -> str:
    keys_json = json.dumps(list(target_keys))
    return (
        "PASS 1 - DIRECT STRUCTURED EXTRACTION.\n"
        "You are extracting statutory or benchmark facts strictly from the provided primary document.\n"
        "Output ONLY valid JSON with top-level key 'entries' (a list of objects).\n"
        "Every requested target key MUST appear once with fields: "
        "'key', 'value', 'unit' ('usd'|'pct'|'brackets'|'months'|'days'|'count'), "
        "'effective_year' (int 2000..2100), 'expires_at' (ISO YYYY-MM-DD strictly after today), "
        "and 'verbatim_quote' (exact substring >= 12 chars copied verbatim from the document).\n"
        "If any target key is absent or ambiguous in the document, do not guess.\n"
        f"property_id={property_id!r}\n"
        f"source_url={source_url!r}\n"
        f"claim_class={claim_class!r}\n"
        f"target_keys={keys_json}\n"
        "DOCUMENT_START\n"
        f"{doc_text[:MAX_PROMPT_DOC_CHARS]}\n"
        "DOCUMENT_END\n"
    )


def _build_intake_pass_2_prompt(
    property_id: str,
    source_url: str,
    claim_class: str,
    target_keys: Sequence[str],
    doc_text: str,
) -> str:
    keys_json = json.dumps(list(target_keys))
    return (
        "PASS 2 - INDEPENDENT ADVERSARIAL RE-EXTRACTION & AUDIT.\n"
        "Independently verify and re-extract every requested key from the primary source text.\n"
        "Reject assumptions, rounded figures, or unstated defaults. Check bracket boundaries, units, "
        "effective_year, and expires_at carefully.\n"
        "Output ONLY valid JSON: {\"entries\": [{\"key\": ..., \"value\": ..., \"unit\": ..., "
        "\"effective_year\": ..., \"expires_at\": ..., \"verbatim_quote\": ...}]}.\n"
        "Every 'verbatim_quote' must be at least 12 characters copied word-for-word from the document.\n"
        f"property_id={property_id!r}\n"
        f"source_url={source_url!r}\n"
        f"claim_class={claim_class!r}\n"
        f"target_keys={keys_json}\n"
        "SOURCE_TEXT_START\n"
        f"{doc_text[:MAX_PROMPT_DOC_CHARS]}\n"
        "SOURCE_TEXT_END\n"
    )


def run_official_source_intake(
    property_id: str,
    source_url: str,
    claim_class: str,
    target_keys: Sequence[str],
    *,
    fetcher: Optional[Callable[[str], str]] = None,
    llm_caller: Optional[Callable[[str], Any]] = None,
    as_of: Optional[Union[date, datetime, str]] = None,
) -> IntakeDecision:
    """
    AI-assisted official-source intake runner with dual independent LLM passes
    followed by deterministic verbatim-quote, dual-pass agreement, and math verification.
    Fails closed (FREEZE_SITE) on any fetch error, LLM error, timeout, missing key,
    fabricated quote, invariant violation, or dual-pass disagreement.
    """
    ref_date = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).date()

    clean_prop = (property_id or "").strip()
    if not clean_prop:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=property_id,
            approved_entries=[],
            reasons=["property_id must be non-empty."],
            raw_doc_sha256="",
            verified_at=ref_date,
        )

    clean_keys = [str(k).strip() for k in (target_keys or []) if str(k).strip()]
    if not clean_keys:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=["target_keys must be non-empty."],
            raw_doc_sha256="",
            verified_at=ref_date,
        )

    if not is_official_primary_url(source_url, claim_class=claim_class):
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=[f"Blocked untrusted source_url for claim_class={claim_class!r}: {source_url!r}"],
            raw_doc_sha256="",
            verified_at=ref_date,
        )

    active_fetcher = fetcher if fetcher is not None else (lambda u: safe_https_fetch(u, claim_class=claim_class))
    try:
        raw_doc = active_fetcher(source_url)
    except Exception as exc:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=[f"Official source fetch failed: {type(exc).__name__}: {exc}"],
            raw_doc_sha256="",
            verified_at=ref_date,
        )

    if not isinstance(raw_doc, str) or not _normalize_whitespace(raw_doc):
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=["Official source fetch returned empty or non-text content."],
            raw_doc_sha256="",
            verified_at=ref_date,
        )

    raw_doc_sha256 = hashlib.sha256(raw_doc.encode("utf-8")).hexdigest()
    active_llm = (
        llm_caller
        if llm_caller is not None
        else (lambda prompt: call_stateless_vertex_json(prompt, enable_google_search=False))
    )

    prompt_1 = _build_intake_pass_1_prompt(clean_prop, source_url, claim_class, clean_keys, raw_doc)
    prompt_2 = _build_intake_pass_2_prompt(clean_prop, source_url, claim_class, clean_keys, raw_doc)

    try:
        pass_1 = active_llm(prompt_1)
    except Exception as exc:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=[f"LLM pass 1 extraction failed: {type(exc).__name__}: {exc}"],
            raw_doc_sha256=raw_doc_sha256,
            verified_at=ref_date,
        )

    try:
        pass_2 = active_llm(prompt_2)
    except Exception as exc:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=[f"LLM pass 2 extraction failed: {type(exc).__name__}: {exc}"],
            raw_doc_sha256=raw_doc_sha256,
            verified_at=ref_date,
        )

    # Require explicit verbatim_quote on pass_2 entries as well in automated intake
    map2, errs2 = _normalize_candidate_entries(pass_2, "pass_2")
    if map2 is not None:
        missing_q2 = [k for k, v in map2.items() if "verbatim_quote" not in v]
        if missing_q2:
            return IntakeDecision(
                status="FREEZE_SITE",
                property_id=clean_prop,
                approved_entries=[],
                reasons=[f"LLM pass 2 entries missing mandatory 'verbatim_quote': {missing_q2}"],
                raw_doc_sha256=raw_doc_sha256,
                verified_at=ref_date,
            )
    elif errs2:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=errs2,
            raw_doc_sha256=raw_doc_sha256,
            verified_at=ref_date,
        )

    decision = verify_extracted_candidate(
        source_url=source_url,
        raw_document_text=raw_doc,
        extracted_fields_pass_1=pass_1,
        extracted_fields_pass_2=pass_2,
        claim_class=claim_class,
        property_id=clean_prop,
        verified_at=ref_date,
    )
    if decision.status != "APPROVED":
        return decision

    approved_keys = {entry["key"] for entry in decision.approved_entries}
    missing_targets = [k for k in clean_keys if k not in approved_keys]
    if missing_targets:
        return IntakeDecision(
            status="FREEZE_SITE",
            property_id=clean_prop,
            approved_entries=[],
            reasons=[f"Requested target_keys missing from verified extraction: {missing_targets}"],
            raw_doc_sha256=decision.raw_doc_sha256,
            verified_at=decision.verified_at,
        )

    return decision


def _serialize_truth_pack_for_prompt(truth_pack_dict: Any) -> str:
    if hasattr(truth_pack_dict, "to_dict") and callable(truth_pack_dict.to_dict):
        obj = truth_pack_dict.to_dict()
    elif is_dataclass(truth_pack_dict):
        obj = {f: getattr(truth_pack_dict, f) for f in truth_pack_dict.__dataclass_fields__}
    else:
        obj = truth_pack_dict
    return json.dumps(obj, indent=2, default=str)


def _build_semantic_critic_prompt(
    property_id: str,
    page_slug: str,
    page_text: str,
    truth_pack_dict: Any,
) -> str:
    truth_json = _serialize_truth_pack_for_prompt(truth_pack_dict)
    return (
        "SEMANTIC FACTUAL CLAIM CRITIC.\n"
        "Compare the rendered page_text strictly against the authoritative Truth Pack JSON.\n"
        "Detect ONLY concrete semantic factual contradictions, such as:\n"
        "- Conflating separate statutory programs or repayment terms (e.g., PSLF 120-month vs RAP 360-month).\n"
        "- Citing an unrelated law or agency for a domain (e.g., FICA or OSHA law cited for workers' compensation).\n"
        "- Mismatching the calculator topic/formula with contradictory statutory limits or rates.\n"
        "Output ONLY valid JSON: {\"violations\": [{\"rule_id\": \"...\", \"truth_key\": \"...\", "
        "\"offending_excerpt\": \"...\", \"explanation\": \"...\", \"severity\": \"error\"}]}.\n"
        "Every 'offending_excerpt' MUST be copied word-for-word verbatim from page_text. "
        "If there are no factual contradictions, return {\"violations\": []}.\n"
        f"property_id={property_id!r}\n"
        f"page_slug={page_slug!r}\n"
        "TRUTH_PACK_JSON_START\n"
        f"{truth_json[:40000]}\n"
        "TRUTH_PACK_JSON_END\n"
        "PAGE_TEXT_START\n"
        f"{page_text[:MAX_PROMPT_DOC_CHARS]}\n"
        "PAGE_TEXT_END\n"
    )


def run_semantic_claim_critic(
    property_id: str,
    page_slug: str,
    page_text: str,
    truth_pack_dict: Any,
    *,
    llm_caller: Optional[Callable[[str], Any]] = None,
    enabled: bool = True,
    fail_closed_on_error: bool = True,
) -> SemanticCriticReport:
    """
    Optional AI semantic claim critic with deterministic verbatim-excerpt gating.
    Every violation reported by the LLM MUST cite a verbatim offending_excerpt
    present in page_text (rejecting hallucinated violations).
    Fails closed with FREEZE_CRITIC_UNAVAILABLE when fail_closed_on_error=True,
    or explicitly marks SKIPPED_OFFLINE when fail_closed_on_error=False.
    """
    if not enabled:
        return SemanticCriticReport(
            status="SKIPPED_DISABLED",
            property_id=property_id,
            page_slug=page_slug,
            reasons=["Semantic claim critic disabled by caller."],
        )

    norm_page = _normalize_whitespace(page_text if isinstance(page_text, str) else "")
    if not norm_page:
        return SemanticCriticReport(
            status="FREEZE_CRITIC_UNAVAILABLE" if fail_closed_on_error else "SKIPPED_OFFLINE",
            property_id=property_id,
            page_slug=page_slug,
            reasons=["page_text is empty."],
        )

    active_llm = (
        llm_caller
        if llm_caller is not None
        else (lambda prompt: call_stateless_vertex_json(prompt, enable_google_search=False))
    )
    prompt = _build_semantic_critic_prompt(property_id, page_slug, page_text, truth_pack_dict)

    try:
        raw_resp = active_llm(prompt)
    except Exception as exc:
        status = "FREEZE_CRITIC_UNAVAILABLE" if fail_closed_on_error else "SKIPPED_OFFLINE"
        return SemanticCriticReport(
            status=status,
            property_id=property_id,
            page_slug=page_slug,
            reasons=[f"Semantic critic LLM error: {type(exc).__name__}: {exc}"],
        )

    raw_violations: Any = None
    if isinstance(raw_resp, dict) and isinstance(raw_resp.get("violations"), list):
        raw_violations = raw_resp["violations"]
    elif isinstance(raw_resp, list):
        raw_violations = raw_resp

    if raw_violations is None:
        status = "FREEZE_CRITIC_UNAVAILABLE" if fail_closed_on_error else "SKIPPED_OFFLINE"
        return SemanticCriticReport(
            status=status,
            property_id=property_id,
            page_slug=page_slug,
            reasons=["Semantic critic returned malformed schema (expected {'violations': [...]})."],
        )

    verified_violations: List[SemanticViolation] = []
    rejected_hallucinations: List[Dict[str, Any]] = []
    reasons: List[str] = []

    for item in raw_violations:
        if not isinstance(item, dict):
            rejected_hallucinations.append({"raw": item, "rejection_reason": "non-dict violation entry"})
            continue
        excerpt_raw = item.get("offending_excerpt")
        norm_excerpt = _normalize_whitespace(excerpt_raw) if isinstance(excerpt_raw, str) else ""
        if len(norm_excerpt) < MIN_EXCERPT_CHARS or norm_excerpt not in norm_page:
            rejected_entry = dict(item)
            rejected_entry["rejection_reason"] = (
                "offending_excerpt not found verbatim in page_text or too short"
            )
            rejected_hallucinations.append(rejected_entry)
            continue

        verified_violations.append(
            SemanticViolation(
                rule_id=str(item.get("rule_id") or "semantic_contradiction"),
                truth_key=str(item.get("truth_key") or ""),
                offending_excerpt=norm_excerpt,
                explanation=str(item.get("explanation") or ""),
                severity=str(item.get("severity") or "error"),
            )
        )

    if rejected_hallucinations:
        reasons.append(
            f"Filtered {len(rejected_hallucinations)} ungrounded critic violation(s) lacking verbatim page_text excerpt."
        )

    if verified_violations:
        reasons.append(f"Confirmed {len(verified_violations)} semantic factual violation(s).")
        return SemanticCriticReport(
            status="VIOLATIONS_FOUND",
            property_id=property_id,
            page_slug=page_slug,
            verified_violations=verified_violations,
            rejected_hallucinated_violations=rejected_hallucinations,
            reasons=reasons,
        )

    return SemanticCriticReport(
        status="PASS",
        property_id=property_id,
        page_slug=page_slug,
        verified_violations=[],
        rejected_hallucinated_violations=rejected_hallucinations,
        reasons=reasons,
    )
