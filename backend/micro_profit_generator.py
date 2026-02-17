import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from database import Trade, EquityCurve, Alert
from binance_simulator import BinanceDataSimulator
from intelligent_simulator import BinancePriceManager
from trade_logger import get_trade_logger
import json

class MicroProfitGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.initial_capital = 100.0
        self.current_capital = 100.0
        self.max_capital = 100.0
        self.trades_count = 0
        self.micro_trades_count = 0
        self.successful_micro_trades = 0
        self.total_micro_profit = 0.0
        
        # Parámetros de micro-trading
        self.target_profit_per_trade = 0.01  # $0.01 objetivo (más realista)
        self.max_risk_per_trade = 0.002  # 0.2% riesgo máximo (un poco más)
        self.min_win_rate = 0.90  # 90% win rate mínimo (más alto)
        self.max_position_size = 0.02  # 2% del capital máximo (más grande)
        
        # Símbolos más seguros para micro-trading
        self.safe_symbols = ['BTC/USD', 'ETH/USD']
        self.binance_simulator = BinanceDataSimulator(db)
        self.price_manager = BinancePriceManager()
        self.price_manager.initialize_client()
        self.trade_logger = get_trade_logger(db)
        
    async def generate_micro_trade(self, iterations: int = 1) -> List[Trade]:
        """Generar múltiples micro-trades seguros"""
        trades = []
        
        print(f"🚀 Starting Micro Profit Generator with {iterations} iterations")
        print(f"📊 Safe symbols: {self.safe_symbols}")
        
        for i in range(iterations):
            try:
                print(f"🔄 Executing micro trade {i+1}/{iterations}")
                trade = await self._execute_single_micro_trade()
                if trade:
                    trades.append(trade)
                    self.micro_trades_count += 1
                    print(f"✅ Trade {i+1} generated: {trade.symbol} ${trade.pnl}")
                    
                    # Actualizar capital
                    self.current_capital += trade.pnl
                    self.max_capital = max(self.max_capital, self.current_capital)
                    
                    if trade.pnl >= 0:
                        self.successful_micro_trades += 1
                        self.total_micro_profit += trade.pnl
                    
                    # Guardar en base de datos
                    self.db.add(trade)
                    self.db.commit()
                    self.db.refresh(trade)
                    
                    # Actualizar equity
                    equity = self._update_equity()
                    if equity:
                        self.db.merge(equity)
                        self.db.commit()
                    
                    # Pequeña pausa entre trades
                    await asyncio.sleep(0.5)
                else:
                    print(f"❌ Trade {i+1} failed - no trade generated")
                    
            except Exception as e:
                print(f"💥 Error in micro trade {i+1}: {e}")
                continue
        
        print(f"📈 Micro Profit Generator completed: {len(trades)}/{iterations} trades generated")
        return trades
    
    async def _execute_single_micro_trade(self) -> Optional[Trade]:
        """Ejecutar un solo micro-trade seguro"""
        # Seleccionar símbolo seguro
        symbol = random.choice(self.safe_symbols)
        print(f"🎯 Selected symbol: {symbol}")
        
        # Obtener precio actual
        current_price = await self._get_current_price(symbol)
        print(f"💰 Current price: ${current_price}")
        if not current_price:
            print("❌ No current price available")
            return None
        
        # Calcular tamaño de posición muy pequeño
        position_value = self.initial_capital * self.max_position_size
        position_size = position_value / current_price
        print(f"📏 Position size: {position_size:.6f} (value: ${position_value:.2f})")
        
        # Análisis de mercado rápido
        market_condition = await self._analyze_market_condition(symbol, current_price)
        print(f"📊 Market condition: {market_condition}")
        
        # Solo trade si condiciones son muy favorables
        if not self._is_safe_condition(market_condition):
            print(f"⚠️ Unsafe market condition - skipping trade")
            return None
        
        # Determinar dirección con alta probabilidad
        direction = self._determine_safe_direction(market_condition)
        print(f"📈 Direction: {direction}")
        
        # Calcular entry/exit con profit objetivo de $0.05
        entry_price = current_price
        target_profit = self.target_profit_per_trade
        
        if direction == 'long':
            # Para long: exit_price = entry_price + profit_needed
            profit_per_unit = target_profit / position_size
            exit_price = entry_price + profit_per_unit
            stop_loss = entry_price * (1 - self.max_risk_per_trade)
        else:  # short
            # Para short: exit_price = entry_price - profit_needed
            profit_per_unit = target_profit / position_size
            exit_price = entry_price - profit_per_unit
            stop_loss = entry_price * (1 + self.max_risk_per_trade)
        
        print(f"🎯 Entry: ${entry_price:.2f}, Exit: ${exit_price:.2f}, Stop: ${stop_loss:.2f}")
        
        # Simular resultado con alta probabilidad de éxito
        success_probability = 0.85 + (market_condition['confidence'] * 0.1)
        is_successful = random.random() < success_probability
        print(f"🎲 Success probability: {success_probability:.2f}, Result: {'SUCCESS' if is_successful else 'FAIL'}")
        
        if is_successful:
            final_price = exit_price
            pnl = target_profit
        else:
            final_price = stop_loss
            pnl = -position_value * self.max_risk_per_trade
        
        print(f"💸 Final P&L: ${pnl:.4f}")
        
        # Crear trade
        entry_time = datetime.now()
        exit_time = entry_time + timedelta(seconds=30)  # Trades muy rápidos
        duration_ms = 30000  # 30 segundos
        
        trade = Trade(
            timestamp_entry=entry_time.isoformat(),
            timestamp_exit=exit_time.isoformat(),
            symbol=symbol,
            strategy="Micro_Profit_Generator",
            entry_price=round(entry_price, 2),
            exit_price=round(final_price, 2),
            size=round(position_size, 6),
            pnl=round(pnl, 4),
            duration_ms=duration_ms,
            entry_reason="micro_profit_signal",
            exit_reason="micro_profit_close",
            source_engine="micro_profit",
            direction="LONG",
            status="executed"
        )
        
        # Log de apertura del trade
        strategy_info = {
            "direction": direction,
            "reason": "micro_profit_target",
            "market_conditions": market_condition,
            "risk_amount": round(position_value * self.max_risk_per_trade, 4),
            "target_profit": self.target_profit_per_trade
        }
        self.trade_logger.log_trade_opened(trade, strategy_info)
        
        # Simular cierre inmediato (micro trades son muy rápidos)
        close_reason = "target_reached" if is_successful else "stop_loss_hit"
        self.trade_logger.log_trade_closed(trade, close_reason)
        
        return trade
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Obtener precio actual del símbolo"""
        try:
            # Usar el price manager para obtener precios reales
            prices = await self.price_manager.get_all_prices()
            symbol_key = symbol.replace('/', '')
            return prices.get(symbol_key, prices.get(symbol.replace('USD', 'USDT')))
        except:
            # Precio fallback si falla Binance
            fallback_prices = {
                'BTC/USD': 68000.0,
                'ETH/USD': 1970.0
            }
            return fallback_prices.get(symbol)
    
    async def _analyze_market_condition(self, symbol: str, current_price: float) -> Dict:
        """Análisis rápido de condiciones del mercado"""
        # Simular análisis técnico básico
        volatility = random.uniform(0.5, 2.0)  # Baja volatilidad preferida
        trend = random.choice(['bullish', 'bearish', 'sideways'])
        volume_ratio = random.uniform(0.8, 1.5)
        
        # Calcular confianza de la señal
        confidence = 0.5  # Base confidence
        
        # Aumentar confianza en condiciones favorables
        if volatility < 1.5:  # Baja volatilidad
            confidence += 0.2
        if trend != 'sideways':  # Tendencia clara
            confidence += 0.15
        if volume_ratio > 1.0:  # Buen volumen
            confidence += 0.1
        
        confidence = min(confidence, 0.9)  # Máximo 90%
        
        return {
            'volatility': volatility,
            'trend': trend,
            'volume_ratio': volume_ratio,
            'confidence': confidence,
            'current_price': current_price
        }
    
    def _is_safe_condition(self, market_condition: Dict) -> bool:
        """Verificar si las condiciones son seguras para micro-trading"""
        volatility = market_condition['volatility']
        confidence = market_condition['confidence']
        trend = market_condition['trend']
        
        # Condiciones de seguridad
        if volatility > 2.5:  # Demasiada volatilidad
            return False
        if confidence < 0.6:  # Poca confianza
            return False
        if trend == 'sideways' and volatility > 1.5:  # Mercado lateral volátil
            return False
        
        return True
    
    def _determine_safe_direction(self, market_condition: Dict) -> str:
        """Determinar dirección basada en condiciones seguras"""
        trend = market_condition['trend']
        confidence = market_condition['confidence']
        
        # Seguir tendencia si hay confianza
        if confidence > 0.7:
            if trend == 'bullish':
                return 'long'
            elif trend == 'bearish':
                return 'short'
        
        # Si no hay tendencia clara, elegir direccionalmente basado en volumen
        if market_condition['volume_ratio'] > 1.2:
            return 'long' if random.random() > 0.4 else 'short'
        
        # Default: slight preference for long in safe conditions
        return 'long' if random.random() > 0.45 else 'short'
    
    def _update_equity(self) -> Optional[EquityCurve]:
        """Actualizar curva de equity"""
        try:
            equity = EquityCurve(
                timestamp=datetime.now(),
                capital=round(self.current_capital, 2),
                drawdown=round(max(0, (self.max_capital - self.current_capital) / self.max_capital * 100), 2)
            )
            return equity
        except Exception as e:
            print(f"Error updating equity: {e}")
            return None
    
    def get_micro_stats(self) -> Dict:
        """Obtener estadísticas de micro-trading"""
        win_rate = (self.successful_micro_trades / self.micro_trades_count * 100) if self.micro_trades_count > 0 else 0
        avg_profit = self.total_micro_profit / self.successful_micro_trades if self.successful_micro_trades > 0 else 0
        
        return {
            'total_micro_trades': self.micro_trades_count,
            'successful_trades': self.successful_micro_trades,
            'win_rate': round(win_rate, 2),
            'total_profit': round(self.total_micro_profit, 4),
            'avg_profit_per_trade': round(avg_profit, 4),
            'current_capital': round(self.current_capital, 2),
            'target_profit_per_trade': self.target_profit_per_trade,
            'success_rate_vs_target': round((avg_profit / self.target_profit_per_trade) * 100, 1) if avg_profit > 0 else 0
        }

# Función para ejecutar micro-trading
async def run_micro_profit_generator(iterations: int = 10, db: Session = None):
    """Ejecutar generador de micro-profits"""
    if not db:
        return {"status": "error", "message": "Database session required"}
    
    generator = MicroProfitGenerator(db)
    
    try:
        trades = await generator.generate_micro_trade(iterations)
        stats = generator.get_micro_stats()
        
        return {
            "status": "success",
            "trades_generated": len(trades),
            "stats": stats,
            "message": f"Generated {len(trades)} micro-trades with ${stats['total_profit']:.4f} total profit"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
