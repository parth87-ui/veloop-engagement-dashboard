// Pure functions that recompute dashboard metrics for the current filter selection.
// With no filters applied they reproduce the pipeline's values exactly (see metrics.test.ts).
import type { Filterable, User } from "./data";

export interface Filters {
  sources: number[]; // empty = all
  devices: number[];
  segments: number[];
  feature: number | null; // restrict to users who used this feature
  dayFrom: number; // activity window, days since observation start (inclusive)
  dayTo: number;
}

export const pct = (num: number, den: number, digits = 1): number | null =>
  den ? Math.round((num / den) * 100 * 10 ** digits) / 10 ** digits : null;

export function defaultFilters(f: Filterable): Filters {
  const last = Math.max(...f.userday.map((r) => r[1]), ...f.sessions.map((r) => r[1]));
  return { sources: [], devices: [], segments: [], feature: null, dayFrom: 0, dayTo: last };
}

export function isFullWindow(flt: Filters, f: Filterable): boolean {
  const d = defaultFilters(f);
  return flt.dayFrom <= d.dayFrom && flt.dayTo >= d.dayTo;
}

export function userMask(users: User[], flt: Filters): boolean[] {
  return users.map(
    (u) =>
      (flt.sources.length === 0 || flt.sources.includes(u.source)) &&
      (flt.devices.length === 0 || flt.devices.includes(u.device)) &&
      (flt.segments.length === 0 || flt.segments.includes(u.segment)) &&
      (flt.feature === null || u.featureEvents[flt.feature] > 0),
  );
}

export interface ExecKpis {
  totalUsers: number;
  activeUsers: number;
  sessions: number;
  activeDays: number;
  avgSessionsPerUser: number | null;
  repeatUserRatePct: number | null;
  multiFeatureRatePct: number | null;
  activationRatePct: number | null;
  activationEligible: number;
}

export function execKpis(users: User[], f: Filterable, flt: Filters): ExecKpis {
  const mask = userMask(users, flt);
  const inWin = (d: number) => d >= flt.dayFrom && d <= flt.dayTo;
  const activeDaysByUser = new Map<number, number>();
  let activeDays = 0;
  for (const [u, day] of f.userday) {
    if (mask[u] && inWin(day)) {
      activeDays += 1;
      activeDaysByUser.set(u, (activeDaysByUser.get(u) ?? 0) + 1);
    }
  }
  let sessions = 0;
  for (const [u, day] of f.sessions) if (mask[u] && inWin(day)) sessions += 1;
  const sel = users.filter((_, i) => mask[i]);
  const activeUsers = activeDaysByUser.size;
  const repeat = [...activeDaysByUser.values()].filter((n) => n >= 2).length;
  const elig = sel.filter((u) => u.activated !== null);
  return {
    totalUsers: sel.length,
    activeUsers,
    sessions,
    activeDays,
    avgSessionsPerUser: sel.length ? Math.round((sessions / sel.length) * 1000) / 1000 : null,
    repeatUserRatePct: pct(repeat, activeUsers),
    // same denominator as every other user-behaviour rate: active users (lifetime, matching filters)
    multiFeatureRatePct: pct(sel.filter((u) => u.isMulti).length, sel.filter((u) => u.isActive).length),
    activationRatePct: pct(elig.filter((u) => u.activated === 1).length, elig.length),
    activationEligible: elig.length,
  };
}

export interface Point {
  day: number;
  date: string;
  dau: number;
  sessions: number;
  events: number;
  avg7: number | null;
}

export function dailySeries(f: Filterable, mask: boolean[], flt: Filters): Point[] {
  const start = new Date(f.start_date + "T00:00:00Z");
  const days = flt.dayTo - flt.dayFrom + 1;
  const dau = new Array(days).fill(0);
  const ev = new Array(days).fill(0);
  const ss = new Array(days).fill(0);
  for (const [u, day, events] of f.userday) {
    if (mask[u] && day >= flt.dayFrom && day <= flt.dayTo) {
      dau[day - flt.dayFrom] += 1;
      ev[day - flt.dayFrom] += events;
    }
  }
  for (const [u, day] of f.sessions) if (mask[u] && day >= flt.dayFrom && day <= flt.dayTo) ss[day - flt.dayFrom] += 1;
  return dau.map((v, i) => {
    const lo = Math.max(0, i - 6);
    const win = dau.slice(lo, i + 1);
    const d = new Date(start.getTime() + (flt.dayFrom + i) * 86400000);
    return {
      day: flt.dayFrom + i,
      date: d.toISOString().slice(0, 10),
      dau: v,
      sessions: ss[i],
      events: ev[i],
      avg7: Math.round((win.reduce((a, b) => a + b, 0) / win.length) * 100) / 100,
    };
  });
}

export interface FunnelStage {
  stage: string;
  users: number;
  pctOfFirst: number | null;
  pctOfPrev: number | null;
  definition: string;
}

export function activationFunnel(users: User[], mask: boolean[]): FunnelStage[] {
  const sel = users.filter((_, i) => mask[i]);
  const steps: [string, string, (u: User) => boolean][] = [
    // identical stage names and rules to analysis/utils/funnel.py (canonical stages)
    ["Registered", "User record exists", () => true],
    ["Logged in", "≥1 session (login proxy)", (u) => u.hasSession === 1],
    ["Used a feature", "≥1 feature event", (u) => u.isActive === 1],
    ["Started an activity", "≥1 start event or task start", (u) => u.started === 1],
    ["Completed a meaningful activity", "≥1 meaningful completion", (u) => u.completedAny === 1],
    ["Returned (2nd active day)", "Active on at least 2 distinct days", (u) => u.activeDays >= 2],
    ["Established (≥3 meaningful days)", "Meaningful activity on ≥3 distinct days", (u) => u.meaningfulDays >= 3],
  ];
  let pool = sel;
  const out: FunnelStage[] = [];
  steps.forEach(([stage, definition, fn], k) => {
    pool = pool.filter(fn);
    out.push({
      stage,
      definition,
      users: pool.length,
      pctOfFirst: pct(pool.length, sel.length),
      pctOfPrev: k === 0 ? 100 : pct(pool.length, out[k - 1].users),
    });
  });
  return out;
}

export function returnRates(users: User[], mask: boolean[]) {
  const sel = users.filter((_, i) => mask[i]);
  return (["d1", "d7", "d14", "d30"] as const).map((k) => {
    const el = sel.filter((u) => u[k] !== null);
    const ret = el.filter((u) => u[k] === 1).length;
    return { window: k.toUpperCase(), eligible: el.length, returned: ret, ratePct: pct(ret, el.length) };
  });
}

export function histogram(values: number[], edges: number[]) {
  const counts = new Array(edges.length - 1).fill(0);
  for (const v of values) {
    for (let i = 0; i < edges.length - 1; i++) {
      const last = i === edges.length - 2;
      if (v >= edges[i] && (v < edges[i + 1] || (last && v <= edges[i + 1]))) {
        counts[i] += 1;
        break;
      }
    }
  }
  return counts;
}

export function featureAdoption(users: User[], mask: boolean[], features: string[]) {
  const sel = users.filter((_, i) => mask[i] && users[i].isActive === 1);
  return features.map((name, k) => ({
    feature: name,
    exposedPct: pct(sel.filter((u) => u.featureEvents[k] > 0).length, sel.length),
    completedPct: pct(sel.filter((u) => u.featureCompletions[k] > 0).length, sel.length),
    users: sel.filter((u) => u.featureEvents[k] > 0).length,
  }));
}
