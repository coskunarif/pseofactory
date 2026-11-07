"""
Regression suite for x-like:2109835011772035193 (AgriciDaniel/jev-seo) integration:
1. Native TypeSafe Jev client (pseofactory/jev_client.py): typed primitives (choice, score, noul),
   side-of-threshold decisiveness (side_probability >= 0.80), opening-after-H1 extraction,
   code-first question pruning, 10-pair Jaccard >= 0.40 cannibalization substitution checks,
   >= 600-word merge/remove guardrail, and fixed typed Jev calls in qualification.py & feedback_loop.py.
2. Deterministic 52-rule Google Search Central parity in audit_estate_technical_seo_and_cannibalization
   (generic_anchors, BFS deep_pages > 3, missing_image_alt, missing_image_dimensions, heavy_html > 500KB,
   missing_html_lang, missing_viewport_meta, multiple_title_tags) + X_LIKE_2109835011772035193_CAPABILITY_MATRIX
   and score_estate_jev_seo_rubric.
3. P2 Autonomous Daily Trend-to-Page Builder pre-publish verification gates: distinct statutory models
   for QSBS Section 1202, Section 199A QBI, and Corporate AMT (CAMT), live sibling-link resolution
   with zero broken internal links, and 0%-state-tax spoke Title/H1 parity.
Zero em-dashes. Zero en-dashes.
"""

import importlib
import importlib.util
from pathlib import Path
from typing import Any, Dict

import pytest


def test_jev_client_primitives_and_side_decisiveness() -> None:
    spec = importlib.util.find_spec("pseofactory.jev_client")
    assert spec is not None, "pseofactory.jev_client module must exist"
    jev_client = importlib.import_module("pseofactory.jev_client")
    ACT_THRESHOLD = getattr(jev_client, "ACT_THRESHOLD", None)
    build_jev_page_questions = getattr(jev_client, "build_jev_page_questions", None)
    choice = getattr(jev_client, "choice", None)
    evaluate_page_prepublish_gate = getattr(jev_client, "evaluate_page_prepublish_gate", None)
    extract_opening_after_h1 = getattr(jev_client, "extract_opening_after_h1", None)
    normalize_jev_answer = getattr(jev_client, "normalize_jev_answer", None)
    noul = getattr(jev_client, "noul", None)
    score = getattr(jev_client, "score", None)
    shortlist_cannibalization_pairs = getattr(jev_client, "shortlist_cannibalization_pairs", None)

    assert ACT_THRESHOLD == 0.80

    # 1. Score side-of-threshold decisiveness: probabilities split across levels 2 and 3 (both >= midpoint)
    # should sum to 0.88 on the upper side and be marked decisive ("act") even though top level is 0.48.
    s_spec = score(
        "How well does page satisfy visitor?",
        ["None", "Superficial", "Adequate", "Thorough"],
    )
    ans_upper = normalize_jev_answer(
        s_spec,
        {
            "score": 2.4,
            "confidence": 0.48,
            "probabilities": {"0": 0.02, "1": 0.10, "2": 0.40, "3": 0.48},
        },
    )
    assert ans_upper["type"] == "score"
    assert ans_upper["value"] == pytest.approx(2.4 / 3.0, abs=1e-3)
    assert ans_upper["side_probability"] == pytest.approx(0.88, abs=1e-3)
    assert ans_upper["band"] == "act"

    # Split across midpoint (level 1 = 0.45, level 2 = 0.45) -> side_probability = 0.50 -> "review"
    ans_split = normalize_jev_answer(
        s_spec,
        {
            "score": 1.5,
            "confidence": 0.45,
            "probabilities": {"0": 0.05, "1": 0.45, "2": 0.45, "3": 0.05},
        },
    )
    assert ans_split["side_probability"] == pytest.approx(0.50, abs=1e-3)
    assert ans_split["band"] == "review"

    # 2. Noul decisive bands (>= 0.80 -> "yes", <= 0.20 -> "no", between -> "review")
    n_spec = noul("Does page.h1 state the main topic?", "Names topic", "Slogan")
    assert normalize_jev_answer(n_spec, {"noul": 0.86})["band"] == "yes"
    assert normalize_jev_answer(n_spec, {"noul": 0.12})["band"] == "no"
    assert normalize_jev_answer(n_spec, {"noul": 0.55})["band"] == "review"

    # 3. Choice decisive band (>= 0.80 confidence -> "act")
    c_spec = choice("Action?", {"keep_or_improve": "Keep", "rewrite": "Rewrite", "merge_or_remove": "Merge"})
    assert normalize_jev_answer(c_spec, {"choice": "keep_or_improve", "confidence": 0.85})["band"] == "act"
    assert normalize_jev_answer(c_spec, {"choice": "rewrite", "confidence": 0.60})["band"] == "review"

    # 4. Opening after H1 ignores header/breadcrumb preamble
    sample_html = (
        "<html><body><nav>Home > Tools > Tax</nav>"
        "<h1>QSBS Section 1202 Tax Calculator</h1>"
        "<p>Under IRC Section 1202(a)(4), qualified small business stock held for 5 years excludes up to $10,000,000 in capital gains. "
        "Calculate your federal and state conformity tax savings instantly.</p></body></html>"
    )
    opening_txt = extract_opening_after_h1(sample_html)
    assert opening_txt.startswith("Under IRC Section 1202(a)(4)")
    assert "Home > Tools" not in opening_txt

    # 5. Code never asks Jev what code can see itself
    q_home_missing = build_jev_page_questions(
        {"url": "https://profithelm.com/", "title": "ProfitHelm", "meta_description": "", "h1": []},
        is_homepage=True,
    )
    assert "page_type" not in q_home_missing
    assert "title_fit" in q_home_missing
    assert "meta_fit" not in q_home_missing
    assert "h1_fit" not in q_home_missing

    # 6. Pair overlap shortlisting and >= 600-word merge/remove guardrail
    pages = [
        {"url": "/tools/parent-plus-double-consolidation/", "title": "Parent PLUS Double Consolidation Calculator", "h1": "Parent PLUS Double Consolidation Loan Calculator"},
        {"url": "/tools/parent-plus-loan-payment-calculator/", "title": "Parent PLUS Loan Payment Calculator", "h1": "Parent PLUS Loan Payment Calculator"},
        {"url": "/tools/soc-2-audit-cost-calculator/", "title": "SOC 2 Audit Cost Calculator", "h1": "SOC 2 Type II Audit Cost Calculator"},
    ]
    pairs = shortlist_cannibalization_pairs(pages, min_jaccard=0.40)
    assert len(pairs) == 1
    assert pairs[0][0]["url"] == "/tools/parent-plus-double-consolidation/"
    assert pairs[0][1]["url"] == "/tools/parent-plus-loan-payment-calculator/"
    assert pairs[0][2] >= 0.40

    # Substantial page (>= 600 words) must never be flagged for merge_or_remove deletion by model action alone
    long_body = " ".join(["IRC Section 1202 statutory calculation parameter"] * 120)
    long_html = (
        f"<html lang='en'><head><title>QSBS Section 1202 Calculator | ProfitHelm</title>"
        f"<meta name='description' content='Calculate IRC Section 1202 qualified small business stock capital gains tax exclusion and state conformity liability.'></head>"
        f"<body><h1>QSBS Section 1202 Calculator</h1><p>{long_body}</p>"
        f"<button type='submit'>Calculate QSBS Exclusion</button></body></html>"
    )
    gate_res = evaluate_page_prepublish_gate(
        html_content=long_html,
        candidate_spec={"slug": "qsbs-section-1202-state-conformity-tax-calculator", "property_id": "profithelm"},
        existing_pages=[],
        jev_mock_override={"action": {"choice": "merge_or_remove", "confidence": 0.95}},
    )
    assert gate_res["passed"] is True
    assert gate_res["merge_or_remove_blocked_by_word_count_guardrail"] is True


def test_typed_jev_calls_in_qualification_and_feedback_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Verifies qualification.evaluate_intent_expected_value and indexing.feedback_loop
    use typed System One state+questions primitives rather than broken json_mode kwargs.
    """
    from pseofactory import qualification
    from pseofactory.indexing.feedback_loop import GSCRootCauseClassifier

    spec = importlib.util.find_spec("pseofactory.jev_client")
    assert spec is not None, "pseofactory.jev_client module must exist"
    jev_client = importlib.import_module("pseofactory.jev_client")
    get_jev_client = getattr(jev_client, "get_jev_client")
    evaluate_intent_expected_value = getattr(qualification, "evaluate_intent_expected_value", None)
    assert evaluate_intent_expected_value is not None, "qualification.evaluate_intent_expected_value must exist"

    captured_calls = []

    def fake_evaluate(state: Dict[str, Any], questions: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        captured_calls.append({"state": state, "questions": questions})
        if "expected_value" in questions:
            return {
                "answers": {
                    "expected_value": {
                        "score": 2.7,
                        "confidence": 0.90,
                        "probabilities": {"0": 0.01, "1": 0.04, "2": 0.25, "3": 0.70},
                    },
                    "is_zero_click_single_fact": {
                        "noul": 0.05,
                        "probabilities": {"true": 0.05, "false": 0.95},
                    },
                }
            }
        return {
            "answers": {
                "classification": {
                    "choice": "CONTENT_DEPTH_DEFICIT",
                    "confidence": 0.88,
                    "probabilities": {"CONTENT_DEPTH_DEFICIT": 0.88},
                }
            }
        }

    client = get_jev_client()
    monkeypatch.setattr(client, "evaluate", fake_evaluate)
    monkeypatch.setattr(client, "is_available", lambda: True)

    ev_res = evaluate_intent_expected_value(
        {
            "query": "qsbs section 1202 state conformity tax calculator",
            "invoke_jev_live": True,
            "force_jev_in_test": True,
        }
    )
    assert ev_res["passed"] is True
    assert ev_res["triage_source"] == "jev_system_one"
    assert ev_res["expected_value_score"] >= 0.80
    assert len(captured_calls) == 1
    assert "expected_value" in captured_calls[0]["questions"]
    assert captured_calls[0]["questions"]["expected_value"]["type"] == "score"

    diag = GSCRootCauseClassifier._triage_unclassified_anomaly(
        url="https://profithelm.com/tools/section-179-calculator/",
        eff_cov="Crawled - currently not indexed",
        eff_err="Failed preflight indexing airlock criteria",
        data={
            "status": "QUARANTINED",
            "stage": "PREFLIGHT",
            "invoke_jev_live": True,
            "force_jev_in_test": True,
        },
        base_meta={},
        section="tools",
        child_sitemap="sitemap-tools.xml",
        child_sitemap_url="https://profithelm.com/sitemap-tools.xml",
        date_bucket="2026-11-07",
        submitted_scope="SUBMITTED_ONLY",
    )
    assert diag is not None
    assert len(captured_calls) == 2
    assert "classification" in captured_calls[1]["questions"]
    assert captured_calls[1]["questions"]["classification"]["type"] == "choice"


def test_verifier_catches_six_new_jev_seo_search_central_rules(tmp_path: Path) -> None:
    """
    Verifies audit_estate_technical_seo_and_cannibalization detects:
    1. generic_anchors ("click here", "read more")
    2. deep_pages (click depth > 3 from /)
    3. missing_image_alt and missing_image_dimensions
    4. heavy_html (> 500 KB)
    5. missing_html_lang, missing_viewport_meta, and multiple_title_tags
    """
    from pseofactory.verifier import audit_estate_technical_seo_and_cannibalization

    dist = tmp_path / "dist"
    (dist / "tools" / "hop1").mkdir(parents=True)
    (dist / "tools" / "hop2").mkdir(parents=True)
    (dist / "tools" / "hop3").mkdir(parents=True)
    (dist / "tools" / "hop4").mkdir(parents=True)

    def make_page(title: str, h1: str, body: str, lang: str = ' lang="en"', vp: bool = True, extra_title: str = "") -> str:
        vp_tag = '<meta name="viewport" content="width=device-width, initial-scale=1">' if vp else ""
        return (
            f"<!DOCTYPE html><html{lang}><head>"
            f"<title>{title}</title>{extra_title}{vp_tag}"
            f'<meta name="description" content="Comprehensive statutory calculation guide and interactive model for {title} under federal rules.">'
            f'<link rel="canonical" href="https://profithelm.com/">'
            f'<meta property="og:url" content="https://profithelm.com/">'
            f'<meta property="og:title" content="{title}">'
            f'<meta name="twitter:card" content="summary_large_image">'
            f"</head><body><h1>{h1}</h1>{body}</body></html>"
        )

    # Fix canonicals per route
    def write_route(rel: str, route_url: str, title: str, h1: str, body: str, lang: str = ' lang="en"', vp: bool = True, extra_title: str = "") -> None:
        html_str = make_page(title, h1, body, lang=lang, vp=vp, extra_title=extra_title).replace(
            "https://profithelm.com/", route_url
        )
        (dist / rel).write_text(html_str, encoding="utf-8")

    # Root links to hop1 using generic anchor "click here" and has an <img> missing alt & width/height
    write_route(
        "index.html",
        "https://profithelm.com/",
        "ProfitHelm Statutory Tax Calculators & Financial Models",
        "ProfitHelm Statutory Tax Calculators",
        '<a href="/tools/hop1/">click here</a><img src="/logo.png">',
        lang="",
        vp=False,
        extra_title="<title>Second Title</title>",
    )
    write_route(
        "tools/hop1/index.html",
        "https://profithelm.com/tools/hop1/",
        "Hop One Statutory Section 179 Equipment Tax Calculator",
        "Hop One Statutory Section 179 Calculator",
        '<a href="/tools/hop2/">Hop Two Tax Calculator</a>',
    )
    write_route(
        "tools/hop2/index.html",
        "https://profithelm.com/tools/hop2/",
        "Hop Two Statutory Section 1031 Exchange Tax Calculator",
        "Hop Two Statutory Section 1031 Calculator",
        '<a href="/tools/hop3/">Hop Three Tax Calculator</a>',
    )
    write_route(
        "tools/hop3/index.html",
        "https://profithelm.com/tools/hop3/",
        "Hop Three Statutory Section 1202 QSBS Tax Calculator",
        "Hop Three Statutory Section 1202 Calculator",
        '<a href="/tools/hop4/">Hop Four Tax Calculator</a>',
    )
    # hop4 is 4 clicks from / and > 500KB
    heavy_padding = "<!-- " + ("x" * 515_000) + " -->"
    write_route(
        "tools/hop4/index.html",
        "https://profithelm.com/tools/hop4/",
        "Hop Four Statutory Corporate AMT CAMT Tax Calculator",
        "Hop Four Statutory Corporate AMT Calculator",
        f"<p>Deep heavy page</p>{heavy_padding}",
    )

    rep = audit_estate_technical_seo_and_cannibalization(dist_dir=dist, property_id="profithelm")
    assert rep["passed"] is False
    assert rep["generic_anchors_count"] >= 1
    assert rep["deep_pages_count"] >= 1
    assert rep["missing_image_alt_count"] >= 1
    assert rep["missing_image_dimensions_count"] >= 1
    assert rep["heavy_html_pages_count"] >= 1
    assert rep["missing_html_lang_count"] >= 1
    assert rep["missing_viewport_meta_count"] >= 1
    assert rep["multiple_titles_count"] >= 1


def test_x_like_2109835011772035193_capability_matrix_and_live_estates() -> None:
    from pseofactory import verifier

    X_LIKE_2109835011772035193_CAPABILITY_MATRIX = getattr(
        verifier, "X_LIKE_2109835011772035193_CAPABILITY_MATRIX", []
    )
    evaluate_x_like_2109835011772035193_capability_matrix = getattr(
        verifier, "evaluate_x_like_2109835011772035193_capability_matrix", None
    )
    score_estate_jev_seo_rubric = getattr(verifier, "score_estate_jev_seo_rubric", None)

    assert len(X_LIKE_2109835011772035193_CAPABILITY_MATRIX) >= 10
    assert evaluate_x_like_2109835011772035193_capability_matrix is not None
    assert score_estate_jev_seo_rubric is not None
    res = evaluate_x_like_2109835011772035193_capability_matrix(include_live_estate_audit=True)
    assert res["pointer"] == "x-like:2109835011772035193"
    assert res["author_handle"] == "haoge6699"
    assert res["status"] == "PASS"
    assert res["passed"] is True

    for tid in ("profithelm", "prexvo", "gainhelm"):
        t_rep = res["tenant_reports"][tid]
        assert t_rep["passed"] is True
        assert t_rep["generic_anchors_count"] == 0
        assert t_rep["deep_pages_count"] == 0
        assert t_rep["missing_image_alt_count"] == 0
        assert t_rep["missing_image_dimensions_count"] == 0
        assert t_rep["heavy_html_pages_count"] == 0

        rubric = score_estate_jev_seo_rubric(property_id=tid)
        assert rubric["overall_score"] >= 95.0
        assert rubric["status"] == "PASS"


def test_p2_builder_distinct_models_and_zero_broken_links_on_real_estate(tmp_path: Path) -> None:
    """
    Verifies:
    1. CompetitorGapEngine.enrich_candidate_spec produces distinct statutory models for
       QSBS Section 1202, Section 199A QBI, and Corporate AMT (CAMT) rather than falling back
       to Section 179 Grounded Model.
    2. Compiling a new P2 page against live tenant tool slugs emits zero broken internal links
       and passes audit_estate_technical_seo_and_cannibalization + evaluate_page_prepublish_gate.
    3. _titles_match in audit.py passes on 0% State Tax spoke titles vs H1 rate schedule headings.
    """
    from pseofactory.audit import _titles_match
    from pseofactory.compiler import compile_high_effort_page
    from pseofactory.competitor import CompetitorGapEngine
    from pseofactory.tenant_facts import TenantFactStore

    assert _titles_match(
        "Alaska 2027 Tax Calculator (0% State Tax) | ProfitHelm",
        "Alaska 2027 Tax Brackets & Statutory Rate Schedules",
    )

    prof = TenantFactStore.get_instance().get_profile("profithelm")
    ge = CompetitorGapEngine(tenant_profile=prof)

    qsbs_spec = ge.enrich_candidate_spec(
        {
            "slug": "qsbs-section-1202-state-conformity-tax-calculator",
            "query": "qsbs section 1202 state conformity tax calculator",
            "property_id": "profithelm",
            "tenant": "profithelm",
        }
    )
    qbi_spec = ge.enrich_candidate_spec(
        {
            "slug": "section-199a-qbi-phaseout-wage-limit-calculator",
            "query": "section 199a qbi phaseout wage limit calculator",
            "property_id": "profithelm",
            "tenant": "profithelm",
        }
    )
    camt_spec = ge.enrich_candidate_spec(
        {
            "slug": "corporate-amt-camt-book-income-minimum-tax-calculator",
            "query": "corporate amt camt book income minimum tax calculator",
            "property_id": "profithelm",
            "tenant": "profithelm",
        }
    )

    assert qsbs_spec["model_name"] != "Section 179 Grounded Model"
    assert "1202" in qsbs_spec["statutory_authority"]
    assert qbi_spec["model_name"] != "Section 179 Grounded Model"
    assert "199A" in qbi_spec["statutory_authority"]
    assert camt_spec["model_name"] != "Section 179 Grounded Model"
    assert "55" in camt_spec["statutory_authority"] or "56A" in camt_spec["statutory_authority"]

    # When compiled with live ProfitHelm tool slugs, qsbs page must not link to non-existent
    # /tools/qsbs-section-1202-calculator/ or /tools/tcja-sunset-bracket-calculator/
    live_ph_slugs = {
        p.name
        for p in Path("/home/ubuntuadmin/projects/profithelm-platform/dist/tools").iterdir()
        if p.is_dir() and (p / "index.html").is_file()
    }
    qsbs_spec["existing_tool_slugs"] = sorted(live_ph_slugs)
    compiled = compile_high_effort_page(qsbs_spec)
    html_out = compiled["html"]
    assert "/tools/qsbs-section-1202-calculator/" not in html_out
    assert "/tools/tcja-sunset-bracket-calculator/" not in html_out

    spec = importlib.util.find_spec("pseofactory.jev_client")
    assert spec is not None
    jev_client = importlib.import_module("pseofactory.jev_client")
    evaluate_page_prepublish_gate = getattr(jev_client, "evaluate_page_prepublish_gate")
    gate = evaluate_page_prepublish_gate(
        html_content=html_out,
        candidate_spec=qsbs_spec,
        existing_pages=[],
    )
    assert gate["passed"] is True


def test_p2_daily_builder_stale_ledger_reconciliation_and_fallback_manifests(tmp_path: Path) -> None:
    """
    Verifies:
    1. RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS includes
       qsbs-section-1202-state-conformity-tax-calculator and
       RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS includes
       dora-ict-third-party-risk-compliance-cost-calculator.
    2. execute_autonomous_daily_trend_page_build reconciles stale ledger entries whose
       output_file is missing on disk, resets the queue item from BUILT to PENDING,
       re-materializes the page, and writes calculation_manifest into deployed_voids.json.
    """
    import json
    from pseofactory.maintenance import ConfigurablePropertyAdapter, RetroReflectionEngine, TenantRegistry
    from pseofactory.pipeline import execute_autonomous_daily_trend_page_build

    assert "qsbs-section-1202-state-conformity-tax-calculator" in RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS
    assert "dora-ict-third-party-risk-compliance-cost-calculator" in RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS

    gh_repo = tmp_path / "gainhelm"
    gh_dist = gh_repo / "dist"
    (gh_dist / "tools").mkdir(parents=True, exist_ok=True)
    (gh_dist / "index.html").write_text("<html><body><main></main></body></html>", encoding="utf-8")
    (gh_dist / "tools" / "index.html").write_text("<html><body><main></main></body></html>", encoding="utf-8")

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="gainhelm",
            brand_name="GainHelm",
            domain="gainhelm.com",
            canonical_base="https://gainhelm.com",
            dist_dir=gh_dist,
            repo_path=gh_repo,
        )
    )

    queue_file = tmp_path / "void_candidates.jsonl"
    queue_file.write_text(
        json.dumps(
            {
                "property_id": "gainhelm",
                "tenant": "gainhelm",
                "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                "query": "dora ict third party risk compliance cost calculator",
                "title": "DORA ICT Third-Party Risk Compliance Cost Model",
                "action": "BUILD_PAGE",
                "status": "BUILT",
                "composite_profit_yield": 92.4,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ledger_file = tmp_path / "daily_ledger.json"
    missing_out = gh_dist / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html"
    ledger_file.write_text(
        json.dumps(
            {
                "days": {
                    "2026-11-07": {
                        "gainhelm": [
                            {
                                "property_id": "gainhelm",
                                "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                                "output_file": str(missing_out),
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    res = execute_autonomous_daily_trend_page_build(
        property_ids=["gainhelm"],
        void_candidates_path=queue_file,
        ledger_path=ledger_file,
        date_key="2026-11-07",
        registry=reg,
        dry_run=False,
        enable_gitops=False,
        dispatch_push_indexing=False,
    )
    assert res["reconciled_stale_ledger_count"] == 1
    assert res["built_count"] == 1
    assert missing_out.is_file()
    dv_file = gh_repo / "content" / "deployed_voids.json"
    assert dv_file.is_file()
    dv_data = json.loads(dv_file.read_text(encoding="utf-8"))
    assert len(dv_data) == 1
    assert dv_data[0]["slug"] == "dora-ict-third-party-risk-compliance-cost-calculator"
    assert isinstance(dv_data[0].get("calculation_manifest"), dict)
    assert 50 <= len(f"{dv_data[0]['title']} | GainHelm") <= 60

    from pseofactory.affiliates import reposition_affiliate_placements_from_gsc_signals
    import inspect
    import pseofactory.maintenance as maint_mod

    assert 'pv.get("source") != "p2_autonomous_daily_builder"' in inspect.getsource(
        maint_mod.reflect_and_recompile_all_assets
    )

    built_html = missing_out.read_text(encoding="utf-8")
    assert 'id="partner-registration-drawer"' in built_html
    retro_html, _ = reposition_affiliate_placements_from_gsc_signals(
        built_html,
        property_id="gainhelm",
        slug="dora-ict-third-party-risk-compliance-cost-calculator",
    )
    assert 'id="partner-registration-drawer"' in retro_html


