import { NavLink } from "react-router-dom";
import useApi from "../hooks/useApi";
import { fetchAlerts } from "../api/client";

// Stable params object defined outside the component so JSON.stringify
// always produces the same key and useApi never re-fetches unnecessarily.
const ALERT_COUNT_PARAMS = { page_size: 1 };

const NAV_ITEMS = [
  { label: "Dashboard", to: "/",          icon: "▦", end: true  },
  { label: "Creators",  to: "/creators",  icon: "◎", end: false },
  { label: "Campaigns", to: "/campaigns", icon: "▤", end: false },
  { label: "Analytics", to: "/analytics", icon: "▲", end: false },
  { label: "Alerts",    to: "/alerts",    icon: "⚠", end: false },
];

// Active / inactive class factories for NavLink
const linkClass = ({ isActive }) =>
  [
    "flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors",
    isActive
      ? "bg-slate-700 text-white"
      : "text-slate-400 hover:bg-slate-800 hover:text-white",
  ].join(" ");

export default function Sidebar() {
  // page_size:1 is the cheapest way to read `total` from the alerts endpoint.
  // The badge count reflects ALL severity levels — a known UX rough edge.
  // TODO: filter to severity=critical,warning once the API supports multi-value
  // severity params, so info-only alert counts don't trigger the red badge.
  const { data } = useApi(fetchAlerts, ALERT_COUNT_PARAMS);
  const alertTotal = data?.total ?? 0;

  return (
    <aside className="w-60 flex-shrink-0 bg-sidebar flex flex-col h-full">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-700">
        <span className="text-white font-bold text-lg tracking-tight">
          Hard<span className="text-primary">Scope</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ label, to, icon, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClass}>
            <span className="text-base leading-none">{icon}</span>
            <span className="flex-1">{label}</span>
            {/* Alert count badge — hidden when zero or still loading */}
            {label === "Alerts" && alertTotal > 0 && (
              <span className="ml-auto bg-alert-critical text-white text-xs font-semibold px-2 py-0.5 rounded-full">
                {alertTotal > 999 ? "999+" : alertTotal}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-700">
        <p className="text-slate-500 text-xs">HardScope v0.1</p>
      </div>
    </aside>
  );
}