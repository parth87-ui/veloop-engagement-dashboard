import { useEffect } from "react";
import type { Filterable } from "../lib/data";
import { defaultFilters, type Filters } from "../lib/metrics";

function MultiSelect({ label, options, value, onChange }: {
  label: string; options: string[]; value: number[]; onChange: (v: number[]) => void;
}) {
  const summary = value.length === 0 ? "All" : value.length === 1 ? options[value[0]] : `${value.length} selected`;
  return (
    <details className="relative">
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-1 rounded-md border border-rule bg-panel px-2.5 py-1.5 text-xs text-ink">
        <span className="text-ink2">{label}:</span> <span className="font-medium">{summary}</span>
        <span aria-hidden className="ml-1 text-ink2">▾</span>
      </summary>
      <fieldset className="absolute z-40 mt-1 w-56 rounded-md border border-rule bg-panel p-2 shadow-lg">
        <legend className="sr-only">{label}</legend>
        {options.map((o, i) => (
          <label key={o} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-xs text-ink hover:bg-surface">
            <input
              type="checkbox"
              checked={value.includes(i)}
              onChange={(ev) => onChange(ev.target.checked ? [...value, i] : value.filter((x) => x !== i))}
            />
            {o}
          </label>
        ))}
        <button type="button" className="focus-ring mt-1 w-full rounded px-1 py-1 text-left text-[11px] text-brand" onClick={() => onChange([])}>
          Clear (all)
        </button>
      </fieldset>
    </details>
  );
}

const dayToDate = (f: Filterable, d: number) => new Date(Date.parse(f.start_date + "T00:00:00Z") + d * 86400000).toISOString().slice(0, 10);
const dateToDay = (f: Filterable, s: string) => Math.round((Date.parse(s + "T00:00:00Z") - Date.parse(f.start_date + "T00:00:00Z")) / 86400000);

export function FilterBar({ f, flt, setFlt, matched }: { f: Filterable; flt: Filters; setFlt: (x: Filters) => void; matched: number }) {
  const def = defaultFilters(f);
  useEffect(() => {
    const close = (ev: Event) => {
      document.querySelectorAll<HTMLDetailsElement>("details[open]").forEach((d) => {
        if (ev.type === "keydown" ? (ev as KeyboardEvent).key === "Escape" : !d.contains(ev.target as Node)) d.open = false;
      });
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("click", close); document.removeEventListener("keydown", close); };
  }, []);
  const dirty = JSON.stringify(flt) !== JSON.stringify(def);
  return (
    <div role="search" aria-label="Dashboard filters" className="flex flex-wrap items-center gap-2">
      <MultiSelect label="Source" options={f.sources} value={flt.sources} onChange={(v) => setFlt({ ...flt, sources: v })} />
      <MultiSelect label="Device" options={f.devices} value={flt.devices} onChange={(v) => setFlt({ ...flt, devices: v })} />
      <MultiSelect label="Segment" options={f.segments} value={flt.segments} onChange={(v) => setFlt({ ...flt, segments: v })} />
      <label className="flex items-center gap-1 rounded-md border border-rule bg-panel px-2 py-1 text-xs">
        <span className="text-ink2">Feature:</span>
        <select
          className="focus-ring bg-transparent text-ink"
          value={flt.feature ?? ""}
          onChange={(e) => setFlt({ ...flt, feature: e.target.value === "" ? null : Number(e.target.value) })}
        >
          <option value="">All users</option>
          {f.features.map((x, i) => <option key={x} value={i}>Used {x}</option>)}
        </select>
      </label>
      <label className="flex items-center gap-1 rounded-md border border-rule bg-panel px-2 py-1 text-xs">
        <span className="text-ink2">Activity from</span>
        <input type="date" className="focus-ring bg-transparent text-ink" min={dayToDate(f, def.dayFrom)} max={dayToDate(f, flt.dayTo)}
          value={dayToDate(f, flt.dayFrom)} onChange={(e) => e.target.value && setFlt({ ...flt, dayFrom: Math.max(def.dayFrom, dateToDay(f, e.target.value)) })} />
        <span className="text-ink2">to</span>
        <input type="date" className="focus-ring bg-transparent text-ink" min={dayToDate(f, flt.dayFrom)} max={dayToDate(f, def.dayTo)}
          value={dayToDate(f, flt.dayTo)} onChange={(e) => e.target.value && setFlt({ ...flt, dayTo: Math.min(def.dayTo, dateToDay(f, e.target.value)) })} />
      </label>
      {dirty && (
        <button type="button" className="focus-ring rounded-md px-2 py-1 text-xs font-medium text-brand" onClick={() => setFlt(def)}>
          Reset filters
        </button>
      )}
      <span className="ml-auto text-xs text-ink2" aria-live="polite">{matched.toLocaleString()} simulated users match</span>
    </div>
  );
}
