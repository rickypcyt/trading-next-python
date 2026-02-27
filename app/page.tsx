'use client';

import { Activity, AlertTriangle, ArrowDown, ArrowUp, Bell, DollarSign, ExternalLink, TrendingDown, TrendingUp } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import Analisis from './components/Analisis';
import EngineControlPanel from './components/EngineControlPanel';
import TradesTable from './components/TradesTable';
import TradingViewWidget from './components/TradingViewWidget';
import { toast } from 'react-toastify';

export interface Trade {
  id: number;
  timestamp_entry: string;
  timestamp_exit: string;
  symbol: string;
  strategy: string;
  source_engine: string;
  source_mode?: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  requested_entry_price: number;
  requested_exit_price: number;
  size: number;
  investment_amount?: number;
  pnl: number;
  gross_pnl: number;
  pnl_percentage: number;
  total_costs: number;
  entry_fees: number;
  exit_fees: number;
  slippage_cost: number;
  spread_cost: number;
  cost_impact_pct: number;
  duration_formatted: string;
  confidence: number;
  volatility: number;
}

interface TradeEventPayload {
  id?: number | string;
  trade_id?: number | string;
  timestamp_entry?: string;
  entry_time?: string;
  timestamp_exit?: string;
  exit_time?: string;
  symbol?: string;
  ticker?: string;
  strategy?: string;
  source_strategy?: string;
  source_engine?: string;
  source?: string;
  source_mode?: string;
  direction?: string;
  side?: string;
  entry_price?: number | string;
  price?: number | string;
  entry?: number | string;
  exit_price?: number | string;
  exit?: number | string;
  target_price?: number | string;
  size?: number | string;
  quantity?: number | string;
  position_size?: number | string;
  investment_amount?: number | string;
  pnl?: number | string;
  net_pnl?: number | string;
  gross_pnl?: number | string;
  total_costs?: number | string;
  costs?: number | string;
  entry_fees?: number | string;
  exit_fees?: number | string;
  slippage_cost?: number | string;
  spread_cost?: number | string;
  requested_entry_price?: number | string;
  requested_exit_price?: number | string;
  confidence?: number | string;
  volatility?: number | string;
  duration_ms?: number | string;
  duration_formatted?: string;
  [key: string]: unknown;
}

interface Engine {
  type: string;
  status: 'idle' | 'running' | 'error';
  last_activity: string | null;
  trades_generated: number;
  errors: number;
  metadata: Record<string, unknown>;
}

interface Metric {
  id: number;
  timestamp: string;
  win_rate: number;
  sharpe: number;
  max_drawdown: number;
  profit_factor: number;
}

interface Alert {
  id: number;
  timestamp: string;
  type: string;
  message: string;
}

interface EquityPoint {
  timestamp: string;
  capital: number;
}

interface TradingMode {
  name: string;
  risk_percentage: number;
  win_rate: number;
  reward_risk_ratio: number;
  max_consecutive_losses: number;
  trades_per_hour: number;
}

interface BinanceModeStatusMap {
  [mode: string]: 'running' | 'stopped';
}

// Funciones para manejar localStorage
const getStoredStatus = (key: string, defaultValue: string) => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(`trading_${key}`);
    return stored || defaultValue;
  }
  return defaultValue;
};


const setStoredStatus = (key: string, value: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem(`trading_${key}`, value);
  }
};

const DETAILED_TRADE_CSV_HEADERS = [
  'ID',
  'Date',
  'Time',
  'Symbol',
  'Strategy',
  'Engine',
  'Direction',
  'Entry',
  'Exit',
  'Size',
  'Investment',
  'P&L',
  'Gross P&L',
  '%',
  'Costs',
  'Fees',
  'Slippage',
  'Spread',
  'Confidence',
  'Volatility',
  'Duration',
];

function getTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export default function TradingDashboard() {
  const [allTrades, setAllTrades] = useState<Trade[]>([]);
  const [engines, setEngines] = useState<Record<string, Engine>>({});
  const [metrics, setMetrics] = useState<Metric | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [wsStatus, setWsStatus] = useState<string>('disconnected');
  const [selectedIntelligentStrategies, setSelectedIntelligentStrategies] = useState<string[]>([
    'MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance'
  ]);
  const [tradingModes, setTradingModes] = useState<Record<string, TradingMode>>({});
  const [binanceModeStatus, setBinanceModeStatus] = useState<BinanceModeStatusMap>(() => {
    // Always start with consistent initial state to avoid hydration mismatch
    const stored: BinanceModeStatusMap = {};
    const modes = ['conservative', 'hybrid', 'aggressive'];
    modes.forEach(mode => {
      stored[mode] = 'stopped';
    });
    return stored;
  });
  const [selectedModes, setSelectedModes] = useState<string[]>([]);
  const [displayLimit, setDisplayLimit] = useState<number>(50);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [hasMoreTrades, setHasMoreTrades] = useState<boolean>(false);
  const [isDeletingTrades, setIsDeletingTrades] = useState<boolean>(false);

  const formatDurationFromMs = useCallback((durationMs: number) => {
    if (!durationMs || durationMs <= 0) return '0s';
    const totalSeconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
  }, []);

  const normalizeTradeFromEvent = useCallback((payload: TradeEventPayload): Trade => {
    const id = Number(payload.id ?? payload.trade_id ?? Date.now());
    const timestampEntry = payload.timestamp_entry ?? payload.entry_time ?? new Date().toISOString();
    const timestampExit = payload.timestamp_exit ?? payload.exit_time ?? '';
    const toNumber = (value: number | string | undefined): number =>
      value === undefined ? 0 : Number(value) || 0;

    const entryPrice = toNumber(payload.entry_price ?? payload.price ?? payload.entry);
    const exitPrice = toNumber(payload.exit_price ?? payload.exit ?? payload.target_price);
    const size = toNumber(payload.size ?? payload.quantity ?? payload.position_size);
    const investment = toNumber(payload.investment_amount) || (entryPrice && size ? entryPrice * size : 0);
    const pnl = toNumber(payload.pnl ?? payload.net_pnl);
    const grossPnl = toNumber(payload.gross_pnl ?? pnl);
    const totalCosts = toNumber(payload.total_costs ?? payload.costs);
    const entryFees = toNumber(payload.entry_fees);
    const exitFees = toNumber(payload.exit_fees);
    const slippageCost = toNumber(payload.slippage_cost);
    const spreadCost = toNumber(payload.spread_cost);
    const requestedEntryPrice = toNumber(payload.requested_entry_price ?? entryPrice);
    const requestedExitPrice = toNumber(payload.requested_exit_price ?? exitPrice);
    const volatility = toNumber(payload.volatility);
    const confidence = toNumber(payload.confidence);
    const durationMs = toNumber(payload.duration_ms);

    const directionRaw = (payload.direction ?? payload.side ?? 'long').toString().toLowerCase();
    const direction: 'long' | 'short' = directionRaw === 'short' ? 'short' : 'long';

    const notional = investment || (entryPrice * size);
    const pnlPercentage = notional ? (pnl / notional) * 100 : 0;
    const costImpactPct = notional ? (totalCosts / notional) * 100 : 0;

    return {
      id,
      timestamp_entry: timestampEntry,
      timestamp_exit: timestampExit,
      symbol: payload.symbol ?? payload.ticker ?? 'UNKNOWN',
      strategy: payload.strategy ?? payload.source_strategy ?? 'unknown',
      source_engine: payload.source_engine ?? payload.source ?? 'unknown',
      source_mode: payload.source_mode ?? '',
      direction,
      entry_price: entryPrice,
      exit_price: exitPrice,
      requested_entry_price: requestedEntryPrice,
      requested_exit_price: requestedExitPrice,
      size,
      investment_amount: investment,
      pnl,
      gross_pnl: grossPnl,
      pnl_percentage: pnlPercentage,
      total_costs: totalCosts,
      entry_fees: entryFees,
      exit_fees: exitFees,
      slippage_cost: slippageCost,
      spread_cost: spreadCost,
      cost_impact_pct: costImpactPct,
      duration_formatted: payload.duration_formatted ?? formatDurationFromMs(durationMs),
      confidence,
      volatility,
    } as Trade;
  }, [formatDurationFromMs]);

  const addTradeFromEvent = useCallback((payload: TradeEventPayload) => {
    const trade = normalizeTradeFromEvent(payload);
    setAllTrades(prevAll => {
      const deduped = prevAll.filter(existing => existing.id !== trade.id);
      const updatedAll = [trade, ...deduped].sort((a, b) => new Date(b.timestamp_entry).getTime() - new Date(a.timestamp_entry).getTime());
      setTrades(updatedAll.slice(0, displayLimit));
      setHasMoreTrades(updatedAll.length > displayLimit);
      return updatedAll;
    });
  }, [displayLimit, normalizeTradeFromEvent]);

  const removeTradeById = useCallback((tradeId: number) => {
    setAllTrades(prev => {
      const updated = prev.filter(trade => trade.id !== tradeId);
      setTrades(updated.slice(0, displayLimit));
      setHasMoreTrades(updated.length > displayLimit);
      return updated;
    });
  }, [displayLimit]);

  const clearTradesState = useCallback(() => {
    setAllTrades([]);
    setTrades([]);
    setHasMoreTrades(false);
  }, []);

  // Restore stored values after mount to avoid hydration mismatch
  useEffect(() => {
    // Only run on client side and only once on mount
    if (typeof window !== 'undefined') {
      // Restore selected modes from localStorage
      const storedModes = getStoredStatus('selected_binance_modes', '');
      const modesArray = storedModes ? storedModes.split(',') : [];
      setSelectedModes(modesArray);

      // Restore intelligent strategies from localStorage
      const storedStrategies = getStoredStatus('selected_intelligent_strategies', '');
      const strategiesArray = storedStrategies ? storedStrategies.split(',') : [
        'MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance'
      ];
      setSelectedIntelligentStrategies(strategiesArray);

      // Restore mode statuses
    }
  }, []);

  const fetchAllData = useCallback(async () => {
    if (!isRefreshing) {
      setIsRefreshing(true);
    }
    try {
      const [tradesRes, metricsRes, alertsRes, modesRes, enginesRes] = await Promise.all([
        fetch('http://127.0.0.1:5000/trades'),
        fetch('http://127.0.0.1:5000/metrics'),
        fetch('http://127.0.0.1:5000/alerts'),
        fetch('http://127.0.0.1:5000/binance/modes').catch(() => null), // Puede no existir aún
        fetch('http://127.0.0.1:5000/engines')
      ]);

      const [tradesData, metricsData, alertsData, modesData, enginesData] = await Promise.all([
        tradesRes.json(),
        metricsRes.json(),
        alertsRes.json(),
        modesRes?.json().catch(() => ({ modes: {} })), // Default si no existe
        enginesRes.json()
      ]);

      // Guardar todos los trades
      const processedTrades = tradesData.map((trade: Trade) => ({
        ...trade,
        investment_amount: trade.investment_amount || (trade.size * trade.entry_price)
      }));
      setAllTrades(processedTrades);
      
      // Update display trades
      const displayTrades = processedTrades.slice(0, displayLimit);
      setTrades(displayTrades);
      setHasMoreTrades(processedTrades.length > displayLimit);
      
      // Actualizar engines
      setEngines(enginesData.engines ?? {});
      
      setMetrics(metricsData[0] || null);
      setAlerts(alertsData);
      setTradingModes(modesData.modes || {});
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error loading dashboard data', { toastId: 'fetch-error' });
    } finally {
      setIsRefreshing(false);
    }
  }, [displayLimit, isRefreshing]);

  // Update selected strategies when they change
  useEffect(() => {
    if (selectedIntelligentStrategies.length > 0) {
      // Save to localStorage
      setStoredStatus('selected_intelligent_strategies', selectedIntelligentStrategies.join(','));
      
      // Send selected strategies to backend
      fetch('http://127.0.0.1:5000/intelligent/strategies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategies: selectedIntelligentStrategies
        })
      }).catch(error => {
        console.error('Error updating strategies:', error);
      });
    }
  }, [selectedIntelligentStrategies]);

  const addTradeFromEventRef = useRef(addTradeFromEvent);
  const clearTradesStateRef = useRef(clearTradesState);
  const removeTradeByIdRef = useRef(removeTradeById);
  const fetchAllDataRef = useRef(fetchAllData);

  useEffect(() => {
    addTradeFromEventRef.current = addTradeFromEvent;
  }, [addTradeFromEvent]);

  useEffect(() => {
    clearTradesStateRef.current = clearTradesState;
  }, [clearTradesState]);

  useEffect(() => {
    removeTradeByIdRef.current = removeTradeById;
  }, [removeTradeById]);

  useEffect(() => {
    fetchAllDataRef.current = fetchAllData;
  }, [fetchAllData]);

  useEffect(() => {
    fetchAllDataRef.current?.();

    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let reconnectTimeout: NodeJS.Timeout | null = null;

    const connectWebSocket = () => {
      try {
        ws = new WebSocket('ws://127.0.0.1:5000/ws');

        ws.onopen = () => {
          setWsStatus('connected');
          reconnectAttempts = 0;
          toast.success('WebSocket connected', { autoClose: 2000, toastId: 'ws-connected' });
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'binance_simulation_started':
              setStoredStatus('binance', 'running');
              toast.success('💎 Binance real-time simulation started', { toastId: 'binance-started' });
              setEngines(prev => ({
                ...prev,
                binance: { ...prev.binance, status: 'running' }
              }));
              break;

            case 'binance_simulation_stopped':
              setStoredStatus('binance', 'stopped');
              toast.error('⏹️ Binance simulation stopped', { toastId: 'binance-stopped' });
              setEngines(prev => ({
                ...prev,
                binance: { ...prev.binance, status: 'idle' }
              }));
              break;

            case 'intelligent_simulation_started':
              setStoredStatus('intelligent', 'running');
              toast.success('🧠 Intelligent simulation with technical analysis started', { toastId: 'intelligent-started' });
              setEngines(prev => ({
                ...prev,
                intelligent: { ...prev.intelligent, status: 'running' }
              }));
              break;

            case 'intelligent_simulation_stopped':
              setStoredStatus('intelligent', 'stopped');
              toast.error('⏹️ Intelligent simulation stopped', { toastId: 'intelligent-stopped' });
              setEngines(prev => ({
                ...prev,
                intelligent: { ...prev.intelligent, status: 'idle' }
              }));
              break;

            case 'binance_mode_started':
              if (data.data?.mode) {
                const mode = data.data.mode;
                setSelectedModes(prev => {
                  const updated = [...prev.filter(m => m !== mode), mode];
                  setStoredStatus('selected_binance_modes', updated.join(','));
                  return updated;
                });
                setEngines(prev => ({
                  ...prev,
                  [`binance_${mode}`]: {
                    ...prev[`binance_${mode}`],
                    status: 'running',
                    type: 'binance_mode',
                    trades_generated: 0,
                    errors: 0,
                    last_activity: new Date().toISOString(),
                    metadata: { mode }
                  }
                }));
              }
              break;

            case 'binance_mode_stopped':
              if (data.data?.mode) {
                const mode = data.data.mode;
                setSelectedModes(prev => {
                  const updated = prev.filter(m => m !== mode);
                  setStoredStatus('selected_binance_modes', updated.join(','));
                  return updated;
                });
                setEngines(prev => ({
                  ...prev,
                  [`binance_${mode}`]: {
                    ...prev[`binance_${mode}`],
                    status: 'idle'
                  }
                }));
              }
              break;

            case 'engine_started':
              if (data.data?.engine_id) {
                setEngines(prev => ({
                  ...prev,
                  [data.data.engine_id]: {
                    ...prev[data.data.engine_id],
                    status: 'running',
                    last_activity: new Date().toISOString()
                  }
                }));
              }
              break;

            case 'engine_stopped':
              if (data.data?.engine_id) {
                setEngines(prev => ({
                  ...prev,
                  [data.data.engine_id]: {
                    ...prev[data.data.engine_id],
                    status: 'idle',
                    last_activity: new Date().toISOString()
                  }
                }));
              }
              break;

            case 'binance_mode_trade_generated':
              if (data.data) {
                const pnlValue = Number(data.data.pnl ?? 0);
                const sign = pnlValue >= 0 ? '+' : '-';
                toast.info(`📊 Binance ${data.data.mode} trade: ${sign}$${Math.abs(pnlValue).toFixed(2)}`, {
                  toastId: `binance-${data.data.mode}-trade-${data.data.trade_id}`,
                });
                addTradeFromEventRef.current?.(data.data);
              }
              break;

            case 'trade_added':
            case 'real_trade_generated':
            case 'monthly_target_trade_generated':
            case 'intelligent_trade_generated':
              if (data.data) addTradeFromEventRef.current?.(data.data);
              break;

            case 'equity_updated':
            case 'metrics_updated':
            case 'alert_added':
              fetchAllDataRef.current?.();
              break;

            case 'trade_deleted':
              if (data.data?.trade_id !== undefined) {
                removeTradeByIdRef.current?.(Number(data.data.trade_id));
              }
              break;

            case 'trades_cleared':
              clearTradesStateRef.current?.();
              break;
          }
        };

        ws.onclose = () => {
          setWsStatus('disconnected');
          toast.error('WebSocket disconnected', { toastId: 'ws-disconnected' });

          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts += 1;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 5000);
            reconnectTimeout = setTimeout(connectWebSocket, delay);
          }
        };

        ws.onerror = (error) => {
          console.warn('WebSocket connection error - will retry:', error);
          setWsStatus('error');
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        setWsStatus('error');
      }
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  const handleBinanceModeControl = async (action: 'select' | 'generate', mode: string) => {
    try {
      if (action === 'select') {
        const isRunning = binanceModeStatus[mode] === 'running';
        
        if (isRunning) {
          // Detener el modo
          const response = await fetch(`http://127.0.0.1:5000/binance/mode/${mode}/stop`, { method: 'POST' });
          const result = await response.json();
          
          if (result.status === 'stopped') {
            setSelectedModes(prev => prev.filter(m => m !== mode));
            setStoredStatus('selected_binance_modes', selectedModes.filter(m => m !== mode).join(','));
            
            // Actualizar engines inmediatamente
            setEngines(prev => ({
              ...prev,
              [`binance_${mode}`]: { 
                ...prev[`binance_${mode}`], 
                status: 'idle',
                last_activity: new Date().toISOString()
              }
            }));
            
            toast.success(`� Binance ${mode} mode stopped`, { toastId: `binance-${mode}-stopped` });
          }
        } else {
          // Iniciar el modo
          const response = await fetch(`http://127.0.0.1:5000/binance/mode/${mode}/start`, { method: 'POST' });
          const result = await response.json();
          
          if (result.status === 'started') {
            setSelectedModes(prev => [...prev.filter(m => m !== mode), mode]);
            setStoredStatus('selected_binance_modes', [...selectedModes.filter(m => m !== mode), mode].join(','));
            
            // Actualizar engines inmediatamente
            setEngines(prev => ({
              ...prev,
              [`binance_${mode}`]: { 
                ...prev[`binance_${mode}`], 
                status: 'running',
                last_activity: new Date().toISOString()
              }
            }));
            
            toast.success(`🚀 Binance ${mode} mode started`, { toastId: `binance-${mode}-started` });
          }
        }
        fetchAllData(); // Refresh data para otros componentes
      }
    } catch (error) {
      console.error(`Error controlling Binance ${mode}:`, error);
      toast.error(`Error controlling Binance ${mode}`, { toastId: `binance-${mode}-error` });
    }
  };

  const handleGenerateBinanceTrade = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/binance/generate', { method: 'POST' });
      if (!response.ok) throw new Error('Failed to generate Binance trade');
      await response.json().catch(() => null);
      toast.success('⚡ Binance trade generated', { toastId: 'binance-trade-generated' });
      fetchAllData();
    } catch (error) {
      console.error('Error generating Binance trade:', error);
      toast.error('Error generating Binance trade', { toastId: 'binance-trade-error' });
    }
  }, [fetchAllData]);

  const handleGenerateIntelligentTrade = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/intelligent/generate', { method: 'POST' });
      if (!response.ok) throw new Error('Failed to generate intelligent trade');
      await response.json().catch(() => null);
      toast.success('🧠 Intelligent trade generated', { toastId: 'intelligent-trade-generated' });
      fetchAllData();
    } catch (error) {
      console.error('Error generating intelligent trade:', error);
      toast.error('Error generating intelligent trade', { toastId: 'intelligent-trade-error' });
    }
  }, [fetchAllData]);

  
  const clearAllStoredStatus = () => {
  if (typeof window !== 'undefined') {
    const keys = ['binance', 'selected_binance_mode'];
    keys.forEach(key => localStorage.removeItem(`trading_${key}`));
  }
};
  const handleClearAllStatus = () => {
    clearAllStoredStatus();
    setSelectedModes([]);
    setSelectedIntelligentStrategies(['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance']);
    setBinanceModeStatus({
      conservative: 'stopped',
      hybrid: 'stopped',
      aggressive: 'stopped'
    });
    toast.info('🔄 All status cleared from localStorage', { toastId: 'status-cleared' });
  };

  const handleShowMoreTrades = () => {
    const newLimit = displayLimit + 50;
    setDisplayLimit(newLimit);
    setTrades(allTrades.slice(0, newLimit));
    setHasMoreTrades(allTrades.length > newLimit);
    toast.info(`📊 Showing ${newLimit} trades`, { toastId: 'show-more-trades' });
  };

  const handleShowAllTrades = () => {
    setDisplayLimit(allTrades.length);
    setTrades(allTrades);
    setHasMoreTrades(false);
    toast.info(`📊 Showing all ${allTrades.length} trades`, { toastId: 'show-all-trades' });
  };

  const copyAllTrades = useCallback(() => {
    if (allTrades.length === 0) {
      toast.error('No trades to copy', { toastId: 'copy-trades-empty' });
      return;
    }

    const csvContent = [
      DETAILED_TRADE_CSV_HEADERS.join(','),
      ...allTrades.map(trade => {
        const entryTime = new Date(trade.timestamp_entry);
        const exitTime = new Date(trade.timestamp_exit);
        const duration = exitTime.getTime() - entryTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        const durationStr = durationMinutes > 0 ? `${durationMinutes}m` : '<1m';

        return [
          trade.id,
          entryTime.toLocaleDateString(),
          entryTime.toLocaleTimeString(),
          trade.symbol,
          trade.strategy,
          trade.source_engine,
          trade.direction?.toUpperCase() || 'N/A',
          trade.entry_price.toFixed(6),
          trade.exit_price?.toFixed(6) || '0',
          trade.size.toFixed(8),
          (trade.investment_amount ?? trade.entry_price * trade.size).toFixed(2),
          `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(6)}`,
          `${trade.gross_pnl >= 0 ? '+' : ''}${trade.gross_pnl.toFixed(6)}`,
          `${trade.pnl_percentage >= 0 ? '+' : ''}${trade.pnl_percentage.toFixed(2)}%`,
          trade.total_costs?.toFixed(6) || '0',
          `${(trade.entry_fees + trade.exit_fees).toFixed(6)}`,
          trade.slippage_cost?.toFixed(6) || '0',
          trade.spread_cost?.toFixed(6) || '0',
          trade.confidence?.toFixed(2) || '0',
          trade.volatility?.toFixed(2) || '0',
          durationStr
        ].join(',');
      })
    ];

    navigator.clipboard.writeText(csvContent.join('\n')).then(() => {
      toast.success(`✅ Copied ${allTrades.length} detailed trades to clipboard!`, { toastId: 'trades-copied' });
    }).catch(() => {
      toast.error('❌ Failed to copy trades', { toastId: 'trades-copy-error' });
    });
  }, [allTrades]);

  const downloadTradesCSV = useCallback(() => {
    if (allTrades.length === 0) {
      toast.error('No trades to download', { toastId: 'download-trades-empty' });
      return;
    }

    const csvContent = [
      DETAILED_TRADE_CSV_HEADERS.join(','),
      ...allTrades.map(trade => {
        const entryTime = new Date(trade.timestamp_entry);
        const exitTime = new Date(trade.timestamp_exit);
        const duration = exitTime.getTime() - entryTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        const durationStr = durationMinutes > 0 ? `${durationMinutes}m` : '<1m';

        return [
          trade.id,
          entryTime.toLocaleDateString(),
          entryTime.toLocaleTimeString(),
          trade.symbol,
          trade.strategy,
          trade.source_engine,
          trade.direction?.toUpperCase() || 'N/A',
          trade.entry_price.toFixed(6),
          trade.exit_price?.toFixed(6) || '0',
          trade.size.toFixed(8),
          (trade.investment_amount ?? trade.entry_price * trade.size).toFixed(2),
          `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(6)}`,
          `${trade.gross_pnl >= 0 ? '+' : ''}${trade.gross_pnl.toFixed(6)}`,
          `${trade.pnl_percentage >= 0 ? '+' : ''}${trade.pnl_percentage.toFixed(2)}%`,
          trade.total_costs?.toFixed(6) || '0',
          `${(trade.entry_fees + trade.exit_fees).toFixed(6)}`,
          trade.slippage_cost?.toFixed(6) || '0',
          trade.spread_cost?.toFixed(6) || '0',
          trade.confidence?.toFixed(2) || '0',
          trade.volatility?.toFixed(2) || '0',
          durationStr
        ].join(',');
      })
    ];

    const blob = new Blob([csvContent.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detailed_trades_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    toast.success(` Downloaded ${allTrades.length} detailed trades as CSV!`, { toastId: 'trades-downloaded' });
  }, [allTrades]);

  const realEquityData = useMemo(() => {
    if (allTrades.length === 0) return [];

    const sortedTrades = [...allTrades].sort((a, b) =>
      new Date(a.timestamp_entry).getTime() - new Date(b.timestamp_entry).getTime()
    );

    const equityPoints: EquityPoint[] = [];
    let runningCapital = 100;
    let lastDate = '';

    if (sortedTrades.length > 0) {
      const firstTradeDate = new Date(sortedTrades[0].timestamp_entry);
      firstTradeDate.setHours(0, 0, 0, 0);
      equityPoints.push({
        timestamp: firstTradeDate.toISOString(),
        capital: 100,
      });
    }

    sortedTrades.forEach(trade => {
      runningCapital += trade.pnl;
      const tradeDate = new Date(trade.timestamp_exit || trade.timestamp_entry);
      const dateStr = tradeDate.toDateString();

      if (dateStr !== lastDate) {
        equityPoints.push({
          timestamp: trade.timestamp_exit || trade.timestamp_entry,
          capital: Math.round(runningCapital * 100) / 100,
        });
        lastDate = dateStr;
      } else if (equityPoints.length > 0) {
        equityPoints[equityPoints.length - 1] = {
          timestamp: trade.timestamp_exit || trade.timestamp_entry,
          capital: Math.round(runningCapital * 100) / 100,
        };
      }
    });

    return equityPoints;
  }, [allTrades]);

  const handleDeleteAllTrades = useCallback(async () => {
    if (allTrades.length === 0 || isDeletingTrades) return;

    const confirmed = window.confirm('⚠️ This will permanently delete all trades, metrics, equity history and alerts. Continue?');
    if (!confirmed) return;

    try {
      setIsDeletingTrades(true);
      const response = await fetch('http://127.0.0.1:5000/trades', {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      toast.success('✅ Trades cleared successfully', { toastId: 'trades-cleared' });
      await fetchAllData();
    } catch (error) {
      console.error('Error deleting trades:', error);
      toast.error('❌ Failed to delete trades');
    } finally {
      setIsDeletingTrades(false);
    }
  }, [allTrades.length, isDeletingTrades, fetchAllData]);

  const totalPnL = useMemo(
    () => allTrades.reduce((sum, trade) => sum + trade.pnl, 0),
    [allTrades]
  );

  const maxGain = useMemo(
    () => allTrades.length > 0 ? Math.max(...allTrades.map(t => t.pnl)) : 0,
    [allTrades]
  );

  const maxLoss = useMemo(
    () => allTrades.length > 0 ? Math.min(...allTrades.map(t => t.pnl)) : 0,
    [allTrades]
  );

  const getAlertStyle = (type: string) => {
    switch (type) {
      // Alertas de Portfolio (existentes)
      case 'HIGH_RISK_LOSS':
        return { color: 'text-red-400', bg: 'bg-red-900/20', border: 'border-red-500', icon: '🔴' };
      case 'SIGNIFICANT_PROFIT':
        return { color: 'text-green-400', bg: 'bg-green-900/20', border: 'border-green-500', icon: '🟢' };
      case 'CRITICAL_DRAWDOWN':
        return { color: 'text-orange-400', bg: 'bg-orange-900/20', border: 'border-orange-500', icon: '🟠' };
      case 'LOW_WIN_RATE':
        return { color: 'text-yellow-400', bg: 'bg-yellow-900/20', border: 'border-yellow-500', icon: '🟡' };
      case 'EXTREME_VOLATILITY':
        return { color: 'text-purple-400', bg: 'bg-purple-900/20', border: 'border-purple-500', icon: '🟣' };
      case 'LOSS_WARNING':
        return { color: 'text-red-300', bg: 'bg-red-900/10', border: 'border-red-400', icon: '⚠️' };
      case 'PROFIT_ALERT':
        return { color: 'text-green-300', bg: 'bg-green-900/10', border: 'border-green-400', icon: '✅' };
      case 'VOLATILITY_ALERT':
        return { color: 'text-blue-400', bg: 'bg-blue-900/20', border: 'border-blue-500', icon: '📊' };
      case 'DRAWDOWN_ALERT':
        return { color: 'text-orange-300', bg: 'bg-orange-900/10', border: 'border-orange-400', icon: '📉' };
      
      // Alertas de Mercado (nuevas)
      case 'STRONG_BUY_SIGNAL':
        return { color: 'text-emerald-400', bg: 'bg-emerald-900/20', border: 'border-emerald-500', icon: '🟢' };
      case 'BUY_DIP':
        return { color: 'text-green-300', bg: 'bg-green-900/15', border: 'border-green-400', icon: '💚' };
      case 'SUPPORT_BOUNCE':
        return { color: 'text-blue-400', bg: 'bg-blue-900/15', border: 'border-blue-400', icon: '🔵' };
      case 'STRONG_SELL_SIGNAL':
        return { color: 'text-red-400', bg: 'bg-red-900/20', border: 'border-red-500', icon: '🔴' };
      case 'SELL_TOP':
        return { color: 'text-red-300', bg: 'bg-red-900/15', border: 'border-red-400', icon: '❌' };
      case 'RESISTANCE_REJECTION':
        return { color: 'text-orange-400', bg: 'bg-orange-900/15', border: 'border-orange-400', icon: '🟠' };
      case 'BREAKOUT_ALERT':
        return { color: 'text-yellow-300', bg: 'bg-yellow-900/15', border: 'border-yellow-400', icon: '🟡' };
      case 'VOLUME_SPIKE':
        return { color: 'text-purple-400', bg: 'bg-purple-900/15', border: 'border-purple-400', icon: '🟣' };
      case 'TREND_REVERSAL':
        return { color: 'text-cyan-400', bg: 'bg-cyan-900/15', border: 'border-cyan-400', icon: '⚪' };
      case 'CONSOLIDATION_BREAK':
        return { color: 'text-amber-400', bg: 'bg-amber-900/15', border: 'border-amber-400', icon: '🔶' };
      
      default:
        return { color: 'text-gray-400', bg: 'bg-gray-900/20', border: 'border-gray-500', icon: 'ℹ️' };
    }
  };

          return (
    <div className="min-h-screen bg-black text-white">
      {/* Sticky Top Bar */}
      <div className="sticky top-0 z-50 bg-black/90 backdrop-blur-md border-b border-gray-800 p-4">
        {/* First Row - Status */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <div className={`flex items-center gap-2 ${
              wsStatus === 'connected' ? 'text-green-400' : 
              wsStatus === 'error' ? 'text-red-400' : 'text-gray-500'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                wsStatus === 'connected' ? 'bg-green-400' : 
                wsStatus === 'error' ? 'bg-red-400' : 'text-gray-500'
              }`}></div>
              WebSocket: {wsStatus}
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-400">
            {/* Engine Status */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                Object.values(engines).filter(e => e.status === 'running').length > 0 
                  ? 'bg-emerald-400' 
                  : 'bg-gray-500'
              }`}></div>
              <span className="text-gray-300">
                Engines: {Object.values(engines).filter(e => e.status === 'running').length}/{Object.keys(engines).length}
              </span>
            </div>
            {/* Backend Link */}
            <a
              href="http://127.0.0.1:5000"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 border border-blue-500/40 rounded-lg text-blue-300 hover:bg-blue-500/30 transition-colors text-xs font-mono"
            >
              <ExternalLink className="w-3 h-3" />
              Backend
            </a>
          </div>
        </div>
        
        {/* Second Row - Running Engines */}
        {Object.values(engines).filter(e => e.status === 'running').length > 0 && (
          <div className="flex flex-wrap items-start gap-2">
            <span className="text-emerald-400 shrink-0 mt-1 text-sm">Running:</span>
            <div className="flex flex-wrap gap-1">
              {Object.entries(engines)
                .filter(([, e]) => e.status === 'running')
                .map(([id]) => (
                  <span key={id} className="px-2 py-1 bg-emerald-500/20 border border-emerald-500/40 rounded text-xs text-emerald-300 font-mono">
                    {id}
                  </span>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="p-4">

      {/* Alerts Panel */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm mb-8">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2 text-cyan-400">
            <Bell className="w-5 h-5" />
            Recent Alerts
          </h2>
          <div className="text-sm text-gray-400">
            Total: {alerts.length} alerts
          </div>
        </div>

        {alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Bell className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <div className="text-sm">No alerts yet</div>
            <div className="text-xs mt-2">Alerts will appear here when trades are executed</div>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {alerts.map(alert => {
                const alertTime = new Date(alert.timestamp);
                const timeAgo = getTimeAgo(alertTime);
                const alertStyle = getAlertStyle(alert.type);

                return (
                  <div
                    key={alert.id}
                    className={`flex items-center justify-between p-4 ${alertStyle.bg} ${alertStyle.border} border rounded-lg hover:opacity-80 transition-all`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">{alertStyle.icon}</div>
                      <div>
                        <div className={`font-bold ${alertStyle.color} font-mono`}>
                          {alert.type.replace('_', ' ')}
                        </div>
                        <div className="text-sm text-gray-300 mt-1">
                          {alert.message}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {alertTime.toLocaleDateString()} at {alertTime.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">{timeAgo}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Engine Control Panel */}
      <EngineControlPanel
        className="mb-8"
        onGenerateBinanceTrade={handleGenerateBinanceTrade}
        onClearTrades={handleDeleteAllTrades}
        onResetStatus={handleClearAllStatus}
        onGenerateIntelligentTrade={handleGenerateIntelligentTrade}
        selectedIntelligentStrategies={selectedIntelligentStrategies}
        setSelectedIntelligentStrategies={setSelectedIntelligentStrategies}
        tradingModes={tradingModes}
        binanceModeStatus={binanceModeStatus}
        selectedModes={selectedModes}
        onBinanceModeControl={handleBinanceModeControl}
      />

      {/* TradingView Widget */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-cyan-400">
          <TrendingUp className="w-5 h-5" />
          Market Overview
        </h2>
        <div className="h-[600px]">
          <TradingViewWidget />
        </div>
      </div>

      {/* Metrics Panel */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">TOTAL P&L</span>
            {totalPnL >= 0 ? <TrendingUp className="w-5 h-5 text-green-400" /> : <TrendingDown className="w-5 h-5 text-red-400" />}
          </div>
          <div className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'} font-mono`}>
            ${totalPnL.toFixed(2)}
          </div>
        </div>
        
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">WIN RATE</span>
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-400 font-mono">
            {metrics ? `${(metrics.win_rate * 100).toFixed(1)}%` : 'N/A'}
          </div>
        </div>
        
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">SHARPE RATIO</span>
            <DollarSign className="w-5 h-5 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-purple-400 font-mono">
            {metrics ? metrics.sharpe.toFixed(2) : 'N/A'}
          </div>
        </div>
        
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">MAX DRAWDOWN</span>
            <AlertTriangle className="w-5 h-5 text-orange-400" />
          </div>
          <div className="text-2xl font-bold text-orange-400 font-mono">
            {metrics ? `${metrics.max_drawdown.toFixed(2)}%` : 'N/A'}
          </div>
        </div>

        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">MAX GAINED</span>
            <ArrowUp className="w-5 h-5 text-green-400" />
          </div>
          <div className={`text-2xl font-bold ${maxGain > 0 ? 'text-green-400' : 'text-gray-400'} font-mono`}>
            {maxGain > 0 ? `+$${maxGain.toFixed(2)}` : '$0.00'}
          </div>
        </div>

        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 font-mono text-sm">MAX LOST</span>
            <ArrowDown className="w-5 h-5 text-red-400" />
          </div>
          <div className={`text-2xl font-bold ${maxLoss < 0 ? 'text-red-400' : 'text-gray-400'} font-mono`}>
            {maxLoss < 0 ? `-$${Math.abs(maxLoss).toFixed(2)}` : '$0.00'}
          </div>
        </div>
      </div>

      {/* All Trades Table */}
        <TradesTable
          trades={trades}
          allTrades={allTrades}
          hasMoreTrades={hasMoreTrades}
          totalPnL={totalPnL}
          onShowMoreTrades={handleShowMoreTrades}
          onShowAllTrades={handleShowAllTrades}
          onCopyAllTrades={copyAllTrades}
          onDownloadTradesCSV={downloadTradesCSV}
          onDeleteAllTrades={handleDeleteAllTrades}
          isDeletingAllTrades={isDeletingTrades}
        />

      {/* Order Book de Nuestros Trades */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm mb-8">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2 text-cyan-400">
            <Activity className="w-5 h-5" />
            Order Book - Nuestros Trades
          </h2>
          <div className="text-sm text-gray-400">
            Últimos 20 trades
          </div>
        </div>

        {allTrades.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <div className="text-sm">No trades yet</div>
            <div className="text-xs mt-2">Los trades aparecerán aquí cuando se ejecuten</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Order Book - Compras (LONG) */}
            <div>
              <h3 className="text-sm font-semibold text-green-400 mb-3 flex items-center gap-2">
                <ArrowUp className="w-4 h-4" />
                COMPRAS (LONG) - {allTrades.filter(t => t.direction === 'long').length} trades
              </h3>
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {allTrades
                  .filter(trade => trade.direction === 'long')
                  .slice(0, 10)
                  .map((trade, index) => (
                    <div key={trade.id} className="flex justify-between items-center bg-gray-900/50 rounded px-3 py-2 text-sm">
                      <div className="flex items-center gap-3">
                        <span className="text-gray-500 font-mono text-xs">#{allTrades.length - index}</span>
                        <span className="text-green-400 font-mono">{trade.symbol}</span>
                        <span className="text-gray-400 text-xs">{trade.strategy}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="text-white font-mono">${trade.entry_price.toFixed(2)}</div>
                          <div className="text-gray-500 text-xs">${trade.size.toFixed(4)}</div>
                        </div>
                        <div className={`text-right font-mono ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          <div>{trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}</div>
                          <div className="text-xs opacity-75">{trade.pnl_percentage.toFixed(2)}%</div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            {/* Order Book - Ventas (SHORT) */}
            <div>
              <h3 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                <ArrowDown className="w-4 h-4" />
                VENTAS (SHORT) - {allTrades.filter(t => t.direction === 'short').length} trades
              </h3>
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {allTrades
                  .filter(trade => trade.direction === 'short')
                  .slice(0, 10)
                  .map((trade, index) => (
                    <div key={trade.id} className="flex justify-between items-center bg-gray-900/50 rounded px-3 py-2 text-sm">
                      <div className="flex items-center gap-3">
                        <span className="text-gray-500 font-mono text-xs">#{allTrades.length - index}</span>
                        <span className="text-red-400 font-mono">{trade.symbol}</span>
                        <span className="text-gray-400 text-xs">{trade.strategy}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="text-white font-mono">${trade.entry_price.toFixed(2)}</div>
                          <div className="text-gray-500 text-xs">${trade.size.toFixed(4)}</div>
                        </div>
                        <div className={`text-right font-mono ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          <div>{trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}</div>
                          <div className="text-xs opacity-75">{trade.pnl_percentage.toFixed(2)}%</div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* Resumen del Order Book */}
        {allTrades.length > 0 && (
          <div className="mt-6 pt-4 border-t border-gray-800">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">Total Trades</div>
                <div className="text-white font-mono font-bold">{allTrades.length}</div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">Win Rate</div>
                <div className="text-cyan-400 font-mono font-bold">
                  {allTrades.length > 0
                    ? `${((allTrades.filter(t => t.pnl > 0).length / allTrades.length) * 100).toFixed(1)}%`
                    : '0%'}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">Total P&L</div>
                <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">Best Trade</div>
                <div className="text-green-400 font-mono font-bold">
                  ${allTrades.length > 0 ? Math.max(...allTrades.map(t => t.pnl)).toFixed(2) : '0.00'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Equity Curve */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm lg:col-span-2">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-cyan-400">Equity Curve - Complete History</h2>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-400 rounded-full"></div>
                <span className="text-gray-400">Capital Inicial ($100)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-cyan-400 rounded-full"></div>
                <span className="text-gray-400">Capital Actual</span>
              </div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={realEquityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
              <XAxis 
                dataKey="timestamp" 
                stroke="#4B5563"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => new Date(value).toLocaleDateString()}
              />
              <YAxis 
                stroke="#4B5563"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => `$${value}`}
                domain={['dataMin - 5', 'dataMax + 5']} // Ajuste automático con margen
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#111827', 
                  border: '1px solid #374151',
                  borderRadius: '8px'
                }}
                labelStyle={{ color: '#F3F4F6' }}
                formatter={(value: number) => [`$${value}`, 'Capital']}
                labelFormatter={(label) => `Fecha: ${new Date(label).toLocaleString()}`}
              />
              <defs>
                <linearGradient id="capitalGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <Area 
                type="monotone" 
                dataKey="capital" 
                stroke="#06B6D4" 
                strokeWidth={2}
                fill="url(#capitalGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
          
          {/* Estadísticas adicionales debajo del gráfico */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6 pt-6 border-t border-gray-800">
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-1">Capital Inicial</div>
              <div className="text-white font-mono font-bold">$100.00</div>
            </div>
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-1">Capital Actual</div>
              <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${(100 + totalPnL).toFixed(2)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-1">Total P&L</div>
              <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-1">Retorno %</div>
              <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(1)}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-400 text-sm mb-1">Progreso Mensual</div>
              <div className={`font-mono font-bold ${totalPnL >= 20 ? 'text-green-400' : totalPnL >= 0 ? 'text-cyan-400' : 'text-red-400'}`}>
                {Math.min(100, Math.max(0, (totalPnL / 20) * 100)).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Analysis Section */}
      <Analisis trades={allTrades} engines={engines} className="mb-8" />

      
      </div>
    </div>
  );
}
