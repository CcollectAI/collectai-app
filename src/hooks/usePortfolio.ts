import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Row = { ts: string; value: number };

export default function usePortfolio() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const { data, error } = await supabase
          .from("portfolio_values")
          .select("ts, value")
          .order("ts", { ascending: true });
        if (error) throw error;
        on && setRows((data as Row[]) ?? []);
      } catch (e: any) {
        on && setError(e?.message ?? "Failed to load portfolio");
        on && setRows([
          { ts: "2025-01-01", value: 100 },
          { ts: "2025-02-01", value: 102 },
          { ts: "2025-03-01", value: 98 },
          { ts: "2025-04-01", value: 110 },
          { ts: "2025-05-01", value: 113 },
          { ts: "2025-06-01", value: 120 },
          { ts: "2025-07-01", value: 118 },
          { ts: "2025-08-01", value: 122 },
          { ts: "2025-09-01", value: 129 },
        ]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, []);

  const series = useMemo(() => rows.map(r => r.value), [rows]);
  const current = rows.at(-1)?.value ?? null;
  const previous = rows.length > 1 ? rows[rows.length-2].value : null;
  const delta = current != null && previous != null ? current - previous : null;
  const deltaPct = delta != null && previous ? (delta / previous) * 100 : null;

  return { rows, series, current, delta, deltaPct, loading, error };
}
