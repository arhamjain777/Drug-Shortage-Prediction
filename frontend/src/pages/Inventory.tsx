import { FormEvent, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus } from "lucide-react";
import { api, download, fmtDate, num } from "../api";
import { Badge, Empty, ErrorBox, Kind, Pager, Skeleton, StatusBadge, STATUS } from "../components/ui";

const canWrite = (role?: string) => role === "admin" || role === "inventory_manager";

function ForecastPanel({ f }: { f: any }) {
  const rows: [string, string][] = [
    ["Usable stock", num(f.usable_stock)], ["Expired (excluded)", num(f.expired_stock)], ["Confirmed incoming counted", num(f.confirmed_incoming_counted)],
    ["Days of supply (stock only)", num(f.days_of_supply)], ["Days of supply (with confirmed orders)", num(f.days_of_supply_with_incoming)],
    ["Estimated stock-out date", f.stockout_beyond_horizon ? "beyond 365 days" : fmtDate(f.estimated_stockout_date)],
    ["Reorder point", num(f.reorder_point)], ["Quantity to reach reorder point", num(f.quantity_to_reach_reorder_point)],
    ["Lead-time gap quantity", num(f.lead_time_gap_quantity)], ["Buffer after lead time (days)", num(f.buffer_days_after_lead_time)],
  ];
  return (
    <div className="space-y-2">
      <div className="flex gap-2 items-center"><StatusBadge s={f.status} /><Kind k="forecast" /></div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">{rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>)}</dl>
      {f.warnings.map((w: string, i: number) => <p key={i} className="text-xs text-warn">⚠ {w}</p>)}
      <p className="text-xs text-muted">Estimate assuming constant average daily demand, first-expiry-first-out, and only confirmed orders. Not a prediction of shortage events.</p>
    </div>
  );
}

function Detail({ id, role, onClose }: { id: number; role?: string; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["item", id], queryFn: () => api(`/inventory/${id}`) });
  const [mv, setMv] = useState({ kind: "receipt", quantity: "", reason: "", expiry: "" });
  const [ord, setOrd] = useState({ quantity: "", expected_date: "", confirmed: false });
  const [sc, setSc] = useState({ name: "", demand_change_pct: "0", delay_confirmed_orders_days: "0", cancel_confirmed_orders: false });
  const [msg, setMsg] = useState("");
  const inval = () => { qc.invalidateQueries({ queryKey: ["item", id] }); qc.invalidateQueries({ queryKey: ["inventory"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const fail = (e: Error) => setMsg(e.message);

  const move = useMutation({ mutationFn: () => api(`/inventory/${id}/movements`, { method: "POST", body: { kind: mv.kind, quantity: Number(mv.quantity), reason: mv.reason, expiry: mv.expiry || null } }),
    onSuccess: () => { setMsg("Movement recorded."); setMv({ ...mv, quantity: "", reason: "" }); inval(); }, onError: fail });
  const order = useMutation({ mutationFn: () => api(`/inventory/${id}/orders`, { method: "POST", body: { quantity: Number(ord.quantity), expected_date: ord.expected_date, confirmed: ord.confirmed } }),
    onSuccess: () => { setMsg("Order recorded."); inval(); }, onError: fail });
  const scen = useMutation({ mutationFn: () => api("/scenarios", { method: "POST", body: { item_id: id, name: sc.name, assumptions: { demand_change_pct: Number(sc.demand_change_pct), delay_confirmed_orders_days: Number(sc.delay_confirmed_orders_days), cancel_confirmed_orders: sc.cancel_confirmed_orders } } }),
    onSuccess: () => { setMsg("Scenario saved (inventory unchanged). See Scenarios page."); qc.invalidateQueries({ queryKey: ["scenarios"] }); }, onError: fail });
  const submit = (fn: () => void) => (e: FormEvent) => { e.preventDefault(); setMsg(""); fn(); };
  const w = canWrite(role);

  return (
    <aside className="fixed inset-y-0 right-0 w-full max-w-lg bg-surface border-l border-line p-5 overflow-y-auto shadow-lg z-20" aria-label="Inventory item details">
      <button className="btn mb-4" onClick={onClose}>Close</button>
      {q.isLoading ? <Skeleton h={300} /> : q.error ? <ErrorBox error={q.error} /> : (
        <div className="space-y-5">
          <div><h2 className="text-lg font-semibold">{q.data.drug_name}</h2><p className="text-sm text-muted">{q.data.location} · {q.data.label}</p></div>
          <ForecastPanel f={q.data.forecast} />
          {msg && <p role="status" className="text-sm text-teal">{msg}</p>}
          {w && <>
            <form onSubmit={submit(() => move.mutate())} className="space-y-2 border-t border-line pt-3"><h3 className="font-medium text-sm">Record stock movement</h3>
              <select className="input" aria-label="Movement type" value={mv.kind} onChange={(e) => setMv({ ...mv, kind: e.target.value })}>
                {["receipt", "issue", "adjustment", "transfer_in", "transfer_out"].map((k) => <option key={k}>{k}</option>)}</select>
              <input className="input" type="number" step="any" required placeholder={mv.kind === "adjustment" ? "Signed quantity (e.g. -5)" : "Quantity"} value={mv.quantity} onChange={(e) => setMv({ ...mv, quantity: e.target.value })} />
              <input className="input" placeholder={mv.kind === "adjustment" ? "Reason (required)" : "Reason (optional)"} value={mv.reason} onChange={(e) => setMv({ ...mv, reason: e.target.value })} />
              {["receipt", "transfer_in"].includes(mv.kind) && <label className="text-sm block">Expiry date (optional)<input className="input mt-1" type="date" value={mv.expiry} onChange={(e) => setMv({ ...mv, expiry: e.target.value })} /></label>}
              <button className="btn btn-primary" disabled={move.isPending}>{move.isPending ? "Saving…" : "Save movement"}</button></form>
            <form onSubmit={submit(() => order.mutate())} className="space-y-2 border-t border-line pt-3"><h3 className="font-medium text-sm">Add purchase order</h3>
              <input className="input" type="number" min="0" step="any" required placeholder="Quantity" value={ord.quantity} onChange={(e) => setOrd({ ...ord, quantity: e.target.value })} />
              <input className="input" type="date" required aria-label="Expected date" value={ord.expected_date} onChange={(e) => setOrd({ ...ord, expected_date: e.target.value })} />
              <label className="text-sm flex gap-2"><input type="checkbox" checked={ord.confirmed} onChange={(e) => setOrd({ ...ord, confirmed: e.target.checked })} /> Supplier confirmed (only confirmed orders count as supply)</label>
              <button className="btn" disabled={order.isPending}>Add order</button></form></>}
          {(w || role === "analyst") && <form onSubmit={submit(() => scen.mutate())} className="space-y-2 border-t border-line pt-3"><h3 className="font-medium text-sm">Save what-if scenario <Kind k="hypothetical" /></h3>
            <input className="input" required placeholder="Scenario name" value={sc.name} onChange={(e) => setSc({ ...sc, name: e.target.value })} />
            <label className="text-sm block">Demand change %<input className="input mt-1" type="number" step="any" value={sc.demand_change_pct} onChange={(e) => setSc({ ...sc, demand_change_pct: e.target.value })} /></label>
            <label className="text-sm block">Delay confirmed orders (days)<input className="input mt-1" type="number" min="0" value={sc.delay_confirmed_orders_days} onChange={(e) => setSc({ ...sc, delay_confirmed_orders_days: e.target.value })} /></label>
            <label className="text-sm flex gap-2"><input type="checkbox" checked={sc.cancel_confirmed_orders} onChange={(e) => setSc({ ...sc, cancel_confirmed_orders: e.target.checked })} /> Cancel confirmed orders</label>
            <button className="btn" disabled={scen.isPending}>Save scenario</button></form>}
          <div className="border-t border-line pt-3"><h3 className="font-medium text-sm mb-1">Batches (first-expiry-first-out)</h3>
            {q.data.batches.length === 0 ? <p className="text-sm text-muted">No stock recorded.</p> :
              <ul className="text-sm">{q.data.batches.map((b: any) => <li key={b.id}>{num(b.quantity)} · expires {fmtDate(b.expiry)} {b.lot && `· lot ${b.lot}`}</li>)}</ul>}</div>
          <div className="border-t border-line pt-3"><h3 className="font-medium text-sm mb-1">Movement history</h3>
            {q.data.movements.length === 0 ? <p className="text-sm text-muted">None yet.</p> :
              <ul className="text-sm space-y-1">{q.data.movements.map((m: any) => <li key={m.id}>{new Date(m.at).toLocaleString()} · {m.kind} {num(m.quantity)} → balance {num(m.balance_after)} {m.reason && `(${m.reason})`}</li>)}</ul>}</div>
        </div>)}
    </aside>
  );
}

export default function Inventory() {
  const { role } = useOutletContext<{ role?: string }>();
  const qc = useQueryClient();
  const [sp, setSp] = useSearchParams();
  const [sel, setSel] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [csv, setCsv] = useState("");
  const [imp, setImp] = useState<any>(null);
  const [err, setErr] = useState("");
  const page = Number(sp.get("page") ?? 1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  for (const k of ["q", "status", "location_id"]) if (sp.get(k)) params.set(k, sp.get(k)!);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); n.delete("page"); setSp(n); };

  const locs = useQuery({ queryKey: ["locations"], queryFn: () => api("/inventory/locations") });
  const list = useQuery({ queryKey: ["inventory", params.toString()], queryFn: () => api(`/inventory?${params}`), placeholderData: keepPreviousData });
  const [f, setF] = useState({ location_id: "", drug_name: "", unit: "units", avg_daily_consumption: "0", lead_time_days: "0", safety_stock_days: "0" });
  const [locName, setLocName] = useState("");
  const done = () => { qc.invalidateQueries({ queryKey: ["inventory"] }); qc.invalidateQueries({ queryKey: ["locations"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const addItem = useMutation({ mutationFn: () => api("/inventory", { method: "POST", body: { ...f, location_id: Number(f.location_id), avg_daily_consumption: Number(f.avg_daily_consumption), lead_time_days: Number(f.lead_time_days), safety_stock_days: Number(f.safety_stock_days) } }),
    onSuccess: (r) => { setShowAdd(false); done(); setSel(r.id); }, onError: (e: Error) => setErr(e.message) });
  const addLoc = useMutation({ mutationFn: () => api("/inventory/locations", { method: "POST", body: { name: locName } }), onSuccess: () => { setLocName(""); done(); }, onError: (e: Error) => setErr(e.message) });
  const runImport = useMutation({ mutationFn: (commit: boolean) => api("/inventory/import", { method: "POST", body: { csv_text: csv, commit } }), onSuccess: (r) => { setImp(r); if (r.committed) done(); }, onError: (e: Error) => setErr(e.message) });
  const w = canWrite(role);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h1 className="text-xl font-semibold">Inventory</h1><p className="text-sm text-muted"><Kind k="forecast" /> Your own recorded stock. Estimates, not certainties.</p></div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => download("/inventory/export.csv", "inventory_export.csv").catch((e) => setErr(e.message))}><Download size={14} /> Export</button>
          <button className="btn" onClick={() => download("/inventory/template.csv", "inventory_template.csv")}>Template</button>
          {w && <><button className="btn" onClick={() => setShowImport(!showImport)}>Import CSV</button><button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}><Plus size={14} /> Add item</button></>}
        </div>
      </div>
      {err && <p role="alert" className="text-sm text-crit">{err}</p>}
      {showAdd && w && (
        <form className="card grid md:grid-cols-3 gap-3" onSubmit={(e) => { e.preventDefault(); setErr(""); addItem.mutate(); }}>
          <select className="input" required aria-label="Location" value={f.location_id} onChange={(e) => setF({ ...f, location_id: e.target.value })}><option value="">Choose location…</option>{locs.data?.map((l: any) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
          <input className="input md:col-span-2" required placeholder="Drug name, strength, form" value={f.drug_name} onChange={(e) => setF({ ...f, drug_name: e.target.value })} />
          <label className="text-sm">Unit<input className="input mt-1" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></label>
          <label className="text-sm">Avg daily consumption<input className="input mt-1" type="number" min="0" step="any" value={f.avg_daily_consumption} onChange={(e) => setF({ ...f, avg_daily_consumption: e.target.value })} /></label>
          <label className="text-sm">Supplier lead time (days)<input className="input mt-1" type="number" min="0" step="any" value={f.lead_time_days} onChange={(e) => setF({ ...f, lead_time_days: e.target.value })} /></label>
          <label className="text-sm">Safety stock (days)<input className="input mt-1" type="number" min="0" step="any" value={f.safety_stock_days} onChange={(e) => setF({ ...f, safety_stock_days: e.target.value })} /></label>
          <div className="flex items-end gap-2"><button className="btn btn-primary" disabled={addItem.isPending}>{addItem.isPending ? "Saving…" : "Create item"}</button></div>
          <div className="md:col-span-3 flex gap-2 items-end border-t border-line pt-3"><label className="text-sm flex-1">New location<input className="input mt-1" value={locName} onChange={(e) => setLocName(e.target.value)} /></label><button type="button" className="btn" disabled={!locName || addLoc.isPending} onClick={() => addLoc.mutate()}>Add location</button></div>
        </form>)}
      {showImport && w && (
        <div className="card space-y-2"><h2 className="font-medium">CSV import (preview first, then commit)</h2>
          <textarea className="input h-32 py-2 font-mono text-xs" placeholder="Paste CSV (download the template for columns)" value={csv} onChange={(e) => setCsv(e.target.value)} />
          <div className="flex gap-2"><button className="btn" disabled={!csv || runImport.isPending} onClick={() => runImport.mutate(false)}>Validate / preview</button>
            <button className="btn btn-primary" disabled={!imp || imp.valid_rows === 0 || imp.committed || runImport.isPending} onClick={() => runImport.mutate(true)}>Commit {imp?.valid_rows ?? 0} valid rows</button></div>
          {imp && <div className="text-sm"><p>{imp.valid_rows} valid · {imp.rejected_rows} rejected {imp.committed && `· ${imp.inserted} inserted`}</p>{imp.errors.map((e: any) => <p key={e.row} className="text-crit">Row {e.row}: {e.error}</p>)}</div>}
        </div>)}
      <div className="card grid md:grid-cols-4 gap-3">
        <input className="input" placeholder="Search drug name" aria-label="Search" value={sp.get("q") ?? ""} onChange={(e) => set("q", e.target.value)} />
        <select className="input" aria-label="Location filter" value={sp.get("location_id") ?? ""} onChange={(e) => set("location_id", e.target.value)}><option value="">All locations</option>{locs.data?.map((l: any) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
        <select className="input" aria-label="Status filter" value={sp.get("status") ?? ""} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
        <button className="btn" onClick={() => setSp(new URLSearchParams())}>Reset</button>
      </div>
      {list.isLoading ? <Skeleton h={260} /> : list.error ? <ErrorBox error={list.error} retry={() => list.refetch()} /> :
        list.data.items.length === 0 ? <Empty title="No inventory items" hint={w ? "Add an item, import a CSV, or run `python -m scripts.seed_demo_data` for simulated demo data." : "Ask an inventory manager to add items."} /> : (
          <><div className="card p-0 overflow-x-auto"><table className="w-full min-w-[760px]"><thead><tr><th className="th">Drug</th><th className="th">Location</th><th className="th">Stock</th><th className="th">Days of supply</th><th className="th">Stock-out (est.)</th><th className="th">Status</th></tr></thead>
            <tbody>{list.data.items.map((r: any) => (
              <tr key={r.id} className="hover:bg-bg cursor-pointer" tabIndex={0} onClick={() => setSel(r.id)} onKeyDown={(e) => e.key === "Enter" && setSel(r.id)}>
                <td className="td font-medium">{r.drug_name} {r.is_demo && <Badge tone="warn">DEMO</Badge>}</td><td className="td">{r.location}</td>
                <td className="td">{num(r.total_stock)} {r.unit}</td><td className="td">{num(r.forecast.days_of_supply_with_incoming)}</td>
                <td className="td">{r.forecast.stockout_beyond_horizon ? ">365 d" : fmtDate(r.forecast.estimated_stockout_date)}</td><td className="td"><StatusBadge s={r.forecast.status} /></td></tr>))}</tbody></table></div>
            <Pager page={list.data.page} pages={list.data.pages} onPage={(p) => { const n = new URLSearchParams(sp); n.set("page", String(p)); setSp(n); }} /></>)}
      {sel != null && <Detail id={sel} role={role} onClose={() => setSel(null)} />}
    </div>
  );
}
