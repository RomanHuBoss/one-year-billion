from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.config.loader import load_project_config
from app.config.validator import validate_config
from app.risk_engine.approval import RiskConfig
from app.risk_engine.cost_model import CostModel


@dataclass(frozen=True)
class RuntimeConfig:
    """Проверенный runtime-конфиг, используемый backend как единый источник policy."""

    raw: dict[str, Any]
    config_hash: str
    phase: int
    live_universe: tuple[str, ...]
    live_strategies: tuple[str, ...]
    shadow_strategies: tuple[str, ...]
    risk: RiskConfig
    costs: CostModel


def _as_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(str(x).upper() if str(x).endswith('USDT') else str(x) for x in value)


def build_runtime_config(raw: dict[str, Any] | None = None) -> RuntimeConfig:
    """Загружает YAML, валидирует запреты спецификации и собирает typed config."""

    cfg = raw or load_project_config()
    validate_config(cfg)
    account = cfg.get('account_phase.yaml', {})
    risk_yaml = cfg.get('risk.yaml', {})
    config_hash = str(cfg.get('config_hash', 'unknown-config'))

    risk = RiskConfig(
        risk_pct_default=float(risk_yaml.get('risk_pct_default', account.get('risk_pct_default', 0.01))),
        max_effective_leverage=float(risk_yaml.get('max_effective_leverage', account.get('max_effective_leverage', 3.0))),
        reserve_cash_pct=float(risk_yaml.get('reserve_cash_pct', 0.20)),
        approval_ttl_seconds=int(risk_yaml.get('approval_ttl_seconds', 60)),
        min_liq_distance_pct=float(risk_yaml.get('min_liq_distance_pct', 0.05)),
        max_spread_bps=float(risk_yaml.get('max_spread_bps', 8.0)),
        min_depth_usdt=float(risk_yaml.get('min_depth_usdt', 1_000_000)),
        min_net_edge_bps=float(risk_yaml.get('min_net_edge_bps', 2.0)),
        config_hash=config_hash,
    )
    costs = CostModel(
        maker_fee_bps=float(risk_yaml.get('maker_fee_bps', 2.0)),
        taker_fee_bps=float(risk_yaml.get('taker_fee_bps', 5.5)),
        slippage_buffer_bps=float(risk_yaml.get('slippage_buffer_bps', 2.0)),
        funding_buffer_bps=float(risk_yaml.get('funding_buffer_bps', 1.0)),
        safety_buffer_bps=float(risk_yaml.get('safety_buffer_bps', 2.0)),
    )
    return RuntimeConfig(
        raw=cfg,
        config_hash=config_hash,
        phase=int(account.get('phase', 0)),
        live_universe=_as_tuple(account.get('live_universe', ())),
        live_strategies=tuple(str(x) for x in account.get('live_strategies', ())),
        shadow_strategies=tuple(str(x) for x in account.get('shadow_strategies', ())),
        risk=risk,
        costs=costs,
    )
