"""
Price Monitor - Monitorea precios en tiempo real para trades manuales
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from database import get_db, ManualTrade
from sqlalchemy.orm import Session

class PriceMonitor:
    def __init__(self):
        self.active_trades: Dict[int, Dict] = {}
        self.price_cache: Dict[str, float] = {}
        self.running = False
        self.notification_callback = None
        
    async def initialize(self, notification_callback=None):
        """Inicializar el monitor con callback de notificaciones"""
        self.notification_callback = notification_callback
        await self.load_active_trades()
        
    async def load_active_trades(self):
        """Cargar trades activos desde la base de datos"""
        db = next(get_db())
        try:
            active_trades = db.query(ManualTrade).filter(
                ManualTrade.status == "executed"
            ).all()
            
            for trade in active_trades:
                self.active_trades[trade.id] = {
                    "symbol": trade.symbol,
                    "action": trade.action,
                    "entry_price": trade.price,
                    "quantity": trade.quantity,
                    "timestamp": trade.timestamp.isoformat()
                }
        finally:
            db.close()
            
    async def add_trade(self, trade_id: int, symbol: str, action: str, 
                       entry_price: float, quantity: float):
        """Agregar un nuevo trade al monitoreo"""
        self.active_trades[trade_id] = {
            "symbol": symbol,
            "action": action,
            "entry_price": entry_price,
            "quantity": quantity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def remove_trade(self, trade_id: int):
        """Remover un trade del monitoreo"""
        if trade_id in self.active_trades:
            del self.active_trades[trade_id]
            
    async def update_prices(self):
        """Actualizar precios desde Binance"""
        try:
            from intelligent_simulator import BinancePriceManager
            price_manager = BinancePriceManager()
            price_manager.initialize_client()
            
            # Obtener símbolos únicos de trades activos
            symbols = list(set(trade["symbol"] for trade in self.active_trades.values()))
            
            # Obtener precios actuales
            prices = await price_manager.get_prices_for_symbols(symbols)
            
            for symbol, price in prices.items():
                self.price_cache[symbol] = price
                
        except Exception as e:
            print(f"Error updating prices: {e}")
            
    def calculate_pnl(self, trade: Dict, current_price: float) -> float:
        """Calcular P&L para un trade"""
        if trade["action"] == "BUY":
            return (current_price - trade["entry_price"]) * trade["quantity"]
        else:  # SELL
            return (trade["entry_price"] - current_price) * trade["quantity"]
            
    def calculate_pnl_percentage(self, trade: Dict, current_price: float) -> float:
        """Calcular porcentaje de P&L"""
        if trade["action"] == "BUY":
            return ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100
        else:  # SELL
            return ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100
            
    async def check_alerts(self):
        """Verificar alertas de precio"""
        for trade_id, trade in self.active_trades.items():
            symbol = trade["symbol"]
            if symbol not in self.price_cache:
                continue
                
            current_price = self.price_cache[symbol]
            pnl = self.calculate_pnl(trade, current_price)
            pnl_percentage = self.calculate_pnl_percentage(trade, current_price)
            
            # Alertas de profit/loss
            if pnl_percentage >= 5.0:  # 5% profit
                await self.send_alert(trade_id, trade, current_price, pnl, pnl_percentage, "TAKE_PROFIT")
            elif pnl_percentage <= -3.0:  # -3% loss
                await self.send_alert(trade_id, trade, current_price, pnl, pnl_percentage, "STOP_LOSS")
                
    async def send_alert(self, trade_id: int, trade: Dict, current_price: float, 
                        pnl: float, pnl_percentage: float, alert_type: str):
        """Enviar alerta de trading"""
        message = {
            "type": "manual_trade_alert",
            "trade_id": trade_id,
            "symbol": trade["symbol"],
            "action": trade["action"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "pnl": pnl,
            "pnl_percentage": pnl_percentage,
            "alert_type": alert_type,
            "message": self._format_alert_message(trade, current_price, pnl, pnl_percentage, alert_type),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.notification_callback:
            await self.notification_callback(json.dumps(message))
            
    def _format_alert_message(self, trade: Dict, current_price: float, 
                             pnl: float, pnl_percentage: float, alert_type: str) -> str:
        """Formatear mensaje de alerta"""
        symbol = trade["symbol"]
        action = trade["action"]
        entry_price = trade["entry_price"]
        
        if alert_type == "TAKE_PROFIT":
            return f"🎯 TAKE PROFIT: {action} {symbol} at ${entry_price} → ${current_price:.2f} (+{pnl_percentage:.1f}%, +${pnl:.2f})"
        else:  # STOP_LOSS
            return f"⛔ STOP LOSS: {action} {symbol} at ${entry_price} → ${current_price:.2f} ({pnl_percentage:.1f}%, ${pnl:.2f})"
            
    async def get_trade_status(self, trade_id: int) -> Optional[Dict]:
        """Obtener estado actual de un trade"""
        if trade_id not in self.active_trades:
            return None
            
        trade = self.active_trades[trade_id]
        symbol = trade["symbol"]
        
        if symbol not in self.price_cache:
            return trade
            
        current_price = self.price_cache[symbol]
        pnl = self.calculate_pnl(trade, current_price)
        pnl_percentage = self.calculate_pnl_percentage(trade, current_price)
        
        return {
            **trade,
            "current_price": current_price,
            "pnl": pnl,
            "pnl_percentage": pnl_percentage,
            "last_update": datetime.utcnow().isoformat()
        }
        
    async def get_all_trades_status(self) -> List[Dict]:
        """Obtener estado de todos los trades activos"""
        statuses = []
        for trade_id in self.active_trades:
            status = await self.get_trade_status(trade_id)
            if status:
                statuses.append(status)
        return statuses
        
    async def start_monitoring(self):
        """Iniciar monitoreo continuo"""
        self.running = True
        print("🔍 Price monitoring started")
        
        while self.running:
            try:
                await self.update_prices()
                await self.check_alerts()
                await asyncio.sleep(10)  # Actualizar cada 10 segundos
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Esperar más si hay error
                
    async def stop_monitoring(self):
        """Detener monitoreo"""
        self.running = False
        print("⏹️ Price monitoring stopped")

# Instancia global
price_monitor = PriceMonitor()
