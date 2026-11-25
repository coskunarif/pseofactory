"""
pseofactory Declarative Site Truth Pack Engine (Wave 1A).

Canonical, schema-validated, fail-closed Truth Pack loader and validator designed
for 50+ sites dynamically via `.pseofactory.json` discovery.

Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.pricing import get_tier_pricing

DEFAULT_TRUTH_PACKS_DIR: Path = Path(__file__).resolve().parent / "truth_packs"
SUPPORTED_SCHEMA_VERSION: str = "2.0"


class ClaimClass(str, Enum):
    """Canonical claim classification for Truth Pack entries."""

    ENACTED_LAW = "enacted_law"
    MARKET_BENCHMARK = "market_benchmark"
    FUTURE_PROJECTION = "future_projection"


VALID_CLAIM_CLASSES: FrozenSet[str] = frozenset(c.value for c in ClaimClass)

OFFICIAL_ENACTED_LAW_DOMAINS: Tuple[str, ...] = (
    ".gov",
    "congress.gov",
    "irs.gov",
    "federalregister.gov",
    "acquisition.gov",
    "ed.gov",
    "studentaid.gov",
    "acq.osd.mil",
    "hhs.gov",
    "bls.gov",
    "census.gov",
    "treasury.gov",
    "dol.gov",
    "sba.gov",
    "sec.gov",
    "ncci.com",
    "aspe.hhs.gov",
)

_SAFE_CALLABLES: Dict[str, Any] = {
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
    "pow": pow,
}

_BINOP_MAP: Dict[type, Any] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}

_JS_BINOP_MAP: Dict[type, str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Mod: "%",
}

_JS_CMPOP_MAP: Dict[type, str] = {
    ast.Eq: "===",
    ast.NotEq: "!==",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}


class TruthPackError(ValueError):
    """Base error for Truth Pack loading, parsing, and validation."""


class TruthPackMissingError(TruthPackError):
    """Raised when no Truth Pack exists for the requested property_id."""


class TruthPackExpiredError(TruthPackError):
    """Raised when a Truth Pack contains expired entries and allow_expired=False."""


class TruthPackValidationError(TruthPackError):
    """Raised when a Truth Pack fails schema, quote hash, formula, or compliance checks."""


def normalize_quote(text: str) -> str:
    """Collapses whitespace runs to single spaces and strips outer whitespace."""
    return " ".join(str(text or "").split())


def compute_quote_sha256(quote: str) -> str:
    """Computes lowercase hex SHA-256 of normalized whitespace verbatim_quote."""
    normalized = normalize_quote(quote)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_official_enacted_law_url(url: str) -> bool:
    """Verifies that a URL uses http(s) and belongs to an approved official domain."""
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return False
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host.endswith(".gov"):
        return True
    for domain in OFFICIAL_ENACTED_LAW_DOMAINS:
        if domain.startswith("."):
            if host.endswith(domain):
                return True
        elif host == domain or host.endswith(f".{domain}"):
            return True
    return False


def _is_valid_http_url(url: str) -> bool:
    """Verifies basic http(s) URL structure with a non-empty hostname."""
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return False
    return parsed.scheme.lower() in ("http", "https") and bool((parsed.hostname or "").strip())


def _parse_iso_date(raw_date: str) -> Optional[date]:
    """Parses strict YYYY-MM-DD date string or returns None."""
    text = str(raw_date or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _eval_ast_node(node: ast.AST, variables: Dict[str, Any]) -> Any:
    """Evaluates a restricted Python AST expression without eval()."""
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str)) or node.value is None:
            return node.value
        raise TruthPackValidationError(f"Unsupported constant type in formula: {type(node.value).__name__}")
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id not in variables:
            raise TruthPackValidationError(f"Undefined formula variable '{node.id}'")
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        val = _eval_ast_node(node.operand, variables)
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.Not):
            return not bool(val)
        raise TruthPackValidationError(f"Unsupported unary operator: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        op_fn = _BINOP_MAP.get(type(node.op))
        if op_fn is None:
            raise TruthPackValidationError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _eval_ast_node(node.left, variables)
        right = _eval_ast_node(node.right, variables)
        return op_fn(left, right)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for val_node in node.values:
                result = _eval_ast_node(val_node, variables)
                if not result:
                    return False
            return bool(result)
        if isinstance(node.op, ast.Or):
            for val_node in node.values:
                result = _eval_ast_node(val_node, variables)
                if result:
                    return True
            return False
        raise TruthPackValidationError(f"Unsupported boolean operator: {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _eval_ast_node(node.left, variables)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval_ast_node(comp, variables)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.In):
                ok = left in right
            elif isinstance(op, ast.NotIn):
                ok = left not in right
            else:
                raise TruthPackValidationError(f"Unsupported comparison operator: {type(op).__name__}")
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        cond = _eval_ast_node(node.test, variables)
        return _eval_ast_node(node.body if cond else node.orelse, variables)
    if isinstance(node, ast.Tuple):
        return tuple(_eval_ast_node(elt, variables) for elt in node.elts)
    if isinstance(node, ast.List):
        return [_eval_ast_node(elt, variables) for elt in node.elts]
    if isinstance(node, ast.Subscript):
        container = _eval_ast_node(node.value, variables)
        if not isinstance(container, (dict, list, tuple)):
            raise TruthPackValidationError("Subscript target must be dict, list, or tuple")
        idx = _eval_ast_node(node.slice, variables)
        return container[idx]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_CALLABLES:
            func_name = getattr(node.func, "id", type(node.func).__name__)
            raise TruthPackValidationError(f"Disallowed function call '{func_name}' in formula")
        if node.keywords:
            if node.func.id != "round" or any(kw.arg != "ndigits" for kw in node.keywords):
                raise TruthPackValidationError(f"Unsupported keyword arguments in call to '{node.func.id}'")
        args = [_eval_ast_node(arg, variables) for arg in node.args]
        kwargs = {kw.arg: _eval_ast_node(kw.value, variables) for kw in node.keywords if kw.arg}
        return _SAFE_CALLABLES[node.func.id](*args, **kwargs)
    raise TruthPackValidationError(f"Disallowed AST node '{type(node).__name__}' in formula")


def safe_eval_formula(expression: str, variables: Dict[str, Any]) -> float:
    """Safely evaluates a mathematical formula expression using a pure Python AST walker."""
    expr = str(expression or "").strip()
    if not expr:
        raise TruthPackValidationError("Formula expression cannot be empty")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise TruthPackValidationError(f"Invalid formula syntax: {exc}") from exc

    try:
        raw_val = _eval_ast_node(tree, dict(variables or {}))
        result = float(raw_val)
    except TruthPackValidationError:
        raise
    except Exception as exc:
        raise TruthPackValidationError(f"Formula evaluation error: {exc}") from exc

    if not math.isfinite(result):
        raise TruthPackValidationError(f"Formula produced non-finite result: {result}")
    return result


def _ast_to_js(node: ast.AST) -> str:
    """Translates a safe formula AST into an equivalent JavaScript expression."""
    if isinstance(node, ast.Expression):
        return _ast_to_js(node.body)
    if isinstance(node, ast.Constant):
        return json.dumps(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp):
        operand = _ast_to_js(node.operand)
        if isinstance(node.op, ast.UAdd):
            return f"(+{operand})"
        if isinstance(node.op, ast.USub):
            return f"(-{operand})"
        if isinstance(node.op, ast.Not):
            return f"(!{operand})"
        raise TruthPackValidationError(f"Unsupported unary op for JS: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        left = _ast_to_js(node.left)
        right = _ast_to_js(node.right)
        if isinstance(node.op, ast.Pow):
            return f"Math.pow({left}, {right})"
        if isinstance(node.op, ast.FloorDiv):
            return f"Math.floor({left} / {right})"
        op_str = _JS_BINOP_MAP.get(type(node.op))
        if op_str is None:
            raise TruthPackValidationError(f"Unsupported binary op for JS: {type(node.op).__name__}")
        return f"({left} {op_str} {right})"
    if isinstance(node, ast.BoolOp):
        joiner = " && " if isinstance(node.op, ast.And) else " || "
        parts = [_ast_to_js(v) for v in node.values]
        return f"({joiner.join(parts)})"
    if isinstance(node, ast.Compare):
        clauses: List[str] = []
        left_js = _ast_to_js(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right_js = _ast_to_js(comp)
            if isinstance(op, ast.In):
                clauses.append(f"({right_js}).includes({left_js})")
            elif isinstance(op, ast.NotIn):
                clauses.append(f"!({right_js}).includes({left_js})")
            else:
                op_str = _JS_CMPOP_MAP.get(type(op))
                if op_str is None:
                    raise TruthPackValidationError(f"Unsupported comparison op for JS: {type(op).__name__}")
                clauses.append(f"{left_js} {op_str} {right_js}")
            left_js = right_js
        return f"({' && '.join(clauses)})" if len(clauses) > 1 else f"({clauses[0]})"
    if isinstance(node, ast.IfExp):
        test_js = _ast_to_js(node.test)
        body_js = _ast_to_js(node.body)
        orelse_js = _ast_to_js(node.orelse)
        return f"({test_js} ? {body_js} : {orelse_js})"
    if isinstance(node, (ast.List, ast.Tuple)):
        return f"[{', '.join(_ast_to_js(e) for e in node.elts)}]"
    if isinstance(node, ast.Subscript):
        return f"{_ast_to_js(node.value)}[{_ast_to_js(node.slice)}]"
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_CALLABLES:
            raise TruthPackValidationError("Disallowed function call in JS derivation")
        args_js = [_ast_to_js(a) for a in node.args]
        fn = node.func.id
        if fn in ("min", "max", "abs", "pow"):
            return f"Math.{fn}({', '.join(args_js)})"
        if fn == "round":
            if len(args_js) == 1:
                return f"Math.round({args_js[0]})"
            if len(args_js) == 2:
                return f"(Math.round(({args_js[0]}) * Math.pow(10, {args_js[1]})) / Math.pow(10, {args_js[1]}))"
        raise TruthPackValidationError(f"Unsupported round signature in JS derivation: {fn}")
    raise TruthPackValidationError(f"Unsupported AST node in JS derivation: {type(node).__name__}")


def derive_js_expression(expression: str) -> str:
    """Derives an equivalent JavaScript expression from a safe Python AST formula."""
    tree = ast.parse(str(expression or "").strip(), mode="eval")
    return _ast_to_js(tree)


@dataclass(frozen=True)
class TruthEntry:
    """Immutable verified statutory, benchmark, or projection fact entry."""

    key: str
    value: Any
    claim_class: str
    unit: str
    effective_year: int
    citation: str
    primary_source_url: str
    publisher: str
    verified_at: str
    expires_at: str
    verbatim_quote: str
    source_quote_sha256: str
    superseded_values: List[Dict[str, Any]] = field(default_factory=list)
    required_qualifier_patterns: List[str] = field(default_factory=list)
    applies_to_slugs: List[str] = field(default_factory=list)
    forbidden_on_slugs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": copy.deepcopy(self.value),
            "claim_class": str(self.claim_class.value if isinstance(self.claim_class, ClaimClass) else self.claim_class),
            "unit": self.unit,
            "effective_year": int(self.effective_year),
            "citation": self.citation,
            "primary_source_url": self.primary_source_url,
            "publisher": self.publisher,
            "verified_at": self.verified_at,
            "expires_at": self.expires_at,
            "verbatim_quote": self.verbatim_quote,
            "source_quote_sha256": self.source_quote_sha256,
            "superseded_values": copy.deepcopy(list(self.superseded_values)),
            "required_qualifier_patterns": list(self.required_qualifier_patterns),
            "applies_to_slugs": list(self.applies_to_slugs),
            "forbidden_on_slugs": list(self.forbidden_on_slugs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TruthEntry":
        qualifiers = data.get("required_qualifier_patterns")
        if qualifiers is None:
            qualifiers = data.get("required_label_patterns")
        raw_class = data.get("claim_class", "")
        if isinstance(raw_class, ClaimClass):
            claim_class_str = raw_class.value
        else:
            claim_class_str = str(raw_class or "").strip()
        return cls(
            key=str(data.get("key") or "").strip(),
            value=copy.deepcopy(data.get("value")),
            claim_class=claim_class_str,
            unit=str(data.get("unit") or "").strip(),
            effective_year=int(data.get("effective_year") or 0),
            citation=str(data.get("citation") or "").strip(),
            primary_source_url=str(data.get("primary_source_url") or "").strip(),
            publisher=str(data.get("publisher") or "").strip(),
            verified_at=str(data.get("verified_at") or "").strip(),
            expires_at=str(data.get("expires_at") or "").strip(),
            verbatim_quote=str(data.get("verbatim_quote") or ""),
            source_quote_sha256=str(data.get("source_quote_sha256") or "").strip().lower(),
            superseded_values=copy.deepcopy(list(data.get("superseded_values") or [])),
            required_qualifier_patterns=[str(p) for p in (qualifiers or [])],
            applies_to_slugs=[str(s) for s in (data.get("applies_to_slugs") or [])],
            forbidden_on_slugs=[str(s) for s in (data.get("forbidden_on_slugs") or [])],
        )


@dataclass(frozen=True)
class FormulaSpec:
    """Immutable deterministic formula specification with baseline and vector tests."""

    formula_id: str
    model_name: str
    expression: str
    js_expression: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    expected_baseline_output: float = 0.0
    tolerance: float = 0.01
    test_vectors: List[Dict[str, Any]] = field(default_factory=list)
    citation_keys: List[str] = field(default_factory=list)
    allowed_slug_patterns: List[str] = field(default_factory=list)
    forbidden_slug_patterns: List[str] = field(default_factory=list)
    output_selectors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not str(self.js_expression or "").strip() and str(self.expression or "").strip():
            try:
                derived = derive_js_expression(self.expression)
                object.__setattr__(self, "js_expression", derived)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formula_id": self.formula_id,
            "model_name": self.model_name,
            "expression": self.expression,
            "js_expression": self.js_expression,
            "variables": copy.deepcopy(dict(self.variables)),
            "expected_baseline_output": float(self.expected_baseline_output),
            "tolerance": float(self.tolerance),
            "test_vectors": copy.deepcopy(list(self.test_vectors)),
            "citation_keys": list(self.citation_keys),
            "allowed_slug_patterns": list(self.allowed_slug_patterns),
            "forbidden_slug_patterns": list(self.forbidden_slug_patterns),
            "output_selectors": list(self.output_selectors),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormulaSpec":
        return cls(
            formula_id=str(data.get("formula_id") or "").strip(),
            model_name=str(data.get("model_name") or "").strip(),
            expression=str(data.get("expression") or "").strip(),
            js_expression=str(data.get("js_expression") or "").strip(),
            variables=copy.deepcopy(dict(data.get("variables") or {})),
            expected_baseline_output=float(data.get("expected_baseline_output") or 0.0),
            tolerance=float(data.get("tolerance") if data.get("tolerance") is not None else 0.01),
            test_vectors=copy.deepcopy(list(data.get("test_vectors") or [])),
            citation_keys=[str(k) for k in (data.get("citation_keys") or [])],
            allowed_slug_patterns=[str(p) for p in (data.get("allowed_slug_patterns") or [])],
            forbidden_slug_patterns=[str(p) for p in (data.get("forbidden_slug_patterns") or [])],
            output_selectors=[str(s) for s in (data.get("output_selectors") or [])],
        )


@dataclass(frozen=True)
class DisclosureRule:
    """Immutable mandatory regulatory disclosure rule."""

    disclosure_id: str
    required_text_patterns: List[str] = field(default_factory=list)
    applies_to_slug_patterns: List[str] = field(default_factory=list)
    canonical_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disclosure_id": self.disclosure_id,
            "required_text_patterns": list(self.required_text_patterns),
            "applies_to_slug_patterns": list(self.applies_to_slug_patterns),
            "canonical_text": self.canonical_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisclosureRule":
        return cls(
            disclosure_id=str(data.get("disclosure_id") or "").strip(),
            required_text_patterns=[str(p) for p in (data.get("required_text_patterns") or [])],
            applies_to_slug_patterns=[str(p) for p in (data.get("applies_to_slug_patterns") or [])],
            canonical_text=str(data.get("canonical_text") or "").strip(),
        )


@dataclass(frozen=True)
class TruthPack:
    """Immutable canonical site Truth Pack."""

    schema_version: str
    property_id: str
    brand_name: str
    canonical_domain: str
    audience_tier: str
    pricing_tiers: Dict[str, Any]
    entries: Dict[str, TruthEntry]
    formulas: Dict[str, FormulaSpec]
    citations_allowlist: Dict[str, Dict[str, Any]]
    disclosures: List[DisclosureRule]
    banned_claims: List[Dict[str, Any]]
    cross_tenant_brand_tokens: List[str]
    allowed_shared_legal_tokens: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "property_id": self.property_id,
            "brand_name": self.brand_name,
            "canonical_domain": self.canonical_domain,
            "audience_tier": self.audience_tier,
            "pricing_tiers": copy.deepcopy(dict(self.pricing_tiers)),
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "formulas": {k: v.to_dict() for k, v in self.formulas.items()},
            "citations_allowlist": copy.deepcopy(dict(self.citations_allowlist)),
            "disclosures": [d.to_dict() for d in self.disclosures],
            "banned_claims": copy.deepcopy(list(self.banned_claims)),
            "cross_tenant_brand_tokens": list(self.cross_tenant_brand_tokens),
            "allowed_shared_legal_tokens": list(self.allowed_shared_legal_tokens),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TruthPack":
        if not isinstance(data, dict):
            raise TruthPackValidationError("TruthPack payload must be a JSON object")

        raw_entries = data.get("entries") or {}
        if not isinstance(raw_entries, dict):
            raise TruthPackValidationError("TruthPack.entries must be an object")
        entries: Dict[str, TruthEntry] = {}
        for k, v in raw_entries.items():
            if not isinstance(v, dict):
                raise TruthPackValidationError(f"Entry '{k}' must be an object")
            item_dict = dict(v)
            if not item_dict.get("key"):
                item_dict["key"] = str(k)
            entries[str(k)] = TruthEntry.from_dict(item_dict)

        raw_formulas = data.get("formulas") or {}
        if not isinstance(raw_formulas, dict):
            raise TruthPackValidationError("TruthPack.formulas must be an object")
        formulas: Dict[str, FormulaSpec] = {}
        for k, v in raw_formulas.items():
            if not isinstance(v, dict):
                raise TruthPackValidationError(f"Formula '{k}' must be an object")
            item_dict = dict(v)
            if not item_dict.get("formula_id"):
                item_dict["formula_id"] = str(k)
            formulas[str(k)] = FormulaSpec.from_dict(item_dict)

        raw_disclosures = data.get("disclosures") or []
        if not isinstance(raw_disclosures, list):
            raise TruthPackValidationError("TruthPack.disclosures must be a list")
        disclosures = [
            DisclosureRule.from_dict(d) if isinstance(d, dict) else DisclosureRule(disclosure_id="")
            for d in raw_disclosures
        ]

        return cls(
            schema_version=str(data.get("schema_version") or "").strip(),
            property_id=str(data.get("property_id") or "").strip().lower(),
            brand_name=str(data.get("brand_name") or "").strip(),
            canonical_domain=str(data.get("canonical_domain") or "").strip(),
            audience_tier=str(data.get("audience_tier") or "").strip().lower(),
            pricing_tiers=copy.deepcopy(dict(data.get("pricing_tiers") or {})),
            entries=entries,
            formulas=formulas,
            citations_allowlist=copy.deepcopy(dict(data.get("citations_allowlist") or {})),
            disclosures=disclosures,
            banned_claims=copy.deepcopy(list(data.get("banned_claims") or [])),
            cross_tenant_brand_tokens=[str(t) for t in (data.get("cross_tenant_brand_tokens") or [])],
            allowed_shared_legal_tokens=[str(t) for t in (data.get("allowed_shared_legal_tokens") or [])],
        )


def _validate_brackets(key: str, value: Any, errors: List[str]) -> None:
    """Validates bracket list structure, rate monotonicity, and contiguous thresholds."""
    if not isinstance(value, list) or not value:
        errors.append(f"Entry '{key}' with unit='brackets' must have a non-empty list of bracket objects")
        return

    prev_rate: Optional[float] = None
    prev_max: Optional[float] = None
    for idx, bracket in enumerate(value):
        if not isinstance(bracket, dict):
            errors.append(f"Entry '{key}' bracket[{idx}] must be an object")
            return
        if "rate" not in bracket or "min" not in bracket or "max" not in bracket:
            errors.append(f"Entry '{key}' bracket[{idx}] must include 'rate', 'min', and 'max'")
            return
        try:
            rate = float(bracket["rate"])
            b_min = float(bracket["min"])
            b_max = None if bracket["max"] is None else float(bracket["max"])
        except (TypeError, ValueError):
            errors.append(f"Entry '{key}' bracket[{idx}] has non-numeric rate/min/max")
            return

        if rate < 0.0 or rate > 100.0:
            errors.append(f"Entry '{key}' bracket[{idx}] rate {rate} out of [0, 100]")
        if prev_rate is not None and rate < prev_rate:
            errors.append(f"Entry '{key}' bracket[{idx}] rate {rate} is lower than prior rate {prev_rate}")
        if b_min < 0.0:
            errors.append(f"Entry '{key}' bracket[{idx}] min {b_min} cannot be negative")
        if idx == 0 and b_min != 0.0:
            errors.append(f"Entry '{key}' bracket[0] min must start at 0, got {b_min}")
        if prev_max is not None and abs(b_min - prev_max) > 1e-6:
            errors.append(f"Entry '{key}' bracket[{idx}] min {b_min} does not match prior max {prev_max}")
        if b_max is not None:
            if b_max <= b_min:
                errors.append(f"Entry '{key}' bracket[{idx}] max {b_max} must exceed min {b_min}")
            if idx == len(value) - 1:
                errors.append(f"Entry '{key}' final bracket[{idx}] must have max=null")
        elif idx != len(value) - 1:
            errors.append(f"Entry '{key}' non-final bracket[{idx}] cannot have max=null")

        prev_rate = rate
        prev_max = b_max


def _validate_regex_list(patterns: List[str], context: str, errors: List[str]) -> None:
    """Compiles regex patterns and appends descriptive errors on invalid syntax."""
    for idx, pat in enumerate(patterns):
        try:
            re.compile(pat)
        except re.error as exc:
            errors.append(f"Invalid regex in {context}[{idx}] ({pat!r}): {exc}")


def validate_truth_pack(
    pack: TruthPack,
    *,
    as_of: Optional[date] = None,
    allow_expired: bool = False,
) -> List[str]:
    """
    Validates a TruthPack against schema, typography, claim-class provenance,
    quote SHA-256, expiry, formula/test-vector execution, bracket monotonicity,
    and pricing tier parity. Returns a list of error strings (empty when valid).
    """
    errors: List[str] = []
    eff_as_of = as_of or date.today()

    serialized = json.dumps(pack.to_dict(), ensure_ascii=False)
    try:
        assert_no_forbidden_dashes(serialized, context=f"truth_pack.{pack.property_id or 'unknown'}")
    except ValueError as exc:
        errors.append(str(exc))

    if pack.schema_version != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version '{pack.schema_version}', expected '{SUPPORTED_SCHEMA_VERSION}'")
    if not pack.property_id:
        errors.append("TruthPack.property_id must be non-empty")
    if not pack.brand_name:
        errors.append("TruthPack.brand_name must be non-empty")
    if not pack.canonical_domain:
        errors.append("TruthPack.canonical_domain must be non-empty")
    if pack.audience_tier not in ("consumer", "business"):
        errors.append(f"Invalid audience_tier '{pack.audience_tier}', must be 'consumer' or 'business'")
    else:
        expected_pricing = get_tier_pricing(pack.audience_tier)
        for req_tier in ("free", "quick", "full", "partner_slot"):
            if req_tier not in pack.pricing_tiers or not isinstance(pack.pricing_tiers[req_tier], dict):
                errors.append(f"TruthPack.pricing_tiers missing required tier '{req_tier}'")
                continue
            tier_obj = pack.pricing_tiers[req_tier]
            try:
                actual_usd = float(tier_obj.get("price_usd"))
            except (TypeError, ValueError):
                errors.append(f"TruthPack.pricing_tiers['{req_tier}'].price_usd must be numeric")
                continue
            expected_usd = 0.0 if req_tier == "free" else float(expected_pricing[req_tier]["price_usd"])
            if abs(actual_usd - expected_usd) > 1e-6:
                errors.append(
                    f"Pricing tier parity mismatch for '{req_tier}': got {actual_usd}, expected {expected_usd}"
                )
            if "price_cents" in tier_obj and tier_obj["price_cents"] is not None:
                try:
                    actual_cents = int(tier_obj["price_cents"])
                except (TypeError, ValueError):
                    errors.append(f"TruthPack.pricing_tiers['{req_tier}'].price_cents must be integer")
                    continue
                expected_cents = 0 if req_tier == "free" else int(expected_pricing[req_tier]["price_cents"])
                if actual_cents != expected_cents:
                    errors.append(
                        f"Pricing cents parity mismatch for '{req_tier}': got {actual_cents}, expected {expected_cents}"
                    )

    for key, entry in pack.entries.items():
        if entry.key != key:
            errors.append(f"Entry key mismatch: dict key '{key}' != entry.key '{entry.key}'")
        if entry.claim_class not in VALID_CLAIM_CLASSES:
            errors.append(f"Entry '{key}' has invalid claim_class '{entry.claim_class}'")

        verified_date = _parse_iso_date(entry.verified_at)
        expires_date = _parse_iso_date(entry.expires_at)
        if verified_date is None:
            errors.append(f"Entry '{key}' has invalid verified_at '{entry.verified_at}' (expected YYYY-MM-DD)")
        if expires_date is None:
            errors.append(f"Entry '{key}' has invalid expires_at '{entry.expires_at}' (expected YYYY-MM-DD)")
        elif not allow_expired and expires_date < eff_as_of:
            errors.append(
                f"EXPIRED: Entry '{key}' expired on {entry.expires_at} (as_of={eff_as_of.isoformat()})"
            )

        if entry.claim_class == ClaimClass.ENACTED_LAW.value:
            if not _is_official_enacted_law_url(entry.primary_source_url):
                errors.append(
                    f"Entry '{key}' (enacted_law) must have an official government/statutory primary_source_url, "
                    f"got '{entry.primary_source_url}'"
                )
            if not entry.citation:
                errors.append(f"Entry '{key}' (enacted_law) must have a non-empty citation")
            if not normalize_quote(entry.verbatim_quote):
                errors.append(f"Entry '{key}' (enacted_law) must have a non-empty verbatim_quote")
            if not entry.source_quote_sha256:
                errors.append(f"Entry '{key}' (enacted_law) must have a non-empty source_quote_sha256")
            else:
                expected_sha = compute_quote_sha256(entry.verbatim_quote)
                if entry.source_quote_sha256.lower() != expected_sha:
                    errors.append(
                        f"Entry '{key}' quote SHA-256 mismatch: got {entry.source_quote_sha256}, "
                        f"expected {expected_sha}"
                    )
        elif entry.claim_class == ClaimClass.MARKET_BENCHMARK.value:
            if not entry.publisher:
                errors.append(f"Entry '{key}' (market_benchmark) must have a non-empty publisher")
            if not _is_valid_http_url(entry.primary_source_url):
                errors.append(
                    f"Entry '{key}' (market_benchmark) must have a valid primary_source_url, "
                    f"got '{entry.primary_source_url}'"
                )
            if not entry.required_qualifier_patterns:
                errors.append(
                    f"Entry '{key}' (market_benchmark) must define non-empty required_qualifier_patterns"
                )
            if entry.source_quote_sha256:
                expected_sha = compute_quote_sha256(entry.verbatim_quote)
                if entry.source_quote_sha256.lower() != expected_sha:
                    errors.append(
                        f"Entry '{key}' quote SHA-256 mismatch: got {entry.source_quote_sha256}, "
                        f"expected {expected_sha}"
                    )
        elif entry.claim_class == ClaimClass.FUTURE_PROJECTION.value:
            if not entry.required_qualifier_patterns:
                errors.append(
                    f"Entry '{key}' (future_projection) must define non-empty required_qualifier_patterns"
                )
            if entry.source_quote_sha256:
                expected_sha = compute_quote_sha256(entry.verbatim_quote)
                if entry.source_quote_sha256.lower() != expected_sha:
                    errors.append(
                        f"Entry '{key}' quote SHA-256 mismatch: got {entry.source_quote_sha256}, "
                        f"expected {expected_sha}"
                    )

        if entry.unit == "brackets":
            _validate_brackets(key, entry.value, errors)

        _validate_regex_list(entry.required_qualifier_patterns, f"entry.{key}.required_qualifier_patterns", errors)
        for sup_idx, sup in enumerate(entry.superseded_values):
            if not isinstance(sup, dict):
                errors.append(f"Entry '{key}' superseded_values[{sup_idx}] must be an object")
                continue
            _validate_regex_list(
                [str(p) for p in (sup.get("patterns") or [])],
                f"entry.{key}.superseded_values[{sup_idx}].patterns",
                errors,
            )

    for fid, formula in pack.formulas.items():
        if formula.formula_id != fid:
            errors.append(f"Formula key mismatch: '{fid}' != formula_id '{formula.formula_id}'")
        if not formula.expression:
            errors.append(f"Formula '{fid}' has empty expression")
            continue
        if not formula.js_expression:
            errors.append(f"Formula '{fid}' failed to derive or define js_expression")
        try:
            baseline_actual = safe_eval_formula(formula.expression, formula.variables)
            if abs(baseline_actual - formula.expected_baseline_output) > formula.tolerance:
                errors.append(
                    f"Formula '{fid}' baseline mismatch: got {baseline_actual}, "
                    f"expected {formula.expected_baseline_output} (tol={formula.tolerance})"
                )
        except TruthPackValidationError as exc:
            errors.append(f"Formula '{fid}' baseline evaluation failed: {exc}")

        if not formula.test_vectors:
            errors.append(f"Formula '{fid}' must include at least one test_vectors item")
        for v_idx, vec in enumerate(formula.test_vectors):
            if not isinstance(vec, dict) or "inputs" not in vec or "expected" not in vec:
                errors.append(f"Formula '{fid}' test_vectors[{v_idx}] must contain 'inputs' and 'expected'")
                continue
            vec_label = str(vec.get("label") or f"vector_{v_idx}")
            vec_vars = {**formula.variables, **dict(vec["inputs"] or {})}
            vec_tol = float(vec.get("tolerance") if vec.get("tolerance") is not None else formula.tolerance)
            try:
                vec_actual = safe_eval_formula(formula.expression, vec_vars)
                vec_expected = float(vec["expected"])
                if abs(vec_actual - vec_expected) > vec_tol:
                    errors.append(
                        f"Formula '{fid}' test vector '{vec_label}' mismatch: "
                        f"got {vec_actual}, expected {vec_expected} (tol={vec_tol})"
                    )
            except (TruthPackValidationError, TypeError, ValueError) as exc:
                errors.append(f"Formula '{fid}' test vector '{vec_label}' failed: {exc}")

        for ck in formula.citation_keys:
            if ck not in pack.citations_allowlist:
                errors.append(f"Formula '{fid}' references unknown citation_key '{ck}'")

        _validate_regex_list(formula.allowed_slug_patterns, f"formula.{fid}.allowed_slug_patterns", errors)
        _validate_regex_list(formula.forbidden_slug_patterns, f"formula.{fid}.forbidden_slug_patterns", errors)

    for ckey, cmeta in pack.citations_allowlist.items():
        if not isinstance(cmeta, dict):
            errors.append(f"citations_allowlist['{ckey}'] must be an object")
            continue
        _validate_regex_list(
            [str(p) for p in (cmeta.get("patterns") or [])],
            f"citations_allowlist.{ckey}.patterns",
            errors,
        )
        _validate_regex_list(
            [str(p) for p in (cmeta.get("allowed_slug_patterns") or [])],
            f"citations_allowlist.{ckey}.allowed_slug_patterns",
            errors,
        )
        _validate_regex_list(
            [str(p) for p in (cmeta.get("forbidden_slug_patterns") or [])],
            f"citations_allowlist.{ckey}.forbidden_slug_patterns",
            errors,
        )

    for d_idx, disc in enumerate(pack.disclosures):
        if not disc.disclosure_id:
            errors.append(f"disclosures[{d_idx}] missing disclosure_id")
        if not disc.canonical_text:
            errors.append(f"Disclosure '{disc.disclosure_id or d_idx}' missing canonical_text")
        if not disc.required_text_patterns:
            errors.append(f"Disclosure '{disc.disclosure_id or d_idx}' missing required_text_patterns")
        _validate_regex_list(disc.required_text_patterns, f"disclosure.{disc.disclosure_id}.required_text_patterns", errors)
        _validate_regex_list(disc.applies_to_slug_patterns, f"disclosure.{disc.disclosure_id}.applies_to_slug_patterns", errors)

    for b_idx, claim in enumerate(pack.banned_claims):
        if not isinstance(claim, dict) or not claim.get("pattern") or not claim.get("reason"):
            errors.append(f"banned_claims[{b_idx}] must include 'pattern' and 'reason'")
            continue
        _validate_regex_list([str(claim["pattern"])], f"banned_claims[{b_idx}].pattern", errors)

    return errors


def _canonicalize_property_id(raw_pid: str, fallback_name: str = "") -> str:
    """Normalizes property_id from .pseofactory.json without hardcoded tenant limits."""
    pid = str(raw_pid or fallback_name or "").strip().lower()
    if pid in ("profithelm-platform", "factory"):
        return "profithelm"
    return pid


def _scan_workspace_truth_pack_markers(workspace_root: Path) -> Dict[str, Optional[Path]]:
    """
    Scans <workspace_root>/*/.pseofactory.json for property_id -> optional truth_pack_path.
    Scales dynamically to 50+ sites.
    """
    markers: Dict[str, Optional[Path]] = {}
    ws = Path(workspace_root).resolve()
    if not ws.is_dir():
        return markers
    for child in sorted(ws.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        marker_file = child / ".pseofactory.json"
        if not marker_file.is_file():
            continue
        try:
            payload = json.loads(marker_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        pid = _canonicalize_property_id(str(payload.get("property_id") or ""), child.name)
        if not pid:
            continue
        raw_tp_path = str(payload.get("truth_pack_path") or "").strip()
        if raw_tp_path:
            tp_path = Path(raw_tp_path)
            if not tp_path.is_absolute():
                tp_path = (child / tp_path).resolve()
            markers[pid] = tp_path
        elif pid not in markers:
            markers[pid] = None
    return markers


def discover_truth_pack_ids(
    *,
    packs_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[str]:
    """Discovers available Truth Pack property IDs from packs_dir and workspace .pseofactory.json markers."""
    found: set[str] = set()
    eff_packs_dir = Path(packs_dir) if packs_dir is not None else DEFAULT_TRUTH_PACKS_DIR
    if eff_packs_dir.is_dir():
        for json_file in sorted(eff_packs_dir.glob("*.json")):
            if json_file.is_file():
                found.add(json_file.stem.strip().lower())

    if workspace_root is not None:
        markers = _scan_workspace_truth_pack_markers(Path(workspace_root))
        for pid, custom_path in markers.items():
            if custom_path is not None and custom_path.is_file():
                found.add(pid)
            elif (eff_packs_dir / f"{pid}.json").is_file():
                found.add(pid)

    return sorted(found)


def load_truth_pack(
    property_id: str,
    *,
    packs_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    as_of: Optional[date] = None,
    allow_expired: bool = False,
) -> TruthPack:
    """
    Loads and validates the TruthPack for property_id.
    Fail-closed: NEVER falls back to 'profithelm' or any default pack.
    """
    pid = _canonicalize_property_id(property_id)
    if not pid:
        raise TruthPackMissingError("property_id must be non-empty")

    eff_packs_dir = Path(packs_dir) if packs_dir is not None else DEFAULT_TRUTH_PACKS_DIR
    target_path: Optional[Path] = None

    if workspace_root is not None:
        markers = _scan_workspace_truth_pack_markers(Path(workspace_root))
        if pid in markers and markers[pid] is not None:
            target_path = markers[pid]

    if target_path is None:
        target_path = eff_packs_dir / f"{pid}.json"

    if not target_path.is_file():
        raise TruthPackMissingError(f"Truth Pack missing for property_id '{pid}' at {target_path}")

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        raise TruthPackValidationError(f"Failed to parse Truth Pack JSON for '{pid}': {exc}") from exc

    pack = TruthPack.from_dict(data)
    if pack.property_id != pid:
        raise TruthPackValidationError(
            f"Truth Pack property_id mismatch at {target_path}: expected '{pid}', got '{pack.property_id}'"
        )

    errors = validate_truth_pack(pack, as_of=as_of, allow_expired=allow_expired)
    if errors:
        expiry_errors = [e for e in errors if e.startswith("EXPIRED:")]
        other_errors = [e for e in errors if not e.startswith("EXPIRED:")]
        if other_errors:
            raise TruthPackValidationError("; ".join(other_errors))
        if expiry_errors and not allow_expired:
            raise TruthPackExpiredError("; ".join(expiry_errors))

    return pack


def load_all_truth_packs(
    *,
    packs_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    as_of: Optional[date] = None,
    allow_expired: bool = False,
) -> Dict[str, TruthPack]:
    """Loads and validates all discovered Truth Packs."""
    ids = discover_truth_pack_ids(packs_dir=packs_dir, workspace_root=workspace_root)
    return {
        pid: load_truth_pack(
            pid,
            packs_dir=packs_dir,
            workspace_root=workspace_root,
            as_of=as_of,
            allow_expired=allow_expired,
        )
        for pid in ids
    }


def compute_truth_pack_sha256(pack: TruthPack) -> str:
    """Computes deterministic SHA-256 digest of a TruthPack."""
    canonical_json = json.dumps(
        pack.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


__all__ = [
    "ClaimClass",
    "DEFAULT_TRUTH_PACKS_DIR",
    "DisclosureRule",
    "FormulaSpec",
    "OFFICIAL_ENACTED_LAW_DOMAINS",
    "SUPPORTED_SCHEMA_VERSION",
    "TruthEntry",
    "TruthPack",
    "TruthPackError",
    "TruthPackExpiredError",
    "TruthPackMissingError",
    "TruthPackValidationError",
    "VALID_CLAIM_CLASSES",
    "compute_quote_sha256",
    "compute_truth_pack_sha256",
    "derive_js_expression",
    "discover_truth_pack_ids",
    "load_all_truth_packs",
    "load_truth_pack",
    "normalize_quote",
    "safe_eval_formula",
    "validate_truth_pack",
]
