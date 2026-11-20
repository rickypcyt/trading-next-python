import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-toastify';
import { apiFetch, describeFetchError } from '@/lib/api';
import type {
  Alert,
  Engine,
  Metric,
  Trade,
  TradeEventPayload,
  TradingMode,
} from '../types';

const INITIAL_DISPLAY_LIMIT = 50;

function formatDurationFromMs(durationMs: number): string {
  if (!durationMs || durationMs <= 0) return '0s';
  const totalSeconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function normalizeTradeFromEvent(payload: TradeEventPayload): Trade {
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

  const notional = investment || entryPrice * size;
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
    duration_ms: durationMs,
    duration_formatted: payload.duration_formatted ?? formatDurationFromMs(durationMs),
    confidence,
    volatility,
  } as Trade;
}

export function useDashboardData() {
  const [allTrades, setAllTrades] = useState<Trade[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [engines, setEngines] = useState<Record<string, Engine>>({});
  const [metrics, setMetrics] = useState<Metric | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [tradingModes, setTradingModes] = useState<Record<string, TradingMode>>({});
  const [hasMoreTrades, setHasMoreTrades] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDeletingTrades, setIsDeletingTrades] = useState(false);
  const [displayLimit, setDisplayLimit] = useState(INITIAL_DISPLAY_LIMIT);
  const [backendStatus, setBackendStatus] = useState<'loading' | 'online' | 'offline'>('loading');
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const backendStatusRef = useRef(backendStatus);
  useEffect(() => { backendStatusRef.current = backendStatus; }, [backendStatus]);

  const isRefreshingRef = useRef(isRefreshing);
  isRefreshingRef.current = isRefreshing;
  const displayLimitRef = useRef(displayLimit);
  displayLimitRef.current = displayLimit;
  const fetchAllDataRef = useRef<() => Promise<void>>(async () => {});

  // Polling: cada 15s como fallback del WebSocket, y cada 5s mientras el backend esté caído
  // para recuperarse solo en cuanto vuelva.
  useEffect(() => {
    let tick = 0;
    const interval = setInterval(() => {
      tick += 1;
      if (backendStatusRef.current !== 'online' || tick % 3 === 0) {
        fetchAllDataRef.current();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-refresh al volver a la pestaña (visibilitychange)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchAllDataRef.current();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  const updateDisplayedTrades = useCallback((updatedAll: Trade[], limit: number) => {
    setTrades(updatedAll.slice(0, limit));
    setHasMoreTrades(updatedAll.length > limit);
  }, []);

  const fetchAllData = useCallback(async () => {
    if (isRefreshingRef.current) return;
    setIsRefreshing(true);
    try {
      const [tradesRes, metricsRes, alertsRes, modesRes, enginesRes] = await Promise.all([
        apiFetch('/trades'),
        apiFetch('/metrics'),
        apiFetch('/alerts'),
        apiFetch('/binance/modes').catch(() => null),
        apiFetch('/engines')
      ]);
      if (!tradesRes.ok || !metricsRes.ok || !alertsRes.ok || !enginesRes.ok) {
        throw new Error(`El backend respondió con error (HTTP ${[tradesRes, metricsRes, alertsRes, enginesRes].find(r => !r.ok)?.status}).`);
      }

      const [tradesData, metricsData, alertsData, modesData, enginesData] = await Promise.all([
        tradesRes.json(),
        metricsRes.json(),
        alertsRes.json(),
        modesRes?.json().catch(() => ({ modes: {} })),
        enginesRes.json()
      ]);

      const processedTrades = (tradesData as Trade[]).map((trade: Trade) => ({
        ...trade,
        investment_amount: trade.investment_amount || trade.size * trade.entry_price
      }));

      const limit = displayLimitRef.current;
      setAllTrades(processedTrades);
      updateDisplayedTrades(processedTrades, limit);
      setEngines(enginesData.engines ?? {});
      setMetrics(metricsData[0] || null);
      setAlerts(alertsData);
      setTradingModes(modesData.modes || {});
      setBackendStatus('online');
      setLastError(null);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error fetching data:', error);
      setBackendStatus('offline');
      setLastError(describeFetchError(error));
    } finally {
      setIsRefreshing(false);
    }
  }, [updateDisplayedTrades]);

  // Keep ref in sync so polling/visibility can call latest version
  useEffect(() => {
    fetchAllDataRef.current = fetchAllData;
  }, [fetchAllData]);

  const addTradeFromEvent = useCallback((payload: TradeEventPayload) => {
    const trade = normalizeTradeFromEvent(payload);
    setAllTrades(prevAll => {
      const deduped = prevAll.filter(existing => existing.id !== trade.id);
      const updatedAll = [trade, ...deduped].sort(
        (a, b) => new Date(b.timestamp_entry).getTime() - new Date(a.timestamp_entry).getTime()
      );
      updateDisplayedTrades(updatedAll, displayLimitRef.current);
      return updatedAll;
    });
  }, [updateDisplayedTrades]);

  const removeTradeById = useCallback((tradeId: number) => {
    setAllTrades(prev => {
      const updated = prev.filter(trade => trade.id !== tradeId);
      updateDisplayedTrades(updated, displayLimitRef.current);
      return updated;
    });
  }, [updateDisplayedTrades]);

  const clearTradesState = useCallback(() => {
    setAllTrades([]);
    setTrades([]);
    setHasMoreTrades(false);
  }, []);

  const showMoreTrades = useCallback(() => {
    const newLimit = displayLimit + 50;
    setDisplayLimit(newLimit);
    updateDisplayedTrades(allTrades, newLimit);
    toast.info(`Showing ${newLimit} trades`, { toastId: 'show-more-trades' });
  }, [allTrades, displayLimit, updateDisplayedTrades]);

  const showAllTrades = useCallback(() => {
    setDisplayLimit(allTrades.length);
    updateDisplayedTrades(allTrades, allTrades.length);
    setHasMoreTrades(false);
    toast.info(`Showing all ${allTrades.length} trades`, { toastId: 'show-all-trades' });
  }, [allTrades, updateDisplayedTrades]);

  const deleteAllTrades = useCallback(async () => {
    if (allTrades.length === 0 || isDeletingTrades) return false;

    const confirmed = window.confirm(
      'This will permanently delete all trades, metrics, equity history and alerts. Continue?'
    );
    if (!confirmed) return false;

    setIsDeletingTrades(true);
    try {
      const response = await apiFetch('/trades', { method: 'DELETE' });
      if (!response.ok) throw new Error(await response.text());
      toast.success('Trades cleared successfully', { toastId: 'trades-cleared' });
      await fetchAllData();
      return true;
    } catch (error) {
      console.error('Error deleting trades:', error);
      toast.error('Failed to delete trades');
      return false;
    } finally {
      setIsDeletingTrades(false);
    }
  }, [allTrades.length, isDeletingTrades, fetchAllData]);

  return {
    allTrades,
    trades,
    engines,
    metrics,
    alerts,
    tradingModes,
    hasMoreTrades,
    isRefreshing,
    isDeletingTrades,
    backendStatus,
    lastError,
    lastUpdated,
    fetchAllData,
    addTradeFromEvent,
    removeTradeById,
    clearTradesState,
    showMoreTrades,
    showAllTrades,
    deleteAllTrades,
    setEngines,
  };
}
