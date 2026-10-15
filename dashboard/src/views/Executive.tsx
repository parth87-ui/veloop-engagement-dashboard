import { useMemo } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, LabelList, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewProps } from "../App";
import { C, ChartTip, Empty, fmt, Kpi, Panel } from "../components/ui";
import { activationFunnel, dailySeries, execKpis, isFullWindow } from "../lib/metrics";

// plain-language display names for the canonical funnel stages (calculations unchanged)
const LABEL: Record<string, string> = {
  "Registered": "Signed up",
  "Logged in": "Opened the app",
  "Used a feature": "Used a feature",
  "Started an activity": "Started an activity",
  "Completed a meaningful activity": "Completed an activity",
  "Returned (2nd active day)": "Came back on a 2nd day",
  "Established (≥3 meaningful days)": "Active on 3+ days",
};

export function Executive({ ds, flt, mask }: ViewProps) {
  const k = useMemo(() => execKpis(ds.users, ds.f, flt), [ds, flt]);
  const series = useMemo(() => dailySeries(ds.f, mask, flt), [ds, mask, flt]);
  const funnel = useMemo(
    () => activationFunnel(ds.users, mask).map((s) => ({ ...s, stage: LABEL[s.stage] ?? s.stage })),
    [ds, mask],
  );
  const W = ds.meta.executive_kpis.activation_window_days;
  const full = isFullWindow(flt, ds.f);
  const findings = ds.agg.insights.findings as Record<string, string>[];
  const top = ["FND-01", "FND-03", "FND-05", "FND-07", "FND-09"].map((id) => findings.find((x) => x.finding_id === id)).filter(Boolean) as Record<string, string>[];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Registered users" value={fmt.n(k.totalUsers)} sub="Matching the filters" />
        <Kpi label="Active users" value={fmt.n(k.activeUsers)} sub={full ? "Used at least one feature" : "Active in the selected dates"} />
        <Kpi label="Sessions" value={fmt.n(k.sessions)} sub={`${fmt.n(k.avgSessionsPerUser, 1)} per registered user`} />
        <Kpi label="Active days" value={fmt.n(k.activeDays)} sub="User-days with activity" />
        <Kpi label={`Activation (${W} days)`} value={fmt.pct(k.activationRatePct)} sub={`Completed a first activity within ${W} days of sign-up`}
          info={`Share of users who completed their first rewarding activity within ${W} days of signing up. Only users who signed up at least ${W} days before the end of the data are counted (${fmt.n(k.activationEligible)} users).`} />
        <Kpi label="Came back" value={fmt.pct(k.repeatUserRatePct)} sub="Active users seen on 2+ days"
          info="Share of active users who were active on at least two different days." />
        <Kpi label="Broad users" value={fmt.pct(k.multiFeatureRatePct)} sub={`Completed ${ds.agg.thresholds.multi_feature_min_completed_features}+ different features`}
          info="Share of active users who completed activities in many different features (the top quarter by variety)." />
        <Kpi label="Task completion" value={fmt.pct(ds.agg.features.task_overall.completion_rate_resolved_pct)} sub="Overall · finished task attempts that succeeded"
          info="Completed tasks ÷ all finished task attempts (completed, failed or abandoned). Shown for all users; filters do not change it." />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel className="lg:col-span-3" title="Daily active users" sub="Users active each day, with 7-day average">
          {series.length === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={series} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} minTickGap={36} />
                <YAxis allowDecimals={false} />
                <Tooltip content={<ChartTip />} />
                <Legend verticalAlign="top" height={24} iconType="plainline" />
                <Area type="monotone" dataKey="dau" name="Daily active users" stroke={C.muted} fill={C.muted} fillOpacity={0.18} strokeWidth={1} isAnimationActive={false} />
                <Line type="monotone" dataKey="avg7" name="7-day average" stroke={C.c1} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </Panel>
        <Panel className="lg:col-span-2" title="User journey" sub="How many users reach each step"
          info="Each step counts users who also completed every step above it.">
          {funnel[0].users === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={funnel} layout="vertical" margin={{ top: 0, right: 56, left: 8, bottom: 0 }}>
                <XAxis type="number" hide domain={[0, funnel[0].users]} />
                <YAxis type="category" dataKey="stage" width={150} tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <Tooltip content={<ChartTip />} />
                <Bar dataKey="users" name="Users" fill={C.c1} radius={[0, 4, 4, 0]} barSize={18} isAnimationActive={false}>
                  <LabelList dataKey="pctOfFirst" position="right" formatter={(v: number) => `${v}%`} className="fill-[rgb(var(--ink2))] text-[11px]" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Panel>
      </div>

      <Panel title="Key findings" sub="What the data shows" static>
        <ol className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {top.map((x, i) => (
            <li key={x.finding_id} className="rounded-lg border border-rule p-3">
              <div className="text-[11px] font-semibold text-brand">Finding {i + 1}</div>
              <p className="mt-1 text-sm font-medium text-ink">{x.title}</p>
              <p className="mt-1 text-xs text-ink2">{x.observation}</p>
            </li>
          ))}
        </ol>
      </Panel>
    </div>
  );
}
