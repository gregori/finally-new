"use client";

import { useEffect, useRef } from "react";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

interface MainChartProps {
  ticker: string;
  sparklineData: number[];
}

export function MainChart({ ticker, sparklineData }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<ISeriesApi<any> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cleanupRo: (() => void) | undefined;

    async function initChart() {
      const { createChart, LineSeries } = await import("lightweight-charts");
      if (!containerRef.current) return;

      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
        layout: {
          background: { color: "#0d1117" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#30363d" },
          horzLines: { color: "#30363d" },
        },
        crosshair: {
          vertLine: { color: "#484f58" },
          horzLine: { color: "#484f58" },
        },
        rightPriceScale: {
          borderColor: "#30363d",
        },
        timeScale: {
          borderColor: "#30363d",
          timeVisible: true,
        },
      });

      const series = chart.addSeries(LineSeries, {
        color: "#209dd7",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });

      chartRef.current = chart;
      seriesRef.current = series;

      const ro = new ResizeObserver(() => {
        if (containerRef.current) {
          chart.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
          });
        }
      });
      ro.observe(containerRef.current);
      cleanupRo = () => ro.disconnect();
    }

    initChart();

    return () => {
      cleanupRo?.();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, []);

  // Update data when sparklineData changes
  useEffect(() => {
    if (!seriesRef.current || sparklineData.length === 0) return;

    const now = Math.floor(Date.now() / 1000);
    const data = sparklineData.map((price, i) => ({
      time: (now - (sparklineData.length - 1 - i)) as import("lightweight-charts").UTCTimestamp,
      value: price,
    }));

    seriesRef.current.setData(data);
  }, [sparklineData]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="px-3 py-2 text-xs font-semibold flex items-center gap-2"
        style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}
      >
        <span className="uppercase tracking-wider">Chart</span>
        <span style={{ color: "#ecad0a", fontFamily: "monospace" }}>
          {ticker}
        </span>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
