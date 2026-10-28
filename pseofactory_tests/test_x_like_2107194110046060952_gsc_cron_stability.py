"""
End-to-End Verification Suite for x-like:2107194110046060952 (@irentdumpsters):
Search Console Cron Loop Stability, 28-Day Measurement Cooldown Locks,
Composite Idempotency Keys, Minimum-Impression Statistical Significance Floors,
Positions 4-30 Striking-Distance Cohort Segmentation & Cannibalization Clustering.
Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pseofactory.audit import (
    X_LIKE_2107194110046060952_CAPABILITY_MATRIX,
    audit_code_slop_ratchet,
    evaluate_x_like_2107194110046060952_capability_matrix,
)
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.gsc_remediation import (
    AsyncRemediationQueue,
    audit_gsc_cron_cohort_and_cooldown_stability,
    calculate_candidate_roi,
    compile_remediation_overlay_spec,
    compute_composite_idempotency_key,
    evaluate_expired_overlays,
    evaluate_variance_threshold,
    expected_ctr_for_position,
    is_overlay_locked,
    persist_overlay_respecting_lock,
)
from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.seo_growth_loops import (
    _parse_gsccli_json_rows,
    compile_search_opportunity_briefs,
)


def test_x_like_2107194110046060952_capability_matrix_and_tradeoffs() -> None:
    """
    Verifies X_LIKE_2107194110046060952_CAPABILITY_MATRIX covers all 7 claims from
    @irentdumpsters's post and thread (@DevMarDe, @dannyveigatx) and passes live
    tenant cohort & cooldown audits across ProfitHelm and Prexvo.
    """
    assert len(X_LIKE_2107194110046060952_CAPABILITY_MATRIX) == 7
    res = evaluate_x_like_2107194110046060952_capability_matrix(include_live_tenant_check=True)
    assert res["status"] == "PASS"
    assert res["passed"] is True
    assert res["integrated_compounding_upgrades_count"] == 4
    assert res["already_solved_count"] == 2
    assert res["rejected_bloat_or_hype_count"] == 1
    assert "profithelm" in res["tenant_audits"]
    assert "prexvo" in res["tenant_audits"]
    assert res["tenant_audits"]["profithelm"]["status"] == "PASS"
    assert res["tenant_audits"]["prexvo"]["status"] == "PASS"
    assert_no_forbidden_dashes(json.dumps(res), context="x_like_2107194110046060952_matrix")


def test_28_day_measurement_cooldown_locks_and_state_machine(tmp_path: Path) -> None:
    """
    Verifies 28-day measurement cooldown lock defaults across:
      1. compile_remediation_overlay_spec (measurement_lock_days=28, lock_days=28)
      2. persist_overlay_respecting_lock (blocks re-writes while ACTIVE_LOCKED and
         enforces 28-day post-rollback cooldown on DEGRADED_ROLLED_BACK)
      3. AsyncRemediationQueue.process_tenant_batch (28-day lock window on completion)
      4. evaluate_expired_overlays (Day-28 transition to ACCRETIVE_CONFIRMED / DEGRADED_ROLLED_BACK)
    """
    spec = compile_remediation_overlay_spec(
        {
            "slug": "california-tax-brackets-2027",
            "query": "ca tax brackets 2027",
            "target_url": "https://profithelm.com/tools/california-tax-brackets-2027/",
            "position": 6.89,
            "impressions": 9,
            "clicks": 1,
        },
        tenant_id="profithelm",
    )
    assert spec["measurement_lock_days"] == 28
    assert spec["lock_days"] == 28
    assert is_overlay_locked(spec) is True

    created_dt = datetime.fromisoformat(spec["created_at"].replace("Z", "+00:00"))
    locked_dt = datetime.fromisoformat(spec["locked_until"].replace("Z", "+00:00"))
    assert 27.9 <= (locked_dt - created_dt).total_seconds() / 86400.0 <= 28.1

    ov_file = tmp_path / ".agy" / "overlays" / "california-tax-brackets-2027.json"
    eff1, written1 = persist_overlay_respecting_lock(ov_file, spec)
    assert written1 is True

    # Consecutive cron tick with shifted timestamps and same query must be a strict no-op
    spec_next_tick = dict(
        spec,
        created_at=(created_dt + timedelta(days=7)).isoformat(),
        locked_until=(locked_dt + timedelta(days=7)).isoformat(),
    )
    eff2, written2 = persist_overlay_respecting_lock(ov_file, spec_next_tick)
    assert written2 is False
    assert eff2["locked_until"] == eff1["locked_until"]

    # DEGRADED_ROLLED_BACK respects default 28-day cooldown when measurement_lock_days is omitted or 28
    now = datetime.now(timezone.utc)
    rb_file = tmp_path / ".agy" / "overlays" / "rap-payment-calculator.json"
    rb_spec = {
        "slug": "rap-payment-calculator",
        "status": "DEGRADED_ROLLED_BACK",
        "locked_until": (now - timedelta(days=1)).isoformat(),
        "rolled_back_at": (now - timedelta(days=20)).isoformat(),
    }
    rb_file.write_text(json.dumps(rb_spec), encoding="utf-8")
    _, written_day20 = persist_overlay_respecting_lock(
        rb_file,
        {"slug": "rap-payment-calculator", "status": "ACTIVE_LOCKED", "query": "rap calculator"},
    )
    assert written_day20 is False

    rb_spec["rolled_back_at"] = (now - timedelta(days=29)).isoformat()
    rb_file.write_text(json.dumps(rb_spec), encoding="utf-8")
    _, written_day29 = persist_overlay_respecting_lock(
        rb_file,
        {"slug": "rap-payment-calculator", "status": "ACTIVE_LOCKED", "query": "rap calculator"},
    )
    assert written_day29 is True

    # AsyncRemediationQueue sets 28-day lock upon task completion
    q = AsyncRemediationQueue(queue_path=tmp_path / "queue.json")
    enq = q.enqueue_batch(
        [
            {
                "tenant_id": "prexvo",
                "slug": "rap-payment-calculator",
                "target_url": "https://prexvo.com/tools/rap-payment-calculator/",
                "anomaly_type": "STRIKING_DISTANCE_QUERY",
                "overlay_spec": spec,
            }
        ],
        tenant_id="prexvo",
    )
    assert enq["enqueued_count"] == 1
    proc_res = q.process_tenant_batch("prexvo", worker_fn=lambda t: {"status": "COMPLETED"})
    assert proc_res["completed_count"] == 1
    tasks = q.get_tenant_tasks("prexvo")
    assert tasks[0]["measurement_lock_days"] == 28


def test_composite_idempotency_and_minimum_impression_significance_floor(tmp_path: Path) -> None:
    """
    Verifies:
      1. Sub-floor striking-distance rows (1-2 impressions) are classified as
         BELOW_STATISTICAL_SIGNIFICANCE_FLOOR in evaluate_variance_threshold and
         DEFERRED_BELOW_SIGNIFICANCE_FLOOR in compile_search_opportunity_briefs
         without mutating live dist/ HTML.
      2. Statistically significant striking-distance rows (positions 4-30, impr >= 3)
         inject overlays once and remain idempotent across consecutive cron ticks.
    """
    var_sub_floor = evaluate_variance_threshold(
        pos_delta=0.2,
        impr_pct_delta=5.0,
        cycles=2,
        dynamic_floor=3,
        current_impressions=1,
        current_position=18.5,
    )
    assert var_sub_floor["classification"] == "BELOW_STATISTICAL_SIGNIFICANCE_FLOOR"
    assert var_sub_floor["action"] == "NO_ACTION"
    assert var_sub_floor["statistical_significance_met"] is False

    var_sig = evaluate_variance_threshold(
        pos_delta=0.2,
        impr_pct_delta=5.0,
        cycles=2,
        dynamic_floor=3,
        current_impressions=9,
        current_position=22.4,
    )
    assert var_sig["classification"] == "SUSTAINED_DEMAND"
    assert var_sig["action"] == "REFACTOR_PAGE"
    assert var_sig["statistical_significance_met"] is True

    # Positions 21-30 striking distance in calculate_candidate_roi & expected_ctr_for_position
    assert expected_ctr_for_position(25.0) == 0.010
    roi_24 = calculate_candidate_roi(
        {
            "query": "how much will my student loan payment be",
            "target_url": "https://prexvo.com/tools/student-loan-repayment-calculator/",
            "position": 21.67,
            "impressions": 6,
            "clicks": 0,
        },
        tenant_id="prexvo",
    )
    assert roi_24["anomaly_type"] == "STRIKING_DISTANCE_QUERY"
    assert roi_24["striking_distance_16_30"] is True
    assert roi_24["striking_distance_4_30"] is True
    assert roi_24["statistical_significance_met"] is True

    # Seed two HTML pages in dist/: one with 1 impression (sub-floor), one with 9 impressions (significant)
    dist_dir = tmp_path / "dist"
    sub_html_path = dist_dir / "tools" / "sub-floor-calculator" / "index.html"
    sig_html_path = dist_dir / "tools" / "rap-payment-calculator" / "index.html"
    sub_html_path.parent.mkdir(parents=True, exist_ok=True)
    sig_html_path.parent.mkdir(parents=True, exist_ok=True)

    initial_sub_html = "<html><head><title>Sub Floor Calculator</title></head><body><h1>Sub Floor</h1></body></html>"
    initial_sig_html = "<html><head><title>RAP Payment Calculator</title></head><body><h1>RAP Calculator</h1></body></html>"
    sub_html_path.write_text(initial_sub_html, encoding="utf-8")
    sig_html_path.write_text(initial_sig_html, encoding="utf-8")

    gsc_bundle = {
        "current_rows": [
            {
                "query": "noisy single impression query",
                "canonical_path": "/tools/sub-floor-calculator",
                "impressions": 1,
                "clicks": 0,
                "position": 14.0,
            },
            {
                "query": "rap calculator",
                "canonical_path": "/tools/rap-payment-calculator",
                "impressions": 9,
                "clicks": 0,
                "position": 16.67,
            },
        ]
    }

    rep_tick_1 = compile_search_opportunity_briefs(
        property_id="prexvo",
        repo_root=tmp_path,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        apply_overlays=True,
        persist=True,
        min_impressions_floor=3,
    )
    briefs_by_slug = {b["slug"]: b for b in rep_tick_1["briefs"]}
    assert briefs_by_slug["sub-floor-calculator"]["statistical_significance_met"] is False
    assert briefs_by_slug["sub-floor-calculator"]["execution_status"] == "DEFERRED_BELOW_SIGNIFICANCE_FLOOR"
    assert sub_html_path.read_text(encoding="utf-8") == initial_sub_html

    assert briefs_by_slug["rap-payment-calculator"]["statistical_significance_met"] is True
    assert briefs_by_slug["rap-payment-calculator"]["measurement_lock_days"] == 28
    assert briefs_by_slug["rap-payment-calculator"]["execution_status"] == "INJECTED_INTO_DIST_HTML"
    html_after_tick_1 = sig_html_path.read_text(encoding="utf-8")
    assert html_after_tick_1 != initial_sig_html

    # Tick 2: Re-running with same telemetry must not mutate HTML or reset lock
    ov_after_tick_1 = json.loads((tmp_path / ".agy" / "overlays" / "rap-payment-calculator.json").read_text(encoding="utf-8"))
    rep_tick_2 = compile_search_opportunity_briefs(
        property_id="prexvo",
        repo_root=tmp_path,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        apply_overlays=True,
        persist=True,
        min_impressions_floor=3,
    )
    assert rep_tick_2["html_pages_injected_count"] == 0
    assert sig_html_path.read_text(encoding="utf-8") == html_after_tick_1
    ov_after_tick_2 = json.loads((tmp_path / ".agy" / "overlays" / "rap-payment-calculator.json").read_text(encoding="utf-8"))
    assert ov_after_tick_2["locked_until"] == ov_after_tick_1["locked_until"]


def test_google_search_console_cli_json_parsing_and_cannibalization_clustering(tmp_path: Path) -> None:
    """
    Verifies _parse_gsccli_json_rows parses google-search-console-cli 'rows'/'keys' output
    and audit_gsc_cron_cohort_and_cooldown_stability segments cohorts and cannibalization
    clusters (distinguishing intentional hub-spoke hierarchy from multi-URL cannibalization).
    """
    raw_cli_out = json.dumps(
        {
            "rows": [
                {
                    "keys": [
                        "michigan tax brackets 2027",
                        "https://profithelm.com/tools/irs-2027-tax-brackets/michigan/",
                    ],
                    "clicks": 1,
                    "impressions": 2,
                    "ctr": 0.5,
                    "position": 2.0,
                },
                {
                    "keys": [
                        "ca tax brackets 2027",
                        "https://profithelm.com/tools/california-tax-brackets-2027/",
                    ],
                    "clicks": 1,
                    "impressions": 9,
                    "ctr": 0.1111,
                    "position": 6.89,
                },
                {
                    "keys": [
                        "ca tax brackets 2027",
                        "https://profithelm.com/tools/2027-california-tax-brackets/",
                    ],
                    "clicks": 0,
                    "impressions": 3,
                    "ctr": 0.0,
                    "position": 6.0,
                },
                {
                    "keys": [
                        "alabama capital gains tax",
                        "https://profithelm.com/tools/section-1031-calculator/alabama/",
                    ],
                    "clicks": 0,
                    "impressions": 2,
                    "ctr": 0.0,
                    "position": 29.5,
                },
            ]
        }
    )
    parsed = _parse_gsccli_json_rows(raw_cli_out, dimensions=["query", "page"])
    assert len(parsed) == 4
    assert parsed[0]["query"] == "michigan tax brackets 2027"
    assert parsed[0]["page"] == "https://profithelm.com/tools/irs-2027-tax-brackets/michigan/"

    audit_rep = audit_gsc_cron_cohort_and_cooldown_stability(
        property_id="profithelm",
        repo_root=tmp_path,
        live_queries=parsed,
        min_impressions_floor=3,
        measurement_lock_days=28,
        dry_run=True,
    )
    assert audit_rep["status"] == "PASS"
    assert audit_rep["cohorts"]["top_3_winners_count"] == 1
    assert audit_rep["cohorts"]["striking_distance_4_30_count"] == 3
    assert audit_rep["cohorts"]["striking_21_30_count"] == 1
    assert audit_rep["cohorts"]["statistically_significant_striking_count"] == 2
    assert audit_rep["cohorts"]["sub_floor_suppressed_count"] == 1
    assert audit_rep["cannibalization"]["multi_url_queries_count"] == 1
    assert audit_rep["cannibalization"]["true_cannibalization_count"] == 1
    cluster = audit_rep["cannibalization"]["clusters"][0]
    assert cluster["query"] == "ca tax brackets 2027"
    assert cluster["canonical_winner_url"] == "https://profithelm.com/tools/california-tax-brackets-2027/"
    assert cluster["remediation_action"] == "CONSOLIDATE_TO_CANONICAL_WINNER"

    # Verify DailyIndexingInspector includes gsc_cooldown_cohort_audit
    inspector = DailyIndexingInspector(tenant_id="profithelm", base_dir=tmp_path)
    insp_rep = inspector.run_inspection(dry_run=True, auto_remediate=True)
    assert "gsc_cooldown_cohort_audit" in insp_rep
    assert insp_rep["gsc_cooldown_cohort_audit"]["status"] == "PASS"
    assert insp_rep["gsc_cooldown_cohort_audit"]["measurement_lock_days"] == 28

    ratchet = audit_code_slop_ratchet()
    assert ratchet["passed"] is True
