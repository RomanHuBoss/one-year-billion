from app.ml.inference import MLGate
from app.schemas.domain import Side, SignalCandidate, MLVerdictType


def test_missing_model_blocks_ml_required_strategy():
    signal = SignalCandidate(signal_id='s1', strategy='breakout', symbol='BTCUSDT', side=Side.BUY, entry_price=1, stop_price=.99, invalidator='x', expected_gross_edge_bps=10, trace_id='t', strategy_version='1', feature_hash='fh', requires_ml=True)
    verdict = MLGate().evaluate(signal)
    assert verdict.verdict == MLVerdictType.UNAVAILABLE
    assert verdict.block is True
