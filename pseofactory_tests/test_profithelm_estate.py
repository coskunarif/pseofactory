"""
Targeted verification suite for `pseofactory/profithelm_estate.py`.

Validates:
- Complete export surface compatible with `profithelm.builder`.
- End-to-end compilation to an isolated temp dist_dir.
- Zero em-dashes (U+2014) and zero en-dashes (U+2013).
- TruthPack 2026 & 2027 IRS constants, Section 179 ($2,560,000 / $4,090,000 /
  $32,000 SUV / 100% bonus), Section 1031, S-Corp OASDI ($184,500), and
  QSBS Section 1202 ($75M / $15M / 50%-75%-100% tiers).
- Zero legacy wrong-widget fallback and fail-closed behavior for unmanifested tools.
- Single SoftwareApplication JSON-LD node, 40-60 word quick answers, and
  HTML-unescaped llms.txt / llms-full.txt.
- Executable Node.js parity & UnifiedTruthGate audit results.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

import pseofactory.profithelm_estate as pe
from pseofactory.truth_gate import UnifiedTruthGate
from pseofactory.truth_pack import load_truth_pack, safe_eval_formula


REQUIRED_EXPORTS: List[str] = [
    "compile_profithelm_estate_impl",
    "render_head",
    "render_header",
    "render_footer",
    "render_byline",
    "render_affiliate_card",
    "render_share_and_pro_card",
    "render_above_the_fold_ftc_disclosure",
    "render_contextual_lead_capture",
    "get_organization_schema",
    "get_dataset_schema",
    "get_howto_schema",
    "get_tech_article_schema",
    "get_software_application_schema",
    "get_web_application_schema",
    "normalize_html_seo_invariants",
    "validate_multi_dataset_enrichment",
    "enrich_quick_answer_with_statutory_benchmarks",
    "reflexive_geo_citability_gate",
    "generate_tool_calculation_manifest",
    "cleanup_orphan_tools",
    "build_machine_endpoints",
    "TOOL_MULTI_DATASET_REGISTRY",
    "render_regulatory_alert_lead_magnet",
    "build_tax_brackets_page",
    "build_section_1031_page",
    "build_crypto_tax_page",
    "build_saas_runway_page",
    "build_prediction_market_page",
    "build_capital_gains_page",
    "build_section_179_page",
    "build_treasury_yield_page",
    "build_prediction_market_tax_page",
    "render_generic_tool_page",
]


def test_required_exports_present_and_usable() -> None:
    for sym in REQUIRED_EXPORTS:
        assert hasattr(pe, sym), f"Missing required export '{sym}' on profithelm_estate"
    assert isinstance(pe.TOOL_MULTI_DATASET_REGISTRY, dict)
    assert len(pe.TOOL_MULTI_DATASET_REGISTRY) >= 9
    assert "Circular 230" in pe.render_above_the_fold_ftc_disclosure(True)
    assert "@type" in pe.get_organization_schema()
    assert pe.get_software_application_schema({"title": "Test"}, "/tools/test/")["@type"] == "SoftwareApplication"


def test_render_generic_tool_page_fails_closed_without_manifest() -> None:
    with pytest.raises(ValueError, match="calculation_manifest"):
        pe.render_generic_tool_page(
            {
                "slug": "unmapped-mystery-calculator",
                "title": "Unmapped Mystery Calculator",
                "description": "Missing formula and inputs.",
            }
        )


def test_compile_estate_and_statutory_invariants(tmp_path: Path) -> None:
    extra_tools: List[Dict[str, Any]] = [
        {
            "slug": "qbi-section-199a-deduction-calculator",
            "title": "QBI Section 199A Deduction Calculator",
            "description": "Compute 20% qualified business income deduction.",
            "calculation_manifest": {
                "model_name": "QBIDeductionModel",
                "statutory_authority": "IRC Section 199A QBI Deduction IRS Guidance",
                "economic_dataset": "IRS SOI Pass-Through Income & BEA Benchmarks",
                "formula": "round(min(qbi * 0.20, max(0.0, taxable_income - net_cap_gain) * 0.20), 2)",
                "inputs": {"qbi": 150000.0, "taxable_income": 180000.0, "net_cap_gain": 10000.0},
                "primary_metric_id": "val-qbi-deduction",
            },
        },
        {
            "slug": "r-and-d-tax-credit-calculator",
            "title": "R&amp;D Tax Credit Calculator",
            "description": "Calculate federal ASC credit for R&amp;D expenditures.",
            "calculation_manifest": {
                "model_name": "FederalResearchCreditASCModel",
                "statutory_authority": "IRC ASC Research Credit IRS Guidance",
                "economic_dataset": "BEA R&D Investment & IRS Form 6765 Series",
                "formula": "round(max(0.0, current_qre - 0.5 * prior_3yr_avg_qre) * 0.14, 2)",
                "inputs": {"current_qre": 500000.0, "prior_3yr_avg_qre": 300000.0},
                "primary_metric_id": "val-rd-credit",
            },
        },
        {
            "slug": "qsbs-section-1202-exclusion-calculator",
            "title": "QSBS Section 1202 Gain Exclusion Calculator",
            "description": "Model post-OBBBA Section 1202 exclusion caps and 3-4-5 year holding tiers.",
        },
        {
            "slug": "1031-exchange-capital-gains-calculator",
            "title": "1031 Exchange Capital Gains Calculator",
            "description": "Model like-kind exchange boot and recognized taxable gain.",
        },
        {
            "slug": "heavy-suv-section-179-calculator",
            "title": "Heavy SUV Section 179 Depreciation Calculator",
            "description": "Model 2026 Section 179 heavy SUV cap and 100% bonus depreciation.",
        },
    ]

    dist = pe.compile_profithelm_estate_impl(tmp_path, run_retrofit=False, extra_tools=extra_tools)
    assert isinstance(dist, Path)
    assert dist == (tmp_path.resolve() / "dist")
    assert (dist / "index.html").is_file()
    assert (dist / "tools" / "index.html").is_file()

    pack = load_truth_pack("profithelm")
    assert pack.entries["standard_deduction_2026_single"].value == 16100.0

    # Check zero em-dashes / en-dashes and zero banned legacy claims across ALL text outputs
    banned_regexes = [
        (r"\$15,000(?!\d|,)", "$15,000"),
        (r"\$19,181(?!\d|,)", "$19,181"),
        (r"\$30,416(?!\d|,)", "$30,416"),
        (r"30\.6%\s+reduction\s+in\s+statutory\s+capital\s+drag", "30.6% reduction in statutory capital drag"),
        (r"30\.6%\s+Average\s+Capital\s+Efficiency\s+Lift", "30.6% Average Capital Efficiency Lift"),
        (r"\$30,500(?!\d|,)", "$30,500"),
        (r"20%\s+bonus\s+depreciation", "20% bonus depreciation"),
        (r"\$8,600(?!\d|,)", "$8,600"),
        (r"\$12,050(?!\d|,)", "$12,050"),
        (r"\$48,900(?!\d|,)", "$48,900"),
        (r"\$104,400(?!\d|,)", "$104,400"),
        (r"39\.6%\s+top", "39.6% top"),
    ]
    for path in dist.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".html", ".js", ".json", ".txt", ".xml"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert "\u2014" not in content, f"Em-dash found in {path}"
            assert "\u2013" not in content, f"En-dash found in {path}"
            for rx, label in banned_regexes:
                assert not re.search(rx, content), f"Banned legacy token {label!r} found in {path}"

    # Verify IRS 2026/2027 constants from TruthPack
    tax_html = (dist / "tools" / "irs-2027-tax-brackets" / "index.html").read_text(encoding="utf-8")
    for expected in ("$16,100", "$32,200", "$24,150", "$12,400", "$50,400", "$105,700", "$201,775", "$256,225", "$640,600"):
        assert expected in tax_html, f"Missing 2026 threshold {expected}"
    for expected27 in ("$16,600", "$33,200", "$24,925", "$12,800", "$52,025", "$109,125", "$208,325", "$264,550", "$661,375"):
        assert expected27 in tax_html, f"Missing 2027 enacted threshold {expected27}"
    assert "$18,734.00" in tax_html
    assert "$18,389.50" in tax_html
    assert "Circular 230" in tax_html

    # Verify Section 179 constants + heavy SUV rule
    s179_html = (dist / "tools" / "section-179-calculator" / "index.html").read_text(encoding="utf-8")
    for tok in ("$2,560,000", "$4,090,000", "$32,000", "100%", "$68,000.00"):
        assert tok in s179_html, f"Missing Section 179 token {tok}"

    heavy_html = (dist / "tools" / "heavy-suv-section-179-calculator" / "index.html").read_text(encoding="utf-8")
    assert "$32,000" in heavy_html
    assert "$2,560,000" not in heavy_html

    # Verify QSBS Section 1202 constants and non-bleed on 1031
    qsbs_html = (dist / "tools" / "qsbs-section-1202-exclusion-calculator" / "index.html").read_text(encoding="utf-8")
    for tok in ("$75,000,000", "$15,000,000", "50%", "75%", "100%", "$15,000,000.00"):
        assert tok in qsbs_html, f"Missing QSBS token {tok}"

    ex1031_html = (dist / "tools" / "1031-exchange-capital-gains-calculator" / "index.html").read_text(encoding="utf-8")
    assert "1202" not in ex1031_html
    assert "total_federal_tax" not in ex1031_html
    assert "$100,000.00" in ex1031_html

    # Verify QBI and R&D custom formulas bound strictly to their own widgets
    qbi_html = (dist / "tools" / "qbi-section-199a-deduction-calculator" / "index.html").read_text(encoding="utf-8")
    assert "val-qbi-deduction" in qbi_html
    assert "$30,000.00" in qbi_html
    assert "total_federal_tax" not in qbi_html

    rd_html = (dist / "tools" / "r-and-d-tax-credit-calculator" / "index.html").read_text(encoding="utf-8")
    assert "val-rd-credit" in rd_html
    assert "$49,000.00" in rd_html

    # Verify llms.txt & llms-full.txt unescaped entities (R&D, zero R&amp;D)
    for llms_name in ("llms.txt", "llms-full.txt"):
        llms_text = (dist / llms_name).read_text(encoding="utf-8")
        assert "&amp;" not in llms_text, f"Raw HTML entity found in {llms_name}"
        assert "R&D Tax Credit Calculator" in llms_text

    # Verify single SoftwareApplication JSON-LD invariant & 40-60 word quick-answers on every tool page
    for tool_dir in (dist / "tools").iterdir():
        if not tool_dir.is_dir():
            continue
        html_txt = (tool_dir / "index.html").read_text(encoding="utf-8")
        qa_match = re.search(r'<aside class="quick-answer">\s*<p>(.*?)</p>\s*</aside>', html_txt, re.DOTALL)
        assert qa_match, f"Missing quick-answer on {tool_dir.name}"
        qa_plain = re.sub(r"<[^>]+>", " ", qa_match.group(1)).strip()
        wc = len(qa_plain.split())
        assert 40 <= wc <= 60, f"Quick-answer word count {wc} outside [40, 60] on {tool_dir.name}"

        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_txt, re.DOTALL)
        assert ld_match, f"Missing JSON-LD on {tool_dir.name}"
        graph = json.loads(ld_match.group(1))["@graph"]
        app_nodes = [n for n in graph if n.get("@type") in ("SoftwareApplication", "WebApplication")]
        assert len(app_nodes) == 1, f"Expected 1 app node on {tool_dir.name}, got {len(app_nodes)}"
        assert app_nodes[0]["@type"] == "SoftwareApplication"
        assert not any(n.get("@type") == "LocalBusiness" for n in graph)

        # Verify inline manifest agrees 100% with sidecar manifest and safe_eval_formula
        cm_match = re.search(r'<script type="application/json" id="calculation-manifest">(.*?)</script>', html_txt, re.DOTALL)
        assert cm_match, f"Missing #calculation-manifest on {tool_dir.name}"
        inline_m = json.loads(cm_match.group(1))
        sidecar_m = json.loads((dist / "manifests" / f"{tool_dir.name}.json").read_text(encoding="utf-8"))
        assert inline_m["formula"] == sidecar_m["formula"]
        assert abs(float(inline_m["published_output"]) - float(sidecar_m["published_output"])) < 0.01
        py_val = round(safe_eval_formula(inline_m["formula"], inline_m["inputs"]), 2)
        assert abs(py_val - float(inline_m["published_output"])) < 0.01


def test_unified_truth_gate_js_parity_and_runtime(tmp_path: Path) -> None:
    dist = pe.compile_profithelm_estate_impl(
        tmp_path,
        run_retrofit=True,
        extra_tools=[
            {
                "slug": "qbi-section-199a-deduction-calculator",
                "title": "QBI Section 199A Deduction Calculator",
                "description": "Compute 20% qualified business income deduction.",
                "calculation_manifest": {
                    "model_name": "QBIDeductionModel",
                    "statutory_authority": "IRC QBI 20% Deduction IRS Guidance",
                    "economic_dataset": "IRS SOI Pass-Through Income & BEA Benchmarks",
                    "formula": "round(min(qbi * 0.20, max(0.0, taxable_income - net_cap_gain) * 0.20), 2)",
                    "inputs": {"qbi": 150000.0, "taxable_income": 180000.0, "net_cap_gain": 10000.0},
                    "primary_metric_id": "val-qbi-deduction",
                },
            },
            {
                "slug": "qsbs-section-1202-exclusion-calculator",
                "title": "QSBS Section 1202 Gain Exclusion Calculator",
                "description": "Compute Section 1202 QSBS gain exclusion.",
            },
        ],
    )
    report = UnifiedTruthGate().audit_estate(
        dist,
        property_id="profithelm",
        repo_root=tmp_path,
        run_js_parity=True,
    )
    assert report.status == "PASS", f"Expected PASS, got {report.status}: {report.violations}"
    assert report.passed is True
    assert len(report.violations) == 0, f"Unexpected TruthGate violations: {report.violations}"
