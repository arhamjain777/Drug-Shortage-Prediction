import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { api, num } from "../api";
import { Badge, ErrorBox, Kind, Skeleton } from "../components/ui";

export default function Admin() {
  const { role } = useOutletContext<{ role?: string }>();
  const qc = useQueryClient();
  const can = role === "admin" || role === "analyst";
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api("/admin/ingestion-runs"), enabled: can });
  const model = useQuery({ queryKey: ["model"], queryFn: () => api("/model/status") });
  const refresh = useMutation({ mutationFn: () => api("/admin/refresh", { method: "POST" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["runs"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); qc.invalidateQueries({ queryKey: ["shortages"] }); } });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Data & model</h1>
      <section className="card space-y-3"><div className="flex items-center justify-between"><h2 className="font-medium">FDA source refresh <Kind k="reported" /></h2>
        {can && <button className="btn btn-primary" disabled={refresh.isPending} onClick={() => refresh.mutate()}><RefreshCw size={14} className={refresh.isPending ? "animate-spin" : ""} /> {refresh.isPending ? "Refreshing…" : "Refresh now"}</button>}</div>
        {!can && <p className="text-sm text-muted">Only analysts and admins can refresh data.</p>}
        {refresh.data?.status === "failed" && <p role="alert" className="text-sm text-crit">Refresh failed: {refresh.data.error}. Stored data was kept.</p>}
        {runs.isLoading && can ? <Skeleton h={120} /> : runs.error ? <ErrorBox error={runs.error} /> : can && (
          runs.data.length === 0 ? <p className="text-sm text-muted">No refresh has been run yet.</p> :
            <div className="overflow-x-auto"><table className="w-full min-w-[640px]"><thead><tr>{["When", "Status", "Fetched", "New", "Updated", "Unchanged", "Dupes", "Rejected"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
              <tbody>{runs.data.map((r: any) => <tr key={r.id}><td className="td">{new Date(r.started_at).toLocaleString()}</td><td className="td"><Badge tone={r.status === "success" ? "ok" : r.status === "failed" ? "crit" : "neutral"}>{r.status}</Badge></td>
                <td className="td">{r.fetched}</td><td className="td">{r.inserted}</td><td className="td">{r.updated}</td><td className="td">{r.unchanged}</td><td className="td">{r.duplicates}</td><td className="td">{r.rejected}</td></tr>)}</tbody></table></div>)}
      </section>
      <section className="card space-y-2"><h2 className="font-medium">Shortage-risk model <Kind k="predicted" /></h2>
        {model.isLoading ? <Skeleton h={80} /> : model.error ? <ErrorBox error={model.error} /> : !model.data.available ? (
          <div className="text-sm"><Badge tone="neutral">Model unavailable</Badge><p className="mt-2 text-muted">{model.data.reason}</p><p className="text-muted mt-1">To train: <code>{model.data.how_to_train}</code></p></div>) : (
          <div className="text-sm space-y-1"><p><Badge tone={model.data.status === "experimental" ? "warn" : "teal"}>{model.data.status}</Badge> version {model.data.version} · horizon {model.data.horizon_days} days</p>
            <p>Test period {model.data.periods.test.join(" → ")} · base rate {num((model.data.test_metrics.base_rate ?? 0) * 100)}% · positives {model.data.test_metrics.n_positive}</p>
            <p>Precision {num(model.data.test_metrics.precision, 2)} · recall {num(model.data.test_metrics.recall, 2)} · PR-AUC {num(model.data.test_metrics.pr_auc, 2)}</p>
            <p className="text-xs text-muted">{model.data.disclaimer}</p></div>)}
      </section>
    </div>
  );
}
