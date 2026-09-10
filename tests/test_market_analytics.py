from __future__ import annotations

import math
import statistics

import pytest

from shared.market_analytics import annualized_sample_volatility, relative_change


def test_relative_change_known_answers() -> None:
    assert relative_change(110.0, 100.0) == pytest.approx(0.10)
    assert relative_change(90.0, 100.0) == pytest.approx(-0.10)
    assert relative_change(100.0, None) is None
    assert relative_change(100.0, 0.0) is None


def test_annualized_volatility_matches_sample_standard_deviation() -> None:
    returns = [value / 1000 for value in range(-10, 10)]

    actual = annualized_sample_volatility(returns)

    assert actual == pytest.approx(statistics.stdev(returns) * math.sqrt(252))


def test_annualized_volatility_requires_full_window() -> None:
    assert annualized_sample_volatility([0.01] * 19) is None
