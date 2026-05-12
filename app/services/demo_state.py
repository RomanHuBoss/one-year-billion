from __future__ import annotations
from datetime import timedelta
from app.core.hashes import new_trace_id
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, EffectiveStatus


class DemoState:
    """In-memory состояние для локального smoke-test, если PostgreSQL еще не поднят."""

    def __init__(self, symbols: tuple[str, ...] | list[str] | None = None, phase: int = 0):
        now = utc_now()
        self.symbols = [s.upper() for s in (symbols or ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'))]
        self.account = AccountSnapshot(
            equity_usdt=500, available_balance_usdt=500, phase=phase, account_mode='demo_runtime_checked',
            fetched_at=now, expires_at=now + timedelta(minutes=5)
        )
        all_specs = {
            'BTCUSDT': InstrumentSpec(symbol='BTCUSDT', tick_size=0.1, qty_step=0.001, min_qty=0.001, min_notional=5, max_leverage=100, specs_version='demo-v1', fetched_at=now, expires_at=now + timedelta(minutes=10)),
            'ETHUSDT': InstrumentSpec(symbol='ETHUSDT', tick_size=0.01, qty_step=0.01, min_qty=0.01, min_notional=5, max_leverage=100, specs_version='demo-v1', fetched_at=now, expires_at=now + timedelta(minutes=10)),
            'SOLUSDT': InstrumentSpec(symbol='SOLUSDT', tick_size=0.001, qty_step=0.1, min_qty=0.1, min_notional=5, max_leverage=75, specs_version='demo-v1', fetched_at=now, expires_at=now + timedelta(minutes=10)),
        }
        all_market = {
            'BTCUSDT': MarketSnapshot(symbol='BTCUSDT', bid1=100000, ask1=100001, spread_bps=0.10, depth_usdt=5_000_000, atr_pct=0.015, volume_z=2.2, btc_aligned=True, fetched_at=now, expires_at=now + timedelta(seconds=20)),
            'ETHUSDT': MarketSnapshot(symbol='ETHUSDT', bid1=3000, ask1=3000.5, spread_bps=1.67, depth_usdt=2_000_000, atr_pct=0.012, volume_z=1.0, btc_aligned=True, fetched_at=now, expires_at=now + timedelta(seconds=20)),
            'SOLUSDT': MarketSnapshot(symbol='SOLUSDT', bid1=150, ask1=150.02, spread_bps=1.33, depth_usdt=1_000_000, atr_pct=0.020, volume_z=0.8, btc_aligned=True, fetched_at=now, expires_at=now + timedelta(seconds=20)),
        }
        self.specs = {s: all_specs[s] for s in self.symbols if s in all_specs}
        self.market = {s: all_market[s] for s in self.symbols if s in all_market}
        self.incidents: list[dict] = []
        self.manual_actions: list[dict] = []

    def overview(self) -> list[dict]:
        now = utc_now()
        rows = []
        for symbol in self.symbols:
            reasons: list[str] = []
            status = EffectiveStatus.NO_TRADE.value
            severity = 'info'
            specs = self.specs.get(symbol)
            market = self.market.get(symbol)
            if specs is None:
                status = EffectiveStatus.BLOCKED.value
                reasons.append('missing_instrument_specs')
                severity = 'high'
            elif not specs.fresh:
                status = EffectiveStatus.BLOCKED.value
                reasons.append('stale_instrument_specs')
                severity = 'high'
            elif market is None:
                status = EffectiveStatus.NO_TRADE.value
                reasons.append('missing_market_snapshot')
                severity = 'medium'
            elif not market.fresh:
                status = EffectiveStatus.NO_TRADE.value
                reasons.append('stale_market')
                severity = 'medium'
            else:
                reasons.append('waiting_for_risk_approved_signal')
            rows.append({
                'symbol': symbol,
                'status_effective': status,
                'severity': severity,
                'reasons': reasons,
                'trace_id': new_trace_id(symbol.lower()),
                'allowed_actions': ['DISABLE_TRADING','CANCEL_OPEN_ENTRIES','FLATTEN_REDUCE'],
                'updated_at': now,
            })
        return rows
