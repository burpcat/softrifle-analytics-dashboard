import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import useApi from "../hooks/useApi";
import {
  fetchChannelComparison, fetchTrends, fetchAnalyticsSummary,
} from "../api/client";
import ChannelComparisonChart from "../components/ChannelComparisonChart";
import TrendsChart            from "../components/TrendsChart";
import SegmentPieChart        from "../components/SegmentPieChart";
import { roiObjectToArray }   from "../utils/format";

// ── Shared Y axis domain (function form — never clips, zooms when data is tight)
const roiDomain = [
  (min) => Math.min(4.9, Math.floor(min * 10) / 10),
  (max) => Math.max(5.1, Math.ceil(max  * 10) / 10),
];

// Consistent bar color across both horizontal charts on this page
const BAR_COLORS = [
  "#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626",
];

// ── Reusable card shell — keeps layout stable while sections load independently
function CardShell({ title, children }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      {title && (
        <h2 className="text-sm font-semibold text-slate-700 mb-4">{title}</h2>
      )}
      {children}
    </div>
  );
}

function SectionLoading() {
  return <p className="text-slate-400 text-sm py-6 text-center">Loading…</p>;
}

function SectionError({ error }) {
  return (
    <p className="text-red-500 text-sm py-6 text-center">
      {error?.detail ?? "Failed to load data."}
    </p>
  );
}

// ── Internal chart components (single-use, inline — not worth separate files)

function HorizontalRoiChart({ data }) {
  if (!data?.length) return <p className="text-slate-400 text-sm py-4">No data.</p>;
  return (
    <ResponsiveContainer width="100%" height={data.length * 44 + 16}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 48, left: 8, bottom: 0 }}
      >
        <XAxis
          type="number"
          domain={roiDomain}
          tick={{ fontSize: 11, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v.toFixed(2)}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={130}
          tick={{ fontSize: 12, fill: "#475569" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(v) => [`${v.toFixed(3)}x`, "Avg ROI"]}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={18}>
          {data.map((_, i) => (
            <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Derived channel insight ───────────────────────────────────────────────────
// Only counts channels where lift_percentage is non-null (both avgs present).
// Null channels are excluded from both numerator and denominator so the
// fraction is accurate rather than artificially deflated.
function channelInsight(results) {
  if (!results?.length) return null;
  const calculable    = results.filter((d) => d.lift_percentage != null);
  const outperforming = calculable.filter((d) => d.lift_percentage > 0).length;
  if (!calculable.length) return null;
  return `Influencer campaigns outperform non-influencer on ${outperforming} of ${calculable.length} channels with comparable data.`;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Analytics() {
  const {
    data: channelData, loading: channelLoading, error: channelError,
  } = useApi(fetchChannelComparison);

  const {
    data: trendsData, loading: trendsLoading, error: trendsError,
  } = useApi(fetchTrends);

  const {
    data: summary, loading: summaryLoading, error: summaryError,
  } = useApi(fetchAnalyticsSummary);

  const insight        = channelData ? channelInsight(channelData.results) : null;
  const segmentRoiData = roiObjectToArray(summary?.avg_roi_by_segment);
  const typeRoiData    = roiObjectToArray(summary?.avg_roi_by_campaign_type);

  return (
    <div className="p-6 space-y-5 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Analytics</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Channel performance, trends, and segment breakdowns
        </p>
      </div>

      {/* 1 — Channel comparison */}
      <CardShell title="Influencer vs Non-Influencer ROI by Channel">
        {channelLoading && <SectionLoading />}
        {channelError   && <SectionError error={channelError} />}
        {!channelLoading && !channelError && (
          <>
            <ChannelComparisonChart data={channelData?.results} />
            {insight && (
              <p className="text-xs text-slate-500 mt-3 border-t border-slate-100 pt-3">
                {insight}
              </p>
            )}
          </>
        )}
      </CardShell>

      {/* 2 — ROI trends over time */}
      <CardShell title="ROI and Conversion Trends Over Time">
        {trendsLoading && <SectionLoading />}
        {trendsError   && <SectionError error={trendsError} />}
        {!trendsLoading && !trendsError && trendsData && (
          <TrendsChart data={trendsData.results} />
        )}
      </CardShell>

      {/* 3 — Segment analysis: pie + ROI side by side */}
      <div className="grid grid-cols-2 gap-5">
        <CardShell title="Campaign Distribution by Segment">
          {summaryLoading && <SectionLoading />}
          {summaryError   && <SectionError error={summaryError} />}
          {!summaryLoading && !summaryError && (
            <SegmentPieChart segmentBreakdown={summary?.segment_breakdown} />
          )}
        </CardShell>

        <CardShell title="Avg ROI by Segment">
          {summaryLoading && <SectionLoading />}
          {summaryError   && <SectionError error={summaryError} />}
          {!summaryLoading && !summaryError && (
            <HorizontalRoiChart data={segmentRoiData} />
          )}
        </CardShell>
      </div>

      {/* 4 — ROI by campaign type */}
      <CardShell title="Avg ROI by Campaign Type">
        {summaryLoading && <SectionLoading />}
        {summaryError   && <SectionError error={summaryError} />}
        {!summaryLoading && !summaryError && (
          <HorizontalRoiChart data={typeRoiData} />
        )}
      </CardShell>
    </div>
  );
}