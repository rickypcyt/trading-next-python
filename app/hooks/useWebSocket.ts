import { useEffect, useRef, useState } from 'react';
import { toast } from 'react-toastify';

export interface WebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
  message?: string;
}

export function useWebSocket(url: string) {
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const toastShownRef = useRef(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let mounted = true;

    // Reset reconnection state on every mount
    reconnectAttemptsRef.current = 0;

    const connect = () => {
      if (!mounted) return;

      try {
        setStatus('connecting');
        ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!mounted) return;
          setStatus('connected');
          reconnectAttemptsRef.current = 0;
          if (!toastShownRef.current) {
            toast.success('WebSocket connected', { autoClose: 2000, toastId: 'ws-connected' });
            toastShownRef.current = true;
          }

          // Heartbeat: send ping every 30s to keep connection alive
          if (heartbeatRef.current) clearInterval(heartbeatRef.current);
          heartbeatRef.current = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }));
            }
          }, 30000);
        };

        ws.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data) as WebSocketMessage;
            if (parsed.type === 'pong') return;
            setLastMessage(parsed);
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        };

        ws.onerror = () => {
          if (!mounted) return;
          setStatus('error');
        };

        ws.onclose = () => {
          if (!mounted) return;
          setStatus('disconnected');
          if (heartbeatRef.current) {
            clearInterval(heartbeatRef.current);
            heartbeatRef.current = null;
          }
          // Infinite reconnection with fast first attempt, then exponential backoff
          // Attempt 1: 300ms, 2: 1s, 3: 2s, 4: 4s, 5+: 8s, max 15s
          reconnectAttemptsRef.current += 1;
          const attempt = reconnectAttemptsRef.current;
          const delay = attempt === 1
            ? 300  // First reconnect: almost instant
            : Math.min(1000 * 2 ** (attempt - 2), 15000);
          if (toastShownRef.current) {
            toast.warn('WebSocket reconnecting...', { autoClose: 3000, toastId: 'ws-reconnecting' });
            toastShownRef.current = false;
          }
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        };
      } catch (e) {
        console.error('Error creating WebSocket:', e);
        setStatus('error');
        // Retry quickly on creation error
        reconnectTimeoutRef.current = setTimeout(connect, 500);
      }
    };

    connect();

    return () => {
      mounted = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      wsRef.current = null;
    };
  }, [url]);

  return { status, lastMessage, send: wsRef.current?.send.bind(wsRef.current) };
}
