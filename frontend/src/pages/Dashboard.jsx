import { Link, useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import useApi from "../hooks/useApi";
import { fetchAnalyticsSummary, fetchAlerts } from "../api/client";
import StatCard from "../components/StatCard";
import HealthScoreBadge from "../components/HealthScoreBadge";
import AlertBadge from "../components/AlertBadge";

// ── Stable params (module-level) ──────────────────────────────────────────────
// Must stay outside the component. Inline object literals re-create on every
// render, causing useApi's JSON.stringify dep to fire on every render loop.
const ALERT_PARAMS = { page_size: 5 };

// ── Formatting helpers ────────────────────────────────────────────────────────
const fmtNumber = (n) => (n == null ? "—" : n.toLocaleString());
const fmtRoi    = (n) => (n == null ? "—" : `${n.toFixed(2)}x`);
const fmtPct    = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);

function relativeTime(dateStr) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  if (isNaN(diff)) return "—";
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins  < 60)  return `${mins}m ago`;
  if (hours < 24)  return `${hours}h ago`;
  return `${days}d ago`;
}

// Case-insensitive key lookup — guards against CSV casing inconsistencies
// (e.g. "influencer" vs "Influencer") on any avg_roi_by_campaign_type object.
function findRoi(obj, key) {
  if (!obj) return null;
  const match = Object.keys(obj).find((k) => k.toLowerCase() === key.toLowerCase());
  return match ? obj[match] : null;
}

// Transform { TypeA: 5.01, TypeB: 4.99 } → [{ type: "TypeA", roi: 5.01 }, ...]
function roiByTypeToArray(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([type, roi]) => ({ type, roi }));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiRow({ summary }) {
  const influencerRoi = findRoi(summary.avg_roi_by_campaign_type, "influencer");
  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard
        title="Total Campaigns"
        value={fmtNumber(summary.total_campaigns)}
        subtitle="All types combined"
      />
      <StatCard
        title="Total Creators"
        value={fmtNumber(summary.total_creators)}
        subtitle="YouTube only"
      />
      <StatCard
        title="Avg Influencer ROI"
        value={fmtRoi(influencerRoi)}
        subtitle="Influencer campaign type"
      />
      <StatCard
        title="Influencer Campaigns"
        value={fmtNumber(summary.total_influencer_campaigns)}
        subtitle={`of ${fmtNumber(summary.total_campaigns)} total`}
      />
    </div>
  );
}

function TopCreatorsTable({ creators }) {
  const navigate = useNavigate();
  if (!creators?.length) {
    return <p className="text-slate-400 text-sm py-4">No creator data available.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-100">
            <th className="pb-2 pr-4 font-semibold">#</th>
            <th className="pb-2 pr-4 font-semibold">Creator</th>
            <th className="pb-2 pr-4 font-semibold">Category</th>
            <th className="pb-2 pr-4 font-semibold">Health Score</th>
            <th className="pb-2 font-semibold">Avg ROI</th>
          </tr>
        </thead>
        <tbody>
          {creators.map((c, i) => (
            <tr
              key={c.id}
              onClick={() => navigate(`/creators/${c.id}`)}
              className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer transition-colors"
            >
              <td className="py-2.5 pr-4 text-slate-400 font-mono">{i + 1}</td>
              <td className="py-2.5 pr-4">
                <div className="font-medium text-slate-800">{c.username}</div>
                <div className="text-xs text-slate-400">{c.platform}</div>
              </td>
              <td className="py-2.5 pr-4 text-slate-600">{c.category ?? "—"}</td>
              <td className="py-2.5 pr-4">
                <HealthScoreBadge score={c.health_score} size="sm" />
              </td>
              <td className="py-2.5 font-medium text-slate-700">
                {fmtRoi(c.avg_roi)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RoiByTypeChart({ avgRoiByType }) {
  const data = roiByTypeToArray(avgRoiByType);
  if (!data.length) return <p className="text-slate-400 text-sm py-4">No data.</p>;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <XAxis
          dataKey="type"
          tick={{ fontSize: 12, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          // Function domain: zooms in on tight data but expands if variance is higher.
          // Guards against Recharts clipping bars that fall outside a hardcoded range.
          domain={[
            (dataMin) => Math.min(4.9, Math.floor(dataMin * 10) / 10),
            (dataMax) => Math.max(5.1, Math.ceil(dataMax  * 10) / 10),
          ]}
          tick={{ fontSize: 12, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
          width={40}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <Tooltip
          formatter={(v) => [`${v.toFixed(3)}x`, "Avg ROI"]}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
        />
        <Bar dataKey="roi" radius={[4, 4, 0, 0]} fill="#2563eb" />
      </BarChart>
    </ResponsiveContainer>
  );
}

function RecentAlerts({ alerts, loading, error }) {
  if (loading) return <p className="text-slate-400 text-sm py-4">Loading alerts…</p>;
  if (error)   return <p className="text-red-500  text-sm py-4">Failed to load alerts.</p>;
  if (!alerts?.length) return <p className="text-slate-400 text-sm py-4">No recent alerts.</p>;

  return (
    <ul className="divide-y divide-slate-100">
      {alerts.map((a) => (
        <li key={a.id} className="py-3 flex items-start gap-3">
          <AlertBadge severity={a.severity} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-700 truncate">{a.message}</p>
            <p className="text-xs text-slate-400 mt-0.5">{a.type} · {relativeTime(a.created_at)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: summary, loading: summaryLoading, error: summaryError } =
    useApi(fetchAnalyticsSummary);
  const { data: alertsData, loading: alertsLoading, error: alertsError } =
    useApi(fetchAlerts, ALERT_PARAMS);

  // Summary drives the majority of the page — block on its loading state.
  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Loading dashboard…
      </div>
    );
  }
  if (summaryError) {
    return (
      <div className="flex items-center justify-center h-full text-red-500 text-sm">
        {summaryError.detail ?? "Failed to load dashboard data."}
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">Campaign performance at a glance</p>
      </div>

      {/* KPI row */}
      <KpiRow summary={summary} />

      {/* Middle row: top creators + ROI chart */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">
            Top Creators by Health Score
          </h2>
          <TopCreatorsTable creators={summary.top_creators} />
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">
            Avg ROI by Campaign Type
          </h2>
          <RoiByTypeChart avgRoiByType={summary.avg_roi_by_campaign_type} />
        </div>
      </div>

      {/* Recent alerts */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700">Recent Alerts</h2>
          <Link
            to="/alerts"
            className="text-xs text-primary font-medium hover:underline"
          >
            View all →
          </Link>
        </div>
        <RecentAlerts
          alerts={alertsData?.results}
          loading={alertsLoading}
          error={alertsError}
        />
      </div>
    </div>
  );
}