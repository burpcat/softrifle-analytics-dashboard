const BASE_URL = "/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Build a query string from a params object.
 * Filters out null, undefined, and empty-string values so no ghost params
 * (e.g. ?search=) are sent to the backend.
 */
function buildQuery(params = {}) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );
  if (!entries.length) return "";
  return "?" + new URLSearchParams(entries).toString();
}

/**
 * Base fetch wrapper.
 * - Accepts an AbortSignal so callers can cancel in-flight requests.
 * - Throws a structured error with .status and .detail on non-2xx responses
 *   so components can branch on error type (404 vs 500 vs network failure).
 */
async function apiFetch(path, signal) {
  const res = await fetch(BASE_URL + path, { signal });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail ?? res.statusText);
    err.status = res.status;
    err.detail = body.detail ?? null;
    throw err;
  }

  return res.json();
}

// ── Endpoint functions ────────────────────────────────────────────────────────
// Each accepts an optional AbortSignal forwarded from useApi's AbortController.
// Params are passed as plain objects; buildQuery handles serialisation.

export const fetchCreators         = (p, sig) => apiFetch(`/creators${buildQuery(p)}`, sig);
export const fetchCreator          = (id, sig) => apiFetch(`/creators/${id}`, sig);
export const fetchCampaigns        = (p, sig)  => apiFetch(`/campaigns${buildQuery(p)}`, sig);
export const fetchCampaign         = (id, sig) => apiFetch(`/campaigns/${id}`, sig);
export const fetchAnalyticsSummary = (_, sig)  => apiFetch("/analytics/summary", sig);
export const fetchChannelComparison= (_, sig)  => apiFetch("/analytics/channel-comparison", sig);
export const fetchTrends           = (_, sig)  => apiFetch("/analytics/trends", sig);
export const fetchAlerts           = (p, sig)  => apiFetch(`/alerts${buildQuery(p)}`, sig);