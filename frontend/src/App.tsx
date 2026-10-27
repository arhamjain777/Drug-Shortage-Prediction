import { useState } from "react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Boxes, FlaskConical, LayoutDashboard, LogOut, Menu, Moon, Pill, Settings, Sun } from "lucide-react";
import { api, getToken, setToken } from "./api";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Drugs from "./pages/Drugs";
import Inventory from "./pages/Inventory";
import Scenarios from "./pages/Scenarios";
import Admin from "./pages/Admin";
import { Logo, LiveDot } from "./components/ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/drugs", label: "Reported shortages", icon: Pill },
  { to: "/inventory", label: "Inventory", icon: Boxes },
  { to: "/scenarios", label: "Scenarios", icon: FlaskConical },
  { to: "/admin", label: "Data & model", icon: Settings },
];

function Shell() {
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));
  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me") });

  const toggle = () => {
    document.documentElement.classList.toggle("dark", !dark);
    localStorage.setItem("mw_theme", dark ? "light" : "dark");
    setDark(!dark);
  };

  return (
    <div className="min-h-screen md:flex gap-4 p-3 md:p-4">
      <aside className={`${open ? "block" : "hidden"} md:block md:w-64 shrink-0 glass p-5 md:sticky md:top-4 md:h-[calc(100vh-2rem)] flex-col`} >
        <Link to="/" className="flex items-center gap-3 mb-8"><Logo size={36} /><span><span className="block font-semibold text-lg leading-none">MediWatch</span><span className="text-[11px] tracking-[.18em] uppercase text-muted">Intelligence</span></span></Link>
        <nav aria-label="Main" className="space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => `relative flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium transition-colors ${isActive ? "text-ink" : "text-muted hover:text-ink"}`}>
              {({ isActive }) => (<>
                {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-2xl border border-teal/40" style={{ background: "linear-gradient(135deg, rgb(var(--teal) / .28), rgb(var(--cyan) / .12))", boxShadow: "0 0 24px -6px rgb(var(--teal) / .6)" }} transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
                <Icon size={17} className="relative" /><span className="relative">{label}</span>
              </>)}
            </NavLink>
          ))}
        </nav>
        <div className="mt-8 rounded-2xl p-3 text-xs text-muted rx-pattern border border-line/50">Decision-support prototype.<br />Not clinically certified.</div>
      </aside>
      <div className="flex-1 min-w-0 space-y-4">
        <header className="glass h-14 !rounded-full flex items-center justify-between px-3 md:px-5 sticky top-3 z-10">
          <button className="md:hidden btn !px-3" aria-label="Toggle menu" onClick={() => setOpen(!open)}><Menu size={16} /></button>
          <span className="text-sm text-muted hidden md:flex items-center gap-2"><LiveDot /> Anticipate disruption. Protect availability.</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted hidden sm:block">{me.data?.email} · <span className="uppercase tracking-wider">{me.data?.role}</span></span>
            <button className="btn !px-3" aria-label="Toggle dark mode" onClick={toggle}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>
            <button className="btn" onClick={() => { setToken(null); nav("/login"); }}><LogOut size={16} /> <span className="hidden sm:inline">Sign out</span></button>
          </div>
        </header>
        <main className="p-1 md:p-2 max-w-7xl">
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname} initial={{ opacity: 0, y: 10, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
              <Outlet context={{ role: me.data?.role }} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

const Protected = () => (getToken() ? <Shell /> : <Navigate to="/login" replace />);

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/drugs" element={<Drugs />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/scenarios" element={<Scenarios />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<div className="p-10 text-center"><h1 className="text-xl font-semibold">Page not found</h1><Link className="text-teal underline" to="/">Back to dashboard</Link></div>} />
    </Routes>
  );
}
