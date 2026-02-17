#!/bin/bash

echo "🔍 Trading Dashboard Backend Status Check"
echo "=========================================="

# Check if backend is running on port 5000
echo "📡 Checking if backend is running on port 5000..."
if curl -s http://127.0.0.1:5000/status > /dev/null 2>&1; then
    echo "✅ Backend is RUNNING on port 5000"
    
    # Check WebSocket endpoint
    echo "🌐 Checking WebSocket endpoint..."
    if curl -s -I http://127.0.0.1:5000/ws | grep -q "101\|websocket"; then
        echo "✅ WebSocket endpoint is available"
    else
        echo "❌ WebSocket endpoint not responding"
    fi
    
    # Check all endpoints
    echo "🔧 Checking all endpoints..."
    endpoints=(
        "/status"
        "/binance/modes"
        "/trades"
        "/metrics"
        "/alerts"
        "/equity"
        "/prices"
        "/micro-profit/stats"
    )
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s http://127.0.0.1:5000$endpoint > /dev/null 2>&1; then
            echo "✅ $endpoint - OK"
        else
            echo "❌ $endpoint - FAILED"
        fi
    done
    
else
    echo "❌ Backend is NOT running on port 5000"
    echo ""
    echo "🚀 To start the backend:"
    echo "cd /home/ricky/coding/trading-next-python/backend"
    echo "python app.py"
    echo ""
    echo "Or if using virtual environment:"
    echo "cd /home/ricky/coding/trading-next-python/backend"
    echo "source venv/bin/activate"
    echo "python app.py"
fi

echo ""
echo "🌐 Frontend should be running on: http://localhost:3000"
echo "📡 WebSocket should connect to: ws://127.0.0.1:5000/ws"
