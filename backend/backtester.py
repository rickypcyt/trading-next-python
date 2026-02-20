import asyncio
import random
import requests
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import uuid

# ==================== IMPORTS REALES DE TU PROYECTO ====================
from advanced_strategies import (
    AdvancedStrategyEngine,
    MarketMakingOrder,
    OrderSide,
    RiskLevel
)
# from portfolio_manager import PortfolioManager, TradeIntent as PM_TradeIntent  # si quieres usarlo


# ==================== TRADE INTENT (compatible con tu sistema) ====================
class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class TradeIntent:
    id: str
    source_engine: str = "market_making"
    symbol: str = "BTCUSDT"
    direction: TradeDirection = TradeDirection.LONG
    entry_price: float = 0.0
    size: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    order_type: str = "limit"          # "limit" o "market"
    strategy: str = "default"
    confidence: float = 0.75


# ==================== BACKTESTER FINAL 2026 ====================
class Backtester:
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        days_back: int = 180,
        initial_capital: float = 10000.0,
        risk_per_trade: float = 0.015,
        slippage_bps: float = 8.0,
        maker_fee_bps: float = 2.0,
        taker_fee_bps: float = 4.0,
        portfolio_manager=None
    ):
        self.symbol = symbol
        self.interval = interval
        self.days_back = days_back
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.slippage_bps = slippage_bps / 10000
        self.maker_fee = maker_fee_bps / 10000
        self.taker_fee = taker_fee_bps / 10000
        self.portfolio_manager = portfolio_manager

        self.cash = initial_capital
        self.unrealized_pnl = 0.0
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.open_positions: List[Dict] = []

        # Anualización correcta por timeframe
        self.candles_per_year = {
            '1m': 525600, '3m': 175200, '5m': 105120, '15m': 35040,
            '30m': 17520, '1h': 8760, '2h': 4380, '4h': 2190, '6h': 1460,
            '8h': 1095, '12h': 730, '1d': 365, '3d': 121.67, '1w': 52, '1M': 12
        }

        # Inicialización de tu motor REAL
        self.engine = AdvancedStrategyEngine(
            symbol=self.symbol,
            current_price=65000.0,          # precio inicial aproximado
            volatility=0.025,
            risk_level=RiskLevel.MODERATE,
            capital=self.initial_capital
        )

    def fetch_klines(self) -> pd.DataFrame:
        print(f"📥 Descargando {self.days_back} días de {self.interval} {self.symbol}...")
        data = []
        end_ts = int(datetime.now().timestamp() * 1000)
        start_ts = end_ts - self.days_back * 86400000

        while start_ts < end_ts:
            params = {
                "symbol": self.symbol,
                "interval": self.interval,
                "limit": 1000,
                "startTime": start_ts,
                "endTime": end_ts
            }
            r = requests.get("https://api.binance.com/api/v3/klines", params=params)
            klines = r.json()
            if not klines:
                break
            data.extend(klines)
            start_ts = klines[-1][0] + 1
            if len(klines) < 1000:
                break

        df = pd.DataFrame(data, columns=['ts','o','h','l','c','v','ct','qv','n','tb','tq','ig'])
        for col in ['o','h','l','c','v']:
            df[col] = df[col].astype(float)
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.rename(columns={'ts':'timestamp','o':'open','h':'high','l':'low','c':'close','v':'volume'})
        print(f"✅ {len(df)} velas cargadas")
        return df

    async def run(self):
        df = self.fetch_klines()

        for _, row in df.iterrows():
            close = row['close']
            high = row['high']
            low = row['low']

            # Actualizar tu motor
            self.engine.update_price(close)

            # Obtener señales reales de tu engine
            raw_signals = self.engine.get_all_strategy_signals()

            # === ADAPTADOR CORRECTO MarketMakingOrder → TradeIntent ===
            intents: List[TradeIntent] = []
            for sig in raw_signals:
                if not isinstance(sig, MarketMakingOrder):
                    continue

                intent = TradeIntent(
                    id=str(uuid.uuid4()),
                    source_engine="advanced_strategy",
                    symbol=self.symbol,
                    direction=TradeDirection.LONG if sig.side == OrderSide.BUY else TradeDirection.SHORT,
                    entry_price=sig.price,
                    size=sig.size,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.target_profit,
                    order_type=sig.order_type,                    # ya viene 'limit' o 'market'
                    strategy=sig.strategy.value if hasattr(sig.strategy, 'value') else str(sig.strategy),
                    confidence=sig.confidence if hasattr(sig, 'confidence') else 0.75
                )
                intents.append(intent)

            # Procesar señales
            for intent in intents:
                self._close_opposite_positions(intent, close)

            for intent in intents:
                await self._try_open(intent, row)

            # Actualizar posiciones (stops, take-profit, mtm)
            self._update_positions(high, low, close)

            # Registrar equity
            equity = self.cash + self.unrealized_pnl
            self.equity_curve.append({'timestamp': row['timestamp'], 'equity': equity})

        self._generate_report()
        self._plot_results()
        self._export_trades_csv()

    def _close_opposite_positions(self, intent: TradeIntent, price: float):
        to_remove = []
        for pos in self.open_positions:
            if intent.direction != pos['direction']:
                self._close_position(pos, price, "opposite_signal")
                to_remove.append(pos)
        for p in to_remove:
            self.open_positions.remove(p)

    async def _try_open(self, intent: TradeIntent, candle: pd.Series):
        if intent.size <= 0:
            sl_dist = abs(candle['close'] - intent.stop_loss) / candle['close'] if intent.stop_loss else 0.025
            intent.size = (self.cash * self.risk_per_trade) / max(sl_dist, 0.0005)

        fill_price = self._simulate_fill(intent, candle)
        if fill_price is None:
            return

        fee_rate = self.maker_fee if intent.order_type == "limit" else self.taker_fee
        entry_value = fill_price * intent.size
        entry_fee = entry_value * fee_rate
        total_cost = entry_value + entry_fee

        if total_cost > self.cash:
            return

        self.cash -= total_cost

        pos = {
            'entry_price': fill_price,
            'size': intent.size,
            'direction': intent.direction,
            'stop_loss': intent.stop_loss,
            'take_profit': intent.take_profit,
            'entry_time': candle['timestamp'],
            'strategy': intent.strategy,
            'order_type': intent.order_type,
            'entry_fee': entry_fee
        }
        self.open_positions.append(pos)
        print(f"🟢 OPEN {intent.direction.value} @ {fill_price:.2f} size={intent.size:.4f} fee={entry_fee:.2f}")

    def _simulate_fill(self, intent: TradeIntent, candle) -> Optional[float]:
        base = candle['close']
        if intent.order_type == "market":
            adj = self.slippage_bps * random.uniform(0.6, 1.8)
            return base * (1 + adj) if intent.direction == TradeDirection.LONG else base * (1 - adj)
        else:  # limit
            desired = intent.entry_price if intent.entry_price > 0 else base * (0.997 if intent.direction == TradeDirection.LONG else 1.003)
            if (intent.direction == TradeDirection.LONG and candle['low'] <= desired) or \
               (intent.direction == TradeDirection.SHORT and candle['high'] >= desired):
                return desired * random.uniform(0.9992, 1.0012)
        return None

    def _update_positions(self, high: float, low: float, close: float):
        to_close = []
        for pos in self.open_positions[:]:
            if pos['direction'] == TradeDirection.LONG:
                if pos['stop_loss'] and low <= pos['stop_loss']:
                    to_close.append((pos, pos['stop_loss'], "stop_loss"))
                elif pos['take_profit'] and high >= pos['take_profit']:
                    to_close.append((pos, pos['take_profit'], "take_profit"))
            else:
                if pos['stop_loss'] and high >= pos['stop_loss']:
                    to_close.append((pos, pos['stop_loss'], "stop_loss"))
                elif pos['take_profit'] and low <= pos['take_profit']:
                    to_close.append((pos, pos['take_profit'], "take_profit"))

        for pos, ex_price, reason in to_close:
            self._close_position(pos, ex_price, reason)

        # Recalcular unrealized PnL con posiciones restantes
        self.unrealized_pnl = 0.0
        for pos in self.open_positions:
            if pos['direction'] == TradeDirection.LONG:
                self.unrealized_pnl += (close - pos['entry_price']) * pos['size']
            else:
                self.unrealized_pnl += (pos['entry_price'] - close) * pos['size']

    def _close_position(self, pos: Dict, exit_price: float, reason: str):
        size = pos['size']
        exit_value = exit_price * size
        fee_rate = self.maker_fee if pos['order_type'] == "limit" else self.taker_fee
        exit_fee = exit_value * fee_rate

        gross_pnl = (exit_price - pos['entry_price']) * size if pos['direction'] == TradeDirection.LONG else \
                    (pos['entry_price'] - exit_price) * size

        net_pnl = gross_pnl - exit_fee

        self.cash += exit_value - exit_fee
        self.unrealized_pnl -= gross_pnl

        trade = {
            'entry_time': pos['entry_time'],
            'exit_time': datetime.now(),
            'direction': pos['direction'].value,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'size': size,
            'entry_fee': pos.get('entry_fee', 0.0),
            'exit_fee': exit_fee,
            'total_fees': pos.get('entry_fee', 0.0) + exit_fee,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'reason': reason,
            'strategy': pos['strategy']
        }
        self.trades.append(trade)

        print(f"🔴 CLOSE {pos['direction'].value} | gross {gross_pnl:+.2f} | net {net_pnl:+.2f} | fees {trade['total_fees']:.2f} | {reason}")
        self.open_positions.remove(pos)

    def _generate_report(self):
        eq = pd.DataFrame(self.equity_curve).set_index('timestamp')
        final = eq['equity'].iloc[-1]
        total_return = (final / self.initial_capital - 1) * 100

        if self.trades:
            tdf = pd.DataFrame(self.trades)
            wins = tdf[tdf['net_pnl'] > 0]
            losses = tdf[tdf['net_pnl'] < 0]
            win_rate = len(wins) / len(tdf) * 100 if len(tdf) else 0
            pf = wins['net_pnl'].sum() / abs(losses['net_pnl'].sum()) if len(losses) else float('inf')
            expectancy = (win_rate/100 * wins['net_pnl'].mean() if len(wins) else 0) + \
                         ((1 - win_rate/100) * losses['net_pnl'].mean() if len(losses) else 0)
            total_fees = tdf['total_fees'].sum()
        else:
            win_rate = pf = expectancy = total_fees = 0

        rets = eq['equity'].pct_change().dropna()
        ann_factor = np.sqrt(self.candles_per_year.get(self.interval, 8760))
        sharpe = rets.mean() / rets.std() * ann_factor if rets.std() != 0 else 0
        sortino = rets.mean() / rets[rets < 0].std() * ann_factor if rets[rets < 0].std() != 0 else 0

        dd = (eq['equity'].cummax() - eq['equity']) / eq['equity'].cummax()
        max_dd = dd.max() * 100

        print("\n" + "═" * 90)
        print(" BACKTEST FINAL – COMPLETO – FEBRERO 2026 ".center(90))
        print("═" * 90)
        print(f" {self.symbol} {self.interval} — {self.days_back} días")
        print(f" Capital: ${self.initial_capital:,.0f} → ${final:,.0f}   ({total_return:+.2f}%)")
        print(f" Max DD: {max_dd:.2f}%   Sharpe: {sharpe:.2f}   Sortino: {sortino:.2f}")
        print(f" Trades: {len(self.trades)}   WinRate: {win_rate:.1f}%   PF: {pf:.2f}")
        print(f" Expectancy: ${expectancy:.2f}   Total fees: ${total_fees:.2f}")
        print("═" * 90)

    def _plot_results(self):
        eq = pd.DataFrame(self.equity_curve).set_index('timestamp')
        fig, ax1 = plt.subplots(figsize=(15, 7))
        ax1.plot(eq['equity'], color='royalblue', lw=1.6, label='Equity')
        ax1.set_ylabel('Capital ($)', color='royalblue')
        ax1.grid(alpha=0.3)

        ax2 = ax1.twinx()
        dd = (eq['equity'].cummax() - eq['equity']) / eq['equity'].cummax() * 100
        ax2.fill_between(eq.index, dd, 0, color='salmon', alpha=0.4)
        ax2.set_ylabel('Drawdown (%)', color='darkred')

        plt.title(f"Backtest Final {self.symbol} — {self.interval}")
        plt.tight_layout()
        plt.savefig("backtest_final.png", dpi=350, bbox_inches='tight')
        plt.show()

    def _export_trades_csv(self):
        if self.trades:
            pd.DataFrame(self.trades).to_csv(f"trades_{self.symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", index=False)
            print(f"💾 Trades exportados a CSV ({len(self.trades)} operaciones)")

# ==================== EJECUCIÓN ====================
if __name__ == "__main__":
    bt = Backtester(
        symbol="BTCUSDT",
        interval="1h",          # prueba también "15m", "4h", "1d"
        days_back=90,
        initial_capital=15000,
        risk_per_trade=0.02
    )
    asyncio.run(bt.run())