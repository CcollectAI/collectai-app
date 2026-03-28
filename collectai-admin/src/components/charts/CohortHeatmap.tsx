"use client";

import React from "react";

interface CohortHeatmapProps {
  data: { creator: string; weeks: number[] }[];
  weekLabels?: string[];
}

function cellColor(v: number, dark: boolean): string {
  if (v >= 75) return dark ? "bg-emerald-700" : "bg-emerald-300";
  if (v >= 50) return dark ? "bg-emerald-900" : "bg-emerald-100";
  if (v >= 25) return dark ? "bg-amber-900" : "bg-amber-100";
  return dark ? "bg-red-900" : "bg-red-100";
}

function cellText(v: number): string {
  if (v >= 75) return "text-emerald-900 dark:text-emerald-100";
  if (v >= 50) return "text-emerald-800 dark:text-emerald-200";
  if (v >= 25) return "text-amber-800 dark:text-amber-200";
  return "text-red-800 dark:text-red-200";
}

export function CohortHeatmap({ data, weekLabels }: CohortHeatmapProps) {
  const cols = data[0]?.weeks.length ?? 0;
  const labels = weekLabels ?? Array.from({ length: cols }, (_, i) => `W${i + 1}`);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-1">
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-gray-500 dark:text-gray-400 pr-3">
              Creator
            </th>
            {labels.map((l) => (
              <th
                key={l}
                className="text-center text-xs font-medium text-gray-500 dark:text-gray-400 px-1"
              >
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.creator}>
              <td className="text-sm font-medium text-gray-700 dark:text-gray-300 pr-3 whitespace-nowrap">
                {row.creator}
              </td>
              {row.weeks.map((v, i) => (
                <td
                  key={i}
                  className={`w-14 h-10 text-center text-xs font-semibold rounded-md ${cellColor(v, false)} dark:${cellColor(v, true).replace("bg-", "dark:bg-").split(" ")[0]} ${cellText(v)}`}
                >
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
