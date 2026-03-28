"use client";

import { useEffect, useRef } from "react";

interface AnomalyConfig {
  metricName: string;
  current: number;
  previous: number;
  threshold?: number;
  direction?: "up" | "down" | "both";
}

type ToastFn = (opts: {
  title: string;
  description: string;
  variant?: "default" | "destructive" | "warning" | "info";
}) => void;

export function useAnomalyDetection(configs: AnomalyConfig[], toast: ToastFn) {
  // Track which metric+value combos we have already alerted on
  const alertedRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    for (const config of configs) {
      const {
        metricName,
        current,
        previous,
        threshold = 0.2,
        direction = "both",
      } = config;

      // Skip if previous is zero (can't compute percentage change)
      if (previous === 0) continue;

      // Skip if we already fired for this exact current value
      if (alertedRef.current.get(metricName) === current) continue;

      const change = (current - previous) / Math.abs(previous);
      const absChange = Math.abs(change);

      if (absChange < threshold) continue;

      const dropped = change < 0;
      const spiked = change > 0;
      const pct = (absChange * 100).toFixed(1);

      let shouldFire = false;
      let variant: "warning" | "info" = "info";

      if (direction === "down" && dropped) {
        shouldFire = true;
        variant = "warning";
      } else if (direction === "up" && spiked) {
        shouldFire = true;
        variant = "info";
      } else if (direction === "both" && absChange >= threshold) {
        shouldFire = true;
        variant = dropped ? "warning" : "info";
      }

      if (shouldFire) {
        alertedRef.current.set(metricName, current);
        toast({
          title: `${metricName} ${dropped ? "dropped" : "spiked"} by ${pct}%`,
          description: `Changed from ${previous.toLocaleString()} to ${current.toLocaleString()}`,
          variant,
        });
      }
    }
  }, [configs, toast]);
}
