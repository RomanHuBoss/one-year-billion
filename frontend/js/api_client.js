function normalizeDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  return '';
}

function operatorHint(status, detailText) {
  const normalized = String(detailText || '').toLowerCase();
  if (status === 401 && normalized.includes('invalid_api_key')) {
    return 'не принят API-ключ доступа к backend. Введите OPERATOR_API_KEY или READONLY_API_KEY, заданный в .env, без пробелов и кавычек; затем повторите действие. Это не ключ Bybit.';
  }
  if (status === 403 && normalized.includes('operator_key_required')) {
    return 'для этого действия нужен именно OPERATOR_API_KEY. READONLY_API_KEY подходит только для чтения статуса.';
  }
  return detailText || `${status}`;
}

export async function api(path, options = {}) {
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const headers = { ...optionHeaders };
  if (requestOptions.body !== undefined && !headers['Content-Type'] && !headers['content-type']) {
    Object.assign(headers, { 'Content-Type': 'application/json' });
  }
  const response = await fetch(path, {
    ...requestOptions,
    headers,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detailText = normalizeDetail(payload.detail) || normalizeDetail(payload.error) || `${response.status}`;
    throw new Error(`Ошибка API ${response.status}: ${operatorHint(response.status, detailText)}`);
  }
  return payload;
}
