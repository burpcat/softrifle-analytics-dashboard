import { useState } from "react";
import { Link } from "react-router-dom";
import useApi from "../hooks/useApi";
import { fetchCampaigns } from "../api/client";
import Pagination from "./Pagination";
import { DEFAULT_CAMPAIGN_PARAMS } from "../constants";
import { fmtRoi, fmtPct, fmtNumber, fmtDate } from "../utils/format";

// ── Constants (module-level) ──────────────────────────────────────────────────
const CAMPAIGN_TYPES = ["Influencer", "Email", "Display", "Search", "Social Media"];
const CHANNELS       = ["YouTube", "Instagram", "Facebook", "Google Ads", "Email", "Website"];
const SEGMENTS       = ["Tech Enthusiasts", "Foodies", "Health & Wellness", "Outdoor Adventurers", "Fashionistas"];

const SORTABLE_COLUMNS = [
  { label: "#",           field: null,              sortable: false },
  { label: "Company",     field: null,              sortable: false },
  { label: "Type",        field: null,              sortable: false },
  { label: "Channel",     field: null,              sortable: false },
  { label: "Segment",     field: null,              sortable: false },
  { label: "ROI",         field: "roi",             sortable: true  },
  { label: "Conv. Rate",  field: "conversion_rate", sortable: true  },
  { label: "Impressions", field: "impressions",     sortable: true  },
  { label: "Clicks",      field: "clicks",          sortable: true  },
  { label: "Duration",    field: null,              sortable: false },
  { label: "Date",        field: "date",            sortable: true  },
  { label: "Creator",     field: null,              sortable: false },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function CampaignFilterBar({ params, onParamsChange }) {
  return (
    <div className="space-y-2 mb-4">
      {/* Row 1: dropdowns + influencer toggle */}
      <div className="flex flex-wrap gap-3">
        <select
          value={params.campaign_type ?? ""}
          onChange={(e) =>
            onParamsChange({ campaign_type: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All types</option>
          {CAMPAIGN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          value={params.channel_used ?? ""}
          onChange={(e) =>
            onParamsChange({ channel_used: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All channels</option>
          {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select
          value={params.customer_segment ?? ""}
          onChange={(e) =>
            onParamsChange({ customer_segment: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All segments</option>
          {SEGMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Three-state influencer toggle.
            "All"              → has_creator: undefined (param removed entirely)
            "With Creator"     → has_creator: true
            "Without Creator"  → has_creator: false
            NOTE: false is a valid filter value — the merge handler must preserve it.
            The Campaigns.jsx handler strips `undefined` but not `false`. */}
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-sm">
          {[
            { label: "All",              value: undefined },
            { label: "With Creator",     value: true      },
            { label: "Without Creator",  value: false     },
          ].map(({ label, value }) => {
            const active = params.has_creator === value;
            return (
              <button
                key={label}
                onClick={() => onParamsChange({ has_creator: value, page: 1 })}
                className={`px-3 py-1.5 transition-colors
                  ${active
                    ? "bg-primary text-white"
                    : "text-slate-600 hover:bg-slate-50"}`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Row 2: ROI range + date range */}
      <div className="flex flex-wrap gap-3">
        <input
          type="number"
          placeholder="Min ROI"
          value={params.min_roi ?? ""}
          onChange={(e) =>
            onParamsChange({ min_roi: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary w-24"
        />
        <input
          type="number"
          placeholder="Max ROI"
          value={params.max_roi ?? ""}
          onChange={(e) =>
            onParamsChange({ max_roi: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary w-24"
        />
        <input
          type="date"
          value={params.date_from ?? ""}
          onChange={(e) =>
            onParamsChange({ date_from: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="date"
          value={params.date_to ?? ""}
          onChange={(e) =>
            onParamsChange({ date_to: e.target.value || undefined, page: 1 })
          }
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-700
            focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CampaignTable({ params, onParamsChange }) {
  const { data, loading, error } = useApi(fetchCampaigns, params);

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
      <CampaignFilterBar params={params} onParamsChange={onParamsChange} />

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                {SORTABLE_COLUMNS.map((col) => (
                  <th
                    key={col.label}
                    onClick={() => col.sortable && handleSort(col.field)}
                    className={`px-4 py-3 text-left text-xs font-semibold uppercase
                      tracking-wide text-slate-500 whitespace-nowrap
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
                  <td colSpan={12} className="px-4 py-10 text-center text-slate-400">
                    Loading campaigns…
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td colSpan={12} className="px-4 py-10 text-center text-red-500">
                    {error.detail ?? "Failed to load campaigns."}
                  </td>
                </tr>
              )}
              {!loading && !error && data?.results?.length === 0 && (
                <tr>
                  <td colSpan={12} className="px-4 py-10 text-center text-slate-400">
                    No campaigns match your filters.{" "}
                    <button
                      onClick={() => onParamsChange(DEFAULT_CAMPAIGN_PARAMS)}
                      className="text-primary underline"
                    >
                      Reset filters
                    </button>
                  </td>
                </tr>
              )}
              {!loading && !error && data?.results?.map((c, i) => {
                const rank = (params.page - 1) * params.page_size + i + 1;
                return (
                  <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs">{rank}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{c.company}</td>
                    <td className="px-4 py-3 text-slate-600">{c.campaign_type}</td>
                    <td className="px-4 py-3 text-slate-600">{c.channel_used}</td>
                    <td className="px-4 py-3 text-slate-600">{c.customer_segment ?? "—"}</td>
                    <td className="px-4 py-3 font-medium text-slate-700">{fmtRoi(c.roi)}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtPct(c.conversion_rate)}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtNumber(c.impressions)}</td>
                    <td className="px-4 py-3 text-slate-600">{fmtNumber(c.clicks)}</td>
                    <td className="px-4 py-3 text-slate-500">{c.duration ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(c.date)}</td>
                    {/* Creator: ◎ icon link if creator_id present, — if null.
                        List endpoint returns creator_id only — no nested creator object. */}
                    <td className="px-4 py-3 text-center">
                      {c.creator_id
                        ? (
                          <Link
                            to={`/creators/${c.creator_id}`}
                            title="View creator"
                            onClick={(e) => e.stopPropagation()}
                            className="text-primary hover:text-blue-800 text-base"
                          >
                            ◎
                          </Link>
                        )
                        : <span className="text-slate-300">—</span>
                      }
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

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