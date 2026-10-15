import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewProps } from "../App";
import { C, ChartTip, fmt, Kpi, Panel } from "../components/ui";
import { returnRates } from "../lib/metrics";

type R = Record<string, number | string | null>;

const WINDOW: Record<string, { label: string; text: string }> = {
  D1: { label: "Next day", text: "came back the day after their first visit" },
  D7: { label: "First week", text: "came back within 7 days" },
  D14: { label: "Second week", text: "were active in days 8–14" },
  D30: { label: "Fourth week", text: "were active in days 24–30" },
};

export function Retention({ ds, mask }: ViewProps) {
  const { agg, users } = ds;
  const rr = useMemo(() => returnRates(users, mask), [users, mask]);
  const monthly = (agg.retention.monthly as R[]).filter((r) => r.D7_rate_pct !== null);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {rr.map((r) => (
          <Kpi key={r.window} label={`${WINDOW[r.window].label} return (${r.window})`} value={fmt.pct(r.ratePct)}
            sub={`${fmt.n(r.returned)} of ${fmt.n(r.eligible)} users ${WINDOW[r.window].text}`}
            info="Measured from each user's first active day. Users who joined too recently to be measured are left out." />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="How many users are still active, week by week" static sub="% of users active in each week after their first visit">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={agg.retention.weekly_curve} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="week" tickFormatter={(w: number) => (w === 0 ? "Start" : `Wk ${w}`)} />
              <YAxis unit="%" domain={[0, 100]} />
              <Tooltip content={<ChartTip unit="%" labelFmt={(l) => (Number(l) === 0 ? "First week" : `Week ${l}`)} />} />
              <Line dataKey="active_pct" name="Still active" stroke={C.c1} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="First-week return by month joined" static sub="Users who joined later came back much more often"
          info="The data does not explain why. Worth checking what changed in the product or marketing over these months.">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthly} margin={{ top: 16, right: 8, left: -14, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="cohort_month" />
              <YAxis unit="%" domain={[0, 100]} />
              <Tooltip content={<ChartTip unit="%" />} />
              <Bar dataKey="D7_rate_pct" name="First-week return" fill={C.c1} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                <LabelList dataKey="D7_rate_pct" position="top" formatter={(v: number) => `${v}%`} className="fill-[rgb(var(--ink2))] text-[11px]" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}
