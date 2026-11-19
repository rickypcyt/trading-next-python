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
  duration_ms?: number;
  entry_reason?: string;
  exit_reason?: string;
  status?: string;
}

export interface Engine {
  type: string;
  status: 'idle' | 'running' | 'error';
  last_activity: string | null;
  trades_generated: number;
  errors: number;
  metadata: Record<string, unknown>;
}

export interface Metric {
  id: number;
  timestamp: string;
  win_rate: number;
  sharpe: number;
  max_drawdown: number;
  profit_factor: number;
}

export interface Alert {
  id: number;
  timestamp: string;
  type: string;
  message: string;
}

export interface EquityPoint {
  timestamp: string;
  capital: number;
}

export interface TradingMode {
  name: string;
  risk_percentage: number;
  win_rate: number;
  reward_risk_ratio: number;
  max_consecutive_losses: number;
  trades_per_hour: number;
}

export type BinanceModeStatusMap = Record<string, 'running' | 'stopped'>;

export interface TradeEventPayload {
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
  side?: string;
  direction?: string;
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
