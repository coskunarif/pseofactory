"""
pseofactory trends: Automated Real-Time Trend Monitoring & Jev Decision Subsystem
Zero em-dashes. Zero en-dashes.
"""

from pseofactory.trends.models import (
    FeedSpike,
    TrendCandidate,
    TregDurabilityResult,
    JevDecisionResult,
)
from pseofactory.trends.collectors import (
    BaseSuggestCollector,
    GoogleSuggestCollector,
    YouTubeSuggestCollector,
    RedditSuggestCollector,
    HackerNewsCollector,
    GoogleTrendsRSSCollector,
    MultiSourceCollector,
)
from pseofactory.trends.filters import (
    NoiseFilter,
    calculate_second_derivative_acceleration,
    calculate_z_score,
    is_transient_noise_text,
    classify_intent_cluster,
)
from pseofactory.trends.treg_checker import (
    TregChecker,
)
from pseofactory.trends.jev_engine import (
    JevEngine,
)
from pseofactory.trends.pipeline import (
    TrendPipeline,
    run_trend_pipeline,
)

__all__ = [
    "FeedSpike",
    "TrendCandidate",
    "TregDurabilityResult",
    "JevDecisionResult",
    "BaseSuggestCollector",
    "GoogleSuggestCollector",
    "YouTubeSuggestCollector",
    "RedditSuggestCollector",
    "HackerNewsCollector",
    "GoogleTrendsRSSCollector",
    "MultiSourceCollector",
    "NoiseFilter",
    "calculate_second_derivative_acceleration",
    "calculate_z_score",
    "is_transient_noise_text",
    "classify_intent_cluster",
    "TregChecker",
    "JevEngine",
    "TrendPipeline",
    "run_trend_pipeline",
]
