"use client";

import { useEffect, useRef, useState } from "react";

export interface PricePoint {
  price: number;
  prev_price: number;
  change: number;
  change_pct: number;
}

export interface PriceStreamState {
  prices: Record<string, PricePoint>;
  sparklines: Record<string, number[]>;
  connectionStatus: "connected" | "reconnecting" | "disconnected";
}

const MAX_SPARKLINE_POINTS = 60;

export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<Record<string, PricePoint>>({});
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [connectionStatus, setConnectionStatus] = useState<
    "connected" | "reconnecting" | "disconnected"
  >("reconnecting");

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function connect() {
      if (esRef.current) {
        esRef.current.close();
      }

      setConnectionStatus("reconnecting");
      const es = new EventSource("/api/stream/prices");
      esRef.current = es;

      es.addEventListener("open", () => {
        setConnectionStatus("connected");
      });

      es.addEventListener("message", (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as {
            ticker: string;
            price: number;
            prev_price: number;
            change: number;
            change_pct: number;
          };

          setPrices((prev) => ({
            ...prev,
            [data.ticker]: {
              price: data.price,
              prev_price: data.prev_price,
              change: data.change,
              change_pct: data.change_pct,
            },
          }));

          setSparklines((prev) => {
            const existing = prev[data.ticker] ?? [];
            const updated = [...existing, data.price].slice(-MAX_SPARKLINE_POINTS);
            return { ...prev, [data.ticker]: updated };
          });
        } catch {
          // Ignore malformed events
        }
      });

      es.addEventListener("error", () => {
        setConnectionStatus("disconnected");
        es.close();
        esRef.current = null;
        // EventSource will reconnect automatically, but we track status manually
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      });
    }

    connect();

    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  return { prices, sparklines, connectionStatus };
}
