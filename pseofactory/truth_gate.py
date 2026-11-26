"""
pseofactory Unified Zero-Bypass Fail-Closed Factual Gate & Executable Python-vs-JS Math Parity Engine.

Audits 100% of a compiled site's surfaces (HTML, inline <script>, external .js, JSON-LD,
llms.txt, llms-full.txt, manifests, feeds, catalog.json, ai-benchmarks/, video scripts/VTT,
and all syndication channels) against the site's declarative TruthPack.

Design invariants:
1. Designed for 50+ sites dynamically via TruthPack registry (zero hardcoded 4-tenant limits).
2. Fail-closed on missing TruthPack, expired entries, empty dist_dir, malformed JSON/JSON-LD,
   or runtime parsing/Node execution errors (zero swallowed exceptions).
3. Typography errors (forbidden dashes) NEVER silence downstream factual checks.
4. Zero em-dashes (U+2014) and zero en-dashes (U+2013).
"""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from datetime import date, datetime, timezone
import hashlib
import html as _html_lib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple, Union
import urllib.parse


# ---------------------------------------------------------------------------
# Lazy / clean TruthPack integration
# ---------------------------------------------------------------------------

class _FallbackTruthPackMissingError(FileNotFoundError):
    """Fallback missing TruthPack error when pseofactory.truth_pack is unavailable."""


class _FallbackTruthPackExpiredError(ValueError):
    """Fallback expired TruthPack error when pseofactory.truth_pack is unavailable."""


class _FallbackTruthPackValidationError(ValueError):
    """Fallback validation error when pseofactory.truth_pack is unavailable."""


def _get_truth_pack_module() -> Optional[Any]:
    try:
        from pseofactory import truth_pack as tp_mod
        return tp_mod
    except ImportError:
        return None


def _get_truth_pack_errors() -> Tuple[type, type, type]:
    tp = _get_truth_pack_module()
    if tp is not None:
        return (
            getattr(tp, "TruthPackMissingError", _FallbackTruthPackMissingError),
            getattr(tp, "TruthPackExpiredError", _FallbackTruthPackExpiredError),
            getattr(tp, "TruthPackValidationError", _FallbackTruthPackValidationError),
        )
    return (
        _FallbackTruthPackMissingError,
        _FallbackTruthPackExpiredError,
        _FallbackTruthPackValidationError,
    )


def _eval_formula(formula: str, inputs: Dict[str, Any]) -> float:
    tp = _get_truth_pack_module()
    if tp is not None and hasattr(tp, "safe_eval_formula"):
        return float(tp.safe_eval_formula(formula, inputs))
    from pseofactory.contracts import safe_eval_mathematical_formula
    return float(safe_eval_mathematical_formula(formula, inputs))


def _compute_pack_sha256(pack: Any) -> str:
    if pack is None:
        return ""
    tp = _get_truth_pack_module()
    if tp is not None and hasattr(tp, "compute_truth_pack_sha256"):
        try:
            return str(tp.compute_truth_pack_sha256(pack))
        except Exception:
            pass
    serialized = json.dumps(_to_plain_dict(pack), sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_pack_by_id(property_id: str, as_of: Optional[Any] = None) -> Any:
    tp = _get_truth_pack_module()
    if tp is None or not hasattr(tp, "load_truth_pack"):
        missing_cls, _, _ = _get_truth_pack_errors()
        raise missing_cls(f"TruthPack module unavailable; cannot load TruthPack for '{property_id}'")
    try:
        return tp.load_truth_pack(property_id, as_of=as_of)
    except TypeError:
        return tp.load_truth_pack(property_id)


def _load_all_packs() -> Dict[str, Any]:
    tp = _get_truth_pack_module()
    if tp is None or not hasattr(tp, "load_all_truth_packs"):
        return {}
    try:
        raw = tp.load_all_truth_packs(allow_expired=True)
    except TypeError:
        raw = tp.load_all_truth_packs()
    return _normalize_pack_collection(raw)


# ---------------------------------------------------------------------------
# Report & Violation Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TruthViolation:
    """Structured violation emitted by UnifiedTruthGate."""

    gate: str
    severity: str
    file_path: str
    code: str
    message: str
    excerpt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "severity": self.severity,
            "file_path": self.file_path,
            "code": self.code,
            "message": self.message,
            "excerpt": self.excerpt,
        }


@dataclass
class TruthGateReport:
    """Fail-closed audit report returned by UnifiedTruthGate."""

    property_id: str
    violations: List[TruthViolation] = field(default_factory=list)
    files_audited: List[str] = field(default_factory=list)
    truth_pack_sha256: str = ""
    as_of: str = ""
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"

    @property
    def gate_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for v in self.violations:
            counts[v.gate] = counts.get(v.gate, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "passed": self.passed,
            "status": self.status,
            "violation_count": len(self.violations),
            "gate_counts": self.gate_counts,
            "files_audited_count": len(self.files_audited),
            "files_audited": list(self.files_audited),
            "truth_pack_sha256": self.truth_pack_sha256,
            "as_of": self.as_of,
            "duration_ms": round(self.duration_ms, 2),
            "violations": [v.to_dict() for v in self.violations],
        }

    def summary(self) -> str:
        header = (
            f"[{self.status}] property={self.property_id} "
            f"files={len(self.files_audited)} violations={len(self.violations)}"
        )
        if not self.violations:
            return header
        preview = "; ".join(
            f"{v.gate}:{v.code}@{Path(v.file_path).name}: {v.message}"
            for v in self.violations[:5]
        )
        if len(self.violations) > 5:
            preview += f" (+{len(self.violations) - 5} more)"
        return f"{header} | {preview}"


# ---------------------------------------------------------------------------
# Normalization Helpers (Duck-typed TruthPack dataclass OR dict support)
# ---------------------------------------------------------------------------

def _to_plain_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _to_plain_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_plain_dict(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _to_plain_dict(obj.to_dict())
    if is_dataclass(obj):
        return {f: _to_plain_dict(getattr(obj, f)) for f in obj.__dataclass_fields__}
    if hasattr(obj, "__dict__") and not isinstance(obj, (str, bytes, int, float, bool, date, datetime)):
        return {k: _to_plain_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


def _normalize_pack_collection(raw: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            d = _to_plain_dict(v)
            if isinstance(d, dict):
                pid = str(d.get("property_id") or d.get("tenant_id") or k).strip().lower()
                out[pid] = d
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            d = _to_plain_dict(item)
            if isinstance(d, dict):
                pid = str(d.get("property_id") or d.get("tenant_id") or "").strip().lower()
                if pid:
                    out[pid] = d
    return out


def _parse_iso_date(val: Any) -> Optional[date]:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _normalize_entries(pack_dict: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    raw = pack_dict.get("entries")
    out: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            vd = _to_plain_dict(v)
            out.append((str(k), vd if isinstance(vd, dict) else {"value": vd}))
    elif isinstance(raw, (list, tuple)):
        for idx, item in enumerate(raw):
            idict = _to_plain_dict(item)
            if not isinstance(idict, dict):
                idict = {"value": idict}
            k = str(idict.get("id") or idict.get("key") or idict.get("fact_key") or f"entry_{idx}")
            out.append((k, idict))
    return out


def _normalize_formulas(pack_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = pack_dict.get("formulas")
    out: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            vd = _to_plain_dict(v)
            if isinstance(vd, dict):
                item = dict(vd)
                item.setdefault("id", str(k))
                out.append(item)
    elif isinstance(raw, (list, tuple)):
        for idx, item in enumerate(raw):
            idict = _to_plain_dict(item)
            if isinstance(idict, dict):
                copy_d = dict(idict)
                copy_d.setdefault("id", str(copy_d.get("formula_id") or f"formula_{idx}"))
                out.append(copy_d)
    return out


def _normalize_disclosures(pack_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = pack_dict.get("disclosures")
    out: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            vd = _to_plain_dict(v)
            if isinstance(vd, dict):
                item = dict(vd)
                item.setdefault("id", str(k))
                out.append(item)
            elif isinstance(vd, str):
                out.append({"id": str(k), "required_text_patterns": [re.escape(vd)]})
    elif isinstance(raw, (list, tuple)):
        for idx, item in enumerate(raw):
            idict = _to_plain_dict(item)
            if isinstance(idict, dict):
                copy_d = dict(idict)
                copy_d.setdefault("id", str(copy_d.get("disclosure_id") or copy_d.get("name") or f"disclosure_{idx}"))
                out.append(copy_d)
            elif isinstance(idict, str):
                out.append({"id": f"disclosure_{idx}", "required_text_patterns": [re.escape(idict)]})
    return out


def _normalize_citations_allowlist(pack_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = pack_dict.get("citations_allowlist")
    out: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            vd = _to_plain_dict(v)
            if isinstance(vd, dict):
                item = dict(vd)
                item.setdefault("citation", str(k))
                out.append(item)
            elif isinstance(vd, str):
                out.append({"citation": str(k), "pattern": vd})
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            idict = _to_plain_dict(item)
            if isinstance(idict, dict):
                out.append(dict(idict))
            elif isinstance(idict, str):
                out.append({"citation": idict})
    return out


def _normalize_pricing_tiers(pack_dict: Dict[str, Any]) -> Set[float]:
    raw = pack_dict.get("pricing_tiers")
    prices: Set[float] = set()
    if isinstance(raw, dict):
        for val in raw.values():
            vd = _to_plain_dict(val)
            if isinstance(vd, dict) and "price_usd" in vd:
                try:
                    prices.add(round(float(vd["price_usd"]), 2))
                except (TypeError, ValueError):
                    pass
            elif isinstance(vd, (int, float)):
                prices.add(round(float(vd), 2))
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            idict = _to_plain_dict(item)
            if isinstance(idict, dict) and "price_usd" in idict:
                try:
                    prices.add(round(float(idict["price_usd"]), 2))
                except (TypeError, ValueError):
                    pass
            elif isinstance(idict, (int, float)):
                prices.add(round(float(idict), 2))
    return prices


def _extract_domain_tokens(domain_val: str) -> List[str]:
    dom = str(domain_val or "").strip().lower()
    dom = re.sub(r"^https?://", "", dom).split("/")[0].split(":")[0].strip()
    if not dom:
        return []
    tokens = [dom]
    if dom.startswith("www."):
        tokens.append(dom[4:])
    return [t for t in tokens if len(t) >= 4]


def _collect_own_tokens(pack_dict: Dict[str, Any]) -> Set[str]:
    own: Set[str] = set()
    for field_name in ("property_id", "tenant_id", "brand_name"):
        val = str(pack_dict.get(field_name) or "").strip().lower()
        if val:
            own.add(val)
    for dt in _extract_domain_tokens(str(pack_dict.get("canonical_domain") or "")):
        own.add(dt)
    for key in ("brand_aliases", "affiliate_tokens", "allowed_affiliates"):
        seq = pack_dict.get(key)
        if isinstance(seq, (list, tuple, set, dict)):
            items = seq.values() if isinstance(seq, dict) else seq
            for it in items:
                s = str(it or "").strip().lower()
                if s:
                    own.add(s)
    return own


def _collect_foreign_tokens(
    pack_dict: Dict[str, Any],
    all_packs: Dict[str, Any],
) -> List[Tuple[str, str]]:
    """
    Dynamically computes foreign brand/domain/affiliate tokens from all OTHER packs
    in the registry, excluding allowed_shared_legal_tokens and own tokens.
    """
    own_pid = str(pack_dict.get("property_id") or pack_dict.get("tenant_id") or "").strip().lower()
    own_tokens = _collect_own_tokens(pack_dict)
    shared_legal = {
        str(t).strip().lower()
        for t in (pack_dict.get("allowed_shared_legal_tokens") or [])
        if str(t).strip()
    }
    foreign: List[Tuple[str, str]] = []
    seen_tokens: Set[Tuple[str, str]] = set()

    for other_pid, other_raw in sorted(all_packs.items()):
        other_d = _to_plain_dict(other_raw)
        if not isinstance(other_d, dict):
            continue
        opid = str(other_d.get("property_id") or other_d.get("tenant_id") or other_pid).strip().lower()
        if not opid or opid == own_pid:
            continue

        candidates: List[str] = [opid]
        brand = str(other_d.get("brand_name") or "").strip()
        if brand:
            candidates.append(brand)
        candidates.extend(_extract_domain_tokens(str(other_d.get("canonical_domain") or "")))
        for list_key in ("brand_aliases", "foreign_tokens", "affiliate_tokens", "allowed_affiliates"):
            seq = other_d.get(list_key)
            if isinstance(seq, (list, tuple, set, dict)):
                items = seq.values() if isinstance(seq, dict) else seq
                for it in items:
                    s = str(it or "").strip()
                    if s:
                        candidates.append(s)

        for tok in candidates:
            tl = tok.lower()
            if len(tl) < 3 or tl in own_tokens or tl in shared_legal:
                continue
            pair = (opid, tok)
            if pair not in seen_tokens:
                seen_tokens.add(pair)
                foreign.append(pair)

    # Also honor explicit cross_tenant_brand_tokens declared on the TruthPack itself
    for raw_tok in (pack_dict.get("cross_tenant_brand_tokens") or []):
        tok = str(raw_tok or "").strip()
        tl = tok.lower()
        if len(tl) < 3 or tl in own_tokens or tl in shared_legal:
            continue
        pair = ("cross_tenant", tok)
        if pair not in seen_tokens:
            seen_tokens.add(pair)
            foreign.append(pair)

    return foreign


# ---------------------------------------------------------------------------
# HTML DOM + Script + Manifest + JSON-LD Extractor
# ---------------------------------------------------------------------------

class _PageDOMExtractor(HTMLParser):
    """Lightweight deterministic HTML parser extracting DOM tree, scripts, manifests, and visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.elements: List[Dict[str, Any]] = []
        self._stack: List[int] = []
        self.visible_chunks: List[str] = []
        self.jsonld_blocks: List[str] = []
        self.manifest_blocks: List[str] = []
        self.executable_scripts: List[Dict[str, Optional[str]]] = []
        self.canonical_url: str = ""
        self._in_style: int = 0
        self._current_script: Optional[Dict[str, Any]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_l = tag.lower()
        attrs_dict: Dict[str, str] = {}
        for k, v in attrs:
            if k:
                attrs_dict[k.lower()] = "" if v is None else str(v)

        if tag_l == "link" and attrs_dict.get("rel", "").lower() == "canonical":
            href = attrs_dict.get("href", "").strip()
            if href and not self.canonical_url:
                self.canonical_url = href

        if tag_l == "style":
            self._in_style += 1

        if tag_l == "script":
            self._current_script = {
                "type": attrs_dict.get("type", "").strip().lower(),
                "id": attrs_dict.get("id", "").strip(),
                "class": attrs_dict.get("class", "").strip(),
                "src": attrs_dict.get("src"),
                "chunks": [],
            }
            return

        parent_idx = self._stack[-1] if self._stack else -1
        node_idx = len(self.elements)
        node = {
            "idx": node_idx,
            "parent_idx": parent_idx,
            "tag": tag_l,
            "attrs": attrs_dict,
            "id": attrs_dict.get("id", ""),
            "name": attrs_dict.get("name", ""),
            "type": attrs_dict.get("type", "").lower(),
            "class_list": [c for c in attrs_dict.get("class", "").split() if c],
            "value": attrs_dict.get("value", ""),
            "text_chunks": [],
            "raw_chunks": [],
            "options": [],
        }
        self.elements.append(node)

        void_tags = {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }
        if tag_l not in void_tags:
            self._stack.append(node_idx)

        if tag_l == "option" and self._stack:
            for ancestor_idx in reversed(self._stack[:-1]):
                if self.elements[ancestor_idx]["tag"] == "select":
                    self.elements[ancestor_idx]["options"].append({
                        "value": attrs_dict.get("value", ""),
                        "selected": "selected" in attrs_dict,
                        "text_chunks": [],
                    })
                    break

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        tag_l = tag.lower()
        if tag_l == "script" and self._current_script is not None:
            self._finalize_script()
        elif self._stack and self.elements[self._stack[-1]]["tag"] == tag_l:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l == "style" and self._in_style > 0:
            self._in_style -= 1
            return
        if tag_l == "script" and self._current_script is not None:
            self._finalize_script()
            return
        if self._stack:
            for pos in range(len(self._stack) - 1, -1, -1):
                if self.elements[self._stack[pos]]["tag"] == tag_l:
                    del self._stack[pos:]
                    break

    def _finalize_script(self) -> None:
        sc = self._current_script
        self._current_script = None
        if sc is None:
            return
        code = "".join(sc["chunks"])
        stype = sc["type"]
        sid = sc["id"]
        scls = sc["class"].split()
        if stype == "application/ld+json":
            self.jsonld_blocks.append(code)
        elif sid == "calculation-manifest" or "calculation-manifest" in scls:
            self.manifest_blocks.append(code)
        elif stype in ("", "text/javascript", "application/javascript", "module"):
            self.executable_scripts.append({"src": sc["src"], "code": code})

    def handle_data(self, data: str) -> None:
        if self._current_script is not None:
            self._current_script["chunks"].append(data)
            return
        if self._in_style > 0:
            return
        decoded = _html_lib.unescape(data)
        self.visible_chunks.append(decoded)
        for idx in self._stack:
            self.elements[idx]["text_chunks"].append(decoded)
            self.elements[idx]["raw_chunks"].append(data)
        if self._stack and self.elements[self._stack[-1]]["tag"] == "option":
            for ancestor_idx in reversed(self._stack[:-1]):
                if self.elements[ancestor_idx]["tag"] == "select" and self.elements[ancestor_idx]["options"]:
                    self.elements[ancestor_idx]["options"][-1]["text_chunks"].append(decoded)
                    break

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def finalize(self) -> None:
        for node in self.elements:
            node["text"] = re.sub(r"\s+", " ", "".join(node["text_chunks"])).strip()
            if node["tag"] == "select" and not node["value"] and node["options"]:
                sel_opt = next((o for o in node["options"] if o["selected"]), node["options"][0])
                opt_val = sel_opt["value"] or "".join(sel_opt["text_chunks"]).strip()
                node["value"] = opt_val
            del node["text_chunks"]
            del node["raw_chunks"]
            del node["options"]

    @property
    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.visible_chunks)).strip()


def _parse_html_dom(html_content: str) -> _PageDOMExtractor:
    parser = _PageDOMExtractor()
    parser.feed(html_content)
    parser.close()
    parser.finalize()
    return parser


def _strip_style_tags(html_content: str) -> str:
    return re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", html_content, flags=re.IGNORECASE)


def _strip_script_and_style_tags(html_content: str) -> str:
    cleaned = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", html_content, flags=re.IGNORECASE)
    cleaned = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _extract_slug_from_context(
    file_path: str,
    slug: str = "",
    canonical_url: str = "",
) -> str:
    if slug:
        s = re.sub(r"/index\.html$", "", slug.strip("/").lower())
        return s.split("/")[-1] if "/" in s else s
    fp_norm = str(file_path or "").replace("\\", "/").lower()
    m = re.search(r"/tools/([a-z0-9_-]+(?:/[a-z0-9_-]+)?)/index\.html$", fp_norm)
    if m:
        return m.group(1)
    m2 = re.search(r"^tools/([a-z0-9_-]+(?:/[a-z0-9_-]+)?)/index\.html$", fp_norm)
    if m2:
        return m2.group(1)
    if canonical_url:
        cm = re.search(r"/tools/([a-z0-9_-]+(?:/[a-z0-9_-]+)?)/?$", canonical_url.lower())
        if cm:
            return cm.group(1)
    return ""


def _parse_numeric_display(raw_text: str) -> Optional[float]:
    if raw_text is None:
        return None
    s = str(raw_text).strip()
    if not s:
        return None
    m = re.search(r"-?\s*\$?\s*\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return None
    num_s = m.group(0).replace("$", "").replace(",", "").replace(" ", "")
    try:
        val = float(num_s)
        return val if math.isfinite(val) else None
    except ValueError:
        return None


def _numeric_tolerance(expected: float, display_text: str = "") -> float:
    if 0 < abs(expected) < 1.0:
        return 0.0005
    if display_text and "." not in display_text and abs(expected - round(expected)) <= 0.5:
        return 0.51
    return 0.05


def _values_match(actual: float, expected: float, tol: float) -> bool:
    return abs(float(actual) - float(expected)) <= tol


# ---------------------------------------------------------------------------
# Gate 1: Truth Pack Presence, Validity & Expiry
# ---------------------------------------------------------------------------

def _check_truth_pack_validity(
    pack_dict: Optional[Dict[str, Any]],
    property_id: str,
    as_of_date: date,
    file_path: str,
    load_error: Optional[Exception] = None,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    missing_cls, expired_cls, validation_cls = _get_truth_pack_errors()

    if load_error is not None:
        if isinstance(load_error, expired_cls):
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_EXPIRED",
                    message=f"TruthPack for '{property_id}' is expired: {load_error}",
                    excerpt=str(load_error)[:160],
                )
            )
            return violations
        if isinstance(load_error, validation_cls):
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_INVALID",
                    message=f"TruthPack for '{property_id}' failed validation: {load_error}",
                    excerpt=str(load_error)[:160],
                )
            )
            return violations
        if isinstance(load_error, (missing_cls, FileNotFoundError)):
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_MISSING",
                    message=f"Missing TruthPack for property '{property_id}': {load_error}",
                    excerpt=property_id,
                )
            )
            return violations
        violations.append(
            TruthViolation(
                gate="GATE_TRUTH_PACK",
                severity="ERROR",
                file_path=file_path,
                code="TRUTH_PACK_INVALID",
                message=f"Error loading TruthPack for '{property_id}': {type(load_error).__name__}: {load_error}",
                excerpt=property_id,
            )
        )
        return violations

    if not pack_dict or not isinstance(pack_dict, dict):
        violations.append(
            TruthViolation(
                gate="GATE_TRUTH_PACK",
                severity="ERROR",
                file_path=file_path,
                code="TRUTH_PACK_MISSING",
                message=f"Missing TruthPack for property '{property_id}'",
                excerpt=property_id,
            )
        )
        return violations

    pack_exp = _parse_iso_date(pack_dict.get("expires_at"))
    if pack_dict.get("expires_at") is not None:
        if pack_exp is None:
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_INVALID",
                    message=f"Invalid pack-level expires_at value: {pack_dict.get('expires_at')!r}",
                    excerpt=str(pack_dict.get("expires_at")),
                )
            )
        elif pack_exp < as_of_date:
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_EXPIRED",
                    message=f"TruthPack '{property_id}' expired on {pack_exp.isoformat()} (as_of={as_of_date.isoformat()})",
                    excerpt=f"expires_at={pack_exp.isoformat()}",
                )
            )

    for entry_key, entry in _normalize_entries(pack_dict):
        raw_exp = entry.get("expires_at")
        if raw_exp is None:
            continue
        exp_d = _parse_iso_date(raw_exp)
        if exp_d is None:
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_INVALID",
                    message=f"Invalid expires_at on entry '{entry_key}': {raw_exp!r}",
                    excerpt=entry_key,
                )
            )
        elif exp_d < as_of_date:
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=file_path,
                    code="TRUTH_PACK_EXPIRED",
                    message=f"TruthPack entry '{entry_key}' expired on {exp_d.isoformat()} (as_of={as_of_date.isoformat()})",
                    excerpt=f"{entry_key}: expires_at={exp_d.isoformat()}",
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Gate 2: Zero Forbidden Dashes
# ---------------------------------------------------------------------------

def _excerpt_at(text: str, pos: int, radius: int = 45) -> str:
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _check_typography(content: str, file_path: str) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    for dash_char, dash_label in (("\u2014", "em-dash (U+2014)"), ("\u2013", "en-dash (U+2013)")):
        idx = content.find(dash_char)
        if idx != -1:
            count = content.count(dash_char)
            violations.append(
                TruthViolation(
                    gate="GATE_TYPOGRAPHY",
                    severity="ERROR",
                    file_path=file_path,
                    code="FORBIDDEN_DASH",
                    message=f"Forbidden {dash_label} detected ({count} occurrence(s)); use plain ASCII hyphen (-)",
                    excerpt=_excerpt_at(content, idx),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Gate 3: Banned Claims, Superseded Values, Ungrounded Stats, Claim Qualifiers
# ---------------------------------------------------------------------------

def _compile_regex_safe(pattern: str, flags: int = re.IGNORECASE) -> Tuple[Optional[re.Pattern], Optional[str]]:
    try:
        return re.compile(pattern, flags), None
    except re.error as exc:
        return None, str(exc)


def _check_banned_claims(
    scan_surfaces: Sequence[str],
    pack_dict: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    raw_banned = pack_dict.get("banned_claims") or []
    seen_patterns: Set[str] = set()

    for idx, item in enumerate(raw_banned):
        item_d = _to_plain_dict(item)
        if isinstance(item_d, str):
            pat_str = item_d
            custom_msg = ""
        elif isinstance(item_d, dict):
            pat_str = str(item_d.get("pattern") or item_d.get("regex") or item_d.get("text") or "")
            custom_msg = str(item_d.get("message") or item_d.get("reason") or "")
        else:
            continue
        if not pat_str or pat_str in seen_patterns:
            continue

        rx, err = _compile_regex_safe(pat_str, re.IGNORECASE)
        if err is not None:
            violations.append(
                TruthViolation(
                    gate="GATE_RUNTIME_ERROR",
                    severity="ERROR",
                    file_path=file_path,
                    code="GATE_RUNTIME_ERROR",
                    message=f"Invalid banned_claims regex at index {idx} ({pat_str!r}): {err}",
                    excerpt=pat_str,
                )
            )
            continue

        for surface_text in scan_surfaces:
            if not surface_text:
                continue
            m = rx.search(surface_text)
            if m:
                seen_patterns.add(pat_str)
                msg = custom_msg or f"Banned claim matched pattern {pat_str!r}"
                violations.append(
                    TruthViolation(
                        gate="GATE_PROVENANCE",
                        severity="ERROR",
                        file_path=file_path,
                        code="BANNED_CLAIM",
                        message=msg,
                        excerpt=_excerpt_at(surface_text, m.start()),
                    )
                )
                break

    return violations


_HISTORICAL_QUALIFIER_RE = re.compile(
    r"\b(?:prior[- ]year|historical|pre[- ]enactment|pre[- ]obbba|pre[- ]tcja|repealed|"
    r"expired|superseded|formerly|previously|prior\s+law|counterfactual|"
    r"(?:before|prior\s+to)\s+(?:p\.?l\.?\s*119-21|obbba)|"
    r"under\s+(?:old|prior)\s+tcja|old\s+(?:law|cap|limit|rule|tcja)|"
    r"was\s+\$?\d|pre[- ]july\s+4,?\s+2025)\b",
    re.IGNORECASE,
)

_COUNTERFACTUAL_REPEAL_RE = re.compile(
    r"\b(?:pre[- ]obbba|pre[- ]tcja|pre[- ]enactment|repealed|superseded|"
    r"prior\s+law|counterfactual|(?:before|prior\s+to)\s+(?:p\.?l\.?\s*119-21|obbba)|"
    r"under\s+(?:old|prior)\s+tcja|old\s+(?:law|tcja)|pre[- ]july\s+4,?\s+2025)\b",
    re.IGNORECASE,
)

_ACTIVE_YEAR_RE = re.compile(r"\b(202[5-9]|203\d)\b")


def _infer_hist_year(item: Dict[str, Any], effective_year: Optional[int] = None) -> Optional[int]:
    hy = item.get("historical_year") or item.get("year")
    cand_year: Optional[int] = None
    if hy is not None:
        try:
            cand_year = int(hy)
        except (TypeError, ValueError):
            cand_year = None
    if cand_year is None:
        lbl = str(item.get("label") or "")
        m = re.search(r"\b(20\d{2})\b", lbl)
        if m and any(k in lbl.lower() for k in ("pre-", "former", "outdated", "superseded", "prior", "2024", "2025")):
            cand_year = int(m.group(1))
    if cand_year is None:
        return None
    if cand_year >= 2026:
        return None
    if effective_year is not None and cand_year >= effective_year:
        return None
    return cand_year


def _iter_superseded_regexes(
    val: Any,
    effective_year: Optional[int] = None,
) -> List[Tuple[Optional[re.Pattern], Optional[int], str, Optional[str]]]:
    """Expands a superseded_values item into [(compiled_regex, historical_year_or_None, label, regex_error_or_None)]."""
    item = _to_plain_dict(val)
    hist_year: Optional[int] = None
    pat_list: List[str] = []
    label = ""

    if isinstance(item, dict):
        hist_year = _infer_hist_year(item, effective_year=effective_year)
        if isinstance(item.get("patterns"), (list, tuple)):
            pat_list.extend(str(p) for p in item["patterns"] if str(p).strip())
        single_pat = str(item.get("pattern") or item.get("regex") or "").strip()
        if single_pat:
            pat_list.append(single_pat)
        label = str(item.get("value") or (pat_list[0] if pat_list else item.get("label") or ""))
        if not pat_list and item.get("value") is not None:
            fallback_pat = _literal_value_to_regex(item["value"])
            if fallback_pat:
                pat_list.append(fallback_pat)
    else:
        label = str(item)
        fallback_pat = _literal_value_to_regex(item)
        if fallback_pat:
            pat_list.append(fallback_pat)

    results: List[Tuple[Optional[re.Pattern], Optional[int], str, Optional[str]]] = []
    for p in pat_list:
        rx, err = _compile_regex_safe(p, re.IGNORECASE)
        results.append((rx, hist_year, label or p, err))
    return results


def _literal_value_to_regex(val: Any) -> str:
    if isinstance(val, bool):
        return ""
    if isinstance(val, int):
        s = str(val)
        comma_s = f"{val:,}"
        if comma_s != s:
            return rf"(?:\$?\b{re.escape(comma_s)}\b|\b{re.escape(s)}\b)"
        return rf"\b{re.escape(s)}\b"
    if isinstance(val, float):
        if val.is_integer():
            return _literal_value_to_regex(int(val))
        s = f"{val:g}"
        return rf"\b{re.escape(s)}\b"
    s = str(val or "").strip()
    if not s:
        return ""
    # If string looks like a bare dollar/number e.g. "$30,500", anchor boundaries cleanly
    if re.fullmatch(r"\$[\d,]+(?:\.\d+)?", s):
        return rf"{re.escape(s)}(?!\d)"
    if re.fullmatch(r"\d[\d,]*(?:\.\d+)?", s):
        return rf"(?<![\d.]){re.escape(s)}(?![\d.])"
    return re.escape(s)


def _is_valid_historical_context(
    text: str,
    match_start: int,
    match_end: int,
    hist_year: Optional[int],
    entry_hist_label: str = "",
    entry_effective_year: Optional[int] = None,
) -> bool:
    """
    Allows a superseded value ONLY when explicitly year/pre-enactment qualified in the
    local clause and NOT paired with an active/wrong year (e.g. '2026 ... $30,500').
    For active-year counterfactuals (hist_year is None), plain 'In 2026' never exempts;
    explicit counterfactual/repeal qualification is required.
    """
    left_bound = max(0, match_start - 100)
    right_bound = min(len(text), match_end + 80)

    # Narrow to current sentence/clause if delimiters exist
    before = text[left_bound:match_start]
    after = text[match_end:right_bound]
    clause_before = re.split(r"[.;!\n]", before)[-1]
    clause_after = re.split(r"[.;!\n]", after)[0]
    clause = f"{clause_before} {text[match_start:match_end]} {clause_after}"

    years_in_clause = {int(y) for y in _ACTIVE_YEAR_RE.findall(clause)}
    # Check 4-digit years like 2023/2024 too
    all_years = {int(y) for y in re.findall(r"\b(20\d{2})\b", clause)}
    has_active_or_eff_year = any(y >= 2026 for y in years_in_clause) or (
        entry_effective_year is not None and any(y >= entry_effective_year for y in all_years)
    )

    if hist_year is not None:
        # Wrong/later year in same clause (e.g. '2026 ... $30,500' when hist_year=2024) -> NEVER allow
        wrong_years = {y for y in all_years if y != hist_year}
        if wrong_years or has_active_or_eff_year:
            return False
        has_hist_year = hist_year in all_years
        has_hist_marker = bool(_HISTORICAL_QUALIFIER_RE.search(clause))
        if has_hist_year and (
            has_hist_marker
            or re.search(rf"\b(?:in|for|from|of|under|was|before|pre[- ])\s*{hist_year}\b|\b{hist_year}\s+(?:cap|limit|deduction|allowance|rate|threshold|standard|rule)\b", clause, re.IGNORECASE)
        ):
            return True
        if entry_hist_label and entry_hist_label.lower() in clause.lower():
            return True
        return False

    # No explicit historical_year on entry (or pre-enactment counterfactual for active year):
    # If an active/effective year (>= 2026 or >= entry_effective_year) appears in the clause,
    # plain year framing MUST NOT exempt; require explicit counterfactual/repeal qualification.
    if has_active_or_eff_year:
        return bool(_COUNTERFACTUAL_REPEAL_RE.search(clause))
    return bool(_HISTORICAL_QUALIFIER_RE.search(clause))


def _entry_applies_to_file(entry: Dict[str, Any], file_path: str, slug: str = "") -> bool:
    """Returns True if entry has empty applies_to_slugs or matches file_path/slug."""
    applies_to = [str(s or "").strip().lower() for s in (entry.get("applies_to_slugs") or []) if str(s or "").strip()]
    if not applies_to:
        return True
    eff_slug = (slug or _extract_slug_from_context(file_path) or "").strip().lower()
    slug_parts = set(eff_slug.split("/")) if eff_slug else set()
    fp_norm = str(file_path or "").replace("\\", "/").lower()
    for target in applies_to:
        if eff_slug and (
            eff_slug == target
            or target in slug_parts
            or re.search(rf"(?:^|[/\-_]){re.escape(target)}(?:$|[/\-_])", eff_slug)
        ):
            return True
        if re.search(rf"(?:^|[/\-_]){re.escape(target)}(?:$|[/\-_\.])", fp_norm):
            return True
    return False


_JS_STD_DED_CONST_RE = re.compile(
    r"\b(?:tcjaStdDed|sunsetStdDed|tcja_std_ded|stdDed|std_ded|standardDeduction)\s*[:=]\s*"
    r"(?:\{[^}]*\b(?:15000|30000|12050|8600|17200|12700|12900)\b|(?:15000|30000|12050|8600|17200|12700|12900)\b)",
    re.IGNORECASE,
)


def _scan_js_chunks_for_superseded(
    js_chunks: Sequence[str],
    pack_dict: Dict[str, Any],
    file_path: str,
    slug: str,
    seen: Set[Tuple[str, str]],
) -> List[TruthViolation]:
    """Scans inline <script> and external .js chunks for superseded statutory constants."""
    violations: List[TruthViolation] = []
    if not any(c and c.strip() for c in js_chunks):
        return violations

    from pseofactory.contracts import _scan_inline_js_statutory_constants

    for js_code in js_chunks:
        if not js_code or not js_code.strip():
            continue

        # 1. Canonical inline JS statutory constant scanner (tcjaStdDed 15000, bonus 0.20, SUV 30500/31300)
        for msg in _scan_inline_js_statutory_constants(f"<script>{js_code}</script>", file_path):
            sig = ("__js_statutory__", msg)
            if sig not in seen:
                seen.add(sig)
                violations.append(
                    TruthViolation(
                        gate="GATE_PROVENANCE",
                        severity="ERROR",
                        file_path=file_path,
                        code="SUPERSEDED_VALUE",
                        message=msg,
                        excerpt=_excerpt_at(js_code, 0, radius=70),
                    )
                )

        # 2. Additional stdDed / std_ded / 12050 / 8600 / 15000 JS object patterns
        m_std = _JS_STD_DED_CONST_RE.search(js_code)
        if m_std:
            sig = ("__js_statutory__", f"std_ded:{m_std.group(0)}")
            if sig not in seen:
                seen.add(sig)
                violations.append(
                    TruthViolation(
                        gate="GATE_PROVENANCE",
                        severity="ERROR",
                        file_path=file_path,
                        code="SUPERSEDED_VALUE",
                        message="Superseded standard deduction constant found in executable JS",
                        excerpt=_excerpt_at(js_code, m_std.start()),
                    )
                )

        # 3. Data-driven comma-free exact non-round superseded numeric constants (e.g. 15650 FPL, 2067813 HIPAA, 12050, 8600)
        for entry_key, entry in _normalize_entries(pack_dict):
            if not _entry_applies_to_file(entry, file_path, slug=slug):
                continue
            entry_eff_year: Optional[int] = None
            if entry.get("effective_year") is not None:
                try:
                    entry_eff_year = int(entry["effective_year"])
                except (TypeError, ValueError):
                    entry_eff_year = None
            for sup_item in (entry.get("superseded_values") or []):
                if not isinstance(sup_item, dict):
                    continue
                raw_val = sup_item.get("value")
                if raw_val is None or isinstance(raw_val, bool):
                    continue
                try:
                    f_val = float(raw_val)
                except (TypeError, ValueError):
                    continue
                if not f_val.is_integer() or f_val < 1000:
                    continue
                i_val = int(f_val)
                if i_val % 5000 == 0:
                    continue
                hist_year = _infer_hist_year(sup_item, effective_year=entry_eff_year)
                m_num = re.search(rf"\b{i_val}\b", js_code)
                if not m_num:
                    continue
                if hist_year is not None:
                    pre_ctx = js_code[max(0, m_num.start() - 60):m_num.start()]
                    if re.search(rf"[\"']?{hist_year}[\"']?\s*[:=]", pre_ctx):
                        continue
                sig = (entry_key, f"js_num:{i_val}")
                if sig not in seen:
                    seen.add(sig)
                    violations.append(
                        TruthViolation(
                            gate="GATE_PROVENANCE",
                            severity="ERROR",
                            file_path=file_path,
                            code="SUPERSEDED_VALUE",
                            message=f"Superseded statutory constant {i_val} for '{entry_key}' found in executable JS",
                            excerpt=_excerpt_at(js_code, m_num.start()),
                        )
                    )

    return violations


def _check_superseded_values(
    html_or_text: str,
    script_texts: Sequence[str],
    visible_text: str,
    pack_dict: Dict[str, Any],
    file_path: str,
    is_js_file: bool = False,
    slug: str = "",
) -> List[TruthViolation]:
    """
    Checks every entry.superseded_values on BOTH visible text AND inline <script>/external .js.
    Never strips <script> before scanning!
    If an entry defines a non-empty applies_to_slugs list, applies only to matching files/slugs.
    """
    violations: List[TruthViolation] = []
    seen: Set[Tuple[str, str]] = set()

    js_chunks = [html_or_text] if is_js_file else list(script_texts)
    violations.extend(_scan_js_chunks_for_superseded(js_chunks, pack_dict, file_path, slug, seen))

    for entry_key, entry in _normalize_entries(pack_dict):
        superseded_list = entry.get("superseded_values") or []
        if not superseded_list:
            continue
        if not _entry_applies_to_file(entry, file_path, slug=slug):
            continue
        entry_eff_year: Optional[int] = None
        if entry.get("effective_year") is not None:
            try:
                entry_eff_year = int(entry["effective_year"])
            except (TypeError, ValueError):
                entry_eff_year = None
        entry_hist_year: Optional[int] = None
        if entry.get("historical_year") is not None:
            try:
                entry_hist_year = int(entry["historical_year"])
                if entry_hist_year >= 2026 or (entry_eff_year is not None and entry_hist_year >= entry_eff_year):
                    entry_hist_year = None
            except (TypeError, ValueError):
                entry_hist_year = None
        entry_hist_label = str(entry.get("historical_label") or entry.get("pre_enactment_label") or "")

        for sup_item in superseded_list:
            for rx, item_hist_year, label, err in _iter_superseded_regexes(sup_item, effective_year=entry_eff_year):
                if err is not None:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=file_path,
                            code="GATE_RUNTIME_ERROR",
                            message=f"Invalid superseded_values regex in '{entry_key}': {err}",
                            excerpt=label,
                        )
                    )
                    continue
                if rx is None:
                    continue

                effective_hist_year = item_hist_year if item_hist_year is not None else entry_hist_year

                # 1. Scan executable JS (inline <script> or external .js) unconditionally (no prose exemption in JS code)
                js_chunks = [html_or_text] if is_js_file else list(script_texts)
                for js_code in js_chunks:
                    if not js_code:
                        continue
                    for m in rx.finditer(js_code):
                        sig = (entry_key, f"js:{label}")
                        if sig not in seen:
                            seen.add(sig)
                            violations.append(
                                TruthViolation(
                                    gate="GATE_PROVENANCE",
                                    severity="ERROR",
                                    file_path=file_path,
                                    code="SUPERSEDED_VALUE",
                                    message=f"Superseded statutory constant {label!r} for '{entry_key}' found in executable JS",
                                    excerpt=_excerpt_at(js_code, m.start()),
                                )
                            )
                        break

                if is_js_file:
                    continue

                # 2. Scan visible prose / non-script content with smart historical context guard
                scan_target = visible_text if visible_text else html_or_text
                for m in rx.finditer(scan_target):
                    if _is_valid_historical_context(
                        scan_target,
                        m.start(),
                        m.end(),
                        effective_hist_year,
                        entry_hist_label,
                        entry_effective_year=entry_eff_year,
                    ):
                        continue
                    sig = (entry_key, f"text:{label}")
                    if sig not in seen:
                        seen.add(sig)
                        violations.append(
                            TruthViolation(
                                gate="GATE_PROVENANCE",
                                severity="ERROR",
                                file_path=file_path,
                                code="SUPERSEDED_VALUE",
                                message=f"Superseded value {label!r} for '{entry_key}' used without valid historical year qualification",
                                excerpt=_excerpt_at(scan_target, m.start()),
                            )
                        )
                    break

    return violations


_UNGROUNDED_STAT_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(
        r"\b(?:average|avg\.?|mean|median|typical(?:ly)?|empirical\s+model(?:ing)?|"
        r"statistical\s+analysis|studies?\s+show|research\s+shows|benchmarks?\s+show|"
        r"data\s+demonstrates|modeling\s+demonstrates|demonstrates\s+(?:a|an)?|"
        r"saves?|reduces?|cuts?)\b[^.\n]{0,65}?(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+(?:\.\d+)?)\s*%\s+(?:reduction|savings|decrease|improvement|drop|lower|higher|drag|lift|on\s+average)\b",
        re.IGNORECASE,
    ),
)


def _collect_grounded_numbers(
    pack_dict: Dict[str, Any],
    manifest_data: Optional[Dict[str, Any]],
    file_path: str = "",
    slug: str = "",
) -> Set[float]:
    grounded: Set[float] = set()

    def _add_val(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            fv = float(v)
            grounded.add(round(fv, 4))
            if 0 < abs(fv) <= 1.0:
                grounded.add(round(fv * 100.0, 4))
        elif isinstance(v, str):
            for num_m in re.finditer(r"\d+(?:\.\d+)?", v.replace(",", "")):
                try:
                    fv = float(num_m.group(0))
                    grounded.add(round(fv, 4))
                except ValueError:
                    pass
        elif isinstance(v, (list, tuple, set)):
            for x in v:
                _add_val(x)
        elif isinstance(v, dict):
            for x in v.values():
                _add_val(x)

    eff_slug = (slug or _extract_slug_from_context(file_path) or "").strip().lower()
    for _, entry in _normalize_entries(pack_dict):
        cclass = str(entry.get("claim_class") or "enacted_law").strip().lower()
        if cclass not in ("enacted_law", "market_benchmark", "future_projection"):
            continue
        if file_path or slug:
            if not _entry_applies_to_file(entry, file_path, slug=slug):
                continue
            forbidden_slugs = [
                str(s or "").strip().lower()
                for s in (entry.get("forbidden_on_slugs") or [])
                if str(s or "").strip()
            ]
            if forbidden_slugs and eff_slug and any(
                eff_slug == target or re.search(rf"(?:^|[/\-_]){re.escape(target)}(?:$|[/\-_])", eff_slug)
                for target in forbidden_slugs
            ):
                continue
        for field_key in ("value", "allowed_values", "numeric_values", "rate_pct", "text", "summary"):
            if field_key in entry:
                _add_val(entry[field_key])

    if isinstance(manifest_data, dict):
        if manifest_data.get("published_output") is not None:
            _add_val(manifest_data["published_output"])
        if isinstance(manifest_data.get("inputs"), dict):
            _add_val(manifest_data["inputs"])
        f_str = str(manifest_data.get("formula") or "").strip()
        in_d = manifest_data.get("inputs")
        if f_str and isinstance(in_d, dict):
            try:
                _add_val(_eval_formula(f_str, in_d))
            except Exception:
                pass

    return grounded


def _check_ungrounded_stats(
    visible_text: str,
    pack_dict: Dict[str, Any],
    manifest_data: Optional[Dict[str, Any]],
    file_path: str,
    slug: str = "",
) -> List[TruthViolation]:
    if not visible_text:
        return []
    grounded = _collect_grounded_numbers(pack_dict, manifest_data, file_path=file_path, slug=slug)
    violations: List[TruthViolation] = []
    seen: Set[str] = set()

    for rx in _UNGROUNDED_STAT_PATTERNS:
        for m in rx.finditer(visible_text):
            pct_str = m.group(1)
            try:
                pct_val = round(float(pct_str), 4)
            except ValueError:
                continue
            # Check if grounded within 0.01 tolerance
            if any(abs(pct_val - g) <= 0.01 for g in grounded):
                continue
            excerpt = _excerpt_at(visible_text, m.start())
            if pct_str in seen:
                continue
            seen.add(pct_str)
            violations.append(
                TruthViolation(
                    gate="GATE_PROVENANCE",
                    severity="ERROR",
                    file_path=file_path,
                    code="UNGROUNDED_STAT",
                    message=f"Ungrounded statistical claim ({pct_str}%) not backed by TruthPack entries or page formula",
                    excerpt=excerpt,
                )
            )
    return violations


_DEFAULT_BENCHMARK_QUALIFIER_RE = re.compile(
    r"\b(?:estimate|estimated|estimates|benchmark|benchmarks|range|ranges|underwriting|"
    r"indicative|typical|typically|market\s+rate|illustrative|planning\s+only|subject\s+to)\b",
    re.IGNORECASE,
)
_DEFAULT_PROJECTION_LABEL_RE = re.compile(
    r"\b(?:projection|projected|forecast|forecasted|unenacted|proposed|"
    r"pending\s+legislation|estimated\s+future|hypothetical|illustrative\s+projection)\b",
    re.IGNORECASE,
)


def _entry_match_patterns(entry: Dict[str, Any]) -> List[str]:
    pats: List[str] = []
    for k in ("match_patterns", "render_patterns"):
        raw = entry.get(k)
        if isinstance(raw, (list, tuple)):
            pats.extend(str(p) for p in raw if str(p).strip())
    if not pats and entry.get("value") is not None:
        val = entry["value"]
        if isinstance(val, str) and len(val.strip()) >= 3:
            pats.append(re.escape(val.strip()))
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            # Avoid matching generic tiny numbers like 0, 1, 2 unless match_patterns provided
            if abs(float(val)) >= 10:
                pats.append(_literal_value_to_regex(val))
    return pats


def _check_claim_qualifiers(
    text_to_check: str,
    pack_dict: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    if not text_to_check:
        return []
    violations: List[TruthViolation] = []

    for entry_key, entry in _normalize_entries(pack_dict):
        cclass = str(entry.get("claim_class") or "enacted_law").strip().lower()
        if cclass not in ("market_benchmark", "future_projection"):
            continue

        match_pats = _entry_match_patterns(entry)
        if not match_pats:
            continue

        matched_excerpt = ""
        for mp in match_pats:
            rx, err = _compile_regex_safe(mp, re.IGNORECASE)
            if err is not None:
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=file_path,
                        code="GATE_RUNTIME_ERROR",
                        message=f"Invalid match_patterns regex on '{entry_key}': {err}",
                        excerpt=mp,
                    )
                )
                continue
            if rx is not None:
                m = rx.search(text_to_check)
                if m:
                    matched_excerpt = _excerpt_at(text_to_check, m.start())
                    break

        if not matched_excerpt:
            continue

        req_pats = entry.get("required_qualifier_patterns") or []
        if req_pats:
            has_qual = False
            for qp in req_pats:
                qrx, qerr = _compile_regex_safe(str(qp), re.IGNORECASE)
                if qerr is not None:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=file_path,
                            code="GATE_RUNTIME_ERROR",
                            message=f"Invalid required_qualifier_patterns regex on '{entry_key}': {qerr}",
                            excerpt=str(qp),
                        )
                    )
                    continue
                if qrx is not None and qrx.search(text_to_check):
                    has_qual = True
                    break
        else:
            if cclass == "market_benchmark":
                has_qual = bool(_DEFAULT_BENCHMARK_QUALIFIER_RE.search(text_to_check))
            else:
                has_qual = bool(_DEFAULT_PROJECTION_LABEL_RE.search(text_to_check))

        if not has_qual:
            code = "MISSING_BENCHMARK_QUALIFIER" if cclass == "market_benchmark" else "MISSING_PROJECTION_LABEL"
            violations.append(
                TruthViolation(
                    gate="GATE_PROVENANCE",
                    severity="ERROR",
                    file_path=file_path,
                    code=code,
                    message=f"{cclass} entry '{entry_key}' rendered without required qualifier/label",
                    excerpt=matched_excerpt,
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Gate 4: Citation Provenance & Domain-Topic Binding
# ---------------------------------------------------------------------------

_CITATION_EXTRACTORS: Tuple[re.Pattern, ...] = (
    re.compile(r"\bIRC[ \t]+Sections?[ \t]*\d+[A-Za-z]?(?:\([a-zA-Z0-9]+\))*", re.IGNORECASE),
    re.compile(r"\bIRC[ \t]+Sections[ \t]*(?=\.|,|;|$|\"|')", re.IGNORECASE),
    re.compile(r"\b\d+[ \t]+U\.S\.C\.[ \t]+(?:Sections?[ \t]+|Sec\.?[ \t]+|§[ \t]*)?\d+[A-Za-z0-9().-]*", re.IGNORECASE),
    re.compile(r"\b\d+[ \t]+C\.?F\.?R\.?[ \t]+(?:Parts?[ \t]+|Sections?[ \t]+|Sec\.?[ \t]+|§[ \t]*)?\d+(?:\.\d+)?(?:\([a-zA-Z0-9]+\))*", re.IGNORECASE),
    re.compile(r"\b(?:IRS[ \t]+)?Rev\.[ \t]*Proc\.[ \t]*\d{4}-\d+", re.IGNORECASE),
    re.compile(r"\bFAR[ \t]+(?:Part[ \t]+)?\d+(?:\.\d+)*(?:-\d+)?"),
    re.compile(r"\b(?:P\.L\.|Pub\.[ \t]*L\.)[ \t]*\d+-\d+", re.IGNORECASE),
)

_VTT_CUE_TIMING_RE = re.compile(
    r"^\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}(?:\s+.*)?$"
)
_VTT_INLINE_TAG_RE = re.compile(
    r"<(?:/?[a-zA-Z][a-zA-Z0-9._-]*(?:\s+[^>]*)?|(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})>"
)


def _extract_webvtt_spoken_text(vtt_text: str) -> str:
    """Strips WebVTT headers, NOTE/STYLE/REGION blocks, cue IDs, and cue timestamps."""
    lines = vtt_text.splitlines()
    out_lines: List[str] = []
    in_header = False
    in_skip_block = False
    n = len(lines)
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if idx == 0 and stripped.upper().startswith("WEBVTT"):
            in_header = True
            continue
        if in_header:
            if not stripped:
                in_header = False
            continue
        if in_skip_block:
            if not stripped:
                in_skip_block = False
            continue
        if stripped == "NOTE" or stripped.startswith(("NOTE ", "NOTE\t", "STYLE", "REGION")):
            in_skip_block = True
            continue
        if not stripped:
            continue
        if _VTT_CUE_TIMING_RE.match(stripped):
            continue
        if idx + 1 < n and _VTT_CUE_TIMING_RE.match(lines[idx + 1].strip()):
            continue
        cleaned_line = _VTT_INLINE_TAG_RE.sub("", stripped).strip()
        if cleaned_line:
            out_lines.append(cleaned_line)
    return re.sub(r"[ \t]+", " ", " ".join(out_lines)).strip()


def _extract_citations(text: str) -> List[Tuple[str, int]]:
    found: List[Tuple[str, int]] = []
    seen_spans: Set[Tuple[int, int]] = set()
    for rx in _CITATION_EXTRACTORS:
        for m in rx.finditer(text):
            span = (m.start(), m.end())
            if any(s <= span[0] and span[1] <= e for s, e in seen_spans):
                continue
            seen_spans.add(span)
            cit_str = re.sub(r"\s+", " ", m.group(0)).strip()
            cit_str = cit_str.rstrip("].")
            while cit_str.endswith(")") and cit_str.count(")") > cit_str.count("("):
                cit_str = cit_str[:-1].rstrip("].")
            if cit_str:
                found.append((cit_str, m.start()))
    return found


def _citation_matches_allow_item(citation: str, item: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    pat_list: List[str] = []
    if isinstance(item.get("patterns"), (list, tuple)):
        pat_list.extend(str(p).strip() for p in item["patterns"] if str(p).strip())
    single_pat = str(item.get("pattern") or item.get("regex") or "").strip()
    if single_pat:
        pat_list.append(single_pat)
    for pat in pat_list:
        rx, err = _compile_regex_safe(pat, re.IGNORECASE)
        if err is not None:
            return False, err
        if rx and rx.search(citation):
            return True, None
    if pat_list:
        return False, None

    base = str(item.get("citation") or item.get("canonical") or item.get("text") or "").strip()
    if not base:
        return False, None
    c_norm = re.sub(r"\s+", " ", citation).strip().lower()
    b_norm = re.sub(r"\s+", " ", base).strip().lower()
    if c_norm == b_norm or c_norm.startswith(b_norm) or b_norm in c_norm:
        # Guard against e.g. allow "IRC Section 179" matching "IRC Section 1790"
        idx = c_norm.find(b_norm)
        if idx != -1:
            end_pos = idx + len(b_norm)
            if end_pos < len(c_norm) and c_norm[end_pos].isalnum():
                return False, None
            return True, None
    return False, None


def _check_citations(
    text_sources: Sequence[str],
    slug: str,
    pack_dict: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    allowlist = _normalize_citations_allowlist(pack_dict)
    seen_citations: Set[str] = set()

    for src in text_sources:
        if not src:
            continue
        for cit, pos in _extract_citations(src):
            cit_key = cit.lower()
            if cit_key in seen_citations:
                continue
            seen_citations.add(cit_key)

            # Truncated plural "IRC Sections " with no number
            if re.fullmatch(r"irc\s+sections?", cit, re.IGNORECASE):
                violations.append(
                    TruthViolation(
                        gate="GATE_CITATIONS",
                        severity="ERROR",
                        file_path=file_path,
                        code="UNLISTED_CITATION",
                        message=f"Truncated or malformed statutory citation '{cit}'",
                        excerpt=_excerpt_at(src, pos),
                    )
                )
                continue

            matched_items: List[Dict[str, Any]] = []
            for allow_item in allowlist:
                is_match, rx_err = _citation_matches_allow_item(cit, allow_item)
                if rx_err is not None:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=file_path,
                            code="GATE_RUNTIME_ERROR",
                            message=f"Invalid citations_allowlist regex: {rx_err}",
                            excerpt=str(allow_item),
                        )
                    )
                    continue
                if is_match:
                    matched_items.append(allow_item)

            if not matched_items:
                violations.append(
                    TruthViolation(
                        gate="GATE_CITATIONS",
                        severity="ERROR",
                        file_path=file_path,
                        code="UNLISTED_CITATION",
                        message=f"Citation '{cit}' is not in TruthPack citations_allowlist",
                        excerpt=_excerpt_at(src, pos),
                    )
                )
                continue

            if slug:
                topic_ok = False
                topic_err_msg = ""
                for mi in matched_items:
                    forb = mi.get("forbidden_slug_patterns") or []
                    allowed = mi.get("allowed_slug_patterns") or []
                    forb_hit = False
                    for fp in forb:
                        frx, ferr = _compile_regex_safe(str(fp), re.IGNORECASE)
                        if ferr:
                            violations.append(
                                TruthViolation(
                                    gate="GATE_RUNTIME_ERROR",
                                    severity="ERROR",
                                    file_path=file_path,
                                    code="GATE_RUNTIME_ERROR",
                                    message=f"Invalid forbidden_slug_patterns regex {fp!r}: {ferr}",
                                    excerpt=cit,
                                )
                            )
                            continue
                        if frx and frx.search(slug):
                            forb_hit = True
                            topic_err_msg = f"Citation '{cit}' is forbidden on topic slug '{slug}' (matched {fp!r})"
                            break
                    if forb_hit:
                        continue
                    if allowed:
                        allow_hit = False
                        for ap in allowed:
                            arx, aerr = _compile_regex_safe(str(ap), re.IGNORECASE)
                            if aerr:
                                violations.append(
                                    TruthViolation(
                                        gate="GATE_RUNTIME_ERROR",
                                        severity="ERROR",
                                        file_path=file_path,
                                        code="GATE_RUNTIME_ERROR",
                                        message=f"Invalid allowed_slug_patterns regex {ap!r}: {aerr}",
                                        excerpt=cit,
                                    )
                                )
                                continue
                            if arx and arx.search(slug):
                                allow_hit = True
                                break
                        if not allow_hit:
                            topic_err_msg = f"Citation '{cit}' is outside allowed_slug_patterns for topic slug '{slug}'"
                            continue
                    topic_ok = True
                    break

                if not topic_ok:
                    violations.append(
                        TruthViolation(
                            gate="GATE_CITATIONS",
                            severity="ERROR",
                            file_path=file_path,
                            code="FORBIDDEN_CITATION_TOPIC",
                            message=topic_err_msg or f"Citation '{cit}' does not bind to topic slug '{slug}'",
                            excerpt=_excerpt_at(src, pos),
                        )
                    )

    return violations


# ---------------------------------------------------------------------------
# Gate 5: Mandatory Disclosures & Dynamic Cross-Tenant Isolation
# ---------------------------------------------------------------------------

def _matches_any_pattern(patterns: Sequence[str], target: str, file_path: str, violations: List[TruthViolation]) -> bool:
    for pat in patterns:
        rx, err = _compile_regex_safe(str(pat), re.IGNORECASE)
        if err is not None:
            violations.append(
                TruthViolation(
                    gate="GATE_RUNTIME_ERROR",
                    severity="ERROR",
                    file_path=file_path,
                    code="GATE_RUNTIME_ERROR",
                    message=f"Invalid disclosure pattern {pat!r}: {err}",
                    excerpt=str(pat),
                )
            )
            continue
        if rx is not None and rx.search(target):
            return True
    return False


_PROSE_DISCLOSURE_SURFACES: FrozenSet[str] = frozenset({"html", "llms_full"})


def _check_disclosures(
    text_to_check: str,
    surface_kind: str,
    slug: str,
    pack_dict: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    target_slug_or_path = f"{slug} {file_path}".strip()
    sk_low = surface_kind.lower()

    for disc in _normalize_disclosures(pack_dict):
        disc_id = str(disc.get("id") or disc.get("name") or "disclosure")
        surfaces = [str(s).lower() for s in (disc.get("applies_to_surfaces") or disc.get("required_surfaces") or [])]
        if surfaces:
            if "all" not in surfaces and sk_low not in surfaces:
                continue
        elif sk_low not in _PROSE_DISCLOSURE_SURFACES:
            # Disclosures without explicit surface overrides apply only to prose/content surfaces
            continue

        mandatory_all = bool(disc.get("mandatory_for_all", False))
        slug_pats = disc.get("applies_to_slug_patterns") or []
        content_pats = disc.get("applies_to_content_patterns") or []

        applies = False
        if mandatory_all:
            applies = True
        elif slug_pats or content_pats:
            if slug_pats and _matches_any_pattern(slug_pats, target_slug_or_path, file_path, violations):
                applies = True
            if not applies and content_pats and _matches_any_pattern(content_pats, text_to_check, file_path, violations):
                applies = True
        else:
            # Global disclosure without trigger filters applies to HTML (or explicitly listed surfaces)
            applies = surface_kind == "html" or bool(surfaces)

        if not applies:
            continue

        req_pats = disc.get("required_text_patterns") or []
        if not req_pats:
            continue
        if not _matches_any_pattern(req_pats, text_to_check, file_path, violations):
            violations.append(
                TruthViolation(
                    gate="GATE_DISCLOSURES_ISOLATION",
                    severity="ERROR",
                    file_path=file_path,
                    code="MISSING_DISCLOSURE",
                    message=f"Mandatory disclosure '{disc_id}' missing required text",
                    excerpt=disc_id,
                )
            )

    return violations


def _check_cross_tenant_isolation(
    content: str,
    foreign_tokens: Sequence[Tuple[str, str]],
    file_path: str,
) -> List[TruthViolation]:
    if not content or not foreign_tokens:
        return []
    violations: List[TruthViolation] = []
    seen_foreign: Set[str] = set()

    for other_pid, tok in foreign_tokens:
        tl = tok.lower()
        if tl in seen_foreign:
            continue
        if "." in tok or "/" in tok or "-" in tok:
            rx = re.compile(rf"(?<![a-z0-9_-]){re.escape(tok)}(?![a-z0-9_-])", re.IGNORECASE)
        else:
            rx = re.compile(rf"\b{re.escape(tok)}\b", re.IGNORECASE)
        m = rx.search(content)
        if m:
            seen_foreign.add(tl)
            violations.append(
                TruthViolation(
                    gate="GATE_DISCLOSURES_ISOLATION",
                    severity="ERROR",
                    file_path=file_path,
                    code="CROSS_TENANT_CONTAMINATION",
                    message=f"Cross-tenant contamination: foreign token '{tok}' (from '{other_pid}') detected",
                    excerpt=_excerpt_at(content, m.start()),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Gate 6: Tool-Topic vs. Widget/Formula Binding & Executable Python-vs-JS Parity
# ---------------------------------------------------------------------------

_NODE_DOM_SHIM_RUNNER = r"""
const fs = require("fs");
const vm = require("vm");

const payload = JSON.parse(fs.readFileSync(0, "utf8"));

function stripTags(html) {
  return String(html || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function makeClassList(initialList) {
  const set = new Set(initialList || []);
  return {
    contains(c) { return set.has(c); },
    add(c) { set.add(c); },
    remove(c) { set.delete(c); },
    toggle(c) { if (set.has(c)) { set.delete(c); return false; } set.add(c); return true; },
    toString() { return Array.from(set).join(" "); }
  };
}

const nodesByIdx = new Map();
const allNodes = [];
const domContentLoadedListeners = [];

function makeElement(raw) {
  const attrs = Object.assign({}, raw.attrs || {});
  let _text = String(raw.text || "");
  let _html = _text;
  const listeners = {};
  const clsList = makeClassList(raw.class_list || []);
  const dataset = {};
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("data-")) {
      const camel = k.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
      dataset[camel] = v;
    }
  }
  const el = {
    _idx: raw.idx,
    _parentIdx: raw.parent_idx,
    _children: [],
    tagName: String(raw.tag || "div").toUpperCase(),
    id: String(raw.id || ""),
    name: String(raw.name || ""),
    type: String(raw.type || ""),
    value: raw.value !== undefined && raw.value !== null ? String(raw.value) : "",
    href: attrs.href || "",
    style: {},
    dataset,
    classList: clsList,
    get className() { return clsList.toString(); },
    set className(v) {
      const parts = String(v || "").split(/\s+/).filter(Boolean);
      const next = makeClassList(parts);
      el.classList = next;
    },
    get textContent() { return _text; },
    set textContent(v) { _text = String(v == null ? "" : v); _html = _text; },
    get innerText() { return _text; },
    set innerText(v) { _text = String(v == null ? "" : v); _html = _text; },
    get innerHTML() { return _html; },
    set innerHTML(v) { _html = String(v == null ? "" : v); _text = stripTags(_html); },
    getAttribute(k) {
      const kl = String(k || "").toLowerCase();
      if (kl === "id") return el.id || null;
      if (kl === "value") return el.value;
      if (kl === "class") return el.className || null;
      return Object.prototype.hasOwnProperty.call(attrs, kl) ? attrs[kl] : null;
    },
    setAttribute(k, v) {
      const kl = String(k || "").toLowerCase();
      attrs[kl] = String(v);
      if (kl === "id") el.id = String(v);
      if (kl === "value") el.value = String(v);
    },
    hasAttribute(k) {
      const kl = String(k || "").toLowerCase();
      return Object.prototype.hasOwnProperty.call(attrs, kl);
    },
    addEventListener(ev, fn) {
      if (!listeners[ev]) listeners[ev] = [];
      listeners[ev].push(fn);
    },
    dispatchEvent(evObj) {
      const evType = typeof evObj === "string" ? evObj : (evObj && evObj.type);
      const evt = typeof evObj === "object" && evObj !== null ? evObj : { type: evType };
      if (!evt.target) evt.target = el;
      if (!evt.preventDefault) evt.preventDefault = function() {};
      const fns = listeners[evType] || [];
      for (const fn of fns) {
        fn.call(el, evt);
      }
      return true;
    },
    querySelector(sel) {
      const res = el.querySelectorAll(sel);
      return res.length > 0 ? res[0] : null;
    },
    querySelectorAll(sel) {
      const descendants = collectDescendants(el);
      return matchSelectorList(descendants, sel);
    },
    appendChild(child) {
      if (child && !el._children.includes(child)) {
        el._children.push(child);
        child._parentIdx = el._idx;
      }
      return child;
    }
  };
  return el;
}

function collectDescendants(rootEl) {
  const out = [];
  const stack = [...rootEl._children];
  while (stack.length > 0) {
    const cur = stack.shift();
    out.push(cur);
    if (cur._children && cur._children.length > 0) {
      stack.unshift(...cur._children);
    }
  }
  return out;
}

function matchSimpleToken(el, token) {
  let rest = token.trim();
  if (!rest) return false;
  let tagReq = "";
  const tagM = rest.match(/^[a-zA-Z][a-zA-Z0-9-]*/);
  if (tagM) {
    tagReq = tagM[0].toUpperCase();
    rest = rest.slice(tagM[0].length);
  }
  if (tagReq && el.tagName !== tagReq) return false;

  while (rest.length > 0) {
    if (rest[0] === "#") {
      const m = rest.slice(1).match(/^[a-zA-Z0-9_-]+/);
      if (!m) return false;
      if (el.id !== m[0]) return false;
      rest = rest.slice(1 + m[0].length);
    } else if (rest[0] === ".") {
      const m = rest.slice(1).match(/^[a-zA-Z0-9_-]+/);
      if (!m) return false;
      if (!el.classList.contains(m[0])) return false;
      rest = rest.slice(1 + m[0].length);
    } else if (rest[0] === "[") {
      const endIdx = rest.indexOf("]");
      if (endIdx === -1) return false;
      const inner = rest.slice(1, endIdx).trim();
      rest = rest.slice(endIdx + 1);
      const eqIdx = inner.indexOf("=");
      if (eqIdx === -1) {
        if (!el.hasAttribute(inner)) return false;
      } else {
        const attrName = inner.slice(0, eqIdx).trim().toLowerCase();
        const attrVal = inner.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, "");
        const actual = attrName === "type" ? el.type : (attrName === "name" ? el.name : el.getAttribute(attrName));
        if (String(actual || "").toLowerCase() !== attrVal.toLowerCase()) return false;
      }
    } else {
      return false;
    }
  }
  return true;
}

function isDescendantOf(el, ancestor) {
  let pid = el._parentIdx;
  while (pid !== undefined && pid !== null && pid >= 0) {
    if (pid === ancestor._idx) return true;
    const p = nodesByIdx.get(pid);
    if (!p) break;
    pid = p._parentIdx;
  }
  return false;
}

function matchSingleSelector(pool, sel) {
  const parts = sel.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return [];
  if (parts.length === 1) {
    return pool.filter((el) => matchSimpleToken(el, parts[0]));
  }
  const leafToken = parts[parts.length - 1];
  const ancestorTokens = parts.slice(0, -1);
  return pool.filter((el) => {
    if (!matchSimpleToken(el, leafToken)) return false;
    let cur = el;
    for (let i = ancestorTokens.length - 1; i >= 0; i--) {
      let foundAnc = null;
      let pid = cur._parentIdx;
      while (pid !== undefined && pid !== null && pid >= 0) {
        const p = nodesByIdx.get(pid);
        if (!p) break;
        if (matchSimpleToken(p, ancestorTokens[i])) {
          foundAnc = p;
          break;
        }
        pid = p._parentIdx;
      }
      if (!foundAnc) return false;
      cur = foundAnc;
    }
    return true;
  });
}

function matchSelectorList(pool, selStr) {
  const parts = String(selStr || "").split(",");
  const seen = new Set();
  const out = [];
  for (const part of parts) {
    for (const el of matchSingleSelector(pool, part)) {
      if (!seen.has(el._idx)) {
        seen.add(el._idx);
        out.push(el);
      }
    }
  }
  return out;
}

for (const raw of payload.elements || []) {
  const el = makeElement(raw);
  nodesByIdx.set(el._idx, el);
  allNodes.push(el);
}
for (const el of allNodes) {
  if (el._parentIdx >= 0 && nodesByIdx.has(el._parentIdx)) {
    nodesByIdx.get(el._parentIdx)._children.push(el);
  }
}

const documentObj = {
  getElementById(id) {
    return allNodes.find((el) => el.id === id) || null;
  },
  querySelector(sel) {
    const res = matchSelectorList(allNodes, sel);
    return res.length > 0 ? res[0] : null;
  },
  querySelectorAll(sel) {
    return matchSelectorList(allNodes, sel);
  },
  createElement(tag) {
    return makeElement({ idx: -(allNodes.length + 1), parent_idx: -1, tag, attrs: {}, class_list: [] });
  },
  addEventListener(ev, fn) {
    if (ev === "DOMContentLoaded") domContentLoadedListeners.push(fn);
  },
  body: allNodes.find((el) => el.tagName === "BODY") || makeElement({ idx: -999, parent_idx: -1, tag: "body", attrs: {}, class_list: [] })
};

const windowObj = globalThis;
windowObj.window = windowObj;
windowObj.self = windowObj;
windowObj.document = documentObj;
windowObj.location = {
  href: "https://example.com/tools/" + (payload.slug || "") + "/",
  origin: "https://example.com",
  pathname: "/tools/" + (payload.slug || "") + "/",
  search: "",
  hash: ""
};
windowObj.history = { replaceState() {}, pushState() {} };
windowObj.addEventListener = function(ev, fn) {
  if (ev === "DOMContentLoaded") domContentLoadedListeners.push(fn);
};
windowObj.setTimeout = function() { return 0; };
windowObj.clearTimeout = function() {};
windowObj.localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
windowObj.sessionStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
windowObj.fetch = function() { return Promise.resolve({ ok: false, json: async () => ({}) }); };

function findAllOutputTexts() {
  const res = { primary: "", output_value: "" };
  if (payload.primary_metric_id) {
    const pm = documentObj.getElementById(payload.primary_metric_id);
    if (pm) res.primary = pm.textContent;
  }
  const outNodes = documentObj.querySelectorAll(".output-value");
  for (const n of outNodes) {
    if (!n.classList.contains("overlay-preset-readout")) {
      res.output_value = n.textContent;
      break;
    }
  }
  return res;
}

function normKey(s) {
  return String(s || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
}

function findMatchingInputElements(key) {
  const nk = normKey(key);
  const matches = [];
  for (const el of allNodes) {
    if (!["INPUT", "SELECT"].includes(el.tagName)) continue;
    const rawId = String(el.id || "");
    const rawName = String(el.name || "");
    const nName = normKey(rawName);
    const nIdFull = normKey(rawId);
    const nId = nIdFull.replace(/^(?:calc_input_|input_|range_|inp_|calc_|gh_|lb_|px_|ph_)/, "");
    if (
      rawId === key ||
      rawName === key ||
      nName === nk ||
      nIdFull === nk ||
      nId === nk ||
      (nk && (nIdFull.endsWith("_" + nk) || rawId.toLowerCase().endsWith("-" + String(key).toLowerCase())))
    ) {
      matches.push(el);
    }
  }
  return matches;
}

function findParentForm(el) {
  let pid = el._parentIdx;
  while (pid !== undefined && pid !== null && pid >= 0) {
    const p = nodesByIdx.get(pid);
    if (!p) break;
    if (p.tagName === "FORM") return p;
    pid = p._parentIdx;
  }
  return null;
}

function runInputEvents(inputsDict) {
  const touchedForms = new Set();
  for (const [k, v] of Object.entries(inputsDict || {})) {
    const els = findMatchingInputElements(k);
    for (const el of els) {
      el.value = String(v);
      el.dispatchEvent({ type: "input", target: el });
      el.dispatchEvent({ type: "change", target: el });
      const pf = findParentForm(el);
      if (pf) touchedForms.add(pf);
    }
  }
  const allForms = touchedForms.size > 0 ? Array.from(touchedForms) : documentObj.querySelectorAll("form");
  for (const fm of allForms) {
    const firstInput = fm.querySelector("input, select") || fm;
    fm.dispatchEvent({ type: "input", target: firstInput });
    fm.dispatchEvent({ type: "change", target: firstInput });
    fm.dispatchEvent({ type: "submit", target: fm, preventDefault() {} });
  }
  if (typeof windowObj.__complianceSyncWorkspaceOutputs === "function") {
    windowObj.__complianceSyncWorkspaceOutputs();
  }
}

function findFallbackOutputText() {
  if (payload.primary_metric_id) {
    const pm = documentObj.getElementById(payload.primary_metric_id);
    if (pm) return pm.textContent;
  }
  const outNodes = documentObj.querySelectorAll(".output-value");
  for (const n of outNodes) {
    if (!n.classList.contains("overlay-preset-readout")) return n.textContent;
  }
  const fallback = documentObj.querySelector("[data-out], output");
  if (fallback) return fallback.textContent;
  for (const n of allNodes) {
    if (/^(?:val|metric|res|sec179-res|sec1031-res|tey-res|kpi)-/i.test(n.id)) {
      return n.textContent;
    }
  }
  return "";
}

try {
  for (const code of payload.scripts || []) {
    vm.runInThisContext(String(code || ""), { timeout: 2000 });
  }
  for (const fn of domContentLoadedListeners) {
    fn.call(documentObj, { type: "DOMContentLoaded", target: documentObj });
  }
  const baselineText = findFallbackOutputText();

  const vectorResults = [];
  for (const vec of payload.vectors || []) {
    runInputEvents(vec.inputs || {});
    const outs = findAllOutputTexts();
    vectorResults.push({
      name: vec.name,
      text: findFallbackOutputText(),
      primary_text: outs.primary,
      output_value_text: outs.output_value
    });
  }

  process.stdout.write(JSON.stringify({
    ok: true,
    baseline_text: baselineText,
    vectors: vectorResults
  }));
} catch (err) {
  process.stdout.write(JSON.stringify({
    ok: false,
    error: (err && err.name ? err.name + ": " : "") + (err && err.message ? err.message : String(err))
  }));
}
"""


def _resolve_node_binary(preferred: Optional[str] = None) -> Optional[str]:
    if preferred and Path(preferred).is_file():
        return preferred
    found = shutil.which("node")
    if found:
        return found
    return None


def _match_formula_specs_for_slug(
    slug: str,
    formulas: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not slug:
        return []
    matched: List[Dict[str, Any]] = []
    for spec in formulas:
        forb = spec.get("forbidden_slug_patterns") or []
        if any(re.search(str(fp), slug, re.IGNORECASE) for fp in forb if str(fp).strip()):
            continue
        allowed = spec.get("allowed_slug_patterns") or []
        if allowed and any(re.search(str(ap), slug, re.IGNORECASE) for ap in allowed if str(ap).strip()):
            matched.append(spec)
    return matched


def _normalize_formula_text(f: str) -> str:
    return re.sub(r"\s+", "", str(f or "")).lower()


def _check_topic_formula_and_widget_binding(
    slug: str,
    manifest_data: Dict[str, Any],
    rendered_widget_ids: Set[str],
    pack_dict: Dict[str, Any],
    file_path: str,
) -> Tuple[List[TruthViolation], Optional[Dict[str, Any]]]:
    violations: List[TruthViolation] = []
    formulas = _normalize_formulas(pack_dict)
    if not formulas:
        return violations, None

    matched_for_slug = _match_formula_specs_for_slug(slug, formulas)
    primary_spec: Optional[Dict[str, Any]] = matched_for_slug[0] if matched_for_slug else None

    m_formula = str(manifest_data.get("formula") or "").strip()
    m_formula_id = str(manifest_data.get("formula_id") or manifest_data.get("model_id") or "").strip()

    # 1. Check whether manifest's formula or formula_id belongs to a spec that forbids this slug
    for spec in formulas:
        spec_id = str(spec.get("id") or spec.get("formula_id") or "").strip()
        spec_expr = str(spec.get("formula") or spec.get("expression") or "").strip()
        spec_matches_manifest = (
            (m_formula_id and spec_id and m_formula_id.lower() == spec_id.lower())
            or (m_formula and spec_expr and _normalize_formula_text(m_formula) == _normalize_formula_text(spec_expr))
        )
        if not spec_matches_manifest:
            continue

        if slug:
            for fp in (spec.get("forbidden_slug_patterns") or []):
                rx, err = _compile_regex_safe(str(fp), re.IGNORECASE)
                if err:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=file_path,
                            code="GATE_RUNTIME_ERROR",
                            message=f"Invalid FormulaSpec forbidden_slug_patterns regex {fp!r}: {err}",
                            excerpt=spec_id,
                        )
                    )
                    continue
                if rx and rx.search(slug):
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="TOPIC_FORMULA_MISMATCH",
                            message=f"Formula '{spec_id}' is forbidden for topic slug '{slug}' (matched {fp!r})",
                            excerpt=m_formula[:120],
                        )
                    )
                    break

            allowed = spec.get("allowed_slug_patterns") or []
            if allowed and not any(re.search(str(ap), slug, re.IGNORECASE) for ap in allowed):
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="TOPIC_FORMULA_MISMATCH",
                        message=f"Formula '{spec_id}' does not match allowed_slug_patterns for topic slug '{slug}'",
                        excerpt=m_formula[:120],
                    )
                )

    # 2. If slug matched a FormulaSpec, check forbidden_widget_ids and foreign widget IDs
    def _spec_widget_ids(sp_obj: Dict[str, Any]) -> Set[str]:
        wset: Set[str] = set()
        if sp_obj.get("primary_metric_id"):
            wset.add(str(sp_obj["primary_metric_id"]).lower())
        for wlist in ("allowed_widget_ids", "widget_ids"):
            for w in (sp_obj.get(wlist) or []):
                wset.add(str(w).lower())
        for sel in (sp_obj.get("output_selectors") or []):
            sel_s = str(sel).strip()
            if sel_s.startswith("#") and len(sel_s) > 1:
                wset.add(sel_s[1:].lower())
        return wset

    allowed_widgets_for_slug: Set[str] = set()
    for sp in matched_for_slug:
        allowed_widgets_for_slug.update(_spec_widget_ids(sp))

        for fw in (sp.get("forbidden_widget_ids") or []):
            if str(fw).lower() in {k.lower() for k in rendered_widget_ids}:
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="TOPIC_FORMULA_MISMATCH",
                        message=f"Forbidden SSR widget '#{fw}' rendered on topic slug '{slug}' (formula '{sp.get('id')}')",
                        excerpt=f"#{fw}",
                    )
                )

    # 3. Any widget ID declared exclusively on OTHER FormulaSpecs must not bleed onto this slug
    if slug:
        rendered_low = {k.lower(): k for k in rendered_widget_ids}
        for spec in formulas:
            if spec in matched_for_slug:
                continue
            spec_allowed_slugs = spec.get("allowed_slug_patterns") or []
            if not spec_allowed_slugs:
                continue
            spec_widgets = _spec_widget_ids(spec)
            for sw in spec_widgets:
                if sw in rendered_low and sw not in allowed_widgets_for_slug:
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="TOPIC_FORMULA_MISMATCH",
                            message=(
                                f"Misbound SSR widget '#{rendered_low[sw]}' (belongs to formula '{spec.get('id')}') "
                                f"rendered on unrelated topic slug '{slug}'"
                            ),
                            excerpt=f"#{rendered_low[sw]}",
                        )
                    )

    # 4. Required FormulaSpec domain/variable compatibility check (50+ site generic)
    man_inputs = manifest_data.get("inputs")
    if slug and isinstance(man_inputs, dict) and man_inputs:
        _generic_var_tokens = {
            "contract", "amount", "rate", "pct", "percent", "fee", "cost", "count",
            "total", "base", "factor", "years", "year", "months", "month", "days",
            "day", "min", "max", "per", "value", "score", "tier", "credit", "hourly",
            "annual", "monthly", "100", "net", "gross", "est", "estimated",
        }

        def _strip_var_prefix(name: str) -> str:
            return re.sub(
                r"^(?:contract|annual|monthly|base|field|trade|underwriting|multi_year|direct|total)_",
                "",
                str(name or "").strip().lower(),
            )

        def _domain_tokens(keys: Iterable[str]) -> Set[str]:
            toks: Set[str] = set()
            for k in keys:
                for part in str(k or "").strip().lower().split("_"):
                    if part and len(part) >= 2 and part not in _generic_var_tokens:
                        toks.add(part)
            return toks

        man_stripped = {_strip_var_prefix(k) for k in man_inputs.keys()}
        man_tokens = _domain_tokens(man_inputs.keys())
        try:
            pub_val_f: Optional[float] = float(manifest_data.get("published_output"))
        except (TypeError, ValueError):
            pub_val_f = None

        specific_specs: List[Dict[str, Any]] = []
        for sp in matched_for_slug:
            sp_vars = sp.get("variables")
            if not isinstance(sp_vars, dict) or not sp_vars:
                continue
            allowed_pats = [str(ap).strip() for ap in (sp.get("allowed_slug_patterns") or []) if str(ap).strip()]
            if not allowed_pats or all(ap in (".*", "^.*$") for ap in allowed_pats):
                continue
            sp_id = str(sp.get("id") or sp.get("formula_id") or "").lower()
            sp_exp_f = float(sp.get("expected_baseline_output") or 0.0)
            # Do not treat a pure 0-110 scoring spec (e.g. SPRS) as required for a dedicated -cost-/-budget- calculator
            if "score" in sp_id and sp_exp_f <= 1000.0 and re.search(r"-(?:cost|budget|fee)-", slug, re.IGNORECASE):
                continue
            specific_specs.append(sp)

        if specific_specs:
            compatible = False
            incompatible_reasons: List[str] = []
            for sp in specific_specs:
                sp_id = str(sp.get("id") or sp.get("formula_id") or "formula")
                sp_vars = sp["variables"]
                sp_stripped = {_strip_var_prefix(k) for k in sp_vars.keys()}
                sp_tokens = _domain_tokens(sp_vars.keys())
                sp_exp_f = float(sp.get("expected_baseline_output") or 0.0)

                has_var_overlap = bool(man_stripped & sp_stripped) or bool(man_tokens & sp_tokens)
                rate_misattribution = (
                    "penal_sum_pct" in sp_vars
                    and any(rk in man_inputs for rk in ("rate", "rate_pct", "credit_tier_rate_pct", "underwriting_rate_pct"))
                    and "penal_sum_pct" not in man_inputs
                )
                magnitude_mismatch = (
                    sp_exp_f >= 10000.0
                    and pub_val_f is not None
                    and pub_val_f < 1000.0
                    and not has_var_overlap
                )

                if has_var_overlap and not rate_misattribution and not magnitude_mismatch:
                    compatible = True
                    break
                incompatible_reasons.append(
                    f"spec '{sp_id}' expects variables {sorted(sp_vars.keys())} (baseline={sp_exp_f}), "
                    f"got {sorted(man_inputs.keys())} (published_output={pub_val_f})"
                )

            if not compatible:
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="TOPIC_FORMULA_MISMATCH",
                        message=(
                            f"Manifest inputs/formula incompatible with required TruthPack FormulaSpec(s) for "
                            f"topic slug '{slug}': {'; '.join(incompatible_reasons)}"
                        ),
                        excerpt=m_formula[:120],
                    )
                )

    return violations, primary_spec


def _find_bound_input_keys(elements: Sequence[Dict[str, Any]], inputs: Dict[str, Any]) -> Set[str]:
    """Returns manifest input keys that correspond to an actual <input> or <select> in DOM."""
    def _nk(s: str) -> str:
        return re.sub(r"[\s-]+", "_", str(s or "").strip().lower())

    bound: Set[str] = set()
    form_controls = [el for el in elements if el.get("tag") in ("input", "select")]
    if not form_controls or not isinstance(inputs, dict):
        return bound

    for k in inputs.keys():
        k_str = str(k)
        nk = _nk(k_str)
        for el in form_controls:
            raw_id = str(el.get("id") or "")
            raw_name = str(el.get("name") or "")
            n_name = _nk(raw_name)
            n_id_full = _nk(raw_id)
            n_id = re.sub(r"^(?:calc_input_|input_|range_|inp_|calc_|gh_|lb_|px_|ph_)", "", n_id_full)
            if (
                raw_id == k_str
                or raw_name == k_str
                or n_name == nk
                or n_id_full == nk
                or n_id == nk
                or (nk and (n_id_full.endswith("_" + nk) or raw_id.lower().endswith("-" + k_str.lower())))
            ):
                bound.add(k_str)
                break
    return bound


def verify_live_js_math_parity(
    *,
    html_content: str,
    formula: str,
    inputs: Dict[str, Any],
    published_output: Optional[float] = None,
    slug: str = "",
    file_path: str = "<memory>.html",
    dist_dir: Optional[Union[str, Path]] = None,
    formula_spec: Optional[Dict[str, Any]] = None,
    node_binary: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> List[TruthViolation]:
    """
    Executes the page's actual inline/external calculator JS inside Node.js using a
    lightweight deterministic DOM shim and verifies baseline + perturbed/test-vector
    outputs against Python AST evaluation (`safe_eval_formula`).
    """
    violations: List[TruthViolation] = []
    node_bin = _resolve_node_binary(node_binary)
    if node_bin is None:
        violations.append(
            TruthViolation(
                gate="GATE_RUNTIME_ERROR",
                severity="ERROR",
                file_path=file_path,
                code="GATE_RUNTIME_ERROR",
                message="Node.js binary not found; cannot execute live JS parity check (fail-closed)",
                excerpt="node",
            )
        )
        return violations

    dom = _parse_html_dom(html_content)
    scripts_to_run: List[str] = []
    dist_resolved = Path(dist_dir).resolve() if dist_dir is not None else None

    for sc in dom.executable_scripts:
        src = sc.get("src")
        if src:
            src_s = str(src).strip()
            if src_s.startswith(("http://", "https://", "//")):
                continue
            if dist_resolved is not None:
                rel_src = src_s.lstrip("/")
                cand = (dist_resolved / rel_src).resolve()
                try:
                    cand.relative_to(dist_resolved)
                except ValueError:
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="JS_RUNTIME_ERROR",
                            message=f"External script path escapes dist_dir: {src_s}",
                            excerpt=src_s,
                        )
                    )
                    continue
                if not cand.is_file():
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="JS_RUNTIME_ERROR",
                            message=f"Referenced local script missing in dist_dir: {src_s}",
                            excerpt=src_s,
                        )
                    )
                    continue
                scripts_to_run.append(cand.read_text(encoding="utf-8", errors="replace"))
        if sc.get("code"):
            scripts_to_run.append(str(sc["code"]))

    if not scripts_to_run:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="JS_RUNTIME_ERROR",
                message="Tool page has no executable calculator JavaScript",
                excerpt=slug or file_path,
            )
        )
        return violations

    # Build deterministic test vectors: baseline + spec.test_vectors + perturbed vectors
    vectors: List[Dict[str, Any]] = []
    try:
        base_py = _eval_formula(formula, inputs)
    except Exception as exc:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_FORMULA_MISMATCH",
                message=f"Python oracle failed on baseline inputs: {exc}",
                excerpt=formula[:120],
            )
        )
        return violations

    vectors.append({"name": "baseline", "inputs": dict(inputs), "expected": base_py})

    bound_keys = _find_bound_input_keys(dom.elements, inputs)
    spec_base_vars = (formula_spec or {}).get("variables") or {}
    spec_expr = str((formula_spec or {}).get("expression") or (formula_spec or {}).get("formula") or "").strip()
    spec_vectors = (formula_spec or {}).get("test_vectors") or []
    matched_spec_vectors = 0

    if bound_keys:
        manifest_keys = set(inputs.keys())
        for idx, tv in enumerate(spec_vectors):
            tv_d = _to_plain_dict(tv)
            if isinstance(tv_d, dict):
                raw_tv_in = dict(tv_d.get("inputs") or {})
                tv_exp = tv_d.get("expected") if tv_d.get("expected") is not None else tv_d.get("expected_output")
            elif isinstance(tv_d, (list, tuple)) and len(tv_d) >= 2 and isinstance(tv_d[0], dict):
                raw_tv_in = dict(tv_d[0])
                tv_exp = tv_d[1]
            else:
                continue

            if not raw_tv_in:
                continue

            # Only evaluate test_vector against manifest["formula"] when ALL tv keys exist in manifest["inputs"]
            if set(raw_tv_in.keys()).issubset(manifest_keys):
                tv_in = {**inputs, **raw_tv_in}
                try:
                    py_val = _eval_formula(formula, tv_in)
                    if tv_exp is not None and abs(py_val - float(tv_exp)) > 0.05:
                        violations.append(
                            TruthViolation(
                                gate="GATE_MATH_JS_PARITY",
                                severity="ERROR",
                                file_path=file_path,
                                code="MANIFEST_FORMULA_MISMATCH",
                                message=f"TruthPack test_vector[{idx}] expected ({tv_exp}) disagrees with Python formula ({py_val})",
                                excerpt=str(tv_in)[:120],
                            )
                        )
                    vectors.append({"name": f"spec_vector_{idx}", "inputs": dict(tv_in), "expected": py_val})
                    matched_spec_vectors += 1
                except ZeroDivisionError:
                    continue
                except Exception as exc:
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="JS_PARITY_MISMATCH",
                            message=f"Python oracle failed on spec_vector_{idx}: {exc}",
                            excerpt=str(tv_in)[:120],
                        )
                    )
            elif spec_expr:
                # Variable names differ: self-check test_vector against FormulaSpec.expression instead
                spec_in = {**spec_base_vars, **raw_tv_in}
                try:
                    spec_py = _eval_formula(spec_expr, spec_in)
                    if tv_exp is not None and abs(spec_py - float(tv_exp)) > 0.05:
                        violations.append(
                            TruthViolation(
                                gate="GATE_MATH_JS_PARITY",
                                severity="ERROR",
                                file_path=file_path,
                                code="MANIFEST_FORMULA_MISMATCH",
                                message=f"TruthPack test_vector[{idx}] expected ({tv_exp}) disagrees with spec expression ({spec_py})",
                                excerpt=str(spec_in)[:120],
                            )
                        )
                except ZeroDivisionError:
                    continue
                except Exception as exc:
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="MANIFEST_FORMULA_MISMATCH",
                            message=f"TruthPack spec expression failed on test_vector[{idx}]: {exc}",
                            excerpt=str(spec_in)[:120],
                        )
                    )

        # Deterministic input perturbations on bound keys when no matching spec vectors
        numeric_keys = [
            k for k, v in inputs.items()
            if k in bound_keys and isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if numeric_keys and matched_spec_vectors == 0:
            for label, mult in (("perturbed_half", 0.5), ("perturbed_double", 2.0)):
                p_in = dict(inputs)
                for k in numeric_keys:
                    val_f = float(inputs[k])
                    p_in[k] = round(val_f * mult, 4) if val_f != 0 else 100.0
                try:
                    py_p = _eval_formula(formula, p_in)
                    vectors.append({"name": label, "inputs": p_in, "expected": py_p})
                except ZeroDivisionError:
                    continue
                except Exception:
                    continue

    primary_metric_id = str((formula_spec or {}).get("primary_metric_id") or "").strip()
    node_payload = {
        "slug": slug,
        "primary_metric_id": primary_metric_id,
        "scripts": scripts_to_run,
        "elements": dom.elements,
        "vectors": [{"name": v["name"], "inputs": v["inputs"]} for v in vectors],
    }

    try:
        proc = subprocess.run(
            [node_bin, "-e", _NODE_DOM_SHIM_RUNNER],
            input=json.dumps(node_payload),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="JS_RUNTIME_ERROR",
                message=f"Node.js execution timed out after {timeout_seconds}s",
                excerpt=slug,
            )
        )
        return violations
    except Exception as exc:
        violations.append(
            TruthViolation(
                gate="GATE_RUNTIME_ERROR",
                severity="ERROR",
                file_path=file_path,
                code="GATE_RUNTIME_ERROR",
                message=f"Failed to invoke Node.js for JS parity check: {exc}",
                excerpt=str(exc)[:120],
            )
        )
        return violations

    if proc.returncode != 0:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="JS_RUNTIME_ERROR",
                message=f"Node.js exited with code {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:200]}",
                excerpt=(proc.stderr or proc.stdout).strip()[:120],
            )
        )
        return violations

    try:
        res_data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        violations.append(
            TruthViolation(
                gate="GATE_RUNTIME_ERROR",
                severity="ERROR",
                file_path=file_path,
                code="GATE_RUNTIME_ERROR",
                message=f"Node.js parity runner returned invalid JSON: {exc}",
                excerpt=proc.stdout.strip()[:120],
            )
        )
        return violations

    if not res_data.get("ok"):
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="JS_RUNTIME_ERROR",
                message=f"Live JS execution threw runtime error: {res_data.get('error')}",
                excerpt=str(res_data.get("error") or "")[:120],
            )
        )
        return violations

    vec_out_by_name = {vr["name"]: vr for vr in (res_data.get("vectors") or [])}
    custom_tol = (formula_spec or {}).get("tolerance")

    for vec in vectors:
        vname = vec["name"]
        expected = float(vec["expected"])
        vr = vec_out_by_name.get(vname) or {}
        raw_js_text = vr.get("text", "")
        outputs_to_check = [("primary", raw_js_text)]
        p_txt = vr.get("primary_text", "")
        ov_txt = vr.get("output_value_text", "")
        if p_txt and ov_txt and p_txt != ov_txt:
            outputs_to_check = [("primary_metric", p_txt), ("output_value", ov_txt)]

        for out_label, txt_val in outputs_to_check:
            if not txt_val or "nan" in txt_val.lower() or "infinity" in txt_val.lower():
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="JS_RUNTIME_ERROR",
                        message=f"Live JS produced invalid/empty DOM output ({out_label}) for '{vname}': {txt_val!r}",
                        excerpt=str(txt_val),
                    )
                )
                continue

            js_num = _parse_numeric_display(txt_val)
            if js_num is None:
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="JS_RUNTIME_ERROR",
                        message=f"Live JS produced non-numeric DOM output ({out_label}) for '{vname}': {txt_val!r}",
                        excerpt=str(txt_val),
                    )
                )
                continue

            tol = float(custom_tol) if custom_tol is not None else _numeric_tolerance(expected, txt_val)
            if not _values_match(js_num, expected, tol):
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="JS_PARITY_MISMATCH",
                        message=(
                            f"Live JS DOM output ({out_label}={js_num} from {txt_val!r}) diverges from Python AST oracle "
                            f"({expected}) on '{vname}' inputs={vec['inputs']}"
                        ),
                        excerpt=f"js={js_num} vs py={expected}",
                    )
                )

    return violations


def _check_scenario_tables(
    html_content: str,
    published_output: float,
    formula: str,
    inputs: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []

    # 1. Class-based 5-point linear benchmarks (.scenario-baseline / .scenario-conservative / etc.)
    base_scen_m = re.search(
        r'<strong[^>]*class=["\'][^"\']*\bscenario-baseline\b[^"\']*["\'][^>]*>([^<]+)</strong>',
        html_content,
        re.IGNORECASE,
    )
    if base_scen_m:
        base_val = _parse_numeric_display(base_scen_m.group(1))
        if base_val is None or not _values_match(base_val, published_output, _numeric_tolerance(published_output, base_scen_m.group(1))):
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="SCENARIO_ROW_MISMATCH",
                    message=f".scenario-baseline ({base_scen_m.group(1).strip()}) diverges from published_output ({published_output})",
                    excerpt=base_scen_m.group(0)[:120],
                )
            )
        ref_base = base_val if base_val is not None else published_output
        for cls_name, mult in (
            ("scenario-conservative", 0.8),
            ("scenario-moderate-contraction", 0.9),
            ("scenario-moderate-expansion", 1.1),
            ("scenario-aggressive", 1.2),
        ):
            sm = re.search(
                rf'<strong[^>]*class=["\'][^"\']*\b{re.escape(cls_name)}\b[^"\']*["\'][^>]*>([^<]+)</strong>',
                html_content,
                re.IGNORECASE,
            )
            if sm:
                s_val = _parse_numeric_display(sm.group(1))
                exp_s = ref_base * mult
                tol_s = _numeric_tolerance(exp_s, sm.group(1))
                if s_val is None or not _values_match(s_val, exp_s, max(tol_s, 0.05)):
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="SCENARIO_ROW_MISMATCH",
                            message=f"Sensitivity cell '.{cls_name}' ({sm.group(1).strip()}) diverges from {mult}x baseline ({exp_s:.2f})",
                            excerpt=sm.group(0)[:120],
                        )
                    )

    # 2. Multiplier table rows (0.8x / 0.9x / 1.0x / 1.1x / 1.2x)
    for table_m in re.finditer(r"<table\b[^>]*class=[\"'][^\"']*\bscenario-table\b[^\"']*[\"'][^>]*>([\s\S]*?)</table>", html_content, re.IGNORECASE):
        for row_html in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>", table_m.group(1), re.IGNORECASE):
            cells = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                for c in re.findall(r"<td\b[^>]*>([\s\S]*?)</td>", row_html, re.IGNORECASE)
            ]
            if len(cells) >= 3 and re.match(r"^(0\.8|0\.9|1\.0|1\.1|1\.2)x$", cells[0]):
                mult = float(cells[0][:-1])
                row_val = _parse_numeric_display(cells[2])
                linear_exp = published_output * mult
                tol_r = max(_numeric_tolerance(linear_exp, cells[2]), 0.05)

                ast_matches = False
                if row_val is not None and formula and isinstance(inputs, dict):
                    try:
                        scaled_in = {
                            k: (float(v) * mult if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                            for k, v in inputs.items()
                        }
                        ast_exp = _eval_formula(formula, scaled_in)
                        if _values_match(row_val, ast_exp, max(_numeric_tolerance(ast_exp, cells[2]), 0.05)):
                            ast_matches = True
                    except Exception:
                        pass

                if row_val is None or (not _values_match(row_val, linear_exp, tol_r) and not ast_matches):
                    violations.append(
                        TruthViolation(
                            gate="GATE_MATH_JS_PARITY",
                            severity="ERROR",
                            file_path=file_path,
                            code="SCENARIO_ROW_MISMATCH",
                            message=f"Scenario table row {cells[0]} output ({cells[2]!r}) diverges from {mult}x baseline ({linear_exp:.2f})",
                            excerpt=" | ".join(cells[:4]),
                        )
                    )

    return violations


def _check_math_and_js_parity(
    html_content: str,
    dom: _PageDOMExtractor,
    slug: str,
    pack_dict: Dict[str, Any],
    dist_dir: Optional[Union[str, Path]],
    file_path: str,
    run_js_parity: bool,
    node_binary: Optional[str],
    js_timeout_seconds: float,
    is_tool_page: bool,
) -> Tuple[List[TruthViolation], Optional[Dict[str, Any]]]:
    violations: List[TruthViolation] = []

    if not dom.manifest_blocks:
        if is_tool_page:
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="MANIFEST_MISSING_OR_INVALID",
                    message="Tool page is missing embedded calculation-manifest JSON",
                    excerpt=slug or file_path,
                )
            )
        return violations, None

    raw_manifest = dom.manifest_blocks[0].strip()
    try:
        manifest_data = json.loads(raw_manifest)
    except json.JSONDecodeError as exc:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_MISSING_OR_INVALID",
                message=f"Invalid calculation-manifest JSON: {exc}",
                excerpt=raw_manifest[:120],
            )
        )
        return violations, None

    if not isinstance(manifest_data, dict):
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_MISSING_OR_INVALID",
                message="calculation-manifest JSON must be an object",
                excerpt=raw_manifest[:120],
            )
        )
        return violations, None

    formula = str(manifest_data.get("formula") or "").strip()
    inputs = manifest_data.get("inputs")
    pub_raw = manifest_data.get("published_output")
    if not formula or not isinstance(inputs, dict) or pub_raw is None:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_MISSING_OR_INVALID",
                message="calculation-manifest missing required 'formula', 'inputs', or 'published_output'",
                excerpt=raw_manifest[:120],
            )
        )
        return violations, manifest_data

    try:
        published_output = float(pub_raw)
    except (TypeError, ValueError):
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_MISSING_OR_INVALID",
                message=f"calculation-manifest published_output is non-numeric: {pub_raw!r}",
                excerpt=str(pub_raw),
            )
        )
        return violations, manifest_data

    # Tautological formula checks
    try:
        from pseofactory.audit import detect_tautological_or_fabricated_manifest_issues
        for ti in detect_tautological_or_fabricated_manifest_issues(formula, inputs, published_output):
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="MANIFEST_FORMULA_MISMATCH",
                    message=ti,
                    excerpt=formula[:120],
                )
            )
    except Exception as exc:
        violations.append(
            TruthViolation(
                gate="GATE_RUNTIME_ERROR",
                severity="ERROR",
                file_path=file_path,
                code="GATE_RUNTIME_ERROR",
                message=f"Tautological formula check failed: {exc}",
                excerpt=formula[:120],
            )
        )

    # Python AST evaluation of manifest formula vs published_output
    try:
        py_eval = _eval_formula(formula, inputs)
        tol = _numeric_tolerance(published_output)
        if not _values_match(py_eval, published_output, tol):
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="MANIFEST_FORMULA_MISMATCH",
                    message=(
                        f"Manifest formula evaluation ({py_eval}) diverges from published_output ({published_output})"
                    ),
                    excerpt=f"formula={formula[:80]}",
                )
            )
    except Exception as exc:
        violations.append(
            TruthViolation(
                gate="GATE_MATH_JS_PARITY",
                severity="ERROR",
                file_path=file_path,
                code="MANIFEST_FORMULA_MISMATCH",
                message=f"Manifest formula evaluation failed: {exc}",
                excerpt=formula[:120],
            )
        )

    # Collect rendered SSR metrics from parsed DOM
    rendered_metrics: Dict[str, float] = {}
    rendered_widget_ids: Set[str] = set()
    output_value_nodes: List[Dict[str, Any]] = []
    variant_baseline_text = ""

    for el in dom.elements:
        el_id = el["id"]
        el_cls = el["class_list"]
        el_txt = el["text"]
        if "output-value" in el_cls and "overlay-preset-readout" not in el_cls:
            output_value_nodes.append(el)
        if el_id == "variant-baseline":
            variant_baseline_text = el_txt
        if el_id and re.match(r"^(?:res|val|sec179-res|sec1031-res|tey-res|metric|kpi)-[a-z0-9_-]+$", el_id, re.IGNORECASE):
            rendered_widget_ids.add(el_id)
            num = _parse_numeric_display(el_txt)
            if num is not None:
                rendered_metrics[el_id] = num

    # Topic-formula & widget binding (ZERO hardcoded exemptions)
    bind_violations, matched_spec = _check_topic_formula_and_widget_binding(
        slug=slug,
        manifest_data=manifest_data,
        rendered_widget_ids=rendered_widget_ids,
        pack_dict=pack_dict,
        file_path=file_path,
    )
    violations.extend(bind_violations)

    # SSR .output-value parity
    for ov_el in output_value_nodes:
        ov_txt = ov_el["text"]
        ov_num = _parse_numeric_display(ov_txt)
        tol = _numeric_tolerance(published_output, ov_txt)
        if ov_num is None or not _values_match(ov_num, published_output, tol):
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="SSR_METRIC_MISMATCH",
                    message=f"SSR .output-value ({ov_txt!r}) diverges from manifest published_output ({published_output})",
                    excerpt=ov_txt[:120],
                )
            )

    # #variant-baseline parity (only when short compact numeric/currency/percent card, not a prose scenario card)
    if variant_baseline_text:
        vt = variant_baseline_text.strip()
        if len(vt) <= 32 and re.fullmatch(
            r"[+-]?\$?\s*\d[\d,]*(?:\.\d+)?(?:\s*%|\s*pts|\s*/\s*(?:mo|yr))?",
            vt,
            re.IGNORECASE,
        ):
            vb_num = _parse_numeric_display(vt)
            if vb_num is not None and not _values_match(vb_num, published_output, _numeric_tolerance(published_output, vt)):
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="SSR_METRIC_MISMATCH",
                        message=f"SSR #variant-baseline ({vt!r}) diverges from published_output ({published_output})",
                        excerpt=vt[:120],
                    )
                )

    # Primary SSR metric card parity (ZERO len>=4 or hardcoded 19181 exemptions)
    primary_metric_id = str((matched_spec or {}).get("primary_metric_id") or "").strip()
    if primary_metric_id:
        if primary_metric_id not in rendered_metrics:
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="SSR_METRIC_MISMATCH",
                    message=f"Required primary SSR metric '#{primary_metric_id}' not found or non-numeric on page",
                    excerpt=f"#{primary_metric_id}",
                )
            )
        else:
            pm_val = rendered_metrics[primary_metric_id]
            if not _values_match(pm_val, published_output, _numeric_tolerance(published_output)):
                violations.append(
                    TruthViolation(
                        gate="GATE_MATH_JS_PARITY",
                        severity="ERROR",
                        file_path=file_path,
                        code="SSR_METRIC_MISMATCH",
                        message=(
                            f"Primary SSR metric '#{primary_metric_id}' ({pm_val}) diverges from "
                            f"manifest published_output ({published_output})"
                        ),
                        excerpt=f"#{primary_metric_id}={pm_val}",
                    )
                )
    elif rendered_metrics:
        # When no explicit primary_metric_id is given, every rendered metric on a 1-metric page
        # must match, and on multi-metric pages at least one primary metric must match published_output.
        tol_m = _numeric_tolerance(published_output)
        any_match = any(
            _values_match(mv, published_output, tol_m)
            or (0 < abs(published_output) < 1.0 and _values_match(mv, published_output * 100.0, 0.05))
            for mv in rendered_metrics.values()
        )
        if not any_match:
            sample = ", ".join(f"#{k}={v}" for k, v in list(rendered_metrics.items())[:4])
            violations.append(
                TruthViolation(
                    gate="GATE_MATH_JS_PARITY",
                    severity="ERROR",
                    file_path=file_path,
                    code="SSR_METRIC_MISMATCH",
                    message=f"Rendered SSR metric(s) ({sample}) diverge from manifest published_output ({published_output})",
                    excerpt=sample,
                )
            )

    # Scenario / sensitivity tables
    violations.extend(_check_scenario_tables(html_content, published_output, formula, inputs, file_path))

    # Executable live JS parity in Node.js
    if run_js_parity:
        violations.extend(
            verify_live_js_math_parity(
                html_content=html_content,
                formula=formula,
                inputs=inputs,
                published_output=published_output,
                slug=slug,
                file_path=file_path,
                dist_dir=dist_dir,
                formula_spec=matched_spec,
                node_binary=node_binary,
                timeout_seconds=js_timeout_seconds,
            )
        )

    return violations, manifest_data


# ---------------------------------------------------------------------------
# Gate 7: JSON-LD, llms.txt / llms-full.txt, & Sidecar Manifests
# ---------------------------------------------------------------------------

def _collect_jsonld_nodes(obj: Any, out: List[Dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if "@type" in obj:
            out.append(obj)
        if isinstance(obj.get("@graph"), list):
            for item in obj["@graph"]:
                _collect_jsonld_nodes(item, out)
        for k, v in obj.items():
            if k != "@graph" and isinstance(v, (dict, list)):
                _collect_jsonld_nodes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_jsonld_nodes(item, out)


def _collect_top_level_jsonld_nodes(obj: Any) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        if isinstance(obj.get("@graph"), list):
            for item in obj["@graph"]:
                if isinstance(item, dict):
                    nodes.append(item)
        else:
            nodes.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                nodes.append(item)
    return nodes


def _extract_offer_prices(node: Any, prices: List[Tuple[float, str]]) -> None:
    if isinstance(node, dict):
        ntype = node.get("@type")
        type_list = [str(t).lower() for t in (ntype if isinstance(ntype, list) else [ntype] if ntype else [])]
        is_offer = any(t in ("offer", "aggregateoffer") for t in type_list) or "pricecurrency" in {k.lower() for k in node.keys()}
        if is_offer:
            for pk in ("price", "lowPrice", "highPrice"):
                if pk in node and node[pk] is not None:
                    try:
                        prices.append((round(float(str(node[pk]).replace("$", "").replace(",", "").strip()), 2), f"{pk}={node[pk]}"))
                    except (TypeError, ValueError):
                        prices.append((float("nan"), f"{pk}={node[pk]}"))
        for v in node.values():
            if isinstance(v, (dict, list)):
                _extract_offer_prices(v, prices)
    elif isinstance(node, list):
        for item in node:
            _extract_offer_prices(item, prices)


def _is_official_primary_source_href(href: str) -> bool:
    """Returns True when href points to an official .gov, .mil, state .us legislature, eur-lex.europa.eu, or pcisecuritystandards.org URL."""
    raw = str(href or "").strip()
    if not raw.startswith(("http://", "https://")):
        return False
    try:
        host = (urllib.parse.urlparse(raw).hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    if host.endswith(".gov") or host.endswith(".mil"):
        return True
    if host == "leg.state.fl.us" or re.search(r"(?:^|\.)state\.[a-z]{2}\.us$", host):
        return True
    if host == "eur-lex.europa.eu" or host.endswith(".eur-lex.europa.eu"):
        return True
    if host == "pcisecuritystandards.org" or host.endswith(".pcisecuritystandards.org"):
        return True
    if host == "fred.stlouisfed.org" or host.endswith(".fred.stlouisfed.org"):
        return True
    return False


def _check_enacted_law_primary_source_links(
    dom: _PageDOMExtractor,
    pack_dict: Dict[str, Any],
    file_path: str,
    slug: str,
    is_tool_page: bool,
) -> List[TruthViolation]:
    """Fail-closed check: enacted-law calculator pages must include >= 1 outbound official primary-source link."""
    if not is_tool_page:
        return []
    enacted_applicable = [
        entry
        for _k, entry in _normalize_entries(pack_dict)
        if str(entry.get("claim_class") or "").strip().lower() == "enacted_law"
        and _entry_applies_to_file(entry, file_path, slug=slug)
    ]
    if not enacted_applicable:
        return []
    has_official_link = any(
        _is_official_primary_source_href(el.get("attrs", {}).get("href", ""))
        for el in dom.elements
        if el.get("tag") == "a"
    )
    if has_official_link:
        return []
    return [
        TruthViolation(
            gate="GATE_PROVENANCE",
            severity="ERROR",
            file_path=file_path,
            code="MISSING_PRIMARY_SOURCE_LINK",
            message=(
                f"Enacted-law calculator page '{slug or file_path}' has 0 outbound official "
                ".gov / eur-lex.europa.eu / pcisecuritystandards.org primary-source links"
            ),
            excerpt=slug or file_path,
        )
    ]


def _check_jsonld(
    dom: _PageDOMExtractor,
    pack_dict: Dict[str, Any],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []
    allowed_prices = _normalize_pricing_tiers(pack_dict)
    top_app_nodes: List[Tuple[str, str]] = []

    for idx, raw_block in enumerate(dom.jsonld_blocks):
        stripped = raw_block.strip()
        if not stripped:
            violations.append(
                TruthViolation(
                    gate="GATE_SURFACES",
                    severity="ERROR",
                    file_path=file_path,
                    code="JSONLD_INVALID",
                    message=f"Empty JSON-LD <script> block at index {idx}",
                    excerpt="",
                )
            )
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            violations.append(
                TruthViolation(
                    gate="GATE_SURFACES",
                    severity="ERROR",
                    file_path=file_path,
                    code="JSONLD_INVALID",
                    message=f"Malformed JSON-LD at block {idx}: {exc}",
                    excerpt=stripped[:120],
                )
            )
            continue

        for tnode in _collect_top_level_jsonld_nodes(parsed):
            ntype = tnode.get("@type")
            types = ntype if isinstance(ntype, list) else ([ntype] if ntype else [])
            for t in types:
                if str(t) in ("SoftwareApplication", "WebApplication"):
                    top_app_nodes.append((str(t), str(tnode.get("name") or "")))

        if allowed_prices:
            offer_prices: List[Tuple[float, str]] = []
            _extract_offer_prices(parsed, offer_prices)
            for pval, pctx in offer_prices:
                if math.isnan(pval) or pval not in allowed_prices:
                    violations.append(
                        TruthViolation(
                            gate="GATE_SURFACES",
                            severity="ERROR",
                            file_path=file_path,
                            code="JSONLD_PRICING_MISMATCH",
                            message=f"JSON-LD Offer price ({pctx}) does not match TruthPack pricing_tiers ({sorted(allowed_prices)})",
                            excerpt=pctx,
                        )
                    )

    if len(top_app_nodes) >= 2:
        types_desc = ", ".join(f"{t}({n})" for t, n in top_app_nodes)
        violations.append(
            TruthViolation(
                gate="GATE_SURFACES",
                severity="ERROR",
                file_path=file_path,
                code="JSONLD_DUPLICATE_APP_NODE",
                message=f"Duplicate top-level SoftwareApplication/WebApplication JSON-LD nodes detected: {types_desc}",
                excerpt=types_desc[:120],
            )
        )

    return violations


_RAW_HTML_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|apos|nbsp);|&#\d+;|&#x[0-9a-fA-F]+;")
_DUPLICATE_ADJACENT_WORD_RE = re.compile(r"\b([A-Za-z]{2,})\s+\1\b", re.IGNORECASE)
_QUERY_STUB_RE = re.compile(
    r"\bCalculate\s+(?:How\s+Do\s+You|How\s+To|What\s+Is|Can\s+You|Why\s+Does|When\s+Should|Where\s+To)\b",
    re.IGNORECASE,
)


def _resolve_internal_url_in_dist(url_path: str, dist_dir: Path) -> bool:
    clean = url_path.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean or clean == "/":
        return (dist_dir / "index.html").is_file()
    rel = clean.lstrip("/")
    if not rel:
        return (dist_dir / "index.html").is_file()
    cand_direct = (dist_dir / rel).resolve()
    try:
        cand_direct.relative_to(dist_dir.resolve())
    except ValueError:
        return False
    if cand_direct.is_file():
        return True
    if (cand_direct / "index.html").is_file():
        return True
    if not rel.endswith(".html") and (dist_dir / f"{rel}.html").is_file():
        return True
    return False


def _check_llms_surface(
    content: str,
    pack_dict: Dict[str, Any],
    dist_dir: Optional[Union[str, Path]],
    file_path: str,
) -> List[TruthViolation]:
    violations: List[TruthViolation] = []

    # 1. Raw HTML entities
    ent_m = _RAW_HTML_ENTITY_RE.search(content)
    if ent_m:
        violations.append(
            TruthViolation(
                gate="GATE_SURFACES",
                severity="ERROR",
                file_path=file_path,
                code="LLMS_HTML_ENTITY",
                message=f"Raw HTML entity '{ent_m.group(0)}' detected in llms surface",
                excerpt=_excerpt_at(content, ent_m.start()),
            )
        )

    # 2. Duplicate adjacent words (e.g. 'Calculate Calculate')
    dup_m = _DUPLICATE_ADJACENT_WORD_RE.search(content)
    if dup_m:
        violations.append(
            TruthViolation(
                gate="GATE_SURFACES",
                severity="ERROR",
                file_path=file_path,
                code="LLMS_DUPLICATE_WORD",
                message=f"Duplicate adjacent word '{dup_m.group(0)}' detected in llms surface",
                excerpt=_excerpt_at(content, dup_m.start()),
            )
        )

    # 3. Uncleaned query stubs (e.g. 'Calculate How Do You')
    stub_m = _QUERY_STUB_RE.search(content)
    if stub_m:
        violations.append(
            TruthViolation(
                gate="GATE_SURFACES",
                severity="ERROR",
                file_path=file_path,
                code="LLMS_QUERY_STUB",
                message=f"Uncleaned query stub '{stub_m.group(0)}' detected in llms surface",
                excerpt=_excerpt_at(content, stub_m.start()),
            )
        )

    # 4. Internal URL verification against dist_dir
    if dist_dir is not None:
        dist_p = Path(dist_dir).resolve()
        if dist_p.is_dir():
            domain_tokens = _extract_domain_tokens(str(pack_dict.get("canonical_domain") or ""))
            urls_to_check: List[str] = []

            for dom in domain_tokens:
                url_rx = re.compile(rf"https?://(?:www\.)?{re.escape(dom)}(/[^\s)\]>\"']*)", re.IGNORECASE)
                for um in url_rx.finditer(content):
                    urls_to_check.append(um.group(1))

            for md_m in re.finditer(r"\]\((/[^\s)]+)\)", content):
                urls_to_check.append(md_m.group(1))

            seen_paths: Set[str] = set()
            for upath in urls_to_check:
                norm_u = upath.rstrip(".,;:")
                if norm_u in seen_paths:
                    continue
                seen_paths.add(norm_u)
                if not _resolve_internal_url_in_dist(norm_u, dist_p):
                    violations.append(
                        TruthViolation(
                            gate="GATE_SURFACES",
                            severity="ERROR",
                            file_path=file_path,
                            code="LLMS_DEAD_LINK",
                            message=f"Dead internal link '{norm_u}' in llms surface does not resolve to an existing file in dist_dir",
                            excerpt=norm_u,
                        )
                    )

    return violations


# ---------------------------------------------------------------------------
# UnifiedTruthGate Orchestrator
# ---------------------------------------------------------------------------

AUDITABLE_SUFFIXES: Tuple[str, ...] = (".html", ".js", ".json", ".txt", ".md", ".xml", ".vtt")


class UnifiedTruthGate:
    """
    Zero-bypass, fail-closed factual truth gate & executable Python-vs-JS math parity engine.
    Designed for 50+ sites dynamically via TruthPack registry.
    """

    def __init__(
        self,
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        node_binary: Optional[str] = None,
        js_timeout_seconds: float = 5.0,
    ) -> None:
        self._default_truth_pack = truth_pack
        self._default_all_packs = (
            _normalize_pack_collection(all_truth_packs) if all_truth_packs is not None else None
        )
        self._node_binary = node_binary
        self._js_timeout_seconds = float(js_timeout_seconds)

    def _resolve_pack_and_registry(
        self,
        property_id: str,
        *,
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        as_of: Optional[Any] = None,
        context_path: str = "<truth_pack>",
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], List[TruthViolation], str]:
        as_of_date = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc).date()

        raw_pack = truth_pack if truth_pack is not None else self._default_truth_pack
        load_err: Optional[Exception] = None
        if raw_pack is None:
            if not str(property_id or "").strip():
                missing_cls, _, _ = _get_truth_pack_errors()
                load_err = missing_cls("Empty property_id")
            else:
                try:
                    raw_pack = _load_pack_by_id(property_id, as_of=as_of_date)
                except Exception as exc:
                    load_err = exc

        pack_dict = _to_plain_dict(raw_pack) if raw_pack is not None else None
        sha256 = _compute_pack_sha256(raw_pack) if raw_pack is not None else ""
        pack_violations = _check_truth_pack_validity(
            pack_dict=pack_dict,
            property_id=str(property_id or ""),
            as_of_date=as_of_date,
            file_path=context_path,
            load_error=load_err,
        )

        if all_truth_packs is not None:
            registry = _normalize_pack_collection(all_truth_packs)
        elif self._default_all_packs is not None:
            registry = dict(self._default_all_packs)
        else:
            registry = _load_all_packs()

        return pack_dict, registry, pack_violations, sha256

    def _audit_html_internal(
        self,
        html_content: str,
        property_id: str,
        pack_dict: Optional[Dict[str, Any]],
        foreign_tokens: Sequence[Tuple[str, str]],
        *,
        file_path: str,
        slug: str,
        dist_dir: Optional[Union[str, Path]],
        run_js_parity: bool,
        is_tool_page: Optional[bool],
        run_semantic_critic: bool = False,
    ) -> List[TruthViolation]:
        violations: List[TruthViolation] = []
        violations.extend(_check_typography(html_content, file_path))

        # Neutralize dashes on working copy so typography defects NEVER silence factual checks
        clean_html = html_content.replace("\u2014", "-").replace("\u2013", "-")

        try:
            dom = _parse_html_dom(clean_html)
        except Exception as exc:
            violations.append(
                TruthViolation(
                    gate="GATE_RUNTIME_ERROR",
                    severity="ERROR",
                    file_path=file_path,
                    code="GATE_RUNTIME_ERROR",
                    message=f"HTML parser crashed on '{file_path}': {exc}",
                    excerpt=str(exc)[:120],
                )
            )
            return violations

        eff_slug = _extract_slug_from_context(file_path, slug=slug, canonical_url=dom.canonical_url)
        fp_norm = str(file_path or "").replace("\\", "/").lower()
        inferred_tool = bool(
            re.search(r"(?:^|/)tools/(?!index\.html$)[a-z0-9_-]+(?:/[a-z0-9_-]+)?/index\.html$", fp_norm)
            or dom.manifest_blocks
            or any(el["tag"] == "form" and "calculator-form" in el["class_list"] for el in dom.elements)
        )
        tool_flag = inferred_tool if is_tool_page is None else bool(is_tool_page)

        if pack_dict is None:
            return violations

        visible_text = dom.visible_text
        raw_no_style = _strip_style_tags(clean_html)
        script_texts = [str(sc.get("code") or "") for sc in dom.executable_scripts if sc.get("code")]

        # Gate 3: Banned claims, superseded values (prose + JS), claim qualifiers
        violations.extend(_check_banned_claims([raw_no_style, visible_text], pack_dict, file_path))
        violations.extend(
            _check_superseded_values(
                raw_no_style,
                script_texts,
                visible_text,
                pack_dict,
                file_path,
                is_js_file=False,
                slug=eff_slug,
            )
        )
        violations.extend(_check_claim_qualifiers(visible_text, pack_dict, file_path))

        # Gate 4: Citations
        cit_sources = [visible_text] + list(dom.jsonld_blocks)
        violations.extend(_check_citations(cit_sources, eff_slug, pack_dict, file_path))

        # Gate 5: Disclosures & Cross-Tenant Isolation
        violations.extend(_check_disclosures(visible_text, "html", eff_slug, pack_dict, file_path))
        violations.extend(_check_cross_tenant_isolation(clean_html, foreign_tokens, file_path))

        # Gate 6: Math, Topic-Formula Binding, SSR Parity, & Live Node JS Parity
        math_violations, manifest_data = _check_math_and_js_parity(
            html_content=clean_html,
            dom=dom,
            slug=eff_slug,
            pack_dict=pack_dict,
            dist_dir=dist_dir,
            file_path=file_path,
            run_js_parity=run_js_parity,
            node_binary=self._node_binary,
            js_timeout_seconds=self._js_timeout_seconds,
            is_tool_page=tool_flag,
        )
        violations.extend(math_violations)

        # Gate 3 (continued): Zero-ungrounded-stat check (uses manifest formula/inputs when present)
        violations.extend(_check_ungrounded_stats(visible_text, pack_dict, manifest_data, file_path, slug=eff_slug))

        # Gate 7: JSON-LD validation & pricing parity + outbound official primary-source provenance
        violations.extend(_check_jsonld(dom, pack_dict, file_path))
        violations.extend(
            _check_enacted_law_primary_source_links(
                dom=dom,
                pack_dict=pack_dict,
                file_path=file_path,
                slug=eff_slug,
                is_tool_page=tool_flag,
            )
        )

        # Sidecar manifest parity check if this is tools/<slug>/index.html inside dist_dir
        if dist_dir is not None and eff_slug and "/" not in eff_slug:
            sidecar_p = Path(dist_dir).resolve() / "manifests" / f"{eff_slug}.json"
            if sidecar_p.is_file() and manifest_data is not None:
                try:
                    sidecar_data = json.loads(sidecar_p.read_text(encoding="utf-8"))
                    if (
                        sidecar_data.get("formula") != manifest_data.get("formula")
                        or sidecar_data.get("published_output") != manifest_data.get("published_output")
                    ):
                        violations.append(
                            TruthViolation(
                                gate="GATE_SURFACES",
                                severity="ERROR",
                                file_path=file_path,
                                code="SIDECAR_MANIFEST_DIVERGENCE",
                                message=f"Sidecar manifest '{sidecar_p.name}' diverges from embedded calculation-manifest",
                                excerpt=sidecar_p.name,
                            )
                        )
                except Exception as exc:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=str(sidecar_p),
                            code="GATE_RUNTIME_ERROR",
                            message=f"Failed parsing sidecar manifest '{sidecar_p.name}': {exc}",
                            excerpt=sidecar_p.name,
                        )
                    )

        # Optional semantic critic
        if run_semantic_critic:
            try:
                from pseofactory.truth_intake import run_semantic_claim_critic
                critic_rep = run_semantic_claim_critic(
                    property_id=property_id,
                    page_slug=eff_slug or Path(file_path).stem,
                    page_text=visible_text,
                    truth_pack_dict=pack_dict,
                    enabled=True,
                    fail_closed_on_error=True,
                )
                if critic_rep.status == "VIOLATIONS_FOUND":
                    for sv in critic_rep.verified_violations:
                        violations.append(
                            TruthViolation(
                                gate="GATE_PROVENANCE",
                                severity="ERROR",
                                file_path=file_path,
                                code="SEMANTIC_CONTRADICTION",
                                message=f"[{sv.rule_id}] {sv.explanation}",
                                excerpt=sv.offending_excerpt,
                            )
                        )
                elif critic_rep.status == "FREEZE_CRITIC_UNAVAILABLE":
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=file_path,
                            code="GATE_RUNTIME_ERROR",
                            message=f"Semantic critic failed closed: {'; '.join(critic_rep.reasons)}",
                            excerpt=critic_rep.status,
                        )
                    )
            except Exception as exc:
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=file_path,
                        code="GATE_RUNTIME_ERROR",
                        message=f"Semantic critic raised unexpected error: {exc}",
                        excerpt=str(exc)[:120],
                    )
                )

        return violations

    def _audit_non_html_internal(
        self,
        content: str,
        file_path: str,
        pack_dict: Optional[Dict[str, Any]],
        foreign_tokens: Sequence[Tuple[str, str]],
        dist_dir: Optional[Union[str, Path]],
    ) -> List[TruthViolation]:
        violations: List[TruthViolation] = []
        violations.extend(_check_typography(content, file_path))

        if pack_dict is None:
            return violations

        clean_content = content.replace("\u2014", "-").replace("\u2013", "-")
        p = Path(file_path)
        fname = p.name.lower()
        suffix = p.suffix.lower()
        fp_norm = str(file_path).replace("\\", "/").lower()
        is_js = suffix == ".js"

        if fname == "llms-full.txt":
            surface_kind = "llms_full"
        elif fname == "llms.txt":
            surface_kind = "llms"
        elif fname in ("catalog.json", "media-kit.json", "_routes.json"):
            surface_kind = "catalog"
        elif fname in ("robots.txt", "_headers") or re.fullmatch(r"[0-9a-f]{32}\.txt", fname):
            surface_kind = "infra"
        elif fname.endswith(".xml"):
            surface_kind = "feed"
        elif "/manifests/" in fp_norm:
            surface_kind = "manifest"
        elif "/syndication/" in fp_norm:
            surface_kind = "syndication_prose" if suffix in (".md", ".txt", ".html") else "syndication_meta"
        elif suffix == ".vtt":
            surface_kind = "vtt"
        elif is_js:
            surface_kind = "js"
        else:
            surface_kind = "non_html"

        # If this is a JSON manifest inside manifests/, validate JSON & formula evaluation fail-closed
        manifest_data: Optional[Dict[str, Any]] = None
        if suffix == ".json":
            try:
                parsed_json = json.loads(clean_content)
                if surface_kind == "manifest" and isinstance(parsed_json, dict):
                    manifest_data = parsed_json
                    f_str = str(parsed_json.get("formula") or "").strip()
                    f_in = parsed_json.get("inputs")
                    f_out = parsed_json.get("published_output")
                    if f_str and isinstance(f_in, dict) and f_out is not None:
                        try:
                            py_eval = _eval_formula(f_str, f_in)
                            pub_f = float(f_out)
                            if not _values_match(py_eval, pub_f, _numeric_tolerance(pub_f)):
                                violations.append(
                                    TruthViolation(
                                        gate="GATE_MATH_JS_PARITY",
                                        severity="ERROR",
                                        file_path=file_path,
                                        code="MANIFEST_FORMULA_MISMATCH",
                                        message=f"Sidecar manifest formula ({py_eval}) diverges from published_output ({pub_f})",
                                        excerpt=f_str[:120],
                                    )
                                )
                        except Exception as exc:
                            violations.append(
                                TruthViolation(
                                    gate="GATE_MATH_JS_PARITY",
                                    severity="ERROR",
                                    file_path=file_path,
                                    code="MANIFEST_FORMULA_MISMATCH",
                                    message=f"Sidecar manifest formula evaluation failed: {exc}",
                                    excerpt=f_str[:120],
                                )
                            )
            except json.JSONDecodeError as exc:
                violations.append(
                    TruthViolation(
                        gate="GATE_SURFACES",
                        severity="ERROR",
                        file_path=file_path,
                        code="JSON_INVALID",
                        message=f"Malformed JSON file '{p.name}': {exc}",
                        excerpt=clean_content[:120],
                    )
                )

        scan_text = _extract_webvtt_spoken_text(clean_content) if surface_kind == "vtt" else clean_content

        if not is_js:
            violations.extend(_check_banned_claims([scan_text], pack_dict, file_path))
            violations.extend(_check_claim_qualifiers(scan_text, pack_dict, file_path))
            violations.extend(_check_ungrounded_stats(scan_text, pack_dict, manifest_data, file_path))
            violations.extend(_check_citations([scan_text], "", pack_dict, file_path))
            violations.extend(_check_disclosures(scan_text, surface_kind, p.stem.lower(), pack_dict, file_path))

        violations.extend(
            _check_superseded_values(
                scan_text,
                [scan_text] if is_js else [],
                "" if is_js else scan_text,
                pack_dict,
                file_path,
                is_js_file=is_js,
            )
        )
        violations.extend(_check_cross_tenant_isolation(scan_text, foreign_tokens, file_path))

        if fname in ("llms.txt", "llms-full.txt"):
            violations.extend(_check_llms_surface(clean_content, pack_dict, dist_dir, file_path))

        return violations

    def audit_html_content(
        self,
        html_content: str,
        property_id: str,
        *,
        file_path: str = "<memory>.html",
        slug: str = "",
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        as_of: Optional[Any] = None,
        run_js_parity: bool = True,
        is_tool_page: Optional[bool] = None,
        run_semantic_critic: bool = False,
    ) -> TruthGateReport:
        t0 = time.monotonic()
        as_of_d = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
        pack_dict, registry, pack_violations, sha256 = self._resolve_pack_and_registry(
            property_id,
            truth_pack=truth_pack,
            all_truth_packs=all_truth_packs,
            as_of=as_of_d,
            context_path=file_path,
        )
        foreign_tokens = _collect_foreign_tokens(pack_dict, registry) if pack_dict is not None else []
        violations = list(pack_violations)

        try:
            violations.extend(
                self._audit_html_internal(
                    html_content=html_content,
                    property_id=property_id,
                    pack_dict=pack_dict,
                    foreign_tokens=foreign_tokens,
                    file_path=file_path,
                    slug=slug,
                    dist_dir=dist_dir,
                    run_js_parity=run_js_parity,
                    is_tool_page=is_tool_page,
                    run_semantic_critic=run_semantic_critic,
                )
            )
        except Exception as exc:
            violations.append(
                TruthViolation(
                    gate="GATE_RUNTIME_ERROR",
                    severity="ERROR",
                    file_path=file_path,
                    code="GATE_RUNTIME_ERROR",
                    message=f"Unhandled error auditing HTML '{file_path}': {type(exc).__name__}: {exc}",
                    excerpt=str(exc)[:120],
                )
            )

        return TruthGateReport(
            property_id=property_id,
            violations=violations,
            files_audited=[file_path],
            truth_pack_sha256=sha256,
            as_of=as_of_d.isoformat() if as_of_d else "",
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    def audit_html_file(
        self,
        file_path: Union[str, Path],
        property_id: str,
        *,
        slug: str = "",
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        as_of: Optional[Any] = None,
        run_js_parity: bool = True,
        is_tool_page: Optional[bool] = None,
        run_semantic_critic: bool = False,
    ) -> TruthGateReport:
        p = Path(file_path)
        t0 = time.monotonic()
        if not p.is_file():
            return TruthGateReport(
                property_id=property_id,
                violations=[
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(p),
                        code="GATE_RUNTIME_ERROR",
                        message=f"HTML file does not exist: {p}",
                        excerpt=str(p),
                    )
                ],
                files_audited=[],
                duration_ms=(time.monotonic() - t0) * 1000.0,
            )
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as exc:
            return TruthGateReport(
                property_id=property_id,
                violations=[
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(p),
                        code="GATE_RUNTIME_ERROR",
                        message=f"Failed reading HTML file '{p}': {exc}",
                        excerpt=str(exc)[:120],
                    )
                ],
                files_audited=[str(p)],
                duration_ms=(time.monotonic() - t0) * 1000.0,
            )
        return self.audit_html_content(
            content,
            property_id=property_id,
            file_path=str(p),
            slug=slug,
            truth_pack=truth_pack,
            all_truth_packs=all_truth_packs,
            dist_dir=dist_dir,
            as_of=as_of,
            run_js_parity=run_js_parity,
            is_tool_page=is_tool_page,
            run_semantic_critic=run_semantic_critic,
        )

    def audit_non_html_file(
        self,
        file_path: Union[str, Path],
        property_id: str,
        *,
        content: Optional[str] = None,
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        as_of: Optional[Any] = None,
    ) -> TruthGateReport:
        t0 = time.monotonic()
        p = Path(file_path)
        as_of_d = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
        pack_dict, registry, pack_violations, sha256 = self._resolve_pack_and_registry(
            property_id,
            truth_pack=truth_pack,
            all_truth_packs=all_truth_packs,
            as_of=as_of_d,
            context_path=str(p),
        )
        foreign_tokens = _collect_foreign_tokens(pack_dict, registry) if pack_dict is not None else []
        violations = list(pack_violations)

        if content is None:
            if not p.is_file():
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(p),
                        code="GATE_RUNTIME_ERROR",
                        message=f"Non-HTML file does not exist: {p}",
                        excerpt=str(p),
                    )
                )
                return TruthGateReport(
                    property_id=property_id,
                    violations=violations,
                    files_audited=[],
                    truth_pack_sha256=sha256,
                    as_of=as_of_d.isoformat() if as_of_d else "",
                    duration_ms=(time.monotonic() - t0) * 1000.0,
                )
            try:
                content = p.read_text(encoding="utf-8")
            except Exception as exc:
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(p),
                        code="GATE_RUNTIME_ERROR",
                        message=f"Failed reading file '{p}': {exc}",
                        excerpt=str(exc)[:120],
                    )
                )
                return TruthGateReport(
                    property_id=property_id,
                    violations=violations,
                    files_audited=[str(p)],
                    truth_pack_sha256=sha256,
                    as_of=as_of_d.isoformat() if as_of_d else "",
                    duration_ms=(time.monotonic() - t0) * 1000.0,
                )

        try:
            violations.extend(
                self._audit_non_html_internal(
                    content=content,
                    file_path=str(p),
                    pack_dict=pack_dict,
                    foreign_tokens=foreign_tokens,
                    dist_dir=dist_dir,
                )
            )
        except Exception as exc:
            violations.append(
                TruthViolation(
                    gate="GATE_RUNTIME_ERROR",
                    severity="ERROR",
                    file_path=str(p),
                    code="GATE_RUNTIME_ERROR",
                    message=f"Unhandled error auditing non-HTML '{p}': {type(exc).__name__}: {exc}",
                    excerpt=str(exc)[:120],
                )
            )

        return TruthGateReport(
            property_id=property_id,
            violations=violations,
            files_audited=[str(p)],
            truth_pack_sha256=sha256,
            as_of=as_of_d.isoformat() if as_of_d else "",
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    def audit_estate(
        self,
        dist_dir: Union[str, Path],
        property_id: str,
        *,
        repo_root: Optional[Union[str, Path]] = None,
        syndication_dir: Optional[Union[str, Path]] = None,
        as_of: Optional[Any] = None,
        run_js_parity: bool = True,
        run_semantic_critic: bool = False,
        truth_pack: Optional[Any] = None,
        all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
    ) -> TruthGateReport:
        t0 = time.monotonic()
        as_of_d = _parse_iso_date(as_of) if as_of is not None else datetime.now(timezone.utc).date()
        dist_p = Path(dist_dir).resolve()
        pack_dict, registry, pack_violations, sha256 = self._resolve_pack_and_registry(
            property_id,
            truth_pack=truth_pack,
            all_truth_packs=all_truth_packs,
            as_of=as_of_d,
            context_path=str(dist_p),
        )
        foreign_tokens = _collect_foreign_tokens(pack_dict, registry) if pack_dict is not None else []
        violations: List[TruthViolation] = list(pack_violations)
        files_audited: List[str] = []

        if not dist_p.is_dir():
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=str(dist_p),
                    code="EMPTY_DIST_DIR",
                    message=f"dist_dir does not exist or is not a directory: {dist_p}",
                    excerpt=str(dist_p),
                )
            )
            return TruthGateReport(
                property_id=property_id,
                violations=violations,
                files_audited=files_audited,
                truth_pack_sha256=sha256,
                as_of=as_of_d.isoformat() if as_of_d else "",
                duration_ms=(time.monotonic() - t0) * 1000.0,
            )

        dist_files = sorted(
            f for f in dist_p.rglob("*")
            if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in AUDITABLE_SUFFIXES
        )
        html_files = [f for f in dist_files if f.suffix.lower() == ".html"]
        if not html_files:
            violations.append(
                TruthViolation(
                    gate="GATE_TRUTH_PACK",
                    severity="ERROR",
                    file_path=str(dist_p),
                    code="EMPTY_DIST_DIR",
                    message=f"dist_dir contains 0 HTML files: {dist_p}",
                    excerpt=str(dist_p),
                )
            )

        for f in dist_files:
            files_audited.append(str(f))
            try:
                content = f.read_text(encoding="utf-8")
            except Exception as exc:
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(f),
                        code="GATE_RUNTIME_ERROR",
                        message=f"Failed reading file '{f}': {exc}",
                        excerpt=str(exc)[:120],
                    )
                )
                continue

            try:
                if f.suffix.lower() == ".html":
                    violations.extend(
                        self._audit_html_internal(
                            html_content=content,
                            property_id=property_id,
                            pack_dict=pack_dict,
                            foreign_tokens=foreign_tokens,
                            file_path=str(f),
                            slug="",
                            dist_dir=dist_p,
                            run_js_parity=run_js_parity,
                            is_tool_page=None,
                            run_semantic_critic=run_semantic_critic,
                        )
                    )
                else:
                    violations.extend(
                        self._audit_non_html_internal(
                            content=content,
                            file_path=str(f),
                            pack_dict=pack_dict,
                            foreign_tokens=foreign_tokens,
                            dist_dir=dist_p,
                        )
                    )
            except Exception as exc:
                violations.append(
                    TruthViolation(
                        gate="GATE_RUNTIME_ERROR",
                        severity="ERROR",
                        file_path=str(f),
                        code="GATE_RUNTIME_ERROR",
                        message=f"Unhandled error auditing '{f}': {type(exc).__name__}: {exc}",
                        excerpt=str(exc)[:120],
                    )
                )

        # Resolve and audit ALL syndication surfaces
        syn_dir: Optional[Path] = None
        if syndication_dir is not None:
            syn_dir = Path(syndication_dir).resolve()
        elif repo_root is not None:
            syn_dir = Path(repo_root).resolve() / "syndication"
        else:
            cand_syn = dist_p.parent / "syndication"
            if cand_syn.is_dir():
                syn_dir = cand_syn

        if syn_dir is not None and syn_dir.is_dir():
            syn_files = sorted(
                f for f in syn_dir.rglob("*")
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in AUDITABLE_SUFFIXES
            )
            for sf in syn_files:
                files_audited.append(str(sf))
                try:
                    scontent = sf.read_text(encoding="utf-8")
                except Exception as exc:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=str(sf),
                            code="GATE_RUNTIME_ERROR",
                            message=f"Failed reading syndication file '{sf}': {exc}",
                            excerpt=str(exc)[:120],
                        )
                    )
                    continue

                try:
                    if sf.suffix.lower() == ".html":
                        violations.extend(
                            self._audit_html_internal(
                                html_content=scontent,
                                property_id=property_id,
                                pack_dict=pack_dict,
                                foreign_tokens=foreign_tokens,
                                file_path=str(sf),
                                slug="",
                                dist_dir=dist_p,
                                run_js_parity=False,
                                is_tool_page=False,
                                run_semantic_critic=False,
                            )
                        )
                    else:
                        violations.extend(
                            self._audit_non_html_internal(
                                content=scontent,
                                file_path=str(sf),
                                pack_dict=pack_dict,
                                foreign_tokens=foreign_tokens,
                                dist_dir=dist_p,
                            )
                        )
                except Exception as exc:
                    violations.append(
                        TruthViolation(
                            gate="GATE_RUNTIME_ERROR",
                            severity="ERROR",
                            file_path=str(sf),
                            code="GATE_RUNTIME_ERROR",
                            message=f"Unhandled error auditing syndication '{sf}': {type(exc).__name__}: {exc}",
                            excerpt=str(exc)[:120],
                        )
                    )

        return TruthGateReport(
            property_id=property_id,
            violations=violations,
            files_audited=files_audited,
            truth_pack_sha256=sha256,
            as_of=as_of_d.isoformat() if as_of_d else "",
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )


def audit_tenant_truth_fail_closed(
    dist_dir: Union[str, Path],
    property_id: str,
    *,
    repo_root: Optional[Union[str, Path]] = None,
    syndication_dir: Optional[Union[str, Path]] = None,
    as_of: Optional[Any] = None,
    run_js_parity: bool = True,
    run_semantic_critic: bool = False,
    truth_pack: Optional[Any] = None,
    all_truth_packs: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
) -> TruthGateReport:
    """Convenience fail-closed estate audit entrypoint."""
    gate = UnifiedTruthGate(truth_pack=truth_pack, all_truth_packs=all_truth_packs)
    return gate.audit_estate(
        dist_dir=dist_dir,
        property_id=property_id,
        repo_root=repo_root,
        syndication_dir=syndication_dir,
        as_of=as_of,
        run_js_parity=run_js_parity,
        run_semantic_critic=run_semantic_critic,
    )
