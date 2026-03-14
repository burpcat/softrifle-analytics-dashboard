import { useState } from "react";
import AlertsList from "../components/AlertsList";

// Stable default params — module-level so JSON.stringify dep never fires
// spuriously in useApi.
const DEFAULT_ALERT_PARAMS = {
  page:      1,
  page_size: 20,
};

const SEVERITY_TABS = [
  { label: "All",      value: undefined   },
  { label: "Critical", value: "critical"  },
  { label: "Warning",  value: "warning"   },
  { label: "Info",     value: "info"      },
];

export default function Alerts() {
  const [params, setParams] = useState(DEFAULT_ALERT_PARAMS);

  // Merges partial updates. Strips undefined so cleared severity filter
  // doesn't linger as a ghost param. Preserves all other values including
  // false (consistent with Campaigns.jsx and Creators.jsx merge pattern).
  function handleParamsChange(updates) {
    setParams(prev => {
      const merged = { ...prev, ...updates };
      return Object.fromEntries(
        Object.entries(merged).filter(([, v]) => v !== undefined)
      );
    });
  }

  function handleTabChange(severityValue) {
    // undefined for "All" — strips severity param cleanly via merge handler
    handleParamsChange({ severity: severityValue, page: 1 });
  }

  const activeSeverity = params.severity ?? undefined;

  return (
    <div className="p-6 space-y-4 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Alerts</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Problems and opportunities flagged across campaigns and creators
        </p>
      </div>

      {/* Severity tabs — no per-tab counts. Filtered total shown in pagination row.
          Adding counts would require 3 extra fetches on every load; the right
          fix if ever needed is a backend /api/alerts/counts endpoint. */}
      <div className="flex gap-1 border-b border-slate-200">
        {SEVERITY_TABS.map(({ label, value }) => {
          const active = activeSeverity === value;
          return (
            <button
              key={label}
              onClick={() => handleTabChange(value)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
                ${active
                  ? "border-primary text-primary"
                  : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
                }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      <AlertsList params={params} onParamsChange={handleParamsChange} />
    </div>
  );
}