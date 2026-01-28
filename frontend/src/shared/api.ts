type ApiRequestOptions = Omit<RequestInit, 'body' | 'headers'> & {
  body?: unknown;
  headers?: Record<string, string>;
};

export async function apiRequest<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(headers || {}),
    },
    ...rest,
  };

  if (body !== undefined) {
    config.body = typeof body === 'string' ? body : JSON.stringify(body);
  }

  const response = await fetch(url, config);
  if (!response.ok) {
    let message = '请求失败';
    const text = await response.text();
    if (text) {
      try {
        const data = JSON.parse(text);
        message = data.detail || message;
      } catch (err) {
        message = text;
      }
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return null as T;
  }
  return response.json();
}
