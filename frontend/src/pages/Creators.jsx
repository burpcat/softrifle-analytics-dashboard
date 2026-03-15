import { useState } from "react";
import CreatorTable from "../components/CreatorTable";
import { DEFAULT_CREATOR_PARAMS } from "../constants";

const STANDARD_CATEGORIES = [
  "Foodies",
  "Tech Enthusiasts",
  "Health & Wellness",
  "Outdoor Adventurers",
  "Fashionistas",
];

// ---------------------------------------------------------------------------
// Add Creators modal
// ---------------------------------------------------------------------------

function AddCreatorsModal({ onClose, onSuccess }) {
  const [category, setCategory]   = useState(STANDARD_CATEGORIES[0]);
  const [customCat, setCustomCat] = useState("");
  const [keywords, setKeywords]   = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  const isCustom = category === "Other";
  const resolvedCategory = isCustom ? customCat.trim() : category;

  async function handleFetch() {
    if (isCustom && !resolvedCategory) {
      setError("Please enter a custom category name.");
      return;
    }

    setLoading(true);
    setError(null);

    const body = {
      category: resolvedCategory,
      max_results: maxResults,
      keywords: keywords
        ? keywords.split(",").map(k => k.trim()).filter(Boolean)
        : [],
    };

    try {
      const res = await fetch("/api/creators/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Something went wrong");
      }

      onSuccess(data.new_creators_added);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Panel */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">Add Creators</h2>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-slate-400 hover:text-slate-600 transition-colors text-lg leading-none disabled:opacity-40"
          >
            ✕
          </button>
        </div>

        {/* Category */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-slate-700">
            Category
          </label>
          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
            disabled={loading}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {STANDARD_CATEGORIES.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
            <option value="Other">Other (custom)</option>
          </select>
        </div>

        {/* Custom category name — shown only when Other is selected */}
        {isCustom && (
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">
              Custom category name
            </label>
            <input
              type="text"
              value={customCat}
              onChange={e => setCustomCat(e.target.value)}
              placeholder="e.g. Gamers, Pet Lovers…"
              disabled={loading}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>
        )}

        {/* Keywords */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-slate-700">
            Keywords{" "}
            <span className="font-normal text-slate-400">(optional, comma-separated)</span>
          </label>
          <input
            type="text"
            value={keywords}
            onChange={e => setKeywords(e.target.value)}
            placeholder="e.g. unboxing, gadget review"
            disabled={loading}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
          <p className="text-xs text-slate-400">
            Leave blank to use default keywords for the selected category.
          </p>
        </div>

        {/* Max results */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-slate-700">
            Creators to fetch{" "}
            <span className="font-normal text-slate-400">({maxResults})</span>
          </label>
          <input
            type="range"
            min={1}
            max={30}
            value={maxResults}
            onChange={e => setMaxResults(Number(e.target.value))}
            disabled={loading}
            className="w-full accent-blue-600 disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-slate-400">
            <span>1</span>
            <span>30</span>
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-1">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 disabled:opacity-40 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleFetch}
            disabled={loading || (isCustom && !customCat.trim())}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Fetching…
              </>
            ) : (
              "Fetch"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Creators() {
  const [params, setParams]       = useState(DEFAULT_CREATOR_PARAMS);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast]         = useState(null); // string | null

  function handleParamsChange(updates) {
    setParams(prev => {
      const merged = { ...prev, ...updates };
      return Object.fromEntries(
        Object.entries(merged).filter(([, v]) => v !== undefined)
      );
    });
  }

  function handleSuccess(newCount) {
    setShowModal(false);
    setToast(
      newCount > 0
        ? `Added ${newCount} new creator${newCount === 1 ? "" : "s"}`
        : "No new creators found — all results already exist in the database."
    );
    // Trigger a table refetch by bumping a param CreatorTable ignores but
    // treats as a dependency change — forces re-fetch without resetting filters.
    setParams(prev => ({ ...prev, _refresh: Date.now() }));
    setTimeout(() => setToast(null), 4000);
  }

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto">
      {/* Toast */}
      {toast && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50 bg-slate-800 text-white text-sm px-4 py-2.5 rounded-xl shadow-lg">
          {toast}
        </div>
      )}

      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Creators</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Browse and evaluate YouTube creators by health score, engagement, and segment
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="shrink-0 flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors mt-1"
        >
          <span className="text-base leading-none">+</span>
          Add Creators
        </button>
      </div>

      <CreatorTable params={params} onParamsChange={handleParamsChange} />

      {showModal && (
        <AddCreatorsModal
          onClose={() => setShowModal(false)}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
}