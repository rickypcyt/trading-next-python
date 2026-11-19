from fastapi import Request, Depends
from sqlalchemy.orm import Session
from database import get_db, EquityCurve
from strategy_engine import strategy_engine
from dynamic_sizer import dynamic_sizer


def register_strategy_endpoints(app):
    """Register endpoints for the unified decision engine and strategy execution."""

    @app.get("/market/context")
    async def get_market_context(symbol: str = "BTCUSDT"):
        """Multi-timeframe market context (trend, volatility, support, etc)."""
        analysis = await strategy_engine.analyze(symbol)
        return analysis.get("context", {})

    @app.get("/market/regime")
    async def get_market_regime(symbol: str = "BTCUSDT"):
        """Current market regime detected from context."""
        analysis = await strategy_engine.analyze(symbol)
        return analysis.get("regime", {})

    @app.get("/market/decision")
    async def get_market_decision(symbol: str = "BTCUSDT"):
        """Full decision with score, probability, risk and recommended action."""
        return await strategy_engine.analyze(symbol)

    @app.get("/strategy/analyze")
    async def get_strategy_analyze(symbol: str = "BTCUSDT"):
        """Alias for the full decision endpoint."""
        return await strategy_engine.analyze(symbol)

    @app.post("/strategy/trade")
    async def post_strategy_trade(request: Request, db: Session = Depends(get_db)):
        """Execute a trade using the unified strategy engine."""
        body = await request.json()
        symbol = body.get("symbol", "BTCUSDT").upper()
        capital = body.get("capital")

        if capital is None:
            # Try to use the latest equity curve capital
            latest = db.query(EquityCurve).order_by(EquityCurve.timestamp.desc()).first()
            capital = latest.capital if latest else 100.0

        result = await strategy_engine.generate_trade(db, symbol, capital)
        return result if result else {"status": "error", "message": "No se pudo generar el trade"}

    @app.get("/strategy/summary")
    async def get_strategy_summary(symbol: str = "BTCUSDT"):
        """Compact summary intended for the UI."""
        analysis = await strategy_engine.analyze(symbol)
        return {
            "symbol": analysis.get("symbol"),
            "current_price": analysis.get("current_price"),
            "regime": analysis.get("regime", {}).get("regime"),
            "score": analysis.get("score"),
            "probability": analysis.get("probability"),
            "decision": analysis.get("decision"),
            "risk": analysis.get("risk"),
            "direction": analysis.get("direction"),
            "recommended_strategy": analysis.get("recommended_strategy"),
            "summary": analysis.get("summary"),
            "factors": analysis.get("factors"),
        }

    @app.get("/capital/allocation")
    def get_capital_allocation(db: Session = Depends(get_db)):
        """Dynamic capital allocation per engine based on performance."""
        dynamic_sizer.refresh_from_db(db)
        return dynamic_sizer.get_allocation_summary()
