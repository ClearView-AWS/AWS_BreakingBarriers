// Getting in: how admission works at a school, what to do next, and by when.
// The backend builds `card.access` (backend/enrollment/access.py). It sits beside
// the match and never changes it, so it is drawn apart from the evidence rows.
import "./getting-in.css";
import { formatDate, t } from "./i18n";

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
  official: { name: string; url: string; more_url?: string | null; summary?: string; next_step?: string };
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

function howLink(how: string): string {
  const key = `gi.how.${how}`;
  const text = t(key);
  return text === key ? t("gi.how") : text;
}

// App registers how a "Yes, it's mine" tap is sent, so cards need no new prop.
// That keeps this change out of the card-list code other branches are rewriting.
let sendZoned: ((schoolId: string, value: boolean) => void) | null = null;
export function onZonedTap(handler: (schoolId: string, value: boolean) => void) {
  sendZoned = handler;
}

// Dates in the UI language. formatDate reads "2026-03-15" by hand so it never shifts a day.
const monthYear = (iso?: string | null) => formatDate(iso, false);
const fullDate = (iso?: string | null) => formatDate(iso, true);

function sourceText(access: Access): string {
  const source = access.source;
  if (!source) return "";
  if (source.type === "parent") return t("gi.src_parent");
  if (source.type === "enrollment_rule") return t("gi.src_rule", { date: fullDate(source.as_of) });
  const kind = source.type === "school_reported" ? t("gi.src_school") : t("gi.src_profile");
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
  if (access.status === "unknown" && !access.zoned_prompt) return t("gi.no_dates", { how: access.how_label });
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
        <span className="gi-title">{t("gi.title")}</span>
        <span className={`pill ${access.status}`}>{access.label}</span>
      </div>
      <div>
        <div className="gi-line">{lineFor(access)}</div>
        {access.detail && <div className="gi-detail">{access.detail}</div>}
        <div className="source">{access.detail_source ?? sourceText(access)}</div>
        <div className="gi-actions">
          {access.zoned_prompt && sendZoned && (
            <button type="button" onClick={() => sendZoned?.(schoolId, true)}>{t("gi.yes_mine")}</button>
          )}
          {access.zoned_prompt && access.district?.locator_url && (
            <External href={access.district.locator_url} title={access.district.name}>{t("gi.find_zoned")}</External>
          )}
          {isMine && sendZoned && (
            <button type="button" className="texty" onClick={() => sendZoned?.(schoolId, false)}>{t("gi.not_mine")}</button>
          )}
          <External href={access.official.url} title={access.official.name}>{howLink(access.how)}</External>
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
      <h3>{t("gi.title")}</h3>
      <p>
        <span className={`pill ${access.status}`}>{access.label}</span> <strong>{lineFor(access)}</strong>
      </p>
      {/* access.text already includes the applicant numbers, so they aren't repeated here. */}
      {access.text && <p>{access.text}</p>}
      {access.official.summary && <p>{access.official.summary}</p>}
      {access.official.next_step && <p><strong>{t("gi.next_step")}</strong> {access.official.next_step}</p>}
      {district?.window && (
        <p>
          {district.window}{" "}
          {district.window_url && <External href={district.window_url}>{district.name}</External>}
        </p>
      )}
      <div className="gi-actions">
        <External href={access.official.url}>{access.official.name}</External>
        {access.official.more_url && <External href={access.official.more_url}>{t("gi.fdoe")}</External>}
        {district?.choice_url && <External href={district.choice_url}>{t("gi.district_choice", { district: district.name })}</External>}
        {district?.locator_url && access.how === "zoned" && <External href={district.locator_url}>{t("gi.find_zoned")}</External>}
        {admissions && <External href={admissions}>{t("gi.admissions")}</External>}
      </div>
      <p className="source">
        {sourceText(access)}
        {access.detail_source ? `; ${t("gi.applicants", { source: access.detail_source })}` : ""}. {t("gi.never_odds")}
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
