import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  LabelList, ResponsiveContainer,
} from "recharts";

// Transform API shape → Recharts-ready flat objects
function toChartData(data) {
  return data.map((d) => ({
    channel:      d.channel,
    influencer:   d.influencer_avg_roi,
    nonInfluencer: d.non_influencer_avg_roi,
    lift:         d.lift_percentage, // decimal — 0.0077 = 0.77%
  }));
}

// Custom label rendered above the influencer bar.
// Guards null — LabelList renders the string "null" if formatter returns null.
// Negative lift renders in red, positive in green, zero/null hidden.
function LiftLabel({ x, y, width, value }) {
  if (value == null) return null;
  const pct     = (value * 100).toFixed(2);
  const display = value >= 0 ? `+${pct}%` : `${pct}%`;
  const color   = value > 0 ? "#059669" : value < 0 ? "#dc2626" : "#94a3b8";
  return (
    <text
      x={x + width / 2}
      y={y - 4}
      textAnchor="middle"
      fill={color}
      fontSize={10}
      fontWeight={600}
    >
      {display}
    </text>
  );
}

export default function ChannelComparisonChart({ data }) {
  if (!data?.length) {
    return <p className="text-slate-400 text-sm py-4">No channel data available.</p>;
  }

  const chartData = toChartData(data);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} margin={{ top: 24, right: 16, left: 0, bottom: 0 }}>
        <XAxis
          dataKey="channel"
          tick={{ fontSize: 12, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[
            (min) => Math.min(4.9, Math.floor(min * 10) / 10),
            (max) => Math.max(5.1, Math.ceil(max  * 10) / 10),
          ]}
          tick={{ fontSize: 12, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
          width={40}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <Tooltip
          formatter={(v, name) => [
            `${v.toFixed(3)}x`,
            name === "influencer" ? "Influencer Avg ROI" : "Non-Influencer Avg ROI",
          ]}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
        />
        <Legend
          formatter={(v) => v === "influencer" ? "Influencer" : "Non-Influencer"}
          wrapperStyle={{ fontSize: 12 }}
        />
        <Bar dataKey="influencer" fill="#2563eb" radius={[4, 4, 0, 0]} barSize={20}>
          {/* Lift label only on influencer bar — non-influencer has no lift to show */}
          <LabelList dataKey="lift" content={<LiftLabel />} />
        </Bar>
        <Bar dataKey="nonInfluencer" fill="#94a3b8" radius={[4, 4, 0, 0]} barSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}