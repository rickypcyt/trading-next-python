'use client';

import { RefreshCw, WifiOff } from 'lucide-react';
import { API_BASE } from '@/lib/api';

interface ConnectionBannerProps {
  backendStatus: 'loading' | 'online' | 'offline';
  wsStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  error?: string | null;
  onRetry: () => void;
}

/** Aviso claro cuando el backend no responde. No se muestra si todo funciona. */
export default function ConnectionBanner({ backendStatus, wsStatus, error, onRetry }: ConnectionBannerProps) {
  if (backendStatus === 'online' && wsStatus === 'connected') return null;
  if (backendStatus === 'loading') return null;

  const offline = backendStatus === 'offline';
  return (
    <div
      role="alert"
      className={`mb-6 rounded-lg border p-4 flex flex-col sm:flex-row sm:items-center gap-3 ${
        offline ? 'border-red-500/40 bg-red-500/10' : 'border-amber-500/40 bg-amber-500/10'
      }`}
    >
      <WifiOff className={`w-6 h-6 shrink-0 ${offline ? 'text-red-400' : 'text-amber-400'}`} />
      <div className="flex-1 text-sm">
        <div className={`font-semibold ${offline ? 'text-red-300' : 'text-amber-300'}`}>
          {offline ? 'Backend sin conexión' : 'Tiempo real no disponible'}
        </div>
        <div className="text-gray-400 text-xs mt-1">
          {offline ? (
            <>
              {error ?? `No se pudo conectar con ${API_BASE}.`} Arranca todo con{' '}
              <code className="px-1 py-0.5 rounded bg-black/50 text-gray-200">bun run dev</code> y la página se
              reconectará sola. Mientras tanto los paneles muestran 0 porque no hay datos, no porque no haya trades.
            </>
          ) : (
            <>Los datos se actualizan cada 15 s; el WebSocket está reconectando.</>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-600 text-gray-200 text-xs hover:bg-white/10 transition-colors"
      >
        <RefreshCw className="w-3 h-3" /> Reintentar ahora
      </button>
    </div>
  );
}
