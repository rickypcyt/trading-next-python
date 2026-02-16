'use client';

import { Activity, AlertTriangle, Bell, Copy, DollarSign, Download, Pause, Play, Settings, TrendingDown, TrendingUp } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useEffect, useState } from 'react';

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

export default function TradingDashboard() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [metrics, setMetrics] = useState<Metric | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [equityData, setEquityData] = useState<EquityPoint[]>([]);
  const [wsStatus, setWsStatus] = useState<string>('disconnected');
  const [simulationStatus, setSimulationStatus] = useState<string>('stopped');
  const [binanceStatus, setBinanceStatus] = useState<string>('stopped');

  useEffect(() => {
    // Fetch initial data
    const fetchAllData = async () => {
      try {
        const [tradesRes, metricsRes, alertsRes, equityRes] = await Promise.all([
          fetch('http://127.0.0.1:5000/trades'),
          fetch('http://127.0.0.1:5000/metrics'),
          fetch('http://127.0.0.1:5000/alerts'),
          fetch('http://127.0.0.1:5000/equity')
        ]);

        const [tradesData, metricsData, alertsData, equityData] = await Promise.all([
          tradesRes.json(),
          metricsRes.json(),
          alertsRes.json(),
          equityRes.json()
        ]);

        setTrades(tradesData);
        setMetrics(metricsData[0] || null);
        setAlerts(alertsData);
        setEquityData(equityData.reverse());
      } catch (error) {
        console.error('Error fetching data:', error);
        toast.error('Error loading dashboard data');
      }
    };

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
          toast.success('WebSocket connected', { autoClose: 2000 });
        };
        
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'simulation_started':
              setSimulationStatus('running');
              toast.success('🚀 Auto simulation started');
              break;
              
            case 'simulation_stopped':
              setSimulationStatus('stopped');
              toast.error('⏹️ Auto simulation stopped');
              break;
              
            case 'binance_simulation_started':
              setBinanceStatus('running');
              toast.success('💎 Binance real-time simulation started');
              break;
              
            case 'binance_simulation_stopped':
              setBinanceStatus('stopped');
              toast.error('⏹️ Binance simulation stopped');
              break;
              
            case 'trade_added':
            case 'real_trade_generated':
              toast.success(`📈 Trade added: ${data.data.symbol} (${data.data.pnl > 0 ? '+' : ''}$${data.data.pnl})`);
              fetchAllData(); // Refresh data
              break;
              
            case 'equity_updated':
              toast.info(`💰 Equity updated: $${data.data.capital}`);
              fetchAllData();
              break;
              
            case 'metrics_updated':
              toast.info('📊 Metrics updated');
              fetchAllData();
              break;
              
            case 'alert_added':
              toast.warning(`🚨 Alert: ${data.data.type}`);
              fetchAllData();
              break;
          }
        };
        
        ws.onclose = () => {
          setWsStatus('disconnected');
          toast.error('WebSocket disconnected');
          
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
  }, []);

  const handleSimulationControl = async (action: 'start' | 'stop', type: 'simulation' | 'binance') => {
    try {
      const endpoint = type === 'simulation' ? '/simulation' : '/binance';
      const response = await fetch(`http://127.0.0.1:5000${endpoint}/${action}`, { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'already_running') {
        toast.info(`${type} is already running`);
      }
    } catch {
      toast.error(`Error controlling ${type}`);
    }
  };

  const toggleSimulation = (type: 'simulation' | 'binance') => {
    const isRunning = type === 'simulation' ? simulationStatus === 'running' : binanceStatus === 'running';
    const action: 'start' | 'stop' = isRunning ? 'stop' : 'start';
    handleSimulationControl(action, type);
  };

  const totalPnL = trades.reduce((sum, trade) => sum + trade.pnl, 0);

  const copyAllTrades = () => {
    if (trades.length === 0) {
      toast.error('No trades to copy');
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
      toast.success(`✅ Copied ${trades.length} trades to clipboard!`);
    }).catch(() => {
      toast.error('❌ Failed to copy trades');
    });
  };

  const downloadTradesCSV = () => {
    if (trades.length === 0) {
      toast.error('No trades to download');
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
    
    toast.success(`📥 Downloaded ${trades.length} trades as CSV!`);
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
            simulationStatus === 'running' 
              ? 'bg-blue-900/50 border-blue-500 text-blue-400' 
              : 'bg-gray-900/50 border-gray-700 text-gray-500'
          }`}>
            <span className="font-mono">Simulation: {simulationStatus}</span>
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm text-gray-400 mb-2 font-mono">SIMULATION CONTROL</h3>
            <div className="flex gap-2">
              <button
                onClick={() => toggleSimulation('simulation')}
                className={`px-4 py-2 border rounded flex items-center gap-2 transition-all font-mono ${
                  simulationStatus === 'running'
                    ? 'bg-red-600/20 border-red-500 hover:bg-red-600/40 text-red-400 hover:text-red-300'
                    : 'bg-purple-600/20 border-purple-500 hover:bg-purple-600/40 text-purple-400 hover:text-purple-300'
                }`}
              >
                {simulationStatus === 'running' ? (
                  <>
                    <Pause className="w-4 h-4" />
                    Stop Auto
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Start Auto
                  </>
                )}
              </button>
              <button
                onClick={() => fetch('http://127.0.0.1:5000/simulation/generate', { method: 'POST' })}
                className="px-4 py-2 bg-indigo-600/20 border border-indigo-500 hover:bg-indigo-600/40 rounded text-indigo-400 hover:text-indigo-300 transition-all"
              >
                Generate Trade
              </button>
            </div>
          </div>
          <div>
            <h3 className="text-sm text-gray-400 mb-2 font-mono">BINANCE CONTROL</h3>
            <div className="flex gap-2">
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
            </div>
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

        {/* Recent Trades */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm lg:col-span-2">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-cyan-400">All Trades History</h2>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-400">
                Total: {trades.length} trades | 
                Ganadores: {trades.filter(t => t.pnl > 0).length} | 
                Perdedores: {trades.filter(t => t.pnl < 0).length}
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left py-3 px-4 text-gray-400 font-mono">ID</th>
                  <th className="text-left py-3 px-4 text-gray-400 font-mono">Timestamp</th>
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
                {trades.map((trade) => {
                  const entryTime = new Date(trade.timestamp_entry);
                  const exitTime = new Date(trade.timestamp_exit);
                  const duration = exitTime.getTime() - entryTime.getTime();
                  const durationMinutes = Math.floor(duration / 60000);
                  const pnlPercentage = ((trade.pnl / 100) * 100);
                  
                  return (
                    <tr 
                      key={trade.id} 
                      className={`border-b border-gray-800 hover:bg-gray-900/50 transition-all ${
                        trade.pnl >= 0 ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-red-500'
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-gray-500">#{trade.id}</td>
                      <td className="py-3 px-4">
                        <div className="font-mono text-white">{entryTime.toLocaleDateString()}</div>
                        <div className="text-xs text-gray-400">{entryTime.toLocaleTimeString()}</div>
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
                        ${trade.exit_price.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-gray-400">
                        {trade.size.toFixed(6)}
                      </td>
                      <td className={`py-3 px-4 text-right font-bold font-mono ${
                        trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                      </td>
                      <td className={`py-3 px-4 text-right font-mono ${
                        trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {trade.pnl >= 0 ? '+' : ''}{pnlPercentage.toFixed(1)}%
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-gray-400">
                        {durationMinutes < 60 
                          ? `${durationMinutes}m` 
                          : durationMinutes < 1440 
                            ? `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`
                            : `${Math.floor(durationMinutes / 1440)}d ${Math.floor((durationMinutes % 1440) / 60)}h`
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          {/* Resumen de trades al final */}
          <div className="mt-6 pt-6 border-t border-gray-800">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">Total Trades</div>
                <div className="text-white font-mono font-bold">{trades.length}</div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">Win Rate</div>
                <div className="text-cyan-400 font-mono font-bold">
                  {trades.length > 0 
                    ? `${((trades.filter(t => t.pnl > 0).length / trades.length) * 100).toFixed(1)}%`
                    : '0%'
                  }
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">Avg P&L</div>
                <div className={`font-mono font-bold ${
                  totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  ${trades.length > 0 ? (totalPnL / trades.length).toFixed(2) : '0.00'}
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">Best Trade</div>
                <div className="text-green-400 font-mono font-bold">
                  ${trades.length > 0 ? Math.max(...trades.map(t => t.pnl)).toFixed(2) : '0.00'}
                </div>
              </div>
            </div>
          </div>
        </div>
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
        
        {/* Función para determinar estilo de alerta */}
        {(() => {
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
          
          return (
            <>
              <div className="space-y-2">
                {alerts.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Bell className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <div className="text-sm">No alerts yet</div>
                    <div className="text-xs mt-2">Alerts will appear here when trades are executed</div>
                  </div>
                ) : (
                  alerts.map(alert => {
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
                  })
                )}
              </div>
              
              {/* Resumen de alertas */}
              {alerts.length > 0 && (
                <div className="mt-6 pt-6 border-t border-gray-800">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {(() => {
                      const alertCounts = alerts.reduce((acc, alert) => {
                        acc[alert.type] = (acc[alert.type] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>);
                      
                      return Object.entries(alertCounts).map(([type, count]) => {
                        const style = getAlertStyle(type);
                        return (
                          <div key={type} className="text-center">
                            <div className="text-gray-400 text-xs mb-1">{style.icon} {type.replace('_', ' ')}</div>
                            <div className={`font-mono font-bold ${style.color}`}>{count}</div>
                          </div>
                        );
                      });
                    })()}
                  </div>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
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
