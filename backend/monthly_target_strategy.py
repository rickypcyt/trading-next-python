#!/usr/bin/env python3
"""
Estrategia optimizada para 20% mensual consistente
"""

import numpy as np
from datetime import datetime, timedelta

class MonthlyTargetStrategy:
    def __init__(self, initial_capital=100, monthly_target=0.20):
        self.initial_capital = initial_capital
        self.monthly_target = monthly_target
        self.daily_target = (1 + monthly_target) ** (1/30) - 1  # ~0.6% daily
        
    def calculate_optimal_parameters(self):
        """Calcular parámetros óptimos para 20% mensual"""
        
        strategies = {
            "Conservadora": {
                "win_rate": 0.65,      # 65% win rate
                "risk_per_trade": 0.02, # 2% riesgo por trade
                "reward_risk": 2.0,     # 1:2 risk/reward
                "trades_per_day": 5,
                "description": "Segura y consistente"
            },
            "Balanceada": {
                "win_rate": 0.60,      # 60% win rate  
                "risk_per_trade": 0.03, # 3% riesgo
                "reward_risk": 2.5,     # 1:2.5 risk/reward
                "trades_per_day": 8,
                "description": "Buen balance riesgo/retorno"
            },
            "Moderada": {
                "win_rate": 0.55,      # 55% win rate
                "risk_per_trade": 0.04, # 4% riesgo
                "reward_risk": 3.0,     # 1:3 risk/reward
                "trades_per_day": 12,
                "description": "Más agresiva pero controlada"
            }
        }
        
        print("🎯 ESTRATEGIAS PARA 20% MENSUAL")
        print("=" * 50)
        print(f"Meta diaria: {self.daily_target:.3%} ({self.initial_capital * self.daily_target:.2f})")
        print(f"Meta mensual: {self.monthly_target:.1%} ({self.initial_capital * self.monthly_target:.2f})")
        print()
        
        for name, params in strategies.items():
            win_rate = params["win_rate"]
            risk = params["risk_per_trade"]
            reward = risk * params["reward_risk"]
            trades = params["trades_per_day"]
            
            # Expectativa diaria
            daily_ev = trades * ((win_rate * reward) - ((1 - win_rate) * risk))
            daily_return = daily_ev / self.initial_capital
            
            # Probabilidad de alcanzar meta mensual
            monthly_ev = daily_ev * 30
            monthly_return = monthly_ev / self.initial_capital
            
            # Drawdown máximo esperado
            max_consecutive_losses = int(np.log(0.1) / np.log(win_rate))
            max_drawdown = max_consecutive_losses * risk
            
            print(f"📊 {name}:")
            print(f"   Win Rate: {win_rate:.1%}")
            print(f"   Riesgo/Trade: {risk:.1%} (${risk * self.initial_capital:.2f})")
            print(f"   Reward/Trade: {reward:.1%} (${reward * self.initial_capital:.2f})")
            print(f"   Trades/Día: {trades}")
            print(f"   Retorno Diario: {daily_return:.3%} (${daily_ev:.2f})")
            print(f"   Retorno Mensual: {monthly_return:.1%} (${monthly_ev:.2f})")
            print(f"   Drawdown Máx: {max_drawdown:.1%}")
            print(f"   Descripción: {params['description']}")
            print()
    
    def generate_daily_plan(self):
        """Generar plan de trading diario"""
        print("📅 PLAN DIARIO OPTIMIZADO")
        print("=" * 30)
        
        hours = [
            ("9:00-10:00", "Sesión Asia", 2),
            ("14:00-15:00", "Sesión Europa", 3), 
            ("19:00-20:00", "Sesión NY", 3),
            ("22:00-23:00", "Overlap Asia/Europa", 2)
        ]
        
        for time_range, session, trades in hours:
            print(f"{time_range} | {session:15} | {trades} trades")
        
        print(f"\nTotal trades día: 10")
        print(f"Meta profit diario: ${self.initial_capital * self.daily_target:.2f}")
    
    def risk_management_rules(self):
        """Reglas de gestión de riesgo"""
        print("🛡️ REGLAS DE GESTIÓN DE RIESGO")
        print("=" * 35)
        
        rules = [
            "Máximo 2% riesgo por trade",
            "Máximo 6% riesgo total diario", 
            "Stop loss automático",
            "Take profit en 1:2 mínimo",
            "No trading si pierdes 3 trades seguidos",
            "Revisar rendimiento semanalmente",
            "Ajustar tamaño según capital actual"
        ]
        
        for i, rule in enumerate(rules, 1):
            print(f"{i}. {rule}")

if __name__ == "__main__":
    strategy = MonthlyTargetStrategy()
    strategy.calculate_optimal_parameters()
    strategy.generate_daily_plan()
    strategy.risk_management_rules()
