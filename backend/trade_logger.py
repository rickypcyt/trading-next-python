import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database import Trade

class TradeLogger:
    def __init__(self, db: Session):
        self.db = db
        self.active_trades = {}  # trades abiertos pero no cerrados
        
    def log_trade_opened(self, trade: Trade, strategy_info: Optional[Dict] = None) -> str:
        """Registrar cuando un trade se abre"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "TRADE_OPENED",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            "entry_price": trade.entry_price,
            "size": trade.size,
            "direction": strategy_info.get("direction", "unknown") if strategy_info else "unknown",
            "type": trade.direction or strategy_info.get("direction", "unknown") if strategy_info else (trade.direction or "unknown"),
            "status": "OPEN",
            "reason": strategy_info.get("reason", "trade_generated") if strategy_info else "trade_generated",
            "market_conditions": strategy_info.get("market_conditions", {}) if strategy_info else {},
            "risk_amount": strategy_info.get("risk_amount", 0) if strategy_info else 0,
            "target_profit": strategy_info.get("target_profit", 0) if strategy_info else 0
        }
        
        # Guardar en active trades
        self.active_trades[trade.id] = {
            "opened_at": log_entry["timestamp"],
            "entry_price": trade.entry_price,
            "symbol": trade.symbol,
            "strategy": trade.strategy
        }
        
        # Escribir a consola y archivo
        self._write_log(log_entry)
        return log_entry["timestamp"]
    
    def log_trade_closed(self, trade: Trade, close_reason: str = "target_reached") -> str:
        """Registrar cuando un trade se cierra"""
        # Obtener información del trade activo
        active_info = self.active_trades.get(trade.id, {})
        
        # Calcular duración real
        duration_seconds = 0
        if "opened_at" in active_info:
            opened_time = datetime.fromisoformat(active_info["opened_at"])
            close_time = datetime.now()
            duration_seconds = (close_time - opened_time).total_seconds()
        
        # Calcular price movement
        price_movement = 0.0
        if trade.entry_price:
            price_movement = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
        pnl_percentage = trade.pnl_percentage if hasattr(trade, 'pnl_percentage') else 0.0
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "TRADE_CLOSED",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "size": trade.size,
            "pnl": trade.pnl,
            "pnl_percentage": round(pnl_percentage, 4),
            "price_movement": round(price_movement, 4),
            "duration_seconds": round(duration_seconds, 1),
            "duration_formatted": self._format_duration(duration_seconds),
            "status": "CLOSED",
            "close_reason": close_reason,
            "result": "PROFIT" if trade.pnl > 0 else "LOSS" if trade.pnl < 0 else "BREAKEVEN",
            "opened_at": active_info.get("opened_at", "unknown"),
            "closed_at": log_entry["timestamp"]
        }
        
        # Remover de active trades
        if trade.id in self.active_trades:
            del self.active_trades[trade.id]
        
        # Escribir a consola y archivo
        self._write_log(log_entry)
        return log_entry["timestamp"]
    
    def log_trade_modified(self, trade: Trade, modification: str, old_value: Any, new_value: Any) -> str:
        """Registrar modificaciones a un trade"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "TRADE_MODIFIED",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "strategy": trade.strategy,
            "modification": modification,
            "old_value": old_value,
            "new_value": new_value,
            "status": "MODIFIED"
        }
        
        self._write_log(log_entry)
        return log_entry["timestamp"]
    
    def get_active_trades_summary(self) -> Dict[str, Any]:
        """Obtener resumen de trades activos"""
        if not self.active_trades:
            return {"active_count": 0, "trades": []}
        
        summary = {
            "active_count": len(self.active_trades),
            "timestamp": datetime.now().isoformat(),
            "trades": []
        }
        
        for trade_id, info in self.active_trades.items():
            # Calcular P&L actual con precio actual (simulado)
            current_pnl = 0  # Aquí podrías calcular con precio actual real
            summary["trades"].append({
                "trade_id": trade_id,
                "symbol": info["symbol"],
                "strategy": info["strategy"],
                "entry_price": info["entry_price"],
                "opened_at": info["opened_at"],
                "current_pnl": current_pnl,
                "duration_seconds": self._calculate_duration(info["opened_at"])
            })
        
        return summary
    
    def _write_log(self, log_entry: Dict[str, Any]):
        """Escribir log a consola con formato especial"""
        # Formato especial para consola
        symbol = log_entry.get("symbol", "UNKNOWN")
        event = log_entry.get("event", "UNKNOWN")
        timestamp = log_entry.get("timestamp", "")
        
        if event == "TRADE_OPENED":
            direction = log_entry.get("direction", "?")
            entry_price = log_entry.get("entry_price", 0)
            size = log_entry.get("size", 0)
            risk = log_entry.get("risk_amount", 0)
            
            print(f"🔓 TRADE OPENED | {symbol} | {direction} | Entry: ${entry_price} | Size: {size} | Risk: ${risk:.4f} | {timestamp}")
            
        elif event == "TRADE_CLOSED":
            result = log_entry.get("result", "UNKNOWN")
            pnl = log_entry.get("pnl", 0)
            pnl_pct = log_entry.get("pnl_percentage", 0)
            duration = log_entry.get("duration_formatted", "")
            close_reason = log_entry.get("close_reason", "")
            
            emoji = "🟢" if result == "PROFIT" else "🔴" if result == "LOSS" else "🟡"
            print(f"{emoji} TRADE CLOSED | {symbol} | {result} | P&L: ${pnl:.4f} ({pnl_pct:+.2f}%) | Duration: {duration} | Reason: {close_reason} | {timestamp}")
            
        elif event == "TRADE_MODIFIED":
            modification = log_entry.get("modification", "")
            print(f"🔄 TRADE MODIFIED | {symbol} | {modification} | {timestamp}")
        
        # También guardar en archivo log
        try:
            with open("trades_log.json", "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass  # Si falla escribir archivo, continuar con consola
    
    def _format_duration(self, seconds: float) -> str:
        """Formatear duración en formato legible"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.0f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _calculate_duration(self, opened_at: str) -> float:
        """Calcular duración en segundos"""
        try:
            opened_time = datetime.fromisoformat(opened_at)
            return (datetime.now() - opened_time).total_seconds()
        except:
            return 0
    
    def print_active_summary(self):
        """Imprimir resumen de trades activos"""
        summary = self.get_active_trades_summary()
        if summary["active_count"] > 0:
            print(f"\n📊 ACTIVE TRADES SUMMARY ({summary['active_count']} trades)")
            print("=" * 80)
            for trade in summary["trades"]:
                duration = self._format_duration(trade["duration_seconds"])
                print(f"📈 {trade['symbol']} | {trade['strategy']} | Entry: ${trade['entry_price']} | Duration: {duration}")
            print("=" * 80)
        else:
            print("\n✅ No active trades")

# Logger global
trade_logger = None

def get_trade_logger(db: Session) -> TradeLogger:
    """Obtener instancia del logger de trades"""
    global trade_logger
    if trade_logger is None:
        trade_logger = TradeLogger(db)
    return trade_logger
