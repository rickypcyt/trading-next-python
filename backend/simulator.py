import random
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Trade, EquityCurve, Metric, Alert
from signal_interface import SimulationSignalEmitter
from execution_engine import TradeDirection
import asyncio

class TradingSimulator:
    def __init__(self, db: Session):
        self.db = db
        self.current_capital = 100.0  # Capital inicial de $100
        self.max_capital = 100.0
        self.current_drawdown = 0.0
        self.trades = []
        self.equity_history = []
        
        # Signal emitter para Portfolio Manager
        self.signal_emitter = SimulationSignalEmitter(db)
        self.signal_emitter.register_engine()
        
    
    
    def calculate_metrics(self):
        """Calcula métricas de rendimiento"""
        trades = self.db.query(Trade).all()
        
        if not trades:
            return None
        
        # Win Rate
        winning_trades = [t for t in trades if t.pnl > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        # Total PnL
        total_pnl = sum(t.pnl for t in trades)
        
        # Sharpe Ratio (simplificado)
        if len(trades) > 1:
            returns = [t.pnl for t in trades]
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            sharpe = avg_return / (math.sqrt(variance) + 0.0001)  # Evitar división por cero
        else:
            sharpe = 0
        
        # Max Drawdown
        self.current_drawdown = max(0, (self.max_capital - self.current_capital) / self.max_capital * 100)
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        profit_factor = gross_profit / (gross_loss + 0.0001)  # Evitar división por cero
        
        return Metric(
            timestamp=datetime.now().isoformat(),
            win_rate=round(win_rate, 4),
            sharpe=round(sharpe, 4),
            max_drawdown=round(self.current_drawdown, 2),
            profit_factor=round(profit_factor, 2)
        )
    
    def check_alerts(self, trade: Trade):
        """Verifica condiciones para alertas"""
        alerts = []
        
        # Alerta de pérdida grande (más de 2% del capital = $2)
        if trade.pnl < -self.current_capital * 0.02:  # Pérdida > $2
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="LOSS_WARNING",
                message=f"Large loss detected: ${trade.pnl:.2f} on {trade.symbol} ({(trade.pnl/self.current_capital*100):.1f}%)"
            ))
        
        # Alerta de drawdown (más de 10% del capital = $10)
        if self.current_drawdown > 10:  # Drawdown > $10
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="DRAWDOWN_ALERT",
                message=f"Max drawdown exceeded: {self.current_drawdown:.2f}% (${self.current_capital * self.current_drawdown/100:.2f})"
            ))
        
        # Alerta de volatilidad
        price_change = abs(trade.exit_price - trade.entry_price) / trade.entry_price
        if price_change > 0.03:  # Cambio de precio > 3%
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="VOLATILITY_ALERT",
                message=f"High volatility on {trade.symbol}: {price_change*100:.2f}%"
            ))
        
        # Alerta de ganancia grande (más de 5% del capital = $5)
        if trade.pnl > self.current_capital * 0.05:  # Ganancia > $5
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="PROFIT_ALERT",
                message=f"Large profit: ${trade.pnl:.2f} on {trade.symbol} ({(trade.pnl/self.current_capital*100):.1f}%)"
            ))
        
        return alerts
    
    def update_equity(self):
        """Actualiza la curva de capital"""
        equity = EquityCurve(
            timestamp=datetime.now().isoformat(),
            capital=round(self.current_capital, 2)
        )
        return equity
    
    

