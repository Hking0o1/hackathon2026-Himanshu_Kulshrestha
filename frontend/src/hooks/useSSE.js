import { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useSSE(onMessage) {
  const [connected, setConnected] = useState(false);
  const handlerRef = useRef(onMessage);

  useEffect(() => {
    handlerRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    const source = new EventSource(`${API_URL}/stream`);

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (event) => {
      try {
        handlerRef.current(JSON.parse(event.data));
      } catch (error) {
        console.error("Failed to parse SSE event", error);
      }
    };

    return () => {
      source.close();
      setConnected(false);
    };
  }, []);

  return connected;
}
