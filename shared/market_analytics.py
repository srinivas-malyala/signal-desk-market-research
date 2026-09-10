"""Pure reference calculations used by local known-answer analytics tests."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

TRADING_DAYS_PER_YEAR = 252


def relative_change(current: float, previous: float | None) -> float | None:
    """Return a decimal change, matching Gold's current / previous - 1 formula."""
    if previous is None or previous <= 0:
        return None
    return current / previous - 1.0


def annualized_sample_volatility(
    daily_returns: Sequence[float | None],
    *,
    required_observations: int = 20,
) -> float | None:
    """Return sample volatility annualized by sqrt(252) for a complete window."""
    values = [value for value in daily_returns if value is not None]
    if len(daily_returns) != required_observations or len(values) < 2:
        return None
    return statistics.stdev(values) * math.sqrt(TRADING_DAYS_PER_YEAR)
