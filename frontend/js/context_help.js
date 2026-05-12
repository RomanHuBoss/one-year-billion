const HELP_TEXT = {
  screen: {
    title: 'Справка по операторскому экрану',
    meaning: 'Этот экран не открывает сделки сам. Он показывает состояние, которое посчитал backend, и разрешает только безопасные действия оператора.',
    doNow: [
      'Сначала смотрите самый верхний блок «Текущее состояние».',
      'Потом идите по плану «Переход от теста к live» сверху вниз.',
      'Если видите красный или желтый блок — нажмите правой кнопкой на него и вызовите справку.',
    ],
    safeWhen: 'Работать дальше можно, когда понятно, почему система не торгует. Для live все пункты preflight и Go/No-Go должны быть PASS.',
    dont: ['Не включайте live вручную, если Live gate закрыт.', 'Не обходите risk engine, stale-data blockers и Go/No-Go.'],
  },
  hero: {
    title: 'Верхний статус системы',
    meaning: 'Это главный вывод backend: можно ли сейчас тестировать, paper-гонять или переходить к следующему gate.',
    doNow: ['Прочитайте строку «Что делать сейчас».', 'Если состояние безопасное локальное — запускайте Paper один раз и validate.', 'Если состояние blocked — устраните причины из блока «Что мешает запуску».'],
    safeWhen: 'Для локальной работы нормальны статусы «Безопасный локальный режим» и blocked по live-gate. Для реальной торговли нужен только полный PASS.',
    dont: ['Не воспринимайте зеленый локальный режим как разрешение на live.', 'Не открывайте сделки вручную в обход системы.'],
  },
  toolbar: {
    title: 'Быстрый тест',
    meaning: 'Здесь находятся действия для быстрой проверки интерфейса и paper-конвейера. Они не должны отправлять реальные ордера.',
    doNow: ['Нажмите «Paper один раз», чтобы проверить путь data → regime → candidate → risk/no-trade.', 'После ошибки смотрите «Результат paper-теста» и «Техническую диагностику».'],
    safeWhen: 'Кнопка безопасна, если backend работает и live-submit выключен.',
    dont: ['Не считайте одиночный paper-запуск доказательством готовности к live. Нужны 14+ дней evidence.'],
  },

  commands: {
    title: 'Операционный центр',
    meaning: 'Здесь браузер не получает терминал. Он отправляет запрос в backend, а backend запускает только заранее разрешенные Python-команды без shell.',
    doNow: ['Введите OPERATOR_API_KEY.', 'Введите конкретную причину запуска.', 'Нажмите нужную команду: validate, testnet preflight, bootstrap DB или live preflight.', 'Дождитесь результата job и прочитайте stdout/stderr.'],
    safeWhen: 'Безопасно, потому что список команд allowlist-only, live-submit не включается, а bootstrap DB заменен на Python-скрипт без psql/shell.',
    dont: ['Не пытайтесь использовать этот блок как произвольную консоль.', 'Не запускайте live preflight как разрешение торговать: он только проверяет gates.'],
  },
  readiness: {
    title: 'Панель допуска',
    meaning: 'Это короткая сводка gate: торговля, БД, risk engine, live gate, фаза, ML.',
    doNow: ['Начинайте с красных карточек.', 'Желтые карточки означают: локально можно тестировать, но для live нужно исправить.', 'Зеленые карточки не требуют действия.'],
    safeWhen: 'Для live не должно оставаться красных или неразобранных желтых gate.',
    dont: ['Не меняйте настройки риска, чтобы «протащить» сделку.', 'Не расширяйте список символов Phase 0 без evidence.'],
  },
  blockers: {
    title: 'Что мешает запуску',
    meaning: 'Это список причин, из-за которых backend блокирует торговлю или live-preflight.',
    doNow: ['Исправляйте причины сверху вниз.', 'После исправления нажмите «Обновить» или повторите preflight.', 'Для stale_market проверьте источник рыночных данных и runtime-проверку Bybit.'],
    safeWhen: 'Блокер закрыт только когда исчез из списка после повторной проверки.',
    dont: ['Не удаляйте блокер из интерфейса вручную.', 'Не запускайте live, пока есть CRITICAL/HIGH blocker.'],
  },
  limits: {
    title: 'Настройки Phase 0',
    meaning: 'Это ограничения малого счета: какие символы и стратегии разрешены, какой риск и плечо допустимы.',
    doNow: ['Проверьте, что Phase 0 содержит только BTCUSDT, ETHUSDT, SOLUSDT.', 'Проверьте, что live-стратегии ограничены no_trade, de_risk, breakout, micro_grid.', 'Не повышайте risk_pct и leverage ради цели доходности.'],
    safeWhen: 'Настройки безопасны, если совпадают со спецификацией Phase 0 и проходят preflight.',
    dont: ['Не включайте carry/stat-arb live в Phase 0/1.', 'Не добавляйте martingale, DCA или усреднение против движения.'],
  },
  steps: {
    title: 'План перехода к live',
    meaning: 'Это контрольный маршрут: local validate → testnet preflight → PostgreSQL → paper/shadow → Go/No-Go → live preflight.',
    doNow: ['Выполняйте пункты строго по порядку.', 'Если пункт blocked или todo — live еще запрещен.', 'Основные команды запускайте из блока «Операционный центр». Терминал нужен только для аварийной диагностики.'],
    safeWhen: 'Переход к live допустим только когда все обязательные пункты имеют PASS и unresolved CRITICAL/HIGH = 0.',
    dont: ['Не прыгайте сразу к live preflight.', 'Не заменяйте 14+ дней paper/shadow одиночным запуском.'],
  },
  symbols: {
    title: 'Список символов',
    meaning: 'Каждая строка показывает backend status_effective по конкретной паре. Frontend не пересчитывает статус сам.',
    doNow: ['Выберите символ, чтобы увидеть причины и разрешенные действия.', 'Если статус NO_TRADE — это не поломка, а штатный запрет входа.', 'Если причина stale_market — обновите market data или проверьте runtime connection.'],
    safeWhen: 'Символ безопасен для дальнейшей проверки, когда причины понятны, данные свежие, risk approval возможен, а protection/reconciliation не конфликтуют.',
    dont: ['Не открывайте сделку по символу со статусом NO_TRADE/BLOCKED/DE_RISK.', 'Не путайте allowed action с торговым сигналом.'],
  },
  symbolDetails: {
    title: 'Детали выбранного символа',
    meaning: 'Здесь расшифрованы причины статуса и показаны только те действия, которые backend разрешает оператору.',
    doNow: ['Сначала прочитайте «Причины».', 'Потом проверьте «Разрешенные действия».', 'Trace ID сохраните для разбора ошибки или инцидента.'],
    safeWhen: 'Действие безопасно только если оно есть в списке разрешенных и вы указали понятную причину.',
    dont: ['Не выполняйте действия без причины.', 'Не пытайтесь увеличить позицию через операторский модуль — таких действий здесь быть не должно.'],
  },
  actions: {
    title: 'Безопасные действия оператора',
    meaning: 'Это единственные ручные действия из интерфейса. Они должны только снижать риск или оставлять его без увеличения.',
    doNow: ['Введите OPERATOR_API_KEY.', 'Введите конкретную причину действия.', 'Выберите символ слева, если действие должно относиться к нему.', 'Нажмите только то действие, смысл которого вам понятен.'],
    safeWhen: 'Safe-action допустим при сомнении, incident, stale data, необходимости отменить входы или снизить риск.',
    dont: ['Не используйте safe-action как способ открыть сделку.', 'Не закрывайте incident без сверки биржи и причины.'],
  },
  paper: {
    title: 'Результат paper-теста',
    meaning: 'Показывает, что произошло в paper-конвейере без реальных денег.',
    doNow: ['Если статус no_trade — смотрите regime reasons и причины отказа.', 'Если есть risk_rejected — это полезный результат, а не ошибка.', 'Для evidence нужны длительные paper/shadow записи, а не один запуск.'],
    safeWhen: 'Paper-тест полезен, когда решения воспроизводимы и reasons понятны.',
    dont: ['Не переходите в live по одному успешному paper-результату.', 'Не игнорируйте costs, slippage и rejected decisions.'],
  },
  diagnostics: {
    title: 'Техническая диагностика',
    meaning: 'Сырой JSON для разработчика, администратора или разбора инцидента. Оператору обычно достаточно основных блоков выше.',
    doNow: ['Используйте «Копировать», если нужно передать разработчику точный payload.', 'Смотрите request_id, trace_id, reasons и runtime checks.'],
    safeWhen: 'Диагностика помогает объяснить проблему, но не является разрешением торговать.',
    dont: ['Не правьте JSON руками.', 'Не показывайте payload третьим лицам, если там могут быть operational details.'],
  },
};

const CARD_HELP = {
  trading: {
    title: 'Карточка «Торговля»',
    meaning: 'Показывает, разрешены ли новые live-входы. В нормальном локальном режиме должно быть «выключена».',
    doNow: ['Если выключена — можно безопасно тестировать UI и paper.', 'Если запрошена — проверьте live preflight и убедитесь, что live-submit не включен случайно.'],
    safeWhen: 'Для реальной торговли одной этой карточки недостаточно: нужен PASS всех live gates.',
    dont: ['Не включайте trading_enabled=true без PostgreSQL, Bybit runtime, paper evidence и Go/No-Go PASS.'],
  },
  database: {
    title: 'Карточка «База данных»',
    meaning: 'PostgreSQL хранит hard constraints, idempotency, risk decisions, fills, incidents и Go/No-Go evidence.',
    doNow: ['Для локального UI отсутствие БД допустимо.', 'Для testnet/live поднимите PostgreSQL и примените миграции: python scripts/bootstrap_db.py или кнопка в «Операционном центре».', 'Повторите preflight и проверьте database_available=true.'],
    safeWhen: 'Для live карточка должна быть «подключена».',
    dont: ['Не торгуйте live без БД: тогда нельзя доказать risk approval, idempotency и incident history.'],
  },
  risk: {
    title: 'Карточка «Risk engine»',
    meaning: 'Risk engine — жесткий gate. Нет approved non-expired risk_decision_id → нет order.',
    doNow: ['Ничего не обходить.', 'Если сделка rejected — смотреть reasons и исправлять данные/условия.', 'Проверять, что risk approval свежий и не истек.'],
    safeWhen: 'Безопасно, когда каждый order связан с approved non-expired RiskDecision.',
    dont: ['Не отправляйте ордера напрямую в Bybit или execution adapter.', 'Не используйте target equity для sizing.'],
  },
  live_gate: {
    title: 'Карточка «Live gate»',
    meaning: 'Показывает, открыт ли путь к реальной торговле. «Закрыт» — правильное состояние, пока нет всех доказательств.',
    doNow: ['Выполните все шаги плана перехода.', 'Запустите python main.py preflight --mode live.', 'Исправляйте все reasons до status=ok.'],
    safeWhen: 'Live gate может открыться только после DB, Bybit runtime, paper/shadow evidence, Go/No-Go PASS и unresolved CRITICAL/HIGH=0.',
    dont: ['Не считайте blocked ошибкой до завершения gates.', 'Не включайте CAS_ENABLE_LIVE_SUBMIT для обхода.'],
  },
  phase: {
    title: 'Карточка «Фаза и символы»',
    meaning: 'Phase 0 ограничивает систему малым счетом: BTCUSDT, ETHUSDT, SOLUSDT и только простые live-стратегии.',
    doNow: ['Оставьте universe узким.', 'Расширяйте фазу только после evidence и решения владельца продукта.'],
    safeWhen: 'Phase 0 безопаснее, когда торгует редко, а no-trade является нормальным результатом.',
    dont: ['Не добавляйте широкий alt-universe на счет 500–1000 USDT.', 'Не включайте carry/stat-arb live в Phase 0/1.'],
  },
  ml: {
    title: 'Карточка «ML»',
    meaning: 'ML здесь не трейдер, а фильтр. Он может только ALLOW, BLOCK или UNAVAILABLE.',
    doNow: ['Если модель отсутствует или stale — система должна fail-closed.', 'Проверяйте OOS/walk-forward evidence перед расширением роли ML.'],
    safeWhen: 'Безопасно, когда ML не открывает сделки, не считает size и не меняет leverage.',
    dont: ['Не используйте ML verdict как приказ открыть позицию.', 'Не разрешайте demo override в live.'],
  },
};

const REASON_HELP = {
  stale_market: 'Рыночные данные устарели. Для live нужно восстановить market-data ingestion/Bybit runtime и повторить preflight. До этого сделки запрещены.',
  stale_or_missing_market: 'Нет свежих рыночных данных. В local smoke это ожидаемо, для testnet/live — blocker, который нужно устранить.',
  waiting_for_risk_approved_signal: 'Система ждет сигнал, который пройдет ML/risk-gate. Это штатное no-trade состояние.',
  no_candidate_after_regime_permissions: 'Regime/permission matrix не дала ни одного допустимого кандидата. Это нормально, если рынок неподходящий.',
  database_required_for_live: 'Для live нужна PostgreSQL-БД с миграциями, constraints, audit и evidence.',
  go_no_go_pass_and_approver_required: 'Нужен записанный Go/No-Go PASS с ответственным approver.',
  bybit_private_api_auth_failed: 'Public API работает, но private API не принял ключ или подпись. Проверьте testnet/live endpoint, ключ, secret, IP whitelist и пробелы в .env.',
  bybit_wallet_balance_failed: 'Ключ прошел не все private runtime checks. Проверьте account mode Bybit и доступ к wallet-balance.',
  bybit_positions_failed: 'Ключ не смог прочитать позиции Linear USDT. Проверьте permissions Contract/Derivatives и IP whitelist.',
  bybit_api_key_trade_permission_not_verified: 'Ключ читается, но права на торговлю Linear/Contract не подтверждены. Для testnet submit нужны Order/Position permissions.',
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

function list(items) {
  return (items || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
}

function normalizeReason(reason) {
  const raw = String(reason || '');
  return raw.includes(':') ? raw.split(':').pop() : raw;
}

function helpForCard(id, dashboard) {
  const card = dashboard?.data?.cards?.find(item => item.id === id);
  const base = CARD_HELP[id] || HELP_TEXT.readiness;
  if (!card) return base;
  return {
    ...base,
    context: [
      `Текущее значение: ${card.value}`,
      `Состояние: ${card.state}`,
      `Подсказка backend: ${card.hint}`,
    ],
  };
}

function helpForStep(id, dashboard) {
  const step = dashboard?.data?.steps?.find(item => item.id === id);
  if (!step) return HELP_TEXT.steps;
  return {
    title: `Шаг: ${step.title}`,
    meaning: step.explain,
    doNow: [
      `Выполните команду: ${step.command}`,
      `Критерий PASS: ${step.pass_when}`,
      step.state === 'blocked' ? 'Пока этот пункт blocked, к live переходить нельзя.' : 'После выполнения обновите экран и проверьте статус.',
    ],
    safeWhen: `Текущий статус шага: ${step.state}. Безопасно двигаться дальше только после PASS или понятного manual PASS.`,
    dont: ['Не пропускайте этот шаг.', 'Не заменяйте командную проверку визуальным ощущением, что «вроде работает».'],
    command: step.command,
  };
}

function helpForSymbol(symbol, dashboard) {
  const row = dashboard?.data?.symbols?.find(item => item.symbol === symbol);
  if (!row) return HELP_TEXT.symbols;
  const reasonTips = (row.reasons || []).map(reason => REASON_HELP[normalizeReason(reason)]).filter(Boolean);
  return {
    title: `Символ ${row.symbol}`,
    meaning: `Backend status_effective: ${row.status_effective}. Операторская расшифровка: ${row.status_label || row.status_effective}.`,
    doNow: [
      row.operator_hint || 'Проверьте причины и действуйте только через разрешенные safe-actions.',
      `Причины: ${(row.reason_labels || row.reasons || []).join('; ') || 'нет'}`,
      reasonTips[0] || 'Если причина непонятна — скопируйте Trace ID и техническую диагностику для разработчика.',
    ],
    safeWhen: `Разрешенные действия: ${(row.allowed_action_labels || row.allowed_actions || []).join(', ') || 'нет'}. Trace ID: ${row.trace_id || 'нет'}.`,
    dont: ['Не открывайте позицию вручную по этому символу.', 'Не нажимайте safe-action без причины и operator key.'],
  };
}

function helpForBlocker(code, dashboard) {
  const blocker = dashboard?.data?.blockers?.find(item => item.code === code);
  const normalized = normalizeReason(code);
  return {
    title: `Блокер: ${code || 'не выбран'}`,
    meaning: blocker?.text || 'Backend сообщил причину блокировки.',
    doNow: [
      REASON_HELP[normalized] || 'Исправьте указанную причину в backend/runtime, затем повторите проверку.',
      'После исправления нажмите «Обновить» или запустите preflight еще раз.',
      'Если это live blocker — не включайте live-submit до исчезновения причины.',
    ],
    safeWhen: 'Блокер закрыт только после повторной проверки, когда он исчез из списка reasons.',
    dont: ['Не игнорируйте blocker из-за того, что интерфейс локально открывается.', 'Не редактируйте статус вручную.'],
  };
}

function helpForAction(action, dashboard) {
  const item = dashboard?.data?.safe_actions?.find(entry => entry.action === action);
  if (!item) return HELP_TEXT.actions;
  return {
    title: `Действие: ${item.title}`,
    meaning: item.description,
    doNow: [
      'Выберите символ слева, если действие относится к конкретной паре.',
      'Введите OPERATOR_API_KEY.',
      'Введите конкретную причину: что случилось и почему действие безопасно.',
      'После выполнения проверьте ответ backend и обновленный статус.',
    ],
    safeWhen: `Направление риска: ${item.risk_direction}. Требуется причина: ${item.requires_reason ? 'да' : 'нет'}. Требуется ключ: ${item.requires_operator_key ? 'да' : 'нет'}.`,
    dont: ['Не используйте действие как торговую кнопку.', 'Не выполняйте flatten/reduce, если не понимаете последствий для открытой позиции.'],
  };
}


function helpForCommand(commandId, dashboard) {
  const cmd = dashboard?.data?.operator_commands?.find(item => item.command_id === commandId);
  if (!cmd) return HELP_TEXT.commands;
  const commandMap = {
    validate: 'Проверяет код и тесты. Запускайте после изменений и перед testnet/live проверками.',
    preflight_testnet: 'Проверяет testnet-готовность без реальных денег. Если status=blocked — исправляйте reasons.',
    bootstrap_db: 'Применяет PostgreSQL migrations через Python. Это замена ./scripts/bootstrap_db.sh; shell/psql больше не нужен.',
    preflight_live: 'Проверяет live gates. До DB, evidence и Go/No-Go PASS нормальный результат — blocked.',
  };
  return {
    title: `Команда: ${cmd.title}`,
    meaning: cmd.description,
    doNow: [
      commandMap[cmd.command_id] || 'Запускайте только если понимаете назначение команды.',
      'Введите OPERATOR_API_KEY и причину запуска.',
      'После завершения смотрите статус job, exit code, stdout и stderr.',
    ],
    safeWhen: `${cmd.safety} Timeout: ${cmd.timeout_sec} сек. Команда запускается backend allowlist-runner, не shell.` ,
    dont: ['Не считайте PASS одной команды разрешением live.', 'Не записывайте demo seed в production-БД.'],
    command: cmd.command_id === 'bootstrap_db' ? 'python scripts/bootstrap_db.py' : cmd.command_id,
  };
}

function helpForLimit(key, value) {
  return {
    title: `Лимит: ${key || 'Phase 0'}`,
    meaning: `Текущее значение: ${value || 'см. экран'}. Эти ограничения защищают малый счет и не должны обходиться оператором.`,
    doNow: ['Сверьте значение со спецификацией Phase 0.', 'Если значение неожиданное — остановите live-переход и проверьте config_hash.', 'Изменения лимитов делаются через config proposal/audit, а не руками во frontend.'],
    safeWhen: 'Лимит безопасен, если проходит config validation и preflight.',
    dont: ['Не повышайте риск или плечо для восстановления просадки.', 'Не расширяйте universe без paper/live evidence.'],
  };
}

function helpFromElement(el, dashboard) {
  const type = el?.dataset?.help;
  if (!type) return HELP_TEXT.screen;
  if (type === 'card') return helpForCard(el.dataset.helpId, dashboard);
  if (type === 'step') return helpForStep(el.dataset.helpId, dashboard);
  if (type === 'symbol') return helpForSymbol(el.dataset.symbol, dashboard);
  if (type === 'symbolDetails') {
    const selected = dashboard?.data?.symbols?.find(row => row.symbol === el.dataset.symbol);
    return selected ? helpForSymbol(selected.symbol, dashboard) : HELP_TEXT.symbolDetails;
  }
  if (type === 'blocker') return helpForBlocker(el.dataset.helpCode, dashboard);
  if (type === 'action') return helpForAction(el.dataset.action, dashboard);
  if (type === 'command') return helpForCommand(el.dataset.commandId, dashboard);
  if (type === 'limit') return helpForLimit(el.dataset.helpKey, el.dataset.helpValue);
  return HELP_TEXT[type] || HELP_TEXT.screen;
}

function renderHelpModal(content) {
  const command = content.command ? `<div class="help-command"><span>Команда</span><code>${escapeHtml(content.command)}</code></div>` : '';
  const context = content.context?.length ? `<section><h4>Текущий контекст</h4><ul>${list(content.context)}</ul></section>` : '';
  return `
    <div class="help-backdrop" data-help-close="true"></div>
    <section class="help-dialog" role="dialog" aria-modal="true" aria-labelledby="helpTitle">
      <header class="help-dialog-header">
        <div>
          <p class="eyebrow">Контекстная справка</p>
          <h2 id="helpTitle">${escapeHtml(content.title)}</h2>
        </div>
        <button class="help-close" type="button" aria-label="Закрыть справку" data-help-close="true">×</button>
      </header>
      <div class="help-dialog-body">
        <section><h4>Что это значит</h4><p>${escapeHtml(content.meaning)}</p></section>
        ${context}
        <section><h4>Что делать оператору</h4><ol>${list(content.doNow)}</ol></section>
        <section><h4>Когда можно считать нормой</h4><p>${escapeHtml(content.safeWhen)}</p></section>
        <section class="help-warning"><h4>Чего не делать</h4><ul>${list(content.dont)}</ul></section>
        ${command}
      </div>
    </section>
  `;
}

export function installContextHelp({ getDashboard, getSelectedSymbol } = {}) {
  const menu = document.createElement('div');
  menu.id = 'contextHelpMenu';
  menu.className = 'context-menu hidden';
  menu.innerHTML = '<button type="button" data-context-help-open>Вызвать справку</button>';
  document.body.appendChild(menu);

  const modalRoot = document.createElement('div');
  modalRoot.id = 'contextHelpModal';
  modalRoot.className = 'help-modal-root hidden';
  document.body.appendChild(modalRoot);

  let targetEl = null;

  function closeMenu() {
    menu.classList.add('hidden');
    targetEl = null;
  }

  function openHelpFor(el) {
    const dashboard = getDashboard ? getDashboard() : null;
    const content = helpFromElement(el, dashboard);
    modalRoot.innerHTML = renderHelpModal(content);
    modalRoot.classList.remove('hidden');
    closeMenu();
    const closeBtn = modalRoot.querySelector('[data-help-close]');
    closeBtn?.focus?.();
  }

  function openGeneralHelp() {
    openHelpFor({ dataset: { help: 'screen' } });
  }

  document.addEventListener('contextmenu', (event) => {
    const candidate = event.target.closest('[data-help]');
    if (!candidate) return;
    event.preventDefault();
    targetEl = candidate;
    const x = Math.min(event.clientX, window.innerWidth - 240);
    const y = Math.min(event.clientY, window.innerHeight - 80);
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.classList.remove('hidden');
  });

  menu.addEventListener('click', (event) => {
    if (event.target.matches('[data-context-help-open]') && targetEl) {
      openHelpFor(targetEl);
    }
  });

  modalRoot.addEventListener('click', (event) => {
    if (event.target.matches('[data-help-close]')) {
      modalRoot.classList.add('hidden');
      modalRoot.innerHTML = '';
    }
  });

  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target)) closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeMenu();
      modalRoot.classList.add('hidden');
      modalRoot.innerHTML = '';
    }
  });

  const helpBtn = document.getElementById('globalHelpBtn');
  helpBtn?.addEventListener('click', openGeneralHelp);
}
