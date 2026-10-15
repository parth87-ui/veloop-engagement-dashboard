import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewProps } from "../App";
import { C, ChartTip, Panel } from "../components/ui";
import { featureAdoption } from "../lib/metrics";

type R = Record<string, number | string | null>;

export function Features({ ds, mask, flt }: ViewProps) {
  const { agg, f, users } = ds;
  const adoption = useMemo(
    () => featureAdoption(users, mask, f.features).sort((a, b) => (b.exposedPct ?? 0) - (a.exposedPct ?? 0)),
    [users, mask, f.features],
  );
  const ft = agg.features.table as R[];
  const repeat = [...ft].sort((a, b) => Number(b.repeat_usage_rate_pct) - Number(a.repeat_usage_rate_pct));
  const lost = ft.filter((r) => r.event_completion_rate_pct !== null).map((r) => ({
    feature: r.feature,
    Completed: r.event_completion_rate_pct,
    lostPct: r.event_abandonment_rate_pct,
    how: String(r.feature) === "Watch Ads" ? "skipped" : String(r.feature) === "CAPTCHA" ? "failed" : "abandoned",
  }));
  const tasks = (agg.features.task_categories as R[]).map((r) => ({
    category: r.task_category,
    Completed: Math.round((Number(r.completed) / Number(r.records)) * 1000) / 10,
    Abandoned: Math.round((Number(r.abandoned) / Number(r.records)) * 1000) / 10,
    Failed: Math.round((Number(r.failed) / Number(r.records)) * 1000) / 10,
    Pending: Math.round((Number(r.pending) / Number(r.records)) * 1000) / 10,
  }));
  const sel = flt.feature !== null ? f.features[flt.feature] : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel className="lg:col-span-2" title="Feature usage" sub="Share of active users who used each feature, and who completed it at least once"
        info="Wallet, Exchange Center and Leaderboard are view-only pages, so they have no 'completed' bar.">
        <ResponsiveContainer width="100%" height={330}>
          <BarChart data={adoption} margin={{ top: 4, right: 8, left: -10, bottom: 50 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="feature" angle={-35} textAnchor="end" interval={0} tick={{ fontSize: 10 }} />
            <YAxis unit="%" domain={[0, 100]} />
            <Tooltip content={<ChartTip unit="%" />} />
            <Legend verticalAlign="top" height={24} />
            <Bar dataKey="exposedPct" name="Used" fill={C.c1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="completedPct" name="Completed at least once" fill={C.c3} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="Which features users come back to" static sub="Share of a feature's users who used it in 2+ sessions">
        <ResponsiveContainer width="100%" height={340}>
          <BarChart data={repeat} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" unit="%" domain={[0, 100]} />
            <YAxis type="category" dataKey="feature" width={110} tickLine={false} tick={{ fontSize: 11 }} />
            <Tooltip content={<ChartTip unit="%" />} />
            <Bar dataKey="repeat_usage_rate_pct" name="Used again" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}>
              {repeat.map((r) => <Cell key={String(r.feature)} fill={sel && r.feature === sel ? C.c2 : C.c1} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="Where attempts are lost" static sub="Three features lose about half of all attempts">
        <div className="space-y-4 pt-2">
          {lost.map((r) => (
            <div key={String(r.feature)}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-medium text-ink">{r.feature}</span>
                <span className="text-ink2">{r.lostPct}% {r.how}</span>
              </div>
              <div className="flex h-3 overflow-hidden rounded-full bg-[var(--grid)]" role="img" aria-label={`${r.feature}: ${r.Completed}% completed, ${r.lostPct}% ${r.how}`}>
                <div style={{ width: `${r.Completed}%`, background: C.c1 }} />
                <div style={{ width: `${r.lostPct}%`, background: C.c2 }} />
              </div>
            </div>
          ))}
          <div className="flex gap-4 text-[11px] text-ink2">
            <span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: C.c1 }} />Completed</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: C.c2 }} />Skipped / failed / abandoned</span>
          </div>
          <p className="text-xs text-ink2">Other features do not record failures, so a comparable rate is not available for them.</p>
        </div>
      </Panel>
      <Panel className="lg:col-span-2" title="Task results by category" static sub="What happened to each task attempt">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={tasks} layout="vertical" stackOffset="expand" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
            <XAxis type="number" tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
            <YAxis type="category" dataKey="category" width={110} tickLine={false} tick={{ fontSize: 11 }} />
            <Tooltip content={<ChartTip unit="%" />} />
            <Legend verticalAlign="top" height={24} />
            {(["Completed", "Abandoned", "Failed", "Pending"] as const).map((k, i) => (
              <Bar key={k} dataKey={k} stackId="a" fill={[C.c1, C.c2, C.c4, C.muted][i]} stroke="rgb(var(--panel))" strokeWidth={2} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}
