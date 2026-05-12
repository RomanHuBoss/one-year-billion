# Crypto Acceleration System 2026

Локальная/VPS-платформа для безопасной торговли **только Bybit Linear USDT Futures / USDT Perpetual**. Проект ориентирован на режим fail-closed: при неполных данных, устаревших спецификациях, отсутствии Go/No-Go или ошибке исполнения система блокирует live-вход, а не пытается «доторговать».

## Что реализовано

- FastAPI backend на Python 3.11+.
- PostgreSQL-миграции с hard constraints и lineage для signals, ML, risk, orders, fills, positions, incidents, configs и Go/No-Go evidence.
- Risk engine как обязательный gate: нет approved non-expired `risk_decision_id` — нет order.
- Execution boundary для Bybit V5: только `category=linear`, deterministic `orderLinkId`, idempotency, per-symbol lock, fail-closed live-submit.
- Runtime-preflight для testnet/live: Bybit public/private checks, права API-ключа, PostgreSQL, Go/No-Go evidence, unresolved incidents и обязательные положительные runtime specs (`tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage`).
- Консервативный regime classifier и phase validator: Phase 0 ограничен BTCUSDT/ETHUSDT/SOLUSDT; carry/stat-arb в Phase 0/1 только shadow.
- Стратегии возвращают только `SignalCandidate`; прямой импорт execution/Bybit из `app/strategies` запрещен static test-ом.
- ML gate работает только как `ALLOW/BLOCK/UNAVAILABLE` и fail-closed при stale/missing model.
- Ollama/LLM news-risk слой может только `BLOCK`, `ANNOTATE` или `UNAVAILABLE`; он не открывает сделки и не меняет размер/плечо.
- Dashboard на Vanilla HTML/CSS/JS без frontend-frameworks; источник истины для статуса — backend `status_effective`.
- Корневой CLI: `python main.py`.

## Текущий статус готовности

Редакция `1.8.0-total-project-check-safety-gated` подготовлена к локальному запуску, testnet-проверкам и live-gated эксплуатации. Live-submit endpoint существует, но по умолчанию заблокирован и не дойдет до Bybit без PostgreSQL, подписанного Go/No-Go, 14+ дней Phase 0 paper evidence, reconciliation/security/CI evidence, runtime Bybit checks, сохраненного approved `RiskDecision`, idempotency key и operator approval.

Важно: внутри архива нельзя подтвердить реальный live-допуск без внешней среды: PostgreSQL, Bybit testnet/prod API keys, реальных runtime-проверок и накопленного paper/shadow evidence. Поэтому корректное поведение проекта до прохождения этих gates — блокировать live.

## Быстрый запуск из командной строки

```bash
python main.py
```

Команда по умолчанию запускает backend и dashboard на `127.0.0.1:8000`.

Полезные CLI-команды:

```bash
python main.py serve --host 127.0.0.1 --port 8000
python main.py serve --mode testnet
python main.py validate
python main.py preflight --mode testnet
python main.py preflight --mode live
```

`--mode live` не включает торговлю автоматически. Он только выставляет контур запуска; live-submit все равно требует явные env-флаги, PostgreSQL evidence и Bybit runtime PASS.

## Установка без Docker

### 1. Виртуальное окружение

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

На Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. PostgreSQL

```bash
createdb cas2026
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/cas2026"
./scripts/bootstrap_db.sh
```

Опциональная локальная demo-загрузка:

```bash
CAS_SEED_DEMO_DATA=true ./scripts/bootstrap_db.sh
```

### 3. Переменные окружения

```bash
cp .env.example .env
```

Затем вручную отредактируйте `.env`. API-ключи Bybit не должны попадать во frontend, git, README, логи или screenshots.

Сгенерировать operator/read-only ключи можно так:

```bash
export OPERATOR_API_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
export READONLY_API_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
```

### 4. Запуск backend/dashboard

```bash
python main.py
```

Dashboard: `http://127.0.0.1:8000/`

OpenAPI: `http://127.0.0.1:8000/docs`

Runtime preflight: `http://127.0.0.1:8000/api/runtime/preflight`

### 5. Проверка проекта

```bash
python main.py validate
```

Проверка выполняет:

- `compileall` для `app`, `scripts`, `tests`, `universe`;
- `pytest`;
- static test запрета direct execution/Bybit imports из strategies;
- architecture invariant check: слои, циклические зависимости, frontend/source-of-truth, target-equity isolation;
- static check миграций;
- secret scan.

## Безопасные значения по умолчанию

В `.env.example` live отключен:

```env
TRADING_ENABLED=false
CAS_ENABLE_LIVE_SUBMIT=false
BYBIT_LIVE_CONFIRM=false
BYBIT_TESTNET=true
CAS_REQUIRE_DB_FOR_LIVE=true
CAS_REQUIRE_LIVE_PREFLIGHT=true
CAS_REQUIRE_GO_NOGO_FOR_LIVE=true
CAS_GO_NOGO_PASS=false
```

Даже если backend запущен, live order невозможен, пока все gates не пройдены.

## Testnet-порядок

1. Поднять PostgreSQL и применить миграции.
2. Указать testnet Bybit keys server-side.
3. Оставить `BYBIT_TESTNET=true`.
4. Выполнить:

```bash
python main.py validate
python main.py preflight --mode testnet
```

5. Если preflight возвращает `blocked`, исправлять причины из `reasons` и `checks`. Это штатное поведение fail-closed.
6. До live-submit записать только реальные evidence в PostgreSQL.

## Чеклист live-gate

Перед тем как `/api/execution/live-submit` сможет отправить order в Bybit, все условия должны быть выполнены:

```bash
export APP_ENV=prod
export DATABASE_URL="postgresql://..."
export OPERATOR_API_KEY="<long-random-operator-key>"
export READONLY_API_KEY="<different-long-random-readonly-key>"
export BYBIT_TESTNET=false
export BYBIT_API_KEY="<server-side-only>"
export BYBIT_API_SECRET="<server-side-only>"
export BYBIT_LIVE_CONFIRM=true
export TRADING_ENABLED=true
export CAS_ENABLE_LIVE_SUBMIT=true
export CAS_REQUIRE_DB_FOR_LIVE=true
export CAS_REQUIRE_LIVE_PREFLIGHT=true
export CAS_REQUIRE_GO_NOGO_FOR_LIVE=true
export CAS_GO_NOGO_PASS=true
export CAS_LIVE_APPROVED_BY="<product-owner>"
export CAS_ALLOW_DEMO_ML=false
export CAS_DEMO_MODE=false
python main.py preflight --mode live
```

DB-backed evidence обязательно. Env-флаги сами по себе недостаточны:

```bash
python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS --started-at 2026-05-01T00:00:00Z --ended-at 2026-05-15T00:00:00Z --metrics-json '{"reconciliation_pass_rate":1.0,"unresolved_incidents":0}'
python scripts/record_go_no_go_evidence.py --type RECONCILIATION --status PASS --metrics-json '{"pass_rate":1.0}'
python scripts/record_go_no_go_evidence.py --type SECURITY --status PASS --metrics-json '{"secret_scan":"PASS"}'
python scripts/record_go_no_go_evidence.py --type CI --status PASS --metrics-json '{"tests":65}'
python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by "<product-owner>"
```

`python main.py preflight --mode live` должен вернуть `status: ok`. Если он возвращает `blocked`, live-submit корректно запрещен.

## Жесткие инварианты

1. Нет approved non-expired `risk_decision_id` — нет order.
2. Нет verified protection — нет ACTIVE position.
3. Strategy modules не импортируют Bybit/execution и возвращают только `SignalCandidate`.
4. Frontend не является source of truth: он отображает backend `status_effective`, `severity`, `reasons`, `trace_id`, `allowed_actions`.
5. Stale account/specs/orderbook/funding блокируют risk approval.
6. Target equity используется только в analytics/stress и не влияет на sizing/risk/execution.
7. Carry/stat-arb Phase 0/1 не имеют live-маршрута исполнения.
8. Manual override может только снижать риск: disable, cancel entries, flatten/reduce, resolve incident, config proposal/activation.
9. Go/No-Go требует unresolved CRITICAL/HIGH = 0.
10. Risk approval в live/testnet-live контуре требует operator key и `X-Idempotency-Key`.

## Структура проекта

```text
app/
  api/                FastAPI routes, response contract, auth/idempotency/audit
  backtest/           execution-aware validation
  config/             config loader and safety validator
  core/               settings, hashing, time utilities
  db/                 PostgreSQL connection/repository helpers
  execution/          order router, idempotency, state machine, Bybit adapter boundary
  live/               live preflight and submit gate
  llm/                Ollama block/annotate-only gate
  market_data/        freshness gates and Bybit normalization
  ml/                 ML fail-closed gate, labels, training utilities
  paper_trading/      paper/shadow pipeline
  reconciliation/     reconciliation and protection checks
  regime/             conservative regime classifier
  reports/            Go/No-Go report generator
docs/GO_NO_GO.md       обязательный live-gate checklist
  risk_engine/        hard approval gate, sizing, cost model, liquidation checks
  schemas/            typed domain/API schemas
  security/           RBAC, redaction, startup guard
  services/           локальное demo-state для smoke-запуска
  strategies/         SignalCandidate-only strategies
frontend/             Vanilla dashboard
migrations/           PostgreSQL schema and seed data
scripts/              run/test/live-preflight utilities
config/               YAML runtime policy
universe/             phase-limited whitelist
main.py               единая CLI-точка запуска
```

## Операционная граница

Репозиторий можно запускать локально, проверять в testnet и готовить к live-gated эксплуатации. Финальное production-live разрешение требует внешних доказательств: примененных миграций PostgreSQL, реальных Bybit credentials/permissions, runtime preflight PASS, отсутствия unresolved HIGH/CRITICAL incidents и DB-recorded paper/shadow Go/No-Go PASS.
