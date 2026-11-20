'use client';

import { API_BASE, apiFetch, apiUrl, describeFetchError } from '@/lib/api';
import { useEffect, useState } from 'react';
import { Activity, Brain, RefreshCw, Shield, Target } from 'lucide-react';

interface DecisionSummary {
  symbol: string;
  current_price: number | null;
  regime: string;
  score: number;
  probability: number;
  decision: string;
  risk: string;
  direction: string;
  recommended_strategy: string;
  summary: {
    tendencia_largo_plazo?: string;
    tendencia_media?: string;
    tendencia_corta?: string;
    correccion_actual?: number;
    rsi?: number;
    macd?: number;
    volumen?: number;
    volatilidad?: number;
    soporte?: number;
    resistencia?: number;
    atr_pct?: number;
    beta?: number;
    sharpe?: number;
  };
  factors?: Record<string, number>;
}

export default function DecisionPanel({ className = '' }: { className?: string }) {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [analysis, setAnalysis] = useState<DecisionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [tradeResult, setTradeResult] = useState<any>(null);

  const fetchAnalysis = async (sym: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/strategy/summary?symbol=${sym}`, {}, 20000);
      if (!res.ok) throw new Error(`El backend respondió HTTP ${res.status} al analizar ${sym}.`);
      const data = await res.json();
      setAnalysis(data);
    } catch (err: any) {
      setError(describeFetchError(err));
    } finally {
      setLoading(false);
    }
  };

  const executeTrade = async () => {
    setTradeLoading(true);
    setTradeResult(null);
    try {
      const res = await fetch(apiUrl('/strategy/trade'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      const data = await res.json();
      setTradeResult(data);
      fetchAnalysis(symbol);
    } catch (err: any) {
      setTradeResult({ status: 'error', message: err.message || 'Error de conexión' });
    } finally {
      setTradeLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis(symbol);
  }, [symbol]);

  const decisionColor = (decision?: string) => {
    if (!decision) return 'text-gray-400';
    if (decision === 'COMPRAR') return 'text-emerald-400';
    if (decision === 'VENDER') return 'text-rose-400';
    if (decision === 'ESPERAR') return 'text-amber-400';
    return 'text-gray-400';
  };

  const riskBadge = (risk?: string) => {
    if (risk === 'Bajo') return 'bg-emerald-500/20 text-emerald-400';
    if (risk === 'Medio') return 'bg-amber-500/20 text-amber-400';
    if (risk === 'Alto') return 'bg-rose-500/20 text-rose-400';
    return 'bg-gray-700 text-gray-300';
  };

  return (
    <div className={`bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm ${className}`}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-indigo-400" />
          <h2 className="text-xl font-bold text-white">Motor de Decisión Unificado</h2>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="bg-gray-900 border border-gray-700 text-white rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
            <option value="BNBUSDT">BNBUSDT</option>
            <option value="XRPUSDT">XRPUSDT</option>
            <option value="ADAUSDT">ADAUSDT</option>
          </select>
          <button
            onClick={() => fetchAnalysis(symbol)}
            disabled={loading}
            className="p-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors"
            title="Recargar"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-rose-500/20 border border-rose-500/30 text-rose-200 rounded">
          {error}
          <button type="button" onClick={() => fetchAnalysis(symbol)} className="ml-3 underline text-rose-100 hover:text-white">Reintentar</button>
        </div>
      )}

      {!analysis && !loading && !error && (
        <div className="text-gray-400 text-sm">Sin análisis todavía. Pulsa el botón de actualizar (↻) para analizar {symbol}.</div>
      )}

      {loading && !analysis && (
        <div className="text-gray-400 flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Analizando múltiples timeframes...
        </div>
      )}

      {analysis && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 border border-gray-800 rounded p-4 flex flex-col justify-between">
            <div className="text-gray-400 text-sm flex items-center gap-2">
              <Target className="w-4 h-4" />
              Decisión
            </div>
            <div className={`text-3xl font-bold ${decisionColor(analysis.decision)}`}>
              {analysis.decision}
            </div>
            <div className="text-gray-500 text-sm mt-1">
              {analysis.recommended_strategy}
            </div>
          </div>

          <div className="bg-gray-900/50 border border-gray-800 rounded p-4 flex flex-col justify-between">
            <div className="text-gray-400 text-sm flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Probabilidad
            </div>
            <div className="text-3xl font-bold text-white">{analysis.probability}%</div>
            <div className="text-gray-500 text-sm mt-1">Score: {analysis.score}</div>
          </div>

          <div className="bg-gray-900/50 border border-gray-800 rounded p-4 flex flex-col justify-between">
            <div className="text-gray-400 text-sm flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Riesgo
            </div>
            <div className={`text-3xl font-bold ${riskBadge(analysis.risk).split(' ')[1]}`}>
              {analysis.risk}
            </div>
            <div className="text-gray-500 text-sm mt-1">Régimen: {analysis.regime}</div>
          </div>

          <MetricCard label="Tendencia Largo Plazo" value={analysis.summary?.tendencia_largo_plazo} />
          <MetricCard label="Tendencia Media" value={analysis.summary?.tendencia_media} />
          <MetricCard label="Tendencia Corta" value={analysis.summary?.tendencia_corta} />

          <MetricCard label="Corrección actual" value={analysis.summary?.correccion_actual} suffix="%" />
          <MetricCard label="RSI" value={analysis.summary?.rsi} />
          <MetricCard label="MACD" value={analysis.summary?.macd} />

          <MetricCard label="Volumen" value={analysis.summary?.volumen} suffix="%" />
          <MetricCard label="Volatilidad" value={analysis.summary?.volatilidad} suffix="%" />
          <MetricCard label="ATR %" value={analysis.summary?.atr_pct} suffix="%" />

          <MetricCard label="Soporte" value={analysis.summary?.soporte} prefix="$" />
          <MetricCard label="Resistencia" value={analysis.summary?.resistencia} prefix="$" />
          <MetricCard label="Precio" value={analysis.current_price} prefix="$" />

          <MetricCard label="Beta" value={analysis.summary?.beta} />
          <MetricCard label="Sharpe" value={analysis.summary?.sharpe} />
          <MetricCard label="Estrategia" value={analysis.recommended_strategy} />
        </div>
      )}

      {analysis && (
        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={executeTrade}
            disabled={tradeLoading || analysis.decision === 'NO ENTRAR'}
            className={`px-4 py-2 rounded font-medium transition-colors ${
              analysis.decision === 'NO ENTRAR'
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            {tradeLoading ? 'Ejecutando...' : 'Ejecutar trade con motor unificado'}
          </button>
          {tradeResult && (
            <span className={`text-sm ${tradeResult.status === 'executed' ? 'text-emerald-400' : 'text-amber-400'}`}>
              {tradeResult.status === 'executed'
                ? `Trade ejecutado: P&L $${tradeResult.pnl?.toFixed(2)}`
                : tradeResult.message || tradeResult.status}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, prefix, suffix }: { label: string; value?: number | string | null; prefix?: string; suffix?: string }) {
  const isNumber = typeof value === 'number';
  const display = isNumber
    ? `${isFinite(value) ? value.toFixed(2) : '-'}${suffix || ''}`
    : value !== undefined && value !== null
    ? `${value}${suffix || ''}`
    : '-';
  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded p-4">
      <div className="text-gray-400 text-sm mb-1">{label}</div>
      <div className="text-xl font-semibold text-white">
        {prefix || ''}{display}
      </div>
    </div>
  );
}
