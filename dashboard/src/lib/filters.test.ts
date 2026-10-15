// For every single-value filter (each source, device, segment, feature) and two date windows, the dashboard's
// client-side calculations must equal values computed independently with pandas (expected_filters.json).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { decodeUsers, type Filterable } from "./data";
import { activationFunnel, defaultFilters, execKpis, returnRates, userMask, type Filters } from "./metrics";

const f = JSON.parse(readFileSync(resolve(__dirname, "../../public/data/filterable.json"), "utf8")) as Filterable;
const fixture = JSON.parse(readFileSync(resolve(__dirname, "expected_filters.json"), "utf8")) as {
  cases: { name: string; filter: Partial<Filters>; expected: Record<string, number | null | number[]> }[];
};
const users = decodeUsers(f);

describe("dashboard filters reproduce pandas results", () => {
  it("covers every filter dimension", () => {
    expect(fixture.cases.length).toBe(f.sources.length + f.devices.length + f.segments.length + f.features.length + 2);
  });
  for (const c of fixture.cases) {
    it(c.name, () => {
      const flt: Filters = { ...defaultFilters(f), ...c.filter };
      const k = execKpis(users, f, flt);
      const mask = userMask(users, flt);
      const e = c.expected;
      expect(k.totalUsers).toBe(e.totalUsers);
      expect(k.activeUsers).toBe(e.activeUsers);
      expect(k.activeDays).toBe(e.activeDays);
      expect(k.sessions).toBe(e.sessions);
      expect(k.repeatUserRatePct).toBe(e.repeatUserRatePct);
      expect(k.multiFeatureRatePct).toBe(e.multiFeatureRatePct);
      expect(k.activationRatePct).toBe(e.activationRatePct);
      expect(returnRates(users, mask)[1].ratePct).toBe(e.d7RatePct);
      expect(activationFunnel(users, mask).map((s) => s.users)).toEqual(e.funnel);
    });
  }
});
