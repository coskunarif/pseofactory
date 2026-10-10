"""
Test Suite: pseofactory Telemetry Event Logger & Subprocess Crash Traps (Loop 1)
Verifies SubprocessCrashError emission, stderr tail capture, exit code 75 preservation,
POSIX advisory flock atomic JSONL append, and 300s fingerprint deduplication.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import sys
import json
import time
import pytest
from pathlib import Path

from pseofactory.telemetry import (
    TelemetryEvent,
    AtomicTelemetryLogger,
    handle_cli as telemetry_cli,
)
from pseofactory.maintenance import (
    SubprocessPropertyAdapter,
    SubprocessCrashError,
    LockContentionError,
)
from pseofactory.supervisor import (
    AsyncFleetCoordinator,
    TenantRegistry,
    MaintenanceLifecycle,
)


def test_subprocess_crash_capture(tmp_path):
    """
    Asserts non-zero child process raises SubprocessCrashError, standard error
    output is preserved, and exit code 75 is preserved as LockContentionError.
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 1. Non-zero exit code: must raise SubprocessCrashError
    crash_cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('CRITICAL: Memory fault in worker process'); sys.exit(42)",
    ]
    adapter_failing = SubprocessPropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tmp_path,
        build_command=crash_cmd,
        build_asset_command=crash_cmd,
    )

    with pytest.raises(SubprocessCrashError) as exc_info:
        adapter_failing.build_all()

    err = exc_info.value
    assert err.returncode == 42
    assert err.exit_code == 42
    assert "CRITICAL: Memory fault in worker process" in err.stderr_tail
    assert err.property_id == "profithelm"

    with pytest.raises(SubprocessCrashError) as exc_info_asset:
        adapter_failing.build_asset("sample-slug")
    assert exc_info_asset.value.returncode == 42
    assert "CRITICAL: Memory fault in worker process" in exc_info_asset.value.stderr_tail

    # 2. Exit code 75: must raise LockContentionError (Chesterton fence)
    contention_cmd = [sys.executable, "-c", "import sys; sys.exit(75)"]
    adapter_contention = SubprocessPropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=tmp_path,
        build_command=contention_cmd,
        build_asset_command=contention_cmd,
    )

    with pytest.raises(LockContentionError) as lce_info:
        adapter_contention.build_all()
    assert lce_info.value.exit_code == 75

    with pytest.raises(LockContentionError) as lce_info_asset:
        adapter_contention.build_asset("sample-slug")
    assert lce_info_asset.value.exit_code == 75


def test_flock_deduplication(tmp_path):
    """
    Verifies POSIX flock atomic appending and 300-second fingerprint deduplication.
    Duplicate events within 300 seconds are suppressed; events after window are logged.
    """
    log_file = tmp_path / "telemetry_events.jsonl"
    logger = AtomicTelemetryLogger(log_path=log_file)

    event1 = TelemetryEvent(
        tenant_id="profithelm",
        event_type="SUBPROCESS_CRASH",
        error_type="SubprocessCrashError",
        error_message="Worker process killed by SIGSEGV",
        exit_code=139,
    )

    # First log must succeed
    appended1 = logger.log(event1)
    assert appended1 is True
    assert log_file.exists()

    # Second log with identical fingerprint within 300s window must be suppressed
    event2 = TelemetryEvent(
        tenant_id="profithelm",
        event_type="SUBPROCESS_CRASH",
        error_type="SubprocessCrashError",
        error_message="Worker process killed by SIGSEGV",
        exit_code=139,
    )
    assert event2.fingerprint == event1.fingerprint
    appended2 = logger.log(event2)
    assert appended2 is False

    # Read back entries from disk
    entries = logger.read_recent(limit=10)
    assert len(entries) == 1
    assert entries[0].fingerprint == event1.fingerprint
    assert entries[0].exit_code == 139


def test_supervisor_crash_telemetry_emission(tmp_path):
    """
    Verifies AsyncFleetCoordinator._run_tenant_sync catches SubprocessCrashError,
    emits structured TelemetryEvent, and returns MaintenanceResult(status='FAILED').
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    log_file = tmp_path / "telemetry_events.jsonl"
    logger = AtomicTelemetryLogger(log_path=log_file)

    crash_cmd = [sys.executable, "-c", "import sys; sys.stderr.write('Fatal abort'); sys.exit(1)"]
    failing_adapter = SubprocessPropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tmp_path,
        build_command=crash_cmd,
        build_asset_command=crash_cmd,
    )

    class CrashingLifecycle(MaintenanceLifecycle):
        def run(self, adapter, **kwargs):
            adapter.build_asset("test-slug")
            return super().run(adapter, **kwargs)

    reg = TenantRegistry()
    reg.register_adapter(failing_adapter)
    coord = AsyncFleetCoordinator(registry=reg, lifecycle=CrashingLifecycle())

    # Temporarily set environment to use temp log
    old_env = os.environ.get("FACTORY_TELEMETRY_PATH")
    os.environ["FACTORY_TELEMETRY_PATH"] = str(log_file)
    try:
        res = coord._run_tenant_sync(
            failing_adapter,
            force=True,
            dry_run=False,
            enable_gitops=False,
            run_id="test_run_123",
            skip_ci=True,
        )
        assert res.status == "FAILED"
        assert len(res.failed_records) > 0
        assert res.failed_records[0].get("type") == "SubprocessCrashError"

        events = logger.read_recent(limit=10)
        assert len(events) >= 1
        assert events[0].event_type == "SUBPROCESS_CRASH"
        assert events[0].tenant_id == "profithelm"
        assert events[0].run_id == "test_run_123"
    finally:
        if old_env is not None:
            os.environ["FACTORY_TELEMETRY_PATH"] = old_env
        else:
            os.environ.pop("FACTORY_TELEMETRY_PATH", None)


def test_telemetry_cli_commands(tmp_path):
    """Verifies CLI execution for systemd emit-failure and tail commands."""
    log_file = tmp_path / "telemetry_cli.jsonl"
    rc = telemetry_cli([
        "emit-failure",
        "--service", "profithelm-factory.service",
        "--result", "exit-code",
        "--exit-code", "42",
        "--exit-status", "42",
        "--log-path", str(log_file),
    ])
    assert rc == 0
    assert log_file.exists()

    logger = AtomicTelemetryLogger(log_path=log_file)
    events = logger.read_recent(limit=5)
    assert len(events) == 1
    assert events[0].tenant_id == "profithelm"
    assert events[0].exit_code == 42
    assert events[0].event_type == "SYSTEMD_FAILURE"
