from __future__ import annotations
from app.schemas.domain import MLVerdict, MLVerdictType, SignalCandidate
from app.ml.model_registry import ModelRegistry


class MLGate:
    def __init__(self, registry: ModelRegistry | None = None, allow_demo_ml: bool = False):
        self.registry = registry or ModelRegistry()
        self.allow_demo_ml = allow_demo_ml

    def evaluate(self, candidate: SignalCandidate) -> MLVerdict:
        if not candidate.requires_ml:
            return MLVerdict(verdict=MLVerdictType.ALLOW, required=False, block=False, reason='ml_not_required')
        model = self.registry.latest(candidate.strategy)
        if model is None:
            if self.allow_demo_ml:
                return MLVerdict(verdict=MLVerdictType.ALLOW, required=True, block=False, reason='demo_ml_override', p_hit_2r=0.55, uncertainty=0.25, model_id='demo')
            return MLVerdict(verdict=MLVerdictType.UNAVAILABLE, required=True, block=True, reason='missing_model')
        if not model.fresh:
            return MLVerdict(verdict=MLVerdictType.BLOCK, required=True, block=True, reason='stale_model', model_id=model.model_id)
        if not model.calibration_pass:
            return MLVerdict(verdict=MLVerdictType.BLOCK, required=True, block=True, reason='calibration_failure', model_id=model.model_id)
        if not model.drift_pass:
            return MLVerdict(verdict=MLVerdictType.BLOCK, required=True, block=True, reason='drift_psi_breach', model_id=model.model_id)
        # The actual estimator load is intentionally behind metadata gates.
        return MLVerdict(verdict=MLVerdictType.ALLOW, required=True, block=False, reason='model_health_pass', p_hit_2r=0.51, uncertainty=0.30, model_id=model.model_id, feature_schema_hash=model.feature_schema_hash)
