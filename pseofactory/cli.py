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
        dashboard = engine.sync_and_evaluate(force_mail_poll=False)

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
        for p in ports_to_probe:
            try:
                req = urllib.request.Request(f"http://{host}:{p}/api/status", headers={"User-Agent": "pseofactory-cli"})
                with urllib.request.urlopen(req, timeout=3) as resp:
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

    # trend-backfill
    p_backfill = subparsers.add_parser("trend-backfill", help="Execute historical session crawl and idempotent bulk insert into trend history DB")
    p_backfill.add_argument("--db-path", type=str, default="pseofactory/trends/data/trend_history.db", help="Path to persistent SQLite trend history database file")
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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

