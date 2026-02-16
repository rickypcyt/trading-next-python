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
    entry_price = Column(Float)
    exit_price = Column(Float)
    size = Column(Float)
    pnl = Column(Float)

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
