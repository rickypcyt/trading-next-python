import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime

class TechnicalAnalyzer:
    """Analizador técnico para señales de trading en tiempo real"""
    
    @staticmethod
    def calculate_rsi(prices: list, period: int = 14) -> float:
        """Calcular RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0  # Neutral si no hay suficientes datos
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Calcular MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        prices_array = np.array(prices)
        
        # Calcular EMAs
        ema_fast = TechnicalAnalyzer._calculate_ema(prices_array, fast)
        ema_slow = TechnicalAnalyzer._calculate_ema(prices_array, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calcular línea de señal (EMA del MACD)
        if len(macd_line) >= signal:
            signal_line = TechnicalAnalyzer._calculate_ema(macd_line, signal)
            histogram = macd_line[-1] - signal_line[-1]
            
            return {
                'macd': macd_line[-1],
                'signal': signal_line[-1],
                'histogram': histogram
            }
        
        return {'macd': 0, 'signal': 0, 'histogram': 0}
    
    @staticmethod
    def _calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calcular EMA (Exponential Moving Average)"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    @staticmethod
    def calculate_bollinger_bands(prices: list, period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """Calcular Bandas de Bollinger"""
        if len(prices) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
        
        prices_array = np.array(prices[-period:])
        middle = np.mean(prices_array)
        std = np.std(prices_array)
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    @staticmethod
    def calculate_sma(prices: list, period: int) -> float:
        """Calcular SMA (Simple Moving Average)"""
        if len(prices) < period:
            return np.mean(prices)
        return np.mean(prices[-period:])
    
    @staticmethod
    def analyze_trend_strength(prices: list) -> Dict[str, float]:
        """Analizar fuerza de tendencia"""
        if len(prices) < 10:
            return {'trend': 0, 'strength': 0}
        
        prices_array = np.array(prices)
        
        # Calcular pendiente de tendencia (regresión lineal simple)
        x = np.arange(len(prices_array))
        slope, _ = np.polyfit(x, prices_array, 1)
        
        # Normalizar pendiente por precio promedio
        avg_price = np.mean(prices_array)
        normalized_slope = slope / avg_price
        
        # Calcular fuerza basada en R²
        y_pred = slope * x + np.mean(prices_array)
        ss_res = np.sum((prices_array - y_pred) ** 2)
        ss_tot = np.sum((prices_array - np.mean(prices_array)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'trend': normalized_slope * 100,  # Porcentaje de cambio
            'strength': r_squared  # 0 a 1, donde 1 es tendencia fuerte
        }
    
    @staticmethod
    def get_trading_signal(prices: list, volume_data: Optional[list] = None) -> Dict[str, any]:
        """Generar señal de trading completa basada en múltiples indicadores"""
        if len(prices) < 26:  # Mínimo para MACD
            return {'direction': 'NEUTRAL', 'confidence': 0, 'signals': []}
        
        current_price = prices[-1]
        
        # Calcular indicadores
        rsi = TechnicalAnalyzer.calculate_rsi(prices)
        macd = TechnicalAnalyzer.calculate_macd(prices)
        bollinger = TechnicalAnalyzer.calculate_bollinger_bands(prices)
        sma_20 = TechnicalAnalyzer.calculate_sma(prices, 20)
        sma_50 = TechnicalAnalyzer.calculate_sma(prices, 50)
        trend = TechnicalAnalyzer.analyze_trend_strength(prices)
        
        signals = []
        confidence_score = 0
        
        # Señal RSI
        if rsi < 30:
            signals.append({'type': 'RSI', 'signal': 'OVERSOLD', 'strength': 0.7})
            confidence_score += 0.7
        elif rsi > 70:
            signals.append({'type': 'RSI', 'signal': 'OVERBOUGHT', 'strength': 0.7})
            confidence_score += 0.7
        
        # Señal MACD
        if macd['histogram'] > 0 and macd['macd'] > macd['signal']:
            signals.append({'type': 'MACD', 'signal': 'BULLISH', 'strength': 0.6})
            confidence_score += 0.6
        elif macd['histogram'] < 0 and macd['macd'] < macd['signal']:
            signals.append({'type': 'MACD', 'signal': 'BEARISH', 'strength': 0.6})
            confidence_score += 0.6
        
        # Señal Bandas de Bollinger
        if current_price < bollinger['lower']:
            signals.append({'type': 'BOLLINGER', 'signal': 'LOWER_BAND', 'strength': 0.5})
            confidence_score += 0.5
        elif current_price > bollinger['upper']:
            signals.append({'type': 'BOLLINGER', 'signal': 'UPPER_BAND', 'strength': 0.5})
            confidence_score += 0.5
        
        # Señal Medias Móviles
        if sma_20 > sma_50 and current_price > sma_20:
            signals.append({'type': 'MA', 'signal': 'GOLDEN_CROSS', 'strength': 0.8})
            confidence_score += 0.8
        elif sma_20 < sma_50 and current_price < sma_20:
            signals.append({'type': 'MA', 'signal': 'DEATH_CROSS', 'strength': 0.8})
            confidence_score += 0.8
        
        # Determinar dirección final
        bullish_signals = sum(1 for s in signals if 'BULLISH' in s['signal'] or 'OVERSOLD' in s['signal'] or 'LOWER_BAND' in s['signal'] or 'GOLDEN_CROSS' in s['signal'])
        bearish_signals = sum(1 for s in signals if 'BEARISH' in s['signal'] or 'OVERBOUGHT' in s['signal'] or 'UPPER_BAND' in s['signal'] or 'DEATH_CROSS' in s['signal'])
        
        if bullish_signals > bearish_signals:
            direction = 'LONG'
        elif bearish_signals > bullish_signals:
            direction = 'SHORT'
        else:
            direction = 'NEUTRAL'
        
        # Normalizar confianza
        max_confidence = len(signals) * 0.8  # Máximo posible
        final_confidence = min(confidence_score / max_confidence, 1.0) if max_confidence > 0 else 0
        
        return {
            'direction': direction,
            'confidence': final_confidence,
            'signals': signals,
            'indicators': {
                'rsi': rsi,
                'macd': macd,
                'bollinger': bollinger,
                'sma_20': sma_20,
                'sma_50': sma_50,
                'trend': trend
            }
        }
