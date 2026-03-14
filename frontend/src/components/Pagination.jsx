// Shared pagination control — used by CreatorTable, CampaignTable, AlertsList.
// Props are identical across all three consumers.

export default function Pagination({ page, pageSize, total, onParamsChange }) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between mt-4 text-sm text-slate-600">
      <span>{total.toLocaleString()} total</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onParamsChange({ page: page - 1 })}
          className="px-3 py-1 rounded-lg border border-slate-200 hover:bg-slate-50
            disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ← Prev
        </button>
        <span className="px-2 text-slate-500">
          {page} / {totalPages}
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => onParamsChange({ page: page + 1 })}
          className="px-3 py-1 rounded-lg border border-slate-200 hover:bg-slate-50
            disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  );
}