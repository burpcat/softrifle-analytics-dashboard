// AlertBadge — color-coded severity pill for alerts.
//
// IMPORTANT: All class names below are complete hardcoded strings.
// Do not interpolate or concatenate them — Tailwind's scanner won't
// detect partial strings and they will be purged in production builds.

const SEVERITY_MAP = {
  critical: {
    bg:    "bg-red-100",
    text:  "text-red-700",
    ring:  "ring-red-300",
    label: "Critical",
  },
  warning: {
    bg:    "bg-amber-100",
    text:  "text-amber-700",
    ring:  "ring-amber-300",
    label: "Warning",
  },
  info: {
    bg:    "bg-blue-100",
    text:  "text-blue-700",
    ring:  "ring-blue-300",
    label: "Info",
  },
};

// Unknown severity falls back to info style — never crashes, never renders blank.
const FALLBACK = SEVERITY_MAP.info;

export default function AlertBadge({ severity }) {
  const style = SEVERITY_MAP[severity] ?? FALLBACK;

  return (
    <span
      className={`inline-flex items-center rounded-full text-xs font-medium px-2.5 py-0.5
        ring-1 ring-inset ${style.bg} ${style.text} ${style.ring}`}
    >
      {style.label}
    </span>
  );
}