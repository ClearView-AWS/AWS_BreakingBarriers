// Names for evidence statuses, sources and criteria. Shared by the chat blocks and the
// List / Map / Compare views so a school reads the same everywhere.
import type { Criterion } from "./types";

export const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  needs_attention: "Needs attention",
  unknown: "Unknown",
};

export const STATUS_MARK: Record<string, string> = { confirmed: "✓", partial: "~", needs_attention: "!", unknown: "?" };

export const SOURCE_LABEL: Record<string, string> = {
  state_data: "State data",
  school_reported: "School-reported",
  school_website: "School website",
  parent_reviews: "Parent reviews",
  community: "Parents say",
  program: "Nearby program",
  funding_rule: "Scholarship rule",
  computed: "Computed from the school's location",
};

/** The filter's name ("STEM-focused"), falling back to the parent's words for anything that maps to no filter. */
export function nameOf(item: Pick<Criterion, "text" | "label">): string {
  return item.label || item.text;
}
