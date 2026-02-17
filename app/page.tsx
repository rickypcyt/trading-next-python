'use client';

import { Activity, AlertTriangle, ArrowDown, ArrowUp, Bell, Copy, DollarSign, Download, Pause, Play, Settings, TrendingDown, TrendingUp } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useCallback, useEffect, useMemo, useState } from 'react';

import TradingViewWidget from './components/TradingViewWidget';
import { toast } from 'react-toastify';

interface Trade {
  id: number;
  timestamp_entry: string;
  timestamp_exit: string;
  symbol: string;
  strategy: string;
  entry_price: number;
  exit_price: number;
  requested_entry_price: number;
  requested_exit_price: number;
  size: number;
  pnl: number;
  gross_pnl: number;
  pnl_percentage: number;
  entry_fees: number;
  exit_fees: number;
  slippage_cost: number;
  spread_cost: number;
  total_costs: number;
  cost_impact_pct: number;
  stop_loss: number | null;
  take_profit: number | null;
  confidence: number;
  volatility: number | null;
  source_engine: string;
  source_mode: string;
  direction: string;
  duration_ms: number;
  duration_formatted: string;
  entry_reason: string;
  exit_reason: string;
  status: string;
  investment_amount: number;  // Nuevo campo: dinero invertido
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

interface SimulationStatus {
  binance: 'running' | 'stopped';
  intelligent: 'running' | 'stopped';
  monthly_target: 'running' | 'stopped';
}

interface TradingMode {
  name: string;
  risk_percentage: number;
  win_rate: number;
  reward_risk_ratio: number;
  max_consecutive_losses: number;
  trades_per_hour: number;
}

interface BinanceModeStatus {
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
  const [trades, setTrades] = useState<Trade[]>([]);
  const [allTrades, setAllTrades] = useState<Trade[]>([]);
  const [displayLimit, setDisplayLimit] = useState(50);
  const [hasMoreTrades, setHasMoreTrades] = useState(false);
  const [metrics, setMetrics] = useState<Metric | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [equityData, setEquityData] = useState<EquityPoint[]>([]);
  const [wsStatus, setWsStatus] = useState<string>('disconnected');
  const [binanceStatus, setBinanceStatus] = useState<string>('stopped'); // Always start with 'stopped' to avoid hydration mismatch
  const [intelligentStatus, setIntelligentStatus] = useState<string>('stopped'); // Always start with 'stopped' to avoid hydration mismatch
  const [selectedIntelligentStrategies, setSelectedIntelligentStrategies] = useState<string[]>([
    'MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance'
  ]); // All strategies selected by default
  const [microProfitStats, setMicroProfitStats] = useState<{
  total_micro_trades: number;
  successful_trades: number;
  win_rate: number;
  total_profit: number;
  avg_profit_per_trade: number;
  current_capital: number;
  target_profit_per_trade: number;
  success_rate_vs_target: number;
} | null>(null); // Micro profit statistics
  const [tradingModes, setTradingModes] = useState<Record<string, TradingMode>>({});
  const [binanceModeStatus, setBinanceModeStatus] = useState<BinanceModeStatus>(() => {
    // Always start with consistent initial state to avoid hydration mismatch
    const stored: BinanceModeStatus = {};
    const modes = ['conservative', 'hybrid', 'aggressive'];
    modes.forEach(mode => {
      stored[mode] = 'stopped';
    });
    return stored;
  });
  const [selectedModes, setSelectedModes] = useState<string[]>([]);

  // Restore stored values after mount to avoid hydration mismatch
  useEffect(() => {
    // Only run on client side and only once on mount
    if (typeof window !== 'undefined') {
      setBinanceStatus(getStoredStatus('binance', 'stopped'));
      
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
      const newStatus: BinanceModeStatus = {};
      const modes = ['conservative', 'hybrid', 'aggressive'];
      modes.forEach(mode => {
        newStatus[mode] = modesArray.includes(mode) ? 'running' : 'stopped';
      });
      setBinanceModeStatus(newStatus);
    }
  }, []);

  const fetchAllData = useCallback(async () => {
    try {
      const [tradesRes, metricsRes, alertsRes, equityRes, statusRes, modesRes] = await Promise.all([
        fetch('http://127.0.0.1:5000/trades'),
        fetch('http://127.0.0.1:5000/metrics'),
        fetch('http://127.0.0.1:5000/alerts'),
        fetch('http://127.0.0.1:5000/equity'),
        fetch('http://127.0.0.1:5000/status'),
        fetch('http://127.0.0.1:5000/binance/modes').catch(() => null) // Puede no existir aún
      ]);

      const [tradesData, metricsData, alertsData, equityDataResponse, statusData, modesData] = await Promise.all([
        tradesRes.json(),
        metricsRes.json(),
        alertsRes.json(),
        equityRes.json(),
        statusRes.json(),
        modesRes?.json().catch(() => ({ modes: {} })) // Default si no existe
      ]);

      // Guardar todos los trades y mostrar solo los primeros 50
      const processedTrades = tradesData.map((trade: Trade) => ({
        ...trade,
        investment_amount: trade.investment_amount || (trade.size * trade.entry_price)
      }));
      setAllTrades(processedTrades);
      setTrades(processedTrades.slice(0, displayLimit));
      setHasMoreTrades(processedTrades.length > displayLimit);
      
      setMetrics(metricsData[0] || null);
      setAlerts(alertsData);
      setEquityData(equityDataResponse.reverse());
      setTradingModes(modesData.modes || {});
      
      if (statusData) {
        setBinanceStatus((statusData as SimulationStatus).binance);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error loading dashboard data', { toastId: 'fetch-error' });
    }
  }, [displayLimit]);

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

  useEffect(() => {
    fetchAllData();

    // WebSocket connection with auto-reconnect
    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let reconnectTimeout: NodeJS.Timeout;

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
              setBinanceStatus('running');
              setStoredStatus('binance', 'running');
              toast.success('💎 Binance real-time simulation started', { toastId: 'binance-started' });
              break;
              
            case 'binance_simulation_stopped':
              setBinanceStatus('stopped');
              setStoredStatus('binance', 'stopped');
              toast.error('⏹️ Binance simulation stopped', { toastId: 'binance-stopped' });
              break;
              
            case 'intelligent_simulation_started':
              setIntelligentStatus('running');
              setStoredStatus('intelligent', 'running');
              toast.success('🧠 Intelligent simulation with technical analysis started', { toastId: 'intelligent-started' });
              break;
              
            case 'intelligent_simulation_stopped':
              setIntelligentStatus('stopped');
              setStoredStatus('intelligent', 'stopped');
              toast.error('⏹️ Intelligent simulation stopped', { toastId: 'intelligent-stopped' });
              break;
              
            case 'intelligent_trade_generated':
              toast.success(`🧠 Intelligent trade: ${data.data.symbol} ${data.data.strategy} ${data.data.pnl > 0 ? '+' : ''}$${data.data.pnl.toFixed(2)}`, {
                toastId: `intelligent-trade-${data.data.trade_id}`,
              });
              fetchAllData();
              break;
              
            case 'micro_profit_generated':
              const stats = data.data.stats;
              toast.success(`💰 Micro Profit: ${data.data.trades_generated} trades, $${stats.total_profit.toFixed(4)} total profit`, {
                toastId: `micro-profit-${data.data.timestamp}`,
              });
              setMicroProfitStats(stats);
              fetchAllData();
              break;
              
            case 'binance_mode_started':
              // Add mode to selected modes
              setSelectedModes(prev => [...prev.filter(m => m !== data.data.mode), data.data.mode]);
              setStoredStatus('selected_binance_modes', [...selectedModes.filter(m => m !== data.data.mode), data.data.mode].join(','));
              
              // Actualizar estado: solo poner el modo iniciado en running, mantener los demás
              setBinanceModeStatus(prev => ({ ...prev, [data.data.mode]: 'running' }));
              
              toast.success(`🎯 Binance ${data.data.mode_name} mode activated`, { toastId: `binance-${data.data.mode}-activated` });
              break;
              
            case 'binance_mode_stopped':
              // Remove mode from selected modes
              setSelectedModes(prev => prev.filter(m => m !== data.data.mode));
              setStoredStatus('selected_binance_modes', selectedModes.filter(m => m !== data.data.mode).join(','));
              
              setBinanceModeStatus(prev => ({ ...prev, [data.data.mode]: 'stopped' }));
              toast.info(`📴 Binance ${data.data.mode} deactivated`, { toastId: `binance-${data.data.mode}-deactivated` });
              break;
              
            case 'binance_mode_trade_generated':
              toast.info(`📊 Binance ${data.data.mode} trade: ${data.data.pnl > 0 ? '+' : ''}$${data.data.pnl.toFixed(2)}`, {
                toastId: `binance-${data.data.mode}-trade-${data.data.trade_id}`,
              });
              fetchAllData();
              break;
              
            case 'trade_added':
            case 'real_trade_generated':
            case 'monthly_target_trade_generated':
              fetchAllData(); // Refresh data
              break;
              
            case 'equity_updated':
              toast.info(`💰 Equity updated: $${data.data.capital}`, {
                toastId: data.data?.timestamp ? `equity-${data.data.timestamp}` : 'equity-update',
              });
              fetchAllData();
              break;
              
            case 'metrics_updated':
              toast.info('📊 Metrics updated', {
                toastId: data.data?.id ? `metrics-${data.data.id}` : 'metrics-update',
              });
              fetchAllData();
              break;
              
            case 'alert_added':
              toast.warning(`🚨 Alert: ${data.data.type}`, {
                toastId: data.data?.id ? `alert-${data.data.id}` : `alert-${data.data?.type ?? 'new'}`,
              });
              fetchAllData();
              break;
          }
        };
        
        ws.onclose = () => {
          setWsStatus('disconnected');
          toast.error('WebSocket disconnected', { toastId: 'ws-disconnected' });
          
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 5000);
            reconnectTimeout = setTimeout(() => connectWebSocket(), delay);
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
  }, [fetchAllData, selectedModes]);

  const handleSimulationControl = async (action: 'start' | 'stop', type: 'simulation' | 'binance' | 'intelligent') => {
    try {
      let endpoint;
      if (type === 'simulation') {
        endpoint = '/simulation';
      } else if (type === 'binance') {
        endpoint = '/binance';
      } else if (type === 'intelligent') {
        endpoint = '/intelligent';
      }
      
      const response = await fetch(`http://127.0.0.1:5000${endpoint}/${action}`, { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'already_running') {
        toast.info(`${type} is already running`, { toastId: `${type}-already-running` });
        if (type === 'binance') setBinanceStatus('running');
        return;
      }

      if (['started', 'stopped'].includes(result.status)) {
        const newStatus = result.status === 'started' ? 'running' : 'stopped';
        setBinanceStatus(newStatus);
        setStoredStatus('binance', newStatus);
      }
    } catch {
      toast.error(`Error controlling ${type}`, { toastId: `${type}-control-error` });
    }
  };

  const handleBinanceModeControl = async (action: 'select' | 'generate', mode: string) => {
    try {
      if (action === 'select') {
        // Toggle mode selection
        const isSelected = selectedModes.includes(mode);
        
        if (isSelected) {
          // Detener el modo
          const response = await fetch(`http://127.0.0.1:5000/binance/mode/${mode}/stop`, { method: 'POST' });
          const result = await response.json();
          
          if (result.status === 'stopped' || result.status === 'not_running') {
            setSelectedModes(prev => prev.filter(m => m !== mode));
            setStoredStatus('selected_binance_modes', selectedModes.filter(m => m !== mode).join(','));
            
            setBinanceModeStatus(prev => ({ ...prev, [mode]: 'stopped' }));
            
            toast.info(`📴 Binance ${tradingModes[mode]?.name || mode} deactivated`, { toastId: `binance-${mode}-deactivated` });
          }
        } else {
          // Iniciar el modo
          const response = await fetch(`http://127.0.0.1:5000/binance/mode/${mode}/start`, { method: 'POST' });
          const result = await response.json();
          
          if (result.status === 'started') {
            setSelectedModes(prev => [...prev.filter(m => m !== mode), mode]);
            setStoredStatus('selected_binance_modes', [...selectedModes.filter(m => m !== mode), mode].join(','));
            
            setBinanceModeStatus(prev => ({ ...prev, [mode]: 'running' }));
            
            toast.success(`🎯 Binance ${tradingModes[mode]?.name || mode} activated`, { toastId: `binance-${mode}-activated` });
          } else if (result.status === 'error') {
            // Handle dependency error
            toast.error(`⚠️ ${result.message}`, { toastId: `binance-${mode}-error` });
          }
        }
      } else if (action === 'generate') {
        // Generar trade del modo seleccionado
        if (selectedModes.length === 0) {
          toast.warning('⚠️ Select at least one trading mode first', { toastId: 'no-mode-selected' });
          return;
        }
        
        // Generate trades for all selected modes
        for (const selectedMode of selectedModes) {
          try {
            const response = await fetch(`http://127.0.0.1:5000/binance/mode/${selectedMode}/generate`, { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'success') {
              toast.success(`📊 Binance ${tradingModes[selectedMode]?.name || selectedMode} trade generated`, { toastId: `binance-${selectedMode}-trade` });
            } else if (result.status === 'no_trade') {
              toast.warning(`⚠️ ${result.message}`, { toastId: `binance-${selectedMode}-no-trade` });
            }
          } catch (error) {
            console.error(`Error generating trade for ${selectedMode}:`, error);
          }
        }
        
        fetchAllData(); // Refresh data
      }
    } catch (error) {
      console.error(`Error controlling Binance ${mode}:`, error);
      toast.error(`Error controlling Binance ${mode}`, { toastId: `binance-${mode}-error` });
    }
  };

  const toggleSimulation = (type: 'simulation' | 'binance' | 'intelligent') => {
    if (type === 'intelligent') {
      // Intelligent simulation control - check current status
      const action: 'start' | 'stop' = intelligentStatus === 'running' ? 'stop' : 'start';
      handleSimulationControl(action, 'intelligent');
    } else {
      // Original simulation control
      const isRunning = binanceStatus === 'running';
      const action: 'start' | 'stop' = isRunning ? 'stop' : 'start';
      handleSimulationControl(action, type);
    }
  };

  const clearAllStoredStatus = () => {
  if (typeof window !== 'undefined') {
    const keys = ['binance', 'selected_binance_mode'];
    keys.forEach(key => localStorage.removeItem(`trading_${key}`));
  }
};

const handleDeleteAllTrades = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/trades', { method: 'DELETE' });
      const result = await response.json();

      if (result.status === 'success') {
        toast.success('🧹 All trades cleared', { toastId: 'trades-cleared' });
        fetchAllData();
      } else {
        toast.error(result.message || 'Failed to clear trades', { toastId: 'clear-trades-error' });
      }
    } catch (error) {
      console.error('Delete trades error:', error);
      toast.error('Error clearing trades', { toastId: 'clear-trades-exception' });
    }
  };

  const handleClearAllStatus = () => {
    clearAllStoredStatus();
    setBinanceStatus('stopped');
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
      default:
        return { color: 'text-gray-400', bg: 'bg-gray-900/20', border: 'border-gray-500', icon: 'ℹ️' };
    }
  };

  const alertCounts = useMemo(() => {
    return alerts.reduce<Record<string, number>>((acc, alert) => {
      acc[alert.type] = (acc[alert.type] || 0) + 1;
      return acc;
    }, {});
  }, [alerts]);

  const formatDuration = (minutes: number) => {
    if (minutes < 0) return '0m';
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours}h ${mins}m`;
    }
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    return `${days}d ${hours}h`;
  };

  const copyAllTrades = () => {
    if (allTrades.length === 0) {
      toast.error('No trades to copy', { toastId: 'copy-trades-empty' });
      return;
    }

    // Crear texto CSV con todos los trades detallados
    const headers = ['ID', 'Date', 'Time', 'Symbol', 'Strategy', 'Engine', 'Direction', 'Entry', 'Exit', 'Size', 'Investment', 'P&L', 'Gross P&L', '%', 'Costs', 'Fees', 'Slippage', 'Spread', 'Confidence', 'Volatility', 'Duration'];
    const csvContent = [
      headers.join(','),
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
          trade.investment_amount?.toFixed(2) || '0',
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

    // Copiar al portapapeles
    navigator.clipboard.writeText(csvContent.join('\n')).then(() => {
      toast.success(`✅ Copied ${allTrades.length} detailed trades to clipboard!`, { toastId: 'trades-copied' });
    }).catch(() => {
      toast.error('❌ Failed to copy trades', { toastId: 'trades-copy-error' });
    });
  };

  const downloadTradesCSV = () => {
    if (allTrades.length === 0) {
      toast.error('No trades to download', { toastId: 'download-trades-empty' });
      return;
    }

    // Crear CSV detallado
    const headers = ['ID', 'Date', 'Time', 'Symbol', 'Strategy', 'Engine', 'Direction', 'Entry', 'Exit', 'Size', 'P&L', 'Gross P&L', '%', 'Costs', 'Fees', 'Slippage', 'Spread', 'Confidence', 'Volatility', 'Duration'];
    const csvContent = [
      headers.join(','),
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

    // Crear blob y descargar
    const blob = new Blob([csvContent.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detailed_trades_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    toast.success(`📥 Downloaded ${allTrades.length} detailed trades as CSV!`, { toastId: 'trades-downloaded' });
  };
          return (
    <div className="min-h-screen bg-black text-white p-4">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 text-cyan-400">Trading Dashboard</h1>
        <div className="flex items-center gap-4 text-sm text-gray-400">
          <div className={`flex items-center gap-2 ${
            wsStatus === 'connected' ? 'text-green-400' : 
            wsStatus === 'error' ? 'text-red-400' : 'text-gray-500'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              wsStatus === 'connected' ? 'bg-green-400' : 
              wsStatus === 'error' ? 'bg-red-400' : 'bg-gray-500'
            }`}></div>
            WebSocket: {wsStatus}
          </div>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Binance Control Panel */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-orange-400">
          <Activity className="w-5 h-5" />
          Binance Control
        </h2>
        <div className="space-y-3">
          <h3 className="text-sm text-gray-400 font-mono">BINANCE CONTROL</h3>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => toggleSimulation('binance')}
              className={`px-4 py-2 border rounded flex items-center gap-2 transition-all font-mono ${
                binanceStatus === 'running'
                  ? 'bg-red-600/20 border-red-500 hover:bg-red-600/40 text-red-400 hover:text-red-300'
                  : 'bg-orange-600/20 border-orange-500 hover:bg-orange-600/40 text-orange-400 hover:text-orange-300'
              }`}
            >
              {binanceStatus === 'running' ? (
                <>
                  <Pause className="w-4 h-4" />
                  Stop Binance
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Binance
                </>
              )}
            </button>
            <button
              onClick={() => fetch('http://127.0.0.1:5000/binance/generate', { method: 'POST' })}
              className="px-4 py-2 bg-yellow-600/20 border border-yellow-500 hover:bg-yellow-600/40 rounded text-yellow-400 hover:text-yellow-300 transition-all"
            >
              Binance Trade
            </button>
            <button
              onClick={handleDeleteAllTrades}
              className="px-4 py-2 bg-red-700/20 border border-red-600 hover:bg-red-700/40 rounded text-red-400 hover:text-red-300 transition-all font-mono"
            >
              Clear Trades
            </button>
            <button
              onClick={handleClearAllStatus}
              className="px-4 py-2 bg-gray-600/20 border border-gray-500 hover:bg-gray-600/40 rounded text-gray-400 hover:text-gray-300 transition-all font-mono"
            >
              Reset Status
            </button>
          </div>
        </div>
      </div>

      {/* Intelligent Trading Panel */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-purple-400">
          <TrendingUp className="w-5 h-5" />
          Intelligent Trading
        </h2>
        <div className="space-y-3">
          <h3 className="text-sm text-gray-400 font-mono">TECHNICAL ANALYSIS CONTROL</h3>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => toggleSimulation('intelligent')}
              className={`px-4 py-2 border rounded flex items-center gap-2 transition-all font-mono ${
                intelligentStatus === 'running'
                  ? 'bg-red-600/20 border-red-500 hover:bg-red-600/40 text-red-400 hover:text-red-300'
                  : binanceStatus === 'running'
                    ? 'bg-purple-600/20 border-purple-500 hover:bg-purple-600/40 text-purple-400 hover:text-purple-300'
                    : 'bg-gray-600/20 border-gray-500 hover:bg-gray-600/40 text-gray-400 hover:text-gray-300'
              }`}
              disabled={binanceStatus !== 'running'}
            >
              {intelligentStatus === 'running' ? (
                <>
                  <Pause className="w-4 h-4" />
                  Stop Intelligent
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Intelligent
                </>
              )}
            </button>
            <button
              onClick={() => fetch('http://127.0.0.1:5000/intelligent/generate', { method: 'POST' })}
              disabled={binanceStatus !== 'running'}
              className={`px-4 py-2 bg-purple-600/20 border border-purple-500 hover:bg-purple-600/40 rounded text-purple-400 hover:text-purple-300 transition-all ${
                binanceStatus !== 'running' ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              Intelligent Trade
            </button>
          </div>
          {binanceStatus !== 'running' && (
            <div className="mt-2 p-2 bg-yellow-900/20 border border-yellow-500/30 rounded text-yellow-400 text-xs">
              <span className="font-mono">⚠️ Binance must be running for technical analysis</span>
            </div>
          )}
        </div>
        
        {/* Strategy Selection Panel */}
        <div className="mt-4 space-y-3">
          <h3 className="text-sm text-gray-400 font-mono">STRATEGY SELECTION</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {[
              { key: 'MACD_Signal', name: 'MACD Signal', color: 'blue' },
              { key: 'MA_Cross', name: 'MA Cross', color: 'green' },
              { key: 'RSI_Divergence', name: 'RSI Divergence', color: 'purple' },
              { key: 'Bollinger_Bands', name: 'Bollinger Bands', color: 'orange' },
              { key: 'Volume_Breakout', name: 'Volume Breakout', color: 'cyan' },
              { key: 'Support_Resistance', name: 'Support/Resistance', color: 'pink' }
            ].map((strategy) => (
              <button
                key={strategy.key}
                onClick={() => {
                  setSelectedIntelligentStrategies(prev => 
                    prev.includes(strategy.key) 
                      ? prev.filter(s => s !== strategy.key)
                      : [...prev, strategy.key]
                  );
                }}
                disabled={intelligentStatus === 'running'}
                className={`px-3 py-2 border rounded text-xs font-mono transition-all ${
                  selectedIntelligentStrategies.includes(strategy.key)
                    ? `bg-${strategy.color}-600/20 border-${strategy.color}-500 text-${strategy.color}-300`
                    : 'bg-gray-800/30 border-gray-600 text-gray-400'
                } ${
                  intelligentStatus === 'running' 
                    ? 'opacity-50 cursor-not-allowed' 
                    : 'hover:opacity-80'
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    selectedIntelligentStrategies.includes(strategy.key)
                      ? `bg-${strategy.color}-400`
                      : 'bg-gray-500'
                  }`}></div>
                  <span>{strategy.name}</span>
                </div>
              </button>
            ))}
          </div>
          {intelligentStatus === 'running' && (
            <div className="mt-2 p-2 bg-red-900/20 border border-red-500/30 rounded text-red-400 text-xs">
              <span className="font-mono">⚠️ Stop Intelligent to change strategies</span>
            </div>
          )}
          <div className="mt-2 text-xs text-gray-500">
            <span className="font-mono">Selected: {selectedIntelligentStrategies.length}/6 strategies</span>
          </div>
        </div>
      </div>

      {/* Micro Profit Generator Panel */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-green-400">
          <DollarSign className="w-5 h-5" />
          Micro Profit Generator
        </h2>
        
        <div className="space-y-4">
          <h3 className="text-sm text-gray-400 font-mono">PROFIT MAXIMIZER ($0.01+ per trade)</h3>
          
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => {
                fetch('http://127.0.0.1:5000/micro-profit/generate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ iterations: 5 })
                }).then(res => res.json()).then(data => {
                  if (data.status === 'success') {
                    toast.success(`💰 Generated ${data.trades_generated} micro-trades`, { toastId: 'micro-profit-success' });
                  } else {
                    toast.error(data.message || 'Failed to generate micro-trades', { toastId: 'micro-profit-error' });
                  }
                }).catch(() => {
                  toast.error('Error generating micro-trades', { toastId: 'micro-profit-exception' });
                });
              }}
              className="px-4 py-2 bg-green-600/20 border border-green-500 hover:bg-green-600/40 rounded text-green-400 hover:text-green-300 transition-all font-mono"
            >
              Generate 5 Trades ($0.05)
            </button>
            
            <button
              onClick={() => {
                fetch('http://127.0.0.1:5000/micro-profit/generate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ iterations: 10 })
                }).then(res => res.json()).then(data => {
                  if (data.status === 'success') {
                    toast.success(`💰 Generated ${data.trades_generated} micro-trades`, { toastId: 'micro-profit-success' });
                  } else {
                    toast.error(data.message || 'Failed to generate micro-trades', { toastId: 'micro-profit-error' });
                  }
                }).catch(() => {
                  toast.error('Error generating micro-trades', { toastId: 'micro-profit-exception' });
                });
              }}
              className="px-4 py-2 bg-green-600/20 border border-green-500 hover:bg-green-600/40 rounded text-green-400 hover:text-green-300 transition-all font-mono"
            >
              Generate 10 Trades ($0.10)
            </button>
            
            <button
              onClick={() => {
                fetch('http://127.0.0.1:5000/micro-profit/generate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ iterations: 20 })
                }).then(res => res.json()).then(data => {
                  if (data.status === 'success') {
                    toast.success(`💰 Generated ${data.trades_generated} micro-trades`, { toastId: 'micro-profit-success' });
                  } else {
                    toast.error(data.message || 'Failed to generate micro-trades', { toastId: 'micro-profit-error' });
                  }
                }).catch(() => {
                  toast.error('Error generating micro-trades', { toastId: 'micro-profit-exception' });
                });
              }}
              className="px-4 py-2 bg-green-600/20 border border-green-500 hover:bg-green-600/40 rounded text-green-400 hover:text-green-300 transition-all font-mono"
            >
              Generate 20 Trades ($0.20)
            </button>
          </div>
          
          {/* Micro Profit Stats */}
          {microProfitStats && (
            <div className="mt-4 p-3 bg-green-900/20 border border-green-500/30 rounded-lg">
              <h4 className="text-xs font-mono text-green-400 mb-2">MICRO TRADING STATS</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <div className="text-gray-400">Total Trades</div>
                  <div className="text-green-300 font-mono">{microProfitStats.total_micro_trades}</div>
                </div>
                <div>
                  <div className="text-gray-400">Win Rate</div>
                  <div className="text-green-300 font-mono">{microProfitStats.win_rate}%</div>
                </div>
                <div>
                  <div className="text-gray-400">Total Profit</div>
                  <div className="text-green-300 font-mono">${microProfitStats.total_profit.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Avg Profit</div>
                  <div className="text-green-300 font-mono">${microProfitStats.avg_profit_per_trade.toFixed(4)}</div>
                </div>
              </div>
            </div>
          )}
          
          <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/30 rounded text-blue-400 text-xs">
            <span className="font-mono">📋 High-probability trading with 90%+ win rate and $0.01+ minimum profit per trade</span>
          </div>
        </div>
      </div>

      {/* Binance Trading Modes Panel */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-orange-400">
          <Activity className="w-5 h-5" />
          Binance Trading Modes
        </h2>
        
        {/* Warning when Binance is not running */}
        {binanceStatus !== 'running' && (
          <div className="mb-4 p-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-mono">Binance must be running before using trading modes</span>
            </div>
          </div>
        )}
        
        {Object.keys(tradingModes).length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            <div className="mb-2">🔧 Trading modes not available</div>
            <div className="text-sm">Make sure the backend is updated with mode endpoints</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(tradingModes).map(([modeKey, mode]) => (
              <div key={modeKey} className="border border-gray-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-cyan-400 capitalize">{modeKey}</h3>
                    <p className="text-sm text-gray-400">{mode.name}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-full border text-sm font-mono ${
                    binanceModeStatus[modeKey] === 'running'
                      ? 'bg-green-900/50 border-green-500 text-green-400'
                      : 'bg-gray-900/50 border-gray-700 text-gray-500'
                  }`}>
                    {binanceModeStatus[modeKey] === 'running' ? 'RUNNING' : 'STOPPED'}
                  </div>
                </div>
                
                <div className="grid grid-cols-1 gap-2 mb-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk:</span>
                    <span className="font-mono text-orange-400">{(mode.risk_percentage * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Win Rate:</span>
                    <span className="font-mono text-green-400">{(mode.win_rate * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">R:R:</span>
                    <span className="font-mono text-cyan-400">1:{mode.reward_risk_ratio}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Max Loss:</span>
                    <span className="font-mono text-red-400">{mode.max_consecutive_losses}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Trades/H:</span>
                    <span className="font-mono text-purple-400">{mode.trades_per_hour}</span>
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleBinanceModeControl('select', modeKey)}
                    disabled={binanceStatus !== 'running'}
                    className={`px-4 py-2 border rounded flex items-center gap-2 transition-all text-sm font-mono relative overflow-hidden ${
                      selectedModes.includes(modeKey)
                        ? modeKey === 'conservative' 
                          ? 'bg-green-600/30 border-green-500 text-green-300 shadow-lg shadow-green-500/20'
                          : modeKey === 'hybrid'
                            ? 'bg-blue-600/30 border-blue-500 text-blue-300 shadow-lg shadow-blue-500/20'
                            : 'bg-orange-600/30 border-orange-500 text-orange-300 shadow-lg shadow-orange-500/20'
                        : binanceStatus !== 'running'
                          ? 'bg-gray-800/20 border-gray-700 text-gray-600 cursor-not-allowed'
                          : 'bg-gray-800/30 border-gray-600 text-gray-400 hover:bg-gray-700/40 hover:text-gray-300'
                    }`}
                  >
                    {/* Indicador de selección */}
                    {selectedModes.includes(modeKey) && (
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-pulse"></div>
                    )}
                    
                    {/* Icono */}
                    {selectedModes.includes(modeKey) ? (
                      <div className="w-3 h-3 rounded-full bg-current animate-pulse"></div>
                    ) : (
                      <div className="w-3 h-3 rounded-full border-2 border-current"></div>
                    )}
                    
                    {/* Texto */}
                    <span className="relative z-10">
                      {selectedModes.includes(modeKey) ? 'Active' : 'Select'}
                    </span>
                  </button>
                  <button
                    onClick={() => handleBinanceModeControl('generate', modeKey)}
                    disabled={selectedModes.length === 0}
                    className={`px-3 py-1 rounded text-sm font-mono transition-all ${
                      selectedModes.includes(modeKey)
                        ? 'bg-yellow-600/20 border border-yellow-500 hover:bg-yellow-600/40 text-yellow-400 hover:text-yellow-300'
                        : 'bg-gray-700/20 border border-gray-600 text-gray-500 cursor-not-allowed'
                    }`}
                  >
                    Generate Trade
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
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
            <AreaChart data={equityData}>
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
                domain={[95, 'dataMax + 5']} // Empezar desde $95 y mostrar hasta 5% por encima del máximo
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
              {/* Línea de referencia del capital inicial */}
              <Area
                type="monotone"
                dataKey={() => 100}
                stroke="#10B981"
                strokeDasharray="5 5"
                strokeWidth={1}
                fill="none"
                dot={false}
              />
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

        {/* Trades Section */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-cyan-400">All Trades</h2>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-400">
                Showing: {trades.length} of {allTrades.length} trades
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleShowMoreTrades}
                  disabled={!hasMoreTrades}
                  className={`px-3 py-1 border rounded flex items-center gap-2 text-sm font-mono transition-all ${
                    hasMoreTrades
                      ? 'bg-blue-600/20 border-blue-500 hover:bg-blue-600/40 text-blue-400 hover:text-blue-300'
                      : 'bg-gray-600/20 border-gray-500 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  Show 50 More
                </button>
                <button
                  onClick={handleShowAllTrades}
                  disabled={trades.length === allTrades.length}
                  className={`px-3 py-1 border rounded flex items-center gap-2 text-sm font-mono transition-all ${
                    trades.length === allTrades.length
                      ? 'bg-gray-600/20 border-gray-500 text-gray-500 cursor-not-allowed'
                      : 'bg-purple-600/20 border-purple-500 hover:bg-purple-600/40 text-purple-400 hover:text-purple-300'
                  }`}
                >
                  Show All
                </button>
                <button
                  onClick={copyAllTrades}
                  className="px-3 py-1 bg-cyan-600/20 border border-cyan-500 hover:bg-cyan-600/40 rounded flex items-center gap-2 text-cyan-400 hover:text-cyan-300 transition-all text-sm"
                >
                  <Copy className="w-4 h-4" />
                  Copy All
                </button>
                <button
                  onClick={downloadTradesCSV}
                  className="px-3 py-1 bg-purple-600/20 border border-purple-500 hover:bg-purple-600/40 rounded flex items-center gap-2 text-purple-400 hover:text-purple-300 transition-all text-sm"
                >
                  <Download className="w-4 h-4" />
                  Download CSV
                </button>
              </div>
            </div>
          </div>
          {trades.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-8">
              No trades yet
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800">
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">ID</th>
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">Opened</th>
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">Closed</th>
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">Symbol</th>
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">Strategy</th>
                      <th className="text-left py-3 px-4 text-gray-400 font-mono">Engine</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Entry</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Exit</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Size</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Investment</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">P&L</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">%</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Costs</th>
                      <th className="text-center py-3 px-4 text-gray-400 font-mono">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map(trade => {
                      const entryTime = new Date(trade.timestamp_entry);
                      const isOpen = !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0;
                      let exitTime, duration, durationMinutes;
                      
                      if (isOpen) {
                        const now = new Date();
                        duration = now.getTime() - entryTime.getTime();
                        durationMinutes = Math.floor(duration / 60000);
                        exitTime = null;
                      } else {
                        exitTime = new Date(trade.timestamp_exit);
                        duration = exitTime.getTime() - entryTime.getTime();
                        durationMinutes = Math.floor(duration / 60000);
                      }

                      return (
                        <tr key={trade.id} className={`border-b border-gray-800 hover:bg-gray-900/50 transition-all ${
                          isOpen ? 'border-l-4 border-l-cyan-500' : 
                          trade.pnl >= 0 ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-red-500'
                        }`}>
                          <td className="py-3 px-4 font-mono text-gray-500">#{trade.id}</td>
                          <td className="py-3 px-4">
                            <div className="font-mono text-white">{entryTime.toLocaleDateString()}</div>
                            <div className="text-xs text-gray-400">{entryTime.toLocaleTimeString()}</div>
                          </td>
                          <td className="py-3 px-4">
                            {isOpen ? (
                              <div className="text-cyan-400 font-mono">OPEN</div>
                            ) : (
                              <>
                                <div className="font-mono text-white">{exitTime!.toLocaleDateString()}</div>
                                <div className="text-xs text-gray-400">{exitTime!.toLocaleTimeString()}</div>
                              </>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col">
                              <span className="font-mono text-cyan-400">{trade.symbol}</span>
                              <span className={`text-xs font-mono ${
                                trade.direction === 'long' ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {trade.direction === 'long' ? 'LONG' : 'SHORT'}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col">
                              <span className="font-mono text-purple-400 text-xs">{trade.strategy}</span>
                              <span className="text-xs text-gray-500 font-mono">{trade.source_engine}</span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col">
                              <span className="font-mono text-gray-400 text-xs">{trade.source_engine}</span>
                              {trade.source_mode && (
                                <span className="text-xs text-gray-500 font-mono">{trade.source_mode}</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex flex-col">
                              <span className="font-mono text-gray-400">${trade.entry_price.toFixed(2)}</span>
                              {trade.requested_entry_price !== trade.entry_price && (
                                <span className="text-xs text-orange-400 font-mono">
                                  ${trade.requested_entry_price.toFixed(2)}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            {isOpen ? (
                              <span className="text-cyan-400">-</span>
                            ) : (
                              <div className="flex flex-col">
                                <span className="font-mono text-gray-400">${trade.exit_price.toFixed(2)}</span>
                                {trade.requested_exit_price !== trade.exit_price && (
                                  <span className="text-xs text-orange-400 font-mono">
                                    ${trade.requested_exit_price.toFixed(2)}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-gray-400">
                            {trade.size.toFixed(6)}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-blue-400">
                            ${trade.investment_amount?.toFixed(2) || '0.00'}
                          </td>
                          <td className={`py-3 px-4 text-right font-bold font-mono ${
                            isOpen ? 'text-cyan-400' : 
                            trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {isOpen ? (
                              'OPEN'
                            ) : (
                              <div className="flex flex-col">
                                <span>{trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}</span>
                                {trade.gross_pnl !== trade.pnl && (
                                  <span className="text-xs text-gray-400">
                                    gross: ${trade.gross_pnl.toFixed(2)}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className={`py-3 px-4 text-right font-mono ${
                            isOpen ? 'text-cyan-400' : 
                            trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {isOpen ? (
                              '-'
                            ) : (
                              <div className="flex flex-col">
                                <span>{trade.pnl >= 0 ? '+' : ''}{trade.pnl_percentage.toFixed(1)}%</span>
                                {trade.total_costs > 0 && (
                                  <span className="text-xs text-orange-400">
                                    -{trade.cost_impact_pct.toFixed(2)}%
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {!isOpen && trade.total_costs > 0 && (
                              <div className="flex flex-col">
                                <span className="text-xs text-orange-400 font-mono">${trade.total_costs.toFixed(4)}</span>
                                <div className="text-xs text-gray-500">
                                  <div>fees: ${trade.entry_fees + trade.exit_fees}</div>
                                  <div>slip: ${trade.slippage_cost.toFixed(4)}</div>
                                  <div>spread: ${trade.spread_cost.toFixed(4)}</div>
                                </div>
                              </div>
                            )}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <div className="flex flex-col">
                              <span className="font-mono text-gray-400 text-xs">{trade.duration_formatted}</span>
                              {trade.confidence > 0 && (
                                <span className="text-xs text-blue-400 font-mono">
                                  {trade.confidence.toFixed(1)}%
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

              <div className="mt-6 pt-6 border-t border-gray-800">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Total Trades</div>
                    <div className="text-white font-mono font-bold">{allTrades.length}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Win Rate</div>
                    <div className="text-cyan-400 font-mono font-bold">
                      {allTrades.length > 0
                        ? `${((allTrades.filter(t => t.pnl > 0).length / allTrades.length) * 100).toFixed(1)}%`
                        : '0%'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Avg P&L</div>
                    <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ${allTrades.length > 0 ? (totalPnL / allTrades.length).toFixed(2) : '0.00'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Best Trade</div>
                    <div className="text-green-400 font-mono font-bold">
                      ${allTrades.length > 0 ? Math.max(...allTrades.map(t => t.pnl)).toFixed(2) : '0.00'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Worst Trade</div>
                    <div className="text-red-400 font-mono font-bold">
                      ${allTrades.length > 0 ? Math.min(...allTrades.map(t => t.pnl)).toFixed(2) : '0.00'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Total Costs</div>
                    <div className="text-orange-400 font-mono font-bold">
                      ${allTrades.length > 0 ? allTrades.reduce((sum, t) => sum + (t.total_costs || 0), 0).toFixed(4) : '0.0000'}
                    </div>
                  </div>
                </div>
              </div>
        </div>

      {/* Order Book de Nuestros Trades */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
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
                <div className="text-gray-400 text-xs mb-1">Total Compras</div>
                <div className="text-green-400 font-mono font-bold">
                  {allTrades.filter(t => t.direction === 'long').length}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">Total Ventas</div>
                <div className="text-red-400 font-mono font-bold">
                  {allTrades.filter(t => t.direction === 'short').length}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">P&L Compras</div>
                <div className={`font-mono font-bold ${
                  allTrades.filter(t => t.direction === 'long').reduce((sum, t) => sum + t.pnl, 0) >= 0 
                    ? 'text-green-400' : 'text-red-400'
                }`}>
                  ${allTrades.filter(t => t.direction === 'long').reduce((sum, t) => sum + t.pnl, 0).toFixed(2)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs mb-1">P&L Ventas</div>
                <div className={`font-mono font-bold ${
                  allTrades.filter(t => t.direction === 'short').reduce((sum, t) => sum + t.pnl, 0) >= 0 
                    ? 'text-green-400' : 'text-red-400'
                }`}>
                  ${allTrades.filter(t => t.direction === 'short').reduce((sum, t) => sum + t.pnl, 0).toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Alerts Panel */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
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
                      <div className={`text-xs ${alertStyle.color} font-mono`}>
                        {timeAgo}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        ID: #{alert.id}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 pt-6 border-t border-gray-800">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(alertCounts).map(([type, count]) => {
                  const style = getAlertStyle(type);
                  return (
                    <div key={type} className="text-center">
                      <div className="text-gray-400 text-xs mb-1">{style.icon} {type.replace('_', ' ')}</div>
                      <div className={`font-mono font-bold ${style.color}`}>{count}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
