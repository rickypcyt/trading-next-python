## Overview

Trading Next Python es una plataforma de monitoreo y simulación de estrategias cripto. El frontend se construye con Next.js y consume una API FastAPI que orquesta distintos motores de generación de trades (simulación pura, datos reales de Binance y un simulador inteligente).

## Stack principal

- **Frontend:** Next.js 14 (App Router)
- **Backend:** FastAPI + SQLAlchemy sobre SQLite
- **Datos en tiempo real:** Cliente público de Binance para precios puntuales
- **WebSocket:** Broadcasting de eventos a la UI cuando se crean/eliminan trades o se actualizan métricas

## Puesta en marcha

1. Instala dependencias del frontend:
   ```bash
   npm install
   ```
2. Inicia la API (requiere Python 3.11+):
   ```bash
   cd backend
   uvicorn app:app --reload --port 8000
   ```
3. Arranca la UI desde la raíz del proyecto:
   ```bash
   npm run dev
   ```
4. Abre [http://localhost:3000](http://localhost:3000) y la app consumirá la API en `http://127.0.0.1:8000`.

## Motores de simulación

| Motor | Descripción | Símbolos soportados |
|-------|-------------|---------------------|
| `TradingSimulator` | Genera trades sintéticos con distribuciones de volatilidad y resultados probabilísticos, además de calcular métricas/alertas posteriores. | BTC/USDT, ETH/USDT, SOL/USDT, ADA/USDT, BNB/USDT, XRP/USDT @backend/simulator.py#17-150 |
| `BinanceDataSimulator` | Consulta precios reales de Binance y construye un trade semi-realista a partir del último precio, volatilidad de las últimas 24h y tamaños de posición conservadores. También publica el trade vía WebSocket. | BTCUSDT, ETHUSDT, BNBUSDT, ADAUSDT, SOLUSDT, XRPUSDT (se muestran como */USD en la UI) @backend/binance_simulator.py#10-126 |
| `AdvancedTradingSimulator` | Obtiene históricos horarios desde Binance, estima tendencia/volatilidad/volumen y selecciona la estrategia adecuada con ponderaciones de riesgo. Actualiza equity, métricas y alertas para cada ciclo. | Lista de pares definida en `BinancePriceManager` (por defecto símbolos mayores de Binance) @backend/intelligent_simulator.py#89-343 |

## Estrategias soportadas

La lógica de señales vive en `TradingStrategies`, utilizada por el motor avanzado para decidir entradas/salidas con gestión de riesgo.

| Estrategia | Indicadores clave | Condición de entrada | Gestión de riesgo | Uso principal |
|------------|-------------------|----------------------|-------------------|---------------|
| `MA_Cross` | SMA 5 vs SMA 20 | Compra cuando la SMA rápida cruza al alza la lenta; venta en cruce bajista @backend/trading_engine.py#167-213 | Stop ±2 %, take profit ±4 %, confianza fija 0.7 | Tendencias alcistas en simulador inteligente y motor avanzado |
| `RSI_Reversion` | RSI 14 | Compra si RSI < 30, venta si RSI > 70 (sobreventa/sobrecompra) @backend/trading_engine.py#124-165 | Stop ±3 %, take profit ±6 %; confianza proporcional al extremo del RSI | Mercados con extremos marcados; el simulador inteligente la etiqueta como `RSI_Divergence` con menor riesgo @backend/intelligent_simulator.py#229-277 |
| `Bollinger_Bands` | Bandas de Bollinger 20 períodos | Compra al tocar la banda inferior, venta al tocar la superior @backend/trading_engine.py#262-306 | Stop ±2 %, objetivo volver a la banda media; confianza 0.5 | Escenarios laterales o de alta volatilidad controlada |
| `MACD_Crossover` | MACD (12/26) + señal (9) | Compra si MACD cruza al alza su señal, venta en cruce bajista @backend/trading_engine.py#215-260 | Stop ±2.5 %, objetivo ±5 %; confianza 0.6 | Confirmación de cambios de tendencia |
| `Volume_Breakout` | Volumen horario medio frente al actual | Seleccionada cuando el volumen supera el promedio y la tendencia es alcista; la PnL esperada se amplifica con factor de riesgo 1.3 @backend/intelligent_simulator.py#229-277 | Tamaño de posición ajustado por volatilidad y riesgo reforzado | Escenarios de impulso con fuerte volumen |
| `Support_Resistance` | SMA 20/50 y análisis de tendencia | Elegida para mercados de alta volatilidad o bajistas; busca rebotes en zonas extremas @backend/intelligent_simulator.py#229-277 | Factor de riesgo moderado (0.8) y tamaño de posición reducido | Rangos volátiles donde se prioriza defensa |

> Nota: El simulador básico asigna la estrategia como etiqueta descriptiva, mientras que las reglas determinísticas provienen del motor `TradingStrategies` y los pesos de riesgo del simulador inteligente.

## Glosario

- **Capital inicial / capital actual:** monto base con el que arranca cada simulador y que se va ajustando tras cada trade ejecutado. @backend/simulator.py#9-172 @backend/intelligent_simulator.py#95-310
- **PnL (Profit and Loss):** beneficio o pérdida generado por el trade; se calcula a partir de la diferencia entre precio de entrada y salida multiplicada por el tamaño de la posición. @backend/trading_engine.py#381-386 @backend/binance_simulator.py#78-124
- **Equity curve:** historial del capital acumulado a lo largo del tiempo; se persiste tras cada ciclo de simulación para graficar la evolución. @backend/simulator.py#152-177 @backend/intelligent_simulator.py#307-314
- **Drawdown:** caída máxima del capital respecto a su valor más alto alcanzado; sirve para medir riesgo y disparar alertas. @backend/simulator.py#97-148 @backend/intelligent_simulator.py#101-305
- **Win rate:** proporción de trades ganadores frente al total, calculada periódicamente para las métricas. @backend/simulator.py#74-111 @backend/intelligent_simulator.py#294-302
- **Alertas:** notificaciones guardadas en la base cuando ocurren pérdidas o ganancias grandes, drawdowns o volatilidad extrema. @backend/simulator.py#113-150 @backend/app.py#313-325
- **Volatilidad:** medida de variación del precio usada para dimensionar el movimiento esperado y ajustar el tamaño de posición. @backend/binance_simulator.py#70-125 @backend/intelligent_simulator.py#147-209

## Flujo de datos

1. Los clientes WebSocket se registran al conectar la UI (`/ws`). @backend/app.py#35-59
2. Al generar un trade (manual, simulación periódica o Binance), se persisten los datos y se notifican los clientes con el evento correspondiente. @backend/app.py#102-293
3. El simulador inteligente añade métricas avanzadas y alertas por drawdown, grandes pérdidas/ganancias y volatilidad. @backend/intelligent_simulator.py#279-343

## Pruebas y desarrollo

- Para ejecutar el loop automático de simulación simple: `POST /simulation/start`.
- Para activar la simulación con datos reales de Binance: `POST /binance/start`.
- El endpoint `DELETE /trades` limpia trades, métricas, alerts y equity para reiniciar el entorno. @backend/app.py#313-329

## Advertencia

El proyecto es un entorno educativo de simulación. No constituye asesoría financiera ni se conecta a cuentas reales de Binance.
