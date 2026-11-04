// Names for evidence statuses, sources and criteria. Shared by the chat blocks and the
// List / Map views so a school reads the same everywhere, in the parent's language.
import { t } from "./i18n";
import type { Criterion } from "./types";

export const STATUS_MARK: Record<string, string> = { confirmed: "✓", partial: "~", needs_attention: "!", unknown: "?" };

/** "Confirmed", "Needs attention"... in the UI language. Unknown codes show as written. */
export function statusLabel(status: string): string {
  const key = `status.${status}`;
  const text = t(key);
  return text === key ? status : text;
}

/** "School-reported", "Nearby program"... in the UI language. Unknown types show as written. */
export function sourceLabel(type: string): string {
  const key = `source.${type}`;
  const text = t(key);
  return text === key ? type : text;
}

/** The filter's name ("STEM-focused"), falling back to the parent's words for anything that maps to no filter. */
export function nameOf(item: Pick<Criterion, "text" | "label">): string {
  return item.label || item.text;
}
