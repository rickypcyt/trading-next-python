'use client';

import { useState, useEffect, useCallback, type SetStateAction } from 'react';
import {
  Settings, Play, Pause, Activity, Zap, TrendingUp, Cpu, BarChart3,
  CheckCircle2, XCircle, Clock, DollarSign, Target,
  ChevronDown, ChevronUp, type LucideIcon,
} from 'lucide-react';
import { toast } from 'react-toastify';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Engine {
  type: string;
  status: 'idle' | 'running' | 'error';
  last_activity: string | null;
  trades_generated: number;
  errors: number;
  metadata: Record<string, unknown>;
}

interface MicroProfitStats {
  total_micro_trades: number;
  successful_trades: number;
  win_rate: number;
  total_profit: number;
  avg_profit_per_trade: number;
  current_capital: number;
  target_profit_per_trade: number;
  success_rate_vs_target: number;
}

interface TradingModeInfo {
  name: string;
  risk_percentage: number;
  win_rate: number;
  reward_risk_ratio: number;
  max_consecutive_losses: number;
  trades_per_hour: number;
}

type BinanceModeStatusMap = Record<string, 'running' | 'stopped'>;
type StrategyStyleKey = 'blue' | 'green' | 'purple' | 'orange' | 'cyan' | 'pink';

interface EngineControlPanelProps {
  className?: string;
  onGenerateBinanceTrade: () => Promise<void> | void;
  onClearTrades: () => Promise<void> | void;
  onResetStatus: () => Promise<void> | void;
  onGenerateIntelligentTrade: () => Promise<void> | void;
  selectedIntelligentStrategies: string[];
  setSelectedIntelligentStrategies: (value: SetStateAction<string[]>) => void;
  microProfitStats: MicroProfitStats | null;
  onGenerateMicroProfit: (iterations: number) => Promise<void> | void;
  tradingModes: Record<string, TradingModeInfo>;
  binanceModeStatus: BinanceModeStatusMap;
  selectedModes: string[];
  onBinanceModeControl: (action: 'select' | 'generate', mode: string) => Promise<void> | void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STRATEGY_OPTIONS: Array<{ key: string; name: string; style: StrategyStyleKey }> = [
  { key: 'MACD_Signal',         name: 'MACD Signal',        style: 'blue'   },
  { key: 'MA_Cross',            name: 'MA Cross',           style: 'green'  },
  { key: 'RSI_Divergence',      name: 'RSI Divergence',     style: 'purple' },
  { key: 'Bollinger_Bands',     name: 'Bollinger Bands',    style: 'orange' },
  { key: 'Volume_Breakout',     name: 'Volume Breakout',    style: 'cyan'   },
  { key: 'Support_Resistance',  name: 'Support/Resistance', style: 'pink'   },
];

const STRATEGY_STYLE_MAP: Record<StrategyStyleKey, { button: string; dot: string }> = {
  blue:   { button: 'bg-blue-600/20 border-blue-500 text-blue-300',     dot: 'bg-blue-400'   },
  green:  { button: 'bg-green-600/20 border-green-500 text-green-300',  dot: 'bg-green-400'  },
  purple: { button: 'bg-purple-600/20 border-purple-500 text-purple-300', dot: 'bg-purple-400' },
  orange: { button: 'bg-orange-600/20 border-orange-500 text-orange-300', dot: 'bg-orange-400' },
  cyan:   { button: 'bg-cyan-600/20 border-cyan-500 text-cyan-300',     dot: 'bg-cyan-400'   },
  pink:   { button: 'bg-pink-600/20 border-pink-500 text-pink-300',     dot: 'bg-pink-400'   },
};

const ENGINE_ICONS: Record<string, LucideIcon> = {
  simulation:   Activity,
  binance_mode: Zap,
  intelligent:  TrendingUp,
  micro_profit: DollarSign,
  execution:    Cpu,
  trading:      BarChart3,
  binance_advanced: Target,  // Icono para market making
};

const ENGINE_INFO: Record<string, { label: string; description: string; highlights: string[] }> = {
  simulation: {
    label: 'Market Simulator',
    description: 'Reproduce historical market data to stress-test strategies before risking capital.',
    highlights: ['Paper trading', 'Deterministic playback', 'Low latency'],
  },
  binance_mode: {
    label: 'Binance Live Engine',
    description: 'Escucha el order book en tiempo real y ejecuta señales sobre tu cuenta de Binance.',
    highlights: ['WS order book', 'Live fills', 'Risk guardrails'],
  },
  intelligent: {
    label: 'Technical Analysis Engine',
    description: 'Motor multi-estrategia que combina señales MACD, MA, RSI y bandas para emitir trades inteligentes.',
    highlights: ['Multi-strategy', 'Signal ranking', 'Auto risk adjust'],
  },
  micro_profit: {
    label: 'Micro Profit Generator',
    description: 'Busca micro ineficiencias repetibles (≥$0.01) para sumar ganancias consistentes.',
    highlights: ['Scalping', 'High hit-rate', 'Auto batching'],
  },
  execution: {
    label: 'Execution Orchestrator',
    description: 'Coordina el enrutamiento de órdenes, slippage control y gestión de fills.',
    highlights: ['Smart routing', 'Slippage control', 'Fill analytics'],
  },
  trading: {
    label: 'Orders & Portfolio',
    description: 'Mantiene la cartera actualizada, consolida trades y expone estadísticas clave.',
    highlights: ['Portfolio sync', 'PnL tracking', 'Exposure limits'],
  },
  binance_advanced: {
    label: 'Binance Advanced Market Making',
    description: 'Motor avanzado que genera trades ADV_MARKET_MAKING_BUY con estrategias de market making en tiempo real.',
    highlights: ['Market making', '85% win rate', 'Real-time Binance data', 'Advanced strategies'],
  },
};

const PANEL_WRAPPER = 'relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-slate-950/95 via-gray-950/70 to-black/80 shadow-[0_0_60px_rgba(34,211,238,0.25)] backdrop-blur-xl';
const SECTION_SURFACE = 'relative overflow-hidden rounded-2xl border border-cyan-500/15 bg-gradient-to-br from-gray-950/90 via-gray-900/65 to-slate-950/80 shadow-[0_0_35px_rgba(59,130,246,0.15)]';
const SECTION_SURFACE_ORANGE = `${SECTION_SURFACE} border-amber-500/30 shadow-[0_0_40px_rgba(249,115,22,0.22)] from-amber-950/80 via-gray-950/55 to-slate-950/80`;
const TAG_CHIP = 'text-[10px] uppercase tracking-[0.25em] px-3 py-1 border border-gray-700/70 rounded-lg bg-gray-900/70 text-gray-300 shadow-[0_0_15px_rgba(148,163,184,0.12)]';

const STATUS_STYLES: Record<string, { bg: string; border: string; text: string }> = {
  idle:    { bg: 'bg-gray-900/60',    border: 'border-gray-800',       text: 'text-gray-300'    },
  running: { bg: 'bg-emerald-900/40', border: 'border-emerald-500/40', text: 'text-emerald-400' },
  error:   { bg: 'bg-red-900/40',     border: 'border-red-500/40',     text: 'text-red-400'     },
};

const BTN = 'px-4 py-2 rounded-lg font-semibold text-xs uppercase tracking-[0.3em] font-mono flex items-center gap-2 transition-all border border-transparent shadow-[0_0_18px_rgba(56,189,248,0.16)]';

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeader({
  icon: Icon,
  label,
  color = 'text-cyan-300',
  expanded,
  onToggle,
}: {
  icon: LucideIcon;
  label: string;
  color?: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between group"
    >
      <div className={`flex items-center gap-2 uppercase tracking-wide text-xs font-semibold ${color}`}>
        <Icon className="w-4 h-4" />
        {label}
      </div>
      {expanded
        ? <ChevronUp className="w-4 h-4 text-gray-500 group-hover:text-gray-300 transition-colors" />
        : <ChevronDown className="w-4 h-4 text-gray-500 group-hover:text-gray-300 transition-colors" />}
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const EngineControlPanel: React.FC<EngineControlPanelProps> = ({
  className = '',
  onGenerateBinanceTrade,
  onClearTrades,
  onResetStatus,
  onGenerateIntelligentTrade,
  selectedIntelligentStrategies,
  setSelectedIntelligentStrategies,
  microProfitStats,
  onGenerateMicroProfit,
  tradingModes,
  binanceModeStatus,
  selectedModes,
  onBinanceModeControl,
}) => {
  const [engines, setEngines] = useState<Record<string, Engine>>({});
  const [loading, setLoading] = useState(true);
  const [selectedEngines, setSelectedEngines] = useState<Set<string>>(new Set());
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Collapsed state per section
  const [sections, setSections] = useState({
    engines:    true,
    binance:    true,
    technical:  true,
    profit:     true,
    modes:      true,
  });

  const toggleSection = (key: keyof typeof sections) =>
    setSections(prev => ({ ...prev, [key]: !prev[key] }));

  // ── API helpers ──────────────────────────────────────────────────────────────

  const fetchEngines = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:5000/engines');
      if (!res.ok) throw new Error();
      const data = await res.json();
      setEngines(data.engines ?? {});
      const running = Object.entries(data.engines ?? {})
        .filter(([, e]) => (e as Engine).status === 'running')
        .map(([id]) => id);
      setSelectedEngines(new Set(running));
    } catch {
      toast.error('Error al cargar engines');
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleEngine = async (engineId: string) => {
    const engine = engines[engineId];
    if (!engine) return;
    const isRunning = engine.status === 'running';
    const url = `http://127.0.0.1:5000/engines/${engineId}/${isRunning ? 'stop' : 'start'}`;
    try {
      const res = await fetch(url, { method: 'POST' });
      if (!res.ok) throw new Error();
      setEngines(prev => ({ ...prev, [engineId]: { ...prev[engineId], status: isRunning ? 'idle' : 'running' } }));
      setSelectedEngines(prev => {
        const s = new Set(prev);
        isRunning ? s.delete(engineId) : s.add(engineId);
        return s;
      });
      toast.success(`Engine ${engineId} ${isRunning ? 'detenido' : 'iniciado'}`);
    } catch {
      toast.error(`Error al ${isRunning ? 'detener' : 'iniciar'} engine ${engineId}`);
    }
  };

  const bulkEngineAction = async (action: 'start' | 'stop', ids?: string[]) => {
    const targets = ids ?? Object.keys(engines);
    await Promise.all(
      targets.map(id => fetch(`http://127.0.0.1:5000/engines/${id}/${action}`, { method: 'POST' }))
    ).catch(() => toast.error(`Error al ${action} engines`));
    toast.success(`Engines ${action === 'start' ? 'iniciados' : 'detenidos'}`);
    fetchEngines();
  };

  const engineAction = async (endpoint: string) => {
    const res = await fetch(endpoint, { method: 'POST' }).catch(() => null);
    if (!res?.ok) { toast.error('Error'); return; }
    toast.success('OK'); fetchEngines();
  };

  useEffect(() => {
    fetchEngines();
    const iv = setInterval(fetchEngines, 10_000);
    return () => clearInterval(iv);
  }, [fetchEngines]);

  // ── Derived counts ───────────────────────────────────────────────────────────

  const engineList   = Object.entries(engines);
  const activeCount  = engineList.filter(([, e]) => e.status === 'running').length;
  const idleCount    = engineList.filter(([, e]) => e.status === 'idle').length;
  const totalTrades  = engineList.reduce((s, [, e]) => s + e.trades_generated, 0);

  const headerStats: Array<{ label: string; value: number; color: 'emerald' | 'slate' | 'cyan' }> = [
    { label: 'Running', value: activeCount, color: 'emerald' },
    { label: 'Idle', value: idleCount, color: 'slate' },
    { label: 'Total Trades', value: totalTrades, color: 'cyan' },
  ];

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className={`${PANEL_WRAPPER} ${className} min-h-[260px] flex items-center justify-center relative`}>
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.35),_transparent_65%)]" />
        <div className="relative flex items-center gap-4">
          <div className="h-10 w-10 rounded-full border-2 border-cyan-300/70 border-t-transparent animate-spin" />
          <span className="text-xs font-mono uppercase tracking-[0.4em] text-cyan-100">Booting engines…</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${PANEL_WRAPPER} ${className}`}>
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.22),_transparent_70%)]" />
      <div className="relative space-y-6 p-6">
        {/* Header */}
        <div className={`${SECTION_SURFACE} p-6`}> 
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-4">
              <div className="relative">
                <div className="absolute inset-0 blur-xl bg-cyan-500/40" />
                <div className="relative rounded-2xl border border-cyan-500/40 bg-cyan-500/10 p-3 shadow-[0_0_30px_rgba(34,211,238,0.35)]">
                  <Settings className="h-6 w-6 text-cyan-200" />
                </div>
              </div>
              <div>
                <span className="text-xs font-mono uppercase tracking-[0.4em] text-gray-500">Command Console</span>
                <h2 className="mt-2 text-2xl font-semibold uppercase tracking-[0.2em] text-cyan-100">Engine Control Panel</h2>
                <p className="mt-3 text-sm leading-relaxed text-gray-400 max-w-xl">
                  Orquesta los motores algorítmicos, monitorea estadísticas en vivo y dispara acciones tácticas sin abandonar el cockpit.
                </p>
              </div>
            </div>
            <div className="w-full lg:w-auto space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                {headerStats.map(({ label, value, color }) => (
                  <div
                    key={label}
                    className={`rounded-2xl border px-4 py-3 shadow-[0_0_30px_rgba(59,130,246,0.25)] ${
                      color === 'emerald'
                        ? 'border-emerald-500/30 bg-emerald-500/10'
                        : color === 'cyan'
                          ? 'border-cyan-500/30 bg-cyan-500/10'
                          : 'border-slate-500/30 bg-slate-800/40'
                    }`}
                  >
                    <p className="text-[10px] uppercase tracking-[0.4em] text-gray-300">{label}</p>
                    <p className="mt-2 text-2xl font-mono font-semibold text-gray-100">{value}</p>
                  </div>
                ))}
              </div>
              <button
                onClick={async () => { setIsRefreshing(true); await fetchEngines(); setIsRefreshing(false); }}
                disabled={isRefreshing}
                className={`${BTN} w-full justify-center bg-cyan-500/20 text-cyan-100 border-cyan-400/50 hover:-translate-y-0.5 hover:bg-cyan-500/30 hover:shadow-[0_0_30px_rgba(34,211,238,0.4)] disabled:cursor-not-allowed disabled:opacity-50`}
              >
                {isRefreshing ? (
                  <span className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full border border-cyan-200 border-t-transparent animate-spin" />
                    Syncing…
                  </span>
                ) : (
                  <>
                    <Activity className="h-4 w-4" /> Refresh Pulse
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Engines */}
        <div className={`${SECTION_SURFACE} p-6 space-y-5`}>
          <SectionHeader icon={Cpu} label="Engines" expanded={sections.engines} onToggle={() => toggleSection('engines')} />
          {sections.engines && (
            <>
              <div className="flex flex-wrap gap-2">
                <button onClick={() => engineAction('http://127.0.0.1:5000/engines/start-all')} className={`${BTN} bg-emerald-500/20 border-emerald-400/60 text-emerald-100 hover:-translate-y-0.5`}> <Play className="h-4 w-4" /> Start All </button>
                <button onClick={() => engineAction('http://127.0.0.1:5000/engines/stop-all')} className={`${BTN} bg-red-500/20 border-red-400/60 text-red-100 hover:-translate-y-0.5`}> <Pause className="h-4 w-4" /> Stop All </button>
                <button
                  onClick={() => bulkEngineAction('start', Array.from(selectedEngines))}
                  disabled={selectedEngines.size === 0}
                  className={`${BTN} bg-cyan-500/15 border-cyan-400/50 text-cyan-100 hover:-translate-y-0.5 disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <Play className="h-4 w-4" /> Start ({selectedEngines.size})
                </button>
                <button
                  onClick={() => bulkEngineAction('stop', Array.from(selectedEngines).filter(id => engines[id]?.status === 'running'))}
                  disabled={selectedEngines.size === 0}
                  className={`${BTN} bg-orange-500/20 border-orange-400/60 text-orange-100 hover:-translate-y-0.5 disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <Pause className="h-4 w-4" /> Stop ({selectedEngines.size})
                </button>
                <div className="ml-auto flex gap-2 items-center">
                  <button onClick={() => setSelectedEngines(new Set(Object.keys(engines)))} className={`${BTN} bg-transparent border-gray-700 text-gray-400 hover:border-cyan-400 hover:text-cyan-200`}>Select All</button>
                  <button onClick={() => setSelectedEngines(new Set())} className={`${BTN} bg-transparent border-gray-700 text-gray-400 hover:border-cyan-400 hover:text-cyan-200`}>Clear</button>
                </div>
              </div>

              <div className="space-y-3">
                {engineList.map(([engineId, engine]) => {
                  const Icon = ENGINE_ICONS[engine.type] ?? Settings;
                  const info = ENGINE_INFO[engine.type];
                  const ss   = STATUS_STYLES[engine.status];
                  const isRunning  = engine.status === 'running';
                  const isSelected = selectedEngines.has(engineId);

                  return (
                    <div key={engineId} className={`relative overflow-hidden rounded-2xl border p-4 transition-all ${isSelected ? 'border-cyan-500/60 bg-gray-900/80 shadow-[0_0_35px_rgba(34,211,238,0.25)]' : 'border-gray-800 bg-gray-950/70 hover:border-cyan-500/40'}`}>
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => setSelectedEngines(prev => { const s = new Set(prev); s.has(engineId) ? s.delete(engineId) : s.add(engineId); return s; })}
                            className="mt-1 h-4 w-4 rounded border-gray-700 bg-gray-800 text-cyan-500 focus:ring-cyan-500"
                          />
                          <div className={`p-3 rounded-xl border ${ss.bg} ${ss.border}`}>
                            <Icon className={`h-5 w-5 ${ss.text}`} />
                          </div>
                          <div>
                            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
                              {engineId}
                              {typeof engine.metadata.mode === 'string' && (
                                <span className={TAG_CHIP}>{engine.metadata.mode}</span>
                              )}
                            </div>
                            <div className="text-[11px] text-gray-400">
                              {info?.label ?? engine.type} · {engine.trades_generated} trades · {engine.errors} err
                            </div>
                            {info && <p className="mt-1 text-[11px] text-gray-500 max-w-xl leading-snug">{info.description}</p>}
                            {info?.highlights?.length ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {info.highlights.map(highlight => (
                                  <span key={`${engineId}-${highlight}`} className="text-[10px] uppercase tracking-[0.3em] px-2 py-1 rounded-lg bg-gray-900/70 border border-gray-800 text-gray-300">
                                    {highlight}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            {engine.metadata && Object.keys(engine.metadata).length > 0 && (
                              <div className="mt-3 grid gap-1 text-[10px] text-gray-500 sm:grid-cols-2 lg:grid-cols-3">
                                {Object.entries(engine.metadata)
                                  .filter(([key, value]) => key !== 'mode' && (typeof value === 'string' || typeof value === 'number'))
                                  .slice(0, 6)
                                  .map(([key, value]) => (
                                    <div key={`${engineId}-${key}`} className="flex items-center gap-2">
                                      <span className="w-16 uppercase tracking-[0.2em] text-gray-600">{key}</span>
                                      <span className="text-gray-300">{String(value)}</span>
                                    </div>
                                  ))}
                              </div>
                            )}
                            {engine.last_activity && (
                              <div className="mt-2 text-[10px] text-gray-600">
                                Last ping: {new Date(engine.last_activity).toLocaleString()}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 self-end lg:self-auto">
                          <div className={`px-3 py-1 rounded-full text-[10px] font-semibold border flex items-center gap-1 ${ss.bg} ${ss.border} ${ss.text}`}>
                            {engine.status === 'running' && <CheckCircle2 className="h-3 w-3" />}
                            {engine.status === 'idle'    && <Clock className="h-3 w-3" />}
                            {engine.status === 'error'   && <XCircle className="h-3 w-3" />}
                            {engine.status.toUpperCase()}
                          </div>
                          <button
                            onClick={() => toggleEngine(engineId)}
                            className={`${BTN} ${isRunning ? 'bg-red-500/30 border-red-400/70 text-red-100' : 'bg-emerald-500/30 border-emerald-400/70 text-emerald-100'} hover:-translate-y-0.5`}
                          >
                            {isRunning ? <><Pause className="h-4 w-4" /> Stop</> : <><Play className="h-4 w-4" /> Start</>}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Binance & Technical */}
        <div className={`${SECTION_SURFACE_ORANGE} p-6 space-y-5`}>
          <SectionHeader icon={Zap} label="Binance & Technical Analysis" color="text-orange-200" expanded={sections.binance} onToggle={() => toggleSection('binance')} />
          {sections.binance && (
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-1 space-y-3">
                <p className="text-[11px] font-mono uppercase tracking-[0.35em] text-orange-300">Technical Analysis Engine</p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => void onGenerateIntelligentTrade()} className={`${BTN} bg-purple-500/30 border-purple-400/70 text-purple-100 hover:-translate-y-0.5`}>Trade</button>
                  <button onClick={() => void onGenerateBinanceTrade()} className={`${BTN} bg-yellow-500/30 border-yellow-400/70 text-yellow-100 hover:-translate-y-0.5`}>Binance Trade</button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => void onClearTrades()} className={`${BTN} bg-red-500/20 border-red-400/50 text-red-100`}>Clear</button>
                  <button onClick={() => void onResetStatus()} className={`${BTN} bg-slate-700/50 border-slate-500/60 text-slate-200`}>Reset</button>
                </div>
              </div>

              <div className="lg:col-span-2 space-y-3">
                <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-[0.3em] text-gray-500">
                  <span>Strategies — {selectedIntelligentStrategies.length}/{STRATEGY_OPTIONS.length}</span>
                  <button
                    onClick={() => setSelectedIntelligentStrategies(STRATEGY_OPTIONS.map(s => s.key))}
                    className="text-cyan-300 hover:text-cyan-100"
                  >
                    Select All
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                  {STRATEGY_OPTIONS.map(({ key, name, style }) => {
                    const sel = selectedIntelligentStrategies.includes(key);
                    const styles = STRATEGY_STYLE_MAP[style];
                    return (
                      <button
                        key={key}
                        onClick={() => {
                          setSelectedIntelligentStrategies(prev => prev.includes(key) ? prev.filter(s => s !== key) : [...prev, key]);
                        }}
                        className={`px-3 py-2 border rounded-lg text-xs font-mono transition-all ${sel ? styles.button : 'bg-gray-900/40 border-gray-700 text-gray-400'} hover:-translate-y-0.5`}
                      >
                        <span className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${sel ? styles.dot : 'bg-gray-500'}`} />
                          {name}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Profit Maximizer */}
        <div className={`${SECTION_SURFACE} p-6 space-y-5`}>
          <SectionHeader icon={DollarSign} label="Profit Maximizer ($0.01+ per trade)" color="text-green-200" expanded={sections.profit} onToggle={() => toggleSection('profit')} />
          {sections.profit && (
            <>
              <div className="flex flex-wrap gap-2">
                {[5, 10, 20].map(n => (
                  <button key={n} onClick={() => void onGenerateMicroProfit(n)} className={`${BTN} bg-emerald-500/25 border-emerald-400/60 text-emerald-100 hover:-translate-y-0.5`}>
                    {n} Trades (${(n * 0.01).toFixed(2)})
                  </button>
                ))}
              </div>
              {microProfitStats && (
                <div className="grid gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-xs font-mono sm:grid-cols-2 lg:grid-cols-4">
                  {[['Total Trades', microProfitStats.total_micro_trades], ['Win Rate', `${microProfitStats.win_rate}%`], ['Total Profit', `$${microProfitStats.total_profit.toFixed(4)}`], ['Avg Profit', `$${microProfitStats.avg_profit_per_trade.toFixed(4)}`]].map(([label, value]) => (
                    <div key={label as string}>
                      <p className="text-gray-300 uppercase tracking-[0.3em]">{label}</p>
                      <p className="mt-1 text-sm font-semibold text-emerald-100">{value}</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-[11px] text-blue-200 font-mono">
                📋 Sessions optimizadas para targets micro: 90%+ win rate · spreads mínimos · batching automático de órdenes.
              </div>
            </>
          )}
        </div>

        {/* Trading Modes */}
        <div className={`${SECTION_SURFACE} p-6 space-y-5`}>
          <SectionHeader icon={Activity} label="Binance Trading Modes" color="text-orange-200" expanded={sections.modes} onToggle={() => toggleSection('modes')} />
          {sections.modes && (
            Object.keys(tradingModes).length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-6">Trading modes not available. Ensure backend mode endpoints are enabled.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(tradingModes).map(([modeKey, mode]) => {
                  const isRunning  = binanceModeStatus[modeKey] === 'running';
                  const isSelected = selectedModes.includes(modeKey);
                  return (
                    <div key={modeKey} className="relative overflow-hidden rounded-2xl border border-gray-800 bg-gray-950/75 p-4 space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold text-cyan-200 capitalize text-sm">{modeKey}</p>
                          <p className="text-[11px] text-gray-500">{mode.name}</p>
                        </div>
                        <span className={`px-2 py-0.5 text-[10px] font-mono rounded-full border whitespace-nowrap ${isRunning ? 'bg-emerald-500/20 border-emerald-400/60 text-emerald-100' : 'bg-gray-800 border-gray-700 text-gray-500'}`}>
                          {isRunning ? 'RUNNING' : 'STOPPED'}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-1.5 text-[11px] font-mono">
                        {(
                          [
                            ['Risk', `${(mode.risk_percentage * 100).toFixed(1)}%`, 'text-orange-300'],
                            ['Win Rate', `${(mode.win_rate * 100).toFixed(0)}%`, 'text-emerald-300'],
                            ['R:R', `1:${mode.reward_risk_ratio}`, 'text-cyan-300'],
                            ['Max Loss', `${mode.max_consecutive_losses}`, 'text-red-300'],
                            ['T/H', `${mode.trades_per_hour}`, 'text-purple-300'],
                          ] as const
                        ).map(([label, value, color]) => (
                          <div key={label} className="flex justify-between text-gray-500">
                            <span>{label}</span>
                            <span className={color}>{value}</span>
                          </div>
                        ))}
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() => void onBinanceModeControl('select', modeKey)}
                          className={`flex-1 py-1.5 border rounded text-[11px] font-mono transition-all ${
                            isSelected
                              ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-100'
                              : 'border-gray-700 text-gray-400 hover:border-cyan-500'
                          }`}
                        >
                          {isSelected ? 'Active' : 'Select'}
                        </button>
                        <button
                          onClick={() => void onBinanceModeControl('generate', modeKey)}
                          disabled={!isSelected}
                          className={`flex-1 py-1.5 border rounded text-[11px] font-mono transition-all ${
                            isSelected
                              ? 'bg-yellow-500/20 border-yellow-400/60 text-yellow-100 hover:-translate-y-0.5'
                              : 'border-gray-700 text-gray-600 cursor-not-allowed'
                          }`}
                        >
                          Trade
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
};

export default EngineControlPanel;