"""
Central Engine Manager - Coordina todos los motores de trading
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import asyncio
import json

from signal_interface import SignalEmitter, IntelligentSignalEmitter, BinanceModeSignalEmitter, MicroProfitSignalEmitter, SimulationSignalEmitter
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
        self.db_session = None
        
    async def initialize(self, notification_callback=None):
        """Inicializar el gestor con todos los engines disponibles"""
        self.notification_callback = notification_callback
        self.db_session = next(get_db())
        
        # Registrar todos los engines disponibles
        await self._register_all_engines()
        
        print(f"🔧 Engine Manager initialized with {len(self.engines)} engines")
        
    async def _register_all_engines(self):
        """Registrar todos los engines disponibles"""
        
        # 1. Engine de Simulación Básica
        await self.register_engine(
            engine_id="simulation",
            engine_type=EngineType.SIMULATION,
            emitter=SimulationSignalEmitter(self.db_session),
            status=EngineStatus.IDLE
        )
        
        # 2. Engines de Modos Binance
        for mode in ["conservative", "hybrid", "aggressive"]:
            await self.register_engine(
                engine_id=f"binance_{mode}",
                engine_type=EngineType.BINANCE_MODE,
                emitter=BinanceModeSignalEmitter(self.db_session, mode),
                status=EngineStatus.IDLE,
                metadata={"mode": mode}
            )
        
        # 3. Engine Intelligent
        await self.register_engine(
            engine_id="intelligent",
            engine_type=EngineType.INTELLIGENT,
            emitter=IntelligentSignalEmitter(self.db_session),
            status=EngineStatus.IDLE
        )
        
        # 4. Engine Micro Profit
        await self.register_engine(
            engine_id="micro_profit",
            engine_type=EngineType.MICRO_PROFIT,
            emitter=MicroProfitSignalEmitter(self.db_session),
            status=EngineStatus.IDLE
        )
        
        # 5. Engine de Ejecución (no emite señales, ejecuta trades)
        await self.register_engine(
            engine_id="execution",
            engine_type=EngineType.EXECUTION,
            emitter=None,  # No emite señales, solo ejecuta
            status=EngineStatus.IDLE
        )
        
        # 6. Trading Engine (análisis técnico)
        await self.register_engine(
            engine_id="trading",
            engine_type=EngineType.TRADING,
            emitter=None,  # No emite señales directamente
            status=EngineStatus.IDLE
        )
        
        # 7. Binance Advanced Engine (genera ADV_MARKET_MAKING_BUY)
        await self.register_engine(
            engine_id="binance_advanced",
            engine_type=EngineType.BINANCE_MODE,
            emitter=None,  # Usa lógica propia de BinanceDataSimulator
            status=EngineStatus.IDLE,
            metadata={
                "source": "binance_simulator",
                "strategies": ["market_making", "scalping", "grid_trading", "mean_reversion", "breakout_momentum"],
                "description": "Advanced Binance trading with market making strategies"
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
    
    async def _run_binance_mode_engine(self, engine_id: str):
        """Ejecutar engine de modo Binance"""
        from binance_mode_simulator import run_binance_mode_simulation
        
        mode = self.engines[engine_id]["metadata"]["mode"]
        
        while engine_id in self.active_tasks:
            try:
                # Ejecutar un ciclo del simulador
                await run_binance_mode_simulation(
                    get_db, 
                    self._create_notification_wrapper(), 
                    mode
                )
                
                # Actualizar estadísticas
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                # Pequeña pausa para no sobrecargar
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in binance mode engine {engine_id}: {e}")
                await asyncio.sleep(5)
    
    async def _run_intelligent_engine(self, engine_id: str):
        """Ejecutar engine intelligent"""
        from intelligent_simulator import run_intelligent_simulation
        
        while engine_id in self.active_tasks:
            try:
                await run_intelligent_simulation(
                    get_db,
                    self._create_notification_wrapper()
                )
                
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in intelligent engine {engine_id}: {e}")
                await asyncio.sleep(5)
    
    async def _run_micro_profit_engine(self, engine_id: str):
        """Ejecutar engine micro profit"""
        from micro_profit_generator import run_micro_profit_generator
        
        while engine_id in self.active_tasks:
            try:
                await run_micro_profit_generator(
                    get_db,
                    self._create_notification_wrapper()
                )
                
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in micro profit engine {engine_id}: {e}")
                await asyncio.sleep(5)
    
    async def _run_simulation_engine(self, engine_id: str):
        """Ejecutar engine de simulación básica"""
        from simulator import run_periodic_simulation
        
        while engine_id in self.active_tasks:
            try:
                await run_periodic_simulation(
                    get_db,
                    self._create_notification_wrapper()
                )
                
                self.engines[engine_id]["trades_generated"] += 1
                self.engines[engine_id]["last_activity"] = datetime.now()
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.engines[engine_id]["errors"] += 1
                print(f"❌ Error in simulation engine {engine_id}: {e}")
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
            if self.notification_callback:
                await self.notification_callback(data)
            else:
                print(f"📢 Engine notification: {data}")
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
        
        # Cerrar sesión de base de datos
        if self.db_session:
            self.db_session.close()
        
        print("✅ All engines shut down")

# Instancia global del gestor
engine_manager = CentralEngineManager()
