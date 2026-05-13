export async function api(path, options = {}) {
  const { headers: optionHeaders = {}, ...requestOptions } = options;
  const response = await fetch(path, {
    ...requestOptions,
    headers: {
      'Content-Type': 'application/json',
      ...optionHeaders,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.detail ? JSON.stringify(payload.detail) : `${response.status}`;
    throw new Error(`Ошибка API ${response.status}: ${message}`);
  }
  return payload;
}
