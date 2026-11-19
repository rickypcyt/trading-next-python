"""
Central Engine Manager - Coordina todos los motores de trading
"""
from typing import Awaitable, Callable, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import asyncio
import json
import os

from signal_interface import SignalEmitter, IntelligentSignalEmitter, BinanceModeSignalEmitter, MicroProfitSignalEmitter, SimulationSignalEmitter, ExecutionSignalEmitter
from portfolio_manager import get_portfolio_manager
from database import get_db

class EngineStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class EngineType(Enum):
    SIMULATION = "simulation"
    BINANCE_MODE = "binance_mode"
    INTELLIGENT = "intelligent"
    MICRO_PROFIT = "micro_profit"
    EXECUTION = "execution"
    TRADING = "trading"

class CentralEngineManager:
    """Gestor central que coordina todos los motores de trading"""
    
    def __init__(self):
        self.engines: Dict[str, Dict] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.notification_callback = None
        self.db_factory = get_db
        
    async def initialize(self, notification_callback=None):
        """Inicializar el gestor con todos los engines disponibles"""
        self.notification_callback = notification_callback
        
        # Registrar todos los engines disponibles
        await self._register_all_engines()
        
        # Solo el engine avanzado de Binance se inicia automáticamente
        await self.start_engine("binance_advanced")

        print(f"🔧 Engine Manager initialized with {len(self.engines)} engines")
        print("🚀 Auto-started engine: binance_advanced")
        
    async def _register_all_engines(self):
        """Registrar todos los engines disponibles"""
        
        # 1. Engine Intelligent
        await self.register_engine(
            engine_id="intelligent",
            engine_type=EngineType.INTELLIGENT,
            emitter=IntelligentSignalEmitter(),
            status=EngineStatus.IDLE,
            metadata={
                "description": "Intelligent multi-strategy technical trading"
            }
        )
        
        # 2. Engine Micro Profit
        await self.register_engine(
            engine_id="micro_profit",
            engine_type=EngineType.MICRO_PROFIT,
            emitter=MicroProfitSignalEmitter(),
            status=EngineStatus.IDLE,
            metadata={
                "description": "Micro profit generator"
            }
        )
        
        # 3. Binance Advanced Engine (genera ADV_MARKET_MAKING_BUY)
        await self.register_engine(
            engine_id="binance_advanced",
            engine_type=EngineType.BINANCE_MODE,
            emitter=None,  # Usa lógica propia de BinanceDataSimulator
            status=EngineStatus.IDLE,
            metadata={
                "source": "binance_simulator",
                "strategies": ["market_making", "scalping", "grid_trading", "mean_reversion", "breakout_momentum"],
                "description": "Advanced Binance trading with market making strategies",
                "user_favorite": True,  # Marcar como favorito del usuario
                "protected": False  # Ahora se puede detener
            }
        )
    
    async def register_engine(self, engine_id: str, engine_type: EngineType, 
                            emitter: Optional[SignalEmitter], status: EngineStatus,
                            metadata: Optional[Dict] = None):
        """Registrar un engine en el sistema"""
        
        self.engines[engine_id] = {
            "id": engine_id,
            "type": engine_type,
            "emitter": emitter,
            "status": status,
            "metadata": metadata or {},
            "registered_at": datetime.now(),
            "last_activity": None,
            "trades_generated": 0,
            "errors": 0
        }
        
        # Registrar en el Portfolio Manager si tiene emitter
        if emitter:
            emitter.register_engine()
        
        print(f"✅ Engine registered: {engine_id} ({engine_type.value})")
    
    async def start_engine(self, engine_id: str) -> bool:
        """Iniciar un engine específico"""
        if engine_id not in self.engines:
            print(f"❌ Engine not found: {engine_id}")
            return False
        
        engine = self.engines[engine_id]
        
        if engine["status"] == EngineStatus.RUNNING:
            print(f"⚠️  Engine already running: {engine_id}")
            return True
        
        try:
            # Iniciar según el tipo de engine
            if engine["type"] == EngineType.BINANCE_MODE:
                if engine_id == "binance_advanced":
                    # Special case for Binance Advanced (uses run_real_time_simulation)
                    task = asyncio.create_task(self._run_binance_advanced_engine(engine_id))
                else:
                    task = asyncio.create_task(self._run_binance_mode_engine(engine_id))
            elif engine["type"] == EngineType.INTELLIGENT:
                task = asyncio.create_task(self._run_intelligent_engine(engine_id))
            elif engine["type"] == EngineType.MICRO_PROFIT:
                task = asyncio.create_task(self._run_micro_profit_engine(engine_id))
            elif engine["type"] == EngineType.SIMULATION:
                task = asyncio.create_task(self._run_simulation_engine(engine_id))
            elif engine["type"] == EngineType.EXECUTION:
                task = asyncio.create_task(self._run_execution_engine(engine_id))
            else:
                print(f"⚠️  Engine type {engine['type'].value} not runnable")
                return False
            
            self.active_tasks[engine_id] = task
            engine["status"] = EngineStatus.RUNNING
            engine["last_activity"] = datetime.now()
            
            await self._notify_engine_status(engine_id, "started")
            print(f"🚀 Engine started: {engine_id}")
            return True
            
        except Exception as e:
            engine["status"] = EngineStatus.ERROR
            engine["errors"] += 1
            print(f"❌ Error starting engine {engine_id}: {e}")
            return False
    
    async def stop_engine(self, engine_id: str) -> bool:
        """Detener un engine específico"""
        if engine_id not in self.engines:
            return False
        
        engine = self.engines[engine_id]
        if engine.get("metadata", {}).get("protected"):
            print(f"🚫 {engine_id} engine is protected and cannot be stopped")
            return False
        
        if engine["status"] != EngineStatus.RUNNING:
            return True
        
        # Cancelar tarea
        if engine_id in self.active_tasks:
            self.active_tasks[engine_id].cancel()
            del self.active_tasks[engine_id]
        
        engine["status"] = EngineStatus.IDLE
        engine["last_activity"] = datetime.now()
        
        await self._notify_engine_status(engine_id, "stopped")
        print(f"🛑 Engine stopped: {engine_id}")
        return True
    
    async def _run_engine_loop(
        self,
        engine_id: str,
        runner: Callable[[], Awaitable[None]],
        *,
        sleep_seconds: float = float(os.getenv("ENGINE_LOOP_SLEEP", "1.0")),
        error_sleep_seconds: float = float(os.getenv("ENGINE_ERROR_SLEEP", "5.0")),
    ):
        """Bucle genérico para ejecutar un motor de forma periódica."""
        while engine_id in self.active_tasks:
            try:
                await runner()
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in engine {engine_id}: {e}")
                await asyncio.sleep(error_sleep_seconds)

    async def _run_binance_mode_engine(self, engine_id: str):
        """Ejecutar engine de modo Binance"""
        from binance_mode_simulator import run_binance_mode_simulation
        
        mode = self.engines[engine_id]["metadata"]["mode"]
        
        await self._run_engine_loop(
            engine_id,
            lambda: run_binance_mode_simulation(
                get_db,
                self._create_notification_wrapper(),
                mode,
            ),
        )
    
    async def _run_intelligent_engine(self, engine_id: str):
        """Ejecutar engine intelligent"""
        from intelligent_simulator import run_intelligent_simulation
        
        await self._run_engine_loop(
            engine_id,
            lambda: run_intelligent_simulation(
                get_db,
                websocket_connections=None,
                notify_clients=self._create_notification_wrapper(),
            ),
        )
    
    async def _run_micro_profit_engine(self, engine_id: str):
        """Ejecutar engine micro profit"""
        from micro_profit_generator import run_micro_profit_generator
        
        await self._run_engine_loop(
            engine_id,
            lambda: run_micro_profit_generator(get_db, self._create_notification_wrapper()),
        )
    
    async def _run_simulation_engine(self, engine_id: str):
        """Ejecutar engine de simulación básica"""
        from simulator import run_periodic_simulation
        
        await self._run_engine_loop(
            engine_id,
            lambda: run_periodic_simulation(get_db, self._create_notification_wrapper()),
        )
    
    async def _run_execution_engine(self, engine_id: str):
        """Ejecutar engine de ejecución con costos realistas"""
        from execution_engine import execution_engine, TradeRequest, TradeDirection
        from portfolio_manager import TradeDirection as PortfolioTradeDirection
        import random
        
        # Símbolos disponibles para trading
        symbols = ["BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD", "SOL/USD"]
        
        while engine_id in self.active_tasks:
            try:
                # Simular recepción de señales de otros motores
                if random.random() < 0.3:  # 30% de probabilidad de generar una señal
                    symbol = random.choice(symbols)
                    direction = random.choice([TradeDirection.LONG, TradeDirection.SHORT])
                    portfolio_direction = PortfolioTradeDirection.LONG if direction == TradeDirection.LONG else PortfolioTradeDirection.SHORT
                    
                    # Precio base (simulado)
                    base_price = random.uniform(30000, 70000) if "BTC" in symbol else random.uniform(1500, 3500)
                    
                    # Generar precios de SL/TP
                    if direction == TradeDirection.LONG:
                        stop_loss = base_price * random.uniform(0.97, 0.99)
                        take_profit = base_price * random.uniform(1.04, 1.08)
                    else:
                        stop_loss = base_price * random.uniform(1.01, 1.03)
                        take_profit = base_price * random.uniform(0.92, 0.96)
                    
                    # Crear solicitud de trade
                    trade_request = TradeRequest(
                        symbol=symbol,
                        direction=direction,
                        entry_price=base_price,
                        size=random.uniform(0.001, 0.01),  # Tamaño pequeño
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        strategy="execution_realistic",
                        volatility=random.uniform(2, 8)
                    )
                    
                    # Ejecutar trade con costos realistas
                    capital = 1000.0  # Capital simulado
                    trade_result = execution_engine.execute_trade(trade_request, capital)
                    
                    # Emitir señal al Portfolio Manager
                    emitter = self.engines[engine_id]["emitter"]
                    success = await emitter.emit_realistic_trade(
                        symbol=trade_result.symbol,
                        direction=portfolio_direction,
                        entry_price=trade_result.requested_entry_price,
                        size=trade_result.position_size,
                        stop_loss=trade_request.stop_loss,
                        take_profit=trade_request.take_profit,
                        strategy=trade_result.strategy,
                        confidence=0.7,
                        volatility=trade_request.volatility,
                        metadata={
                            "actual_entry_price": trade_result.actual_entry_price,
                            "entry_fees": trade_result.entry_fees,
                            "slippage_cost": trade_result.slippage_cost,
                            "spread_cost": trade_result.spread_cost,
                            "total_costs": trade_result.entry_fees + trade_result.slippage_cost + trade_result.spread_cost
                        }
                    )
                    
                    if success:
                        print(f"💰 Execution engine trade: {symbol} {direction.value} @ {trade_result.actual_entry_price:.2f}")
                    
                    # Simular cierre de algunos trades
                    if random.random() < 0.2:  # 20% de probabilidad de cerrar trades existentes
                        # Aquí podrías agregar lógica para cerrar trades abiertos
                        pass
                
                # Actualizar estadísticas
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                # Esperar antes de siguiente ciclo
                await asyncio.sleep(10)  # 10 segundos entre trades
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in execution engine {engine_id}: {e}")
                await asyncio.sleep(5)
    
    async def _run_binance_advanced_engine(self, engine_id: str):
        """Ejecutar engine Binance Advanced (genera ADV_MARKET_MAKING_BUY)"""
        from binance_simulator import run_real_time_simulation
        
        while engine_id in self.active_tasks:
            try:
                # Usar la misma lógica que el sistema original
                await run_real_time_simulation(
                    get_db,
                    self._create_notification_wrapper()
                )
                
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                # Pequeña pausa para no sobrecargar
                await asyncio.sleep(30)  # Más lento que otros engines
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in binance advanced engine {engine_id}: {e}")
                await asyncio.sleep(5)
    
    
    def _create_notification_wrapper(self):
        """Crear wrapper para notificaciones"""
        async def notification_wrapper(data):
            payload = data
            if not isinstance(payload, str):
                def _serialize(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return str(obj)
                payload = json.dumps(payload, default=_serialize)
            if self.notification_callback:
                await self.notification_callback(payload)
            else:
                print(f"📢 Engine notification: {payload}")
        return notification_wrapper
    
    async def _notify_engine_status(self, engine_id: str, status: str):
        """Notificar cambio de estado de engine"""
        if self.notification_callback:
            await self.notification_callback({
                "type": "engine_status_change",
                "engine_id": engine_id,
                "status": status,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_engine_status(self, engine_id: str) -> Optional[Dict]:
        """Obtener estado de un engine"""
        return self.engines.get(engine_id)
    
    def get_all_engines_status(self) -> Dict:
        """Obtener estado de todos los engines"""
        return {
            "engines": {
                engine_id: {
                    "type": engine["type"].value,
                    "status": engine["status"].value,
                    "last_activity": engine["last_activity"].isoformat() if engine["last_activity"] else None,
                    "trades_generated": engine["trades_generated"],
                    "errors": engine["errors"],
                    "metadata": engine["metadata"]
                }
                for engine_id, engine in self.engines.items()
            },
            "active_count": len(self.active_tasks),
            "total_engines": len(self.engines)
        }
    
    async def shutdown(self):
        """Apagar todos los engines"""
        print("🛑 Shutting down all engines...")
        
        # Cancelar todas las tareas activas
        for engine_id in list(self.active_tasks.keys()):
            await self.stop_engine(engine_id)
        
        print("✅ All engines shut down")
        
        # Cerrar sesión de base de datos
        if self.db_session:
            self.db_session.close()

# Instancia global del gestor
engine_manager = CentralEngineManager()
