#!/usr/bin/env python3
"""
Script para agregar automáticamente los endpoints de modos a app.py
"""
import re

def add_modes_to_app():
    # Leer el archivo actual
    with open('app.py', 'r') as f:
        content = f.read()
    
    # 1. Agregar import
    if 'from binance_mode_simulator import' not in content:
        # Encontrar dónde agregar el import
        import_pattern = r'(from monthly_target_simulator import MonthlyTargetSimulator, run_monthly_target_simulation)'
        replacement = r'\1\nfrom binance_mode_simulator import BinanceModeSimulator, run_binance_mode_simulation, TRADING_MODES'
        content = re.sub(import_pattern, replacement, content)
        print("✅ Import agregado")
    else:
        print("ℹ️ Import ya existe")
    
    # 2. Agregar variable global
    if 'binance_mode_tasks = {}' not in content:
        # Encontrar dónde agregar la variable
        global_pattern = r'(monthly_target_task = None)'
        replacement = r'\1\nbinance_mode_tasks = {}  # Tareas para cada modo'
        content = re.sub(global_pattern, replacement, content)
        print("✅ Variable global agregada")
    else:
        print("ℹ️ Variable global ya existe")
    
    # Guardar el contenido modificado
    with open('app.py', 'w') as f:
        f.write(content)
    
    print("\n🎯 Archivo app.py modificado!")
    print("⚠️ Ahora necesitas agregar manualmente los endpoints (paso 3 del integration_instructions.md)")

if __name__ == "__main__":
    add_modes_to_app()
