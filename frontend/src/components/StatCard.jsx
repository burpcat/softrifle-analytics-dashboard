// StatCard — KPI tile for the Dashboard grid.
//
// `trend` is optional. When provided, the caller (Dashboard.jsx) is responsible
// for formatting the label string (e.g. "+12%" or "vs last month") — StatCard
// only renders whatever string it receives. Direction controls the color/arrow.

const TREND_MAP = {
  up:   { icon: "▲", className: "text-green-600" },
  down: { icon: "▼", className: "text-red-500"   },
  flat: { icon: "→", className: "text-slate-400"  },
};

export default function StatCard({ title, value, subtitle, trend }) {
  const trendStyle = trend ? (TREND_MAP[trend.direction] ?? TREND_MAP.flat) : null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 px-6 py-5 flex flex-col gap-1 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </p>
      <p className="text-3xl font-bold text-slate-800 leading-tight">
        {value ?? "—"}
      </p>
      {subtitle && (
        <p className="text-sm text-slate-500">{subtitle}</p>
      )}
      {trendStyle && (
        <p className={`text-xs font-medium mt-1 ${trendStyle.className}`}>
          {trendStyle.icon} {trend.label}
        </p>
      )}
    </div>
  );
}