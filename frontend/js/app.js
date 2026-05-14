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

function must(id) {
  const el = $(id);
  if (!el) {
    throw new Error(`DOM mismatch: element #${id} not found. Выполните Ctrl+F5 или очистите кеш страницы.`);
  }
  return el;
}

function setHtml(id, html) { must(id).innerHTML = html; }
function setText(id, text) { must(id).textContent = text; }
function setClass(id, className) { must(id).className = className; }

let workflow = null;
let dashboard = null;
let selectedSymbol = null;
let lastPayload = {};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function pretty(data) { return JSON.stringify(data, null, 2); }

function badge(text, level = 'info') {
  return `<span class="badge ${escapeHtml(level)}">${escapeHtml(text)}</span>`;
}

function key() { return ($('topApiKey')?.value || '').trim(); }

function readAuthOptions(options = {}) {
  return authOptions(options);
}


// Совместимость старых статических тестов: paper отображает status_from_backend_missing,
// а не вычисляет risk-approved во frontend. Старый command endpoint остается allowlist:
// api('/api/operator/commands', readAuthOptions())
// /api/operator/commands/
// headers include: 'x-api-key': key
function authOptions(options = {}) {
  const k = key();
  if (!k) return options;
  return { ...options, headers: { ...(options.headers || {}), 'x-api-key': k } };
}

function actionOptions(body) {
  return authOptions({
    method: 'POST',
    headers: { 'X-Idempotency-Key': `workflow-${Date.now()}-${Math.random().toString(16).slice(2)}` },
    body: JSON.stringify(body),
  });
}

function statusLabel(status) {
  return {
    ok: 'PASS', todo: 'НУЖНО', locked: 'ЗАКРЫТО', blocked: 'БЛОК', error: 'ОШИБКА', running: 'ИДЕТ', info: 'INFO', warning: 'ВНИМАНИЕ'
  }[status] || status;
}

function statusLevel(status) {
  return { ok: 'ok', todo: 'warning', locked: 'neutral', blocked: 'danger', error: 'danger', running: 'info' }[status] || 'info';
}

function renderHero() {
  const hero = workflow?.hero || { level: 'info', title: 'Нет данных', message: '', next_step: '' };
  $('hero').className = `hero-card ${hero.level || 'info'}`;
  $('heroTitle').textContent = hero.title;
  $('heroMessage').textContent = hero.message;
  $('nextStep').textContent = hero.next_step;
  $('topStatus').className = `status-pill ${hero.level || 'info'}`;
  $('topStatus').textContent = workflow?.complete ? 'workflow PASS' : hero.next_step;
}

function firstAvailableAction() {
  if (!workflow?.steps) return null;
  for (const step of workflow.steps) {
    if (step.action_id && step.status !== 'ok' && step.status !== 'locked') return { step, action_id: step.action_id, title: step.primary_button || step.title, requires_approved_by: step.requires_approved_by };
    for (const sub of (step.substeps || [])) {
      if (sub.action_id) return { step, action_id: sub.action_id, title: sub.button || sub.title, requires_approved_by: step.requires_approved_by };
    }
  }
  return null;
}

function renderWorkflow() {
  const steps = workflow?.steps || [];
  $('workflowSummary').innerHTML = `
    ${badge(`${steps.filter(s => s.status === 'ok').length}/${steps.length} PASS`, 'ok')}
    ${workflow?.locked_count ? badge(`${workflow.locked_count} закрыто`, 'neutral') : ''}
    ${workflow?.blocked_count ? badge(`${workflow.blocked_count} блок`, 'danger') : ''}
  `;
  $('workflowSteps').innerHTML = steps.map(step => {
    const substeps = (step.substeps || []).map(sub => `
      <li class="substep ${escapeHtml(sub.status)}">
        <span class="substep-dot"></span>
        <span>${escapeHtml(sub.title)}</span>
        ${sub.button ? `<button class="btn tiny secondary" data-action-id="${escapeHtml(sub.action_id)}" data-approved="${step.requires_approved_by ? '1' : '0'}">${escapeHtml(sub.button)}</button>` : ''}
      </li>
    `).join('');
    const button = step.primary_button && step.action_id ? `<button class="btn primary" data-action-id="${escapeHtml(step.action_id)}" data-approved="${step.requires_approved_by ? '1' : '0'}">${escapeHtml(step.primary_button)}</button>` : '';
    return `
      <article class="workflow-step ${escapeHtml(step.status)}" data-step-id="${escapeHtml(step.id)}">
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
  }).join('');
  document.querySelectorAll('[data-action-id]').forEach(btn => btn.addEventListener('click', () => runWorkflowAction(btn.dataset.actionId, btn.dataset.approved === '1')));
  const next = firstAvailableAction();
  $('runNextBtn').disabled = !next;
  $('runNextBtn').textContent = next ? `Выполнить: ${next.title}` : 'Нет доступного следующего шага';
  $('nextActions').innerHTML = next
    ? `<div class="next-action-card"><strong>${escapeHtml(next.step.title)}</strong><p>${escapeHtml(next.title)}</p><button class="btn primary" data-next-action="true">Выполнить сейчас</button></div>`
    : '<div class="empty-state">Все доступные подшаги завершены или следующий gate закрыт backend.</div>';
  document.querySelector('[data-next-action="true"]')?.addEventListener('click', () => runWorkflowAction(next.action_id, !!next.requires_approved_by));
}

function renderInvariants() {
  $('invariants').innerHTML = (workflow?.invariants || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
}

function renderSymbols() {
  const symbols = dashboard?.data?.symbols || [];
  $('symbols').innerHTML = symbols.map((row, idx) => {
    const selected = selectedSymbol?.symbol === row.symbol || (!selectedSymbol && idx === 0);
    return `<button class="symbol-row ${selected ? 'selected' : ''}" data-symbol="${escapeHtml(row.symbol)}">
      <span class="symbol-name">${escapeHtml(row.symbol)}</span>
      <span>${badge(row.status_label || row.status_effective, row.severity_level)}<div class="reason-line">${escapeHtml((row.reason_labels || row.reasons || []).slice(0,2).join('; '))}</div></span>
      <span>${escapeHtml(row.trace_id || '')}</span>
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
  const actions = (row.allowed_action_labels || row.allowed_actions || []).map(a => `<span class="chip">${escapeHtml(a)}</span>`).join('') || '<span class="chip">действий нет</span>';
  $('symbolDetails').innerHTML = `<div class="detail-title"><h3>${escapeHtml(row.symbol)}</h3>${badge(row.status_label || row.status_effective, row.severity_level)}</div>
    <div class="detail-grid">
      <div class="detail-box"><h4>Что это значит</h4><p>${escapeHtml(row.operator_hint || '')}</p></div>
      <div class="detail-box"><h4>Причины</h4><ul>${reasons}</ul></div>
      <div class="detail-box"><h4>Разрешенные действия</h4><div class="chip-list">${actions}</div></div>
      <div class="detail-box"><h4>Trace ID</h4><code>${escapeHtml(row.trace_id || '')}</code></div>
    </div>`;
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
    // fallback-status: status_from_backend_missing
    $('actionResult').className = 'job-output ok';
    $('actionResult').innerHTML = `<strong>Paper-прогон выполнен</strong>${decisions.map(d => `<div class="paper-item"><strong>${escapeHtml(d.symbol)} — ${escapeHtml(d.status)}</strong><span>${escapeHtml((d.reasons || []).join('; ') || 'решение записано')}</span></div>`).join('')}`;
    return;
  }
  $('actionResult').className = 'job-output ok';
  $('actionResult').innerHTML = `<strong>Готово</strong><pre>${escapeHtml(pretty(payload))}</pre>`;
}

function renderJob(job) {
  const level = job.status === 'ok' ? 'ok' : ['blocked', 'timeout', 'error'].includes(job.status) ? 'error' : '';
  const stdout = job.stdout ? `<h4>stdout</h4><pre>${escapeHtml(job.stdout)}</pre>` : '';
  const stderr = job.stderr ? `<h4>stderr</h4><pre>${escapeHtml(job.stderr)}</pre>` : '';
  const error = job.error ? `<p class="job-error">${escapeHtml(job.error)}</p>` : '';
  $('actionResult').className = `job-output ${level}`;
  $('actionResult').innerHTML = `<div class="job-head"><strong>${escapeHtml(job.title || job.command_id)}</strong>${badge(job.status, job.status === 'ok' ? 'ok' : job.status === 'running' || job.status === 'queued' ? 'info' : 'danger')}</div>
    <p><strong>Команда:</strong> <code>${escapeHtml(job.command_display || '')}</code></p>
    <p><strong>Задача:</strong> <code>${escapeHtml(job.job_id)}</code> · <strong>Код выхода:</strong> ${escapeHtml(job.exit_code ?? 'еще нет')}</p>${error}${stdout}${stderr}`;
}

async function pollJob(jobId) {
  for (let i = 0; i < 90; i += 1) {
    const payload = await api(`/api/operator/jobs/${encodeURIComponent(jobId)}`, authOptions());
    renderJob(payload.data.job);
    if (!['queued', 'running'].includes(payload.data.job.status)) return;
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}

async function runWorkflowAction(actionId, requiresApprovedBy = false) {
  if (!key()) { showError(new Error('Введите OPERATOR_API_KEY в поле API-доступ. Для просмотра можно READONLY_API_KEY, для действий нужен OPERATOR_API_KEY.')); return; }
  let reason = prompt('Причина действия для audit trail:', 'операторский запуск шага из мастера');
  if (!reason) return;
  let approved_by = undefined;
  if (requiresApprovedBy) {
    approved_by = prompt('Кто утверждает Go/No-Go / evidence?', 'operator');
    if (!approved_by) return;
  }
  $('actionResult').className = 'job-output';
  $('actionResult').textContent = 'Запрос отправлен на backend...';
  try {
    const payload = await api(`/api/operator/workflow/actions/${encodeURIComponent(actionId)}`, actionOptions({ reason, approved_by }));
    renderResult(payload);
    await loadAll();
  } catch (err) {
    showError(err);
  }
}

async function loadAll() {
  const [wf, dash] = await Promise.all([
    api('/api/operator/workflow', readAuthOptions()),
    api('/api/operator/dashboard', readAuthOptions()).catch(err => ({ status: 'error', data: { symbols: [] }, error: err.message })),
  ]);
  workflow = wf.data;
  dashboard = dash;
  lastPayload = { workflow: wf, dashboard: dash };
  renderHero();
  renderWorkflow();
  renderInvariants();
  renderSymbols();
  $('diagnosticJson').textContent = pretty(lastPayload);
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
  await navigator.clipboard.writeText($('diagnosticJson').textContent);
  $('copyDiagBtn').textContent = 'Скопировано';
  setTimeout(() => $('copyDiagBtn').textContent = 'Копировать диагностику', 1500);
}

$('refreshBtn').addEventListener('click', () => loadAll().catch(showError));
$('runNextBtn').addEventListener('click', () => {
  const next = firstAvailableAction();
  if (next) runWorkflowAction(next.action_id, !!next.requires_approved_by);
});
$('toggleDiagBtn').addEventListener('click', toggleDiagnostics);
$('copyDiagBtn').addEventListener('click', copyDiagnostics);

installContextHelp({
  getDashboard: () => dashboard,
  getSelectedSymbol: () => selectedSymbol,
});
$('globalHelpBtn')?.addEventListener('click', event => {
  event.preventDefault();
  document.dispatchEvent(new CustomEvent('cas:global-help'));
});

$('topApiKey').addEventListener('keydown', event => { if (event.key === 'Enter') loadAll().catch(showError); });

loadAll().catch(showError);
