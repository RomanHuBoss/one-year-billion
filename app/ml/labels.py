from __future__ import annotations
from typing import Literal
import pandas as pd


AmbiguousPolicy = Literal['conservative_sl', 'skip']


def label_hit_2r_before_1r(prices: pd.Series, entry: float, stop: float, side: str) -> int:
    """Close-only fallback label.

    Для production-меток предпочтителен label_ohlc_hit_2r_before_1r(): close-only
    ряд не видит same-bar TP/SL ambiguity и годится только для грубых smoke tests.
    """

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


def label_ohlc_hit_2r_before_1r(
    bars: pd.DataFrame,
    entry: float,
    stop: float,
    side: str,
    *,
    high_col: str = 'high',
    low_col: str = 'low',
    ambiguous_policy: AmbiguousPolicy = 'conservative_sl',
) -> int | None:
    """Leakage-safe label: +2R раньше -1R по закрытым будущим барам.

    Если TP и SL достижимы в одном и том же баре, порядок внутри бара неизвестен.
    По умолчанию применяется консервативная политика: считать SL, а не прибыль.
    Это исключает оптимистичное смещение backtest/ML labels.
    """

    r = abs(entry - stop)
    if r <= 0:
        raise ValueError('invalid R')
    if high_col not in bars.columns or low_col not in bars.columns:
        raise ValueError('ohlc_high_low_required')
    side = side.upper()
    if side not in {'BUY', 'SELL'}:
        raise ValueError('side_must_be_buy_or_sell')

    if side == 'BUY':
        tp = entry + 2 * r
        sl = entry - r
        for _, row in bars.iterrows():
            hit_tp = float(row[high_col]) >= tp
            hit_sl = float(row[low_col]) <= sl
            if hit_tp and hit_sl:
                return 0 if ambiguous_policy == 'conservative_sl' else None
            if hit_tp:
                return 1
            if hit_sl:
                return 0
    else:
        tp = entry - 2 * r
        sl = entry + r
        for _, row in bars.iterrows():
            hit_tp = float(row[low_col]) <= tp
            hit_sl = float(row[high_col]) >= sl
            if hit_tp and hit_sl:
                return 0 if ambiguous_policy == 'conservative_sl' else None
            if hit_tp:
                return 1
            if hit_sl:
                return 0
    return 0
