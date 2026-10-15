import { useId, useState, type ReactNode } from "react";

export const C = { c1: "var(--c1)", c2: "var(--c2)", c3: "var(--c3)", c4: "var(--c4)", muted: "var(--c-muted)" };

export const fmt = {
  n: (v: number | null | undefined, d = 0) =>
    v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }),
  pct: (v: number | null | undefined, d = 1) => (v === null || v === undefined ? "—" : `${v.toFixed(d)}%`),
};

export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-block align-middle">
      <button
        type="button"
        aria-label="More information"
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="focus-ring ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-rule text-[10px] text-ink2"
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute left-1/2 top-5 z-30 w-64 -translate-x-1/2 rounded-md border border-rule bg-panel p-2 text-[11px] font-normal leading-snug text-ink shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  );
}

export function Panel({ title, sub, info, children, className = "", right, static: isStatic }: {
  title: string; sub?: string; info?: string; children: ReactNode; className?: string; right?: ReactNode; static?: boolean;
}) {
  return (
    <section className={`panel ${className}`} aria-label={title}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="panel-title">
            {title}
            {info && <InfoTip text={info} />}
          </h3>
          {sub && <p className="panel-sub">{sub}</p>}
        </div>
        <div className="flex items-center gap-2">
          {isStatic && <span className="badge" title="Shows all users; filters do not change this panel">Overall</span>}
          {right}
        </div>
      </header>
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub, info }: { label: string; value: string; sub?: string; info?: string }) {
  return (
    <div className="panel flex flex-col gap-1 p-3">
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink2">
        {label}
        {info && <InfoTip text={info} />}
      </span>
      <span className="text-2xl font-semibold tabular-nums text-ink">{value}</span>
      {sub && <span className="text-[11px] text-ink2">{sub}</span>}
    </div>
  );
}

export function Table({ rows, cols, max = 50, caption }: {
  rows: Record<string, unknown>[]; cols: { key: string; label: string; num?: boolean; w?: string }[]; max?: number; caption?: string;
}) {
  if (!rows?.length) return <Empty />;
  return (
    <div className="max-h-[420px] overflow-auto rounded-md border border-rule">
      <table className="tbl">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>{cols.map((c) => <th key={c.key} scope="col" style={{ width: c.w }} className={c.num ? "text-right" : ""}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const v = r[c.key];
                const s = typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString("en-US") : v.toFixed(2)) : v === null || v === undefined ? "—" : String(v);
                return <td key={c.key} className={c.num ? "text-right tabular-nums" : ""}>{s}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Empty({ msg = "No data for the current filters." }: { msg?: string }) {
  return <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-rule text-xs text-ink2">{msg}</div>;
}

export function ChartTip({ active, payload, label, unit = "", labelFmt }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string | number; unit?: string;
  labelFmt?: (l: string | number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-rule bg-panel px-2.5 py-1.5 text-xs text-ink shadow-md">
      <div className="mb-1 font-semibold">{labelFmt && label !== undefined ? labelFmt(label) : label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color }} />
          <span className="text-ink2">{p.name}</span>
          <span className="ml-auto pl-3 tabular-nums">{typeof p.value === "number" ? p.value.toLocaleString("en-US", { maximumFractionDigits: 2 }) : p.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

export function Heatmap({ rows, cols, values, rowLabel, max, fmtCell = (v) => (v === null ? "" : v.toFixed(0)), unit = "" }: {
  rows: string[]; cols: string[]; values: (number | null)[][]; rowLabel: string; max?: number; fmtCell?: (v: number | null) => string; unit?: string;
}) {
  const m = max ?? Math.max(...values.flat().filter((v): v is number => v !== null), 1);
  return (
    <div className="overflow-auto">
      <table className="border-separate text-[10px]" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th scope="col" className="pr-2 text-left font-medium text-ink2">{rowLabel}</th>
            {cols.map((c) => <th key={c} scope="col" className="px-1 font-medium text-ink2">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r}>
              <th scope="row" className="whitespace-nowrap pr-2 text-left font-normal text-ink2">{r}</th>
              {cols.map((c, j) => {
                const v = values[i][j];
                const t = v === null ? 0 : Math.min(1, v / m);
                return (
                  <td
                    key={c}
                    title={`${r} · ${c}: ${v === null ? "not observable" : v.toFixed(1) + unit}`}
                    className="h-6 min-w-[34px] rounded-sm text-center tabular-nums"
                    style={{
                      background: v === null ? "transparent" : `color-mix(in srgb, var(--seq-1) ${Math.round(t * 100)}%, var(--seq-0))`,
                      color: t > 0.55 ? "white" : "rgb(var(--ink))",
                      border: v === null ? "1px dashed rgb(var(--rule))" : undefined,
                    }}
                  >
                    {fmtCell(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
