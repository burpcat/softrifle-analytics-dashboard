// Shared default params for API calls.
// Both the page (state initialisation) and the table (reset behaviour)
// import from here — neither depends on the other for constants.

export const DEFAULT_CREATOR_PARAMS = {
  page:       1,
  page_size:  20,
  sort_by:    "health_score",
  sort_order: "desc",
};

export const DEFAULT_CAMPAIGN_PARAMS = {
  page:       1,
  page_size:  20,
  sort_by:    "roi",
  sort_order: "desc",
};