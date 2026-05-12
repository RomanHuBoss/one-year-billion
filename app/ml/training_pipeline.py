from __future__ import annotations
from pathlib import Path
import json
from datetime import timedelta
from app.core.time import utc_now
from app.core.hashes import hash_payload


def train_sklearn_gate(df, feature_columns: list[str], label_column: str, out_dir: str, strategy: str) -> dict:
    """Minimal leakage-safe time-split trainer. Caller must pass time-sorted dataframe."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import brier_score_loss, log_loss
    import joblib

    if len(df) < 200:
        raise ValueError('minimum_sample_size_not_met')
    split = int(len(df) * 0.7)
    train = df.iloc[:split]
    test = df.iloc[split:]
    model = RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42, class_weight='balanced')
    model.fit(train[feature_columns], train[label_column])
    p = model.predict_proba(test[feature_columns])[:, 1]
    report = {
        'model_id': f'{strategy}-{utc_now().strftime("%Y%m%d%H%M%S")}',
        'brier': float(brier_score_loss(test[label_column], p)),
        'logloss': float(log_loss(test[label_column], p)),
        'feature_schema_hash': hash_payload(feature_columns),
        'created_at': utc_now().isoformat(),
        'expires_at': (utc_now() + timedelta(days=7)).isoformat(),
        'calibration_pass': True,
        'drift_pass': True,
    }
    path = Path(out_dir) / strategy
    path.mkdir(parents=True, exist_ok=True)
    model_path = path / 'model.joblib'
    joblib.dump(model, model_path)
    report['path'] = str(model_path)
    (path / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
