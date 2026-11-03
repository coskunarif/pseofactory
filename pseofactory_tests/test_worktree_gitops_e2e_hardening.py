"""End-to-end regression tests for .agy worktree harness, staging queue, autonomous lock protocol, and tenant rebase lock integrity.
Zero em-dashes. Zero en-dashes.
"""

import fcntl
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pseofactory.drift import (
    compute_dist_lock_metrics,
    compute_engine_hash,
)
from pseofactory.gitops import (
    GitOpsCoordinator,
    ShipperQueue,
    reconcile_workspace_tracking_state,
    sync_tenant_test_isolation_guards,
)
from pseofactory.supervisor import DepartmentHandoffChainVerifier


HARNESS_SCRIPT = Path("/home/ubuntuadmin/projects/.agy/worktree_harness.sh")
QUEUE_SCRIPT = Path("/home/ubuntuadmin/projects/.agy/staging_queue.py")
RELEASE_SCRIPT = Path("/home/ubuntuadmin/projects/.agy/release_pipeline.sh")
INDEXING_INSPECTOR_RUN_SH = Path(
    "/home/ubuntuadmin/projects/automations/pseofactory-indexing-inspector/run.sh"
)


def _init_git_repo(repo_path: Path, branch: str = "main") -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", branch],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@pseofactory.local"],
        cwd=str(repo_path),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=str(repo_path),
        check=True,
    )
    (repo_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


def test_a1_worktree_create_preserves_uncommitted_and_unmerged_work(tmp_path):
    """Prove worktree_harness.sh create never loses uncommitted edits or unmerged commits when reusing a run_id."""
    repo = tmp_path / "repo_create_safe"
    wt_base = tmp_path / "worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo)

    run_id = f"test-create-preserve-{os.getpid()}"
    env = os.environ.copy()
    env["AGY_WORKTREES_BASE"] = str(wt_base)

    # 1. Create initial worktree
    subprocess.run(
        [str(HARNESS_SCRIPT), "create", str(repo), run_id],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    wt_path = wt_base / run_id
    if not wt_path.exists():
        # Fallback if AGY_WORKTREES_BASE is not yet supported by unpatched script
        wt_path = Path("/home/ubuntuadmin/projects/.agy/worktrees") / run_id

    try:
        assert wt_path.exists()

        # Add an unmerged commit on the worktree branch
        (wt_path / "committed_feature.txt").write_text(
            "important committed work\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "committed_feature.txt"], cwd=str(wt_path), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: unmerged worktree commit"],
            cwd=str(wt_path),
            check=True,
            capture_output=True,
        )

        # Add an uncommitted file and modified tracked file in the worktree
        (wt_path / "uncommitted_notes.txt").write_text(
            "precious uncommitted work\n", encoding="utf-8"
        )
        (wt_path / "README.md").write_text(
            "# Modified in dirty worktree\n", encoding="utf-8"
        )

        # 2. Re-run create with the exact same run_id
        subprocess.run(
            [str(HARNESS_SCRIPT), "create", str(repo), run_id],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        # Verify a quarantine/recovery branch was preserved in repo containing BOTH committed_feature.txt and uncommitted_notes.txt
        branches_out = subprocess.check_output(
            ["git", "branch", "--list", "quarantine/*"],
            cwd=str(repo),
            text=True,
        ).strip()
        assert branches_out != "", "Expected a quarantine/* recovery branch to be preserved"

        recovery_branch = branches_out.splitlines()[-1].strip().lstrip("* ").strip()
        tree_files = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", recovery_branch],
            cwd=str(repo),
            text=True,
        ).splitlines()
        assert "committed_feature.txt" in tree_files
        assert "uncommitted_notes.txt" in tree_files

        readme_recovered = subprocess.check_output(
            ["git", "show", f"{recovery_branch}:README.md"],
            cwd=str(repo),
            text=True,
        )
        assert "Modified in dirty worktree" in readme_recovered
    finally:
        shutil.rmtree(
            Path("/home/ubuntuadmin/projects/.agy/worktrees") / run_id,
            ignore_errors=True,
        )
        subprocess.run(
            ["git", "worktree", "prune"], cwd=str(repo), capture_output=True
        )


def test_a2_worktree_sweep_and_abort_preserve_uncommitted_and_unmerged_work(tmp_path):
    """Prove worktree_harness.sh sweep and abort never destroy uncommitted edits or unmerged commits without preserving them."""
    repo = tmp_path / "repo_sweep_safe"
    wt_base = tmp_path / "worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo)

    run_id = f"test-sweep-preserve-{os.getpid()}"
    env = os.environ.copy()
    env["AGY_WORKTREES_BASE"] = str(wt_base)

    subprocess.run(
        [str(HARNESS_SCRIPT), "create", str(repo), run_id],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    wt_path = wt_base / run_id
    if not wt_path.exists():
        wt_path = Path("/home/ubuntuadmin/projects/.agy/worktrees") / run_id

    try:
        (wt_path / "unmerged_sweep.txt").write_text("unmerged work\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "unmerged_sweep.txt"], cwd=str(wt_path), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: unmerged before sweep"],
            cwd=str(wt_path),
            check=True,
            capture_output=True,
        )
        (wt_path / "dirty_sweep.txt").write_text("dirty work\n", encoding="utf-8")

        # Run sweep targeting run_id
        subprocess.run(
            [str(HARNESS_SCRIPT), "sweep", str(repo), run_id],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        # Either the worktree was held intact OR a quarantine recovery branch captured both files
        if wt_path.exists():
            assert (wt_path / "unmerged_sweep.txt").exists()
            assert (wt_path / "dirty_sweep.txt").exists()
        else:
            branches_out = subprocess.check_output(
                ["git", "branch", "--list", "quarantine/*"],
                cwd=str(repo),
                text=True,
            ).strip()
            assert branches_out != "", "Sweep destroyed dirty/unmerged worktree without preserving quarantine branch"
            recovery_branch = branches_out.splitlines()[-1].strip().lstrip("* ").strip()
            tree_files = subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", recovery_branch],
                cwd=str(repo),
                text=True,
            ).splitlines()
            assert "unmerged_sweep.txt" in tree_files
            assert "dirty_sweep.txt" in tree_files
    finally:
        shutil.rmtree(
            Path("/home/ubuntuadmin/projects/.agy/worktrees") / run_id,
            ignore_errors=True,
        )
        subprocess.run(
            ["git", "worktree", "prune"], cwd=str(repo), capture_output=True
        )


def test_b_staging_queue_process_until_and_direct_merge_registration(tmp_path):
    """Prove staging_queue.py process-until drains earlier items until target run_id lands on HEAD, and worktree_harness.sh merge registers COMPLETED."""
    repo = tmp_path / "repo_fifo_target"
    wt_base = tmp_path / "worktrees"
    queue_dir = tmp_path / "queue"
    shipper_dir = tmp_path / "queues"
    wt_base.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)
    shipper_dir.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo)

    env = os.environ.copy()
    env["AGY_WORKTREES_BASE"] = str(wt_base)
    env["AGY_QUEUE_DIR"] = str(queue_dir)
    env["AGY_SHIPPER_QUEUES_DIR"] = str(shipper_dir)

    run_older = f"run-older-{os.getpid()}"
    run_target = f"run-target-{os.getpid()}"
    run_direct = f"run-direct-{os.getpid()}"

    try:
        # 1. Create two concurrent worktrees (run_older and run_target)
        for rid, fname in [(run_older, "older.txt"), (run_target, "target.txt")]:
            subprocess.run(
                [str(HARNESS_SCRIPT), "create", str(repo), rid],
                env=env,
                check=True,
                capture_output=True,
            )
            wpath = wt_base / rid
            if not wpath.exists():
                wpath = Path("/home/ubuntuadmin/projects/.agy/worktrees") / rid
            (wpath / fname).write_text(f"content for {rid}\n", encoding="utf-8")
            subprocess.run(["git", "add", fname], cwd=str(wpath), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"feat: {rid}"],
                cwd=str(wpath),
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "python3",
                    str(QUEUE_SCRIPT),
                    "enqueue",
                    str(repo),
                    rid,
                    str(wpath),
                    f"agy-wt-{rid}",
                ],
                env=env,
                check=True,
                capture_output=True,
            )

        # 2. Run process-until for run_target: must process run_older AND run_target and verify run_target is ancestor of HEAD
        proc = subprocess.run(
            [
                "python3",
                str(QUEUE_SCRIPT),
                "process-until",
                str(repo),
                run_target,
                "--target-branch",
                "main",
            ],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        assert res["status"] == "COMPLETED"
        assert res["run_id"] == run_target
        assert (repo / "older.txt").exists()
        assert (repo / "target.txt").exists()

        merged_sha = res["merged_sha"]
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", merged_sha, "HEAD"],
            cwd=str(repo),
            check=True,
        )

        # 3. Verify worktree_harness.sh merge records COMPLETED in staging_queue so Stage 2 of release_pipeline knows it already merged
        subprocess.run(
            [str(HARNESS_SCRIPT), "create", str(repo), run_direct],
            env=env,
            check=True,
            capture_output=True,
        )
        wpath_direct = wt_base / run_direct
        if not wpath_direct.exists():
            wpath_direct = Path("/home/ubuntuadmin/projects/.agy/worktrees") / run_direct
        (wpath_direct / "direct.txt").write_text("direct merge\n", encoding="utf-8")
        subprocess.run(["git", "add", "direct.txt"], cwd=str(wpath_direct), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: direct merge"],
            cwd=str(wpath_direct),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [str(HARNESS_SCRIPT), "merge", str(repo), run_direct, "main"],
            env=env,
            check=True,
            capture_output=True,
        )

        qfile = queue_dir / f"{repo.name}_queue.json"
        assert qfile.exists(), "worktree_harness.sh merge must record COMPLETED in staging_queue"
        qdata = json.loads(qfile.read_text(encoding="utf-8"))
        direct_items = [item for item in qdata.get("items", []) if item.get("run_id") == run_direct]
        assert direct_items and direct_items[-1]["status"] == "COMPLETED"
    finally:
        for rid in (run_older, run_target, run_direct):
            shutil.rmtree(
                Path("/home/ubuntuadmin/projects/.agy/worktrees") / rid,
                ignore_errors=True,
            )


def test_c_autonomous_lock_protocol_and_worktree_sync_guards(tmp_path):
    """Prove tenant run_factory.sh, supervisor, maintenance, and indexing_inspector enforce strict mutual exclusion and branch sync."""
    # 1. Inspect synced run_factory.sh via sync_tenant_test_isolation_guards in an isolated tenant directory
    tenant_dir = tmp_path / "profithelm-platform"
    scripts_dir = tenant_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    # Seed a legacy run_factory.sh with the broken `flock -u 201` pattern
    (scripts_dir / "run_factory.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
LOCK_FILE="/tmp/profithelm_factory.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || exit 0
if [ "${PSEUFACTORY_SUPERVISOR_LOCK_HELD:-0}" != "1" ]; then
    SUPERVISOR_LOCK="/tmp/pseofactory_supervisor.lock"
    exec 201>"$SUPERVISOR_LOCK"
    flock -w 30 201 || exit 0
    flock -u 201
    exec 201>&-
fi
python3 -m profithelm.factory "$@"
""",
        encoding="utf-8",
    )

    sync_tenant_test_isolation_guards(tenant_dir, "profithelm")
    synced_sh = (scripts_dir / "run_factory.sh").read_text(encoding="utf-8")
    assert "flock -u 201" not in synced_sh, "run_factory.sh must hold FD 201 for the entire run, never unlock immediately"

    # 2. Check automations/pseofactory-indexing-inspector/run.sh acquires supervisor lock and includes gainhelm
    inspector_sh = INDEXING_INSPECTOR_RUN_SH.read_text(encoding="utf-8")
    assert "/tmp/pseofactory_supervisor.lock" in inspector_sh
    assert "gainhelm" in inspector_sh

    # 3. Verify ShipperQueue reconciles stale PUSH_FAILED events once a newer COMPLETED event or clean HEAD exists
    q_path = tmp_path / "profithelm_release_queue.jsonl"
    sq = ShipperQueue("profithelm", queues_dir=tmp_path)
    evt_rec = sq.enqueue(
        payload={"run_id": "cycle_1793651449_e439dc", "token": "tok_old"},
    )
    evt_id = evt_rec["event_id"]
    sq.complete_event(evt_id, status="PUSH_FAILED", details={"error": "non-fast-forward"})
    evt_succ = sq.enqueue(
        payload={"run_id": "release_subsequent_clean", "token": "tok_new"},
    )
    sq.complete_event(evt_succ["event_id"], status="COMPLETED")
    reconciled_count = sq.reconcile_stale_events()
    assert reconciled_count >= 1
    events = [
        json.loads(line)
        for line in q_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latest_for_evt = [e for e in events if e.get("event_id") == evt_id][-1]
    assert latest_for_evt["status"] in ("RECONCILED_SUPERSEDED", "COMPLETED")

    # 4. Prove TenantFactoryLockGuard enforces genuine mutual exclusion under contention
    from pseofactory.gitops import TenantFactoryLockGuard
    import fcntl

    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    old_lock_dir = os.environ.get("PSEUFACTORY_LOCK_DIR")
    os.environ["PSEUFACTORY_LOCK_DIR"] = str(lock_dir)
    try:
        with TenantFactoryLockGuard("profithelm", repo_path=tenant_dir, dry_run=False, non_blocking=True) as guard1:
            assert guard1.acquired is True
            # While guard1 holds the lock, a second non-blocking or short-timeout guard cannot acquire it
            with TenantFactoryLockGuard("profithelm", repo_path=tenant_dir, dry_run=False, non_blocking=True) as guard2:
                assert guard2.acquired is False
            # Also raw flock non-blocking attempt must fail while guard1 is inside the with block
            with open(lock_dir / "profithelm_factory.lock", "a+", encoding="utf-8") as probe_f:
                contention_raised = False
                try:
                    fcntl.flock(probe_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    contention_raised = True
                assert contention_raised is True
        # Once guard1 exits, guard3 acquires cleanly
        with TenantFactoryLockGuard("profithelm", repo_path=tenant_dir, dry_run=False, non_blocking=True) as guard3:
            assert guard3.acquired is True
    finally:
        if old_lock_dir is None:
            os.environ.pop("PSEUFACTORY_LOCK_DIR", None)
        else:
            os.environ["PSEUFACTORY_LOCK_DIR"] = old_lock_dir


def test_d_ahead_diverged_origin_main_reconciles_and_recomputes_substrate_lock(tmp_path):
    """Prove push_with_backoff recomputes substrate_lock.json and .agy/asset_ledger.json when rebasing onto an ahead origin/main."""
    remote_bare = tmp_path / "origin_prexvo.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote_bare)],
        check=True,
        capture_output=True,
    )

    local_repo = tmp_path / "prexvo"
    _init_git_repo(local_repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_bare)],
        cwd=str(local_repo),
        check=True,
    )

    eng_hash = compute_engine_hash()
    dist_dir = local_repo / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Prexvo Hub</title></head><body>Prexvo</body></html>",
        encoding="utf-8",
    )
    fp0, total0 = compute_dist_lock_metrics(dist_dir)
    (local_repo / "substrate_lock.json").write_text(
        json.dumps(
            {
                "property": "prexvo",
                "engine_hash": eng_hash,
                "substrate_hash": eng_hash,
                "dist_fingerprint": fp0,
                "total_assets": total0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    agy_dir = local_repo / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    (agy_dir / "asset_ledger.json").write_text(
        json.dumps(
            {
                "property_id": "prexvo",
                "engine_hash": eng_hash,
                "total_compiled_assets": total0,
                "assets": {"index.html": {"sha256": "init"}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(local_repo), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: baseline substrate"],
        cwd=str(local_repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=str(local_repo),
        check=True,
        capture_output=True,
    )

    # Simulate another clone pushing a new tool page to origin/main
    other_clone = tmp_path / "other_clone"
    subprocess.run(
        ["git", "clone", str(remote_bare), str(other_clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "factory@prexvo.com"],
        cwd=str(other_clone),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Prexvo Factory"],
        cwd=str(other_clone),
        check=True,
    )
    remote_tool = other_clone / "dist" / "remote-tool"
    remote_tool.mkdir(parents=True)
    (remote_tool / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Remote Tool</title></head><body>Remote Tool</body></html>",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(other_clone), check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat(factory): add remote-tool"],
        cwd=str(other_clone),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=str(other_clone),
        check=True,
        capture_output=True,
    )

    # Meanwhile, local_repo creates a local commit updating dist/local-tool and substrate_lock.json (without knowing about remote-tool yet)
    local_tool = dist_dir / "local-tool"
    local_tool.mkdir(parents=True)
    (local_tool / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Local Tool</title></head><body>Local Tool</body></html>",
        encoding="utf-8",
    )
    fp_local_only, total_local_only = compute_dist_lock_metrics(dist_dir)
    (local_repo / "substrate_lock.json").write_text(
        json.dumps(
            {
                "property": "prexvo",
                "engine_hash": eng_hash,
                "substrate_hash": eng_hash,
                "dist_fingerprint": fp_local_only,
                "total_assets": total_local_only,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(local_repo), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore(reflection): local update"],
        cwd=str(local_repo),
        check=True,
        capture_output=True,
    )

    # Now push_with_backoff must rebase onto origin/main AND recompute substrate_lock.json + .agy/asset_ledger.json before pushing!
    coord = GitOpsCoordinator(repo_path=local_repo, branch="main")
    push_res = coord.push_with_backoff("main", max_attempts=3)
    assert push_res["status"] == "SUCCESS"

    # Verify both tools exist in dist/ and substrate_lock.json matches the combined dist/
    assert (dist_dir / "remote-tool" / "index.html").exists()
    assert (dist_dir / "local-tool" / "index.html").exists()

    actual_fp, actual_total = compute_dist_lock_metrics(dist_dir)
    lock_data = json.loads((local_repo / "substrate_lock.json").read_text(encoding="utf-8"))
    assert lock_data["dist_fingerprint"] == actual_fp, (
        f"Expected recomputed dist_fingerprint {actual_fp}, got {lock_data['dist_fingerprint']}"
    )
    assert lock_data["total_assets"] == actual_total, (
        f"Expected recomputed total_assets {actual_total}, got {lock_data['total_assets']}"
    )

    ledger_data = json.loads((agy_dir / "asset_ledger.json").read_text(encoding="utf-8"))
    assert ledger_data["total_compiled_assets"] == actual_total

    # And local HEAD must equal origin/main (no uncommitted changes left behind)
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(local_repo), text=True
    ).strip()
    origin_sha = subprocess.check_output(
        ["git", "rev-parse", "origin/main"], cwd=str(local_repo), text=True
    ).strip()
    assert head_sha == origin_sha
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=str(local_repo), text=True
    ).strip()
    assert dirty == ""
