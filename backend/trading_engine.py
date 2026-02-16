import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class TradingSignal:
    symbol: str
    signal: Signal
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-1
    strategy: str
    indicators: Dict
    timestamp: datetime

class TechnicalIndicators:
    """Calculadora de indicadores técnicos"""
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return [100.0] * len(prices)
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return [rsi] * len(prices)
    
    @staticmethod
    def moving_average(prices: List[float], period: int) -> List[float]:
        """Media móvil simple"""
        if len(prices) < period:
            return [prices[-1]] * len(prices)
        
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(prices[i])
            else:
                ma.append(np.mean(prices[i-period+1:i+1]))
        
        return ma
    
    @staticmethod
    def exponential_moving_average(prices: List[float], period: int) -> List[float]:
        """Media móvil exponencial"""
        if len(prices) < period:
            return [prices[-1]] * len(prices)
        
        multiplier = 2 / (period + 1)
        ema = [prices[0]]
        
        for i in range(1, len(prices)):
            ema.append((prices[i] * multiplier) + (ema[-1] * (1 - multiplier)))
        
        return ema
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return [0] * len(prices), [0] * len(prices), [0] * len(prices)
        
        ema_fast = TechnicalIndicators.exponential_moving_average(prices, fast)
        ema_slow = TechnicalIndicators.exponential_moving_average(prices, slow)
        
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = TechnicalIndicators.exponential_moving_average(macd_line, signal)
        histogram = [m - s for m, s in zip(macd_line, signal_line)]
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        """Bandas de Bollinger"""
        if len(prices) < period:
            middle = [prices[-1]] * len(prices)
            upper = [prices[-1] * 1.02] * len(prices)
            lower = [prices[-1] * 0.98] * len(prices)
            return upper, middle, lower
        
        middle = TechnicalIndicators.moving_average(prices, period)
        
        upper = []
        lower = []
        for i in range(len(prices)):
            if i < period - 1:
                upper.append(prices[i] * 1.02)
                lower.append(prices[i] * 0.98)
            else:
                period_prices = prices[i-period+1:i+1]
                std = np.std(period_prices)
                upper.append(middle[i] + (std * std_dev))
                lower.append(middle[i] - (std * std_dev))
        
        return upper, middle, lower

class TradingStrategies:
    """Estrategias de trading basadas en indicadores técnicos"""
    
    def __init__(self, initial_capital: float = 100.0, risk_per_trade: float = 0.02):
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade  # 2% de riesgo por trade
        
    def rsi_strategy(self, symbol: str, prices: List[float], current_price: float) -> Optional[TradingSignal]:
        """Estrategia basada en RSI (sobrecompra/sobreventa)"""
        if len(prices) < 15:
            return None
        
        rsi_values = TechnicalIndicators.rsi(prices)
        current_rsi = rsi_values[-1]
        
        # Reglas de RSI
        if current_rsi < 30:  # Sobreventa - comprar
            stop_loss = current_price * 0.97  # 3% debajo
            take_profit = current_price * 1.06  # 6% arriba
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.BUY,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=max(0, (30 - current_rsi) / 30),  # Más confianza si está más sobreventa
                strategy="RSI_Reversion",
                indicators={"rsi": current_rsi, "signal": "oversold"},
                timestamp=datetime.now()
            )
        
        elif current_rsi > 70:  # Sobrecompra - vender
            stop_loss = current_price * 1.03  # 3% arriba
            take_profit = current_price * 0.94  # 6% abajo
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.SELL,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=max(0, (current_rsi - 70) / 30),  # Más confianza si está más sobrecompra
                strategy="RSI_Reversion",
                indicators={"rsi": current_rsi, "signal": "overbought"},
                timestamp=datetime.now()
            )
        
        return None
    
    def moving_average_crossover(self, symbol: str, prices: List[float], current_price: float) -> Optional[TradingSignal]:
        """Estrategia de cruce de medias móviles"""
        if len(prices) < 25:
            return None
        
        ma_fast = TechnicalIndicators.moving_average(prices, 5)
        ma_slow = TechnicalIndicators.moving_average(prices, 20)
        
        current_fast = ma_fast[-1]
        current_slow = ma_slow[-1]
        prev_fast = ma_fast[-2] if len(ma_fast) > 1 else current_fast
        prev_slow = ma_slow[-2] if len(ma_slow) > 1 else current_slow
        
        # Detectar cruce
        if prev_fast <= prev_slow and current_fast > current_slow:  # Cruce alcista
            stop_loss = current_price * 0.98  # 2% debajo
            take_profit = current_price * 1.04  # 4% arriba
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.BUY,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.7,
                strategy="MA_Crossover",
                indicators={"ma_fast": current_fast, "ma_slow": current_slow, "signal": "bullish_cross"},
                timestamp=datetime.now()
            )
        
        elif prev_fast >= prev_slow and current_fast < current_slow:  # Cruce bajista
            stop_loss = current_price * 1.02  # 2% arriba
            take_profit = current_price * 0.96  # 4% abajo
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.SELL,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.7,
                strategy="MA_Crossover",
                indicators={"ma_fast": current_fast, "ma_slow": current_slow, "signal": "bearish_cross"},
                timestamp=datetime.now()
            )
        
        return None
    
    def macd_strategy(self, symbol: str, prices: List[float], current_price: float) -> Optional[TradingSignal]:
        """Estrategia basada en MACD"""
        if len(prices) < 30:
            return None
        
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        prev_macd = macd_line[-2] if len(macd_line) > 1 else current_macd
        prev_signal = signal_line[-2] if len(signal_line) > 1 else current_signal
        
        # Detectar cruce con línea de señal
        if prev_macd <= prev_signal and current_macd > current_signal:  # Cruce alcista
            stop_loss = current_price * 0.975  # 2.5% debajo
            take_profit = current_price * 1.05  # 5% arriba
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.BUY,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                strategy="MACD_Crossover",
                indicators={"macd": current_macd, "signal": current_signal, "histogram": histogram[-1]},
                timestamp=datetime.now()
            )
        
        elif prev_macd >= prev_signal and current_macd < current_signal:  # Cruce bajista
            stop_loss = current_price * 1.025  # 2.5% arriba
            take_profit = current_price * 0.95  # 5% abajo
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.SELL,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.6,
                strategy="MACD_Crossover",
                indicators={"macd": current_macd, "signal": current_signal, "histogram": histogram[-1]},
                timestamp=datetime.now()
            )
        
        return None
    
    def bollinger_bands_strategy(self, symbol: str, prices: List[float], current_price: float) -> Optional[TradingSignal]:
        """Estrategia de Bandas de Bollinger"""
        if len(prices) < 25:
            return None
        
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices)
        
        current_upper = upper[-1]
        current_middle = middle[-1]
        current_lower = lower[-1]
        
        # Señales basadas en posición respecto a las bandas
        if current_price <= current_lower:  # Toca banda inferior - posible compra
            stop_loss = current_price * 0.98  # 2% debajo
            take_profit = current_middle  # Volver a la banda media
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.BUY,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.5,
                strategy="Bollinger_Bands",
                indicators={"upper": current_upper, "middle": current_middle, "lower": current_lower, "position": "lower_band"},
                timestamp=datetime.now()
            )
        
        elif current_price >= current_upper:  # Toca banda superior - posible venta
            stop_loss = current_price * 1.02  # 2% arriba
            take_profit = current_middle  # Volver a la banda media
            
            return TradingSignal(
                symbol=symbol,
                signal=Signal.SELL,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.5,
                strategy="Bollinger_Bands",
                indicators={"upper": current_upper, "middle": current_middle, "lower": current_lower, "position": "upper_band"},
                timestamp=datetime.now()
            )
        
        return None
    
    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """Calcular tamaño de posición basado en gestión de riesgo"""
        risk_amount = self.capital * self.risk_per_trade  # 2% del capital
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0
        
        position_size = risk_amount / price_risk
        return min(position_size, self.capital * 0.1)  # Máximo 10% del capital en una posición

class AdvancedTradingEngine:
    """Motor de trading avanzado con múltiples estrategias"""
    
    def __init__(self, initial_capital: float = 100.0):
        self.capital = initial_capital
        self.strategies = TradingStrategies(initial_capital, risk_per_trade=0.02)
        self.active_signals = {}
        
    def analyze_symbol(self, symbol: str, price_data: List[Dict]) -> List[TradingSignal]:
        """Analizar un símbolo con todas las estrategias"""
        if not price_data:
            return []
        
        prices = [data['close'] for data in price_data]
        current_price = prices[-1]
        
        signals = []
        
        # Ejecutar todas las estrategias
        rsi_signal = self.strategies.rsi_strategy(symbol, prices, current_price)
        if rsi_signal:
            signals.append(rsi_signal)
        
        ma_signal = self.strategies.moving_average_crossover(symbol, prices, current_price)
        if ma_signal:
            signals.append(ma_signal)
        
        macd_signal = self.strategies.macd_strategy(symbol, prices, current_price)
        if macd_signal:
            signals.append(macd_signal)
        
        bb_signal = self.strategies.bollinger_bands_strategy(symbol, prices, current_price)
        if bb_signal:
            signals.append(bb_signal)
        
        return signals
    
    def get_best_signal(self, signals: List[TradingSignal]) -> Optional[TradingSignal]:
        """Seleccionar la mejor señal basada en confianza"""
        if not signals:
            return None
        
        # Filtrar señales con confianza mínima
        valid_signals = [s for s in signals if s.confidence > 0.3]
        
        if not valid_signals:
            return None
        
        # Seleccionar la señal con mayor confianza
        best_signal = max(valid_signals, key=lambda s: s.confidence)
        
        # Calcular tamaño de posición
        position_size = self.strategies.calculate_position_size(
            best_signal.entry_price, 
            best_signal.stop_loss
        )
        
        # Actualizar señal con tamaño de posición
        best_signal.indicators['position_size'] = position_size
        
        return best_signal
    
    def calculate_pnl(self, signal: TradingSignal, exit_price: float) -> float:
        """Calcular P&L de una señal ejecutada"""
        if signal.signal == Signal.BUY:
            return (exit_price - signal.entry_price) * signal.indicators.get('position_size', 0)
        else:  # SELL
            return (signal.entry_price - exit_price) * signal.indicators.get('position_size', 0)

# Ejemplo de uso
if __name__ == "__main__":
    # Datos de ejemplo (precios de BTC)
    sample_prices = [
        {'close': 45000}, {'close': 45200}, {'close': 44800},
        {'close': 45500}, {'close': 45300}, {'close': 45700},
        {'close': 45600}, {'close': 45900}, {'close': 46200},
        {'close': 46100}, {'close': 46400}, {'close': 46300},
        {'close': 46600}, {'close': 46800}, {'close': 46700},
        {'close': 47000}, {'close': 47200}, {'close': 47100},
        {'close': 47400}, {'close': 47600}, {'close': 47500},
        {'close': 47800}, {'close': 48000}, {'close': 47900},
        {'close': 48200}, {'close': 48400}, {'close': 48300}
    ]
    
    engine = AdvancedTradingEngine(100.0)
    signals = engine.analyze_symbol("BTC/USD", sample_prices)
    best_signal = engine.get_best_signal(signals)
    
    if best_signal:
        print(f"🚀 Signal: {best_signal.signal.value}")
        print(f"💰 Entry: ${best_signal.entry_price}")
        print(f"🛡️  Stop Loss: ${best_signal.stop_loss}")
        print(f"🎯 Take Profit: ${best_signal.take_profit}")
        print(f"📊 Strategy: {best_signal.strategy}")
        print(f"💪 Confidence: {best_signal.confidence:.2f}")
        print(f"📈 Position Size: ${best_signal.indicators.get('position_size', 0):.2f}")
    else:
        print("❌ No trading signals available")
