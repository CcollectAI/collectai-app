"use client";

import React, { useMemo } from "react";
import { ForecastChart } from "@/components/charts/ForecastChart";
import { CohortHeatmap } from "@/components/charts/CohortHeatmap";
import { PostingTimeHeatmap } from "@/components/charts/PostingTimeHeatmap";
import { MetricCard } from "@/components/ui/MetricCard";

// --- Mock data generators ---

function mockRevenue() {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const actuals = [12400, 15200, 14800, 18900, 21300, 19700, 23500, 25100, 27800, 26400, 30200, 32100];
  const data: { label: string; actual: number; forecast?: number }[] = months.map((m, i) => ({ label: m, actual: actuals[i] }));

  // 4 forecast points using 3-month moving average
  const forecastMonths = ["Jan+1", "Feb+1", "Mar+1", "Apr+1"];
  let prev = actuals.slice(-3);
  for (let i = 0; i < 4; i++) {
    const avg = Math.round(prev.reduce((a, b) => a + b, 0) / 3);
    data.push({ label: forecastMonths[i], actual: undefined as unknown as number, forecast: avg });
    prev = [prev[1], prev[2], avg];
  }

  // Add forecast to last actual point so lines connect
  data[11] = { ...data[11], forecast: data[11].actual };

  return data;
}

const COHORT_DATA = [
  { creator: "Alex Rivera", weeks: [82, 75, 88, 91] },
  { creator: "Jordan Lee", weeks: [45, 62, 58, 71] },
  { creator: "Sam Chen", weeks: [90, 85, 92, 95] },
  { creator: "Taylor Kim", weeks: [30, 42, 55, 48] },
  { creator: "Morgan Blake", weeks: [68, 72, 80, 78] },
  { creator: "Casey Park", weeks: [15, 28, 35, 40] },
];

function mockPostingTimes() {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const result: { hour: number; day: string; avgViews: number }[] = [];
  for (const day of days) {
    for (let h = 0; h < 24; h++) {
      // Peak hours: 9-11 and 18-21, weekends slightly higher
      const isWeekend = day === "Sat" || day === "Sun";
      const isPeak = (h >= 9 && h <= 11) || (h >= 18 && h <= 21);
      const base = isPeak ? 3000 : h >= 6 && h <= 23 ? 1200 : 300;
      const mult = isWeekend ? 1.3 : 1;
      const noise = 0.7 + Math.random() * 0.6;
      result.push({ hour: h, day, avgViews: Math.round(base * mult * noise) });
    }
  }
  return result;
}

const SPARKLINES = {
  avgViews: [1200, 1350, 1100, 1500, 1800, 1650, 1900, 2100, 1950, 2300, 2500, 2400],
  hitRate: [12, 15, 11, 18, 22, 19, 25, 28, 24, 30, 33, 31],
  revenue: [8200, 9100, 8800, 10500, 12200, 11800, 13900, 15100, 14600, 16800, 18200, 17500],
  engagement: [3.2, 3.5, 3.1, 3.8, 4.2, 3.9, 4.5, 4.8, 4.4, 5.1, 5.4, 5.2],
};

export function IntelligenceTab() {
  const revenueData = useMemo(() => mockRevenue(), []);
  const postingData = useMemo(() => mockPostingTimes(), []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Intelligence & Insights
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          AI-powered content analytics
        </p>
      </div>

      {/* Quick Insights */}
      <section>
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3">
          Quick Insights
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Avg Views"
            value={2400}
            trend={8.3}
            sparklineData={SPARKLINES.avgViews}
            subtitle="Per post, last 30d"
          />
          <MetricCard
            label="Hit Rate"
            value={31}
            suffix="%"
            trend={5.1}
            sparklineData={SPARKLINES.hitRate}
            subtitle="Posts exceeding 2x avg"
          />
          <MetricCard
            label="Revenue"
            value={17500}
            prefix="$"
            trend={12.7}
            sparklineData={SPARKLINES.revenue}
            subtitle="Monthly recurring"
          />
          <MetricCard
            label="Engagement"
            value={5.2}
            suffix="%"
            trend={3.2}
            sparklineData={SPARKLINES.engagement}
            subtitle="Avg interaction rate"
          />
        </div>
      </section>

      {/* Revenue Forecast */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Revenue Forecast
        </h3>
        <ForecastChart data={revenueData} height={320} />
      </section>

      {/* Creator Cohort Performance */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Creator Cohort Performance
        </h3>
        <CohortHeatmap data={COHORT_DATA} weekLabels={["W1", "W2", "W3", "W4"]} />
      </section>

      {/* Best Posting Times */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Best Posting Times
        </h3>
        <PostingTimeHeatmap data={postingData} />
      </section>
    </div>
  );
}
