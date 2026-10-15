import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewProps } from "../App";
import { C, ChartTip, Empty, Panel } from "../components/ui";
import { dailySeries, histogram } from "../lib/metrics";

const bins = (vals: number[], edges: number[], labels: string[]) => histogram(vals, edges).map((c, i) => ({ bin: labels[i], users: c }));

const SEGMENT_NOTE: Record<string, string> = {
  "No Recorded Activity": "Signed up, never used a feature",
  "One-Time Users": "Active on a single day",
  "Occasional Users": "A few active days",
  "Returning Users": "Comes back regularly",
  "Multi-Feature Users": "Uses many different features",
  "High-Frequency Users": "Most active quarter of users",
};

export function Behavior({ ds, flt, mask }: ViewProps) {
  const { f, users } = ds;
  const sel = useMemo(() => users.filter((_, i) => mask[i]), [users, mask]);
  const weekly = useMemo(() => {
    const s = dailySeries(f, mask, flt);
    const out: { week: string; avgDau: number }[] = [];
    for (let i = 0; i < s.length; i += 7) {
      const w = s.slice(i, i + 7);
      out.push({ week: w[0].date, avgDau: Math.round((w.reduce((a, b) => a + b.dau, 0) / w.length) * 10) / 10 });
    }
    return out;
  }, [f, mask, flt]);
  const freq = useMemo(() => bins(sel.map((u) => u.sessions), [0, 1, 2, 3, 6, 11, 21, 1e6], ["0", "1", "2", "3–5", "6–10", "11–20", "21+"]), [sel]);
  const actDays = useMemo(() => bins(sel.map((u) => u.activeDays), [0, 1, 2, 3, 5, 10, 15, 1e6], ["0", "1", "2", "3–4", "5–9", "10–14", "15+"]), [sel]);
  const dur = useMemo(() => {
    const vals: number[] = [];
    for (const r of f.sessions) if (mask[r[0]] && r[1] >= flt.dayFrom && r[1] <= flt.dayTo) vals.push(r[4]);
    const edges = [20, 30, 40, 50, 60, 80, 100, 150, 1e6];
    const labels = ["20–29", "30–39", "40–49", "50–59", "60–79", "80–99", "100–149", "150+"];
    const sorted = [...vals].sort((a, b) => a - b);
    return { data: histogram(vals, edges).map((c, i) => ({ bin: labels[i], sessions: c })), median: sorted.length ? sorted[Math.floor(sorted.length / 2)] : null, n: vals.length };
  }, [f, mask, flt]);
  const segs = useMemo(() => f.segments.map((s, i) => ({ segment: s, users: sel.filter((u) => u.segment === i).length })), [f, sel]);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Active users over time" sub="Average daily active users, week by week">
        {weekly.length === 0 ? <Empty /> : (
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={weekly} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="week" tickFormatter={(d: string) => d.slice(5)} minTickGap={30} />
              <YAxis />
              <Tooltip content={<ChartTip labelFmt={(l) => `Week of ${l}`} />} />
              <Line dataKey="avgDau" name="Avg daily users" stroke={C.c1} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Panel>
      <Panel title="How often users visit" sub="Users by total number of sessions">
        <ResponsiveContainer width="100%" height={230}>
          <BarChart data={freq} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="bin" />
            <YAxis allowDecimals={false} />
            <Tooltip content={<ChartTip />} />
            <Bar dataKey="users" name="Users" fill={C.c1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="Session length" sub={`Seconds per session · median ${dur.median ?? "—"}s`}
        info="Most visits are short. Longer sessions did not mean users did more.">
        {dur.n === 0 ? <Empty /> : (
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={dur.data} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="bin" interval={0} tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} />
              <Tooltip content={<ChartTip unit=" sessions" />} />
              <Bar dataKey="sessions" name="Sessions" fill={C.c1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>
      <Panel title="How many days users were active" sub="Users by number of different active days">
        <ResponsiveContainer width="100%" height={230}>
          <BarChart data={actDays} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="bin" />
            <YAxis allowDecimals={false} />
            <Tooltip content={<ChartTip />} />
            <Bar dataKey="users" name="Users" fill={C.c1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel className="lg:col-span-2" title="User groups" sub="Every user belongs to exactly one group, based on how often and how broadly they use the product">
        <div className="grid gap-4 md:grid-cols-5">
          <div className="md:col-span-3">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={segs} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="segment" width={140} tickLine={false} tick={{ fontSize: 11 }} />
                <Tooltip content={<ChartTip />} />
                <Bar dataKey="users" name="Users" fill={C.c1} radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-1.5 text-xs md:col-span-2">
            {segs.map((s) => (
              <li key={s.segment} className="flex justify-between gap-3 border-b border-rule/60 pb-1">
                <span><span className="font-medium text-ink">{s.segment}</span><span className="block text-ink2">{SEGMENT_NOTE[s.segment]}</span></span>
                <span className="tabular-nums text-ink">{s.users.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      </Panel>
    </div>
  );
}
