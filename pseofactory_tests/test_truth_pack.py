"""
Unit and contract verification tests for pseofactory.truth_pack (Wave 1A).

Covers all 4 canonical Truth Packs, dynamic 50+ site discovery via .pseofactory.json,
fail-closed missing/expired/tampered checks, AST formula safety, bracket monotonicity,
pricing parity, and domain-specific guardrails.

Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

from pseofactory.pricing import get_tier_pricing
from pseofactory.truth_pack import (
    ClaimClass,
    DisclosureRule,
    FormulaSpec,
    TruthEntry,
    TruthPack,
    TruthPackExpiredError,
    TruthPackMissingError,
    TruthPackValidationError,
    compute_quote_sha256,
    compute_truth_pack_sha256,
    derive_js_expression,
    discover_truth_pack_ids,
    load_all_truth_packs,
    load_truth_pack,
    normalize_quote,
    safe_eval_formula,
    validate_truth_pack,
)

AS_OF_TODAY = date(2026, 11, 24)


def _clone_pack_dict(property_id: str = "profithelm") -> dict:
    pack = load_truth_pack(property_id, as_of=AS_OF_TODAY)
    return pack.to_dict()


def test_load_all_four_canonical_truth_packs():
    packs = load_all_truth_packs(as_of=AS_OF_TODAY)
    assert set(["profithelm", "prexvo", "gainhelm", "lienbond"]).issubset(packs.keys())

    for pid, pack in packs.items():
        assert pack.schema_version == "2.0"
        assert pack.property_id == pid
        assert validate_truth_pack(pack, as_of=AS_OF_TODAY) == []

        serialized = json.dumps(pack.to_dict(), ensure_ascii=False)
        assert "\u2014" not in serialized
        assert "\u2013" not in serialized

        expected_tp = get_tier_pricing(pack.audience_tier)
        assert pack.pricing_tiers["free"]["price_usd"] == 0.0
        for tier_key in ("quick", "full", "partner_slot"):
            assert pack.pricing_tiers[tier_key]["price_usd"] == expected_tp[tier_key]["price_usd"]
            assert pack.pricing_tiers[tier_key]["price_cents"] == expected_tp[tier_key]["price_cents"]


def test_every_formula_and_test_vector_in_all_four_packs():
    packs = load_all_truth_packs(as_of=AS_OF_TODAY)
    for pid, pack in packs.items():
        assert len(pack.formulas) >= 3, f"{pid} should define at least 3 formulas"
        for fid, spec in pack.formulas.items():
            assert spec.js_expression, f"{pid}.{fid} missing js_expression"
            baseline = safe_eval_formula(spec.expression, spec.variables)
            assert abs(baseline - spec.expected_baseline_output) <= spec.tolerance, (
                f"{pid}.{fid} baseline {baseline} != {spec.expected_baseline_output}"
            )
            assert len(spec.test_vectors) >= 2, f"{pid}.{fid} needs >= 2 test vectors"
            for vec in spec.test_vectors:
                merged = {**spec.variables, **vec["inputs"]}
                actual = safe_eval_formula(spec.expression, merged)
                tol = float(vec.get("tolerance", spec.tolerance))
                assert abs(actual - float(vec["expected"])) <= tol, (
                    f"{pid}.{fid} vector {vec['label']}: got {actual}, expected {vec['expected']}"
                )


def test_synthetic_fifth_site_missing_never_falls_back_to_profithelm(tmp_path):
    with pytest.raises(TruthPackMissingError):
        load_truth_pack("synthetic_fifth_site", as_of=AS_OF_TODAY)

    ws = tmp_path / "workspace"
    site_dir = ws / "site5"
    site_dir.mkdir(parents=True)
    (site_dir / ".pseofactory.json").write_text(
        json.dumps({"property_id": "site5", "domain": "site5.example.com"}),
        encoding="utf-8",
    )
    with pytest.raises(TruthPackMissingError):
        load_truth_pack("site5", workspace_root=ws, as_of=AS_OF_TODAY)


def test_dynamic_50_plus_site_discovery_via_pseofactory_json(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    base_dict = _clone_pack_dict("profithelm")

    for idx in range(5, 56):
        pid = f"site_{idx:02d}"
        repo_dir = ws / pid
        custom_pack_file = repo_dir / "config" / "truth_pack.json"
        custom_pack_file.parent.mkdir(parents=True)

        custom_dict = copy.deepcopy(base_dict)
        custom_dict["property_id"] = pid
        custom_dict["brand_name"] = f"Site {idx:02d}"
        custom_dict["canonical_domain"] = f"https://{pid}.example.com"
        custom_pack_file.write_text(json.dumps(custom_dict), encoding="utf-8")

        (repo_dir / ".pseofactory.json").write_text(
            json.dumps({
                "property_id": pid,
                "domain": f"{pid}.example.com",
                "truth_pack_path": "config/truth_pack.json",
            }),
            encoding="utf-8",
        )

    discovered = discover_truth_pack_ids(workspace_root=ws)
    assert "site_55" in discovered
    assert len([d for d in discovered if d.startswith("site_")]) == 51

    loaded_55 = load_truth_pack("site_55", workspace_root=ws, as_of=AS_OF_TODAY)
    assert loaded_55.property_id == "site_55"
    assert loaded_55.brand_name == "Site 55"


def test_expired_truth_pack_raises_and_allow_expired_overrides(tmp_path):
    pack_dict = _clone_pack_dict("prexvo")
    pack_dict["property_id"] = "expired_site"
    pack_dict["entries"]["hhs_poverty_2026_1person"]["expires_at"] = "2026-11-23"

    pack_path = tmp_path / "expired_site.json"
    pack_path.write_text(json.dumps(pack_dict), encoding="utf-8")

    with pytest.raises(TruthPackExpiredError):
        load_truth_pack("expired_site", packs_dir=tmp_path, as_of=AS_OF_TODAY)

    loaded = load_truth_pack("expired_site", packs_dir=tmp_path, as_of=AS_OF_TODAY, allow_expired=True)
    assert loaded.property_id == "expired_site"

    # Real packs automatically expire in the next agency cycle
    with pytest.raises(TruthPackExpiredError):
        load_truth_pack("prexvo", as_of=date(2028, 1, 1))


def test_tampered_quote_hash_raises_validation_error(tmp_path):
    pack_dict = _clone_pack_dict("profithelm")
    pack_dict["property_id"] = "tampered_site"
    pack_dict["entries"]["section_179_cap_2026"]["verbatim_quote"] += " TAMPERED"

    (tmp_path / "tampered_site.json").write_text(json.dumps(pack_dict), encoding="utf-8")
    with pytest.raises(TruthPackValidationError, match="SHA-256 mismatch"):
        load_truth_pack("tampered_site", packs_dir=tmp_path, as_of=AS_OF_TODAY)


def test_normalize_quote_and_sha256_determinism():
    q1 = "  Section 179   limit is\n\t$2,560,000   for 2026.  "
    q2 = "Section 179 limit is $2,560,000 for 2026."
    assert normalize_quote(q1) == q2
    assert compute_quote_sha256(q1) == compute_quote_sha256(q2)


def test_enacted_law_rejects_non_official_url_and_domain_spoofing(tmp_path):
    for bad_url in (
        "https://example.com/tax-guide",
        "https://irs.gov.attacker.com/rp-25-32.pdf",
        "ftp://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    ):
        pack_dict = _clone_pack_dict("profithelm")
        pack_dict["property_id"] = "bad_url_site"
        pack_dict["entries"]["section_179_cap_2026"]["primary_source_url"] = bad_url
        pack = TruthPack.from_dict(pack_dict)
        errors = validate_truth_pack(pack, as_of=AS_OF_TODAY)
        assert any("official government/statutory primary_source_url" in err for err in errors)


def test_market_benchmark_and_future_projection_rules():
    pack_dict = _clone_pack_dict("gainhelm")
    pack_dict["entries"]["bls_infosec_hourly_loaded_2026"]["required_qualifier_patterns"] = []
    pack_dict["entries"]["bls_infosec_hourly_loaded_2026"]["publisher"] = ""
    pack_dict["entries"]["future_cmmc_projection"] = {
        "key": "future_cmmc_projection",
        "value": 95000.0,
        "claim_class": ClaimClass.FUTURE_PROJECTION.value,
        "unit": "usd",
        "effective_year": 2027,
        "citation": "Internal 2027 compliance cost projection",
        "primary_source_url": "https://gainhelm.com/methodology",
        "publisher": "GainHelm Research",
        "verified_at": "2026-11-24",
        "expires_at": "2027-11-15",
        "verbatim_quote": "Projected 2027 CMMC Level 2 remediation cost estimate.",
        "source_quote_sha256": compute_quote_sha256("Projected 2027 CMMC Level 2 remediation cost estimate."),
        "required_qualifier_patterns": [],
    }
    pack = TruthPack.from_dict(pack_dict)
    errors = validate_truth_pack(pack, as_of=AS_OF_TODAY)
    assert any("market_benchmark" in e and "publisher" in e for e in errors)
    assert any("market_benchmark" in e and "required_qualifier_patterns" in e for e in errors)
    assert any("future_projection" in e and "required_qualifier_patterns" in e for e in errors)


def test_forbidden_dashes_rejected_in_truth_pack():
    pack_dict = _clone_pack_dict("lienbond")
    pack_dict["disclosures"][0]["canonical_text"] += " \u2014 invalid em-dash"
    pack = TruthPack.from_dict(pack_dict)
    errors = validate_truth_pack(pack, as_of=AS_OF_TODAY)
    assert any("em-dash" in e for e in errors)


def test_bracket_monotonicity_and_pricing_parity_checks():
    pack_dict = _clone_pack_dict("profithelm")
    # Non-monotonic bracket rate (10 -> 12 -> 11) and pricing mismatch
    pack_dict["entries"]["tax_brackets_2026_single"]["value"][2]["rate"] = 11.0
    pack_dict["pricing_tiers"]["quick"]["price_usd"] = 99.0
    pack = TruthPack.from_dict(pack_dict)
    errors = validate_truth_pack(pack, as_of=AS_OF_TODAY)
    assert any("lower than prior rate" in e for e in errors)
    assert any("Pricing tier parity mismatch" in e for e in errors)


def test_safe_eval_formula_security_and_js_derivation():
    val = safe_eval_formula(
        "round(max(min(x, 100), abs(-10)) + pow(2, 3) if flag == 1 else 0, 2)",
        {"x": 45.5, "flag": 1},
    )
    assert val == 53.5

    js_expr = derive_js_expression("round(max(a, b) + pow(c, 2), 2)")
    assert "Math.max" in js_expr
    assert "Math.pow" in js_expr
    assert "Math.round" in js_expr

    for dangerous_expr in (
        "__import__('os').system('echo pwned')",
        "eval('1+1')",
        "(1).__class__.__bases__",
        "open('/etc/passwd').read()",
    ):
        with pytest.raises(TruthPackValidationError):
            safe_eval_formula(dangerous_expr, {})


def test_formula_baseline_or_vector_mismatch_fails_validation():
    pack_dict = _clone_pack_dict("gainhelm")
    pack_dict["formulas"]["sprs_score_calculation"]["expected_baseline_output"] = 99.0
    pack_dict["formulas"]["sprs_score_calculation"]["test_vectors"][1]["expected"] = -196.0
    pack = TruthPack.from_dict(pack_dict)
    errors = validate_truth_pack(pack, as_of=AS_OF_TODAY)
    assert any("baseline mismatch" in e for e in errors)
    assert any("test vector" in e and "mismatch" in e for e in errors)


def test_domain_specific_verified_facts_and_guardrails():
    ph = load_truth_pack("profithelm", as_of=AS_OF_TODAY)
    assert ph.entries["section_179_cap_2025"].value == 2500000.0
    assert ph.entries["section_179_cap_2026"].value == 2560000.0
    assert ph.entries["section_179_heavy_suv_cap_2026"].value == 32000.0
    assert ph.entries["bonus_depreciation_pct_2026"].value == 100.0
    assert ph.entries["standard_deduction_2026_single"].value == 16100.0
    assert ph.entries["standard_deduction_2027_single"].value == 16600.0
    assert ph.entries["qsbs_asset_ceiling_post_obbba"].value == 75000000.0
    assert ph.entries["qsbs_exclusion_cap_post_obbba"].value == 15000000.0
    assert ph.entries["oasdi_wage_base_2026"].value == 184500.0

    # S-Corp FICA caps BOTH sides at $184,500
    scorp_expr = ph.formulas["scorp_fica_savings_2026"].expression
    assert safe_eval_formula(scorp_expr, {"net_profit": 300000.0, "reasonable_salary": 200000.0}) == 2234.45

    px = load_truth_pack("prexvo", as_of=AS_OF_TODAY)
    assert px.entries["hhs_poverty_2026_1person"].value == 15960.0
    assert px.entries["hhs_poverty_2026_per_additional"].value == 5680.0
    assert px.entries["rap_forgiveness_months"].value == 360
    assert px.entries["pslf_qualifying_payments"].value == 120

    gh = load_truth_pack("gainhelm", as_of=AS_OF_TODAY)
    assert gh.entries["hipaa_tier4_annual_cap_2026"].value == 2190294.0
    assert gh.entries["sprs_max_score"].value == 110
    assert gh.entries["sprs_min_score"].value == -203
    assert gh.entries["sprs_max_deduction"].value == 313
    assert gh.entries["sprs_control_counts"].value == {"5_pt": 44, "3_pt": 14, "1_pt": 51, "0_pt": 1}
    # Non-C3PAO disclosure cannot be satisfied merely by mentioning "c3pao"
    disc = gh.disclosures[0]
    assert not all(re.search(pat, "CMMC requires a C3PAO audit.", re.IGNORECASE) for pat in disc.required_text_patterns)
    assert all(re.search(pat, disc.canonical_text, re.IGNORECASE) for pat in disc.required_text_patterns)

    lb = load_truth_pack("lienbond", as_of=AS_OF_TODAY)
    assert lb.entries["miller_act_threshold_usd"].value == 150000.0
    assert "irc_section_3111" in lb.citations_allowlist
    assert "osha_29_cfr_1904" in lb.citations_allowlist
    assert any("workers-comp" in p for p in lb.citations_allowlist["irc_section_3111"]["forbidden_slug_patterns"])
    assert any("emr" in p for p in lb.citations_allowlist["osha_29_cfr_1904"]["forbidden_slug_patterns"])
    assert "bid_bond" in lb.formulas and "contractor_license_bond" in lb.formulas
    assert any("license-bond" in p for p in lb.formulas["bid_bond"].forbidden_slug_patterns)
    assert any("bid-bond" in p for p in lb.formulas["contractor_license_bond"].forbidden_slug_patterns)


def test_roundtrip_and_pack_sha256_determinism():
    pack = load_truth_pack("profithelm", as_of=AS_OF_TODAY)
    rebuilt = TruthPack.from_dict(pack.to_dict())
    assert compute_truth_pack_sha256(pack) == compute_truth_pack_sha256(rebuilt)
    assert isinstance(
        FormulaSpec(formula_id="x", model_name="m", expression="a + b"),
        FormulaSpec,
    )
    assert isinstance(
        DisclosureRule(disclosure_id="d", canonical_text="c"),
        DisclosureRule,
    )
    assert isinstance(
        TruthEntry(
            key="k",
            value=1.0,
            claim_class=ClaimClass.ENACTED_LAW.value,
            unit="usd",
            effective_year=2026,
            citation="c",
            primary_source_url="https://www.irs.gov/",
            publisher="IRS",
            verified_at="2026-11-24",
            expires_at="2027-11-15",
            verbatim_quote="q",
            source_quote_sha256=compute_quote_sha256("q"),
        ),
        TruthEntry,
    )
