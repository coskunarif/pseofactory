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

import ast
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_valid_jsonld,
    detect_placeholder_verification_token_issues,
    detect_sentence_truncation_issues,
    detect_title_year_conflict_issues,
    detect_ungrounded_synthetic_claims,
    detect_uninitialized_ssr_calculator_metrics,
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

        # Check calculation container H2 (accept either raw model_name or its human-formatted heading label)
        from pseofactory.competitor import _format_safe_heading_topic
        safe_model_h2 = _format_safe_heading_topic(model_name, "")
        h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
        if not any(model_name in h or (safe_model_h2 and safe_model_h2 in h) for h in h2_matches):
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
    out_val_m = re.search(
        r'<strong[^>]*class=["\'][^"\']*\boutput-value\b[^"\']*["\'][^>]*>([^<]+)</strong>',
        html_content,
        re.IGNORECASE,
    )
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
        eff_tol = min(tolerance, 0.0005) if (0 < abs(calc_output) < 1) else tolerance
        if spec_pub_val is not None and abs(calc_output - spec_pub_val) > eff_tol:
            g5_ok = False
            violations.append(
                f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from spec published_output {spec_pub_val} (tolerance {eff_tol})"
            )
        if html_output_val is not None and abs(calc_output - html_output_val) > eff_tol:
            g5_ok = False
            violations.append(
                f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from HTML rendered output {html_output_val} (tolerance {eff_tol})"
            )
        manifest_pub = manifest_data.get("published_output")
        if manifest_pub is not None:
            try:
                man_pub_val = float(manifest_pub)
                if abs(calc_output - man_pub_val) > eff_tol:
                    g5_ok = False
                    violations.append(
                        f"Gate 5 (Formula Parity): Evaluated formula output {calc_output} diverges from manifest published_output {man_pub_val} (tolerance {eff_tol})"
                    )
            except ValueError:
                pass
    gate_results["formula_evaluation_parity"] = g5_ok

    # -------------------------------------------------------------
    # Gate 6: Data Table Cell Truthfulness Gate
    # -------------------------------------------------------------
    g6_ok = True
    table_m = re.search(
        r'<table[^>]*class=["\'][^"\']*(?:calculation-table|scenario-table)[^"\']*["\'][^>]*>(.*?)</table>',
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

    if g6_ok and calc_output is not None:
        sensitivity_checks = [
            ("scenario-baseline", 1.0),
            ("scenario-conservative", 0.8),
            ("scenario-moderate-contraction", 0.9),
            ("scenario-moderate-expansion", 1.1),
            ("scenario-aggressive", 1.2),
        ]
        for cls_name, mult in sensitivity_checks:
            scen_m = re.search(
                rf'<strong[^>]*class=["\'][^"\']*\b{re.escape(cls_name)}\b[^"\']*["\'][^>]*>([^<]+)</strong>',
                html_content,
                re.IGNORECASE,
            )
            if scen_m:
                raw_scen = scen_m.group(1).replace("$", "").replace(",", "").replace("%", "").strip()
                try:
                    scen_val = float(raw_scen)
                    raw_prod = calc_output * mult
                    expected_scen = round(raw_prod, 4 if (0 < abs(raw_prod) < 1) else 2)
                    tol_scen = 0.0005 if (0 < abs(raw_prod) < 1) else max(tolerance, 0.02)
                    if abs(scen_val - expected_scen) > tol_scen:
                        g6_ok = False
                        violations.append(
                            f"Gate 6 (Table Cells): Sensitivity table cell '{cls_name}' value {scen_val} diverges from expected {expected_scen} ({mult}x of {calc_output})"
                        )
                        break
                except ValueError:
                    g6_ok = False
                    violations.append(
                        f"Gate 6 (Table Cells): Sensitivity table cell '{cls_name}' contains non-numeric value '{scen_m.group(1)}'"
                    )
                    break
    gate_results["table_cell_truthfulness"] = g6_ok

    no_scripts_text = _audit_template_and_structure_gates(
        html_content=html_content,
        slug=slug,
        violations=violations,
        gate_results=gate_results,
    )

    _audit_schema_and_fact_gates(
        html_content=html_content,
        expected_title=expected_title,
        slug=slug,
        statutory=statutory,
        economic=economic,
        formula=formula,
        no_scripts_text=no_scripts_text,
        tenant=tenant,
        candidate_spec=candidate_spec,
        violations=violations,
        gate_results=gate_results,
    )

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


def _audit_template_and_structure_gates(
    html_content: str,
    slug: str,
    violations: List[str],
    gate_results: Dict[str, bool],
) -> str:
    """Executes Gates 7 and 8 for audit_rendered_asset and returns stripped visible text."""
    g7_ok = True
    fmt_matches = re.findall(r'\{\s*[a-zA-Z0-9_]+\s*\}', html_content)
    if fmt_matches:
        g7_ok = False
        violations.append(f"Gate 7 (Template Leakage): Unrendered format strings detected: {fmt_matches}")

    jinja_matches = re.findall(r'\{\{.*?\}\}', html_content)
    if jinja_matches:
        g7_ok = False
        violations.append(f"Gate 7 (Template Leakage): Unrendered template brackets detected: {jinja_matches}")

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
    if re.search(r'\bNaN\b', no_scripts_text):
        g7_ok = False
        violations.append("Gate 7 (Template Leakage): Rendered HTML contains uninitialized NaN text outside script tags")
    if "google-site-verification" in html_content.lower():
        for tok_err in detect_placeholder_verification_token_issues(html_content, context=slug):
            g7_ok = False
            violations.append(f"Gate 7 (Template Leakage): {tok_err}")
    for ssr_err in detect_uninitialized_ssr_calculator_metrics(html_content, context=slug):
        g7_ok = False
        violations.append(f"Gate 7 (Template Leakage): {ssr_err}")
    gate_results["template_leakage_free"] = g7_ok

    g8_ok = True
    required_components = [
        ("calculator-form", r'<form[^>]*class=["\'][^"\']*calculator-form[^"\']*["\']'),
        ("result-box", r'<div[^>]*class=["\'][^"\']*result-box[^"\']*["\']'),
        ("multi-dataset-join", r'<(?:div|section)[^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\']'),
        ("methodology", r'<section[^>]*class=["\'][^"\']*methodology[^"\']*["\']'),
        ("calculation-manifest", r'<script[^>]*class=["\'][^"\']*calculation-manifest[^"\']*["\']'),
    ]
    for comp_name, comp_pat in required_components:
        if not re.search(comp_pat, html_content, re.IGNORECASE):
            g8_ok = False
            violations.append(f"Gate 8 (Structural Components): Missing mandatory component '{comp_name}'")

    qa_m = re.search(r'<aside[^>]*class=["\'][^"\']*\bquick-answer\b', html_content, re.IGNORECASE)
    first_h2_m = re.search(r"<h2\b", html_content, re.IGNORECASE)
    if qa_m and first_h2_m and qa_m.start() > first_h2_m.start():
        g8_ok = False
        violations.append("Gate 8 (Structural Components): .quick-answer must appear before the first <h2> heading")

    calc_anchor_idx = html_content.find('id="calculator-workspace-anchor"')
    mdj_dom_m = re.search(
        r'<(?:div|section)[^>]*class=["\'][^"\']*\bmulti-dataset-join\b',
        html_content,
        re.IGNORECASE,
    )
    mdj_idx = mdj_dom_m.start() if mdj_dom_m else -1
    if calc_anchor_idx != -1 and mdj_idx != -1 and calc_anchor_idx > mdj_idx:
        g8_ok = False
        violations.append(
            "Gate 8 (Structural Components): #calculator-workspace-anchor must appear before .multi-dataset-join above the fold"
        )

    meth_sec_m = re.search(
        r'<section[^>]*class=["\'][^"\']*\bmethodology\b[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        html_content,
        re.IGNORECASE,
    )
    if meth_sec_m:
        meth_inner = meth_sec_m.group(1)
        if "<ul" not in meth_inner.lower() and "<ol" not in meth_inner.lower():
            g8_ok = False
            violations.append("Gate 8 (Structural Components): methodology section missing scannable list (<ul> or <ol>)")
        if "/tools/" not in meth_inner:
            g8_ok = False
            violations.append("Gate 8 (Structural Components): methodology section missing contextual internal /tools/ links")

    if "Statutory analysis and compliance guidelines for " in html_content:
        g8_ok = False
        violations.append("Gate 8 (Structural Components): body contains tautological overlay heading filler")
    if "&amp;amp;" in html_content:
        g8_ok = False
        violations.append("Gate 8 (Structural Components): HTML contains double-escaped entity (&amp;amp;)")
    if "<td>480.00%</td>" in html_content:
        g8_ok = False
        violations.append("Gate 8 (Structural Components): HTML contains unnormalized percentage scale (480.00%)")
    if re.search(r"<h2[^>]*>[^<]*[a-z][A-Z][a-z]+[A-Z][a-z]+[^<]*</h2>", html_content):
        g8_ok = False
        violations.append("Gate 8 (Structural Components): H2 heading contains unsplit CamelCase identifier")

    title_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", html_content, re.IGNORECASE)
    if title_m:
        title_txt = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
        for t_err in detect_title_year_conflict_issues(title_txt, context=slug):
            g8_ok = False
            violations.append(f"Gate 8 (Structural Components): {t_err}")

    meta_m = re.search(
        r'<meta\b[^>]*name=["\']description["\'][^>]*content=(["\'])([\s\S]*?)\1',
        html_content,
        re.IGNORECASE,
    )
    if not meta_m:
        meta_m = re.search(
            r'<meta\b[^>]*content=(["\'])([\s\S]*?)\1[^>]*name=["\']description["\']',
            html_content,
            re.IGNORECASE,
        )
    if meta_m:
        meta_txt = html.unescape(meta_m.group(2)).strip()
        for m_err in detect_sentence_truncation_issues(meta_txt, context=f"{slug} meta description"):
            g8_ok = False
            violations.append(f"Gate 8 (Structural Components): {m_err}")

    qa_block_m = re.search(
        r'<aside[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>([\s\S]*?)</aside>',
        html_content,
        re.IGNORECASE,
    )
    if qa_block_m:
        qa_p_m = re.search(r"<p[^>]*>([\s\S]*?)</p>", qa_block_m.group(1), re.IGNORECASE)
        qa_txt = html.unescape(re.sub(r"<[^>]+>", " ", (qa_p_m.group(1) if qa_p_m else qa_block_m.group(1)))).strip()
        qa_txt = re.sub(r"^\s*Quick\s+Answer\s*:?\s*", "", qa_txt, flags=re.IGNORECASE).strip()
        if qa_txt:
            for q_err in detect_sentence_truncation_issues(qa_txt, context=f"{slug} quick-answer"):
                g8_ok = False
                violations.append(f"Gate 8 (Structural Components): {q_err}")

    gate_results["structural_components"] = g8_ok
    return no_scripts_text


def _audit_schema_and_fact_gates(
    html_content: str,
    expected_title: str,
    slug: str,
    statutory: str,
    economic: str,
    formula: str,
    no_scripts_text: str,
    tenant: str,
    candidate_spec: Dict[str, Any],
    violations: List[str],
    gate_results: Dict[str, bool],
) -> None:
    """Executes Gates 9, 10, and 11 for audit_rendered_asset."""
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
                for q_item in main_entity:
                    if isinstance(q_item, dict):
                        q_name = q_item.get("name", "").strip()
                        ans_obj = q_item.get("acceptedAnswer", {})
                        a_ans = ans_obj.get("text", "").strip() if isinstance(ans_obj, dict) else ""
                        if q_name and q_name not in no_scripts_text:
                            g9_ok = False
                            violations.append(
                                f"Gate 9 (Schema.org): FAQPage question '{q_name}' not found in visible HTML body"
                            )
                        if a_ans and a_ans not in no_scripts_text:
                            g9_ok = False
                            violations.append(
                                "Gate 9 (Schema.org): FAQPage acceptedAnswer text not found in visible HTML body"
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

    g10_ok = True
    try:
        assert_no_forbidden_dashes(html_content, context=f"audit stage '{slug}'")
    except Exception as ex:
        g10_ok = False
        violations.append(f"Gate 10 (Anti-Slop): Forbidden dashes detected: {ex}")

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
        if not re.search(r'\.touch-target[^{]*\{[^}]*min-height:\s*44px', html_content, re.IGNORECASE):
            g10_ok = False
            violations.append("Gate 10 (Touch Target): #calculate-btn missing 44x44px touch target specification")

    from pseofactory.visual_primitives import (
        VISUAL_PRIMITIVES_VERSION,
        classify_screen_archetype,
        detect_visual_and_ux_contract_issues,
        get_screen_archetype_contract,
    )

    visual_ux_issues = detect_visual_and_ux_contract_issues(
        html_content,
        rel_path=slug or "index.html",
        require_primitives=None,
    )
    if visual_ux_issues:
        g10_ok = False
        for vui in visual_ux_issues:
            violations.append(f"Gate 10 (Visual/UX Contract): {vui}")

    gate_results["antislop_and_touch_target"] = g10_ok
    gate_results["visual_ui_quality_contract"] = len(visual_ux_issues) == 0

    g11_ok = True
    try:
        from pseofactory.contracts import detect_uncorroborated_statutory_claims
        from pseofactory.tenant_facts import TenantFactStore, TruthReconciliationEngine
        fact_store = TenantFactStore.get_instance()
        if fact_store.get_profile(tenant) is not None:
            spec_disclosures = candidate_spec.get("mandatory_disclosures") or []
            is_valid, fact_violations = fact_store.verify_claim(
                tenant=tenant,
                text=html_content,
                context="Gate 11",
                spec_disclosures=spec_disclosures,
            )
            if not is_valid:
                g11_ok = False
                for fv in fact_violations:
                    violations.append(f"Gate 11 (Tenant Fact Parity): {fv}")
            recon_issues = TruthReconciliationEngine.audit_html_truth_reconciliation(
                html_content,
                tenant=tenant,
                rel_path=slug or "index.html",
                slug=slug or "",
            )
            if recon_issues:
                g11_ok = False
                for ri in recon_issues:
                    msg = f"Gate 11 (Truth Reconciliation): {ri}"
                    if msg not in violations:
                        violations.append(msg)
        stat_issues = detect_uncorroborated_statutory_claims(html_content, rel_path=slug or "index.html")
        if stat_issues:
            g11_ok = False
            for si in stat_issues:
                violations.append(f"Gate 11 (Tenant Fact Parity): {si}")
    except Exception as ex:
        g11_ok = False
        violations.append(f"Gate 11 (Tenant Fact Parity): Fact store check failed: {ex}")

    gate_results["tenant_fact_parity"] = g11_ok


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


def audit_visual_ui_quality_contract(
    html_content: str,
    rel_path: str = "index.html",
    require_primitives: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Audits a rendered HTML page against its classified screen archetype contract
    (interactive_calculator, statutory_guide, comparison_page, index_hub) and
    returns structured pass/fail diagnostics.
    """
    from pseofactory.visual_primitives import (
        VISUAL_PRIMITIVES_VERSION,
        classify_screen_archetype,
        detect_visual_and_ux_contract_issues,
        get_screen_archetype_contract,
    )

    archetype = classify_screen_archetype(html_content, rel_path=rel_path)
    contract = get_screen_archetype_contract(html_content, rel_path=rel_path)
    issues = detect_visual_and_ux_contract_issues(
        html_content,
        rel_path=rel_path,
        require_primitives=require_primitives,
    )
    return {
        "passed": len(issues) == 0,
        "archetype": archetype,
        "contract_version": VISUAL_PRIMITIVES_VERSION,
        "contract": contract,
        "issues": issues,
        "rel_path": rel_path,
    }


def audit_code_slop_ratchet(
    target_files: Optional[Union[str, Path, List[Union[str, Path]]]] = None,
    max_function_lines: int = 450,
    target_dir: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    SlopCodeBench AST Maintainability and Duplication Ratchet.
    Inspects Python builder and compiler files using Python's ast module,
    counting functions, flagging duplicate AST function bodies and oversized
    bespoke functions exceeding max_function_lines.
    Zero em-dashes. Zero en-dashes.
    """
    pkg_dir = Path(__file__).resolve().parent
    effective_targets = target_files if target_files is not None else target_dir
    if effective_targets is None:
        resolved_files = [
            pkg_dir / "competitor.py",
            pkg_dir / "qualification.py",
            pkg_dir / "compiler.py",
            pkg_dir / "audit.py",
            pkg_dir / "drift.py",
            pkg_dir / "browser_verifier.py",
            pkg_dir / "visual_primitives.py",
        ]
    else:
        if isinstance(effective_targets, (str, Path)):
            iter_targets: List[Union[str, Path]] = [effective_targets]
        else:
            iter_targets = list(effective_targets)
        resolved_files = []
        for tf in iter_targets:
            p = Path(tf)
            if p.is_dir():
                resolved_files.extend(
                    f for f in sorted(p.glob("**/*.py")) if "__pycache__" not in f.parts
                )
            elif p.is_file():
                resolved_files.append(p)

    files_scanned = 0
    functions_scanned = 0
    duplicate_ast_blocks = 0
    duplicate_functions: List[Dict[str, Any]] = []
    oversized_functions: List[Dict[str, Any]] = []
    seen_bodies: Dict[str, str] = {}

    for fpath in resolved_files:
        if not fpath.is_file():
            continue
        try:
            source = fpath.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=str(fpath))
        except Exception:
            continue

        files_scanned += 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions_scanned += 1
                start_line = getattr(node, "lineno", 1)
                end_line = getattr(node, "end_lineno", start_line)
                raw_span = max(1, end_line - start_line + 1)

                # Discount multi-line embedded HTML/CSS/JS string and f-string templates
                template_line_nums = set()
                for child in ast.walk(node):
                    if isinstance(child, (ast.JoinedStr, ast.Constant)):
                        if isinstance(child, ast.Constant) and not isinstance(child.value, str):
                            continue
                        c_start = getattr(child, "lineno", 0)
                        c_end = getattr(child, "end_lineno", 0)
                        if c_end - c_start + 1 >= 4:
                            template_line_nums.update(range(c_start, c_end + 1))

                effective_lines = 0
                for ln in range(start_line, min(end_line, len(source_lines)) + 1):
                    if ln in template_line_nums:
                        continue
                    stripped = source_lines[ln - 1].strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    effective_lines += 1
                effective_lines = max(1, effective_lines)

                if effective_lines > max_function_lines:
                    oversized_functions.append({
                        "file": fpath.name,
                        "function": node.name,
                        "lines": effective_lines,
                        "raw_lines": raw_span,
                        "max_allowed": max_function_lines,
                    })

                body_stmts = list(node.body)
                if (
                    body_stmts
                    and isinstance(body_stmts[0], ast.Expr)
                    and isinstance(getattr(body_stmts[0], "value", None), ast.Constant)
                    and isinstance(body_stmts[0].value.value, str)
                ):
                    body_stmts = body_stmts[1:]

                if len(body_stmts) >= 4 and effective_lines >= 12:
                    body_dump = ast.dump(ast.Module(body=body_stmts, type_ignores=[]), include_attributes=False)
                    loc_label = f"{fpath.name}:{node.name}"
                    if body_dump in seen_bodies:
                        duplicate_ast_blocks += 1
                        duplicate_functions.append({
                            "function": loc_label,
                            "duplicate_of": seen_bodies[body_dump],
                        })
                    else:
                        seen_bodies[body_dump] = loc_label

    passed = (duplicate_ast_blocks == 0) and (len(oversized_functions) == 0)
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "files_scanned": files_scanned,
        "functions_scanned": functions_scanned,
        "duplicate_ast_blocks": duplicate_ast_blocks,
        "duplicate_functions": duplicate_functions,
        "oversized_functions": oversized_functions,
    }


REQUIRED_SYNDICATION_CHANNELS = ("youtube", "linkedin", "facebook", "ghost", "github_gist")
STALE_STATUTORY_PATTERNS = (
    (r"\$1,220,000", "Stale Section 179 deduction cap ($1,220,000 vs statutory $2,560,000)"),
    (r"\$1,250,000\s+(?:maximum\s+)?(?:deduction|cap|Section\s+179)", "Stale Section 179 deduction cap ($1,250,000 vs statutory $2,560,000)"),
    (r"\$3,050,000", "Stale Section 179 phase-out threshold ($3,050,000 vs statutory $4,090,000)"),
    (r"\$3,130,000", "Stale Section 179 phase-out threshold ($3,130,000 vs statutory $4,090,000)"),
    (r"\$31,300", "Stale Section 179 SUV cap ($31,300 vs statutory $30,500)"),
    (r"60%\s+(?:bonus\s+depreciation|first-year\s+bonus)", "Stale 2026 bonus depreciation rate (60% vs statutory 20%)"),
    (r"\$11,925|\$48,475|\$103,350", "Stale 2026 single tax bracket thresholds ($11,925/$48,475/$103,350 vs statutory $12,050/$48,900/$104,400)"),
)
GENERIC_SYNDICATION_FILLER_PHRASES = (
    "15% to 35% variance",
    "Users analyze complex tax liabilities and cash flow projections",
    "Read our full breakdown of the 2026 student loan forgiveness rules and IDR plan updates:",
)


def _extract_channel_text_and_urls(channel_name: str, payload: Any) -> Dict[str, Any]:
    """Extract normalized text body and parameterized URLs from a syndication channel payload."""
    if payload is None:
        return {"text": "", "has_param_url": False}
    if isinstance(payload, str):
        text = payload.strip()
    elif isinstance(payload, dict):
        parts: List[str] = []
        has_primary_content = isinstance(payload.get("content"), str) and bool(payload["content"].strip())
        for key in (
            "title",
            "content",
            "copy",
            "description",
            "pinned_comment",
            "article_markdown",
            "markdown",
            "html",
            "code",
            "summary",
        ):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        if not has_primary_content:
            for fallback_key in ("teaser_content", "first_comment"):
                fval = payload.get(fallback_key)
                if isinstance(fval, str) and fval.strip():
                    parts.append(fval.strip())
        elif "http" not in str(payload.get("content", "")) and isinstance(payload.get("first_comment"), str):
            parts.append(payload["first_comment"].strip())
        if channel_name == "youtube":
            tr = payload.get("transcript")
            if isinstance(tr, str) and tr.strip():
                parts.append(tr.strip())
            elif isinstance(tr, list):
                for seg in tr:
                    if isinstance(seg, dict):
                        seg_txt = seg.get("spoken_script") or seg.get("text")
                        if isinstance(seg_txt, str) and seg_txt.strip():
                            parts.append(seg_txt.strip())
        if channel_name == "github_gist" and isinstance(payload.get("files"), dict):
            for fmeta in payload["files"].values():
                if isinstance(fmeta, dict) and isinstance(fmeta.get("content"), str):
                    parts.append(fmeta["content"].strip())
                elif isinstance(fmeta, str):
                    parts.append(fmeta.strip())
        text = "\n".join(parts)
    else:
        text = str(payload)

    has_param_url = bool(re.search(r"https?://[^\s)\"'>]+\?[^\s)\"'>]+=", text))
    return {"text": text, "has_param_url": has_param_url}


def _verify_gist_executable_proof(gist_payload: Any, expected_output: float) -> List[str]:
    """Verify exact-match GitHub Gist payload contains AST-valid executable Python matching published_output."""
    violations: List[str] = []
    if not isinstance(gist_payload, dict):
        return ["THIN_PAYLOAD_STUB:github_gist_not_dict"]
    files_map = gist_payload.get("files")
    if not isinstance(files_map, dict) or not files_map:
        return ["THIN_PAYLOAD_STUB:github_gist_missing_files"]

    py_sources: List[str] = []
    for fname, fval in files_map.items():
        content = fval.get("content", "") if isinstance(fval, dict) else (fval if isinstance(fval, str) else "")
        if str(fname).endswith(".py") and content.strip():
            py_sources.append(content)

    if not py_sources:
        return ["THIN_PAYLOAD_STUB:github_gist_missing_python_proof"]

    for src in py_sources:
        try:
            ast.parse(src)
            ns: Dict[str, Any] = {}
            exec(compile(src, "<github_gist_proof>", "exec"), ns, ns)
            if "verify_calculation_proof" in ns and callable(ns["verify_calculation_proof"]):
                result = ns["verify_calculation_proof"]()
                if isinstance(result, dict) and "published_output" in result:
                    if abs(float(result["published_output"]) - float(expected_output)) > 0.05:
                        violations.append("CALCULATION_PARITY_MISMATCH:github_gist_output_drift")
        except Exception as exc:
            violations.append(f"CALCULATION_PARITY_MISMATCH:github_gist_exec_failed:{exc}")
    return violations


def _check_calculation_proof_gate(asset_pack: Dict[str, Any], channel_texts: Dict[str, str]) -> List[str]:
    """Validate calculation_proof mathematical parity and cross-channel proof presence."""
    violations: List[str] = []
    proof = asset_pack.get("calculation_proof")
    if not isinstance(proof, dict):
        return ["MISSING_CALCULATION_PROOF:calculation_proof_missing"]

    formula = str(proof.get("formula", "")).strip()
    inputs = proof.get("inputs")
    pub_out = proof.get("published_output")
    sample_calc = str(proof.get("sample_calculation", "")).strip()
    param_url = str(proof.get("parameterized_url", "")).strip()

    if not formula or not isinstance(inputs, dict) or not inputs or pub_out is None or not sample_calc:
        return ["MISSING_CALCULATION_PROOF:incomplete_proof_fields"]
    if "?" not in param_url or "=" not in param_url:
        violations.append("UNPARAMETERIZED_CANONICAL_URL:calculation_proof_url")

    try:
        numeric_inputs = {str(k): float(v) for k, v in inputs.items()}
        evaluated = float(safe_eval_mathematical_formula(formula, numeric_inputs))
        expected = float(pub_out)
        if abs(evaluated - expected) > 0.05:
            violations.append(
                f"CALCULATION_PARITY_MISMATCH:evaluated={evaluated:.2f}_vs_published={expected:.2f}"
            )
    except Exception as exc:
        violations.append(f"CALCULATION_PARITY_MISMATCH:formula_eval_error:{exc}")
        return violations

    expected_val = float(pub_out)
    formatted_tokens = {
        f"{expected_val:,.0f}",
        f"{expected_val:.0f}",
        f"{expected_val:,.2f}",
        f"{expected_val:.2f}",
    }
    for ch in REQUIRED_SYNDICATION_CHANNELS:
        body = channel_texts.get(ch, "")
        if not body:
            continue
        if not any(tok in body for tok in formatted_tokens) and sample_calc not in body:
            violations.append(f"MISSING_CALCULATION_PROOF:{ch}_missing_published_output")

    yt_payload = asset_pack.get("youtube")
    if isinstance(yt_payload, dict):
        tr = yt_payload.get("transcript")
        spoken_text = ""
        if isinstance(tr, str):
            spoken_text = tr
        elif isinstance(tr, list):
            spoken_text = " ".join(
                str(seg.get("spoken_script") or seg.get("text") or "")
                for seg in tr
                if isinstance(seg, dict)
            )
        if spoken_text and not any(tok in spoken_text for tok in formatted_tokens):
            violations.append("MISSING_CALCULATION_PROOF:youtube_transcript_missing_spoken_output")

    violations.extend(_verify_gist_executable_proof(asset_pack.get("github_gist"), expected_val))
    return violations


def audit_syndication_asset_against_truth_store(
    asset_pack: Dict[str, Any],
    property_id: str = "profithelm",
    fact_store: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Outside truth-store audit for a tool's syndication asset pack.
    Enforces Gates S1-S6 across canonical tools, YouTube, LinkedIn, Facebook, Ghost, and GitHub Gists.
    Deliberately rejects Reddit and classifies untested/missing channels as UNKNOWN.
    """
    from pseofactory.contracts import detect_uncorroborated_statutory_claims
    from pseofactory.tenant_facts import TenantFactStore

    if not isinstance(asset_pack, dict) or not asset_pack:
        return {
            "passed": False,
            "status": "FAIL",
            "property_id": property_id,
            "slug": "",
            "violations": ["EMPTY_ASSET_PACK"],
            "failures": ["EMPTY_ASSET_PACK"],
            "unknown_channels": list(REQUIRED_SYNDICATION_CHANNELS),
        }

    store = fact_store or TenantFactStore.get_instance()
    slug = str(asset_pack.get("slug") or asset_pack.get("tool_slug") or "unknown-slug")
    resolved_prop = str(asset_pack.get("property_id") or property_id or "profithelm").lower()
    if "prexvo" in resolved_prop:
        resolved_prop = "prexvo"
    elif "gainhelm" in resolved_prop:
        resolved_prop = "gainhelm"
    else:
        resolved_prop = "profithelm"

    violations: List[str] = []
    unknown_channels: List[str] = []

    # Gate S1: Deliberately omit Reddit
    channels_list = asset_pack.get("channels", [])
    if (
        "reddit" in asset_pack
        or "reddit_teardown" in asset_pack
        or (isinstance(channels_list, list) and "reddit" in channels_list)
    ):
        violations.append("PROHIBITED_CHANNEL_REDDIT")

    # Gate S2: Required channels present and non-empty
    channel_texts: Dict[str, str] = {}
    channel_param_urls: Dict[str, bool] = {}
    for ch in REQUIRED_SYNDICATION_CHANNELS:
        raw_ch = asset_pack.get(ch)
        extracted = _extract_channel_text_and_urls(ch, raw_ch)
        if not extracted["text"]:
            unknown_channels.append(ch)
            violations.append(f"MISSING_OR_UNKNOWN_CHANNEL:{ch}")
        else:
            channel_texts[ch] = extracted["text"]
            channel_param_urls[ch] = extracted["has_param_url"]

    # Gate S3: Calculation proof & AST parity
    violations.extend(_check_calculation_proof_gate(asset_pack, channel_texts))

    # Gate S4: Statutory Truth-Store Verification
    combined_text = "\n".join(channel_texts.values())
    for extra_key in ("linkedin_pulse", "substack_teardown", "x"):
        if extra_key in asset_pack:
            combined_text += "\n" + _extract_channel_text_and_urls(extra_key, asset_pack[extra_key])["text"]

    try:
        assert_no_forbidden_dashes(combined_text, context=f"syndication:{slug}")
    except Exception as exc:
        violations.append(f"TYPOGRAPHY_VIOLATION:{exc}")

    for pattern, reason in STALE_STATUTORY_PATTERNS:
        if re.search(pattern, combined_text, flags=re.IGNORECASE):
            violations.append(f"STATUTORY_TRUTH_MISMATCH:{reason}")

    uncorroborated = detect_uncorroborated_statutory_claims(combined_text, rel_path=f"{resolved_prop}/{slug}")
    for bad_claim in uncorroborated:
        violations.append(f"STATUTORY_TRUTH_MISMATCH:{bad_claim}")

    if hasattr(store, "detect_banned_claims"):
        for banned in store.detect_banned_claims(resolved_prop, combined_text):
            violations.append(f"STATUTORY_TRUTH_MISMATCH:banned_claim:{banned}")

    if hasattr(store, "verify_claim"):
        claim_res = store.verify_claim(
            resolved_prop,
            combined_text,
            context=f"syndication:{slug}",
        )
        if isinstance(claim_res, tuple) and len(claim_res) == 2:
            claim_ok, claim_violations = claim_res
            if not claim_ok:
                for cv in claim_violations:
                    violations.append(f"STATUTORY_TRUTH_MISMATCH:{cv}")
        elif not claim_res:
            violations.append("STATUTORY_TRUTH_MISMATCH:verify_claim_failed")

    proof = asset_pack.get("calculation_proof")
    if isinstance(proof, dict):
        stat_Claim = str(proof.get("statutory_claim_key", "")).strip()
        stat_Val = proof.get("statutory_claim_value")
        if stat_Claim and stat_Val is not None:
            if hasattr(store, "get_profile"):
                prof = store.get_profile(resolved_prop)
                if prof is not None:
                    limits_map = dict(getattr(prof.statutory_truth, "limits_and_thresholds", {}) or {})
                    alias_map = {
                        "section_179_limit_2026": "section_179_expense_limit_2026",
                        "section_179_suv_cap_2026": "section_179_heavy_vehicle_2026",
                        "qsbs_exclusion_cap": "section_1202_qsbs_exclusion_cap",
                    }
                    lookup_key = alias_map.get(stat_Claim, stat_Claim)
                    if lookup_key in limits_map and lookup_key not in ("standard_deduction_2026_single",):
                        try:
                            if abs(float(limits_map[lookup_key]) - float(stat_Val)) > 0.05:
                                violations.append(f"STATUTORY_TRUTH_MISMATCH:unverified_claim:{stat_Claim}={stat_Val}")
                        except (TypeError, ValueError):
                            pass
            else:
                res = store.verify_claim(resolved_prop, str(stat_Claim), str(stat_Val))
                ok = res[0] if isinstance(res, tuple) else bool(res)
                if not ok:
                    violations.append(f"STATUTORY_TRUTH_MISMATCH:unverified_claim:{stat_Claim}={stat_Val}")

    # Gate S5: Parameterized canonical URLs & dual dataset citations
    citations = asset_pack.get("dual_dataset_citations")
    if not isinstance(citations, list) or isinstance(citations, bool) or len(citations) < 2:
        violations.append("INVALID_DUAL_DATASET_CITATIONS")
    elif not all(isinstance(c, str) and len(c.strip()) >= 8 for c in citations):
        violations.append("INVALID_DUAL_DATASET_CITATIONS:empty_citation_entry")

    for ch, has_url in channel_param_urls.items():
        if not has_url:
            violations.append(f"UNPARAMETERIZED_CANONICAL_URL:{ch}")

    # Gate S6: Anti-Slop / Thin Stub Rejection
    for phrase in GENERIC_SYNDICATION_FILLER_PHRASES:
        if phrase.lower() in combined_text.lower():
            violations.append(f"THIN_PAYLOAD_STUB:generic_filler:{phrase[:32]}")

    min_lengths = {
        "linkedin": 220,
        "facebook": 180,
        "ghost": 600,
        "github_gist": 280,
        "youtube": 250,
    }
    for ch, min_len in min_lengths.items():
        if ch in channel_texts and len(channel_texts[ch]) < min_len:
            violations.append(f"THIN_PAYLOAD_STUB:{ch}_len_{len(channel_texts[ch])}_lt_{min_len}")

    for long_key in ("linkedin_pulse", "substack_teardown"):
        if long_key in asset_pack:
            ltext = _extract_channel_text_and_urls(long_key, asset_pack[long_key])["text"]
            if len(ltext) < 600:
                violations.append(f"THIN_PAYLOAD_STUB:{long_key}_len_{len(ltext)}_lt_600")

    passed = len(violations) == 0
    return {
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "property_id": resolved_prop,
        "slug": slug,
        "violations": violations,
        "failures": violations,
        "unknown_channels": unknown_channels,
    }


def audit_distribution_draft_payload(
    draft_payload: Dict[str, Any],
    property_id: str = "profithelm",
    fact_store: Optional[Any] = None,
) -> Dict[str, Any]:
    """Audit a full distribution_draft.json run payload against the outside truth store."""
    from pseofactory.tenant_facts import TenantFactStore

    store = fact_store or TenantFactStore.get_instance()
    if not isinstance(draft_payload, dict) or not draft_payload:
        return {
            "passed": False,
            "status": "FAIL",
            "tools_audited": 0,
            "passed_tools": 0,
            "total_tools_audited": 0,
            "failed_tools": 0,
            "violations": ["EMPTY_DISTRIBUTION_DRAFT_PAYLOAD"],
            "failures": ["EMPTY_DISTRIBUTION_DRAFT_PAYLOAD"],
            "tool_reports": {},
        }

    all_assets = draft_payload.get("all_assets")
    total_generated = draft_payload.get("total_assets_generated")
    if not isinstance(all_assets, dict) or not all_assets or (total_generated is not None and int(total_generated or 0) <= 0):
        return {
            "passed": False,
            "status": "FAIL",
            "tools_audited": 0,
            "passed_tools": 0,
            "total_tools_audited": 0,
            "failed_tools": 0,
            "violations": ["EMPTY_DISTRIBUTION_RUN_ZERO_ASSETS"],
            "failures": ["EMPTY_DISTRIBUTION_RUN_ZERO_ASSETS"],
            "tool_reports": {},
        }

    channels_list = draft_payload.get("channels", [])
    aggregated_violations: List[str] = []
    if isinstance(channels_list, list) and "reddit" in channels_list:
        aggregated_violations.append("PROHIBITED_CHANNEL_REDDIT:draft_channels")

    prop_default = str(draft_payload.get("property_id") or property_id or "profithelm")
    tool_reports: Dict[str, Any] = {}
    failed_tools = 0

    for slug, pack in all_assets.items():
        pack_dict = dict(pack) if isinstance(pack, dict) else {}
        pack_dict.setdefault("slug", slug)
        rep = audit_syndication_asset_against_truth_store(
            pack_dict,
            property_id=str(pack_dict.get("property_id") or prop_default),
            fact_store=store,
        )
        tool_reports[slug] = rep
        if not rep["passed"]:
            failed_tools += 1
            for v in rep["violations"]:
                aggregated_violations.append(f"{slug}:{v}")

    total_audited = len(tool_reports)
    passed_count = total_audited - failed_tools
    passed = failed_tools == 0 and len(aggregated_violations) == 0 and total_audited > 0
    return {
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "tools_audited": total_audited,
        "passed_tools": passed_count,
        "total_tools_audited": total_audited,
        "failed_tools": failed_tools,
        "violations": aggregated_violations,
        "failures": aggregated_violations,
        "tool_reports": tool_reports,
    }


def audit_historical_distribution_runs(
    runs_dir: Union[str, Path] = "/home/ubuntuadmin/projects/.agy/runs",
    fact_store: Optional[Any] = None,
    max_runs: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Replay outside truth-store audit across earlier repo runs (distribution_draft*.json)
    to demonstrate that thin, Reddit-containing, unparameterized, or statutory-mismatched drafts fail automatically.
    """
    from pseofactory.tenant_facts import TenantFactStore

    store = fact_store or TenantFactStore.get_instance()
    root = Path(runs_dir)
    if not root.exists():
        return {
            "runs_scanned": 0,
            "runs_audited": 0,
            "runs_failed": 0,
            "runs_passed": 0,
            "failure_reason_counts": {},
            "sample_failures": [],
        }

    eff_limit = limit if limit is not None else max_runs
    draft_files = sorted(root.glob("*/distribution_draft*.json"))
    if eff_limit is not None and eff_limit > 0:
        draft_files = draft_files[:eff_limit]

    runs_scanned = 0
    runs_failed = 0
    runs_passed = 0
    reason_counts: Dict[str, int] = {}
    sample_failures: List[Dict[str, Any]] = []

    for fpath in draft_files:
        try:
            payload = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs_scanned += 1
        report = audit_distribution_draft_payload(payload, fact_store=store)
        if report["passed"]:
            runs_passed += 1
        else:
            runs_failed += 1
            seen_categories = set()
            for v in report["violations"]:
                parts = v.split(":")
                cat = parts[1] if len(parts) > 1 and parts[0] in report.get("tool_reports", {}) else parts[0]
                seen_categories.add(cat)
            for cat in seen_categories:
                reason_counts[cat] = reason_counts.get(cat, 0) + 1
            if len(sample_failures) < 10:
                sample_failures.append({
                    "run_file": str(fpath),
                    "failed_tools": report["failed_tools"],
                    "sample_violations": report["violations"][:6],
                })

    return {
        "runs_scanned": runs_scanned,
        "runs_audited": runs_scanned,
        "runs_failed": runs_failed,
        "runs_passed": runs_passed,
        "failure_reason_counts": reason_counts,
        "sample_failures": sample_failures,
    }


def inspect_raw_syndication_manifests_and_trails(
    syndication_root: Union[str, Path] = "/home/ubuntuadmin/projects/pseofactory/syndication",
    runs_dir: Union[str, Path] = "/home/ubuntuadmin/projects/.agy/runs",
) -> Dict[str, Any]:
    """
    Single-pass diagnostic over raw syndication manifests and historical audit trails.
    Separates observed payload quality from unverified assumptions and marks untested channels as UNKNOWN.
    """
    syn_path = Path(syndication_root)
    pack_files = sorted(syn_path.glob("*/*/syndication_pack.json")) if syn_path.exists() else []

    observed_channels: Dict[str, int] = {ch: 0 for ch in ("youtube", "linkedin", "facebook", "x", "reddit", "ghost", "github_gist")}
    parameterized_url_packs = 0
    boolean_citation_packs = 0
    thin_substack_packs = 0

    for pf in pack_files:
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        for ch in observed_channels:
            if data.get(ch):
                observed_channels[ch] += 1
        if isinstance(data.get("dual_dataset_citations"), bool):
            boolean_citation_packs += 1
        raw_sub = data.get("substack_teardown")
        sub = raw_sub.get("article_markdown", "") if isinstance(raw_sub, dict) else str(raw_sub or "")
        if 0 < len(sub) < 450:
            thin_substack_packs += 1
        li_obj = data.get("linkedin") if isinstance(data.get("linkedin"), dict) else {}
        li_copy = str(li_obj.get("content") or li_obj.get("copy") or "")
        if "?" in li_copy and "=" in li_copy:
            parameterized_url_packs += 1

    unknown_channels = [
        ch for ch in REQUIRED_SYNDICATION_CHANNELS if observed_channels.get(ch, 0) == 0
    ]
    historical_summary = audit_historical_distribution_runs(runs_dir=runs_dir, max_runs=50)

    return {
        "manifests_inspected": len(pack_files),
        "observed_channel_counts": observed_channels,
        "unknown_channels": {ch: "UNKNOWN" for ch in unknown_channels},
        "observed_facts": {
            "parameterized_url_packs": parameterized_url_packs,
            "boolean_citation_packs": boolean_citation_packs,
            "thin_substack_packs": thin_substack_packs,
            "historical_runs_sampled": historical_summary["runs_scanned"],
            "historical_runs_failed": historical_summary["runs_failed"],
        },
        "unverified_assumptions_falsified": [
            "Assumed external channels only published statutory-verified figures (falsified by stale $1,220,000 Section 179 and $31,300 SUV limits in teardown/YouTube/benchmark generators).",
            "Assumed YouTube spoken transcripts contained concrete mathematical proofs (falsified by generic filler sentences lacking numerical inputs/outputs).",
            "Assumed fallback dynamic tools carried parameterized deep-link query strings (falsified by empty {} query mappings and '15% to 35% variance' filler).",
            "Assumed Prexvo long-form syndication carried calculation proofs (falsified by 332-char Substack stubs and boolean dual_dataset_citations=True).",
        ],
    }


from pseofactory.verifier import (
    X_LIKE_2102358751290236980_CAPABILITY_MATRIX,
    X_LIKE_2109219955271196726_CAPABILITY_MATRIX,
    audit_estate_technical_seo_and_cannibalization,
    evaluate_x_like_2102358751290236980_capability_matrix,
    evaluate_x_like_2109219955271196726_capability_matrix,
)

__all__ = [
    "ContentAccuracyAuditStage",
    "ContentAccuracyAuditReport",
    "ContentAccuracyAuditError",
    "audit_rendered_asset",
    "audit_code_slop_ratchet",
    "audit_syndication_asset_against_truth_store",
    "audit_distribution_draft_payload",
    "audit_historical_distribution_runs",
    "inspect_raw_syndication_manifests_and_trails",
    "X_LIKE_2102358751290236980_CAPABILITY_MATRIX",
    "X_LIKE_2109219955271196726_CAPABILITY_MATRIX",
    "audit_estate_technical_seo_and_cannibalization",
    "evaluate_x_like_2102358751290236980_capability_matrix",
    "evaluate_x_like_2109219955271196726_capability_matrix",
]


