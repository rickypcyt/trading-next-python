import os
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
        
    def initialize_client(self):
        """Inicializar cliente de Binance con API Keys"""
        try:
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_SECRET_KEY')
            
            if api_key and api_secret:
                self.client = Client(api_key, api_secret)
                print("🔐 Binance client initialized with API Keys")
                return True
            else:
                self.client = Client()
                print("⚠️  Binance client initialized without API Keys (public data only)")
                return False
        except Exception as e:
            print(f"❌ Error initializing Binance client: {e}")
            return False
    
    async def get_all_prices(self) -> Dict[str, float]:
        """Obtener precios actuales de todos los símbolos"""
        if not self.client:
            self.initialize_client()
        
        prices = {}
        try:
            for symbol in self.symbols:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                prices[symbol] = float(ticker['price'])
                self.last_update[symbol] = datetime.now()
        except Exception as e:
            print(f"❌ Error getting prices: {e}")
        
        return prices
    
    def get_historical_data(self, symbol: str, interval: str = '1h', limit: int = 24) -> List[Dict]:
        """Obtener datos históricos OHLCV"""
        if not self.client:
            self.initialize_client()
        
        try:
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
            return []
    
    def calculate_volatility(self, data: List[Dict]) -> float:
        """Calcular volatilidad a partir de datos históricos"""
        if len(data) < 2:
            return 0.02  # Default 2%
        
        returns = [(data[i]['close'] - data[i-1]['close']) / data[i-1]['close'] for i in range(1, len(data))]
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        return (variance ** 0.5) * 100  # Volatilidad en porcentaje

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
        
        # Simular resultado basado en análisis técnico
        success_probability = 0.65 + (analysis['market_condition']['confidence'] * 0.15)  # Realista: 65-80%
        is_successful = random.random() < success_probability
        
        # Calcular movimiento de precio basado en volatilidad real
        base_movement = max(analysis['volatility'] / 100, 0.001)
        price_movement = random.uniform(base_movement * 0.5, base_movement * 1.5)
        price_movement = min(price_movement, 0.05)  # limitar 5%
        
        if is_successful:
            # Ganancia basada en dirección
            if direction == TradeDirection.LONG:
                exit_price = current_price * (1 + price_movement)
            else:
                exit_price = current_price * (1 - price_movement)
        else:
            # Pérdida basada en dirección
            if direction == TradeDirection.LONG:
                exit_price = current_price * (1 - price_movement * 0.7)  # Pérdida menor que ganancia
            else:
                exit_price = current_price * (1 + price_movement * 0.7)
        
        # Simular tiempo de espera realista para el trade (10-120 segundos para trades inteligentes)
        trade_duration_seconds = random.uniform(10, 120)
        
        # Crear timestamps con separación realista
        entry_time = datetime.now()
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
            timestamp_entry=closed_trade.timestamp_entry.isoformat(),
            timestamp_exit=closed_trade.timestamp_exit.isoformat(),
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
            status="executed"
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
                    timestamp=datetime.now().isoformat(),
                    capital=round(self.current_capital, 2)
                )
                self.db.merge(equity)
                self.db.commit()
                
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
                    self.db.commit()
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
                timestamp=datetime.now().isoformat(),
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
        pnl_percentage = (trade.pnl / self.current_capital) * 100
        
        # Alertas de riesgo basadas en porcentaje
        if pnl_percentage < -3:  # Pérdida > 3% del capital
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="HIGH_RISK_LOSS",
                message=f"High risk loss: {trade.pnl:.2f} ({pnl_percentage:.1f}%) on {trade.symbol}"
            ))
        elif pnl_percentage > 5:  # Ganancia > 5% del capital
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="SIGNIFICANT_PROFIT",
                message=f"Significant profit: {trade.pnl:.2f} ({pnl_percentage:.1f}%) on {trade.symbol}"
            ))
        
        # Alertas de drawdown
        if self.current_drawdown > 15:  # Drawdown > 15%
            alerts.append(Alert(
                timestamp=datetime.now().isoformat(),
                type="CRITICAL_DRAWDOWN",
                message=f"Critical drawdown: {self.current_drawdown:.1f}% (${self.current_capital * self.current_drawdown/100:.2f})"
            ))
        
        # Alertas de estrategia
        if self.trades_count > 0:
            current_win_rate = self.winning_trades / self.trades_count
            if current_win_rate < 0.3:  # Win rate < 30%
                alerts.append(Alert(
                    timestamp=datetime.now().isoformat(),
                    type="LOW_WIN_RATE",
                    message=f"Low win rate: {current_win_rate:.1%} ({self.winning_trades}/{self.trades_count})"
                ))
        
        # Alertas de volatilidad
        symbol = trade.symbol.replace('/USD', 'USDT')
        if symbol in self.technical_data:
            volatility = self.technical_data[symbol]['volatility']
            if volatility > 5:  # Volatilidad > 5%
                alerts.append(Alert(
                    timestamp=datetime.now().isoformat(),
                    type="EXTREME_VOLATILITY",
                    message=f"Extreme volatility on {trade.symbol}: {volatility:.1f}%"
                ))
        
        return alerts

# Sistema de notificaciones mejorado
class NotificationManager:
    def __init__(self, websocket_connections):
        self.connections = websocket_connections
    
    async def broadcast_intelligent_update(self, data: Dict):
        """Enviar notificación inteligente con datos completos"""
        if not self.connections:
            return
        
        message = {
            "type": "intelligent_trade_generated",
            "message": f"Intelligent trade: {data['trade'].symbol} ({('+' if data['trade'].pnl > 0 else '')}${data['trade'].pnl:.2f})",
            "data": {
                "trade_id": data['trade'].id,
                "symbol": data['trade'].symbol,
                "strategy": data['trade'].strategy,
                "entry_price": data['trade'].entry_price,
                "exit_price": data['trade'].exit_price,
                "pnl": data['trade'].pnl,
                "pnl_percentage": (data['trade'].pnl / 100) * 100,  # Asumiendo $100 capital
                "capital": data['equity'].capital,
                "win_rate": data['metrics'].win_rate if data['metrics'] else 0,
                "total_trades": data.get('total_trades', 0),
                "current_drawdown": data.get('current_drawdown', 0),
                "prices": data.get('prices', {}),
                "analysis": data.get('analysis', {}),
                "alerts_count": len(data['alerts'])
            }
        }
        
        # Enviar a todos los clientes conectados
        for connection in self.connections.copy():
            try:
                await connection.send_text(json.dumps(message))
            except:
                self.connections.discard(connection)

# Función principal para ejecutar el sistema inteligente
async def run_intelligent_simulation(db_factory, notify_clients):
    """Ejecutar simulación inteligente cada 8 segundos"""
    notification_manager = NotificationManager(set())
    
    while True:
        try:
            db = next(db_factory())
            simulator = AdvancedTradingSimulator(db)
            
            # Ejecutar ciclo inteligente
            result = await simulator.run_intelligent_cycle()
            
            if result:
                # Actualizar contador de trades
                result['total_trades'] = simulator.trades_count
                result['current_drawdown'] = simulator.current_drawdown
                
                # Enviar notificación
                await notification_manager.broadcast_intelligent_update(result)
            
            db.close()
            
        except Exception as e:
            print(f"❌ Error in intelligent simulation: {e}")
        
        await asyncio.sleep(20)  # Intervalo de 20 segundos
