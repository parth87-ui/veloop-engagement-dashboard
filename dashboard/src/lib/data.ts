// Data contracts for the JSON files produced by analysis/pipeline/s21_export.py.
// All data is simulated, aggregate or identifier-free (users are array positions only).

export type Row = Record<string, string | number | boolean | null>;

export interface Filterable {
  start_date: string;
  end_date: string;
  sources: string[];
  devices: string[];
  segments: string[];
  features: string[];
  user_fields: string[];
  users: (number | null | number[])[][];
  userday_fields: string[];
  userday: number[][];
  session_fields: string[];
  sessions: number[][];
}

export interface Meta {
  generated_at_utc: string;
  observation_start: string;
  observation_end: string;
  disclaimer: string;
  executive_kpis: {
    total_users: number;
    active_users: number;
    sessions: number;
    active_user_days: number;
    avg_sessions_per_user: number;
    repeat_user_rate_pct: number;
    multi_feature_user_rate_pct: number;
    activation_rate_pct: number;
    activation_window_days: number;
  };
  record_counts: Record<string, number>;
}

// The aggregates file is large and heterogeneous; views read the parts they need.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Aggregates = Record<string, any>;

export interface User {
  source: number;
  device: number;
  segment: number;
  regDay: number;
  firstActiveDay: number | null;
  activeDays: number;
  sessions: number;
  validSessions: number;
  events: number;
  features: number;
  featuresCompleted: number;
  meaningful: number;
  tasksResolved: number;
  tasksCompleted: number;
  score: number;
  activated: number | null;
  d1: number | null;
  d7: number | null;
  d14: number | null;
  d30: number | null;
  hasSession: number;
  isActive: number;
  isMulti: number;
  isRegular: number;
  meaningfulDays: number;
  hoursToFirstActivity: number | null;
  featureEvents: number[];
  featureCompletions: number[];
  started: number;
  exposed: number;
  completedAny: number;
}

export interface Dataset {
  meta: Meta;
  agg: Aggregates;
  f: Filterable;
  users: User[];
}

export function decodeUsers(f: Filterable): User[] {
  const i = (name: string) => {
    const k = f.user_fields.indexOf(name);
    if (k < 0) throw new Error(`Missing user field ${name}`);
    return k;
  };
  const ix = {
    source: i("source"), device: i("device"), segment: i("segment"), reg: i("reg_day"), fa: i("first_active_day"),
    ad: i("active_days"), s: i("sessions"), vs: i("valid_sessions"), ev: i("events"), ft: i("features"),
    fc: i("features_completed"), m: i("meaningful"), tr: i("tasks_resolved"), tc: i("tasks_completed"), sc: i("score"),
    act: i("activated"), d1: i("d1"), d7: i("d7"), d14: i("d14"), d30: i("d30"), hs: i("has_session"), ia: i("is_active"),
    im: i("is_multi"), ir: i("is_regular"), md: i("meaningful_days"), h: i("hours_to_first_activity"),
    fe: i("feature_events"), fcs: i("feature_completions"), st: i("started"), ex: i("exposed"), ca: i("completed_any"),
  };
  return f.users.map((r) => ({
    source: r[ix.source] as number, device: r[ix.device] as number, segment: r[ix.segment] as number,
    regDay: r[ix.reg] as number, firstActiveDay: r[ix.fa] as number | null, activeDays: r[ix.ad] as number,
    sessions: r[ix.s] as number, validSessions: r[ix.vs] as number, events: r[ix.ev] as number,
    features: r[ix.ft] as number, featuresCompleted: r[ix.fc] as number, meaningful: r[ix.m] as number,
    tasksResolved: r[ix.tr] as number, tasksCompleted: r[ix.tc] as number, score: r[ix.sc] as number,
    activated: r[ix.act] as number | null, d1: r[ix.d1] as number | null, d7: r[ix.d7] as number | null,
    d14: r[ix.d14] as number | null, d30: r[ix.d30] as number | null, hasSession: r[ix.hs] as number,
    isActive: r[ix.ia] as number, isMulti: r[ix.im] as number, isRegular: r[ix.ir] as number,
    meaningfulDays: r[ix.md] as number, hoursToFirstActivity: r[ix.h] as number | null,
    featureEvents: r[ix.fe] as number[], featureCompletions: r[ix.fcs] as number[], started: r[ix.st] as number,
    exposed: r[ix.ex] as number, completedAny: r[ix.ca] as number,
  }));
}

export async function loadDataset(base = "/data"): Promise<Dataset> {
  const get = async <T,>(name: string): Promise<T> => {
    const res = await fetch(`${base}/${name}.json`);
    if (!res.ok) throw new Error(`Could not load ${name}.json (${res.status})`);
    return (await res.json()) as T;
  };
  const [meta, agg, f] = await Promise.all([get<Meta>("meta"), get<Aggregates>("aggregates"), get<Filterable>("filterable")]);
  return { meta, agg, f, users: decodeUsers(f) };
}
