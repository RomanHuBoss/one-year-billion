import { api } from './api_client.js';
import { installContextHelp } from './context_help.js';

const $ = (id) => document.getElementById(id);
let lastDashboard = null;
let selectedSymbol = null;
let operatorCommands = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

function badge(text, level = 'info') {
  return `<span class="badge ${escapeHtml(level)}">${escapeHtml(text)}</span>`;
}

function setHero(hero) {
  const heroEl = $('hero');
  heroEl.className = `hero-card ${hero.level || 'info'}`;
  $('heroTitle').textContent = hero.title;
  $('heroMessage').textContent = hero.message;
  $('nextStep').textContent = hero.next_step;
  $('topStatus').className = `status-pill ${hero.level || 'info'}`;
  $('topStatus').textContent = hero.title;
}

function renderCards(cards) {
  $('cards').innerHTML = cards.map(card => `
    <article class="metric-card" data-help="card" data-help-id="${escapeHtml(card.id)}">
      <header>
        <h3>${escapeHtml(card.title)}</h3>
        ${badge(card.state === 'ok' ? 'OK' : card.state === 'danger' ? 'БЛОК' : card.state === 'warning' ? 'ВНИМАНИЕ' : 'INFO', card.state)}
      </header>
      <div class="metric-value">${escapeHtml(card.value)}</div>
      <div class="metric-hint">${escapeHtml(card.hint)}</div>
    </article>
  `).join('');
}

function renderBlockers(blockers) {
  if (!blockers || blockers.length === 0) {
    $('blockers').innerHTML = '<div class="blocker empty" data-help="blockers"><strong>Явных блокеров нет.</strong><span>Продолжайте по плану перехода к live.</span></div>';
    return;
  }
  $('blockers').innerHTML = blockers.map(item => `
    <div class="blocker" data-help="blocker" data-help-code="${escapeHtml(item.code)}">
      <code>${escapeHtml(item.code)}</code>
      <div><strong>${escapeHtml(item.text)}</strong><span>Устраните причину и повторите preflight.</span></div>
    </div>
  `).join('');
}

function renderLimits(limits) {
  const rows = [
    ['Фаза', `Phase ${limits.phase}`],
    ['Символы', (limits.universe || []).join(', ')],
    ['Live-стратегии', (limits.live_strategies || []).join(', ')],
    ['Shadow-сканеры', (limits.shadow_strategies || []).join(', ')],
    ['Риск по умолчанию', `${(Number(limits.risk_pct_default) * 100).toFixed(2)}%`],
    ['Абсолютный риск max', `${(Number(limits.risk_pct_absolute_max) * 100).toFixed(2)}%`],
    ['Макс. плечо', `${limits.max_effective_leverage}x`],
    ['TTL risk approval', `${limits.approval_ttl_seconds} сек.`],
    ['Оборот', `до ${limits.turnover_round_turns_per_day} round-turn/day`],
  ];
  $('limits').innerHTML = rows.map(([k, v]) => `<div data-help="limit" data-help-key="${escapeHtml(k)}" data-help-value="${escapeHtml(v)}"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join('');
}

function stepAction(step) {
  if (step.command_id) {
    return `<button class="btn tiny secondary" data-run-command="${escapeHtml(step.command_id)}">Запустить</button>`;
  }
  if (step.id === 'paper_shadow') {
    return '<button class="btn tiny secondary" data-paper-step="true">Paper один раз</button>';
  }
  return '<span class="step-note">ручная фиксация evidence</span>';
}

function renderSteps(steps) {
  const stateLabel = { ok: 'PASS', todo: 'НУЖНО', blocked: 'БЛОК', manual: 'ПРОВЕРИТЬ' };
  const stateLevel = { ok: 'ok', todo: 'warning', blocked: 'danger', manual: 'info' };
  $('steps').innerHTML = steps.map(step => `
    <article class="step-card ${escapeHtml(step.state)}" data-help="step" data-help-id="${escapeHtml(step.id)}" data-command-id="${escapeHtml(step.command_id || '')}">
      <div class="step-top">
        ${badge(stateLabel[step.state] || step.state, stateLevel[step.state] || 'info')}
        ${stepAction(step)}
      </div>
      <h3>${escapeHtml(step.title)}</h3>
      <p>${escapeHtml(step.explain)}</p>
      <p><strong>PASS:</strong> ${escapeHtml(step.pass_when)}</p>
      <div class="command-line">
        <code class="command">${escapeHtml(step.command)}</code>
        ${step.command_id ? `<button class="btn icon-run" title="Запустить команду" data-run-command="${escapeHtml(step.command_id)}">▶</button>` : ''}
      </div>
    </article>
  `).join('');
  [...document.querySelectorAll('button[data-run-command]')].forEach(btn => {
    btn.addEventListener('click', () => runOperatorCommand(btn.dataset.runCommand));
  });
  [...document.querySelectorAll('button[data-paper-step]')].forEach(btn => {
    btn.addEventListener('click', runPaper);
  });
}

function renderSymbols(symbols) {
  const rows = symbols.map((row, idx) => {
    const selected = selectedSymbol?.symbol === row.symbol || (!selectedSymbol && idx === 0);
    return `
      <button class="symbol-row ${selected ? 'selected' : ''}" data-help="symbol" data-symbol="${escapeHtml(row.symbol)}">
        <span class="symbol-name">${escapeHtml(row.symbol)}</span>
        <span>
          ${badge(row.status_label || row.status_effective, row.severity_level)}
          <div class="reason-line">${escapeHtml((row.reason_labels || row.reasons || []).slice(0, 2).join('; '))}</div>
        </span>
        <span>${escapeHtml(row.trace_id || '')}</span>
      </button>
    `;
  }).join('');
  $('symbols').innerHTML = rows || '<div class="empty-state">Символов нет.</div>';
  [...document.querySelectorAll('.symbol-row')].forEach(btn => {
    btn.addEventListener('click', () => {
      selectedSymbol = symbols.find(s => s.symbol === btn.dataset.symbol);
      renderSymbols(symbols);
      renderSymbolDetails(selectedSymbol);
    });
  });
  if (!selectedSymbol && symbols.length) selectedSymbol = symbols[0];
  if (selectedSymbol) renderSymbolDetails(selectedSymbol);
}

function renderSymbolDetails(row) {
  if (!row) {
    $('symbolDetails').dataset.help = 'symbolDetails';
    $('symbolDetails').removeAttribute('data-symbol');
    $('symbolDetails').innerHTML = '<div class="empty-state">Выберите символ слева.</div>';
    return;
  }
  const reasonItems = (row.reason_labels || row.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join('') || '<li>Причины не указаны.</li>';
  const actions = (row.allowed_action_labels || row.allowed_actions || []).map(a => `<span class="chip">${escapeHtml(a)}</span>`).join('') || '<span class="chip">действий нет</span>';
  $('symbolDetails').dataset.help = 'symbolDetails';
  $('symbolDetails').dataset.symbol = row.symbol;
  $('symbolDetails').innerHTML = `
    <div class="detail-title">
      <h3>${escapeHtml(row.symbol)}</h3>
      ${badge(row.status_label || row.status_effective, row.severity_level)}
    </div>
    <div class="detail-grid">
      <div class="detail-box"><h4>Что это значит</h4><p>${escapeHtml(row.operator_hint || '')}</p></div>
      <div class="detail-box"><h4>Причины</h4><ul>${reasonItems}</ul></div>
      <div class="detail-box"><h4>Разрешенные действия</h4><div class="chip-list">${actions}</div></div>
      <div class="detail-box"><h4>Trace ID</h4><code>${escapeHtml(row.trace_id || '')}</code></div>
    </div>
  `;
}

function renderActions(actions) {
  if (!actions || actions.length === 0) {
    $('safeActions').innerHTML = '<div class="empty-state">Backend не разрешает действия для текущего состояния.</div>';
    return;
  }
  $('safeActions').innerHTML = actions.map(item => `
    <article class="action-card" data-help="action" data-action="${escapeHtml(item.action)}">
      <h3>${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.description)}</p>
      <button class="btn danger" data-action="${escapeHtml(item.action)}">Выполнить</button>
    </article>
  `).join('');
  [...document.querySelectorAll('button[data-action]')].forEach(btn => {
    btn.addEventListener('click', () => submitSafeAction(btn.dataset.action));
  });
}


function renderOperatorCommands(commands) {
  operatorCommands = commands || [];
  const box = $('operatorCommands');
  if (!operatorCommands.length) {
    box.textContent = 'Backend не вернул доступных операторских команд.';
    return;
  }
  const names = operatorCommands.map(cmd => cmd.title).join(' · ');
  box.textContent = `Доступные серверные команды: ${names}. Запускайте их кнопками прямо в карточках плана.`;
}

async function loadCommands() {
  const payload = await api('/api/operator/commands');
  renderOperatorCommands(payload.data.commands || []);
  if (payload.data.jobs?.length) {
    renderJob(payload.data.jobs[0]);
  }
}

function renderJob(job) {
  const level = job.status === 'ok' ? 'ok' : ['blocked', 'timeout', 'error'].includes(job.status) ? 'error' : '';
  const stdout = job.stdout ? `<h4>stdout</h4><pre>${escapeHtml(job.stdout)}</pre>` : '';
  const stderr = job.stderr ? `<h4>stderr</h4><pre>${escapeHtml(job.stderr)}</pre>` : '';
  const error = job.error ? `<p class="job-error">${escapeHtml(job.error)}</p>` : '';
  $('operatorJobResult').className = `job-output ${level}`;
  $('operatorJobResult').innerHTML = `
    <div class="job-head">
      <strong>${escapeHtml(job.title || job.command_id)}</strong>
      ${badge(job.status, job.status === 'ok' ? 'ok' : job.status === 'running' || job.status === 'queued' ? 'info' : 'danger')}
    </div>
    <p><strong>Команда:</strong> <code>${escapeHtml(job.command_display || '')}</code></p>
    <p><strong>Задача:</strong> <code>${escapeHtml(job.job_id)}</code> · <strong>Код выхода:</strong> ${escapeHtml(job.exit_code ?? 'еще нет')}</p>
    ${error}${stdout}${stderr}
  `;
}

async function pollJob(jobId) {
  for (let i = 0; i < 60; i += 1) {
    const payload = await api(`/api/operator/jobs/${encodeURIComponent(jobId)}`);
    renderJob(payload.data.job);
    if (!['queued', 'running'].includes(payload.data.job.status)) return;
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}

async function runOperatorCommand(commandId) {
  const key = $('commandOperatorKey').value.trim();
  const reason = $('commandReason').value.trim();
  const resultBox = $('operatorJobResult');
  if (!key || !reason) {
    resultBox.className = 'job-output error';
    resultBox.textContent = 'Нужны OPERATOR_API_KEY и причина запуска. Backend не примет команду без audit-причины.';
    return;
  }
  const options = {};
  if (commandId === 'bootstrap_db') {
    options.seed_demo = $('seedDemoData').checked;
  }
  try {
    resultBox.className = 'job-output';
    resultBox.textContent = 'Команда отправлена на сервер...';
    const payload = await api(`/api/operator/commands/${encodeURIComponent(commandId)}/run`, {
      method: 'POST',
      headers: {
        'x-api-key': key,
        'X-Idempotency-Key': `operator-command-${commandId}-${Date.now()}`,
      },
      body: JSON.stringify({ reason, options }),
    });
    renderJob(payload.data.job);
    await pollJob(payload.data.job.job_id);
    await loadAll();
  } catch (err) {
    resultBox.className = 'job-output error';
    resultBox.textContent = err.message;
  }
}

function renderDiagnostics(payload) {
  $('diagnosticJson').textContent = pretty(payload);
}

function renderPaperSummary(data) {
  const decisions = data?.decisions || [];
  if (!decisions.length) {
    $('paperSummary').innerHTML = '<div class="empty-state">Paper-конвейер не создал решений.</div>';
    return;
  }
  $('paperSummary').innerHTML = decisions.map(row => {
    // Статус paper-решения формирует сервер. Браузер только отображает
    // готовое значение и не выводит его из вложенных полей risk.
    const status = row.status || 'status_from_backend_missing';
    const strategy = row.strategy ? ` · ${row.strategy}` : '';
    const reasons = row.reasons || [];
    return `<div class="paper-item" data-help="paper"><strong>${escapeHtml(row.symbol)}${escapeHtml(strategy)} — ${escapeHtml(status)}</strong><span>${escapeHtml(reasons.join('; ') || 'решение записано')}</span></div>`;
  }).join('');
}

async function loadAll() {
  const payload = await api('/api/operator/dashboard');
  lastDashboard = payload;
  const data = payload.data;
  selectedSymbol = null;
  setHero(data.hero);
  renderCards(data.cards);
  renderBlockers(data.blockers);
  renderLimits(data.limits);
  renderSteps(data.steps);
  renderSymbols(data.symbols);
  renderActions(data.safe_actions);
  renderOperatorCommands(data.operator_commands || operatorCommands);
  renderDiagnostics(payload);
}

async function runPaper() {
  $('paperRunBtn').disabled = true;
  $('paperRunBtn').textContent = 'Запускаю...';
  try {
    const result = await api('/api/paper/run-once', { method: 'POST', body: '{}' });
    renderPaperSummary(result.data);
    renderDiagnostics({ dashboard: lastDashboard, paper: result });
  } catch (err) {
    $('paperSummary').innerHTML = `<div class="empty-state">Ошибка paper: ${escapeHtml(err.message)}</div>`;
  } finally {
    $('paperRunBtn').disabled = false;
    $('paperRunBtn').textContent = 'Paper один раз';
  }
}

async function submitSafeAction(action) {
  const key = $('operatorKey').value.trim();
  const reason = $('actionReason').value.trim();
  const resultBox = $('actionResult');
  resultBox.className = 'callout';
  if (!key || !reason) {
    resultBox.className = 'callout error';
    resultBox.textContent = 'Нужны OPERATOR_API_KEY и причина действия. Без причины backend не примет команду.';
    return;
  }
  try {
    const result = await api('/api/actions', {
      method: 'POST',
      headers: {
        'x-api-key': key,
        'X-Idempotency-Key': `operator-ui-${action}-${Date.now()}`,
      },
      body: JSON.stringify({ action, reason, target: selectedSymbol ? { symbol: selectedSymbol.symbol } : {} }),
    });
    resultBox.textContent = `Ответ сервера: ${result.status}\n${pretty(result.data)}`;
    await loadAll();
  } catch (err) {
    resultBox.className = 'callout error';
    resultBox.textContent = err.message;
  }
}

function toggleDiagnostics() {
  $('diagnostics').classList.toggle('hidden');
  $('toggleDiagBtn').textContent = $('diagnostics').classList.contains('hidden') ? 'Показать диагностику' : 'Скрыть диагностику';
}

async function copyDiagnostics() {
  await navigator.clipboard.writeText($('diagnosticJson').textContent);
  $('copyDiagBtn').textContent = 'Скопировано';
  setTimeout(() => $('copyDiagBtn').textContent = 'Копировать', 1500);
}

$('refreshBtn').addEventListener('click', () => loadAll().catch(showFatal));
$('paperRunBtn').addEventListener('click', runPaper);
$('toggleDiagBtn').addEventListener('click', toggleDiagnostics);
$('reloadCommandsBtn').addEventListener('click', () => loadCommands().catch(showFatal));
$('copyDiagBtn').addEventListener('click', copyDiagnostics);

installContextHelp({
  getDashboard: () => lastDashboard,
  getSelectedSymbol: () => selectedSymbol,
});

function showFatal(err) {
  document.body.insertAdjacentHTML('beforeend', `<div class="callout error" style="margin:20px">${escapeHtml(err.message)}</div>`);
}

loadAll().then(loadCommands).catch(showFatal);
