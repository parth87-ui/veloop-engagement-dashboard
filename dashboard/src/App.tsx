import { useEffect, useMemo, useState } from "react";
import { FilterBar } from "./components/FilterBar";
import { loadDataset, type Dataset } from "./lib/data";
import { defaultFilters, userMask, type Filters } from "./lib/metrics";
import { Behavior } from "./views/Behavior";
import { Executive } from "./views/Executive";
import { Features } from "./views/Features";
import { Insights } from "./views/Insights";
import { Retention } from "./views/Retention";

const TABS = [
  { id: "exec", label: "Overview" },
  { id: "behavior", label: "User Behaviour" },
  { id: "features", label: "Features" },
  { id: "retention", label: "Retention" },
  { id: "insights", label: "Insights & Actions" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export interface ViewProps {
  ds: Dataset;
  flt: Filters;
  mask: boolean[];
}

export default function App() {
  const [ds, setDs] = useState<Dataset | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [flt, setFlt] = useState<Filters | null>(null);
  const [tab, setTab] = useState<Tab>(() => {
    const h = window.location.hash.slice(1);
    return (TABS.find((t) => t.id === h)?.id ?? "exec") as Tab;
  });
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  useEffect(() => {
    loadDataset().then((d) => { setDs(d); setFlt(defaultFilters(d.f)); }).catch((e: Error) => setErr(e.message));
  }, []);
  useEffect(() => { window.history.replaceState(null, "", `#${tab}`); }, [tab]);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem("veloop-theme", dark ? "dark" : "light"); } catch { /* storage unavailable */ }
  }, [dark]);

  const mask = useMemo(() => (ds && flt ? userMask(ds.users, flt) : []), [ds, flt]);
  const matched = mask.filter(Boolean).length;

  return (
    <div className="min-h-screen">
      <header className="border-b border-rule bg-panel">
        <div className="mx-auto max-w-7xl px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <h1 className="text-base font-semibold text-ink sm:text-lg">VELOOP Rewards — User Engagement Dashboard</h1>
              <p className="text-xs text-ink2">Prepared by Parth Khandelwal · Data covers {ds ? `${ds.meta.observation_start} to ${ds.meta.observation_end}` : "…"}</p>
            </div>
            <button type="button" onClick={() => setDark((d) => !d)} className="focus-ring ml-auto rounded-md border border-rule px-2.5 py-1 text-xs text-ink"
              aria-pressed={dark}>{dark ? "Light mode" : "Dark mode"}</button>
          </div>
          <nav aria-label="Dashboard views" className="-mb-3 mt-3 flex gap-1 overflow-x-auto" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                className={`focus-ring whitespace-nowrap border-b-2 px-3 py-2 text-xs font-medium sm:text-sm ${tab === t.id ? "border-brand text-ink" : "border-transparent text-ink2 hover:text-ink"}`}>
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <div role="note" className="border-b border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200">
        <p className="mx-auto max-w-7xl px-4 py-2 text-xs sm:text-sm">
          <strong>Simulated data – not actual VELoop Rewards user data.</strong> Every figure here is calculated from a fictional
          dataset provided for the analysis task. It demonstrates the method and findings; it does not describe real users,
          retention or business performance.
        </p>
      </div>
      <main className="mx-auto max-w-7xl px-4 py-4">
        {err && <div role="alert" className="panel text-sm text-ink">The dashboard data could not be loaded. Please refresh the page.</div>}
        {!ds && !err && <div className="panel text-sm text-ink2" aria-busy="true">Loading dashboard…</div>}
        {ds && flt && (
          <>
            <div className="sticky top-0 z-20 -mx-4 mb-4 border-b border-rule bg-surface/95 px-4 py-2 backdrop-blur">
              <FilterBar f={ds.f} flt={flt} setFlt={setFlt} matched={matched} />
            </div>
            {tab === "exec" && <Executive ds={ds} flt={flt} mask={mask} />}
            {tab === "behavior" && <Behavior ds={ds} flt={flt} mask={mask} />}
            {tab === "features" && <Features ds={ds} flt={flt} mask={mask} />}
            {tab === "retention" && <Retention ds={ds} flt={flt} mask={mask} />}
            {tab === "insights" && <Insights ds={ds} flt={flt} mask={mask} />}
          </>
        )}
        <footer className="mt-8 border-t border-rule pt-3 text-[11px] leading-relaxed text-ink2">
          Based on a simulated dataset – not actual VELoop Rewards user data. Panels marked “Overall” show all users and are not
          changed by the filters. No personal information is included. © Parth Khandelwal
        </footer>
      </main>
    </div>
  );
}
