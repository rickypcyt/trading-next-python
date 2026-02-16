'use client';

import { useEffect, useState } from 'react';

export default function Home() {
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [wsStatus, setWsStatus] = useState<string>('disconnected');

  useEffect(() => {
    // Fetch initial data
    const fetchData = () => {
      fetch('http://127.0.0.1:5000')
        .then(response => response.text())
        .then(data => {
          setMessage(data);
          setLoading(false);
        })
        .catch(error => {
          console.error('Error fetching backend:', error);
          setMessage('Error connecting to backend');
          setLoading(false);
        });
    };

    fetchData();

    // WebSocket connection with auto-reconnect
    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let reconnectTimeout: NodeJS.Timeout;

    const connectWebSocket = () => {
      try {
        ws = new WebSocket('ws://127.0.0.1:5000/ws');
        
        ws.onopen = () => {
          setWsStatus('connected');
          reconnectAttempts = 0;
          console.log('WebSocket connected');
        };
        
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'refresh') {
            console.log('Received refresh notification:', data.message);
            fetchData(); // Refrescar los datos
          }
        };
        
        ws.onclose = () => {
          setWsStatus('disconnected');
          console.log('WebSocket disconnected');
          
          // Auto-reconnect logic
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 5000); // Exponential backoff
            console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
            
            reconnectTimeout = setTimeout(() => {
              connectWebSocket();
            }, delay);
          } else {
            console.log('Max reconnection attempts reached');
          }
        };
        
        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setWsStatus('error');
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        setWsStatus('error');
      }
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        ws.close();
      }
    };
  }, []);

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-white text-center">
        <div className="text-2xl font-mono mb-4">
          {loading ? (
            <div>Loading...</div>
          ) : (
            <div>{message}</div>
          )}
        </div>
        <div className="text-sm text-gray-400 mb-4">
          WebSocket: {wsStatus}
        </div>
        <button 
          onClick={() => fetch('http://127.0.0.1:5000/change', {method: 'POST'})}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
        >
          Trigger Change
        </button>
      </div>
    </div>
  );
}
