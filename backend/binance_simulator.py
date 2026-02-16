from binance import Client
import asyncio
import os
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from simulator import TradingSimulator
from database import Trade, EquityCurve, Metric, Alert

class BinanceDataSimulator(TradingSimulator):
    def __init__(self, db: Session):
        super().__init__(db)
        self.binance_client = None
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        
    def initialize_binance(self):
        """Inicializar cliente de Binance (puede usar datos públicos sin API keys)"""
        try:
            # Para datos públicos no necesitamos API keys
            self.binance_client = Client()
            return True
        except Exception as e:
            print(f"Error initializing Binance client: {e}")
            return False
    
    def get_real_price_data(self, symbol: str):
        """Obtener datos de precio reales de Binance"""
        if not self.binance_client:
            self.initialize_binance()
        
        try:
            # Obtener precio actual
            ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Obtener datos de velas de 24h para volatilidad
            klines = self.binance_client.get_klines(
                symbol=symbol, 
                interval=Client.KLINE_INTERVAL_1HOUR,
                limit=24
            )
            
            # Calcular volatilidad basada en las últimas 24 horas
            prices = [float(k[4]) for k in klines]  # Close prices
            if len(prices) > 1:
                price_changes = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
                volatility = sum(abs(change) for change in price_changes) / len(price_changes)
            else:
                volatility = 0.02  # Default 2%
            
            return {
                'current_price': current_price,
                'volatility': volatility,
                'volume': float(klines[-1][5]) if klines else 0
            }
        except Exception as e:
            print(f"Error getting Binance data for {symbol}: {e}")
            return None
    
    def generate_realistic_trade(self):
        """Genera un trade basado en datos reales de Binance"""
        # Seleccionar símbolo aleatorio
        symbol = self.symbols[random.randint(0, len(self.symbols) - 1)]
        
        # Obtener datos reales de Binance
        market_data = self.get_real_price_data(symbol)
        
        if not market_data:
            # Fallback a simulación si Binance falla
            return super().generate_simulated_trade()
        
        strategies = ['MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'MACD_Signal']
        strategy = random.choice(strategies)
        
        current_price = market_data['current_price']
        volatility = market_data['volatility']
        
        # Generar precios basados en volatilidad real
        price_movement = random.uniform(-volatility, volatility) * 0.5  # Mitad de la volatilidad real
        entry_price = current_price * (1 + price_movement)
        
        # Tamaño de posición (1-3% del capital con $100 base = $1-$3 para ser más conservador)
        position_size = self.current_capital * random.uniform(0.01, 0.03)
        size = position_size / entry_price
        
        # Determinar resultado basado en tendencia y volatilidad
        trend_factor = random.uniform(-1, 1)  # -1 (bearish) a 1 (bullish)
        
        if trend_factor > 0.2:  # Tendencia alcista
            profit_factor = random.uniform(0.1, min(volatility * 100, 2.0))
            pnl = position_size * profit_factor / 100
            exit_price = entry_price * (1 + profit_factor / 100)
        elif trend_factor < -0.2:  # Tendencia bajista
            loss_factor = random.uniform(0.1, min(volatility * 100, 1.5))
            pnl = -position_size * loss_factor / 100
            exit_price = entry_price * (1 - loss_factor / 100)
        else:  # Lateral
            if random.random() < 0.5:  # 50% ganancia
                profit_factor = random.uniform(0.05, volatility * 50)
                pnl = position_size * profit_factor / 100
                exit_price = entry_price * (1 + profit_factor / 100)
            else:
                loss_factor = random.uniform(0.05, volatility * 50)
                pnl = -position_size * loss_factor / 100
                exit_price = entry_price * (1 - loss_factor / 100)
        
        # Timestamps
        now = datetime.now()
        entry_time = now - timedelta(minutes=random.randint(5, 60))
        exit_time = now
        
        # Convertir símbolo de Binance a formato estándar
        symbol_display = symbol.replace('USDT', '/USD')
        
        trade = Trade(
            timestamp_entry=entry_time.isoformat(),
            timestamp_exit=exit_time.isoformat(),
            symbol=symbol_display,
            strategy=strategy,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            size=round(size, 6),
            pnl=round(pnl, 2)
        )
        
        return trade

# Función para ejecutar simulación con datos reales
async def run_real_time_simulation(db_factory, notify_clients):
    """Ejecuta simulación con datos de Binance cada 10 segundos"""
    while True:
        try:
            db = next(db_factory())
            simulator = BinanceDataSimulator(db)
            
            # Generar trade con datos reales
            trade = simulator.generate_realistic_trade()
            
            if trade:
                db.add(trade)
                db.commit()
                db.refresh(trade)
                
                # Actualizar capital
                simulator.current_capital += trade.pnl
                simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
                
                # Actualizar equity
                equity = simulator.update_equity()
                db.merge(equity)
                db.commit()
                
                # Calcular métricas
                metrics = simulator.calculate_metrics()
                if metrics:
                    db.add(metrics)
                    db.commit()
                    db.refresh(metrics)
                
                # Verificar alertas
                alerts = simulator.check_alerts(trade)
                for alert in alerts:
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                
                # Notificar via WebSocket con estructura correcta
                await notify_clients({
                    "type": "real_trade_generated",
                    "message": f"Real Binance trade: {trade.symbol}",
                    "data": {
                        "trade_id": trade.id,
                        "symbol": trade.symbol,
                        "strategy": trade.strategy,
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "pnl": trade.pnl,
                        "capital": equity.capital,
                        "alerts_count": len(alerts),
                        "source": "binance_real_time"
                    }
                })
            
            db.close()
            
        except Exception as e:
            print(f"Error in real-time simulation: {e}")
        
        await asyncio.sleep(10)  # Esperar 10 segundos (más lento para datos reales)
