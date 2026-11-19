import numpy as np
import pytest

from trading_engine import Signal, TechnicalIndicators, TradingStrategies


class TestTechnicalIndicators:
    def test_rsi_returns_default_for_insufficient_data(self):
        prices = [100.0] * 5
        result = TechnicalIndicators.rsi(prices, period=14)
        assert result == [50.0] * len(prices)

    def test_rsi_high_for_strong_uptrend(self):
        prices = [float(i) for i in range(1, 30)]
        result = TechnicalIndicators.rsi(prices, period=14)
        assert all(r > 80 for r in result[-5:])

    def test_rsi_low_for_strong_downtrend(self):
        prices = [float(30 - i) for i in range(1, 30)]
        result = TechnicalIndicators.rsi(prices, period=14)
        assert all(r < 20 for r in result[-5:])

    def test_moving_average(self):
        prices = list(range(1, 21))
        ma = TechnicalIndicators.moving_average(prices, period=5)
        expected_tail = [np.mean(prices[i - 4 : i + 1]) for i in range(4, 20)]
        assert ma[4:] == expected_tail

    def test_exponential_moving_average(self):
        prices = [100.0, 102.0, 101.0, 103.0, 104.0]
        ema = TechnicalIndicators.exponential_moving_average(prices, period=3)
        assert len(ema) == len(prices)
        assert ema[-1] > ema[0]

    def test_macd(self):
        prices = [float(i) for i in range(1, 50)]
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)

    def test_bollinger_bands(self):
        prices = [100.0 + i * 0.5 for i in range(-10, 11)]
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)
        assert len(upper) == len(prices)
        assert all(u >= m for u, m in zip(upper, middle))
        assert all(m >= l for m, l in zip(middle, lower))


class TestTradingStrategies:
    def test_ma_cross_strategy_buy(self):
        strategy = TradingStrategies()
        # Serie que provoca un cruce alcista: velas viejas altas, reciente baja y salto final
        prices = [10.0] * 4 + [50.0] * 5 + [10.0] * 15 + [200.0]
        signal = strategy.moving_average_crossover("BTCUSDT", prices, prices[-1])
        assert signal is not None
        assert signal.signal == Signal.BUY

    def test_rsi_strategy_oversold(self):
        strategy = TradingStrategies()
        prices = [100.0 - i for i in range(20)]
        signal = strategy.rsi_strategy("BTCUSDT", prices, prices[-1])
        assert signal is not None
        assert signal.signal == Signal.BUY
        assert signal.confidence > 0
