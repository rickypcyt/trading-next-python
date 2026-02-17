# Bitcoin Day Trading Bot Configuration

## Binance Testnet Setup

To use Binance Testnet for paper trading, you need to:

1. **Create Binance Testnet Account:**
   - Go to [Binance Testnet](https://testnet.binance.vision/)
   - Register with your email
   - Get testnet funds (unlimited virtual money)

2. **Get API Keys:**
   - In Testnet dashboard, go to API Management
   - Create new API key
   - Save both API Key and Secret Key

3. **Set Environment Variables:**
   ```bash
   export BINANCE_TESTNET_API_KEY="your_api_key_here"
   export BINANCE_TESTNET_SECRET_KEY="your_secret_key_here"
   ```

## Dependencies Installation

```bash
cd backend
pip install -r requirements.txt
```

## Running the Bot

### Mode 1: Backtesting (Recommended First)
```bash
python bitcoin_trading_bot.py
# Choose option 1
# Enter days for backtesting (default 30)
```

### Mode 2: Live Paper Trading
```bash
python bitcoin_trading_bot.py
# Choose option 2
# Enter minutes for live trading (default 60)
```

## Strategy Details

### LONG Entry Conditions:
- Price ≤ $67,500
- RSI > 30 (not oversold)
- Volume > 150% of average
- Price > MA20 (uptrend)
- Bounce confirmation (bullish reversal candle)

**LONG Parameters:**
- Entry: $67,500
- Stop Loss: $67,200 (0.4% risk)
- Take Profit: $69,500 (3.0% reward)

### SHORT Entry Conditions:
- Price ≥ $69,500
- RSI < 70 (not overbought)
- Rejection at resistance (long upper wick)
- MA cross down
- High volume on rejection

**SHORT Parameters:**
- Entry: $69,500
- Stop Loss: $70,200 (1.0% risk)
- Take Profit: $67,000 (3.6% reward)

## Risk Management

- **Initial Capital:** $100 USD
- **Risk per Trade:** 2% ($2 max)
- **Leverage:** 10x (amplifies position size)
- **Max Position:** 0.001 BTC (~$68)
- **Capital per Trade:** 20% ($20)
- **Expected Daily ROI:** 5-10% with 5 successful trades

## Performance Metrics

The bot tracks:
- Win rate
- Average win/loss
- Profit factor
- Total return
- Sharpe ratio (for backtesting)

## Features

- **Real-time Data:** Binance Testnet or simulation
- **Technical Analysis:** RSI, Moving Averages, Bollinger Bands, MACD
- **Risk Management:** Position sizing, stop loss, take profit
- **Backtesting:** Historical validation without risk
- **Paper Trading:** Test with virtual money
- **Logging:** Detailed trade logs and performance metrics
