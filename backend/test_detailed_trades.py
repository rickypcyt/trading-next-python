#!/usr/bin/env python3
"""
Test script para verificar los nuevos datos detallados de trades
"""

import requests
import json
from datetime import datetime

def test_detailed_trades():
    """Probar el endpoint de trades detallados"""
    
    print("🧪 Testing Detailed Trades Endpoint...")
    print("=" * 60)
    
    try:
        # Obtener trades detallados
        response = requests.get("http://127.0.0.1:5000/trades")
        
        if response.status_code == 200:
            trades = response.json()
            print(f"✅ Retrieved {len(trades)} trades")
            
            if trades:
                # Mostrar información detallada del primer trade
                trade = trades[0]
                
                print(f"\n📊 Sample Trade Details (ID: {trade['id']}):")
                print(f"   📍 Symbol: {trade['symbol']}")
                print(f"   🎯 Strategy: {trade['strategy']}")
                print(f"   ⬆️  Direction: {trade['direction']}")
                print(f"   🔧 Source Engine: {trade['source_engine']}")
                print(f"   📈 Source Mode: {trade['source_mode'] or 'N/A'}")
                
                print(f"\n💰 Pricing Information:")
                print(f"   📝 Requested Entry: ${trade['requested_entry_price']}")
                print(f"   ✅ Actual Entry: ${trade['entry_price']}")
                print(f"   📝 Requested Exit: ${trade['requested_exit_price']}")
                print(f"   ✅ Actual Exit: ${trade['exit_price']}")
                
                print(f"\n💸 P&L Analysis:")
                print(f"   💰 Gross P&L: ${trade['gross_pnl']}")
                print(f"   💰 Net P&L: ${trade['pnl']}")
                print(f"   📊 P&L %: {trade['pnl_percentage']}%")
                
                print(f"\n💸 Execution Costs:")
                print(f"   🏦 Entry Fees: ${trade['entry_fees']}")
                print(f"   🏦 Exit Fees: ${trade['exit_fees']}")
                print(f"   📈 Slippage Cost: ${trade['slippage_cost']}")
                print(f"   📊 Spread Cost: ${trade['spread_cost']}")
                print(f"   💰 Total Costs: ${trade['total_costs']}")
                print(f"   📊 Cost Impact: {trade['cost_impact_pct']}%")
                
                print(f"\n⚠️  Risk Information:")
                print(f"   🛡️  Stop Loss: ${trade['stop_loss'] or 'N/A'}")
                print(f"   🎯 Take Profit: ${trade['take_profit'] or 'N/A'}")
                print(f"   💪 Confidence: {trade['confidence']}")
                print(f"   📊 Volatility: {trade['volatility']}%")
                
                print(f"\n⏱️  Timing:")
                print(f"   🕐 Entry: {trade['timestamp_entry']}")
                print(f"   🕐 Exit: {trade['timestamp_exit']}")
                print(f"   ⏱️  Duration: {trade['duration_formatted']}")
                print(f"   📊 Duration (ms): {trade['duration_ms']}")
                
                print(f"\n📝 Status:")
                print(f"   ✅ Status: {trade['status']}")
                print(f"   📝 Entry Reason: {trade['entry_reason']}")
                print(f"   📝 Exit Reason: {trade['exit_reason']}")
                
                # Calcular estadísticas de costos
                total_fees = sum(t['entry_fees'] + t['exit_fees'] for t in trades)
                total_slippage = sum(t['slippage_cost'] for t in trades)
                total_spread = sum(t['spread_cost'] for t in trades)
                total_costs = sum(t['total_costs'] for t in trades)
                
                print(f"\n📈 Portfolio Cost Analysis ({len(trades)} trades):")
                print(f"   🏦 Total Fees: ${total_fees:.6f}")
                print(f"   📈 Total Slippage: ${total_slippage:.6f}")
                print(f"   📊 Total Spread: ${total_spread:.6f}")
                print(f"   💰 Total Costs: ${total_costs:.6f}")
                print(f"   📊 Avg Cost per Trade: ${total_costs/len(trades):.6f}")
                
                # Análisis de impacto
                winning_trades = [t for t in trades if t['pnl'] > 0]
                losing_trades = [t for t in trades if t['pnl'] < 0]
                
                print(f"\n📊 Trade Performance:")
                print(f"   ✅ Winning Trades: {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
                print(f"   ❌ Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
                print(f"   💰 Avg Win: ${sum(t['pnl'] for t in winning_trades)/len(winning_trades):.4f}" if winning_trades else "N/A")
                print(f"   💸 Avg Loss: ${sum(t['pnl'] for t in losing_trades)/len(losing_trades):.4f}" if losing_trades else "N/A")
                
                # Análisis por motor
                engines = {}
                for trade in trades:
                    engine = trade['source_engine']
                    if engine not in engines:
                        engines[engine] = {'count': 0, 'pnl': 0, 'costs': 0}
                    engines[engine]['count'] += 1
                    engines[engine]['pnl'] += trade['pnl']
                    engines[engine]['costs'] += trade['total_costs']
                
                print(f"\n🔧 Performance by Engine:")
                for engine, stats in engines.items():
                    print(f"   {engine}: {stats['count']} trades, P&L: ${stats['pnl']:.4f}, Costs: ${stats['costs']:.6f}")
                
            else:
                print("❌ No trades found")
                
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure the server is running on http://127.0.0.1:5000")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Detailed trades test completed!")

if __name__ == "__main__":
    test_detailed_trades()
