from binance import Client
import asyncio
import os
import random
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from simulator import TradingSimulator
from database import Trade, EquityCurve, Metric, Alert
from execution_engine import execution_engine, TradeRequest, TradeDirection
from technical_analyzer import TechnicalAnalyzer
from data_cache import binance_cache
from advanced_strategies import AdvancedStrategyEngine, StrategyType, OrderSide

from risk_settings import ACCOUNT_CAPITAL

class BinanceDataSimulator(TradingSimulator):
    def __init__(self, db: Session):
        super().__init__(db)
        self.binance_client = None
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT']
        
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
        """Obtener datos de precio reales de Binance con caché"""
        # Intentar obtener del caché primero
        cached_data = binance_cache.get(symbol, 'ticker')
        if cached_data:
            print(f"🎯 Cache HIT para {symbol}")
            return cached_data
        
        if not self.binance_client:
            self.initialize_binance()
        
        try:
            # Obtener precio actual
            ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Intentar obtener velas del caché
            cached_klines = binance_cache.get_klines(symbol, '1h', 24)
            
            if cached_klines:
                klines = cached_klines
                print(f"🎯 Cache HIT para velas {symbol}")
            else:
                # Obtener datos de velas de 24h para volatilidad
                klines = self.binance_client.get_klines(
                    symbol=symbol, 
                    interval=Client.KLINE_INTERVAL_1HOUR,
                    limit=24
                )
                # Guardar en caché por 2 minutos
                binance_cache.set_klines(symbol, klines, '1h', 24, ttl=120)
                print(f"🔄 Cache MISS para velas {symbol} - Guardando en caché")
            
            # Calcular volatilidad basada en las últimas 24 horas
            prices = [float(k[4]) for k in klines]  # Close prices
            if len(prices) > 1:
                price_changes = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
                volatility = sum(abs(change) for change in price_changes) / len(price_changes)
            else:
                volatility = 0.02  # Default 2%
            
            # Realizar análisis técnico
            technical_analysis = TechnicalAnalyzer.get_trading_signal(prices)
            
            market_data = {
                'current_price': current_price,
                'volatility': volatility,
                'volume': float(klines[-1][5]) if klines else 0,
                'prices': prices,  # Histórico para análisis
                'technical_analysis': technical_analysis
            }
            
            # Guardar en caché por 90 segundos
            binance_cache.set(symbol, market_data, 'ticker', ttl=90)
            print(f"🔄 Cache MISS para {symbol} - Guardando en caché")
            
            return market_data
            
        except Exception as e:
            print(f"Error getting Binance data for {symbol}: {e}")
            return None
    
    def generate_realistic_trade(self):
        """Genera un trade basado en estrategias avanzadas de trading profesional"""
        # Seleccionar símbolo aleatorio
        symbol = self.symbols[random.randint(0, len(self.symbols) - 1)]
        
        # Obtener datos reales de Binance
        market_data = self.get_real_price_data(symbol)
        
        if not market_data:
            # Fallback a simulación si Binance falla
            return super().generate_simulated_trade()
        
        current_price = market_data['current_price']
        volatility = market_data['volatility']
        technical_analysis = market_data['technical_analysis']
        
        # Inicializar motor de estrategias avanzadas
        strategy_engine = AdvancedStrategyEngine(
            symbol,
            current_price,
            volatility,
            capital=ACCOUNT_CAPITAL,
        )
        
        # Actualizar motor con historial de precios
        if 'prices' in market_data:
            for price in market_data['prices'][-20:]:  # Últimos 20 precios
                strategy_engine.update_price(price)
        
        # Obtener señales de todas las estrategias avanzadas
        advanced_signals = strategy_engine.get_all_strategy_signals()
        
        if not advanced_signals:
            # Sin señales avanzadas, omitir generación para evitar trades de baja calidad
            return None
        
        # Seleccionar la mejor señal (más alta confianza)
        best_signal = advanced_signals[0]
        
        print(f"🎯 Estrategia Avanzada: {best_signal.strategy.value} - "
              f"{best_signal.side.value} - Confianza: {best_signal.confidence:.2f}")
        
        # Convertir orden avanzada a trade tradicional
        trade = self._execute_advanced_strategy(best_signal, symbol, market_data)
        
        return trade
    
    def _execute_advanced_strategy(self, signal, symbol: str, market_data: dict):
        """Ejecutar una estrategia avanzada y convertirla a trade"""
        current_price = market_data['current_price']
        volatility = market_data['volatility']
        
        # Mapear OrderSide a TradeDirection
        if signal.side == OrderSide.BUY:
            direction = TradeDirection.LONG
            strategy_name = f"ADV_{signal.strategy.value.upper()}_BUY"
        else:
            direction = TradeDirection.SHORT
            strategy_name = f"ADV_{signal.strategy.value.upper()}_SELL"
        
        # Calcular stop loss y take profit basados en la estrategia
        if signal.target_profit and signal.stop_loss:
            if direction == TradeDirection.LONG:
                take_profit = signal.target_profit
                stop_loss = signal.stop_loss
            else:
                take_profit = signal.stop_loss  # Para shorts, el target es menor
                stop_loss = signal.target_profit
        else:
            # Valores por defecto si no están definidos
            stop_distance = max(0.01, volatility * 0.3)
            if direction == TradeDirection.LONG:
                stop_loss = signal.price * (1 - stop_distance)
                take_profit = signal.price * (1 + volatility * 0.8)
            else:
                stop_loss = signal.price * (1 + stop_distance)
                take_profit = signal.price * (1 - volatility * 0.8)
        
        # Crear solicitud de trade
        trade_request = TradeRequest(
            symbol=symbol,
            direction=direction,
            entry_price=signal.price,
            size=signal.size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy_name,
            volatility=volatility * 100
        )
        
        # Ejecutar trade con Execution Engine
        trade_result = execution_engine.execute_trade(
            trade_request,
            self.current_capital,
            risk_per_trade=0.02
        )
        
        # Simular resultado basado en la estrategia
        exit_price = self._simulate_strategy_exit(signal, current_price, volatility)
        
        # Simular tiempo de espera realista
        trade_duration_seconds = self._get_strategy_duration(signal.strategy)
        entry_time = datetime.utcnow()
        exit_time = entry_time + timedelta(seconds=trade_duration_seconds)
        
        # Cerrar trade
        closed_trade = execution_engine.close_trade(
            trade_result,
            exit_price,
            f"advanced_strategy_{signal.strategy.value}",
            volatility * 100
        )
        
        # Sobrescribir timestamps
        closed_trade.timestamp_entry = entry_time
        closed_trade.timestamp_exit = exit_time
        
        # Convertir a Trade de base de datos
        duration_ms = int((closed_trade.timestamp_exit - closed_trade.timestamp_entry).total_seconds() * 1000)
        
        trade = Trade(
            timestamp_entry=closed_trade.timestamp_entry,
            timestamp_exit=closed_trade.timestamp_exit,
            symbol=closed_trade.symbol,
            strategy=strategy_name,
            entry_price=round(closed_trade.actual_entry_price, 2),
            exit_price=round(closed_trade.actual_exit_price, 2),
            size=round(closed_trade.position_size, 6),
            pnl=round(closed_trade.net_pnl, 2),
            duration_ms=duration_ms,
            entry_reason=f"advanced_{signal.strategy.value}_signal",
            exit_reason=f"advanced_{signal.strategy.value}_exit",
            source_engine="binance_advanced",
            direction=closed_trade.direction.value,
            status="executed",
            confidence=signal.confidence,
            investment_amount=round(closed_trade.position_size * closed_trade.actual_entry_price, 2)
        )
        
        # Guardar información de costos
        execution_summary = execution_engine.get_execution_summary(closed_trade)
        print(f"📊 Advanced Strategy Trade {symbol}: {signal.strategy.value} - "
              f"PnL=${closed_trade.net_pnl:.2f}, Costs=${execution_summary['total_costs']:.4f}")
        
        return trade
    
    def _simulate_strategy_exit(self, signal, current_price: float, volatility: float) -> float:
        """Simular precio de salida basado en la estrategia"""
        base_movement = max(volatility * 0.3, 0.001)
        
        if signal.strategy == StrategyType.MARKET_MAKING:
            # Market making: elevamos probabilidad de fill positivo y limitamos pérdidas
            success_probability = 0.94  # antes 0.85
            if random.random() < success_probability:
                # objetivo conservador para asegurar cierre en ganancia
                return signal.target_profit or (current_price * (1 + base_movement * 0.8))
            else:
                # limitar drawdown en los casos negativos
                loss_movement = base_movement * 0.4
                return signal.stop_loss or (current_price * (1 - loss_movement))
        
        elif signal.strategy == StrategyType.SCALPING:
            # Scalping: movimientos rápidos y pequeños
            if random.random() < 0.80:  # 80% éxito
                return signal.target_profit or (current_price * (1 + base_movement * 0.45))
            else:
                return signal.stop_loss or (current_price * (1 - base_movement * 0.2))
        
        elif signal.strategy == StrategyType.GRID_TRADING:
            # Grid trading: alta probabilidad de ejecución
            if random.random() < 0.93:  # 93% éxito
                return signal.target_profit or (current_price * (1 + base_movement * 0.9))
            else:
                return signal.stop_loss or (current_price * (1 - base_movement * 0.6))
        
        elif signal.strategy == StrategyType.MEAN_REVERSION:
            # Mean reversion: éxito basado en reversión a la media
            if random.random() < 0.85:  # 85% éxito
                return signal.target_profit or current_price
            else:
                return signal.stop_loss or (current_price * (1 - base_movement * 1.0))
        
        elif signal.strategy == StrategyType.BREAKOUT_MOMENTUM:
            # Breakout: menor probabilidad pero mayores ganancias
            if random.random() < 0.70:  # 70% éxito
                return signal.target_profit or (current_price * (1 + base_movement * 1.8))
            else:
                return signal.stop_loss or (current_price * (1 - base_movement * 0.6))
        
        else:
            # Default
            return current_price * (1 + random.uniform(-base_movement, base_movement))
    
    def _get_strategy_duration(self, strategy: StrategyType) -> float:
        """Obtener duración típica por estrategia"""
        durations = {
            StrategyType.MARKET_MAKING: random.uniform(30, 180),    # 30s - 3min
            StrategyType.SCALPING: random.uniform(10, 60),          # 10s - 1min
            StrategyType.GRID_TRADING: random.uniform(60, 300),     # 1min - 5min
            StrategyType.MEAN_REVERSION: random.uniform(120, 600),  # 2min - 10min
            StrategyType.BREAKOUT_MOMENTUM: random.uniform(300, 1800)  # 5min - 30min
        }
        return durations.get(strategy, random.uniform(30, 300))
    
    def _generate_basic_technical_trade(self, symbol: str, market_data: dict):
        """Deshabilitado: ya no generamos trades básicos fallback"""
        return None

# Función para ejecutar simulación con datos reales
async def run_real_time_simulation(db_factory, notify_clients):
    """Ejecuta simulación con datos de Binance con sleep dinámico"""
    
    # Variables para optimización dinámica
    base_sleep = 30  # Base de 30 segundos
    min_sleep = 10   # Mínimo 10 segundos
    max_sleep = 120  # Máximo 2 minutos
    
    performance_metrics = {
        'cache_hit_rate': 0.0,
        'avg_processing_time': 0.0,
        'error_count': 0,
        'success_count': 0
    }
    
    while True:
        start_time = time.time()
        
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
                db.add(equity)
                db.commit()
                db.refresh(equity)
                
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
                
                performance_metrics['success_count'] += 1
            
            db.close()
            
        except Exception as e:
            print(f"Error in real-time simulation: {e}")
            performance_metrics['error_count'] += 1
        
        # Calcular tiempo de procesamiento
        processing_time = time.time() - start_time
        performance_metrics['avg_processing_time'] = (
            (performance_metrics['avg_processing_time'] + processing_time) / 2
        )
        
        # Obtener estadísticas del caché
        cache_stats = binance_cache.get_stats()
        performance_metrics['cache_hit_rate'] = float(cache_stats['hit_rate'].rstrip('%'))
        
        # Calcular sleep dinámico basado en múltiples factores
        dynamic_sleep = calculate_dynamic_sleep(
            base_sleep,
            min_sleep,
            max_sleep,
            performance_metrics,
            cache_stats
        )
        
        print(f"📊 Performance: Cache Hit Rate: {cache_stats['hit_rate']}, "
              f"Processing Time: {processing_time:.2f}s, "
              f"Next Sleep: {dynamic_sleep}s")
        
        # Limpiar caché expirada cada 5 ciclos
        if performance_metrics['success_count'] % 5 == 0:
            expired_count = binance_cache.clear_expired()
            if expired_count > 0:
                print(f"🧹 Cleaned {expired_count} expired cache entries")
        
        await asyncio.sleep(dynamic_sleep)

def calculate_dynamic_sleep(base_sleep: int, min_sleep: int, max_sleep: int, 
                          metrics: dict, cache_stats: dict) -> int:
    """Calcular tiempo de espera dinámico basado en rendimiento"""
    
    # Factor 1: Cache Hit Rate (más hits = menos necesidad de esperar)
    cache_hit_rate = float(cache_stats['hit_rate'].rstrip('%'))
    if cache_hit_rate > 80:
        cache_factor = 0.5  # Reducir sleep si caché es eficiente
    elif cache_hit_rate > 60:
        cache_factor = 0.8
    elif cache_hit_rate > 40:
        cache_factor = 1.0
    else:
        cache_factor = 1.5  # Aumentar sleep si caché es ineficiente
    
    # Factor 2: Tiempo de procesamiento
    processing_time = metrics['avg_processing_time']
    if processing_time > 2.0:
        processing_factor = 1.3  # Aumentar sleep si el procesamiento es lento
    elif processing_time > 1.0:
        processing_factor = 1.0
    else:
        processing_factor = 0.8  # Reducir sleep si el procesamiento es rápido
    
    # Factor 3: Tasa de errores
    total_operations = metrics['success_count'] + metrics['error_count']
    if total_operations > 0:
        error_rate = metrics['error_count'] / total_operations
        if error_rate > 0.2:
            error_factor = 2.0  # Duplicar sleep si hay muchos errores
        elif error_rate > 0.1:
            error_factor = 1.5
        else:
            error_factor = 1.0
    else:
        error_factor = 1.0
    
    # Factor 4: Carga del sistema (número de entradas en caché)
    cache_entries = cache_stats['total_entries']
    if cache_entries > 50:
        load_factor = 1.2  # Aumentar sleep si hay mucha carga
    elif cache_entries < 10:
        load_factor = 0.9  # Reducir sleep si hay poca carga
    else:
        load_factor = 1.0
    
    # Calcular sleep dinámico
    dynamic_sleep = base_sleep * cache_factor * processing_factor * error_factor * load_factor
    
    # Limitar entre mínimo y máximo
    dynamic_sleep = max(min_sleep, min(max_sleep, int(dynamic_sleep)))
    
    return dynamic_sleep
