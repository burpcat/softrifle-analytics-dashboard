// HealthScoreBadge — color-coded pill for creator health scores.
//
// Thresholds:  > 60  → high (green)
//              30–60 → mid  (amber)
//              < 30  → low  (red)
//              null  → none (gray)
//
// IMPORTANT: All class names below are complete hardcoded strings.
// Do not interpolate or concatenate them — Tailwind's scanner won't
// detect partial strings and they will be purged in production builds.

const TIER_MAP = {
  high: {
    bg:   "bg-green-100",
    text: "text-green-700",
    ring: "ring-green-300",
  },
  mid: {
    bg:   "bg-amber-100",
    text: "text-amber-700",
    ring: "ring-amber-300",
  },
  low: {
    bg:   "bg-red-100",
    text: "text-red-700",
    ring: "ring-red-300",
  },
  none: {
    bg:   "bg-slate-100",
    text: "text-slate-500",
    ring: "ring-slate-300",
  },
};

const SIZE_MAP = {
  sm: "text-xs px-2 py-0.5",
  md: "text-sm px-2.5 py-0.5",
  lg: "text-base px-3 py-1 font-semibold",
};

function getTier(score) {
  if (score == null) return "none";
  if (score > 60)    return "high";
  if (score >= 30)   return "mid";
  return "low";
}

export default function HealthScoreBadge({ score, size = "md" }) {
  // Null guard before toFixed — score.toFixed(1) would throw on null/undefined.
  const display = score == null ? "N/A" : score.toFixed(1);
  const tier    = getTier(score);
  const colors  = TIER_MAP[tier];
  const sizing  = SIZE_MAP[size] ?? SIZE_MAP.md;

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ring-1 ring-inset
        ${colors.bg} ${colors.text} ${colors.ring} ${sizing}`}
    >
      {display}
    </span>
  );
}