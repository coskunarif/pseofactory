"""
Tests for pseofactory trend noise suppression and acceleration filters.
Enforces HWL-1215 discrete acceleration gating, stoplist rejection, token bounds, and z-score thresholds.
Zero em-dashes. Zero en-dashes.
"""

from pseofactory.trends.models import FeedSpike
from pseofactory.trends.filters import (
    NoiseFilter,
    calculate_second_derivative_acceleration,
    calculate_z_score,
    is_transient_noise_text,
    classify_intent_cluster,
)


def test_calculate_second_derivative_acceleration():
    """Verifies discrete second-derivative acceleration formula A_t = v_t - 2*v_{t-1} + v_{t-2}."""
    # Constant velocity -> acceleration = 0
    assert calculate_second_derivative_acceleration(10.0, 10.0, 10.0) == 0.0

    # Accelerating momentum: 10 -> 20 -> 35
    # A_t = 35 - 2*20 + 10 = 5.0 > 0
    assert calculate_second_derivative_acceleration(35.0, 20.0, 10.0) == 5.0

    # Decelerating news spike: 10 -> 40 -> 50
    # A_t = 50 - 2*40 + 10 = -20.0 < 0
    assert calculate_second_derivative_acceleration(50.0, 40.0, 10.0) == -20.0


def test_calculate_z_score():
    """Verifies statistical anomaly score calculation."""
    assert calculate_z_score(velocity=48.0, baseline_mean=6.2, baseline_std=1.8) > 20.0
    assert calculate_z_score(velocity=10.0, baseline_mean=10.0, baseline_std=2.0) == 0.0
    assert calculate_z_score(velocity=10.0, baseline_mean=5.0, baseline_std=0.0) == 0.0


def test_is_transient_noise_text():
    """Verifies detection of viral memes, entertainment rumours, and ephemeral news."""
    assert is_transient_noise_text("zendaya oscars dress designer 2026") is True
    assert is_transient_noise_text("hawk tuah soundboard remix generator") is True
    assert is_transient_noise_text("spacex starship launch scrubbed reasons today") is True
    assert is_transient_noise_text("super bowl halftime performer leak 2027") is True

    # Viable utility queries must not be flagged
    assert is_transient_noise_text("form 8829 home office deduction calculator 2026") is False
    assert is_transient_noise_text("section 179d clean energy deduction matrix") is False
    assert is_transient_noise_text("ai token usage cost estimator") is False


def test_classify_intent_cluster():
    """Verifies intent clustering across utility taxonomy."""
    assert classify_intent_cluster("form 8829 home office deduction calculator") in ("statutory_compliance", "calculator")
    assert classify_intent_cluster("section 179d commercial clean energy deduction matrix") == "statutory_compliance"
    assert classify_intent_cluster("openai vs anthropic token pricing comparison") == "comparison"
    assert classify_intent_cluster("json schema to pydantic converter tool") == "tool"
    assert classify_intent_cluster("what is a good credit score") == "informational"


def test_noise_filter_token_and_char_bounds():
    """Verifies token count (2-8) and character bounds (6-80)."""
    filter_engine = NoiseFilter()

    # Single token rejected
    spike_single = FeedSpike(
        id="single",
        query="calculator",
        source="google_suggest",
        velocity=50.0,
        acceleration=10.0,
        z_score=3.0,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_single)
    assert passes is False
    assert cand.qualification_status == "FILTERED_NOISE"
    assert "below minimum threshold" in reason

    # Too many tokens (> 8) rejected
    spike_long = FeedSpike(
        id="long",
        query="one two three four five six seven eight nine ten",
        source="google_suggest",
        velocity=50.0,
        acceleration=10.0,
        z_score=3.0,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_long)
    assert passes is False
    assert "exceeds maximum threshold" in reason

    # Too short in characters (< 6) rejected
    spike_short = FeedSpike(
        id="short",
        query="ab cd",
        source="google_suggest",
        velocity=50.0,
        acceleration=10.0,
        z_score=3.0,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_short)
    assert passes is False
    assert "outside permitted range" in reason


def test_noise_filter_stoplist_rejection():
    """Verifies stoplist rejects viral entertainment chatter."""
    filter_engine = NoiseFilter()
    spike_meme = FeedSpike(
        id="meme-01",
        query="hawk tuah soundboard remix generator",
        source="youtube_suggest",
        velocity=310.0,
        acceleration=-92.0,
        z_score=6.8,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_meme)
    assert passes is False
    assert cand.is_transient_noise is True
    assert cand.qualification_status == "FILTERED_NOISE"


def test_noise_filter_z_score_threshold():
    """Verifies low z-score spikes are rejected as background noise."""
    filter_engine = NoiseFilter(min_z_score=1.5)
    spike_low_z = FeedSpike(
        id="low-z",
        query="home office deduction rules",
        source="google_suggest",
        velocity=10.0,
        acceleration=2.0,
        z_score=1.1,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_low_z)
    assert passes is False
    assert "below anomaly rupture threshold" in reason


def test_second_derivative_acceleration_hwl_1215():
    """
    Enforces HWL-1215: Decelerating spikes (A_t <= 0) are rejected UNLESS
    established baseline search volume >= 1000 provides baseline support.
    """
    filter_engine = NoiseFilter()

    # Case 1: Decelerating without baseline volume -> REJECT
    spike_decel_no_vol = FeedSpike(
        id="decel-01",
        query="clean energy commercial matrix",
        source="google_suggest",
        velocity=80.0,
        acceleration=-4.5,
        z_score=3.0,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_decel_no_vol, search_volume=400)
    assert passes is False
    assert "Decelerating spike" in reason
    assert cand.qualification_status == "FILTERED_NOISE"

    # Case 2: Decelerating WITH baseline volume >= 1000 -> PASS
    passes, reason, cand = filter_engine.evaluate_spike(spike_decel_no_vol, search_volume=2500)
    assert passes is True
    assert cand.qualification_status == "PENDING_TREG"

    # Case 3: Positive acceleration (A_t > 0) -> PASS
    spike_surging = FeedSpike(
        id="surging-01",
        query="form 8829 deduction calculator",
        source="google_suggest",
        velocity=48.0,
        acceleration=14.5,
        z_score=3.8,
    )
    passes, reason, cand = filter_engine.evaluate_spike(spike_surging, search_volume=500)
    assert passes is True
    assert cand.qualification_status == "PENDING_TREG"
    assert cand.slug == "form-8829-deduction-calculator"
