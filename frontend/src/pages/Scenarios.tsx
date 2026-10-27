import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { api, fmtDate, num } from "../api";
import { Empty, ErrorBox, Kind, Skeleton, StatusBadge } from "../components/ui";

const rows = (b: any, s: any): [string, string, string][] => [
  ["Days of supply (with confirmed orders)", num(b.days_of_supply_with_incoming), num(s.days_of_supply_with_incoming)],
  ["Estimated stock-out date", fmtDate(b.estimated_stockout_date), fmtDate(s.estimated_stockout_date)],
  ["Reorder point", num(b.reorder_point), num(s.reorder_point)],
  ["Potential gap during lead time", num(b.lead_time_gap_quantity), num(s.lead_time_gap_quantity)],
  ["Buffer after lead time (days)", num(b.buffer_days_after_lead_time), num(s.buffer_days_after_lead_time)],
];

export default function Scenarios() {
  const { role } = useOutletContext<{ role?: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["scenarios"], queryFn: () => api("/scenarios") });
  const refresh = () => qc.invalidateQueries({ queryKey: ["scenarios"] });
  const dup = useMutation({ mutationFn: (id: number) => api(`/scenarios/${id}/duplicate`, { method: "POST" }), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/scenarios/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const ren = useMutation({ mutationFn: (v: { id: number; name: string }) => api(`/scenarios/${v.id}`, { method: "PATCH", body: { name: v.name } }), onSuccess: refresh });
  const w = ["admin", "inventory_manager", "analyst"].includes(role ?? "");

  return (
    <div className="space-y-4">
      <div><h1 className="text-xl font-semibold">Scenario laboratory</h1><p className="text-sm text-muted"><Kind k="hypothetical" /> What-if results. They never change real inventory. Create one from an item's detail panel on the Inventory page.</p></div>
      {q.isLoading ? <Skeleton h={200} /> : q.error ? <ErrorBox error={q.error} retry={() => q.refetch()} /> :
        q.data.length === 0 ? <Empty title="No saved scenarios" hint="Open an inventory item and use “Save what-if scenario”." /> :
          q.data.map((s: any) => (
            <section key={s.id} className="card space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-medium">{s.name} <Kind k="hypothetical" /></h2>
                {w && <div className="flex gap-2">
                  <button className="btn" onClick={() => { const n = prompt("New name", s.name); if (n) ren.mutate({ id: s.id, name: n }); }}>Rename</button>
                  <button className="btn" onClick={() => dup.mutate(s.id)}>Duplicate</button>
                  <button className="btn" onClick={() => confirm(`Delete scenario “${s.name}”?`) && del.mutate(s.id)}>Delete</button></div>}</div>
              <p className="text-xs text-muted">Saved {new Date(s.created_at).toLocaleString()} · assumptions: {Object.entries(s.assumptions).filter(([, v]) => v !== 0 && v !== null && v !== false).map(([k, v]) => `${k}=${v}`).join(", ") || "none changed"}</p>
              <table className="w-full"><thead><tr><th className="th">Measure</th><th className="th">Baseline (actual records)</th><th className="th">Scenario (hypothetical)</th></tr></thead>
                <tbody>{rows(s.result.baseline, s.result.scenario).map(([k, b, sc]) => <tr key={k}><td className="td">{k}</td><td className="td">{b}</td><td className="td font-medium">{sc}</td></tr>)}
                  <tr><td className="td">Status</td><td className="td"><StatusBadge s={s.result.baseline.status} /></td><td className="td"><StatusBadge s={s.result.scenario.status} /></td></tr></tbody></table>
              <p className="text-xs text-muted">Saved result reflects inventory at the time of saving.</p>
            </section>))}
    </div>
  );
}
