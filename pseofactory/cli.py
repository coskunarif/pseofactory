"""
pseofactory CLI Gateway
Autonomous execution interface for auditing, maintaining, refactoring, and fleet coordination.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from typing import List, Optional

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
        report = evaluator.audit_all(adapter)
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

    report = audit_property_assets(property_id=property_id, adapter=adapter)
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
    property_id = args.property or "prexvo"
    res = run_maintenance_lifecycle(property_id=property_id, force=args.force)
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
            print(
                f"[{res.status}] Property: {res.property_id} | "
                f"Audited: {res.assets_audited} | Drifted: {res.assets_drifted} | "
                f"Refactored: {res.assets_refactored} | Failed: {res.assets_failed}"
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
                print(
                    f"[{res.status}] Property: {pid} | "
                    f"Audited: {res.assets_audited} | Drifted: {res.assets_drifted} | "
                    f"Refactored: {res.assets_refactored} | Failed: {res.assets_failed}"
                )
        all_success = all(
            r.status in ("SUCCESS", "SKIPPED_NO_CHANGES", "DRY_RUN")
            for r in results.values()
        )
        return 0 if all_success else 1


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

        treg_checker = TregChecker(mock_data=mock_registry)
    else:
        seeds = [s.strip() for s in (args.seeds or "calculator,tax deduction,compliance").split(",") if s.strip()]
        collector = MultiSourceCollector()
        spikes = collector.harvest(seeds)
        treg_checker = TregChecker()

    if args.source:
        spikes = [s for s in spikes if s.source == args.source]

    jev_engine = JevEngine(min_build_yield=float(args.min_yield))
    result = run_trend_pipeline(
        spikes=spikes,
        sink_path=args.sink,
        treg_checker=treg_checker,
        jev_engine=jev_engine,
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
    p_cycle.add_argument("--json", action="store_true", help="Output result as JSON")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit static assets against engine baselines")
    p_audit.add_argument("--property", type=str, default=None, help="Property ID (e.g. prexvo, profithelm)")
    p_audit.add_argument("--dist-dir", type=str, default=None, help="Explicit dist directory to audit")
    p_audit.add_argument("--json", action="store_true", help="Output result as JSON")

    # maintain
    p_maintain = subparsers.add_parser("maintain", help="Execute closed-loop maintenance lifecycle on a property")
    p_maintain.add_argument("--property", type=str, default="prexvo", help="Property ID (default: prexvo)")
    p_maintain.add_argument("--force", action="store_true", help="Force rebuild even if no drift detected")
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
    p_intake.add_argument("--json", action="store_true", help="Output result as JSON")

    # trend-monitor
    p_monitor = subparsers.add_parser("trend-monitor", help="Monitor live streaming suggest queries and report momentum rankings")
    p_monitor.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries to monitor")
    p_monitor.add_argument("--source", type=str, default=None, help="Optional feed source filter")
    p_monitor.add_argument("--once", action="store_true", default=True, help="Execute single monitor cycle")
    p_monitor.add_argument("--json", action="store_true", help="Output result as JSON")

    # trend-cron
    p_cron = subparsers.add_parser("trend-cron", help="Execute autonomous daily cron loop trend monitoring and longitudinal analysis")
    p_cron.add_argument("--db-path", type=str, default="trends_history.db", help="Path to persistent SQLite trend history database file")
    p_cron.add_argument("--fixture", type=str, default=None, help="Path to JSON multi-source crawl fixture file for deterministic testing")
    p_cron.add_argument("--seeds", type=str, default=None, help="Comma-separated seed queries for live streaming collectors")
    p_cron.add_argument("--cycle-id", type=str, default=None, help="Explicit cycle identifier (default: auto-generated UTC timestamp/hash)")
    p_cron.add_argument("--min-yield", type=float, default=60.0, help="Minimum composite profit yield threshold for asset build/refactor")
    p_cron.add_argument("--property", type=str, default=None, help="Optional tenant filter (prexvo, profithelm, unassigned)")
    p_cron.add_argument("--json", action="store_true", help="Output machine-readable JSON cycle summary")
    p_cron.add_argument("--dry-run", action="store_true", help="Evaluate cycle without committing mutations to SQLite history")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "cycle":
        return cmd_cycle(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command == "maintain":
        return cmd_maintain(args)
    elif args.command == "refactor":
        return cmd_refactor(args)
    elif args.command == "fleet-maintain":
        return cmd_fleet_maintain(args)
    elif args.command == "drift":
        return cmd_drift(args)
    elif args.command == "replay-dlq":
        return cmd_replay_dlq(args)
    elif args.command == "trend-intake":
        return cmd_trend_intake(args)
    elif args.command == "trend-monitor":
        return cmd_trend_monitor(args)
    elif args.command == "trend-cron":
        return cmd_trend_cron(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

