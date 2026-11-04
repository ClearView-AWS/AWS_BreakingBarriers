export const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  needs_attention: "Needs attention",
  unknown: "Unknown",
};

export const SOURCE_LABEL: Record<string, string> = {
  state_data: "State data",
  school_reported: "School-reported",
  school_website: "School website",
  parent_reviews: "Parent reviews",
  program: "Nearby program",
  funding_rule: "Scholarship rule",
};

export const LEVEL: Record<string, string> = {
  p: "Pre-K",
  e: "Elementary",
  m: "Middle",
  h: "High",
};

export const STRENGTH_CYCLE = {
  require: "prefer",
  prefer: "avoid",
  avoid: "require",
} as const;

export const STRENGTH_LABEL = {
  require: "Must have",
  prefer: "Nice to have",
  avoid: "Avoid",
} as const;
