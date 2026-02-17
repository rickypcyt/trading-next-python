#!/usr/bin/env python3
"""
Simulador optimizado para 20% mensual consistente
"""
from simulator import TradingSimulator
from database import get_db, Trade, EquityCurve, Metric, Alert
from datetime import datetime, timedelta
import random
import asyncio
import requests

class MonthlyTargetSimulator(TradingSimulator):
    def __init__(self, db):
        super().__init__(db)
        self.daily_target = 0.006  # 0.6% diario
        self.monthly_target = 0.20  # 20% mensual
        self.max_daily_risk = 0.06  # 6% máximo riesgo diario
        self.daily_trades = 0
        self.daily_pnl = 0
        self.consecutive_losses = 0
    
    def get_real_btc_price(self):
        """Obtener precio real de Bitcoin desde Binance API"""
        try:
            response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                print("⚠️ Error obteniendo precio de Binance, usando fallback")
                return 68800.0  # Precio fallback
        except Exception as e:
            print(f"⚠️ Error API Binance: {e}, usando fallback")
            return 68800.0  # Precio fallback
    
    def should_trade_today(self):
        """Verificar si se debe operar hoy"""
        # Regla: no operar si hay 3 pérdidas consecutivas
        if self.consecutive_losses >= 3:
            return False, "3 pérdidas consecutivas - descansar"
        
        # Regla: no superar 6% riesgo diario
        if abs(self.daily_pnl) >= (self.current_capital * self.max_daily_risk):
            return False, "Límite de riesgo diario alcanzado"
        
        return True, "Condiciones favorables"
    
    def calculate_position_size(self, risk_percentage=0.04):
        """Calcular tamaño de posición según 4% riesgo"""
        risk_amount = self.current_capital * risk_percentage
        return risk_amount
    
    def generate_monthly_target_trade(self):
        """Generar trade optimizado para 20% mensual con precios reales de Binance"""
        can_trade, reason = self.should_trade_today()
        
        if not can_trade:
            print(f"🚫 No trading hoy: {reason}")
            return None
        
        # Obtener precio real de Bitcoin
        real_btc_price = self.get_real_btc_price()
        print(f"💰 Precio real BTC: ${real_btc_price:.2f}")
        
        # Parámetros de la estrategia moderada
        win_rate = 0.55  # 55% win rate
        risk_reward = 3.0  # 1:3 risk/reward
        
        position_size = self.calculate_position_size(0.04)  # 4% riesgo
        potential_loss = position_size * 0.04  # 4% de riesgo
        potential_profit = potential_loss * risk_reward  # 12% profit
        
        # Determinar si es trade ganador (55% probabilidad)
        is_winner = random.random() < win_rate
        
        if is_winner:
            pnl = potential_profit
            self.consecutive_losses = 0
            result = "WIN"
        else:
            pnl = -potential_loss
            self.consecutive_losses += 1
            result = "LOSS"
        
        # Actualizar métricas diarias
        self.daily_trades += 1
        self.daily_pnl += pnl
        
        # Crear trade con precios reales de Binance
        trade = Trade(
            timestamp_entry=datetime.now().isoformat(),
            timestamp_exit=datetime.now().isoformat(),
            symbol="BTC/USDT",  # Enfocado en BTC para consistencia
            strategy="Monthly Target 20%",
            entry_price=real_btc_price,  # Precio real de Binance
            exit_price=real_btc_price + (pnl * 100),  # Precio real + P&L ajustado
            size=position_size,
            pnl=pnl
        )
        
        print(f"📊 Trade #{self.daily_trades}: {result} | PnL: ${pnl:+.2f} | Consecutivas: {self.consecutive_losses}")
        
        return trade

async def run_monthly_target_simulation(get_db_func, notification_callback):
    """Ejecutar simulación optimizada para 20% mensual"""
    print("🎯 Iniciando simulación para 20% mensual...")
    
    while True:
        db = next(get_db_func())
        simulator = MonthlyTargetSimulator(db)
        
        try:
            # Generar trade optimizado
            trade = simulator.generate_monthly_target_trade()
            
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
                        "total_trades": simulator.daily_trades
                    }
                })
                
                # Calcular métricas si hay suficientes trades
                if simulator.daily_trades % 10 == 0:
                    metrics = simulator.calculate_metrics()
                    if metrics:
                        db.add(metrics)
                        db.commit()
                
                # Generar alertas importantes
                alerts = []
                if simulator.consecutive_losses >= 3:
                    alerts.append(Alert(
                        timestamp=datetime.now().isoformat(),
                        type="risk_warning",
                        message=f"3 pérdidas consecutivas - considerar descansar"
                    ))
                
                if trade.pnl > 0 and simulator.daily_pnl > (simulator.current_capital * simulator.daily_target):
                    alerts.append(Alert(
                        timestamp=datetime.now().isoformat(),
                        type="target_achieved",
                        message=f"Meta diaria alcanzada: +{simulator.daily_pnl:.2f}"
                    ))
                
                for alert in alerts:
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                
                # Notificar clientes
                await notification_callback({
                    "type": "monthly_target_trade",
                    "message": f"Trade {trade.pnl > 0 and 'ganador' or 'perdedor'}: ${trade.pnl:+.2f}",
                    "data": {
                        "trade_id": trade.id,
                        "symbol": trade.symbol,
                        "strategy": trade.strategy,
                        "pnl": trade.pnl,
                        "capital": equity.capital,
                        "daily_trades": simulator.daily_trades,
                        "daily_pnl": simulator.daily_pnl,
                        "consecutive_losses": simulator.consecutive_losses,
                        "monthly_progress": (simulator.current_capital - 100) / 20,  # Progreso hacia 20%
                        "source": "monthly_target"
                    }
                })
            
            db.close()
            
        except Exception as e:
            print(f"❌ Error en simulación mensual: {e}")
        
        # Intervalo optimizado: 20 segundos entre trades
        await asyncio.sleep(20)
