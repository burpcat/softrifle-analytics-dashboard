import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard     from "./pages/Dashboard";
import Creators      from "./pages/Creators";
import CreatorDetail from "./pages/CreatorDetail";
import Campaigns     from "./pages/Campaigns";
import Analytics     from "./pages/Analytics";
import Alerts        from "./pages/Alerts";

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