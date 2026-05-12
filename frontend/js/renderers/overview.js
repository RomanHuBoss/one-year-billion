import { renderBadge } from '../status_contract.js';

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

export function renderSymbols(rows, onSelect = null) {
  const body = document.getElementById('symbolsBody');
  body.innerHTML = rows.map((row, idx) => `
    <tr data-row-index="${idx}">
      <td>${escapeHtml(row.symbol)}</td>
      <td>${renderBadge(row)}</td>
      <td>${escapeHtml(row.severity)}</td>
      <td>${escapeHtml((row.reasons || []).join(', '))}</td>
      <td><code>${escapeHtml(row.trace_id)}</code></td>
      <td>${escapeHtml((row.allowed_actions || []).join(', '))}</td>
    </tr>
  `).join('');
  [...body.querySelectorAll('tr')].forEach(tr => {
    tr.addEventListener('click', () => onSelect && onSelect(rows[Number(tr.dataset.rowIndex)]));
  });
  if (rows.length && onSelect) onSelect(rows[0]);
}
