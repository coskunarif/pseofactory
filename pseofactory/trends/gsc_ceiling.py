"""
pseofactory Google Search Console Traffic Trends and Algorithmic Ceiling Detection
Ingests 480 days of Search Console metrics, correlates dated Google ranking update intervals,
and detects algorithmic glass ceilings to prevent wasting crawl budget on programmatic voids.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.trends.models import (
    GSCDailyMetricRecord,
    GoogleUpdateEvent,
    AlgorithmicCeilingAnalysis,
    CeilingThresholdSpec,
)


DEFAULT_GOOGLE_UPDATES: List[GoogleUpdateEvent] = [
    GoogleUpdateEvent(
        event_id="goog_core_2024_03",
        name="March 2024 Core and Spam Update",
        update_type="CORE",
        start_date="2024-03-05",
        end_date="2024-04-19",
        impact_buffer_days=14,
        confirmed=1,
        notes="Major HCU integration into core ranking, mass pure-spam penalties",
    ),
    GoogleUpdateEvent(
        event_id="goog_spam_2024_06",
        name="June 2024 Spam Update",
        update_type="SPAM",
        start_date="2024-06-20",
        end_date="2024-06-27",
        impact_buffer_days=7,
        confirmed=1,
        notes="SpamBrain expansion across synthetic sites",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2024_08",
        name="August 2024 Core Update",
        update_type="CORE",
        start_date="2024-08-15",
        end_date="2024-09-03",
        impact_buffer_days=14,
        confirmed=1,
        notes="Independent publisher promotion, HCU feedback calibration",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2024_11",
        name="November 2024 Core Update",
        update_type="CORE",
        start_date="2024-11-11",
        end_date="2024-11-29",
        impact_buffer_days=14,
        confirmed=1,
        notes="Pre-holiday core ranking recalibration",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2024_12",
        name="December 2024 Core Update",
        update_type="CORE",
        start_date="2024-12-12",
        end_date="2024-12-18",
        impact_buffer_days=7,
        confirmed=1,
        notes="Rapid volatility dampening update",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2025_03",
        name="March 2025 Core Update",
        update_type="CORE",
        start_date="2025-03-13",
        end_date="2025-03-30",
        impact_buffer_days=14,
        confirmed=1,
        notes="NavBoost click model recalibration and fresh intent scoring",
    ),
    GoogleUpdateEvent(
        event_id="goog_reputation_2025_06",
        name="June 2025 Spam and Site Reputation Abuse Update",
        update_type="REPUTATION_ABUSE",
        start_date="2025-06-10",
        end_date="2025-06-24",
        impact_buffer_days=14,
        confirmed=1,
        notes="Enforcement against parasitic host leases and subdomains",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2025_08",
        name="August 2025 Core Update",
        update_type="CORE",
        start_date="2025-08-14",
        end_date="2025-09-02",
        impact_buffer_days=14,
        confirmed=1,
        notes="Entity authority validation and GEO compliance weighting",
    ),
    GoogleUpdateEvent(
        event_id="goog_quality_2025_11",
        name="November 2025 Quality and Intent Update",
        update_type="HELPFUL_CONTENT",
        start_date="2025-11-06",
        end_date="2025-11-22",
        impact_buffer_days=14,
        confirmed=1,
        notes="Crawl throttle on low-intent programmatic page clusters",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2026_02",
        name="February 2026 Core Update",
        update_type="CORE",
        start_date="2026-02-12",
        end_date="2026-03-01",
        impact_buffer_days=14,
        confirmed=1,
        notes="AI Overview inclusion alignment and search intent verification",
    ),
    GoogleUpdateEvent(
        event_id="goog_ai_2026_05",
        name="May 2026 AI Overviews and Quality Update",
        update_type="HELPFUL_CONTENT",
        start_date="2026-05-08",
        end_date="2026-05-24",
        impact_buffer_days=14,
        confirmed=1,
        notes="Princeton GEO empirical evidence multiplier enforcement",
    ),
    GoogleUpdateEvent(
        event_id="goog_core_2026_08",
        name="August 2026 Core Update",
        update_type="CORE",
        start_date="2026-08-18",
        end_date="2026-09-04",
        impact_buffer_days=14,
        confirmed=1,
        notes="Information gain scoring and synthetic copy suppression",
    ),
]


def interpolate_metric_timeline(records: List[GSCDailyMetricRecord]) -> List[GSCDailyMetricRecord]:
    """
    Interpolates any missing dates in a historical Search Console series.
    Missing dates are zero-filled with last-known position.
    """
    if not records:
        return []

    sorted_records = sorted(records, key=lambda r: r.date)
    start_dt = datetime.strptime(sorted_records[0].date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(sorted_records[-1].date, "%Y-%m-%d").date()
    prop_id = sorted_records[0].property_id

    records_by_date = {r.date: r for r in sorted_records}
    interpolated: List[GSCDailyMetricRecord] = []
    curr_dt = start_dt
    last_position = sorted_records[0].position or 50.0

    while curr_dt <= end_dt:
        date_str = curr_dt.isoformat()
        if date_str in records_by_date:
            rec = records_by_date[date_str]
            last_position = rec.position
            interpolated.append(rec)
        else:
            interpolated.append(
                GSCDailyMetricRecord(
                    property_id=prop_id,
                    date=date_str,
                    clicks=0,
                    impressions=0,
                    ctr=0.0,
                    position=last_position,
                )
            )
        curr_dt += timedelta(days=1)

    return interpolated


def compute_rolling_averages(records: List[GSCDailyMetricRecord]) -> List[Dict[str, Any]]:
    """
    Computes RMA_7, RMA_28, daily velocity, and second-derivative acceleration.
    Operates strictly using standard library math without external dependencies.
    """
    if not records:
        return []

    timeline_records = interpolate_metric_timeline(records)
    timeline: List[Dict[str, Any]] = []

    for idx, rec in enumerate(timeline_records):
        # RMA_7: window of up to 7 trailing days
        w7_start = max(0, idx - 6)
        w7_slice = timeline_records[w7_start : idx + 1]
        rma_7 = sum(r.impressions for r in w7_slice) / len(w7_slice)

        # RMA_28: window of up to 28 trailing days
        w28_start = max(0, idx - 27)
        w28_slice = timeline_records[w28_start : idx + 1]
        rma_28 = sum(r.impressions for r in w28_slice) / len(w28_slice)

        # Velocity: daily change in short-term momentum
        prev_rma7 = timeline[idx - 1]["rma_7"] if idx > 0 else rma_7
        velocity = rma_7 - prev_rma7

        # Discrete second-derivative acceleration: A_t = v_t - 2 * v_{t-1} + v_{t-2}
        if idx >= 2:
            v_curr = velocity
            v_prev1 = timeline[idx - 1]["velocity"]
            v_prev2 = timeline[idx - 2]["velocity"]
            acceleration = v_curr - 2.0 * v_prev1 + v_prev2
        elif idx == 1:
            acceleration = velocity - timeline[idx - 1]["velocity"]
        else:
            acceleration = 0.0

        timeline.append(
            {
                "date": rec.date,
                "clicks": rec.clicks,
                "impressions": rec.impressions,
                "ctr": rec.ctr,
                "position": rec.position,
                "rma_7": round(rma_7, 2),
                "rma_28": round(rma_28, 2),
                "velocity": round(velocity, 2),
                "acceleration": round(acceleration, 2),
            }
        )

    return timeline


def detect_algorithmic_ceiling(
    metrics: List[GSCDailyMetricRecord],
    updates: Optional[List[GoogleUpdateEvent]] = None,
    threshold: float = 0.35,
) -> AlgorithmicCeilingAnalysis:
    """
    Evaluates historical GSC metrics against known Google algorithm update windows.
    Detects authority dampening ceilings where impression growth plateaus or rejects.
    """
    if not metrics:
        return AlgorithmicCeilingAnalysis(
            property_id="unknown",
            analysis_window_days=480,
            total_days=0,
            ceiling_threshold=threshold,
        )

    if updates is None:
        updates = DEFAULT_GOOGLE_UPDATES

    prop_id = metrics[0].property_id
    timeline = compute_rolling_averages(metrics)
    total_days = len(timeline)

    peak_rma28 = max((d["rma_28"] for d in timeline), default=0.0)
    curr_rma28 = timeline[-1]["rma_28"] if timeline else 0.0

    # Plateau gap: measures distance between current RMA_28 and peak RMA_28
    plateau_gap = max(0.0, 1.0 - (curr_rma28 / max(1.0, peak_rma28)))

    # Correlate timeline with Google updates
    correlated_updates: List[Dict[str, Any]] = []
    timeline_dates = {d["date"]: d for d in timeline}

    for ev in updates:
        try:
            ev_start = datetime.strptime(ev.start_date, "%Y-%m-%d").date()
            ev_end = datetime.strptime(ev.end_date, "%Y-%m-%d").date() if ev.end_date else (ev_start + timedelta(days=14))
        except (ValueError, TypeError):
            continue

        # Pre-update baseline window: 28 days preceding update rollout
        pre_dates = [(ev_start - timedelta(days=i)).isoformat() for i in range(1, 29)]
        pre_metrics = [timeline_dates[d] for d in pre_dates if d in timeline_dates]

        # Post-update observation window: 28 days following completion
        post_dates = [(ev_end + timedelta(days=i)).isoformat() for i in range(1, 29)]
        post_metrics = [timeline_dates[d] for d in post_dates if d in timeline_dates]

        if len(pre_metrics) >= 7 and len(post_metrics) >= 7:
            pre_rma = sum(d["rma_28"] for d in pre_metrics) / len(pre_metrics)
            post_rma = sum(d["rma_28"] for d in post_metrics) / len(post_metrics)
            drop_ratio = max(0.0, (pre_rma - post_rma) / max(1.0, pre_rma))

            # Post-update impression volatility: CV = std_dev / mean
            post_imprs = [d["impressions"] for d in post_metrics]
            p_mean = sum(post_imprs) / len(post_imprs) if post_imprs else 0.0
            p_var = sum((x - p_mean) ** 2 for x in post_imprs) / len(post_imprs) if post_imprs else 0.0
            cv = (math.sqrt(p_var) / max(1.0, p_mean)) if p_mean > 0 else 0.0

            if drop_ratio >= 0.15 or (drop_ratio >= 0.08 and cv >= 0.35) or (pre_rma > 500 and post_rma < pre_rma * 0.85):
                correlated_updates.append(
                    {
                        "event_id": ev.event_id,
                        "name": ev.name,
                        "update_type": ev.update_type,
                        "start_date": ev.start_date,
                        "end_date": ev.end_date,
                        "drop_ratio": round(drop_ratio, 4),
                        "pre_rma28": round(pre_rma, 2),
                        "post_rma28": round(post_rma, 2),
                        "cv": round(cv, 4),
                    }
                )

    max_drop_ratio = max((cu["drop_ratio"] for cu in correlated_updates), default=0.0)

    # Position stagnation: average ranking position in trailing 28 days
    last_28_records = timeline[-28:] if len(timeline) >= 28 else timeline
    valid_positions = [d["position"] for d in last_28_records if d["position"] > 0]
    avg_pos = sum(valid_positions) / len(valid_positions) if valid_positions else 50.0

    if avg_pos > 20.0:
        position_stagnation = min(1.0, max(0.0, (avg_pos - 15.0) / 35.0))
    else:
        position_stagnation = 0.0

    # Ceiling Dampening Score (S)
    score = (0.40 * plateau_gap) + (0.40 * max_drop_ratio) + (0.20 * position_stagnation)
    score = round(max(0.0, min(1.0, score)), 4)

    # Detection logic
    ceiling_detected = (score >= threshold) and (
        len(correlated_updates) > 0 or max_drop_ratio >= 0.20 or plateau_gap >= 0.30
    )

    if score >= 0.60 and ceiling_detected:
        suppression_severity = "HIGH"
        recommendation = "FREEZE_EXPANSION"
    elif ceiling_detected:
        suppression_severity = "MODERATE"
        recommendation = "MONITOR"
    else:
        suppression_severity = "NONE"
        recommendation = "BUILD_PAGE"

    return AlgorithmicCeilingAnalysis(
        property_id=prop_id,
        computed_at=datetime.now(timezone.utc).isoformat(),
        analysis_window_days=480,
        total_days=total_days,
        peak_impressions_rma28=round(peak_rma28, 2),
        current_impressions_rma28=round(curr_rma28, 2),
        ceiling_threshold=threshold,
        ceiling_dampening_score=score,
        ceiling_detected=ceiling_detected,
        suppression_severity=suppression_severity,
        correlated_updates=correlated_updates,
        recommendation=recommendation,
        metrics_timeline=timeline,
        metadata={
            "plateau_gap": round(plateau_gap, 4),
            "max_drop_ratio": round(max_drop_ratio, 4),
            "position_stagnation": round(position_stagnation, 4),
            "trailing_avg_position": round(avg_pos, 2),
        },
    )


class GSCCeilingPipeline:
    """Pipeline coordinating daily Search Console metric ingestion and ceiling analysis."""

    def __init__(self, db: Any = None, threshold: float = 0.35):
        self.db = db
        self.threshold = threshold

    def ingest_records(self, records: List[GSCDailyMetricRecord]) -> int:
        if self.db:
            return self.db.upsert_gsc_daily_metrics(records)
        return len(records)

    def analyze_property(self, property_id: str, days: int = 480) -> AlgorithmicCeilingAnalysis:
        metrics = self.db.get_gsc_daily_metrics(property_id, days=days) if self.db else []
        updates = self.db.get_google_update_events() if self.db else None
        return detect_algorithmic_ceiling(metrics, updates, threshold=self.threshold)
