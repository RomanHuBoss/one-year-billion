# README для разработчиков

Проект реализуется и проверяется строго по Sprint 1–9. При конфликте требований действует `docs/specification.docx`, затем `docs/roadmap.docx`.

## Слои проекта по roadmap

- Sprint 1 — data foundation: `migrations/`, `app/market_data/`, `app/db/`.
- Sprint 2 — risk engine: `app/risk_engine/`, `app/api/routes/risk.py`.
- Sprint 3 — execution engine: `app/execution/`, `app/reconciliation/`.
- Sprint 4 — regime classifier: `app/regime/`.
- Sprint 5 — basic strategies: `app/strategies/`; стратегии возвращают только `SignalCandidate`.
- Sprint 6 — backtesting/validation: `app/backtest/`.
- Sprint 7 — ML filter: `app/ml/`.
- Sprint 8 — API/dashboard: `app/api/`, `frontend/`.
- Sprint 9 — paper/shadow/Go-No-Go: `app/paper_trading/`, `app/reports/go_no_go.py`.

## Обязательная проверка перед merge

```bash
python main.py validate
```

Команда запускает compileall, pytest, static strategy import check, architecture invariant check, migration invariant check и secret scan.

## Runtime-gates

- `app/config/runtime.py` загружает YAML, считает `config_hash` и передает `RiskConfig`/`CostModel` в risk/paper pipeline.
- `app/config/phase_validator.py` блокирует расширение Phase 0 за пределы BTC/ETH/SOL и запрещает live-route для carry/stat-arb в Phase 0/1.
- `/api/runtime/preflight` показывает безопасный scope, live-флаги, config_hash и stale/missing runtime inputs.
- `OrderRouter` держит per-symbol lock, чтобы retry/idempotency не увеличивали exposure.
- POST `/api/risk/approve` в live/testnet-live контуре требует operator key и `X-Idempotency-Key`, потому что создает `RiskDecision` для live order gate.

## Live-gated порядок отправки ордера

`/api/execution/live-submit` не является shortcut к бирже. Последовательность обязательна:

1. `validate_startup_security()` блокирует unsafe env.
2. `run_live_preflight()` проверяет DB, Go/No-Go, unresolved incidents, Bybit public/private access и runtime instruments, включая положительные `tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage`.
3. `Repository.verify_live_risk_decision()` проверяет, что `RiskDecision` реально сохранен в PostgreSQL, approved и non-expired.
4. `OrderRouter` строит deterministic `orderLinkId` и idempotent intent.
5. `Repository.reserve_order_intent()` вставляет order в DB, где trigger повторно проверяет approved risk decision.
6. `BybitAdapter.place_order()` отправляет order только при `TRADING_ENABLED=true` и `BYBIT_LIVE_CONFIRM=true`.
7. HTTP ack не переводит позицию в ACTIVE; следующий обязательный контур — reconciliation + protection watchdog.

Нельзя добавлять live-route, который обходит эти шаги.

## Дополнительные safety-исправления ревизии 1.7

- Redaction маскирует `apiSecret`, `BYBIT_API_KEY`, `X-BAPI-SIGN` и другие распространенные формы секретов регистронезависимо.
- Config validator регистронезависимо запрещает DCA/martingale/spot/inverse/options в live permissions.
- Risk sizing считает резерв после estimated initial margin, а не только после fees/slippage.
- AccountSnapshot содержит daily/weekly loss counters и portfolio/beta exposure для hard caps risk engine.
- ML training validator запрещает leakage, random shuffle временных рядов и `feature_ts > decision_ts`.
- OHLC-labeling консервативно трактует same-bar TP/SL ambiguity как loss/skip, а не как прибыль.
- `scripts/check_architecture.py` добавлен в обязательный validation pipeline.

## Запрещено

- Открывать order без approved non-expired `risk_decision_id`.
- Показывать ACTIVE без `protection_state=VALID` и `reconciliation_status=PASS`.
- Импортировать `app.execution` или Bybit adapter из `app/strategies`.
- Хранить API keys или бизнес-логику во frontend.
- Делать carry/stat-arb live в Phase 0/1.
- Использовать gross-only backtest как основание для live.
- Повышать риск из-за просадки или разрыва до целевой доходности.

## CLI

```bash
python main.py              # запуск backend/dashboard
python main.py validate     # полная локальная проверка
python main.py preflight --mode testnet
python main.py preflight --mode live
```
