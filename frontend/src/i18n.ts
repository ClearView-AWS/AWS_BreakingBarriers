// The UI's own words in the parent's language. Everything the Guide writes is translated by the
// backend with the reply; these are the buttons, tabs and labels around it. English lives here;
// other languages come from POST /api/ui-text (Amazon Translate), once per language, cached.
import { useEffect, useState } from "react";

export const EN = {
  // labels.ts
  "status.confirmed": "Confirmed",
  "status.partial": "Partial",
  "status.needs_attention": "Needs attention",
  "status.unknown": "Unknown",
  "source.state_data": "State data",
  "source.school_reported": "School-reported",
  "source.school_website": "School website",
  "source.parent_reviews": "Parent reviews",
  "source.community": "Parents say",
  "source.program": "Nearby program",
  "source.funding_rule": "Scholarship rule",
  "source.computed": "Computed from the school's location",
  // App.tsx
  "app.tagline": "Washington OSPI + Florida demo · facts come from the data",
  "app.search": "Search",
  "app.saved": "Saved ({n})",
  "app.community": "Community",
  "app.demo_controls": "Demo controls",
  "app.saved_title": "Saved schools",
  "app.saved_empty": "Save a school from a result card. The visit list is built from what is still unknown.",
  "app.checklist": "Visit checklist",
  "app.back_results": "Back to results",
  "app.all_schools": "All schools",
  "app.error_status": "Something went wrong ({status}). Try again.",
  "app.error": "Something went wrong. Try again.",
  "a11y.skip_main": "Skip to main content",
  "a11y.skip_composer": "Skip to message box",
  "a11y.read_aloud": "Read aloud",
  "a11y.stop_reading": "Stop reading",
  "a11y.evidence_grid": "Evidence grid",
  "a11y.evidence_grid_help": "Every cell cites where the answer came from.",
  "a11y.school_col": "School",
  "a11y.no_cell": "No evidence on file",
  "a11y.saved_help": "Keep the ones worth a closer look. Visit questions come from facts still unknown.",
  "a11y.thinking": "Looking for schools",
  "a11y.close_details": "Close details",
  "a11y.open_school": "Open details for {name}",

  // Chat.tsx
  "chat.guide": "Guide",
  "chat.intro": "Tell me the grade, city, and what matters most. Or pick an example to start.",
  "chat.looking": "Looking…",
  "chat.compare_pair": "Compare {a} and {b}",
  "chat.compare_one": "Pick one more school to compare with {name}.",
  "chat.clear": "Clear",
  "chat.ask_label": "Ask about these schools or change your search",
  "chat.ask_placeholder": "Ask about these schools, like “does #2 have a bus?”, or change your search",
  "chat.describe": "Describe the school you need",
  "chat.send": "Send",
  // blocks.tsx
  "blocks.read_from": "Read from {language} · translated with Amazon Translate",
  "blocks.your_search": "Your search",
  "blocks.you_said": "You said: “{text}”",
  "blocks.change_strength": "Change how much this matters",
  "strength.require": "require",
  "strength.prefer": "prefer",
  "strength.avoid": "avoid",
  "kind.grade": "grade",
  "kind.city": "city",
  "kind.type": "type",
  "blocks.remove": "Remove {name}",
  "blocks.earlier_one": "Earlier results: {n} school",
  "blocks.earlier_other": "Earlier results: {n} schools",
  "blocks.earlier_for": "for {about}",
  "blocks.show": "Show",
  "blocks.earlier_hide": "Earlier results · Hide",
  "blocks.group_gaps": "Missing a fact we can ask about",
  "blocks.group_missed": "Missed a must-have",
  "blocks.show_fewer": "Show fewer",
  "blocks.show_all": "Show all {total}",
  "blocks.more_one": "{n} more match",
  "blocks.more_other": "{n} more matches",
  "blocks.rest_gaps": "{n} missing a fact",
  "blocks.rest_missed": "{n} missed a must-have",
  "level.p": "Pre-K",
  "level.e": "Elementary",
  "level.m": "Middle",
  "level.h": "High",
  "type.public": "Public",
  "type.private": "Private",
  "type.charter": "Charter",
  "blocks.miles": "{n} miles",
  "blocks.at_a_glance": "Evidence at a glance",
  "blocks.not_on_file_ask": "Not on file. Ask the school.",
  "blocks.ask_short": "ask",
  "blocks.hide_evidence": "Hide evidence",
  "blocks.show_evidence": "Show evidence",
  "blocks.save": "Save",
  "blocks.selected": "Selected",
  "blocks.compare": "Compare",
  "blocks.cost_after": "Cost after scholarships",
  "blocks.community": "Community",
  "blocks.thumbs_up": "Thumbs up",
  "blocks.thumbs_down": "Thumbs down",
  "reason.too_far": "Too far",
  "reason.too_expensive": "Too expensive",
  "reason.missing_program": "Missing a program",
  "reason.wrong_grade": "Wrong grade",
  "blocks.discussed_one": "{n} parent discussed {topic} here",
  "blocks.discussed_other": "{n} parents discussed {topic} here",
  "blocks.asked_one": "{n} parent asked about {topic} this month",
  "blocks.asked_other": "{n} parents asked about {topic} this month",
  "blocks.no_value": "No value on file",
  "blocks.as_of": "as of {date}",
  "blocks.confidence": "{level} confidence",
  "blocks.ask_school": "Ask the school",
  "blocks.ask_parents": "Ask parents at this school",
  "call.button_one": "📞 Have AI call {school} · {n} question not on file",
  "call.button_other": "📞 Have AI call {school} · {n} questions not on file",
  "call.hint": "An AI assistant calls our demo handset (206-535-0596), never a real school office, asks every open question, and updates this card.",
  "call.dialing": "Calling {school}…",
  "call.in_call": "On the phone with {school}",
  "call.completed": "Call finished",
  "call.ended": "The school hung up",
  "call.no_answer": "No one answered. We emailed the questions instead.",
  "call.declined": "The school preferred not to be transcribed. We emailed the questions instead.",
  "call.failed": "The call didn't go through. We emailed the questions instead.",
  "call.off": "Phone calls are off in this build. We emailed the questions instead.",
  "call.blocked": "Call not placed for {school}. Questions go by email instead.",
  "call.ai": "AI assistant",
  "call.school": "Demo handset (not a real school line)",
  "call.asking": "Asking for {n} parents",
  "call.learned": "What the school said",
  "call.updated": "Updated this school's card.",
  "call.no_answers": "Nothing on the call could be confirmed, so the card stays as it was.",
  "call.close": "Close",
  "blocks.cost_title": "Cost after likely scholarships",
  "blocks.tuition": "Tuition",
  "blocks.official_page": "Official page",
  "blocks.reviews_by_topic": "Reviews by topic",
  "blocks.reviews_note": "Review scores in the file are sentiment, not stars, so they are not shown as a rating.",
  "blocks.verified": "Verified {verified}",
  "blocks.source": "Source: {cite}",
  "blocks.listed_tuition": "Listed tuition: ${n}. This is not a net price.",
  "blocks.conflict": "Website says {website}; the profile says {profile}.",
  "blocks.rating": "summary rating {rating}",
  "blocks.rating_unknown": "unknown",
  "blocks.synthetic": "synthetic profile",
  "blocks.review_counts": "{positive} positive · {negative} negative",
  "blocks.review_range": "{start} to {end}",
  // components/Brief.tsx and components/QuestionPrompt.tsx (shown in the chat before the first search)
  "brief.label": "Search brief",
  "brief.title": "Here’s what I’ll look for",
  "brief.approve": "Looks right — search",
  "brief.must": "Must have",
  "brief.nice": "Nice to have",
  "brief.avoid": "Avoid",
  "brief.hint": "Tap a need to cycle must / nice / avoid. Remove anything that doesn’t belong.",
  "brief.cycle": "Cycle strength",
  "questions.quick_one": "One quick question",
  "questions.quick_other": "{n} quick questions",
  "questions.skip": "Just show me results",
  // the two-school comparison
  "compare.not_on_file": "Not on file",
  "compare.nearby_program": "Nearby program: {name}",
  "compare.until": "Until {time}",
  "compare.match": "Match",
  "compare.match_value": "{pct}% · verified {verified}",
  "compare.getting_in": "Getting in",
  "compare.distance": "Distance",
  "compare.distance_value": "{n} miles from the city center",
  "compare.type": "Type",
  "compare.tuition": "Listed tuition",
  "compare.tuition_value": "${n} a year",
  "compare.none_listed": "None listed",
  "compare.community": "Parent community",
  "compare.no_threads": "No threads yet",
  "compare.threads_one": "{n} thread",
  "compare.threads_other": "{n} threads",
  "compare.differ": "Where they differ",
  "compare.all_same": "They match on everything on file",
  "compare.same": "Same for both: {rows}",
  // Views.tsx
  "views.list": "List",
  "views.map": "Map",
  "views.label": "Results view",
  "views.hint_distance": "You mentioned distance, so the map may help.",
  "views.hint_spread": "These schools are spread across about {n} miles, so the map may help.",
  "views.show_map": "Show map",
  "views.search_area": "Search area",
  "views.search_this_area": "Search this area",
  "views.drag_you": "Drag to move the search area, then tap Search this area",
  "views.program_fills": "{need} at {where} · {miles} mi",
  "views.a_need": "a need",
  "views.nearby_program": "Nearby program: {name}",
  "views.pin_title": "{name}, {pct}% match",
  "views.pin_missed": "missed a must-have",
  "views.on_map_one": "{n} school on the map.",
  "views.on_map_other": "{n} schools on the map.",
  "views.numbers": "The top 5 from the list, numbered the same way.",
  "views.programs_note": "◆ marks a nearby program that fills a gap, with a dashed line to its school.",
  "views.unplaced_one": "{n} school has no map point and is only in the list.",
  "views.unplaced_other": "{n} schools have no map point and are only in the list.",
  "views.map_label": "Map of the schools in the list",
  "views.legend_high": "85%+ match",
  "views.legend_mid": "65 to 84%",
  "views.legend_low": "under 65%",
  "views.legend_missed": "missed a must-have",
  "views.legend_program": "nearby program",
  "views.close": "Close",
  "views.legend_zone": "demo attendance area",
  "views.zone_demo": "Shaded area: a demo attendance area from the nearest zoned school. Not the official zone.",
  "views.zone_open": "Open to families from any address. No attendance area.",
  "views.zone_choice": "Admission by application or lottery. No attendance area.",
  "views.zone_find": "Find the official zone",
  "views.pin_meta": "{pct}% match · Verified {verified}",
  "views.pin_program": "◆ {name} · {miles} mi · fills {need}",
  "views.details": "Details",
  // GettingIn.tsx
  "gi.title": "Getting in",
  "gi.how.zoned": "How zoned schools work",
  "gi.how.choice": "How school choice works",
  "gi.how.lottery": "How the lottery works",
  "gi.how.application": "How private school admission works",
  "gi.how": "How admission works",
  "gi.src_parent": "You told us this is your zoned school",
  "gi.src_rule": "Admission rule, checked {date}",
  "gi.src_school": "School-reported",
  "gi.src_profile": "School profile",
  "gi.no_dates": "{how} · no dates or open seats on file yet",
  "gi.yes_mine": "Yes, it's mine",
  "gi.find_zoned": "Find my zoned school",
  "gi.not_mine": "Not my zoned school",
  "gi.next_step": "Next step:",
  "gi.state_ed": "State education department",
  "gi.fdoe": "Florida Department of Education",
  "gi.district_choice": "{district} school choice",
  "gi.admissions": "School's admissions page",
  "gi.applicants": "applicant numbers: {source}",
  "gi.never_odds": "We explain how admission works; we never estimate a family's chances.",
  // Community.tsx
  "community.viewing_as": "Viewing as",
  "persona.parent_a": "Parent A",
  "persona.parent_b": "Parent B",
  "persona.school_staff": "School staff",
  "community.load_error": "Could not load the community",
  "community.school": "School",
  "community.title": "{school} · Community",
  "community.intro": "Parents ask and share here. Posts can support what you see on a card. Only data or the school itself confirms it.",
  "community.asked_label": "What parents asked this month",
  "community.asked_title": "Parents asked this month",
  "community.no_questions": "No questions yet.",
  "community.staff_note":
    "You are viewing as school staff. Answer a thread once and every parent who asked will see it. Your answers carry a Verified school badge.",
  "community.send_digest": "Send digest",
  "community.digest_label": "Digest email",
  "community.digest_to": "To {to}",
  "community.digest_sent": "sent through SES sandbox",
  "community.digest_recorded": "recorded (SES is off)",
  "community.threads": "Threads",
  "community.threads_about": "Threads about {topic}",
  "community.all_topics": "Show all topics",
  "community.top": "Top",
  "community.new": "New",
  "community.no_threads": "No threads yet. Ask the first question.",
  "community.upvote": "Upvote, {n} votes",
  "community.question": "Question",
  "community.experience": "Experience",
  "community.reply_one": "{n} reply",
  "community.reply_other": "{n} replies",
  "community.school_answered": "✓ School answered",
  "community.via_ask": "asked through Ask the school",
  "community.sample": "sample post",
  "community.not_posted": "Not posted.",
  "community.found": "Found: {items}.",
  "community.checked_by": "Checked by {checks}.",
  "community.check_rules": "our rules",
  "community.check_guardrails": "Amazon Bedrock Guardrails",
  "community.ask_question": "Ask a question",
  "community.share": "Share your experience",
  "community.drafted": "The assistant drafted this from your search. Edit it if you like. Nothing is posted until you tap Post.",
  "community.your_question": "Your question",
  "community.your_experience": "Your experience",
  "community.question_placeholder": "What do you want to know from other parents?",
  "community.experience_placeholder": "What has it really been like?",
  "community.topics": "Topics",
  "community.topics_tap": "Topics (tap to confirm):",
  "community.posted": "Posted. Names, emails, phone numbers and addresses were checked first.",
  "community.no_pii": "Don't include names, phone numbers, emails or addresses.",
  "community.checking": "Checking",
  "community.post": "Post",
  "community.verified": "✓ Verified school",
  "community.answer_as_school": "Answer as the school",
  "community.reply": "Reply",
  "community.answer_placeholder": "Answer once for every parent who asked",
  "community.reply_placeholder": "Write a reply",
  "community.topic": "Topic",
  "community.ends_at": "Ends at",
  "community.this_answer": "This answer",
  "community.offers_yes": "confirms we offer it",
  "community.offers_no": "says we don't offer it",
  "community.offers_info": "is just information",
  "community.post_answer": "Post answer",
  "community.questions_title": "Questions for the school",
  "community.questions_note":
    "Parents asked these through “Ask the school”. Your answer is posted on this page with a Verified school badge and updates their results.",
  "community.parents_asked_one": "{n} parent asked",
  "community.parents_asked_other": "{n} parents asked",
  "community.answer_for": "Answer: {question}",
  "community.home_title": "Parent community",
  "community.home_intro":
    "Every school has a page where parents ask questions and share what it's really like. Posts can support what you see on a card. Only data or the school itself confirms it.",
  "community.find_school": "Find a school",
  "community.find_placeholder": "Find a school by name",
  "community.matching": "Schools matching “{query}”",
  "community.active": "Active this month",
  "community.no_match": "No school by that name.",
  "community.no_posts": "No posts yet. Open a school from your results to start one.",
} as const;

export type UiKey = keyof typeof EN;

type Strings = Record<string, string>;

let language = "en";
let strings: Strings = EN;
const cache = new Map<string, Strings>([["en", EN]]);

/** The UI string for `key` in the current language, with {placeholders} filled in. */
export function t(key: UiKey | string, vars?: Record<string, string | number>): string {
  const text = strings[key] ?? (EN as Strings)[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (vars[name] === undefined ? whole : String(vars[name])));
}

/** `one` or `other` key for a count, so plurals read naturally ("1 thread", "2 threads"). */
export function tn(base: string, n: number, vars: Record<string, string | number> = {}): string {
  return t(`${base}_${n === 1 ? "one" : "other"}`, { n, ...vars });
}

/** The current UI language code ("en", "es", "ht"...). */
export function uiLanguage(): string {
  return language;
}

/** A language's own name in the current UI language ("es" -> "español" when the UI is Spanish). */
export function languageName(code: string): string {
  try {
    return new Intl.DisplayNames([language, "en"], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** A date in the UI language. Reads "2026-03-15" by hand so it never shifts a day for time zones. */
export function formatDate(iso: string | null | undefined, withDay: boolean): string {
  const [year, month, day] = (iso ?? "").split("-").map(Number);
  if (!year || !month || (withDay && !day)) return "";
  const date = new Date(Date.UTC(year, month - 1, withDay ? day : 1));
  const options: Intl.DateTimeFormatOptions = withDay
    ? { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }
    : { year: "numeric", month: "short", timeZone: "UTC" };
  try {
    return new Intl.DateTimeFormat([language, "en"], options).format(date);
  } catch {
    return new Intl.DateTimeFormat("en", options).format(date);
  }
}

/**
 * Switch the UI to `next` (the language of the parent's latest message). Fetches and caches the
 * translated table once per language, and returns a version number that changes when the strings
 * change, so App re-renders everything that calls t().
 */
export function useUiLanguage(next: string | null | undefined): number {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const code = next || "en";
    let live = true;
    const apply = (table: Strings) => {
      if (!live) return;
      language = code;
      strings = table;
      setVersion((value) => value + 1);
    };
    const cached = cache.get(code);
    if (cached) {
      apply(cached);
    } else {
      fetch("/api/ui-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: code, strings: EN }),
      })
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
        .then((data: { strings?: Strings; error?: string | null }) => {
          // A failed translation comes back as English; don't cache it, so the next turn retries.
          if (data.strings && !data.error) cache.set(code, data.strings);
          apply(data.strings ?? EN);
        })
        .catch(() => apply(EN));
    }
    return () => {
      live = false;
    };
  }, [next]);
  return version;
}
