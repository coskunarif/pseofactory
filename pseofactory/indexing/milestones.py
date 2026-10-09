"""
pseofactory Google Search Lifecycle Stage-Gate Progression and Milestone Timers.
Implements asymmetric independent operational envelopes mapped to Google Search
Central empirical telemetry (October 2026 benchmarks).
Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


class LifecycleState(str, Enum):
    STATE_DRAFT = "STATE_DRAFT"
    STATE_PREFLIGHT_VERIFIED = "STATE_PREFLIGHT_VERIFIED"
    STATE_SITEMAP_DISPATCHED = "STATE_SITEMAP_DISPATCHED"
    STATE_INITIAL_DISCOVERY = "STATE_INITIAL_DISCOVERY"
    STATE_SITEMAP_ABSORBED = "STATE_SITEMAP_ABSORBED"
    STATE_CRAWLED = "STATE_CRAWLED"
    STATE_RAPID_INDEXED = "STATE_RAPID_INDEXED"
    STATE_CANONICAL_STABILIZED = "STATE_CANONICAL_STABILIZED"
    STATE_QUARANTINED = "STATE_QUARANTINED"
    STATE_MILESTONE_STALLED = "STATE_MILESTONE_STALLED"

    def __str__(self) -> str:
        return self.value


STATE_DRAFT = LifecycleState.STATE_DRAFT
STATE_PREFLIGHT_VERIFIED = LifecycleState.STATE_PREFLIGHT_VERIFIED
STATE_SITEMAP_DISPATCHED = LifecycleState.STATE_SITEMAP_DISPATCHED
STATE_INITIAL_DISCOVERY = LifecycleState.STATE_INITIAL_DISCOVERY
STATE_SITEMAP_ABSORBED = LifecycleState.STATE_SITEMAP_ABSORBED
STATE_CRAWLED = LifecycleState.STATE_CRAWLED
STATE_RAPID_INDEXED = LifecycleState.STATE_RAPID_INDEXED
STATE_CANONICAL_STABILIZED = LifecycleState.STATE_CANONICAL_STABILIZED
STATE_QUARANTINED = LifecycleState.STATE_QUARANTINED
STATE_MILESTONE_STALLED = LifecycleState.STATE_MILESTONE_STALLED


class LifecycleEvent(str, Enum):
    EVENT_URL_PREFLIGHT_PASSED = "EVENT_URL_PREFLIGHT_PASSED"
    EVENT_SITEMAP_DISPATCHED = "EVENT_SITEMAP_DISPATCHED"
    EVENT_INITIAL_DISCOVERY_DETECTED = "EVENT_INITIAL_DISCOVERY_DETECTED"
    EVENT_SITEMAP_FULLY_ABSORBED = "EVENT_SITEMAP_FULLY_ABSORBED"
    EVENT_URL_CRAWLED = "EVENT_URL_CRAWLED"
    EVENT_SEARCH_INDEXED = "EVENT_SEARCH_INDEXED"
    EVENT_CANONICAL_STABILIZED = "EVENT_CANONICAL_STABILIZED"
    EVENT_MILESTONE_BREACHED = "EVENT_MILESTONE_BREACHED"
    EVENT_QUARANTINE_TRIGGERED = "EVENT_QUARANTINE_TRIGGERED"

    def __str__(self) -> str:
        return self.value


EVENT_URL_PREFLIGHT_PASSED = LifecycleEvent.EVENT_URL_PREFLIGHT_PASSED
EVENT_SITEMAP_DISPATCHED = LifecycleEvent.EVENT_SITEMAP_DISPATCHED
EVENT_INITIAL_DISCOVERY_DETECTED = LifecycleEvent.EVENT_INITIAL_DISCOVERY_DETECTED
EVENT_SITEMAP_FULLY_ABSORBED = LifecycleEvent.EVENT_SITEMAP_FULLY_ABSORBED
EVENT_URL_CRAWLED = LifecycleEvent.EVENT_URL_CRAWLED
EVENT_SEARCH_INDEXED = LifecycleEvent.EVENT_SEARCH_INDEXED
EVENT_CANONICAL_STABILIZED = LifecycleEvent.EVENT_CANONICAL_STABILIZED
EVENT_MILESTONE_BREACHED = LifecycleEvent.EVENT_MILESTONE_BREACHED
EVENT_QUARANTINE_TRIGGERED = LifecycleEvent.EVENT_QUARANTINE_TRIGGERED


EVENT_STATE_TRANSITIONS: Dict[LifecycleEvent, LifecycleState] = {
    LifecycleEvent.EVENT_URL_PREFLIGHT_PASSED: LifecycleState.STATE_PREFLIGHT_VERIFIED,
    LifecycleEvent.EVENT_SITEMAP_DISPATCHED: LifecycleState.STATE_SITEMAP_DISPATCHED,
    LifecycleEvent.EVENT_INITIAL_DISCOVERY_DETECTED: LifecycleState.STATE_INITIAL_DISCOVERY,
    LifecycleEvent.EVENT_SITEMAP_FULLY_ABSORBED: LifecycleState.STATE_SITEMAP_ABSORBED,
    LifecycleEvent.EVENT_URL_CRAWLED: LifecycleState.STATE_CRAWLED,
    LifecycleEvent.EVENT_SEARCH_INDEXED: LifecycleState.STATE_RAPID_INDEXED,
    LifecycleEvent.EVENT_CANONICAL_STABILIZED: LifecycleState.STATE_CANONICAL_STABILIZED,
    LifecycleEvent.EVENT_MILESTONE_BREACHED: LifecycleState.STATE_MILESTONE_STALLED,
    LifecycleEvent.EVENT_QUARANTINE_TRIGGERED: LifecycleState.STATE_QUARANTINED,
}


@dataclass
class MilestoneEnvelope:
    name: str
    typical_hours: float
    min_hours: float
    warn_hours: float
    breach_hours: float
    typical_minutes: Optional[float] = None
    min_minutes: Optional[float] = None
    warn_minutes: Optional[float] = None
    breach_minutes: Optional[float] = None
    typical_min_hours: Optional[float] = None
    typical_max_hours: Optional[float] = None
    max_hours: Optional[float] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.typical_minutes is None:
            self.typical_minutes = self.typical_hours * 60.0
        if self.min_minutes is None:
            self.min_minutes = self.min_hours * 60.0
        if self.warn_minutes is None:
            self.warn_minutes = self.warn_hours * 60.0
        if self.breach_minutes is None:
            self.breach_minutes = self.breach_hours * 60.0
        if self.typical_min_hours is None:
            self.typical_min_hours = self.min_hours
        if self.typical_max_hours is None:
            self.typical_max_hours = self.warn_hours
        if self.max_hours is None:
            self.max_hours = self.typical_max_hours

    @property
    def typical(self) -> float:
        return self.typical_hours

    def is_breached(
        self,
        elapsed_hours: Optional[float] = None,
        elapsed_minutes: Optional[float] = None,
    ) -> bool:
        if elapsed_hours is None and elapsed_minutes is None:
            return False
        total_hours = 0.0
        if elapsed_hours is not None:
            total_hours += float(elapsed_hours)
        if elapsed_minutes is not None:
            total_hours += float(elapsed_minutes) / 60.0
        return total_hours >= self.breach_hours

    def check_status(
        self,
        elapsed_hours: Optional[float] = None,
        elapsed_minutes: Optional[float] = None,
    ) -> str:
        if elapsed_hours is None and elapsed_minutes is None:
            return "OK"
        total_hours = 0.0
        if elapsed_hours is not None:
            total_hours += float(elapsed_hours)
        if elapsed_minutes is not None:
            total_hours += float(elapsed_minutes) / 60.0

        if total_hours >= self.breach_hours:
            return "BREACH"
        if total_hours >= self.warn_hours:
            return "WARN"
        return "OK"

    @classmethod
    def get_default_envelopes(cls) -> Dict[str, "MilestoneEnvelope"]:
        return MILESTONE_ENVELOPES


_INITIAL_DISCOVERY = MilestoneEnvelope(
    name="initial_discovery",
    typical_hours=20.0,
    min_hours=4.0,
    warn_hours=48.0,
    breach_hours=72.0,
    description="Initial new URL discovery occurs after ~20 hours median",
)

_FULL_SITEMAP_ABSORPTION = MilestoneEnvelope(
    name="full_sitemap_absorption",
    typical_hours=24.0,
    min_hours=12.0,
    warn_hours=36.0,
    breach_hours=48.0,
    description="Sitemap processing and absorption completes within ~24 hours",
)

_RAPID_INDEXING = MilestoneEnvelope(
    name="rapid_indexing",
    typical_hours=1.5,
    typical_minutes=90.0,
    min_hours=0.25,
    min_minutes=15.0,
    warn_hours=2.0,
    warn_minutes=120.0,
    breach_hours=3.0,
    breach_minutes=180.0,
    description="Indexing after crawl completes within ~1.5 hours (90 minutes)",
)

_CANONICAL_UPDATES = MilestoneEnvelope(
    name="canonical_updates",
    typical_hours=336.0,
    min_hours=168.0,
    typical_min_hours=168.0,
    typical_max_hours=504.0,
    max_hours=504.0,
    warn_hours=504.0,
    breach_hours=672.0,
    description="Canonical recognition and stabilization requires 1 to 3 weeks",
)

_SITE_MOVE = MilestoneEnvelope(
    name="site_move",
    typical_hours=1440.0,
    min_hours=720.0,
    typical_min_hours=720.0,
    typical_max_hours=2160.0,
    max_hours=2160.0,
    warn_hours=2160.0,
    breach_hours=4320.0,
    description="Domain migration convergence requires 1 to 3 months",
)

MILESTONE_ENVELOPES: Dict[str, MilestoneEnvelope] = {
    "initial_discovery": _INITIAL_DISCOVERY,
    "INITIAL_DISCOVERY": _INITIAL_DISCOVERY,
    "full_sitemap_absorption": _FULL_SITEMAP_ABSORPTION,
    "FULL_SITEMAP_ABSORPTION": _FULL_SITEMAP_ABSORPTION,
    "sitemap_absorption": _FULL_SITEMAP_ABSORPTION,
    "SITEMAP_ABSORPTION": _FULL_SITEMAP_ABSORPTION,
    "rapid_indexing": _RAPID_INDEXING,
    "RAPID_INDEXING": _RAPID_INDEXING,
    "canonical_updates": _CANONICAL_UPDATES,
    "CANONICAL_UPDATES": _CANONICAL_UPDATES,
    "site_move": _SITE_MOVE,
    "SITE_MOVE": _SITE_MOVE,
}


@dataclass
class URLMilestoneRecord:
    url: str
    tenant: str
    state: LifecycleState
    created_at: str
    updated_at: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    milestone_timers: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "tenant": self.tenant,
            "state": str(self.state),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "events": self.events,
            "milestone_timers": self.milestone_timers,
        }


VALID_TENANTS: Set[str] = {"profithelm", "prexvo", "unassigned"}


class MilestoneTracker:
    DEFAULT_ENVELOPES = MILESTONE_ENVELOPES

    def __init__(
        self,
        tenant: str = "unassigned",
        now_fn: Optional[Callable[[], datetime]] = None,
        envelopes: Optional[Dict[str, MilestoneEnvelope]] = None,
    ):
        if tenant not in VALID_TENANTS:
            raise ValueError(
                f"Invalid tenant space '{tenant}'. Allowed tenants: {sorted(VALID_TENANTS)}"
            )
        self.tenant = tenant
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.envelopes = envelopes or dict(self.DEFAULT_ENVELOPES)
        self.records: Dict[str, URLMilestoneRecord] = {}
        self.event_log: List[Dict[str, Any]] = []
        self._seen_event_keys: Set[Tuple[str, str, str, Optional[str]]] = set()

    def get_now(self) -> datetime:
        return self._now_fn()

    def _normalize_event(self, event: Union[str, LifecycleEvent]) -> LifecycleEvent:
        if isinstance(event, LifecycleEvent):
            return event
        if isinstance(event, str):
            ev_clean = event.strip()
            ev_upper = ev_clean.upper()
            if hasattr(LifecycleEvent, ev_upper):
                return getattr(LifecycleEvent, ev_upper)
            if not ev_upper.startswith("EVENT_"):
                candidate = f"EVENT_{ev_upper}"
                if hasattr(LifecycleEvent, candidate):
                    return getattr(LifecycleEvent, candidate)
            for member in LifecycleEvent:
                if member.value == ev_clean or member.name == ev_upper:
                    return member
        raise ValueError(f"Unknown lifecycle event: '{event}'")

    def _get_envelope(self, name: str) -> MilestoneEnvelope:
        key = name.strip().lower()
        if key in self.envelopes:
            return self.envelopes[key]
        key_upper = name.strip().upper()
        if key_upper in self.envelopes:
            return self.envelopes[key_upper]
        raise KeyError(f"Unknown milestone envelope: '{name}'")

    def check_envelope_status(
        self,
        milestone_name: str,
        elapsed_hours: Optional[float] = None,
        elapsed_minutes: Optional[float] = None,
        url: Optional[str] = None,
    ) -> str:
        env = self._get_envelope(milestone_name)
        if elapsed_hours is not None or elapsed_minutes is not None:
            return env.check_status(
                elapsed_hours=elapsed_hours, elapsed_minutes=elapsed_minutes
            )
        if url and url in self.records:
            h = self.get_url_elapsed_hours(url, milestone_name)
            return env.check_status(elapsed_hours=h)
        return "OK"

    def is_envelope_breached(
        self,
        milestone_name: str,
        elapsed_hours: Optional[float] = None,
        elapsed_minutes: Optional[float] = None,
        url: Optional[str] = None,
    ) -> bool:
        env = self._get_envelope(milestone_name)
        if elapsed_hours is not None or elapsed_minutes is not None:
            return env.is_breached(
                elapsed_hours=elapsed_hours, elapsed_minutes=elapsed_minutes
            )
        if url and url in self.records:
            h = self.get_url_elapsed_hours(url, milestone_name)
            return env.is_breached(elapsed_hours=h)
        return False

    def get_url_elapsed_hours(self, url: str, milestone_name: str) -> float:
        if url not in self.records:
            return 0.0
        rec = self.records[url]
        norm_name = milestone_name.lower().strip()
        timer_info = rec.milestone_timers.get(norm_name)
        if not timer_info or "started_at" not in timer_info:
            return 0.0
        started_dt = datetime.fromisoformat(timer_info["started_at"])
        if timer_info.get("closed_at"):
            end_dt = datetime.fromisoformat(timer_info["closed_at"])
        else:
            end_dt = self.get_now()
        diff = (end_dt - started_dt).total_seconds()
        return max(0.0, diff / 3600.0)

    def record_event(
        self,
        url: str,
        event: Union[str, LifecycleEvent],
        sequence_id: Optional[str] = None,
    ) -> LifecycleState:
        norm_event = self._normalize_event(event)
        key = (self.tenant, url, norm_event.value, sequence_id)

        # Idempotency check: duplicate event returns current state without re-running transitions
        if key in self._seen_event_keys:
            if url in self.records:
                return self.records[url].state
            return EVENT_STATE_TRANSITIONS.get(norm_event, LifecycleState.STATE_DRAFT)

        self._seen_event_keys.add(key)
        now_iso = self.get_now().isoformat()

        if url not in self.records:
            self.records[url] = URLMilestoneRecord(
                url=url,
                tenant=self.tenant,
                state=LifecycleState.STATE_DRAFT,
                created_at=now_iso,
                updated_at=now_iso,
            )

        record = self.records[url]
        target_state = EVENT_STATE_TRANSITIONS.get(norm_event, record.state)
        record.state = target_state
        record.updated_at = now_iso

        event_entry = {
            "event": norm_event.value,
            "target_state": target_state.value,
            "sequence_id": sequence_id,
            "timestamp": now_iso,
        }
        record.events.append(event_entry)
        self.event_log.append(
            {
                "tenant": self.tenant,
                "url": url,
                **event_entry,
            }
        )

        # Milestone timer transitions
        if norm_event == LifecycleEvent.EVENT_SITEMAP_DISPATCHED:
            record.milestone_timers["initial_discovery"] = {
                "started_at": now_iso,
                "closed_at": None,
            }
        elif norm_event == LifecycleEvent.EVENT_INITIAL_DISCOVERY_DETECTED:
            if "initial_discovery" in record.milestone_timers:
                record.milestone_timers["initial_discovery"]["closed_at"] = now_iso
            record.milestone_timers["full_sitemap_absorption"] = {
                "started_at": now_iso,
                "closed_at": None,
            }
        elif norm_event == LifecycleEvent.EVENT_SITEMAP_FULLY_ABSORBED:
            if "full_sitemap_absorption" in record.milestone_timers:
                record.milestone_timers["full_sitemap_absorption"]["closed_at"] = now_iso
        elif norm_event == LifecycleEvent.EVENT_URL_CRAWLED:
            record.milestone_timers["rapid_indexing"] = {
                "started_at": now_iso,
                "closed_at": None,
            }
        elif norm_event == LifecycleEvent.EVENT_SEARCH_INDEXED:
            if "rapid_indexing" in record.milestone_timers:
                record.milestone_timers["rapid_indexing"]["closed_at"] = now_iso
            record.milestone_timers["canonical_updates"] = {
                "started_at": now_iso,
                "closed_at": None,
            }
        elif norm_event == LifecycleEvent.EVENT_CANONICAL_STABILIZED:
            if "canonical_updates" in record.milestone_timers:
                record.milestone_timers["canonical_updates"]["closed_at"] = now_iso

        return record.state

    def get_state(self, url: str) -> Optional[LifecycleState]:
        record = self.records.get(url)
        return record.state if record else None

    def get_record(self, url: str) -> Optional[URLMilestoneRecord]:
        return self.records.get(url)

    def export_ledger(self) -> Dict[str, Any]:
        return {
            "tenant": self.tenant,
            "exported_at": self.get_now().isoformat(),
            "urls": {url: rec.to_dict() for url, rec in self.records.items()},
            "event_count": len(self.event_log),
        }

    def save_ledger(self, target_path: Optional[Union[str, Path]] = None) -> Path:
        if target_path is None:
            base_dir = Path(
                f"/home/ubuntuadmin/projects/.agy/runs/ledgers/{self.tenant}"
            )
            base_dir.mkdir(parents=True, exist_ok=True)
            target_path = base_dir / "milestone_ledger.json"
        else:
            target_path = Path(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.export_ledger()
        target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return target_path
