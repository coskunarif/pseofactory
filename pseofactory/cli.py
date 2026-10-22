"""
pseofactory CLI Gateway
Autonomous execution interface for auditing, maintaining, refactoring, and fleet coordination.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Optional

# Ensure package root takes precedence in sys.path when invoked directly
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pseofactory.maintenance import (
    TenantRegistry,
    ConfigurablePropertyAdapter,
    AssetIntegrityEvaluator,
    AssetDriftRecord,
    RefactorCascadeEngine,
    MaintenanceLifecycle,
    FleetMaintenanceCoordinator,
    run_maintenance_lifecycle,
    run_fleet_maintenance,
    audit_property_assets,
    DriftReason,
    reflect_and_recompile_all_assets,
    recompile_drifted_assets,
)
from pseofactory.drift import (
    detect_engine_drift,
    record_engine_hash,
    compute_engine_hash,
)


def cmd_audit(args: argparse.Namespace) -> int:
    """
    Executes asset integrity audit across property static assets.
    Returns 0 if all assets are compliant (status PASS), 1 if drift detected or error.
    Zero em-dashes. Zero en-dashes.
    """
    if getattr(args, "browser", False):
        from pseofactory.browser_verifier import (
            UnifiedBrowserAuditor,
            ProfitHelmBrowserAdapter,
            PrexvoBrowserAdapter,
        )
        browser_adapter = None
        prop = (args.property or "").lower()
        if prop == "profithelm":
            browser_adapter = ProfitHelmBrowserAdapter()
        elif prop == "prexvo":
            browser_adapter = PrexvoBrowserAdapter()

        auditor = UnifiedBrowserAuditor(
            adapter=browser_adapter,
            dist_dir=args.dist_dir,
            cdp_port=getattr(args, "cdp_port", 9222),
            fail_closed=getattr(args, "fail_closed", False),
        )
        report = auditor.run_audit(sample_size=getattr(args, "sample", None))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            status = report.get("status", "UNKNOWN")
            print(f"[{status}] Browser CDP Audit for '{args.property or 'dist'}': Total: {report.get('total_routes', 0)} | Audited: {report.get('routes_audited', 0)} | Failed: {report.get('failed_count', 0)}")
            for f in report.get("findings", []):
                route = f.get("route")
                if f.get("targets_under_44"):
                    print(f"  - {route}: {len(f['targets_under_44'])} undersized touch targets")
                if f.get("cls_value", 0.0) > 0.0:
                    print(f"  - {route}: CLS {f['cls_value']}")
                if f.get("overflow_375") or f.get("overflow_1280"):
                    print(f"  - {route}: horizontal overflow detected")
                if f.get("dashes"):
                    print(f"  - {route}: forbidden dashes detected")
        return 0 if report.get("status") in ("PASS", "SKIPPED_CDP_OFFLINE") else 1

    reg = TenantRegistry.default()
    if args.dist_dir:
        dist_path = Path(args.dist_dir).resolve()
        property_id = args.property or "custom"
        adapter = ConfigurablePropertyAdapter(
            property_id=property_id,
            brand_name=property_id.capitalize(),
            domain=f"{property_id}.com",
            canonical_base=f"https://{property_id}.com",
            dist_dir=dist_path,
        )
        evaluator = AssetIntegrityEvaluator()
        report = evaluator.audit_all(adapter, check_engine_drift=getattr(args, "check_engine_drift", False))
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"[{report.status}] Property: {report.property_id} | Total: {report.total_assets_checked} | Compliant: {report.compliant_assets_count} | Drifted: {report.drifted_assets_count}")
            for d in report.drifted_assets:
                print(f"  - {d.asset_path}: {[r.value if isinstance(r, DriftReason) else str(r) for r in d.reasons]} ({'; '.join(d.details)})")
        return 0 if report.status == "PASS" else 1

    property_id = args.property or "prexvo"
    try:
        adapter = reg.get_adapter(property_id)
    except KeyError:
        print(f"Error: Property '{property_id}' not found in registry", file=sys.stderr)
        return 1

    report = audit_property_assets(
        property_id=property_id,
        adapter=adapter,
        check_engine_drift=getattr(args, "check_engine_drift", False),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"[{report.status}] Property: {report.property_id} | Total: {report.total_assets_checked} | Compliant: {report.compliant_assets_count} | Drifted: {report.drifted_assets_count}")
        for d in report.drifted_assets:
            print(f"  - {d.asset_path}: {[r.value if isinstance(r, DriftReason) else str(r) for r in d.reasons]} ({'; '.join(d.details)})")
    return 0 if report.status == "PASS" else 1


def cmd_maintain(args: argparse.Namespace) -> int:
    """
    Executes closed-loop maintenance lifecycle on a property.
    Returns 0 on SUCCESS or SKIPPED_NO_CHANGES, 1 on failure.
    Zero em-dashes. Zero en-dashes.
    """
    if getattr(args, "fast", False):
        os.environ["PSEUFACTORY_FAST_MODE"] = "1"
        os.environ.setdefault("PSEUFACTORY_CI_DISCOVERY_INTERVAL", "0.05")
        os.environ.setdefault("PSEUFACTORY_CI_POLL_INTERVAL", "0.25")
        os.environ.setdefault("PSEUFACTORY_GIT_BACKOFF", "0.05,0.1,0.2")
        os.environ.setdefault("PSEUFACTORY_EDGE_BACKOFF", "0.001")

    property_id = args.property or "prexvo"
    auto_heal = getattr(args, "auto_heal", False)
    res = run_maintenance_lifecycle(property_id=property_id, force=args.force or auto_heal)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print(f"[{res.status}] Property: {res.property_id} | Audited: {res.assets_audited} | Drifted: {res.assets_drifted} | Refactored: {res.assets_refactored} | Failed: {res.assets_failed}")
        if res.engine_hash:
            print(f"  Engine Hash: {res.engine_hash[:16]}...")
        if res.failed_records:
            for fr in res.failed_records:
                print(f"  - Failed asset: {fr.get('asset_path')}")
    return 0 if res.status in ("SUCCESS", "SKIPPED_NO_CHANGES") else 1


def _ancestor_or_inherited_fd_holds_lock(lock_file: Path) -> bool:
    """
    Returns True if the current process inherited a file descriptor (such as FD 209
    from release_pipeline.sh) pointing to lock_file, or if an ancestor PID in our
    process tree already holds a FLOCK on lock_file. Prevents self-deadlock when a
    parent shell holds flock on lock_file without exporting PSEUFACTORY_SUPERVISOR_LOCK_HELD=1.
    Zero em-dashes. Zero en-dashes.
    """
    try:
        if not lock_file.exists():
            return False
        target_stat = lock_file.stat()
        target_dev_ino = (target_stat.st_dev, target_stat.st_ino)
    except OSError:
        return False

    # 1. Check inherited file descriptors (e.g., FD 209 from release_pipeline.sh)
    fd_dir = Path("/proc/self/fd")
    if fd_dir.is_dir():
        try:
            for fd_entry in fd_dir.iterdir():
                try:
                    fd_num = int(fd_entry.name)
                    if fd_num in (0, 1, 2):
                        continue
                    st = os.fstat(fd_num)
                    if (st.st_dev, st.st_ino) == target_dev_ino:
                        return True
                except (OSError, ValueError):
                    continue
        except OSError:
            pass

    # 2. Check /proc/locks for any ancestor PID holding a lock on this inode
    proc_locks = Path("/proc/locks")
    if proc_locks.is_file():
        try:
            ancestors = set()
            curr_pid = os.getpid()
            for _ in range(16):
                ancestors.add(curr_pid)
                stat_file = Path(f"/proc/{curr_pid}/stat")
                if not stat_file.is_file():
                    break
                raw_stat = stat_file.read_text(encoding="utf-8", errors="ignore")
                rpar = raw_stat.rfind(")")
                if rpar == -1:
                    break
                fields = raw_stat[rpar + 2 :].split()
                if len(fields) < 2:
                    break
                ppid = int(fields[1])
                if ppid <= 1 or ppid == curr_pid:
                    break
                curr_pid = ppid

            ino_str = str(target_stat.st_ino)
            for line in proc_locks.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 6 and parts[5].endswith(f":{ino_str}"):
                    try:
                        holder_pid = int(parts[4])
                        if holder_pid in ancestors:
                            return True
                    except ValueError:
                        continue
        except OSError:
            pass

    return False


def cmd_reflect(args: argparse.Namespace) -> int:
    """
    Reflects engine changes across existing assets and triggers re-auditing / recompiling.
    Zero em-dashes. Zero en-dashes.
    """
    props = [args.property] if getattr(args, "property", None) else None
    no_gitops = getattr(args, "no_gitops", False)
    lock_fd = None
    lock_file = Path(os.environ.get("PSEUFACTORY_SUPERVISOR_LOCK", "/tmp/pseofactory_supervisor.lock"))
    if _ancestor_or_inherited_fd_holds_lock(lock_file):
        os.environ["PSEUFACTORY_SUPERVISOR_LOCK_HELD"] = "1"
    if "PYTEST_CURRENT_TEST" not in os.environ and os.environ.get("PSEUFACTORY_SUPERVISOR_LOCK_HELD") != "1":
        try:
            import fcntl
            lock_fd = open(lock_file, "a+", encoding="utf-8")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            os.environ["PSEUFACTORY_SUPERVISOR_LOCK_HELD"] = "1"
        except OSError:
            if lock_fd is not None:
                lock_fd.close()
                lock_fd = None
    try:
        res = reflect_and_recompile_all_assets(
            properties=props,
            force=getattr(args, "force", False),
            verbose=getattr(args, "verbose", False),
            latch_state=True,
            defer_live_indexing=True,
        )
    finally:
        if lock_fd is not None:
            try:
                import fcntl
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass
    if res.get("total_recompiled", 0) > 0 and not no_gitops:
        from pseofactory.gitops import GitOpsCoordinator
        from pseofactory.indexer import PushIndexer
        reg = TenantRegistry.default()
        for p_id, r_info in res.get("property_reports", {}).items():
            if r_info.get("recompiled", 0) > 0 and r_info.get("final_status") == "PASS":
                try:
                    adapter = reg.get_adapter(p_id)
                    repo_path = adapter.repo_path or adapter.dist_dir.parent
                    if (repo_path / ".git").exists():
                        coordinator = GitOpsCoordinator(repo_path=repo_path, branch="main", dry_run=False)
                        gitops_res = coordinator.dispatch_to_shipper(
                            property_id=p_id,
                            dry_run=False,
                            commit_message=f"fix({p_id}): automated reflection and maintenance cycle",
                            edge_url=getattr(adapter, "canonical_base", None),
                            dist_dir=adapter.dist_dir,
                        )
                        r_info["gitops_status"] = gitops_res.status
                        if gitops_res.status not in ("SUCCESS", "SKIPPED_NO_CHANGES", "SKIPPED_NOT_GIT_REPO", "SKIPPED_DRY_RUN", "DRY_RUN", "COMPLETED"):
                            res["status"] = "FAIL"
                        else:
                            canon_base = str(getattr(adapter, "canonical_base", f"https://{adapter.domain}")).rstrip("/")
                            indexer = PushIndexer(
                                domain=adapter.domain,
                                canonical_base=canon_base,
                                base_dir=repo_path,
                                dist_dir=adapter.dist_dir,
                                tenant_id=adapter.property_id,
                            )
                            idx_res = indexer.dispatch_automated_indexing(urls=None, live=True)
                            if isinstance(r_info.get("downstream"), dict):
                                r_info["downstream"]["indexing_status"] = idx_res.get("status", "SUCCESS") if isinstance(idx_res, dict) else "SUCCESS"
                except Exception as g_err:
                    res["status"] = "FAIL"
                    if getattr(args, "verbose", False):
                        print(f"Warning: GitOps auto-chain failed for '{p_id}': {g_err}")

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
    else:
        print(f"[{res['status']}] Properties: {res['properties_scanned']} | Checked: {res['total_assets_checked']} | Drifted: {res['total_drifted']} | Recompiled: {res['total_recompiled']}")
    return 0 if res["status"] == "PASS" else 1


def cmd_refactor(args: argparse.Namespace) -> int:
    """
    Refactors a single drifted asset by slug or path.
    Zero em-dashes. Zero en-dashes.
    """
    if not args.property:
        print("Error: --property argument is required for refactor", file=sys.stderr)
        return 1
    if not args.asset:
        print("Error: --asset argument is required for refactor", file=sys.stderr)
        return 1

    reg = TenantRegistry.default()
    try:
        adapter = reg.get_adapter(args.property)
    except KeyError:
        print(f"Error: Property '{args.property}' not found in registry", file=sys.stderr)
        return 1

    target = Path(args.asset)
    if not target.is_absolute() and adapter.dist_dir.exists():
        target = adapter.dist_dir / args.asset

    record = AssetDriftRecord(
        asset_path=str(target),
        slug=target.stem,
        reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
        details=["Targeted CLI refactor requested"],
    )

    engine = RefactorCascadeEngine()
    success = engine.refactor_asset(record, adapter)
    status_str = "SUCCESS" if success else "FAILED"
    if args.json:
        print(json.dumps({"property_id": args.property, "asset": str(target), "status": status_str}, indent=2))
    else:
        print(f"[{status_str}] Refactor {target} for property {args.property}")
    return 0 if success else 1


def cmd_fleet_maintain(args: argparse.Namespace) -> int:
    """
    Executes sequential fleet maintenance across all registered properties.
    Zero em-dashes. Zero en-dashes.
    """
    results = run_fleet_maintenance(force=args.force, dry_run=args.dry_run)
    all_ok = True
    if args.json:
        print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2))
    else:
        for p_id, r in results.items():
            print(f"[{r.status}] Property: {p_id} | Audited: {r.assets_audited} | Drifted: {r.assets_drifted} | Refactored: {r.assets_refactored} | Failed: {r.assets_failed}")
            if r.status not in ("SUCCESS", "SKIPPED_NO_CHANGES", "DRY_RUN"):
                all_ok = False
    return 0 if all_ok else 1


def cmd_drift(args: argparse.Namespace) -> int:
    """
    Audits or records substrate engine hash drift.
    Zero em-dashes. Zero en-dashes.
    """
    state_file = args.state_file or ".agy/engine_hash.json"
    drift_res = detect_engine_drift(state_file=state_file, auto_record=args.record)
    if args.json:
        print(json.dumps(drift_res, indent=2))
    else:
        print(f"[{drift_res['status']}] Current: {drift_res['current_hash'][:16]} | Recorded: {str(drift_res['recorded_hash'])[:16]} | Requires Recompile: {drift_res['requires_recompile']}")
    if args.record:
        return 0
    return 0 if drift_res["status"] == "ALIGNED" else 1


def cmd_replay_dlq(args: argparse.Namespace) -> int:
    """
    Lists or replays quarantined entries from Dead Letter Queue (DLQ).
    Zero em-dashes. Zero en-dashes.
    """
    engine = RefactorCascadeEngine(dlq_path=args.dlq_path)
    if args.list:
        entries = engine.list_dlq(property_id=args.property)
        if args.slug:
            entries = [e for e in entries if e.get("slug") == args.slug]
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            print(f"Quarantined DLQ Entries ({len(entries)}):")
            for e in entries:
                print(f"  - [{e.get('property_id')}] {e.get('slug')} ({e.get('asset_path')}) [Reason: {e.get('reasons')}] Last error: {e.get('last_error')}")
        return 0
    else:
        replayed = engine.replay_dlq(property_id=args.property, slug=args.slug)
        if args.json:
            print(json.dumps({"replayed_count": len(replayed), "replayed": replayed}, indent=2))
        else:
            print(f"Replayed {len(replayed)} quarantined DLQ entries.")
            for e in replayed:
                print(f"  - [{e.get('property_id')}] {e.get('slug')} ({e.get('asset_path')})")
        return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    """
    Executes complete autonomous cycle across specified property or whole fleet:
    1. Preflight Audit: AssetIntegrityEvaluator
    2. Atomic Refactor: RefactorCascadeEngine
    3. Statutory Isolation Scan: CrossPropertyContaminationScanner
    4. GitOps Commit Latch: GitOpsCoordinator
    5. CI/CD Quality Gate Watch: CICDWatcher
    6. Live Edge Verification: LiveEdgeVerifier
    Zero em-dashes. Zero en-dashes.
    """
    if getattr(args, "fast", False):
        os.environ["PSEUFACTORY_FAST_MODE"] = "1"
        os.environ.setdefault("PSEUFACTORY_CI_DISCOVERY_INTERVAL", "0.05")
        os.environ.setdefault("PSEUFACTORY_CI_POLL_INTERVAL", "0.25")
        os.environ.setdefault("PSEUFACTORY_GIT_BACKOFF", "0.05,0.1,0.2")
        os.environ.setdefault("PSEUFACTORY_EDGE_BACKOFF", "0.001")

    property_id = getattr(args, "property", None)
    dry_run = getattr(args, "dry_run", False)
    timeout = getattr(args, "timeout", 300)
    skip_ci = getattr(args, "skip_ci", False)
    as_json = getattr(args, "json", False)

    reg = TenantRegistry.default()
    if property_id:
        try:
            adapter = reg.get_adapter(property_id)
        except KeyError:
            print(f"Error: Property '{property_id}' not found in registry", file=sys.stderr)
            return 1
        lifecycle = MaintenanceLifecycle(registry=reg)
        res = lifecycle.run(
            adapter,
            force=False,
            enable_gitops=True,
            dry_run=dry_run,
            skip_ci=skip_ci,
        )
        if as_json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            gitops_tag = f" | GitOps: {res.gitops_status}" if getattr(res, "gitops_status", None) else ""
            dist_tag = f" | Distribution: {res.distribution_status}" if getattr(res, "distribution_status", None) else ""
            idx_tag = f" | Indexing: {res.indexing_status}" if getattr(res, "indexing_status", None) else ""
            trend_tag = f" | Trends: {res.trend_status}" if getattr(res, "trend_status", None) else ""
            partner_tag = f" | PartnerReadiness: {res.partner_readiness_status}" if getattr(res, "partner_readiness_status", None) else ""
            print(
                f"[{res.status}] Property: {res.property_id} | "
                f"Audited: {res.assets_audited} | Drifted: {res.assets_drifted} | "
                f"Refactored: {res.assets_refactored} | Failed: {res.assets_failed}{gitops_tag}{dist_tag}{idx_tag}{trend_tag}{partner_tag}"
            )
        return 0 if res.status in ("SUCCESS", "SKIPPED_NO_CHANGES", "DRY_RUN") else 1
    else:
        coordinator = FleetMaintenanceCoordinator(registry=reg)
        results = coordinator.run_fleet(
            force=False,
            dry_run=dry_run,
            enable_gitops=True,
            skip_ci=skip_ci,
        )
        if as_json:
            print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2))
        else:
            for pid, res in results.items():
                gitops_tag = f" | GitOps: {res.gitops_status}" if getattr(res, "gitops_status", None) else ""
                dist_tag = f" | Distribution: {res.distribution_status}" if getattr(res, "distribution_status", None) else ""
                idx_tag = f" | Indexing: {res.indexing_status}" if getattr(res, "indexing_status", None) else ""
                trend_tag = f" | Trends: {res.trend_status}" if getattr(res, "trend_status", None) else ""
                partner_tag = f" | PartnerReadiness: {res.partner_readiness_status}" if getattr(res, "partner_readiness_status", None) else ""
                print(
                    f"[{res.status}] Property: {pid} | "
                    f"Audited: {res.assets_audited} | Drifted: {res.assets_drifted} | "
                    f"Refactored: {res.assets_refactored} | Failed: {res.assets_failed}{gitops_tag}{dist_tag}{idx_tag}{trend_tag}{partner_tag}"
                )
        all_success = all(
            r.status in ("SUCCESS", "SKIPPED_NO_CHANGES", "DRY_RUN")
            for r in results.values()
        )
        return 0 if all_success else 1


def cmd_supervisor(args: argparse.Namespace) -> int:
    """
    Executes continuous or single-cycle autonomous lifecycle supervisor:
    1. Monitors engine hash drift and asset ledgers
    2. Coordinates asynchronous multi-tenant rebuilds and audits
    3. Enforces timeout budgets and failure backoff ceilings
    4. Writes atomic heartbeat records (HWL-1231, HWL-1349)
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.supervisor import AutonomousLifecycleSupervisor

    interval = getattr(args, "interval", 3600.0)
    daemon = getattr(args, "daemon", False)
    run_once = getattr(args, "run_once", False)
    property_id = getattr(args, "property", None)
    force = getattr(args, "force", False)
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)
    skip_ci = getattr(args, "skip_ci", False)

    is_once = run_once or (not daemon)
    budget = getattr(args, "budget", None) or float(os.environ.get("PSEUFACTORY_SUPERVISOR_TICK_BUDGET", "2400.0"))

    supervisor = AutonomousLifecycleSupervisor(
        interval=interval,
        execution_budget_seconds=budget,
    )

    prop_ids = [property_id] if property_id else None

    if is_once:
        lock_fd = None
        lock_file = Path(os.environ.get("PSEUFACTORY_SUPERVISOR_LOCK", "/tmp/pseofactory_supervisor.lock"))
        if _ancestor_or_inherited_fd_holds_lock(lock_file):
            os.environ["PSEUFACTORY_SUPERVISOR_LOCK_HELD"] = "1"
        if "PYTEST_CURRENT_TEST" not in os.environ and os.environ.get("PSEUFACTORY_SUPERVISOR_LOCK_HELD") != "1":
            try:
                import fcntl
                lock_fd = open(lock_file, "a+", encoding="utf-8")
                if run_once:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            except OSError:
                if lock_fd is not None:
                    lock_fd.close()
                if as_json:
                    print(json.dumps({"status": "DEFERRED", "reason": "supervisor_lock_busy"}, indent=2))
                else:
                    print("[SUPERVISOR] Deferred: another supervisor or release pipeline holds the central lock.")
                return 75
        try:
            res = supervisor.run_cycle(
                force=force,
                dry_run=dry_run,
                property_ids=prop_ids,
                skip_ci=skip_ci,
            )
        finally:
            if lock_fd is not None:
                try:
                    import fcntl
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except Exception:
                    pass
        if as_json:
            print(json.dumps(res, indent=2))
        else:
            status = res.get("status", "UNKNOWN")
            dur = res.get("duration_seconds", 0.0)
            print(f"[SUPERVISOR] Cycle {res.get('cycle_id')}: status={status} duration={dur:.2f}s")
            if "properties" in res and isinstance(res["properties"], dict):
                from pseofactory.supervisor import extract_failure_reason
                for p, p_res in res["properties"].items():
                    print(f"  - [{p}] status={p_res.get('status')}")
                    if p_res.get("status") in ("FAILED", "TIMEOUT"):
                        reason = extract_failure_reason(p_res.get("failed_records") or [])
                        if reason:
                            print(f"    reason: {reason}")
            if res.get("error"):
                print(f"  error: {res['error']}")
            for esc in res.get("escalations") or []:
                print(
                    f"  ESCALATED [{esc['tenant_id']}] identical failure for {esc['streak']} "
                    f"consecutive cycles since {esc['first_seen']}"
                )
        if res.get("status") == "DEFERRED":
            return 75
        return 0 if res.get("status") in ("SUCCESS", "SKIPPED_ALIGNED", "SKIPPED_NO_CHANGES", "DRY_RUN", "NO_PROPERTIES") else 1
    else:
        try:
            supervisor.start(
                once=False,
                force=force,
                dry_run=dry_run,
                property_ids=prop_ids,
                skip_ci=skip_ci,
            )
            return 0
        except KeyboardInterrupt:
            print("\nSupervisor interrupted by operator. Exiting cleanly.")
            return 0
        except Exception as exc:
            print(f"Supervisor error: {exc}", file=sys.stderr)
            return 1


def cmd_distribute(args: argparse.Namespace) -> int:
    """
    Executes multi-channel syndication export and Voice DNA verification.
    Zero em-dashes. Zero en-dashes.
    """
    property_id = getattr(args, "property", "profithelm") or "profithelm"
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)

    from pseofactory.distributor import dispatch_to_distribution_lead
    res = dispatch_to_distribution_lead(
        run_id=None,
        property_id=property_id,
        dry_run=dry_run,
    )
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print(
            f"[{res.get('status', 'SUCCESS')}] Property: {property_id} | "
            f"Assets: {res.get('total_assets_generated', 0)} | "
            f"Voice Check: {'PASS' if res.get('voice_check_passed') else 'FAIL'}"
        )
    return 0 if res.get("status") in ("SUCCESS", "STAGED", "DRY_RUN") else 1


def cmd_trend_intake(args: argparse.Namespace) -> int:
    """
    Executes automated trend intake and qualification pipeline.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.trends import run_trend_pipeline, FeedSpike, MultiSourceCollector, TregChecker, JevEngine

    spikes = []
    if args.fixture:
        fix_path = Path(args.fixture).resolve()
        if not fix_path.exists():
            print(f"Error: Fixture file not found: {args.fixture}", file=sys.stderr)
            return 1
        with open(fix_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict) and "records" in data:
            raw_list = data["records"]
        else:
            raw_list = [data]

        mock_registry = {}
        for item in raw_list:
            sp = FeedSpike(
                id=str(item.get("id", "")),
                query=str(item.get("query", "")),
                source=str(item.get("source", "fixture")),
                detected_at=str(item.get("detected_at", "")),
                sample_count=int(item.get("sample_count", 1)),
                velocity=float(item.get("velocity", 0.0)),
                acceleration=float(item.get("acceleration", 0.0)),
                z_score=float(item.get("z_score", 0.0)),
                baseline_mean=float(item.get("baseline_mean", 0.0)),
                baseline_std=float(item.get("baseline_std", 0.0)),
                raw_payload=item,
            )
            spikes.append(sp)
            if "treg_mock" in item:
                mock_registry[sp.query.lower().strip()] = item["treg_mock"]

        treg_checker = TregChecker(mock_data=mock_registry, timeout=args.per_item_timeout)
    else:
        seeds = [s.strip() for s in (args.seeds or "calculator,tax deduction,compliance").split(",") if s.strip()]
        collector = MultiSourceCollector()
        spikes = collector.harvest(seeds)
        treg_checker = TregChecker(timeout=args.per_item_timeout)

    if args.source:
        spikes = [s for s in spikes if s.source == args.source]

    jev_engine = JevEngine(min_build_yield=float(args.min_yield))
    result = run_trend_pipeline(
        spikes=spikes,
        sink_path=args.sink,
        treg_checker=treg_checker,
        jev_engine=jev_engine,
        batch_size=args.batch_size,
        cycle_budget=args.cycle_budget,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"[TREND INTAKE] Processed: {result['total_spikes']} | "
            f"Filtered Noise: {result['filtered_noise_count']} | "
            f"Approved Build: {len(result['approved_build'])} | "
            f"Refactor Pages: {len(result['refactor_pages'])} | "
            f"Monitored: {len(result['monitored'])} | "
            f"Rejected: {len(result['rejected'])}"
        )
        for r in result["approved_build"]:
            print(f" -> [BUILD_PAGE] {r['query']} ({r['slug']}) - Yield: {r['composite_profit_yield']:.1f}")
        for r in result["refactor_pages"]:
            print(f" -> [REFACTOR_PAGE] {r['query']} -> {r.get('matching_tool')} (Striking Distance)")

    return 0


def cmd_trend_monitor(args: argparse.Namespace) -> int:
    """
    Executes trend monitoring across streaming sources.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.trends import MultiSourceCollector, TrendPipeline

    seeds = [s.strip() for s in (args.seeds or "calculator,estimator,tax").split(",") if s.strip()]
    collector = MultiSourceCollector()
    spikes = collector.harvest(seeds)
    if args.source:
        spikes = [s for s in spikes if s.source == args.source]

    pipe = TrendPipeline()
    result = pipe.process_spikes(spikes)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[TREND MONITOR] Monitored {len(spikes)} topics across {len(seeds)} seeds.")
        for r in result["rankings"][:5]:
            print(f" - {r['query']} [{r['action']}]: yield={r['composite_profit_yield']:.1f}")

    return 0


def cmd_trend_cron(args: argparse.Namespace) -> int:
    """
    Executes autonomous daily cron loop trend monitoring and longitudinal analysis.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.trends.cron import TrendCronRunner

    try:
        runner = TrendCronRunner(
            db_path=args.db_path,
            min_yield=float(args.min_yield),
        )
        result = runner.run_cycle(
            cycle_id=args.cycle_id,
            fixture_path=args.fixture,
            seeds=args.seeds,
            property_filter=args.property,
            dry_run=args.dry_run,
            include_unassigned=getattr(args, "include_unassigned", False),
            sink_path=getattr(args, "sink", None),
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                f"[TREND CRON] Cycle: {result['cycle_id']} | "
                f"Observations: {result['total_raw_observations']} | "
                f"Unique: {result['unique_queries_count']} | "
                f"Filtered: {result['filtered_noise_count']} | "
                f"Build: {len(result['approved_build'])} | "
                f"Refactor: {len(result['refactor_pages'])} | "
                f"Monitored: {len(result['monitored'])} | "
                f"Proposals: {len(result.get('proposals', []))}"
            )
            for b in result["approved_build"]:
                print(f" -> [BUILD_PAGE] {b['query']} ({b['property_id']}) - Yield: {b['composite_profit_yield']:.1f}")
            for r in result["refactor_pages"]:
                print(f" -> [REFACTOR_PAGE] {r['query']} ({r['property_id']}) -> {r.get('matching_tool')} (Striking Distance)")
            for p in result.get("proposals", []):
                print(f" -> [PROPOSE_NEW_APP] {p['cluster_slug']} - Yield: {p['mean_composite_yield']:.1f} - Sustained: {p['consecutive_cycles_sustained']} cycles")
        return 0
    except Exception as ex:
        print(f"Error executing trend-cron: {ex}", file=sys.stderr)
        return 1


def cmd_factory_pipeline(args: argparse.Namespace) -> int:
    """
    Executes automated discovery and content generation pipeline across breakout search spikes.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.pipeline import FactoryPipeline, PipelineConfig

    if not getattr(args, "fixture", None) and not getattr(args, "seeds", None):
        from pseofactory.maintenance import TenantRegistry, FleetMaintenanceCoordinator
        reg = TenantRegistry.default()
        coordinator = FleetMaintenanceCoordinator(registry=reg)
        dry_run = getattr(args, "dry_run", False)
        skip_ci = getattr(args, "skip_ci", False)
        results = coordinator.run_fleet(
            force=getattr(args, "force", False),
            dry_run=dry_run,
            enable_gitops=True,
            enable_distribution=True,
            skip_ci=skip_ci,
        )
        if getattr(args, "json", False):
            print(json.dumps({k: v.to_dict() if hasattr(v, "to_dict") else str(v) for k, v in results.items()}, indent=2))
        else:
            for pid, res in results.items():
                p_id = getattr(res, "property_id", pid)
                st = getattr(res, "status", "UNKNOWN")
                print(f"[{st}] Property: {p_id}")
        all_ok = all(
            (getattr(r, "status", None) in ("SUCCESS", "SKIPPED_NO_CHANGES", "DRY_RUN"))
            for r in results.values()
        )
        return 0 if all_ok else 1

    spikes_data = []
    if getattr(args, "fixture", None):
        fix_path = Path(args.fixture).resolve()
        if not fix_path.exists():
            print(f"[ERROR] Fixture file not found: {fix_path}", file=sys.stderr)
            return 1
        raw = json.loads(fix_path.read_text(encoding="utf-8"))
        spikes_data = raw if isinstance(raw, list) else [raw]
    elif getattr(args, "seeds", None):
        from pseofactory.trends.collectors import MultiSourceCollector
        seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
        collector = MultiSourceCollector()
        spikes = collector.harvest(seeds)
        if getattr(args, "source", None):
            spikes = [s for s in spikes if s.source == args.source]
        spikes_data = spikes

    config = PipelineConfig(
        min_jev_score=getattr(args, "min_jev", 1.20),
        min_durable_prob=getattr(args, "min_prob", 0.50),
        min_build_yield=getattr(args, "min_yield", 60.0),
        sink_path=Path(args.sink) if getattr(args, "sink", None) else None,
        dry_run=getattr(args, "dry_run", False),
    )

    pipeline = FactoryPipeline(config=config)
    result = pipeline.execute(
        raw_spikes=spikes_data,
        output_dir=getattr(args, "output_dir", None),
    )

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(
            f"[FACTORY PIPELINE] Total: {result.total_spikes} | "
            f"Filtered Noise: {result.filtered_noise_count} | "
            f"Evaluated: {result.evaluated_count} | "
            f"Compiled: {result.compiled_count} | "
            f"Aborted: {result.aborted_count}"
        )
        for asset in result.compiled_assets:
            print(f" -> [COMPILED] [{asset.tenant}] {asset.query} ({asset.slug}) - HTML len: {asset.html_length}")
        for aborted in result.aborted_opportunities:
            print(f" -> [ABORTED] {aborted.query} - Reason: {aborted.reason} [{aborted.action}]")

    return 0


def cmd_trend_backfill(args: argparse.Namespace) -> int:
    """
    Executes historical session crawl and idempotent bulk insert into trend history DB.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.trends.backfill import run_trend_backfill

    try:
        result = run_trend_backfill(
            db_path=args.db_path,
            staging_dir=args.staging_dir,
            dlq_path=args.dlq_path,
            fixture_path=getattr(args, "fixture", None),
            dry_run=getattr(args, "dry_run", False),
            limit_cycles=getattr(args, "limit_cycles", None),
        )
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            print(
                f"[TREND BACKFILL] Evaluated: {result['total_cycles_evaluated']} cycles | "
                f"Completed: {result['cycles_completed']} | "
                f"Skipped: {result['cycles_skipped']} | "
                f"Observations: {result['total_observations_inserted']} | "
                f"Keywords: {result['total_keywords_upserted']} | "
                f"Proposals: {result['total_proposals_created']}"
            )
        return 0
    except Exception as ex:
        print(f"Error executing trend-backfill: {ex}", file=sys.stderr)
        return 1


def cmd_sync_monetization(args: argparse.Namespace) -> int:
    """
    Synchronizes approved partner programs into local monetization vault.
    Supports payload file or raw JSON string, dry-run evaluation, and JSON reporting.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.affiliates_hub import MonetizationHub

    hub = MonetizationHub()
    payload_data = None

    if args.payload:
        raw_val = args.payload.strip()
        if os.path.isfile(raw_val):
            try:
                with open(raw_val, "r", encoding="utf-8") as f:
                    payload_data = json.load(f)
            except Exception as exc:
                if args.json:
                    print(json.dumps({"ok": False, "error": f"Failed to read payload file: {exc}"}))
                else:
                    print(f"Error: Failed to read payload file: {exc}", file=sys.stderr)
                return 1
        else:
            try:
                payload_data = json.loads(raw_val)
            except json.JSONDecodeError as exc:
                if args.json:
                    print(json.dumps({"ok": False, "error": f"Invalid JSON payload: {exc}"}))
                else:
                    print(f"Error: Invalid JSON payload: {exc}", file=sys.stderr)
                return 1
    else:
        if args.json:
            print(json.dumps({"ok": False, "error": "Missing --payload argument"}))
        else:
            print("Error: --payload argument is required.", file=sys.stderr)
        return 1

    try:
        report = hub.sync_from_network_payload(
            network=args.network,
            payload=payload_data,
            property_id=args.property,
            save=not args.dry_run,
        )
        report["ok"] = True
        report["dry_run"] = args.dry_run

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Monetization Sync Complete [{args.network} -> {args.property}]")
            print(f"  Received: {report.get('total_received', 0)}")
            print(f"  Updated:  {report.get('updated', 0)}")
            print(f"  Skipped:  {report.get('skipped', 0)}")
            if report.get("errors"):
                print(f"  Errors:   {len(report['errors'])}")
                for err in report["errors"]:
                    print(f"    - {err}")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"Sync failed: {exc}", file=sys.stderr)
        return 1


def cmd_partner_sync(args: argparse.Namespace) -> int:
    """
    Executes automated email checking across zoho and personal inboxes,
    reconciles partner applications, and routes operator action items.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.partner_tracker import PartnerTrackingEngine

    engine = PartnerTrackingEngine()
    try:
        dashboard = engine.sync_and_evaluate(
            force_mail_poll=getattr(args, "force", False),
            personal_fixture=getattr(args, "personal_fixture", None),
        )
        if getattr(args, "json", False):
            print(json.dumps(dashboard.to_dict(), indent=2))
        else:
            print(f"Partner Correspondence Sync Complete [Updated: {dashboard.updated_at}]")
            ph = dashboard.profithelm
            px = dashboard.prexvo
            print(f"  ProfitHelm Active Partners: {ph.active_partners_count} / {ph.total_registered_partners} (Readiness: {ph.monetization_readiness_score}%)")
            print(f"  Prexvo Active Partners:     {px.active_partners_count} / {px.total_registered_partners} (Readiness: {px.monetization_readiness_score}%)")
            pending_count = sum(1 for it in dashboard.all_action_items if it.status == "PENDING_OPERATOR")
            print(f"  Human Action Bus Items:     {pending_count} pending operator confirmation")
        return 0
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"Error during partner sync: {exc}", file=sys.stderr)
        return 1


def cmd_partner_status(args: argparse.Namespace) -> int:
    """
    Displays actionable application status and monetization readiness across ProfitHelm and Prexvo.
    Optionally exports the minimal modern light interface HTML.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.partner_tracker import PartnerTrackingEngine
    from pseofactory.ui import render_light_interface

    engine = PartnerTrackingEngine()
    try:
        dashboard = engine.sync_and_evaluate(
            force_mail_poll=getattr(args, "force_poll", False)
        )

        if getattr(args, "html", None):
            html_content = render_light_interface(dashboard)
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(html_content)
            if not getattr(args, "json", False):
                print(f"Standalone light interface exported to: {args.html}")

        if getattr(args, "json", False):
            res = dashboard.to_dict()
            prop_filter = getattr(args, "property", None)
            if prop_filter:
                p_clean = prop_filter.strip().lower()
                res = res.get(p_clean, res)
            print(json.dumps(res, indent=2))
            return 0

        prop_filter = getattr(args, "property", None)
        reports = []
        if not prop_filter or prop_filter.lower() in ("all", "profithelm"):
            reports.append(dashboard.profithelm)
        if not prop_filter or prop_filter.lower() in ("all", "prexvo"):
            reports.append(dashboard.prexvo)

        for r in reports:
            print(f"=== {r.property_name} Monetization Readiness: {r.monetization_readiness_score}% ===")
            print(f"  Active Live: {r.active_partners_count} | Awaiting: {r.awaiting_response_count} | Follow-up: {r.requires_followup_count} | Pending: {r.pending_expansion_count}")
            print("  Partners:")
            for p in r.partners:
                mark = "[LIVE]" if p.operational_status == "LIVE_ACTIVE" else f"[{p.operational_status}]"
                req_str = f" (Needs: {', '.join(p.missing_requirements)})" if p.missing_requirements else ""
                print(f"    - {mark} {p.name} ({p.category}) - Bounty: {p.bounty_est}{req_str}")

        pending_actions = [it for it in dashboard.all_action_items if it.status == "PENDING_OPERATOR"]
        if prop_filter and prop_filter.lower() != "all":
            pending_actions = [it for it in pending_actions if it.property_id.lower() == prop_filter.lower()]
        if pending_actions:
            print(f"\n=== Dedicated Human Action Bus ({len(pending_actions)} Pending Operator Confirmation) ===")
            for it in pending_actions:
                dead_str = f" [Deadline: {it.deadline}]" if it.deadline else ""
                print(f"  * [{it.severity}] [{it.property_id}] {it.title}{dead_str}")
                print(f"    Action ID: {it.action_id} | Requires confirmation (auto-approval forbidden)")
        return 0
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"Error evaluating partner status: {exc}", file=sys.stderr)
        return 1


def cmd_partner_action(args: argparse.Namespace) -> int:
    """
    Manages operator intervention actions on the human action bus.
    Enforces that partner agreements cannot be auto-approved without operator confirmation.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.action_bus import HumanActionBus

    bus = HumanActionBus()
    action_subcmd = getattr(args, "action_command", "list")

    if action_subcmd == "list":
        pending = bus.get_pending_items(property_id=getattr(args, "property", None))
        if getattr(args, "json", False):
            print(json.dumps([it.to_dict() for it in pending], indent=2))
        else:
            print(f"Dedicated Human Action Bus ({len(pending)} pending decisions):")
            for it in pending:
                dead_str = f" [Deadline: {it.deadline}]" if it.deadline else ""
                print(f"  - [{it.severity}] {it.action_id}: {it.title}{dead_str}")
                print(f"    {it.description}")
        return 0

    action_id = getattr(args, "action_id", None)
    if not action_id:
        print("Error: action_id is required.", file=sys.stderr)
        return 1

    if action_subcmd in ("approve", "reject", "resolve"):
        decision_map = {"approve": "APPROVE", "reject": "REJECT", "resolve": "RESOLVE"}
        decision = decision_map[action_subcmd]
        notes = getattr(args, "notes", "") or f"Manual operator {action_subcmd} executed via CLI."
        operator = getattr(args, "operator", "operator") or "operator"
        try:
            updated = bus.confirm_decision(
                action_id=action_id,
                decision=decision,
                operator=operator,
                notes=notes,
            )
            if getattr(args, "json", False):
                print(json.dumps(updated.to_dict(), indent=2))
            else:
                print(f"Confirmed {decision} for action '{action_id}' (by {operator}). Status: {updated.status}")
            return 0
        except Exception as exc:
            print(f"Error executing action decision: {exc}", file=sys.stderr)
            return 1
    else:
        print(f"Unknown action command: {action_subcmd}", file=sys.stderr)
        return 1


def cmd_partner_ui(args: argparse.Namespace) -> int:
    """
    Starts minimal modern light interface dashboard server or inspects daemon status.
    Zero em-dashes. Zero en-dashes.
    """
    import subprocess
    import urllib.request
    from pseofactory.ui import run_ui_server, get_ui_runtime_state, DEFAULT_UI_PORT, DEFAULT_UI_HOST

    if getattr(args, "status", False):
        runtime_state = get_ui_runtime_state()
        svc_active = False
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", "pseofactory-partner-ui.service"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            svc_active = (res.returncode == 0 and res.stdout.strip() == "active")
        except Exception:
            svc_active = False

        host = getattr(args, "host", None) or (runtime_state.get("host") if runtime_state else None) or DEFAULT_UI_HOST
        user_specified_port = any(arg.startswith("--port") for arg in sys.argv)
        if user_specified_port and getattr(args, "port", None):
            ports_to_probe = [args.port]
        else:
            ports_to_probe = []
            if runtime_state and runtime_state.get("port"):
                ports_to_probe.append(runtime_state["port"])
            default_p = getattr(args, "port", DEFAULT_UI_PORT) or DEFAULT_UI_PORT
            if default_p not in ports_to_probe:
                ports_to_probe.append(default_p)

        http_ok = False
        active_port = ports_to_probe[0] if ports_to_probe else DEFAULT_UI_PORT
        probe_timeout = float(os.getenv("PSEUFACTORY_PROBE_TIMEOUT", 0.3 if "PYTEST_CURRENT_TEST" in os.environ else 1.0))
        for p in ports_to_probe:
            try:
                req = urllib.request.Request(f"http://{host}:{p}/api/status", headers={"User-Agent": "pseofactory-cli"})
                with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                    if resp.status == 200:
                        http_ok = True
                        active_port = p
                        break
            except Exception:
                continue

        status_info = {
            "service_active": svc_active,
            "http_responsive": http_ok,
            "host": host,
            "port": active_port,
            "url": f"http://{host}:{active_port}/",
            "runtime_state": runtime_state,
        }

        if getattr(args, "json", False):
            print(json.dumps(status_info, indent=2))
        else:
            print("=== pseofactory Partner UI Status ===")
            print(f"  Systemd Service: {'ACTIVE' if svc_active else 'INACTIVE'}")
            print(f"  HTTP Endpoint:   {'RESPONSIVE (200 OK)' if http_ok else 'UNAVAILABLE'}")
            print(f"  URL:             http://{host}:{active_port}/")
            if runtime_state:
                print(f"  PID:             {runtime_state.get('pid')}")
                print(f"  State:           {runtime_state.get('status')}")
                print(f"  Updated At:      {runtime_state.get('updated_at')}")
        return 0 if (svc_active or http_ok) else 1

    port = getattr(args, "port", None)
    if port is None:
        port = DEFAULT_UI_PORT
    host = getattr(args, "host", DEFAULT_UI_HOST)
    try:
        run_ui_server(port=port, host=host)
        return 0
    except Exception as exc:
        print(f"Error starting dashboard server: {exc}", file=sys.stderr)
        return 1


def cmd_indexing_preflight(args: argparse.Namespace) -> int:
    """
    Executes automated indexing preflight inspection and crawl budget partitioning.
    Returns 0 on success/clean, 1 on strict blocked URLs, 2 on argument/config error.
    """
    property_id = getattr(args, "property", None) or "profithelm"
    domain = f"{property_id}.com"
    dist_dir = Path(args.dist_dir).resolve() if getattr(args, "dist_dir", None) else None

    reg = TenantRegistry.default()
    if getattr(args, "property", None):
        try:
            adapter = reg.get_adapter(args.property)
            domain = adapter.domain
            if not dist_dir:
                dist_dir = adapter.dist_dir
        except KeyError:
            if not getattr(args, "fixture", None) and not getattr(args, "urls", None) and not getattr(args, "sitemap", None) and not dist_dir:
                print(f"Error: Property '{args.property}' not found in registry and no targets provided", file=sys.stderr)
                return 2

    if not getattr(args, "fixture", None) and not getattr(args, "urls", None) and not getattr(args, "sitemap", None) and not dist_dir:
        default_dist = Path("dist")
        if default_dist.exists():
            dist_dir = default_dist.resolve()
        else:
            print("Error: No inspection target specified (--fixture, --urls, --sitemap, --dist-dir)", file=sys.stderr)
            return 2

    from pseofactory.indexing.preflight import run_indexing_preflight
    try:
        report = run_indexing_preflight(
            urls=getattr(args, "urls", None),
            dist_dir=dist_dir,
            sitemap_path=getattr(args, "sitemap", None),
            fixture_path=getattr(args, "fixture", None),
            domain=domain,
            property_id=property_id,
            min_words=getattr(args, "min_words", 150),
            tier1_cap=getattr(args, "tier1_cap", 150),
        )
    except Exception as ex:
        print(f"Error executing indexing preflight: {ex}", file=sys.stderr)
        return 2

    as_json = getattr(args, "json", False) or getattr(args, "format", "table") == "json"
    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("=" * 60)
        print(f"INDEXING PREFLIGHT REPORT: {property_id.upper()} ({domain})")
        print("=" * 60)
        print(f"Total Inspected:       {report.total_inspected}")
        print(f"Passed URLs:           {report.passed_count}")
        print(f"Blocked URLs:          {report.blocked_count}")
        print(f"Tier-1 Hubs (Push):    {report.tier1_hubs_eligible} (cap {getattr(args, 'tier1_cap', 150)})")
        print(f"Tier-2 Leaves (Queue): {report.tier2_leaves_queued}")
        print(f"Gate Status:           {'PASS' if report.is_gate_passed else 'FAIL'}")
        print("-" * 60)
        print("Breakdown:")
        for status_name, cnt in report.breakdown.items():
            print(f"  {status_name:<30}: {cnt}")
        if report.blocked_urls:
            print("-" * 60)
            print(f"Blocked Sample (up to 5 of {len(report.blocked_urls)}):")
            for u in report.blocked_urls[:5]:
                print(f"  [X] {u}")
        print("=" * 60)

    if getattr(args, "dry_run", False):
        return 0

    if getattr(args, "strict", False) and not report.is_gate_passed:
        return 1

    return 0


def cmd_gsc_ceiling(args: argparse.Namespace) -> int:
    """Executes Search Console traffic trends and algorithmic ceiling detection."""
    from datetime import datetime, timezone
    from pseofactory.trends.models import GSCDailyMetricRecord, GoogleUpdateEvent
    from pseofactory.trends.gsc_ceiling import detect_algorithmic_ceiling, DEFAULT_GOOGLE_UPDATES
    from pseofactory.trends.db import TrendHistoryDB
    from pseofactory.ui import render_gsc_ceiling_dashboard

    property_id = getattr(args, "property", "profithelm") or "profithelm"
    days = getattr(args, "days", 480)
    fixture_path = getattr(args, "fixture", None)
    threshold = getattr(args, "ceiling_threshold", 0.35)
    updates_path = getattr(args, "updates", None)
    output_json = getattr(args, "json", False)
    html_out = getattr(args, "html", None)

    records: List[GSCDailyMetricRecord] = []
    updates: Optional[List[GoogleUpdateEvent]] = None

    if fixture_path:
        p = Path(fixture_path).resolve()
        if not p.is_file():
            print(f"Error: Fixture file not found: {fixture_path}", file=sys.stderr)
            return 1
        try:
            with open(p, "r", encoding="utf-8") as f:
                fix_data = json.load(f)
            if isinstance(fix_data, dict):
                metric_dicts = fix_data.get("metrics") or fix_data.get("records") or []
                update_dicts = fix_data.get("google_updates") or fix_data.get("updates") or []
                if "property_id" in fix_data and not getattr(args, "property", None):
                    property_id = fix_data["property_id"]
                if update_dicts and not updates_path:
                    updates = [GoogleUpdateEvent.from_dict(u) for u in update_dicts]
            elif isinstance(fix_data, list):
                metric_dicts = fix_data
            else:
                metric_dicts = []

            records = [
                GSCDailyMetricRecord(
                    property_id=m.get("property_id", property_id),
                    date=m["date"],
                    clicks=int(m.get("clicks", 0)),
                    impressions=int(m.get("impressions", 0)),
                    ctr=float(m.get("ctr", 0.0)),
                    position=float(m.get("position", 0.0)),
                    recorded_at=m.get("recorded_at", datetime.now(timezone.utc).isoformat()),
                )
                for m in metric_dicts
            ]
        except Exception as ex:
            print(f"Error parsing fixture file: {ex}", file=sys.stderr)
            return 1
    else:
        try:
            db = TrendHistoryDB()
            records = db.get_gsc_daily_metrics(property_id, days=days)
            if not updates_path:
                updates = db.get_google_update_events()
                if not updates:
                    updates = DEFAULT_GOOGLE_UPDATES
        except Exception as ex:
            print(f"Error connecting to TrendHistoryDB: {ex}", file=sys.stderr)
            return 1

    if updates_path:
        up_path = Path(updates_path).resolve()
        if not up_path.is_file():
            print(f"Error: Updates file not found: {updates_path}", file=sys.stderr)
            return 1
        try:
            with open(up_path, "r", encoding="utf-8") as f:
                up_data = json.load(f)
            u_list = up_data if isinstance(up_data, list) else up_data.get("updates", [])
            updates = [GoogleUpdateEvent.from_dict(u) for u in u_list]
        except Exception as ex:
            print(f"Error loading updates file: {ex}", file=sys.stderr)
            return 1

    analysis = detect_algorithmic_ceiling(records, updates=updates, threshold=threshold)

    if not fixture_path:
        try:
            db = TrendHistoryDB()
            db.record_gsc_ceiling_snapshot(analysis)
        except Exception:
            pass

    if html_out:
        html_markup = render_gsc_ceiling_dashboard(analysis)
        h_path = Path(html_out).resolve()
        h_path.parent.mkdir(parents=True, exist_ok=True)
        h_path.write_text(html_markup, encoding="utf-8")
        if not output_json:
            print(f"Wrote GSC ceiling dashboard to {h_path}")

    if output_json:
        print(json.dumps(analysis.to_dict(), indent=2))
    elif not html_out:
        print("=" * 60)
        print(f"GSC TRAFFIC TRENDS & CEILING ANALYSIS: {property_id.upper()}")
        print("=" * 60)
        print(f"Total Days Analyzed:      {analysis.total_days}")
        print(f"Peak Impressions (RMA 28): {int(analysis.peak_impressions_rma28)}")
        print(f"Current Velocity (RMA 28): {int(analysis.current_impressions_rma28)}")
        print(f"Ceiling Threshold:        {analysis.ceiling_threshold}")
        print(f"Dampening Score:          {analysis.ceiling_dampening_score:.2f}")
        print(f"Ceiling Detected:         {'YES' if analysis.ceiling_detected else 'NO'}")
        print(f"Suppression Severity:     {analysis.suppression_severity}")
        print(f"Recommendation:           {analysis.recommendation}")
        print(f"Correlated Updates:       {len(analysis.correlated_updates)}")
        if analysis.correlated_updates:
            print("-" * 60)
            print("Correlated Google Updates:")
            for cu in analysis.correlated_updates:
                print(f"  * {cu['name']} ({cu['start_date']}): drop ratio {cu['drop_ratio']:.2%}")
        print("=" * 60)

    return 0


def cmd_indexing_inspect(args: argparse.Namespace) -> int:
    """
    Executes Daily Indexing Inspector audit across GSC rollover queue, airlock quarantine,
    velocity ledger, and search traffic trajectory (Loop 3).
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.indexer import PushIndexer
    property_id = getattr(args, "property", "profithelm") or "profithelm"
    strict = getattr(args, "strict", False)
    dry_run = getattr(args, "dry_run", False)
    sample = getattr(args, "sample", False)
    auto_remediate = getattr(args, "auto_remediate", False)
    prune_sitemaps = getattr(args, "prune_sitemaps", False)
    output_json = getattr(args, "json", False)

    inspector = DailyIndexingInspector(tenant_id=property_id)
    report = inspector.run_inspection(
        strict=strict,
        dry_run=dry_run,
        sample=sample,
        auto_remediate=auto_remediate,
    )
    if prune_sitemaps or auto_remediate:
        try:
            indexer = PushIndexer(
                domain=f"{property_id}.com",
                tenant_id=property_id,
                dist_dir=inspector.base_dir / "dist",
            )
            report["sitemap_hygiene"] = indexer.prune_dead_gsc_sitemaps(live=not dry_run)
        except Exception as ex:
            report["sitemap_hygiene"] = {"status": "ERROR", "error": str(ex)}

    if output_json:
        print(json.dumps(report, indent=2))
    else:
        status = report.get("audit_status", "UNKNOWN")
        print(f"[{status}] Daily Indexing Inspection for '{report.get('tenant_id')}':")
        print(f"  - Rollover Queue: size={report['gsc_rollover']['queue_size']}, quota_exhausted={report['gsc_rollover']['quota_exhausted']}")
        print(f"  - Quarantine: total={report['airlock_quarantine']['total_quarantined']}, 404s={report['airlock_quarantine']['breakdown'].get('HTTP_404', 0)}")
        print(f"  - Velocity: stalled={report['velocity_stagnation']['stalled_routes_count']}/{report['velocity_stagnation']['routes_monitored']}")
        if report.get("remediation_prompts"):
            print("  Suggested Remediation Prompts:")
            for prompt in report["remediation_prompts"]:
                print(f"    * {prompt}")

    if strict and report.get("audit_status") in ("FAIL", "WARN"):
        return 1
    return 0


def cmd_indexing_feedback_loop(args: argparse.Namespace) -> int:
    """
    Executes autonomous closed-loop indexing feedback coordinator (Loop 4).
    Audits unindexed pages, diagnoses root causes, reflects engine repairs,
    enforces preflight airlock, and dispatches multi-engine push indexing.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop
    from pseofactory.indexer import PushIndexer
    property_id = getattr(args, "property", "profithelm") or "profithelm"
    dry_run = getattr(args, "dry_run", False)
    live = getattr(args, "live", False)
    output_json = getattr(args, "json", False)

    coordinator = IndexingFeedbackLoop(property_id=property_id)
    result = coordinator.run_feedback_cycle(dry_run=dry_run, live=live)
    try:
        indexer = PushIndexer(
            domain=coordinator.domain,
            tenant_id=property_id,
            dist_dir=coordinator.dist_dir,
        )
        result["sitemap_hygiene"] = indexer.prune_dead_gsc_sitemaps(live=(live and not dry_run))
    except Exception as ex:
        result["sitemap_hygiene"] = {"status": "ERROR", "error": str(ex)}

    if output_json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "UNKNOWN")
        print(f"[{status}] Indexing Feedback Loop for '{result.get('property_id')}':")
        print(f"  - Audited unindexed: {result.get('unindexed_audited', 0)}")
        print(f"  - Diagnosed defects: {len(result.get('diagnosed_defects', []))}")
        print(f"  - Repaired & recompiled assets: {result.get('repair_summary', {}).get('recompiled_assets_count', 0)}")
        print(f"  - Preflight inspected: {result.get('preflight_summary', {}).get('total_inspected', 0)} (push eligible: {result.get('preflight_summary', {}).get('push_eligible', 0)})")
        print(f"  - Multi-engine push status: {result.get('push_summary', {}).get('status')}")
    return 0 if result.get("status") in ("SUCCESS", "PARTIAL") else 1


def cmd_market_intel(args: argparse.Namespace) -> int:
    """
    Executes the Market Intelligence Workflow measuring buyer intent, organic ranking difficulty,
    and active commission offers to rank the fastest-monetizing new programmatic tenant candidates.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.market_intel import MarketIntelligenceEngine
    from pseofactory.trends.db import DEFAULT_DB_PATH

    db_path = getattr(args, "db_path", None) or str(DEFAULT_DB_PATH)
    engine = MarketIntelligenceEngine(db_path=db_path)

    query_arg = getattr(args, "query", None)
    if query_arg:
        q_res = engine.evaluate_query_opportunity(query=query_arg)
        if getattr(args, "json", False):
            print(json.dumps(q_res, indent=2))
        else:
            print(
                f"[MARKET INTEL QUERY] {q_res['query']} -> Tenant: {q_res['recommended_brand_name']} ({q_res['recommended_domain']})"
            )
            print(
                f"  Fast-Money Score: {q_res['fast_money_score']:.2f} | "
                f"Buyer Intent: {q_res['buyer_intent']['buyer_intent_score']:.2f} | "
                f"Ease of Ranking: {q_res['ranking_difficulty']['ease_of_ranking_score']:.2f} (KD {q_res['keyword_difficulty']:.1f}) | "
                f"Commission Score: {q_res['active_commission_offers']['commission_offer_score']:.2f}"
            )
            print(
                f"  Expected Bounty: ${q_res['active_commission_offers']['expected_bounty_usd']:.2f} | "
                f"Projected Monthly Rev: ${q_res['projected_monthly_revenue_usd']:.2f} | "
                f"Est. Days to First Dollar: {q_res['estimated_days_to_first_dollar']}d"
            )
        return 0

    sync_db = getattr(args, "sync_db", False)
    confirm_cycles = getattr(args, "confirm_three_cycles", False)
    output_path = getattr(args, "output", None)
    top_k = getattr(args, "top", None)

    report = engine.run_workflow(
        sync_db=sync_db,
        simulate_three_cycle_confirmation=confirm_cycles,
        output_path=output_path,
        top_k=top_k,
    )

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print("=" * 88)
        print("PSEOFACTORY MARKET INTELLIGENCE: TOP NEW TENANT CANDIDATES (FASTEST REAL MONEY)")
        print("=" * 88)
        for cand in report["top_new_tenant_candidates"]:
            primary_offer = cand["active_commission_offers"][0] if cand["active_commission_offers"] else {}
            print(
                f"#{cand['rank']} {cand['brand_name']} ({cand['recommended_domain']}) | "
                f"Fast-Money Score: {cand['fast_money_score']:.2f}/100 | "
                f"Yield: {cand['composite_profit_yield']:.2f}"
            )
            print(
                f"   Vertical: {cand['vertical_name']}"
            )
            print(
                f"   Buyer Intent: {cand['buyer_intent_score']:.1f}/100 (Mean CPC ${cand['mean_cpc_usd']:.2f}, Vol {cand['aggregate_search_volume']:,}/mo) | "
                f"Ranking Ease: {cand['ease_of_ranking_score']:.1f}/100 (Mean KD {cand['mean_keyword_difficulty']:.1f})"
            )
            print(
                f"   Commission Score: {cand['commission_offer_score']:.1f}/100 | "
                f"Lead Offer: {primary_offer.get('partner_name', 'N/A')} (${cand['expected_bounty_usd']:.0f} bounty via {primary_offer.get('network', 'N/A')})"
            )
            print(
                f"   Projected Monthly Revenue: ${cand['projected_monthly_revenue_usd']:,.2f}/mo | "
                f"Est. Days to First Dollar: {cand['estimated_days_to_first_dollar']} days | "
                f"Isolation Verified: {cand['isolation_boundary_verified']}"
            )
            print("-" * 88)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Builds argument parser for pseofactory CLI commands."""
    parser = argparse.ArgumentParser(
        prog="pseofactory",
        description="Unified Programmatic SEO Substrate for Prexvo and ProfitHelm Software Factories",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # cycle
    p_cycle = subparsers.add_parser("cycle", help="Execute complete autonomous release cycle across property or fleet")
    p_cycle.add_argument("--property", type=str, default=None, help="Optional property ID (default: all fleet properties)")
    p_cycle.add_argument("--dry-run", action="store_true", help="Dry-run audit mode without committing or pushing")
    p_cycle.add_argument("--timeout", type=int, default=300, help="Timeout in seconds for CI watcher")
    p_cycle.add_argument("--skip-ci", action="store_true", help="Skip remote CI/CD quality gate watching")
    p_cycle.add_argument("--fast", action="store_true", help="Enable fast mode: aggressive polling intervals and concurrency")
    p_cycle.add_argument("--json", action="store_true", help="Output result as JSON")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit static assets against engine baselines")
    p_audit.add_argument("--property", type=str, default=None, help="Property ID (e.g. prexvo, profithelm)")
    p_audit.add_argument("--dist-dir", type=str, default=None, help="Explicit dist directory to audit")
    p_audit.add_argument("--browser", action="store_true", help="Audit static distribution using live Chrome DevTools Protocol (CDP)")
    p_audit.add_argument("--sample", type=int, default=None, help="Sample N routes for fast browser audit")
    p_audit.add_argument("--cdp-port", type=int, default=9222, help="Chrome DevTools Protocol port (default: 9222)")
    p_audit.add_argument("--fail-closed", action="store_true", help="Fail closed if Chrome CDP port is unreachable")
    p_audit.add_argument("--check-engine-drift", action="store_true", help="Audit engine hash drift against state file")
    p_audit.add_argument("--json", action="store_true", help="Output result as JSON")

    # maintain
    p_maintain = subparsers.add_parser("maintain", help="Execute closed-loop maintenance lifecycle on a property")
    p_maintain.add_argument("--property", type=str, default="prexvo", help="Property ID (default: prexvo)")
    p_maintain.add_argument("--force", action="store_true", help="Force rebuild even if no drift detected")
    p_maintain.add_argument("--fast", action="store_true", help="Enable fast mode: aggressive polling intervals and concurrency")
    p_maintain.add_argument("--auto-heal", action="store_true", help="Automatically heal drifted assets in single pass")
    p_maintain.add_argument("--json", action="store_true", help="Output result as JSON")

    # refactor
    p_refactor = subparsers.add_parser("refactor", help="Rebuild and refactor a single drifted asset")
    p_refactor.add_argument("--property", type=str, required=True, help="Property ID")
    p_refactor.add_argument("--asset", type=str, required=True, help="Asset slug or file path")
    p_refactor.add_argument("--json", action="store_true", help="Output result as JSON")

    # fleet-maintain
    p_fleet = subparsers.add_parser("fleet-maintain", help="Execute fleet maintenance across all tenants")
    p_fleet.add_argument("--dry-run", action="store_true", help="Dry-run audit mode without modifying assets")
    p_fleet.add_argument("--force", action="store_true", help="Force refactor across all tenants")
    p_fleet.add_argument("--json", action="store_true", help="Output result as JSON")

    # drift
    p_drift = subparsers.add_parser("drift", help="Audit engine hash drift")
    p_drift.add_argument("--state-file", type=str, default=None, help="Path to engine_hash.json")
    p_drift.add_argument("--record", action="store_true", help="Persist current engine hash into state file")
    p_drift.add_argument("--json", action="store_true", help="Output result as JSON")

    # replay-dlq
    p_dlq = subparsers.add_parser("replay-dlq", help="Inspect and replay quarantined Dead Letter Queue (DLQ) entries")
    p_dlq.add_argument("--list", action="store_true", help="List currently quarantined DLQ entries without replaying")
    p_dlq.add_argument("--property", type=str, default=None, help="Optional property ID filter")
    p_dlq.add_argument("--slug", type=str, default=None, help="Optional slug filter")
    p_dlq.add_argument("--dlq-path", type=str, default=None, help="Custom DLQ JSON path")
    p_dlq.add_argument("--json", action="store_true", help="Output result as JSON")

    # trend-intake
    p_intake = subparsers.add_parser("trend-intake", help="Execute automated breakout trend intake and Jev decision pipeline")
    p_intake.add_argument("--fixture", type=str, default=None, help="Path to JSON fixture file containing raw spikes")
    p_intake.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries for live streaming intake")
    p_intake.add_argument("--source", type=str, default=None, help="Optional feed source filter (e.g. google_suggest)")
    p_intake.add_argument("--sink", type=str, default="void_candidates.jsonl", help="Output path for JSONL candidates sink (default: void_candidates.jsonl)")
    p_intake.add_argument("--min-yield", type=float, default=60.0, help="Minimum composite profit yield threshold (default: 60.0)")
    p_intake.add_argument("--batch-size", type=int, default=15, help="Maximum candidate spikes to evaluate per cycle (default: 15, ceiling: 25)")
    p_intake.add_argument("--cycle-budget", type=float, default=240.0, help="Cycle execution deadline budget in seconds before degradation (default: 240.0s)")
    p_intake.add_argument("--per-item-timeout", type=float, default=5.0, help="Per-candidate external network check timeout in seconds (default: 5.0s)")
    p_intake.add_argument("--json", action="store_true", help="Output result as JSON")

    # factory-run
    p_factory = subparsers.add_parser("factory-run", help="Execute automated discovery and content generation pipeline")
    p_factory.add_argument("--fixture", type=str, default=None, help="Path to JSON fixture file containing raw spikes")
    p_factory.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries for streaming intake")
    p_factory.add_argument("--source", type=str, default=None, help="Optional feed source filter")
    p_factory.add_argument("--sink", type=str, default=None, help="Optional sink path for flock JSONL output")
    p_factory.add_argument("--min-yield", type=float, default=60.0, help="Minimum composite profit yield (default: 60.0)")
    p_factory.add_argument("--min-jev", type=float, default=1.20, help="Minimum Jev durability score (default: 1.20)")
    p_factory.add_argument("--min-prob", type=float, default=0.50, help="Minimum durability probability (default: 0.50)")
    p_factory.add_argument("--output-dir", type=str, default=None, help="Optional directory to write compiled HTML assets")
    p_factory.add_argument("--dry-run", action="store_true", help="Dry run mode without writing compiled assets to disk")
    p_factory.add_argument("--json", action="store_true", help="Output result as JSON")

    # trend-monitor
    p_monitor = subparsers.add_parser("trend-monitor", help="Monitor live streaming suggest queries and report momentum rankings")
    p_monitor.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries to monitor")
    p_monitor.add_argument("--source", type=str, default=None, help="Optional feed source filter")
    p_monitor.add_argument("--once", action="store_true", default=True, help="Execute single monitor cycle")
    p_monitor.add_argument("--json", action="store_true", help="Output result as JSON")

    # trend-cron
    from pseofactory.trends.db import DEFAULT_DB_PATH
    p_cron = subparsers.add_parser("trend-cron", help="Execute autonomous daily cron loop trend monitoring and longitudinal analysis")
    p_cron.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help="Path to persistent SQLite trend history database file")
    p_cron.add_argument("--fixture", type=str, default=None, help="Path to JSON multi-source crawl fixture file for deterministic testing")
    p_cron.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries for live streaming collectors")
    p_cron.add_argument("--cycle-id", type=str, default=None, help="Explicit cycle identifier (default: auto-generated UTC timestamp/hash)")
    p_cron.add_argument("--min-yield", type=float, default=60.0, help="Minimum composite profit yield threshold for asset build/refactor")
    p_cron.add_argument("--property", type=str, default=None, help="Optional tenant filter (prexvo, profithelm, unassigned)")
    p_cron.add_argument("--include-unassigned", action="store_true", help="Also evaluate unassigned greenfield clusters when --property is set")
    p_cron.add_argument("--sink", type=str, default=None, help="Optional path for JSONL candidates sink (e.g. void_candidates.jsonl)")
    p_cron.add_argument("--json", action="store_true", help="Output machine-readable JSON cycle summary")
    p_cron.add_argument("--dry-run", action="store_true", help="Evaluate cycle without committing mutations to SQLite history")

    # market-intel
    p_mi = subparsers.add_parser(
        "market-intel",
        help="Evaluate buyer intent, organic ranking difficulty, and active commission offers for new tenant launches",
    )
    p_mi.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help="Path to persistent SQLite trend history database")
    p_mi.add_argument("--query", type=str, default=None, help="Evaluate a single search query across all 3 market-intelligence pillars")
    p_mi.add_argument("--top", type=int, default=None, help="Limit output to top N ranked tenant candidates")
    p_mi.add_argument("--sync-db", action="store_true", help="Persist ranked tenant candidates into market_intel_candidates table")
    p_mi.add_argument("--confirm-three-cycles", action="store_true", help="Run 3-cycle longitudinal confirmation for greenfield anchor tools in DB")
    p_mi.add_argument("--output", type=str, default=None, help="Optional JSON file path to write the market intelligence report")
    p_mi.add_argument("--json", action="store_true", help="Output machine-readable JSON market intelligence report")

    # trend-backfill
    p_backfill = subparsers.add_parser("trend-backfill", help="Execute historical session crawl and idempotent bulk insert into trend history DB")
    p_backfill.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help="Path to persistent SQLite trend history database file")
    p_backfill.add_argument("--staging-dir", type=str, default=".agy/scratch/backfill_staged", help="Path to intermediate staged buffer directory")
    p_backfill.add_argument("--dlq-path", type=str, default=".agy/runs/5017e890/staging_dlq.jsonl", help="Path to quarantine dead letter queue file")
    p_backfill.add_argument("--fixture", type=str, default=None, help="Optional JSON fixture file to include in backfill")
    p_backfill.add_argument("--limit-cycles", type=int, default=None, help="Optional ceiling on number of cycles to process")
    p_backfill.add_argument("--dry-run", action="store_true", help="Parse and validate without committing mutations to SQLite")
    p_backfill.add_argument("--json", action="store_true", help="Output machine-readable JSON backfill summary")

    # sync-monetization
    p_sync = subparsers.add_parser(
        "sync-monetization",
        help="Synchronize approved partner programs into local monetization vault",
    )
    p_sync.add_argument(
        "--network",
        type=str,
        default="partnerstack",
        help="Affiliate network identifier (e.g. partnerstack, impact, sovrn_commerce)",
    )
    p_sync.add_argument(
        "--payload",
        type=str,
        default=None,
        help="Path to JSON payload file or raw JSON payload string",
    )
    p_sync.add_argument(
        "--property",
        type=str,
        default="profithelm",
        help="Target property identifier (default: profithelm)",
    )
    p_sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate synchronization and print summary without writing to disk",
    )
    p_sync.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON synchronization report",
    )

    # distribute
    p_dist = subparsers.add_parser("distribute", help="Execute multi-channel syndication export and Voice DNA verification")
    p_dist.add_argument("--property", type=str, default="profithelm", help="Target property identifier (default: profithelm)")
    p_dist.add_argument("--dry-run", action="store_true", help="Dry-run simulation mode without live publishing")
    p_dist.add_argument("--json", action="store_true", help="Output machine-readable JSON distribution report")

    # partner-sync
    p_psync = subparsers.add_parser(
        "partner-sync",
        help="Automated correspondence check via himalaya CLI and personal inbox to update partner readiness",
    )
    p_psync.add_argument("--force", action="store_true", help="Bypass poll rate-limit interval to query mail server directly")
    p_psync.add_argument("--personal-fixture", type=str, default=None, help="Path to optional personal inbox fixture JSON")
    p_psync.add_argument("--json", action="store_true", help="Output result as JSON")

    # partner-status
    p_pstat = subparsers.add_parser(
        "partner-status",
        help="Display actionable affiliate application status, readiness scores, and action bus items",
    )
    p_pstat.add_argument("--property", type=str, default=None, help="Optional property filter (profithelm, prexvo, all)")
    p_pstat.add_argument("--html", type=str, default=None, help="Export minimal modern light interface to specified HTML path")
    p_pstat.add_argument("--force-poll", "--force", dest="force_poll", action="store_true", help="Bypass poll rate-limit interval to query mail server directly")
    p_pstat.add_argument("--json", action="store_true", help="Output result as JSON")

    # partner-action
    p_pact = subparsers.add_parser(
        "partner-action",
        help="Manage dedicated human action bus operator intervention and partner decisions",
    )
    p_pact.add_argument("action_command", choices=["list", "approve", "reject", "resolve"], help="Action operation")
    p_pact.add_argument("--action-id", type=str, default=None, help="Target action item identifier")
    p_pact.add_argument("--property", type=str, default=None, help="Optional property filter for listing")
    p_pact.add_argument("--notes", type=str, default="", help="Operator notes for decision audit log")
    p_pact.add_argument("--operator", type=str, default="operator", help="Operator name or identifier")
    p_pact.add_argument("--json", action="store_true", help="Output result as JSON")

    # partner-ui
    p_pui = subparsers.add_parser(
        "partner-ui",
        help="Start minimal modern light interface dashboard server for live partner tracking",
    )
    p_pui.add_argument("--port", type=int, default=8090, help="Server port (default: 8090)")
    p_pui.add_argument("--host", type=str, default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    p_pui.add_argument("--status", action="store_true", help="Inspect active runtime status of the partner UI daemon")
    p_pui.add_argument("--json", action="store_true", help="Output status report as JSON")

    # indexing-preflight
    p_preflight = subparsers.add_parser(
        "indexing-preflight",
        help="Execute automated indexing preflight inspection and crawl budget partition",
    )
    p_preflight.add_argument("--property", type=str, default=None, help="Property ID (e.g. profithelm, prexvo)")
    p_preflight.add_argument("--urls", nargs="*", default=None, help="Explicit URLs to inspect")
    p_preflight.add_argument("--sitemap", type=str, default=None, help="Path or URL to sitemap.xml")
    p_preflight.add_argument("--dist-dir", type=str, default=None, help="Explicit dist directory")
    p_preflight.add_argument("--fixture", type=str, default=None, help="Path to JSON fixture file")
    p_preflight.add_argument("--strict", action="store_true", help="Fail with exit code 1 if any blocked URLs exist")
    p_preflight.add_argument("--dry-run", action="store_true", help="Simulate inspection and exit 0 without blocking")
    p_preflight.add_argument("--format", type=str, choices=["json", "table"], default="table", help="Output format (json or table)")
    p_preflight.add_argument("--json", action="store_true", help="Alias for --format json")
    p_preflight.add_argument("--min-words", type=int, default=150, help="Minimum body word count threshold (default: 150)")
    p_preflight.add_argument("--tier1-cap", type=int, default=150, help="Maximum cap on Tier-1 Hub push URLs (default: 150)")

    # supervisor
    p_sup = subparsers.add_parser(
        "supervisor",
        help="Runs autonomous lifecycle supervisor babysitting fleet assets",
    )
    p_sup.add_argument("--interval", type=float, default=3600.0, help="Loop interval in seconds (default: 3600)")
    p_sup.add_argument("--daemon", action="store_true", help="Run supervisor continuously as a daemon")
    p_sup.add_argument("--run-once", action="store_true", help="Run single lifecycle cycle and exit")
    p_sup.add_argument("--property", type=str, default=None, help="Restrict supervisor to specific property ID")
    p_sup.add_argument("--force", action="store_true", help="Force rebuild and verification regardless of drift")
    p_sup.add_argument("--dry-run", action="store_true", help="Simulate cycle without writing disk assets or git commits")
    p_sup.add_argument("--json", action="store_true", help="Output summary in JSON format")
    p_sup.add_argument("--skip-ci", action="store_true", help="Skip CI/CD watcher gate during GitOps dispatch")
    p_sup.add_argument("--budget", type=float, default=float(os.environ.get("PSEUFACTORY_SUPERVISOR_TICK_BUDGET", "2400.0")), help="Execution budget in seconds (default: 2400)")

    # gsc-ceiling
    p_ceiling = subparsers.add_parser(
        "gsc-ceiling",
        help="Analyze 480-day Search Console trajectory and detect algorithmic glass ceilings",
    )
    p_ceiling.add_argument("--property", type=str, default="profithelm", choices=["profithelm", "prexvo"], help="Target property identifier")
    p_ceiling.add_argument("--days", type=int, default=480, help="Historical time series lookback days (default: 480)")
    p_ceiling.add_argument("--fixture", type=str, default=None, help="Path to JSON fixture file containing historical GSC records")
    p_ceiling.add_argument("--ceiling-threshold", type=float, default=0.35, help="Algorithmic ceiling dampening threshold (default: 0.35)")
    p_ceiling.add_argument("--updates", type=str, default=None, help="Path to optional Google update intervals JSON fixture")
    p_ceiling.add_argument("--json", action="store_true", help="Output analysis result as structured JSON")
    p_ceiling.add_argument("--html", type=str, default=None, help="Output file path to render standalone minimal modern light HTML report")

    # indexing-inspect
    p_inspect = subparsers.add_parser(
        "indexing-inspect",
        help="Execute daily indexing inspection auditing GSC rollover, quarantine, and velocity (Loop 3)",
    )
    p_inspect.add_argument("--property", "--tenant", dest="property", type=str, default="profithelm", help="Target property/tenant identifier")
    p_inspect.add_argument("--strict", action="store_true", help="Fail with non-zero exit code if anomalies or warnings detected")
    p_inspect.add_argument("--dry-run", action="store_true", help="Audit without updating recovery ledger on disk")
    p_inspect.add_argument("--sample", action="store_true", help="Audit sample partition")
    p_inspect.add_argument("--auto-remediate", action="store_true", help="Automatically trigger closed-loop remediation and dead sitemap pruning")
    p_inspect.add_argument("--prune-sitemaps", action="store_true", help="Audit and delete dead or unfetchable sitemaps from GSC and ledger")
    p_inspect.add_argument("--json", action="store_true", help="Output inspection results as structured JSON")

    # indexing-feedback-loop
    p_feedback = subparsers.add_parser(
        "indexing-feedback-loop",
        help="Execute autonomous closed-loop indexing feedback coordinator (Loop 4)",
    )
    p_feedback.add_argument("--property", "--tenant", dest="property", type=str, default="profithelm", help="Target property/tenant identifier (default: profithelm)")
    p_feedback.add_argument("--dry-run", action="store_true", help="Audit and diagnose without executing actual live pushes or asset recompiles")
    p_feedback.add_argument("--live", action="store_true", help="Execute live network push submissions and live GSC inspections")
    p_feedback.add_argument("--json", action="store_true", help="Output feedback cycle results as structured JSON")

    # reflect
    p_ref = subparsers.add_parser(
        "reflect",
        help="Reflect engine changes across all existing assets and recompile drifted assets",
    )
    p_ref.add_argument("--property", type=str, default=None, help="Property ID filter (e.g. profithelm, prexvo)")
    p_ref.add_argument("--force", action="store_true", help="Force recompilation regardless of drift")
    p_ref.add_argument("--verbose", action="store_true", help="Verbose log output")
    p_ref.add_argument("--json", action="store_true", help="Output summary as JSON")
    p_ref.add_argument("--no-gitops", action="store_true", help="Bypass automated gitops staging and verification")

    # seo-workflows
    p_seowf = subparsers.add_parser(
        "seo-workflows",
        help="Execute all 8 autonomous SEO growth workflows across historical and live Search Console telemetry",
    )
    p_seowf.add_argument("--property", "--tenant", dest="property", type=str, default="profithelm", help="Property ID (profithelm, prexvo, or all)")
    p_seowf.add_argument("--dry-run", action="store_true", help="Evaluate workflows without writing overlays or ledger updates")
    p_seowf.add_argument("--json", action="store_true", help="Output workflow report as structured JSON")

    # north-star
    p_ns = subparsers.add_parser(
        "north-star",
        help="Evaluate 30-day and 60-day North Star SEO, AI citation, and conversion targets",
    )
    p_ns.add_argument("--property", "--tenant", dest="property", type=str, default="profithelm", help="Property ID (profithelm, prexvo, or all)")
    p_ns.add_argument("--dry-run", action="store_true", help="Evaluate North Star targets without persisting scorecard JSON")
    p_ns.add_argument("--json", action="store_true", help="Output North Star scorecard as structured JSON")

    p_cr = subparsers.add_parser(
        "cohort-reflection",
        help="Execute closed-loop cohort reflection across title remediation, indexing push, citation restructure, and sponsor slot updates",
    )
    p_cr.add_argument("--property", "--tenant", dest="property", type=str, default="profithelm", help="Property ID (profithelm, prexvo, or all)")
    p_cr.add_argument("--dry-run", action="store_true", help="Evaluate cohort reflection without persisting ledger or propagating winning patterns")
    p_cr.add_argument("--json", action="store_true", help="Output cohort reflection report as structured JSON")

    return parser


def cmd_north_star(args: argparse.Namespace) -> int:
    """
    Evaluates 30-day and 60-day North Star targets for one or all properties.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.seo_growth_loops import evaluate_north_star_targets

    prop_arg = str(getattr(args, "property", "profithelm") or "profithelm").strip().lower()
    dry_run = bool(getattr(args, "dry_run", False))
    props = ["profithelm", "prexvo"] if prop_arg == "all" else [prop_arg]
    cards = {}
    for p_id in props:
        cards[p_id] = evaluate_north_star_targets(property_id=p_id, persist=not dry_run)
    out = cards[props[0]] if len(props) == 1 else {"status": "PASS", "properties": cards}
    if getattr(args, "json", False):
        print(json.dumps(out, indent=2))
    else:
        for p_id, sc in cards.items():
            p1 = sc.get("pillars", {}).get("1_search_impressions_and_ctr", {})
            p3 = sc.get("pillars", {}).get("3_ai_citations_and_entity_authority", {})
            print(
                f"[{sc.get('status', 'PASS')}] North Star ({p_id}): "
                f"30d_impr={p1.get('current_30d_impressions', 0)}/{p1.get('target_30d_impressions', 0)} | "
                f"30d_clicks={p1.get('current_30d_clicks', 0)}/{p1.get('target_30d_clicks', 0)} | "
                f"citation_ready={p3.get('citation_ready_briefs_coverage_pct', 0)}% | "
                f"kw_ratio_gate={p3.get('source_keyword_inflation_gate_status', 'PASS')}"
            )
    return 0


def cmd_cohort_reflection(args: argparse.Namespace) -> int:
    """
    Executes closed-loop cohort reflection and winning-pattern inventory propagation for one or all properties.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.seo_growth_loops import evaluate_closed_loop_cohort_reflection

    prop_arg = str(getattr(args, "property", "profithelm") or "profithelm").strip().lower()
    dry_run = bool(getattr(args, "dry_run", False))
    props = ["profithelm", "prexvo"] if prop_arg == "all" else [prop_arg]
    reports = {}
    for p_id in props:
        reports[p_id] = evaluate_closed_loop_cohort_reflection(
            property_id=p_id,
            propagate_winning_patterns=not dry_run,
            persist=not dry_run,
        )
    out = reports[props[0]] if len(props) == 1 else {"status": "PASS", "properties": reports}
    if getattr(args, "json", False):
        print(json.dumps(out, indent=2))
    else:
        for p_id, rep in reports.items():
            cohorts = rep.get("cohorts", {})
            c1 = cohorts.get("1_title_remediation", {})
            c3 = cohorts.get("3_citation_restructure", {})
            c4 = cohorts.get("4_sponsor_slot_update", {})
            prop_summary = rep.get("inventory_propagation", {})
            print(
                f"[{rep.get('status', 'PASS')}] Cohort Reflection ({p_id}): "
                f"title_verdict={c1.get('cohort_verdict', 'PASS')} | "
                f"citation_coverage={c3.get('autonomous_assertions_coverage_pct', 0)}% | "
                f"sponsor_clicks={c4.get('total_outbound_clicks', 0)} (${c4.get('total_estimated_revenue_yield_usd', 0)}) | "
                f"propagated={prop_summary.get('overlays_enriched_with_winning_patterns_count', 0)}"
            )
    return 0


def cmd_seo_workflows(args: argparse.Namespace) -> int:
    """
    Executes all 8 autonomous SEO growth workflows for one or all properties.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.seo_growth_loops import run_all_seo_growth_workflows

    prop_arg = str(getattr(args, "property", "profithelm") or "profithelm").strip().lower()
    dry_run = bool(getattr(args, "dry_run", False))
    props = ["profithelm", "prexvo"] if prop_arg == "all" else [prop_arg]
    reports = {}
    for p_id in props:
        reports[p_id] = run_all_seo_growth_workflows(
            property_id=p_id,
            apply_overlays=not dry_run,
            persist=not dry_run,
        )
    out = reports[props[0]] if len(props) == 1 else {"status": "PASS", "properties": reports}
    if getattr(args, "json", False):
        print(
            json.dumps(
                out,
                indent=2,
                default=lambda o: o.to_dict() if hasattr(o, "to_dict") else (o.__dict__ if hasattr(o, "__dict__") else str(o)),
            )
        )
    else:
        for p_id, rep in reports.items():
            wf = rep.get("workflows", {})
            print(
                f"[{rep.get('status', 'PASS')}] SEO Growth Workflows ({p_id}): "
                f"decay={wf.get('1_identify_content_decay', {}).get('decayed_pages_count', 0)} | "
                f"sprint={wf.get('2_technical_seo_sprint', {}).get('sprint_tickets_count', 0)} | "
                f"spikes={wf.get('3_competitor_traffic_spikes', {}).get('spikes_count', 0)} | "
                f"briefs={wf.get('4_search_opportunity_briefs', {}).get('briefs_count', 0)} | "
                f"links={wf.get('5_internal_linking_opportunities', {}).get('injection_recommendations_count', 0)} | "
                f"portfolio={wf.get('6_content_portfolio_decisions', {}).get('pages_audited', 0)} | "
                f"ai_pr={wf.get('7_ai_citation_digital_pr_queue', {}).get('queue_count', 0)} | "
                f"regressions={wf.get('8_post_release_seo_regressions', {}).get('regressions_count', 0)}"
            )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "cycle":
        return cmd_cycle(args)
    elif args.command == "supervisor":
        return cmd_supervisor(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command == "maintain":
        return cmd_maintain(args)
    elif args.command == "refactor":
        return cmd_refactor(args)
    elif args.command == "reflect":
        return cmd_reflect(args)
    elif args.command == "fleet-maintain":
        return cmd_fleet_maintain(args)
    elif args.command == "drift":
        return cmd_drift(args)
    elif args.command == "replay-dlq":
        return cmd_replay_dlq(args)
    elif args.command == "trend-intake":
        return cmd_trend_intake(args)
    elif args.command == "factory-run":
        return cmd_factory_pipeline(args)
    elif args.command == "trend-monitor":
        return cmd_trend_monitor(args)
    elif args.command == "trend-cron":
        return cmd_trend_cron(args)
    elif args.command == "market-intel":
        return cmd_market_intel(args)
    elif args.command == "trend-backfill":
        return cmd_trend_backfill(args)
    elif args.command == "sync-monetization":
        return cmd_sync_monetization(args)
    elif args.command == "distribute":
        return cmd_distribute(args)
    elif args.command == "partner-sync":
        return cmd_partner_sync(args)
    elif args.command == "partner-status":
        return cmd_partner_status(args)
    elif args.command == "partner-action":
        return cmd_partner_action(args)
    elif args.command == "partner-ui":
        return cmd_partner_ui(args)
    elif args.command == "indexing-preflight":
        return cmd_indexing_preflight(args)
    elif args.command == "gsc-ceiling":
        return cmd_gsc_ceiling(args)
    elif args.command == "indexing-inspect":
        return cmd_indexing_inspect(args)
    elif args.command == "indexing-feedback-loop":
        return cmd_indexing_feedback_loop(args)
    elif args.command == "seo-workflows":
        return cmd_seo_workflows(args)
    elif args.command == "north-star":
        return cmd_north_star(args)
    elif args.command == "cohort-reflection":
        return cmd_cohort_reflection(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())


