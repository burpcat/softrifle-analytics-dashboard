import { useState } from "react";
import CreatorTable from "../components/CreatorTable";
import { DEFAULT_CREATOR_PARAMS } from "../constants";

export default function Creators() {
  const [params, setParams] = useState(DEFAULT_CREATOR_PARAMS);

  // Merges partial updates from CreatorTable (filters, sort, page changes).
  // Strips undefined values so cleared filters don't linger as ghost keys —
  // FilterBar sends undefined to signal "remove this param".
  function handleParamsChange(updates) {
    setParams(prev => {
      const merged = { ...prev, ...updates };
      return Object.fromEntries(
        Object.entries(merged).filter(([, v]) => v !== undefined)
      );
    });
  }

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Creators</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Browse and evaluate YouTube creators by health score, engagement, and segment
        </p>
      </div>
      <CreatorTable params={params} onParamsChange={handleParamsChange} />
    </div>
  );
}