import numpy as np
from enum import Enum
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

class StrategyType(Enum):
    MARKET_MAKING = "market_making"
    SCALPING = "scalping"
    GRID_TRADING = "grid_trading"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT_MOMENTUM = "breakout_momentum"
    ARBITRAGE = "arbitrage"

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
    """Motor de estrategias avanzadas de trading"""
    
    def __init__(self, symbol: str, current_price: float, volatility: float):
        self.symbol = symbol
        self.current_price = current_price
        self.volatility = volatility
        self.price_history = []
        self.order_book = {'bids': [], 'asks': []}
        self.grid_levels: List[GridLevel] = []
        self.active_orders: List[MarketMakingOrder] = []
        
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
    
    def calculate_spread(self) -> float:
        """Calcular spread basado en volatilidad"""
        base_spread = 0.001  # 0.1% base
        volatility_adjustment = self.volatility * 0.5
        return max(base_spread, volatility_adjustment)
    
    def market_making_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 1: Market Making
        - Colocar órdenes de compra por debajo del precio actual
        - Colocar órdenes de venta por encima del precio actual
        - Ganar el spread entre bid/ask
        """
        spread = self.calculate_spread()
        orders = []
        
        # Calcular niveles de precio
        bid_price = self.current_price * (1 - spread/2)
        ask_price = self.current_price * (1 + spread/2)
        
        # Múltiples niveles de liquidez
        for i in range(3):  # 3 niveles cada lado
            level_spread = spread * (i + 1) * 0.5
            
            # Orden de compra (bid)
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=bid_price * (1 - level_spread),
                size=self.calculate_position_size(0.01),  # 1% riesgo
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),  # Menor confianza en niveles lejanos
                target_profit=ask_price * (1 + level_spread)
            )
            orders.append(buy_order)
            
            # Orden de venta (ask)
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=ask_price * (1 + level_spread),
                size=self.calculate_position_size(0.01),
                order_type='limit',
                strategy=StrategyType.MARKET_MAKING,
                confidence=0.8 - (i * 0.1),
                stop_loss=bid_price * (1 - level_spread)
            )
            orders.append(sell_order)
        
        return orders
    
    def scalping_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 2: Scalping Intradía
        - Entradas rápidas en pullbacks
        - Salidas rápidas con pequeñas ganancias
        - Alto volumen, pequeño riesgo por trade
        """
        if len(self.price_history) < 10:
            return []
        
        # Calcular media móvil corta
        recent_prices = [p['price'] for p in self.price_history[-10:]]
        sma_5 = np.mean(recent_prices[-5:])
        sma_10 = np.mean(recent_prices)
        
        orders = []
        
        # Detectar pullback para compra
        if (self.current_price < sma_5 and 
            self.current_price > sma_10 and 
            self.volatility < 0.03):  # Baja volatilidad para scalping
            
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=self.current_price,
                size=self.calculate_position_size(0.005),  # 0.5% riesgo
                order_type='market',
                strategy=StrategyType.SCALPING,
                confidence=0.7,
                target_profit=self.current_price * (1 + self.volatility * 0.5),  # Pequeña ganancia
                stop_loss=self.current_price * (1 - self.volatility * 0.3)
            )
            orders.append(buy_order)
        
        # Detectar pico para venta
        elif (self.current_price > sma_5 and 
              self.current_price < sma_10 and 
              self.volatility < 0.03):
            
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=self.current_price,
                size=self.calculate_position_size(0.005),
                order_type='market',
                strategy=StrategyType.SCALPING,
                confidence=0.7,
                target_profit=self.current_price * (1 - self.volatility * 0.5),
                stop_loss=self.current_price * (1 + self.volatility * 0.3)
            )
            orders.append(sell_order)
        
        return orders
    
    def grid_trading_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 3: Grid Trading
        - Red de órdenes buy/sell a diferentes niveles
        - Automatizar compra baja, venta alta
        - Funciona bien en mercados laterales
        """
        # Crear grid si no existe
        if not self.grid_levels:
            self.create_grid_levels()
        
        orders = []
        
        for level in self.grid_levels:
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
        
        return orders
    
    def mean_reversion_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 4: Mean Reversion
        - Comprar cuando el precio está muy por debajo de la media
        - Vender cuando está muy por encima de la media
        - Basado en que los precios vuelven a su promedio
        """
        if len(self.price_history) < 20:
            return []
        
        prices = [p['price'] for p in self.price_history[-20:]]
        mean_price = np.mean(prices)
        std_dev = np.std(prices)
        
        # Zonas de sobreventa/sobrecompra
        oversold_threshold = mean_price - 2 * std_dev
        overbought_threshold = mean_price + 2 * std_dev
        
        orders = []
        
        # Comprar en zona de sobreventa
        if self.current_price <= oversold_threshold:
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=self.current_price,
                size=self.calculate_position_size(0.02),  # 2% riesgo
                order_type='market',
                strategy=StrategyType.MEAN_REVERSION,
                confidence=0.85,  # Alta confianza en reversión a la media
                target_profit=mean_price,  # Objetivo: volver a la media
                stop_loss=self.current_price * (1 - std_dev)
            )
            orders.append(buy_order)
        
        # Vender en zona de sobrecompra
        elif self.current_price >= overbought_threshold:
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=self.current_price,
                size=self.calculate_position_size(0.02),
                order_type='market',
                strategy=StrategyType.MEAN_REVERSION,
                confidence=0.85,
                target_profit=mean_price,
                stop_loss=self.current_price * (1 + std_dev)
            )
            orders.append(sell_order)
        
        return orders
    
    def breakout_momentum_strategy(self) -> List[MarketMakingOrder]:
        """
        Estrategia 5: Breakout/Momentum
        - Seguir tendencias fuertes
        - Entrar en rupturas de soportes/resistencias
        - Dejar correr las ganancias
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
        
        orders = []
        
        # Breakout alcista
        if (self.current_price > resistance * 1.01 and  # 1% por encima de resistencia
            price_change > 0.02 and  # 2% de cambio positivo
            volume_proxy > 0.02):  # Volumen (volatilidad) decente
            
            buy_order = MarketMakingOrder(
                side=OrderSide.BUY,
                price=self.current_price,
                size=self.calculate_position_size(0.025),  # 2.5% riesgo
                order_type='market',
                strategy=StrategyType.BREAKOUT_MOMENTUM,
                confidence=0.75,
                target_profit=self.current_price * (1 + self.volatility * 3),  # Dejar correr
                stop_loss=resistance  # Stop en resistencia rota
            )
            orders.append(buy_order)
        
        # Breakout bajista
        elif (self.current_price < support * 0.99 and  # 1% por debajo de soporte
              price_change < -0.02 and  # 2% de cambio negativo
              volume_proxy > 0.02):
            
            sell_order = MarketMakingOrder(
                side=OrderSide.SELL,
                price=self.current_price,
                size=self.calculate_position_size(0.025),
                order_type='market',
                strategy=StrategyType.BREAKOUT_MOMENTUM,
                confidence=0.75,
                target_profit=self.current_price * (1 - self.volatility * 3),
                stop_loss=support
            )
            orders.append(sell_order)
        
        return orders
    
    def create_grid_levels(self):
        """Crear niveles de grid trading"""
        grid_spacing = self.current_price * self.volatility * 0.5
        num_levels = 10
        
        self.grid_levels = []
        
        for i in range(-num_levels, num_levels + 1):
            level_price = self.current_price * (1 + i * grid_spacing / self.current_price)
            
            if i < 0:  # Niveles de compra
                side = OrderSide.BUY
            elif i > 0:  # Niveles de venta
                side = OrderSide.SELL
            else:
                continue  # Saltar nivel central
            
            grid_level = GridLevel(
                price=level_price,
                side=side,
                order_size=self.calculate_position_size(0.01)
            )
            self.grid_levels.append(grid_level)
    
    def calculate_position_size(self, risk_percentage: float) -> float:
        """Calcular tamaño de posición basado en riesgo"""
        # Simplificado: usar porcentaje fijo del capital
        # En producción, esto usaría el capital real disponible
        base_position = 1000  # $1000 base
        return base_position * risk_percentage / self.current_price
    
    def get_all_strategy_signals(self) -> List[MarketMakingOrder]:
        """Obtener señales de todas las estrategias"""
        all_orders = []
        
        # Ejecutar todas las estrategias
        all_orders.extend(self.market_making_strategy())
        all_orders.extend(self.scalping_strategy())
        all_orders.extend(self.grid_trading_strategy())
        all_orders.extend(self.mean_reversion_strategy())
        all_orders.extend(self.breakout_momentum_strategy())
        
        # Filtrar por confianza
        filtered_orders = [order for order in all_orders if order.confidence > 0.6]
        
        # Ordenar por confianza
        filtered_orders.sort(key=lambda x: x.confidence, reverse=True)
        
        return filtered_orders[:5]  # Top 5 órdenes
    
    def get_strategy_summary(self) -> Dict:
        """Resumen de todas las estrategias"""
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
