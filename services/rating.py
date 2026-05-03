"""Multi-source rating aggregation.

Each source stores its own raw {score, scale, fetched_at}. We aggregate to a 0~5 score
using the configured weights, normalising on whichever sources are present.
"""
from __future__ import annotations
from typing import Optional

from config import RATING_WEIGHTS


def _normalise_to_0_5(score: float, scale: float) -> Optional[float]:
    if score is None or scale is None or scale <= 0:
        return None
    if score <= 0:
        return None
    return float(score) * 5.0 / float(scale)


def aggregate(sources: dict) -> Optional[float]:
    """Return weighted 0-5 score; None if nothing usable."""
    if not sources:
        return None
    weighted_sum = 0.0
    weight_total = 0.0
    for key, source in sources.items():
        if not source:
            continue
        w = RATING_WEIGHTS.get(key, 0.0)
        if w <= 0:
            continue
        norm = _normalise_to_0_5(source.get("score"), source.get("scale"))
        if norm is None:
            continue
        weighted_sum += norm * w
        weight_total += w
    if weight_total <= 0:
        return None
    return round(weighted_sum / weight_total, 2)


def star_tag_value(score: Optional[float]) -> Optional[str]:
    """Round to nearest 0.5 for the 星級- tag."""
    if score is None:
        return None
    half = round(score * 2) / 2
    return f"星級-{half:.1f}"
