from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from app.core.hashes import hash_payload

CONFIG_ROOT = Path('config')


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data


def load_project_config() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for name in ('account_phase.yaml', 'risk.yaml', 'strategy_permissions.yaml', 'system.yaml'):
        merged[name] = load_yaml(CONFIG_ROOT / name)
    merged['config_hash'] = hash_payload(merged)
    return merged
