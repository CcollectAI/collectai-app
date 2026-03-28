"use client";

import React, { useMemo, useState } from "react";

interface PostingTimeHeatmapProps {
  data: { hour: number; day: string; avgViews: number }[];
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function PostingTimeHeatmap({ data }: PostingTimeHeatmapProps) {
  const [tooltip, setTooltip] = useState<{
    day: string;
    hour: number;
    views: number;
    x: number;
    y: number;
  } | null>(null);

  const { lookup, max } = useMemo(() => {
    const map = new Map<string, number>();
    let mx = 0;
    for (const d of data) {
      const key = `${d.day}-${d.hour}`;
      map.set(key, d.avgViews);
      if (d.avgViews > mx) mx = d.avgViews;
    }
    return { lookup: map, max: mx };
  }, [data]);

  function opacity(views: number): number {
    if (max === 0) return 0.05;
    return 0.08 + 0.92 * (views / max);
  }

  return (
    <div className="relative overflow-x-auto">
      <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: `60px repeat(24, 28px)` }}>
        {/* Header row */}
        <div />
        {HOURS.map((h) => (
          <div key={h} className="text-[10px] text-center text-gray-400 dark:text-gray-500">
            {h}
          </div>
        ))}

        {/* Data rows */}
        {DAYS.map((day) => (
          <React.Fragment key={day}>
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 flex items-center">
              {day}
            </div>
            {HOURS.map((hour) => {
              const views = lookup.get(`${day}-${hour}`) ?? 0;
              return (
                <div
                  key={hour}
                  className="w-7 h-7 rounded-sm cursor-pointer transition-transform hover:scale-110"
                  style={{
                    backgroundColor: `rgba(129, 216, 208, ${opacity(views)})`,
                  }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setTooltip({ day, hour, views, x: rect.left, y: rect.top - 40 });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })}
          </React.Fragment>
        ))}
      </div>

      {tooltip && (
        <div
          className="fixed z-50 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded px-2 py-1 pointer-events-none shadow-lg"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.day} {tooltip.hour}:00 &mdash; {tooltip.views.toLocaleString()} avg views
        </div>
      )}
    </div>
  );
}
