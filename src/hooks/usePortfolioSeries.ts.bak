import supabase from "../../lib/supabaseClient";
import { useSWR } from "../cache/useSWR";

export type Pt = { t: string; v: number };

async function fetchSeries(): Promise<Pt[]> {
  // expects a table:
  //   portfolio_values(at timestamptz, value numeric)
  // with some data in the last ~30 days
  if (!supabase) return demoSeries();
  const { data, error } = await supabase
    .from("portfolio_values")
    .select("at,value")
    .order("at", { ascending: true })
    .limit(365);
  if (error) throw error;
  const rows = (data ?? []) as { at: string; value: number }[];
  if (!rows.length) return demoSeries();
  return rows.map((r) => ({ t: r.at, v: Number(r.value) }));
}

export default function usePortfolioSeries() {
  const { data, loading, refresh } = useSWR<Pt[]>("portfolio:series", fetchSeries, { staleMs: 120_000 });
  const points = data ?? demoSeries();

  const deltaPct = (() => {
    if (points.length < 2) return 0;
    const first = points[0].v;
    const last = points[points.length - 1].v;
    return first ? ((last - first) / first) * 100 : 0;
  })();

  const total = points.length ? points[points.length - 1].v : 0;

  return { data: points, total, deltaPct, loading, refresh };
}

function demoSeries(): Pt[] {
  // 30 points with a gentle uptrend + noise
  const base = 100;
  return Array.from({ length: 30 }).map((_, i) => {
    const v = base + i * 1.6 + (Math.sin(i / 2) * 3);
    const t = new Date(Date.now() - (29 - i) * 24 * 3600 * 1000).toISOString();
    return { t, v: Math.round(v * 10) / 10 };
  });
}
