from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import asyncio
from typing import List, Dict, Any
from database import get_db, Trade, EquityCurve, Metric, Alert
from simulator import TradingSimulator, run_periodic_simulation
from binance_simulator import BinanceDataSimulator, run_real_time_simulation
from intelligent_simulator import AdvancedTradingSimulator, run_intelligent_simulation

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
websocket_connections = set()

# Variable global para el bucle de simulación
simulation_task = None
binance_simulation_task = None
intelligent_simulation_task = None


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
        websocket_connections.remove(websocket)
        # Notificar que un cliente se desconectó
        await notify_clients(json.dumps({"type": "refresh", "message": "Client disconnected"}))

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
    global binance_simulation_task
    
    if is_task_running(binance_simulation_task):
        binance_simulation_task.cancel()
        binance_simulation_task = None
        
        await notify_clients(json.dumps({
            "type": "binance_simulation_stopped",
            "message": "Binance simulation stopped"
        }))
        
        return {"status": "stopped"}
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
        for trade in trades
    ]

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
    return {
        "simulation": "running" if is_task_running(simulation_task) else "stopped",
        "binance": "running" if is_task_running(binance_simulation_task) else "stopped",
        "intelligent": "running" if is_task_running(intelligent_simulation_task) else "stopped"
    }


@app.on_event("startup")
async def startup_event():
    """Inicialización del servidor sin iniciar simulaciones automáticamente"""
    # Este hook queda para futuras inicializaciones necesarias.
    return

@app.on_event("shutdown")
async def shutdown_event():
    """Detener simulación al apagar el servidor"""
    global simulation_task, binance_simulation_task, intelligent_simulation_task
    
    if simulation_task and not simulation_task.done():
        simulation_task.cancel()
    
    if binance_simulation_task and not binance_simulation_task.done():
        binance_simulation_task.cancel()
    
    if intelligent_simulation_task and not intelligent_simulation_task.done():
        intelligent_simulation_task.cancel()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5000)
