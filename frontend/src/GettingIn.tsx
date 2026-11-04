// Getting in: how admission works at a school, what to do next, and by when.
// The backend builds `card.access` (backend/enrollment/access.py). It sits beside
// the match and never changes it, so it is drawn apart from the evidence rows.
import "./getting-in.css";

export type Access = {
  status: "confirmed" | "partial" | "needs_attention" | "unknown";
  label: string;
  how: "zoned" | "choice" | "lottery" | "application";
  how_label: string;
  line: string;
  text?: string;
  deadline?: string | null;
  days_left?: number | null;
  detail?: string | null;
  detail_source?: string | null;
  source?: { type: string; path: string; as_of?: string | null } | null;
  official: { name: string; url: string; more_url?: string | null; more_name?: string | null; state?: string | null; summary?: string; next_step?: string };
  admissions_url?: string | null;
  district?: {
    name: string;
    locator_url?: string | null;
    choice_url?: string | null;
    window?: string | null;
    window_url?: string | null;
  } | null;
  zoned_prompt?: boolean;
  ask_open_seats?: boolean;
};

const HOW_LINK: Record<string, string> = {
  zoned: "How attendance areas work",
  choice: "How school choice works",
  lottery: "How the lottery works",
  application: "How private school admission works",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// App registers how a "Yes, it's mine" tap is sent, so cards need no new prop.
// That keeps this change out of the card-list code other branches are rewriting.
let sendZoned: ((schoolId: string, value: boolean) => void) | null = null;
export function onZonedTap(handler: (schoolId: string, value: boolean) => void) {
  sendZoned = handler;
}

// Read "2026-03-15" by hand: new Date() would read it as UTC and can show the day before.
function monthYear(iso?: string | null): string {
  const [year, month] = (iso ?? "").split("-").map(Number);
  return year && month ? `${MONTHS[month - 1]} ${year}` : "";
}

function fullDate(iso?: string | null): string {
  const [year, month, day] = (iso ?? "").split("-").map(Number);
  return year && month && day ? `${MONTHS[month - 1]} ${day}, ${year}` : "";
}

function sourceText(access: Access): string {
  const source = access.source;
  if (!source) return "";
  if (source.type === "parent") return "You told us this is your zoned school";
  if (source.type === "enrollment_rule") return `${access.official?.state ?? "State"} admission rule, checked ${fullDate(source.as_of)}`;
  const kind = source.type === "school_reported" ? "School-reported" : "School profile";
  return source.as_of ? `${kind}, ${monthYear(source.as_of)}` : kind;
}

// The sample and generated schools carry example.org admissions pages, which go nowhere.
function realLink(url?: string | null): string | null {
  if (!url) return null;
  try {
    return /(^|\.)example\.(org|com|net)$/.test(new URL(url).hostname) ? null : url;
  } catch {
    return null;
  }
}

function lineFor(access: Access): string {
  // "Ask about open seats" is the label of a button that isn't wired yet, so say what is known.
  if (access.status === "unknown" && !access.zoned_prompt) return `${access.how_label} · no dates or open seats on file yet`;
  return access.line;
}

function External({ href, children, title }: { href: string; children: string; title?: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" title={title}>
      {children} ↗
    </a>
  );
}

/** The Getting in row on a result card. */
export function GettingInLine({ schoolId, access }: { schoolId: string; access?: Access | null }) {
  if (!access) return null;
  const isMine = access.source?.type === "parent";
  return (
    <div className="getting-in">
      <div className="gi-head">
        <span className="gi-title">Getting in</span>
        <span className={`pill ${access.status}`}>{access.label}</span>
      </div>
      <div>
        <div className="gi-line">{lineFor(access)}</div>
        {access.detail && <div className="gi-detail">{access.detail}</div>}
        <div className="source">{access.detail_source ?? sourceText(access)}</div>
        <div className="gi-actions">
          {access.zoned_prompt && sendZoned && (
            <button type="button" onClick={() => sendZoned?.(schoolId, true)}>Yes, it's mine</button>
          )}
          {access.zoned_prompt && access.district?.locator_url && (
            <External href={access.district.locator_url} title={access.district.name}>Find my zoned school</External>
          )}
          {isMine && sendZoned && (
            <button type="button" className="texty" onClick={() => sendZoned?.(schoolId, false)}>Not my zoned school</button>
          )}
          <External href={access.official.url} title={access.official.name}>{HOW_LINK[access.how] ?? "How admission works"}</External>
        </div>
      </div>
    </div>
  );
}

/** The fuller version for the school detail panel: the cited explanation and every official link. */
export function GettingInDetail({ access }: { access?: Access | null }) {
  if (!access) return null;
  const admissions = realLink(access.admissions_url);
  const district = access.district;
  return (
    <section className="gi-detail-panel">
      <h3>Getting in</h3>
      <p>
        <span className={`pill ${access.status}`}>{access.label}</span> <strong>{lineFor(access)}</strong>
      </p>
      {/* access.text already includes the applicant numbers, so they aren't repeated here. */}
      {access.text && <p>{access.text}</p>}
      {access.official.summary && <p>{access.official.summary}</p>}
      {access.official.next_step && <p><strong>Next step:</strong> {access.official.next_step}</p>}
      {district?.window && (
        <p>
          {district.window}{" "}
          {district.window_url && <External href={district.window_url}>{district.name}</External>}
        </p>
      )}
      <div className="gi-actions">
        <External href={access.official.url}>{access.official.name}</External>
        {access.official.more_url && <External href={access.official.more_url}>{access.official.more_name ?? "More details"}</External>}
        {district?.choice_url && <External href={district.choice_url}>{`${district.name} school choice`}</External>}
        {district?.locator_url && access.how === "zoned" && <External href={district.locator_url}>Find my school by address</External>}
        {admissions && <External href={admissions}>School's admissions page</External>}
      </div>
      <p className="source">
        {sourceText(access)}
        {access.detail_source ? `; applicant numbers: ${access.detail_source}` : ""}. We explain how admission works; we never
        estimate a family's chances.
      </p>
    </section>
  );
}

/** One line for a school in the saved list, which the backend sorts by deadline. */
export function SavedDeadline({ access }: { access?: Access | null }) {
  if (!access) return null;
  return (
    <span className="gi-saved">
      <span className={`pill ${access.status}`}>{access.label}</span> {lineFor(access)}
    </span>
  );
}
