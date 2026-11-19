"""
Market Alert Generator - Sistema de alertas de oportunidades de trading
Analiza el mercado en tiempo real y genera señales de compra/venta
"""
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from database import Alert
from binance.client import Client
from technical_analyzer import TechnicalAnalyzer
import json

class AlertType(Enum):
    # Señales de Compra (LONG)
    STRONG_BUY_SIGNAL = "STRONG_BUY_SIGNAL"
    BUY_DIP = "BUY_DIP"
    SUPPORT_BOUNCE = "SUPPORT_BOUNCE"
    
    # Señales de Venta (SHORT)
    STRONG_SELL_SIGNAL = "STRONG_SELL_SIGNAL"
    SELL_TOP = "SELL_TOP"
    RESISTANCE_REJECTION = "RESISTANCE_REJECTION"
    
    # Momentum y Patrones
    BREAKOUT_ALERT = "BREAKOUT_ALERT"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    TREND_REVERSAL = "TREND_REVERSAL"
    CONSOLIDATION_BREAK = "CONSOLIDATION_BREAK"

@dataclass
class MarketSignal:
    symbol: str
    alert_type: AlertType
    message: str
    confidence: float  # 0-1
    price: float
    volume_ratio: float
    indicators: Dict[str, float]
    timestamp: datetime
    timeframe: str

class MarketAlertGenerator:
    """Generador de alertas de oportunidades de mercado"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = Client()  # Cliente público de Binance
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']
        self.timeframes = ['1h', '4h', '1d']
        self.min_confidence = 0.7  # Confianza mínima para generar alerta
        
        # Umbrales para alertas
        self.thresholds = {
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'price_change_pct': 3.0,
            'volume_spike_multiplier': 3.0,
            'support_resistance_touch_pct': 0.5,  # 0.5% de tolerancia
            'macd_signal_strength': 0.1
        }
    
    async def analyze_market_and_generate_alerts(self):
        """Analizar todos los símbolos y timeframes para generar alertas"""
        alerts_generated = []
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                try:
                    # Obtener datos del mercado
                    market_data = await self.get_market_data(symbol, timeframe)
                    if not market_data:
                        continue
                    
                    # Analizar y generar señales
                    signals = await self.analyze_symbol(symbol, timeframe, market_data)
                    
                    # Filtrar por confianza y guardar alertas
                    for signal in signals:
                        if signal.confidence >= self.min_confidence:
                            await self.save_market_alert(signal)
                            alerts_generated.append(signal)
                            print(f"🚨 Market Alert: {signal.alert_type.value} - {signal.message}")
                
                except Exception as e:
                    print(f"❌ Error analyzing {symbol} {timeframe}: {e}")
                    continue
        
        return alerts_generated
    
    async def get_market_data(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Obtener datos de mercado de Binance"""
        try:
            # Obtener velas sin bloquear el event loop
            klines = await asyncio.to_thread(
                self.client.get_klines,
                symbol=symbol,
                interval=self.client.KLINE_INTERVAL_1HOUR if timeframe == '1h' else 
                          self.client.KLINE_INTERVAL_4HOUR if timeframe == '4h' else 
                          self.client.KLINE_INTERVAL_1DAY,
                limit=100  # Últimas 100 velas
            )
            
            # Procesar datos
            closes = [float(k[4]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            
            # Precio actual
            ticker = await asyncio.to_thread(self.client.get_symbol_ticker, symbol=symbol)
            current_price = float(ticker['price'])
            
            # Análisis técnico
            technical_analysis = TechnicalAnalyzer.get_trading_signal(closes)
            
            # Calcular indicadores adicionales
            rsi = self.calculate_rsi(closes)
            macd = self.calculate_macd(closes)
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'closes': closes,
                'volumes': volumes,
                'highs': highs,
                'lows': lows,
                'technical_analysis': technical_analysis,
                'rsi': rsi[-1] if rsi else 50,
                'macd': macd,
                'avg_volume': np.mean(volumes),
                'current_volume': volumes[-1]
            }
            
        except Exception as e:
            print(f"❌ Error getting market data for {symbol}: {e}")
            return None
    
    async def analyze_symbol(self, symbol: str, timeframe: str, data: Dict) -> List[MarketSignal]:
        """Analizar un símbolo específico y generar señales"""
        signals = []
        
        # 1. Señales de Compra Fuerte
        if self.detect_strong_buy_signal(data):
            signals.append(MarketSignal(
                symbol=symbol,
                alert_type=AlertType.STRONG_BUY_SIGNAL,
                message=f"Fuerte señal de compra en {symbol}: RSI oversold + MACD bullish",
                confidence=0.85,
                price=data['current_price'],
                volume_ratio=data['current_volume'] / data['avg_volume'],
                indicators={'rsi': data['rsi'], 'macd': data['macd']['macd'] if data['macd'] else 0},
                timestamp=datetime.now(),
                timeframe=timeframe
            ))
        
        # 2. Oportunidad de Compra en Dip
        if self.detect_buy_dip(data):
            signals.append(MarketSignal(
                symbol=symbol,
                alert_type=AlertType.BUY_DIP,
                message=f"Oportunidad de compra: {symbol} en dip -{self.get_price_change_pct(data):.1f}% con volumen bajo",
                confidence=0.75,
                price=data['current_price'],
                volume_ratio=data['current_volume'] / data['avg_volume'],
                indicators={'price_change': self.get_price_change_pct(data)},
                timestamp=datetime.now(),
                timeframe=timeframe
            ))
        
        # 3. Señales de Venta Fuerte
        if self.detect_strong_sell_signal(data):
            signals.append(MarketSignal(
                symbol=symbol,
                alert_type=AlertType.STRONG_SELL_SIGNAL,
                message=f"Fuerte señal de venta: {symbol} overbought + MACD bearish",
                confidence=0.85,
                price=data['current_price'],
                volume_ratio=data['current_volume'] / data['avg_volume'],
                indicators={'rsi': data['rsi'], 'macd': data['macd']['macd'] if data['macd'] else 0},
                timestamp=datetime.now(),
                timeframe=timeframe
            ))
        
        # 4. Pico de Volumen Anómalo
        if self.detect_volume_spike(data):
            signals.append(MarketSignal(
                symbol=symbol,
                alert_type=AlertType.VOLUME_SPIKE,
                message=f"Pico de volumen: {symbol} volumen {data['current_volume']/data['avg_volume']:.1f}x con movimiento {self.get_price_change_pct(data):+.1f}%",
                confidence=0.80,
                price=data['current_price'],
                volume_ratio=data['current_volume'] / data['avg_volume'],
                indicators={'volume_ratio': data['current_volume']/data['avg_volume']},
                timestamp=datetime.now(),
                timeframe=timeframe
            ))
        
        # 5. Breakout Detector
        if self.detect_breakout(data):
            signals.append(MarketSignal(
                symbol=symbol,
                alert_type=AlertType.BREAKOUT_ALERT,
                message=f"Breakout detectado: {symbol} rompe nivel clave con volumen alto",
                confidence=0.78,
                price=data['current_price'],
                volume_ratio=data['current_volume'] / data['avg_volume'],
                indicators={'breakout_strength': self.get_price_change_pct(data)},
                timestamp=datetime.now(),
                timeframe=timeframe
            ))
        
        return signals
    
    def detect_strong_buy_signal(self, data: Dict) -> bool:
        """Detectar señales fuertes de compra"""
        return (
            data['rsi'] < self.thresholds['rsi_oversold'] and
            data['macd'] and
            data['macd'].get('macd', 0) > data['macd'].get('signal', 0) and
            self.get_price_change_pct(data) < -2.0
        )
    
    def detect_buy_dip(self, data: Dict) -> bool:
        """Detectar oportunidades de compra en dips"""
        price_change = self.get_price_change_pct(data)
        return (
            price_change < -self.thresholds['price_change_pct'] and
            data['current_volume'] < data['avg_volume'] * 0.8  # Volumen bajo
        )
    
    def detect_strong_sell_signal(self, data: Dict) -> bool:
        """Detectar señales fuertes de venta"""
        return (
            data['rsi'] > self.thresholds['rsi_overbought'] and
            data['macd'] and
            data['macd'].get('macd', 0) < data['macd'].get('signal', 0) and
            self.get_price_change_pct(data) > 2.0
        )
    
    def detect_volume_spike(self, data: Dict) -> bool:
        """Detectar picos de volumen anómalos"""
        volume_ratio = data['current_volume'] / data['avg_volume']
        return volume_ratio > self.thresholds['volume_spike_multiplier']
    
    def detect_breakout(self, data: Dict) -> bool:
        """Detectar breakouts de niveles clave"""
        # Lógica simplificada: precio cambia significativamente con volumen alto
        return (
            abs(self.get_price_change_pct(data)) > self.thresholds['price_change_pct'] and
            data['current_volume'] > data['avg_volume'] * 2.0
        )
    
    def get_price_change_pct(self, data: Dict) -> float:
        """Calcular cambio porcentual de precio"""
        if len(data['closes']) < 2:
            return 0.0
        current_price = data['closes'][-1]
        previous_price = data['closes'][-2]
        return ((current_price - previous_price) / previous_price) * 100
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calcular RSI"""
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
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calcular MACD"""
        if len(prices) < slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        # EMA rápida y lenta
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA del MACD)
        signal_line = self.calculate_ema(macd_line, signal)
        
        # Histogram
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line[-1] if len(macd_line) > 0 else 0,
            'signal': signal_line[-1] if len(signal_line) > 0 else 0,
            'histogram': histogram[-1] if len(histogram) > 0 else 0
        }
    
    def calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Calcular EMA"""
        if len(data) < period:
            return data
        
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        
        for i in range(1, len(data)):
            ema.append((data[i] * multiplier) + (ema[-1] * (1 - multiplier)))
        
        return ema
    
    async def save_market_alert(self, signal: MarketSignal):
        """Guardar alerta de mercado en la base de datos"""
        try:
            alert = Alert(
                timestamp=signal.timestamp.isoformat(),
                type=signal.alert_type.value,
                message=signal.message
            )
            
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)
            
            return alert
            
        except Exception as e:
            print(f"❌ Error saving market alert: {e}")
            self.db.rollback()
            return None

# Función para ejecutar el generador de alertas de mercado periódicamente
async def run_market_alert_generator(db_factory, notification_callback):
    """Ejecutar análisis de mercado y generar alertas periódicamente"""
    print("🚀 Starting Market Alert Generator...")
    
    while True:
        try:
            db = next(db_factory())
            generator = MarketAlertGenerator(db)
            
            # Analizar mercado y generar alertas
            alerts = await generator.analyze_market_and_generate_alerts()
            
            if alerts:
                # Notificar alertas importantes
                for alert in alerts:
                    await notification_callback({
                        "type": "market_alert",
                        "message": f"🚨 {alert.alert_type.value}: {alert.message}",
                        "data": {
                            "alert_id": f"market_{alert.timestamp.timestamp()}",
                            "symbol": alert.symbol,
                            "alert_type": alert.alert_type.value,
                            "confidence": alert.confidence,
                            "price": alert.price,
                            "timeframe": alert.timeframe,
                            "volume_ratio": alert.volume_ratio
                        }
                    })
                
                print(f"📊 Generated {len(alerts)} market alerts")
            
            db.close()
            
        except Exception as e:
            print(f"❌ Error in market alert generator: {e}")
        
        # Esperar 5 minutos para el siguiente análisis
        await asyncio.sleep(300)

# Instancia global del generador
market_alert_generator = None

def get_market_alert_generator(db: Session) -> MarketAlertGenerator:
    """Obtener instancia del generador de alertas de mercado"""
    global market_alert_generator
    if market_alert_generator is None:
        market_alert_generator = MarketAlertGenerator(db)
    return market_alert_generator
