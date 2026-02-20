import numpy as np
from enum import Enum
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import random

from risk_settings import ACCOUNT_CAPITAL

class RiskLevel(Enum):
    CONSERVATIVE = "conservative"  # 10% risk
    MODERATE = "moderate"         # 25% risk  
    AGGRESSIVE = "aggressive"     # 50% risk

class StrategyType(Enum):
    MARKET_MAKING = "market_making"
    SCALPING = "scalping"
    GRID_TRADING = "grid_trading"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT_MOMENTUM = "breakout_momentum"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class MarketMakingOrder:
    """Orden para estrategia de market making"""
    side: OrderSide
    price: float
    size: float
    order_type: str  # 'limit', 'market'
    strategy: StrategyType
    confidence: float
    target_profit: Optional[float] = None
    stop_loss: Optional[float] = None

@dataclass
class GridLevel:
    """Nivel para grid trading"""
    price: float
    side: OrderSide
    order_size: float
    filled: bool = False
    timestamp: Optional[datetime] = None

class AdvancedStrategyEngine:
    """Motor de estrategias avanzadas de trading con niveles de riesgo"""
    
    def __init__(self, symbol: str, current_price: float, volatility: float, risk_level: RiskLevel = RiskLevel.MODERATE, capital: Optional[float] = None, leverage: float = 1.0):
        self.symbol = symbol
        self.current_price = current_price
        self.volatility = volatility
        self.risk_level = risk_level
        self.capital = capital if capital is not None else ACCOUNT_CAPITAL  # Capital real disponible
        self.leverage = leverage  # Apalancamiento para futures/perpetuos
        self.price_history = []
        self.order_book = {'bids': [], 'asks': []}
        self.grid_levels: List[GridLevel] = []
        self.active_orders: List[MarketMakingOrder] = []
        
        # Trading fees (configurables por exchange)
        self.maker_fee = 0.0002   # 0.02% maker fee
        self.taker_fee = 0.0005   # 0.05% taker fee (conservador)
        
        # Position tracking real
        self.net_position = 0.0  # Posición neta en base asset (+long, -short)
        self.avg_entry_price = 0.0  # Precio promedio de entrada
        
        # Cache para estrategia ejecutadas (evitar doble cómputo)
        self._strategy_cache = {}
        self._cache_timestamp = None
        self._cache_ttl_seconds = 1  # Cache válido por 1 segundo
        
        # Funding rate para perpetuals (placeholder)
        self.funding_rate = 0.0001  # 0.01% por defecto (8 horas)
        self.last_funding_time = datetime.now()
        
        # Configuración de riesgo
        self.risk_config = self._get_risk_config()
        
    def _get_risk_config(self) -> Dict:
        """Obtener configuración según nivel de riesgo"""
        configs = {
            RiskLevel.CONSERVATIVE: {
                'base_risk': 0.10,  # 10% riesgo base
                'position_multiplier': 0.5,  # Mitad de tamaño
                'confidence_threshold': 0.7,  # Mayor confianza requerida
                'max_orders_per_strategy': 3,
                'spread_multiplier': 0.8,  # Spreads más anchos
                'stop_loss_multiplier': 1.5,  # Stops más ajustados
                'grid_levels': 8,  # Menos niveles de grid
                'volatility_threshold': 0.02  # Umbral de volatilidad más bajo
            },
            RiskLevel.MODERATE: {
                'base_risk': 0.25,  # 25% riesgo base
                'position_multiplier': 1.0,  # Tamaño normal
                'confidence_threshold': 0.6,
                'max_orders_per_strategy': 5,
                'spread_multiplier': 1.0,
                'stop_loss_multiplier': 2.0,
                'grid_levels': 10,
                'volatility_threshold': 0.03
            },
            RiskLevel.AGGRESSIVE: {
                'base_risk': 0.50,  # 50% riesgo base
                'position_multiplier': 2.0,  # Doble tamaño
                'confidence_threshold': 0.5,  # Menor confianza requerida
                'max_orders_per_strategy': 8,
                'spread_multiplier': 1.2,  # Spreads más competitivos
                'stop_loss_multiplier': 2.5,  # Stops más amplios
                'grid_levels': 15,  # Más niveles de grid
                'volatility_threshold': 0.05  # Umbral de volatilidad más alto
            }
        }
        return configs.get(self.risk_level, configs[RiskLevel.MODERATE])
        
    def update_price(self, new_price: float, timestamp: datetime = None):
        """Actualizar precio y mantener historial"""
        self.current_price = new_price
        if timestamp is None:
            timestamp = datetime.now()
        
        self.price_history.append({
            'price': new_price,
            'timestamp': timestamp,
            'volatility': self.volatility
        })
        
        # Mantener solo últimos 100 precios
        if len(self.price_history) > 100:
            self.price_history = self.price_history[-100:]
        
        # Invalidar cache cuando el precio cambia
        self._invalidate_cache()
        self._maybe_update_funding_rate(timestamp)

    def update_funding_rate(self, new_rate: Optional[float] = None):
        """Actualizar funding rate (simulación simple o valor externo)"""
        if new_rate is None:
            drift = random.uniform(-0.0001, 0.0001)
            updated_rate = self.funding_rate + drift
        else:
            updated_rate = new_rate

        self.funding_rate = max(-0.005, min(0.005, updated_rate))
        self.last_funding_time = datetime.now()

    def _maybe_update_funding_rate(self, current_time: datetime):
        if current_time - self.last_funding_time >= timedelta(hours=8):
            self.update_funding_rate()
    
    def get_inventory_imbalance(self) -> float:
        """
        Net exposure: +1.0 = 100% long, -1.0 = 100% short, 0 = neutral
        Calcula el desbalance de inventario de órdenes activas
        """
        if not self.active_orders:
            return 0.0
        
        long_size = sum(o.size for o in self.active_orders if o.side == OrderSide.BUY)
        short_size = sum(o.size for o in self.active_orders if o.side == OrderSide.SELL)
        total = long_size + short_size
        
        return (long_size - short_size) / total if total > 0 else 0.0
    
    def calculate_spread(self) -> float:
        """
        Calcular spread basado en volatilidad con límites y spreads específicos por símbolo
        Ajustado según nivel de riesgo configurado
        """
        # Spreads base por liquidez (datos reales Binance 2026)
        SYMBOL_SPREADS = {
            'BTCUSDT': 0.0003,  # Top tier
            'ETHUSDT': 0.0004,
            'BNBUSDT': 0.0008,
            'SOLUSDT': 0.0015,  # Media
            'XRPUSDT': 0.0020,
            'ADAUSDT': 0.0030,  # Baja liquidez
        }
        
        base_spread = SYMBOL_SPREADS.get(self.symbol, 0.002)  # Default conservador
        
        # Ajuste por volatilidad (0-50%)
        vol_multiplier = max(0.5, min(1.5, 1 + self.volatility * 2))
        
        # Ajuste por nivel de riesgo
        risk_multiplier = self.risk_config['spread_multiplier']
        
        spread = base_spread * vol_multiplier * risk_multiplier
        
        return min(spread, 0.01)  # Cap al 1%
    
    def _generate_ask_orders_only(self, spread: float) -> List[MarketMakingOrder]:
        """Generar solo órdenes de venta para reducir inventario long"""
        orders = []
        ask_price = self.current_price * (1 + spread/2)
        
        for i in range(3):
            level_spread = spread * (i + 1) * 0.5
            sell_price = ask_price * (1 + level_spread)
            
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=sell_price,
                size=self.calculate_position_size(0.01),
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),
                target_profit=sell_price * (1 - spread),
                stop_loss=sell_price * (1 + spread * 2)
            )
            orders.append(sell_order)
        
        return orders
    
    def _generate_bid_orders_only(self, spread: float) -> List[MarketMakingOrder]:
        """Generar solo órdenes de compra para reducir inventario short"""
        orders = []
        bid_price = self.current_price * (1 - spread/2)
        
        for i in range(3):
            level_spread = spread * (i + 1) * 0.5
            buy_price = bid_price * (1 - level_spread)
            
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=buy_price,
                size=self.calculate_position_size(0.01),
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),
                target_profit=buy_price * (1 + spread),
                stop_loss=buy_price * (1 - spread * 2)
            )
            orders.append(buy_order)
        
        return orders
    
    def _balanced_market_making(self, spread: float) -> List[MarketMakingOrder]:
        """Market making balanceado con inventario neutral y ajuste por riesgo"""
        orders = []
        bid_price = self.current_price * (1 - spread/2)
        ask_price = self.current_price * (1 + spread/2)
        
        # Número de niveles según riesgo
        max_levels = self.risk_config['max_orders_per_strategy'] // 2
        
        for i in range(max_levels):
            level_spread = spread * (i + 1) * 0.5
            
            # Orden de compra (bid)
            buy_price = bid_price * (1 - level_spread)
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=buy_price,
                size=self.calculate_position_size(self.risk_config['base_risk']),
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),
                target_profit=ask_price * (1 + level_spread),
                stop_loss=buy_price * (1 - spread * self.risk_config['stop_loss_multiplier'])
            )
            orders.append(buy_order)
            
            # Orden de venta (ask)
            sell_price = ask_price * (1 + level_spread)
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=sell_price,
                size=self.calculate_position_size(self.risk_config['base_risk']),
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),
                target_profit=bid_price * (1 - level_spread),
                stop_loss=sell_price * (1 + spread * self.risk_config['stop_loss_multiplier'])
            )
            orders.append(sell_order)
        
        return orders
    
    def market_making_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 1: Market Making Optimizado
        - Balanceo de inventario dinámico
        - Spreads específicos por símbolo
        - Stop-loss dinámico basado en spread (2x)
        - Priorización según desbalance de inventario
        """
        if self.is_trending_market():
            return []

        spread = self.calculate_spread()
        imbalance = self.get_inventory_imbalance()
        
        # Si muy long → priorizar SELLS para reducir inventario
        if imbalance > 0.3:
            return self._generate_ask_orders_only(spread * 1.2)
        # Si muy short → priorizar BUYS para reducir inventario
        elif imbalance < -0.3:
            return self._generate_bid_orders_only(spread * 1.2)
        else:
            # Market making balanceado
            orders = self._balanced_market_making(spread)
            
            # Reducir número de órdenes si hay desbalance moderado
            if abs(imbalance) > 0.2:
                return orders[:6]  # Mitad de órdenes
            else:
                return orders
    
    def scalping_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 2: Scalping Intradía con ajuste por riesgo
        - Entradas rápidas en pullbacks durante tendencias claras
        - Ordenes LIMIT con offset para evitar taker fees
        - Salidas rápidas con pequeñas ganancias
        """
        if len(self.price_history) < 10:
            return []
        
        # Calcular medias móviles
        recent_prices = [p['price'] for p in self.price_history[-10:]]
        sma_5 = np.mean(recent_prices[-5:])
        sma_10 = np.mean(recent_prices)
        
        orders = []
        
        # Umbral de volatilidad según riesgo
        vol_threshold = self.risk_config['volatility_threshold']
        
        # Offset para limit orders (0.05-0.1% para evitar taker fees)
        limit_offset = 0.0008  # 0.08% offset
        
        # Detectar tendencia alcista y pullback para compra
        if (sma_5 > sma_10 and  # Tendencia alcista
            self.current_price < sma_5 and  # Pullback por debajo de SMA corta
            self.current_price > sma_10 and  # Pero aún por encima de SMA larga
            self.volatility < vol_threshold):  # Volatilidad según riesgo
            
            if self.is_funding_favorable("long"):
                # LIMIT order por debajo del precio actual
                limit_price = self.current_price * (1 - limit_offset)
                
                buy_order = MarketMakingOrder(
                    side=OrderSide.BUY,
                    price=limit_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.5),  # Mitad de riesgo base
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.SCALPING,
                    confidence=0.7,
                    target_profit=self.calculate_fee_adjusted_target(
                        limit_price, 
                        limit_price * (1 + self.volatility * 0.5), 
                        is_buy=True
                    ),
                    stop_loss=limit_price * (1 - self.volatility * 0.3)
                )
                orders.append(buy_order)
        
        # Detectar tendencia bajista y pullback para venta
        elif (sma_5 < sma_10 and  # Tendencia bajista
              self.current_price > sma_5 and  # Pullback por encima de SMA corta
              self.current_price < sma_10 and  # Pero aún por debajo de SMA larga
              self.volatility < vol_threshold):
            
            if self.is_funding_favorable("short"):
                # LIMIT order por encima del precio actual
                limit_price = self.current_price * (1 + limit_offset)
                
                sell_order = MarketMakingOrder(
                    side=OrderSide.SELL,
                    price=limit_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.5),
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.SCALPING,
                    confidence=0.7,
                    target_profit=self.calculate_fee_adjusted_target(
                        limit_price,
                        limit_price * (1 - self.volatility * 0.5),
                        is_buy=False
                    ),
                    stop_loss=limit_price * (1 + self.volatility * 0.3)
                )
                orders.append(sell_order)
        
        return orders
    
    def grid_trading_strategy(self, mutate_levels: bool = True) -> List[MarketMakingOrder]:
        """
        Estrategia 3: Grid Trading con gestión individual de niveles
        - Red de órdenes buy/sell a diferentes niveles
        - Automatizar compra baja, venta alta
        - Funciona bien en mercados laterales
        - Gestión individual del ciclo de vida de cada nivel
        """
        # Crear grid si no existe
        if not self.grid_levels:
            self.create_grid_levels()
        
        # Verificar si necesitamos resetear el grid
        if self.should_reset_grid():
            self.create_grid_levels()
        
        orders = []
        
        for i, level in enumerate(self.grid_levels):
            if not level.filled:
                # Verificar si el precio cruzó este nivel
                if (level.side == OrderSide.BUY and 
                    self.current_price <= level.price):
                    
                    order = MarketMakingOrder(
                        side=OrderSide.BUY,
                        price=level.price,
                        size=level.order_size,
                        order_type='limit',
                        strategy=StrategyType.GRID_TRADING,
                        confidence=0.9,  # Alta confianza en niveles predefinidos
                        target_profit=level.price * (1 + self.volatility)
                    )
                    orders.append(order)
                    
                    if mutate_levels:
                        level.filled = True
                        level.timestamp = datetime.now()
                    
                    # Programar reset automático después de cierto tiempo (opcional)
                    # Esto permite que el nivel esté disponible nuevamente
                    # después de que la orden se ejecute o expire
                    
                elif (level.side == OrderSide.SELL and 
                      self.current_price >= level.price):
                    
                    order = MarketMakingOrder(
                        side=OrderSide.SELL,
                        price=level.price,
                        size=level.order_size,
                        order_type='limit',
                        strategy=StrategyType.GRID_TRADING,
                        confidence=0.9,
                        stop_loss=level.price * (1 - self.volatility)
                    )
                    orders.append(order)
                    
                    if mutate_levels:
                        level.filled = True
                        level.timestamp = datetime.now()
        
        return orders

    def _mark_grid_level_fill(self, price: float, side: OrderSide):
        """Marcar un nivel de grid como ejecutado tras confirmación en exchange."""
        if not self.grid_levels:
            return

        tolerance = price * 0.0001  # 1 bps de tolerancia en comparación de precios
        for idx, level in enumerate(self.grid_levels):
            if level.side == side and abs(level.price - price) <= tolerance:
                level.filled = True
                level.timestamp = datetime.now()
                # Permitir reutilizar el nivel cuando se resetee explícitamente
                break
    
    def mean_reversion_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 4: Mean Reversion con KILL SWITCH automático
        - SOLO opera en mercados laterales seguros
        - Detecta y evita squeezes y tendencias fuertes
        - Ordenes LIMIT con offset para mejor ejecución
        - Targets ajustados por fees
        """
        # 🔥 KILL SWITCH - Verificar condiciones de seguridad
        if not self.is_mean_reversion_safe():
            return []  # ❌ NO OPERAR - Peligro detectado
        
        if len(self.price_history) < 20:
            return []
        
        prices = [p['price'] for p in self.price_history[-20:]]
        mean_price = np.mean(prices)
        std_dev = np.std(prices)
        
        # Zonas de sobreventa/sobrecompra
        oversold_threshold = mean_price - 2 * std_dev
        overbought_threshold = mean_price + 2 * std_dev
        
        orders = []
        
        # Offset para limit orders
        limit_offset = 0.0005  # 0.05% offset
        
        # Comprar en zona de sobreventa
        if self.current_price <= oversold_threshold:
            if self.is_funding_favorable("long"):
                # LIMIT order ligeramente por debajo del precio actual
                limit_price = self.current_price * (1 - limit_offset)
                
                buy_order = MarketMakingOrder(
                    side=OrderSide.BUY,
                    price=limit_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.8),  # 80% del riesgo base
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.MEAN_REVERSION,
                    confidence=0.85,  # Alta confianza en reversión a la media
                    target_profit=self.calculate_fee_adjusted_target(
                        limit_price,
                        mean_price,  # Objetivo: volver a la media
                        is_buy=True
                    ),
                    stop_loss=limit_price - (2 * std_dev)
                )
                orders.append(buy_order)
        
        # Vender en zona de sobrecompra
        elif self.current_price >= overbought_threshold:
            if self.is_funding_favorable("short"):
                # LIMIT order ligeramente por encima del precio actual
                limit_price = self.current_price * (1 + limit_offset)
                
                sell_order = MarketMakingOrder(
                    side=OrderSide.SELL,
                    price=limit_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.8),
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.MEAN_REVERSION,
                    confidence=0.85,
                    target_profit=self.calculate_fee_adjusted_target(
                        limit_price,
                        mean_price,
                        is_buy=False
                    ),
                    stop_loss=limit_price + (2 * std_dev)
                )
                orders.append(sell_order)
        
        return orders
    
    def breakout_momentum_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 5: Breakout/Momentum con limit orders agresivas
        - Seguir tendencias fuertes con confirmación
        - Usar limit orders para evitar taker fees altos
        - Chase breakout con pricing agresivo
        - Requerir confirmación de tendencia y momentum
        """
        if len(self.price_history) < 30:
            return []
        
        # Calcular soporte y resistencia
        prices = [p['price'] for p in self.price_history[-30:]]
        support = min(prices)
        resistance = max(prices)
        
        # Calcular momentum
        price_change = (self.current_price - prices[0]) / prices[0]
        volume_proxy = self.volatility  # Usar volatilidad como proxy de volumen
        
        # Calcular EMAs para confirmación de tendencia
        ema_short = self.calculate_ema(prices, 10)
        ema_long = self.calculate_ema(prices, 20)
        
        orders = []
        
        # Breakout alcista con limit order agresivo
        if (self.current_price > resistance * 1.01 and  # 1% por encima de resistencia
            price_change > 0.02 and  # 2% de cambio positivo
            volume_proxy > 0.02 and  # Volumen (volatilidad) decente
            ema_short > ema_long):  # Confirmación de tendencia alcista
            
            # Ajustar umbral de cambio según volatilidad
            volatility_threshold = max(0.02, self.volatility * 2)
            if price_change > volatility_threshold and self.is_funding_favorable("long"):
                # Limit order agresivo para chase breakout
                chase_price = resistance * 1.005  # 0.5% por encima de resistencia
                
                buy_order = MarketMakingOrder(
                    side=OrderSide.BUY,
                    price=chase_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.025),  # 2.5% riesgo
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.BREAKOUT_MOMENTUM,
                    confidence=0.75,
                    target_profit=self.calculate_fee_adjusted_target(
                        chase_price,
                        chase_price * (1 + self.volatility * 3),  # Dejar correr
                        is_buy=True
                    ),
                    stop_loss=resistance  # Stop en resistencia rota
                )
                orders.append(buy_order)
        
        # Breakout bajista con limit order agresivo
        elif (self.current_price < support * 0.99 and  # 1% por debajo de soporte
              price_change < -0.02 and  # 2% de cambio negativo
              volume_proxy > 0.02 and  # Volumen decente
              ema_short < ema_long):  # Confirmación de tendencia bajista
            
            # Ajustar umbral de cambio según volatilidad
            volatility_threshold = max(0.02, self.volatility * 2)
            if abs(price_change) > volatility_threshold and self.is_funding_favorable("short"):
                # Limit order agresivo para chase breakout
                chase_price = support * 0.995  # 0.5% por debajo de soporte
                
                sell_order = MarketMakingOrder(
                    side=OrderSide.SELL,
                    price=chase_price,
                    size=self.calculate_position_size(self.risk_config['base_risk'] * 0.025),
                    order_type='limit',  # Cambiado de 'market' a 'limit'
                    strategy=StrategyType.BREAKOUT_MOMENTUM,
                    confidence=0.75,
                    target_profit=self.calculate_fee_adjusted_target(
                        chase_price,
                        chase_price * (1 - self.volatility * 3),
                        is_buy=False
                    ),
                    stop_loss=support
                )
                orders.append(sell_order)
        
        return orders
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calcular RSI usando el método Wilder (EMA-based) - estándar de la industria"""
        if len(prices) < period + 1:
            return 50.0  # Neutral si no hay suficientes datos
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Método Wilder: usar EMA suavizada en vez de simple mean
        alpha = 1.0 / period  # Factor de suavizado Wilder
        
        # Inicializar primer valor con el promedio simple del primer período
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        # Aplicar EMA de Wilder para el resto de valores
        for i in range(period, len(gains)):
            avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def is_short_squeeze_conditions(self) -> bool:
        """Detectar squeezes antes de que exploten - KILL SWITCH"""
        if len(self.price_history) < 20:
            return False
        
        prices = [p['price'] for p in self.price_history[-20:]]
        rsi = self.calculate_rsi(prices)
        
        # Detectar spike de volatilidad
        recent_vol = np.std(prices[-5:]) / np.mean(prices[-5:])
        historical_vol = np.std(prices) / np.mean(prices)
        vol_spike = recent_vol / historical_vol if historical_vol > 0 else 1
        
        # Condiciones de peligro
        rsi_extreme = rsi > 75 or rsi < 25
        vol_extreme = vol_spike > 2.0  # 2x volatilidad normal
        high_volatility = self.volatility > 0.03  # >3%
        
        return rsi_extreme or vol_extreme or high_volatility
    
    def is_trending_market(self) -> bool:
        """Detectar mercado en tendencia fuerte = no mean reversion"""
        if len(self.price_history) < 20:
            return False
        
        prices = [p['price'] for p in self.price_history[-20:]]
        
        # Calcular EMAs
        ema_short = self.calculate_ema(prices, 10)
        ema_long = self.calculate_ema(prices, 20)
        
        # Slope de la tendencia
        slope = abs(ema_short - ema_long) / ema_long
        
        # Detectar breakout reciente
        recent_high = max(prices[-5:])
        recent_low = min(prices[-5:])
        older_range = max(prices[:-5]) - min(prices[:-5])
        
        breakout = (recent_high - recent_low) > older_range * 0.8
        
        return slope > 0.02 or breakout  # >2% slope o breakout fuerte
    
    def is_mean_reversion_safe(self) -> bool:
        """Verificar si es seguro usar mean reversion"""
        if self.is_short_squeeze_conditions():
            return False  # ❌ NO operar
        
        if self.is_trending_market():
            return False  # ❌ NO operar
        
        # Condiciones adicionales de seguridad
        if len(self.price_history) < 20:
            return False
        
        # Verificar rango lateral (2-5%)
        prices = [p['price'] for p in self.price_history[-20:]]
        price_range = (max(prices) - min(prices)) / np.mean(prices)
        
        return 0.02 <= price_range <= 0.05  # ✅ Rango perfecto para MR
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calcular EMA para confirmación de tendencia"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def smart_reversion_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia Híbrida Inteligente:
        - Mean Reversion cuando el mercado es lateral seguro
        - Momentum cuando el mercado está en tendencia
        - Cambio automático según condiciones del mercado
        """
        if self.is_mean_reversion_safe():
            # ✅ Mercado lateral seguro → Mean Reversion
            return self.mean_reversion_strategy()
        elif self.is_trending_market():
            # ✅ Mercado en tendencia → Momentum
            return self.breakout_momentum_strategy()
        else:
            # ❌ Condiciones ambiguas → No operar
            return []

    def is_funding_favorable(self, direction: str = "long") -> bool:
        if direction == "long" and self.funding_rate > 0.0005:
            return False

        if direction == "short" and self.funding_rate < -0.0005:
            return False

        return True
    
    def reset_individual_grid_level(self, level_index: int):
        """Resetear un nivel individual del grid (ej: después de ejecución)"""
        if 0 <= level_index < len(self.grid_levels):
            level = self.grid_levels[level_index]
            level.filled = False
            level.timestamp = None
            # Opcional: recalcular order_size con capital actual
            level.order_size = self.calculate_position_size(self.risk_config['base_risk'] * 0.4)
    
    def reset_filled_grid_levels(self):
        """Resetear solo los niveles llenados, mantener los vacíos"""
        for i, level in enumerate(self.grid_levels):
            if level.filled:
                self.reset_individual_grid_level(i)
    
    def get_grid_level_status(self) -> Dict:
        """Obtener estado detallado de los niveles del grid"""
        filled_levels = [i for i, level in enumerate(self.grid_levels) if level.filled]
        empty_levels = [i for i, level in enumerate(self.grid_levels) if not level.filled]
        
        return {
            'total_levels': len(self.grid_levels),
            'filled_levels': len(filled_levels),
            'empty_levels': len(empty_levels),
            'filled_indices': filled_levels,
            'empty_indices': empty_levels,
            'fill_percentage': len(filled_levels) / len(self.grid_levels) * 100 if self.grid_levels else 0
        }
    
    def should_reset_grid(self) -> bool:
        """Determinar si el grid debe resetearse cuando el precio se aleja demasiado"""
        if not self.grid_levels:
            return False
        
        # Obtener precios extremos del grid
        grid_prices = [level.price for level in self.grid_levels]
        min_grid_price = min(grid_prices)
        max_grid_price = max(grid_prices)
        
        # Resetear si el precio está más del 50% fuera del rango del grid
        grid_range = max_grid_price - min_grid_price
        margin = grid_range * 0.5
        
        return (self.current_price < min_grid_price - margin or 
                self.current_price > max_grid_price + margin)
    
    def calculate_atr(self, period: int = 14) -> float:
        """
        Calcular Average True Range - Proxy mejorado con Wilder EMA
        
        NOTA: Sin datos OHLCV completos, este es un proxy mejorado que usa:
        - Cambio absoluto entre velas consecutivas
        - Wilder EMA para suavizado (estándar de la industria)
        
        Para ATR real se necesitarían datos OHLCV completos
        """
        if len(self.price_history) < period + 1:
            return self.volatility * self.current_price  # Fallback a volatilidad
        
        # Extraer precios de cierre
        closes = [p['price'] for p in self.price_history[-period-1:]]
        
        trs = []

        for i in range(1, len(closes)):
            close_delta = abs(closes[i] - closes[i - 1])
            simulated_high = close_delta * (1 + self.volatility * 0.5)
            simulated_low = close_delta * (1 - self.volatility * 0.5)
            tr = max(close_delta, simulated_high, simulated_low)
            trs.append(tr)
        
        if not trs:
            return self.volatility * self.current_price
        
        # Wilder EMA para ATR (estándar de la industria)
        atr = trs[0]  # Inicializar con primer TR
        alpha = 1.0 / period  # Factor de suavizado Wilder
        
        for tr in trs[1:]:
            atr = alpha * tr + (1 - alpha) * atr
        
        return atr
    
    def create_grid_levels(self):
        """Crear niveles de grid trading mejorados con spacing mínimo y sizing progresivo"""
        # Spacing dinámico con ATR o volatilidad, mínimo 0.3%
        atr = self.calculate_atr()
        atr_percentage = atr / self.current_price
        grid_spacing = max(atr_percentage * 1.0, self.volatility * 0.6, 0.003)  # ATR realista, mínimo 0.3%

        if grid_spacing < 0.001:
            grid_spacing = 0.003
        
        num_levels = self.risk_config['grid_levels']
        self.grid_levels = []
        
        for i in range(1, num_levels + 1):
            # Compra abajo (más agresivo cerca del precio)
            buy_spacing_multiplier = 1.2 if i <= 3 else 1.0  # Más cerca los primeros 3 niveles
            buy_price = self.current_price * (1 - i * grid_spacing * buy_spacing_multiplier)
            
            # Sizing decreciente (martingala inversa)
            buy_size_multiplier = 0.7 ** (i - 1)  # 0.7, 0.49, 0.34, ...
            buy_size = self.calculate_position_size(self.risk_config['base_risk'] * 0.4 * buy_size_multiplier)
            
            self.grid_levels.append(GridLevel(
                price=buy_price,
                side=OrderSide.BUY,
                order_size=buy_size
            ))
            
            # Venta arriba (spacing normal)
            sell_price = self.current_price * (1 + i * grid_spacing)
            sell_size_multiplier = 0.7 ** (i - 1)
            sell_size = self.calculate_position_size(self.risk_config['base_risk'] * 0.4 * sell_size_multiplier)
            
            self.grid_levels.append(GridLevel(
                price=sell_price,
                side=OrderSide.SELL,
                order_size=sell_size
            ))
    
    def calculate_position_size(self, risk_percentage: float, use_leverage: bool = True) -> float:
        """Calcular tamaño de posición basado en riesgo, capital real y apalancamiento"""
        # Ajustar riesgo base según configuración del nivel
        adjusted_risk = risk_percentage * self.risk_config['position_multiplier']
        
        # Calcular monto de riesgo en USD
        risk_amount = self.capital * adjusted_risk  # ej: $250 riesgo
        
        # Aplicar apalancamiento si se especifica
        if use_leverage and self.leverage > 1.0:
            notional_value = risk_amount * self.leverage  # con 10x → $2500 exposición
        else:
            notional_value = risk_amount
        
        # Calcular tamaño en unidades del activo
        position_size = notional_value / self.current_price
        
        # Límites duros (evitar liquidación fácil)
        max_notional = self.capital * self.leverage * 5  # no más de 5x capital total
        max_position = max_notional / self.current_price
        position_size = min(position_size, max_position)
        
        return position_size
    
    def adjust_price_for_fees(self, price: float, is_buy: bool, is_maker: bool = False) -> float:
        """Ajustar precio considerando fees de trading"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        
        if is_buy:
            # Para compra: precio + fee
            return price * (1 + fee_rate)
        else:
            # Para venta: precio - fee
            return price * (1 - fee_rate)
    
    def calculate_fee_adjusted_target(self, entry_price: float, desired_target: float, is_buy: bool) -> float:
        """Ajusta el target deseado para compensar fees round-trip (maker si limit)"""
        entry_fee_rate = self.maker_fee
        exit_fee_rate = self.maker_fee
        round_trip_fee = entry_fee_rate + exit_fee_rate

        if round_trip_fee > 0.01:
            logging.warning(
                "Round-trip fee %.4f (>1%%) detected for %s. Consider reducing aggressiveness.",
                round_trip_fee,
                self.symbol,
            )

        if is_buy:
            return desired_target * (1 + round_trip_fee / max(1e-9, (1 - round_trip_fee)))

        return desired_target * (1 - round_trip_fee / (1 + round_trip_fee))
    
    def on_fill(self, side: OrderSide, size: float, price: float, is_maker: bool = False):
        """Actualizar posición real cuando se ejecuta una orden (longs y shorts)"""
        if size <= 0:
            return

        fee_rate = self.maker_fee if is_maker else self.taker_fee
        trade_value = size * price
        trade_fees = trade_value * fee_rate
        fill_size = size
        remaining_size = size
        fees_remaining = trade_fees
        
        if side == OrderSide.BUY:
            if self.net_position < 0:
                close_size = min(remaining_size, abs(self.net_position))
                fees_close = trade_fees * (close_size / fill_size)
                gross_pnl = (self.avg_entry_price - price) * close_size
                net_pnl = gross_pnl - fees_close
                self.capital += net_pnl
                fees_remaining -= fees_close
                self.net_position += close_size
                remaining_size -= close_size
                if self.net_position == 0:
                    self.avg_entry_price = 0.0
            if remaining_size > 0:
                new_total = self.net_position + remaining_size
                if self.net_position == 0:
                    self.avg_entry_price = price
                else:
                    self.avg_entry_price = ((self.avg_entry_price * self.net_position) + (price * remaining_size)) / new_total
                self.net_position = new_total
                self.capital -= fees_remaining
        else:
            if self.net_position > 0:
                close_size = min(remaining_size, self.net_position)
                fees_close = trade_fees * (close_size / fill_size)
                gross_pnl = (price - self.avg_entry_price) * close_size
                net_pnl = gross_pnl - fees_close
                self.capital += net_pnl
                fees_remaining -= fees_close
                self.net_position -= close_size
                remaining_size -= close_size
                if self.net_position == 0:
                    self.avg_entry_price = 0.0
            if remaining_size > 0:
                short_size_before = abs(self.net_position)
                new_total = self.net_position - remaining_size
                total_short = abs(new_total)
                if total_short > 0:
                    if short_size_before == 0:
                        self.avg_entry_price = price
                    else:
                        self.avg_entry_price = ((self.avg_entry_price * short_size_before) + (price * remaining_size)) / total_short
                self.net_position = new_total
                self.capital -= fees_remaining
        
        unrealized_pnl = ((self.current_price - self.avg_entry_price) * self.net_position) if self.net_position != 0 else 0.0
        print(
            f"💰 Fill: {side.value} {fill_size:.6f} @ ${price:.2f} | Fees: ${trade_fees:.4f} | Capital: ${self.capital:.2f} | UnrealizedPnL: ${unrealized_pnl:.2f}"
        )

        if side in (OrderSide.BUY, OrderSide.SELL):
            self._mark_grid_level_fill(price, side)
    
    def get_liquidation_price(self) -> float:
        """
        Calcular precio de liquidación usando fórmula real de Binance Futures
        Fórmula: Entry Price * (1 - Maintenance Margin / Leverage)
        """
        if self.net_position == 0 or self.avg_entry_price == 0:
            return 0.0
        
        # Maintenance margin rates (Binance 2026)
        maintenance_margin_rates = {
            'BTCUSDT': 0.005,   # 0.5%
            'ETHUSDT': 0.005,   # 0.5%
            'SOLUSDT': 0.01,    # 1.0%
            'XRPUSDT': 0.01,    # 1.0%
            'ADAUSDT': 0.01,    # 1.0%
        }
        
        maintenance_margin = maintenance_margin_rates.get(self.symbol, 0.01)  # Default 1%
        
        if self.net_position > 0:  # Posición LONG
            # Liquidación cuando el precio cae
            liquidation_price = self.avg_entry_price * (1 - maintenance_margin / self.leverage)
        else:  # Posición SHORT
            # Liquidación cuando el precio sube
            liquidation_price = self.avg_entry_price * (1 + maintenance_margin / self.leverage)
        
        return liquidation_price
    
    def get_liquidation_distance(self) -> Dict:
        """
        Calcular distancia al precio de liquidación en porcentaje y USD
        """
        if self.net_position == 0:
            return {
                'liquidation_price': 0.0,
                'distance_percentage': 0.0,
                'distance_usd': 0.0,
                'is_safe': True
            }
        
        liq_price = self.get_liquidation_price()
        
        if self.net_position > 0:  # LONG
            distance_pct = (self.current_price - liq_price) / self.current_price * 100
            distance_usd = (self.current_price - liq_price) * abs(self.net_position)
        else:  # SHORT
            distance_pct = (liq_price - self.current_price) / self.current_price * 100
            distance_usd = (liq_price - self.current_price) * abs(self.net_position)
        
        # Considerar seguro si está a más del 20% de distancia
        is_safe = distance_pct > 20.0
        
        return {
            'liquidation_price': liq_price,
            'distance_percentage': distance_pct,
            'distance_usd': distance_usd,
            'is_safe': is_safe,
            'risk_level': 'LOW' if distance_pct > 50 else 'MEDIUM' if distance_pct > 20 else 'HIGH'
        }
    def get_position_info(self) -> Dict:
        """Obtener información detallada de la posición actual"""
        liquidation_info = self.get_liquidation_distance()
        
        return {
            'net_position': self.net_position,
            'avg_entry_price': self.avg_entry_price,
            'position_value': self.net_position * self.current_price,
            'unrealized_pnl': (self.current_price - self.avg_entry_price) * self.net_position if self.net_position != 0 else 0,
            'leverage_used': self.leverage,
            'available_capital': self.capital,
            'margin_used': abs(self.net_position * self.avg_entry_price) / self.leverage if self.net_position != 0 else 0,
            'liquidation_price': liquidation_info['liquidation_price'],
            'liquidation_distance_pct': liquidation_info['distance_percentage'],
            'liquidation_risk': liquidation_info['risk_level'],
            'is_safe_from_liquidation': liquidation_info['is_safe']
        }
    
    def update_capital(self, new_capital: float):
        """Actualizar capital disponible (para PnL real)"""
        self.capital = max(0, new_capital)  # No permitir capital negativo
    
    def get_capital_allocation(self) -> Dict:
        """Obtener distribución de capital real basada en posición y margen actual"""
        position_info = self.get_position_info()
        
        # Calcular margen usado por posición actual
        margin_used = position_info['margin_used']
        
        # Calcular capital disponible real
        # Capital total - margen usado - buffer de seguridad (5%)
        safety_buffer = self.capital * 0.05
        available_capital = max(0, self.capital - margin_used - safety_buffer)
        
        # Calcular exposición total (posición + órdenes activas)
        total_exposure = abs(position_info['position_value'])
        for order in self.active_orders:
            total_exposure += order.size * order.price
        
        return {
            'total_capital': round(self.capital, 2),
            'available_capital': round(available_capital, 2),
            'margin_used': round(margin_used, 2),
            'safety_buffer': round(safety_buffer, 2),
            'position_value': round(position_info['position_value'], 2),
            'total_exposure': round(total_exposure, 2),
            'exposure_pct': round((total_exposure / self.capital * 100) if self.capital > 0 else 0, 2),
            'risk_per_trade': round(self.capital * self.risk_config['base_risk'], 2),
            'max_position_size': round(self.calculate_position_size(self.risk_config['base_risk']), 6),
            'leverage_utilization': round((margin_used / self.capital * 100) if self.capital > 0 else 0, 2),
            'available_for_new_trades': round(available_capital * 0.8, 2)  # 80% del disponible para nuevas operaciones
        }
    
    def _is_cache_valid(self) -> bool:
        """Verificar si el cache de estrategias es válido"""
        if self._cache_timestamp is None:
            return False
        
        import time
        current_time = time.time()
        return (current_time - self._cache_timestamp) < self._cache_ttl_seconds
    
    def _invalidate_cache(self):
        """Invalidar cache de estrategias"""
        self._strategy_cache = {}
        self._cache_timestamp = None
    
    def _get_cached_strategies(self) -> Dict[str, List]:
        """Obtener estrategias desde cache o calcularlas"""
        if self._is_cache_valid():
            return self._strategy_cache.copy()
        
        # Calcular todas las estrategias
        all_orders = {}
        
        # Ejecutar todas las estrategias
        mm_orders = self.market_making_strategy()
        if mm_orders:
            all_orders['market_making'] = mm_orders
            
        scalping_orders = self.scalping_strategy()
        if scalping_orders:
            all_orders['scalping'] = scalping_orders
            
        grid_orders = self.grid_trading_strategy(mutate_levels=False)
        if grid_orders:
            all_orders['grid_trading'] = grid_orders
            
        mr_orders = self.mean_reversion_strategy()
        if mr_orders:
            all_orders['mean_reversion'] = mr_orders
            
        breakout_orders = self.breakout_momentum_strategy()
        if breakout_orders:
            all_orders['breakout_momentum'] = breakout_orders
        
        # Guardar en cache
        import time
        self._strategy_cache = all_orders
        self._cache_timestamp = time.time()
        
        return all_orders.copy()
    
    def get_all_strategy_signals(self) -> List[MarketMakingOrder]:
        """Obtener señales de todas las estrategias con filtro por confianza según riesgo"""
        # Obtener estrategias cacheadas
        cached_strategies = self._get_cached_strategies()
        
        # Aplanar todas las órdenes
        all_orders = []
        for strategy_orders in cached_strategies.values():
            all_orders.extend(strategy_orders)
        
        # Filtrar por confianza según configuración de riesgo
        confidence_threshold = self.risk_config['confidence_threshold']
        filtered_orders = [order for order in all_orders if order.confidence > confidence_threshold]
        
        # Ordenar por confianza
        filtered_orders.sort(key=lambda x: x.confidence, reverse=True)
        
        # Limitar número de órdenes según riesgo
        max_orders = self.risk_config['max_orders_per_strategy']
        
        return filtered_orders[:max_orders]
    
    def get_all_raw_signals(self) -> List[MarketMakingOrder]:
        """
        Obtener todas las señales crudas sin filtrar por confianza
        
        Returns:
            List[MarketMakingOrder]: Todas las órdenes generadas por todas las estrategias
        """
        # Obtener estrategias cacheadas
        cached_strategies = self._get_cached_strategies()
        
        # Aplanar todas las órdenes sin filtrar
        all_orders = []
        for strategy_orders in cached_strategies.values():
            all_orders.extend(strategy_orders)
        
        return all_orders
    
    def get_strategy_summary(self) -> Dict:
        """
        Resumen de todas las estrategias (basado en top 5 filtrado por confianza)
        
        Nota: Este resumen muestra la distribución de las señales que pasaron
        el filtro de confianza (>0.6) y están en el top 5. Para ver todas las
        señales crudas sin filtrar, usar get_all_raw_signals().
        """
        all_orders = self.get_all_strategy_signals()
        
        strategy_counts = {}
        for strategy in StrategyType:
            strategy_counts[strategy.value] = len([o for o in all_orders if o.strategy == strategy])
        
        return {
            'total_signals': len(all_orders),
            'strategy_distribution': strategy_counts,
            'avg_confidence': np.mean([o.confidence for o in all_orders]) if all_orders else 0,
            'current_price': self.current_price,
            'volatility': self.volatility,
            'grid_levels_count': len(self.grid_levels),
            'price_history_length': len(self.price_history)
        }
