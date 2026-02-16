from binance.client import Client
import os
from dotenv import load_dotenv

# Cargar claves del .env
load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET_KEY")

# Conectar a Binance (para datos públicos no necesita API keys)
if api_key and api_secret:
    client = Client(api_key, api_secret)
    print("🔐 Conectado con API keys")
else:
    client = Client()  # Solo datos públicos
    print("🌐 Conectado sin API keys (datos públicos)")

# Lista de símbolos que quieres ver
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "BNBUSDT"]

print("\n💰 Precios actuales de Binance:")
print("=" * 40)

try:
    # Obtener precios actuales
    for symbol in symbols:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        
        # Formatear precio según su magnitud
        if price >= 1000:
            formatted_price = f"${price:,.2f}"
        elif price >= 1:
            formatted_price = f"${price:.4f}"
        else:
            formatted_price = f"${price:.6f}"
        
        print(f"{symbol:<10} {formatted_price:>15}")
    
    print("=" * 40)
    
    # Obtener datos adicionales de BTC
    btc_ticker = client.get_ticker(symbol="BTCUSDT")
    print(f"\n📊 BTC/USDT 24h Stats:")
    print(f"Cambio 24h: {float(btc_ticker['priceChangePercent']):.2f}%")
    print(f"Volumen 24h: {float(btc_ticker['volume']):,.0f} BTC")
    print(f"Alto 24h: ${float(btc_ticker['highPrice']):,.2f}")
    print(f"Bajo 24h: ${float(btc_ticker['lowPrice']):,.2f}")
    
except Exception as e:
    print(f"❌ Error obteniendo precios: {e}")
    print("💡 Asegúrate de tener conexión a internet")
