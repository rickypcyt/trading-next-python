import os
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from binance.client import Client
from sqlalchemy.orm import Session
from database import Trade, EquityCurve, Metric, Alert
from execution_engine import execution_engine, TradeRequest, TradeDirection
import asyncio
import json
import random

class BinancePriceManager:
    def __init__(self):
        self.client = None
        self.prices = {}
        self.symbols = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,ADAUSDT,BNBUSDT').split(',')
        self.last_update = {}
        self.use_fallback = False
        
    def initialize_client(self):
        """Inicializar cliente de Binance con API Keys"""
        try:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_SECRET_KEY')
            
            if api_key and api_secret:
                self.client = Client(api_key, api_secret)
                self.use_fallback = False
                print("🔐 Binance client initialized with API Keys")
                return True
            else:
                self.client = Client()
                self.use_fallback = False
                print("⚠️  Binance client initialized without API Keys (public data only)")
                return False
        except Exception as e:
            print(f"❌ Error initializing Binance client: {e}")
            self.use_fallback = True
            return False
    
    async def get_all_prices(self) -> Dict[str, float]:
        """Obtener precios actuales de todos los símbolos"""
        if not self.client and not self.use_fallback:
            self.initialize_client()
        
        prices = {}
        try:
            for symbol in self.symbols:
                if self.use_fallback:
                    price = self._get_fallback_price(symbol)
                else:
                    try:
                        ticker = self.client.get_symbol_ticker(symbol=symbol)
                        price = float(ticker['price'])
                    except Exception as e:
                        print(f"❌ Error getting price for {symbol}: {e}" )
                        self.use_fallback = True
                        price = self._get_fallback_price(symbol)
                prices[symbol] = price
                self.prices[symbol] = price
                self.last_update[symbol] = datetime.now()
        except Exception as e:
            print(f"❌ Error getting prices: {e}")
            self.use_fallback = True
            for symbol in self.symbols:
                price = self._get_fallback_price(symbol)
                prices[symbol] = price
                self.last_update[symbol] = datetime.now()
        
        return prices
    
    def get_historical_data(self, symbol: str, interval: str = '1h', limit: int = 24) -> List[Dict]:
        """Obtener datos históricos OHLCV"""
        if not self.client and not self.use_fallback:
            self.initialize_client()
        
        try:
            if self.use_fallback:
                return self._generate_fallback_klines(symbol, limit)
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            data = []
            for k in klines:
                data.append({
                    'timestamp': datetime.fromtimestamp(int(k[0]) / 1000),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            return data
        except Exception as e:
            print(f"❌ Error getting historical data for {symbol}: {e}")
            self.use_fallback = True
            return self._generate_fallback_klines(symbol, limit)
    
    def calculate_volatility(self, data: List[Dict]) -> float:
        """Calcular volatilidad a partir de datos históricos"""
        if len(data) < 2:
            return 0.02  # Default 2%
        
        returns = [(data[i]['close'] - data[i-1]['close']) / data[i-1]['close'] for i in range(1, len(data))]
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        return (variance ** 0.5) * 100  # Volatilidad en porcentaje

    def _get_fallback_price(self, symbol: str) -> float:
        """Generar precio sintético cuando Binance no está disponible"""
        base_symbol = symbol.replace('USDT', '')
        base_price = self.prices.get(symbol)
        if base_price is None:
            seed_prices = {
                'BTC': 68000.0,
                'ETH': 3500.0,
                'BNB': 450.0,
                'SOL': 120.0,
                'XRP': 0.55,
                'ADA': 0.85
            }
            base_price = seed_prices.get(base_symbol, 100.0)
        # Aplicar pequeño movimiento aleatorio (±1%)
        drift = random.uniform(-0.01, 0.01)
        price = max(0.1, base_price * (1 + drift))
        self.prices[symbol] = price
        return price

    def _generate_fallback_klines(self, symbol: str, limit: int) -> List[Dict]:
        """Generar velas sintéticas para análisis técnico"""
        prices = []
        current_price = self._get_fallback_price(symbol)
        now = datetime.now()
        for i in range(limit):
            # Generar variaciones pequeñas basadas en volatilidad típica
            change_pct = random.uniform(-0.015, 0.015)
            open_price = current_price
            close_price = max(0.1, open_price * (1 + change_pct))
            high = max(open_price, close_price) * (1 + abs(change_pct) * 0.5)
            low = min(open_price, close_price) * (1 - abs(change_pct) * 0.5)
            volume = random.uniform(100, 1000)
            prices.append({
                'timestamp': now - timedelta(hours=limit - i),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close_price, 2),
                'volume': round(volume, 2)
            })
            current_price = close_price
        return prices

class AdvancedTradingSimulator:
    def __init__(self, db: Session):
        self.db = db
        self.price_manager = BinancePriceManager()
        self.price_manager.initialize_client()
        
        # Configuración desde .env
        self.initial_capital = float(os.getenv('INITIAL_CAPITAL', '100'))
        self.current_capital = self.initial_capital
        self.max_capital = self.initial_capital
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE_PERCENT', '3')) / 100
        
        self.current_drawdown = 0.0
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self._initialize_trading_state()
        
        # Estrategias disponibles
        self.strategies = [
            'MA_Cross',
            'RSI_Divergence', 
            'Bollinger_Bands',
            'MACD_Signal',
            'Volume_Breakout',
            'Support_Resistance'
        ]
        
        # Análisis técnico
        self.technical_data = {}
    
    def _initialize_trading_state(self):
        """Inicializar métricas usando los trades históricos en la base"""
        trades = self.db.query(Trade).order_by(Trade.timestamp_entry.asc()).all()
        equity = self.initial_capital
        max_equity = self.initial_capital

        for trade in trades:
            equity += trade.pnl
            max_equity = max(max_equity, equity)

        self.current_capital = equity
        self.max_capital = max_equity
        self.trades_count = len(trades)
        self.winning_trades = len([t for t in trades if t.pnl > 0])
        self.losing_trades = len([t for t in trades if t.pnl <= 0])
        self.current_drawdown = max(0, (self.max_capital - self.current_capital) / self.max_capital * 100) if self.max_capital else 0

    def update_technical_analysis(self, symbol: str):
        """Actualizar análisis técnico mejorado para un símbolo"""
        data = self.price_manager.get_historical_data(symbol, '1h', 50)
        if not data:
            return
        
        # Calcular indicadores básicos
        closes = [d['close'] for d in data]
        volumes = [d['volume'] for d in data]
        highs = [d['high'] for d in data]
        lows = [d['low'] for d in data]
        
        # Medias móviles mejoradas
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
        ema_12 = self.calculate_ema(closes, 12)
        ema_26 = self.calculate_ema(closes, 26)
        
        # Volatilidad mejorada
        volatility = self.price_manager.calculate_volatility(data)
        
        # Volumen análisis mejorado
        avg_volume = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volumes[-1]
        current_volume = volumes[-1] if volumes else avg_volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Tendencia mejorada con múltiples confirmaciones
        price_vs_sma20 = closes[-1] - sma_20
        price_vs_sma50 = closes[-1] - sma_50
        sma_trend = sma_20 - sma_50
        
        if price_vs_sma20 > 0 and price_vs_sma50 > 0 and sma_trend > 0:
            trend = 'bullish'
        elif price_vs_sma20 < 0 and price_vs_sma50 < 0 and sma_trend < 0:
            trend = 'bearish'
        else:
            trend = 'sideways'
        
        # RSI simulado
        rsi = self.calculate_rsi(closes, 14)
        
        # Soporte y resistencia dinámicos
        resistance = max(highs[-20:]) if len(highs) >= 20 else highs[-1]
        support = min(lows[-20:]) if len(lows) >= 20 else lows[-1]
        
        # Filtro de condición de mercado
        market_condition = self.assess_market_condition(volatility, trend, rsi, volume_ratio)
        
        self.technical_data[symbol] = {
            'sma_20': sma_20,
            'sma_50': sma_50,
            'ema_12': ema_12,
            'ema_26': ema_26,
            'volatility': volatility,
            'avg_volume': avg_volume,
            'current_volume': current_volume,
            'volume_ratio': volume_ratio,
            'trend': trend,
            'rsi': rsi,
            'resistance': resistance,
            'support': support,
            'market_condition': market_condition,
            'price_position': (closes[-1] - support) / (resistance - support) if resistance != support else 0.5,
            'current_price': closes[-1]  # Agregar precio actual
        }
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calcular EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calcular RSI simulado"""
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(change if change > 0 else 0)
            losses.append(abs(change) if change < 0 else 0)
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def assess_market_condition(self, volatility: float, trend: str, rsi: float, volume_ratio: float) -> str:
        """Evaluar condición general del mercado"""
        if volatility > 4:
            return 'high_volatility'
        elif volatility < 1 and trend == 'sideways':
            return 'low_activity'
        elif rsi > 70 or rsi < 30:
            return 'extreme_conditions'
        elif volume_ratio > 2:
            return 'high_volume'
        elif trend in ['bullish', 'bearish'] and 1 < volatility < 3:
            return 'trending_market'
        else:
            return 'normal'
    
    def generate_intelligent_trade(self, symbol: str = None) -> Optional[Trade]:
        """Generar trade inteligente con Execution Engine realista"""
        if symbol is None:
            symbol = random.choice(self.price_manager.symbols)
        
        # Actualizar análisis técnico
        self.update_technical_analysis(symbol)
        
        if symbol not in self.technical_data:
            return None
        
        analysis = self.technical_data[symbol]
        current_price = analysis['current_price']
        
        # Seleccionar estrategia basada en condiciones del mercado
        strategy = self.select_strategy(analysis)
        
        # Determinar dirección basada en análisis técnico
        direction = self.determine_direction(analysis, strategy)
        
        # Calcular stop loss basado en volatilidad y análisis técnico
        volatility = analysis['volatility'] / 100  # Convertir a decimal
        support = analysis['support']
        resistance = analysis['resistance']
        
        if direction == TradeDirection.LONG:
            # Stop loss debajo de soporte o volatilidad
            stop_loss = max(support * 0.98, current_price * (1 - max(0.02, volatility * 0.5)))
        else:
            # Stop loss encima de resistencia o volatilidad
            stop_loss = min(resistance * 1.02, current_price * (1 + max(0.02, volatility * 0.5)))
        
        # Crear solicitud de trade
        trade_request = TradeRequest(
            symbol=symbol,
            direction=direction,
            entry_price=current_price,
            size=0.0,  # Se calculará automáticamente
            stop_loss=stop_loss,
            strategy=strategy,
            volatility=analysis['volatility']  # Ya está en porcentaje
        )
        
        # Ejecutar trade con Execution Engine
        trade_result = execution_engine.execute_trade(
            trade_request,
            self.current_capital,
            risk_per_trade=0.02  # 2% de riesgo
        )

        signal_strength = self.calculate_signal_strength(analysis, strategy)
        exit_price = self.estimate_projected_exit_price(
            analysis=analysis,
            direction=direction,
            current_price=current_price,
            stop_loss=stop_loss,
            signal_strength=signal_strength
        )

        # Estimar duración del trade basada en condiciones actuales
        trade_duration_seconds = self.estimate_trade_duration(analysis)

        # Crear timestamps con separación realista
        entry_time = datetime.utcnow()
        exit_time = entry_time + timedelta(seconds=trade_duration_seconds)
        
        # Cerrar trade con Execution Engine
        closed_trade = execution_engine.close_trade(
            trade_result, 
            exit_price, 
            exit_reason="intelligent_simulation_close", 
            volatility=analysis['volatility']
        )
        
        # Sobrescribir timestamps para tener duración realista
        closed_trade.timestamp_entry = entry_time
        closed_trade.timestamp_exit = exit_time
        
        # Aplicar factor de riesgo basado en estrategia
        risk_factor = self.get_strategy_risk_factor(strategy)
        final_pnl = closed_trade.net_pnl * risk_factor
        
        # Convertir a formato de base de datos
        duration_ms = int((closed_trade.timestamp_exit - closed_trade.timestamp_entry).total_seconds() * 1000)

        trade = Trade(
            timestamp_entry=closed_trade.timestamp_entry,
            timestamp_exit=closed_trade.timestamp_exit,
            symbol=closed_trade.symbol.replace('USDT', '/USD'),
            strategy=closed_trade.strategy,
            entry_price=round(closed_trade.actual_entry_price, 2),
            exit_price=round(closed_trade.actual_exit_price, 2),
            size=round(closed_trade.position_size, 6),
            pnl=round(final_pnl, 2),
            duration_ms=duration_ms,
            entry_reason=closed_trade.entry_reason,
            exit_reason=closed_trade.exit_reason,
            source_engine="intelligent",
            direction=closed_trade.direction.value,
            status="executed",
            investment_amount=round(closed_trade.actual_entry_price * closed_trade.position_size, 2)
        )
        
        # Guardar información de costos para análisis
        execution_summary = execution_engine.get_execution_summary(closed_trade)
        print(f"🧠 Intelligent Trade {symbol}: PnL=${final_pnl:.2f}, Costs=${execution_summary['total_costs']:.4f}")
        
        return trade
    
    def select_strategy(self, analysis: Dict) -> str:
        """Seleccionar estrategia basada en condiciones del mercado mejoradas"""
        # Importar estrategias seleccionadas desde el backend
        try:
            import app
            available_strategies = getattr(app, 'selected_intelligent_strategies', 
                ['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance'])
        except:
            available_strategies = ['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance']
        
        volatility = analysis['volatility']
        trend = analysis['trend']
        rsi = analysis.get('rsi', 50)
        market_condition = analysis.get('market_condition', 'normal')
        volume_ratio = analysis.get('volume_ratio', 1)
        
        # Filtros inteligentes según condiciones del mercado
        if market_condition == 'high_volatility':
            # Alta volatilidad - estrategias conservadoras
            candidates = ['Support_Resistance', 'RSI_Divergence']
        elif market_condition == 'low_activity':
            # Baja actividad - evitar trades
            candidates = ['MA_Cross', 'MACD_Signal']  # Solo si hay tendencia clara
        elif market_condition == 'extreme_conditions':
            # Condiciones extremas RSI - reversiones
            candidates = ['RSI_Divergence', 'Bollinger_Bands']
        elif market_condition == 'trending_market':
            # Mercado en tendencia - seguir tendencia
            if trend == 'bullish':
                candidates = ['MA_Cross', 'Volume_Breakout', 'MACD_Signal']
            else:  # bearish
                candidates = ['RSI_Divergence', 'Support_Resistance']
        elif market_condition == 'high_volume':
            # Alto volumen - breakout y momentum
            candidates = ['Volume_Breakout', 'MACD_Signal', 'MA_Cross']
        else:  # normal
            # Condiciones normales - balanceado
            if 30 < rsi < 70:  # RSI normal
                if trend == 'bullish':
                    candidates = ['MA_Cross', 'MACD_Signal', 'Volume_Breakout']
                elif trend == 'bearish':
                    candidates = ['RSI_Divergence', 'Support_Resistance']
                else:  # sideways
                    candidates = ['Bollinger_Bands', 'MACD_Signal', 'Support_Resistance']
            else:  # RSI extremo
                candidates = ['RSI_Divergence', 'Bollinger_Bands']
        
        # Filtrar solo las estrategias disponibles y seleccionadas
        valid_candidates = [s for s in candidates if s in available_strategies]
        
        # Si no hay estrategias válidas, usar todas las disponibles
        if not valid_candidates:
            valid_candidates = available_strategies
        
        # Si no hay estrategias seleccionadas, usar todas por defecto
        if not valid_candidates:
            valid_candidates = ['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance']
        
        return random.choice(valid_candidates)
    
    def determine_direction(self, analysis: Dict, strategy: str) -> TradeDirection:
        """Determinar dirección del trade basado en análisis y estrategia mejorados"""
        # Factor de tendencia (aumentado para más precisión)
        trend_weight = 0.8 if analysis['trend'] == 'bullish' else -0.6 if analysis['trend'] == 'bearish' else 0
        
        # Factor de volumen mejorado
        current_volume = analysis.get('current_volume', analysis['avg_volume'])
        volume_weight = 0.4 if current_volume > analysis['avg_volume'] * 1.2 else -0.3 if current_volume < analysis['avg_volume'] * 0.8 else 0
        
        # Factor de estrategia optimizado para mayor win rate
        strategy_weights = {
            'MA_Cross': 0.3,           # Aumentado - más confiable en tendencia
            'RSI_Divergence': 0.2,     # Aumentado - mejor para reversiones
            'Bollinger_Bands': 0.1,    # Reducido - menos confiable
            'MACD_Signal': 0.25,       # Aumentado - buen momentum
            'Volume_Breakout': 0.15,   # Reducido - más riesgoso
            'Support_Resistance': 0.2  # Mantenido - confiable
        }
        
        # Factor de volatilidad para ajustar decisión
        volatility = analysis['volatility']
        volatility_adjustment = -0.2 if volatility > 4 else 0.1 if volatility < 1 else 0
        
        total_weight = trend_weight + volume_weight + strategy_weights.get(strategy, 0) + volatility_adjustment
        
        # Añadir umbral para evitar trades ambiguos
        if abs(total_weight) < 0.1:
            return TradeDirection.LONG if analysis['trend'] == 'bullish' else TradeDirection.SHORT if analysis['trend'] == 'bearish' else random.choice([TradeDirection.LONG, TradeDirection.SHORT])
        
        return TradeDirection.LONG if total_weight > 0 else TradeDirection.SHORT
    
    def get_strategy_risk_factor(self, strategy: str) -> float:
        """Obtener factor de riesgo para cada estrategia"""
        risk_factors = {
            'MA_Cross': 1.0,           # Moderado
            'RSI_Divergence': 0.7,       # Conservador
            'Bollinger_Bands': 1.2,      # Agresivo
            'MACD_Signal': 0.9,         # Moderado
            'Volume_Breakout': 1.3,      # Agresivo
            'Support_Resistance': 0.8   # Moderado
        }
        return risk_factors.get(strategy, 1.0)

    def calculate_signal_strength(self, analysis: Dict, strategy: str) -> float:
        """Calcular la fortaleza de la señal basada en análisis técnico."""
        strength = 0.0

        trend_bias = {
            'bullish': 0.6,
            'bearish': -0.6,
            'sideways': 0.0
        }
        strength += trend_bias.get(analysis.get('trend'), 0.0)

        volume_ratio = analysis.get('volume_ratio', 1)
        strength += (volume_ratio - 1) * 0.4

        rsi = analysis.get('rsi', 50)
        rsi_component = (50 - abs(rsi - 50)) / 50  # 0 (extremo) a 1 (equilibrado)
        strength += (rsi_component - 0.5) * 0.3

        volatility = analysis.get('volatility', 0)
        if volatility > 5:
            strength -= 0.3
        elif volatility < 1:
            strength += 0.1

        price_position = analysis.get('price_position', 0.5)
        strength += (price_position - 0.5) * 0.4

        strength += self.get_market_condition_bias(analysis.get('market_condition'))
        strength += self.get_strategy_bias(strategy)

        return max(-1.0, min(1.0, strength))

    def get_market_condition_bias(self, market_condition: Optional[str]) -> float:
        biases = {
            'trending_market': 0.25,
            'high_volume': 0.2,
            'normal': 0.1,
            'low_activity': -0.2,
            'high_volatility': -0.25,
            'extreme_conditions': -0.35
        }
        return biases.get(market_condition, 0.0)

    def get_strategy_bias(self, strategy: str) -> float:
        biases = {
            'MA_Cross': 0.15,
            'MACD_Signal': 0.12,
            'Volume_Breakout': 0.08,
            'Support_Resistance': 0.05,
            'RSI_Divergence': 0.0,
            'Bollinger_Bands': -0.05
        }
        return biases.get(strategy, 0.0)

    def estimate_projected_exit_price(
        self,
        analysis: Dict,
        direction: TradeDirection,
        current_price: float,
        stop_loss: float,
        signal_strength: float
    ) -> float:
        """Estimar precio de salida basado en la fortaleza de la señal y volatilidad."""
        volatility_pct = analysis.get('volatility', 0)
        base_movement = max(volatility_pct / 100, 0.002)

        sma_ratio = 0.0
        sma_20 = analysis.get('sma_20') or current_price
        sma_50 = analysis.get('sma_50') or current_price
        if sma_50:
            sma_ratio = (sma_20 - sma_50) / abs(sma_50)

        magnitude_multiplier = 0.35 + abs(signal_strength) * 0.45 + abs(sma_ratio) * 0.2
        projected_move_pct = base_movement * magnitude_multiplier

        if signal_strength < 0:
            projected_move_pct *= -1

        projected_price = current_price * (1 + projected_move_pct)

        if direction == TradeDirection.LONG and projected_price < stop_loss:
            projected_price = stop_loss
        elif direction == TradeDirection.SHORT and projected_price > stop_loss:
            projected_price = stop_loss

        # Limitar movimientos extremos al 6%
        max_move_pct = 0.06
        upper_bound = current_price * (1 + max_move_pct)
        lower_bound = current_price * (1 - max_move_pct)
        projected_price = max(lower_bound, min(upper_bound, projected_price))

        return projected_price

    def estimate_trade_duration(self, analysis: Dict) -> float:
        """Determinar duración estimada del trade basada en volatilidad y volumen."""
        volatility = analysis.get('volatility', 1)
        volume_ratio = max(analysis.get('volume_ratio', 1), 0.5)
        trend = analysis.get('trend', 'sideways')

        base_duration = 45.0 + (volatility * 4)
        if trend in ('bullish', 'bearish'):
            base_duration *= 1.2
        else:
            base_duration *= 0.9

        adjusted_duration = base_duration / volume_ratio
        return max(15.0, min(adjusted_duration, 240.0))
    
    async def run_intelligent_cycle(self):
        """Ejecutar ciclo de trading inteligente"""
        try:
            # 1. Obtener precios actualizados
            prices = await self.price_manager.get_all_prices()
            
            # 2. Generar trade para símbolo aleatorio
            trade = self.generate_intelligent_trade()
            
            if trade:
                # 3. Guardar trade en base de datos
                self.db.add(trade)
                self.db.commit()
                self.db.refresh(trade)
                
                # 4. Actualizar capital
                self.current_capital += trade.pnl
                self.max_capital = max(self.max_capital, self.current_capital)
                self.trades_count += 1
                
                if trade.pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # 5. Actualizar drawdown
                self.current_drawdown = max(0, (self.max_capital - self.current_capital) / self.max_capital * 100)
                
                # 6. Actualizar equity curve
                equity = EquityCurve(
                    timestamp=datetime.utcnow(),
                    capital=round(self.current_capital, 2)
                )
                self.db.add(equity)
                self.db.commit()
                self.db.refresh(equity)
                
                # 7. Calcular métricas
                metrics = self.calculate_comprehensive_metrics()
                if metrics:
                    self.db.add(metrics)
                    self.db.commit()
                    self.db.refresh(metrics)
                
                # 8. Generar alertas
                alerts = self.generate_intelligent_alerts(trade)
                for alert in alerts:
                    self.db.add(alert)
                if alerts:
                    self.db.commit()
                    for alert in alerts:
                        self.db.refresh(alert)
                
                return {
                    "trade": trade,
                    "equity": equity,
                    "metrics": metrics,
                    "alerts": alerts,
                    "prices": prices,
                    "analysis": self.technical_data
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error in intelligent cycle: {e}")
            self.db.rollback()
            return None
    
    def calculate_comprehensive_metrics(self) -> Optional[Metric]:
        """Calcular métricas completas del sistema"""
        try:
            trades = self.db.query(Trade).all()
            
            if not trades:
                return None
            
            # Métricas básicas
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl < 0]
            
            win_rate = len(winning_trades) / len(trades) if trades else 0
            
            total_pnl = sum(t.pnl for t in trades)
            
            # Sharpe Ratio simplificado
            if len(trades) > 1:
                returns_list = [t.pnl for t in trades]
                avg_return = sum(returns_list) / len(returns_list)
                variance = sum((r - avg_return) ** 2 for r in returns_list) / len(returns_list)
                sharpe = avg_return / (variance ** 0.5 + 0.0001) if variance > 0 else 0
            else:
                sharpe = 0
            
            # Profit Factor
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = gross_profit / (gross_loss + 0.0001) if gross_loss > 0 else float('inf')
            
            # Drawdown
            max_drawdown = self.current_drawdown
            
            # Win Rate por estrategia
            strategy_performance = {}
            for strategy in self.strategies:
                strategy_trades = [t for t in trades if t.strategy == strategy]
                if strategy_trades:
                    strategy_wins = [t for t in strategy_trades if t.pnl > 0]
                    strategy_performance[strategy] = len(strategy_wins) / len(strategy_trades)
            
            return Metric(
                timestamp=datetime.utcnow(),
                win_rate=round(win_rate, 4),
                sharpe=round(sharpe, 4),
                max_drawdown=round(max_drawdown, 2),
                profit_factor=round(profit_factor, 2)
            )
            
        except Exception as e:
            print(f"❌ Error calculating metrics: {e}")
            return None
    
    def generate_intelligent_alerts(self, trade: Trade) -> List[Alert]:
        """Genera alertas inteligentes basadas en análisis"""
        alerts = []
        invested_capital = (trade.entry_price or 0) * (trade.size or 0)
        pnl_percentage = (trade.pnl / invested_capital * 100) if invested_capital else 0
        
        # Alertas de riesgo basadas en porcentaje
        if pnl_percentage < -3:  # Pérdida > 3% del capital
            alerts.append(Alert(
                timestamp=datetime.utcnow(),
                type="HIGH_RISK_LOSS",
                message=f"High risk loss: {trade.pnl:.2f} ({pnl_percentage:.1f}%) on {trade.symbol}"
            ))
        elif pnl_percentage > 5:  # Ganancia > 5% del capital
            alerts.append(Alert(
                timestamp=datetime.utcnow(),
                type="SIGNIFICANT_PROFIT",
                message=f"Significant profit: {trade.pnl:.2f} ({pnl_percentage:.1f}%) on {trade.symbol}"
            ))
        
        # Alertas de drawdown
        if self.current_drawdown > 15:  # Drawdown > 15%
            alerts.append(Alert(
                timestamp=datetime.utcnow(),
                type="CRITICAL_DRAWDOWN",
                message=f"Critical drawdown: {self.current_drawdown:.1f}% (${self.current_capital * self.current_drawdown/100:.2f})"
            ))
        
        # Alertas de estrategia
        if self.trades_count > 0:
            current_win_rate = self.winning_trades / self.trades_count
            if current_win_rate < 0.3:  # Win rate < 30%
                alerts.append(Alert(
                    timestamp=datetime.utcnow(),
                    type="LOW_WIN_RATE",
                    message=f"Low win rate: {current_win_rate:.1%} ({self.winning_trades}/{self.trades_count})"
                ))
        
        # Alertas de volatilidad
        symbol = trade.symbol.replace('/USD', 'USDT')
        if symbol in self.technical_data:
            volatility = self.technical_data[symbol]['volatility']
            if volatility > 5:  # Volatilidad > 5%
                alerts.append(Alert(
                    timestamp=datetime.utcnow(),
                    type="EXTREME_VOLATILITY",
                    message=f"Extreme volatility on {trade.symbol}: {volatility:.1f}%"
                ))
        
        return alerts

# Sistema de notificaciones mejorado
class NotificationManager:
    def __init__(self, websocket_connections=None, fallback_broadcaster=None):
        self.connections = websocket_connections
        self.fallback_broadcaster = fallback_broadcaster
    
    async def broadcast_intelligent_update(self, data: Dict):
        """Enviar notificación inteligente con datos completos"""
        if not self.connections and not self.fallback_broadcaster:
            return

        trade = data['trade']
        equity = data['equity']
        metrics = data.get('metrics')
        invested_capital = (trade.entry_price or 0) * (trade.size or 0)
        pnl_percentage = (trade.pnl / invested_capital * 100) if invested_capital else 0

        message = {
            "type": "intelligent_trade_generated",
            "message": f"Intelligent trade: {trade.symbol} ({('+' if trade.pnl > 0 else '')}${trade.pnl:.2f})",
            "data": {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "strategy": trade.strategy,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "timestamp_entry": trade.timestamp_entry,
                "timestamp_exit": trade.timestamp_exit,
                "pnl": trade.pnl,
                "pnl_percentage": pnl_percentage,
                "capital": equity.capital,
                "win_rate": metrics.win_rate if metrics else 0,
                "total_trades": data.get('total_trades', 0),
                "current_drawdown": data.get('current_drawdown', 0),
                "prices": data.get('prices', {}),
                "analysis": data.get('analysis', {}),
                "alerts_count": len(data['alerts'])
            }
        }

        payload = json.dumps(message, default=self._serialize_datetime)

        if self.connections:
            for connection in self.connections.copy():
                try:
                    await connection.send_text(payload)
                except Exception:
                    self.connections.discard(connection)

        if self.fallback_broadcaster:
            await self.fallback_broadcaster(payload)

    @staticmethod
    def _serialize_datetime(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

# Función principal para ejecutar el sistema inteligente
async def run_intelligent_simulation(db_factory, websocket_connections=None, notify_clients=None):
    """Ejecutar simulación inteligente cada 20 segundos"""
    notification_manager = NotificationManager(websocket_connections, notify_clients)

    while True:
        db_generator = db_factory()
        try:
            db = next(db_generator)
        except StopIteration:
            print("❌ Unable to acquire database session for intelligent simulation")
            await asyncio.sleep(20)
            continue

        try:
            simulator = AdvancedTradingSimulator(db)

            # Ejecutar ciclo inteligente
            result = await simulator.run_intelligent_cycle()

            if result:
                result['total_trades'] = simulator.trades_count
                result['current_drawdown'] = simulator.current_drawdown

                await notification_manager.broadcast_intelligent_update(result)

        except Exception as e:
            print(f"❌ Error in intelligent simulation: {e}")
        finally:
            with suppress(StopIteration):
                next(db_generator)

        await asyncio.sleep(20)
