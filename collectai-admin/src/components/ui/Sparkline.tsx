"use client";

import React from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  showDot?: boolean;
}

export function Sparkline({
  data,
  width = 80,
  height = 24,
  color = "#81D8D0",
  showDot = true,
}: SparklineProps) {
  if (!data.length) return null;

  const chartData = data.map((value, index) => ({ value, index }));
  const lastIndex = data.length - 1;

  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={
              showDot
                ? (props: Record<string, unknown>) => {
                    const { cx, cy, index } = props as {
                      cx: number;
                      cy: number;
                      index: number;
                    };
                    if (index !== lastIndex) return <g key={`dot-${index}`} />;
                    return (
                      <circle
                        key={`dot-${index}`}
                        cx={cx}
                        cy={cy}
                        r={2}
                        fill={color}
                        stroke="none"
                      />
                    );
                  }
                : false
            }
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
