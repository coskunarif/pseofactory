"""
End-to-End Truth Engine v2 Break-It & Hardening Test Suite.

Proves with real code execution (zero mocks of UnifiedTruthGate):
1. All 4 real Truth Packs (profithelm, prexvo, gainhelm, lienbond) validate
   cleanly with zero expired entries and 100% Python + Node.js formula
   test-vector pass rate.
2. Synthetic 5th site (site50_no_pack) FAILS CLOSED across load_truth_pack,
   UnifiedTruthGate.audit_estate, TenantFactStore.verify_claim, and
   GitOpsCoordinator.dispatch_to_shipper.
3. Break-it mutations each trigger HARD FAIL on UnifiedTruthGate and freeze
   deploy via GitOpsCoordinator.dispatch_to_shipper (TRUTH_GATE_FAILED):
   - Injecting "30.6% reduction in statutory capital drag"
   - Injecting stale JS constant `const tcjaStdDed = { single: 15000 }`
   - Injecting wrong calculator JS math (diverging from Python formula in Node.js)
   - Injecting expired `expires_at: "2020-01-01"` in a Truth Pack
   - Injecting `#val-total_federal_tax` widget onto a QBI 199A tool page
   - Injecting Contractor License Bond $375 formula onto `bid-bond-calculator`
   - Injecting `IRC Section 3111` onto a LienBond workers' comp page
   - Injecting dead link `/tools/surety-bond-cost-calculator-philippines/` or
     `R&amp;D` into `llms.txt`
   - Injecting a quarantined failing asset into MaintenanceLifecycle Stage 6
     (proving it STILL freezes that site's deploy instead of shipping)
4. AI Intake + Deterministic Proof gate (run_official_source_intake) rejects
   fabricated verbatim quotes, non-official URLs, and dual-pass numeric
   disagreements with FREEZE_SITE, and approves exact matching official .gov
   extractions with SHA-256 quote proof.

Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pseofactory.gitops import GitOpsCoordinator
from pseofactory.maintenance import (
    AssetDriftRecord,
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    DriftReason,
    MaintenanceLifecycle,
    RefactorCascadeEngine,
    TenantRegistry,
)
from pseofactory.tenant_facts import TenantFactStore
from pseofactory.truth_gate import UnifiedTruthGate
from pseofactory.truth_intake import (
    check_truth_pack_freshness,
    run_official_source_intake,
)
from pseofactory.truth_pack import (
    DEFAULT_TRUTH_PACKS_DIR,
    TruthPackExpiredError,
    TruthPackMissingError,
    compute_quote_sha256,
    discover_truth_pack_ids,
    load_truth_pack,
    safe_eval_formula,
    validate_truth_pack,
)


PROFITHELM_DISCLOSURE = (
    "Treasury Circular 230 Notice: ProfitHelm calculators provide deterministic "
    "statutory modeling for educational and planning purposes only and do not "
    "constitute individualized tax, legal, or accounting advice. Consult a "
    "licensed CPA or tax attorney before filing."
)

LIENBOND_DISCLOSURE = (
    "Underwriting & Statutory Notice: LienBond is not a licensed attorney, law "
    "firm, admitted surety underwriter, or licensed insurance producer. Bond "
    "premiums, EMR impacts, and statutory lien calculations are informational "
    "underwriting estimates only; consult qualified legal counsel and a "
    "licensed surety broker before binding coverage or recording liens."
)


def _eval_js_expression_in_node(js_expr: str, variables: Dict[str, Any]) -> float:
    node_bin = shutil.which("node")
    assert node_bin is not None, "Node.js binary is required for E2E JS math parity proof"
    decl_lines = [f"const {k} = {json.dumps(v)};" for k, v in variables.items()]
    script = "\n".join(decl_lines) + f"\nconst __out = ({js_expr});\nconsole.log(JSON.stringify(Number(__out)));\n"
    proc = subprocess.run([node_bin, "-e", script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node.js execution failed: {proc.stderr}\nScript:\n{script}"
    return float(json.loads(proc.stdout.strip()))


def _init_git_repo_with_dist(repo_dir: Path, property_id: str, domain: str) -> Path:
    dist_dir = repo_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": property_id,
                "brand_name": property_id.capitalize(),
                "domain": domain,
                "canonical_base": f"https://{domain}",
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@pseofactory.local"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Truth E2E"], cwd=repo_dir, check=True, capture_output=True)
    return dist_dir


def _build_clean_profithelm_estate(repo_dir: Path) -> Path:
    dist_dir = _init_git_repo_with_dist(repo_dir, "profithelm", "profithelm.com")
    tool_dir = dist_dir / "tools" / "section-179-heavy-suv-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>ProfitHelm Tax Engine</title>"
        "<link rel=\"canonical\" href=\"https://profithelm.com/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"WebSite\",\"name\":\"ProfitHelm\",\"url\":\"https://profithelm.com\"}"
        "</script>"
        "</head><body><main>"
        "<h1>ProfitHelm Tax Engine</h1>"
        f"<p class=\"disclosure\">{PROFITHELM_DISCLOSURE}</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    ph_pack = load_truth_pack("profithelm")
    suv_spec = ph_pack.formulas["section_179_heavy_suv_plus_bonus_2026"]
    manifest = {
        "formula": suv_spec.expression,
        "inputs": dict(suv_spec.variables),
        "published_output": suv_spec.expected_baseline_output,
    }
    (tool_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>2026 Section 179 Heavy SUV Calculator | ProfitHelm</title>"
        "<link rel=\"canonical\" href=\"https://profithelm.com/tools/section-179-heavy-suv-calculator/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"SoftwareApplication\",\"name\":\"Section 179 Heavy SUV Calculator\"}"
        "</script>"
        f"<script id=\"calculation-manifest\" type=\"application/json\">{json.dumps(manifest)}</script>"
        "</head><body><main>"
        "<h1>2026 Section 179 Heavy SUV Calculator</h1>"
        "<p>Models heavy SUV expensing under IRC Section 179 and 26 U.S.C. 168(k). "
        "Primary statutory source: <a href=\"https://www.irs.gov/publications/p946\" "
        "rel=\"noopener noreferrer\" target=\"_blank\">IRS Publication 946</a>.</p>"
        "<form class=\"calculator-form\">"
        "<input id=\"input-equipment_cost\" name=\"equipment_cost\" value=\"85000\">"
        "<input id=\"input-business_use_pct\" name=\"business_use_pct\" value=\"0.8\">"
        "<input id=\"input-is_heavy_suv\" name=\"is_heavy_suv\" value=\"1\">"
        "<input id=\"input-bonus_pct\" name=\"bonus_pct\" value=\"100\">"
        "<span id=\"total-first-year-deduction\" class=\"output-value\">$68,000.00</span>"
        "</form>"
        f"<p class=\"disclosure\">{PROFITHELM_DISCLOSURE}</p>"
        "<script>"
        "function recompute() {"
        "  var equipment_cost = Number(document.getElementById('input-equipment_cost').value || 0);"
        "  var business_use_pct = Number(document.getElementById('input-business_use_pct').value || 0);"
        "  var is_heavy_suv = Number(document.getElementById('input-is_heavy_suv').value || 0);"
        "  var bonus_pct = Number(document.getElementById('input-bonus_pct').value || 0);"
        f"  var val = {suv_spec.js_expression};"
        "  document.getElementById('total-first-year-deduction').textContent = '$' + val.toFixed(2);"
        "}"
        "document.querySelector('form').addEventListener('input', recompute);"
        "document.addEventListener('DOMContentLoaded', recompute);"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )

    (dist_dir / "llms.txt").write_text(
        "# ProfitHelm\n"
        "> Deterministic 2026-2027 tax modeling calculators.\n"
        "- [Section 179 Heavy SUV Calculator](https://profithelm.com/tools/section-179-heavy-suv-calculator/)\n"
        f"\n{PROFITHELM_DISCLOSURE}\n",
        encoding="utf-8",
    )
    return dist_dir


def _build_clean_lienbond_estate(repo_dir: Path) -> Path:
    dist_dir = _init_git_repo_with_dist(repo_dir, "lienbond", "lienbond.com")
    bid_dir = dist_dir / "tools" / "bid-bond-calculator"
    wc_dir = dist_dir / "tools" / "workers-compensation-class-code-rate-calculator-by-state"
    bid_dir.mkdir(parents=True, exist_ok=True)
    wc_dir.mkdir(parents=True, exist_ok=True)

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>LienBond Surety &amp; Lien Engine</title>"
        "<link rel=\"canonical\" href=\"https://lienbond.com/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"WebSite\",\"name\":\"LienBond\",\"url\":\"https://lienbond.com\"}"
        "</script>"
        "</head><body><main>"
        "<h1>LienBond Surety Engine</h1>"
        f"<p class=\"disclosure\">{LIENBOND_DISCLOSURE}</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    lb_pack = load_truth_pack("lienbond")
    bid_spec = lb_pack.formulas["bid_bond"]
    bid_manifest = {
        "formula": bid_spec.expression,
        "inputs": dict(bid_spec.variables),
        "published_output": bid_spec.expected_baseline_output,
    }
    (bid_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>Bid Bond Calculator | LienBond</title>"
        "<link rel=\"canonical\" href=\"https://lienbond.com/tools/bid-bond-calculator/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"SoftwareApplication\",\"name\":\"Bid Bond Calculator\"}"
        "</script>"
        f"<script id=\"calculation-manifest\" type=\"application/json\">{json.dumps(bid_manifest)}</script>"
        "</head><body><main>"
        "<h1>Bid Bond Calculator</h1>"
        "<p>Primary statutory source: <a href=\"https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title40-section3131&amp;num=0&amp;edition=prelim\" "
        "rel=\"noopener noreferrer\" target=\"_blank\">40 U.S.C. 3131 (Miller Act)</a>.</p>"
        "<form class=\"calculator-form\">"
        "<input id=\"input-contract_bid_amount\" name=\"contract_bid_amount\" value=\"500000\">"
        "<input id=\"input-penal_sum_pct\" name=\"penal_sum_pct\" value=\"20\">"
        "<span id=\"bid-bond-penal-sum\" class=\"output-value\">$100,000.00</span>"
        "</form>"
        f"<p class=\"disclosure\">{LIENBOND_DISCLOSURE}</p>"
        "<script>"
        "function recompute() {"
        "  var contract_bid_amount = Number(document.getElementById('input-contract_bid_amount').value || 0);"
        "  var penal_sum_pct = Number(document.getElementById('input-penal_sum_pct').value || 0);"
        f"  var val = {bid_spec.js_expression};"
        "  document.getElementById('bid-bond-penal-sum').textContent = '$' + val.toFixed(2);"
        "}"
        "document.querySelector('form').addEventListener('input', recompute);"
        "document.addEventListener('DOMContentLoaded', recompute);"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )

    wc_spec = lb_pack.formulas["ncci_workers_comp_premium"]
    wc_manifest = {
        "formula": wc_spec.expression,
        "inputs": dict(wc_spec.variables),
        "published_output": wc_spec.expected_baseline_output,
    }
    (wc_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>Workers Comp Class Code Calculator | LienBond</title>"
        "<link rel=\"canonical\" href=\"https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"SoftwareApplication\",\"name\":\"Workers Comp Calculator\"}"
        "</script>"
        f"<script id=\"calculation-manifest\" type=\"application/json\">{json.dumps(wc_manifest)}</script>"
        "</head><body><main>"
        "<h1>Workers Comp Class Code Calculator</h1>"
        "<p>Calculates estimated NCCI Experience Rating Plan Manual workers compensation premium. "
        "Primary statutory source: <a href=\"https://www.dol.gov/agencies/owcp\" "
        "rel=\"noopener noreferrer\" target=\"_blank\">U.S. Department of Labor OWCP</a>.</p>"
        "<form class=\"calculator-form\">"
        "<input id=\"input-annual_payroll\" name=\"annual_payroll\" value=\"500000\">"
        "<input id=\"input-class_rate\" name=\"class_rate\" value=\"6.4\">"
        "<input id=\"input-emr_factor\" name=\"emr_factor\" value=\"1.15\">"
        "<input id=\"input-schedule_credit\" name=\"schedule_credit\" value=\"0.0\">"
        "<span id=\"net-wc-premium\" class=\"output-value\">$36,800.00</span>"
        "</form>"
        f"<p class=\"disclosure\">{LIENBOND_DISCLOSURE}</p>"
        "<script>"
        "function recompute() {"
        "  var annual_payroll = Number(document.getElementById('input-annual_payroll').value || 0);"
        "  var class_rate = Number(document.getElementById('input-class_rate').value || 0);"
        "  var emr_factor = Number(document.getElementById('input-emr_factor').value || 0);"
        "  var schedule_credit = Number(document.getElementById('input-schedule_credit').value || 0);"
        f"  var val = {wc_spec.js_expression};"
        "  document.getElementById('net-wc-premium').textContent = '$' + val.toFixed(2);"
        "}"
        "document.querySelector('form').addEventListener('input', recompute);"
        "document.addEventListener('DOMContentLoaded', recompute);"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )

    (dist_dir / "llms.txt").write_text(
        "# LienBond\n"
        "> Commercial surety bond and lien calculators.\n"
        "- [Bid Bond Calculator](https://lienbond.com/tools/bid-bond-calculator/)\n"
        "- [Workers Comp Calculator](https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/)\n"
        f"\n{LIENBOND_DISCLOSURE}\n",
        encoding="utf-8",
    )
    return dist_dir


def _assert_truth_gate_and_shipper_freeze(
    dist_dir: Path,
    repo_dir: Path,
    property_id: str,
    *,
    expected_code: str = "",
) -> List[Any]:
    gate = UnifiedTruthGate()
    report = gate.audit_estate(dist_dir, property_id, repo_root=repo_dir)
    assert not report.passed, f"Expected UnifiedTruthGate to fail for {property_id}, got PASS"
    assert report.status == "FAIL"
    if expected_code:
        codes = {v.code for v in report.violations}
        assert expected_code in codes, f"Expected violation code {expected_code!r}, got {sorted(codes)}: {report.summary()}"

    coord = GitOpsCoordinator(repo_path=repo_dir, dry_run=True)
    ship_res = coord.dispatch_to_shipper(property_id=property_id, dist_dir=dist_dir)
    assert ship_res.status == "TRUTH_GATE_FAILED", f"Expected TRUTH_GATE_FAILED, got {ship_res}"
    return report.violations


def test_all_four_truth_packs_validate_fresh_with_100pct_python_and_js_formula_parity() -> None:
    """
    Acceptance Criterion 1:
    All 4 real Truth Packs (profithelm, prexvo, gainhelm, lienbond) validate cleanly
    with zero expired entries and 100% Python + Node.js formula test-vector pass rate.
    """
    discovered = set(discover_truth_pack_ids())
    expected = {"profithelm", "prexvo", "gainhelm", "lienbond"}
    assert expected.issubset(discovered), f"Missing Truth Packs: {expected - discovered}"

    for pid in sorted(expected):
        pack = load_truth_pack(pid, allow_expired=False)
        errors = validate_truth_pack(pack, allow_expired=False)
        assert errors == [], f"TruthPack '{pid}' failed validation: {errors}"

        freshness = check_truth_pack_freshness(pack)
        assert freshness.status in ("FRESH", "EXPIRING_SOON"), f"TruthPack '{pid}' expired: {freshness}"
        assert freshness.expired_keys == []

        assert len(pack.formulas) > 0, f"TruthPack '{pid}' has no formulas"
        for fid, formula in pack.formulas.items():
            py_base = safe_eval_formula(formula.expression, formula.variables)
            assert abs(py_base - formula.expected_baseline_output) <= formula.tolerance, (
                f"{pid}.{fid} baseline mismatch: py={py_base} vs {formula.expected_baseline_output}"
            )
            js_base = _eval_js_expression_in_node(formula.js_expression, formula.variables)
            assert abs(js_base - formula.expected_baseline_output) <= formula.tolerance, (
                f"{pid}.{fid} JS baseline mismatch: js={js_base} vs {formula.expected_baseline_output}"
            )

            assert len(formula.test_vectors) >= 1, f"{pid}.{fid} missing test_vectors"
            for vec in formula.test_vectors:
                merged_vars = {**formula.variables, **dict(vec["inputs"])}
                tol = float(vec.get("tolerance") if vec.get("tolerance") is not None else formula.tolerance)
                py_val = safe_eval_formula(formula.expression, merged_vars)
                js_val = _eval_js_expression_in_node(formula.js_expression, merged_vars)
                exp_val = float(vec["expected"])
                assert abs(py_val - exp_val) <= tol, f"{pid}.{fid} Python vector {vec['label']} failed: {py_val} != {exp_val}"
                assert abs(js_val - exp_val) <= tol, f"{pid}.{fid} JS vector {vec['label']} failed: {js_val} != {exp_val}"


def test_synthetic_fifth_site_no_truth_pack_fails_closed_everywhere(tmp_path: Path) -> None:
    """
    Acceptance Criterion 2:
    Synthetic 5th+ site (site50_no_pack) FAILS CLOSED across load_truth_pack,
    UnifiedTruthGate.audit_estate, TenantFactStore.verify_claim, and
    GitOpsCoordinator.dispatch_to_shipper.
    """
    pid = "site50_no_pack"
    with pytest.raises(TruthPackMissingError):
        load_truth_pack(pid)

    repo_dir = tmp_path / pid
    dist_dir = _init_git_repo_with_dist(repo_dir, pid, f"{pid}.com")
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head><title>Site 50</title>"
        "<link rel=\"canonical\" href=\"https://site50_no_pack.com/\"></head>"
        "<body><h1>Site 50</h1></body></html>",
        encoding="utf-8",
    )

    gate_report = UnifiedTruthGate().audit_estate(dist_dir, pid, repo_root=repo_dir)
    assert gate_report.passed is False
    assert gate_report.status == "FAIL"
    assert any(v.code == "TRUTH_PACK_MISSING" for v in gate_report.violations)

    store = TenantFactStore.get_instance()
    claim_ok, claim_violations = store.verify_claim(pid, "Verified statutory calculation baseline.")
    assert claim_ok is False
    assert any("TRUTH_PACK_MISSING" in msg for msg in claim_violations)

    coord = GitOpsCoordinator(repo_path=repo_dir, dry_run=True)
    ship_res = coord.dispatch_to_shipper(property_id=pid, dist_dir=dist_dir)
    assert ship_res.status == "TRUTH_GATE_FAILED"
    assert "TRUTH_PACK_MISSING" in (ship_res.error or "")


def test_baseline_estates_pass_unified_truth_gate_before_mutations(tmp_path: Path) -> None:
    """Sanity check: clean profithelm and lienbond fixture estates pass UnifiedTruthGate with 0 violations."""
    ph_repo = tmp_path / "ph_clean"
    ph_dist = _build_clean_profithelm_estate(ph_repo)
    ph_rep = UnifiedTruthGate().audit_estate(ph_dist, "profithelm", repo_root=ph_repo)
    assert ph_rep.passed, ph_rep.summary()

    lb_repo = tmp_path / "lb_clean"
    lb_dist = _build_clean_lienbond_estate(lb_repo)
    lb_rep = UnifiedTruthGate().audit_estate(lb_dist, "lienbond", repo_root=lb_repo)
    assert lb_rep.passed, lb_rep.summary()


def test_break_it_banned_claim_30_6_pct_capital_drag_freezes_deploy(tmp_path: Path) -> None:
    """Break-it 3a: Injecting '30.6% reduction in statutory capital drag' triggers HARD FAIL and freezes deploy."""
    repo_dir = tmp_path / "ph_banned"
    dist_dir = _build_clean_profithelm_estate(repo_dir)
    idx_file = dist_dir / "index.html"
    idx_file.write_text(
        idx_file.read_text(encoding="utf-8").replace(
            "<h1>ProfitHelm Tax Engine</h1>",
            "<h1>ProfitHelm Tax Engine</h1><p>Achieve a 30.6% reduction in statutory capital drag today.</p>",
        ),
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "profithelm", expected_code="BANNED_CLAIM")


def test_break_it_stale_js_constant_tcja_std_ded_15000_triggers_hard_fail(tmp_path: Path) -> None:
    """
    Break-it 3b: Injecting stale JS constant `const tcjaStdDed = { single: 15000 }`
    must fail closed on UnifiedTruthGate and freeze deploy.
    """
    repo_dir = tmp_path / "ph_stale_js"
    dist_dir = _build_clean_profithelm_estate(repo_dir)
    tool_file = dist_dir / "tools" / "section-179-heavy-suv-calculator" / "index.html"
    tool_file.write_text(
        tool_file.read_text(encoding="utf-8").replace(
            "function recompute() {",
            "const tcjaStdDed = { single: 15000 };\nfunction recompute() {",
        ),
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "profithelm")


def test_break_it_wrong_calculator_js_math_diverging_from_python_freezes_deploy(tmp_path: Path) -> None:
    """Break-it 3c: Injecting wrong calculator JS math diverging from Python formula fails Node.js parity."""
    repo_dir = tmp_path / "ph_bad_js_math"
    dist_dir = _build_clean_profithelm_estate(repo_dir)
    tool_file = dist_dir / "tools" / "section-179-heavy-suv-calculator" / "index.html"
    tool_file.write_text(
        tool_file.read_text(encoding="utf-8").replace(
            "var val = ",
            "var val = 9999.0 + ",
        ),
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "profithelm", expected_code="JS_PARITY_MISMATCH")


def test_break_it_expired_truth_pack_entry_freezes_deploy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Break-it 3d: Injecting expires_at='2020-01-01' in a Truth Pack fails closed across loader, gate, and shipper."""
    import pseofactory.truth_pack as tp_mod

    packs_dir = tmp_path / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    for src in DEFAULT_TRUTH_PACKS_DIR.glob("*.json"):
        shutil.copy2(src, packs_dir / src.name)

    ph_path = packs_dir / "profithelm.json"
    ph_data = json.loads(ph_path.read_text(encoding="utf-8"))
    first_key = next(iter(ph_data["entries"]))
    ph_data["entries"][first_key]["expires_at"] = "2020-01-01"
    ph_path.write_text(json.dumps(ph_data, indent=2), encoding="utf-8")

    repo_dir = tmp_path / "ph_expired"
    dist_dir = _build_clean_profithelm_estate(repo_dir)

    monkeypatch.setattr(tp_mod, "DEFAULT_TRUTH_PACKS_DIR", packs_dir)

    with pytest.raises(TruthPackExpiredError):
        load_truth_pack("profithelm", packs_dir=packs_dir, allow_expired=False)

    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "profithelm", expected_code="TRUTH_PACK_EXPIRED")


def test_break_it_misbound_federal_tax_widget_on_qbi_199a_page_freezes_deploy(tmp_path: Path) -> None:
    """Break-it 3e: Injecting #val-total_federal_tax widget onto a QBI 199A tool page triggers HARD FAIL."""
    repo_dir = tmp_path / "ph_qbi_widget"
    dist_dir = _build_clean_profithelm_estate(repo_dir)
    qbi_dir = dist_dir / "tools" / "qbi-section-199a-deduction-calculator"
    qbi_dir.mkdir(parents=True, exist_ok=True)
    qbi_manifest = {
        "formula": "round(qbi * 0.20, 2)",
        "inputs": {"qbi": 100000.0},
        "published_output": 20000.0,
    }
    (qbi_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>QBI Section 199A Deduction Calculator | ProfitHelm</title>"
        "<link rel=\"canonical\" href=\"https://profithelm.com/tools/qbi-section-199a-deduction-calculator/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"SoftwareApplication\",\"name\":\"QBI 199A Calculator\"}"
        "</script>"
        f"<script id=\"calculation-manifest\" type=\"application/json\">{json.dumps(qbi_manifest)}</script>"
        "</head><body><main>"
        "<h1>QBI Section 199A Deduction Calculator</h1>"
        "<form class=\"calculator-form\">"
        "<input id=\"input-qbi\" name=\"qbi\" value=\"100000\">"
        "<span class=\"output-value\">$20,000.00</span>"
        "<span id=\"val-total_federal_tax\">$18,734.00</span>"
        "</form>"
        f"<p class=\"disclosure\">{PROFITHELM_DISCLOSURE}</p>"
        "<script>"
        "function recompute() {"
        "  var qbi = Number(document.getElementById('input-qbi').value || 0);"
        "  document.querySelector('.output-value').textContent = '$' + (Math.round(qbi * 0.20 * 100) / 100).toFixed(2);"
        "}"
        "document.querySelector('form').addEventListener('input', recompute);"
        "document.addEventListener('DOMContentLoaded', recompute);"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "profithelm", expected_code="SSR_METRIC_MISMATCH")


def test_break_it_contractor_license_bond_formula_on_bid_bond_calculator_freezes_deploy(tmp_path: Path) -> None:
    """Break-it 3f: Injecting Contractor License Bond $375 formula onto bid-bond-calculator triggers HARD FAIL."""
    repo_dir = tmp_path / "lb_formula_misbind"
    dist_dir = _build_clean_lienbond_estate(repo_dir)
    bid_file = dist_dir / "tools" / "bid-bond-calculator" / "index.html"
    lb_pack = load_truth_pack("lienbond")
    lic_spec = lb_pack.formulas["contractor_license_bond"]
    wrong_manifest = {
        "formula": lic_spec.expression,
        "inputs": dict(lic_spec.variables),
        "published_output": lic_spec.expected_baseline_output,
    }
    bid_file.write_text(
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        "<title>Bid Bond Calculator | LienBond</title>"
        "<link rel=\"canonical\" href=\"https://lienbond.com/tools/bid-bond-calculator/\">"
        "<script type=\"application/ld+json\">"
        "{\"@context\":\"https://schema.org\",\"@type\":\"SoftwareApplication\",\"name\":\"Bid Bond Calculator\"}"
        "</script>"
        f"<script id=\"calculation-manifest\" type=\"application/json\">{json.dumps(wrong_manifest)}</script>"
        "</head><body><main>"
        "<h1>Bid Bond Calculator</h1>"
        "<p>Primary statutory source: <a href=\"https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title40-section3131&amp;num=0&amp;edition=prelim\" "
        "rel=\"noopener noreferrer\" target=\"_blank\">40 U.S.C. 3131 (Miller Act)</a>.</p>"
        "<form class=\"calculator-form\">"
        "<input id=\"input-bond_amount\" name=\"bond_amount\" value=\"25000\">"
        "<input id=\"input-rate_pct\" name=\"rate_pct\" value=\"1.5\">"
        "<input id=\"input-term_years\" name=\"term_years\" value=\"1\">"
        "<input id=\"input-multi_year_discount\" name=\"multi_year_discount\" value=\"0.0\">"
        "<input id=\"input-min_premium\" name=\"min_premium\" value=\"100.0\">"
        "<span id=\"license-bond-premium\" class=\"output-value\">$375.00</span>"
        "</form>"
        f"<p class=\"disclosure\">{LIENBOND_DISCLOSURE}</p>"
        "<script>"
        "function recompute() {"
        "  var bond_amount = Number(document.getElementById('input-bond_amount').value || 0);"
        "  var rate_pct = Number(document.getElementById('input-rate_pct').value || 0);"
        "  var term_years = Number(document.getElementById('input-term_years').value || 0);"
        "  var multi_year_discount = Number(document.getElementById('input-multi_year_discount').value || 0);"
        "  var min_premium = Number(document.getElementById('input-min_premium').value || 0);"
        f"  var val = {lic_spec.js_expression};"
        "  document.getElementById('license-bond-premium').textContent = '$' + val.toFixed(2);"
        "}"
        "document.querySelector('form').addEventListener('input', recompute);"
        "document.addEventListener('DOMContentLoaded', recompute);"
        "</script>"
        "</main></body></html>",
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "lienbond", expected_code="TOPIC_FORMULA_MISMATCH")


def test_break_it_irc_3111_on_lienbond_workers_comp_page_freezes_deploy(tmp_path: Path) -> None:
    """Break-it 3g: Injecting 'IRC Section 3111' onto a LienBond workers' comp page triggers HARD FAIL."""
    repo_dir = tmp_path / "lb_irc3111"
    dist_dir = _build_clean_lienbond_estate(repo_dir)
    wc_file = dist_dir / "tools" / "workers-compensation-class-code-rate-calculator-by-state" / "index.html"
    wc_file.write_text(
        wc_file.read_text(encoding="utf-8").replace(
            "NCCI Experience Rating Plan Manual",
            "IRC Section 3111 and NCCI Experience Rating Plan Manual",
        ),
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dir, repo_dir, "lienbond", expected_code="FORBIDDEN_CITATION_TOPIC")


def test_break_it_llms_txt_dead_link_and_html_entity_freeze_deploy(tmp_path: Path) -> None:
    """Break-it 3h: Injecting dead link or 'R&amp;D' into llms.txt triggers HARD FAIL and freezes deploy."""
    # Case 1: Dead link
    repo_dead = tmp_path / "lb_dead_llms"
    dist_dead = _build_clean_lienbond_estate(repo_dead)
    llms_dead = dist_dead / "llms.txt"
    llms_dead.write_text(
        llms_dead.read_text(encoding="utf-8")
        + "- [Philippines Surety](https://lienbond.com/tools/surety-bond-cost-calculator-philippines/)\n",
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_dead, repo_dead, "lienbond", expected_code="LLMS_DEAD_LINK")

    # Case 2: Raw HTML entity R&amp;D
    repo_ent = tmp_path / "ph_entity_llms"
    dist_ent = _build_clean_profithelm_estate(repo_ent)
    llms_ent = dist_ent / "llms.txt"
    llms_ent.write_text(
        llms_ent.read_text(encoding="utf-8") + "\n- R&amp;D Tax Credit Modeling\n",
        encoding="utf-8",
    )
    _assert_truth_gate_and_shipper_freeze(dist_ent, repo_ent, "profithelm", expected_code="LLMS_HTML_ENTITY")


def test_break_it_quarantined_failing_asset_still_freezes_maintenance_stage_6(tmp_path: Path) -> None:
    """
    Break-it 3i: Even when a failing asset is quarantined in the DLQ,
    MaintenanceLifecycle Stage 6 STILL freezes that site's deploy instead of shipping.
    """
    repo_dir = tmp_path / "ph_quarantined"
    dist_dir = _build_clean_profithelm_estate(repo_dir)
    failing_html = dist_dir / "index.html"
    failing_html.write_text(
        failing_html.read_text(encoding="utf-8").replace(
            "<h1>ProfitHelm Tax Engine</h1>",
            "<h1>ProfitHelm Tax Engine</h1><p>Delivers a 30.6% reduction in statutory capital drag.</p>",
        ),
        encoding="utf-8",
    )

    cascade = RefactorCascadeEngine(dlq_path=tmp_path / "dlq.json")
    drift_rec = AssetDriftRecord(
        asset_path=str(failing_html),
        slug="index",
        reasons=[DriftReason.CONTENT_RELEVANCE_GAP],
        details=["Simulated quarantined asset"],
    )
    cascade.route_to_dlq("profithelm", drift_rec, "Quarantined failing asset")
    assert cascade.is_quarantined(drift_rec, "profithelm") is True

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
    )
    reg = TenantRegistry()
    reg.register_adapter(adapter)

    class _NoopTrendRunner:
        def run_cron_cycle(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"status": "SUCCESS", "approved_build": [], "refactor_pages": []}

    lifecycle = MaintenanceLifecycle(
        registry=reg,
        evaluator=AssetIntegrityEvaluator(enforce_master_seo=False),
        cascade_engine=cascade,
        trend_runner=_NoopTrendRunner(),
    )
    result = lifecycle.run(
        adapter,
        force=False,
        dry_run=False,
        enable_gitops=True,
        enable_distribution=False,
    )
    assert result.status == "FAILED", f"Quarantined failing asset bypassed Stage 6! Result: {result}"
    assert result.engine_hash is None
    assert result.gitops_status is None


def test_ai_intake_deterministic_proof_gate_rejects_fabrications_and_approves_verified_gov() -> None:
    """
    Acceptance Criterion 4:
    run_official_source_intake rejects fabricated verbatim quotes, dual-pass numeric
    disagreements, and non-official URLs with FREEZE_SITE, and approves exact matching
    official .gov extractions with SHA-256 quote proof.
    """
    official_url = "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"
    official_quote = (
        "For taxable years beginning in 2026, the standard deduction under section 63(c)(2) "
        "is $16,100 for single individuals and married individuals filing separate returns."
    )
    raw_doc = (
        "Internal Revenue Bulletin 2025-45. Rev. Proc. 2025-32. "
        + official_quote
        + " Section 179 aggregate cost limitation is $2,560,000."
    )

    def _valid_entry(val: float, quote: str) -> Dict[str, Any]:
        return {
            "entries": [
                {
                    "key": "standard_deduction_2026_single",
                    "value": val,
                    "unit": "usd",
                    "effective_year": 2026,
                    "expires_at": "2027-11-15",
                    "verbatim_quote": quote,
                }
            ]
        }

    # 1. Fabricated verbatim quote -> FREEZE_SITE
    call_idx_1 = {"n": 0}

    def _llm_fabricated_quote(_prompt: str) -> Dict[str, Any]:
        call_idx_1["n"] += 1
        return _valid_entry(16100.0, "This fabricated quote does not appear in the IRS document at all.")

    dec_fab = run_official_source_intake(
        property_id="profithelm",
        source_url=official_url,
        claim_class="enacted_law",
        target_keys=["standard_deduction_2026_single"],
        fetcher=lambda _u: raw_doc,
        llm_caller=_llm_fabricated_quote,
        as_of="2026-11-24",
    )
    assert dec_fab.status == "FREEZE_SITE"
    assert dec_fab.approved_entries == []
    assert any("verbatim_quote" in r for r in dec_fab.reasons)

    # 2. Dual-pass numeric disagreement -> FREEZE_SITE
    call_idx_2 = {"n": 0}

    def _llm_disagree(_prompt: str) -> Dict[str, Any]:
        call_idx_2["n"] += 1
        val = 16100.0 if call_idx_2["n"] == 1 else 15350.0
        return _valid_entry(val, official_quote)

    dec_disagree = run_official_source_intake(
        property_id="profithelm",
        source_url=official_url,
        claim_class="enacted_law",
        target_keys=["standard_deduction_2026_single"],
        fetcher=lambda _u: raw_doc,
        llm_caller=_llm_disagree,
        as_of="2026-11-24",
    )
    assert dec_disagree.status == "FREEZE_SITE"
    assert dec_disagree.approved_entries == []
    assert any("disagreement" in r.lower() for r in dec_disagree.reasons)

    # 3. Non-official domain -> FREEZE_SITE
    dec_unofficial = run_official_source_intake(
        property_id="profithelm",
        source_url="https://random-tax-blog.example.com/2026-deduction",
        claim_class="enacted_law",
        target_keys=["standard_deduction_2026_single"],
        fetcher=lambda _u: raw_doc,
        llm_caller=lambda _p: _valid_entry(16100.0, official_quote),
        as_of="2026-11-24",
    )
    assert dec_unofficial.status == "FREEZE_SITE"
    assert dec_unofficial.approved_entries == []

    # 4. Exact matching official .gov extraction -> APPROVED with SHA-256 quote proof
    dec_ok = run_official_source_intake(
        property_id="profithelm",
        source_url=official_url,
        claim_class="enacted_law",
        target_keys=["standard_deduction_2026_single"],
        fetcher=lambda _u: raw_doc,
        llm_caller=lambda _p: _valid_entry(16100.0, official_quote),
        as_of="2026-11-24",
    )
    assert dec_ok.status == "APPROVED", dec_ok.reasons
    assert len(dec_ok.approved_entries) == 1
    approved = dec_ok.approved_entries[0]
    assert approved["value"] == 16100.0
    assert approved["source_quote_sha256"] == compute_quote_sha256(official_quote)
    assert len(dec_ok.raw_doc_sha256) == 64
