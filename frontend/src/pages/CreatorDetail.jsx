import { useParams, Link } from "react-router-dom";
import useApi from "../hooks/useApi";
import { fetchCreator } from "../api/client";
import HealthScoreBadge from "../components/HealthScoreBadge";
import { fmtFollowers, fmtPct, fmtNumber, fmtRoi, fmtDate } from "../utils/format";

// ── Sub-components ────────────────────────────────────────────────────────────

function MetricTile({ label, value }) {
  return (
    <div className="bg-slate-50 rounded-lg px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{label}</p>
      <p className="text-xl font-bold text-slate-800 mt-0.5">{value}</p>
    </div>
  );
}

function ProfileCard({ creator }) {
  // Avatar: use avatar_url if present, otherwise render an initial-letter circle.
  const initial = (creator.display_name ?? creator.username ?? "?")[0].toUpperCase();

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-start gap-6">
        {/* Avatar */}
        {creator.avatar_url ? (
          <img
            src={creator.avatar_url}
            alt={creator.display_name}
            className="w-16 h-16 rounded-full object-cover flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-primary flex items-center justify-center
            text-white text-2xl font-bold flex-shrink-0">
            {initial}
          </div>
        )}

        {/* Identity */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-xl font-bold text-slate-800">
              {creator.display_name ?? creator.username}
            </h2>
            <HealthScoreBadge score={creator.health_score} size="lg" />
          </div>
          <p className="text-sm text-slate-500 mt-0.5">{creator.username}</p>
          <div className="flex gap-4 mt-1 text-xs text-slate-400">
            <span className="capitalize">{creator.platform}</span>
            {creator.category && <span>{creator.category}</span>}
            {creator.country  && <span>{creator.country}</span>}
          </div>
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-4 gap-3 mt-6">
        <MetricTile label="Followers"       value={fmtFollowers(creator.followers)} />
        <MetricTile label="Engagement Rate" value={fmtPct(creator.engagement_rate)} />
        <MetricTile label="Avg Views"       value={fmtNumber(creator.avg_views)} />
        <MetricTile label="Posts / Week"    value={creator.posts_per_week?.toFixed(1) ?? "—"} />
      </div>
    </div>
  );
}

function CreatorCampaignsTable({ campaigns }) {
  if (!campaigns?.length) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-4">Linked Campaigns</h2>
        <p className="text-slate-400 text-sm">No campaigns linked to this creator yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-sm font-semibold text-slate-700">
          Linked Campaigns
          <span className="ml-2 text-slate-400 font-normal">({campaigns.length})</span>
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {["Company", "Type", "Channel", "Segment", "ROI",
                "Conv. Rate", "Eng. Score", "Date"].map((h) => (
                <th key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase
                    tracking-wide text-slate-500 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {campaigns.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-800">{c.company}</td>
                <td className="px-4 py-3 text-slate-600">{c.campaign_type}</td>
                <td className="px-4 py-3 text-slate-600">{c.channel_used}</td>
                <td className="px-4 py-3 text-slate-600">{c.customer_segment ?? "—"}</td>
                <td className="px-4 py-3 font-medium text-slate-700">{fmtRoi(c.roi)}</td>
                <td className="px-4 py-3 text-slate-600">{fmtPct(c.conversion_rate)}</td>
                {/* engagement_score is 1–10 from Kaggle (distinct from creator engagement_rate) */}
                <td className="px-4 py-3 text-slate-600">{c.engagement_score ?? "—"} / 10</td>
                <td className="px-4 py-3 text-slate-400">{fmtDate(c.date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CreatorDetail() {
  const { id } = useParams();
  const { data: creator, loading, error } = useApi(fetchCreator, id);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Loading creator…
      </div>
    );
  }

  if (error) {
    // Distinguish 404 (bad ID / not found) from server errors.
    const message = error.status === 404
      ? "Creator not found."
      : "Something went wrong loading this creator.";
    return (
      <div className="p-6 space-y-3">
        <p className="text-red-500 text-sm">{message}</p>
        <Link to="/creators" className="text-primary text-sm hover:underline">
          ← Back to Creators
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <Link to="/creators" className="text-sm text-primary hover:underline">
        ← Back to Creators
      </Link>

      <ProfileCard creator={creator} />
      <CreatorCampaignsTable campaigns={creator.campaigns} />
    </div>
  );
}