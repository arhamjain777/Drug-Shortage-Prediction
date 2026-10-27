import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import App from "./App";
import "./index.css";

// dark is the default look; the toggle stores "light" to opt out
if (localStorage.getItem("mw_theme") !== "light") document.documentElement.classList.add("dark");

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      {/* reducedMotion="user" makes Motion respect the OS "reduce motion" setting */}
      <MotionConfig reducedMotion="user">
        <BrowserRouter><App /></BrowserRouter>
      </MotionConfig>
    </QueryClientProvider>
  </React.StrictMode>
);
