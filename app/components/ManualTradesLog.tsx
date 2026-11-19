'use client'

import { API_BASE, WS_URL, apiUrl } from '@/lib/api';
import { useEffect, useState } from 'react'

import { DollarSign } from 'lucide-react'
import { format } from 'date-fns'

interface ManualTrade {
  id: number
  timestamp: string
  symbol: string
  action: 'BUY' | 'SELL'
  quantity: number
  price: number
  total_amount: number
  status: 'executed' | 'closed' | 'pending' | 'cancelled'
  notes: string
  exit_price?: number
  exit_timestamp?: string
  pnl?: number
  created_by: string
}

interface TradeStatus {
  symbol: string
  action: string
  entry_price: number
  quantity: number
  timestamp: string
  current_price?: number
  pnl?: number
  pnl_percentage?: number
  last_update?: string
}

interface ManualTradeAlert {
  type: 'manual_trade_alert'
  trade_id: number
  symbol: string
  action: string
  entry_price: number
  current_price: number
  pnl: number
  pnl_percentage: number
  alert_type: 'TAKE_PROFIT' | 'STOP_LOSS'
  message: string
  timestamp: string
}

export default function ManualTradesLog() {
  const [trades, setTrades] = useState<ManualTrade[]>([])
  const [tradesStatus, setTradesStatus] = useState<Record<number, TradeStatus>>({})
  const [alerts, setAlerts] = useState<ManualTradeAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    symbol: '',
    action: 'BUY' as 'BUY' | 'SELL',
    quantity: '',
    price: '',
    notes: ''
  })

  useEffect(() => {
    fetchManualTrades()
    fetchTradesStatus()
    
    // WebSocket para actualizaciones en tiempo real
    const ws = new WebSocket(WS_URL)
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'manual_trade_created' || 
          data.type === 'manual_trade_closed' || 
          data.type === 'manual_trade_deleted') {
        fetchManualTrades()
        fetchTradesStatus()
      } else if (data.type === 'manual_trade_alert') {
        setAlerts(prev => [data, ...prev].slice(0, 10)) // Mantener últimas 10 alertas
      }
    }
    
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [])

  const fetchTradesStatus = async () => {
    try {
      const response = await fetch(apiUrl('/manual-trades/status'))
      const data = await response.json()
      if (data.status === 'success') {
        const statusMap: Record<number, TradeStatus> = {}
        data.trades.forEach((trade: TradeStatus) => {
          // Extraer ID del timestamp o usar symbol como clave temporal
          const id = Object.keys(tradesStatus).find(key => {
            const status = tradesStatus[parseInt(key)]
            return status?.symbol === trade.symbol && status?.entry_price === trade.entry_price
          })
          if (id) {
            statusMap[parseInt(id)] = trade
          }
        })
        setTradesStatus(statusMap)
      }
    } catch (error) {
      console.error('Error fetching trades status:', error)
    }
  }

  const fetchManualTrades = async () => {
    try {
      const response = await fetch(apiUrl('/manual-trades'))
      const data = await response.json()
      setTrades(data)
    } catch (error) {
      console.error('Error fetching manual trades:', error)
    } finally {
      setLoading(false)
    }
  }

  const createManualTrade = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      const response = await fetch(apiUrl('/manual-trades'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: formData.symbol,
          action: formData.action,
          quantity: parseFloat(formData.quantity),
          price: parseFloat(formData.price),
          notes: formData.notes
        })
      })
      
      if (response.ok) {
        setShowForm(false)
        setFormData({
          symbol: '',
          action: 'BUY',
          quantity: '',
          price: '',
          notes: ''
        })
        fetchManualTrades()
        fetchTradesStatus()
      }
    } catch (error) {
      console.error('Error creating manual trade:', error)
    }
  }

  const closeTrade = async (tradeId: number, exitPrice: number) => {
    try {
      const response = await fetch(`${API_BASE}/manual-trades/${tradeId}/close`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          exit_price: exitPrice
        })
      })
      
      if (response.ok) {
        fetchManualTrades()
      }
    } catch (error) {
      console.error('Error closing trade:', error)
    }
  }

  const deleteTrade = async (tradeId: number) => {
    if (!confirm('Are you sure you want to delete this trade?')) return
    
    try {
      const response = await fetch(`${API_BASE}/manual-trades/${tradeId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        fetchManualTrades()
      }
    } catch (error) {
      console.error('Error deleting trade:', error)
    }
  }

  const calculateTotalPnL = () => {
    return trades
      .filter(t => t.pnl !== null && t.pnl !== undefined)
      .reduce((sum, t) => sum + (t.pnl || 0), 0)
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded mb-4"></div>
          <div className="space-y-2">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-950/50 border border-gray-800 rounded-lg p-6 backdrop-blur-sm">
      <div className="p-6 border-b border-gray-800">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-cyan-400 flex items-center gap-2">
              <DollarSign className="w-5 h-5" />
              My Manual Trades
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Personal log of trades independent from simulators
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm text-gray-400">Total P&L</p>
              <p className={`text-lg font-semibold font-mono ${
                calculateTotalPnL() >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                ${calculateTotalPnL().toFixed(2)}
              </p>
            </div>
            <button
              onClick={() => setShowForm(!showForm)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              {showForm ? 'Cancel' : 'New Trade'}
            </button>
          </div>
        </div>
      </div>

      {showForm && (
        <div className="p-6 bg-gray-900/50 border-b border-gray-800">
          <form onSubmit={createManualTrade} className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Symbol
              </label>
              <input
                type="text"
                value={formData.symbol}
                onChange={(e) => setFormData({...formData, symbol: e.target.value})}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-400"
                placeholder="BTCUSDT"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Action
              </label>
              <select
                value={formData.action}
                onChange={(e) => setFormData({...formData, action: e.target.value as 'BUY' | 'SELL'})}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Quantity
              </label>
              <input
                type="number"
                step="0.000001"
                value={formData.quantity}
                onChange={(e) => setFormData({...formData, quantity: e.target.value})}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-400"
                placeholder="0.001"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Price
              </label>
              <input
                type="number"
                step="0.01"
                value={formData.price}
                onChange={(e) => setFormData({...formData, price: e.target.value})}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-400"
                placeholder="50000"
                required
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Notes (optional)
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-white placeholder-gray-400"
                rows={2}
                placeholder="Trade reason, strategy, etc."
              />
            </div>
            <div className="col-span-2">
              <button
                type="submit"
                className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors"
              >
                Create Trade
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Alertas */}
      {alerts.length > 0 && (
        <div className="p-6 bg-gray-900/50 border-b border-gray-800">
          <h3 className="text-lg font-semibold text-cyan-400 mb-4">Trading Alerts</h3>
          <div className="space-y-2">
            {alerts.map((alert, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg border ${
                  alert.alert_type === 'TAKE_PROFIT' 
                    ? 'bg-green-900/30 border-green-800 text-green-400'
                    : 'bg-red-900/30 border-red-800 text-red-400'
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium">{alert.message}</span>
                  <span className="text-xs opacity-75">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Date
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Symbol
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Action
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Quantity
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Price
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Total
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Current Price
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Live P&L
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                P&L
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Notes
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-gray-900/30 divide-y divide-gray-800">
            {trades.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-6 py-12 text-center text-gray-400">
                  You have no manual trades registered
                </td>
              </tr>
            ) : (
              trades.map((trade) => (
                <tr key={trade.id} className="hover:bg-gray-800/50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    {format(new Date(trade.timestamp), 'dd/MM HH:mm')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                    {trade.symbol}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      trade.action === 'BUY' 
                        ? 'bg-green-900/50 text-green-400 border border-green-800' 
                        : 'bg-red-900/50 text-red-400 border border-red-800'
                    }`}>
                      {trade.action}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    {trade.quantity}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    ${trade.price}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    ${trade.total_amount.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    {tradesStatus[trade.id]?.current_price ? (
                      <span className="font-mono">
                        ${tradesStatus[trade.id]!.current_price!.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {tradesStatus[trade.id]?.pnl !== undefined ? (
                      <div className="flex flex-col">
                        <span className={`font-medium ${
                          tradesStatus[trade.id]!.pnl! >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          ${tradesStatus[trade.id]!.pnl!.toFixed(2)}
                        </span>
                        {tradesStatus[trade.id]!.pnl_percentage && (
                          <span className={`text-xs ${
                            tradesStatus[trade.id]!.pnl_percentage! >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {tradesStatus[trade.id]!.pnl_percentage! >= 0 ? '+' : ''}{tradesStatus[trade.id]!.pnl_percentage!.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      trade.status === 'executed' 
                        ? 'bg-blue-900/50 text-blue-400 border border-blue-800'
                        : trade.status === 'closed'
                        ? 'bg-gray-700/50 text-gray-400 border border-gray-600'
                        : 'bg-yellow-900/50 text-yellow-400 border border-yellow-800'
                    }`}>
                      {trade.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {trade.pnl !== null && trade.pnl !== undefined ? (
                      <span className={`font-medium ${
                        trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${trade.pnl.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400 max-w-xs truncate">
                    {trade.notes || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <div className="flex space-x-2">
                      {trade.status === 'executed' && (
                        <button
                          onClick={() => {
                            const exitPrice = prompt('Close price:', trade.price.toString())
                            if (exitPrice && !isNaN(parseFloat(exitPrice))) {
                              closeTrade(trade.id, parseFloat(exitPrice))
                            }
                          }}
                          className="text-cyan-400 hover:text-cyan-300"
                        >
                          Close
                        </button>
                      )}
                      <button
                        onClick={() => deleteTrade(trade.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
