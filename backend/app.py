from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
websocket_connections = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.add(websocket)
    
    # Notificar a todos los clientes que hay una nueva conexión
    await notify_clients(json.dumps({"type": "refresh", "message": "New client connected"}))
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        # Notificar que un cliente se desconectó
        await notify_clients(json.dumps({"type": "refresh", "message": "Client disconnected"}))

async def notify_clients(message: str):
    """Notificar a todos los clientes conectados"""
    if websocket_connections:
        for connection in websocket_connections.copy():
            try:
                await connection.send_text(message)
            except:
                websocket_connections.discard(connection)

@app.get('/')
def hello_world():
    return 'Hello World'

@app.post('/change')
async def trigger_change():
    """Endpoint para simular cambios en la base de datos"""
    await notify_clients(json.dumps({"type": "refresh", "message": "Data changed"}))
    return {"status": "notification sent"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5000)
