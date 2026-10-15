// Verifies that the dashboard's client-side calculations reproduce the Python pipeline outputs.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { decodeUsers, type Filterable, type Meta } from "./data";
import { activationFunnel, defaultFilters, execKpis, histogram, pct, returnRates, userMask } from "./metrics";

const dir = resolve(__dirname, "../../public/data");
const f = JSON.parse(readFileSync(resolve(dir, "filterable.json"), "utf8")) as Filterable;
const meta = JSON.parse(readFileSync(resolve(dir, "meta.json"), "utf8")) as Meta;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const agg = JSON.parse(readFileSync(resolve(dir, "aggregates.json"), "utf8")) as any;
const users = decodeUsers(f);

describe("unfiltered dashboard KPIs match the analysis outputs", () => {
  const k = execKpis(users, f, defaultFilters(f));
  const m = meta.executive_kpis;
  it("counts", () => {
    expect(k.totalUsers).toBe(m.total_users);
    expect(k.activeUsers).toBe(m.active_users);
    expect(k.sessions).toBe(m.sessions);
    expect(k.activeDays).toBe(m.active_user_days);
  });
  it("rates", () => {
    expect(k.avgSessionsPerUser).toBeCloseTo(m.avg_sessions_per_user, 3);
    expect(k.repeatUserRatePct).toBe(m.repeat_user_rate_pct);
    expect(k.multiFeatureRatePct).toBe(m.multi_feature_user_rate_pct);
    expect(k.activationRatePct).toBe(m.activation_rate_pct);
  });
  it("activation funnel equals pipeline funnel", () => {
    const fn = activationFunnel(users, userMask(users, defaultFilters(f)));
    const py = agg.activation.funnel as { users: number }[];
    expect(fn.map((s) => s.users)).toEqual(py.map((s) => s.users));
  });
  it("return rates equal pipeline return rates", () => {
    const rr = returnRates(users, userMask(users, defaultFilters(f)));
    const ov = agg.retention.overall;
    expect(rr.map((r) => r.ratePct)).toEqual([ov.D1_rate_pct, ov.D7_rate_pct, ov.D14_rate_pct, ov.D30_rate_pct]);
  });
});

describe("filters behave sensibly", () => {
  it("source filters partition the population", () => {
    const total = f.sources.reduce((acc, _, i) => {
      const flt = { ...defaultFilters(f), sources: [i] };
      return acc + execKpis(users, f, flt).totalUsers;
    }, 0);
    expect(total).toBe(users.length);
  });
  it("an impossible filter returns zeros, not NaN", () => {
    const flt = { ...defaultFilters(f), dayFrom: 10_000, dayTo: 10_001 };
    const k = execKpis(users, f, flt);
    expect(k.sessions).toBe(0);
    expect(k.activeUsers).toBe(0);
    expect(k.repeatUserRatePct).toBeNull();
  });
});

describe("helpers", () => {
  it("pct handles zero denominators", () => expect(pct(1, 0)).toBeNull());
  it("histogram includes the right edge in the last bin", () => expect(histogram([0, 5, 10], [0, 5, 10])).toEqual([1, 2]));
});
