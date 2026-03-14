import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";

// One color per campaign type — hardcoded hex, Tailwind-purge-safe.
// Used for both ROI and conversion views so colors stay consistent on toggle.
const LINE_COLORS = {
  "Influencer":   "#2563eb",
  "Email":        "#7c3aed",
  "Display":      "#059669",
  "Search":       "#d97706",
  "Social Media": "#dc2626",
};

const CAMPAIGN_TYPES = Object.keys(LINE_COLORS);

export default function TrendsChart({ data }) {
  const [view, setView] = useState("roi"); // "roi" | "conversion"

  // Memoised — only recomputes when data or view changes.
  // Backend guarantees all 5 campaign type keys per month (null for gaps),
  // so the spread always produces the same keys — connectNulls handles nulls.
  const chartData = useMemo(() =>
    data.map((d) => ({
      month: d.month,
      ...(view === "roi" ? d.avg_roi_by_type : d.avg_conversion_by_type),
    })),
  [data, view]);

  const isRoi = view === "roi";

  return (
    <div>
      {/* Toggle */}
      <div className="flex gap-2 mb-4">
        {[
          { key: "roi",        label: "Avg ROI"         },
          { key: "conversion", label: "Conversion Rate"  },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${view === key
                ? "bg-primary text-white"
                : "border border-slate-200 text-slate-600 hover:bg-slate-50"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="month"
            tick={{ fontSize: 11, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 12, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
            width={48}
            tickFormatter={(v) =>
              isRoi ? `${v.toFixed(2)}x` : `${(v * 100).toFixed(1)}%`
            }
          />
          <Tooltip
            formatter={(v, name) => [
              isRoi ? `${v?.toFixed(3)}x` : `${((v ?? 0) * 100).toFixed(2)}%`,
              name,
            ]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {CAMPAIGN_TYPES.map((type) => (
            <Line
              key={type}
              type="monotone"
              dataKey={type}
              stroke={LINE_COLORS[type]}
              strokeWidth={2}
              dot={false}
              connectNulls  // draws through null gaps rather than breaking the line
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}