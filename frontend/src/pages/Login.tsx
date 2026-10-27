import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/ui";
import { api, setToken } from "../api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const r = await api("/auth/login", { method: "POST", body: { email, password } });
      setToken(r.access_token); nav("/");
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 !p-8 !rounded-[28px]">
        <div className="flex items-center gap-3"><Logo size={44} /><div><h1 className="text-2xl font-semibold grad-text leading-tight">MediWatch</h1><p className="text-[11px] tracking-[.18em] uppercase text-muted">Intelligence</p></div></div>
        <p className="text-sm text-muted">Anticipate disruption. Protect availability.</p>
        <label className="block text-sm">Email<input className="input mt-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></label>
        <label className="block text-sm">Password<input className="input mt-1" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
        {error && <p role="alert" className="text-sm text-crit">{error}</p>}
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="text-xs text-muted">Demo accounts are created by <code>python -m scripts.seed_demo_data</code> (passwords are printed once).</p>
      </form>
    </div>
  );
}
