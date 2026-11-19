'use client';

import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Wallet, Zap } from 'lucide-react';
import { apiUrl } from '@/lib/api';

interface EngineAllocation {
  base_allocation: number;
  performance_multiplier: number;
  final_allocation: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  total_pnl: number;
  current_streak: number;
  risk_per_trade: number;
}

interface AllocationData {
  total_capital: number;
  allocations: Record<string, EngineAllocation>;
  last_refresh: string | null;
}

export default function CapitalAllocation({ className }: { className?: string }) {
  const [allocation, setAllocation] = useState<AllocationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAllocation = async () => {
      try {
        const res = await fetch(apiUrl('/capital/allocation'));
        if (!res.ok) return;
        const data = await res.json();
        setAllocation(data);
      } catch (e) {
        console.error('Error fetching capital allocation:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchAllocation();
    const interval = setInterval(fetchAllocation, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className={`bg-slate-900/80 backdrop-blur-sm rounded-xl border border-slate-800 p-6 ${className}`}>
        <div className="animate-pulse text-slate-500">Cargando allocation...</div>
      </div>
    );
  }

  if (!allocation || !allocation.allocations) {
    return null;
  }

  const engines = Object.entries(allocation.allocations).sort(
    (a, b) => b[1].final_allocation - a[1].final_allocation
  );

  return (
    <div className={`bg-slate-900/80 backdrop-blur-sm rounded-xl border border-slate-800 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-semibold text-white">Capital Allocation Dinámica</h2>
        </div>
        <div className="text-sm text-slate-400">
          Total: <span className="text-amber-400 font-bold">${allocation.total_capital.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-3">
        {engines.map(([engineName, data]) => {
          const isProfitable = data.total_pnl > 0;
          const streakPositive = data.current_streak > 0;
          const multiplier = data.performance_multiplier;
          const pctOfTotal = allocation.total_capital > 0
            ? (data.final_allocation / allocation.total_capital) * 100
            : 0;

          return (
            <div
              key={engineName}
              className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">{engineName}</span>
                  {multiplier > 1.2 && (
                    <span className="flex items-center gap-0.5 text-xs text-emerald-400">
                      <TrendingUp className="w-3 h-3" />
                      {multiplier.toFixed(1)}x
                    </span>
                  )}
                  {multiplier < 0.8 && (
                    <span className="flex items-center gap-0.5 text-xs text-red-400">
                      <TrendingDown className="w-3 h-3" />
                      {multiplier.toFixed(1)}x
                    </span>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-lg font-bold text-amber-400">
                    ${data.final_allocation.toFixed(2)}
                  </span>
                  <span className="text-xs text-slate-500 ml-1">
                    ({pctOfTotal.toFixed(1)}%)
                  </span>
                </div>
              </div>

              {/* Barra de allocation */}
              <div className="w-full bg-slate-700/50 rounded-full h-2 mb-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    isProfitable ? 'bg-emerald-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.min(pctOfTotal, 100)}%` }}
                />
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div>
                  <span className="text-slate-500">Win Rate</span>
                  <div className={data.win_rate >= 0.5 ? 'text-emerald-400' : 'text-red-400'}>
                    {(data.win_rate * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">P&L</span>
                  <div className={isProfitable ? 'text-emerald-400' : 'text-red-400'}>
                    {isProfitable ? '+' : ''}${data.total_pnl.toFixed(2)}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">Trades</span>
                  <div className="text-slate-300">{data.total_trades}</div>
                </div>
                <div>
                  <span className="text-slate-500">Streak</span>
                  <div className={streakPositive ? 'text-emerald-400' : data.current_streak < 0 ? 'text-red-400' : 'text-slate-400'}>
                    {data.current_streak > 0 ? `${data.current_streak}W` : data.current_streak < 0 ? `${Math.abs(data.current_streak)}L` : '-'}
                  </div>
                </div>
              </div>

              {/* Risk per trade */}
              <div className="flex items-center gap-1 mt-2 text-xs text-slate-500">
                <Zap className="w-3 h-3" />
                Risk/trade: {(data.risk_per_trade * 100).toFixed(2)}%
                <span className="text-slate-600">·</span>
                PF: {data.profit_factor.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 text-xs text-slate-500 text-center">
        Los engines con mejor performance reciben más capital automáticamente
      </div>
    </div>
  );
}
