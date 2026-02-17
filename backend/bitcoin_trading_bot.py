import ccxt
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BitcoinDayTradingBot:
    """
    Bitcoin Day Trading Bot para paper trading con estrategia específica:
    - Long: Compra en $67,500 con RSI > 30 y volumen alto
    - Short: Venta en $69,500 con rechazo y cruce MA bajista
    """
    
    def __init__(self, initial_balance: float = 100.0, leverage: int = 10):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        self.risk_per_trade = 0.02  # 2% de riesgo por trade
        self.max_position_size_btc = 0.001  # Máximo 0.001 BTC por posición
        
        # Niveles de estrategia
        self.long_level = 67500.0
        self.short_level = 69500.0
        self.long_stop_loss = 67200.0
        self.short_stop_loss = 70200.0
        self.long_take_profit = 69500.0
        self.short_take_profit = 67000.0
        
        # Configuración de exchange (testnet por defecto)
        self.exchange = None
        self.is_testnet = True
        self.positions = []
        self.trade_history = []
        
        # Métricas
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        
        self._initialize_exchange()
    
    def _initialize_exchange(self):
        """Inicializar conexión con Binance Testnet"""
        try:
            # Configuración para Binance Testnet
            api_key = os.getenv('BINANCE_TESTNET_API_KEY', '')
            secret_key = os.getenv('BINANCE_TESTNET_SECRET_KEY', '')
            
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': secret_key,
                'sandbox': True,  # Testnet
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Trading de futuros
                }
            })
            
            # Si no hay API keys, usar modo simulación
            if not api_key or not secret_key:
                logger.warning("No API keys found - Using simulation mode")
                self.is_testnet = False
                self.exchange = None
            else:
                # Probar conexión
                self.exchange.load_markets()
                logger.info("Binance Testnet connection established")
                
        except Exception as e:
            logger.error(f"Error initializing exchange: {e}")
            logger.info("Falling back to simulation mode")
            self.exchange = None
            self.is_testnet = False
    
    def get_market_data(self, symbol: str = 'BTC/USDT', timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """
        Obtener datos de mercado del exchange o simulación
        """
        if self.exchange:
            try:
                # Obtener datos reales del exchange
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
            except Exception as e:
                logger.error(f"Error fetching real data: {e}")
        
        # Simulación de datos si no hay exchange o falla
        return self._generate_simulated_data(limit)
    
    def _generate_simulated_data(self, limit: int) -> pd.DataFrame:
        """Generar datos simulados realistas para BTC"""
        import random
        
        # Precio base alrededor de los niveles de estrategia
        base_price = 68500  # Entre $67.5k y $69.5k
        
        timestamps = [datetime.now() - timedelta(hours=i) for i in range(limit, 0, -1)]
        
        data = []
        for i, ts in enumerate(timestamps):
            # Simular movimiento de precio con tendencia y volatilidad
            price_change = random.gauss(0, 0.02)  # 2% volatilidad
            trend = math.sin(i * 0.1) * 0.01  # Tendencia suave
            
            price = base_price * (1 + price_change + trend)
            
            # Generar OHLC
            high = price * (1 + abs(random.gauss(0, 0.01)))
            low = price * (1 - abs(random.gauss(0, 0.01)))
            open_price = price * (1 + random.gauss(0, 0.005))
            close_price = price
            volume = random.uniform(1000, 10000)
            
            data.append([ts, open_price, high, low, close_price, volume])
        
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcular indicadores técnicos para la estrategia
        """
        # RSI manual implementation
        def calculate_rsi(prices, period=14):
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        
        # Simple Moving Average
        def calculate_sma(prices, period):
            return prices.rolling(window=period).mean()
        
        # Bollinger Bands
        def calculate_bollinger_bands(prices, period=20, std_dev=2):
            sma = calculate_sma(prices, period)
            std = prices.rolling(window=period).std()
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            return upper_band, sma, lower_band
        
        # MACD
        def calculate_macd(prices, fast=12, slow=26, signal=9):
            exp1 = prices.ewm(span=fast).mean()
            exp2 = prices.ewm(span=slow).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            return macd, signal_line, histogram
        
        # Calculate all indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['ma20'] = calculate_sma(df['close'], 20)
        df['ma50'] = calculate_sma(df['close'], 50)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df['close'])
        df['bb_upper'] = bb_upper
        df['bb_middle'] = bb_middle
        df['bb_lower'] = bb_lower
        
        # MACD
        macd, macd_signal, macd_histogram = calculate_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_histogram'] = macd_histogram
        
        # Volume SMA
        df['volume_sma'] = calculate_sma(df['volume'], 20)
        
        return df
    
    def should_long(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Evaluar condiciones de entrada LONG según la estrategia:
        - Precio cerca o por debajo de $67,500
        - RSI > 30 (no sobrevendido)
        - Volumen alto
        - Precio por encima de media móvil
        """
        if len(df) < 20:
            return False, 0.0
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        current_price = latest['close']
        
        # Condición 1: Precio en zona de compra ($67,500 o inferior)
        price_condition = current_price <= self.long_level
        
        # Condición 2: RSI > 30 (no sobrevendido)
        rsi_condition = latest['rsi'] > 30
        
        # Condición 3: Volumen alto (más del 150% del promedio)
        volume_condition = latest['volume'] > (latest['volume_sma'] * 1.5)
        
        # Condición 4: Precio por encima de media móvil (tendencia alcista)
        ma_condition = current_price > latest['ma20']
        
        # Condición 5: Rebote confirmado (vela anterior bajista, actual alcista)
        bounce_condition = (prev['close'] < prev['open']) and (latest['close'] > latest['open'])
        
        # Calcular confianza de la señal
        confidence = 0.0
        if price_condition:
            confidence += 0.3
        if rsi_condition:
            confidence += 0.2
        if volume_condition:
            confidence += 0.2
        if ma_condition:
            confidence += 0.2
        if bounce_condition:
            confidence += 0.1
        
        should_enter = all([price_condition, rsi_condition, volume_condition, ma_condition])
        
        logger.info(f"LONG Signal - Price: {current_price:.0f}, RSI: {latest['rsi']:.1f}, "
                   f"Volume Ratio: {latest['volume']/latest['volume_sma']:.2f}, "
                   f"Confidence: {confidence:.2f}")
        
        return should_enter, confidence
    
    def should_short(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Evaluar condiciones de entrada SHORT según la estrategia:
        - Precio cerca o por encima de $69,500
        - RSI < 70 (no sobrecomprado)
        - Rechazo en resistencia
        - Cruce bajista de media móvil
        """
        if len(df) < 20:
            return False, 0.0
        
        latest = df.iloc[-1]
        prev = df.iloc[-1]
        
        current_price = latest['close']
        
        # Condición 1: Precio en zona de venta ($69,500 o superior)
        price_condition = current_price >= self.short_level
        
        # Condición 2: RSI < 70 (no sobrecomprado extremo)
        rsi_condition = latest['rsi'] < 70
        
        # Condición 3: Rechazo en resistencia (mecha superior larga)
        wick_ratio = (latest['high'] - latest['close']) / (latest['close'] - latest['low'])
        rejection_condition = wick_ratio > 0.6  # Mecha superior 60% más larga que inferior
        
        # Condición 4: Cruce bajista de media móvil
        ma_cross_condition = current_price < latest['ma20'] and prev['close'] > prev['ma20']
        
        # Condición 5: Volumen alto en rechazo
        volume_condition = latest['volume'] > (latest['volume_sma'] * 1.3)
        
        # Calcular confianza
        confidence = 0.0
        if price_condition:
            confidence += 0.3
        if rsi_condition:
            confidence += 0.2
        if rejection_condition:
            confidence += 0.2
        if ma_cross_condition:
            confidence += 0.2
        if volume_condition:
            confidence += 0.1
        
        should_enter = all([price_condition, rsi_condition, rejection_condition])
        
        logger.info(f"SHORT Signal - Price: {current_price:.0f}, RSI: {latest['rsi']:.1f}, "
                   f"Wick Ratio: {wick_ratio:.2f}, Confidence: {confidence:.2f}")
        
        return should_enter, confidence
    
    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Calcular tamaño de posición basado en gestión de riesgo
        """
        # Riesgo monetario por trade
        risk_amount = self.current_balance * self.risk_per_trade
        
        # Riesgo por BTC
        risk_per_btc = abs(entry_price - stop_loss)
        
        # Tamaño de posición en BTC
        position_btc = risk_amount / risk_per_btc
        
        # Aplicar leverage
        position_btc *= self.leverage
        
        # Limitar al máximo permitido
        position_btc = min(position_btc, self.max_position_size_btc)
        
        # Limitar al balance disponible
        max_affordable = (self.current_balance * 0.2) / entry_price  # 20% del balance por trade
        position_btc = min(position_btc, max_affordable)
        
        return position_btc
    
    def execute_trade(self, direction: str, entry_price: float, confidence: float) -> Dict:
        """
        Ejecutar trade (simulado o real)
        """
        if direction == 'LONG':
            stop_loss = self.long_stop_loss
            take_profit = self.long_take_profit
        else:  # SHORT
            stop_loss = self.short_stop_loss
            take_profit = self.short_take_profit
        
        # Calcular tamaño de posición
        position_size = self.calculate_position_size(entry_price, stop_loss)
        
        # Valor de la posición
        position_value = position_size * entry_price
        
        # Crear registro del trade
        trade = {
            'id': len(self.trade_history) + 1,
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'position_value': position_value,
            'confidence': confidence,
            'entry_time': datetime.now(),
            'status': 'OPEN',
            'exit_price': None,
            'exit_time': None,
            'pnl': 0.0,
            'fees': position_value * 0.001  # 0.1% fees
        }
        
        self.positions.append(trade)
        self.total_trades += 1
        
        logger.info(f"Trade Executed - {direction} {position_size:.6f} BTC @ ${entry_price:.0f}, "
                   f"SL: ${stop_loss:.0f}, TP: ${take_profit:.0f}")
        
        return trade
    
    def monitor_positions(self, current_price: float):
        """
        Monitorizar posiciones abiertas y ejecutar salidas
        """
        for position in self.positions[:]:
            if position['status'] != 'OPEN':
                continue
            
            direction = position['direction']
            stop_loss = position['stop_loss']
            take_profit = position['take_profit']
            
            # Verificar condiciones de salida
            should_exit = False
            exit_reason = ''
            exit_price = current_price
            
            if direction == 'LONG':
                if current_price <= stop_loss:
                    should_exit = True
                    exit_reason = 'STOP_LOSS'
                    exit_price = stop_loss
                elif current_price >= take_profit:
                    should_exit = True
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = take_profit
            else:  # SHORT
                if current_price >= stop_loss:
                    should_exit = True
                    exit_reason = 'STOP_LOSS'
                    exit_price = stop_loss
                elif current_price <= take_profit:
                    should_exit = True
                    exit_reason = 'TAKE_PROFIT'
                    exit_price = take_profit
            
            if should_exit:
                self.close_position(position, exit_price, exit_reason)
    
    def close_position(self, position: Dict, exit_price: float, exit_reason: str):
        """
        Cerrar posición y calcular P&L
        """
        direction = position['direction']
        entry_price = position['entry_price']
        position_size = position['position_size']
        fees = position['fees']
        
        # Calcular P&L
        if direction == 'LONG':
            pnl = (exit_price - entry_price) * position_size - fees
        else:  # SHORT
            pnl = (entry_price - exit_price) * position_size - fees
        
        # Actualizar posición
        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now()
        position['pnl'] = pnl
        position['status'] = 'CLOSED'
        position['exit_reason'] = exit_reason
        
        # Actualizar balance y métricas
        self.current_balance += pnl
        self.total_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Mover a historial
        self.trade_history.append(position)
        self.positions.remove(position)
        
        logger.info(f"Position Closed - {direction} P&L: ${pnl:.2f}, "
                   f"Reason: {exit_reason}, Balance: ${self.current_balance:.2f}")
    
    def run_strategy(self, duration_minutes: int = 60, check_interval_seconds: int = 60):
        """
        Ejecutar estrategia de trading por un período determinado
        """
        logger.info(f"Starting Bitcoin Day Trading Bot - Duration: {duration_minutes} minutes")
        logger.info(f"Initial Balance: ${self.current_balance:.2f}, Leverage: {self.leverage}x")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        while datetime.now() < end_time:
            try:
                # Obtener datos de mercado
                df = self.get_market_data()
                
                # Calcular indicadores técnicos
                df = self.calculate_technical_indicators(df)
                
                if len(df) > 0:
                    current_price = df['close'].iloc[-1]
                    
                    # Monitorizar posiciones abiertas
                    self.monitor_positions(current_price)
                    
                    # Verificar nuevas señales (solo si no hay posiciones abiertas)
                    if len(self.positions) == 0:
                        # Señal LONG
                        should_long, long_confidence = self.should_long(df)
                        if should_long and long_confidence > 0.6:
                            self.execute_trade('LONG', current_price, long_confidence)
                            continue
                        
                        # Señal SHORT
                        should_short, short_confidence = self.should_short(df)
                        if should_short and short_confidence > 0.6:
                            self.execute_trade('SHORT', current_price, short_confidence)
                            continue
                
                # Esperar siguiente chequeo
                time.sleep(check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in strategy execution: {e}")
                time.sleep(check_interval_seconds)
        
        # Cerrar todas las posiciones abiertas
        final_df = self.get_market_data()
        if len(final_df) > 0:
            final_price = final_df['close'].iloc[-1]
            for position in self.positions[:]:
                if position['status'] == 'OPEN':
                    self.close_position(position, final_price, 'END_OF_SESSION')
        
        self.print_summary()
    
    def print_summary(self):
        """
        Imprimir resumen de resultados
        """
        logger.info("=" * 60)
        logger.info("TRADING BOT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Initial Balance: ${self.initial_balance:.2f}")
        logger.info(f"Final Balance: ${self.current_balance:.2f}")
        logger.info(f"Total P&L: ${self.total_pnl:.2f}")
        logger.info(f"Return: {(self.total_pnl/self.initial_balance)*100:.2f}%")
        logger.info(f"Total Trades: {self.total_trades}")
        logger.info(f"Winning Trades: {self.winning_trades}")
        logger.info(f"Losing Trades: {self.losing_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            logger.info(f"Win Rate: {win_rate:.2f}%")
            
            avg_win = 0
            avg_loss = 0
            wins = [t for t in self.trade_history if t['pnl'] > 0]
            losses = [t for t in self.trade_history if t['pnl'] < 0]
            
            if wins:
                avg_win = sum(t['pnl'] for t in wins) / len(wins)
            if losses:
                avg_loss = sum(t['pnl'] for t in losses) / len(losses)
            
            logger.info(f"Average Win: ${avg_win:.2f}")
            logger.info(f"Average Loss: ${avg_loss:.2f}")
            
            if avg_loss != 0:
                profit_factor = abs(avg_win * len(wins) / (avg_loss * len(losses)))
                logger.info(f"Profit Factor: {profit_factor:.2f}")
        
        logger.info("=" * 60)


# Función para backtesting
def run_backtesting(days: int = 30):
    """
    Ejecutar backtesting de la estrategia con datos históricos simulados
    """
    logger.info(f"Starting backtesting for {days} days")
    
    bot = BitcoinDayTradingBot(initial_balance=100.0, leverage=10)
    
    # Simular datos históricos
    total_minutes = days * 24 * 60  # Días a minutos
    check_interval = 60  # Chequear cada hora (1 hora = 60 minutos)
    total_checks = total_minutes // check_interval
    
    for i in range(total_checks):
        # Generar datos simulados para este período
        df = bot.get_market_data(limit=100)
        df = bot.calculate_technical_indicators(df)
        
        if len(df) > 0:
            current_price = df['close'].iloc[-1]
            
            # Monitorizar posiciones
            bot.monitor_positions(current_price)
            
            # Nuevas señales
            if len(bot.positions) == 0:
                should_long, long_confidence = bot.should_long(df)
                if should_long and long_confidence > 0.6:
                    bot.execute_trade('LONG', current_price, long_confidence)
                    continue
                
                should_short, short_confidence = bot.should_short(df)
                if should_short and short_confidence > 0.6:
                    bot.execute_trade('SHORT', current_price, short_confidence)
        
        # Simular paso del tiempo
        time.sleep(0.01)  # Pequeña pausa para no sobrecargar
    
    # Cerrar posiciones finales
    final_df = bot.get_market_data()
    if len(final_df) > 0:
        final_price = final_df['close'].iloc[-1]
        for position in bot.positions[:]:
            if position['status'] == 'OPEN':
                bot.close_position(position, final_price, 'BACKTEST_END')
    
    bot.print_summary()
    return bot


if __name__ == "__main__":
    
    print("Bitcoin Day Trading Bot")
    print("=" * 50)
    print("Strategy:")
    print("- LONG: Buy at $67,500 with RSI > 30 and high volume")
    print("- SHORT: Sell at $69,500 with rejection and MA cross down")
    print("- Risk: 2% per trade with 10x leverage")
    print("- Position size: Max 0.001 BTC")
    print("=" * 50)
    
    # Elegir modo
    mode = input("Choose mode (1=Backtesting, 2=Live Paper Trading): ")
    
    if mode == "1":
        days = int(input("Backtesting days (default 30): ") or "30")
        run_backtesting(days)
    else:
        minutes = int(input("Live trading minutes (default 60): ") or "60")
        bot = BitcoinDayTradingBot(initial_balance=100.0, leverage=10)
        bot.run_strategy(duration_minutes=minutes)
