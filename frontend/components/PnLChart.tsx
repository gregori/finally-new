"use client";

import { useEffect, useRef } from "react";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import type { PortfolioSnapshot } from "@/lib/api";

interface PnLChartProps {
  snapshots: PortfolioSnapshot[];
}

export function PnLChart({ snapshots }: PnLChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<ISeriesApi<any> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cleanupRo: (() => void) | undefined;

    async function init() {
      const { createChart, AreaSeries } = await import("lightweight-charts");
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
        rightPriceScale: { borderColor: "#30363d" },
        timeScale: { borderColor: "#30363d", timeVisible: true },
      });

      const series = chart.addSeries(AreaSeries, {
        lineColor: "#ecad0a",
        topColor: "rgba(236, 173, 10, 0.3)",
        bottomColor: "rgba(236, 173, 10, 0.0)",
        lineWidth: 2,
        priceLineVisible: false,
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

    init();

    return () => {
      cleanupRo?.();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || snapshots.length === 0) return;

    const data = snapshots
      .map((s) => ({
        time: Math.floor(
          new Date(s.recorded_at).getTime() / 1000
        ) as import("lightweight-charts").UTCTimestamp,
        value: s.total_value,
      }))
      .sort((a, b) => a.time - b.time);

    // Deduplicate by time (keep last value per timestamp)
    const deduped = data.filter(
      (d, i, arr) => i === arr.length - 1 || d.time !== arr[i + 1].time
    );

    if (deduped.length > 0) {
      seriesRef.current.setData(deduped);
    }
  }, [snapshots]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="px-3 py-2 text-xs font-semibold uppercase tracking-wider"
        style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}
      >
        Portfolio P&amp;L
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
