"use client";

import React from "react";
import { MetricCard } from "@/components/ui/MetricCard";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area, CartesianGrid,
} from "recharts";

const TIFFANY = "#81D8D0";
const BLUE = "#3B82F6";
const AMBER = "#F59E0B";

const sectionCls = "bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-5 transition-colors";
const titleCls = "text-lg font-semibold text-gray-900 dark:text-white mb-4";
const thCls = "text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide px-3 py-2";
const tdCls = "px-3 py-2 text-sm text-gray-700 dark:text-gray-300";

// Sparkline helper
const spark = (min: number, max: number, n = 30) =>
  Array.from({ length: n }, () => Math.round(min + Math.random() * (max - min)));

// ---------- Section 1: Item Add Funnel ----------
const funnelBar = [{ name: "Adds", quickscan: 4832, manual: 2147, barcode: 1563 }];

// ---------- Section 3: Pro-Grade Tier ----------
const tierData = [
  { name: "Free", value: 2103, color: "#94A3B8" },
  { name: "Pro", value: 584, color: BLUE },
  { name: "Premium", value: 160, color: AMBER },
];

const featureUsage = [
  { feature: "Condition Grading", free: 342, pro: 489, premium: 148, conv: "63.8%" },
  { feature: "Set Completion", free: 210, pro: 412, premium: 135, conv: "72.1%" },
  { feature: "Price Predictions", free: 1890, pro: 584, premium: 160, conv: "27.7%" },
  { feature: "Portfolio Analytics", free: 0, pro: 467, premium: 158, conv: "84.0%" },
  { feature: "Export Collections", free: 0, pro: 398, premium: 160, conv: "75.1%" },
  { feature: "Priority Alerts", free: 0, pro: 0, premium: 142, conv: "88.8%" },
];

// ---------- Section 4: Revenue ----------
const revenueData = [
  { month: "Jan", subs: 8200, affiliate: 1100 },
  { month: "Feb", subs: 9000, affiliate: 1300 },
  { month: "Mar", subs: 9800, affiliate: 1500 },
  { month: "Apr", subs: 10400, affiliate: 1800 },
  { month: "May", subs: 11200, affiliate: 2100 },
  { month: "Jun", subs: 12000, affiliate: 2400 },
];

// ---------- Section 5: Affiliate ----------
const affiliatePartners = [
  { partner: "eBay", clicks: "8,240", revenue: "$1,156", roas: "5.1x", acos: "19.6%" },
  { partner: "Amazon", clicks: "4,120", revenue: "$494", roas: "3.2x", acos: "31.3%" },
  { partner: "StockX", clicks: "2,890", revenue: "$347", roas: "4.8x", acos: "20.8%" },
  { partner: "TCGPlayer", clicks: "1,940", revenue: "$252", roas: "6.1x", acos: "16.4%" },
  { partner: "Cardmarket", clicks: "1,242", revenue: "$163", roas: "3.9x", acos: "25.6%" },
];

const fmtK = (v: number) => `$${(v / 1000).toFixed(1)}K`;

export function CollectAIKPIDashboard() {
  return (
    <div className="space-y-6">
      {/* ───── 1. Item Add Funnel ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Item Add Funnel</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          <MetricCard label="QuickScan Adds" value={4832} trend={12} />
          <MetricCard label="Manual Adds" value={2147} trend={-3} />
          <MetricCard label="Barcode Adds" value={1563} trend={8} />
          <MetricCard label="Total Items Added (30d)" value={8542} sparklineData={spark(200, 400)} />
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
          <MetricCard label="DAU" value={1247} trend={5.2} />
          <MetricCard label="WAU" value={3891} trend={3.8} />
          <MetricCard label="MAU" value={8432} trend={7.1} />
          <MetricCard label="Avg Session (min)" value={4.7} trend={0.3} />
          <MetricCard label="Collections per User" value={2.3} />
          <MetricCard label="Items per Collection" value={34.6} />
        </div>
      </section>

      {/* ───── 3. Pro-Grade Tier Usage ───── */}
      <section className={sectionCls}>
        <h2 className={titleCls}>Pro-Grade Tier Usage</h2>
        <div className="flex flex-col md:flex-row gap-6">
          <div className="w-full md:w-1/3">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={tierData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} innerRadius={50} paddingAngle={3}>
                  {tierData.map((d) => <Cell key={d.name} fill={d.color} />)}
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
                {featureUsage.map((r) => (
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
          <MetricCard label="MRR" value={12840} prefix="$" trend={9.2} sparklineData={spark(9000, 13000, 12)} formatter={(n) => n.toLocaleString()} />
          <MetricCard label="ARPU" value={4.51} prefix="$" trend={2.1} />
          <MetricCard label="Churn Rate" value={3.2} suffix="%" trend={-0.5} />
          <MetricCard label="LTV" value={141} prefix="$" trend={8} />
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={revenueData}>
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
          <MetricCard label="Affiliate Clicks (30d)" value={18432} trend={14} />
          <MetricCard label="Affiliate Revenue" value={2412} prefix="$" trend={18} />
          <MetricCard label="Avg Commission" value={0.13} prefix="$" subtitle="per click" />
          <MetricCard label="ROAS" value={4.2} suffix="x" />
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
              {affiliatePartners.map((r) => (
                <tr key={r.partner} className="border-b border-gray-100 dark:border-gray-700/50">
                  <td className={`${tdCls} font-medium`}>{r.partner}</td>
                  <td className={tdCls}>{r.clicks}</td>
                  <td className={tdCls}>{r.revenue}</td>
                  <td className={tdCls}>{r.roas}</td>
                  <td className={tdCls}>{r.acos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
