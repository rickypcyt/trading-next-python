import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, Calendar } from 'lucide-react';
import type { Trade } from '../types';
import { PanelState } from './PanelState';

type Granularity = 'hour' | 'day' | 'week' | 'month';

interface TradesGenerationPanelProps {
  trades: Trade[];
  className?: string;
}

function getISOWeek(date: Date): number {
  const tmp = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  return Math.ceil((((tmp.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

function getBucketKey(date: Date, granularity: Granularity): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const h = String(date.getHours()).padStart(2, '0');

  switch (granularity) {
    case 'hour':
      return `${y}-${m}-${d} ${h}:00`;
    case 'day':
      return `${y}-${m}-${d}`;
    case 'week': {
      const week = getISOWeek(date);
      return `${y}-W${String(week).padStart(2, '0')}`;
    }
    case 'month':
      return `${y}-${m}`;
  }
}

interface Bucket {
  label: string;
  count: number;
  pnl: number;
}

function groupTradesByPeriod(trades: Trade[], granularity: Granularity): Bucket[] {
  const groups = new Map<string, Bucket>();

  for (const trade of trades) {
    const timestamp = trade.timestamp_entry || trade.timestamp_exit;
    if (!timestamp) continue;

    const date = new Date(timestamp);
    if (isNaN(date.getTime())) continue;

    const key = getBucketKey(date, granularity);
    const existing = groups.get(key);
    if (existing) {
      existing.count += 1;
      existing.pnl += trade.pnl;
    } else {
      groups.set(key, { label: key, count: 1, pnl: trade.pnl });
    }
  }

  return Array.from(groups.values()).sort((a, b) => a.label.localeCompare(b.label));
}

const GRANULARITY_LABELS: Record<Granularity, string> = {
  hour: 'Hour',
  day: 'Day',
  week: 'Week',
  month: 'Month',
};

export default function TradesGenerationPanel({ trades, className = '' }: TradesGenerationPanelProps) {
  const [granularity, setGranularity] = useState<Granularity>('day');

  const data = useMemo(() => groupTradesByPeriod(trades, granularity), [trades, granularity]);

  const totals = useMemo(() => {
    const totalCount = data.reduce((sum, b) => sum + b.count, 0);
    const totalPnl = data.reduce((sum, b) => sum + b.pnl, 0);
    const bestBucket = data.length > 0 ? data.reduce((max, b) => (b.count > max.count ? b : max), data[0]) : null;
    return { totalCount, totalPnl, bestBucket };
  }, [data]);

  return (
    <div className={`bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2 text-cyan-400">
          <BarChart3 className="w-5 h-5" />
          Trade Generation by Period
        </h2>

        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-400" />
          <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-800">
            {( ['hour', 'day', 'week', 'month'] as Granularity[] ).map((g) => (
              <button
                key={g}
                onClick={() => setGranularity(g)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  granularity === g
                    ? 'bg-cyan-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                {GRANULARITY_LABELS[g]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {data.length === 0 ? (
        <PanelState kind="empty" title="Sin trades en este periodo" hint="Cuando los engines ejecuten trades verás aquí cuántos se generan por hora, día, semana o mes. Prueba con otra granularidad." />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Total Trades</p>
              <p className="text-2xl font-bold text-white">{totals.totalCount}</p>
            </div>
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Net P&L</p>
              <p className={`text-2xl font-bold ${totals.totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {totals.totalPnl >= 0 ? '+' : ''}${totals.totalPnl.toFixed(2)}
              </p>
            </div>
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4">
              <p className="text-gray-400 text-sm">Most Active {GRANULARITY_LABELS[granularity]}</p>
              <p className="text-lg font-semibold text-white truncate">
                {totals.bestBucket ? `${totals.bestBucket.label} (${totals.bestBucket.count})` : '-'}
              </p>
            </div>
          </div>

          <div className="h-64 mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="label" stroke="#9ca3af" fontSize={12} angle={-30} textAnchor="end" height={60} />
                <YAxis stroke="#9ca3af" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '0.5rem' }}
                  itemStyle={{ color: '#e5e7eb' }}
                  formatter={(value: number) => [value, 'Trades']}
                />
                <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-800">
                  <th className="pb-2 pl-2">Period</th>
                  <th className="pb-2">Trades</th>
                  <th className="pb-2">Net P&L</th>
                  <th className="pb-2">Avg P&L</th>
                </tr>
              </thead>
              <tbody>
                {data.slice().reverse().map((bucket) => (
                  <tr key={bucket.label} className="border-b border-gray-800/50 hover:bg-gray-900/30">
                    <td className="py-2 pl-2 text-gray-200">{bucket.label}</td>
                    <td className="py-2 text-gray-200">{bucket.count}</td>
                    <td className={`py-2 font-medium ${bucket.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {bucket.pnl >= 0 ? '+' : ''}${bucket.pnl.toFixed(2)}
                    </td>
                    <td className={`py-2 ${bucket.pnl / bucket.count >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {bucket.pnl / bucket.count >= 0 ? '+' : ''}${(bucket.pnl / bucket.count).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
