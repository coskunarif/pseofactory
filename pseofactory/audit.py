"""
pseofactory Autonomous Content Accuracy & Truthfulness Audit Stage
Evaluates 100% of rendered HTML and calculation manifests against ground-truth
candidate specifications before static filesystem persistence.
Enforces 10 mechanical truthfulness and accuracy gates:
1. Title & H1 Parity Gate
2. Model Name Truthfulness Gate
3. Statutory Authority Provenance Gate
4. Empirical Economic Dataset Grounding Gate
5. Published Output & AST Formula Evaluation Parity Gate
6. Data Table Cell Truthfulness Gate
7. Empty Template / Format Leakage Gate
8. Mandatory Structural Components Gate
9. Schema.org JSON-LD 1:1 Parity Gate
10. Anti-Slop Typography & Touch Target Invariant Gate
Zero em-dashes. Zero en-dashes.
"""

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_valid_jsonld,
    detect_ungrounded_synthetic_claims,
    safe_eval_mathematical_formula,
)


class ContentAccuracyAuditError(ValueError):
    """
    Raised when a rendered asset fails content accuracy or truthfulness audit.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, message: str, report: Optional["ContentAccuracyAuditReport"] = None):
        super().__init__(message)
        self.report = report


@dataclass
class ContentAccuracyAuditReport:
    """
    Mechanical audit report produced by ContentAccuracyAuditStage.
    Zero em-dashes. Zero en-dashes.
    """

    passed: bool
    violations: List[str]
    gate_results: Dict[str, bool]
    tenant: str
    slug: str
    evaluated_output: Optional[float] = None
    published_output: Optional[float] = None
    tolerance: float = 0.01
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": list(self.violations),
            "gate_results": dict(self.gate_results),
            "tenant": self.tenant,
            "slug": self.slug,
            "evaluated_output": self.evaluated_output,
            "published_output": self.published_output,
            "tolerance": self.tolerance,
            "metadata": dict(self.metadata),
        }


def _resolve_expected_title(candidate_spec: Dict[str, Any]) -> str:
    """
    Resolves the expected title exactly matching compiler.py title derivation.
    """
    title = str(candidate_spec.get("title") or "").strip()
    if not title:
        query = str(candidate_spec.get("query") or candidate_spec.get("primary_keyword") or "").strip()
        if query:
            words = [w.capitalize() for w in query.split() if w]
            title = " ".join(words) + " Calculator and Statutory Analysis"
        else:
            title = "Proprietary Model Calculator and Statutory Analysis"
    return title


def audit_rendered_asset(
    html_content: str,
    candidate_spec: Dict[str, Any],
    tenant: str,
    tolerance: float = 0.01,
) -> ContentAccuracyAuditReport:
    """
    Evaluates rendered HTML and calculation manifest against candidate_spec
    across 10 deterministic truthfulness and accuracy gates.
    Returns a ContentAccuracyAuditReport.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_content, str) or not html_content.strip():
        return ContentAccuracyAuditReport(
            passed=False,
            violations=["Rendered HTML content is empty or not a string"],
            gate_results={"html_non_empty": False},
            tenant=tenant,
            slug=str(candidate_spec.get("slug") or ""),
            tolerance=tolerance,
        )

    violations: List[str] = []
    gate_results: Dict[str, bool] = {}
    slug = str(candidate_spec.get("slug") or "").strip()
    expected_title = _resolve_expected_title(candidate_spec)

    # Extract manifest data early if available
    manifest_data: Dict[str, Any] = {}
    manifest_m = re.search(
        r'<script[^>]*class=["\'][^"\']*calculation-manifest[^"\']*["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if manifest_m:
        try:
            manifest_data = json.loads(manifest_m.group(1).strip())
        except Exception:
            manifest_data = {}

    # -------------------------------------------------------------
    # Gate 1: Title & H1 Parity Gate
    # -------------------------------------------------------------
    g1_ok = True
    title_m = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
    h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
    if not title_m:
        g1_ok = False
        violations.append("Gate 1 (Title & H1 Parity): Missing <title> tag in rendered HTML")
    if not h1_m:
        g1_ok = False
        violations.append("Gate 1 (Title & H1 Parity): Missing <h1> tag in rendered HTML")

    if title_m and h1_m:
        title_text = html.unescape(title_m.group(1)).strip()
        h1_text = html.unescape(re.sub(r'<[^>]+>', '', h1_m.group(1))).strip()
        if title_text != expected_title:
            g1_ok = False
            violations.append(
                f"Gate 1 (Title & H1 Parity): <title> text '{title_text}' does not match expected '{expected_title}'"
            )
        if h1_text != expected_title:
            g1_ok = False
            violations.append(
                f"Gate 1 (Title & H1 Parity): <h1> text '{h1_text}' does not match expected '{expected_title}'"
            )
    gate_results["title_h1_parity"] = g1_ok

    # -------------------------------------------------------------
    # Gate 2: Model Name Truthfulness Gate
    # -------------------------------------------------------------
    g2_ok = True
    model_name = str(
        candidate_spec.get("model_name")
        or candidate_spec.get("proprietary_model")
        or manifest_data.get("model_name")
        or ""
    ).strip()
    if not model_name:
        g2_ok = False
        violations.append("Gate 2 (Model Name): candidate_spec missing model_name")
    else:
        # Check header takeaway
        takeaway_m = re.search(
            r'<p class=["\']takeaway["\'][^>]*>(.*?)</p>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        header_m = re.search(r'<header[^>]*>(.*?)</header>', html_content, re.DOTALL)
        header_text = (takeaway_m.group(1) if takeaway_m else "") + " " + (header_m.group(1) if header_m else "")
        if model_name not in header_text:
            g2_ok = False
            violations.append(f"Gate 2 (Model Name): model_name '{model_name}' missing from header takeaway text")

        # Check calculation container H2
        h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
        if not any(model_name in h for h in h2_matches):
            g2_ok = False
            violations.append(f"Gate 2 (Model Name): model_name '{model_name}' missing from calculation <h2> headings")

        # Check manifest
        if manifest_data.get("model_name") != model_name:
            g2_ok = False
            violations.append(
                f"Gate 2 (Model Name): manifest model_name '{manifest_data.get('model_name')}' does not match '{model_name}'"
            )
    gate_results["model_name_truthfulness"] = g2_ok

    # -------------------------------------------------------------
    # Gate 3: Statutory Authority Provenance Gate
    # -------------------------------------------------------------
    g3_ok = True
    statutory = str(
        candidate_spec.get("statutory_authority")
        or candidate_spec.get("statutory_provenance")
        or manifest_data.get("statutory_authority")
        or ""
    ).strip()
    if not statutory:
        g3_ok = False
        violations.append("Gate 3 (Statutory Authority): candidate_spec missing statutory_authority")
    else:
        # Check text presence
        if statutory not in html_content:
            g3_ok = False
            violations.append(f"Gate 3 (Statutory Authority): '{statutory}' not found in rendered HTML text")

        # Check data-statutory-source in multi-dataset-join
        div_m = re.search(
            r'<div[^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\'][^>]*data-statutory-source=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        ) or re.search(
            r'<div[^>]*data-statutory-source=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\']',
            html_content,
            re.IGNORECASE,
        )
        if not div_m:
            g3_ok = False
            violations.append("Gate 3 (Statutory Authority): multi-dataset-join missing data-statutory-source attribute")
        elif div_m.group(1).strip() != statutory:
            g3_ok = False
            violations.append(
                f"Gate 3 (Statutory Authority): multi-dataset-join data-statutory-source '{div_m.group(1)}' != '{statutory}'"
            )

        # Check data-statutory-source in table.calculation-table
        table_m = re.search(
            r'<table[^>]*data-statutory-source=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if not table_m:
            g3_ok = False
            violations.append("Gate 3 (Statutory Authority): calculation-table missing data-statutory-source attribute")
        elif table_m.group(1).strip() != statutory:
            g3_ok = False
            violations.append(
                f"Gate 3 (Statutory Authority): calculation-table data-statutory-source '{table_m.group(1)}' != '{statutory}'"
            )

        # Check manifest statutory_authority
        if manifest_data.get("statutory_authority") != statutory:
            g3_ok = False
            violations.append(
                f"Gate 3 (Statutory Authority): manifest statutory_authority '{manifest_data.get('statutory_authority')}' != '{statutory}'"
            )
    gate_results["statutory_authority_provenance"] = g3_ok

    # -------------------------------------------------------------
    # Gate 4: Empirical Economic Dataset Grounding Gate
    # -------------------------------------------------------------
    g4_ok = True
    economic = str(
        candidate_spec.get("economic_dataset")
        or candidate_spec.get("economic_source")
        or manifest_data.get("economic_dataset")
        or ""
    ).strip()
    if not economic:
        g4_ok = False
        violations.append("Gate 4 (Economic Dataset): candidate_spec missing economic_dataset")
    else:
        # Check text presence
        if economic not in html_content:
            g4_ok = False
            violations.append(f"Gate 4 (Economic Dataset): '{economic}' not found in rendered HTML text")

        # Check data-economic-source in multi-dataset-join
        div_econ_m = re.search(
            r'<div[^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\'][^>]*data-economic-source=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        ) or re.search(
            r'<div[^>]*data-economic-source=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\']',
            html_content,
            re.IGNORECASE,
        )
        if not div_econ_m:
            g4_ok = False
            violations.append("Gate 4 (Economic Dataset): multi-dataset-join missing data-economic-source attribute")
        elif div_econ_m.group(1).strip() != economic:
            g4_ok = False
            violations.append(
                f"Gate 4 (Economic Dataset): multi-dataset-join data-economic-source '{div_econ_m.group(1)}' != '{economic}'"
            )

        # Check data-economic-source in table.calculation-table
        table_econ_m = re.search(
            r'<table[^>]*data-economic-source=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if not table_econ_m:
            g4_ok = False
            violations.append("Gate 4 (Economic Dataset): calculation-table missing data-economic-source attribute")
        elif table_econ_m.group(1).strip() != economic:
            g4_ok = False
            violations.append(
                f"Gate 4 (Economic Dataset): calculation-table data-economic-source '{table_econ_m.group(1)}' != '{economic}'"
            )

        # Check manifest economic_dataset
        if manifest_data.get("economic_dataset") != economic:
            g4_ok = False
            violations.append(
                f"Gate 4 (Economic Dataset): manifest economic_dataset '{manifest_data.get('economic_dataset')}' != '{economic}'"
            )
    gate_results["economic_dataset_grounding"] = g4_ok

    # -------------------------------------------------------------
    # Gate 5: Published Output & AST Formula Evaluation Parity Gate
    # -------------------------------------------------------------
    g5_ok = True
    formula = str(
        candidate_spec.get("formula")
        or manifest_data.get("formula")
        or ""
    ).strip()
    raw_inputs = (
        candidate_spec.get("inputs")
        if candidate_spec.get("inputs") is not None
        else manifest_data.get("inputs", {})
    )
    if not isinstance(raw_inputs, dict):
        raw_inputs = {}

    # Clamp numeric inputs >= 0 per HWL-1263
    clamped_inputs: Dict[str, Any] = {}
    for k, v in raw_inputs.items():
        if isinstance(v, (int, float)):
            clamped_inputs[k] = max(0.0, float(v)) if isinstance(v, float) else max(0, v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                num_v = float(v_clean)
                clamped_inputs[k] = max(0.0, num_v)
            except ValueError:
                clamped_inputs[k] = v
        else:
            clamped_inputs[k] = v

    calc_output: Optional[float] = None
    if not formula:
        g5_ok = False
        violations.append("Gate 5 (Formula Parity): Missing formula string in candidate_spec/manifest")
    else:
        try:
            calc_output = safe_eval_mathematical_formula(formula, clamped_inputs)
        except Exception as ex:
            g5_ok = False
            violations.append(f"Gate 5 (Formula Parity): safe_eval_mathematical_formula failed: {ex}")

    # Extract published output from HTML
    html_output_val: Optional[float] = None
    out_val_m = re.search(r'<strong class=["\']output-value["\']>([^<]+)</strong>', html_content)
    if not out_val_m:
        # Fallback to takeaway direct answer bold result
        out_val_m = re.search(
            r'Executive Direct Answer:.*?<strong>([^<]+)</strong>',
            html_content,
            re.DOTALL,
        )

    if out_val_m:
        clean_html_val = out_val_m.group(1).replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            html_output_val = float(clean_html_val)
        except ValueError:
            g5_ok = False
            violations.append(f"Gate 5 (Formula Parity): Failed to parse float from HTML output '{out_val_m.group(1)}'")
    else:
        g5_ok = False
        violations.append("Gate 5 (Formula Parity): Missing published output in rendered HTML")

    spec_pub = candidate_spec.get("published_output")
    if spec_pub is None:
        spec_pub = candidate_spec.get("expected_output") or manifest_data.get("published_output")
    spec_pub_val = float(spec_pub) if spec_pub is not None else None

    if g5_ok and calc_output is not None:
        if spec_pub_val is not None and abs(calc_output - spec_pub_val) > tolerance:
            g5_ok = False
            violations.append(
                f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from spec published_output {spec_pub_val} (tolerance {tolerance})"
            )
        if html_output_val is not None and abs(calc_output - html_output_val) > tolerance:
            g5_ok = False
            violations.append(
                f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from HTML rendered output {html_output_val} (tolerance {tolerance})"
            )
        manifest_pub = manifest_data.get("published_output")
        if manifest_pub is not None:
            try:
                man_pub_val = float(manifest_pub)
                if abs(calc_output - man_pub_val) > tolerance:
                    g5_ok = False
                    violations.append(
                        f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from manifest published_output {man_pub_val} (tolerance {tolerance})"
                    )
            except ValueError:
                pass
    gate_results["formula_evaluation_parity"] = g5_ok

    # -------------------------------------------------------------
    # Gate 6: Data Table Cell Truthfulness Gate
    # -------------------------------------------------------------
    g6_ok = True
    table_m = re.search(
        r'<table[^>]*class=["\'][^"\']*calculation-table[^"\']*["\'][^>]*>(.*?)</table>',
        html_content,
        re.DOTALL | re.IGNORECASE,
    )
    if not table_m:
        g6_ok = False
        violations.append("Gate 6 (Table Cells): calculation-table missing from rendered HTML")
    else:
        td_cells = re.findall(r'<td[^>]*>(.*?)</td>', table_m.group(1), re.DOTALL | re.IGNORECASE)
        if not td_cells:
            g6_ok = False
            violations.append("Gate 6 (Table Cells): calculation-table contains zero <td> cells")
        for cell_raw in td_cells:
            cell_clean = re.sub(r'<[^>]+>', '', cell_raw).strip()
            if not cell_clean:
                g6_ok = False
                violations.append("Gate 6 (Table Cells): Data table contains empty cell")
                break
            if re.search(r'\b(nan|null|none|undefined)\b', cell_clean, re.IGNORECASE):
                g6_ok = False
                violations.append(f"Gate 6 (Table Cells): Data table cell contains illegal token: '{cell_clean}'")
                break
            if re.search(r'\b(mock|dummy|hypothetical|placeholder)\b', cell_clean, re.IGNORECASE):
                g6_ok = False
                violations.append(
                    f"Gate 6 (Table Cells): Data table cell contains ungrounded synthetic token: '{cell_clean}'"
                )
                break
            syn_issues = detect_ungrounded_synthetic_claims(cell_clean)
            if syn_issues:
                g6_ok = False
                violations.append(
                    f"Gate 6 (Table Cells): Data table cell contains synthetic claim: '{syn_issues[0]}'"
                )
                break
    gate_results["table_cell_truthfulness"] = g6_ok

    # -------------------------------------------------------------
    # Gate 7: Empty Template / Format Leakage Gate
    # -------------------------------------------------------------
    g7_ok = True
    # Format strings {[a-zA-Z0-9_]+}
    fmt_matches = re.findall(r'\{[a-zA-Z0-9_]+\}', html_content)
    if fmt_matches:
        g7_ok = False
        violations.append(f"Gate 7 (Template Leakage): Unrendered format strings detected: {fmt_matches}")

    # Jinja/Mustache {{...}}
    jinja_matches = re.findall(r'\{\{.*?\}\}', html_content)
    if jinja_matches:
        g7_ok = False
        violations.append(f"Gate 7 (Template Leakage): Unrendered template brackets detected: {jinja_matches}")

    # Leakage of undefined or None in text (excluding script and style blocks)
    no_scripts_text = re.sub(
        r'<(script|style)[^>]*>.*?</\1>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if re.search(r'\b(undefined|None)\b', no_scripts_text):
        g7_ok = False
        violations.append("Gate 7 (Template Leakage): Rendered HTML contains uninitialized None or undefined text")
    if re.search(r'\bnull\b', no_scripts_text):
        g7_ok = False
        violations.append("Gate 7 (Template Leakage): Rendered HTML contains uninitialized null text")
    gate_results["template_leakage_free"] = g7_ok

    # -------------------------------------------------------------
    # Gate 8: Mandatory Structural Components Gate
    # -------------------------------------------------------------
    g8_ok = True
    required_components = [
        ("calculator-form", r'<form[^>]*class=["\'][^"\']*calculator-form[^"\']*["\']'),
        ("result-box", r'<div[^>]*class=["\'][^"\']*result-box[^"\']*["\']'),
        ("multi-dataset-join", r'<div[^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\']'),
        ("methodology", r'<section[^>]*class=["\'][^"\']*methodology[^"\']*["\']'),
        ("calculation-manifest", r'<script[^>]*class=["\'][^"\']*calculation-manifest[^"\']*["\']'),
    ]
    for comp_name, comp_pat in required_components:
        if not re.search(comp_pat, html_content, re.IGNORECASE):
            g8_ok = False
            violations.append(f"Gate 8 (Structural Components): Missing mandatory component '{comp_name}'")
    gate_results["structural_components"] = g8_ok

    # -------------------------------------------------------------
    # Gate 9: Schema.org JSON-LD 1:1 Parity Gate
    # -------------------------------------------------------------
    g9_ok = True
    try:
        jsonld_blocks = assert_valid_jsonld(html_content, context="ContentAccuracyAuditStage")
        has_app = False
        has_faq = False
        for block in jsonld_blocks:
            b_type = block.get("@type")
            if b_type == "SoftwareApplication" or (isinstance(b_type, list) and "SoftwareApplication" in b_type):
                has_app = True
                app_name = block.get("name")
                if app_name != expected_title:
                    g9_ok = False
                    violations.append(
                        f"Gate 9 (Schema.org): SoftwareApplication name '{app_name}' does not match title '{expected_title}'"
                    )
                app_url = block.get("url", "")
                if slug and f"/tools/{slug}" not in app_url:
                    g9_ok = False
                    violations.append(
                        f"Gate 9 (Schema.org): SoftwareApplication url '{app_url}' does not reference '/tools/{slug}'"
                    )
            elif b_type == "FAQPage":
                has_faq = True
                main_entity = block.get("mainEntity", [])
                if not main_entity or not isinstance(main_entity, list):
                    g9_ok = False
                    violations.append("Gate 9 (Schema.org): FAQPage mainEntity is empty or invalid")
                faq_text = " ".join(
                    q.get("acceptedAnswer", {}).get("text", "")
                    for q in main_entity
                    if isinstance(q, dict) and isinstance(q.get("acceptedAnswer"), dict)
                )
                if statutory and statutory not in faq_text:
                    g9_ok = False
                    violations.append(
                        f"Gate 9 (Schema.org): FAQPage acceptedAnswer text does not quote statutory authority '{statutory}'"
                    )
                if economic and economic not in faq_text:
                    g9_ok = False
                    violations.append(
                        f"Gate 9 (Schema.org): FAQPage acceptedAnswer text does not quote economic dataset '{economic}'"
                    )
                if formula and formula not in faq_text:
                    g9_ok = False
                    violations.append(
                        f"Gate 9 (Schema.org): FAQPage acceptedAnswer text does not quote formula '{formula}'"
                    )
        if not has_app:
            g9_ok = False
            violations.append("Gate 9 (Schema.org): Missing SoftwareApplication JSON-LD block")
        if not has_faq:
            g9_ok = False
            violations.append("Gate 9 (Schema.org): Missing FAQPage JSON-LD block")
    except Exception as ex:
        g9_ok = False
        violations.append(f"Gate 9 (Schema.org): JSON-LD parsing/validation failed: {ex}")
    gate_results["schema_jsonld_parity"] = g9_ok

    # -------------------------------------------------------------
    # Gate 10: Anti-Slop Typography & Touch Target Invariant Gate
    # -------------------------------------------------------------
    g10_ok = True
    try:
        assert_no_forbidden_dashes(html_content, context=f"audit stage '{slug}'")
    except Exception as ex:
        g10_ok = False
        violations.append(f"Gate 10 (Anti-Slop): Forbidden dashes detected: {ex}")

    # Touch target check for #calculate-btn and inputs
    btn_m = re.search(
        r'<button[^>]*id=["\']calculate-btn["\'][^>]*style=["\']([^"\']+)["\']',
        html_content,
        re.IGNORECASE,
    ) or re.search(
        r'<button[^>]*style=["\']([^"\']+)["\'][^>]*id=["\']calculate-btn["\']',
        html_content,
        re.IGNORECASE,
    )
    if btn_m:
        style_str = btn_m.group(1)
        h_m = re.search(r'min-height:\s*(\d+)px', style_str)
        w_m = re.search(r'min-width:\s*(\d+)px', style_str)
        if h_m and int(h_m.group(1)) < 44:
            g10_ok = False
            violations.append(f"Gate 10 (Touch Target): #calculate-btn min-height {h_m.group(1)}px < 44px")
        if w_m and int(w_m.group(1)) < 44:
            g10_ok = False
            violations.append(f"Gate 10 (Touch Target): #calculate-btn min-width {w_m.group(1)}px < 44px")
    else:
        # Check global touch-target CSS rule
        if not re.search(r'\.touch-target\s*\{[^}]*min-height:\s*44px', html_content, re.IGNORECASE):
            g10_ok = False
            violations.append("Gate 10 (Touch Target): #calculate-btn missing 44x44px touch target specification")

    gate_results["antislop_and_touch_target"] = g10_ok

    passed = len(violations) == 0
    return ContentAccuracyAuditReport(
        passed=passed,
        violations=violations,
        gate_results=gate_results,
        tenant=tenant,
        slug=slug,
        evaluated_output=calc_output,
        published_output=html_output_val,
        tolerance=tolerance,
        metadata={
            "expected_title": expected_title,
            "statutory_authority": statutory,
            "economic_dataset": economic,
            "formula": formula,
            "model_name": model_name,
        },
    )


class ContentAccuracyAuditStage:
    """
    Mandatory synchronous in-memory audit stage verifying 10 mechanical truthfulness
    and accuracy gates for high-effort programmatic assets before filesystem persistence.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, tolerance: float = 0.01, strict: bool = True):
        self.tolerance = tolerance
        self.strict = strict

    def audit(
        self,
        html: str,
        candidate_spec: Dict[str, Any],
        tenant: str,
    ) -> ContentAccuracyAuditReport:
        """
        Executes audit against rendered HTML and candidate specification.
        In strict mode, raises ContentAccuracyAuditError on failure.
        """
        report = audit_rendered_asset(
            html_content=html,
            candidate_spec=candidate_spec,
            tenant=tenant,
            tolerance=self.tolerance,
        )
        if self.strict and not report.passed:
            raise ContentAccuracyAuditError(
                f"Content accuracy audit failed with {len(report.violations)} violation(s): {report.violations[0]}",
                report=report,
            )
        return report


__all__ = [
    "ContentAccuracyAuditStage",
    "ContentAccuracyAuditReport",
    "ContentAccuracyAuditError",
    "audit_rendered_asset",
]
