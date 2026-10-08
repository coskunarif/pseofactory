"""
pseofactory Ingestion Noise Filtering & Mathematical Acceleration Gating
Enforces token bounds, stoplist rejection, z-score rupture thresholding, and HWL-1215 second-derivative acceleration.
Zero em-dashes. Zero en-dashes.
"""

import re
from typing import Tuple, List, Optional
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

        # Candidate passed all filters
        cand_meta = dict(spike.raw_payload or {})
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
