import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useApi from "../hooks/useApi";
import { fetchCreators } from "../api/client";
import HealthScoreBadge from "./HealthScoreBadge";
import Pagination from "./Pagination";
import { DEFAULT_CREATOR_PARAMS } from "../constants";
import { fmtFollowers, fmtPct, fmtNumber } from "../utils/format";

// ── Constants (module-level) ──────────────────────────────────────────────────
// Hardcoded from API contract — deriving from current results is wrong because
// an already-filtered result set won't contain all categories.
const CATEGORIES = [
  "Tech Enthusiasts",
  "Foodies",
  "Health & Wellness",
  "Outdoor Adventurers",
  "Fashionistas",
];

const SORTABLE_COLUMNS = [
  { label: "#",              field: null,             sortable: false },
  { label: "Creator",        field: null,             sortable: false },
  { label: "Platform",       field: null,             sortable: false },
  { label: "Category",       field: null,             sortable: false },
  { label: "Followers",      field: "followers",      sortable: true  },
  { label: "Engagement",     field: "engagement_rate",sortable: true  },
  { label: "Health Score",   field: "health_score",   sortable: true  },
  { label: "Avg Views",      field: "avg_views",      sortable: true  },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function FilterBar({ params, onParamsChange }) {
  // Local state for the search input — only fires onParamsChange on Enter/blur
  // to avoid per-keystroke fetch+abort cycles.
  const [searchDraft, setSearchDraft] = useState(params.search ?? "");

  function commitSearch() {
    if (searchDraft !== (params.search ?? "")) {
      onParamsChange({ search: searchDraft, page: 1 });
    }
  }

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {/* Search */}
      <input
        type="text"
        placeholder="Search creators…"
        value={searchDraft}
        onChange={(e) => setSearchDraft(e.target.value)}
        onBlur={commitSearch}
        onKeyDown={(e) => e.key === "Enter" && commitSearch()}
        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
          placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary w-52"
      />

      {/* Category */}
      <select
        value={params.category ?? ""}
        onChange={(e) => onParamsChange({ category: e.target.value || undefined, page: 1 })}
        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
          focus:outline-none focus:ring-2 focus:ring-primary"
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>

      {/* Health score range */}
      <input
        type="number"
        placeholder="Min health"
        min={0} max={100}
        value={params.min_health_score ?? ""}
        onChange={(e) =>
          onParamsChange({ min_health_score: e.target.value || undefined, page: 1 })
        }
        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
          placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary w-28"
      />
      <input
        type="number"
        placeholder="Max health"
        min={0} max={100}
        value={params.max_health_score ?? ""}
        onChange={(e) =>
          onParamsChange({ max_health_score: e.target.value || undefined, page: 1 })
        }
        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
          placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary w-28"
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CreatorTable({ params, onParamsChange }) {
  const navigate = useNavigate();
  const { data, loading, error } = useApi(fetchCreators, params);

  // Clicking the same column toggles asc/desc.
  // Clicking a different column resets to desc (most useful default).
  function handleSort(field) {
    const newOrder =
      field === params.sort_by
        ? params.sort_order === "desc" ? "asc" : "desc"
        : "desc";
    onParamsChange({ sort_by: field, sort_order: newOrder, page: 1 });
  }

  function sortIndicator(field) {
    if (params.sort_by !== field) return <span className="text-slate-300 ml-1">↕</span>;
    return (
      <span className="text-primary ml-1">
        {params.sort_order === "asc" ? "▲" : "▼"}
      </span>
    );
  }

  return (
    <div>
      <FilterBar params={params} onParamsChange={onParamsChange} />

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                {SORTABLE_COLUMNS.map((col) => (
                  <th
                    key={col.label}
                    onClick={() => col.sortable && handleSort(col.field)}
                    className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide
                      text-slate-500 whitespace-nowrap
                      ${col.sortable ? "cursor-pointer hover:text-slate-800 select-none" : ""}`}
                  >
                    {col.label}
                    {col.sortable && sortIndicator(col.field)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                    Loading creators…
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-red-500">
                    {error.detail ?? "Failed to load creators."}
                  </td>
                </tr>
              )}
              {!loading && !error && data?.results?.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                    No creators match your filters.{" "}
                    <button
                      onClick={() => onParamsChange(DEFAULT_CREATOR_PARAMS)}
                      className="text-primary underline"
                    >
                      Reset filters
                    </button>
                  </td>
                </tr>
              )}
              {!loading && !error && data?.results?.map((creator, i) => {
                // Rank accounts for pagination so page 2 starts at 21, not 1.
                const rank = (params.page - 1) * params.page_size + i + 1;
                return (
                  <tr
                    key={creator.id}
                    onClick={() => navigate(`/creators/${creator.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs">{rank}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">
                        {creator.display_name ?? creator.username}
                      </div>
                      <div className="text-xs text-slate-400">{creator.username}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600 capitalize">{creator.platform}</td>
                    <td className="px-4 py-3 text-slate-600">{creator.category ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{fmtFollowers(creator.followers)}</td>
                    <td className="px-4 py-3 text-slate-700">{fmtPct(creator.engagement_rate)}</td>
                    <td className="px-4 py-3">
                      <HealthScoreBadge score={creator.health_score} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-slate-700">{fmtNumber(creator.avg_views)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination lives inside the card, below the table */}
        {!loading && !error && data && (
          <div className="px-4 pb-4">
            <Pagination
              page={params.page}
              pageSize={params.page_size}
              total={data.total}
              onParamsChange={onParamsChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}