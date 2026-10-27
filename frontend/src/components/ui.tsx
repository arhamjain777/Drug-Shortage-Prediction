import { ReactNode, useEffect, useRef, useState } from "react";
import { animate } from "motion/react";

export const Skeleton = ({ h = 20, w = "100%" }: { h?: number; w?: string }) => <div className="skeleton" style={{ height: h, width: w }} />;

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="card border-crit/40 text-sm">
      <p className="font-medium text-crit">Something went wrong</p>
      <p className="text-muted mt-1">{(error as Error)?.message ?? "Unknown error"}</p>
      {retry && <button className="btn mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="card text-center py-10"><p className="font-medium">{title}</p>{hint && <p className="text-sm text-muted mt-1">{hint}</p>}</div>
);

const TONES: Record<string, string> = {
  ok: "bg-ok/10 text-ok", warn: "bg-warn/10 text-warn", crit: "bg-crit/10 text-crit", neutral: "bg-line text-muted", teal: "bg-teal/10 text-teal",
};
export const Badge = ({ tone = "neutral", children }: { tone?: string; children: ReactNode }) => (
  <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>
);

export const STATUS: Record<string, { label: string; tone: string }> = {
  adequate: { label: "Adequate", tone: "ok" }, below_reorder: { label: "Below reorder point", tone: "warn" },
  coverage_shorter_than_lead: { label: "Coverage < lead time", tone: "crit" }, stocked_out: { label: "Stocked out", tone: "crit" },
  no_demand_data: { label: "No demand data", tone: "neutral" },
};
export const StatusBadge = ({ s }: { s: string }) => <Badge tone={STATUS[s]?.tone}>{STATUS[s]?.label ?? s}</Badge>;

/** The three concepts must never be confused: always label the data type. */
export const Kind = ({ k }: { k: "reported" | "forecast" | "predicted" | "hypothetical" | "demo" }) => {
  const m = {
    reported: ["Reported shortage (FDA)", "teal"], forecast: ["Local stock-out estimate", "warn"],
    predicted: ["Model risk score (experimental)", "neutral"], hypothetical: ["Hypothetical scenario", "neutral"], demo: ["DEMO / simulated", "warn"],
  }[k];
  return <Badge tone={m[1]}>{m[0]}</Badge>;
};

export function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  return (
    <div className="flex items-center justify-between mt-3 text-sm">
      <span className="text-muted">Page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <button className="btn" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

/* ---------- visual primitives: pharmacy logo, live dot, count-up, sparkline, health ring, ECG ---------- */

export const LiveDot = () => <span className="live-dot" aria-hidden="true" />;

/** Capsule + cross mark: the pharmacy motif. */
export const Logo = ({ size = 36 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" style={{ filter: "drop-shadow(0 6px 14px rgb(var(--teal) / .55))" }}>
    <defs><linearGradient id="lg1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="rgb(45,212,191)" /><stop offset="1" stopColor="rgb(56,189,248)" /></linearGradient></defs>
    <rect x="3" y="3" width="42" height="42" rx="13" fill="rgb(8,14,26)" stroke="url(#lg1)" strokeWidth="1.5" />
    <g transform="rotate(-40 24 24)"><rect x="11" y="17" width="26" height="14" rx="7" fill="rgb(255 255 255 / .12)" stroke="url(#lg1)" strokeWidth="1.6" />
      <path d="M24 17h6a7 7 0 0 1 0 14h-6z" fill="url(#lg1)" /></g>
    <path d="M36 9v6M33 12h6" stroke="rgb(45,212,191)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/** Number that eases to its value (real values only; honours reduced motion). */
export function CountUp({ value, dp = 0 }: { value: number; dp?: number }) {
  const [v, setV] = useState(value);
  const prev = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(value); return; }
    const c = animate(prev.current, value, { duration: 0.9, ease: [0.2, 0.8, 0.2, 1], onUpdate: (x) => setV(x) });
    prev.current = value;
    return () => c.stop();
  }, [value]);
  return <>{v.toLocaleString(undefined, { maximumFractionDigits: dp, minimumFractionDigits: dp })}</>;
}

export function Spark({ data, color = "var(--teal)" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;                       // no fake trend lines
  const w = 110, h = 34, max = Math.max(...data), min = Math.min(...data), span = max - min || 1;
  const pts = data.map((d, i) => [(i / (data.length - 1)) * w, h - 4 - ((d - min) / span) * (h - 8)]);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <defs><linearGradient id="sp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={`rgb(${color} / .35)`} /><stop offset="1" stopColor={`rgb(${color} / 0)`} /></linearGradient></defs>
      <path d={`${path} L${w} ${h} L0 ${h} Z`} fill="url(#sp)" /><path d={path} fill="none" stroke={`rgb(${color})`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HealthRing({ pct, label, sub }: { pct: number; label: string; sub: string }) {
  const r = 52, c = 2 * Math.PI * r, tone = pct >= 75 ? "var(--ok)" : pct >= 40 ? "var(--warn)" : "var(--crit)";
  return (
    <div className="relative grid place-items-center" role="img" aria-label={`${label}: ${Math.round(pct)}%`}>
      <svg width="150" height="150" viewBox="0 0 130 130" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="65" cy="65" r={r} fill="none" stroke="rgb(var(--edge) / .14)" strokeWidth="10" />
        <circle className="ring" cx="65" cy="65" r={r} fill="none" stroke={`rgb(${tone})`} strokeWidth="10" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} style={{ filter: `drop-shadow(0 0 8px rgb(${tone} / .7))` }} />
      </svg>
      <div className="absolute text-center"><p className="text-3xl font-semibold"><CountUp value={pct} />%</p><p className="text-[11px] uppercase tracking-wider text-muted">{sub}</p></div>
    </div>
  );
}

export const Ecg = () => (
  <svg viewBox="0 0 260 40" className="w-full h-10" aria-hidden="true">
    <path className="ecg" d="M0 22h70l8-14 10 28 9-34 8 20h12l8-6h137" fill="none" stroke="rgb(var(--teal))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ filter: "drop-shadow(0 0 6px rgb(var(--teal) / .9))" }} />
  </svg>
);
