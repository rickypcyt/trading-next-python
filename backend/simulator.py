import random
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Trade, EquityCurve, Metric, Alert
import asyncio

class TradingSimulator:
    def __init__(self, db: Session):
        self.db = db
        self.current_capital = 100.0  # Capital inicial de $100
        self.max_capital = 100.0
        self.current_drawdown = 0.0
        self.trades = []
        self.equity_history = []
        
    def generate_simulated_trade(self):
        """Genera un trade simulado realista"""
        symbols = ['BTC/USD', 'ETH/USD', 'SPY', 'QQQ', 'AAPL']
        strategies = ['MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'MACD_Signal']
        
        symbol = random.choice(symbols)
        strategy = random.choice(strategies)
        
        # Precios base según símbolo
        base_prices = {
            'BTC/USD': 45000,
            'ETH/USD': 3000,
            'SPY': 450,
            'QQQ': 380,
            'AAPL': 180
        }
        
        base_price = base_prices[symbol]
        
        # Generar precios con volatilidad
        volatility = random.uniform(0.01, 0.05)  # 1-5% de volatilidad
        entry_price = base_price * (1 + random.uniform(-volatility, volatility))
        
        # Tamaño de posición (1-5% del capital con $100 base = $1-$5)
        position_size = self.current_capital * random.uniform(0.01, 0.05)
        size = position_size / entry_price
        
        # Determinar si es ganancia o pérdida (60% probabilidad de ganancia)
        is_profit = random.random() < 0.6
        
        if is_profit:
            profit_factor = random.uniform(0.5, 3.0)  # 0.5% a 3% de ganancia
            pnl = position_size * profit_factor / 100
            exit_price = entry_price * (1 + profit_factor / 100)
        else:
            loss_factor = random.uniform(0.3, 2.0)  # 0.3% a 2% de pérdida
            pnl = -position_size * loss_factor / 100
            exit_price = entry_price * (1 - loss_factor / 100)
        
        # Timestamps
        now = datetime.now()
        entry_time = now - timedelta(minutes=random.randint(5, 60))
        exit_time = now
        
        trade = Trade(
            timestamp_entry=entry_time.isoformat(),
            timestamp_exit=exit_time.isoformat(),
            symbol=symbol,
            strategy=strategy,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            size=round(size, 6),
            pnl=round(pnl, 2)
        )
        
        return trade
    
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
    
    async def run_simulation_cycle(self):
        """Ejecuta un ciclo completo de simulación"""
        try:
            # 1. Generar y guardar trade
            trade = self.generate_simulated_trade()
            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)
            
            # 2. Actualizar capital
            self.current_capital += trade.pnl
            self.max_capital = max(self.max_capital, self.current_capital)
            
            # 3. Actualizar equity curve
            equity = self.update_equity()
            self.db.merge(equity)
            self.db.commit()
            
            # 4. Calcular métricas
            metrics = self.calculate_metrics()
            if metrics:
                self.db.add(metrics)
                self.db.commit()
                self.db.refresh(metrics)
            
            # 5. Verificar alertas
            alerts = self.check_alerts(trade)
            for alert in alerts:
                self.db.add(alert)
                self.db.commit()
                self.db.refresh(alert)
            
            # Retornar diccionario con resultados
            return {
                "trade": trade,
                "equity": equity,
                "metrics": metrics,
                "alerts": alerts
            }
            
        except Exception as e:
            print(f"Error in simulation cycle: {e}")
            self.db.rollback()
            return None

# Función para ejecutar simulación periódica
async def run_periodic_simulation(db_factory, notify_clients):
    """Ejecuta simulación cada 5 segundos"""
    while True:
        try:
            db = next(db_factory())
            simulator = TradingSimulator(db)
            result = await simulator.run_simulation_cycle()
            
            if result:
                # Notificar via WebSocket con estructura correcta
                await notify_clients({
                    "type": "simulation_complete",
                    "message": "New simulation cycle completed",
                    "data": {
                        "trade_id": result["trade"].id,
                        "symbol": result["trade"].symbol,
                        "pnl": result["trade"].pnl,
                        "capital": result["equity"].capital,
                        "alerts_count": len(result["alerts"])
                    }
                })
            
            db.close()
            
        except Exception as e:
            print(f"Error in periodic simulation: {e}")
        
        await asyncio.sleep(5)  # Esperar 5 segundos para el siguiente ciclo
