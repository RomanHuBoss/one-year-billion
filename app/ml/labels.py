from __future__ import annotations
import pandas as pd


def label_hit_2r_before_1r(prices: pd.Series, entry: float, stop: float, side: str) -> int:
    r = abs(entry - stop)
    if r <= 0:
        raise ValueError('invalid R')
    sign = 1 if side.upper() == 'BUY' else -1
    tp = entry + sign * 2 * r
    sl = entry - sign * 1 * r
    for _, price in prices.items():
        if sign * (price - tp) >= 0:
            return 1
        if sign * (price - sl) <= 0:
            return 0
    return 0
