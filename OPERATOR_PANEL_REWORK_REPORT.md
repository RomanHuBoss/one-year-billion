# Отчет о переделке операторской панели

## Причина переделки

Предыдущая панель показывала отдельные блоки и частично требовала от оператора выполнять консольные команды и вручную понимать, какие evidence уже можно записывать. Это делало эксплуатацию непрозрачной.

## Что изменено

### Backend

- Добавлен новый backend-контракт: `GET /api/operator/workflow`.
- Добавлен endpoint действий: `POST /api/operator/workflow/actions/{action_id}`.
- Workflow строится на backend и является source of truth для frontend.
- Крупные шаги закрываются только после завершения обязательных подшагов.
- Следующий gate остается `locked`, пока предыдущий gate не имеет PASS.
- Evidence теперь можно записывать из панели: `CI`, `PHASE0_PAPER`, `SECURITY`, `RECONCILIATION`, `GO_NO_GO`.
- Команды validate/testnet preflight/bootstrap/live preflight запускаются через существующий allowlist job-runner.
- Добавлен `Repository.evidence_summary()` для server-side состояния evidence.

### Frontend

- Панель переписана в формат мастера запуска.
- Убрана логика, где оператору нужно интерпретировать разрозненные карточки и переносить команды в терминал.
- Добавлены крупные последовательные вехи:
  1. База данных и миграции.
  2. Проверка проекта и CI evidence.
  3. Testnet preflight.
  4. Phase 0 paper/shadow evidence.
  5. Security evidence.
  6. Reconciliation evidence.
  7. Подписанный Go/No-Go.
  8. Live preflight.
- Добавлена кнопка «Выполнить следующий доступный шаг».
- Каждый подшаг имеет собственный статус и кнопку, если действие доступно.
- Заблокированные шаги визуально закрыты и не дают оператору перескочить дальше.
- Сохранены символы, trace_id, safe-actions и диагностика, но они перестали быть центром сценария.

### Tests

- Добавлены тесты `tests/test_operator_workflow_wizard.py`.
- Проверяется backend workflow, последовательность gate и отсутствие прямой frontend-логики готовности.
- Сохранены старые тесты operator module / API 401 / command runner.

## Результат проверки

```text
python main.py validate
pytest: 128 passed, 1 warning
check_strategy_imports: OK
check_architecture: OK
check_migrations_static: OK
secret_scan: OK
```

## Ограничения

- Live-submit не включался и не должен включаться этой переделкой.
- В среде сборки не проверялись реальные Bybit private credentials и внешняя PostgreSQL пользователя.
- 14-дневный paper/shadow период невозможно искусственно закрывать без фактического времени evidence.
