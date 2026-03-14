import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

// Hardcoded hex — Tailwind-purge-safe, consistent across charts.
const SEGMENT_COLORS = {
  "Tech Enthusiasts":   "#2563eb",
  "Foodies":            "#059669",
  "Health & Wellness":  "#7c3aed",
  "Outdoor Adventurers":"#d97706",
  "Fashionistas":       "#dc2626",
};

// Fallback color for any unexpected segment key
const FALLBACK_COLOR = "#94a3b8";

function toChartData(segmentBreakdown) {
  return Object.entries(segmentBreakdown).map(([name, value]) => ({ name, value }));
}

export default function SegmentPieChart({ segmentBreakdown }) {
  if (!segmentBreakdown || !Object.keys(segmentBreakdown).length) {
    return <p className="text-slate-400 text-sm py-4">No segment data available.</p>;
  }

  const chartData = toChartData(segmentBreakdown);
  const total     = chartData.reduce((sum, d) => sum + d.value, 0);

  return (
    // Relative wrapper enables the CSS-overlay center label.
    // cx/cy are internal to Recharts' Pie — not reliably accessible from outside.
    <div className="relative">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={64}
            outerRadius={96}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((entry) => (
              <Cell
                key={entry.name}
                fill={SEGMENT_COLORS[entry.name] ?? FALLBACK_COLOR}
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [
              `${value.toLocaleString()} (${((value / total) * 100).toFixed(1)}%)`,
              name,
            ]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Center label — CSS overlay avoids cx/cy SVG coordinate math.
          pointerEvents: none so tooltip interaction on the pie is unaffected. */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{ pointerEvents: "none" }}
      >
        <span className="text-2xl font-bold text-slate-800">
          {total.toLocaleString()}
        </span>
        <span className="text-xs text-slate-500 mt-0.5">campaigns</span>
      </div>
    </div>
  );
}