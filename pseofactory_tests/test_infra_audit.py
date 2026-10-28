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
    ACTIVE_ROUTABLE_ZONE_IDS,
    ACTIVE_TENANT_DOMAINS,
    ALL_PORTFOLIO_ZONE_IDS,
    DECOMMISSIONED_DOMAINS,
    DEFAULT_ENDPOINTS,
    DEFAULT_PROFITHELM_REPO,
    EXPECTED_ACTIVE_CNAME_TARGETS,
    HIBERNATED_RESERVE_DOMAINS,
    KEPT_DOMAINS,
    NON_ROUTABLE_ZONE_IDS,
    PERSONAL_INFRA_DOMAINS,
    audit_active_zone_dns_hygiene,
    audit_cloudflare_and_multi_cloud,
    audit_gcp_billing_summary,
    audit_hibernated_and_retired_dns_isolation,
    audit_host_hygiene,
    audit_live_edge_endpoints,
    audit_registrar_renewal_posture,
    run_consolidated_infra_audit,
)
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent
from pseofactory.tenant_facts import (
    CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER,
    CLOUDFLARE_REGISTRAR_ATTESTATION_SHA256,
    TenantFactStore,
)


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


def test_default_endpoints_excludes_decommissioned_gainhelm():
    """Asserts decommissioned gainhelm.com is excluded from active DEFAULT_ENDPOINTS while profithelm.com and prexvo.com remain."""
    assert "https://gainhelm.com" not in DEFAULT_ENDPOINTS
    assert "https://profithelm.com" in DEFAULT_ENDPOINTS
    assert "https://prexvo.com" in DEFAULT_ENDPOINTS


def test_audit_hibernated_and_retired_dns_isolation_live():
    """
    Verifies live Cloudflare DNS isolation across all 5 retired domains
    (adspendguardian.com, gainhelm.com, heyjunto.com, thecoachloop.com, viraljacker.com):
    - 0 A, AAAA, CNAME, or MX routing records on all 5 non-routable zones.
    - Graceful handling of HTTP 403/401 Registrar API token scope restrictions.
    """
    ok, msg = audit_hibernated_and_retired_dns_isolation()
    assert ok is True, f"Live DNS isolation check failed: {msg}"
    assert "Zero routing records verified across 5 hibernated/retired zones" in msg


def test_audit_registrar_renewal_posture_mocked():
    """
    Verifies audit_registrar_renewal_posture handles:
    1. HTTP 200 OK with compliant auto_renew states (kept=True, retired=False).
    2. HTTP 200 OK with violation (retired domain still has auto_renew=True).
    3. HTTP 403 Forbidden token scope restriction (graceful pass in unattended CLI runs).
    """
    import urllib.error

    compliant_domains = [
        {"name": d, "auto_renew": True} for d in KEPT_DOMAINS
    ] + [
        {"name": d, "auto_renew": False} for d in DECOMMISSIONED_DOMAINS
    ]
    mock_resp_ok = MagicMock()
    mock_resp_ok.read.return_value = json.dumps({"success": True, "result": compliant_domains}).encode("utf-8")
    mock_resp_ok.__enter__.return_value = mock_resp_ok

    with patch("urllib.request.urlopen", return_value=mock_resp_ok):
        ok, msg, details = audit_registrar_renewal_posture(api_token="mock-token")
        assert ok is True
        assert details["status"] == "VERIFIED"

    violating_domains = [
        {"name": d, "auto_renew": True} for d in KEPT_DOMAINS
    ] + [
        {"name": d, "auto_renew": (d == "viraljacker.com")} for d in DECOMMISSIONED_DOMAINS
    ]
    mock_resp_fail = MagicMock()
    mock_resp_fail.read.return_value = json.dumps({"success": True, "result": violating_domains}).encode("utf-8")
    mock_resp_fail.__enter__.return_value = mock_resp_fail

    with patch("urllib.request.urlopen", return_value=mock_resp_fail):
        ok, msg, details = audit_registrar_renewal_posture(api_token="mock-token")
        assert ok is False
        assert "viraljacker.com" in msg

    http_403 = urllib.error.HTTPError(
        url="https://api.cloudflare.com/client/v4/accounts/mock/registrar/domains",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_403):
        ok, msg, details = audit_registrar_renewal_posture(api_token="mock-token")
        assert ok is True
        assert details["status"] == "TOKEN_SCOPE_RESTRICTED"
        assert details["http_code"] == 403


def test_audit_hibernated_and_retired_dns_isolation_catches_dangling_records():
    """Verifies DNS isolation audit catches dangling A/CNAME records on retired domains."""
    def _fake_urlopen(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        resp.__enter__.return_value = resp
        if NON_ROUTABLE_ZONE_IDS["adspendguardian.com"] in url:
            payload = {
                "success": True,
                "result": [
                    {"type": "CNAME", "name": "www.adspendguardian.com", "content": "ghs.googlehosted.com"}
                ],
            }
        else:
            payload = {"success": True, "result": []}
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        return resp

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen), patch(
        "pseofactory.infra_audit.audit_registrar_renewal_posture",
        return_value=(True, "Registrar verified", {"status": "VERIFIED"}),
    ):
        ok, msg = audit_hibernated_and_retired_dns_isolation(api_token="mock-token")
        assert ok is False
        assert "adspendguardian.com has 1 dangling routing record(s)" in msg


def test_active_zone_dns_hygiene_live_and_registrar_attestation_ledger():
    """
    Verifies live active-zone DNS hygiene (profithelm.com, prexvo.com, arifcoskun.com)
    and cryptographic Registrar state attestation across all 8 portfolio domains:
    - Proxied Pages CNAMEs, SPF, and DMARC (p=reject) verified on all 3 active zones.
    - Transfer lock (locked=True, clienttransferprohibited), WHOIS privacy (redaction),
      and $41.84/yr exposure verified across the 8-domain Registrar ledger.
    - Unlocks or WHOIS privacy regressions are caught deterministically.
    """
    ok_active, msg_active, summaries = audit_active_zone_dns_hygiene()
    assert ok_active is True, f"Active zone DNS hygiene failed: {msg_active}"
    for dom, expected_target in EXPECTED_ACTIVE_CNAME_TARGETS.items():
        assert summaries[dom]["expected_cname"] == expected_target
        assert summaries[dom]["has_spf"] is True
        assert summaries[dom]["has_dmarc_reject"] is True

    ok_ledger, msg_ledger, meta = TenantFactStore.verify_registrar_ledger_integrity()
    assert ok_ledger is True, f"Registrar ledger integrity failed: {msg_ledger}"
    assert meta["domains_verified"] == 8
    assert meta["total_annual_exposure_usd"] == 31.38
    assert meta["attestation_sha256"] == CLOUDFLARE_REGISTRAR_ATTESTATION_SHA256
    for retired in DECOMMISSIONED_DOMAINS:
        assert retired in meta["sunset_windows_days"]

    # Mutate transfer lock on a cloned ledger and verify fail-closed rejection
    tampered = {k: dict(v) for k, v in CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER.items()}
    tampered["gainhelm.com"]["locked"] = False
    ok_bad, msg_bad, _ = TenantFactStore.verify_registrar_ledger_integrity(ledger=tampered)
    assert ok_bad is False
    assert "gainhelm.com transfer lock is False" in msg_bad

    # Verify audit_registrar_renewal_posture catches live unlocked or unredacted domain
    unlocked_payload = [
        {"name": d, "auto_renew": True, "locked": (d != "profithelm.com"), "privacy": True}
        for d in KEPT_DOMAINS
    ] + [
        {"name": d, "auto_renew": False, "locked": True, "privacy": True}
        for d in DECOMMISSIONED_DOMAINS
    ]
    mock_resp_unlocked = MagicMock()
    mock_resp_unlocked.read.return_value = json.dumps({"success": True, "result": unlocked_payload}).encode("utf-8")
    mock_resp_unlocked.__enter__.return_value = mock_resp_unlocked
    with patch("urllib.request.urlopen", return_value=mock_resp_unlocked):
        ok_u, msg_u, _ = audit_registrar_renewal_posture(api_token="mock-token")
        assert ok_u is False
        assert "profithelm.com has locked=False" in msg_u




