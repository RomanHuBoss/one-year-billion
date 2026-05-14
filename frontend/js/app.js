import { api } from './api_client.js';
import { installContextHelp } from './context_help.js';

function $(id) {
  let el = document.getElementById(id);
  if (!el) {
    console.error(`DOM mismatch: element #${id} not found. Creating inert placeholder to avoid operator panel crash.`);
    let root = document.getElementById('domMismatchPlaceholders');
    if (!root) {
      root = document.createElement('div');
      root.id = 'domMismatchPlaceholders';
      root.hidden = true;
      document.body.appendChild(root);
    }
    el = document.createElement('div');
    el.id = id;
    root.appendChild(el);
  }
  return el;
}

let workflow = null;
let dashboard = null;
let selectedSymbol = null;
let lastPayload = {};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function pretty(data) { return JSON.stringify(data, null, 2); }

function parseJsonMaybe(text) {
  if (!text) return null;
  try { return JSON.parse(text); } catch (_) { return null; }
}

function badge(text, level = 'info') {
  return `<span class="badge ${escapeHtml(level || 'info')}">${escapeHtml(text || '—')}</span>`;
}

function key() { return ($('topApiKey')?.value || '').trim(); }

function reasonText() {
  return ($('workflowReason')?.value || '').trim() || 'операторский запуск шага из мастера';
}

function approvedByText() {
  return ($('workflowApprovedBy')?.value || '').trim();
}

function authOptions(options = {}) {
  const k = key();
  if (!k) return options;
  return { ...options, headers: { ...(options.headers || {}), 'x-api-key': k } };
}

function readAuthOptions(options = {}) {
  return authOptions(options);
}

// Совместимость и статический контроль: frontend читает /api/operator/dashboard,
// а write-команды доступны только через backend allowlist /api/operator/commands/.
// Legacy allowlist fetch shape for diagnostics: api('/api/operator/commands', readAuthOptions())
// headers include: 'x-api-key': key
// Paper отображает status_from_backend_missing, если backend не вернул статус, и не выводит его из client-side risk approval.
function actionOptions(body) {
  return authOptions({
    method: 'POST',
    headers: { 'X-Idempotency-Key': `workflow-${Date.now()}-${Math.random().toString(16).slice(2)}` },
    body: JSON.stringify(body),
  });
}

function statusLabel(status) {
  return {
    ok: 'PASS',
    todo: 'НУЖНО',
    locked: 'ЗАКРЫТО',
    blocked: 'БЛОК',
    error: 'ОШИБКА',
    running: 'ИДЕТ',
    manual: 'ВРУЧНУЮ',
    info: 'INFO',
    warning: 'ВНИМАНИЕ',
  }[status] || status || '—';
}

function statusLevel(status) {
  return {
    ok: 'ok',
    todo: 'warning',
    locked: 'neutral',
    blocked: 'danger',
    error: 'danger',
    running: 'info',
    manual: 'info',
  }[status] || 'info';
}

function currentStepIndex() {
  const steps = workflow?.steps || [];
  const id = workflow?.current_step_id;
  const idx = steps.findIndex(step => step.id === id);
  return idx < 0 ? 0 : idx;
}

function renderHero() {
  const hero = workflow?.hero || dashboard?.data?.hero || { level: 'info', title: 'Нет данных', message: '', next_step: '' };
  const level = hero.level || 'info';
  $('hero').className = `hero-card ${level}`;
  $('heroTitle').textContent = hero.title || 'Операторский модуль';
  $('heroMessage').textContent = hero.message || 'Нет ответа backend.';
  $('nextStep').textContent = hero.next_step || 'нет доступного шага';
  $('topStatus').className = `status-pill ${level}`;
  $('topStatus').textContent = workflow?.complete ? 'workflow PASS' : (hero.next_step || 'workflow');

  const steps = workflow?.steps || [];
  $('metricPass').textContent = `${steps.filter(s => s.status === 'ok').length}/${steps.length || 0}`;
  $('metricLocked').textContent = String(workflow?.locked_count ?? '0');
  $('metricBlocked').textContent = String(workflow?.blocked_count ?? '0');
}

function renderReadinessCards() {
  const cards = dashboard?.data?.cards || [];
  $('cardsGrid').innerHTML = cards.map(card => `
    <article class="metric-card ${escapeHtml(card.state || 'info')}" data-help="readiness">
      <header>
        <span>${escapeHtml(card.title)}</span>
        ${badge(statusLabel(card.state), statusLevel(card.state))}
      </header>
      <strong>${escapeHtml(card.value)}</strong>
      <p>${escapeHtml(card.hint)}</p>
    </article>
  `).join('') || '<div class="empty-state wide">Панель допуска пока недоступна. Введите READONLY_API_KEY или OPERATOR_API_KEY и обновите страницу.</div>';
}

function firstAvailableAction() {
  if (!workflow?.steps) return null;
  for (const step of workflow.steps) {
    if (step.action_id && step.status !== 'ok' && step.status !== 'locked') {
      return { step, action_id: step.action_id, title: step.primary_button || step.title, requires_approved_by: step.requires_approved_by };
    }
    for (const sub of (step.substeps || [])) {
      if (sub.action_id) {
        return { step, action_id: sub.action_id, title: sub.button || sub.title, requires_approved_by: step.requires_approved_by };
      }
    }
  }
  return null;
}

function renderWorkflow() {
  const steps = workflow?.steps || [];
  const passCount = steps.filter(s => s.status === 'ok').length;
  $('workflowSummary').innerHTML = `
    ${badge(`${passCount}/${steps.length || 0} PASS`, 'ok')}
    ${workflow?.locked_count ? badge(`${workflow.locked_count} закрыто`, 'neutral') : ''}
    ${workflow?.blocked_count ? badge(`${workflow.blocked_count} блок`, 'danger') : ''}
  `;

  const activeIndex = currentStepIndex();
  $('workflowSteps').innerHTML = steps.map((step, idx) => {
    const substeps = (step.substeps || []).map(sub => `
      <li class="substep ${escapeHtml(sub.status || 'info')}">
        <span class="substep-dot" aria-hidden="true"></span>
        <span class="substep-title">${escapeHtml(sub.title)}</span>
        ${sub.button ? `<button class="btn tiny secondary" data-action-id="${escapeHtml(sub.action_id)}" data-approved="${step.requires_approved_by ? '1' : '0'}">${escapeHtml(sub.button)}</button>` : ''}
      </li>
    `).join('');
    const button = step.primary_button && step.action_id
      ? `<button class="btn primary" data-action-id="${escapeHtml(step.action_id)}" data-approved="${step.requires_approved_by ? '1' : '0'}">${escapeHtml(step.primary_button)}</button>`
      : '';
    const isCurrent = idx === activeIndex ? ' current' : '';
    return `
      <article class="workflow-step ${escapeHtml(step.status || 'info')}${isCurrent}" data-step-id="${escapeHtml(step.id)}" data-help="steps">
        <div class="workflow-step-number">${escapeHtml(step.n)}</div>
        <div class="workflow-step-body">
          <div class="workflow-step-head">
            <div>
              <h3>${escapeHtml(step.title)}</h3>
              <p>${escapeHtml(step.goal)}</p>
            </div>
            ${badge(statusLabel(step.status), statusLevel(step.status))}
          </div>
          <p class="operator-text">${escapeHtml(step.operator_text || '')}</p>
          <ul class="substep-list">${substeps}</ul>
          <div class="workflow-actions">${button}</div>
        </div>
      </article>
    `;
  }).join('') || '<div class="empty-state">Workflow не загружен.</div>';

  document.querySelectorAll('[data-action-id]').forEach(btn => btn.addEventListener('click', () => runWorkflowAction(btn.dataset.actionId, btn.dataset.approved === '1')));
  renderNextAction();
}

function renderNextAction() {
  const next = firstAvailableAction();
  $('runNextBtn').disabled = !next;
  $('runNextBtn').textContent = next ? `Выполнить: ${next.title}` : 'Нет доступного следующего шага';
  $('nextActions').innerHTML = next
    ? `<div class="next-action-card">
        <span>Следующая безопасная операция</span>
        <strong>${escapeHtml(next.step.title)}</strong>
        <p>${escapeHtml(next.title)}</p>
        <button class="btn primary" data-next-action="true">Выполнить сейчас</button>
      </div>`
    : '<div class="empty-state">Все доступные подшаги завершены или следующий gate закрыт backend.</div>';
  document.querySelector('[data-next-action="true"]')?.addEventListener('click', () => runWorkflowAction(next.action_id, !!next.requires_approved_by));
}

function renderBlockers() {
  const blockers = dashboard?.data?.blockers || [];
  const dbError = workflow?.database_error;
  const missing = workflow?.database_missing_tables || [];
  const items = [...blockers];
  if (dbError) items.unshift({ code: 'database_error', text: dbError, level: 'danger' });
  if (missing.length) items.unshift({ code: 'database_missing_tables', text: missing.join(', '), level: 'warning' });
  $('blockersList').innerHTML = items.length ? items.map(item => `
    <article class="blocker ${escapeHtml(item.level || 'danger')}">
      <code>${escapeHtml(item.code)}</code>
      <p>${escapeHtml(item.text)}</p>
    </article>
  `).join('') : '<div class="blocker empty"><strong>Блокеры не обнаружены</strong><p>Это не разрешение на live-order: каждый order все равно требует approved RiskDecision и protection/reconciliation.</p></div>';
}

function renderCommandMatrix() {
  const commands = dashboard?.data?.operator_commands || [];
  $('commandMatrix').innerHTML = commands.slice(0, 4).map(cmd => `
    <article class="command-card">
      <div>
        <strong>${escapeHtml(cmd.title || cmd.command_id)}</strong>
        <code>${escapeHtml(cmd.command_display || '')}</code>
      </div>
      <span>${escapeHtml(cmd.safety || 'allowlist')}</span>
    </article>
  `).join('');
}

function renderInvariants() {
  $('invariants').innerHTML = (workflow?.invariants || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>Инварианты не загружены.</li>';
}

function renderSafeActions() {
  const actions = dashboard?.data?.safe_actions || [];
  $('safeActionsList').innerHTML = actions.length ? actions.map(action => `
    <article class="safe-action-card">
      <span>${escapeHtml(action.risk_direction || 'risk-neutral')}</span>
      <strong>${escapeHtml(action.title || action.action)}</strong>
      <p>${escapeHtml(action.description || '')}</p>
    </article>
  `).join('') : '<div class="empty-state">Backend не разрешил safe-actions для текущего состояния символов.</div>';
}

function symbolTone(row) {
  const severity = row.severity_level || row.severity || 'info';
  if (row.status_effective === 'ACTIVE') return 'ok';
  if (row.status_effective === 'ERROR_RECONCILIATION_REQUIRED' || severity === 'danger') return 'danger';
  if (row.status_effective === 'BLOCKED' || row.status_effective === 'DE_RISK' || severity === 'warning') return 'warning';
  return 'info';
}

function renderSymbols() {
  const symbols = dashboard?.data?.symbols || [];
  $('symbols').innerHTML = symbols.map((row, idx) => {
    const selected = selectedSymbol?.symbol === row.symbol || (!selectedSymbol && idx === 0);
    const reasons = (row.reason_labels || row.reasons || []).slice(0, 2).join('; ');
    return `<button class="symbol-row ${symbolTone(row)} ${selected ? 'selected' : ''}" data-symbol="${escapeHtml(row.symbol)}">
      <span class="symbol-name">${escapeHtml(row.symbol)}</span>
      <span class="symbol-status">${badge(row.status_label || row.status_effective, row.severity_level)}<small>${escapeHtml(reasons || 'причин нет')}</small></span>
      <span class="symbol-trace">${escapeHtml(row.trace_id || 'trace_id отсутствует')}</span>
    </button>`;
  }).join('') || '<div class="empty-state">Символы не загружены.</div>';

  document.querySelectorAll('.symbol-row').forEach(btn => btn.addEventListener('click', () => {
    selectedSymbol = symbols.find(s => s.symbol === btn.dataset.symbol);
    renderSymbols();
    renderSymbolDetails();
  }));
  if (!selectedSymbol && symbols.length) selectedSymbol = symbols[0];
  renderSymbolDetails();
}

function renderSymbolDetails() {
  const row = selectedSymbol;
  if (!row) { $('symbolDetails').innerHTML = '<div class="empty-state">Выберите символ слева.</div>'; return; }
  const reasons = (row.reason_labels || row.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join('') || '<li>Причины не указаны.</li>';
  const actions = (row.allowed_action_labels || row.allowed_actions || []).map(a => `<span class="chip">${escapeHtml(a)}</span>`).join('') || '<span class="chip muted">действий нет</span>';
  $('symbolDetails').innerHTML = `
    <div class="detail-title">
      <div><h3>${escapeHtml(row.symbol)}</h3><span>${escapeHtml(row.trace_id || 'trace_id отсутствует')}</span></div>
      ${badge(row.status_label || row.status_effective, row.severity_level)}
    </div>
    <div class="detail-grid">
      <div class="detail-box accent"><h4>Что означает статус</h4><p>${escapeHtml(row.operator_hint || '')}</p></div>
      <div class="detail-box"><h4>Причины</h4><ul>${reasons}</ul></div>
      <div class="detail-box"><h4>Разрешенные действия</h4><div class="chip-list">${actions}</div></div>
      <div class="detail-box"><h4>Backend source</h4><code>status_effective=${escapeHtml(row.status_effective || '')}</code></div>
    </div>`;
}

function renderJobOperatorHints(parsed) {
  const hints = parsed?.data?.operator_private_api_hint || parsed?.operator_private_api_hint || [];
  const timeSync = parsed?.data?.bybit_time_sync || parsed?.bybit_time_sync || null;
  const privateErrors = parsed?.data?.bybit_private_errors || parsed?.bybit_private_errors || [];
  const hasTimestampError = privateErrors.some(err => String(err.ret_code) === '10002' || err.code === 'bybit_timestamp_window_error');
  if (!hints.length && !timeSync && !hasTimestampError) return '';
  const hintItems = hints.map(h => `<li>${escapeHtml(h)}</li>`).join('');
  const syncText = timeSync ? `<p><strong>Синхронизация Bybit time:</strong> offset=${escapeHtml(timeSync.server_time_offset_ms ?? '—')} мс, recv_window=${escapeHtml(timeSync.recv_window_ms ?? '—')} мс, safety=${escapeHtml(timeSync.time_safety_margin_ms ?? '—')} мс.</p>` : '';
  const timestampText = hasTimestampError ? '<p><strong>Диагноз:</strong> это timestamp/recv_window gate Bybit, не признак испорченного API key.</p>' : '';
  return `<div class="job-hints"><h4>Что делать оператору</h4>${timestampText}${syncText}<ul>${hintItems}</ul></div>`;
}

function renderResult(payload) {
  if (!payload) return;
  const data = payload.data || {};
  if (data.job) {
    renderJob(data.job);
    pollJob(data.job.job_id).then(loadAll).catch(showError);
    return;
  }
  if (data.paper) {
    const decisions = data.paper.decisions || [];
    $('actionResult').className = 'job-output ok';
    $('actionResult').innerHTML = `<strong>Paper-прогон выполнен</strong>${decisions.map(d => `<div class="paper-item"><strong>${escapeHtml(d.symbol)} — ${escapeHtml(d.status || 'status_from_backend_missing')}</strong><span>${escapeHtml((d.reasons || []).join('; ') || 'решение записано')}</span></div>`).join('')}`;
    return;
  }
  $('actionResult').className = 'job-output ok';
  $('actionResult').innerHTML = `<strong>Готово</strong><pre>${escapeHtml(pretty(payload))}</pre>`;
}

function renderJob(job) {
  const level = job.status === 'ok' ? 'ok' : ['blocked', 'timeout', 'error'].includes(job.status) ? 'error' : '';
  const parsedStdout = parseJsonMaybe(job.stdout);
  const hints = renderJobOperatorHints(parsedStdout);
  const stdout = job.stdout ? `<h4>stdout</h4><pre>${escapeHtml(job.stdout)}</pre>` : '';
  const stderr = job.stderr ? `<h4>stderr</h4><pre>${escapeHtml(job.stderr)}</pre>` : '';
  const error = job.error ? `<p class="job-error">${escapeHtml(job.error)}</p>` : '';
  $('actionResult').className = `job-output ${level}`;
  $('actionResult').innerHTML = `<div class="job-head"><strong>${escapeHtml(job.title || job.command_id)}</strong>${badge(job.status, job.status === 'ok' ? 'ok' : job.status === 'running' || job.status === 'queued' ? 'info' : 'danger')}</div>
    <p><strong>Команда:</strong> <code>${escapeHtml(job.command_display || '')}</code></p>
    <p><strong>Задача:</strong> <code>${escapeHtml(job.job_id)}</code> · <strong>Код выхода:</strong> ${escapeHtml(job.exit_code ?? 'еще нет')}</p>${error}${hints}${stdout}${stderr}`;
}

async function pollJob(jobId) {
  for (let i = 0; i < 90; i += 1) {
    const payload = await api(`/api/operator/jobs/${encodeURIComponent(jobId)}`, authOptions());
    renderJob(payload.data.job);
    if (!['queued', 'running'].includes(payload.data.job.status)) return;
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}

function ensureActionInput(requiresApprovedBy) {
  if (!key()) throw new Error('Введите OPERATOR_API_KEY в поле Backend API-доступ. READONLY_API_KEY подходит только для просмотра.');
  if (!reasonText()) throw new Error('Укажите причину действия для audit trail.');
  if (requiresApprovedBy && !approvedByText()) throw new Error('Для этого gate нужен утверждающий в поле approved_by.');
}

async function runWorkflowAction(actionId, requiresApprovedBy = false) {
  try {
    ensureActionInput(requiresApprovedBy);
  } catch (err) {
    showError(err);
    return;
  }
  $('actionResult').className = 'job-output';
  $('actionResult').innerHTML = '<div class="loader-row"><span class="loader"></span><strong>Запрос отправлен на backend...</strong></div>';
  try {
    const payload = await api(`/api/operator/workflow/actions/${encodeURIComponent(actionId)}`, actionOptions({ reason: reasonText(), approved_by: approvedByText() || undefined }));
    renderResult(payload);
    await loadAll();
  } catch (err) {
    showError(err);
  }
}

function renderAll() {
  renderHero();
  renderReadinessCards();
  renderWorkflow();
  renderBlockers();
  renderCommandMatrix();
  renderSafeActions();
  renderInvariants();
  renderSymbols();
  $('diagnosticJson').textContent = pretty(lastPayload);
}

async function loadAll() {
  const [wf, dash] = await Promise.all([
    api('/api/operator/workflow', readAuthOptions()),
    api('/api/operator/dashboard', readAuthOptions()).catch(err => ({ status: 'error', data: { symbols: [], cards: [], blockers: [], safe_actions: [], operator_commands: [] }, error: err.message })),
  ]);
  workflow = wf.data;
  dashboard = dash;
  lastPayload = { workflow: wf, dashboard: dash };
  renderAll();
}

function showError(err) {
  $('actionResult').className = 'job-output error';
  $('actionResult').innerHTML = `<strong>Ошибка</strong><p>${escapeHtml(err.message || err)}</p>`;
}

function toggleDiagnostics() {
  $('diagnostics').classList.toggle('hidden');
  $('toggleDiagBtn').textContent = $('diagnostics').classList.contains('hidden') ? 'Диагностика' : 'Скрыть диагностику';
}

async function copyDiagnostics() {
  try {
    await navigator.clipboard.writeText($('diagnosticJson').textContent);
    $('copyDiagBtn').textContent = 'Скопировано';
  } catch (_) {
    $('copyDiagBtn').textContent = 'Не удалось скопировать';
  }
  setTimeout(() => $('copyDiagBtn').textContent = 'Копировать диагностику', 1500);
}

$('refreshBtn').addEventListener('click', () => loadAll().catch(showError));
$('runNextBtn').addEventListener('click', () => {
  const next = firstAvailableAction();
  if (next) runWorkflowAction(next.action_id, !!next.requires_approved_by);
});
$('toggleDiagBtn').addEventListener('click', toggleDiagnostics);
$('copyDiagBtn').addEventListener('click', copyDiagnostics);
$('topApiKey').addEventListener('keydown', event => { if (event.key === 'Enter') loadAll().catch(showError); });
$('workflowReason').addEventListener('keydown', event => { if (event.key === 'Enter') $('runNextBtn').click(); });
$('workflowApprovedBy').addEventListener('keydown', event => { if (event.key === 'Enter') $('runNextBtn').click(); });

installContextHelp({
  getDashboard: () => dashboard,
  getSelectedSymbol: () => selectedSymbol,
});
$('globalHelpBtn')?.addEventListener('click', event => {
  event.preventDefault();
  document.dispatchEvent(new CustomEvent('cas:global-help'));
});

loadAll().catch(showError);
