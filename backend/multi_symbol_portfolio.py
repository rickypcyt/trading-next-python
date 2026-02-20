"""
Multi-Symbol Portfolio Manager para Advanced Strategy Engine
Gestiona múltiples engines de trading simultáneamente con risk management a nivel portfolio
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from advanced_strategies import AdvancedStrategyEngine, RiskLevel, OrderSide

@dataclass
class PortfolioConfig:
    """Configuración del portfolio multi-símbolo"""
    total_capital: float
    max_correlation_exposure: float = 0.6  # 60% máximo en activos correlacionados
    max_leverage_total: float = 3.0  # 3x leverage total del portfolio
    rebalance_threshold: float = 0.1  # 10% desbalance para rebalancear
    diversification_min_symbols: int = 3  # Mínimo 3 símbolos diferentes
    
@dataclass
class SymbolAllocation:
    """Asignación de capital por símbolo"""
    symbol: str
    capital: float
    risk_level: RiskLevel
    leverage: float
    engine: Optional[AdvancedStrategyEngine] = None
    
@dataclass
class PortfolioMetrics:
    """Métricas del portfolio completo"""
    total_value: float
    total_pnl: float
    daily_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    var_95: float
    correlation_matrix: Dict
    leverage_used: float
    liquidation_risk: Dict

class MultiSymbolPortfolio:
    """Gestor de portfolio multi-símbolo con engines independientes"""
    
    def __init__(self, config: PortfolioConfig):
        self.config = config
        self.engines: Dict[str, AdvancedStrategyEngine] = {}
        self.allocations: Dict[str, SymbolAllocation] = {}
        self.metrics = PortfolioMetrics(
            total_value=config.total_capital,
            total_pnl=0.0,
            daily_pnl=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            var_95=0.0,
            correlation_matrix={},
            leverage_used=0.0,
            liquidation_risk={}
        )
        self.price_history: Dict[str, List[float]] = {}
        self.pnl_history: List[float] = []
        
    def add_symbol(self, symbol: str, capital: float, risk_level: RiskLevel = RiskLevel.MODERATE, 
                   leverage: float = 1.0, current_price: float = 0.0, volatility: float = 0.02):
        """Agregar un nuevo símbolo al portfolio"""
        
        # Validaciones
        if symbol in self.engines:
            raise ValueError(f"Symbol {symbol} already exists in portfolio")
        
        total_allocated = sum(alloc.capital for alloc in self.allocations.values())
        if total_allocated + capital > self.config.total_capital:
            raise ValueError(f"Insufficient capital: need ${total_allocated + capital:.2f}, available ${self.config.total_capital:.2f}")
        
        # Crear engine para el símbolo
        engine = AdvancedStrategyEngine(
            symbol=symbol,
            current_price=current_price,
            volatility=volatility,
            risk_level=risk_level,
            capital=capital,
            leverage=leverage
        )
        
        # Guardar engine y asignación
        self.engines[symbol] = engine
        self.allocations[symbol] = SymbolAllocation(
            symbol=symbol,
            capital=capital,
            risk_level=risk_level,
            leverage=leverage,
            engine=engine
        )
        
        # Inicializar historial de precios
        self.price_history[symbol] = []
        
        print(f"✅ Added {symbol}: ${capital:.2f} capital, {risk_level.value} risk, {leverage}x leverage")
        
    def update_prices(self, price_updates: Dict[str, float]):
        """Actualizar precios de todos los símbolos"""
        for symbol, new_price in price_updates.items():
            if symbol in self.engines:
                self.engines[symbol].update_price(new_price)
                self.price_history[symbol].append(new_price)
                
                # Mantener solo últimos 100 precios
                if len(self.price_history[symbol]) > 100:
                    self.price_history[symbol] = self.price_history[symbol][-100:]
        
        # Actualizar métricas del portfolio
        self._update_portfolio_metrics()
        
    def get_all_signals(self) -> Dict[str, List]:
        """Obtener señales de todos los engines"""
        all_signals = {}
        
        for symbol, engine in self.engines.items():
            signals = engine.get_all_strategy_signals()
            if signals:
                all_signals[symbol] = signals
                
        return all_signals
    
    def execute_portfolio_signals(self) -> Dict[str, List]:
        """Ejecutar señales considerando risk management del portfolio"""
        executed_signals = {}
        
        # Obtener todas las señales
        all_signals = self.get_all_signals()
        
        # Validar risk management del portfolio
        for symbol, signals in all_signals.items():
            valid_signals = self._validate_portfolio_risk(symbol, signals)
            if valid_signals:
                executed_signals[symbol] = valid_signals
                
                # Simular ejecución y actualizar posiciones
                for signal in valid_signals:
                    self.engines[symbol].on_fill(
                        signal.side, 
                        signal.size, 
                        signal.price,
                        is_maker=True
                    )
        
        return executed_signals
    
    def _validate_portfolio_risk(self, symbol: str, signals: List) -> List:
        """Validar señales contra risk management del portfolio"""
        valid_signals = []
        
        # Calcular exposición total actual
        total_exposure = self._calculate_total_exposure()
        
        # Calcular correlación con otros símbolos
        correlation_risk = self._calculate_correlation_risk(symbol)
        
        # Validar leverage total
        total_leverage = self._calculate_total_leverage()
        
        for signal in signals:
            signal_value = signal.size * signal.price
            
            # Validar leverage total
            if total_leverage > self.config.max_leverage_total:
                print(f"⚠️ Portfolio leverage limit reached: {total_leverage:.2f}x > {self.config.max_leverage_total}x")
                continue
                
            # Validar correlación
            if correlation_risk > self.config.max_correlation_exposure:
                print(f"⚠️ Correlation risk too high for {symbol}: {correlation_risk:.2f}")
                continue
                
            # Validar diversificación
            if len(self.engines) < self.config.diversification_min_symbols:
                print(f"⚠️ Insufficient diversification: {len(self.engines)} < {self.config.diversification_min_symbols}")
                continue
                
            valid_signals.append(signal)
            
        return valid_signals
    
    def _calculate_total_exposure(self) -> float:
        """Calcular exposición total del portfolio"""
        total_exposure = 0.0
        
        for symbol, engine in self.engines.items():
            position_info = engine.get_position_info()
            total_exposure += abs(position_info['position_value'])
            
        return total_exposure
    
    def _calculate_correlation_risk(self, symbol: str) -> float:
        """Calcular riesgo de correlación para un símbolo"""
        if len(self.engines) < 2:
            return 0.0
            
        # Calcular correlación con otros símbolos
        correlations = []
        symbol_returns = self._calculate_returns(symbol)
        
        for other_symbol in self.engines:
            if other_symbol != symbol and len(self.price_history[other_symbol]) > 10:
                other_returns = self._calculate_returns(other_symbol)
                
                if len(symbol_returns) > 1 and len(other_returns) > 1:
                    correlation = np.corrcoef(symbol_returns[-10:], other_returns[-10:])[0, 1]
                    if not np.isnan(correlation):
                        correlations.append(abs(correlation))
        
        return np.mean(correlations) if correlations else 0.0
    
    def _calculate_returns(self, symbol: str) -> List[float]:
        """Calcular retornos para un símbolo"""
        prices = self.price_history[symbol]
        if len(prices) < 2:
            return []
            
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
            
        return returns
    
    def _calculate_total_leverage(self) -> float:
        """Calcular leverage total del portfolio"""
        total_notional = 0.0
        total_capital = 0.0
        
        for symbol, allocation in self.allocations.items():
            engine = self.engines[symbol]
            position_info = engine.get_position_info()
            
            total_notional += abs(position_info['position_value'])
            total_capital += allocation.capital
            
        return total_notional / total_capital if total_capital > 0 else 0.0
    
    def _update_portfolio_metrics(self):
        """Actualizar métricas del portfolio"""
        total_value = 0.0
        total_pnl = 0.0
        
        # Calcular valor y P&L total
        for symbol, engine in self.engines.items():
            position_info = engine.get_position_info()
            total_value += position_info['position_value'] + position_info['available_capital']
            total_pnl += position_info['unrealized_pnl']
            
        self.metrics.total_value = total_value
        self.metrics.total_pnl = total_pnl
        
        # Actualizar historial de P&L
        self.pnl_history.append(total_pnl)
        if len(self.pnl_history) > 100:
            self.pnl_history = self.pnl_history[-100:]
            
        # Calcular métricas adicionales
        self._calculate_sharpe_ratio()
        self._calculate_var_95()
        self._update_liquidation_risk()
        
    def _calculate_sharpe_ratio(self):
        """Calcular Sharpe Ratio del portfolio"""
        if len(self.pnl_history) < 2:
            self.metrics.sharpe_ratio = 0.0
            return
            
        returns = np.diff(self.pnl_history)
        if len(returns) == 0 or np.std(returns) == 0:
            self.metrics.sharpe_ratio = 0.0
            return
            
        # Sharpe Ratio anualizado (asumiendo retornos diarios)
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365)
        self.metrics.sharpe_ratio = sharpe
        
    def _calculate_var_95(self):
        """Calcular Value at Risk 95% del portfolio"""
        if len(self.pnl_history) < 10:
            self.metrics.var_95 = 0.0
            return
            
        # VaR 95% sobre el 5% peor de los retornos
        returns = np.diff(self.pnl_history)
        var_95 = np.percentile(returns, 5)
        self.metrics.var_95 = abs(var_95)
        
    def _update_liquidation_risk(self):
        """Actualizar riesgo de liquidación del portfolio"""
        liquidation_risks = {}
        
        for symbol, engine in self.engines.items():
            liq_info = engine.get_liquidation_distance()
            liquidation_risks[symbol] = {
                'liquidation_price': liq_info['liquidation_price'],
                'distance_pct': liq_info['distance_percentage'],
                'risk_level': liq_info['risk_level'],
                'is_safe': liq_info['is_safe']
            }
            
        self.metrics.liquidation_risk = liquidation_risks
        
    def get_portfolio_summary(self) -> Dict:
        """Obtener resumen completo del portfolio"""
        return {
            'portfolio_value': round(self.metrics.total_value, 2),
            'total_pnl': round(self.metrics.total_pnl, 2),
            'daily_pnl': round(self.metrics.daily_pnl, 2),
            'max_drawdown': round(self.metrics.max_drawdown, 2),
            'sharpe_ratio': round(self.metrics.sharpe_ratio, 3),
            'var_95': round(self.metrics.var_95, 2),
            'leverage_used': round(self.metrics.total_leverage, 2),
            'symbols_count': len(self.engines),
            'allocations': {
                symbol: {
                    'capital': round(allocation.capital, 2),
                    'risk_level': allocation.risk_level.value,
                    'leverage': allocation.leverage,
                    'position_value': round(self.engines[symbol].get_position_info()['position_value'], 2),
                    'pnl': round(self.engines[symbol].get_position_info()['unrealized_pnl'], 2)
                }
                for symbol, allocation in self.allocations.items()
            },
            'liquidation_risks': self.metrics.liquidation_risk,
            'risk_metrics': {
                'total_exposure': round(self._calculate_total_exposure(), 2),
                'correlation_avg': round(np.mean([self._calculate_correlation_risk(s) for s in self.engines.keys()]), 3),
                'diversification_score': len(self.engines) / max(1, self.config.diversification_min_symbols)
            }
        }
        
    def rebalance_portfolio(self):
        """Rebalancear portfolio si es necesario"""
        current_allocations = {}
        total_value = self.metrics.total_value
        
        # Calcular allocation actual
        for symbol, engine in self.engines.items():
            position_info = engine.get_position_info()
            current_allocations[symbol] = position_info['position_value'] / total_value
            
        # Calcular allocation target
        target_allocation = 1.0 / len(self.engines)  # Igual ponderación
        
        # Verificar si necesita rebalanceo
        needs_rebalance = False
        for symbol, current_alloc in current_allocations.items():
            if abs(current_alloc - target_allocation) > self.config.rebalance_threshold:
                needs_rebalance = True
                break
                
        if needs_rebalance:
            print(f"🔄 Portfolio rebalancing needed")
            # Aquí iría lógica de rebalanceo real
            return True
            
        return False

# Ejemplo de uso
if __name__ == "__main__":
    # Configuración del portfolio
    config = PortfolioConfig(total_capital=10000.0)
    
    # Crear portfolio multi-símbolo
    portfolio = MultiSymbolPortfolio(config)
    
    # Agregar símbolos
    portfolio.add_symbol("BTCUSDT", 3000.0, RiskLevel.MODERATE, 2.0, 50000.0, 0.02)
    portfolio.add_symbol("SOLUSDT", 2000.0, RiskLevel.AGGRESSIVE, 5.0, 100.0, 0.04)
    portfolio.add_symbol("ETHUSDT", 2500.0, RiskLevel.CONSERVATIVE, 1.5, 3000.0, 0.025)
    
    # Actualizar precios
    portfolio.update_prices({
        "BTCUSDT": 51000.0,
        "SOLUSDT": 105.0,
        "ETHUSDT": 3100.0
    })
    
    # Obtener señales
    signals = portfolio.get_all_signals()
    print(f"📊 Portfolio signals: {len(signals)} symbols with signals")
    
    # Ejecutar señales
    executed = portfolio.execute_portfolio_signals()
    print(f"⚡ Executed signals: {executed}")
    
    # Ver resumen
    summary = portfolio.get_portfolio_summary()
    print(f"💰 Portfolio value: ${summary['portfolio_value']:.2f}")
    print(f"📈 Total P&L: ${summary['total_pnl']:.2f}")
    print(f"⚡ Leverage used: {summary['leverage_used']:.2f}x")
    print(f"🎯 Sharpe ratio: {summary['sharpe_ratio']:.3f}")
