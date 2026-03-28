"use client";

import React from "react";
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ForecastChartProps {
  data: { label: string; actual: number; forecast?: number }[];
  title?: string;
  height?: number;
  color?: string;
  forecastColor?: string;
}

export function ForecastChart({
  data,
  title,
  height = 300,
  color = "#81D8D0",
  forecastColor = "#94A3B8",
}: ForecastChartProps) {
  return (
    <div>
      {title && (
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
          {title}
        </h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} tickLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgba(31,41,55,0.95)",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              fontSize: 12,
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          />
          <Area
            type="monotone"
            dataKey="actual"
            stroke={color}
            fill={color}
            fillOpacity={0.15}
            strokeWidth={2}
            dot={{ r: 3, fill: color }}
            name="Actual"
          />
          <Line
            type="monotone"
            dataKey="forecast"
            stroke={forecastColor}
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={{ r: 3, fill: forecastColor }}
            name="Forecast"
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
