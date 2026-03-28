"use client";

import { isUsingDemoData } from "@/lib/kpi";

export function AdminDemoBanner() {
  if (!isUsingDemoData()) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div>
          <p className="text-xs font-semibold text-amber-800">Demo Mode</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-amber-700">
            Showing sample data. Connect Supabase to see live metrics.
          </p>
        </div>
      </div>
    </div>
  );
}
