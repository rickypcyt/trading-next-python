from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from database import get_db, Trade, EquityCurve, Metric, Alert
from simulator import TradingSimulator, run_periodic_simulation
from binance_simulator import BinanceDataSimulator, run_real_time_simulation
from binance_mode_simulator import BinanceModeSimulator, run_binance_mode_simulation, TRADING_MODES
from intelligent_simulator import AdvancedTradingSimulator, run_intelligent_simulation
from micro_profit_generator import MicroProfitGenerator, run_micro_profit_generator
from monthly_target_simulator import MonthlyTargetSimulator, run_monthly_target_simulation
from trade_logger import get_trade_logger
from portfolio_manager import get_portfolio_manager
from engine_manager import engine_manager
from engine_endpoints import register_engine_endpoints

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar endpoints de engines
register_engine_endpoints(app)

# WebSocket connections
websocket_connections = set()

# Variable global para el bucle de simulación
simulation_task = None
binance_simulation_task = None
binance_mode_tasks = {}  # Tareas para cada modo
intelligent_simulation_task = None
monthly_target_task = None

# Variable global para estrategias seleccionadas del Intelligent Simulator
selected_intelligent_strategies = ['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance']


def is_task_running(task):
    return task is not None and not task.done()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.add(websocket)
    
    # Notificar a todos los clientes que hay una nueva conexión
    await notify_clients(json.dumps({"type": "refresh", "message": "New client connected"}))
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        # Remover conexión de forma segura
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
        # Notificar que un cliente se desconectó
        await notify_clients(json.dumps({"type": "refresh", "message": "Client disconnected"}))
    except Exception as e:
        # Manejar otros errores de conexión
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
        print(f"WebSocket error: {e}")

async def notify_clients(message: str):
    """Notificar a todos los clientes conectados"""
    if websocket_connections:
        for connection in websocket_connections.copy():
            try:
                await connection.send_text(message)
            except:
                websocket_connections.discard(connection)

@app.get('/')
def hello_world():
    return 'Trading API with SQLite - Auto Simulation Active'

@app.post('/simulation/start')
async def start_simulation():
    """Iniciar la simulación automática"""
    global simulation_task
    
    if is_task_running(simulation_task):
        return {"status": "already_running"}
    
    # Iniciar tarea de simulación en background
    simulation_task = asyncio.create_task(
        run_periodic_simulation(get_db, lambda data: notify_clients(json.dumps(data)))
    )
    
    await notify_clients(json.dumps({
        "type": "simulation_started",
        "message": "Auto simulation started"
    }))
    
    return {"status": "started"}

@app.post('/simulation/stop')
async def stop_simulation():
    """Detener la simulación automática"""
    global simulation_task
    
    if is_task_running(simulation_task):
        simulation_task.cancel()
        simulation_task = None
        
        await notify_clients(json.dumps({
            "type": "simulation_stopped",
            "message": "Auto simulation stopped"
        }))
        
        return {"status": "stopped"}
    else:
        return {"status": "not_running"}

@app.post('/simulation/generate')
async def generate_single_trade(db: Session = Depends(get_db)):
    """Generar un trade manualmente para testing"""
    simulator = TradingSimulator(db)
    result = await simulator.run_simulation_cycle()
    
    if result:
        await notify_clients(json.dumps({
            "type": "manual_trade_generated",
            "message": "Manual trade generated",
            "data": {
                "trade_id": result.trade.id,
                "symbol": result.trade.symbol,
                "pnl": result.trade.pnl,
                "capital": result.equity.capital,
                "alerts_count": len(result.alerts)
            }
        }))
        
        return {"status": "success", "data": {
            "trade_id": result.trade.id,
            "symbol": result.trade.symbol,
            "pnl": result.trade.pnl
        }}
    else:
        return {"status": "error"}

@app.post('/binance/start')
async def start_binance_simulation():
    """Iniciar simulación con datos reales de Binance"""
    global binance_simulation_task
    
    if is_task_running(binance_simulation_task):
        return {"status": "already_running"}
    
    # Iniciar tarea de simulación Binance en background
    binance_simulation_task = asyncio.create_task(
        run_real_time_simulation(get_db, lambda data: notify_clients(json.dumps(data)))
    )
    
    await notify_clients(json.dumps({
        "type": "binance_simulation_started",
        "message": "Binance real-time simulation started"
    }))
    
    return {"status": "started"}

@app.post('/binance/stop')
async def stop_binance_simulation():
    """Detener simulación de Binance"""
    global binance_simulation_task, binance_mode_tasks
    
    if is_task_running(binance_simulation_task):
        binance_simulation_task.cancel()
        binance_simulation_task = None
        
        # Detener todos los modos de Binance automáticamente
        stopped_modes = []
        for mode, task in binance_mode_tasks.items():
            if is_task_running(task):
                task.cancel()
                stopped_modes.append(mode)
        
        # Limpiar tareas de modos
        binance_mode_tasks.clear()
        
        await notify_clients(json.dumps({
            "type": "binance_simulation_stopped",
            "message": "Binance simulation stopped",
            "data": {
                "stopped_modes": stopped_modes
            }
        }))
        
        return {"status": "stopped", "stopped_modes": stopped_modes}
    else:
        return {"status": "not_running"}

@app.post('/binance/generate')
async def generate_binance_trade(db: Session = Depends(get_db)):
    """Genera un trade con datos reales de Binance"""
    simulator = BinanceDataSimulator(db)
    
    try:
        trade = simulator.generate_realistic_trade()
        
        if trade:
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            # Actualizar capital
            simulator.current_capital += trade.pnl
            simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
            
            # Actualizar equity
            equity = simulator.update_equity()
            db.merge(equity)
            db.commit()
            
            # Calcular métricas
            metrics = simulator.calculate_metrics()
            if metrics:
                db.add(metrics)
                db.commit()
                db.refresh(metrics)
            
            # Verificar alertas
            alerts = simulator.check_alerts(trade)
            for alert in alerts:
                db.add(alert)
                db.commit()
                db.refresh(alert)
            
            await notify_clients(json.dumps({
                "type": "real_trade_generated",
                "message": f"Real Binance trade: {trade.symbol}",
                "data": {
                    "trade_id": trade.id,
                    "symbol": trade.symbol,
                    "strategy": trade.strategy,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": trade.pnl,
                    "capital": equity.capital,
                    "alerts_count": len(alerts),
                    "source": "binance_manual"
                }
            }))
            
            return {"status": "success", "data": {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "pnl": trade.pnl,
                "source": "binance"
            }}
        else:
            return {"status": "error", "message": "Failed to generate Binance trade"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Trades endpoints
@app.get('/trades')
def get_trades(db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.timestamp_entry.desc()).limit(50).all()
    return [
        {
            # Información básica
            "id": trade.id,
            "timestamp_entry": trade.timestamp_entry,
            "timestamp_exit": trade.timestamp_exit,
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            
            # Precios detallados
            "entry_price": trade.entry_price or 0.0,
            "exit_price": trade.exit_price or 0.0,
            "requested_entry_price": trade.requested_entry_price or 0.0,
            "requested_exit_price": trade.requested_exit_price or 0.0,
            
            # Tamaño y P&L
            "size": trade.size or 0.0,
            "pnl": trade.pnl or 0.0,
            "gross_pnl": trade.gross_pnl or 0.0,
            "pnl_percentage": round((trade.pnl / (trade.entry_price * trade.size) * 100), 2) if trade.entry_price and trade.size and trade.pnl else 0,
            
            # Costos de ejecución
            "entry_fees": trade.entry_fees or 0.0,
            "exit_fees": trade.exit_fees or 0.0,
            "slippage_cost": trade.slippage_cost or 0.0,
            "spread_cost": trade.spread_cost or 0.0,
            "total_costs": trade.total_costs or 0.0,
            "cost_impact_pct": round((trade.total_costs / (trade.entry_price * trade.size) * 100), 2) if trade.entry_price and trade.size and trade.total_costs else 0,
            
            # Información de riesgo
            "stop_loss": trade.stop_loss or 0.0,
            "take_profit": trade.take_profit or 0.0,
            "confidence": trade.confidence or 0.0,
            "volatility": trade.volatility or 0.0,
            
            # Metadatos del motor
            "source_engine": trade.source_engine or "unknown",
            "source_mode": trade.source_mode or "unknown",
            "direction": trade.direction or "UNKNOWN",
            
            # Tiempos
            "duration_ms": trade.duration_ms or 0,
            "duration_formatted": format_duration(trade.duration_ms or 0),
            
            # Estado y razón
            "entry_reason": trade.entry_reason or "unknown",
            "exit_reason": trade.exit_reason or "unknown",
            "status": trade.status or "unknown"
        }
        for trade in trades
    ]

def format_duration(duration_ms: int) -> str:
    """Formatear duración en milisegundos a texto legible"""
    if duration_ms == 0:
        return "0m"
    
    seconds = duration_ms / 1000
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{remaining_seconds}s"

@app.post('/trades')
async def create_trade(
    timestamp_entry: str,
    symbol: str,
    strategy: str,
    entry_price: float,
    size: float,
    timestamp_exit: str = "",
    exit_price: float = 0.0,
    pnl: float = 0.0,
    db: Session = Depends(get_db)
):
    trade = Trade(
        timestamp_entry=timestamp_entry,
        timestamp_exit=timestamp_exit,
        symbol=symbol,
        strategy=strategy,
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        pnl=pnl
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    
    # Notificar a todos los clientes sobre el nuevo trade
    await notify_clients(json.dumps({
        "type": "trade_added", 
        "message": "New trade added",
        "data": {
            "id": trade.id,
            "timestamp_entry": trade.timestamp_entry,
            "timestamp_exit": trade.timestamp_exit,
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "size": trade.size,
            "pnl": trade.pnl
        }
    }))
    
    return {"status": "success", "trade_id": trade.id}

@app.delete('/trades/{trade_id}')
async def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    db.delete(trade)
    db.commit()
    
    # Notificar a todos los clientes sobre el trade eliminado
    await notify_clients(json.dumps({
        "type": "trade_deleted",
        "message": "Trade deleted",
        "data": {"trade_id": trade_id}
    }))
    
    return {"status": "success"}

@app.delete('/trades')
async def delete_all_trades(db: Session = Depends(get_db)):
    try:
        db.query(Trade).delete()
        db.query(EquityCurve).delete()
        db.query(Metric).delete()
        db.query(Alert).delete()
        db.commit()

        await notify_clients(json.dumps({
            "type": "trades_cleared",
            "message": "All trades and related data cleared"
        }))

        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Equity Curve endpoints
@app.get('/equity')
def get_equity_curve(db: Session = Depends(get_db)):
    equity = db.query(EquityCurve).order_by(EquityCurve.timestamp.desc()).limit(100).all()
    return [
        {
            "timestamp": eq.timestamp,
            "capital": eq.capital
        }
        for eq in equity
    ]

@app.post('/equity')
async def update_equity(timestamp: str, capital: float, db: Session = Depends(get_db)):
    equity = EquityCurve(timestamp=timestamp, capital=capital)
    db.merge(equity)  # merge handles insert or update based on primary key
    db.commit()
    
    # Notificar a todos los clientes sobre la actualización de equity
    await notify_clients(json.dumps({
        "type": "equity_updated",
        "message": "Equity curve updated",
        "data": {"timestamp": timestamp, "capital": capital}
    }))
    
    return {"status": "success"}

# Metrics endpoints
@app.get('/metrics')
def get_metrics(db: Session = Depends(get_db)):
    metrics = db.query(Metric).order_by(Metric.timestamp.desc()).limit(10).all()
    return [
        {
            "id": metric.id,
            "timestamp": metric.timestamp,
            "win_rate": metric.win_rate,
            "sharpe": metric.sharpe,
            "max_drawdown": metric.max_drawdown,
            "profit_factor": metric.profit_factor
        }
        for metric in metrics
    ]

@app.post('/metrics')
async def create_metrics(
    timestamp: str,
    win_rate: float,
    sharpe: float,
    max_drawdown: float,
    profit_factor: float,
    db: Session = Depends(get_db)
):
    metric = Metric(
        timestamp=timestamp,
        win_rate=win_rate,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    
    # Notificar a todos los clientes sobre las nuevas métricas
    await notify_clients(json.dumps({
        "type": "metrics_updated",
        "message": "Metrics updated",
        "data": {
            "id": metric.id,
            "timestamp": metric.timestamp,
            "win_rate": metric.win_rate,
            "sharpe": metric.sharpe,
            "max_drawdown": metric.max_drawdown,
            "profit_factor": metric.profit_factor
        }
    }))
    
    return {"status": "success", "metric_id": metric.id}

# Alerts endpoints
@app.get('/alerts')
def get_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(20).all()
    return [
        {
            "id": alert.id,
            "timestamp": alert.timestamp,
            "type": alert.type,
            "message": alert.message
        }
        for alert in alerts
    ]

@app.post('/alerts')
async def create_alert(timestamp: str, type: str, message: str, db: Session = Depends(get_db)):
    alert = Alert(timestamp=timestamp, type=type, message=message)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    # Notificar a todos los clientes sobre la nueva alerta
    await notify_clients(json.dumps({
        "type": "alert_added",
        "message": "New alert",
        "data": {
            "id": alert.id,
            "timestamp": alert.timestamp,
            "type": alert.type,
            "message": alert.message
        }
    }))
    
    return {"status": "success", "alert_id": alert.id}

@app.post('/change')
async def trigger_change():
    """Endpoint para simular cambios en la base de datos"""
    await notify_clients(json.dumps({"type": "refresh", "message": "Data changed"}))
    return {"status": "notification sent"}

@app.post('/intelligent/start')
async def start_intelligent_simulation():
    """Iniciar simulación inteligente con análisis técnico"""
    global intelligent_simulation_task
    
    if is_task_running(intelligent_simulation_task):
        return {"status": "already_running"}
    
    # Iniciar tarea de simulación inteligente en background
    intelligent_simulation_task = asyncio.create_task(
        run_intelligent_simulation(get_db, lambda data: notify_clients(json.dumps(data)))
    )
    
    await notify_clients(json.dumps({
        "type": "intelligent_simulation_started",
        "message": "Intelligent simulation with technical analysis started"
    }))
    
    return {"status": "started"}

@app.post('/intelligent/stop')
async def stop_intelligent_simulation():
    """Detener simulación inteligente"""
    global intelligent_simulation_task
    
    if is_task_running(intelligent_simulation_task):
        intelligent_simulation_task.cancel()
        intelligent_simulation_task = None
        
        await notify_clients(json.dumps({
            "type": "intelligent_simulation_stopped",
            "message": "Intelligent simulation stopped"
        }))
        
        return {"status": "stopped"}
    else:
        return {"status": "not_running"}

@app.post('/intelligent/generate')
async def generate_intelligent_trade(db: Session = Depends(get_db)):
    """Genera un trade inteligente manualmente"""
    from intelligent_simulator import AdvancedTradingSimulator
    from datetime import datetime
    
    simulator = AdvancedTradingSimulator(db)
    
    try:
        trade = simulator.generate_intelligent_trade()
        
        if trade:
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            # Actualizar capital
            simulator.current_capital += trade.pnl
            simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
            simulator.trades_count += 1
            
            if trade.pnl > 0:
                simulator.winning_trades += 1
            else:
                simulator.losing_trades += 1
            
            # Actualizar drawdown
            simulator.current_drawdown = max(0, (simulator.max_capital - simulator.current_capital) / simulator.max_capital * 100)
            
            # Actualizar equity
            equity = EquityCurve(
                timestamp=datetime.now().isoformat(),
                capital=round(simulator.current_capital, 2)
            )
            db.merge(equity)
            db.commit()
            
            # Calcular métricas
            metrics = simulator.calculate_comprehensive_metrics()
            if metrics:
                db.add(metrics)
                db.commit()
                db.refresh(metrics)
            
            # Generar alertas
            alerts = simulator.generate_intelligent_alerts(trade)
            for alert in alerts:
                db.add(alert)
                db.commit()
                db.refresh(alert)
            
            await notify_clients(json.dumps({
                "type": "intelligent_trade_generated",
                "message": f"Intelligent trade: {trade.symbol} ({('+' if trade.pnl > 0 else '')}${trade.pnl:.2f})",
                "data": {
                    "trade_id": trade.id,
                    "symbol": trade.symbol,
                    "strategy": trade.strategy,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": trade.pnl,
                    "pnl_percentage": (trade.pnl / 100) * 100,
                    "capital": equity.capital,
                    "total_trades": simulator.trades_count,
                    "win_rate": (simulator.winning_trades / simulator.trades_count) * 100 if simulator.trades_count > 0 else 0,
                    "current_drawdown": simulator.current_drawdown,
                    "alerts_count": len(alerts),
                    "source": "intelligent_manual"
                }
            }))
            
            return {"status": "success", "data": {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "pnl": trade.pnl,
                "strategy": trade.strategy,
                "source": "intelligent"
            }}
        else:
            return {"status": "error", "message": "Failed to generate intelligent trade"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post('/intelligent/strategies')
async def update_intelligent_strategies(request: dict):
    """Actualizar estrategias seleccionadas para el Intelligent Simulator"""
    try:
        strategies = request.get('strategies', [])
        
        # Validar estrategias
        valid_strategies = ['MACD_Signal', 'MA_Cross', 'RSI_Divergence', 'Bollinger_Bands', 'Volume_Breakout', 'Support_Resistance']
        
        # Filtrar solo estrategias válidas
        filtered_strategies = [s for s in strategies if s in valid_strategies]
        
        # Guardar en variable global o configuración
        # Por ahora, lo guardamos en una variable global (podría mejorarse con DB)
        global selected_intelligent_strategies
        selected_intelligent_strategies = filtered_strategies
        
        # Notificar cambio
        await notify_clients(json.dumps({
            "type": "intelligent_strategies_updated",
            "data": {
                "strategies": filtered_strategies,
                "count": len(filtered_strategies)
            }
        }))
        
        return {
            "status": "success", 
            "strategies": filtered_strategies,
            "message": f"Updated {len(filtered_strategies)} strategies"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post('/micro-profit/generate')
async def generate_micro_profit(request: dict, db: Session = Depends(get_db)):
    """Generar micro-trades seguros de ~$0.05 cada uno"""
    try:
        iterations = request.get('iterations', 5)  # Default 5 trades
        
        # Validar iteraciones
        if iterations < 1 or iterations > 50:
            return {"status": "error", "message": "Iterations must be between 1 and 50"}
        
        # Ejecutar micro-trading
        result = await run_micro_profit_generator(iterations, db)
        
        if result['status'] == 'success':
            # Notificar trades generados
            await notify_clients(json.dumps({
                "type": "micro_profit_generated",
                "data": {
                    "trades_generated": result['trades_generated'],
                    "stats": result['stats'],
                    "iterations": iterations,
                    "timestamp": datetime.now().isoformat()
                }
            }))
        
        return result
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/micro-profit/stats')
async def get_micro_profit_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas de micro-trading"""
    try:
        generator = MicroProfitGenerator(db)
        stats = generator.get_micro_stats()
        
        return {
            "status": "success",
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/trades/active')
async def get_active_trades(db: Session = Depends(get_db)):
    """Obtener trades activos actualmente abiertos"""
    try:
        logger = get_trade_logger(db)
        summary = logger.get_active_trades_summary()
        
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/trades/log')
async def get_trades_log(db: Session = Depends(get_db)):
    """Obtener log de trades recientes"""
    try:
        # Leer últimas líneas del log
        logs = []
        try:
            with open("trades_log.json", "r") as f:
                lines = f.readlines()[-50:]  # Últimas 50 líneas
                for line in lines:
                    if line.strip():
                        logs.append(json.loads(line.strip()))
        except FileNotFoundError:
            logs = []
        
        return {
            "status": "success",
            "logs": logs,
            "count": len(logs),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/prices')
def get_prices():
    """Obtener precios actuales de todos los símbolos"""
    try:
        from intelligent_simulator import BinancePriceManager
        price_manager = BinancePriceManager()
        price_manager.initialize_client()
        
        prices = asyncio.run(price_manager.get_all_prices())
        
        return {
            "status": "success",
            "prices": prices,
            "last_update": price_manager.last_update,
            "symbols": price_manager.symbols
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/stats')
def get_system_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas completas del sistema"""
    try:
        trades = db.query(Trade).all()
        metrics = db.query(Metric).order_by(Metric.timestamp.desc()).first()
        alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(10).all()
        
        # Estadísticas básicas
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        total_pnl = sum(t.pnl for t in trades)
        
        # Por símbolo
        symbol_stats = {}
        for trade in trades:
            symbol = trade.symbol
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {"trades": 0, "wins": 0, "pnl": 0}
            symbol_stats[symbol]["trades"] += 1
            symbol_stats[symbol]["wins"] += 1 if trade.pnl > 0 else 0
            symbol_stats[symbol]["pnl"] += trade.pnl
        
        return {
            "status": "success",
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "total_pnl": round(total_pnl, 2),
            "current_capital": 100 + total_pnl, # $100 inicial + P&L
            "win_rate": round((winning_trades / total_trades) * 100, 2) if total_trades > 0 else 0,
            "metrics": metrics.__dict__ if metrics else None,
            "recent_alerts": [
                {
                    "id": alert.id,
                    "type": alert.type,
                    "message": alert.message,
                    "timestamp": alert.timestamp
                } for alert in alerts
            ],
            "symbol_performance": symbol_stats
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Endpoint para consultar el estado de las simulaciones
@app.get('/status')
def get_simulation_status():
    binance_running = is_task_running(binance_simulation_task)
    
    return {
        "simulation": "running" if is_task_running(simulation_task) else "stopped",
        "binance": "running" if binance_running else "stopped",
        "intelligent": "running" if is_task_running(intelligent_simulation_task) else "stopped",
        "monthly_target": "running" if is_task_running(monthly_target_task) else "stopped",
        "binance_modes": {
            mode: {
                "status": "running" if is_task_running(task) else "stopped",
                "can_run": binance_running  # Indica si puede running dado el estado de Binance principal
            }
            for mode, task in binance_mode_tasks.items()
        },
        "dependencies": {
            "binance_modes_require_binance": True
        }
    }


@app.on_event("startup")
async def startup_event():
    """Inicialización del servidor y del Engine Manager"""
    global engine_manager
    
    # Inicializar el Engine Manager
    await engine_manager.initialize(notification_callback=notify_clients)
    
    print("🚀 Trading system initialized with Engine Manager")
    print(f"📊 Available engines: {list(engine_manager.engines.keys())}")
    return

@app.on_event("shutdown")
async def shutdown_event():
    """Detener todas las simulaciones y engines al apagar el servidor"""
    global simulation_task, binance_simulation_task, intelligent_simulation_task, monthly_target_task, binance_mode_tasks, engine_manager
    
    # Detener tareas antiguas
    if simulation_task and not simulation_task.done():
        simulation_task.cancel()
    
    if binance_simulation_task and not binance_simulation_task.done():
        binance_simulation_task.cancel()
    
    if intelligent_simulation_task and not intelligent_simulation_task.done():
        intelligent_simulation_task.cancel()
    
    if monthly_target_task and not monthly_target_task.done():
        monthly_target_task.cancel()
    
    # Detener tareas de modos Binance
    for mode, task in binance_mode_tasks.items():
        if task and not task.done():
            task.cancel()
    
    # Apagar el Engine Manager
    await engine_manager.shutdown()
    
    print("🛑 All systems shut down gracefully")

@app.post('/monthly/start')
async def start_monthly_target_simulation():
    """Iniciar simulación optimizada para 20% mensual"""
    global monthly_target_task
    
    if is_task_running(monthly_target_task):
        return {"status": "already_running"}
    
    # Iniciar tarea de simulación mensual en background
    monthly_target_task = asyncio.create_task(
        run_monthly_target_simulation(get_db, lambda data: notify_clients(json.dumps(data)))
    )
    
    await notify_clients(json.dumps({
        "type": "monthly_target_started",
        "message": "Monthly target simulation started (20% monthly goal)"
    }))
    
    return {"status": "started"}

@app.post('/monthly/stop')
async def stop_monthly_target_simulation():
    """Detener simulación mensual"""
    global monthly_target_task
    
    if is_task_running(monthly_target_task):
        monthly_target_task.cancel()
        monthly_target_task = None
        
        await notify_clients(json.dumps({
            "type": "monthly_target_stopped",
            "message": "Monthly target simulation stopped"
        }))
        
        return {"status": "stopped"}
    else:
        return {"status": "not_running"}

@app.post('/monthly/generate')
async def generate_monthly_target_trade(db: Session = Depends(get_db)):
    """Genera un trade optimizado para 20% mensual"""
    from datetime import datetime
    
    simulator = MonthlyTargetSimulator(db)
    
    try:
        trade = simulator.generate_monthly_target_trade()
        
        if trade:
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            # Actualizar capital
            simulator.current_capital += trade.pnl
            simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
            
            # Actualizar equity
            equity = EquityCurve(
                timestamp=datetime.now().isoformat(),
                capital=round(simulator.current_capital, 2)
            )
            db.merge(equity)
            db.commit()
            
            await notify_clients(json.dumps({
                "type": "monthly_target_trade_generated",
                "message": f"Monthly target trade: {trade.symbol} (${trade.pnl:+.2f})",
                "data": {
                    "trade_id": trade.id,
                    "symbol": trade.symbol,
                    "strategy": trade.strategy,
                    "pnl": trade.pnl,
                    "capital": equity.capital,
                    "daily_trades": simulator.daily_trades,
                    "daily_pnl": simulator.daily_pnl,
                    "consecutive_losses": simulator.consecutive_losses,
                    "monthly_progress": (simulator.current_capital - 100) / 20,
                    "source": "monthly_target_manual"
                }
            }))
            
            return {"status": "success", "data": {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "pnl": trade.pnl,
                "strategy": trade.strategy,
                "source": "monthly_target"
            }}
        else:
            return {"status": "no_trade", "message": "No trade generated - risk limits reached"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Binance Mode Simulation Endpoints
@app.get('/binance/modes')
def get_trading_modes():
    """Obtener modos de trading disponibles"""
    return {
        "modes": {
            mode: {
                "name": config.name,
                "risk_percentage": config.risk_percentage,
                "win_rate": config.win_rate,
                "reward_risk_ratio": config.reward_risk_ratio,
                "max_consecutive_losses": config.max_consecutive_losses,
                "trades_per_hour": config.trades_per_hour
            }
            for mode, config in TRADING_MODES.items()
        }
    }

@app.post('/binance/mode/{mode}/start')
async def start_binance_mode_simulation(mode: str):
    """Iniciar simulación Binance con modo específico"""
    global binance_mode_tasks, binance_simulation_task
    
    if mode not in TRADING_MODES:
        raise HTTPException(status_code=400, detail=f"Modo '{mode}' no válido. Modos disponibles: {list(TRADING_MODES.keys())}")
    
    # Verificar que la simulación principal de Binance esté running
    if not is_task_running(binance_simulation_task):
        return {"status": "error", "message": "La simulación principal de Binance no está running. Inicie Binance primero."}
    
    if mode in binance_mode_tasks and is_task_running(binance_mode_tasks[mode]):
        return {"status": "already_running", "mode": mode}
    
    # Iniciar tarea de simulación en background
    binance_mode_tasks[mode] = asyncio.create_task(
        run_binance_mode_simulation(get_db, lambda data: notify_clients(json.dumps(data)), mode)
    )
    
    await notify_clients(json.dumps({
        "type": "binance_mode_started",
        "message": f"Binance simulation started in {TRADING_MODES[mode].name} mode",
        "data": {
            "mode": mode,
            "mode_name": TRADING_MODES[mode].name,
            "risk_percentage": TRADING_MODES[mode].risk_percentage
        }
    }))
    
    return {"status": "started", "mode": mode, "mode_name": TRADING_MODES[mode].name}

@app.post('/binance/mode/{mode}/stop')
async def stop_binance_mode_simulation(mode: str):
    """Detener simulación Binance de modo específico"""
    global binance_mode_tasks
    
    if mode not in binance_mode_tasks:
        return {"status": "not_running", "mode": mode}
    
    if is_task_running(binance_mode_tasks[mode]):
        binance_mode_tasks[mode].cancel()
        del binance_mode_tasks[mode]
        
        await notify_clients(json.dumps({
            "type": "binance_mode_stopped",
            "message": f"Binance simulation stopped for {TRADING_MODES[mode].name} mode",
            "data": {"mode": mode}
        }))
        
        return {"status": "stopped", "mode": mode}
    else:
        return {"status": "not_running", "mode": mode}

@app.post('/binance/mode/{mode}/generate')
async def generate_binance_mode_trade(mode: str, db: Session = Depends(get_db)):
    """Genera un trade con modo específico de Binance"""
    if mode not in TRADING_MODES:
        raise HTTPException(status_code=400, detail=f"Modo '{mode}' no válido")
    
    simulator = BinanceModeSimulator(db, mode)
    
    try:
        trade = simulator.generate_mode_trade()
        
        if trade:
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            # Actualizar capital
            simulator.current_capital += trade.pnl
            simulator.max_capital = max(simulator.max_capital, simulator.current_capital)
            
            # Actualizar equity
            equity = EquityCurve(
                timestamp=datetime.now().isoformat(),
                capital=round(simulator.current_capital, 2)
            )
            db.merge(equity)
            db.commit()
            
            await notify_clients(json.dumps({
                "type": "binance_mode_trade_generated",
                "message": f"Binance {TRADING_MODES[mode].name} trade: {trade.symbol} (${trade.pnl:+.2f})",
                "data": {
                    "trade_id": trade.id,
                    "symbol": trade.symbol,
                    "strategy": trade.strategy,
                    "pnl": trade.pnl,
                    "capital": equity.capital,
                    "mode": TRADING_MODES[mode].name,
                    "risk_percentage": TRADING_MODES[mode].risk_percentage,
                    "daily_trades": simulator.daily_trades,
                    "daily_pnl": simulator.daily_pnl,
                    "consecutive_losses": simulator.consecutive_losses,
                    "source": f"binance_{mode}_manual"
                }
            }))
            
            return {"status": "success", "data": {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "pnl": trade.pnl,
                "strategy": trade.strategy,
                "mode": TRADING_MODES[mode].name,
                "source": f"binance_{mode}"
            }}
        else:
            return {"status": "no_trade", "message": "No trade generated - risk limits reached"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Portfolio Manager Endpoints
@app.get('/portfolio/summary')
def get_portfolio_summary(db: Session = Depends(get_db)):
    """Obtener resumen completo del portfolio"""
    try:
        portfolio = get_portfolio_manager(db)
        
        # Configurar callback de notificación si no está configurado
        if not portfolio.notify_callbacks:
            portfolio.add_notify_callback(lambda data: notify_clients(data))
        
        return portfolio.get_portfolio_summary()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post('/portfolio/engine/{engine_name}/register')
def register_engine(engine_name: str, db: Session = Depends(get_db)):
    """Registrar un motor de trading"""
    try:
        portfolio = get_portfolio_manager(db)
        portfolio.register_engine(engine_name)
        
        return {"status": "success", "message": f"Engine {engine_name} registered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post('/portfolio/engine/{engine_name}/unregister')
def unregister_engine(engine_name: str, db: Session = Depends(get_db)):
    """Desregistrar un motor de trading"""
    try:
        portfolio = get_portfolio_manager(db)
        portfolio.unregister_engine(engine_name)
        
        return {"status": "success", "message": f"Engine {engine_name} unregistered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get('/portfolio/signals')
def get_signal_history(db: Session = Depends(get_db)):
    """Obtener historial de señales del portfolio"""
    try:
        portfolio = get_portfolio_manager(db)
        
        # Retornar últimas 50 señales
        recent_signals = portfolio.signal_history[-50:] if portfolio.signal_history else []
        
        return {
            "signals": recent_signals,
            "total_signals": len(portfolio.signal_history),
            "active_engines": list(portfolio.active_engines)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post('/portfolio/limits/update')
def update_portfolio_limits(request: dict, db: Session = Depends(get_db)):
    """Actualizar límites del portfolio"""
    try:
        portfolio = get_portfolio_manager(db)
        
        # Actualizar límites si se proporcionan
        if 'max_engine_exposure' in request:
            portfolio.state.max_engine_exposure = request['max_engine_exposure']
        if 'max_symbol_exposure' in request:
            portfolio.state.max_symbol_exposure = request['max_symbol_exposure']
        if 'max_total_exposure' in request:
            portfolio.state.max_total_exposure = request['max_total_exposure']
        if 'max_daily_loss' in request:
            portfolio.state.max_daily_loss = request['max_daily_loss']
        if 'max_drawdown_limit' in request:
            portfolio.state.max_drawdown_limit = request['max_drawdown_limit']
        
        return {"status": "success", "message": "Portfolio limits updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5000)
