import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, CheckCircle2, Database, PackageX, RefreshCw, TrendingUp } from "lucide-react";
import { api } from "../api";
import { CountUp, Ecg, Empty, ErrorBox, HealthRing, Kind, LiveDot, Skeleton, Spark } from "../components/ui";

const tip = { background: "rgb(var(--surface) / .9)", border: "1px solid rgb(var(--edge) / .2)", borderRadius: 14, backdropFilter: "blur(12px)", color: "rgb(var(--ink))" };

function Kpi({ label, value, to, kind, spark, tone = "var(--teal)" }: { label: string; value: number; to: string; kind: any; spark?: number[]; tone?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}>
      <Link to={to} className="card block h-full">
        <p className="text-xs uppercase tracking-wider text-muted">{label}</p>
        <div className="flex items-end justify-between mt-2 mb-3"><p className="text-4xl font-semibold tabular-nums"><CountUp value={value} /></p>{spark && <Spark data={spark} color={tone} />}</div>
        <Kind k={kind} />
      </Link>
    </motion.div>
  );
}

type Insight = { tone: "crit" | "warn" | "ok" | "info"; icon: ReactNode; text: string; to?: string };

/** Insights are derived ONLY from the API summary. Nothing is invented. */
function buildInsights(d: any): Insight[] {
  const out: Insight[] = [], inv = d.inventory, rs = d.reported_shortages, fr = d.data_freshness;
  if (fr.last_run_status === "failed") out.push({ tone: "crit", icon: <Database size={16} />, text: `Last FDA refresh failed (${fr.last_run_error}). Stored data was kept.`, to: "/admin" });
  if (inv.stocked_out > 0) out.push({ tone: "crit", icon: <PackageX size={16} />, text: `${inv.stocked_out} item(s) have no usable stock.`, to: "/inventory?status=stocked_out" });
  if (inv.coverage_shorter_than_lead_time > 0) out.push({ tone: "crit", icon: <AlertTriangle size={16} />, text: `${inv.coverage_shorter_than_lead_time} item(s) will run out before a resupply could arrive.`, to: "/inventory?status=coverage_shorter_than_lead" });
  if (inv.below_reorder > 0) out.push({ tone: "warn", icon: <AlertTriangle size={16} />, text: `${inv.below_reorder} item(s) are below their reorder point.`, to: "/inventory?status=below_reorder" });
  if (inv.no_demand_data > 0) out.push({ tone: "info", icon: <TrendingUp size={16} />, text: `${inv.no_demand_data} item(s) have no daily-consumption figure, so no forecast is possible.`, to: "/inventory?status=no_demand_data" });
  if (rs.updated_last_30_days > 0) out.push({ tone: "info", icon: <RefreshCw size={16} />, text: `${rs.updated_last_30_days.toLocaleString()} FDA shortage record(s) were updated in the last 30 days.`, to: "/drugs?sort=update_date" });
  if (inv.items > 0 && out.every((o) => o.tone === "info")) out.unshift({ tone: "ok", icon: <CheckCircle2 size={16} />, text: "No inventory item is currently flagged." });
  return out;
}
const TONE = { crit: "var(--crit)", warn: "var(--warn)", ok: "var(--ok)", info: "var(--cyan)" };

export default function Dashboard() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api("/dashboard/summary"), refetchInterval: 30_000 });   // live refresh
  if (q.isLoading) return <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <div key={i} className="card"><Skeleton h={96} /></div>)}</div>;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data, rs = d.reported_shortages, inv = d.inventory, fr = d.data_freshness;
  const years: number[] = rs.postings_by_year.map((y: any) => y.count);
  const adequate = inv.status_counts.adequate ?? 0;
  const insights = buildInsights(d);

  return (
    <div className="space-y-5">
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card relative overflow-hidden !p-7 rx-pattern">
        <div className="relative z-10 grid md:grid-cols-[1fr_320px] gap-6 items-center">
          <div>
            <p className="flex items-center gap-2 text-xs uppercase tracking-[.18em] text-muted"><LiveDot /> Live · refreshed {new Date(q.dataUpdatedAt).toLocaleTimeString()}</p>
            <h1 className="text-3xl md:text-4xl font-semibold mt-2 grad-text">Supply intelligence, at a glance</h1>
            <p className="text-sm text-muted mt-2 max-w-xl">Reported FDA shortages, your own stock-out estimates and the experimental risk model are shown side by side, but never blended into one number.</p>
            <p className="text-xs text-muted mt-3">Last successful FDA refresh: {fr.last_successful_refresh ? new Date(fr.last_successful_refresh).toLocaleString() : "never"}</p>
          </div>
          <Ecg />
        </div>
      </motion.section>

      {rs.total_records === 0 && <Empty title="No FDA shortage records yet" hint="An admin or analyst can run a refresh under Data & model." />}

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Current reported shortages" value={rs.current} to="/drugs?status=Current" kind="reported" spark={years} tone="var(--crit)" />
        <Kpi label="FDA records updated · 30 d" value={rs.updated_last_30_days} to="/drugs?sort=update_date" kind="reported" />
        <Kpi label="Below reorder point" value={inv.below_reorder} to="/inventory?status=below_reorder" kind="forecast" tone="var(--warn)" />
        <Kpi label="Coverage < lead time" value={inv.coverage_shorter_than_lead_time} to="/inventory?status=coverage_shorter_than_lead" kind="forecast" tone="var(--crit)" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <section className="card flex flex-col items-center justify-center gap-3">
          <h2 className="font-medium self-start">Inventory coverage health</h2>
          {inv.items === 0 ? <p className="text-sm text-muted py-8">No inventory recorded yet.</p> : <HealthRing pct={(adequate / inv.items) * 100} label="Items with adequate coverage" sub="adequate" />}
          <p className="text-xs text-muted text-center">{adequate} of {inv.items} item(s) adequate · <Kind k="forecast" />{inv.demo_items > 0 && <> · {inv.demo_items} DEMO</>}</p>
        </section>

        <section className="card lg:col-span-2">
          <h2 className="font-medium mb-3 flex items-center gap-2">Live insights <span className="text-xs text-muted font-normal">· derived from your data</span></h2>
          {insights.length === 0 ? <p className="text-sm text-muted">Nothing to report yet. Add inventory or refresh FDA data.</p> : (
            <ul className="space-y-2"><AnimatePresence initial={false}>{insights.map((i, idx) => (
              <motion.li key={i.text} layout initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ delay: idx * 0.05, duration: 0.3 }}>
                <Link to={i.to ?? "#"} className="flex items-center gap-3 rounded-2xl px-4 py-3 text-sm lift transition-all border border-transparent" style={{ background: `rgb(${TONE[i.tone]} / .1)` }}>
                  <span style={{ color: `rgb(${TONE[i.tone]})` }}>{i.icon}</span><span>{i.text}</span></Link>
              </motion.li>))}</AnimatePresence></ul>)}
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="card"><h2 className="font-medium mb-3">FDA postings by year <Kind k="reported" /></h2>
          {years.length === 0 ? <p className="text-sm text-muted">No data.</p> :
            <div style={{ height: 250 }}><ResponsiveContainer><AreaChart data={rs.postings_by_year}>
              <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="rgb(45,212,191)" stopOpacity=".5" /><stop offset="1" stopColor="rgb(45,212,191)" stopOpacity="0" /></linearGradient></defs>
              <CartesianGrid strokeDasharray="3 6" stroke="rgba(148,163,184,.18)" /><XAxis dataKey="year" tick={{ fill: "#8e9db6", fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: "#8e9db6", fontSize: 12 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={tip} />
              <Area type="monotone" dataKey="count" stroke="rgb(45,212,191)" strokeWidth={2.5} fill="url(#ag)" animationDuration={900} /></AreaChart></ResponsiveContainer></div>}
        </section>
        <section className="card"><h2 className="font-medium mb-3">Usable stock by location <Kind k="forecast" /></h2>
          {inv.exposure_by_location.length === 0 ? <p className="text-sm text-muted">No inventory recorded yet.</p> :
            <div style={{ height: 250 }}><ResponsiveContainer><BarChart data={inv.exposure_by_location}>
              <defs><linearGradient id="bg2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="rgb(56,189,248)" /><stop offset="1" stopColor="rgb(139,112,255)" /></linearGradient></defs>
              <CartesianGrid strokeDasharray="3 6" stroke="rgba(148,163,184,.18)" /><XAxis dataKey="location" tick={{ fill: "#8e9db6", fontSize: 12 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#8e9db6", fontSize: 12 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={tip} cursor={{ fill: "rgba(148,163,184,.08)" }} />
              <Bar dataKey="usable_stock_units" fill="url(#bg2)" radius={[10, 10, 0, 0]} animationDuration={900} /></BarChart></ResponsiveContainer></div>}
        </section>
      </div>
      <p className="text-xs text-muted">{rs.scope_note}. Decision-support prototype; not clinically certified.</p>
    </div>
  );
}
