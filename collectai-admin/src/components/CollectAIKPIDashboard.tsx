"use client";

import React, { useState, useEffect, useCallback } from "react";
import { MetricCard } from "@/components/ui/MetricCard";
import { Skeleton, SkeletonCard, SkeletonTable } from "@/components/ui/Skeleton";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area, CartesianGrid,
} from "recharts";
import { APP_CONFIG } from "../../admin.config";

const TIFFANY = "#81D8D0";
const BLUE = "#3B82F6";
const AMBER = "#F59E0B";

const sectionCls = "bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-5 transition-colors";
const titleCls = "text-lg font-semibold text-gray-900 dark:text-white mb-4";
const thCls = "text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide px-3 py-2";
const tdCls = "px-3 py-2 text-sm text-gray-700 dark:text-gray-300";

const API = APP_CONFIG.api.baseUrl;
const headers: Record<string, string> = {
  "X-Ops-Key": APP_CONFIG.api.opsKey,
  "Content-Type": "application/json",
};

// ---------- Types ----------

interface FunnelData {
  quickscan_adds: number;
  manual_adds: number;
  barcode_adds: number;
  total_adds_30d: number;
  total_adds_sparkline: number[];
}

interface UsageKPIs {
  dau: number;
  wau: number;
  mau: number;
  avg_session_min: number;
  collections_per_user: number;
  items_per_collection: number;
  dau_trend: number;
  wau_trend: number;
  mau_trend: number;
  session_trend: number;
}

interface TierData {
  name: string;
  value: number;
  color: string;
}

interface FeatureUsageRow {
  feature: string;
  free: number;
  pro: number;
  premium: number;
  conv: string;
}

interface RevenuePoint {
  month: string;
  subs: number;
  affiliate: number;
}

interface RevenueKPIs {
  mrr: number;
  mrr_trend: number;
  mrr_sparkline: number[];
  arpu: number;
  arpu_trend: number;
  churn_rate: number;
  churn_trend: number;
  ltv: number;
  ltv_trend: number;
}

interface AffiliatePartner {
  partner: string;
  clicks: string;
  revenue: string;
  roas: string;
  acos: string;
}

interface AffiliateKPIs {
  total_clicks_30d: number;
  clicks_trend: number;
  total_revenue: number;
  revenue_trend: number;
  avg_commission: number;
  roas: number;
}

interface KPISummary {
  funnel: FunnelData;
  usage: UsageKPIs;
  tiers: TierData[];
  feature_usage: FeatureUsageRow[];
  revenue_chart: RevenuePoint[];
  revenue_kpis: RevenueKPIs;
  affiliate_partners: AffiliatePartner[];
  affiliate_kpis: AffiliateKPIs;
}

// ---------- Empty State ----------

function EmptyState({ message }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6">
      <div className="w-16 h-16 rounded-full bg-gray-100 dark:bg-slate-700 flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">
        Waiting for data
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-md">
        {message || "KPI data will appear once users start using the app. Check back after launch."}
      </p>
    </div>
  );
}

// ---------- Loading Skeleton ----------

function KPILoadingSkeleton() {
  return (
    <div className="space-y-6">
      <section className={sectionCls}>
        <Skeleton width="30%" height={20} rounded="md" className="mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
        <Skeleton width="100%" height={60} rounded="lg" />
      </section>
      <section className={sectionCls}>
        <Skeleton width="30%" height={20} rounded="md" className="mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </section>
      <SkeletonTable rows={6} cols={5} />
      <section className={sectionCls}>
        <Skeleton width="40%" height={20} rounded="md" className="mb-4" />
        <Skeleton width="100%" height={280} rounded="lg" />
      </section>
    </div>
  );
}

// ---------- Fetch ----------

async function fetchKPIData(): Promise<KPISummary | null> {
  try {
    const res = await fetch(`${API}/admin/kpi-summary`, { headers });
    if (!res.ok) return null;
    const json = await res.json();
    // Basic shape validation
    if (!json || typeof json !== "object") return null;
    return json as KPISummary;
  } catch {
    return null;
  }
}

const fmtK = (v: number) => `$${(v / 1000).toFixed(1)}K`;

// ---------- Component ----------

export function CollectAIKPIDashboard() {
  const [data, setData] = useState<KPISummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const result = await fetchKPIData();
    setData(result);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60_000); // refresh every 60s
    return () => clearInterval(interval);
  }, [load]);

  if (loading) return <KPILoadingSkeleton />;
  if (!data) return <EmptyState />;

  const { funnel, usage, tiers, feature_usage, revenue_chart, revenue_kpis, affiliate_partners, affiliate_kpis } = data;

  const funnelBar = [{ name: "Adds", quickscan: funnel.quickscan_adds, manual: funnel.manual_adds, barcode: funnel.barcode_adds }];

  return (
    <div className="space-y-6">
      {/* ───── 1. Item Add Funnel ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Item Add Funnel</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          <MetricCard label="QuickScan Adds" value={funnel.quickscan_adds} />
          <MetricCard label="Manual Adds" value={funnel.manual_adds} />
          <MetricCard label="Barcode Adds" value={funnel.barcode_adds} />
          <MetricCard label="Total Items Added (30d)" value={funnel.total_adds_30d} sparklineData={funnel.total_adds_sparkline} />
        </div>
        <ResponsiveContainer width="100%" height={60}>
          <BarChart data={funnelBar} layout="vertical" stackOffset="expand" barSize={28}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip formatter={(v) => Number(v).toLocaleString()} />
            <Bar dataKey="quickscan" stackId="a" fill={TIFFANY} name="QuickScan" radius={[8, 0, 0, 8]} />
            <Bar dataKey="manual" stackId="a" fill={BLUE} name="Manual" />
            <Bar dataKey="barcode" stackId="a" fill={AMBER} name="Barcode" radius={[0, 8, 8, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="flex gap-5 mt-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: TIFFANY }} /> QuickScan</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: BLUE }} /> Manual</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ background: AMBER }} /> Barcode</span>
        </div>
      </section>

      {/* ───── 2. App Usage KPIs ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>App Usage KPIs</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <MetricCard label="DAU" value={usage.dau} trend={usage.dau_trend} />
          <MetricCard label="WAU" value={usage.wau} trend={usage.wau_trend} />
          <MetricCard label="MAU" value={usage.mau} trend={usage.mau_trend} />
          <MetricCard label="Avg Session (min)" value={usage.avg_session_min} trend={usage.session_trend} />
          <MetricCard label="Collections per User" value={usage.collections_per_user} />
          <MetricCard label="Items per Collection" value={usage.items_per_collection} />
        </div>
      </section>

      {/* ───── 3. Pro-Grade Tier Usage ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Pro-Grade Tier Usage</h2>
        <div className="flex flex-col md:flex-row gap-6">
          <div className="w-full md:w-1/3">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={tiers} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} innerRadius={50} paddingAngle={3}>
                  {tiers.map((d) => <Cell key={d.name} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v) => Number(v).toLocaleString()} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="w-full md:w-2/3 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className={thCls}>Feature</th>
                  <th className={thCls}>Free Users</th>
                  <th className={thCls}>Pro Users</th>
                  <th className={thCls}>Premium Users</th>
                  <th className={thCls}>Conversion %</th>
                </tr>
              </thead>
              <tbody>
                {feature_usage.map((r) => (
                  <tr key={r.feature} className="border-b border-gray-100 dark:border-gray-700/50">
                    <td className={`${tdCls} font-medium`}>{r.feature}</td>
                    <td className={tdCls}>{r.free.toLocaleString()}</td>
                    <td className={tdCls}>{r.pro.toLocaleString()}</td>
                    <td className={tdCls}>{r.premium.toLocaleString()}</td>
                    <td className={tdCls}>{r.conv}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ───── 4. Revenue & Financial KPIs ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Revenue &amp; Financial KPIs</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          <MetricCard label="MRR" value={revenue_kpis.mrr} prefix="$" trend={revenue_kpis.mrr_trend} sparklineData={revenue_kpis.mrr_sparkline} formatter={(n) => n.toLocaleString()} />
          <MetricCard label="ARPU" value={revenue_kpis.arpu} prefix="$" trend={revenue_kpis.arpu_trend} />
          <MetricCard label="Churn Rate" value={revenue_kpis.churn_rate} suffix="%" trend={revenue_kpis.churn_trend} />
          <MetricCard label="LTV" value={revenue_kpis.ltv} prefix="$" trend={revenue_kpis.ltv_trend} />
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={revenue_chart}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} stroke="#9CA3AF" />
            <YAxis tickFormatter={fmtK} tick={{ fontSize: 12 }} stroke="#9CA3AF" />
            <Tooltip formatter={(v) => `$${Number(v).toLocaleString()}`} />
            <Area type="monotone" dataKey="subs" stackId="1" stroke={TIFFANY} fill={TIFFANY} fillOpacity={0.6} name="Subscriptions" />
            <Area type="monotone" dataKey="affiliate" stackId="1" stroke={BLUE} fill={BLUE} fillOpacity={0.6} name="Affiliate" />
            <Legend />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      {/* ───── 5. Affiliate & Backlinking Financials ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Affiliate &amp; Backlinking Financials</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          <MetricCard label="Affiliate Clicks (30d)" value={affiliate_kpis.total_clicks_30d} trend={affiliate_kpis.clicks_trend} />
          <MetricCard label="Affiliate Revenue" value={affiliate_kpis.total_revenue} prefix="$" trend={affiliate_kpis.revenue_trend} />
          <MetricCard label="Avg Commission" value={affiliate_kpis.avg_commission} prefix="$" subtitle="per click" />
          <MetricCard label="ROAS" value={affiliate_kpis.roas} suffix="x" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className={thCls}>Partner</th>
                <th className={thCls}>Clicks</th>
                <th className={thCls}>Revenue</th>
                <th className={thCls}>ROAS</th>
                <th className={thCls}>ACOS</th>
              </tr>
            </thead>
            <tbody>
              {affiliate_partners.map((r) => (
                <tr key={r.partner} className="border-b border-gray-100 dark:border-gray-700/50">
                  <td className={`${tdCls} font-medium`}>{r.partner}</td>
                  <td className={tdCls}>{r.clicks}</td>
                  <td className={tdCls}>{r.revenue}</td>
                  <td className={tdCls}>{r.roas}</td>
                  <td className={tdCls}>{r.acos}</td>
                </tr>
              ))}
              {affiliate_partners.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                    No affiliate data yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
