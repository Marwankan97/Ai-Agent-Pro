from __future__ import annotations

import math
import pytest

from pro_agent.models import Bar


@pytest.fixture
def synthetic_bars():
    def build(n=260, trend=0.0015, wobble=0.012):
        rows = []
        price = 20_000.0
        start = 1_700_000_000 // 86_400 * 86_400
        for i in range(n):
            previous = price
            price *= math.exp(trend + wobble * math.sin(i / 5.0))
            open_price = previous
            close = price
            high = max(open_price, close) * 1.002
            low = min(open_price, close) * 0.998
            rows.append(Bar(start + i * 86_400, open_price, high, low, close, 10.0 + i))
        return rows
    return build
