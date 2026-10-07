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


def build_parser() -> argparse.ArgumentParser:
    """Builds argument parser for pseofactory CLI commands."""
    parser = argparse.ArgumentParser(
        prog="pseofactory",
        description="Unified Programmatic SEO Substrate for Prexvo and ProfitHelm Software Factories",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

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

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "audit":
        return cmd_audit(args)
    elif args.command == "maintain":
        return cmd_maintain(args)
    elif args.command == "refactor":
        return cmd_refactor(args)
    elif args.command == "fleet-maintain":
        return cmd_fleet_maintain(args)
    elif args.command == "drift":
        return cmd_drift(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
