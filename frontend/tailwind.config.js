/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // ── Health score tiers ────────────────────────────────────────────
        // Use these aliases everywhere — never raw green-*/amber-*/red-*
        // for health scores, so the thresholds stay consistent.
        //   > 60  → health-high
        //   30–60 → health-mid
        //   < 30  → health-low
        //   null  → health-none (gray)
        "health-high": "#22c55e", // green-500
        "health-mid":  "#fbbf24", // amber-400
        "health-low":  "#ef4444", // red-500
        "health-none": "#94a3b8", // slate-400

        // ── Alert severity tiers ──────────────────────────────────────────
        // Same convention — alias only, no raw color classes for severities.
        "alert-critical": "#dc2626", // red-600
        "alert-warning":  "#f59e0b", // amber-500
        "alert-info":     "#3b82f6", // blue-500

        // ── Layout chrome ─────────────────────────────────────────────────
        sidebar:  "#0f172a", // slate-900
        content:  "#f8fafc", // slate-50

        // ── Primary action ────────────────────────────────────────────────
        primary:  "#2563eb", // blue-600
      },
    },
  },
  plugins: [],
};