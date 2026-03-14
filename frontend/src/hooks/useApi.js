import { useState, useEffect, useCallback } from "react";

/**
 * useApi(fetchFn, params)
 *
 * Generic data-fetching hook. Handles loading, error, and stale-data safety.
 *
 * @param {Function} fetchFn  - Any fetch* function from api/client.js
 * @param {Object}   params   - Query params object (or undefined for param-less endpoints)
 * @returns {{ data, loading, error, refetch }}
 *
 * Stale-data race condition:
 *   AbortController is created per effect run. If params change before a
 *   fetch resolves, the previous controller is aborted and its result is
 *   discarded — only the latest fetch can write to state.
 *
 * Dependency stability:
 *   params is serialised with sorted keys before being used as an effect
 *   dependency. This means { page:1, search:"x" } and { search:"x", page:1 }
 *   are treated as identical, avoiding spurious re-fetches when params objects
 *   are assembled in different key orders across renders.
 *
 * Manual refetch:
 *   A `tick` counter is included in the effect deps. Calling refetch()
 *   increments tick, forcing a re-fetch even if params haven't changed
 *   (e.g. a user-triggered refresh button).
 */
export default function useApi(fetchFn, params) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [tick,    setTick]    = useState(0);

  // Stable key: sort keys so insertion order doesn't cause false mismatches
  const paramKey = JSON.stringify(params, Object.keys(params ?? {}).sort());

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError(null);

    fetchFn(params, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          setData(result);
          setLoading(false);
        }
      })
      .catch(err => {
        if (!controller.signal.aborted) {
          // AbortError is not a real error — it means a newer fetch took over.
          if (err.name !== "AbortError") {
            setError(err);
            setLoading(false);
          }
        }
      });

    return () => controller.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramKey, tick]);

  const refetch = useCallback(() => setTick(t => t + 1), []);

  return { data, loading, error, refetch };
}