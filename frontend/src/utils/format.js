// Shared formatting helpers.
// Single source of truth — import from here, never redefine locally.
// Drift risk: fmtPct multiplying by 100 in one file and not another
// is the exact bug this file prevents.

export const fmtNumber = (n) =>
  n == null ? "—" : n.toLocaleString();

export const fmtRoi = (n) =>
  n == null ? "—" : `${n.toFixed(2)}x`;

// Conversion rate and engagement rate are both 0–1 decimals from the API.
// Multiply by 100 here — never at the callsite.
export const fmtPct = (n) =>
  n == null ? "—" : `${(n * 100).toFixed(1)}%`;

export function fmtFollowers(n) {
  if (n == null)      return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

// ISO date string "2021-06-15" → "Jun 15, 2021"
// Appending T00:00:00 forces local-time parsing — bare date strings parse
// as UTC midnight, which renders as the previous day in UTC-offset timezones.
export const fmtDate = (d) => {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day:   "numeric",
    year:  "numeric",
  });
};

// Case-insensitive key lookup for avg_roi_by_* objects.
// Guards against CSV casing inconsistencies (e.g. "influencer" vs "Influencer").
export function findRoi(obj, key) {
  if (!obj) return null;
  const match = Object.keys(obj).find((k) => k.toLowerCase() === key.toLowerCase());
  return match ? obj[match] : null;
}

// Transform { TypeA: 5.01, TypeB: 4.99 } → [{ name: "TypeA", value: 5.01 }, ...]
// Used by any chart that needs to iterate avg_roi_by_* objects.
export function roiObjectToArray(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([name, value]) => ({ name, value }));
}

// Alert type display labels — lookup map handles known acronyms correctly
// (e.g. "low_roi" → "Low ROI", not "Low Roi").
// Fallback handles any future types added to the AlertType enum gracefully.
const TYPE_LABELS = {
  low_roi:                "Low ROI",
  low_engagement:         "Low Engagement",
  low_conversion:         "Low Conversion",
  outreach_opportunity:   "Outreach Opportunity",
  segment_outperformance: "Segment Outperformance",
};

export const fmtAlertType = (type) =>
  TYPE_LABELS[type] ??
  type?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ??
  "—";

// Relative time for alert timestamps (created_at is a full datetime string,
// not a bare date — no timezone fix needed here).
export function relativeTime(dateStr) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  if (isNaN(diff)) return "—";
  const mins  = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (mins  < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}