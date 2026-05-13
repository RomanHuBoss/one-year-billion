from __future__ import annotations
from typing import Any

FORBIDDEN_TERMS = {'martingale', 'dca', 'spot_grid', 'inverse_futures', 'options', 'copy_trading', 'signal_bot', 'portfolio_bot', 'frontend_keys'}


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
    for field in (
        'maker_fee_bps', 'taker_fee_bps', 'slippage_buffer_bps',
        'funding_buffer_bps', 'safety_buffer_bps', 'max_spread_bps',
        'min_depth_usdt', 'reserve_cash_pct', 'min_liq_distance_pct',
    ):
        if field in risk and float(risk.get(field, 0)) < 0:
            reasons.append(f'{field}_must_be_nonnegative')
    if float(risk.get('max_effective_leverage', 0)) <= 0:
        reasons.append('max_effective_leverage_must_be_positive')

    # Phase 0 — самый уязвимый контур малого счета. Верхние лимиты должны
    # проверяться валидатором конфига, а не оставаться только текстом в README.
    phase = int(account.get('phase', 0))
    if phase <= 0:
        if float(risk.get('risk_pct_default', account.get('risk_pct_default', 0))) > 0.015:
            reasons.append('phase0_risk_default_above_1_5pct')
        if float(risk.get('risk_pct_absolute_max', account.get('risk_pct_absolute_max', 0.015))) > 0.015:
            reasons.append('phase0_risk_absolute_above_1_5pct')
        if float(risk.get('max_effective_leverage', account.get('max_effective_leverage', 0))) > 3.0:
            reasons.append('phase0_default_leverage_above_3x')
        if float(risk.get('max_effective_leverage_absolute', account.get('max_effective_leverage_absolute', 5.0))) > 5.0:
            reasons.append('phase0_absolute_leverage_above_5x')
        if int(risk.get('turnover_round_turns_per_day', 4)) > 4:
            reasons.append('phase0_turnover_above_4_round_turns_per_day')

    live = {str(x).lower() for x in account.get('live_strategies', [])}
    if live & FORBIDDEN_TERMS:
        reasons.append('forbidden_strategy_in_live_permissions')
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
