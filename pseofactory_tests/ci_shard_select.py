"""
Deterministic balanced CI shard partitioner for pseofactory_tests.
Partitions collected test nodeids across N shards with zero drops, zero duplicates,
and deterministic LPT load balancing independent of PYTHONHASHSEED.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple

# Relative duration weights (in approximate seconds) for known heavier portable test files/substrings
# so greedy LPT bin-packing balances wall-clock runtime across all N cloud CI shards.
_NODEID_SUBSTRING_WEIGHTS: Tuple[Tuple[str, float], ...] = (
    ("test_standalone_lienbond_cli_build_and_audit_preserve_bootstrap", 48.0),
    ("test_gainhelm_governance_parity_under_seo_growth_workflows", 44.0),
    ("test_lienbond_clean_ci_and_local_substrate_audit_drift_parity", 28.0),
    ("test_lienbond_git_archive_ci_audit_tracks_substrate_syndication", 25.0),
    ("test_lienbond_p2_daily_build_and_rebuild_persistence", 24.0),
    ("test_compile_lienbond_estate_end_to_end", 22.0),
    ("test_live_fetch_respects_time_budget_and_resumes", 22.0),
    ("test_lienbond_upgrades_legacy_gitignore", 12.0),
    ("test_sandbox_standalone_substrate_real_verification", 20.0),
    ("test_ci_sharding_invariants.py", 12.0),
    ("test_step4_isolation_and_parallel_deploys.py", 4.0),
    ("test_step5_external_runtime_sync.py", 3.5),
    ("test_end_to_end_truth_check.py", 4.0),
    ("test_partner_tracking.py", 2.5),
    ("test_seo_growth_loops.py", 2.5),
    ("test_qualified_lead_capture_funnel.py", 2.5),
    ("test_maintenance_lifecycle.py", 2.5),
    ("test_four_tenant_parity_and_lock_guard.py", 3.0),
    ("test_porcelain_determinism_contract.py", 3.0),
    ("test_porcelain_full_estate_gate.py", 3.0),
    ("test_post_tour_engine_sync.py", 2.5),
    ("test_monetization_overhaul_", 2.5),
    ("test_governance_seo_guard.py", 3.0),
)


def parse_shard_spec(spec: str) -> Tuple[int, int]:
    """Parses a 'K/N' 1-indexed shard specification fail-closed."""
    raw = (spec or "").strip()
    if "/" not in raw:
        raise ValueError(f"Invalid --ci-shard value {spec!r}: expected 'K/N' (e.g. '1/4').")
    parts = raw.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid --ci-shard value {spec!r}: expected 'K/N' (e.g. '1/4').")
    try:
        shard_index = int(parts[0].strip())
        shard_total = int(parts[1].strip())
    except ValueError as exc:
        raise ValueError(f"Invalid --ci-shard integers in {spec!r}: {exc}") from exc
    if shard_total < 1 or shard_index < 1 or shard_index > shard_total:
        raise ValueError(
            f"Invalid --ci-shard range {spec!r}: require 1 <= K <= N and N >= 1."
        )
    return shard_index, shard_total


def estimate_nodeid_weight(nodeid: str) -> float:
    """Returns a deterministic positive relative weight for a pytest nodeid."""
    for needle, weight in _NODEID_SUBSTRING_WEIGHTS:
        if needle in nodeid:
            return weight
    return 1.0


def partition_nodeids_across_shards(
    nodeids: Sequence[str],
    shard_total: int,
) -> Dict[int, List[int]]:
    """
    Partitions index positions 0..len(nodeids)-1 into shard_total balanced shards (1..shard_total).
    Guarantees every index appears in exactly one shard and output order is deterministic.
    """
    if shard_total < 1:
        raise ValueError(f"shard_total must be >= 1, got {shard_total}")

    buckets: Dict[int, List[int]] = {k: [] for k in range(1, shard_total + 1)}
    loads: Dict[int, float] = {k: 0.0 for k in range(1, shard_total + 1)}

    # Longest-Processing-Time (LPT) greedy assignment with deterministic lexicographical tie-breaking
    indexed = [
        (idx, nid, estimate_nodeid_weight(nid))
        for idx, nid in enumerate(nodeids)
    ]
    indexed.sort(key=lambda rec: (-rec[2], rec[1], rec[0]))

    for idx, _nid, weight in indexed:
        target_shard = min(
            range(1, shard_total + 1),
            key=lambda k: (loads[k], len(buckets[k]), k),
        )
        buckets[target_shard].append(idx)
        loads[target_shard] += weight

    # Preserve original collection order within each shard
    for k in buckets:
        buckets[k].sort()
    return buckets


def select_shard_indices(
    nodeids: Sequence[str],
    shard_index: int,
    shard_total: int,
) -> Set[int]:
    """Returns the exact set of indices belonging to 1-indexed shard_index of shard_total."""
    if shard_total < 1 or shard_index < 1 or shard_index > shard_total:
        raise ValueError(
            f"Invalid shard selection {shard_index}/{shard_total}: require 1 <= K <= N."
        )
    buckets = partition_nodeids_across_shards(nodeids, shard_total)
    return set(buckets[shard_index])
