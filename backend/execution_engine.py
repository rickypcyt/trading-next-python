import math
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"

class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"

@dataclass
class ExecutionConfig:
    """Configuración de costos de ejecución"""
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0004  # 0.04%
    spread_pct: float = 0.0001  # 0.01%
    slippage_base_pct: float = 0.0001  # 0.01% base
    slippage_volatility_factor: float = 0.5  # Factor de volatilidad para slippage
    min_slippage_pct: float = 0.0001  # 0.01% mínimo
    max_slippage_pct: float = 0.0003  # 0.03% máximo

@dataclass
class TradeRequest:
    """Solicitud de trade original"""
    symbol: str
    direction: TradeDirection
    entry_price: float
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = ""
    volatility: Optional[float] = None  # Volatilidad para cálculo de slippage

@dataclass
class TradeResult:
    """Resultado del trade con costos reales"""
    symbol: str
    direction: TradeDirection
    strategy: str
    
    # Precios reales de ejecución
    requested_entry_price: float
    actual_entry_price: float
    requested_exit_price: Optional[float]
    actual_exit_price: Optional[float]
    
    # Tamaños y costos
    position_size: float
    entry_fees: float
    exit_fees: float
    slippage_cost: float
    spread_cost: float
    
    # Resultados
    gross_pnl: float
    net_pnl: float
    pnl_percentage: float
    
    # Timing
    timestamp_entry: datetime
    timestamp_exit: Optional[datetime]
    
    # Metadatos
    entry_reason: str
    exit_reason: str
    confidence: float = 0.0

class ExecutionEngine:
    """Motor de ejecución realista con fees, slippage y spread"""
    
    def __init__(self, config: ExecutionConfig = None):
        self.config = config or ExecutionConfig()
    
    def calculate_slippage(self, price: float, volatility: Optional[float] = None) -> float:
        """
        Calcular slippage basado en volatilidad
        
        Args:
            price: Precio del activo
            volatility: Volatilidad (opcional, si None usa base)
        
        Returns:
            Porcentaje de slippage (decimal)
        """
        if volatility is None:
            # Slippage base sin datos de volatilidad
            slippage_pct = self.config.slippage_base_pct
        else:
            # Slippage escalado por volatilidad
            volatility_factor = min(volatility / 100, 1.0)  # Normalizar volatilidad
            slippage_pct = (self.config.slippage_base_pct + 
                          (volatility_factor * self.config.slippage_volatility_factor * 0.0002))
        
        # Limitar entre mínimo y máximo
        slippage_pct = max(self.config.min_slippage_pct, 
                          min(slippage_pct, self.config.max_slippage_pct))
        
        return slippage_pct
    
    def calculate_spread_adjustment(self, price: float, direction: TradeDirection) -> float:
        """
        Calcular ajuste por spread
        
        Args:
            price: Precio base
            direction: Dirección del trade
        
        Returns:
            Precio ajustado por spread
        """
        spread_amount = price * self.config.spread_pct / 2
        
        if direction == TradeDirection.LONG:
            # Compramos al precio + spread/2
            return price + spread_amount
        else:
            # Vendemos al precio - spread/2
            return price - spread_amount
    
    def apply_fees(self, price: float, size: float, order_type: OrderType = OrderType.MARKET) -> float:
        """
        Calcular fees de transacción
        
        Args:
            price: Precio de ejecución
            size: Tamaño de posición
            order_type: Tipo de orden (maker/taker)
        
        Returns:
            Costo total de fees
        """
        fee_rate = self.config.maker_fee if order_type == OrderType.LIMIT else self.config.taker_fee
        notional_value = price * size
        return notional_value * fee_rate
    
    def calculate_position_size(self, capital: float, risk_per_trade: float, 
                              entry_price: float, stop_loss: float) -> float:
        """
        Calcular tamaño de posición basado en gestión de riesgo
        
        Args:
            capital: Capital disponible
            risk_per_trade: Porcentaje de riesgo por trade (decimal)
            entry_price: Precio de entrada
            stop_loss: Precio de stop loss
        
        Returns:
            Tamaño de posición en unidades del activo
        """
        if stop_loss == 0 or entry_price == stop_loss:
            return 0.0
        
        # Riesgo monetario por trade
        risk_amount = capital * risk_per_trade
        
        # Riesgo por unidad del activo
        price_risk_per_unit = abs(entry_price - stop_loss)
        
        if price_risk_per_unit == 0:
            return 0.0
        
        # Tamaño de posición para arriesgar exactamente risk_amount
        position_size = risk_amount / price_risk_per_unit
        
        # Limitar a máximo 20% del capital en una posición
        max_position_value = capital * 0.2
        max_size_by_capital = max_position_value / entry_price
        
        return min(position_size, max_size_by_capital)
    
    def execute_trade(self, request: TradeRequest, capital: float, 
                     risk_per_trade: float = 0.02) -> TradeResult:
        """
        Ejecutar trade con costos realistas
        
        Args:
            request: Solicitud de trade
            capital: Capital disponible
            risk_per_trade: Riesgo por trade (decimal)
        
        Returns:
            TradeResult con costos reales aplicados
        """
        # Calcular tamaño de posición si no se proporciona
        if request.size == 0 and request.stop_loss:
            request.size = self.calculate_position_size(
                capital, risk_per_trade, request.entry_price, request.stop_loss
            )
        
        # Aplicar spread al precio de entrada
        spread_adjusted_entry = self.calculate_spread_adjustment(
            request.entry_price, request.direction
        )
        
        # Calcular slippage
        slippage_pct = self.calculate_slippage(spread_adjusted_entry, request.volatility)
        slippage_amount = spread_adjusted_entry * slippage_pct
        
        # Precio real de entrada con slippage
        if request.direction == TradeDirection.LONG:
            actual_entry_price = spread_adjusted_entry + slippage_amount
        else:
            actual_entry_price = spread_adjusted_entry - slippage_amount
        
        # Calcular fees de entrada
        entry_fees = self.apply_fees(actual_entry_price, request.size, OrderType.MARKET)
        
        # Costos totales de entrada
        spread_cost = abs(spread_adjusted_entry - request.entry_price) * request.size
        slippage_cost = slippage_amount * request.size
        
        # Crear resultado inicial (trade abierto)
        result = TradeResult(
            symbol=request.symbol,
            direction=request.direction,
            strategy=request.strategy,
            requested_entry_price=request.entry_price,
            actual_entry_price=actual_entry_price,
            requested_exit_price=None,
            actual_exit_price=None,
            position_size=request.size,
            entry_fees=entry_fees,
            exit_fees=0.0,
            slippage_cost=slippage_cost,
            spread_cost=spread_cost,
            gross_pnl=0.0,
            net_pnl=0.0,
            pnl_percentage=0.0,
            timestamp_entry=datetime.now(),
            timestamp_exit=None,
            entry_reason="signal_execution",
            exit_reason="",
            confidence=0.0
        )
        
        return result
    
    def close_trade(self, open_trade: TradeResult, exit_price: float, 
                   exit_reason: str = "signal_close", volatility: Optional[float] = None) -> TradeResult:
        """
        Cerrar trade aplicando costos de salida
        
        Args:
            open_trade: Trade abierto
            exit_price: Precio de salida solicitado
            exit_reason: Razón de cierre
            volatility: Volatilidad para slippage
        
        Returns:
            TradeResult completo con P&L calculado
        """
        # Aplicar spread al precio de salida
        if open_trade.direction == TradeDirection.LONG:
            spread_adjusted_exit = self.calculate_spread_adjustment(exit_price, TradeDirection.SHORT)
        else:
            spread_adjusted_exit = self.calculate_spread_adjustment(exit_price, TradeDirection.LONG)
        
        # Calcular slippage de salida
        slippage_pct = self.calculate_slippage(spread_adjusted_exit, volatility)
        slippage_amount = spread_adjusted_exit * slippage_pct
        
        # Precio real de salida
        if open_trade.direction == TradeDirection.LONG:
            actual_exit_price = spread_adjusted_exit - slippage_amount
        else:
            actual_exit_price = spread_adjusted_exit + slippage_amount
        
        # Calcular fees de salida
        exit_fees = self.apply_fees(actual_exit_price, open_trade.position_size, OrderType.MARKET)
        
        # Costos adicionales de salida
        exit_slippage_cost = slippage_amount * open_trade.position_size
        exit_spread_cost = abs(spread_adjusted_exit - exit_price) * open_trade.position_size
        
        # Calcular P&L bruto
        if open_trade.direction == TradeDirection.LONG:
            gross_pnl = (actual_exit_price - open_trade.actual_entry_price) * open_trade.position_size
        else:
            gross_pnl = (open_trade.actual_entry_price - actual_exit_price) * open_trade.position_size
        
        # P&L neto (descontando todos los costos)
        total_fees = open_trade.entry_fees + exit_fees
        total_slippage = open_trade.slippage_cost + exit_slippage_cost
        total_spread = open_trade.spread_cost + exit_spread_cost
        
        net_pnl = gross_pnl - total_fees - total_slippage - total_spread
        
        # Calcular porcentaje sobre capital invertido
        invested_capital = open_trade.actual_entry_price * open_trade.position_size
        pnl_percentage = (net_pnl / invested_capital * 100) if invested_capital > 0 else 0
        
        # Actualizar trade con datos de cierre
        open_trade.requested_exit_price = exit_price
        open_trade.actual_exit_price = actual_exit_price
        open_trade.exit_fees = exit_fees
        open_trade.slippage_cost += exit_slippage_cost
        open_trade.spread_cost += exit_spread_cost
        open_trade.gross_pnl = gross_pnl
        open_trade.net_pnl = net_pnl
        open_trade.pnl_percentage = pnl_percentage
        open_trade.timestamp_exit = datetime.now()
        open_trade.exit_reason = exit_reason
        
        return open_trade
    
    def get_execution_summary(self, trade: TradeResult) -> Dict:
        """
        Obtener resumen de costos de ejecución
        
        Args:
            trade: Trade ejecutado
        
        Returns:
            Diccionario con desglose de costos
        """
        if not trade.timestamp_exit:
            return {"status": "open_trade"}
        
        total_cost = trade.entry_fees + trade.exit_fees + trade.slippage_cost + trade.spread_cost
        total_notional = trade.actual_entry_price * trade.position_size
        
        return {
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            "direction": trade.direction.value,
            "total_notional": total_notional,
            "gross_pnl": trade.gross_pnl,
            "net_pnl": trade.net_pnl,
            "total_costs": total_cost,
            "cost_breakdown": {
                "entry_fees": trade.entry_fees,
                "exit_fees": trade.exit_fees,
                "total_fees": trade.entry_fees + trade.exit_fees,
                "slippage_cost": trade.slippage_cost,
                "spread_cost": trade.spread_cost
            },
            "cost_percentage": (total_cost / total_notional * 100) if total_notional > 0 else 0,
            " pnl_after_costs": trade.net_pnl,
            "price_impact": {
                "requested_entry": trade.requested_entry_price,
                "actual_entry": trade.actual_entry_price,
                "requested_exit": trade.requested_exit_price,
                "actual_exit": trade.actual_exit_price,
                "entry_slippage_pct": ((trade.actual_entry_price - trade.requested_entry_price) / trade.requested_entry_price * 100) if trade.requested_entry_price > 0 else 0,
                "exit_slippage_pct": ((trade.actual_exit_price - trade.requested_exit_price) / trade.requested_exit_price * 100) if trade.requested_exit_price and trade.requested_exit_price > 0 else 0
            }
        }

# Instancia global para uso en toda la aplicación
execution_engine = ExecutionEngine()
