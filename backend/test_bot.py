#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bitcoin_trading_bot import BitcoinDayTradingBot, run_backtesting

def main():
    print("Bitcoin Day Trading Bot - Quick Test")
    print("=" * 50)
    print("Running 5-day backtesting demo...")
    
    # Run backtesting for 5 days as demo
    bot = run_backtesting(days=5)
    
    print("\nDemo completed! Check the results above.")
    print("To run with custom parameters:")
    print("1. Interactive mode: python bitcoin_trading_bot.py")
    print("2. Custom backtesting: python -c \"from bitcoin_trading_bot import run_backtesting; run_backtesting(30)\"")

if __name__ == "__main__":
    main()
