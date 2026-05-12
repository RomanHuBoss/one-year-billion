from __future__ import annotations
from typing import Any

FORBIDDEN_TERMS = {'martingale', 'dca', 'spot_grid', 'inverse_futures', 'options', 'frontend_keys'}


class ConfigValidationError(ValueError):
    pass


def validate_config(cfg: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    system = cfg.get('system.yaml', {})
    account = cfg.get('account_phase.yaml', {})
    risk = cfg.get('risk.yaml', {})

    scope = system.get('exchange_scope', {})
    if scope.get('category') != 'linear' or scope.get('quote') != 'USDT':
        reasons.append('exchange_scope_must_be_bybit_linear_usdt')
    if not scope.get('forbid_spot', True) or not scope.get('forbid_inverse', True) or not scope.get('forbid_options', True):
        reasons.append('forbidden_exchange_scope_enabled')
    if system.get('frontend', {}).get('store_secrets') is not False:
        reasons.append('frontend_secrets_forbidden')
    if risk.get('recovery_can_increase_risk') is not False:
        reasons.append('recovery_risk_increase_forbidden')
    if float(risk.get('risk_pct_default', 0)) <= 0:
        reasons.append('risk_pct_default_must_be_positive')
    if float(risk.get('risk_pct_default', 0)) > float(risk.get('risk_pct_absolute_max', risk.get('risk_pct_default', 0))):
        reasons.append('risk_default_above_absolute_max')
    if float(risk.get('max_effective_leverage', 0)) > float(risk.get('max_effective_leverage_absolute', risk.get('max_effective_leverage', 0))):
        reasons.append('leverage_default_above_absolute_max')
    if float(risk.get('min_net_edge_bps', 0)) <= 0:
        reasons.append('min_net_edge_must_be_positive')
    live = set(account.get('live_strategies', []))
    if live & FORBIDDEN_TERMS:
        reasons.append('forbidden_strategy_in_live_permissions')
    phase = int(account.get('phase', 0))
    universe = {str(x).upper() for x in account.get('live_universe', [])}
    if phase <= 1 and ({'carry_live','statarb_live'} & live):
        reasons.append('carry_statarb_live_forbidden_phase_0_1')
    if phase <= 0 and universe - {'BTCUSDT', 'ETHUSDT', 'SOLUSDT'}:
        reasons.append('phase0_universe_too_wide')
    if not account.get('manual_override_reduce_only', False):
        reasons.append('manual_override_must_be_reduce_only')
    if reasons:
        raise ConfigValidationError(';'.join(reasons))
    return reasons
