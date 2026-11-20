'use client';

import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';

type Kind = 'loading' | 'error' | 'empty';

interface PanelStateProps {
  kind: Kind;
  title: string;
  hint?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

const STYLES: Record<Kind, { icon: ReactNode; color: string }> = {
  loading: { icon: <Loader2 className="w-8 h-8 animate-spin" />, color: 'text-cyan-400' },
  error: { icon: <AlertTriangle className="w-8 h-8" />, color: 'text-amber-400' },
  empty: { icon: <Inbox className="w-8 h-8" />, color: 'text-gray-500' },
};

/** Estado uniforme para paneles: cargando / error (con reintentar) / vacío (con explicación). */
export function PanelState({ kind, title, hint, onRetry, className = '' }: PanelStateProps) {
  const s = STYLES[kind];
  return (
    <div className={`flex flex-col items-center justify-center text-center gap-2 py-10 px-4 ${className}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div className={s.color}>{s.icon}</div>
      <div className="text-sm font-medium text-gray-200">{title}</div>
      {hint && <div className="text-xs text-gray-500 max-w-md">{hint}</div>}
      {kind === 'error' && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-300 text-xs hover:bg-amber-500/20 transition-colors"
        >
          <RefreshCw className="w-3 h-3" /> Reintentar
        </button>
      )}
    </div>
  );
}

/** Título de sección para agrupar paneles. */
export function SectionHeader({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex items-baseline gap-3 mb-4 mt-2">
      <h2 className="text-xs font-mono uppercase tracking-[0.3em] text-gray-500">{title}</h2>
      <div className="h-px flex-1 bg-gray-800" />
      {hint && <span className="text-xs text-gray-600 hidden sm:inline">{hint}</span>}
    </div>
  );
}
