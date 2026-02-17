#!/usr/bin/env python3
"""
Modos de trading para Binance con diferentes niveles de riesgo
"""
from binance_simulator import BinanceDataSimulator
from database import get_db, Trade, EquityCurve, Metric, Alert
from datetime import datetime, timedelta
import random
import asyncio

class BinanceTradingMode:
    def __init__(self, name, risk_percentage, win_rate, reward_risk_ratio, max_consecutive_losses, trades_per_hour):
        self.name = name
        self.risk_percentage = risk_percentage  # % de capital en riesgo por trade
        self.win_rate = win_rate  # Probabilidad de ganar
        self.reward_risk_ratio = reward_risk_ratio  # 1:x ratio
        self.max_consecutive_losses = max_consecutive_losses
        self.trades_per_hour = trades_per_hour

# Definir los modos de trading
TRADING_MODES = {
    "conservative": BinanceTradingMode(
        name="Conservador",
        risk_percentage=0.01,  # 1% riesgo
        win_rate=0.70,  # 70% win rate
        reward_risk_ratio=1.5,  # 1:1.5
        max_consecutive_losses=5,
        trades_per_hour=2
    ),
    "hybrid": BinanceTradingMode(
        name="Híbrido",
        risk_percentage=0.025,  # 2.5% riesgo
        win_rate=0.60,  # 60% win rate
        reward_risk_ratio=2.0,  # 1:2
        max_consecutive_losses=4,
        trades_per_hour=4
    ),
    "aggressive": BinanceTradingMode(
        name="Agresivo",
        risk_percentage=0.05,  # 5% riesgo
        win_rate=0.45,  # 45% win rate
        reward_risk_ratio=3.0,  # 1:3
        max_consecutive_losses=3,
        trades_per_hour=8
    )
}

class BinanceModeSimulator(BinanceDataSimulator):
    def __init__(self, db, mode="conservative"):
        super().__init__(db)
        self.mode = TRADING_MODES[mode]
        self.consecutive_losses = 0
        self.daily_trades = 0
        self.daily_pnl = 0
        self.hourly_trades = 0
        self.last_trade_hour = datetime.now().hour
        
    def should_trade(self):
        """Verificar si se debe operar según el modo"""
        # Verificar pérdidas consecutivas
        if self.consecutive_losses >= self.mode.max_consecutive_losses:
            return False, f"Límite de {self.mode.max_consecutive_losses} pérdidas consecutivas alcanzado"
        
        # Verificar límite de trades por hora
        current_hour = datetime.now().hour
        if current_hour != self.last_trade_hour:
            self.hourly_trades = 0
            self.last_trade_hour = current_hour
            
        if self.hourly_trades >= self.mode.trades_per_hour:
            return False, f"Límite de {self.mode.trades_per_hour} trades por hora alcanzado"
        
        return True, "Todo OK para operar"
    
    def calculate_position_size(self):
        """Calcular tamaño de posición según el modo"""
        risk_amount = self.current_capital * self.mode.risk_percentage
        return risk_amount
    
    def generate_mode_trade(self):
        """Generar trade según el modo seleccionado"""
        can_trade, reason = self.should_trade()
        
        if not can_trade:
            print(f"🚫 [{self.mode.name}] No trading: {reason}")
            return None
        
        position_size = self.calculate_position_size()
        potential_loss = position_size * self.mode.risk_percentage
        potential_profit = potential_loss * self.mode.reward_risk_ratio
        
        # Obtener precio real de Binance PRIMERO
        market_data = self.get_real_price_data('BTCUSDT')
        
        if market_data:
            base_price = market_data['current_price']
            volatility = market_data.get('volatility', 0.02)  # 2% default
            
            # Simular movimiento de precio basado en volatilidad real
            price_movement = random.uniform(-volatility, volatility) * 0.5  # Mitad de la volatilidad real
            entry_price = base_price * (1 + price_movement)
            
            # Decidir resultado basado en tendencia REAL del mercado
            trend_factor = random.uniform(-1, 1)  # -1 (bearish) a 1 (bullish)
            
            # Ajustar probabilidad según tendencia y modo
            base_win_rate = self.mode.win_rate
            trend_adjustment = trend_factor * 0.1  # ±10% de ajuste
            adjusted_win_rate = max(0.1, min(0.9, base_win_rate + trend_adjustment))
            
            # Decidir si es trade ganador basado en análisis real
            is_winner = random.random() < adjusted_win_rate
            
            # Tiempo de holding según modo
            holding_minutes = {
                "conservative": random.randint(15, 30),  # 15-30 minutos
                "hybrid": random.randint(5, 15),          # 5-15 minutos
                "aggressive": random.randint(1, 5)         # 1-5 minutos
            }
            
            hold_time = holding_minutes.get(self.mode.name, 10)
            
            if is_winner:
                # Ganancia basada en volatilidad real y tiempo
                profit_factor = random.uniform(0.1, min(volatility * 100, 2.0))
                # Ajustar ganancia según tiempo de holding
                time_multiplier = 1 + (hold_time / 60)  # Más tiempo = más ganancia potencial
                adjusted_profit = profit_factor * time_multiplier
                
                pnl = position_size * adjusted_profit / 100
                exit_price = entry_price * (1 + adjusted_profit / 100)
                self.consecutive_losses = 0
                result = "WIN"
            else:
                # Pérdida basada en volatilidad real y tiempo
                loss_factor = random.uniform(0.1, min(volatility * 100, 1.5))
                # Ajustar pérdida según tiempo de holding
                time_multiplier = 1 + (hold_time / 120)  # Más tiempo = más pérdida potencial
                adjusted_loss = loss_factor * time_multiplier
                
                pnl = -position_size * adjusted_loss / 100
                exit_price = entry_price * (1 - adjusted_loss / 100)
                self.consecutive_losses += 1
                result = "LOSS"
        else:
            # Fallback a simulación si Binance falla
            base_price = 50000 + random.uniform(-5000, 5000)
            entry_price = base_price
            
            # Mantener lógica original como fallback
            is_winner = random.random() < self.mode.win_rate
            hold_time = 10  # Default 10 minutos
            
            if is_winner:
                pnl = potential_profit
                exit_price = entry_price + (pnl * 100)
                self.consecutive_losses = 0
                result = "WIN"
            else:
                pnl = -potential_loss
                exit_price = entry_price + (pnl * 100)
                self.consecutive_losses += 1
                result = "LOSS"
        
        # Actualizar contadores
        self.daily_trades += 1
        self.hourly_trades += 1
        self.daily_pnl += pnl
        
        # Timestamps realistas - COMPRA en pasado, VENTA ahora
        now = datetime.now()
        entry_time = now - timedelta(minutes=hold_time)
        exit_time = now
        
        # Calcular duración real
        duration_minutes = (exit_time - entry_time).total_seconds() / 60
        
        # Crear trade
        trade = Trade(
            timestamp_entry=entry_time.isoformat(),
            timestamp_exit=exit_time.isoformat(),
            symbol="BTC/USDT",
            strategy=f"Binance {self.mode.name}",
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            size=position_size,
            pnl=pnl,
            source_engine="binance_mode",
            source_mode=self.mode.name.lower(),
            direction="LONG",
            status="executed",
            confidence=self.mode.win_rate,
            volatility=volatility * 100 if 'volatility' in locals() else 2.0,
            duration_ms=int(duration_minutes * 60 * 1000)
        )
        
        print(f"📊 [{self.mode.name}] Trade #{self.daily_trades}: {result} | PnL: ${pnl:+.2f} | Entry: ${entry_price:.2f} | Exit: ${exit_price:.2f} | Duration: {duration_minutes:.0f}m | Trend: {trend_factor:+.2f}")
        
        return trade

async def run_binance_mode_simulation(get_db_func, notification_callback, mode="conservative"):
    """Ejecutar simulación Binance con modo específico"""
    print(f"🎯 Iniciando simulación Binance en modo {TRADING_MODES[mode].name}...")
    
    while True:
        db = next(get_db_func())
        simulator = BinanceModeSimulator(db, mode)
        
        try:
            # Generar trade según modo
            trade = simulator.generate_mode_trade()
            
            if trade:
                db.add(trade)
                db.commit()
                db.refresh(trade)
                
                # Actualizar capital
                simulator.current_capital += trade.pnl
                simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
                
                # Actualizar equity curve con el capital real
                equity = EquityCurve(
                    timestamp=datetime.now().isoformat(),
                    capital=round(simulator.current_capital, 2)
                )
                db.merge(equity)
                db.commit()
                
                # Enviar notificación con equity actualizado
                await notification_callback({
                    "type": "equity_updated",
                    "message": f"Capital updated: ${simulator.current_capital:.2f}",
                    "data": {
                        "timestamp": datetime.now().isoformat(),
                        "capital": round(simulator.current_capital, 2),
                        "trade_pnl": trade.pnl,
                        "mode": simulator.mode.name,
                        "daily_trades": simulator.daily_trades
                    }
                })
                
                # Calcular métricas cada 10 trades
                if simulator.daily_trades % 10 == 0:
                    metrics = simulator.calculate_metrics()
                    if metrics:
                        db.add(metrics)
                        db.commit()
                
                # Generar alertas según modo
                alerts = []
                
                # Alerta de pérdidas consecutivas
                if simulator.consecutive_losses >= simulator.mode.max_consecutive_losses:
                    alerts.append(Alert(
                        timestamp=datetime.now().isoformat(),
                        type="risk_warning",
                        message=f"[{simulator.mode.name}] {simulator.consecutive_losses} pérdidas consecutivas"
                    ))
                
                # Alerta de buen rendimiento
                if simulator.daily_pnl > (simulator.current_capital * 0.05):  # 5% diario
                    alerts.append(Alert(
                        timestamp=datetime.now().isoformat(),
                        type="performance_alert",
                        message=f"[{simulator.mode.name}] Excelente día: +{simulator.daily_pnl:.2f}"
                    ))
                
                for alert in alerts:
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                
                # Notificar clientes
                await notification_callback({
                    "type": "binance_mode_trade",
                    "message": f"Trade {simulator.mode.name}: {trade.pnl > 0 and 'ganador' or 'perdedor'} (${trade.pnl:+.2f})",
                    "data": {
                        "trade_id": trade.id,
                        "symbol": trade.symbol,
                        "strategy": trade.strategy,
                        "pnl": trade.pnl,
                        "capital": equity.capital,
                        "mode": simulator.mode.name,
                        "risk_percentage": simulator.mode.risk_percentage,
                        "daily_trades": simulator.daily_trades,
                        "daily_pnl": simulator.daily_pnl,
                        "consecutive_losses": simulator.consecutive_losses,
                        "hourly_trades": simulator.hourly_trades,
                        "source": f"binance_{mode}"
                    }
                })
            
            db.close()
            
        except Exception as e:
            print(f"❌ Error en simulación Binance {mode}: {e}")
        
        # Intervalo según modo (más agresivo = más rápido)
        interval = {
            "conservative": 45,  # 45 segundos
            "hybrid": 30,        # 30 segundos  
            "aggressive": 15     # 15 segundos
        }
        
        await asyncio.sleep(interval[mode])
