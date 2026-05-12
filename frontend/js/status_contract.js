// Visual mapping only. Status, reasons and allowed actions come from backend.
export function statusClass(row) {
  if (row.status_effective === 'ACTIVE') return 'ok';
  if (row.status_effective === 'ERROR_RECONCILIATION_REQUIRED') return 'critical';
  if (row.status_effective === 'BLOCKED' || row.status_effective === 'DE_RISK') return 'high';
  if (row.status_effective === 'NO_TRADE' || row.status_effective === 'PENDING') return 'medium';
  return 'info';
}

export function renderBadge(row) {
  return `<span class="badge ${statusClass(row)}">${row.status_effective}</span>`;
}
