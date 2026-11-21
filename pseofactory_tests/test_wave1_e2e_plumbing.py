"""
Regression tests for Wave 1 pseofactory E2E plumbing fixes:
  - Item 2: Compact AsyncRemediationQueue persistence, legacy auto-compaction,
    bounded COMPLETED pruning, batched saves, and AtomicStateLedger temp cleanup.
  - Item 3: Fail-closed functions/api/signal.js generator, sync, and parity guard.
  - Item 4: Tenant-local quarantine ledger routing and cross-domain stale pruning.
  - Item 5: IndexingFeedbackLoop dist_dir isolation and live repo mutation guard.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest


def test_async_remediation_queue_compacts_bloat_deduplicates_prunes_and_batches_saves(tmp_path: Path) -> None:
    from pseofactory.gsc_remediation import AsyncRemediationQueue
    from pseofactory.supervisor import AtomicStateLedger

    q_path = tmp_path / ".agy" / "gsc_remediation_queue.json"
    q_path.parent.mkdir(parents=True, exist_ok=True)

    # Seed legacy bloated state with 70 COMPLETED tasks (including duplicates + stale >14d)
    # and 3 PENDING tasks carrying massive engagement_metrics, partner_offer, and overlay_spec blobs.
    now = datetime.now(timezone.utc)
    giant_eng = {
        "total_events": 9999,
        "by_slug": {f"tool-{i}": {"clicks": i, "payload": "x" * 200} for i in range(50)},
        "by_page": {f"/tools/tool-{i}/": {"clicks": i} for i in range(50)},
    }
    giant_offer = {
        "partner_key": "mercury",
        "partner_name": "Mercury",
        "cta_slot": "calculator_primary_cta",
        "yield_score": 42.5,
        "partner_roster": {"entries": ["r" * 400 for _ in range(20)]},
        "slot_plan": {"slots": ["s" * 400 for _ in range(20)]},
        "ranked_partner_candidates": [{"k": f"p{i}", "blob": "b" * 200} for i in range(10)],
    }
    giant_overlay = {
        "slug": "about",
        "title_rewrite": "About ProfitHelm",
        "measurement_lock_days": 28,
        "partner_offer": giant_offer,
        "partner_roster": giant_offer["partner_roster"],
        "slot_plan": giant_offer["slot_plan"],
    }

    legacy_tasks = []
    # 15 duplicate COMPLETED tasks for the same slug "about"
    for i in range(15):
        ts = (now - timedelta(days=1, minutes=i)).isoformat()
        legacy_tasks.append({
            "tenant_id": "profithelm",
            "property_id": "profithelm",
            "slug": "about",
            "target_url": "https://profithelm.com/about/",
            "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
            "status": "COMPLETED",
            "completed_at": ts,
            "updated_at": ts,
            "idempotency_key": f"dup-about-{i}",
            "engagement_metrics": giant_eng,
            "partner_offer": giant_offer,
            "overlay_spec": giant_overlay,
        })
    # 60 unique recent COMPLETED tasks (exceeds 50-task rolling cap)
    for i in range(60):
        ts = (now - timedelta(hours=i + 1)).isoformat()
        legacy_tasks.append({
            "tenant_id": "profithelm",
            "property_id": "profithelm",
            "slug": f"completed-tool-{i:02d}",
            "target_url": f"https://profithelm.com/tools/completed-tool-{i:02d}/",
            "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
            "status": "COMPLETED",
            "completed_at": ts,
            "updated_at": ts,
            "idempotency_key": f"comp-{i:02d}",
            "engagement_metrics": giant_eng,
            "partner_offer": giant_offer,
            "overlay_spec": giant_overlay,
        })
    # 5 expired COMPLETED tasks older than 14 days
    for i in range(5):
        ts = (now - timedelta(days=20 + i)).isoformat()
        legacy_tasks.append({
            "tenant_id": "profithelm",
            "property_id": "profithelm",
            "slug": f"old-tool-{i}",
            "target_url": f"https://profithelm.com/tools/old-tool-{i}/",
            "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
            "status": "COMPLETED",
            "completed_at": ts,
            "updated_at": ts,
            "idempotency_key": f"old-{i}",
            "engagement_metrics": giant_eng,
        })
    # 3 distinct PENDING tasks (must NEVER be dropped!)
    for i in range(3):
        legacy_tasks.append({
            "tenant_id": "profithelm",
            "property_id": "profithelm",
            "slug": f"pending-tool-{i}",
            "target_url": f"https://profithelm.com/tools/pending-tool-{i}/",
            "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
            "status": "PENDING",
            "roi_score": 100.0 + i,
            "idempotency_key": f"pend-{i}",
            "engagement_metrics": giant_eng,
            "partner_offer": giant_offer,
            "overlay_spec": giant_overlay,
        })

    q_path.write_text(
        json.dumps({"version": 1, "tenants": {"profithelm": {"tasks": legacy_tasks}}}),
        encoding="utf-8",
    )
    bloated_bytes = q_path.stat().st_size
    assert bloated_bytes > 500_000

    queue = AsyncRemediationQueue(queue_path=q_path)

    # Re-enqueuing an already-pending slug must deduplicate
    enq_dup = queue.enqueue_batch(
        [
            {
                "tenant_id": "profithelm",
                "slug": "pending-tool-0",
                "target_url": "https://profithelm.com/tools/pending-tool-0/",
                "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
                "engagement_metrics": giant_eng,
                "partner_offer": giant_offer,
                "overlay_spec": giant_overlay,
            }
        ],
        tenant_id="profithelm",
    )
    assert enq_dup["enqueued_count"] == 0
    assert enq_dup["deduplicated_count"] == 1

    # Verify disk file shrank dramatically, all 3 PENDING tasks survived, and COMPLETED <= 50
    compacted_bytes = q_path.stat().st_size
    assert compacted_bytes < 50_000
    tasks_after = queue.get_tenant_tasks("profithelm")
    pending_slugs = {t["slug"] for t in tasks_after if t["status"] == "PENDING"}
    completed_tasks = [t for t in tasks_after if t["status"] == "COMPLETED"]
    assert pending_slugs == {"pending-tool-0", "pending-tool-1", "pending-tool-2"}
    assert len(completed_tasks) <= 50
    for t in tasks_after:
        assert "engagement_metrics" not in t
        assert "overlay_spec" not in t
        assert "partner_roster" not in t
        assert "slot_plan" not in t
        if "partner_offer" in t:
            assert "partner_roster" not in t["partner_offer"]
            assert "slot_plan" not in t["partner_offer"]

    # Verify process_tenant_batch saves state ONCE (not per task)
    save_calls = 0
    orig_save = AtomicStateLedger.save_json

    def _counting_save(path, data):
        nonlocal save_calls
        save_calls += 1
        return orig_save(path, data)

    with patch.object(AtomicStateLedger, "save_json", side_effect=_counting_save):
        proc = queue.process_tenant_batch(
            tenant_id="profithelm",
            worker_fn=lambda task: {"status": "COMPLETED"},
        )
    assert proc["completed_count"] == 3
    assert save_calls == 1


def test_atomic_state_ledger_cleans_temp_file_on_interrupt_and_stale_orphans(tmp_path: Path) -> None:
    from pseofactory.supervisor import AtomicStateLedger

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    target = agy_dir / "state.json"

    # Simulate an exception mid-write inside NamedTemporaryFile
    class _ExplodingTempFile:
        def __init__(self, real_tf):
            self._real = real_tf
            self.name = real_tf.name

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._real.__exit__(exc_type, exc, tb)

        def write(self, data):
            self._real.write(data[:10])
            raise KeyboardInterrupt("simulated SIGTERM mid-write")

        def flush(self):
            return self._real.flush()

        def fileno(self):
            return self._real.fileno()

    import tempfile as _tempfile
    real_ntf = _tempfile.NamedTemporaryFile

    def _wrapped_ntf(*args, **kwargs):
        return _ExplodingTempFile(real_ntf(*args, **kwargs))

    with patch("pseofactory.supervisor.tempfile.NamedTemporaryFile", side_effect=_wrapped_ntf):
        with pytest.raises(KeyboardInterrupt):
            AtomicStateLedger.save_json(target, {"hello": "world"})

    # Zero orphaned tmp* files left behind!
    orphans = [p.name for p in agy_dir.iterdir() if p.name.startswith("tmp")]
    assert orphans == []

    # Stale >1h orphaned NamedTemporaryFile in .agy/ is self-healed on next save_json,
    # while fresh tmp* files and real .json files are preserved.
    stale_orphan = agy_dir / "tmpzxgjv28i"
    stale_orphan.write_text("partial", encoding="utf-8")
    old_mtime = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
    os.utime(stale_orphan, (old_mtime, old_mtime))

    fresh_tmp = agy_dir / "tmpfresh123"
    fresh_tmp.write_text("in-flight", encoding="utf-8")

    AtomicStateLedger.save_json(target, {"ok": True})
    assert not stale_orphan.exists()
    assert fresh_tmp.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_edge_signal_function_fail_closed_no_hardcoded_secret_and_sync_parity(tmp_path: Path) -> None:
    from pseofactory.edge import (
        generate_edge_signal_function,
        sync_tenant_edge_redirect_function,
        verify_tenant_edge_functions_parity,
    )

    js_src = generate_edge_signal_function()
    # Must NEVER contain a hardcoded fallback secret literal
    assert "sig_sec_" not in js_src
    assert "env.AGY_PHONE_SIGNAL_TOKEN" in js_src
    assert "503" in js_src

    # Execute generated ES module directly in Node.js to verify fail-closed runtime behavior
    signal_mjs = tmp_path / "signal.mjs"
    signal_mjs.write_text(js_src, encoding="utf-8")
    probe_script = f"""
import {{ onRequestPost, onRequestOptions, onRequest }} from {json.dumps(signal_mjs.as_uri())};

async function run() {{
  // 1. Missing env var must fail closed with HTTP 503 even if a Bearer token is supplied
  const rUnset = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
      headers: {{ Authorization: "Bearer anything-at-all" }},
      body: JSON.stringify({{ receipt_id: "r1" }}),
    }}),
    env: {{}},
  }});
  // 2. Empty/whitespace env var must also fail closed with HTTP 503
  const rEmpty = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
      headers: {{ Authorization: "Bearer anything-at-all" }},
    }}),
    env: {{ AGY_PHONE_SIGNAL_TOKEN: "   " }},
  }});
  // 3. Configured env var + wrong Bearer -> 401
  const rWrong = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
      headers: {{ Authorization: "Bearer wrong-token" }},
    }}),
    env: {{ AGY_PHONE_SIGNAL_TOKEN: "unit-test-token-value" }},
  }});
  // 4. Configured env var + missing Authorization -> 401
  const rMissing = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
    }}),
    env: {{ AGY_PHONE_SIGNAL_TOKEN: "unit-test-token-value" }},
  }});
  // 5. Configured env var + valid Bearer -> 200
  const rOk = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
      headers: {{
        Authorization: "Bearer unit-test-token-value",
        "Content-Type": "application/json",
      }},
      body: JSON.stringify({{ receipt_id: "rcpt-42" }}),
    }}),
    env: {{ AGY_PHONE_SIGNAL_TOKEN: "unit-test-token-value" }},
  }});
  const okBody = await rOk.json();
  // 6. Configured env var + JSON literal null body -> 200 (never 500 TypeError)
  const rNull = await onRequestPost({{
    request: new Request("https://profithelm.com/api/signal", {{
      method: "POST",
      headers: {{
        Authorization: "Bearer unit-test-token-value",
        "Content-Type": "application/json",
      }},
      body: "null",
    }}),
    env: {{ AGY_PHONE_SIGNAL_TOKEN: "unit-test-token-value" }},
  }});
  const nullBody = await rNull.json();
  console.log(JSON.stringify({{
    unset_status: rUnset.status,
    empty_status: rEmpty.status,
    wrong_status: rWrong.status,
    missing_status: rMissing.status,
    ok_status: rOk.status,
    ok_receipt: okBody.receipt_id,
    null_status: rNull.status,
    null_receipt: nullBody.receipt_id,
  }}));
}}
run();
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", probe_script],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    res = json.loads(proc.stdout.strip())
    assert res["unset_status"] == 503
    assert res["empty_status"] == 503
    assert res["wrong_status"] == 401
    assert res["missing_status"] == 401
    assert res["ok_status"] == 200
    assert res["ok_receipt"] == "rcpt-42"
    assert res["null_status"] == 200
    assert res["null_receipt"] is None

    # Verify sync_tenant_edge_redirect_function heals stale signal.js and parity gate enforces it
    repo = tmp_path / "profithelm-repo"
    (repo / "functions" / "r").mkdir(parents=True, exist_ok=True)
    (repo / "functions" / "api").mkdir(parents=True, exist_ok=True)
    (repo / "dist").mkdir(parents=True, exist_ok=True)
    (repo / "functions" / "api" / "signal.js").write_text(
        'const HARDCODED = "stale"; export async function onRequestPost() {}',
        encoding="utf-8",
    )
    sync_tenant_edge_redirect_function(repo, property_id="profithelm")
    ok_synced, reasons_synced = verify_tenant_edge_functions_parity(repo, "profithelm")
    assert ok_synced is True, reasons_synced
    assert (repo / "functions" / "api" / "signal.js").read_text(encoding="utf-8") == js_src

    # Tampering with signal.js must fail parity
    (repo / "functions" / "api" / "signal.js").write_text("// tampered", encoding="utf-8")
    ok_tampered, reasons_tampered = verify_tenant_edge_functions_parity(repo, "profithelm")
    assert ok_tampered is False
    assert any("functions/api/signal.js" in r for r in reasons_tampered)


def test_quarantine_cross_domain_pruner_and_feedback_loop_dist_isolation(tmp_path: Path) -> None:
    from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop
    from pseofactory.indexing.preflight import prune_stale_cross_domain_quarantine_entries

    # 1. Cross-domain stale canonical mismatch entries (profithelm.com -> gainhelm.com) are pruned,
    # while genuine same-domain or non-tenant (example.com) entries are preserved.
    q_file = tmp_path / "indexing_quarantine_ledger.json"
    ph_dist = tmp_path / "profithelm-dist"
    ph_dist.mkdir(parents=True, exist_ok=True)
    q_file.write_text(
        json.dumps(
            {
                "https://profithelm.com/tools/soc-2-audit-cost-calculator/": {
                    "url": "https://profithelm.com/tools/soc-2-audit-cost-calculator/",
                    "code": "QUARANTINE_UNINDEXABLE_META",
                    "reason": "Canonical mismatch: target 'https://profithelm.com/tools/soc-2-audit-cost-calculator/' points to canonical 'https://gainhelm.com/tools/soc-2-audit-cost-calculator/'",
                },
                "https://profithelm.com/tools/real-external-mismatch/": {
                    "url": "https://profithelm.com/tools/real-external-mismatch/",
                    "code": "QUARANTINE_UNINDEXABLE_META",
                    "reason": "Canonical mismatch: points to https://example.com/other",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pruned = prune_stale_cross_domain_quarantine_entries(
        q_file,
        tenant_dist_dirs={"profithelm.com": ph_dist},
        dry_run=False,
    )
    assert pruned == ["https://profithelm.com/tools/soc-2-audit-cost-calculator/"]
    remaining = json.loads(q_file.read_text(encoding="utf-8"))
    assert list(remaining.keys()) == ["https://profithelm.com/tools/real-external-mismatch/"]

    # 2. IndexingFeedbackLoop(base_dir=tmp_repo) MUST default dist_dir to tmp_repo/dist,
    # NEVER live /home/ubuntuadmin/projects/profithelm-platform/dist, and block live mutations.
    ph_repo = tmp_path / "ph-isolated"
    (ph_repo / "dist").mkdir(parents=True, exist_ok=True)
    loop = IndexingFeedbackLoop(base_dir=ph_repo, property_id="profithelm")
    assert loop.dist_dir == (ph_repo / "dist").resolve()
    assert IndexingFeedbackLoop._is_live_repo_mutation_blocked(
        Path("/home/ubuntuadmin/projects/profithelm-platform/dist/index.html")
    ) is True
    assert IndexingFeedbackLoop._is_live_repo_mutation_blocked(
        ph_repo / "dist" / "index.html"
    ) is False


def test_preflight_reads_declarative_contract_dataclass_and_preserves_existing_and_homepage_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Regression tests for Blockers 1 & 3:
      1. IndexingPreflightEngine(property_id="profithelm").quarantine_blocked_urls(...)
         without dist_dir resolves DeclarativeTenantContract dataclass attributes and writes
         to <tenant-repo>/.agy/indexing_quarantine_ledger.json (NOT root .agy/).
      2. prune_stale_cross_domain_quarantine_entries(...) without explicit tenant_dist_dirs
         discovers live dist/ from DeclarativeTenantContract and does NOT falsely prune a real
         canonical defect on an existing route (like /tools/saas-runway-calculator/) or on the
         root homepage (https://profithelm.com/ when dist/index.html exists).
    """
    from dataclasses import replace
    from pseofactory.indexing.preflight import (
        IndexingPreflightEngine,
        prune_stale_cross_domain_quarantine_entries,
    )
    from pseofactory.tenant_facts import CANONICAL_TENANT_DECLARATIONS

    # (a) Quarantine routing without dist_dir uses DeclarativeTenantContract dataclass
    fake_repo = tmp_path / "profithelm-platform"
    fake_repo.mkdir(parents=True, exist_ok=True)
    patched_ph = replace(
        CANONICAL_TENANT_DECLARATIONS["profithelm"],
        repo_root=str(fake_repo),
        repo_dir_name=fake_repo.name,
    )
    patched_decls = dict(CANONICAL_TENANT_DECLARATIONS)
    patched_decls["profithelm"] = patched_ph

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with patch("pseofactory.tenant_facts.CANONICAL_TENANT_DECLARATIONS", patched_decls):
        eng = IndexingPreflightEngine(property_id="profithelm", domain="profithelm.com", dist_dir=None)
        eng.quarantine_blocked_urls(["https://profithelm.com/tools/broken-test/"])

    expected_tenant_ledger = fake_repo / ".agy" / "indexing_quarantine_ledger.json"
    assert expected_tenant_ledger.is_file()
    written = json.loads(expected_tenant_ledger.read_text(encoding="utf-8"))
    assert len(written) == 1
    assert written[0]["url"] == "https://profithelm.com/tools/broken-test/"

    # (b) Pruner without explicit tenant_dist_dirs discovers dist/ via DeclarativeTenantContract
    # and preserves existing routes (saas-runway-calculator) and root homepage (/) while pruning
    # non-existent cross-tenant routes (soc-2-audit-cost-calculator).
    fake_dist = fake_repo / "dist"
    (fake_dist / "tools" / "saas-runway-calculator").mkdir(parents=True, exist_ok=True)
    (fake_dist / "index.html").write_text("<!DOCTYPE html><html><body>ProfitHelm</body></html>", encoding="utf-8")
    (fake_dist / "tools" / "saas-runway-calculator" / "index.html").write_text(
        "<!DOCTYPE html><html><body>SaaS Runway Calculator</body></html>",
        encoding="utf-8",
    )

    q_file = tmp_path / "live_dist_probe_quarantine.json"
    q_file.write_text(
        json.dumps(
            {
                "https://profithelm.com/tools/saas-runway-calculator/": {
                    "url": "https://profithelm.com/tools/saas-runway-calculator/",
                    "code": "QUARANTINE_UNINDEXABLE_META",
                    "reason": "Canonical mismatch: target 'https://profithelm.com/tools/saas-runway-calculator/' points to canonical 'https://gainhelm.com/tools/saas-runway-calculator/'",
                },
                "https://profithelm.com/": {
                    "url": "https://profithelm.com/",
                    "code": "QUARANTINE_UNINDEXABLE_META",
                    "reason": "Canonical mismatch: target 'https://profithelm.com/' points to canonical 'https://gainhelm.com/'",
                },
                "https://profithelm.com/tools/soc-2-audit-cost-calculator/": {
                    "url": "https://profithelm.com/tools/soc-2-audit-cost-calculator/",
                    "code": "QUARANTINE_UNINDEXABLE_META",
                    "reason": "Canonical mismatch: target 'https://profithelm.com/tools/soc-2-audit-cost-calculator/' points to canonical 'https://gainhelm.com/tools/soc-2-audit-cost-calculator/'",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with patch("pseofactory.tenant_facts.CANONICAL_TENANT_DECLARATIONS", patched_decls):
        pruned = prune_stale_cross_domain_quarantine_entries(q_file, dry_run=False)
    assert pruned == ["https://profithelm.com/tools/soc-2-audit-cost-calculator/"]
    kept = json.loads(q_file.read_text(encoding="utf-8"))
    assert "https://profithelm.com/tools/saas-runway-calculator/" in kept
    assert "https://profithelm.com/" in kept
    assert "https://profithelm.com/tools/soc-2-audit-cost-calculator/" not in kept


def test_async_remediation_queue_preserves_active_28day_locked_completed_tasks_beyond_14d_ttl_and_50_cap(
    tmp_path: Path,
) -> None:
    """
    Regression test for Blocker 2:
      A day-15 COMPLETED task with measurement_lock_days=28 (locked_until = now + 13d)
      must survive _compact_and_prune_state() (exempt from both 14-day TTL and 50-task cap)
      AND cause enqueue_batch() to deduplicate it (enqueued_count == 0, deduplicated_count == 1).
    """
    from pseofactory.gsc_remediation import AsyncRemediationQueue

    q_path = tmp_path / ".agy" / "gsc_remediation_queue.json"
    q_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    day15_completed_at = (now - timedelta(days=15)).isoformat()
    day15_locked_until = (now + timedelta(days=13)).isoformat()
    tasks = [
        {
            "tenant_id": "profithelm",
            "property_id": "profithelm",
            "slug": "locked-day15-calculator",
            "target_url": "https://profithelm.com/tools/locked-day15-calculator/",
            "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
            "status": "COMPLETED",
            "completed_at": day15_completed_at,
            "updated_at": day15_completed_at,
            "measurement_lock_days": 28,
            "locked_until": day15_locked_until,
            "idempotency_key": "day15-locked-key",
        }
    ]
    # Add 60 newer UNLOCKED completed tasks to exceed the 50-task rolling cap
    for i in range(60):
        ts = (now - timedelta(hours=i + 1)).isoformat()
        expired_lock = (now - timedelta(minutes=5)).isoformat()
        tasks.append(
            {
                "tenant_id": "profithelm",
                "property_id": "profithelm",
                "slug": f"newer-unlocked-{i:02d}",
                "target_url": f"https://profithelm.com/tools/newer-unlocked-{i:02d}/",
                "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
                "status": "COMPLETED",
                "completed_at": ts,
                "updated_at": ts,
                "locked_until": expired_lock,
                "idempotency_key": f"newer-unlocked-{i:02d}",
            }
        )

    q_path.write_text(
        json.dumps({"version": 1, "tenants": {"profithelm": {"tasks": tasks}}}),
        encoding="utf-8",
    )

    q = AsyncRemediationQueue(queue_path=q_path)
    loaded = q.get_tenant_tasks("profithelm")
    slugs = {t["slug"] for t in loaded}
    assert "locked-day15-calculator" in slugs
    # 1 locked task + 50 capped unlocked tasks = 51 total
    assert len(loaded) == 51

    # Re-enqueuing the same slug/action with a new payload hash must STILL deduplicate
    # because locked_until is still 13 days in the future!
    enq = q.enqueue_batch(
        [
            {
                "tenant_id": "profithelm",
                "slug": "locked-day15-calculator",
                "target_url": "https://profithelm.com/tools/locked-day15-calculator/",
                "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
                "query": "slightly different query text",
            }
        ],
        tenant_id="profithelm",
    )
    assert enq["enqueued_count"] == 0
    assert enq["deduplicated_count"] == 1
    assert enq["status"] == "DEDUPLICATED_NO_OP"

