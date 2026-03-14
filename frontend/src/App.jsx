import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";

// ── Temporary stubs ───────────────────────────────────────────────────────────
// Replace each with the real import as its step is completed.
// Do not delete this block until all page files exist.
const Dashboard    = () => <div className="p-6 text-slate-700">Dashboard</div>;
const Creators     = () => <div className="p-6 text-slate-700">Creators</div>;
const CreatorDetail = () => <div className="p-6 text-slate-700">Creator Detail</div>;
const Campaigns    = () => <div className="p-6 text-slate-700">Campaigns</div>;
const Analytics    = () => <div className="p-6 text-slate-700">Analytics</div>;
const Alerts       = () => <div className="p-6 text-slate-700">Alerts</div>;
// ─────────────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Layout wraps all routes — Outlet in Layout injects the active page */}
        <Route element={<Layout />}>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/creators"     element={<Creators />} />
          <Route path="/creators/:id" element={<CreatorDetail />} />
          <Route path="/campaigns"    element={<Campaigns />} />
          <Route path="/analytics"    element={<Analytics />} />
          <Route path="/alerts"       element={<Alerts />} />
          {/* Catch-all — always last */}
          <Route path="*" element={
            <div className="p-6 text-slate-500">404 — Page not found.</div>
          } />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}