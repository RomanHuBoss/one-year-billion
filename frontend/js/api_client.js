const READONLY_KEY_STORAGE = 'cas_readonly_api_key_session';

export function getReadApiKey() {
  try {
    return sessionStorage.getItem(READONLY_KEY_STORAGE) || '';
  } catch (_err) {
    return '';
  }
}

export function setReadApiKey(value) {
  const key = String(value || '').trim();
  try {
    if (key) {
      sessionStorage.setItem(READONLY_KEY_STORAGE, key);
    } else {
      sessionStorage.removeItem(READONLY_KEY_STORAGE);
    }
  } catch (_err) {
    // Браузер может запретить sessionStorage. В этом случае ключ просто не
    // запоминается, а оператор увидит обычную 401-ошибку и сможет повторить ввод.
  }
  return key;
}

export function clearReadApiKey() {
  try {
    sessionStorage.removeItem(READONLY_KEY_STORAGE);
  } catch (_err) {
    // Безопасный no-op.
  }
}

function headersWithReadKey(optionHeaders = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...optionHeaders,
  };
  const hasApiKey = Object.keys(headers).some(key => key.toLowerCase() === 'x-api-key');
  const readKey = getReadApiKey();
  if (!hasApiKey && readKey) {
    headers['x-api-key'] = readKey;
  }
  return headers;
}

export async function api(path, options = {}) {
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const response = await fetch(path, {
    ...requestOptions,
    headers: headersWithReadKey(optionHeaders),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ? JSON.stringify(payload.detail) : `${response.status}`;
    const message = response.status === 401
      ? `${detail}. Укажите READONLY_API_KEY для чтения панели или OPERATOR_API_KEY для команд.`
      : detail;
    throw new Error(`Ошибка API ${response.status}: ${message}`);
  }
  return payload;
}
