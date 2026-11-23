"""
Tests for sync_tenant_test_isolation_guards Prexvo pending/declined partner status sync.
Proves both legacy (pre-overhaul) and current (post-847424d) prexvo/freshness.py and
tests/test_affiliate_routes.py transform cleanly, idempotently, and pass prexvo's real
affiliate route test suite in an isolated temporary copy.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.gitops import sync_tenant_test_isolation_guards


_LEGACY_FRESHNESS_PY = '''"""Sample legacy prexvo/freshness.py."""
from typing import Dict

PREXVO_EXTENDED_PARTNERS: Dict[str, Dict[str, str]] = {
    "sofi_refi": {
        "default_url": "https://www.sofi.com/refinance-student-loan/",
        "env_var": "AFFILIATE_SOFI_URL",
        "status_env_var": "AFFILIATE_SOFI_STATUS",
        "status": "live",
    },
    "laurel_road": {
        "default_url": "https://www.laurelroad.com/student-loan-refinancing/",
        "env_var": "AFFILIATE_LAUREL_ROAD_URL",
        "status_env_var": "AFFILIATE_LAUREL_ROAD_STATUS",
        "status": "live",
    },
    "juno": {
        "default_url": "https://joinjuno.com/student-loan-refinancing",
        "env_var": "AFFILIATE_JUNO_URL",
        "status_env_var": "AFFILIATE_JUNO_STATUS",
        "status": "live",
    },
}


def audit_affiliate_routes():
    """
    2. Operational statuses are either pending_p2 or live.
    """
    suppressed_partners = 0
    for status in ("pending", "pending_p2", "declined"):
        if status == "live":
            pass
        elif status == "pending_p2":
            suppressed_partners += 1
    return suppressed_partners
'''

_CURRENT_BROKEN_FRESHNESS_PY = _LEGACY_FRESHNESS_PY.replace(
    '        elif status == "pending_p2":\n            suppressed_partners += 1',
    '        elif status in ("pending_p2", "declined"):\n            suppressed_partners += 1',
)

_LEGACY_TEST_AFFILIATE_ROUTES_PY = '''"""Sample legacy prexvo tests/test_affiliate_routes.py."""


def test_audit_affiliate_routes_contract():
    assert report["total_partners"] == 5
    assert report["live_partners"] == 5
    assert report["suppressed_partners"] == 0


def test_cli_verify_affiliates_subprocess():
    assert data["total_partners"] == 5
    assert data["live_partners"] == 5
    assert data["suppressed_partners"] == 0


def test_clean_slot_suppression_invariant():
    # Default CTA and matrix are live and route via /r/
    cta_html = build_refinance_partner_cta()
    assert "/r/splash_financial" in cta_html
    assert 'rel="noopener sponsored nofollow"' in cta_html

    matrix_html = build_partners_matrix_section()
    assert "partner-matrix-grid" in matrix_html
    for p_key in PREXVO_AFFILIATES.keys():
        assert f'/r/{p_key}' in matrix_html


def test_safe_edge_fallback_invariant():
    for p_key in list(PREXVO_AFFILIATES.keys()) + ["sofi_refi", "laurel_road", "juno"]:
        edge_res = simulate_edge_redirect(p_key)
        assert edge_res["status"] == 302
        assert edge_res["location"] != EDUCATIONAL_CALCULATOR_URL
        assert "prexvo.com" not in edge_res["location"].split("?")[0]
        assert "ref=prexvo" in edge_res["location"]
        assert edge_res["has_tracking"] is True
        assert "noindex, nofollow" in edge_res["headers"]["X-Robots-Tag"]
        assert "no-cache" in edge_res["headers"]["Cache-Control"]
'''

_CURRENT_BROKEN_TEST_AFFILIATE_ROUTES_PY = '''"""Sample current broken prexvo tests/test_affiliate_routes.py."""


def test_audit_affiliate_routes_contract():
    expected_live = sum(1 for p in PREXVO_AFFILIATES.values() if p.status in ("live", "pending"))
    expected_suppressed = sum(1 for p in PREXVO_AFFILIATES.values() if p.status in ("pending_p2", "declined"))
    assert report["total_partners"] == len(PREXVO_AFFILIATES)
    assert report["live_partners"] == expected_live
    assert report["suppressed_partners"] == expected_suppressed


def test_cli_verify_affiliates_subprocess():
    expected_live = sum(1 for p in PREXVO_AFFILIATES.values() if p.status in ("live", "pending"))
    expected_suppressed = sum(1 for p in PREXVO_AFFILIATES.values() if p.status in ("pending_p2", "declined"))
    assert data["total_partners"] == len(PREXVO_AFFILIATES)
    assert data["live_partners"] == expected_live
    assert data["suppressed_partners"] == expected_suppressed


def test_clean_slot_suppression_invariant():
    # Default CTA and matrix are live and route via /r/
    cta_html = build_refinance_partner_cta()
    assert "/r/splash_financial" in cta_html
    assert 'rel="noopener sponsored nofollow"' in cta_html

    matrix_html = build_partners_matrix_section()
    assert "partner-matrix-grid" in matrix_html
    for p_key, p_obj in PREXVO_AFFILIATES.items():
        if p_obj.status in ("live", "pending"):
            assert f'/r/{p_key}' in matrix_html
        else:
            assert f'/r/{p_key}' not in matrix_html


def test_safe_edge_fallback_invariant():
    active_keys = [k for k, v in PREXVO_AFFILIATES.items() if v.status in ("live", "pending")]
    suppressed_keys = [k for k, v in PREXVO_AFFILIATES.items() if v.status in ("pending_p2", "declined")]
    for p_key in active_keys + ["sofi_refi", "laurel_road", "juno"]:
        edge_res = simulate_edge_redirect(p_key)
        assert edge_res["status"] == 302
        assert edge_res["location"] != EDUCATIONAL_CALCULATOR_URL
        assert "prexvo.com" not in edge_res["location"].split("?")[0]
        assert "ref=prexvo" in edge_res["location"]
        assert edge_res["has_tracking"] is True
        assert "noindex, nofollow" in edge_res["headers"]["X-Robots-Tag"]
        assert "no-cache" in edge_res["headers"]["Cache-Control"]
    for p_key in suppressed_keys:
        edge_res = simulate_edge_redirect(p_key)
        assert edge_res["status"] == 302
        assert edge_res["location"] == EDUCATIONAL_CALCULATOR_URL
        assert edge_res["has_tracking"] is False
'''


@pytest.mark.parametrize(
    "label,freshness_src,test_src",
    [
        ("legacy", _LEGACY_FRESHNESS_PY, _LEGACY_TEST_AFFILIATE_ROUTES_PY),
        ("current_broken", _CURRENT_BROKEN_FRESHNESS_PY, _CURRENT_BROKEN_TEST_AFFILIATE_ROUTES_PY),
    ],
)
def test_sync_tenant_test_isolation_guards_transforms_prexvo_pending_contracts(
    tmp_path: Path, label: str, freshness_src: str, test_src: str
) -> None:
    """Verifies both legacy and post-847424d Prexvo files transform cleanly and idempotently."""
    fake_repo = tmp_path / f"prexvo_{label}"
    (fake_repo / "prexvo").mkdir(parents=True)
    (fake_repo / "tests").mkdir(parents=True)
    freshness_file = fake_repo / "prexvo" / "freshness.py"
    test_file = fake_repo / "tests" / "test_affiliate_routes.py"
    freshness_file.write_text(freshness_src, encoding="utf-8")
    test_file.write_text(test_src, encoding="utf-8")

    first = sync_tenant_test_isolation_guards(fake_repo)
    assert first["status"] == "PASS"
    assert first["updated_files"] == 2

    synced_fresh = freshness_file.read_text(encoding="utf-8")
    assert 'elif status in ("pending", "pending_p2", "declined"):' in synced_fresh
    assert "live, pending, pending_p2, or declined." in synced_fresh
    assert '"sofi_refi": {' in synced_fresh and '"status": "declined"' in synced_fresh
    assert '"laurel_road": {' in synced_fresh and '"status": "pending"' in synced_fresh
    assert '"juno": {' in synced_fresh and '"status": "pending"' in synced_fresh
    assert '"status": "live"' not in synced_fresh
    assert_no_forbidden_dashes(synced_fresh, f"synced_freshness_{label}")

    synced_test = test_file.read_text(encoding="utf-8")
    assert 'if p.status == "live"' in synced_test
    assert 'if p.status in ("pending", "pending_p2", "declined")' in synced_test
    assert 'if p.status in ("live", "pending")' not in synced_test
    assert 'assert "withheld" in cta_html.lower()' in synced_test
    assert 'assert "withheld" in matrix_html.lower()' in synced_test
    assert 'live_fixture = {**PREXVO_AFFILIATES["splash_financial"].to_dict(), "status": "live"}' in synced_test
    assert 'for p_key in suppressed_keys + ["sofi_refi", "laurel_road", "juno"]:' in synced_test
    assert 'simulate_edge_redirect(p_key, env={env_var: "live"})' in synced_test
    assert_no_forbidden_dashes(synced_test, f"synced_test_affiliate_routes_{label}")

    # Second run must be strictly idempotent (zero changes)
    second = sync_tenant_test_isolation_guards(fake_repo)
    assert second["updated_files"] == 0
    assert freshness_file.read_text(encoding="utf-8") == synced_fresh
    assert test_file.read_text(encoding="utf-8") == synced_test


def test_synced_temp_copy_of_prexvo_passes_affiliate_routes_suite(tmp_path: Path) -> None:
    """Copies prexvo to tmp_path, applies sync_tenant_test_isolation_guards, and runs pytest."""
    src_prexvo = Path("/home/ubuntuadmin/projects/prexvo")
    if not (src_prexvo / "prexvo" / "freshness.py").is_file():
        pytest.skip("Host prexvo repo not present")

    tmp_px = tmp_path / "prexvo"
    shutil.copytree(
        src_prexvo,
        tmp_px,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "dist"),
    )
    sync_res = sync_tenant_test_isolation_guards(tmp_px)
    assert sync_res["status"] == "PASS"

    repo_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{tmp_px}:{repo_root}"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_affiliate_routes.py", "-q"],
        cwd=str(tmp_px),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"Synced prexvo affiliate tests failed:\n{proc.stdout}\n{proc.stderr}"
