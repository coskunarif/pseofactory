"""
Lifecycle simulation test suite for Google Search Lifecycle stage-gate progression.
Validates asymmetric independent operational envelopes, tier partitioning,
happy path transitions, idempotency, tenant isolation, and clean syntax invariants.
Zero em-dashes. Zero en-dashes.
"""

from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import pytest

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.indexer import PushIndexer
from pseofactory.indexing.milestones import (
    EVENT_CANONICAL_STABILIZED,
    EVENT_INITIAL_DISCOVERY_DETECTED,
    EVENT_MILESTONE_BREACHED,
    EVENT_QUARANTINE_TRIGGERED,
    EVENT_SEARCH_INDEXED,
    EVENT_SITEMAP_DISPATCHED,
    EVENT_SITEMAP_FULLY_ABSORBED,
    EVENT_URL_CRAWLED,
    EVENT_URL_PREFLIGHT_PASSED,
    LifecycleEvent,
    LifecycleState,
    MILESTONE_ENVELOPES,
    MilestoneEnvelope,
    MilestoneTracker,
    STATE_CANONICAL_STABILIZED,
    STATE_CRAWLED,
    STATE_DRAFT,
    STATE_INITIAL_DISCOVERY,
    STATE_MILESTONE_STALLED,
    STATE_PREFLIGHT_VERIFIED,
    STATE_QUARANTINED,
    STATE_RAPID_INDEXED,
    STATE_SITEMAP_ABSORBED,
    STATE_SITEMAP_DISPATCHED,
)
from pseofactory.indexing.preflight import (
    IndexingPreflightEngine,
    TierClassification,
)


def test_milestone_envelopes_and_operational_bounds():
    """Verifies distinct benchmark operational windows and boundary logic."""
    # 1. Initial discovery: 20h typical, 4h min, 48h warn, 72h breach
    disc = MILESTONE_ENVELOPES["initial_discovery"]
    assert disc.typical_hours == 20.0
    assert disc.typical == 20.0
    assert disc.min_hours == 4.0
    assert disc.warn_hours == 48.0
    assert disc.breach_hours == 72.0
    assert not disc.is_breached(elapsed_hours=20.0)
    assert not disc.is_breached(elapsed_hours=50.0)
    assert disc.check_status(elapsed_hours=50.0) == "WARN"
    assert disc.is_breached(elapsed_hours=73.0)
    assert disc.check_status(elapsed_hours=73.0) == "BREACH"

    # 2. Sitemap absorption: 24h typical, 12h min, 36h warn, 48h breach
    absorb = MILESTONE_ENVELOPES["full_sitemap_absorption"]
    assert absorb.typical_hours == 24.0
    assert absorb.min_hours == 12.0
    assert absorb.warn_hours == 36.0
    assert absorb.breach_hours == 48.0
    assert absorb.check_status(elapsed_hours=10.0) == "OK"
    assert absorb.check_status(elapsed_hours=40.0) == "WARN"
    assert absorb.check_status(elapsed_hours=50.0) == "BREACH"

    # 3. Rapid indexing: 90m typical (1.5h), 15m min, 120m warn, 180m breach
    rapid = MILESTONE_ENVELOPES["rapid_indexing"]
    assert rapid.typical_hours == 1.5
    assert rapid.typical_minutes == 90.0
    assert rapid.min_minutes == 15.0
    assert rapid.warn_minutes == 120.0
    assert rapid.breach_minutes == 180.0
    assert not rapid.is_breached(elapsed_minutes=90.0)
    assert not rapid.is_breached(elapsed_minutes=130.0)
    assert rapid.check_status(elapsed_minutes=130.0) == "WARN"
    assert rapid.is_breached(elapsed_minutes=185.0)
    assert rapid.check_status(elapsed_minutes=185.0) == "BREACH"

    # 4. Canonical updates: 168h min, 504h warn/max, 672h breach
    canon = MILESTONE_ENVELOPES["canonical_updates"]
    assert canon.min_hours == 168.0
    assert canon.typical_min_hours == 168.0
    assert canon.typical_max_hours == 504.0
    assert canon.max_hours == 504.0
    assert canon.warn_hours == 504.0
    assert canon.breach_hours == 672.0
    assert not canon.is_breached(elapsed_hours=336.0)  # 14 days is healthy
    assert canon.check_status(elapsed_hours=336.0) == "OK"
    assert canon.check_status(elapsed_hours=550.0) == "WARN"
    assert canon.is_breached(elapsed_hours=700.0)
    assert canon.check_status(elapsed_hours=700.0) == "BREACH"


def test_rejection_of_uniform_deadlines():
    """Validates asymmetric operational envelopes resisting naive uniform SLAs."""
    tracker = MilestoneTracker(tenant="profithelm")

    # Fast indexing must trigger breach alert after 180 minutes (3 hours)
    assert tracker.is_envelope_breached("rapid_indexing", elapsed_minutes=185)
    assert tracker.check_envelope_status("rapid_indexing", elapsed_minutes=185) == "BREACH"

    # Under a naive 24h uniform timeout, canonical updates would false-alarm at 24h or 48h.
    # Our asymmetric envelope correctly recognizes 336h (14 days) as perfectly normal:
    assert not tracker.is_envelope_breached("canonical_updates", elapsed_hours=24)
    assert not tracker.is_envelope_breached("canonical_updates", elapsed_hours=48)
    assert not tracker.is_envelope_breached("canonical_updates", elapsed_hours=336)
    assert tracker.check_envelope_status("canonical_updates", elapsed_hours=336) == "OK"


def test_tier_partitioning_and_hub_cap():
    """Validates Tier-1 Hub depth <= 2 capped at 150 and Tier-2 Leaf depth > 2."""
    engine = IndexingPreflightEngine(domain="profithelm.com")
    hub_url = "https://profithelm.com/tools/margin-calculator"
    leaf_url = "https://profithelm.com/tools/margin/florida/miami"

    assert engine._calculate_tier(hub_url) == TierClassification.TIER_1_HUB
    assert engine._calculate_tier(leaf_url) == TierClassification.TIER_2_LEAF

    # PushIndexer must strictly enforce 150 URL cap on Tier-1 Hubs (HWL-1076)
    indexer = PushIndexer(domain="profithelm.com")
    hubs_pool = [f"https://profithelm.com/hub-{i}" for i in range(250)]
    partitioned_hubs, _ = indexer.partition_indexing_urls(hubs_pool)
    assert len(partitioned_hubs) == 150


def test_sequential_transition_events_happy_path():
    """Simulates complete stage-gate progression using virtual clock."""
    simulated_now = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)

    def virtual_clock():
        return simulated_now

    tracker = MilestoneTracker(tenant="profithelm", now_fn=virtual_clock)
    url = "https://profithelm.com/tools/gross-margin/"

    # Stage 1: Preflight Pass
    st1 = tracker.record_event(url, EVENT_URL_PREFLIGHT_PASSED)
    assert st1 == STATE_PREFLIGHT_VERIFIED
    assert tracker.get_state(url) == STATE_PREFLIGHT_VERIFIED

    # Stage 2: Sitemap Dispatched (starts discovery timer)
    simulated_now += timedelta(minutes=15)
    st2 = tracker.record_event(url, EVENT_SITEMAP_DISPATCHED)
    assert st2 == STATE_SITEMAP_DISPATCHED
    rec = tracker.get_record(url)
    assert "initial_discovery" in rec.milestone_timers
    assert rec.milestone_timers["initial_discovery"]["closed_at"] is None

    # Stage 3: Initial Discovery Detected after 20 hours (starts absorption timer)
    simulated_now += timedelta(hours=20)
    st3 = tracker.record_event(url, EVENT_INITIAL_DISCOVERY_DETECTED)
    assert st3 == STATE_INITIAL_DISCOVERY
    assert rec.milestone_timers["initial_discovery"]["closed_at"] is not None
    assert "full_sitemap_absorption" in rec.milestone_timers

    # Stage 4: Sitemap Fully Absorbed after 24 hours
    simulated_now += timedelta(hours=24)
    st4 = tracker.record_event(url, EVENT_SITEMAP_FULLY_ABSORBED)
    assert st4 == STATE_SITEMAP_ABSORBED
    assert rec.milestone_timers["full_sitemap_absorption"]["closed_at"] is not None

    # Stage 5: URL Crawled (starts rapid indexing timer)
    simulated_now += timedelta(hours=2)
    st5 = tracker.record_event(url, EVENT_URL_CRAWLED)
    assert st5 == STATE_CRAWLED
    assert "rapid_indexing" in rec.milestone_timers

    # Stage 6: Search Indexed after 90 minutes (starts canonical timer)
    simulated_now += timedelta(minutes=90)
    st6 = tracker.record_event(url, EVENT_SEARCH_INDEXED)
    assert st6 == STATE_RAPID_INDEXED
    assert rec.milestone_timers["rapid_indexing"]["closed_at"] is not None
    assert "canonical_updates" in rec.milestone_timers

    # Stage 7: Canonical Stabilized after 2 weeks (336 hours)
    simulated_now += timedelta(hours=336)
    st7 = tracker.record_event(url, EVENT_CANONICAL_STABILIZED)
    assert st7 == STATE_CANONICAL_STABILIZED
    assert rec.milestone_timers["canonical_updates"]["closed_at"] is not None


def test_universal_idempotency_on_event_replay():
    """Verifies duplicate events return current state without corrupting timers."""
    simulated_now = datetime(2026, 10, 9, 10, 0, 0, tzinfo=timezone.utc)

    def virtual_clock():
        return simulated_now

    tracker = MilestoneTracker(tenant="profithelm", now_fn=virtual_clock)
    url = "https://profithelm.com/tools/pricing-calculator/"

    # Initial event submission
    st_init = tracker.record_event(
        url, EVENT_URL_PREFLIGHT_PASSED, sequence_id="seq-100"
    )
    assert st_init == STATE_PREFLIGHT_VERIFIED
    rec = tracker.get_record(url)
    first_updated_at = rec.updated_at
    event_count_before = len(rec.events)

    # Advance time by 3 hours
    simulated_now += timedelta(hours=3)

    # Replay identical event with same sequence_id
    st_replay = tracker.record_event(
        url, EVENT_URL_PREFLIGHT_PASSED, sequence_id="seq-100"
    )
    assert st_replay == STATE_PREFLIGHT_VERIFIED
    assert rec.updated_at == first_updated_at
    assert len(rec.events) == event_count_before


def test_strict_tenant_isolation_under_simulation(tmp_path):
    """Verifies partition between tenant spaces and rejection of invalid tenants."""
    # 1. Valid tenants succeed
    for tenant in ("profithelm", "prexvo", "unassigned"):
        t = MilestoneTracker(tenant=tenant)
        assert t.tenant == tenant

    # 2. Invalid tenant raises ValueError
    with pytest.raises(ValueError):
        MilestoneTracker(tenant="rogue_cross_tenant_space")

    # 3. Operational isolation: events in profithelm do not leak to prexvo
    t_profithelm = MilestoneTracker(tenant="profithelm")
    t_prexvo = MilestoneTracker(tenant="prexvo")

    test_url = "https://shared-domain.com/tools/calc/"
    t_profithelm.record_event(test_url, EVENT_URL_PREFLIGHT_PASSED)

    assert t_profithelm.get_record(test_url) is not None
    assert t_prexvo.get_record(test_url) is None

    # 4. Isolated ledger exports
    ledger_file = tmp_path / "ledger.json"
    t_profithelm.save_ledger(ledger_file)
    assert ledger_file.exists()


def test_clean_syntax_zero_forbidden_dashes():
    """Asserts clean syntax invariant across milestones module, tests, and exports."""
    import pseofactory.indexing.milestones as milestones_mod
    import pseofactory.indexing as indexing_mod

    # Verify milestones source code
    source_milestones = inspect.getsource(milestones_mod)
    assert_no_forbidden_dashes(source_milestones, context="milestones module source")

    # Verify indexing init source code
    source_init = inspect.getsource(indexing_mod)
    assert_no_forbidden_dashes(source_init, context="indexing init source")

    # Verify test suite source code
    test_source = Path(__file__).read_text(encoding="utf-8")
    assert_no_forbidden_dashes(test_source, context="milestones test suite source")

    # Verify exported ledger payload
    tracker = MilestoneTracker(tenant="profithelm")
    tracker.record_event(
        "https://profithelm.com/tools/test/", EVENT_URL_PREFLIGHT_PASSED
    )
    ledger_dict = tracker.export_ledger()
    ledger_str = str(ledger_dict)
    assert_no_forbidden_dashes(ledger_str, context="milestones ledger export")
