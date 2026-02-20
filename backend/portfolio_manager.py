import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.orm import Session
from database import Trade, EquityCurve, Metric, Alert
from execution_engine import execution_engine, TradeRequest, TradeDirection
import json

class SignalType(Enum):
    TRADE_INTENT = "trade_intent"
    RISK_ALERT = "risk_alert"
    PORTFOLIO_UPDATE = "portfolio_update"

class SignalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"

@dataclass
class TradeIntent:
    """Intención de trade de un motor"""
    id: str
    source_engine: str  # intelligent, binance_mode, micro_profit
    source_mode: Optional[str] = None  # conservative, hybrid, aggressive, etc.
    symbol: str = ""
    direction: TradeDirection = TradeDirection.LONG
    entry_price: float = 0.0
    size: float = 0.0
    stop_loss: Optional[float] = None
    strategy: str = ""
    confidence: float = 0.0
    volatility: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def to_trade_request(self) -> TradeRequest:
        """Convertir a TradeRequest para Execution Engine"""
        return TradeRequest(
            symbol=self.symbol,
            direction=self.direction,
            entry_price=self.entry_price,
            size=self.size,
            stop_loss=self.stop_loss,
            strategy=self.strategy,
            volatility=self.volatility
        )

@dataclass
class PortfolioState:
    """Estado completo del portfolio"""
    total_capital: float = 100.0
    available_capital: float = 100.0
    allocated_capital: float = 0.0
    peak_capital: float = 100.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    
    # Exposición por motor
    engine_exposure: Dict[str, float] = field(default_factory=dict)
    
    # Exposición por símbolo
    symbol_exposure: Dict[str, float] = field(default_factory=dict)
    pending_exposure: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Límites de riesgo
    max_engine_exposure: float = 0.4  # 40% máximo por motor
    max_symbol_exposure: float = 0.3   # 30% máximo por símbolo
    max_total_exposure: float = 0.8   # 80% máximo total expuesto
    max_daily_loss: float = 0.05      # 5% máximo pérdida diaria
    max_drawdown_limit: float = 0.15  # 15% máximo drawdown

@dataclass
class RiskMetrics:
    """Métricas de riesgo del portfolio"""
    var_95: float = 0.0  # Value at Risk 95%
    correlation_matrix: Dict = field(default_factory=dict)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    beta: float = 0.0
    volatility: float = 0.0

class PortfolioManager:
    """Gestor central de portfolio y riesgo"""
    
    def __init__(self, db: Session, initial_capital: float = 100.0):
        self.db = db
        self.state = PortfolioState(total_capital=initial_capital, available_capital=initial_capital)
        self.risk_metrics = RiskMetrics()
        self.pending_signals: List[TradeIntent] = []
        self.signal_history: List[Dict] = []
        self.active_engines: Set[str] = set()
        self.last_risk_check = datetime.now()
        
        # Callbacks para notificaciones
        self.notify_callbacks = []
        
        # Inicializar estado desde base de datos
        self._initialize_from_database()
    
    def add_notify_callback(self, callback):
        """Agregar callback para notificaciones WebSocket"""
        self.notify_callbacks.append(callback)
    
    async def notify_clients(self, message: Dict):
        """Notificar a todos los clientes via WebSocket"""
        for callback in self.notify_callbacks:
            try:
                await callback(json.dumps(message))
            except Exception as e:
                print(f"Error in notify callback: {e}")
    
    def _initialize_from_database(self):
        """Inicializar estado desde trades existentes"""
        try:
            trades = self.db.query(Trade).order_by(Trade.timestamp_entry.asc()).all()
            
            if not trades:
                return
            
            # Calcular capital y P&L desde trades
            initial_capital = self.state.total_capital
            running_capital = initial_capital
            peak_capital = self.state.peak_capital
            
            # Reiniciar exposición acumulada (solo reconstruiremos si hay posiciones abiertas)
            self.state.engine_exposure.clear()
            self.state.symbol_exposure.clear()
            self.state.pending_exposure.clear()
            self.state.allocated_capital = 0.0
            
            for trade in trades:
                running_capital += trade.pnl
                peak_capital = max(peak_capital, running_capital)
                
                # Si el trade permanece abierto (sin timestamp_exit), reservar exposición
                trade_open = getattr(trade, 'timestamp_exit', None) in (None, '', '0')
                trade_status = getattr(trade, 'status', 'executed')
                if trade_open or trade_status not in ('executed', 'closed', 'finished'):
                    notional = abs(float(trade.entry_price) * float(trade.size))
                    engine = self._extract_engine_from_strategy(trade.strategy)
                    self.state.engine_exposure[engine] = self.state.engine_exposure.get(engine, 0.0) + notional
                    self.state.symbol_exposure[trade.symbol] = self.state.symbol_exposure.get(trade.symbol, 0.0) + notional
                    self.state.allocated_capital += notional
            
            # Actualizar estado final
            self.state.total_capital = running_capital
            self.state.peak_capital = max(peak_capital, running_capital)
            self.state.total_pnl = running_capital - initial_capital
            self.state.available_capital = max(0.0, running_capital - self.state.allocated_capital)
            if self.state.peak_capital > 0:
                drawdown = max(0.0, (self.state.peak_capital - running_capital) / self.state.peak_capital * 100)
                self.state.current_drawdown = drawdown
                self.state.max_drawdown = max(self.state.max_drawdown, drawdown)
            
            print(f"📊 Portfolio initialized: ${running_capital:.2f} capital, {self.state.max_drawdown:.2f}% max DD")
            
        except Exception as e:
            print(f"❌ Error initializing portfolio: {e}")
    
    def _extract_engine_from_strategy(self, strategy: str) -> str:
        """Extraer nombre del motor desde estrategia"""
        if any(s in strategy for s in ['MA_Cross', 'RSI_Divergence', 'MACD_Signal', 'Bollinger_Bands']):
            return 'intelligent'
        elif any(s in strategy for s in ['Conservative', 'Hybrid', 'Aggressive']):
            return 'binance_mode'
        elif 'Micro' in strategy:
            return 'micro_profit'
        else:
            return 'simulation'
    
    async def submit_trade_intent(self, intent: TradeIntent) -> SignalStatus:
        """Recibir intención de trade y evaluar riesgo"""
        print(f"📥 Trade intent received: {intent.source_engine} {intent.symbol} ${intent.size * intent.entry_price:.2f}")
        trade_value = intent.size * intent.entry_price
        
        # 1. Validaciones básicas
        if not self._validate_basic_constraints(intent):
            status = SignalStatus.REJECTED
            await self._log_signal(intent, status, "Basic constraints validation failed")
            return status
        
        # 2. Evaluación de riesgo de portfolio
        risk_check = self._evaluate_portfolio_risk(intent)
        if not risk_check['approved']:
            status = SignalStatus.REJECTED
            await self._log_signal(intent, status, risk_check['reason'])
            await self.notify_clients({
                "type": "risk_alert",
                "message": f"Trade rejected: {risk_check['reason']}",
                "data": {
                    "intent_id": intent.id,
                    "source": intent.source_engine,
                    "reason": risk_check['reason']
                }
            })
            return status
        
        # Reservar capital y exposición antes de ejecutar
        self._reserve_trade_capacity(intent, trade_value)
        
        # 3. Aprobar y ejecutar
        status = SignalStatus.APPROVED
        await self._log_signal(intent, status, "Approved for execution")
        
        # Ejecutar trade
        try:
            executed_trade = await self._execute_approved_intent(intent)
            if executed_trade:
                self._release_trade_capacity(intent.id, executed_trade)
                status = SignalStatus.EXECUTED
                await self._update_portfolio_state(executed_trade)
                await self._log_signal(intent, status, "Successfully executed")
                
                # Notificar ejecución
                await self.notify_clients({
                    "type": "portfolio_trade_executed",
                    "message": f"Portfolio trade executed: {intent.symbol} ${executed_trade.pnl:.2f}",
                    "data": {
                        "intent_id": intent.id,
                        "source": intent.source_engine,
                        "symbol": executed_trade.symbol,
                        "pnl": executed_trade.pnl,
                        "portfolio_capital": self.state.total_capital
                    }
                })
            else:
                status = SignalStatus.FAILED
                self._release_trade_capacity(intent.id)
                await self._log_signal(intent, status, "Execution failed")
                
        except Exception as e:
            status = SignalStatus.FAILED
            self._release_trade_capacity(intent.id)
            await self._log_signal(intent, status, f"Execution error: {str(e)}")
            print(f"❌ Error executing trade intent: {e}")
        
        return status
    
    def _validate_basic_constraints(self, intent: TradeIntent) -> bool:
        """Validaciones básicas de la intención"""
        # Validar motor activo
        if intent.source_engine not in self.active_engines:
            print(f"❌ Engine {intent.source_engine} not active")
            return False
        
        # Validar tamaño mínimo
        trade_value = intent.size * intent.entry_price
        if trade_value < 0.01:  # Mínimo $0.01
            print(f"❌ Trade value too small: ${trade_value:.4f}")
            return False
        
        # Validar precio razonable
        if intent.entry_price <= 0 or intent.size <= 0:
            print(f"❌ Invalid price or size")
            return False
        
        return True

    def _get_pending_exposure_sum(self, *, engine: Optional[str] = None, symbol: Optional[str] = None) -> float:
        total = 0.0
        for reservation in self.state.pending_exposure.values():
            if engine is not None and reservation['engine'] != engine:
                continue
            if symbol is not None and reservation['symbol'] != symbol:
                continue
            total += reservation['notional']
        return total

    def _reserve_trade_capacity(self, intent: TradeIntent, notional: float):
        self.state.pending_exposure[intent.id] = {
            'engine': intent.source_engine,
            'symbol': intent.symbol,
            'notional': notional,
        }
        self.state.allocated_capital += notional
        self.state.available_capital = max(0.0, self.state.total_capital - self.state.allocated_capital)

    def _release_trade_capacity(self, intent_id: str, executed_trade: Optional[Trade] = None):
        reservation = self.state.pending_exposure.pop(intent_id, None)
        if not reservation:
            return

        notional = reservation['notional']
        engine = reservation['engine']
        symbol = reservation['symbol']

        self.state.allocated_capital = max(0.0, self.state.allocated_capital - notional)

        trade_still_open = executed_trade is not None and self._is_trade_open(executed_trade)
        if trade_still_open:
            open_notional = abs(float(executed_trade.entry_price) * float(executed_trade.size))
            self.state.engine_exposure[engine] = self.state.engine_exposure.get(engine, 0.0) + open_notional
            self.state.symbol_exposure[symbol] = self.state.symbol_exposure.get(symbol, 0.0) + open_notional
            self.state.allocated_capital += open_notional
        else:
            # Si la operación cerró una exposición existente, reducir notional pendiente
            if engine in self.state.engine_exposure:
                self.state.engine_exposure[engine] = max(0.0, self.state.engine_exposure[engine] - notional)
                if self.state.engine_exposure[engine] <= 1e-9:
                    del self.state.engine_exposure[engine]
            if symbol in self.state.symbol_exposure:
                self.state.symbol_exposure[symbol] = max(0.0, self.state.symbol_exposure[symbol] - notional)
                if self.state.symbol_exposure[symbol] <= 1e-9:
                    del self.state.symbol_exposure[symbol]

        self.state.available_capital = max(0.0, self.state.total_capital - self.state.allocated_capital)

    def _is_trade_open(self, trade: Trade) -> bool:
        status = getattr(trade, 'status', '') or ''
        exit_timestamp = getattr(trade, 'timestamp_exit', None)
        if status.lower() in {'executed', 'closed', 'finished'} and exit_timestamp:
            return False
        return True
    
    def _evaluate_portfolio_risk(self, intent: TradeIntent) -> Dict:
        """Evaluar riesgo de portfolio para la intención"""
        trade_value = intent.size * intent.entry_price
        
        # 1. Verificar capital disponible
        if trade_value > self.state.available_capital:
            return {
                'approved': False,
                'reason': f'Insufficient capital: need ${trade_value:.2f}, available ${self.state.available_capital:.2f}'
            }
        
        # 2. Verificar exposición por motor
        engine_pending = self._get_pending_exposure_sum(engine=intent.source_engine)
        current_engine_exposure = self.state.engine_exposure.get(intent.source_engine, 0.0) + engine_pending
        new_engine_exposure = current_engine_exposure + trade_value
        max_engine_allowed = self.state.total_capital * self.state.max_engine_exposure
        
        if new_engine_exposure > max_engine_allowed:
            return {
                'approved': False,
                'reason': f'Engine exposure limit: {new_engine_exposure:.2f} > {max_engine_allowed:.2f}'
            }
        
        # 3. Verificar exposición por símbolo
        symbol_pending = self._get_pending_exposure_sum(symbol=intent.symbol)
        current_symbol_exposure = self.state.symbol_exposure.get(intent.symbol, 0.0) + symbol_pending
        new_symbol_exposure = current_symbol_exposure + trade_value
        max_symbol_allowed = self.state.total_capital * self.state.max_symbol_exposure
        
        if new_symbol_exposure > max_symbol_allowed:
            return {
                'approved': False,
                'reason': f'Symbol exposure limit: {new_symbol_exposure:.2f} > {max_symbol_allowed:.2f}'
            }
        
        # 4. Verificar exposición total
        current_total_exposure = self.state.allocated_capital
        new_total_exposure = current_total_exposure + trade_value
        max_total_allowed = self.state.total_capital * self.state.max_total_exposure
        
        if new_total_exposure > max_total_allowed:
            return {
                'approved': False,
                'reason': f'Total exposure limit: {new_total_exposure:.2f} > {max_total_allowed:.2f}'
            }
        
        # 5. Verificar pérdida diaria
        if self.state.daily_pnl < -self.state.total_capital * self.state.max_daily_loss:
            return {
                'approved': False,
                'reason': f'Daily loss limit reached: {self.state.daily_pnl:.2f}'
            }
        
        # 6. Verificar drawdown
        if self.state.current_drawdown > self.state.max_drawdown_limit:
            return {
                'approved': False,
                'reason': f'Max drawdown exceeded: {self.state.current_drawdown:.2f}%'
            }
        
        return {'approved': True, 'reason': 'All risk checks passed'}
    
    async def _execute_approved_intent(self, intent: TradeIntent) -> Optional[Trade]:
        """Ejecutar intención aprobada usando Execution Engine"""
        try:
            # Convertir a TradeRequest
            trade_request = intent.to_trade_request()
            
            # Ejecutar con Execution Engine
            trade_result = execution_engine.execute_trade(
                trade_request,
                self.state.total_capital,
                risk_per_trade=0.02
            )
            
            # Simular salida (aquí iría lógica real de salida)
            # Por ahora simulamos resultado basado en confianza
            exit_price = trade_result.actual_entry_price * (1 + (intent.confidence - 0.5) * 0.02)
            
            # Simular tiempo de espera realista para el trade (15-90 segundos para portfolio manager)
            trade_duration_seconds = random.uniform(15, 90)
            
            # Crear timestamps con separación realista
            entry_time = datetime.now()
            exit_time = entry_time + timedelta(seconds=trade_duration_seconds)
            
            # Cerrar trade
            closed_trade = execution_engine.close_trade(
                trade_result,
                exit_price,
                f"portfolio_execution_{intent.source_engine}",
                intent.volatility or 2.0
            )
            
            # Sobrescribir timestamps para tener duración realista
            closed_trade.timestamp_entry = entry_time
            closed_trade.timestamp_exit = exit_time
            
            # Convertir a Trade de base de datos con información completa
            db_trade = Trade(
                timestamp_entry=closed_trade.timestamp_entry.isoformat(),
                timestamp_exit=closed_trade.timestamp_exit.isoformat(),
                symbol=closed_trade.symbol,
                strategy=f"{intent.source_engine}_{intent.strategy}",
                
                # Precios reales vs solicitados
                entry_price=round(closed_trade.actual_entry_price, 6),
                exit_price=round(closed_trade.actual_exit_price, 6),
                requested_entry_price=round(intent.entry_price, 6),
                requested_exit_price=round(closed_trade.actual_exit_price, 6),  # Mismo precio por ahora
                
                # Tamaño y P&L
                size=round(closed_trade.position_size, 8),
                pnl=round(closed_trade.net_pnl, 6),
                gross_pnl=round(closed_trade.gross_pnl, 6),
                
                # Costos de ejecución
                entry_fees=round(closed_trade.entry_fees, 6),
                exit_fees=round(closed_trade.exit_fees, 6),
                slippage_cost=round(closed_trade.slippage_cost, 6),
                spread_cost=round(closed_trade.spread_cost, 6),
                total_costs=round(closed_trade.entry_fees + closed_trade.exit_fees + closed_trade.slippage_cost + closed_trade.spread_cost, 6),
                
                # Información de riesgo
                stop_loss=round(intent.stop_loss, 6) if intent.stop_loss else None,
                take_profit=None,  # Por ahora no se usa
                confidence=round(intent.confidence, 3),
                volatility=round(intent.volatility, 2) if intent.volatility else None,
                
                # Metadatos del motor
                source_engine=intent.source_engine,
                source_mode=intent.source_mode or '',
                direction=closed_trade.direction.value,
                
                # Tiempos
                duration_ms=int((closed_trade.timestamp_exit - closed_trade.timestamp_entry).total_seconds() * 1000),
                
                # Estado y razón
                entry_reason=closed_trade.entry_reason,
                exit_reason=closed_trade.exit_reason,
                status='executed'
            )
            
            # Guardar en base de datos
            self.db.add(db_trade)
            self.db.commit()
            self.db.refresh(db_trade)
            
            return db_trade
            
        except Exception as e:
            print(f"❌ Error executing approved intent: {e}")
            self.db.rollback()
            return None
    
    async def _update_portfolio_state(self, trade: Trade):
        """Actualizar estado del portfolio después de trade ejecutado"""
        # Actualizar capital
        self.state.total_capital += trade.pnl
        
        # Actualizar P&L
        self.state.total_pnl += trade.pnl
        self.state.daily_pnl += trade.pnl
        
        # Actualizar drawdown y capital disponible
        self.state.peak_capital = max(self.state.peak_capital, self.state.total_capital)
        if self.state.peak_capital > 0:
            drawdown = max(0.0, (self.state.peak_capital - self.state.total_capital) / self.state.peak_capital * 100)
            self.state.current_drawdown = drawdown
            self.state.max_drawdown = max(self.state.max_drawdown, drawdown)
        
        self.state.available_capital = max(0.0, self.state.total_capital - self.state.allocated_capital)
        
        # Actualizar equity curve
        equity = EquityCurve(
            timestamp=datetime.now().isoformat(),
            capital=round(self.state.total_capital, 2)
        )
        self.db.merge(equity)
        self.db.commit()
        
        print(f"💰 Portfolio updated: ${self.state.total_capital:.2f} capital, P&L: ${trade.pnl:+.2f}")
    
    async def _log_signal(self, intent: TradeIntent, status: SignalStatus, reason: str):
        """Registrar señal en historial"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'intent_id': intent.id,
            'source_engine': intent.source_engine,
            'symbol': intent.symbol,
            'status': status.value,
            'reason': reason,
            'trade_value': intent.size * intent.entry_price
        }
        
        self.signal_history.append(log_entry)
        
        # Mantener solo últimos 1000 logs
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-1000:]
    
    def register_engine(self, engine_name: str):
        """Registrar motor como activo"""
        self.active_engines.add(engine_name)
        print(f"✅ Engine registered: {engine_name}")
    
    def unregister_engine(self, engine_name: str):
        """Desregistrar motor"""
        self.active_engines.discard(engine_name)
        print(f"📴 Engine unregistered: {engine_name}")
    
    def get_portfolio_summary(self) -> Dict:
        """Obtener resumen completo del portfolio"""
        return {
            'capital': {
                'total': round(self.state.total_capital, 2),
                'available': round(self.state.available_capital, 2),
                'allocated': round(self.state.allocated_capital, 2),
                'total_pnl': round(self.state.total_pnl, 2),
                'daily_pnl': round(self.state.daily_pnl, 2)
            },
            'risk': {
                'max_drawdown': round(self.state.max_drawdown, 2),
                'current_drawdown': round(self.state.current_drawdown, 2),
                'daily_loss_limit': round(self.state.total_capital * self.state.max_daily_loss, 2)
            },
            'exposure': {
                'by_engine': self.state.engine_exposure,
                'by_symbol': self.state.symbol_exposure,
                'total_exposure_pct': round(self.state.allocated_capital / self.state.total_capital * 100, 2) if self.state.total_capital > 0 else 0
            },
            'limits': {
                'max_engine_exposure_pct': round(self.state.max_engine_exposure * 100, 1),
                'max_symbol_exposure_pct': round(self.state.max_symbol_exposure * 100, 1),
                'max_total_exposure_pct': round(self.state.max_total_exposure * 100, 1),
                'max_daily_loss_pct': round(self.state.max_daily_loss * 100, 1),
                'max_drawdown_limit_pct': round(self.state.max_drawdown_limit * 100, 1)
            },
            'active_engines': list(self.active_engines),
            'signals_today': len([s for s in self.signal_history if datetime.fromisoformat(s['timestamp']).date() == datetime.now().date()])
        }

# Instancia global del Portfolio Manager
portfolio_manager = None

def get_portfolio_manager(db: Session) -> PortfolioManager:
    """Obtener instancia del Portfolio Manager"""
    global portfolio_manager
    if portfolio_manager is None:
        portfolio_manager = PortfolioManager(db)
    return portfolio_manager
