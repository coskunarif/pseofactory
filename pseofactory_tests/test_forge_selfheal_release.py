"""
Regression tests for the self-healing release path (forge-selfheal):
- watcher verdict normalization ("FAILED" used to ship as success)
- automatic rollback of a pushed release on CI or live edge failure
- transient edge failure re-verification (no rollback of correct content)
- latency SLO vs hard deploy gate
- no hourly churn from volatile trend counters in published manifests
Zero em-dashes. Zero en-dashes.
"""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from pseofactory import gitops
from pseofactory.gitops import GitOpsCoordinator, LiveEdgeVerifier


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def tenant_repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    repo = tmp_path / "tenant"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "dist").mkdir()
    (repo / "dist" / "index.html").write_text("<html>known good</html>\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "known good")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-u", "origin", "main")
    monkeypatch.setenv("AGY_WORKTREES_BASE", str(tmp_path / "no_worktrees"))
    monkeypatch.setenv("PSEUFACTORY_GIT_BACKOFF", "0.01,0.01,0.01")
    monkeypatch.setenv("PSEUFACTORY_EDGE_RECHECK_DELAY_S", "0")
    return repo, origin


def _make_release_change(repo):
    (repo / "dist" / "index.html").write_text("<html>broken release</html>\n", encoding="utf-8")


def test_ci_result_is_failure_covers_every_failure_spelling():
    ci_result_is_failure = getattr(gitops, "ci_result_is_failure", None)
    assert callable(ci_result_is_failure), "gitops must expose a single watcher-verdict normalizer"
    for bad in ("FAIL", "FAILED", "failed", "CI_TIMEOUT", "TIMEOUT", "ERROR", "CANCELLED"):
        assert ci_result_is_failure({"status": bad}) is True, bad
    for ok in ("SUCCESS", "PASSED", "SKIPPED", "SKIPPED_NO_GH"):
        assert ci_result_is_failure({"status": ok}) is False, ok
    assert ci_result_is_failure(None) is False


def test_failed_deploy_status_is_not_shipped_and_release_is_rolled_back(tenant_repo):
    repo, origin = tenant_repo
    known_good = _git(repo, "rev-parse", "HEAD")
    known_good_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    _make_release_change(repo)

    seen = []

    def fake_watch(self, head_sha, repo_path=None, run_id=None):
        seen.append(head_sha)
        # First call: the release deploy failed (local Wrangler path spelling).
        # Second call: the rollback commit deploys fine.
        return {"status": "FAILED", "reason": "wrangler pages deploy failed"} if len(seen) == 1 else {"status": "SUCCESS"}

    coord = GitOpsCoordinator(repo_path=repo, run_id="rb-ci", dry_run=False, workflow="ci.yml")
    with patch.object(gitops.CICDWatcher, "watch", fake_watch):
        res = coord.dispatch_to_shipper(property_id="test_tenant", skip_edge=True, workflow="ci.yml")

    assert res.status == "CI_FAILURE", f"a FAILED deploy was shipped as {res.status}"
    rb = res.details.get("rollback") or {}
    assert rb["status"] == "ROLLED_BACK", rb
    assert len(seen) == 2 and seen[1] == rb["revert_sha"]
    # main and origin/main are back on the known-good tree, via a forward commit (no rewrite)
    assert _git(repo, "rev-parse", "HEAD^{tree}") == known_good_tree
    assert subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "main^{tree}"], capture_output=True, text=True, check=True
    ).stdout.strip() == known_good_tree
    assert _git(repo, "merge-base", "--is-ancestor", known_good, "HEAD") == ""
    assert (repo / "dist" / "index.html").read_text(encoding="utf-8") == "<html>known good</html>\n"


def test_edge_failure_after_recheck_rolls_back_and_reverifies(tenant_repo):
    repo, origin = tenant_repo
    known_good_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    _make_release_change(repo)
    calls = []

    def fake_edge(self, base_url, dist_dir=None, dry_run=False, sample_tools=None):
        calls.append(base_url)
        if len(calls) <= 2:
            return {"status": "FAIL", "error": "Live-vs-local SSR metric mismatch"}
        return {"status": "PASS", "error": None}

    coord = GitOpsCoordinator(repo_path=repo, run_id="rb-edge", dry_run=False)
    with patch.object(LiveEdgeVerifier, "verify_edge_deployment", fake_edge):
        res = coord.dispatch_to_shipper(
            property_id="test_tenant", skip_ci=True, edge_url="https://tenant.example", dist_dir=repo / "dist"
        )

    assert res.status == "EDGE_VERIFICATION_FAILED"
    assert len(calls) == 3  # first probe, delayed recheck, post-rollback verification
    assert (res.details.get("rollback") or {}).get("status") == "ROLLED_BACK"
    assert _git(repo, "rev-parse", "HEAD^{tree}") == known_good_tree


def test_transient_edge_failure_recovers_on_recheck_without_rollback(tenant_repo):
    repo, origin = tenant_repo
    _make_release_change(repo)
    calls = []

    def fake_edge(self, base_url, dist_dir=None, dry_run=False, sample_tools=None):
        calls.append(base_url)
        return {"status": "FAIL", "error": "timeout"} if len(calls) == 1 else {"status": "PASS", "error": None}

    coord = GitOpsCoordinator(repo_path=repo, run_id="rb-transient", dry_run=False)
    with patch.object(LiveEdgeVerifier, "verify_edge_deployment", fake_edge):
        res = coord.dispatch_to_shipper(
            property_id="test_tenant", skip_ci=True, edge_url="https://tenant.example", dist_dir=repo / "dist"
        )

    assert res.status in ("SUCCESS", "COMPLETED")
    assert (repo / "dist" / "index.html").read_text(encoding="utf-8") == "<html>broken release</html>\n"
    assert subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "main"], capture_output=True, text=True, check=True
    ).stdout.strip() == _git(repo, "rev-parse", "HEAD")


def test_rollback_refuses_when_head_moved_past_failed_release(tenant_repo):
    repo, _ = tenant_repo
    base = _git(repo, "rev-parse", "HEAD")
    _make_release_change(repo)
    _git(repo, "commit", "-am", "release")
    failed = _git(repo, "rev-parse", "HEAD")
    (repo / "dist" / "other.html").write_text("newer work", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "newer work by another writer")
    coord = GitOpsCoordinator(repo_path=repo, run_id="rb-moved", dry_run=False)
    assert hasattr(coord, "auto_rollback_release"), "shipper has no automatic rollback"
    rb = coord.auto_rollback_release(
        target_dir=repo, failed_sha=failed, known_good_sha=base, run_id="rb-moved", property_id="test_tenant", reason="x"
    )
    assert rb["status"] == "SKIPPED_HEAD_MOVED"
    assert (repo / "dist" / "other.html").exists()


def _probe_factory(root_latency_ms):
    def fake_verify_url(url, user_agent=None):
        body = (
            "<urlset><loc>https://prexvo.com/</loc></urlset>"
            if "sitemap" in url
            else "<html><head><title>Prexvo</title><link rel='canonical' href='https://prexvo.com/'/></head><body>Prexvo</body></html>"
        )
        return {
            "url": url,
            "status": 200,
            "latency_ms": root_latency_ms if url.endswith(".com/") else 100.0,
            "has_canonical": True,
            "has_title": True,
            "content": body,
        }

    return fake_verify_url


def test_slow_probe_is_an_slo_signal_not_a_failed_deploy():
    verifier = LiveEdgeVerifier()
    with patch.object(verifier, "verify_url", side_effect=_probe_factory(503.1)):
        res = verifier.verify_edge_deployment("https://prexvo.com")
    assert res["latency_sla"] is False
    assert res["all_passed"] is True
    assert res["status"] == "PASS"


def test_outage_class_latency_still_fails_the_gate():
    verifier = LiveEdgeVerifier()
    with patch.object(verifier, "verify_url", side_effect=_probe_factory(4500.0)):
        res = verifier.verify_edge_deployment("https://prexvo.com")
    assert res["status"] == "FAIL"
    assert "hard limit" in (res["error"] or "")


def test_published_demand_telemetry_is_stable_across_trend_cycles(monkeypatch):
    from pseofactory import proprietary_signals as ps

    def cache_with(cycles, velocity, accel):
        return {
            "series_by_id": {},
            "keywords_by_prop": {
                "profithelm": [
                    {
                        "query_slug": "saas-runway-calculator",
                        "query": "saas runway calculator",
                        "property_id": "profithelm",
                        "source": "pseofactory/trends/data/trend_history.db",
                        "consecutive_cycles_count": cycles,
                        "latest_velocity": velocity,
                        "acceleration_2nd_deriv": accel,
                        "search_volume": 2940,
                        "cpc_usd": 4.2,
                        "keyword_difficulty": 30.0,
                        "historical_stability": 0.9,
                        "jev_score": 12.0,
                        "composite_profit_yield": 70.0,
                    }
                ]
            },
        }

    monkeypatch.setattr(ps, "_TREND_DB_CACHE", cache_with(417, 56.0, 12.0))
    b1 = ps.resolve_proprietary_signal_bundle("profithelm", "saas-runway-calculator")
    monkeypatch.setattr(ps, "_TREND_DB_CACHE", cache_with(418, 44.0, -3.0))
    b2 = ps.resolve_proprietary_signal_bundle("profithelm", "saas-runway-calculator")

    t1 = b1["proprietary_telemetry"]["demand_telemetry"]
    t2 = b2["proprietary_telemetry"]["demand_telemetry"]
    assert t1 == t2
    for k in ("consecutive_cycles_count", "latest_velocity", "acceleration_2nd_deriv"):
        assert k not in t1
    assert t1["source"] == "pseofactory/trends/data/trend_history.db"
    assert t1["jev_score"] > 0


def test_missing_gsccli_does_not_fake_url_inspection_pass(monkeypatch):
    from pseofactory.indexer import PushIndexer

    orchestrator = PushIndexer(domain="profithelm.com")
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    res = orchestrator.inspect_gsc_url("https://profithelm.com/tools/section-179-calculator/")
    assert res["is_indexed"] is False
    assert res["verdict"] != "PASS"
    assert res["status"] == "UNAVAILABLE"


def test_traffic_audit_reports_warn_when_gsc_harvest_throws(monkeypatch, tmp_path):
    from pseofactory.indexing_inspector import DailyIndexingInspector
    import pseofactory.seo_growth_loops as sgl

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        sgl,
        "harvest_and_sync_gsc_daily_timeline",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("gsccli auth expired")),
    )
    inspector = DailyIndexingInspector(tenant_id="profithelm", base_dir=tmp_path)
    res = inspector.audit_search_traffic()
    assert res["status"] == "WARN"
    assert res["reason"] == "GSC_TIMELINE_HARVEST_ERROR"


def test_inspector_does_not_override_failed_auto_remediation_to_pass(tmp_path):
    import json
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.telemetry import AtomicTelemetryLogger

    rollover = tmp_path / "rollover.json"
    quarantine = tmp_path / "quarantine.json"
    velocity = tmp_path / "velocity.json"
    recovery = tmp_path / "recovery.json"
    rollover.write_text(json.dumps(["https://profithelm.com/tools/t1/"]), encoding="utf-8")
    quarantine.write_text(json.dumps({}), encoding="utf-8")
    velocity.write_text(json.dumps({"routes": []}), encoding="utf-8")

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        base_dir=tmp_path,
        recovery_ledger_path=recovery,
        quarantine_ledger_path=quarantine,
        velocity_ledger_path=velocity,
        rollover_queue_path=rollover,
        telemetry_logger=AtomicTelemetryLogger(log_path=tmp_path / "t.jsonl"),
    )

    with patch(
        "pseofactory.indexing.feedback_loop.IndexingFeedbackLoop.run_feedback_cycle",
        return_value={"status": "FAILED", "error": "recompile error"},
    ):
        rep = inspector.run_inspection(dry_run=True, auto_remediate=True)

    assert rep["audit_status"] == "FAIL"


def test_supervisor_escalation_triggers_autonomous_self_healing(tmp_path):
    from pseofactory.maintenance import TenantRegistry
    from pseofactory.supervisor import AutonomousLifecycleSupervisor, MaintenanceResult

    sup = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        registry=TenantRegistry.default(),
        max_consecutive_failures=1,
    )
    fail_res = MaintenanceResult(
        property_id="profithelm",
        status="FAILED",
        assets_audited=10,
        assets_drifted=1,
        assets_refactored=0,
        assets_failed=1,
        failed_records=[{"error": "edge fail"}],
        engine_hash=None,
        duration_seconds=1.0,
    )
    with patch.object(sup.coordinator, "run_fleet", return_value={"profithelm": fail_res}), patch.object(
        sup.failure_streak,
        "record_cycle",
        return_value=[{"tenant_id": "profithelm", "streak": 3, "first_seen": "2026-11-06T00:00:00Z", "reason": "edge fail"}],
    ), patch(
        "pseofactory.gitops.reconcile_workspace_tracking_state",
        return_value={"status": "PASS"},
    ), patch(
        "pseofactory.indexing_inspector.DailyIndexingInspector.run_inspection",
        return_value={"audit_status": "PASS"},
    ) as mock_insp:
        res = sup.run_cycle(property_ids=["profithelm"], force=True, dry_run=False, enable_gitops=False)

    actions = res.get("self_healing_actions") or []
    assert len(actions) == 1
    assert actions[0]["status"] == "RECOVERED"
    assert mock_insp.called
    assert (tmp_path / ".agy" / "self_healing_ledger.jsonl").is_file()


def test_retro_reflection_flags_and_heals_volatile_telemetry_in_html_and_sidecar(tmp_path):
    import json
    from pseofactory.maintenance import RetroReflectionEngine

    raw_html = Path("/home/ubuntuadmin/projects/prexvo/dist/tools/icr-repayment-calculator/index.html").read_text(
        encoding="utf-8"
    )
    if '"consecutive_cycles_count":' not in raw_html:
        raw_html = raw_html.replace(
            '"property_id": "prexvo"',
            '"property_id": "prexvo",\n      "consecutive_cycles_count": 355',
            1,
        )
    missing = RetroReflectionEngine.audit_html_mechanics(raw_html)
    assert "calculation_manifest" in missing

    sidecar = tmp_path / "icr-repayment-calculator.json"
    sidecar.write_text(
        json.dumps(
            {
                "entity_type": "STUDENT_LOAN_REPAYMENT",
                "formula": "x",
                "inputs": {"x": 1},
                "published_output": 1.0,
                "statutory_economic_matrix": {"a": 1},
                "proprietary_telemetry": {
                    "demand_telemetry": {
                        "query": "icr repayment calculator",
                        "consecutive_cycles_count": 355,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert RetroReflectionEngine._sidecar_needs_sync(sidecar, raw_html) is True


