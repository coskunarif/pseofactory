"""
Focused regression tests for:
1. Leak-proof headless Chrome process-group and temp user-data-dir cleanup
2. Pre-deploy cached headless Chrome gate inside MaintenanceLifecycle.run()
3. Weekly autonomous SEO tuning CLI command (weekly-seo-tune)
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any, Dict, List

import pytest

from pseofactory import browser_verifier, cli
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    AssetIntegrityReport,
    ConfigurablePropertyAdapter,
    MaintenanceLifecycle,
    RefactorCascadeEngine,
)
from pseofactory.supervisor import SupervisorTimeoutError


def _is_pid_alive(pid: int) -> bool:
    stat_file = Path(f"/proc/{pid}/stat")
    if stat_file.is_file():
        try:
            raw = stat_file.read_text(encoding="utf-8", errors="ignore")
            rparen = raw.rfind(")")
            if rparen != -1:
                state = raw[rparen + 2 :].split()[0]
                if state == "Z":
                    return False
        except Exception:
            pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _create_fake_chrome_script(tmp_path: Path, pid_record_file: Path) -> Path:
    """Creates an executable script mimicking Chrome: spawns a grandchild, serves /json/version."""
    script = tmp_path / "fake_chrome.py"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            from http.server import BaseHTTPRequestHandler, HTTPServer
            from pathlib import Path
            import os
            import subprocess
            import sys
            import time

            user_data_dir = None
            for arg in sys.argv[1:]:
                if arg.startswith("--user-data-dir="):
                    user_data_dir = arg.split("=", 1)[1]

            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            Path({str(pid_record_file)!r}).write_text(f"{{os.getpid()}},{{child.pid}},{{os.getpgid(0)}}", encoding="utf-8")

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{{"Browser":"FakeChrome/1.0"}}')
                def log_message(self, *args):
                    pass

            srv = HTTPServer(("127.0.0.1", 0), Handler)
            port = srv.server_address[1]
            if user_data_dir:
                Path(user_data_dir, "DevToolsActivePort").write_text(f"{{port}}\\n/devtools/browser/fake\\n", encoding="utf-8")
            srv.serve_forever()
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_headless_chrome_process_group_cleanup_on_timeout_and_interrupt(tmp_path: Path):
    """Proves _HeadlessChromiumInstance uses start_new_session=True and reaps pgid + tmp_dir on exceptions."""
    pid_record = tmp_path / "pids.txt"
    fake_chrome = _create_fake_chrome_script(tmp_path, pid_record)

    for exc_cls in (TimeoutError, SupervisorTimeoutError, KeyboardInterrupt):
        pid_record.unlink(missing_ok=True)
        captured_tmp_dir = ""
        with pytest.raises(exc_cls):
            with browser_verifier._HeadlessChromiumInstance(str(fake_chrome), is_headless_shell=True) as inst:
                captured_tmp_dir = inst.tmp_dir or ""
                assert captured_tmp_dir and Path(captured_tmp_dir).is_dir()
                assert inst.proc is not None
                assert inst.pgid == os.getpgid(inst.proc.pid)
                assert inst.pgid != os.getpgid(os.getpid())
                raise exc_cls("simulated failure")

        parent_pid, child_pid, pgid = [int(x) for x in pid_record.read_text(encoding="utf-8").split(",")]
        assert pgid == parent_pid
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and (_is_pid_alive(parent_pid) or _is_pid_alive(child_pid)):
            time.sleep(0.05)
        assert not _is_pid_alive(parent_pid), f"Parent PID {parent_pid} survived {exc_cls.__name__}"
        assert not _is_pid_alive(child_pid), f"Grandchild PID {child_pid} survived {exc_cls.__name__}"
        assert captured_tmp_dir and not Path(captured_tmp_dir).exists()


def test_headless_chrome_sigterm_handler_cleanup_and_restore(tmp_path: Path):
    """Proves SIGTERM during active Chrome worker kills entire pgid, deletes tmp_dir, and restores prior handlers."""
    pid_record = tmp_path / "sigterm_pids.txt"
    fake_chrome = _create_fake_chrome_script(tmp_path, pid_record)
    tmpdir_record = tmp_path / "tmpdir.txt"
    ready_flag = tmp_path / "ready.txt"

    runner = tmp_path / "sigterm_runner.py"
    runner.write_text(
        textwrap.dedent(
            f"""\
            import os
            from pathlib import Path
            import signal
            import time
            from pseofactory import browser_verifier

            def custom_prior(signum, frame):
                raise SystemExit(42)

            signal.signal(signal.SIGTERM, custom_prior)
            with browser_verifier._HeadlessChromiumInstance({str(fake_chrome)!r}, is_headless_shell=True) as inst:
                Path({str(tmpdir_record)!r}).write_text(inst.tmp_dir or "", encoding="utf-8")
                Path({str(ready_flag)!r}).write_text("ready", encoding="utf-8")
                time.sleep(30)
            """
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    proc = subprocess.Popen([sys.executable, str(runner)], env=env)
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not ready_flag.is_file():
            time.sleep(0.05)
        assert ready_flag.is_file()
        proc.send_signal(signal.SIGTERM)
        rc = proc.wait(timeout=10.0)
        assert rc == 42
    finally:
        if proc.poll() is None:
            proc.kill()

    parent_pid, child_pid, _pgid = [int(x) for x in pid_record.read_text(encoding="utf-8").split(",")]
    tmp_dir_path = Path(tmpdir_record.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and (_is_pid_alive(parent_pid) or _is_pid_alive(child_pid)):
        time.sleep(0.05)
    assert not _is_pid_alive(parent_pid)
    assert not _is_pid_alive(child_pid)
    assert not tmp_dir_path.exists()

    # Also verify _ChromeSignalGuard restores prior SIGTERM/SIGINT handlers cleanly
    def _sentinel(s, f):
        return None

    old_term = signal.getsignal(signal.SIGTERM)
    old_int = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGTERM, _sentinel)
        signal.signal(signal.SIGINT, _sentinel)
        with browser_verifier._ChromeSignalGuard():
            assert signal.getsignal(signal.SIGTERM) is browser_verifier._chrome_signal_handler
        assert signal.getsignal(signal.SIGTERM) is _sentinel
        assert signal.getsignal(signal.SIGINT) is _sentinel
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def test_reap_stale_cdp_workers_preserves_live_run_and_cleans_orphans(tmp_path: Path):
    """Proves reap_stale_cdp_workers cleans dead dirs while never touching a live process's dir."""
    orphan_dir = Path(tempfile.mkdtemp(prefix=browser_verifier._CDP_WORKER_TEMP_PREFIX, dir=tmp_path))
    (orphan_dir / "stale.txt").write_text("dead", encoding="utf-8")

    live_dir = Path(tempfile.mkdtemp(prefix=browser_verifier._CDP_WORKER_TEMP_PREFIX, dir=tmp_path))
    live_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", f"--user-data-dir={live_dir}"]
    )
    try:
        time.sleep(0.1)
        reaped = browser_verifier.reap_stale_cdp_workers(tmp_root=tmp_path, min_age_seconds=0.0)
        assert str(orphan_dir) in reaped
        assert not orphan_dir.exists()
        assert str(live_dir) not in reaped
        assert live_dir.is_dir()
        assert live_proc.poll() is None
    finally:
        live_proc.terminate()
        live_proc.wait(timeout=5.0)
        if live_dir.exists():
            import shutil
            shutil.rmtree(live_dir, ignore_errors=True)


def _init_clean_git_tenant(repo_root: Path, prop_id: str, html_body: str = "<html><body><h1>OK</h1></body></html>") -> ConfigurablePropertyAdapter:
    repo_root.mkdir(parents=True, exist_ok=True)
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".gitignore").write_text(".agy/\n", encoding="utf-8")
    (repo_root / ".pseofactory.json").write_text(
        json.dumps({"property_id": prop_id, "domain": f"{prop_id}.com", "canonical_base": f"https://{prop_id}.com"}),
        encoding="utf-8",
    )
    (dist_dir / "index.html").write_text(html_body, encoding="utf-8")
    (dist_dir / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset><url><loc>https://{prop_id}.com/</loc></url></urlset>',
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo_root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-q", "-m", "init"], check=True)
    return ConfigurablePropertyAdapter(
        property_id=prop_id,
        brand_name=prop_id.capitalize(),
        domain=f"{prop_id}.com",
        canonical_base=f"https://{prop_id}.com",
        dist_dir=dist_dir,
        repo_path=repo_root,
    )


def _mock_passing_gates(monkeypatch: pytest.MonkeyPatch, dist_dir: Path) -> None:
    """Stubs non-browser gates so MaintenanceLifecycle tests isolate the pre-deploy browser gate."""
    import pseofactory.maintenance as maint_mod
    import pseofactory.truth_gate as truth_mod

    class _PassEvaluator(AssetIntegrityEvaluator):
        def audit_all(self, adapter, check_engine_drift=True, check_ledger=True, ledger_path=None, state_file=None):
            return AssetIntegrityReport(
                property_id=adapter.property_id,
                total_assets_checked=1,
                compliant_assets_count=1,
                drifted_assets_count=0,
                drifted_assets=[],
                status="PASS",
            )

    monkeypatch.setattr(maint_mod, "AssetIntegrityEvaluator", _PassEvaluator)
    monkeypatch.setattr(
        maint_mod.CrossPropertyContaminationScanner,
        "scan_directory",
        lambda self, d, p: {},
    )
    monkeypatch.setattr(
        truth_mod.UnifiedTruthGate,
        "audit_estate",
        lambda self, *args, **kwargs: type(
            "TruthRep",
            (),
            {"passed": True, "violations": [], "files_audited": [str(dist_dir / "index.html")]},
        )(),
    )


def test_maintenance_predeploy_browser_gate_blocks_on_failure_and_skips_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verifies MaintenanceLifecycle.run():
    1. Skips browser audit when dist/ has no delta
    2. Runs cached UnifiedBrowserAuditor when dist/ changed + enable_gitops=True + enable_browser_audit=True
    3. Aborts BEFORE dispatch_to_shipper() when browser audit fails
    4. Proceeds to dispatch_to_shipper() when browser audit passes
    """
    import pseofactory.gitops as gitops_mod

    repo_root = tmp_path / "customgate"
    adapter = _init_clean_git_tenant(repo_root, "customgate")
    _mock_passing_gates(monkeypatch, adapter.dist_dir)

    browser_calls: List[Dict[str, Any]] = []
    shipper_calls: List[Dict[str, Any]] = []
    browser_outcome = {"passed": False, "failed_count": 1, "failed_routes": ["/"], "status": "FAIL", "findings": [{"route": "/", "passed": False, "error": "CLS=0.25"}]}

    class _FakeBrowserAuditor:
        def __init__(self, **kwargs):
            browser_calls.append(kwargs)

        def run_audit(self):
            return dict(browser_outcome)

    class _FakeGitOps:
        def __init__(self, **kwargs):
            pass

        def dispatch_to_shipper(self, **kwargs):
            shipper_calls.append(kwargs)
            return type("GitOpsRes", (), {"status": "SUCCESS", "error": None, "to_dict": lambda s: {"status": "SUCCESS"}})()

    monkeypatch.setattr(browser_verifier, "UnifiedBrowserAuditor", _FakeBrowserAuditor)
    monkeypatch.setattr(gitops_mod, "GitOpsCoordinator", _FakeGitOps)

    lifecycle = MaintenanceLifecycle(
        evaluator=AssetIntegrityEvaluator(),
        cascade_engine=RefactorCascadeEngine(),
    )
    # Replace evaluator with clean pass evaluator
    from pseofactory import maintenance as maint_mod
    lifecycle.evaluator = maint_mod.AssetIntegrityEvaluator()
    lifecycle.cascade_engine = RefactorCascadeEngine(evaluator=lifecycle.evaluator)

    # 1. Steady-state clean dist/ -> skipped, 0 browser calls, 0 shipper calls
    clean_res = lifecycle.run(
        adapter,
        enable_gitops=True,
        enable_distribution=False,
        enable_browser_audit=True,
        latch_workspace=False,
    )
    assert clean_res.status == "SKIPPED_NO_CHANGES"
    assert len(browser_calls) == 0
    assert len(shipper_calls) == 0

    # 2. Mutate dist/ and fail browser audit -> aborts BEFORE dispatch_to_shipper()
    (adapter.dist_dir / "index.html").write_text("<html><body><h1>Broken</h1></body></html>", encoding="utf-8")
    fail_res = lifecycle.run(
        adapter,
        enable_gitops=True,
        enable_distribution=False,
        enable_browser_audit=True,
        latch_workspace=False,
    )
    assert fail_res.status == "FAILED"
    assert fail_res.browser_audit_status == "FAILED"
    assert fail_res.gitops_status == "ABORTED_BROWSER_AUDIT"
    assert len(browser_calls) == 1
    assert browser_calls[0]["no_verify_cache"] is False
    assert browser_calls[0]["fail_closed"] is True
    assert len(shipper_calls) == 0

    # 3. Respects PYTEST_CURRENT_TEST when enable_browser_audit is not explicitly True
    no_override_res = lifecycle.run(
        adapter,
        enable_gitops=True,
        enable_distribution=False,
        latch_workspace=False,
    )
    assert no_override_res.status == "SUCCESS"
    assert no_override_res.browser_audit_status == "SKIPPED_TEST_ENV"
    assert len(browser_calls) == 1
    assert len(shipper_calls) == 1

    # 4. Explicit enable_browser_audit=True with passing browser audit -> ships!
    browser_outcome.update({"passed": True, "failed_count": 0, "failed_routes": [], "status": "PASS", "findings": []})
    pass_res = lifecycle.run(
        adapter,
        enable_gitops=True,
        enable_distribution=False,
        enable_browser_audit=True,
        latch_workspace=False,
    )
    assert pass_res.status == "SUCCESS"
    assert pass_res.browser_audit_status == "PASS"
    assert len(browser_calls) == 2
    assert len(shipper_calls) == 2


def test_cli_weekly_seo_tune_discovery_dry_run_no_delta_and_ship(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """
    Verifies `cli.py weekly-seo-tune`:
    - Dynamically discovers non-canonical tenants via `.pseofactory.json`
    - Handles `--dry-run` cleanly without invoking MaintenanceLifecycle
    - Leaves zero-delta tenants untouched (`NO_DIST_DELTA`) with clean git status (even without .agy/ in .gitignore)
    - Invokes MaintenanceLifecycle(enable_gitops=True) ONLY for tenants whose dist/ changed
    - Writes summary ledger JSON
    """
    import pseofactory.seo_growth_loops as seo_mod

    ws_root = tmp_path / "ws"
    alpha_root = ws_root / "alpha"
    beta_root = ws_root / "beta"
    _init_clean_git_tenant(alpha_root, "alpha")
    _init_clean_git_tenant(beta_root, "beta")
    # Remove .agy/ from beta's .gitignore to prove zero-delta tenants never leave untracked .agy/ files
    (beta_root / ".gitignore").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(beta_root), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(beta_root), "commit", "-q", "-m", "drop agy gitignore"], check=True)

    workflow_calls: List[Dict[str, Any]] = []
    cohort_calls: List[Dict[str, Any]] = []
    maint_calls: List[Dict[str, Any]] = []

    def _fake_workflows(property_id, repo_root, dist_dir, apply_overlays=True, persist=True, **kwargs):
        workflow_calls.append({"property_id": property_id, "apply_overlays": apply_overlays, "persist": persist})
        if persist and Path(repo_root).name == "beta":
            agy_dir = Path(repo_root) / ".agy"
            agy_dir.mkdir(parents=True, exist_ok=True)
            (agy_dir / "seo_workflows_cache.json").write_text("{}", encoding="utf-8")
        if apply_overlays and property_id == "alpha":
            (Path(dist_dir) / "index.html").write_text("<html><body><h1>Tuned Alpha</h1></body></html>", encoding="utf-8")
        return {"status": "PASS", "workflows": {}}

    def _fake_cohort(property_id, repo_root, dist_dir, propagate_winning_patterns=True, persist=True, **kwargs):
        cohort_calls.append({"property_id": property_id, "propagate_winning_patterns": propagate_winning_patterns, "persist": persist})
        return {"status": "PASS"}

    def _fake_maint_run(self, adapter, enable_gitops=True, dry_run=False, run_id=None, enable_browser_audit=None, **kwargs):
        maint_calls.append(
            {
                "property_id": adapter.property_id,
                "enable_gitops": enable_gitops,
                "dry_run": dry_run,
                "enable_browser_audit": enable_browser_audit,
            }
        )
        return type(
            "MaintRes",
            (),
            {
                "status": "SUCCESS",
                "browser_audit_status": "SKIPPED" if enable_browser_audit is False else "PASS",
                "gitops_status": "SUCCESS",
                "failed_records": [],
            },
        )()

    monkeypatch.setattr(seo_mod, "run_all_seo_growth_workflows", _fake_workflows)
    monkeypatch.setattr(seo_mod, "evaluate_closed_loop_cohort_reflection", _fake_cohort)
    monkeypatch.setattr(MaintenanceLifecycle, "run", _fake_maint_run)

    ledger_path = tmp_path / "weekly_seo_tune_ledger.json"

    # 1. Dry-run: discovers alpha & beta dynamically, runs workflows with apply_overlays=False, never calls MaintenanceLifecycle
    rc_dry = cli.main(
        [
            "weekly-seo-tune",
            "--property",
            "all",
            "--dry-run",
            "--json",
            "--workspace-root",
            str(ws_root),
            "--ledger-path",
            str(ledger_path),
        ]
    )
    assert rc_dry == 0
    dry_out = json.loads(capsys.readouterr().out)
    assert dry_out["status"] == "DRY_RUN"
    assert dry_out["tenants_discovered"] == ["alpha", "beta"]
    assert dry_out["changed_tenants_count"] == 0
    assert dry_out["total_changed_files"] == 0
    assert dry_out["properties"]["alpha"]["status"] == "DRY_RUN"
    assert dry_out["properties"]["beta"]["status"] == "DRY_RUN"
    assert len(maint_calls) == 0
    assert all(c["apply_overlays"] is False for c in workflow_calls)

    # 1b. Dry-run with an existing dist/ change must accurately count changed_tenants_count and total_changed_files
    orig_alpha_index = (alpha_root / "dist" / "index.html").read_text(encoding="utf-8")
    (alpha_root / "dist" / "index.html").write_text("<html><body><h1>Dirty Alpha</h1></body></html>", encoding="utf-8")
    rc_dry_dirty = cli.main(
        [
            "weekly-seo-tune",
            "--property",
            "all",
            "--dry-run",
            "--json",
            "--workspace-root",
            str(ws_root),
            "--ledger-path",
            str(ledger_path),
        ]
    )
    assert rc_dry_dirty == 0
    dry_dirty_out = json.loads(capsys.readouterr().out)
    assert dry_dirty_out["status"] == "DRY_RUN"
    assert dry_dirty_out["properties"]["alpha"]["dist_changed"] is True
    assert dry_dirty_out["properties"]["alpha"]["changed_files_count"] == 1
    assert dry_dirty_out["changed_tenants_count"] == 1
    assert dry_dirty_out["total_changed_files"] == 1
    assert len(maint_calls) == 0
    (alpha_root / "dist" / "index.html").write_text(orig_alpha_index, encoding="utf-8")

    # 2. Live run with --skip-browser-audit: alpha dist/ changes -> ships; beta has no dist delta -> NO_DIST_DELTA + clean git
    workflow_calls.clear()
    cohort_calls.clear()
    rc_live = cli.main(
        [
            "weekly-seo-tune",
            "--property",
            "all",
            "--skip-browser-audit",
            "--json",
            "--workspace-root",
            str(ws_root),
            "--ledger-path",
            str(ledger_path),
        ]
    )
    assert rc_live == 0
    live_out = json.loads(capsys.readouterr().out)
    assert live_out["status"] == "PASS"
    assert live_out["changed_tenants_count"] == 1
    assert live_out["total_changed_files"] == 1
    assert live_out["properties"]["alpha"]["status"] == "SHIPPED"
    assert live_out["properties"]["alpha"]["changed_files_count"] == 1
    assert live_out["properties"]["beta"]["status"] == "NO_DIST_DELTA"
    assert live_out["properties"]["beta"]["changed_files_count"] == 0
    assert len(maint_calls) == 1
    assert maint_calls[0]["property_id"] == "alpha"
    assert maint_calls[0]["enable_gitops"] is True
    assert maint_calls[0]["enable_browser_audit"] is False
    assert ledger_path.is_file()

    # Beta git repo must remain 100% clean (no untracked .agy/ dirty files)
    beta_status = subprocess.run(
        ["git", "-C", str(beta_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert beta_status.stdout.strip() == ""
