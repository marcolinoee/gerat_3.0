import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartBoxProps {
  option: echarts.EChartsCoreOption;
  height?: number | string;
  dark?: boolean;
  onChartReady?: (instance: echarts.ECharts) => void;
}

export function EChartBox({
  option,
  height = 360,
  dark = false,
  onChartReady,
}: EChartBoxProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current, dark ? "dark" : undefined, {
      renderer: "canvas",
    });
    instanceRef.current = chart;
    if (onChartReady) onChartReady(chart);

    const ro = new ResizeObserver(() => {
      chart.resize();
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
      instanceRef.current = null;
    };
  }, [dark]);

  useEffect(() => {
    if (instanceRef.current) {
      instanceRef.current.setOption(
        {
          backgroundColor: "transparent",
          ...option,
        },
        { notMerge: true }
      );
    }
  }, [option, dark]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: typeof height === "number" ? `${height}px` : height }}
    />
  );
}
