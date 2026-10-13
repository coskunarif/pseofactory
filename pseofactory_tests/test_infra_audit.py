"""
Test Suite: pseofactory Multi-Cloud Infrastructure & Host Hygiene Audit
Tests consolidated monitoring, HostHygieneAuditor integration, live edge curl probes,
and AtomicTelemetryLogger anomaly logging on failure.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pseofactory.infra_audit import (
    audit_cloudflare_and_multi_cloud,
    audit_gcp_billing_summary,
    audit_host_hygiene,
    audit_live_edge_endpoints,
    run_consolidated_infra_audit,
    DEFAULT_PROFITHELM_REPO,
)
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent


def test_audit_host_hygiene_live():
    """Asserts live profithelm-platform has zero host hygiene violations."""
    ok, msg = audit_host_hygiene(DEFAULT_PROFITHELM_REPO)
    assert ok is True
    assert "0 violations" in msg


def test_audit_host_hygiene_catches_violation(tmp_path):
    """Asserts audit_host_hygiene catches lethal wildcard noindex in mock repo."""
    mock_firebase = {
        "hosting": {
            "headers": [
                {
                    "source": "**",
                    "headers": [
                        {"key": "X-Robots-Tag", "value": "noindex, nofollow"}
                    ],
                }
            ]
        }
    }
    (tmp_path / "firebase.json").write_text(json.dumps(mock_firebase), encoding="utf-8")
    ok, msg = audit_host_hygiene(tmp_path)
    assert ok is False
    assert "lethal X-Robots-Tag directive" in msg


def test_audit_live_edge_endpoints_mocked():
    """Verifies live edge probe pass and fail branches with mocked subprocess."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="HTTP/2 200\nserver: cloudflare\n")
        ok, msg = audit_live_edge_endpoints(["https://profithelm.com", "https://prexvo.com"])
        assert ok is True
        assert "All 2 tenant endpoints verified" in msg

    with patch("subprocess.run") as mock_run_fail:
        mock_run_fail.return_value = MagicMock(returncode=22, stderr="404 Not Found")
        ok, msg = audit_live_edge_endpoints(["https://fail.domain.local"])
        assert ok is False
        assert "Failed endpoints" in msg


def test_consolidated_infra_audit_pass():
    """Verifies run_consolidated_infra_audit returns PASS when all components succeed."""
    with patch("pseofactory.infra_audit.audit_cloudflare_and_multi_cloud", return_value=(True, "Clean")), \
         patch("pseofactory.infra_audit.audit_gcp_billing_summary", return_value=(True, "Clean")), \
         patch("pseofactory.infra_audit.audit_host_hygiene", return_value=(True, "Clean")), \
         patch("pseofactory.infra_audit.audit_live_edge_endpoints", return_value=(True, "Clean")):
        res = run_consolidated_infra_audit()
        assert res["status"] == "PASS"
        assert res["violations_count"] == 0
        assert len(res["failures"]) == 0
        assert res["checks"]["cloud_audit"]["ok"] is True
        assert res["checks"]["gcp_billing"]["ok"] is True
        assert res["checks"]["host_hygiene"]["ok"] is True
        assert res["checks"]["live_edge"]["ok"] is True


def test_consolidated_infra_audit_failure_telemetry_emission(tmp_path):
    """
    Verifies that when a check fails, run_consolidated_infra_audit emits
    structured TelemetryEvent to AtomicTelemetryLogger disk log.
    """
    log_file = tmp_path / "telemetry_test.jsonl"
    logger = AtomicTelemetryLogger(log_path=log_file)

    with patch("pseofactory.infra_audit.audit_cloudflare_and_multi_cloud", return_value=(True, "Clean")), \
         patch("pseofactory.infra_audit.audit_gcp_billing_summary", return_value=(True, "Clean")), \
         patch("pseofactory.infra_audit.audit_host_hygiene", return_value=(False, "Lethal crawler barrier")), \
         patch("pseofactory.infra_audit.audit_live_edge_endpoints", return_value=(True, "Clean")):
        res = run_consolidated_infra_audit(telemetry_logger=logger)
        assert res["status"] == "FAIL"
        assert res["violations_count"] == 1
        assert "host_hygiene: Lethal crawler barrier" in res["failures"]

    events = logger.read_recent(limit=5)
    assert len(events) == 1
    assert events[0].event_type == "INFRA_AUDIT_FAILURE"
    assert events[0].error_type == "HostHygieneViolation"
    assert "Lethal crawler barrier" in events[0].error_message


def test_audit_infra_script_exists_and_executable():
    """Asserts bin/audit-infra.sh exists and has execute permissions."""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "bin" / "audit-infra.sh"
    assert script_path.exists(), f"Script missing at {script_path}"
    assert os.access(script_path, os.X_OK), f"Script not executable: {script_path}"
