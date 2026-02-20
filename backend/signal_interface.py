"""
Interfaz unificada para que todos los motores emitan señales al Portfolio Manager
"""
from datetime import datetime
from typing import Optional
from portfolio_manager import TradeIntent, TradeDirection, get_portfolio_manager
import uuid

class SignalEmitter:
    """Interfaz para que los motores emitan señales al Portfolio Manager"""
    
    def __init__(self, engine_name: str, db_session):
        self.engine_name = engine_name
        self.db = db_session
        self.portfolio = get_portfolio_manager(db_session)
    
    async def emit_trade_intent(self, 
                              symbol: str,
                              direction: TradeDirection,
                              entry_price: float,
                              size: float,
                              stop_loss: Optional[float],
                              strategy: str,
                              confidence: float = 0.0,
                              volatility: Optional[float] = None,
                              mode: Optional[str] = None,
                              metadata: Optional[dict] = None) -> bool:
        """
        Emitir intención de trade al Portfolio Manager
        
        Returns:
            True si la señal fue aprobada y ejecutada, False si fue rechazada
        """
        # Crear Trade Intent
        intent = TradeIntent(
            id=str(uuid.uuid4()),
            source_engine=self.engine_name,
            source_mode=mode,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            strategy=strategy,
            confidence=confidence,
            volatility=volatility,
            metadata=metadata or {}
        )
        
        # Enviar al Portfolio Manager
        status = await self.portfolio.submit_trade_intent(intent)
        
        return status.value in ['approved', 'executed']
    
    def register_engine(self):
        """Registrar este motor en el Portfolio Manager"""
        self.portfolio.register_engine(self.engine_name)
    
    def unregister_engine(self):
        """Desregistrar este motor del Portfolio Manager"""
        self.portfolio.unregister_engine(self.engine_name)

# Clases base para cada motor
class IntelligentSignalEmitter(SignalEmitter):
    """Emitter específico para Intelligent Trading Simulator"""
    
    def __init__(self, db_session):
        super().__init__('intelligent', db_session)

class BinanceModeSignalEmitter(SignalEmitter):
    """Emitter específico para Binance Mode Simulator"""
    
    def __init__(self, db_session, mode: str):
        super().__init__('binance_mode', db_session)
        self.mode = mode
    
    async def emit_mode_trade_intent(self, **kwargs):
        """Emitir señal específica de modo"""
        return await self.emit_trade_intent(mode=self.mode, **kwargs)

class MicroProfitSignalEmitter(SignalEmitter):
    """Emitter específico para Micro Profit Generator"""
    
    def __init__(self, db_session):
        super().__init__('micro_profit', db_session)

class SimulationSignalEmitter(SignalEmitter):
    """Emitter específico para Trading Simulator básico"""
    
    def __init__(self, db_session):
        super().__init__('simulation', db_session)

class ExecutionSignalEmitter(SignalEmitter):
    """Emitter específico para Execution Engine con costos realistas"""
    
    def __init__(self, db_session):
        super().__init__('execution', db_session)
    
    async def emit_realistic_trade(self, 
                                 symbol: str,
                                 direction: TradeDirection,
                                 entry_price: float,
                                 size: float,
                                 stop_loss: Optional[float],
                                 take_profit: Optional[float],
                                 strategy: str,
                                 confidence: float = 0.0,
                                 volatility: Optional[float] = None,
                                 metadata: Optional[dict] = None) -> bool:
        """
        Emitir trade con costos realistas (fees, slippage, spread)
        """
        enhanced_metadata = {
            'execution_type': 'realistic',
            'includes_fees': True,
            'includes_slippage': True,
            'includes_spread': True,
            **(metadata or {})
        }
        
        return await self.emit_trade_intent(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            strategy=strategy,
            confidence=confidence,
            volatility=volatility,
            metadata=enhanced_metadata
        )

class TradingSignalEmitter(SignalEmitter):
    """Emitter específico para Trading Engine con análisis técnico"""
    
    def __init__(self, db_session):
        super().__init__('trading', db_session)
    
    async def emit_technical_signal(self,
                                  symbol: str,
                                  direction: TradeDirection,
                                  entry_price: float,
                                  stop_loss: Optional[float],
                                  take_profit: Optional[float],
                                  strategy: str,
                                  indicators: dict,
                                  confidence: float = 0.0,
                                  volatility: Optional[float] = None,
                                  metadata: Optional[dict] = None) -> bool:
        """
        Emitir señal basada en análisis técnico
        """
        enhanced_metadata = {
            'signal_type': 'technical_analysis',
            'indicators': indicators,
            'analysis_method': strategy,
            **(metadata or {})
        }
        
        return await self.emit_trade_intent(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            size=0.0,  # Se calculará en base al riesgo
            stop_loss=stop_loss,
            strategy=strategy,
            confidence=confidence,
            volatility=volatility,
            metadata=enhanced_metadata
        )
