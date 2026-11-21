"""
Pytest configuration for pseofactory test suite.
Ensures current worktree codebase takes precedence over editable parent installations.
Zero em-dashes. Zero en-dashes.
"""

import sys
from pathlib import Path
import pytest

worktree_root = Path(__file__).resolve().parent.parent

# Filter out parent repo paths and editable hooks to ensure worktree isolation
sys.path = [
    p for p in sys.path
    if "projects/pseofactory" not in p and "__editable__.pseofactory" not in p
]
sys.path_hooks = [h for h in sys.path_hooks if "pseofactory" not in str(h)]
sys.path_importer_cache.clear()

if str(worktree_root) not in sys.path:
    sys.path.insert(0, str(worktree_root))


def pytest_addoption(parser):
    parser.addoption(
        "--ci-shard",
        action="store",
        default=None,
        help="Deterministic balanced CI shard selector in 'K/N' format (1-indexed, e.g. '1/4').",
    )


_HOST_ESTATE_LPT_PRIORITY = (
    "test_prexvo_and_profithelm_temp_archive_build_and_seo_audit_parity[profithelm]",
    "test_four_tenant_real_estate_gsc_and_retrofit_convergence_and_callout_parity[profithelm]",
    "test_reflect_recompiles_gainhelm_when_substrate_syncs_and_force",
    "test_unmocked_subprocess_reflect_latch_false_refreshes_existing_ledger_outside_pytest",
    "test_gainhelm_isolated_archive_sync_build_audit_pytest_and_browser",
    "test_gainhelm_live_preexisting_html_heals_via_retrofit_html_and_retrofit_estate",
    "test_automated_readiness_audit_flags_unwired_vault_links_and_missing_payouts",
    "test_prexvo_and_profithelm_temp_archive_build_and_seo_audit_parity[prexvo]",
    "test_gainhelm_datapack_edge_metadata_and_ci_temp_build_parity",
    "test_stage_4_unattended_reflection_and_real_browser_verification",
    "test_four_tenant_real_estate_gsc_and_retrofit_convergence_and_callout_parity[prexvo]",
    "test_end_to_end_six_department_handoff_chain_across_all_three_tenants[profithelm]",
    "test_real_browser_e2e_interactive_surface_across_profithelm_and_prexvo",
)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    shard_spec = config.getoption("--ci-shard")
    if shard_spec:
        from pseofactory_tests.ci_shard_select import parse_shard_spec, select_shard_indices

        try:
            shard_index, shard_total = parse_shard_spec(shard_spec)
        except ValueError as exc:
            raise pytest.UsageError(str(exc)) from exc

        nodeids = [item.nodeid for item in items]
        keep_indices = select_shard_indices(nodeids, shard_index=shard_index, shard_total=shard_total)
        selected = []
        deselected = []
        for idx, item in enumerate(items):
            if idx in keep_indices:
                selected.append(item)
            else:
                deselected.append(item)
        if deselected:
            config.hook.pytest_deselected(items=deselected)
        items[:] = selected
        return

    # Longest-Processing-Time (LPT) ordering so xdist dispatches the heaviest host_estate
    # tests to separate workers at t=0 instead of serializing two 400s tests on one worker.
    def _lpt_rank(item):
        nid = item.nodeid
        for rank, needle in enumerate(_HOST_ESTATE_LPT_PRIORITY):
            if needle in nid:
                return (0, rank)
        return (1, 0)

    items.sort(key=_lpt_rank)


def pytest_sessionfinish(session, exitstatus):
    import os
    import shutil

    pid = os.getpid()
    tmp_root = Path("/tmp")
    for pattern in (f"pseofactory_pytest_*_{pid}*", f"pseofactory_test_syndication_*_{pid}*"):
        for item in list(tmp_root.glob(pattern)):
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except OSError:
                pass

