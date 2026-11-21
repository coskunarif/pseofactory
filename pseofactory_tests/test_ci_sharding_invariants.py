"""
Fail-closed invariants for hybrid CI splitting (host_estate + 4 portable shards)
and atomic multi-state-file drift latch recording.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pseofactory_tests.ci_shard_select import (
    estimate_nodeid_weight,
    parse_shard_spec,
    partition_nodeids_across_shards,
    select_shard_indices,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ci_shard_spec_parsing_fail_closed() -> None:
    assert parse_shard_spec("1/4") == (1, 4)
    assert parse_shard_spec("4/4") == (4, 4)
    for bad in ("", "0/4", "5/4", "1/0", "1/2/3", "abc/4", "1"):
        with pytest.raises(ValueError):
            parse_shard_spec(bad)


def test_ci_shard_partition_zero_drop_zero_dup_and_balanced_across_live_collection() -> None:
    """
    Collects every test item in pseofactory_tests/ in one deterministic pass and proves:
    1. host_estate and (not host_estate) form an exact disjoint partition of 100% of tests.
    2. Shards 1/4..4/4 of (not host_estate) have exact union == 100% of portable tests,
       zero drops, zero duplicates, non-empty shards, and balanced total weight.
    3. At least 75% of all collected tests execute on parallel portable ubuntu-latest shards.
    """
    probe = (
        "import json, pytest\n"
        "class _Collector:\n"
        "    def __init__(self):\n"
        "        self.rows = []\n"
        "    def pytest_collection_modifyitems(self, items):\n"
        "        for it in items:\n"
        "            self.rows.append((it.nodeid, it.get_closest_marker('host_estate') is not None))\n"
        "col = _Collector()\n"
        "rc = pytest.main(['pseofactory_tests/', '--collect-only', '-q', '-o', 'addopts='], plugins=[col])\n"
        "assert rc == 0, f'collect-only failed with rc={rc}'\n"
        "print('__SHARD_PROBE_JSON__' + json.dumps(col.rows))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    marker_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("__SHARD_PROBE_JSON__")]
    assert marker_lines, f"Missing probe output. stdout={proc.stdout[-400:]!r} stderr={proc.stderr[-400:]!r}"
    rows = json.loads(marker_lines[-1][len("__SHARD_PROBE_JSON__") :])

    all_nodeids = [r[0] for r in rows]
    assert len(all_nodeids) == len(set(all_nodeids)), "Duplicate test nodeids detected in collection"
    assert len(all_nodeids) >= 1000, f"Unexpectedly small collected suite: {len(all_nodeids)}"

    host_nodeids = [nid for nid, is_host in rows if is_host]
    portable_nodeids = [nid for nid, is_host in rows if not is_host]
    assert set(host_nodeids).isdisjoint(set(portable_nodeids))
    assert set(host_nodeids) | set(portable_nodeids) == set(all_nodeids)
    assert len(host_nodeids) >= 30, f"Expected host_estate tests >= 30, got {len(host_nodeids)}"
    portable_ratio = len(portable_nodeids) / len(all_nodeids)
    assert portable_ratio >= 0.75, f"Portable ratio too low ({portable_ratio:.2%}); keep host_estate tight"

    buckets = partition_nodeids_across_shards(portable_nodeids, shard_total=4)
    seen_indices: set[int] = set()
    shard_weights: list[float] = []
    for k in range(1, 5):
        idxs = buckets[k]
        assert len(idxs) > 0, f"Shard {k}/4 is empty"
        assert select_shard_indices(portable_nodeids, k, 4) == set(idxs)
        assert seen_indices.isdisjoint(idxs), f"Duplicate test index in shard {k}/4"
        seen_indices.update(idxs)
        shard_weights.append(sum(estimate_nodeid_weight(portable_nodeids[i]) for i in idxs))

    assert seen_indices == set(range(len(portable_nodeids))), "Dropped test indices detected across 4 shards"
    assert max(shard_weights) / min(shard_weights) <= 1.25, (
        f"Unbalanced shard weights across 4 shards: {shard_weights}"
    )

    # End-to-end check that conftest.py --ci-shard option actually slices collection cleanly
    sub_counts = []
    for k in range(1, 5):
        p_sub = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "pseofactory_tests/test_ci_sharding_invariants.py",
                "--collect-only",
                "-q",
                "-o",
                "addopts=",
                f"--ci-shard={k}/4",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # rc == 0 (tests collected) or rc == 5 (empty slice when file has <4 tests)
        assert p_sub.returncode in (0, 5), f"--ci-shard={k}/4 failed: {p_sub.stdout}\n{p_sub.stderr}"
        collected_lines = [
            ln for ln in p_sub.stdout.splitlines() if ln.startswith("pseofactory_tests/test_ci_sharding_invariants.py::")
        ]
        sub_counts.append(len(collected_lines))
    assert sum(sub_counts) == 3, f"Expected exact sum of 3 tests in this module, got {sub_counts}"


def test_cli_drift_record_also_state_file_atomic_single_verification(tmp_path: Path, monkeypatch) -> None:
    """
    Verifies cli drift --record --also-state-file writes both engine_hash.json files atomically
    while invoking verify_all_tenants_aligned_for_latch only ONCE, and fails closed without
    writing either file if tenant alignment fails.
    """
    import argparse
    import pseofactory.cli as cli_mod
    import pseofactory.drift as drift_mod

    primary = tmp_path / "ws" / ".agy" / "engine_hash.json"
    secondary = tmp_path / "proj" / ".agy" / "engine_hash.json"

    calls: list[dict] = []

    def _fake_verify_pass(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return True, []

    monkeypatch.setattr(drift_mod, "verify_all_tenants_aligned_for_latch", _fake_verify_pass)

    # 1. Verify passing run writes BOTH files after ONE verification pass
    res_ok = drift_mod.detect_engine_drift(
        state_file=primary,
        also_state_files=[secondary],
        auto_record=True,
        verify_tenants=True,
        workspace_root=tmp_path,
    )
    assert len(calls) == 1, f"Expected single tenant verification call, got {len(calls)}"
    assert not res_ok.get("latch_blocked")
    assert primary.is_file() and secondary.is_file()
    p_data = json.loads(primary.read_text(encoding="utf-8"))
    s_data = json.loads(secondary.read_text(encoding="utf-8"))
    assert p_data["engine_hash"] == res_ok["current_hash"]
    assert s_data["engine_hash"] == res_ok["current_hash"]

    # 2. Verify CLI parser accepts repeatable --also-state-file and routes to cmd_drift
    tertiary = tmp_path / "proj2" / ".agy" / "engine_hash.json"
    calls.clear()
    rc = cli_mod.cmd_drift(
        argparse.Namespace(
            state_file=str(primary),
            also_state_file=[str(secondary), str(tertiary)],
            record=True,
            allow_tenant_scoped_hash=True,
            strict_global_hash=False,
            json=True,
        )
    )
    assert rc == 0
    assert tertiary.is_file()
    assert json.loads(tertiary.read_text(encoding="utf-8"))["engine_hash"] == res_ok["current_hash"]

    # 3. Verify failing tenant alignment blocks latching BOTH state files (fail-closed)
    blocked_p = tmp_path / "blocked_ws" / ".agy" / "engine_hash.json"
    blocked_s = tmp_path / "blocked_proj" / ".agy" / "engine_hash.json"
    monkeypatch.setattr(
        drift_mod,
        "verify_all_tenants_aligned_for_latch",
        lambda *a, **kw: (False, ["profithelm: simulated drift"]),
    )
    res_bad = drift_mod.detect_engine_drift(
        state_file=blocked_p,
        also_state_files=[blocked_s],
        auto_record=True,
        verify_tenants=True,
        workspace_root=tmp_path,
    )
    assert res_bad.get("latch_blocked") is True
    assert res_bad["status"] == "TENANT_DRIFT_UNLATCHED"
    assert not blocked_p.exists()
    assert not blocked_s.exists()
