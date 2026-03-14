import { useState } from "react";
import CampaignTable from "../components/CampaignTable";
import { DEFAULT_CAMPAIGN_PARAMS } from "../constants";

export default function Campaigns() {
  const [params, setParams] = useState(DEFAULT_CAMPAIGN_PARAMS);

  // Merges partial updates from CampaignTable (filters, sort, page changes).
  // Strips undefined so cleared filters don't linger as ghost keys.
  // Preserves false — needed for has_creator: false ("Without Creator" toggle).
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
        <h1 className="text-2xl font-bold text-slate-800">Campaigns</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Filter and explore campaigns by type, channel, segment, and ROI
        </p>
      </div>
      <CampaignTable params={params} onParamsChange={handleParamsChange} />
    </div>
  );
}