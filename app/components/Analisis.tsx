'use client';

import { Activity, BarChart3, Calculator, DollarSign, PieChart as PieChartIcon, TrendingUp } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Trade } from '../page';
import { useMemo } from 'react';

interface AnalisisProps {
  trades: Trade[];
  engines: Record<string, {
    type?: string;
    status?: string;
    last_activity?: string | null;
    errors?: number;
    trades_generated?: number;
    metadata?: Record<string, unknown>;
  }>;
  className?: string;
}

interface EnginePerformance {
  engineId: string;
  engineType: string;
  status: string;
  trades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalPnL: number;
  averageWin: number;
  averageLoss: number;
  profitFactor: number;
  maxDrawdown: number;
  totalVolume: number;
  lastActivity: string | null;
  errors: number;
}

export default function Analisis({ trades, engines, className = '' }: AnalisisProps) {
  const enginePerformance = useMemo<EnginePerformance[]>(() => {
    const performance: EnginePerformance[] = [];
    
    const legacyBinanceModes = new Set(['binance_conservative', 'binance_hybrid', 'binance_aggressive']);
    const hiddenEngines = new Set(['execution', 'binance_basic']);

    Object.entries(engines).forEach(([engineId, engineData]) => {
      if (legacyBinanceModes.has(engineId) || hiddenEngines.has(engineId)) {
        return;
      }
      // Get trades for this engine
      const engineTrades = trades.filter(trade => trade.source_engine === engineId);
      
      if (engineTrades.length === 0 && !engineData.status) {
        return; // Skip engines with no trades and no status
      }
      
      const winningTrades = engineTrades.filter(t => t.pnl > 0);
      const losingTrades = engineTrades.filter(t => t.pnl < 0);
      const totalPnL = engineTrades.reduce((sum, t) => sum + t.pnl, 0);
      const totalWins = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
      const totalLosses = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));
      const totalVolume = engineTrades.reduce((sum, t) => sum + t.size, 0);
      
      const averageWin = winningTrades.length > 0 ? totalWins / winningTrades.length : 0;
      const averageLoss = losingTrades.length > 0 ? totalLosses / losingTrades.length : 0;
      const profitFactor = totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0;
      
      // Calculate max drawdown for this engine
      let runningPnL = 0;
      let peak = 0;
      let maxDrawdown = 0;
      engineTrades.forEach(trade => {
        runningPnL += trade.pnl;
        if (runningPnL > peak) peak = runningPnL;
        const drawdown = peak - runningPnL;
        if (drawdown > maxDrawdown) maxDrawdown = drawdown;
      });
      
      performance.push({
        engineId,
        engineType: engineData.type || 'Unknown',
        status: engineData.status || 'idle',
        trades: engineTrades.length,
        winningTrades: winningTrades.length,
        losingTrades: losingTrades.length,
        winRate: engineTrades.length > 0 ? (winningTrades.length / engineTrades.length) * 100 : 0,
        totalPnL,
        averageWin,
        averageLoss,
        profitFactor,
        maxDrawdown,
        totalVolume,
        lastActivity: engineData.last_activity || null,
        errors: engineData.errors || 0
      });
    });
    
    // Also add engines that might have trades but aren't in the engines object
    const uniqueEnginesFromTrades = [...new Set(trades.map(t => t.source_engine))];
    uniqueEnginesFromTrades.forEach(engineId => {
      if (!engines[engineId] && !legacyBinanceModes.has(engineId) && !hiddenEngines.has(engineId)) {
        const engineTrades = trades.filter(trade => trade.source_engine === engineId);
        const winningTrades = engineTrades.filter(t => t.pnl > 0);
        const losingTrades = engineTrades.filter(t => t.pnl < 0);
        const totalPnL = engineTrades.reduce((sum, t) => sum + t.pnl, 0);
        const totalWins = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
        const totalLosses = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));
        
        const averageWin = winningTrades.length > 0 ? totalWins / winningTrades.length : 0;
        const averageLoss = losingTrades.length > 0 ? totalLosses / losingTrades.length : 0;
        const profitFactor = totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0;
        
        performance.push({
          engineId,
          engineType: 'Unknown',
          status: 'idle',
          trades: engineTrades.length,
          winningTrades: winningTrades.length,
          losingTrades: losingTrades.length,
          winRate: engineTrades.length > 0 ? (winningTrades.length / engineTrades.length) * 100 : 0,
          totalPnL,
          averageWin,
          averageLoss,
          profitFactor,
          maxDrawdown: 0,
          totalVolume: engineTrades.reduce((sum, t) => sum + t.size, 0),
          lastActivity: null,
          errors: 0
        });
      }
    });
    
    return performance.sort((a, b) => b.totalPnL - a.totalPnL);
  }, [trades, engines]);

  const pieChartData = useMemo(() => {
    const totalWins = enginePerformance.reduce((sum, engine) => sum + engine.winningTrades, 0);
    const totalLosses = enginePerformance.reduce((sum, engine) => sum + engine.losingTrades, 0);
    return [
      { name: 'Winning Trades', value: totalWins, color: '#10b981' },
      { name: 'Losing Trades', value: totalLosses, color: '#ef4444' }
    ];
  }, [enginePerformance]);

  const enginePnLData = useMemo(() => {
    return enginePerformance.map(engine => ({
      engineId: engine.engineId,
      pnl: engine.totalPnL
    }));
  }, [enginePerformance]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`;
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <div className="flex items-center gap-3 mb-6">
          <BarChart3 className="w-6 h-6 text-cyan-400" />
          <h2 className="text-2xl font-bold text-cyan-400">Análisis de Engines</h2>
        </div>
        
        {/* Global Engine Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-blue-400" />
              <span className="text-sm text-gray-400">Total Engines</span>
            </div>
            <div className="text-2xl font-bold text-white">{enginePerformance.length}</div>
            <div className="text-xs text-gray-500 mt-1">
              {enginePerformance.filter(e => e.status === 'running').length} running
            </div>
          </div>

          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm text-gray-400">Total Trades</span>
            </div>
            <div className="text-2xl font-bold text-green-400">
              {enginePerformance.reduce((sum, e) => sum + e.trades, 0)}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              All engines combined
            </div>
          </div>

          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-yellow-400" />
              <span className="text-sm text-gray-400">Total P&L</span>
            </div>
            <div className={`text-2xl font-bold ${enginePerformance.reduce((sum, e) => sum + e.totalPnL, 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatCurrency(enginePerformance.reduce((sum, e) => sum + e.totalPnL, 0))}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Combined profit/loss
            </div>
          </div>

          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calculator className="w-4 h-4 text-purple-400" />
              <span className="text-sm text-gray-400">Avg Win Rate</span>
            </div>
            <div className="text-2xl font-bold text-purple-400">
              {formatPercentage(
                enginePerformance.length > 0 
                  ? enginePerformance.reduce((sum, e) => sum + e.winRate, 0) / enginePerformance.length 
                  : 0
              )}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Across all engines
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Win/Loss Pie Chart */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <PieChartIcon className="w-5 h-5 text-cyan-400" />
            Global Win/Loss Distribution
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieChartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value, percent }) => `${name}: ${value} (${(percent * 100).toFixed(0)}%)`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {pieChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Engine P&L Comparison */}
        <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            Engine P&L Comparison
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={enginePnLData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="engineId" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                formatter={(value: number) => [formatCurrency(value), 'P&L']}
              />
              <Bar dataKey="pnl" fill="#06b6d4" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Engine Performance Table */}
      <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          Engine Performance Details
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-3 px-4 text-gray-400">Engine</th>
                <th className="text-center py-3 px-4 text-gray-400">Status</th>
                <th className="text-right py-3 px-4 text-gray-400">Trades</th>
                <th className="text-right py-3 px-4 text-gray-400">Win Rate</th>
                <th className="text-right py-3 px-4 text-gray-400">Total P&L</th>
                <th className="text-right py-3 px-4 text-gray-400">Avg Win</th>
                <th className="text-right py-3 px-4 text-gray-400">Avg Loss</th>
                <th className="text-right py-3 px-4 text-gray-400">Profit Factor</th>
                <th className="text-right py-3 px-4 text-gray-400">Max DD</th>
                <th className="text-right py-3 px-4 text-gray-400">Errors</th>
              </tr>
            </thead>
            <tbody>
              {enginePerformance.map((engine, index) => (
                <tr key={engine.engineId} className={`border-b border-gray-800 ${index % 2 === 0 ? 'bg-gray-900/30' : ''}`}>
                  <td className="py-3 px-4">
                    <div>
                      <div className="text-white font-mono font-semibold">{engine.engineId}</div>
                      <div className="text-xs text-gray-400">{engine.engineType}</div>
                    </div>
                  </td>
                  <td className="text-center py-3 px-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      engine.status === 'running' 
                        ? 'bg-green-500/20 text-green-400 border border-green-500/40'
                        : engine.status === 'error'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                        : 'bg-gray-500/20 text-gray-400 border border-gray-500/40'
                    }`}>
                      {engine.status}
                    </span>
                  </td>
                  <td className="text-right py-3 px-4 text-gray-300">{engine.trades}</td>
                  <td className={`text-right py-3 px-4 ${engine.winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatPercentage(engine.winRate)}
                  </td>
                  <td className={`text-right py-3 px-4 font-semibold ${engine.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(engine.totalPnL)}
                  </td>
                  <td className={`text-right py-3 px-4 ${engine.averageWin >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(engine.averageWin)}
                  </td>
                  <td className={`text-right py-3 px-4 ${engine.averageLoss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(engine.averageLoss)}
                  </td>
                  <td className="text-right py-3 px-4 text-purple-400">
                    {engine.profitFactor === Infinity ? '∞' : engine.profitFactor.toFixed(2)}
                  </td>
                  <td className="text-right py-3 px-4 text-red-400">
                    {formatCurrency(engine.maxDrawdown)}
                  </td>
                  <td className="text-right py-3 px-4">
                    {engine.errors > 0 ? (
                      <span className="text-red-400 font-semibold">{engine.errors}</span>
                    ) : (
                      <span className="text-gray-400">{engine.errors}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Engine Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {enginePerformance.map((engine) => (
          <div key={engine.engineId} className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h4 className="text-white font-mono font-semibold">{engine.engineId}</h4>
                <p className="text-xs text-gray-400">{engine.engineType}</p>
              </div>
              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                engine.status === 'running' 
                  ? 'bg-green-500/20 text-green-400 border border-green-500/40'
                  : engine.status === 'error'
                  ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                  : 'bg-gray-500/20 text-gray-400 border border-gray-500/40'
              }`}>
                {engine.status}
              </span>
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Trades:</span>
                <span className="text-sm font-semibold text-white">{engine.trades}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Win Rate:</span>
                <span className={`text-sm font-semibold ${engine.winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatPercentage(engine.winRate)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">P&L:</span>
                <span className={`text-sm font-semibold ${engine.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatCurrency(engine.totalPnL)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-400">Profit Factor:</span>
                <span className="text-sm font-semibold text-purple-400">
                  {engine.profitFactor === Infinity ? '∞' : engine.profitFactor.toFixed(2)}
                </span>
              </div>
              {engine.lastActivity && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Last Activity:</span>
                  <span className="text-xs text-gray-300">
                    {new Date(engine.lastActivity).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
