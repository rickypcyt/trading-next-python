"""
Engine Manager API Endpoints
Endpoints para gestionar todos los motores de trading
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from engine_manager import engine_manager, EngineStatus

def register_engine_endpoints(app):
    """Registra todos los endpoints de engines en la app FastAPI"""
    
    @app.get('/engines')
    def get_all_engines():
        """Obtener estado de todos los engines"""
        return engine_manager.get_all_engines_status()

    @app.get('/engines/{engine_id}')
    def get_engine_status(engine_id: str):
        """Obtener estado de un engine específico"""
        status = engine_manager.get_engine_status(engine_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
        return status

    @app.post('/engines/{engine_id}/start')
    async def start_engine(engine_id: str):
        """Iniciar un engine específico"""
        success = await engine_manager.start_engine(engine_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to start engine '{engine_id}'")
        return {"status": "started", "engine_id": engine_id}

    @app.post('/engines/{engine_id}/stop')
    async def stop_engine(engine_id: str):
        """Detener un engine específico"""
        success = await engine_manager.stop_engine(engine_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found or not running")
        return {"status": "stopped", "engine_id": engine_id}

    @app.post('/engines/start-all')
    async def start_all_engines():
        """Iniciar todos los engines disponibles"""
        results = {}
        for engine_id in engine_manager.engines.keys():
            success = await engine_manager.start_engine(engine_id)
            results[engine_id] = "started" if success else "failed"
        
        return {"status": "completed", "results": results}

    @app.post('/engines/stop-all')
    async def stop_all_engines():
        """Detener todos los engines"""
        results = {}
        for engine_id in list(engine_manager.active_tasks.keys()):
            success = await engine_manager.stop_engine(engine_id)
            results[engine_id] = "stopped" if success else "failed"
        
        return {"status": "completed", "results": results}

    @app.get('/engines/active')
    def get_active_engines():
        """Obtener lista de engines activos"""
        return {
            "active_engines": list(engine_manager.active_tasks.keys()),
            "active_count": len(engine_manager.active_tasks)
        }

    @app.get('/engines/types')
    def get_engine_types():
        """Obtener tipos de engines disponibles"""
        from engine_manager import EngineType
        return {
            "engine_types": [etype.value for etype in EngineType],
            "descriptions": {
                "simulation": "Motor de simulación básica",
                "binance_mode": "Modos de trading Binance (conservador, híbrido, agresivo)",
                "intelligent": "Motor de trading inteligente con múltiples estrategias",
                "micro_profit": "Generador de micro ganancias",
                "execution": "Motor de ejecución de trades",
                "trading": "Motor de análisis técnico y trading",
                "binance_advanced": "Motor avanzado Binance con estrategias Market Making (ADV_MARKET_MAKING_BUY)"
            }
        }
