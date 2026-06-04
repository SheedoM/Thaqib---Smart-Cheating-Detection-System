/** API origin: empty string uses same origin (Vite dev proxy → FastAPI). */
const RAW = import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE;

export const API_ORIGIN = typeof RAW === 'string' ? RAW.replace(/\/$/, '') : '';

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_ORIGIN}${p}`;
}

function readCookie(name: string): string | null {
  const value = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(`${name}=`));
  return value ? decodeURIComponent(value.split('=').slice(1).join('=')) : null;
}

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (!headers.has('X-CSRF-Token')) {
      const csrfToken = readCookie('thaqib_csrf_token');
      if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
    }
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }

  return fetch(apiUrl(path), {
    ...init,
    credentials: 'include',
    headers,
  });
}

/** WebSocket origin for PTT (same-origin Vite proxy to backend :8001 in dev). */
export function wsOrigin(): string {
  const o = import.meta.env.VITE_WS_ORIGIN;
  if (typeof o === 'string' && o.length > 0) return o.replace(/\/$/, '');

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
}

/** WebSocket URL for a hall's voice channel. */
export function voiceWebSocketUrl(hallId: string): string {
  return `${wsOrigin()}/api/v1/voice/ws/${encodeURIComponent(hallId)}`;
}

export const STREAM_BASE = '/api/stream';
