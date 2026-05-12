import pandas as pd
import pytest

from app.ml.labels import label_ohlc_hit_2r_before_1r
from app.ml.training_pipeline import validate_leakage_safe_frame


def test_same_bar_tp_sl_ambiguity_is_conservative_loss():
    bars = pd.DataFrame([{'high': 122.0, 'low': 98.0}])
    assert label_ohlc_hit_2r_before_1r(bars, entry=100.0, stop=99.0, side='BUY') == 0


def test_same_bar_tp_sl_ambiguity_can_be_skipped():
    bars = pd.DataFrame([{'high': 122.0, 'low': 98.0}])
    assert label_ohlc_hit_2r_before_1r(bars, entry=100.0, stop=99.0, side='BUY', ambiguous_policy='skip') is None


def test_ml_training_rejects_unsorted_time_series():
    df = pd.DataFrame({
        'ts': pd.to_datetime(['2026-01-02', '2026-01-01']),
        'feature': [1.0, 2.0],
        'label': [0, 1],
    })
    with pytest.raises(ValueError, match='time_series_must_be_sorted'):
        validate_leakage_safe_frame(df, ['feature'], 'label')


def test_ml_training_rejects_future_named_feature():
    df = pd.DataFrame({
        'ts': pd.to_datetime(['2026-01-01', '2026-01-02']),
        'future_return': [1.0, 2.0],
        'label': [0, 1],
    })
    with pytest.raises(ValueError, match='future_or_label'):
        validate_leakage_safe_frame(df, ['future_return'], 'label')


def test_ml_training_rejects_feature_timestamp_after_decision():
    df = pd.DataFrame({
        'ts': pd.to_datetime(['2026-01-01']),
        'feature_ts': pd.to_datetime(['2026-01-02']),
        'decision_ts': pd.to_datetime(['2026-01-01']),
        'feature': [1.0],
        'label': [0],
    })
    with pytest.raises(ValueError, match='feature_timestamp_after_decision'):
        validate_leakage_safe_frame(df, ['feature'], 'label')
