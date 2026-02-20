# Sistema de Motores de Trading - Arquitectura y Comunicación

## 📊 Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                                │
│                        ┌─────────────────────┐                             │
│                        │   EngineControlPanel │                             │
│                        └─────────┬───────────┘                             │
│                                  │ WebSocket/API                           │
└──────────────────────────────────┼─────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼─────────────────────────────────────────┐
│                        BACKEND (FastAPI)                                    │
│                                  │                                         │
│                    ┌─────────────▼─────────────┐                             │
│                    │      engine_endpoints.py │◄────────────────┐          │
│                    │  (REST API Endpoints)    │                 │          │
│                    └─────────────┬─────────────┘                 │          │
│                                  │                             │          │
│                    ┌─────────────▼─────────────┐                 │          │
│                    │     engine_manager.py    │                 │          │
│                    │   (Central Engine Mgr)   │                 │          │
│                    └─────────────┬─────────────┘                 │          │
│                                  │                             │          │
└──────────────────────────────────┼─────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼─────────────────────────────────────────┐
│                     CORE ENGINE SYSTEM                                        │
│                                  │                                         │
│           ┌──────────────────────▼──────────────────────┐                  │
│           │           signal_interface.py               │                  │
│           │     (SignalEmitter Base Classes)           │                  │
│           └──────────────────────┬──────────────────────┘                  │
│                                  │                                         │
│           ┌──────────────────────▼──────────────────────┐                  │
│           │         portfolio_manager.py                │                  │
│           │      (Trade Intent Processing)              │                  │
│           └──────────────────────┬──────────────────────┘                  │
│                                  │                                         │
└──────────────────────────────────┼─────────────────────────────────────────┘
                                   │ Trade Intents
┌──────────────────────────────────┼─────────────────────────────────────────┐
│                        ENGINES LAYER                                           │
│                                  │                                         │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│    │  simulation  │  │ intelligent │  │micro_profit │  │ execution   │     │
│    │   engine     │  │   engine    │  │   engine    │  │   engine    │     │
│    │ simulator.py │  │intelligent_ │  │micro_profit_│  │execution_   │     │
│    │              │  │simulator.py │  │generator.py │  │engine.py    │     │
│    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│           │                 │                 │                 │         │
│    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐     │
│    │SignalEmitter│  │SignalEmitter│  │SignalEmitter│  │SignalEmitter│     │
│    │Simulation   │  │Intelligent  │  │MicroProfit  │  │Execution    │     │
│    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│           │                 │                 │                 │         │
│           └─────────────────┼─────────────────┼─────────────────┼─────────┘
│                             │                 │                 │
│    ┌─────────────┐  ┌──────▼──────┐  ┌─────────────┐  ┌─────────────┐     │
│    │   trading   │  │binance_mode │  │binance_mode │  │binance_mode │     │
│    │   engine    │  │ conservative│  │   hybrid    │  │ aggressive  │     │
│    │trading_     │  │binance_mode │  │binance_mode │  │binance_mode │     │
│    │engine.py    │  │simulator.py │  │simulator.py │  │simulator.py │     │
│    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│           │                 │                 │                 │         │
│    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐     │
│    │SignalEmitter│  │SignalEmitter│  │SignalEmitter│  │SignalEmitter│     │
│    │Trading      │  │BinanceMode   │  │BinanceMode   │  │BinanceMode   │     │
│    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│           │                 │                 │                 │         │
│           └─────────────────┼─────────────────┼─────────────────┼─────────┘
│                             │                 │                 │
│    ┌─────────────────────────▼─────────────────────────────────┼───────┐ │
│    │                   binance_advanced                        │       │ │
│    │                    binance_simulator.py                   │       │ │
│    │                     (No SignalEmitter)                    │       │ │
│    └───────────────────────────────────────────────────────────┘       │ │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼─────────────────────────────────────────┐
│                      DATA LAYER                                               │
│                                  │                                         │
│           ┌──────────────────────▼──────────────────────┐                  │
│           │              database.py                    │                  │
│           │         (SQLAlchemy Models)                 │                  │
│           └──────────────────────┬──────────────────────┘                  │
│                                  │                                         │
│           ┌──────────────────────▼──────────────────────┐                  │
│           │              data_cache.py                 │                  │
│           │           (Price Caching)                  │                  │
│           └─────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Flujo de Comunicación

### 1. **Inicialización del Sistema**
```
engine_manager.py
    ↓
signal_interface.py (SignalEmitter classes)
    ↓
portfolio_manager.py (Register engines)
    ↓
database.py (Initialize connections)
```

### 2. **Flujo de Trading**
```
Engine (ej: trading_engine.py)
    ↓
SignalEmitter (ej: TradingSignalEmitter)
    ↓
portfolio_manager.py (submit_trade_intent)
    ↓
database.py (Save trades)
    ↓
WebSocket (Frontend notification)
```

### 3. **Comandos del Usuario**
```
Frontend (EngineControlPanel)
    ↓
engine_endpoints.py (REST API)
    ↓
engine_manager.py (start/stop engines)
    ↓
Specific Engine Logic
```

## 📋 Archivos y Responsabilidades

### **Capa de Coordinación**
- **`engine_manager.py`**: Orquesta todos los motores, maneja estados
- **`engine_endpoints.py`**: Endpoints HTTP para controlar motores
- **`signal_interface.py`**: Clases base para emisión de señales

### **Motores de Trading**
- **`simulation.py`**: Motor básico de simulación
- **`trading_engine.py`**: Análisis técnico (RSI, MACD, Bollinger)
- **`execution_engine.py`**: Ejecución con costos realistas
- **`intelligent_simulator.py`**: Trading inteligente
- **`micro_profit_generator.py`**: Micro ganancias
- **`binance_mode_simulator.py`**: Modos Binance (3 variantes)
- **`binance_simulator.py`**: Motor avanzado Binance

### **Gestión y Datos**
- **`portfolio_manager.py`**: Gestión de portfolio y trades
- **`database.py`**: Persistencia de datos
- **`data_cache.py`**: Caching de precios

## 🔗 Tipos de Comunicación

### **1. Señales de Trading**
```python
# Engine → SignalEmitter → Portfolio Manager
await emitter.emit_trade_intent(
    symbol="BTC/USD",
    direction=TradeDirection.LONG,
    entry_price=67500.0,
    size=0.001,
    strategy="RSI_Reversion"
)
```

### **2. Control de Motores**
```python
# Frontend → Engine Endpoints → Engine Manager
POST /engines/start/{engine_id}
POST /engines/stop/{engine_id}
GET /engines
```

### **3. Notificaciones en Tiempo Real**
```python
# Portfolio Manager → WebSocket → Frontend
await notify_clients(json.dumps({
    "type": "trade_added",
    "message": "New trade executed"
}))
```

## 🎯 Estados de los Motores

### **Estados Posibles**
- **IDLE**: Motor registrado pero no activo
- **RUNNING**: Motor ejecutando y generando señales
- **PAUSED**: Motor temporalmente detenido
- **ERROR**: Motor con errores

### **Motores por Tipo**
- **SIMULATION**: `simulation`
- **INTELLIGENT**: `intelligent`
- **MICRO_PROFIT**: `micro_profit`
- **EXECUTION**: `execution` *(Nuevo)*
- **TRADING**: `trading` *(Nuevo)*
- **BINANCE_MODE**: `binance_conservative`, `binance_hybrid`, `binance_aggressive`, `binance_advanced`

## 🚀 Características Clave

### **SignalEmitter Pattern**
Todos los motores (excepto binance_advanced) usan el patrón SignalEmitter:
- Heredan de `SignalEmitter`
- Emiten `TradeIntent` al Portfolio Manager
- Se registran automáticamente

### **Gestión Centralizada**
- `engine_manager.py` controla todos los motores
- Estados centralizados y monitoreo
- Inicio/parada coordinada

### **Integración con Portfolio**
- Todas las señales pasan por `portfolio_manager.py`
- Validación de riesgos y ejecución
- Persistencia en base de datos

### **Comunicación con Frontend**
- WebSocket para actualizaciones en tiempo real
- REST API para control de motores
- Notificaciones de estado y trades
