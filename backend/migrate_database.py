#!/usr/bin/env python3
"""
Script para migrar la base de datos a la nueva estructura con información detallada de trades
"""

import sqlite3
from datetime import datetime
import json

def migrate_database():
    """Migrar base de datos existente a nueva estructura"""
    
    db_path = "trading.db"
    
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Starting database migration...")
        
        # 1. Hacer backup de la tabla actual
        print("📦 Backing up existing trades...")
        cursor.execute("CREATE TABLE IF NOT EXISTS trades_backup AS SELECT * FROM trades")
        
        # 2. Obtener datos existentes
        cursor.execute("SELECT * FROM trades")
        existing_trades = cursor.fetchall()
        
        # Obtener nombres de columnas
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Found {len(existing_trades)} existing trades with columns: {columns}")
        
        # 3. Eliminar tabla antigua
        print("🗑️  Dropping old trades table...")
        cursor.execute("DROP TABLE trades")
        
        # 4. Crear nueva estructura (se creará automáticamente al importar database.py)
        print("🏗️  Creating new trades table structure...")
        
        # Importar para crear la nueva tabla
        import database
        print("✅ New table structure created")
        
        # 5. Migrar datos existentes con valores por defecto para nuevos campos
        print("📝 Migrating existing trades to new structure...")
        
        for i, trade in enumerate(existing_trades):
            try:
                # Mapear columnas antiguas a nuevas
                old_data = dict(zip(columns, trade))
                
                # Insertar en nueva estructura con valores por defecto
                cursor.execute("""
                    INSERT INTO trades (
                        id, timestamp_entry, timestamp_exit, symbol, strategy,
                        entry_price, exit_price, size, pnl,
                        requested_entry_price, requested_exit_price,
                        gross_pnl, entry_fees, exit_fees, slippage_cost,
                        spread_cost, total_costs, stop_loss, take_profit,
                        confidence, volatility, source_engine, source_mode,
                        direction, duration_ms, entry_reason, exit_reason, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    old_data.get('id'),
                    old_data.get('timestamp_entry'),
                    old_data.get('timestamp_exit'),
                    old_data.get('symbol'),
                    old_data.get('strategy'),
                    old_data.get('entry_price'),
                    old_data.get('exit_price'),
                    old_data.get('size'),
                    old_data.get('pnl'),
                    old_data.get('entry_price'),  # requested_entry_price (mismo por defecto)
                    old_data.get('exit_price'),    # requested_exit_price (mismo por defecto)
                    old_data.get('pnl'),          # gross_pnl (mismo por defecto)
                    0.0,                          # entry_fees (cero por defecto)
                    0.0,                          # exit_fees (cero por defecto)
                    0.0,                          # slippage_cost (cero por defecto)
                    0.0,                          # spread_cost (cero por defecto)
                    0.0,                          # total_costs (cero por defecto)
                    None,                         # stop_loss
                    None,                         # take_profit
                    0.5,                          # confidence (defecto)
                    2.0,                          # volatility (defecto)
                    'simulation',                 # source_engine (defecto)
                    '',                           # source_mode
                    'LONG',                       # direction (defecto)
                    0,                            # duration_ms (defecto)
                    'migrated',                  # entry_reason
                    'migrated',                  # exit_reason
                    'executed'                    # status
                ))
                
                if (i + 1) % 100 == 0:
                    print(f"   📊 Migrated {i + 1}/{len(existing_trades)} trades...")
                    
            except Exception as e:
                print(f"❌ Error migrating trade {i}: {e}")
                continue
        
        # 6. Confirmar cambios
        conn.commit()
        
        # 7. Verificar migración
        cursor.execute("SELECT COUNT(*) FROM trades")
        new_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trades_backup")
        backup_count = cursor.fetchone()[0]
        
        print(f"✅ Migration completed!")
        print(f"   📊 Original trades: {backup_count}")
        print(f"   📊 Migrated trades: {new_count}")
        
        # 8. Mostrar ejemplo de nuevo trade
        cursor.execute("SELECT * FROM trades LIMIT 1")
        sample_trade = cursor.fetchone()
        
        cursor.execute("PRAGMA table_info(trades)")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        print(f"\n📋 New trade structure ({len(new_columns)} columns):")
        for i, (col, val) in enumerate(zip(new_columns, sample_trade)):
            print(f"   {col}: {val}")
        
        # 9. Opcional: eliminar backup después de verificar
        print(f"\n🔐 Backup table 'trades_backup' preserved for safety")
        print(f"   To remove backup: DROP TABLE trades_backup;")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("\n🎉 Database migration successful!")
        print("📈 New detailed trade information is now available")
    else:
        print("\n💥 Migration failed - check error messages above")
