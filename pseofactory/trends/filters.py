"""
pseofactory Ingestion Noise Filtering & Mathematical Acceleration Gating
Enforces token bounds, stoplist rejection, z-score rupture thresholding, and HWL-1215 second-derivative acceleration.
Zero em-dashes. Zero en-dashes.
"""

import re
from typing import Tuple, List, Optional, Dict, Any
from pseofactory.contracts import sanitize_url_slug, assert_no_forbidden_dashes
from pseofactory.trends.models import FeedSpike, TrendCandidate


DEFAULT_STOPLIST: List[str] = [
    "oscars dress",
    "red carpet",
    "dress designer",
    "soundboard remix",
    "hawk tuah",
    "scrubbed reasons",
    "launch scrubbed",
    "halftime performer leak",
    "performer leak",
    "celebrity gossip",
    "breakup",
    "divorce",
    "dating rumor",
    "dating rumour",
    "box office weekend",
    "trailer reaction",
    "wardrobe malfunction",
    "meme remix",
    "viral meme",
]

CALCULATOR_PATTERNS = [
    r"\bcalc\b",
    r"\bcalculator\b",
    r"\bestimator\b",
    r"\bestimate\b",
    r"\bamortization\b",
    r"\brepayment\b",
    r"\bdeduction\b",
]

STATUTORY_PATTERNS = [
    r"\bform\s+\d+",
    r"\bsection\s+\d+",
    r"\birc\s+\d+",
    r"\bcfr\s+\d+",
    r"\bmatrix\b",
    r"\bstatutory\b",
    r"\bcompliance\b",
    r"\bclean energy deduction\b",
    r"\bhome office deduction\b",
]

COMPARISON_PATTERNS = [
    r"\bvs\b",
    r"\bversus\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\balternative\b",
]


def calculate_second_derivative_acceleration(v_t: float, v_prev1: float, v_prev2: float) -> float:
    """
    Computes discrete second-derivative acceleration A_t = v_t - 2 * v_{t-1} + v_{t-2}
    per HWL-1215. Positive acceleration confirms surging, non-decaying momentum.
    """
    return float(v_t - 2.0 * v_prev1 + v_prev2)


def calculate_z_score(velocity: float, baseline_mean: float, baseline_std: float) -> float:
    """Computes statistical anomaly score (v - mean) / std."""
    if baseline_std <= 0.0:
        return 0.0
    return float((velocity - baseline_mean) / baseline_std)


def is_transient_noise_text(text: str, custom_stoplist: Optional[List[str]] = None) -> bool:
    """Detects ephemeral gossip, viral memes, entertainment rumours, and breaking news."""
    t_clean = text.lower().strip()
    stoplist = custom_stoplist or DEFAULT_STOPLIST
    for stop_term in stoplist:
        if stop_term.lower() in t_clean:
            return True

    # Generic heuristics for transient breaking chatter
    if any(k in t_clean for k in ["oscars", "grammys", "super bowl", "halftime", "soundboard"]):
        if any(w in t_clean for w in ["dress", "leak", "rumor", "rumour", "meme", "remix"]):
            return True

    if "launch scrubbed" in t_clean or ("scrubbed" in t_clean and "today" in t_clean):
        return True

    if any(op in t_clean for op in ("site:", "filetype:", "inurl:", "intitle:", "site-irs-gov")):
        return True

    return False


def classify_intent_cluster(query: str) -> str:
    """Classifies query into programmatic utility cluster."""
    q_lower = query.lower()
    for pat in STATUTORY_PATTERNS:
        if re.search(pat, q_lower):
            return "statutory_compliance"
    for pat in CALCULATOR_PATTERNS:
        if re.search(pat, q_lower):
            return "calculator"
    for pat in COMPARISON_PATTERNS:
        if re.search(pat, q_lower):
            return "comparison"
    if any(w in q_lower for w in ["tool", "generator", "converter", "validator", "checker"]):
        return "tool"
    return "informational"


SEASONAL_STATUTORY_MARKERS: tuple[str, ...] = (
    "tax",
    "179",
    "168",
    "174",
    "199a",
    "1099",
    "fafsa",
    "pell",
    "pslf",
    "extension",
    "deadline",
    "quarterly",
    "annual",
)


def classify_longitudinal_trajectory(
    query: str = "",
    series: Optional[List[float]] = None,
    velocity: float = 0.0,
    acceleration: float = 0.0,
    search_volume: Optional[int] = None,
    growth_pct: Optional[float] = None,
    is_breakout: bool = False,
    cpc_usd: float = 0.0,
    intent_cluster: Optional[str] = None,
    relative_index_0_100: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic multi-horizon trajectory and breakout-baseline qualifier
    (x-like:2098466289282842729 Steps 2, 3, and 4):
      1. Never conflates a 0-100 Google Trends relative index with actual monthly search volume.
      2. Flags 'Breakout' (>5,000% growth or is_breakout=True) starting from near-zero search
         volume (<100/mo, or <250/mo informational with CPC <$0.50) as BREAKOUT_LOW_BASELINE_TRAP.
      3. Evaluates 5-year / multi-window longitudinal series right-hand slope and peak retention
         to separate POST_SPIKE_DECAY from SEASONAL_PRE_PEAK and SUSTAINED_GROWTH.
    Zero em-dashes. Zero en-dashes.
    """
    q_clean = str(query or "").strip().lower()
    cluster = intent_cluster or classify_intent_cluster(q_clean)
    eff_growth = float(growth_pct) if growth_pct is not None else 0.0
    breakout_flag = bool(is_breakout) or eff_growth >= 5000.0

    # 1. Breakout Low-Baseline Trap Gate (>5,000% from near-zero baseline or unverified 0-100 index)
    if search_volume is not None:
        vol = int(search_volume)
        if breakout_flag and vol < 100:
            return {
                "classification": "BREAKOUT_LOW_BASELINE_TRAP",
                "is_viable": False,
                "is_breakout_flag": True,
                "relative_index_is_not_search_volume": True,
                "verified_search_volume": vol,
                "growth_pct": eff_growth or 5000.0,
                "retention_ratio": 0.0,
                "right_hand_slope": 0.0,
                "jev_multiplier": 0.0,
                "recommended_action": "HOLD_LOW_BASELINE_TRAP",
                "reason": (
                    f"Breakout (>5,000% growth) started from near-zero baseline volume ({vol}/mo < 100 floor); "
                    "relative 0-100 trend index is not search volume."
                ),
            }
        if breakout_flag and vol < 250 and cluster == "informational" and float(cpc_usd) < 0.50:
            return {
                "classification": "BREAKOUT_LOW_BASELINE_TRAP",
                "is_viable": False,
                "is_breakout_flag": True,
                "relative_index_is_not_search_volume": True,
                "verified_search_volume": vol,
                "growth_pct": eff_growth or 5000.0,
                "retention_ratio": 0.0,
                "right_hand_slope": 0.0,
                "jev_multiplier": 0.0,
                "recommended_action": "HOLD_LOW_BASELINE_TRAP",
                "reason": (
                    f"Informational breakout ({vol}/mo, CPC ${cpc_usd:.2f}) lacks commercial/statutory "
                    "utility floor and risks zero-impression crawl dilution."
                ),
            }
    elif relative_index_0_100 is not None and breakout_flag:
        # Relative 0-100 index supplied without verified search volume
        return {
            "classification": "BREAKOUT_LOW_BASELINE_TRAP",
            "is_viable": False,
            "is_breakout_flag": True,
            "relative_index_is_not_search_volume": True,
            "verified_search_volume": 0,
            "growth_pct": eff_growth or 5000.0,
            "retention_ratio": 0.0,
            "right_hand_slope": 0.0,
            "jev_multiplier": 0.0,
            "recommended_action": "REQUIRE_VOLUME_CROSS_CHECK",
            "reason": (
                f"Relative Google Trends index ({relative_index_0_100}/100) with Breakout flag "
                "cannot be treated as search volume without Treg/GSC volume verification."
            ),
        }

    # 2. Multi-window / 5-Year Longitudinal Series Evaluation (Step 4)
    clean_series = [float(x) for x in (series or []) if x is not None]
    if len(clean_series) >= 3:
        peak_val = max(clean_series)
        peak_idx = clean_series.index(peak_val)
        start_val = clean_series[0]
        current_val = clean_series[-1]
        prev_val = clean_series[-2]
        retention_ratio = round(current_val / peak_val, 4) if peak_val > 0 else 0.0
        right_hand_slope = round(current_val - prev_val, 4)

        # Count local peaks for seasonality detection
        local_peaks = 0
        for idx in range(1, len(clean_series) - 1):
            if clean_series[idx] > clean_series[idx - 1] and clean_series[idx] >= clean_series[idx + 1]:
                if clean_series[idx] >= 0.60 * peak_val:
                    local_peaks += 1

        # Post-spike decay: peaked earlier and right-hand tail has collapsed below 45% of peak
        if peak_idx < len(clean_series) - 1 and retention_ratio < 0.45 and right_hand_slope <= 0.0:
            return {
                "classification": "POST_SPIKE_DECAY",
                "is_viable": False,
                "is_breakout_flag": breakout_flag,
                "relative_index_is_not_search_volume": True,
                "verified_search_volume": search_volume,
                "growth_pct": eff_growth,
                "retention_ratio": retention_ratio,
                "right_hand_slope": right_hand_slope,
                "jev_multiplier": 0.0,
                "recommended_action": "REJECT_POST_SPIKE_DECAY",
                "reason": (
                    f"5-year/multi-window trajectory peaked earlier (retention {retention_ratio:.2f} < 0.45, "
                    f"right-hand slope {right_hand_slope:.2f} <= 0); topic spiked briefly and is dying out."
                ),
            }

        has_seasonal_token = any(tok in q_clean for tok in SEASONAL_STATUTORY_MARKERS)
        if (local_peaks >= 2 or has_seasonal_token) and right_hand_slope > 0.0 and retention_ratio < 0.92:
            return {
                "classification": "SEASONAL_PRE_PEAK",
                "is_viable": True,
                "is_breakout_flag": breakout_flag,
                "relative_index_is_not_search_volume": True,
                "verified_search_volume": search_volume,
                "growth_pct": eff_growth,
                "retention_ratio": retention_ratio,
                "right_hand_slope": right_hand_slope,
                "jev_multiplier": 1.15,
                "recommended_action": "PRIORITIZE_PRE_PEAK_PUBLISH",
                "reason": (
                    f"Recurring seasonal/statutory trajectory ramping pre-peak "
                    f"(right-hand slope +{right_hand_slope:.2f}, retention {retention_ratio:.2f})."
                ),
            }

        if retention_ratio >= 0.65 and current_val >= start_val and right_hand_slope >= -0.05 * max(1.0, peak_val):
            return {
                "classification": "SUSTAINED_GROWTH",
                "is_viable": True,
                "is_breakout_flag": breakout_flag,
                "relative_index_is_not_search_volume": True,
                "verified_search_volume": search_volume,
                "growth_pct": eff_growth,
                "retention_ratio": retention_ratio,
                "right_hand_slope": right_hand_slope,
                "jev_multiplier": 1.20,
                "recommended_action": "APPROVE_SUSTAINED_GROWTH",
                "reason": (
                    f"Sustained multi-window upward trajectory (retention {retention_ratio:.2f}, "
                    f"start {start_val:.1f} -> current {current_val:.1f})."
                ),
            }

    # 3. Default trajectory evaluation when multi-year series is not explicitly supplied
    if float(acceleration) > 0.0 and float(velocity) >= 15.0:
        return {
            "classification": "SUSTAINED_GROWTH",
            "is_viable": True,
            "is_breakout_flag": breakout_flag,
            "relative_index_is_not_search_volume": True,
            "verified_search_volume": search_volume,
            "growth_pct": eff_growth,
            "retention_ratio": 1.0,
            "right_hand_slope": float(acceleration),
            "jev_multiplier": 1.0,
            "recommended_action": "APPROVE_SUSTAINED_GROWTH",
            "reason": "Positive velocity and second-derivative acceleration confirm active inflection.",
        }

    return {
        "classification": "STEADY_BASELINE",
        "is_viable": True,
        "is_breakout_flag": breakout_flag,
        "relative_index_is_not_search_volume": True,
        "verified_search_volume": search_volume,
        "growth_pct": eff_growth,
        "retention_ratio": 1.0,
        "right_hand_slope": float(acceleration),
        "jev_multiplier": 1.0,
        "recommended_action": "EVALUATE_STANDARD_JEV",
        "reason": "Standard baseline trajectory.",
    }


class NoiseFilter:
    """
    Filters raw breakout spikes, rejecting transient chatter and decelerating news.
    Enforces HWL-1215 discrete second-derivative acceleration and z-score thresholds.
    """

    def __init__(
        self,
        min_tokens: int = 2,
        max_tokens: int = 8,
        min_chars: int = 6,
        max_chars: int = 80,
        min_z_score: float = 1.5,
        stoplist: Optional[List[str]] = None,
    ):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.min_z_score = min_z_score
        self.stoplist = stoplist or DEFAULT_STOPLIST

    def evaluate_spike(
        self,
        spike: FeedSpike,
        search_volume: int = 0,
    ) -> Tuple[bool, str, TrendCandidate]:
        """
        Evaluates a raw feed spike.
        Returns (passes, rejection_reason, candidate).
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(spike.query, "NoiseFilter.evaluate_spike.query")
        clean_q = spike.query.strip()
        slug = sanitize_url_slug(clean_q)
        tokens = [t for t in re.split(r"\s+", clean_q) if t]
        token_count = len(tokens)
        char_count = len(clean_q)
        intent = classify_intent_cluster(clean_q)

        # 1. Token bounds
        if token_count < self.min_tokens:
            reason = f"Token count ({token_count}) below minimum threshold ({self.min_tokens})"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata={"rejection_reason": reason},
            )
            return False, reason, cand

        if token_count > self.max_tokens:
            reason = f"Token count ({token_count}) exceeds maximum threshold ({self.max_tokens})"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata={"rejection_reason": reason},
            )
            return False, reason, cand

        # 2. Character bounds
        if char_count < self.min_chars or char_count > self.max_chars:
            reason = f"Character length ({char_count}) outside permitted range [{self.min_chars}, {self.max_chars}]"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata={"rejection_reason": reason},
            )
            return False, reason, cand

        # 3. Stoplist & transient noise rejection
        if is_transient_noise_text(clean_q, self.stoplist):
            reason = "Classified as transient chatter or ephemeral entertainment gossip"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata={"rejection_reason": reason},
            )
            return False, reason, cand

        # 4. Z-score anomaly rupture filter
        if spike.z_score < self.min_z_score:
            reason = f"Z-score ({spike.z_score:.2f}) below anomaly rupture threshold ({self.min_z_score})"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=False,
                qualification_status="FILTERED_NOISE",
                metadata={"rejection_reason": reason},
            )
            return False, reason, cand

        # 5. Discrete second-derivative acceleration gate (HWL-1215)
        # Decelerating spikes (A_t <= 0) are rejected unless established baseline volume >= 1000 exists
        if spike.acceleration <= 0.0 and search_volume < 1000:
            reason = f"Decelerating spike (acceleration {spike.acceleration:.2f} <= 0) without baseline volume >= 1000 per HWL-1215"
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata={**(spike.raw_payload or {}), "rejection_reason": reason},
            )
            return False, reason, cand

        # 6. Multi-window 5-year longitudinal trajectory & Breakout low-baseline check
        cand_meta = dict(spike.raw_payload or {})
        raw_series = cand_meta.get("longitudinal_series") or cand_meta.get("five_year_series")
        known_vol: Optional[int] = int(search_volume) if search_volume > 0 else cand_meta.get("verified_search_volume")
        traj_eval = classify_longitudinal_trajectory(
            query=clean_q,
            series=raw_series if isinstance(raw_series, list) else None,
            velocity=spike.velocity,
            acceleration=spike.acceleration,
            search_volume=int(known_vol) if known_vol is not None else None,
            growth_pct=cand_meta.get("growth_pct"),
            is_breakout=bool(cand_meta.get("is_breakout", False)),
            cpc_usd=float(cand_meta.get("cpc_usd", 0.0) or 0.0),
            intent_cluster=intent,
            relative_index_0_100=cand_meta.get("relative_index_0_100"),
        )
        cand_meta["trajectory_classification"] = traj_eval
        if traj_eval["classification"] == "POST_SPIKE_DECAY":
            reason = str(traj_eval["reason"])
            cand_meta["rejection_reason"] = reason
            cand = TrendCandidate(
                id=spike.id,
                query=clean_q,
                slug=slug,
                source=spike.source,
                discovered_at=spike.detected_at,
                velocity=spike.velocity,
                acceleration=spike.acceleration,
                z_score=spike.z_score,
                intent_cluster=intent,
                is_transient_noise=True,
                qualification_status="FILTERED_NOISE",
                metadata=cand_meta,
            )
            return False, reason, cand

        # Candidate passed all filters
        cand_meta.update({"token_count": token_count, "char_count": char_count})
        cand = TrendCandidate(
            id=spike.id,
            query=clean_q,
            slug=slug,
            source=spike.source,
            discovered_at=spike.detected_at,
            velocity=spike.velocity,
            acceleration=spike.acceleration,
            z_score=spike.z_score,
            intent_cluster=intent,
            is_transient_noise=False,
            qualification_status="PENDING_TREG",
            metadata=cand_meta,
        )
        return True, "Passed noise and acceleration filters", cand
