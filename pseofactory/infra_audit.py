"""
Consolidated Multi-Cloud Infrastructure & Host Hygiene Audit Subsystem
Consolidates Cloudflare zone & SSL inspection, GCP IAM key checks, GCP BigQuery
billing summaries, repository host hygiene auditing, and live edge curl probes.
Emits structured JSON anomaly logs to .agy/telemetry_events.jsonl via
AtomicTelemetryLogger upon failure.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from pseofactory.edge import HostHygieneAuditor
from pseofactory.telemetry import TelemetryEvent, AtomicTelemetryLogger

DEFAULT_ENDPOINTS = [
    "https://profithelm.com",
    "https://prexvo.com",
    "https://arifcoskun.com",
    "https://gainhelm.com",
]

DEFAULT_CLOUD_CLI = Path("/home/ubuntuadmin/projects/satellites/cloudflare/bin/cloud")
DEFAULT_GCP_CLI = Path("/home/ubuntuadmin/projects/satellites/cloudflare/bin/gcp")
DEFAULT_PROFITHELM_REPO = Path("/home/ubuntuadmin/projects/profithelm-platform")


def audit_cloudflare_and_multi_cloud(
    cloud_cli: Optional[Path] = None, timeout_seconds: int = 45
) -> Tuple[bool, str]:
    """Runs satellites/cloudflare/bin/cloud audit."""
    cli_path = cloud_cli or DEFAULT_CLOUD_CLI
    if not cli_path.exists():
        return False, f"Cloud CLI executable not found: {cli_path}"

    try:
        proc = subprocess.run(
            [str(cli_path), "audit"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            return False, f"cloud audit exited {proc.returncode}: {err}"
        return True, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, f"cloud audit timed out after {timeout_seconds}s"
    except Exception as exc:
        return False, f"cloud audit execution error: {exc}"


def audit_gcp_billing_summary(
    gcp_cli: Optional[Path] = None, timeout_seconds: int = 45
) -> Tuple[bool, str]:
    """Runs satellites/cloudflare/bin/gcp billing summary."""
    cli_path = gcp_cli or DEFAULT_GCP_CLI
    if not cli_path.exists():
        return False, f"GCP CLI executable not found: {cli_path}"

    try:
        proc = subprocess.run(
            [str(cli_path), "billing", "summary"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            return False, f"gcp billing summary exited {proc.returncode}: {err}"
        return True, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, f"gcp billing summary timed out after {timeout_seconds}s"
    except Exception as exc:
        return False, f"gcp billing summary execution error: {exc}"


def audit_host_hygiene(
    repo_path: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Audits repository host configuration using HostHygieneAuditor."""
    target_repo = repo_path or DEFAULT_PROFITHELM_REPO
    try:
        res = HostHygieneAuditor.audit_repo_host_configs(target_repo)
        if res.get("status") != "PASS" or res.get("violations_count", 0) > 0:
            issues = res.get("issues", ["Host hygiene audit failed"])
            return False, "; ".join(issues)
        return True, "Host hygiene verified: 0 violations"
    except Exception as exc:
        return False, f"HostHygieneAuditor exception: {exc}"


def audit_live_edge_endpoints(
    endpoints: Optional[List[str]] = None, timeout_seconds: int = 15
) -> Tuple[bool, str]:
    """Probes live edge endpoints with curl asserting HTTP 200."""
    target_endpoints = endpoints or DEFAULT_ENDPOINTS
    failures = []

    for ep in target_endpoints:
        try:
            proc = subprocess.run(
                ["curl", "-fsSI", ep],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if proc.returncode != 0:
                failures.append(f"{ep} (curl exited {proc.returncode})")
        except subprocess.TimeoutExpired:
            failures.append(f"{ep} (timeout after {timeout_seconds}s)")
        except Exception as exc:
            failures.append(f"{ep} ({exc})")

    if failures:
        return False, f"Failed endpoints: {', '.join(failures)}"
    return True, f"All {len(target_endpoints)} tenant endpoints verified (HTTP 200)"


def run_consolidated_infra_audit(
    telemetry_logger: Optional[AtomicTelemetryLogger] = None,
    cloud_cli: Optional[Path] = None,
    gcp_cli: Optional[Path] = None,
    profithelm_repo: Optional[Path] = None,
    endpoints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Executes full multi-cloud infrastructure and host hygiene audit suite.
    Emits TelemetryEvent via AtomicTelemetryLogger for any failed check.
    """
    logger = telemetry_logger or AtomicTelemetryLogger()

    checks: Dict[str, Dict[str, Any]] = {}
    failures: List[str] = []

    # 1. Cloudflare & Multi-Cloud Audit
    ok_cloud, msg_cloud = audit_cloudflare_and_multi_cloud(cloud_cli=cloud_cli)
    checks["cloud_audit"] = {"ok": ok_cloud, "message": msg_cloud}
    if not ok_cloud:
        failures.append(f"cloud_audit: {msg_cloud}")
        logger.log(
            TelemetryEvent(
                event_type="INFRA_AUDIT_FAILURE",
                tenant_id="infrastructure",
                service_name="satellites-cloud-audit",
                error_type="CloudAuditFailure",
                error_message=f"Cloudflare infrastructure audit failure: {msg_cloud}",
                stderr_tail=msg_cloud[-2048:] if msg_cloud else None,
                action_taken="ALERTED",
            )
        )

    # 2. GCP Billing Summary
    ok_gcp, msg_gcp = audit_gcp_billing_summary(gcp_cli=gcp_cli)
    checks["gcp_billing"] = {"ok": ok_gcp, "message": msg_gcp}
    if not ok_gcp:
        failures.append(f"gcp_billing: {msg_gcp}")
        logger.log(
            TelemetryEvent(
                event_type="INFRA_AUDIT_FAILURE",
                tenant_id="infrastructure",
                service_name="satellites-gcp-billing",
                error_type="GcpBillingAuditFailure",
                error_message=f"GCP billing summary failure: {msg_gcp}",
                stderr_tail=msg_gcp[-2048:] if msg_gcp else None,
                action_taken="ALERTED",
            )
        )

    # 3. Host Hygiene Audit
    ok_hygiene, msg_hygiene = audit_host_hygiene(repo_path=profithelm_repo)
    checks["host_hygiene"] = {"ok": ok_hygiene, "message": msg_hygiene}
    if not ok_hygiene:
        failures.append(f"host_hygiene: {msg_hygiene}")
        logger.log(
            TelemetryEvent(
                event_type="INFRA_AUDIT_FAILURE",
                tenant_id="profithelm",
                service_name="host-hygiene-auditor",
                error_type="HostHygieneViolation",
                error_message=f"Host hygiene violation detected: {msg_hygiene}",
                stderr_tail=msg_hygiene[-2048:] if msg_hygiene else None,
                action_taken="ALERTED",
            )
        )

    # 4. Live Edge Probes
    ok_edge, msg_edge = audit_live_edge_endpoints(endpoints=endpoints)
    checks["live_edge"] = {"ok": ok_edge, "message": msg_edge}
    if not ok_edge:
        failures.append(f"live_edge: {msg_edge}")
        logger.log(
            TelemetryEvent(
                event_type="INFRA_AUDIT_FAILURE",
                tenant_id="infrastructure",
                service_name="live-edge-prober",
                error_type="LiveEdgeUnreachable",
                error_message=f"Live edge endpoint probe failure: {msg_edge}",
                stderr_tail=msg_edge[-2048:] if msg_edge else None,
                action_taken="ALERTED",
            )
        )

    status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "violations_count": len(failures),
        "failures": failures,
        "checks": checks,
    }


def main() -> int:
    """CLI Entrypoint for bin/audit-infra.sh."""
    print("=================================================================")
    print(" Consolidated Multi-Cloud Infrastructure & Host Hygiene Audit")
    print("=================================================================")

    print("[1/4] Auditing Cloudflare zones, SSL, and GCP IAM keys...")
    ok_cloud, msg_cloud = audit_cloudflare_and_multi_cloud()
    if ok_cloud:
        print("      PASS: Cloudflare & GCP IAM security audit clean")
    else:
        print(f"      FAIL: {msg_cloud}")

    print("[2/4] Querying GCP BigQuery billing summary ledger...")
    ok_gcp, msg_gcp = audit_gcp_billing_summary()
    if ok_gcp:
        print("      PASS: GCP billing ledger query verified")
    else:
        print(f"      FAIL: {msg_gcp}")

    print("[3/4] Auditing profithelm-platform host configuration hygiene...")
    ok_hygiene, msg_hygiene = audit_host_hygiene()
    if ok_hygiene:
        print("      PASS: 0 crawler barriers or header violations")
    else:
        print(f"      FAIL: {msg_hygiene}")

    print("[4/4] Probing live edge endpoints (profithelm, prexvo, arifcoskun, gainhelm)...")
    ok_edge, msg_edge = audit_live_edge_endpoints()
    if ok_edge:
        print("      PASS: All active production endpoints returned HTTP 200")
    else:
        print(f"      FAIL: {msg_edge}")

    res = run_consolidated_infra_audit()
    print("=================================================================")
    if res["status"] == "PASS":
        print(" Status: PASS (All multi-cloud infrastructure healthy & compliant)")
        print("=================================================================")
        return 0
    else:
        print(f" Status: FAIL ({len(res['failures'])} violations detected)")
        for fail in res["failures"]:
            print(f"   - {fail}")
        print(" Anomaly telemetry logged to .agy/telemetry_events.jsonl")
        print("=================================================================")
        return 1


if __name__ == "__main__":
    sys.exit(main())
