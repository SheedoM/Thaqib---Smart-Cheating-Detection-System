/** API origin: empty string uses same origin (Vite dev proxy → FastAPI). */
const RAW = import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE;

export const API_ORIGIN = typeof RAW === 'string' ? RAW.replace(/\/$/, '') : '';

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_ORIGIN}${p}`;
}

/** WebSocket origin for PTT (FastAPI on :8000 in dev). */
export function wsOrigin(): string {
  const o = import.meta.env.VITE_WS_ORIGIN;
  if (typeof o === 'string' && o.length > 0) return o.replace(/\/$/, '');
  if (import.meta.env.DEV) return 'ws://127.0.0.1:8000';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
}

export function pttWebSocketUrl(clientId: string): string {
  return `${wsOrigin()}/api/v1/ptt/ws/${encodeURIComponent(clientId)}`;
}

export const STREAM_BASE = '/api/stream';
