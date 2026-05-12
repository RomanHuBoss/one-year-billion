from __future__ import annotations
from dataclasses import dataclass
from typing import Any

PHASE0_SYMBOLS = {'BTCUSDT', 'ETHUSDT', 'SOLUSDT'}
SHADOW_ONLY_PHASE_0_1 = {'carry_live', 'statarb_live', 'carry', 'funding', 'funding_carry', 'pair_statarb', 'statarb', 'stat_arb'}
FORBIDDEN_STRATEGIES = {'martingale', 'dca', 'spot_grid', 'inverse_futures', 'options', 'copy_trading', 'signal_bot', 'portfolio_bot'}


@dataclass(frozen=True)
class PhaseCheck:
    allowed: bool
    reasons: list[str]


def validate_symbol_for_phase(symbol: str, phase: int, live_universe: tuple[str, ...]) -> PhaseCheck:
    """Проверяет, что symbol не шире разрешенного runtime-universe для фазы."""

    symbol = symbol.upper()
    reasons: list[str] = []
    if symbol not in {x.upper() for x in live_universe}:
        reasons.append('symbol_not_in_config_live_universe')
    if phase <= 0 and symbol not in PHASE0_SYMBOLS:
        reasons.append('phase0_symbol_requires_explicit_expansion_evidence')
    return PhaseCheck(not reasons, reasons)


def validate_strategy_for_phase(strategy: str, phase: int, live_strategies: tuple[str, ...], shadow_strategies: tuple[str, ...] = ()) -> PhaseCheck:
    """Запрещает live-маршрут для shadow/forbidden стратегий."""

    strategy = strategy.lower()
    live = {x.lower() for x in live_strategies}
    shadow = {x.lower() for x in shadow_strategies}
    reasons: list[str] = []
    if strategy in FORBIDDEN_STRATEGIES:
        reasons.append('strategy_forbidden_product_scope')
    if phase <= 1 and strategy in SHADOW_ONLY_PHASE_0_1:
        reasons.append('strategy_shadow_only_phase_0_1')
    if strategy not in live:
        if strategy in shadow or strategy.replace('_shadow', '_live') in SHADOW_ONLY_PHASE_0_1:
            reasons.append('strategy_has_no_live_route')
        else:
            reasons.append('strategy_not_in_live_permissions')
    return PhaseCheck(not reasons, reasons)


def startup_phase_validation(cfg: dict[str, Any]) -> list[str]:
    """Fail-fast проверки YAML-фазы при старте приложения."""

    account = cfg.get('account_phase.yaml', {})
    phase = int(account.get('phase', 0))
    universe = tuple(str(x).upper() for x in account.get('live_universe', ()))
    live = tuple(str(x).lower() for x in account.get('live_strategies', ()))
    shadow = tuple(str(x).lower() for x in account.get('shadow_strategies', ()))
    reasons: list[str] = []
    for symbol in universe:
        reasons.extend(validate_symbol_for_phase(symbol, phase, universe).reasons)
    for strategy in live:
        reasons.extend(validate_strategy_for_phase(strategy, phase, live, shadow).reasons)
    return sorted(set(reasons))
