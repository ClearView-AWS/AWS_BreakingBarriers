// What the Guide says, drawn from the blocks /api/chat returns. Every block of a
// turn renders inside that turn's chat message: results as compact cards, the
// clarifying question as buttons, and detail, compare, cost, why-not and
// definitions inline.
import { useEffect, useMemo, useState } from "react";
import type { Block, Card, Criterion, Evidence, ProgramPin, Turn } from "./types";
import { GettingInDetail, GettingInLine, type Access } from "./GettingIn";
import type { CommunityTarget } from "./Community";
import { STATUS_MARK, nameOf, sourceLabel, statusLabel } from "./labels";
import { languageName, t, tn } from "./i18n";
import { MapView, ViewToggle, type ResultsView } from "./Views";
import { Brief } from "./components/Brief";
import { QuestionPrompt, type QuestionItem } from "./components/QuestionPrompt";
import { CallButton } from "./Call";
import { ReadAloud } from "./components/ReadAloud";
import { StatusBadge } from "./components/StatusBadge";

/** "public" -> "Public" in the UI language; anything else as written. */
function typeLabel(type: string | null | undefined): string {
  if (!type) return "";
  const text = t(`type.${type}`);
  return text === `type.${type}` ? type : text;
}
const SHOWN_FIRST = 3;

export type Picked = { id: string; name: string };

/** What a block can ask the app to do. Every tap goes through `send`, so it lands in the chat. */
export type Actions = {
  send: (body: Record<string, unknown>) => void;
  busy: boolean;
  picked: Picked[];
  setPicked: (next: Picked[]) => void;
  /** Open a school's community page in the Community tab. */
  openCommunity?: (target: CommunityTarget) => void;
  /** List or Map for the results on screen. Starts as List and sticks for the session. */
  resultsView: ResultsView;
  setResultsView: (view: ResultsView) => void;
  /** The chat session, so a school call is grouped with this parent's questions. */
  sessionId?: string | null;
};

export function blockOf(blocks: Block[], type: string) {
  return blocks.find((block) => block.type === type)?.payload ?? null;
}

/**
 * One Guide message. `latest` turns on the question and chip buttons, which only
 * make sense for the newest reply. `current` marks the results the parent is
 * looking at now; older results fold to one line so "#2" always means one list.
 */
export function AgentBlocks({
  turn,
  latest,
  current,
  briefHere = false,
  actions,
}: {
  turn: Turn;
  latest: boolean;
  current: boolean;
  /** This reply holds the newest brief, so it draws it. */
  briefHere?: boolean;
  actions: Actions;
}) {
  return (
    <div className="agent-blocks">
      {turn.read_from && <p className="read-from">{t("blocks.read_from", { language: languageName(turn.read_from) })}</p>}
      {turn.blocks.map((block, index) => (
        <AgentBlock key={index} block={block} turn={turn} latest={latest} current={current} briefHere={briefHere} actions={actions} />
      ))}
    </div>
  );
}

function AgentBlock({
  block,
  turn,
  latest,
  current,
  briefHere,
  actions,
}: {
  block: Block;
  turn: Turn;
  latest: boolean;
  current: boolean;
  briefHere: boolean;
  actions: Actions;
}) {
  const payload = block.payload;
  switch (block.type) {
    case "message": {
      const text = String(payload.text ?? "");
      const prompt = payload.prompt ? String(payload.prompt) : "";
      if (!text && !prompt) return null;
      return (
        <div className="agent-text">
          {text && <p>{text}</p>}
          {prompt && <p className="agent-prompt">{prompt}</p>}
          {(text || prompt) && <ReadAloud text={[text, prompt].filter(Boolean).join(". ")} lang={turn.language} />}
        </div>
      );
    }
    case "question":
      // Before the first search the same question also comes in the `questions` block, drawn above.
      if (turn.blocks.some((other) => other.type === "questions")) return null;
      return (
        <Question
          payload={payload}
          disabled={!latest || actions.busy}
          onPick={(optionId) => actions.send({ action: "refresh", answer: { question_id: payload.id, option_id: optionId } })}
        />
      );
    case "brief": {
      // The parent's search: must / nice / avoid. Only the newest brief is drawn. Before the first
      // search it waits for approval; after that, editing a chip re-runs the search. It's the one
      // place the search is shown and edited.
      const approved = Boolean(payload.approved);
      if (!briefHere) return null;
      return (
        <Brief
          criteria={turn.criteria}
          approved={approved}
          onChange={(next) => actions.send({ event: "brief_edited", action: "refresh", criteria: next })}
          onApprove={() => actions.send({ event: "brief_approved", action: "refresh" })}
        />
      );
    }
    case "questions": {
      // Up to three questions that would change the results, each skippable.
      if (!latest || turn.blocks.some((other) => other.type === "results")) return null;
      return (
        <QuestionPrompt
          items={(payload.items as QuestionItem[]) ?? []}
          skipLabel={payload.skip_label ? String(payload.skip_label) : undefined}
          onPick={(questionId, optionId) =>
            actions.send({ event: "answers_submitted", action: "refresh", answer: { question_id: questionId, option_id: optionId } })
          }
          onSkip={() => actions.send({ event: "skip_to_results", action: "refresh" })}
        />
      );
    }
    case "chips":
      // Chips name a school and an action ("Open the full profile"), so they still work later.
      return <Chips items={(payload.items as ChatChip[]) ?? []} disabled={actions.busy} onAction={actions.send} />;
    case "results":
      return <Results payload={payload} criteria={turn.criteria} current={current} actions={actions} />;
    case "evidence_grid":
      // The grid only repeats the cards' statuses. A search shows its list and map; a compare
      // shows where the schools differ (the comparison block).
      return null;
    case "why_not": {
      const why = payload as { school_name?: string; text?: string; change?: string };
      return (
        <div className="inline-panel">
          <h3>{why.school_name}</h3>
          <p>{why.text}</p>
          {why.change && <p>{why.change}</p>}
        </div>
      );
    }
    case "definition": {
      const term = payload as { term?: string; title?: string; text?: string; cite?: string };
      return (
        <div className="inline-panel">
          <h3>{term.title ?? term.term}</h3>
          <p>{term.text}</p>
          <p className="source">{t("blocks.source", { cite: String(term.cite ?? "") })}</p>
        </div>
      );
    }
    case "cost":
      return <Cost schools={(payload.schools as Record<string, unknown>[]) ?? []} />;
    case "school_detail":
      return <SchoolDetail payload={payload as unknown as DetailPayload} />;
    case "comparison":
      return <Comparison schools={(payload.schools as Card[]) ?? []} criteria={turn.criteria} />;
    default:
      // criteria (the bar above the input), answer (data behind a cited reply), checklist (Saved tab).
      return null;
  }
}

// --- chips and questions -----------------------------------------------------

export type ChatChip = { label: string; payload?: Record<string, unknown>; href?: string };

function Chips({ items, disabled, onAction }: { items: ChatChip[]; disabled: boolean; onAction: (payload: Record<string, unknown>) => void }) {
  if (!items.length) return null;
  return (
    <div className="chat-chips">
      {items.map((chip) =>
        chip.href ? (
          <a key={chip.label} href={chip.href} target="_blank" rel="noreferrer">
            {chip.label} ↗
          </a>
        ) : (
          <button key={chip.label} type="button" disabled={disabled} onClick={() => chip.payload && onAction(chip.payload)}>
            {chip.label}
          </button>
        ),
      )}
    </div>
  );
}

function Question({ payload, disabled, onPick }: { payload: Record<string, unknown>; disabled: boolean; onPick: (id: string) => void }) {
  const options = (payload.options as { id: string; label: string }[]) ?? [];
  return (
    <section className="question">
      <p>{String(payload.text)}</p>
      <div className="options">
        {options.map((option) => (
          <button key={option.id} disabled={disabled} onClick={() => onPick(option.id)}>{option.label}</button>
        ))}
      </div>
    </section>
  );
}


// --- results -----------------------------------------------------------------

function Results({
  payload,
  criteria,
  current,
  actions,
}: {
  payload: Record<string, unknown>;
  criteria: Criterion[];
  current: boolean;
  actions: Actions;
}) {
  const schools = (payload.schools as Card[]) ?? [];
  const gaps = (payload.gaps as Card[]) ?? [];
  const missed = (payload.missed as Card[]) ?? [];
  const center = (payload.center as [number, number] | null) ?? null;
  const programs = (payload.programs as ProgramPin[]) ?? [];
  const total = schools.length + gaps.length + missed.length;
  const [open, setOpen] = useState(current);
  const [all, setAll] = useState(false);
  // Fold when a newer search replaces this one as the list the parent is looking at.
  useEffect(() => setOpen(current), [current]);
  if (!total) return null;

  if (!current && !open) {
    const about = criteria.map(nameOf).join(" · ");
    return (
      <button type="button" className="results-folded" onClick={() => setOpen(true)}>
        {tn("blocks.earlier", total)}
        {about ? ` ${t("blocks.earlier_for", { about })}` : ""} · {t("blocks.show")}
      </button>
    );
  }

  const hidden = schools.length - SHOWN_FIRST;
  const rest = Math.max(hidden, 0) + gaps.length + missed.length;
  const card = (item: Card, number?: number) => (
    <SchoolCard key={item.id} card={item} number={number} criteria={criteria} actions={actions} />
  );
  const list = (
    <div className="results">
      {!current && (
        <button type="button" className="texty results-fold" onClick={() => setOpen(false)}>
          {t("blocks.earlier_hide")}
        </button>
      )}
      <div className="cards">{schools.slice(0, all ? undefined : SHOWN_FIRST).map((item, index) => card(item, index + 1))}</div>
      {all && gaps.length > 0 && (
        <>
          <h4 className="results-group">{t("blocks.group_gaps")}</h4>
          <div className="cards">{gaps.map((item) => card(item))}</div>
        </>
      )}
      {all && missed.length > 0 && (
        <>
          <h4 className="results-group">{t("blocks.group_missed")}</h4>
          <div className="cards">{missed.map((item) => card(item))}</div>
        </>
      )}
      {rest > 0 && (
        <button type="button" className="texty results-more" onClick={() => setAll((value) => !value)}>
          {all ? t("blocks.show_fewer") : t("blocks.show_all", { total }) + describeRest(Math.max(hidden, 0), gaps.length, missed.length)}
        </button>
      )}
    </div>
  );
  // Earlier results the parent reopened stay a plain list; the views belong to the list on screen now.
  if (!current) return list;
  return (
    <ViewToggle view={actions.resultsView} onChange={actions.setResultsView} cards={[...schools, ...gaps]} criteria={criteria}>
      {{
        list,
        map: <MapView schools={schools} gaps={gaps} missed={missed} criteria={criteria} center={center} programs={programs} actions={actions} />,
      }}
    </ViewToggle>
  );
}

function describeRest(more: number, gaps: number, missed: number): string {
  const parts = [
    more ? tn("blocks.more", more) : "",
    gaps ? t("blocks.rest_gaps", { n: gaps }) : "",
    missed ? t("blocks.rest_missed", { n: missed }) : "",
  ].filter(Boolean);
  return parts.length ? ` (${parts.join(", ")})` : "";
}

function SchoolCard({ card, number, criteria, actions }: { card: Card; number?: number; criteria: Criterion[]; actions: Actions }) {
  const [evidence, setEvidence] = useState(false);
  const [reasons, setReasons] = useState(false);
  const labels = useMemo(() => new Map(criteria.map((item) => [item.id, nameOf(item)])), [criteria]);
  const needs = useMemo(() => new Map(criteria.map((item) => [item.id, item.need])), [criteria]);
  const { send, busy, picked, setPicked, openCommunity } = actions;
  const selected = picked.some((item) => item.id === card.id);
  const levels = (card.level_codes ?? []).map((code) => (t(`level.${code}`) === `level.${code}` ? code : t(`level.${code}`))).join(", ");
  const ask = (row: Evidence) => {
    const need = needs.get(row.criterion_id);
    return row.status === "unknown" && need ? () => send({ action: "ask_school", school_ids: [card.id], need }) : undefined;
  };
  // Opens the school's community page with a drafted question. Nothing posts until the parent taps Post.
  const askParents = (row: Evidence) => {
    const need = needs.get(row.criterion_id);
    return row.status === "unknown" && need && openCommunity
      ? () => openCommunity({ schoolId: card.id, draftNeed: need, from: "results" })
      : undefined;
  };
  return (
    <article className={selected ? "card compact compare-on" : "card compact"} data-school-id={card.id}>
      <header>
        <div>
          <h3>
            {number != null && <span className="card-number" aria-hidden="true">#{number}</span>}
            <button
              type="button"
              aria-label={t("a11y.open_school", { name: card.name })}
              onClick={() => send({ action: "school_detail", school_ids: [card.id] })}
            >
              {card.name}
            </button>
          </h3>
          <div className="meta">
            {[card.city, typeLabel(card.entity_type), levels, card.distance_miles != null ? t("blocks.miles", { n: card.distance_miles }) : ""].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="score">
          <strong>{Math.round(card.match * 100)}%</strong>
          <span>{t("blocks.verified", { verified: card.verified })}</span>
        </div>
      </header>
      {card.summary && <p className="summary">{card.summary}</p>}
      <GettingInLine schoolId={card.id} access={(card as Card & { access?: Access }).access} />
      {openCommunity && <CommunityLine card={card} onCommunity={openCommunity} />}
      {!evidence && (
        <div className="pills" aria-label={t("blocks.at_a_glance")}>
          {card.evidence.map((row) => {
            const criterion = labels.get(row.criterion_id) ?? row.criterion_id;
            const status = statusLabel(row.status);
            const mark = STATUS_MARK[row.status] ?? "";
            const onAsk = ask(row);
            return onAsk ? (
              <button
                key={row.criterion_id}
                type="button"
                data-criterion-id={row.criterion_id}
                className={`pill ${row.status}`}
                disabled={busy}
                title={t("blocks.not_on_file_ask")}
                onClick={onAsk}
              >
                <span className="status-mark" aria-hidden="true">{mark}</span> {status}: {criterion} · {t("blocks.ask_short")}
              </button>
            ) : (
              <span key={row.criterion_id} data-criterion-id={row.criterion_id} className={`pill ${row.status}`} title={status}>
                <span className="status-mark" aria-hidden="true">{mark}</span> {status}: {criterion}
              </span>
            );
          })}
        </div>
      )}
      <CallButton
        schoolId={card.id}
        schoolName={card.name}
        needs={card.evidence.filter((row) => row.status === "unknown").map((row) => needs.get(row.criterion_id)).filter((need): need is string => !!need)}
        actions={actions}
      />
      {evidence && (
        <div className="evidence">
          {card.evidence.map((row) => (
            <EvidenceRow
              key={row.criterion_id}
              row={row}
              label={labels.get(row.criterion_id) ?? row.criterion_id}
              onAsk={ask(row)}
              onAskParents={askParents(row)}
            />
          ))}
        </div>
      )}
      <div className="row-actions">
        <button aria-expanded={evidence} onClick={() => setEvidence((value) => !value)}>{evidence ? t("blocks.hide_evidence") : t("blocks.show_evidence")}</button>
        <button disabled={busy} onClick={() => send({ action: "save", school_ids: [card.id] })}>{t("blocks.save")}</button>
        <button
          aria-pressed={selected}
          onClick={() =>
            setPicked(selected ? picked.filter((item) => item.id !== card.id) : [...picked, { id: card.id, name: card.name }].slice(-2))
          }
        >
          {selected ? t("blocks.selected") : t("blocks.compare")}
        </button>
        {card.entity_type === "private" && (
          <button disabled={busy} onClick={() => send({ action: "cost", school_ids: [card.id] })}>{t("blocks.cost_after")}</button>
        )}
        {openCommunity && (
          <button onClick={() => openCommunity({ schoolId: card.id, from: "results" })}>
            {t("blocks.community")}{card.community?.threads ? ` (${card.community.threads})` : ""}
          </button>
        )}
        <button disabled={busy} aria-label={t("blocks.thumbs_up")} onClick={() => send({ action: "feedback", feedback: { school_id: card.id, vote: "up" } })}>👍</button>
        <button aria-label={t("blocks.thumbs_down")} aria-expanded={reasons} onClick={() => setReasons((value) => !value)}>👎</button>
      </div>
      {reasons && (
        <div className="reasons">
          {[
            "too_far",
            "too_expensive",
            "missing_program",
            "wrong_grade",
          ].map((id) => (
            <button
              key={id}
              disabled={busy}
              onClick={() => {
                send({ action: "feedback", feedback: { school_id: card.id, vote: "down", reason: id } });
                setReasons(false);
              }}
            >
              {t(`reason.${id}`)}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

/** "4 parents discussed after-school care here" and this month's top ask, under the card summary. */
function CommunityLine({ card, onCommunity }: { card: Card; onCommunity: (target: CommunityTarget) => void }) {
  const info = card.community;
  if (!info || (!info.discussed.length && !info.demand.length)) return null;
  const topDemand = info.demand[0];
  return (
    <div className="community-line">
      {info.discussed.map((row) => (
        <button key={row.need} className="texty" onClick={() => onCommunity({ schoolId: card.id, filterNeed: row.need, from: "results" })}>
          {tn("blocks.discussed", row.parents, { topic: row.label.toLowerCase() })}
        </button>
      ))}
      {topDemand && (
        <span className="meta">
          {tn("blocks.asked", topDemand.count, { topic: topDemand.label.toLowerCase() })}
        </span>
      )}
    </div>
  );
}

function EvidenceRow({ row, label, onAsk, onAskParents }: { row: Evidence; label: string; onAsk?: () => void; onAskParents?: () => void }) {
  const source = row.source;
  return (
    <div className="ev" data-criterion-id={row.criterion_id}>
      <div>
        <StatusBadge status={row.status} />
        <div>{label}</div>
      </div>
      <div>
        <div>{row.value != null && row.value !== "" ? String(row.value) : t("blocks.no_value")}</div>
        {source && (
          <div className="source">
            {sourceLabel(source.type)} · {source.path}
            {source.as_of ? ` · ${t("blocks.as_of", { date: source.as_of })}` : ""}
            {source.confidence ? ` · ${t("blocks.confidence", { level: source.confidence })}` : ""}
          </div>
        )}
        {row.conflict && (
          <div className="conflict">
            {t("blocks.conflict", { website: String(row.conflict.website_value), profile: String(row.conflict.profile_value) })}
          </div>
        )}
        {(onAsk || onAskParents) && (
          <div className="ask-row">
            {onAsk && <button onClick={onAsk}>{t("blocks.ask_school")}</button>}
            {onAskParents && <button onClick={onAskParents}>{t("blocks.ask_parents")}</button>}
          </div>
        )}
      </div>
    </div>
  );
}

// --- inline answers ----------------------------------------------------------

function Cost({ schools }: { schools: Record<string, unknown>[] }) {
  return (
    <div className="inline-panel">
      <h3>{schools.some((school) => school.entity_type === "private") ? t("blocks.cost_title") : t("blocks.tuition")}</h3>
      {schools.map((school) => (
        <div key={String(school.school_id)}>
          <h4>{String(school.school_name)}</h4>
          {school.tuition != null && <p>{t("blocks.listed_tuition", { n: String(school.tuition) })}</p>}
          <p>{String(school.disclaimer ?? "")}</p>
          <ul className="checklist">
            {((school.lines as Record<string, string>[]) ?? []).map((line, index) => (
              <li key={index}>
                <strong>{line.wording}</strong> {line.name ? ` ${line.name}.` : ""} {line.eligibility ?? ""}{" "}
                {line.official_url && <a href={line.official_url} target="_blank" rel="noreferrer">{t("blocks.official_page")}</a>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

type DetailPayload = {
  school: Record<string, unknown>;
  reviews: { topic: string; positive: number; negative: number; earliest?: string; latest?: string; quotes: { side: string; date: string; text: string }[] }[];
  card?: Card | null;
};

function SchoolDetail({ payload }: { payload: DetailPayload }) {
  const school = payload.school;
  return (
    <div className="inline-panel" data-school-id={String(school.id)}>
      <h3>{String(school.name)}</h3>
      <p className="meta">{String(school.street ?? "")} {String(school.city ?? "")} {String(school.state ?? "")}</p>
      <p>
        {typeLabel(String(school.entity_type))} · {t("blocks.rating", { rating: school.summary_rating == null ? t("blocks.rating_unknown") : String(school.summary_rating) })}
        {school.synthetic ? ` · ${t("blocks.synthetic")}` : ""}
      </p>
      {((school.esp_text as string[]) ?? []).map((line) => <p key={line}>{line}</p>)}
      <GettingInDetail access={(payload.card as (Card & { access?: Access }) | null | undefined)?.access} />
      {payload.reviews.length > 0 && <h4>{t("blocks.reviews_by_topic")}</h4>}
      <div className="quotes">
        {payload.reviews.map((topic) => (
          <div key={topic.topic} className="quote">
            <strong>{topic.topic}</strong> · {t("blocks.review_counts", { positive: topic.positive, negative: topic.negative })}
            {topic.earliest ? ` · ${t("blocks.review_range", { start: topic.earliest, end: topic.latest ?? "" })}` : ""}
            {topic.quotes.map((quote, index) => (
              <p key={index}>{quote.date} · {quote.side}: {quote.text}</p>
            ))}
          </div>
        ))}
      </div>
      <p className="source">{t("blocks.reviews_note")}</p>
    </div>
  );
}

// --- compare: where two schools differ ----------------------------------------

type CompareCell = { text: string; status?: string; source?: string };
type CompareRow = { label: string; cells: CompareCell[] };

/** "18:00" -> "6:00 PM"; null for anything that isn't a clock time. */
function clockText(value: string): string | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const hour = Number(match[1]);
  return `${hour % 12 || 12}:${match[2]} ${hour < 12 ? "AM" : "PM"}`;
}

/** What the evidence actually says, so "Confirmed" and "Confirmed" can still differ. */
function evidenceCell(row: Evidence | undefined): CompareCell {
  if (!row || row.status === "unknown") return { text: t("compare.not_on_file"), status: "unknown" };
  const value = row.value == null ? "" : String(row.value);
  const time = clockText(value);
  const text =
    row.source?.type === "program" ? t("compare.nearby_program", { name: value }) : time ? t("compare.until", { time }) : value || statusLabel(row.status);
  const source = row.source ? `${sourceLabel(row.source.type)}${row.source.as_of ? ` · ${row.source.as_of}` : ""}` : undefined;
  return { text, status: row.status, source };
}

function compareRows(schools: Card[], criteria: Criterion[]): CompareRow[] {
  const rows: CompareRow[] = [
    { label: t("compare.match"), cells: schools.map((s) => ({ text: s.match == null ? "—" : t("compare.match_value", { pct: Math.round(s.match * 100), verified: s.verified }) })) },
  ];
  for (const criterion of criteria) {
    if (!((criterion.kind === "need" && criterion.need) || criterion.kind === "distance")) continue;
    rows.push({
      label: nameOf(criterion),
      cells: schools.map((s) => evidenceCell(s.evidence.find((row) => row.criterion_id === criterion.id))),
    });
  }
  // How and by when, in one line, so two lotteries with different deadlines still differ.
  const gettingIn = (s: Card) => {
    const access = (s as Card & { access?: Access }).access;
    if (!access) return "—";
    return access.line.startsWith(access.how_label) ? access.line : `${access.how_label} · ${access.line}`;
  };
  rows.push(
    { label: t("compare.getting_in"), cells: schools.map((s) => ({ text: gettingIn(s) })) },
    { label: t("compare.distance"), cells: schools.map((s) => ({ text: s.distance_miles != null ? t("compare.distance_value", { n: s.distance_miles }) : "—" })) },
    { label: t("compare.type"), cells: schools.map((s) => ({ text: typeLabel(s.entity_type) || "—" })) },
  );
  if (schools.some((s) => s.tuition != null)) {
    rows.push({ label: t("compare.tuition"), cells: schools.map((s) => ({ text: s.tuition != null ? t("compare.tuition_value", { n: Number(s.tuition).toLocaleString() }) : t("compare.none_listed") })) });
  }
  rows.push({
    label: t("compare.community"),
    cells: schools.map((s) => {
      const info = s.community;
      if (!info?.threads) return { text: t("compare.no_threads") };
      const topics = info.discussed.map((row) => row.label).join(", ");
      return { text: `${tn("compare.threads", info.threads)}${topics ? ` (${topics})` : ""}` };
    }),
  });
  return rows.filter((row) => row.cells.some((cell) => cell.text !== "—"));
}

/** Two schools side by side, leading with what differs. Rows that read the same fold into one line. */
function Comparison({ schools, criteria }: { schools: Card[]; criteria: Criterion[] }) {
  if (schools.length < 2) return null;
  const rows = compareRows(schools, criteria);
  const key = (cell: CompareCell) => `${cell.status ?? ""}|${cell.text}`;
  const differ = rows.filter((row) => new Set(row.cells.map(key)).size > 1);
  const same = rows.filter((row) => new Set(row.cells.map(key)).size === 1);
  return (
    <div className="comparison">
      <h4>{differ.length ? t("compare.differ") : t("compare.all_same")}</h4>
      {differ.length > 0 && (
        <div className="table-wrap">
          <table className="side-by-side">
            <thead>
              <tr>
                <th />
                {schools.map((school) => <th key={school.id} scope="col">{school.name}</th>)}
              </tr>
            </thead>
            <tbody>
              {differ.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  {row.cells.map((cell, index) => (
                    <td key={index}>
                      {cell.status && <StatusBadge status={cell.status} />} {cell.text}
                      {cell.source && <div className="source">{cell.source}</div>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {same.length > 0 && (
        <p className="meta">
          {t("compare.same", { rows: same.map((row) => `${row.label} (${row.cells[0].text})`).join(" · ") })}
        </p>
      )}
    </div>
  );
}
