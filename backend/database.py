from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./trading.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp_entry = Column(String)
    timestamp_exit = Column(String)
    symbol = Column(String, index=True)
    strategy = Column(String)
    
    # Precios reales con Execution Engine
    entry_price = Column(Float)  # Precio real de entrada
    exit_price = Column(Float)    # Precio real de salida
    requested_entry_price = Column(Float)  # Precio solicitado
    requested_exit_price = Column(Float)    # Precio solicitado
    
    # Tamaño y P&L
    size = Column(Float)
    pnl = Column(Float)  # P&L neto (después de costos)
    gross_pnl = Column(Float)  # P&L bruto (antes de costos)
    
    # Costos de ejecución
    entry_fees = Column(Float)
    exit_fees = Column(Float)
    slippage_cost = Column(Float)
    spread_cost = Column(Float)
    total_costs = Column(Float)
    
    # Información de riesgo
    stop_loss = Column(Float)
    take_profit = Column(Float)
    confidence = Column(Float)  # Confianza de la señal
    volatility = Column(Float)  # Volatilidad al momento del trade
    
    # Metadatos del motor
    source_engine = Column(String)  # intelligent, binance_mode, micro_profit
    source_mode = Column(String)    # conservative, hybrid, aggressive
    direction = Column(String)      # LONG, SHORT
    
    # Tiempos
    duration_ms = Column(Integer)   # Duración en milisegundos
    
    # Dinero invertido
    investment_amount = Column(Float)  # Dinero total invertido en el trade
    
    # Estado y razón
    entry_reason = Column(String)   # Razón de entrada
    exit_reason = Column(String)    # Razón de salida
    status = Column(String)         # executed, rejected, failed

class EquityCurve(Base):
    __tablename__ = "equity_curve"
    
    timestamp = Column(String, primary_key=True)
    capital = Column(Float)

class Metric(Base):
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String)
    win_rate = Column(Float)
    sharpe = Column(Float)
    max_drawdown = Column(Float)
    profit_factor = Column(Float)

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String)
    type = Column(String)
    message = Column(Text)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
