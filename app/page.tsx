'use client';

import { Activity, AlertTriangle, Bell, Copy, DollarSign, Download, Pause, Play, Settings, TrendingDown, TrendingUp } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { toast } from 'react-toastify';

interface Trade {
  id: number;
  timestamp_entry: string;
  timestamp_exit: string;
  symbol: string;
  strategy: string;
  entry_price: number;
  exit_price: number;
  size: number;
  pnl: number;
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
}

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
  const [metrics, setMetrics] = useState<Metric | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [equityData, setEquityData] = useState<EquityPoint[]>([]);
  const [wsStatus, setWsStatus] = useState<string>('disconnected');
  const [binanceStatus, setBinanceStatus] = useState<string>('stopped');

  const fetchAllData = useCallback(async () => {
    try {
      const [tradesRes, metricsRes, alertsRes, equityRes, statusRes] = await Promise.all([
        fetch('http://127.0.0.1:5000/trades'),
        fetch('http://127.0.0.1:5000/metrics'),
        fetch('http://127.0.0.1:5000/alerts'),
        fetch('http://127.0.0.1:5000/equity'),
        fetch('http://127.0.0.1:5000/status')
      ]);

      const [tradesData, metricsData, alertsData, equityDataResponse, statusData] = await Promise.all([
        tradesRes.json(),
        metricsRes.json(),
        alertsRes.json(),
        equityRes.json(),
        statusRes.json()
      ]);

      setTrades(tradesData);
      setMetrics(metricsData[0] || null);
      setAlerts(alertsData);
      setEquityData(equityDataResponse.reverse());
      if (statusData) {
        setBinanceStatus((statusData as SimulationStatus).binance);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error loading dashboard data', { toastId: 'fetch-error' });
    }
  }, []);

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
              toast.success('💎 Binance real-time simulation started', { toastId: 'binance-started' });
              break;
              
            case 'binance_simulation_stopped':
              setBinanceStatus('stopped');
              toast.error('⏹️ Binance simulation stopped', { toastId: 'binance-stopped' });
              break;
              
            case 'trade_added':
            case 'real_trade_generated':
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
          console.error('WebSocket error:', error);
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
  }, [fetchAllData]);

  const handleSimulationControl = async (action: 'start' | 'stop', type: 'simulation' | 'binance') => {
    try {
      const endpoint = type === 'simulation' ? '/simulation' : '/binance';
      const response = await fetch(`http://127.0.0.1:5000${endpoint}/${action}`, { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'already_running') {
        toast.info(`${type} is already running`, { toastId: `${type}-already-running` });
        if (type === 'binance') setBinanceStatus('running');
        return;
      }

      if (['started', 'stopped'].includes(result.status)) {
        setBinanceStatus(result.status === 'started' ? 'running' : 'stopped');
      }
    } catch {
      toast.error(`Error controlling ${type}`, { toastId: `${type}-control-error` });
    }
  };

  const toggleSimulation = (type: 'simulation' | 'binance') => {
    const isRunning = binanceStatus === 'running';
    const action: 'start' | 'stop' = isRunning ? 'stop' : 'start';
    handleSimulationControl(action, type);
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

  const openTrades = useMemo(
    () => trades.filter(trade => !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0),
    [trades]
  );

  const closedTrades = useMemo(
    () => trades.filter(trade => trade.timestamp_exit && trade.timestamp_exit !== '' && trade.exit_price !== 0),
    [trades]
  );

  const totalPnL = useMemo(
    () => closedTrades.reduce((sum, trade) => sum + trade.pnl, 0),
    [closedTrades]
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
    if (trades.length === 0) {
      toast.error('No trades to copy', { toastId: 'copy-trades-empty' });
      return;
    }

    // Crear texto CSV con todos los trades
    const headers = ['ID', 'Date', 'Time', 'Symbol', 'Strategy', 'Entry', 'Exit', 'Size', 'P&L', '%', 'Duration'];
    const csvContent = [
      headers.join(','),
      ...trades.map(trade => {
        const entryTime = new Date(trade.timestamp_entry);
        const exitTime = new Date(trade.timestamp_exit);
        const duration = exitTime.getTime() - entryTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        const pnlPercentage = ((trade.pnl / 100) * 100);
        
        const durationStr = durationMinutes < 60 
          ? `${durationMinutes}m` 
          : durationMinutes < 1440 
            ? `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`
            : `${Math.floor(durationMinutes / 1440)}d ${Math.floor((durationMinutes % 1440) / 60)}h`;
        
        return [
          trade.id,
          entryTime.toLocaleDateString(),
          entryTime.toLocaleTimeString(),
          trade.symbol,
          trade.strategy,
          trade.entry_price.toFixed(2),
          trade.exit_price.toFixed(2),
          trade.size.toFixed(6),
          `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}`,
          `${trade.pnl >= 0 ? '+' : ''}${pnlPercentage.toFixed(1)}%`,
          durationStr
        ].join(',');
      })
    ].join('\n');

    // Copiar al portapapeles
    navigator.clipboard.writeText(csvContent).then(() => {
      toast.success(`✅ Copied ${trades.length} trades to clipboard!`, { toastId: 'trades-copied' });
    }).catch(() => {
      toast.error('❌ Failed to copy trades', { toastId: 'trades-copy-error' });
    });
  };

  const downloadTradesCSV = () => {
    if (trades.length === 0) {
      toast.error('No trades to download', { toastId: 'download-trades-empty' });
      return;
    }

    // Crear contenido CSV
    const headers = ['ID', 'Date', 'Time', 'Symbol', 'Strategy', 'Entry', 'Exit', 'Size', 'P&L', '%', 'Duration'];
    const csvContent = [
      headers.join(','),
      ...trades.map(trade => {
        const entryTime = new Date(trade.timestamp_entry);
        const exitTime = new Date(trade.timestamp_exit);
        const duration = exitTime.getTime() - entryTime.getTime();
        const durationMinutes = Math.floor(duration / 60000);
        const pnlPercentage = ((trade.pnl / 100) * 100);
        
        const durationStr = durationMinutes < 60 
          ? `${durationMinutes}m` 
          : durationMinutes < 1440 
            ? `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`
            : `${Math.floor(durationMinutes / 1440)}d ${Math.floor((durationMinutes % 1440) / 60)}h`;
        
        return [
          trade.id,
          entryTime.toLocaleDateString(),
          entryTime.toLocaleTimeString(),
          trade.symbol,
          trade.strategy,
          trade.entry_price.toFixed(2),
          trade.exit_price.toFixed(2),
          trade.size.toFixed(6),
          `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}`,
          `${trade.pnl >= 0 ? '+' : ''}${pnlPercentage.toFixed(1)}%`,
          durationStr
        ].join(',');
      })
    ].join('\n');

    // Crear blob y descargar
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    toast.success(`📥 Downloaded ${trades.length} trades as CSV!`, { toastId: 'trades-downloaded' });
  };

  return (
    <div className="min-h-screen bg-black text-white p-6">
      {/* Header */}
      <div className="mb-8">


        <div className="flex items-center gap-4 text-sm">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full border ${
            wsStatus === 'connected' 
              ? 'bg-green-900/50 border-green-500 text-green-400' 
              : 'bg-red-900/50 border-red-500 text-red-400'
          }`}>
            <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-400' : 'bg-red-400'} animate-pulse`} />
            <span className="font-mono">WebSocket: {wsStatus}</span>
          </div>
          <div className={`px-3 py-1 rounded-full border ${
            binanceStatus === 'running' 
              ? 'bg-orange-900/50 border-orange-500 text-orange-400' 
              : 'bg-gray-900/50 border-gray-700 text-gray-500'
          }`}>
            <span className="font-mono">Binance: {binanceStatus}</span>
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div className="mb-8 bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-cyan-400">
          <Settings className="w-5 h-5" />
          Control Panel
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
          </div>
        </div>
      </div>

      {/* Metrics Panel */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
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
                <span className="text-gray-400">Ganancias</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-400 rounded-full"></div>
                <span className="text-gray-400">Pérdidas</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-cyan-400 rounded-full"></div>
                <span className="text-gray-400">Capital</span>
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-800">
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
              <div className="text-gray-400 text-sm mb-1">Retorno</div>
              <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {totalPnL >= 0 ? '+' : ''}{(totalPnL).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      </div>

        {/* Trades Section */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-cyan-400">All Trades</h2>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-400">
                Total: {trades.length} | Open: {openTrades.length} | Closed: {closedTrades.length}
              </div>
              <div className="flex gap-2">
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
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Entry</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Exit</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">Size</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">P&L</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-mono">%</th>
                      <th className="text-center py-3 px-4 text-gray-400 font-mono">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map(trade => {
                      const entryTime = new Date(trade.timestamp_entry);
                      const isOpen = !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0;
                      let exitTime, duration, durationMinutes, pnlPercentage;
                      
                      if (isOpen) {
                        const now = new Date();
                        duration = now.getTime() - entryTime.getTime();
                        durationMinutes = Math.floor(duration / 60000);
                        exitTime = null;
                        pnlPercentage = 0;
                      } else {
                        exitTime = new Date(trade.timestamp_exit);
                        duration = exitTime.getTime() - entryTime.getTime();
                        durationMinutes = Math.floor(duration / 60000);
                        pnlPercentage = ((trade.pnl / trade.entry_price) * 100);
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
                            <span className="font-mono text-cyan-400">{trade.symbol}</span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-mono text-purple-400">{trade.strategy}</span>
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-gray-400">
                            ${trade.entry_price.toFixed(2)}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-gray-400">
                            {isOpen ? (
                              <span className="text-cyan-400">-</span>
                            ) : (
                              `$${trade.exit_price.toFixed(2)}`
                            )}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-gray-400">
                            {trade.size.toFixed(6)}
                          </td>
                          <td className={`py-3 px-4 text-right font-bold font-mono ${
                            isOpen ? 'text-cyan-400' : 
                            trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {isOpen ? (
                              'OPEN'
                            ) : (
                              `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}`
                            )}
                          </td>
                          <td className={`py-3 px-4 text-right font-mono ${
                            isOpen ? 'text-cyan-400' : 
                            trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {isOpen ? (
                              '-'
                            ) : (
                              `${trade.pnl >= 0 ? '+' : ''}${pnlPercentage.toFixed(2)}%`
                            )}
                          </td>
                          <td className="py-3 px-4 text-center font-mono text-gray-400">
                            {formatDuration(durationMinutes)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-800">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Total Trades</div>
                    <div className="text-white font-mono font-bold">{trades.length}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Win Rate</div>
                    <div className="text-cyan-400 font-mono font-bold">
                      {closedTrades.length > 0
                        ? `${((closedTrades.filter(t => t.pnl > 0).length / closedTrades.length) * 100).toFixed(1)}%`
                        : '0%'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Avg P&L</div>
                    <div className={`font-mono font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      ${closedTrades.length > 0 ? (totalPnL / closedTrades.length).toFixed(2) : '0.00'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-400 text-sm mb-1">Best Trade</div>
                    <div className="text-green-400 font-mono font-bold">
                      ${closedTrades.length > 0 ? Math.max(...closedTrades.map(t => t.pnl)).toFixed(2) : '0.00'}
                    </div>
                  </div>
                </div>
              </div>
            </>
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
