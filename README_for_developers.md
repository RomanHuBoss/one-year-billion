# README for developers

Обязательный порядок реализации и проверки сохранен по Sprint 1-9. Проект уже разложен по слоям:

- Sprint 1: `migrations/`, `app/market_data/`, `app/db/`.
- Sprint 2: `app/risk_engine/`, `app/api/routes/risk.py`.
- Sprint 3: `app/execution/`, `app/reconciliation/`.
- Sprint 4: `app/regime/`.
- Sprint 5: `app/strategies/`; стратегии возвращают только `SignalCandidate`.
- Sprint 6: `app/backtest/`.
- Sprint 7: `app/ml/`.
- Sprint 8: `app/api/`, `frontend/`.
- Sprint 9: `app/paper_trading/`, `app/reports/go_no_go.py`.

Перед любым live-режимом выполнить:

```bash
pytest -q
python scripts/check_strategy_imports.py
python scripts/secret_scan.py
python scripts/validate_project.py
```

`TRADING_ENABLED=false` и `BYBIT_LIVE_CONFIRM=false` — безопасные значения по умолчанию.


Новые runtime-gates:

- `app/config/runtime.py` загружает YAML, считает `config_hash` и передает RiskConfig/CostModel в risk/paper pipeline.
- `app/config/phase_validator.py` блокирует расширение Phase 0 за пределы BTC/ETH/SOL и запрещает live-route для carry/stat-arb в Phase 0/1.
- `/api/runtime/preflight` показывает безопасный scope, live-флаги, config_hash и stale/missing runtime inputs.
- `OrderRouter` держит per-symbol lock, чтобы retry/idempotency не увеличивали exposure.

## Live-gated revision notes

Live-submit реализован отдельным route `/api/execution/live-submit`, но он не является shortcut к бирже. Порядок проверки:

1. `validate_startup_security()` блокирует unsafe env.
2. `run_live_preflight()` подтверждает DB, Go/No-Go, unresolved incidents, Bybit public/private access and runtime instruments.
3. `Repository.verify_live_risk_decision()` проверяет, что risk decision реально сохранен в PostgreSQL, approved and non-expired.
4. `OrderRouter` строит deterministic orderLinkId and idempotent intent.
5. `Repository.persist_order_intent()` вставляет order в DB, где trigger повторно проверяет approved risk decision.
6. `BybitAdapter.place_order()` отправляет order только при `TRADING_ENABLED=true` + `BYBIT_LIVE_CONFIRM=true`.
7. HTTP ack не переводит позицию в ACTIVE; следующий обязательный контур — reconciliation + protection watchdog.

Нельзя добавлять новый live-route, который обходит эти шаги.
