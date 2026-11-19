# Binance Mode Simulation Endpoints
# Agregar estos endpoints al final de app.py

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
    global binance_mode_tasks
    
    if mode not in TRADING_MODES:
        raise HTTPException(status_code=400, detail=f"Modo '{mode}' no válido. Modos disponibles: {list(TRADING_MODES.keys())}")
    
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
        trade = await simulator.generate_mode_trade()
        
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
