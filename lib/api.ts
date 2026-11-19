/**
 * Configuración centralizada del backend.
 *
 * Usa NEXT_PUBLIC_API_URL para cambiar el backend sin tocar componentes.
 * Ejemplo: NEXT_PUBLIC_API_URL=http://192.168.1.10:5000
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:5000';

/** URL del WebSocket derivada del API_BASE. */
export const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws';

/** Helper para construir endpoints absolutos. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}
