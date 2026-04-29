type ApiRequestOptions = Omit<RequestInit, 'body' | 'headers'> & {
  body?: unknown;
  headers?: Record<string, string>;
};

type ApiAuthSession = {
  token: string;
  audience?: string | null;
};

let apiAuthSession: ApiAuthSession | null = null;

export function setApiAuthSession(session: ApiAuthSession | null) {
  apiAuthSession = session;
}

export async function apiRequest<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const authHeaders: Record<string, string> = apiAuthSession?.token
    ? {
        'X-Portal-JWT': apiAuthSession.token,
        'X-Portal-Audience': apiAuthSession.audience || window.location.origin,
      }
    : {};
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
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
    let code = '';
    const text = await response.text();
    if (text) {
      try {
        const data = JSON.parse(text);
        message = data.detail || message;
        code = data.code || '';
      } catch (err) {
        message = text;
      }
    }
    if (response.status === 401 && (code === 'SSO_JWT_INVALID' || message.includes('SSO_JWT_INVALID'))) {
      window.portalAuth?.clearJwtSession?.();
      void window.portalAuth?.requireJwtUser?.();
      throw new Error('登录凭证已失效，正在重新登录/请重新登录');
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return null as T;
  }
  return response.json();
}
