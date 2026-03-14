import { Link } from "react-router-dom";
import useApi from "../hooks/useApi";
import { fetchAlerts } from "../api/client";
import AlertBadge from "./AlertBadge";
import Pagination from "./Pagination";
import { relativeTime, fmtAlertType } from "../utils/format";

export default function AlertsList({ params, onParamsChange }) {
  const { data, loading, error } = useApi(fetchAlerts, params);

  if (loading) {
    return (
      <p className="text-slate-400 text-sm py-10 text-center">Loading alerts…</p>
    );
  }
  if (error) {
    return (
      <p className="text-red-500 text-sm py-10 text-center">
        {error.detail ?? "Failed to load alerts."}
      </p>
    );
  }
  if (!data?.results?.length) {
    return (
      <p className="text-slate-400 text-sm py-10 text-center">No alerts found.</p>
    );
  }

  return (
    <div>
      <ul className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100 overflow-hidden">
        {data.results.map((alert) => (
          <li key={alert.id} className="px-5 py-4 flex items-start gap-4">
            {/* Severity badge */}
            <div className="pt-0.5 flex-shrink-0">
              <AlertBadge severity={alert.severity} />
            </div>

            {/* Body */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-700">
                  {fmtAlertType(alert.type)}
                </span>
                <span className="text-xs text-slate-400">
                  {relativeTime(alert.created_at)}
                </span>
              </div>
              {/* Full message — not truncated. No detail page exists; this is the detail. */}
              <p className="text-sm text-slate-600 mt-0.5">{alert.message}</p>

              {/* Links / references */}
              <div className="flex items-center gap-4 mt-1.5 text-xs">
                {alert.creator_id && (
                  <Link
                    to={`/creators/${alert.creator_id}`}
                    className="text-primary hover:underline font-medium"
                  >
                    View creator →
                  </Link>
                )}
                {/* No campaign detail page — show ID as plain reference only */}
                {alert.campaign_id && (
                  <span className="text-slate-400 font-mono">
                    Campaign: {alert.campaign_id.slice(0, 8)}
                  </span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <Pagination
        page={params.page}
        pageSize={params.page_size}
        total={data.total}
        onParamsChange={onParamsChange}
      />
    </div>
  );
}