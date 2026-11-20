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

/**
 * fetch con timeout (por defecto 8s) para que ningún panel se quede "cargando" para siempre
 * cuando el backend está caído o colgado.
 */
export function apiFetch(path: string, init: RequestInit = {}, timeoutMs = 8000): Promise<Response> {
  return fetch(apiUrl(path), { ...init, signal: init.signal ?? AbortSignal.timeout(timeoutMs) });
}

/** Mensaje legible para errores de red. */
export function describeFetchError(err: unknown): string {
  if (err instanceof DOMException && (err.name === 'TimeoutError' || err.name === 'AbortError')) {
    return 'El backend no respondió a tiempo.';
  }
  if (err instanceof TypeError) {
    return `No se pudo conectar con el backend (${API_BASE}).`;
  }
  return err instanceof Error ? err.message : 'Error desconocido.';
}
