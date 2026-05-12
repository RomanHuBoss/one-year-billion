import { api } from './api_client.js';
import { installContextHelp } from './context_help.js';

const $ = (id) => document.getElementById(id);
let lastDashboard = null;
let selectedSymbol = null;

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

function renderSteps(steps) {
  const stateLabel = { ok: 'PASS', todo: 'НУЖНО', blocked: 'БЛОК', manual: 'ПРОВЕРИТЬ' };
  const stateLevel = { ok: 'ok', todo: 'warning', blocked: 'danger', manual: 'info' };
  $('steps').innerHTML = steps.map(step => `
    <article class="step-card ${escapeHtml(step.state)}" data-help="step" data-help-id="${escapeHtml(step.id)}">
      ${badge(stateLabel[step.state] || step.state, stateLevel[step.state] || 'info')}
      <h3>${escapeHtml(step.title)}</h3>
      <p>${escapeHtml(step.explain)}</p>
      <p><strong>PASS:</strong> ${escapeHtml(step.pass_when)}</p>
      <code class="command">${escapeHtml(step.command)}</code>
    </article>
  `).join('');
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
    const status = row.status || (row.risk?.approved ? 'risk_approved' : 'risk_rejected');
    const strategy = row.strategy ? ` · ${row.strategy}` : '';
    const reasons = row.reasons || row.risk?.reasons || [];
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
    resultBox.textContent = `Ответ backend: ${result.status}\n${pretty(result.data)}`;
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
$('copyDiagBtn').addEventListener('click', copyDiagnostics);

installContextHelp({
  getDashboard: () => lastDashboard,
  getSelectedSymbol: () => selectedSymbol,
});

function showFatal(err) {
  document.body.insertAdjacentHTML('beforeend', `<div class="callout error" style="margin:20px">${escapeHtml(err.message)}</div>`);
}

loadAll().catch(showFatal);
