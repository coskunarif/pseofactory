"""
Regression tests for pipeline guard, verification fail-closed invariants,
historical-year / off-jurisdiction / discovery-artifact cannibalization guards,
dynamic tenant discovery, duplicate retro-scan avoidance, and honest CLI exits.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


def test_historical_year_cannibalization_and_off_jurisdiction_guards() -> None:
    """
    1. Historical years (2016..2023) are stripped from core_tokens just like 2024..2028
       so 'capital gains tax rate 2021 calculator' cannibalizes 'tcja-sunset-capital-gains'.
    2. Statutory CFR part numbers like '1904' are preserved in core_tokens.
    3. Non-US country queries (e.g. 'surety bond cost calculator philippines') are rejected
       for US-statutory tenants (profithelm, prexvo, lienbond), while EU DORA/AI Act on
       gainhelm and Section 301 China tariff queries on profithelm remain allowed.
    """
    import pseofactory.qualification as qual_mod
    from pseofactory.qualification import (
        assert_high_effort_content_qualified,
        check_search_intent_cannibalization,
        normalize_search_intent_tokens,
        qualify_search_intent,
    )

    tools = [{"slug": "tcja-sunset-capital-gains", "query": "capital gains tax calculator"}]
    for yr in ("2016", "2017", "2021", "2022", "2026"):
        norm = normalize_search_intent_tokens(f"capital gains tax rate {yr} calculator")
        assert yr not in norm["core_tokens"]
        cannib = check_search_intent_cannibalization(
            f"capital gains tax rate {yr} calculator",
            existing_tools=tools,
        )
        assert cannib["is_cannibalizing"] is True
        assert cannib["parent_slug"] == "tcja-sunset-capital-gains"

    # Preserve non-year 4-digit statutory numbers like 29 CFR 1904
    norm_osha = normalize_search_intent_tokens("29 cfr 1904 osha recordkeeping calculator")
    assert "1904" in norm_osha["core_tokens"]

    # Non-US foreign jurisdiction queries rejected through public qualification entrypoints
    verdict = qualify_search_intent(
        {"query": "surety bond cost calculator philippines", "property_id": "lienbond", "impressions": 200},
        existing_tools=[],
    )
    assert verdict.action == "REJECT_OFF_JURISDICTION"
    assert verdict.status == "PRUNE"

    with pytest.raises(ValueError, match="off-jurisdiction non-US"):
        assert_high_effort_content_qualified(
            {
                "query": "surety bond cost calculator philippines",
                "slug": "surety-bond-cost-calculator-philippines",
                "property_id": "lienbond",
                "statutory_authority": "40 U.S.C. Section 3131 Miller Act",
                "economic_dataset": "FRED Total Construction Spending Series",
                "model_name": "TestModel",
                "formula": "bond_amount * 0.015",
                "inputs": {"bond_amount": 50000.0},
                "published_output": 750.0,
                "sample_calculation": "50000 * 0.015 = 750",
            }
        )

    detect_non_us_jurisdiction = getattr(qual_mod, "detect_non_us_jurisdiction", None)
    assert callable(detect_non_us_jurisdiction), "detect_non_us_jurisdiction helper missing"
    assert detect_non_us_jurisdiction("surety bond cost calculator philippines", property_id="lienbond") == "philippines"
    assert detect_non_us_jurisdiction("capital gains tax calculator canada", property_id="profithelm") == "canada"
    assert detect_non_us_jurisdiction("student loan repayment calculator uk", property_id="prexvo") == "united_kingdom"

    # Legitimate EU compliance on gainhelm and US Section 301 China tariffs on profithelm stay allowed
    assert detect_non_us_jurisdiction("eu ai act high risk conformity assessment cost calculator", property_id="gainhelm") is None
    assert detect_non_us_jurisdiction("dora ict third party risk compliance cost calculator", property_id="gainhelm") is None
    assert detect_non_us_jurisdiction("section 301 china import tariff landed cost calculator", property_id="profithelm") is None


def test_non_page_discovery_artifacts_excluded_from_gsc_cannibalization() -> None:
    """
    GSC striking-distance rows for llms.txt, llms-full.txt, robots.txt, sitemap*.xml,
    feed.xml, and *.json must never be selected as cannibalization or REFACTOR_PAGE targets.
    """
    import pseofactory.qualification as qual_mod
    from pseofactory.qualification import check_search_intent_cannibalization

    for art in (
        "llms.txt",
        "llms-full.txt",
        "robots.txt",
        "sitemap.xml",
        "sitemap-hubs.xml",
        "feed.xml",
        "catalog.json",
        "ai-benchmarks.json",
    ):
        res = check_search_intent_cannibalization(
            "pslf calculator",
            existing_tools=[],
            gsc_rows=[
                {
                    "query": "pslf calculator",
                    "page": f"https://prexvo.com/{art}",
                    "position": 11.0,
                    "impressions": 80,
                }
            ],
        )
        assert res["is_cannibalizing"] is False, f"Artifact {art} was falsely matched: {res}"

    # Real tool page still matches properly even when llms.txt ranks higher in GSC
    res_real = check_search_intent_cannibalization(
        "pslf calculator",
        existing_tools=[],
        gsc_rows=[
            {
                "query": "pslf calculator",
                "page": "https://prexvo.com/llms.txt",
                "position": 8.0,
                "impressions": 200,
            },
            {
                "query": "pslf calculator",
                "page": "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
                "position": 12.0,
                "impressions": 50,
            },
        ],
    )
    assert res_real["is_cannibalizing"] is True
    assert res_real["parent_slug"] == "pslf-qualifying-payment-simulator"

    is_art_fn = getattr(qual_mod, "is_non_page_discovery_artifact", None)
    assert callable(is_art_fn), "is_non_page_discovery_artifact helper missing"
    assert is_art_fn("llms.txt") is True
    assert is_art_fn("pslf-qualifying-payment-simulator") is False


def test_daily_trend_builder_fail_closed_ymyl_gate_and_reweighted_queue_persist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    1. execute_autonomous_daily_trend_page_build fails closed when a compiled page violates
       detect_asset_partner_roster_and_slot_issues (such as a Prexvo suppressed-default page
       carrying commercial /r/ links) or off-jurisdiction guards, even after compiler fixes.
    2. execute_autonomous_daily_trend_page_build persists revenue_weighted_expansion_queue.json
       alongside void_candidates.jsonl when dry_run=False.
    """
    import pseofactory.maintenance as maint_mod
    import pseofactory.pipeline as pipe_mod
    from pseofactory.maintenance import ConfigurablePropertyAdapter, TenantRegistry
    from pseofactory.pipeline import execute_autonomous_daily_trend_page_build

    # Wrap retrofit_html so the Prexvo test slug always receives a contradictory
    # suppressed-default YMYL + commercial /r/ link section right before Stage 4 gating.
    # This proves pipeline.py fails closed independently of compiler.py fixes.
    orig_retrofit_html = maint_mod.RetroReflectionEngine.retrofit_html

    def _inject_contradictory_ymyl_retrofit(
        cls: Any,
        html_text: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        out_html, changed = orig_retrofit_html(html_text, *args, **kwargs)
        slug_arg = str(kwargs.get("slug") or "")
        if slug_arg == "discretionary-income-calculator-for-student-loans":
            poison_block = (
                '<section data-commercial-offers="suppressed-default">'
                '<a href="/r/splash_financial">Compare Refinance Rates</a>'
                "</section>"
            )
            if "</body>" in out_html:
                out_html = out_html.replace("</body>", f"{poison_block}</body>", 1)
            else:
                out_html = out_html + poison_block
        return out_html, changed

    monkeypatch.setattr(
        maint_mod.RetroReflectionEngine,
        "retrofit_html",
        classmethod(_inject_contradictory_ymyl_retrofit),
    )

    prexvo_dist = tmp_path / "prexvo" / "dist"
    (prexvo_dist / "tools").mkdir(parents=True, exist_ok=True)
    lienbond_dist = tmp_path / "lienbond" / "dist"
    (lienbond_dist / "tools").mkdir(parents=True, exist_ok=True)

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="prexvo",
            brand_name="Prexvo",
            domain="prexvo.com",
            canonical_base="https://prexvo.com",
            dist_dir=prexvo_dist,
            repo_path=tmp_path / "prexvo",
        )
    )
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="lienbond",
            brand_name="LienBond",
            domain="lienbond.com",
            canonical_base="https://lienbond.com",
            dist_dir=lienbond_dist,
            repo_path=tmp_path / "lienbond",
        )
    )

    queue_file = tmp_path / "void_candidates.jsonl"
    ledger_file = tmp_path / "daily_page_build_ledger.json"
    candidates = [
        {
            "property_id": "prexvo",
            "tenant": "prexvo",
            "slug": "discretionary-income-calculator-for-student-loans",
            "query": "discretionary income calculator for student loans",
            "title": "Discretionary Income Calculator For Student Loans",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 80.0,
        },
        {
            "property_id": "lienbond",
            "tenant": "lienbond",
            "slug": "surety-bond-cost-calculator-philippines",
            "query": "surety bond cost calculator philippines",
            "title": "Surety Bond Cost Calculator Philippines",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 93.0,
        },
    ]
    queue_file.write_text("\n".join(json.dumps(c) for c in candidates) + "\n", encoding="utf-8")

    # Sanity-check module binding is untouched
    assert pipe_mod.execute_autonomous_daily_trend_page_build is execute_autonomous_daily_trend_page_build

    res = execute_autonomous_daily_trend_page_build(
        property_ids=["prexvo", "lienbond"],
        void_candidates_path=queue_file,
        ledger_path=ledger_file,
        registry=reg,
        dry_run=False,
        enable_gitops=False,
        dispatch_push_indexing=False,
    )

    # Both broken candidates MUST be aborted fail-closed (never written to dist/)
    assert res["built_count"] == 0
    assert not (prexvo_dist / "tools" / "discretionary-income-calculator-for-student-loans" / "index.html").exists()
    assert not (lienbond_dist / "tools" / "surety-bond-cost-calculator-philippines" / "index.html").exists()

    aborted_by_slug = {a["slug"]: a["reason"] for a in res["aborted_candidates"]}
    assert "surety-bond-cost-calculator-philippines" in aborted_by_slug
    assert "non-US" in aborted_by_slug["surety-bond-cost-calculator-philippines"]
    assert "discretionary-income-calculator-for-student-loans" in aborted_by_slug
    assert (
        "PartnerRosterAndSlotContract" in aborted_by_slug["discretionary-income-calculator-for-student-loans"]
        or "AEOGEOThreePlaneReadiness" in aborted_by_slug["discretionary-income-calculator-for-student-loans"]
    )

    # revenue_weighted_expansion_queue.json MUST have been persisted freshly
    reweighted_json = tmp_path / "revenue_weighted_expansion_queue.json"
    assert reweighted_json.is_file()
    rw_data = json.loads(reweighted_json.read_text(encoding="utf-8"))
    assert "generated_at" in rw_data


def test_handoff_verifier_does_not_bypass_on_dirty_git_without_active_lock(
    tmp_path: Path,
) -> None:
    """
    DepartmentHandoffChainVerifier must NOT use dirty `git status --porcelain` to force
    in_flight_build=True, and must require a real active advisory flock via
    _has_active_build_lock (False on unheld lockfile, True only while live process holds LOCK_EX).
    """
    from pseofactory.supervisor import DepartmentHandoffChainVerifier

    # Stage 4 (_run_verification_stage) must not consult git status --porcelain to set in_flight_build
    stage4_src = inspect.getsource(DepartmentHandoffChainVerifier._run_verification_stage)
    assert "--porcelain" not in stage4_src

    has_lock = getattr(DepartmentHandoffChainVerifier, "_has_active_build_lock", None)
    assert callable(has_lock), "DepartmentHandoffChainVerifier._has_active_build_lock missing"

    test_pid_slug = f"guard_test_tenant_{tmp_path.name}"
    lock_path = Path(f"/tmp/{test_pid_slug}_factory.lock")
    try:
        # Unheld lock file must NOT trigger in-flight bypass
        lock_path.write_text("", encoding="utf-8")
        assert has_lock(test_pid_slug) is False

        # Spawn a child process that actually holds LOCK_EX on the tenant lock
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import fcntl, sys, time; "
                    f"f = open({str(lock_path)!r}, 'a+'); "
                    "fcntl.flock(f.fileno(), fcntl.LOCK_EX); "
                    "print('LOCKED', flush=True); "
                    "time.sleep(10)"
                ),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            line = holder.stdout.readline().strip() if holder.stdout else ""
            assert line == "LOCKED"
            assert has_lock(test_pid_slug) is True
        finally:
            holder.terminate()
            holder.wait(timeout=5)

        # Immediately after child exits, lock is released -> False
        assert has_lock(test_pid_slug) is False
    finally:
        lock_path.unlink(missing_ok=True)


def test_dynamic_tenant_discovery_in_verifier_and_drift_latch(tmp_path: Path) -> None:
    """
    Both drift.verify_all_tenants_aligned_for_latch and verifier dynamic tenant discovery
    must discover newly added .pseofactory.json tenants (50+ site scaling) rather than
    hardcoding 3 or 4 tenants.
    """
    import pseofactory.verifier as ver_mod
    from pseofactory.drift import verify_all_tenants_aligned_for_latch

    ws = tmp_path / "ws_50_sites"
    new_tenant = ws / "novacorp"
    (new_tenant / "dist").mkdir(parents=True, exist_ok=True)
    (new_tenant / ".git").mkdir(parents=True, exist_ok=True)
    (new_tenant / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": "novacorp",
                "domain": "novacorp.com",
                "canonical_base": "https://novacorp.com",
                "brand_name": "NovaCorp",
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    (new_tenant / "dist" / "index.html").write_text("<html><body>NovaCorp</body></html>", encoding="utf-8")

    ok, reasons = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        require_git_clean_and_pushed=False,
    )
    assert ok is False
    assert any("novacorp: missing substrate_lock.json" in r for r in reasons), reasons

    discover_fn = getattr(ver_mod, "_discover_live_audit_tenants", None)
    assert callable(discover_fn), "verifier._discover_live_audit_tenants missing"
    discovered = discover_fn(workspace_root=ws)
    assert "novacorp" in discovered


def test_supervisor_failure_streak_updates_timestamp_and_skips_duplicate_retro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    1. SupervisorFailureStreak.record_cycle always updates state['updated_at'].
    2. AutonomousLifecycleSupervisor.run_cycle skips redundant sequential
       RetroReflectionEngine.audit_estate when detect_engine_drift already verified the
       tenant on the same aligned engine hash.
    """
    import pseofactory.maintenance as maint_mod
    import pseofactory.supervisor as sup_mod
    from pseofactory.maintenance import ConfigurablePropertyAdapter, TenantRegistry
    from pseofactory.supervisor import AutonomousLifecycleSupervisor, SupervisorFailureStreak

    streak_file = tmp_path / "supervisor_failure_streak.json"
    streak_file.write_text(
        json.dumps({"consecutive_failures": 0, "tenants": {}, "updated_at": "2026-11-10T02:47:44+00:00"}),
        encoding="utf-8",
    )
    sfs = SupervisorFailureStreak(streak_file)
    sfs.record_cycle(cycle_ok=True, consecutive_failures=0, properties={}, scoped=False)
    updated_data = json.loads(streak_file.read_text(encoding="utf-8"))
    assert updated_data["updated_at"] != "2026-11-10T02:47:44+00:00"

    # Verify duplicate RetroReflectionEngine.audit_estate is skipped when detect_engine_drift
    # already returned tenants_retro_verified
    dist_dir = tmp_path / "prexvo" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="prexvo",
            brand_name="Prexvo",
            domain="prexvo.com",
            canonical_base="https://prexvo.com",
            dist_dir=dist_dir,
            repo_path=tmp_path / "prexvo",
        )
    )

    monkeypatch.setattr(
        sup_mod,
        "detect_engine_drift",
        lambda **kwargs: {
            "current_hash": "a" * 64,
            "drift_detected": False,
            "tenants_retro_verified": ["prexvo"],
        },
    )

    class _CleanRep:
        drifted_assets_count = 0

    monkeypatch.setattr(maint_mod.AssetIntegrityEvaluator, "audit_all", lambda self, *a, **k: _CleanRep())
    retro_calls: List[str] = []
    monkeypatch.setattr(
        maint_mod.RetroReflectionEngine,
        "audit_estate",
        classmethod(lambda cls, d, pid: retro_calls.append(pid) or {"status": "PASS", "stale_count": 0}),
    )

    sup = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        state_file=tmp_path / ".agy" / "engine_hash.json",
        ledger_file=tmp_path / ".agy" / "asset_ledger.json",
        heartbeat_path=tmp_path / ".agy" / "supervisor_heartbeat.json",
        registry=reg,
    )
    res = sup.run_cycle(dry_run=True, enable_gitops=False)
    assert res["status"] == "SKIPPED_ALIGNED"
    assert retro_calls == []


def test_cli_verify_handoffs_prints_failures_and_aio_observe_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    1. cmd_supervisor --verify-handoffs without --json prints stage failures and Failures list.
    2. cmd_aio_observe sample returns exit 1 when any tenant has 100% errors OR overall error
       rate >= 50%, and exit 0 when all tenants succeed with < 50% overall errors.
    """
    import pseofactory.aio_observatory as aio_mod
    import pseofactory.cli as cli_mod
    import pseofactory.supervisor as sup_mod

    monkeypatch.setattr(
        sup_mod,
        "verify_department_handoff_chain",
        lambda **kwargs: {
            "status": "FAIL",
            "stages_passed": 3,
            "stages_total": 6,
            "tenants_verified": ["profithelm", "prexvo"],
            "failing_stages_count": 3,
            "stages": {
                "VERIFICATION": {
                    "order": 4,
                    "status": "FAIL",
                    "upstream_stage": "ENGINEERING",
                    "downstream_stage": "SYNDICATION",
                    "inputs_verified": True,
                    "outputs_verified": True,
                    "failures": ["VERIFICATION[prexvo]: AEO/GEO check failed"],
                }
            },
            "failures": ["VERIFICATION[prexvo]: AEO/GEO check failed"],
        },
    )
    rc = cli_mod.cmd_supervisor(
        argparse.Namespace(verify_handoffs=True, dry_run=True, json=False)
    )
    out_txt = capsys.readouterr().out
    assert rc == 1
    assert "VERIFICATION[prexvo]: AEO/GEO check failed" in out_txt
    assert "Failures:" in out_txt

    # AIO observe exit code tests
    sample_pairs = [
        ("profithelm", "q1"),
        ("profithelm", "q2"),
        ("profithelm", "q3"),
        ("profithelm", "q4"),
        ("lienbond", "q_lb1"),
        ("lienbond", "q_lb2"),
    ]
    monkeypatch.setattr(aio_mod, "load_watchlist", lambda tenants=None: sample_pairs)

    class _FakeObs:
        def __init__(self, _db=None):
            self.payload: Dict[str, Any] = {}

        def sample(self, pairs, max_queries=None):
            return dict(self.payload)

    fake_obs = _FakeObs()
    monkeypatch.setattr(aio_mod, "AIOObservatory", lambda _db=None: fake_obs)

    # Case A: Single tenant (lienbond) has 100% errors even though overall error rate is 2/6 (33%)
    fake_obs.payload = {
        "sampled": 4,
        "found": 4,
        "errors": 2,
        "cost_usd": 0.01,
        "error_samples": [
            {"query": "q_lb1", "error": "treg HTTP 400"},
            {"query": "q_lb2", "error": "treg HTTP 400"},
        ],
    }
    rc_tenant_outage = cli_mod.cmd_aio_observe(
        argparse.Namespace(action="sample", db=None, window_days=7, tenant=None, query=None, max_queries=None)
    )
    capsys.readouterr()
    assert rc_tenant_outage == 1

    # Case B: Overall error rate >= 50% (3/6 errors across both tenants)
    fake_obs.payload = {
        "sampled": 3,
        "found": 3,
        "errors": 3,
        "cost_usd": 0.01,
        "error_samples": [
            {"query": "q1", "error": "treg HTTP 502"},
            {"query": "q2", "error": "treg HTTP 502"},
            {"query": "q_lb1", "error": "treg HTTP 400"},
        ],
    }
    rc_half_fail = cli_mod.cmd_aio_observe(
        argparse.Namespace(action="sample", db=None, window_days=7, tenant=None, query=None, max_queries=None)
    )
    capsys.readouterr()
    assert rc_half_fail == 1

    # Case C: Healthy run (<50% errors, every tenant has >=1 sampled)
    fake_obs.payload = {
        "sampled": 5,
        "found": 5,
        "errors": 1,
        "cost_usd": 0.01,
        "error_samples": [
            {"query": "q_lb1", "error": "treg HTTP 502"},
        ],
    }
    rc_ok = cli_mod.cmd_aio_observe(
        argparse.Namespace(action="sample", db=None, window_days=7, tenant=None, query=None, max_queries=None)
    )
    capsys.readouterr()
    assert rc_ok == 0


def test_load_and_enrich_deployed_voids_skips_legacy_off_jurisdiction_entries(
    tmp_path: Path,
) -> None:
    """
    load_and_enrich_deployed_voids must skip legacy off-jurisdiction non-US entries
    (such as lienbond's surety-bond-cost-calculator-philippines) so full estate rebuilds
    succeed without direct tenant repo edits, while keeping valid US voids and GainHelm
    EU compliance voids intact.
    """
    from pseofactory.estate_common import load_and_enrich_deployed_voids
    from pseofactory.qualification import assert_high_effort_content_qualified

    lb_repo = tmp_path / "lienbond"
    (lb_repo / "content").mkdir(parents=True, exist_ok=True)
    (lb_repo / "content" / "deployed_voids.json").write_text(
        json.dumps(
            [
                {
                    "slug": "surety-bond-cost-calculator-philippines",
                    "query": "surety bond cost calculator philippines",
                    "title": "Surety Bond Cost Calculator Philippines",
                },
                {
                    "slug": "miller-act-payment-bond-calculator",
                    "query": "miller act payment bond calculator",
                    "title": "Miller Act Payment Bond Calculator",
                    "formula": "bond_amount * 0.015",
                    "inputs": {"bond_amount": 100000.0},
                    "published_output": 1500.0,
                    "sample_calculation": "100000 * 0.015 = 1500",
                },
            ]
        ),
        encoding="utf-8",
    )

    known_lb: set = set()
    lb_voids = load_and_enrich_deployed_voids(
        repo_root=lb_repo,
        property_id="lienbond",
        domain="lienbond.com",
        brand_name="LienBond",
        canonical_base="https://lienbond.com",
        known_slugs=known_lb,
        default_authority="40 U.S.C. Section 3131 Miller Act",
        default_dataset="FRED Total Construction Spending Series",
    )
    loaded_lb_slugs = [v["slug"] for v in lb_voids]
    assert "surety-bond-cost-calculator-philippines" not in loaded_lb_slugs
    assert "surety-bond-cost-calculator-philippines" not in known_lb
    assert loaded_lb_slugs == ["miller-act-payment-bond-calculator"]
    assert_high_effort_content_qualified(lb_voids[0], context="test_estate_common:lienbond")

    # Non-US-statutory tenant (gainhelm) retains legitimate EU compliance voids
    gh_repo = tmp_path / "gainhelm"
    (gh_repo / "content").mkdir(parents=True, exist_ok=True)
    (gh_repo / "content" / "deployed_voids.json").write_text(
        json.dumps(
            [
                {
                    "slug": "eu-ai-act-conformity-fee-estimator",
                    "query": "eu ai act conformity fee estimator",
                    "title": "EU AI Act Conformity Fee Estimator",
                }
            ]
        ),
        encoding="utf-8",
    )
    gh_voids = load_and_enrich_deployed_voids(
        repo_root=gh_repo,
        property_id="gainhelm",
        domain="gainhelm.com",
        brand_name="GainHelm",
        canonical_base="https://gainhelm.com",
        known_slugs=set(),
        default_authority="Regulation (EU) 2024/1689 EU AI Act",
        default_dataset="IBM Cost of a Data Breach Report 2025",
    )
    assert [v["slug"] for v in gh_voids] == ["eu-ai-act-conformity-fee-estimator"]


def test_cmd_aio_observe_fails_closed_when_live_treg_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    aio-observe sample must exit non-zero (fail closed) with clear status/reason
    when PSEUFACTORY_LIVE_TREG != '1' and 0 queries were sampled, unless --dry-run is set.
    """
    import subprocess
    import pseofactory.cli as cli_mod

    monkeypatch.delenv("PSEUFACTORY_LIVE_TREG", raising=False)
    monkeypatch.delattr(subprocess.run, "assert_called", raising=False)
    monkeypatch.delattr(subprocess.run, "mock", raising=False)

    db_path = str(tmp_path / "aio_disabled.db")
    rc_fail = cli_mod.cmd_aio_observe(
        argparse.Namespace(
            action="sample",
            db=db_path,
            window_days=7,
            tenant=None,
            query=None,
            max_queries=1,
            dry_run=False,
        )
    )
    captured_fail = capsys.readouterr()
    assert rc_fail == 1
    out_fail = json.loads(captured_fail.out)
    assert out_fail["sampled"] == 0
    assert out_fail["skipped_live_disabled"] == 1
    assert out_fail["status"] == "FAIL"
    assert "PSEUFACTORY_LIVE_TREG" in out_fail["reason"]
    assert "PSEUFACTORY_LIVE_TREG" in captured_fail.err

    rc_dry = cli_mod.cmd_aio_observe(
        argparse.Namespace(
            action="sample",
            db=db_path,
            window_days=7,
            tenant=None,
            query=None,
            max_queries=1,
            dry_run=True,
        )
    )
    captured_dry = capsys.readouterr()
    assert rc_dry == 0
    out_dry = json.loads(captured_dry.out)
    assert out_dry["status"] == "DRY_RUN"


