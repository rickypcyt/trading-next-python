from binance.client import Client
from binance.enums import KLINE_INTERVAL_1HOUR, KLINE_INTERVAL_4HOUR, KLINE_INTERVAL_1DAY
import os
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd

# Cargar claves del .env
load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET_KEY")

# Conectar a Binance
if api_key and api_secret:
    client = Client(api_key, api_secret)
    print("🔐 Conectado con API keys")
else:
    client = Client()  # Solo datos públicos
    print("🌐 Conectado sin API keys (datos públicos)")

# Lista de símbolos
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def get_ohlcv_data(symbol, interval=KLINE_INTERVAL_1HOUR, limit=50):
    """Obtiene datos OHLCV y los convierte a DataFrame"""
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        data = []
        for k in klines:
            timestamp = datetime.fromtimestamp(int(k[0]) / 1000)
            data.append({
                'timestamp': timestamp,
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })
        
        df = pd.DataFrame(data)
        return df
        
    except Exception as e:
        print(f"❌ Error obteniendo datos de {symbol}: {e}")
        return None

def calculate_indicators(df):
    """Calcula indicadores técnicos básicos"""
    if df is None or len(df) < 14:
        return df
    
    # RSI (14 períodos)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Medias móviles
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    # Bandas de Bollinger
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # MACD
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    return df

def print_analysis(symbol, df):
    """Imprime análisis técnico"""
    if df is None or len(df) == 0:
        return
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    print(f"\n📊 {symbol} - Análisis Técnico:")
    print("=" * 50)
    print(f"Precio Actual: ${latest['close']:,.2f}")
    print(f"Cambio Anterior: {((latest['close'] - prev['close']) / prev['close'] * 100):+.2f}%")
    
    if 'rsi' in latest and not pd.isna(latest['rsi']):
        rsi = latest['rsi']
        rsi_signal = "🔥 Sobrecompra" if rsi > 70 else "❄️ Sobreventa" if rsi < 30 else "⚖️ Neutral"
        print(f"RSI (14): {rsi:.2f} {rsi_signal}")
    
    if 'sma_20' in latest and not pd.isna(latest['sma_20']):
        sma20 = latest['sma_20']
        sma50 = latest['sma_50'] if 'sma_50' in latest and not pd.isna(latest['sma_50']) else sma20
        trend = "📈 Alcista" if latest['close'] > sma20 > sma50 else "📉 Bajista" if latest['close'] < sma20 < sma50 else "➡️ Lateral"
        print(f"Tendencia: {trend}")
        print(f"SMA 20: ${sma20:,.2f}")
        if 'sma_50' in latest and not pd.isna(latest['sma_50']):
            print(f"SMA 50: ${sma50:,.2f}")
    
    if 'bb_upper' in latest and not pd.isna(latest['bb_upper']):
        bb_upper = latest['bb_upper']
        bb_lower = latest['bb_lower']
        bb_position = "🔺 Superior" if latest['close'] > bb_upper else "🔺 Inferior" if latest['close'] < bb_lower else "📍 Medio"
        print(f"Bollinger: {bb_position}")
    
    if 'macd' in latest and not pd.isna(latest['macd']):
        macd = latest['macd']
        macd_signal = "📈 Cruce Alcista" if macd > 0 and prev['macd'] <= 0 else "📉 Cruce Bajista" if macd < 0 and prev['macd'] >= 0 else "➡️ Sin cruce"
        print(f"MACD: {macd:+.4f} {macd_signal}")

# Obtener y analizar datos
print("🕯 Obteniendo datos OHLCV históricos...")

for symbol in symbols:
    print(f"\n{'='*60}")
    print(f"📈 Analizando {symbol}")
    print(f"{'='*60}")
    
    # Obtener datos de 1 hora
    df = get_ohlcv_data(symbol, KLINE_INTERVAL_1HOUR, 50)
    
    if df is not None:
        # Calcular indicadores
        df = calculate_indicators(df)
        
        # Mostrar últimas 5 velas
        print(f"\n🕯 Últimas 5 velas de {symbol}:")
        print("Timestamp             Open     High      Low    Close    Volume")
        print("-" * 70)
        for _, row in df.tail(5).iterrows():
            print(f"{row['timestamp'].strftime('%Y-%m-%d %H:%M')}  {row['open']:>8.2f}  {row['high']:>8.2f}  {row['low']:>8.2f}  {row['close']:>8.2f}  {row['volume']:>8.0f}")
        
        # Análisis técnico
        print_analysis(symbol, df)

print(f"\n{'='*60}")
print("✅ Análisis completado")
print("💡 Usa estos datos para estrategias de trading automatizado")
print(f"{'='*60}")
