from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from app.core.time import utc_now


@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    path: Path
    feature_schema_hash: str
    created_at: datetime
    expires_at: datetime
    calibration_pass: bool
    drift_pass: bool

    @property
    def fresh(self) -> bool:
        return self.expires_at > utc_now()


class ModelRegistry:
    def __init__(self, model_dir: str = 'models'):
        self.model_dir = Path(model_dir)

    def latest(self, strategy: str) -> ModelInfo | None:
        meta_path = self.model_dir / strategy / 'latest.json'
        if not meta_path.exists():
            return None
        import json
        data = json.loads(meta_path.read_text(encoding='utf-8'))
        return ModelInfo(
            model_id=data['model_id'], path=Path(data['path']), feature_schema_hash=data['feature_schema_hash'],
            created_at=datetime.fromisoformat(data['created_at']), expires_at=datetime.fromisoformat(data['expires_at']),
            calibration_pass=bool(data.get('calibration_pass')), drift_pass=bool(data.get('drift_pass')),
        )
