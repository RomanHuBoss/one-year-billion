import { api } from './api_client.js';
import { renderSymbols } from './renderers/overview.js';

function pretty(data) { return JSON.stringify(data, null, 2); }

async function loadAll() {
  const [health, risk, ml, runtime, overview] = await Promise.all([
    api('/api/health'), api('/api/risk/status'), api('/api/ml/health'), api('/api/runtime/preflight'), api('/api/state/overview')
  ]);
  document.getElementById('health').textContent = pretty(health.data);
  document.getElementById('risk').textContent = pretty(risk.data);
  document.getElementById('ml').textContent = pretty(ml.data);
  document.getElementById('runtime').textContent = pretty({ status: runtime.status, reasons: runtime.reasons, ...runtime.data });
  renderSymbols(overview.data.symbols, row => {
    // Карточка деталей получает тот же объект backend status_effective, что и таблица.
    document.getElementById('symbolDetails').textContent = pretty(row);
  });
}

async function runPaper() {
  const result = await api('/api/paper/run-once', { method: 'POST', body: '{}' });
  document.getElementById('paperResult').textContent = pretty(result.data);
}

document.getElementById('refreshBtn').addEventListener('click', loadAll);
document.getElementById('paperRunBtn').addEventListener('click', runPaper);
loadAll().catch(err => { document.body.insertAdjacentHTML('beforeend', `<pre>${err.message}</pre>`); });
