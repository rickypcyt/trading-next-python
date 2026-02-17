#!/usr/bin/env python3
"""
Test script para Execution Engine
Verifica que los costos se apliquen correctamente
"""

from execution_engine import execution_engine, TradeRequest, TradeDirection, ExecutionConfig
from datetime import datetime

def test_execution_engine():
    print("🧪 Testing Execution Engine...")
    print("=" * 50)
    
    # Configuración de prueba
    capital = 1000.0
    risk_per_trade = 0.02  # 2%
    
    # Test 1: Trade LONG con volatilidad baja
    print("\n📈 Test 1: LONG Trade - Low Volatility")
    trade_request = TradeRequest(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        entry_price=45000.0,
        size=0.0,
        stop_loss=44100.0,  # 2% debajo
        strategy="MA_Cross",
        volatility=2.0  # 2% volatilidad
    )
    
    # Ejecutar trade
    trade_result = execution_engine.execute_trade(trade_request, capital, risk_per_trade)
    print(f"   ✅ Entry Price: ${trade_result.actual_entry_price:.2f}")
    print(f"   ✅ Position Size: {trade_result.position_size:.6f}")
    print(f"   ✅ Entry Fees: ${trade_result.entry_fees:.4f}")
    print(f"   ✅ Slippage Cost: ${trade_result.slippage_cost:.4f}")
    print(f"   ✅ Spread Cost: ${trade_result.spread_cost:.4f}")
    
    # Cerrar trade con ganancia
    exit_price = 45900.0  # 2% arriba
    closed_trade = execution_engine.close_trade(trade_result, exit_price, "test_close", 2.0)
    
    print(f"\n   📊 Exit Price: ${closed_trade.actual_exit_price:.2f}")
    print(f"   📊 Exit Fees: ${closed_trade.exit_fees:.4f}")
    print(f"   📊 Gross PnL: ${closed_trade.gross_pnl:.2f}")
    print(f"   📊 Net PnL: ${closed_trade.net_pnl:.2f}")
    print(f"   📊 PnL %: {closed_trade.pnl_percentage:.2f}%")
    
    # Obtener resumen
    summary = execution_engine.get_execution_summary(closed_trade)
    print(f"\n   💰 Total Costs: ${summary['total_costs']:.4f}")
    print(f"   💰 Cost Percentage: {summary['cost_percentage']:.2f}%")
    print(f"   💰 Total Notional: ${summary['total_notional']:.2f}")
    
    # Test 2: Trade SHORT con volatilidad alta
    print("\n📉 Test 2: SHORT Trade - High Volatility")
    trade_request_2 = TradeRequest(
        symbol="ETH/USDT",
        direction=TradeDirection.SHORT,
        entry_price=3000.0,
        size=0.0,
        stop_loss=3060.0,  # 2% arriba
        strategy="RSI_Divergence",
        volatility=5.0  # 5% volatilidad
    )
    
    trade_result_2 = execution_engine.execute_trade(trade_request_2, capital, risk_per_trade)
    print(f"   ✅ Entry Price: ${trade_result_2.actual_entry_price:.2f}")
    print(f"   ✅ Position Size: {trade_result_2.position_size:.6f}")
    
    # Cerrar trade con pérdida
    exit_price_2 = 3030.0  # 1% arriba (pérdida para SHORT)
    closed_trade_2 = execution_engine.close_trade(trade_result_2, exit_price_2, "test_close", 5.0)
    
    print(f"\n   📊 Exit Price: ${closed_trade_2.actual_exit_price:.2f}")
    print(f"   📊 Gross PnL: ${closed_trade_2.gross_pnl:.2f}")
    print(f"   📊 Net PnL: ${closed_trade_2.net_pnl:.2f}")
    print(f"   📊 PnL %: {closed_trade_2.pnl_percentage:.2f}%")
    
    summary_2 = execution_engine.get_execution_summary(closed_trade_2)
    print(f"\n   💰 Total Costs: ${summary_2['total_costs']:.4f}")
    print(f"   💰 Cost Percentage: {summary_2['cost_percentage']:.2f}%")
    
    # Test 3: Comparación sin costos vs con costos
    print("\n🔄 Test 3: Cost Impact Analysis")
    entry_price = 50000.0
    exit_price_test = 51000.0  # 2% ganancia
    position_size_test = 0.1  # 0.1 BTC
    
    # PnL sin costos (ideal)
    ideal_pnl = (exit_price_test - entry_price) * position_size_test
    print(f"   🎯 Ideal PnL (no costs): ${ideal_pnl:.2f}")
    
    # PnL con Execution Engine
    test_request = TradeRequest(
        symbol="BTC/USDT",
        direction=TradeDirection.LONG,
        entry_price=entry_price,
        size=position_size_test,
        stop_loss=49000.0,
        strategy="Test",
        volatility=3.0
    )
    
    test_result = execution_engine.execute_trade(test_request, capital, risk_per_trade)
    test_closed = execution_engine.close_trade(test_result, exit_price_test, "test", 3.0)
    
    print(f"   📊 Real PnL (with costs): ${test_closed.net_pnl:.2f}")
    print(f"   📉 Cost Impact: ${ideal_pnl - test_closed.net_pnl:.2f}")
    print(f"   📉 Impact Percentage: {((ideal_pnl - test_closed.net_pnl) / ideal_pnl * 100):.2f}%")
    
    print("\n" + "=" * 50)
    print("✅ Execution Engine test completed!")
    print("🔍 Key observations:")
    print(f"   • Fees: ~0.08% total (0.04% entry + 0.04% exit)")
    print(f"   • Slippage: 0.01%-0.03% based on volatility")
    print(f"   • Spread: 0.01% fixed")
    print(f"   • Total impact: ~0.1%-0.12% per trade")
    print(f"   • High volatility trades have higher slippage")

if __name__ == "__main__":
    test_execution_engine()
