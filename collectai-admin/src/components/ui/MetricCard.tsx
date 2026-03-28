"use client";

import React from "react";
import { AnimatedCounter } from "./AnimatedCounter";
import { Sparkline } from "./Sparkline";
import { SkeletonCard } from "./Skeleton";

interface MetricCardProps {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  subtitle?: string;
  trend?: number;
  sparklineData?: number[];
  loading?: boolean;
  formatter?: (n: number) => string;
}

export function MetricCard({
  label,
  value,
  prefix,
  suffix,
  subtitle,
  trend,
  sparklineData,
  loading = false,
  formatter,
}: MetricCardProps) {
  if (loading) {
    return <SkeletonCard />;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-5 transition-colors">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
        {label}
      </p>

      <div className="flex items-end gap-3">
        <AnimatedCounter
          value={value}
          prefix={prefix}
          suffix={suffix}
          formatter={formatter}
          className="text-3xl font-bold text-gray-900 dark:text-white"
        />

        {trend !== undefined && (
          <span
            className={`inline-flex items-center gap-0.5 text-sm font-medium ${
              trend >= 0
                ? "text-green-600 dark:text-green-400"
                : "text-red-600 dark:text-red-400"
            }`}
          >
            {trend >= 0 ? (
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 15l7-7 7 7"
                />
              </svg>
            ) : (
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            )}
            {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>

      {sparklineData && sparklineData.length > 1 && (
        <div className="mt-3">
          <Sparkline data={sparklineData} width={120} height={28} />
        </div>
      )}

      {subtitle && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
          {subtitle}
        </p>
      )}
    </div>
  );
}
