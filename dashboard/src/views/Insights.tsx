import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewProps } from "../App";
import { C, ChartTip, Panel } from "../components/ui";

type R = Record<string, number | string | null>;

// plain-language labels for the drop-off steps shown to the client (prefix of the stage name -> label)
const DROP_STEPS: [string, string][] = [
  ["Registration → Login", "Signed up but never opened the app"],
  ["First active day → second", "Did not come back after their first day"],
  ["Second active day → third", "Came back once, but not a third time"],
  ["Third active day → seventh", "Did not reach 7 active days"],
  ["First week → later", "Not active again after the first week"],
  ["Task start → task completion", "Task attempts that were not completed"],
  ["Feature view → feature start", "Viewed a mission or spin but did not start it"],
];

const PRIORITY_STYLE: Record<string, string> = {
  High: "bg-[color-mix(in_srgb,var(--c2)_18%,transparent)] text-ink",
  Medium: "bg-[color-mix(in_srgb,var(--c4)_18%,transparent)] text-ink",
  Low: "bg-[color-mix(in_srgb,var(--c-muted)_25%,transparent)] text-ink",
};

export function Insights({ ds }: ViewProps) {
  const { agg } = ds;
  const dm = agg.dropoff.matrix as R[];
  const drops = DROP_STEPS.map(([prefix, label]) => {
    const r = dm.find((x) => String(x.stage).startsWith(prefix));
    return r ? { label, pct: Number(r.drop_off_pct), lost: Number(r.drop_off), base: Number(r.entering) } : null;
  }).filter(Boolean) as { label: string; pct: number; lost: number; base: number }[];

  // client-facing problem cards: one clear rate per problem, all read from the analysis outputs
  const drop = (prefix: string) => dm.find((x) => String(x.stage).startsWith(prefix)) as R;
  const ft = Object.fromEntries((agg.features.table as R[]).map((r) => [String(r.feature), r]));
  const to = agg.features.task_overall;
  const pendingOld = (agg.anomalies.summary as R[]).find((r) => String(r.type).startsWith("Pending")) as R | undefined;
  const firstVisitDays = Number(agg.lifecycle.time_to.hours_to_first_session.summary_hours.p50) / 24;
  const problems = [
    { area: "Onboarding", title: "Slow start after sign-up", value: `${firstVisitDays.toFixed(1)} days`,
      note: "typical wait between signing up and the first visit" },
    { area: "Return", title: "Many users don't come back after day one", value: `${drop("First active day → second").drop_off_pct}%`,
      note: "of users were active on only one day in their first month" },
    { area: "Tasks", title: "Task attempts fail or are abandoned", value: `${(to.abandonment_rate_resolved_pct + to.failure_rate_resolved_pct).toFixed(1)}%`,
      note: "of finished task attempts did not succeed" },
    { area: "Ads", title: "Ads are often skipped", value: `${ft["Watch Ads"].event_abandonment_rate_pct}%`,
      note: "of ad attempts were skipped" },
    { area: "Missions", title: "Missions are often abandoned", value: `${ft["Missions"].event_abandonment_rate_pct}%`,
      note: "of mission attempts were abandoned" },
    { area: "Rewards", title: "Rewards wait long in validation", value: pendingOld ? `${pendingOld.entities_flagged}` : "—",
      note: `tasks still pending after 30+ days (of ${to.pending} pending)` },
  ];
  const exps = Object.fromEntries((agg.insights.experiments as R[]).map((e) => [String(e.experiment_id), e]));
  const recs = (agg.insights.recommendations as R[]).map((r) => {
    const id = String(r.how_to_test).split(":")[0];
    const e = exps[id];
    return {
      action: String(r.finding),
      priority: String(r.priority),
      why: String(r.user_impact),
      test: e ? `A/B test: ${e.control} vs ${e.variant}` : String(r.how_to_test),
      success: e ? `${e.primary_metric}: from ${e.baseline_value_pct}% to ${e.target_value_pct}% or more` : String(r.how_to_measure),
    };
  });

  return (
    <div className="space-y-4">
      <Panel title="Where users drop off" static sub="Share of users (or attempts) lost at each step">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={drops} layout="vertical" margin={{ top: 0, right: 48, left: 8, bottom: 0 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" unit="%" domain={[0, 100]} />
            <YAxis type="category" dataKey="label" width={250} tickLine={false} tick={{ fontSize: 11 }} />
            <Tooltip content={<ChartTip unit="%" />} />
            <Bar dataKey="pct" name="Lost at this step" fill={C.c2} radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
              <LabelList dataKey="pct" position="right" formatter={(v: number) => `${v}%`} className="fill-[rgb(var(--ink2))] text-[11px]" />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-1 text-[11px] text-ink2">Day-by-day steps are measured over each user's first 30 days, for users with enough history.</p>
      </Panel>

      <Panel title="Biggest problems found" static sub="The main points where users or attempts are lost">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {problems.map((p) => (
            <div key={p.title} className="rounded-lg border border-rule p-3">
              <div className="text-[11px] uppercase tracking-wide text-ink2">{p.area}</div>
              <p className="mt-1 text-sm font-medium text-ink">{p.title}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-ink">{p.value}</p>
              <p className="text-[11px] text-ink2">{p.note}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Recommended actions" static sub="What to do next, how to test it, and what success looks like"
        info="Each action should be confirmed with its A/B test before a full roll-out. Targets are based on the current (simulated) baseline.">
        <ol className="space-y-3">
          {recs.map((r, i) => (
            <li key={r.action} className="rounded-lg border border-rule p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-ink2">{i + 1}.</span>
                <span className="text-sm font-semibold text-ink">{r.action}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_STYLE[r.priority] ?? ""}`}>{r.priority} priority</span>
              </div>
              <dl className="mt-2 grid gap-2 text-xs md:grid-cols-3">
                <div><dt className="font-medium text-ink2">Why</dt><dd className="text-ink">{r.why}</dd></div>
                <div><dt className="font-medium text-ink2">How to test</dt><dd className="text-ink">{r.test}</dd></div>
                <div><dt className="font-medium text-ink2">Success looks like</dt><dd className="text-ink">{r.success}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      </Panel>

      <p className="text-xs text-ink2">
        All numbers were recalculated from the raw data and independently checked. The full data-quality review, unusual-activity
        checks, calculation methods and source code are in the report and the project repository.
      </p>
    </div>
  );
}
