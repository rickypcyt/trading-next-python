'use client';

import { Copy, Download, GripVertical, RotateCcw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

// Importar tipos desde page.tsx
import type { Trade } from '../types';

interface ColumnConfig {
  key: keyof Trade | 'custom_opened' | 'custom_closed' | 'custom_duration' | 'copy';
  label: string;
  align: 'left' | 'right' | 'center';
  width?: string;
}

const defaultColumns: ColumnConfig[] = [
  { key: 'copy', label: '', align: 'center', width: '60px' }, // Columna de copiar al principio
  { key: 'id', label: 'ID', align: 'left' },
  { key: 'custom_opened', label: 'Opened', align: 'left' },
  { key: 'custom_closed', label: 'Closed', align: 'left' },
  { key: 'symbol', label: 'Symbol', align: 'left' },
  { key: 'strategy', label: 'Strategy', align: 'left' },
  { key: 'entry_price', label: 'Entry', align: 'right' },
  { key: 'exit_price', label: 'Exit', align: 'right' },
  { key: 'size', label: 'Size', align: 'right' },
  { key: 'investment_amount', label: 'Amount', align: 'right' },
  { key: 'pnl', label: 'P&L', align: 'right' },
  { key: 'pnl_percentage', label: '%', align: 'right' },
  { key: 'custom_duration', label: 'Duration', align: 'center' },
];

interface TradesTableProps {
  trades: Trade[];
  allTrades: Trade[];
  hasMoreTrades: boolean;
  totalPnL: number;
  onShowMoreTrades: () => void;
  onShowAllTrades: () => void;
  onCopyAllTrades: () => void;
  onDownloadTradesCSV: () => void;
  onDeleteAllTrades: () => void;
  isDeletingAllTrades?: boolean;
}

const TradesTable: React.FC<TradesTableProps> = ({
  trades,
  allTrades,
  hasMoreTrades,
  totalPnL,
  onShowMoreTrades,
  onShowAllTrades,
  onCopyAllTrades,
  onDownloadTradesCSV,
  onDeleteAllTrades,
  isDeletingAllTrades = false,
}) => {
  // Cargar columnas desde localStorage o usar las por defecto
  const [columns, setColumns] = useState<ColumnConfig[]>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('trades-table-columns');
      if (stored) {
        try {
          const parsedColumns = JSON.parse(stored);
          // Validar que los datos cargados sean válidos
          if (Array.isArray(parsedColumns) && parsedColumns.length > 0) {
            // Check if the removed columns are still in the stored configuration
            const hasCostsColumn = parsedColumns.some((col: ColumnConfig) => col.key === 'total_costs');
            const hasEngineColumn = parsedColumns.some((col: ColumnConfig) => col.key === 'source_engine');
            const hasCopyColumn = parsedColumns.some((col: ColumnConfig) => col.key === 'copy');
            
            if (hasCostsColumn || hasEngineColumn || !hasCopyColumn) {
              // Auto-reset to remove the old columns and add copy column
              localStorage.removeItem('trades-table-columns');
              return defaultColumns;
            }
            return parsedColumns;
          }
        } catch (error) {
          console.warn('Error loading column configuration from localStorage:', error);
        }
      }
    }
    return defaultColumns;
  });
  
  const [draggedColumn, setDraggedColumn] = useState<number | null>(null);

  // Guardar columnas en localStorage cuando cambien
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('trades-table-columns', JSON.stringify(columns));
    }
  }, [columns]);

  const handleDragStart = (index: number) => {
    setDraggedColumn(index);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedColumn === null || draggedColumn === dropIndex) return;

    const newColumns = [...columns];
    const draggedItem = newColumns[draggedColumn];
    newColumns.splice(draggedColumn, 1);
    newColumns.splice(dropIndex, 0, draggedItem);
    
    setColumns(newColumns);
    setDraggedColumn(null);
  };

  // Resetear columnas a la configuración por defecto
  const handleResetColumns = () => {
    setColumns(defaultColumns);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('trades-table-columns');
    }
  };

  const copyTradeToClipboard = async (trade: Trade) => {
    try {
      const entryTime = new Date(trade.timestamp_entry);
      const exitTime = trade.timestamp_exit ? new Date(trade.timestamp_exit) : null;
      const isOpen = !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0;
      
      // Formatear toda la información del trade
      const tradeInfo = [
        `ID: ${trade.id}`,
        `Opened: ${entryTime.toLocaleDateString()} ${entryTime.toLocaleTimeString()}`,
        `Closed: ${isOpen ? 'OPEN' : `${exitTime!.toLocaleDateString()} ${exitTime!.toLocaleTimeString()}`}`,
        `Symbol: ${trade.symbol}`,
        `Direction: ${trade.direction?.toUpperCase() || 'N/A'}`,
        `Strategy: ${trade.strategy}`,
        `Engine: ${trade.source_engine}`,
        `Entry Price: $${trade.entry_price.toFixed(6)}`,
        `Exit Price: ${isOpen ? '-' : `$${trade.exit_price.toFixed(6)}`}`,
        `Size: ${trade.size.toFixed(8)}`,
        `Investment: $${trade.investment_amount?.toFixed(2) || '0.00'}`,
        `P&L: ${isOpen ? 'OPEN' : `${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(6)}`}`,
        `P&L %: ${isOpen ? '-' : `${trade.pnl >= 0 ? '+' : ''}${trade.pnl_percentage.toFixed(2)}%`}`,
        `Duration: ${trade.duration_formatted}`,
        `Confidence: ${trade.confidence > 0 ? `${trade.confidence.toFixed(1)}%` : 'N/A'}`,
        `Volatility: ${trade.volatility > 0 ? trade.volatility.toFixed(2) : 'N/A'}`,
        `Costs: $${trade.total_costs?.toFixed(6) || '0.00'}`,
        `Fees: $${(trade.entry_fees + trade.exit_fees).toFixed(6)}`,
        `Slippage: $${trade.slippage_cost?.toFixed(6) || '0.00'}`,
        `Spread: $${trade.spread_cost?.toFixed(6) || '0.00'}`,
        `Cost Impact: ${trade.cost_impact_pct > 0 ? `${trade.cost_impact_pct.toFixed(2)}%` : 'N/A'}`,
        `Requested Entry: $${trade.requested_entry_price.toFixed(6)}`,
        `Requested Exit: $${trade.requested_exit_price.toFixed(6)}`,
      ].join('\n');
      
      await navigator.clipboard.writeText(tradeInfo);
      
      // Mostrar notificación de éxito
      import('react-toastify').then(toast => {
        toast.toast.success(`✅ Trade #${trade.id} copied to clipboard!`, {
          toastId: `trade-${trade.id}-copied`,
          autoClose: 2000
        });
      });
    } catch (error) {
      console.error('Error copying trade:', error);
      import('react-toastify').then(toast => {
        toast.toast.error('❌ Failed to copy trade', {
          toastId: 'copy-trade-error'
        });
      });
    }
  };

  const renderCellContent = (trade: Trade, column: ColumnConfig) => {
    const entryTime = new Date(trade.timestamp_entry);
    const isOpen = !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0;
    let exitTime;
    
    if (isOpen) {
      exitTime = null;
    } else {
      exitTime = new Date(trade.timestamp_exit);
    }

    switch (column.key) {
      case 'id':
        return <span className="font-mono text-gray-500">#{trade.id}</span>;
      
      case 'custom_opened':
        return (
          <div>
            <div className="font-mono text-white">{entryTime.toLocaleDateString()}</div>
            <div className="text-xs text-gray-400">{entryTime.toLocaleTimeString()}</div>
          </div>
        );
      
      case 'custom_closed':
        return isOpen ? (
          <div className="text-cyan-400 font-mono">OPEN</div>
        ) : (
          <div>
            <div className="font-mono text-white">{exitTime!.toLocaleDateString()}</div>
            <div className="text-xs text-gray-400">{exitTime!.toLocaleTimeString()}</div>
          </div>
        );
      
      case 'symbol':
        return (
          <div className="flex flex-col">
            <span className="font-mono text-cyan-400">{trade.symbol}</span>
            <span className={`text-xs font-mono ${
              trade.direction === 'long' ? 'text-green-400' : 'text-red-400'
            }`}>
              {trade.direction === 'long' ? 'LONG' : 'SHORT'}
            </span>
          </div>
        );
      
      case 'strategy':
        return (
          <div className="flex flex-col">
            <span className="font-mono text-purple-400 text-xs">{trade.strategy}</span>
            <span className="text-xs text-gray-500 font-mono">{trade.source_engine}</span>
          </div>
        );
      
      case 'source_engine':
        return (
          <span className="font-mono text-gray-400 text-xs">{trade.source_engine}</span>
        );
      
      case 'entry_price':
        return (
          <span className="font-mono text-gray-400">${trade.entry_price.toFixed(2)}</span>
        );
      
      case 'exit_price':
        return isOpen ? (
          <span className="text-cyan-400">-</span>
        ) : (
          <span className="font-mono text-gray-400">${trade.exit_price.toFixed(2)}</span>
        );
      
      case 'size':
        return <span className="font-mono text-gray-400">{trade.size.toFixed(6)}</span>;
      
      case 'investment_amount':
        return <span className="font-mono text-blue-400">${trade.investment_amount?.toFixed(2) || '0.00'}</span>;
      
      case 'pnl':
        return isOpen ? (
          <span className="text-cyan-400">OPEN</span>
        ) : (
          <span className={trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
            {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
          </span>
        );
      
      case 'pnl_percentage':
        return isOpen ? (
          '-'
        ) : (
          <div className="flex flex-col">
            <span className={trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
              {trade.pnl >= 0 ? '+' : ''}{trade.pnl_percentage.toFixed(1)}%
            </span>
            {trade.total_costs > 0 && (
              <span className="text-xs text-orange-400">
                -{trade.cost_impact_pct.toFixed(2)}%
              </span>
            )}
          </div>
        );
      
      case 'total_costs':
        return !isOpen && trade.total_costs > 0 ? (
          <div className="flex flex-col">
            <span className="text-xs text-orange-400 font-mono">${trade.total_costs.toFixed(4)}</span>
            <div className="text-xs text-gray-500">
              <div>fees: ${trade.entry_fees + trade.exit_fees}</div>
              <div>slip: ${trade.slippage_cost.toFixed(4)}</div>
              <div>spread: ${trade.spread_cost.toFixed(4)}</div>
            </div>
          </div>
        ) : null;
      
      case 'custom_duration':
        return (
          <div className="flex flex-col">
            <span className="font-mono text-gray-400 text-xs">{trade.duration_formatted}</span>
            {trade.confidence > 0 && (
              <span className="text-xs text-blue-400 font-mono">
                {trade.confidence.toFixed(1)}%
              </span>
            )}
          </div>
        );
      
      case 'copy':
        return (
          <button
            onClick={() => copyTradeToClipboard(trade)}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors group"
            title="Copy trade details"
          >
            <Copy className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors" />
          </button>
        );
      
      default:
        return null;
    }
  };
  return (
    <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm mb-8">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-cyan-400">All Trades</h2>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-400">
             {trades.length} of {allTrades.length} trades
          </div>
          <div className="flex gap-2">
            <button
              onClick={onShowMoreTrades}
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
              onClick={onShowAllTrades}
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
              onClick={onCopyAllTrades}
              className="px-3 py-1 bg-cyan-600/20 border border-cyan-500 hover:bg-cyan-600/40 rounded flex items-center gap-2 text-cyan-400 hover:text-cyan-300 transition-all text-sm"
            >
              <Copy className="w-4 h-4" />
              Copy All
            </button>
            <button
              onClick={onDownloadTradesCSV}
              className="px-3 py-1 bg-purple-600/20 border border-purple-500 hover:bg-purple-600/40 rounded flex items-center gap-2 text-purple-400 hover:text-purple-300 transition-all text-sm"
            >
              <Download className="w-4 h-4" />
               CSV
            </button>
            <button
              onClick={handleResetColumns}
              className="px-3 py-1 bg-gray-600/20 border border-gray-500 hover:bg-gray-600/40 rounded flex items-center gap-2 text-gray-400 hover:text-gray-300 transition-all text-sm"
              title="Reset columns to default order"
            >
              <RotateCcw className="w-4 h-4" />
              Reset Columns
            </button>
            <button
              onClick={onDeleteAllTrades}
              disabled={isDeletingAllTrades || allTrades.length === 0}
              className={`px-3 py-1 border rounded flex items-center gap-2 text-sm font-mono transition-all ${
                isDeletingAllTrades || allTrades.length === 0
                  ? 'bg-red-900/20 border-red-800 text-red-800 cursor-not-allowed'
                  : 'bg-red-600/20 border-red-500 hover:bg-red-600/40 text-red-400 hover:text-red-300'
              }`}
              title={allTrades.length === 0 ? 'No trades to delete' : 'Delete all trades'}
            >
              <Trash2 className={`w-4 h-4 ${isDeletingAllTrades ? 'animate-pulse' : ''}`} />
              {isDeletingAllTrades ? 'Clearing…' : 'Delete All'}
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
                  {columns.map((column, index) => (
                    <th
                      key={column.key}
                      draggable
                      onDragStart={() => handleDragStart(index)}
                      onDragOver={handleDragOver}
                      onDrop={(e) => handleDrop(e, index)}
                      className={`py-3 px-4 text-gray-400 font-mono cursor-move hover:bg-gray-800/50 transition-colors ${
                        column.align === 'right' ? 'text-right' : 
                        column.align === 'center' ? 'text-center' : 'text-left'
                      }`}
                      style={{ width: column.width || 'auto' }}
                    >
                      <div className="flex items-center gap-2">
                        <GripVertical className="w-3 h-3 text-gray-600" />
                        {column.label}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((trade: Trade) => {
                  const isOpen = !trade.timestamp_exit || trade.timestamp_exit === '' || trade.exit_price === 0;

                  return (
                    <tr key={trade.id} className={`border-b border-gray-800 hover:bg-gray-900/50 transition-all ${
                      isOpen ? 'border-l-4 border-l-cyan-500' : 
                      trade.pnl >= 0 ? 'border-l-4 border-l-green-500' : 'border-l-4 border-l-red-500'
                    }`}>
                      {columns.map((column) => (
                        <td
                          key={column.key}
                          className={`py-3 px-4 ${
                            column.align === 'right' ? 'text-right' : 
                            column.align === 'center' ? 'text-center' : 'text-left'
                          }`}
                        >
                          {renderCellContent(trade, column)}
                        </td>
                      ))}
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
                ? `${((allTrades.filter((t: Trade) => t.pnl > 0).length / allTrades.length) * 100).toFixed(1)}%`
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
              ${allTrades.length > 0 ? Math.max(...allTrades.map((t: Trade) => t.pnl)).toFixed(2) : '0.00'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-1">Worst Trade</div>
            <div className="text-red-400 font-mono font-bold">
              ${allTrades.length > 0 ? Math.min(...allTrades.map((t: Trade) => t.pnl)).toFixed(2) : '0.00'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-1">Total Costs</div>
            <div className="text-orange-400 font-mono font-bold">
              ${allTrades.length > 0 ? allTrades.reduce((sum: number, t: Trade) => sum + (t.total_costs || 0), 0).toFixed(4) : '0.0000'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradesTable;