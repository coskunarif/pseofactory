"""
Contract and unit tests for pseofactory.truth_intake.
Verifies:
1. Official primary domain allowlist + HTTPS + SSRF guard (enacted_law vs market_benchmark).
2. Deterministic TruthPack expiry & freshness check (no fake freshness stamps).
3. Verbatim-quote proof, dual-pass agreement proof, and structural math invariants.
4. Fail-closed AI-assisted official-source intake runner with dual independent prompt framings.
5. Semantic claim critic with deterministic verbatim-excerpt gating and fail-closed offline handling.
6. Dynamic 50+ site scalability (zero hardcoded tenant lists) and zero forbidden dashes.

Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.truth_intake import (
    FreshnessReport,
    IntakeDecision,
    SemanticCriticReport,
    check_truth_pack_freshness,
    is_official_primary_url,
    run_official_source_intake,
    run_semantic_claim_critic,
    verify_extracted_candidate,
)


# =====================================================================
# 1. Official Primary Domain Allowlist & SSRF Guard
# =====================================================================


@pytest.mark.parametrize(
    "url",
    [
        "https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        "https://congress.gov/bill/119th-congress/house-bill/1",
        "https://www.federalregister.gov/documents/2025/01/15/example",
        "https://www.acquisition.gov/far/part-31",
        "https://www.ed.gov/laws-and-guidance",
        "https://studentaid.gov/manage-loans/forgiveness-cancellation/public-service",
        "https://www.acq.osd.mil/dpap/dars/dfarspgi/current/index.html",
        "https://aspe.hhs.gov/topics/poverty-economic-measures/poverty-guidelines",
        "https://www.bls.gov/cpi/",
        "https://www.census.gov/data/tables.html",
        "https://home.treasury.gov/policy-issues/tax-policy",
        "https://www.dol.gov/agencies/whd/minimum-wage",
        "https://www.sba.gov/size-standards",
        "https://www.sec.gov/rules-regulations",
        "https://tax.ny.gov/pit/file/standard_deduction.htm",
    ],
)
def test_official_primary_urls_allowed_for_enacted_law(url: str):
    assert is_official_primary_url(url, claim_class="enacted_law") is True
    assert is_official_primary_url(url, claim_class="market_benchmark") is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ncci.com/Articles/Pages/Insights.aspx",
        "https://www.sfaa.org/page/surety-benchmarks",
        "https://www.aicpa-cima.com/resources/landing/tax-standards",
        "https://www.pcisecuritystandards.org/document_library/",
        "https://www.iso.org/standard/27001",
    ],
)
def test_benchmark_authorities_allowed_only_for_market_benchmark(url: str):
    assert is_official_primary_url(url, claim_class="enacted_law") is False
    assert is_official_primary_url(url, claim_class="market_benchmark") is True


@pytest.mark.parametrize(
    "url",
    [
        "http://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        "ftp://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        "file:///etc/passwd",
        "https://investopedia.com/terms/s/standarddeduction.asp",
        "https://irs.gov.evil.com/phishing",
        "https://fakeirs.gov.example.org/",
        "https://evil-ncci.com/data",
        "https://fakeiso.org/standard",
        "https://localhost/admin",
        "https://127.0.0.1/internal",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/secret",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://2130706433/loopback-int",
        "https://0x7f000001/loopback-hex",
        "https://irs.gov@evil.com/steal",
        "https://10.0.0.1/private",
        "",
        "not-a-url",
    ],
)
def test_untrusted_http_and_ssrf_urls_blocked(url: str):
    assert is_official_primary_url(url, claim_class="enacted_law") is False
    assert is_official_primary_url(url, claim_class="market_benchmark") is False


def test_unknown_claim_class_fails_closed():
    assert is_official_primary_url("https://www.irs.gov/", claim_class="editorial_blog") is False
    assert is_official_primary_url("https://www.irs.gov/", claim_class="") is False


# =====================================================================
# 2. Expiry & Freshness Check
# =====================================================================


@dataclass
class _MockTruthPack:
    property_id: str
    entries: Dict[str, Dict[str, Any]]


def test_freshness_fresh_expiring_soon_and_expired():
    as_of = date(2026, 6, 1)

    fresh_pack = {
        "property_id": "site_012_payroll",
        "entries": {
            "fica_wage_base": {"value": 176100, "expires_at": "2026-12-31"},
            "futa_rate": {"value": 0.6, "expires_at": "2027-01-01"},
        },
    }
    res_fresh = check_truth_pack_freshness(fresh_pack, as_of=as_of, warning_days=30)
    assert isinstance(res_fresh, FreshnessReport)
    assert res_fresh.status == "FRESH"
    assert res_fresh.expired_keys == []
    assert res_fresh.expiring_soon_keys == []
    assert res_fresh.checked_count == 2

    expiring_pack = _MockTruthPack(
        property_id="site_028_lending",
        entries={
            "pslf_months": {"value": 120, "expires_at": "2026-06-20"},
            "rap_months": {"value": 360, "expires_at": "2027-06-01"},
        },
    )
    res_soon = check_truth_pack_freshness(expiring_pack, as_of=as_of, warning_days=30)
    assert res_soon.status == "EXPIRING_SOON"
    assert res_soon.expiring_soon_keys == ["pslf_months"]
    assert res_soon.expired_keys == []

    expired_pack = {
        "property_id": "site_051_freight",
        "entries": {
            "section_179_cap": {"value": 1220000, "expires_at": "2026-05-31"},
            "bonus_depreciation_pct": {"value": 40, "expires_at": "2026-06-01"},
            "valid_key": {"value": 100, "expires_at": "2026-12-31"},
        },
    }
    res_exp = check_truth_pack_freshness(expired_pack, as_of=as_of, warning_days=30)
    assert res_exp.status == "FREEZE_EXPIRED"
    assert res_exp.expired_keys == ["section_179_cap", "bonus_depreciation_pct"]
    assert res_exp.checked_count == 3


def test_freshness_empty_or_missing_expiry_fails_closed():
    as_of = date(2026, 6, 1)
    assert check_truth_pack_freshness({"entries": {}}, as_of=as_of).status == "FREEZE_EXPIRED"
    res_missing = check_truth_pack_freshness(
        {"entries": {"k1": {"value": 100}}},
        as_of=as_of,
    )
    assert res_missing.status == "FREEZE_EXPIRED"
    assert res_missing.expired_keys == ["k1"]


# =====================================================================
# 3. Deterministic Verbatim-Quote, Dual-Pass, and Math Invariants
# =====================================================================


SAMPLE_IRS_DOC = (
    "Internal Revenue Bulletin Rev. Proc. 2024-40. "
    "For taxable years beginning in 2025, the standard deduction under section 63(c)(2) "
    "is $15,000 for unmarried individuals and $30,000 for married individuals filing jointly. "
    "Tax rates begin at 10 percent on taxable income not over $11,925, "
    "12 percent over $11,925 up to $48,475, and 22 percent over $48,475."
)


def _valid_entry(
    key: str = "standard_deduction_single",
    value: Any = 15000,
    unit: str = "usd",
    quote: str = "is $15,000 for unmarried individuals",
) -> Dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "unit": unit,
        "effective_year": 2025,
        "expires_at": "2026-12-31",
        "verbatim_quote": quote,
    }


def test_verify_extracted_candidate_approved_with_sha256():
    quote_multiline = "is $15,000 for\n  unmarried\tindividuals"
    pass_1 = [_valid_entry(quote=quote_multiline)]
    pass_2 = [_valid_entry(value=15000.0, quote="is $15,000 for unmarried individuals")]

    decision = verify_extracted_candidate(
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        raw_document_text=SAMPLE_IRS_DOC,
        extracted_fields_pass_1=pass_1,
        extracted_fields_pass_2=pass_2,
        claim_class="enacted_law",
        property_id="site_047_tax_prep",
        verified_at=date(2026, 1, 15),
    )

    assert isinstance(decision, IntakeDecision)
    assert decision.status == "APPROVED"
    assert decision.property_id == "site_047_tax_prep"
    assert decision.reasons == []
    assert decision.raw_doc_sha256 == hashlib.sha256(SAMPLE_IRS_DOC.encode("utf-8")).hexdigest()
    assert len(decision.approved_entries) == 1
    expected_quote_sha = hashlib.sha256(
        "is $15,000 for unmarried individuals".encode("utf-8")
    ).hexdigest()
    assert decision.approved_entries[0]["source_quote_sha256"] == expected_quote_sha


def test_verify_fabricated_verbatim_quote_freezes_site():
    fabricated_quote = "is $15,750 for unmarried individuals"
    pass_1 = [_valid_entry(quote=fabricated_quote)]
    pass_2 = [_valid_entry(quote=fabricated_quote)]

    decision = verify_extracted_candidate(
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        raw_document_text=SAMPLE_IRS_DOC,
        extracted_fields_pass_1=pass_1,
        extracted_fields_pass_2=pass_2,
        claim_class="enacted_law",
        property_id="site_047_tax_prep",
        verified_at=date(2026, 1, 15),
    )

    assert decision.status == "FREEZE_SITE"
    assert decision.approved_entries == []
    assert any("verbatim_quote not found verbatim" in r for r in decision.reasons)


def test_verify_dual_pass_numeric_disagreement_freezes_site():
    pass_1 = [_valid_entry(value=15000)]
    pass_2 = [_valid_entry(value=14600)]

    decision = verify_extracted_candidate(
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        raw_document_text=SAMPLE_IRS_DOC,
        extracted_fields_pass_1=pass_1,
        extracted_fields_pass_2=pass_2,
        claim_class="enacted_law",
        property_id="site_047_tax_prep",
        verified_at=date(2026, 1, 15),
    )

    assert decision.status == "FREEZE_SITE"
    assert decision.approved_entries == []
    assert any("Dual-pass disagreement" in r and "15000" in r and "14600" in r for r in decision.reasons)


@pytest.mark.parametrize(
    "bad_brackets",
    [
        # Non-ascending rate (12 -> 10)
        [
            {"min": 0, "max": 11925, "rate": 12},
            {"min": 11925, "max": 48475, "rate": 10},
        ],
        # Non-contiguous gap (11925 -> 12500)
        [
            {"min": 0, "max": 11925, "rate": 10},
            {"min": 12500, "max": 48475, "rate": 12},
        ],
        # Overlapping brackets (11925 -> 11000)
        [
            {"min": 0, "max": 11925, "rate": 10},
            {"min": 11000, "max": 48475, "rate": 12},
        ],
        # Rate > 100
        [
            {"min": 0, "max": 11925, "rate": 10},
            {"min": 11925, "max": 48475, "rate": 105},
        ],
        # max=None before final bracket
        [
            {"min": 0, "max": None, "rate": 10},
            {"min": 11925, "max": 48475, "rate": 12},
        ],
    ],
)
def test_verify_non_monotonic_or_invalid_brackets_freezes_site(bad_brackets: List[Dict[str, Any]]):
    quote = "Tax rates begin at 10 percent on taxable income not over $11,925"
    entry = _valid_entry(key="federal_single_brackets", value=bad_brackets, unit="brackets", quote=quote)
    decision = verify_extracted_candidate(
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        raw_document_text=SAMPLE_IRS_DOC,
        extracted_fields_pass_1=[entry],
        extracted_fields_pass_2=[entry],
        claim_class="enacted_law",
        property_id="site_047_tax_prep",
        verified_at=date(2026, 1, 15),
    )
    assert decision.status == "FREEZE_SITE"
    assert decision.approved_entries == []


def test_verify_valid_contiguous_brackets_approved():
    good_brackets = [
        {"min": 0, "max": 11925, "rate": 10},
        {"min": 11925, "max": 48475, "rate": 12},
        {"min": 48475, "max": None, "rate": 22},
    ]
    quote = "Tax rates begin at 10 percent on taxable income not over $11,925"
    entry = _valid_entry(key="federal_single_brackets", value=good_brackets, unit="brackets", quote=quote)
    decision = verify_extracted_candidate(
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        raw_document_text=SAMPLE_IRS_DOC,
        extracted_fields_pass_1=[entry],
        extracted_fields_pass_2=[entry],
        claim_class="enacted_law",
        property_id="site_047_tax_prep",
        verified_at=date(2026, 1, 15),
    )
    assert decision.status == "APPROVED"


def test_verify_unit_and_temporal_invariants_freeze_site():
    bad_pct = _valid_entry(key="bad_pct", value=120.5, unit="pct")
    bad_usd = _valid_entry(key="bad_usd", value=-100, unit="usd")
    bad_year = _valid_entry(key="bad_year", value=100, unit="usd")
    bad_year["effective_year"] = 1995
    bad_expiry = _valid_entry(key="bad_expiry", value=100, unit="usd")
    bad_expiry["expires_at"] = "2026-01-15"

    for bad_entry in (bad_pct, bad_usd, bad_year, bad_expiry):
        dec = verify_extracted_candidate(
            source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
            raw_document_text=SAMPLE_IRS_DOC,
            extracted_fields_pass_1=[bad_entry],
            extracted_fields_pass_2=[bad_entry],
            claim_class="enacted_law",
            property_id="site_047_tax_prep",
            verified_at=date(2026, 1, 15),
        )
        assert dec.status == "FREEZE_SITE"


# =====================================================================
# 4. AI-Assisted Official-Source Intake Runner
# =====================================================================


@pytest.mark.parametrize("property_id", ["profithelm", "prexvo", "site_019_medicaid", "site_053_defense_acq"])
def test_run_official_source_intake_approved_for_any_site(property_id: str):
    prompts_seen: List[str] = []

    def fake_fetcher(url: str) -> str:
        assert url == "https://www.irs.gov/pub/irs-drop/rp-24-40.pdf"
        return SAMPLE_IRS_DOC

    def fake_llm(prompt: str) -> Dict[str, Any]:
        prompts_seen.append(prompt)
        return {
            "entries": [
                _valid_entry(
                    key="standard_deduction_single",
                    value=15000,
                    unit="usd",
                    quote="is $15,000 for unmarried individuals",
                )
            ]
        }

    decision = run_official_source_intake(
        property_id=property_id,
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        claim_class="enacted_law",
        target_keys=["standard_deduction_single"],
        fetcher=fake_fetcher,
        llm_caller=fake_llm,
        as_of=date(2026, 1, 15),
    )

    assert decision.status == "APPROVED"
    assert decision.property_id == property_id
    assert len(prompts_seen) == 2
    assert prompts_seen[0] != prompts_seen[1]
    assert "PASS 1" in prompts_seen[0]
    assert "PASS 2" in prompts_seen[1]


def test_run_official_source_intake_fail_closed_on_errors():
    # Untrusted URL must block before fetcher runs
    fetcher_called = False

    def should_not_fetch(_url: str) -> str:
        nonlocal fetcher_called
        fetcher_called = True
        return SAMPLE_IRS_DOC

    dec_bad_url = run_official_source_intake(
        property_id="site_055_surety",
        source_url="https://www.sfaa.org/page/surety-benchmarks",
        claim_class="enacted_law",
        target_keys=["surety_bond_rate"],
        fetcher=should_not_fetch,
        llm_caller=lambda _p: {"entries": []},
        as_of=date(2026, 1, 15),
    )
    assert dec_bad_url.status == "FREEZE_SITE"
    assert fetcher_called is False

    # Fetch error freezes
    def failing_fetcher(_url: str) -> str:
        raise TimeoutError("HTTP read timed out")

    dec_fetch_err = run_official_source_intake(
        property_id="site_055_surety",
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        claim_class="enacted_law",
        target_keys=["standard_deduction_single"],
        fetcher=failing_fetcher,
        llm_caller=lambda _p: {"entries": []},
        as_of=date(2026, 1, 15),
    )
    assert dec_fetch_err.status == "FREEZE_SITE"

    # LLM error on pass 2 freezes
    calls = {"n": 0}

    def flaky_llm(_prompt: str) -> Dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("agy quota exhausted")
        return {"entries": [_valid_entry()]}

    dec_llm_err = run_official_source_intake(
        property_id="site_055_surety",
        source_url="https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
        claim_class="enacted_law",
        target_keys=["standard_deduction_single"],
        fetcher=lambda _u: SAMPLE_IRS_DOC,
        llm_caller=flaky_llm,
        as_of=date(2026, 1, 15),
    )
    assert dec_llm_err.status == "FREEZE_SITE"
    assert any("pass 2" in r.lower() for r in dec_llm_err.reasons)


# =====================================================================
# 5. AI Semantic Claim Critic
# =====================================================================


def test_semantic_critic_rejects_hallucinated_excerpts_and_surfaces_real_violations():
    page_text = (
        "Public Service Loan Forgiveness (PSLF) requires 360 monthly qualifying payments "
        "under 34 CFR 685.219 before remaining federal loan balances are discharged."
    )
    truth_pack = {
        "property_id": "prexvo",
        "entries": {
            "pslf_qualifying_payments_months": {"value": 120, "unit": "months"},
            "rap_forgiveness_months": {"value": 360, "unit": "months"},
        },
    }

    def critic_llm(_prompt: str) -> Dict[str, Any]:
        return {
            "violations": [
                {
                    "rule_id": "pslf_rap_term_conflation",
                    "truth_key": "pslf_qualifying_payments_months",
                    "offending_excerpt": "requires 360 monthly qualifying payments",
                    "explanation": "Conflates PSLF 120-month term with RAP 360-month term.",
                    "severity": "error",
                },
                {
                    "rule_id": "hallucinated_osha_cite",
                    "truth_key": "workers_comp_rate",
                    "offending_excerpt": "Employers must pay OSHA penalty of $99,999 per claim",
                    "explanation": "Fabricated violation excerpt not present in page_text.",
                    "severity": "error",
                },
            ]
        }

    report = run_semantic_claim_critic(
        property_id="prexvo",
        page_slug="pslf-forgiveness-calculator",
        page_text=page_text,
        truth_pack_dict=truth_pack,
        llm_caller=critic_llm,
    )

    assert isinstance(report, SemanticCriticReport)
    assert report.status == "VIOLATIONS_FOUND"
    assert len(report.verified_violations) == 1
    assert report.verified_violations[0].rule_id == "pslf_rap_term_conflation"
    assert report.verified_violations[0].offending_excerpt == "requires 360 monthly qualifying payments"
    assert len(report.rejected_hallucinated_violations) == 1
    assert report.rejected_hallucinated_violations[0]["rule_id"] == "hallucinated_osha_cite"


def test_semantic_critic_passes_when_only_hallucinated_violations_returned():
    page_text = "PSLF requires 120 qualifying monthly payments while working full-time."
    report = run_semantic_claim_critic(
        property_id="prexvo",
        page_slug="pslf-calculator",
        page_text=page_text,
        truth_pack_dict={"entries": {"pslf_qualifying_payments_months": {"value": 120}}},
        llm_caller=lambda _p: {
            "violations": [
                {
                    "rule_id": "hallucination",
                    "truth_key": "pslf_qualifying_payments_months",
                    "offending_excerpt": "PSLF requires 360 payments",
                    "explanation": "Does not exist in page_text.",
                }
            ]
        },
    )
    assert report.status == "PASS"
    assert report.verified_violations == []
    assert len(report.rejected_hallucinated_violations) == 1


def test_semantic_critic_offline_and_fail_closed_modes():
    def failing_llm(_prompt: str) -> Any:
        raise TimeoutError("Critic call timed out")

    res_closed = run_semantic_claim_critic(
        property_id="site_050_comp",
        page_slug="workers-comp-calculator",
        page_text="Workers compensation rates vary by NCCI class code.",
        truth_pack_dict={"entries": {}},
        llm_caller=failing_llm,
        fail_closed_on_error=True,
    )
    assert res_closed.status == "FREEZE_CRITIC_UNAVAILABLE"

    res_offline = run_semantic_claim_critic(
        property_id="site_050_comp",
        page_slug="workers-comp-calculator",
        page_text="Workers compensation rates vary by NCCI class code.",
        truth_pack_dict={"entries": {}},
        llm_caller=failing_llm,
        fail_closed_on_error=False,
    )
    assert res_offline.status == "SKIPPED_OFFLINE"

    res_disabled = run_semantic_claim_critic(
        property_id="site_050_comp",
        page_slug="workers-comp-calculator",
        page_text="Workers compensation rates vary by NCCI class code.",
        truth_pack_dict={"entries": {}},
        enabled=False,
    )
    assert res_disabled.status == "SKIPPED_DISABLED"


# =====================================================================
# 6. Zero Forbidden Dashes Invariant
# =====================================================================


def test_truth_intake_files_contain_zero_forbidden_dashes():
    repo_root = Path(__file__).resolve().parent.parent
    for rel_path in (
        "pseofactory/truth_intake.py",
        "pseofactory_tests/test_truth_intake.py",
    ):
        text = (repo_root / rel_path).read_text(encoding="utf-8")
        assert assert_no_forbidden_dashes(text, context=rel_path) is True
