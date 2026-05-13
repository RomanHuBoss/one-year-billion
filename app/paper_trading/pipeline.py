from __future__ import annotations
from app.regime.classifier import RegimeClassifier
from app.strategies.orchestrator import StrategyOrchestrator
from app.ml.inference import MLGate
from app.risk_engine.approval import RiskConfig, approve_signal
from app.risk_engine.cost_model import CostModel
from app.execution.order_router import OrderRouter
from app.services.demo_state import DemoState
from app.config.phase_validator import validate_symbol_for_phase, validate_strategy_for_phase


class PaperPipeline:
    def __init__(self, state: DemoState, allow_demo_ml: bool = False, runtime_config=None):
        self.state = state
        self.runtime_config = runtime_config
        self.regime = RegimeClassifier()
        self.strategies = StrategyOrchestrator(include_shadow=True)
        self.ml = MLGate(allow_demo_ml=allow_demo_ml)
        self.router = OrderRouter()

    @property
    def risk_config(self) -> RiskConfig:
        return self.runtime_config.risk if self.runtime_config else RiskConfig()

    @property
    def cost_model(self) -> CostModel:
        return self.runtime_config.costs if self.runtime_config else CostModel()

    def run_once(self) -> dict:
        decisions = []
        phase = self.runtime_config.phase if self.runtime_config else self.state.account.phase
        live_universe = self.runtime_config.live_universe if self.runtime_config else tuple(self.state.symbols)
        live_strategies = self.runtime_config.live_strategies if self.runtime_config else ('breakout', 'micro_grid')
        shadow_strategies = self.runtime_config.shadow_strategies if self.runtime_config else ('carry_shadow', 'statarb_shadow')
        for symbol in self.state.symbols:
            symbol_check = validate_symbol_for_phase(symbol, phase, live_universe)
            if not symbol_check.allowed:
                decisions.append({'symbol': symbol, 'status': 'blocked', 'reasons': symbol_check.reasons})
                continue
            market = self.state.market.get(symbol)
            specs = self.state.specs.get(symbol)
            account = self.state.account
            if market is None or specs is None:
                decisions.append({'symbol': symbol, 'status': 'blocked', 'reasons': ['symbol_runtime_data_missing']})
                continue
            reg = self.regime.classify(market, account)
            proposed = self.strategies.propose(market, account, reg)
            if not proposed:
                decisions.append({'symbol': symbol, 'status': 'no_trade', 'regime': reg.model_dump(mode='json'), 'reasons': ['no_candidate_after_regime_permissions']})
                continue
            for cand in proposed:
                if cand.shadow_only:
                    if cand.strategy not in shadow_strategies:
                        decisions.append({'symbol': symbol, 'strategy': cand.strategy, 'status': 'blocked', 'reasons': ['shadow_strategy_not_in_config']})
                        continue
                    decisions.append({
                        'symbol': symbol,
                        'strategy': cand.strategy,
                        'status': 'shadow_signal',
                        'candidate': cand.model_dump(mode='json'),
                        'reasons': ['shadow_only_no_live_execution_path'],
                    })
                    continue
                strategy_check = validate_strategy_for_phase(cand.strategy, phase, live_strategies, shadow_strategies)
                if not strategy_check.allowed:
                    decisions.append({'symbol': symbol, 'strategy': cand.strategy, 'status': 'blocked', 'reasons': strategy_check.reasons})
                    break
                ml = self.ml.evaluate(cand)
                risk = approve_signal(cand, ml, account, market, specs, self.risk_config, self.cost_model)
                # Paper endpoint тоже возвращает готовый backend-status.
                # Frontend не должен выводить статус из risk.approved локально: даже
                # smoke-резюме должно оставаться отображением backend-contract.
                row = {
                    'symbol': symbol,
                    'strategy': cand.strategy,
                    'status': 'risk_approved' if risk.approved else 'risk_rejected',
                    'reasons': [] if risk.approved else list(risk.reasons),
                    'ml': ml.model_dump(),
                    'risk': risk.model_dump(mode='json'),
                }
                if risk.approved:
                    row['order_intent'] = self.router.build_intent(cand, risk, f'paper-{cand.signal_id}').model_dump(mode='json')
                decisions.append(row)
                break
        return {'mode': 'paper', 'decisions': decisions, 'config_hash': self.runtime_config.config_hash if self.runtime_config else 'default-config'}
