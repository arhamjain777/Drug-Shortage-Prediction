import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, download, fmtDate } from "../api";
import { Badge, Empty, ErrorBox, Kind, Pager, Skeleton } from "../components/ui";

export default function Drugs() {
  const [sp, setSp] = useSearchParams();               // filters live in the URL (shareable)
  const [selected, setSelected] = useState<number | null>(null);
  const page = Number(sp.get("page") ?? 1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  for (const k of ["q", "status", "dosage_form", "sort", "order"]) if (sp.get(k)) params.set(k, sp.get(k)!);

  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api("/shortages/facets"), staleTime: 300_000 });
  const list = useQuery({ queryKey: ["shortages", params.toString()], queryFn: () => api(`/shortages?${params}`), placeholderData: keepPreviousData });
  const detail = useQuery({ queryKey: ["shortage", selected], queryFn: () => api(`/shortages/${selected}`), enabled: selected != null });

  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); n.delete("page"); setSp(n); };
  const exportQs = new URLSearchParams(params); exportQs.delete("page"); exportQs.delete("page_size");

  return (
    <div className="space-y-4">
      <div><h1 className="text-xl font-semibold">Reported shortages</h1>
        <p className="text-sm text-muted"><Kind k="reported" /> Official US FDA records via openFDA. Not a feed for India.</p></div>
      <div className="card grid md:grid-cols-5 gap-3">
        <input className="input md:col-span-2" placeholder="Search generic name, company, presentation" aria-label="Search" value={sp.get("q") ?? ""} onChange={(e) => set("q", e.target.value)} />
        <select className="input" aria-label="Status" value={sp.get("status") ?? ""} onChange={(e) => set("status", e.target.value)}>
          <option value="">All statuses</option>{facets.data?.statuses.map((s: string) => <option key={s}>{s}</option>)}</select>
        <select className="input" aria-label="Dosage form" value={sp.get("dosage_form") ?? ""} onChange={(e) => set("dosage_form", e.target.value)}>
          <option value="">All dosage forms</option>{facets.data?.dosage_forms.map((s: string) => <option key={s}>{s}</option>)}</select>
        <div className="flex gap-2">
          <button className="btn" onClick={() => setSp(new URLSearchParams())}>Reset</button>
          <button className="btn" onClick={() => download(`/shortages/export.csv?${exportQs}`, "reported_shortages.csv").catch((e) => alert(e.message))}><Download size={14} /> CSV</button>
        </div>
      </div>
      {list.isLoading ? <Skeleton h={300} /> : list.error ? <ErrorBox error={list.error} retry={() => list.refetch()} /> :
        list.data.items.length === 0 ? <Empty title="No matching records" hint="Clear filters, or refresh FDA data from Data & model." /> : (
          <>
            <div className="card p-0 overflow-x-auto">
              <table className="w-full min-w-[720px]"><thead><tr><th className="th">Generic name</th><th className="th">Company</th><th className="th">Status</th><th className="th">Dosage form</th><th className="th">Posted</th><th className="th">Updated</th></tr></thead>
                <tbody>{list.data.items.map((r: any) => (
                  <tr key={r.id} className="hover:bg-bg cursor-pointer" onClick={() => setSelected(r.id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSelected(r.id)}>
                    <td className="td font-medium">{r.generic_name}</td><td className="td">{r.company_name ?? "—"}</td>
                    <td className="td"><Badge tone={r.status?.toLowerCase() === "current" ? "crit" : "neutral"}>{r.status ?? "—"}</Badge></td>
                    <td className="td">{r.dosage_form ?? "—"}</td><td className="td">{fmtDate(r.initial_posting_date)}</td><td className="td">{fmtDate(r.update_date)}</td></tr>))}</tbody></table>
            </div>
            <p className="text-sm text-muted">{list.data.total.toLocaleString()} records</p>
            <Pager page={list.data.page} pages={list.data.pages} onPage={(p) => { const n = new URLSearchParams(sp); n.set("page", String(p)); setSp(n); }} />
          </>)}
      {selected != null && (
        <aside className="fixed inset-y-0 right-0 w-full max-w-md bg-surface border-l border-line p-5 overflow-y-auto shadow-lg z-20" aria-label="Record details">
          <button className="btn mb-4" onClick={() => setSelected(null)}>Close</button>
          {detail.isLoading ? <Skeleton h={200} /> : detail.error ? <ErrorBox error={detail.error} /> : (
            <div className="space-y-2 text-sm">
              <h2 className="text-lg font-semibold">{detail.data.generic_name}</h2><Kind k="reported" />
              {[["Company", detail.data.company_name], ["Status", detail.data.status], ["Availability", detail.data.availability], ["Reason", detail.data.shortage_reason],
                ["Presentation", detail.data.presentation], ["Dosage form", detail.data.dosage_form], ["Strength", detail.data.strength?.join(", ")],
                ["Therapeutic category", detail.data.therapeutic_category?.join(", ")], ["Brand names", detail.data.brand_names?.join(", ")],
                ["Posted", fmtDate(detail.data.initial_posting_date)], ["Updated", fmtDate(detail.data.update_date)], ["Related info", detail.data.related_info]]
                .map(([k, v]) => <p key={k as string}><span className="text-muted">{k}: </span>{v || "—"}</p>)}
              <p className="text-xs text-muted pt-2">{detail.data.note}</p>
            </div>)}
        </aside>)}
    </div>
  );
}
