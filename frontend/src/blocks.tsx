// What the Guide says, drawn from the blocks /api/chat returns. Every block of a
// turn renders inside that turn's chat message: results as compact cards, the
// clarifying question as buttons, and detail, compare, cost, why-not and
// definitions inline.
import { useEffect, useMemo, useState } from "react";
import type { Block, Card, Criterion, Evidence, Turn } from "./types";
import { GettingInDetail, GettingInLine, type Access } from "./GettingIn";
import type { CommunityTarget } from "./Community";

export const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  needs_attention: "Needs attention",
  unknown: "Unknown",
};
const STATUS_MARK: Record<string, string> = { confirmed: "✓", partial: "~", needs_attention: "!", unknown: "?" };
const SOURCE_LABEL: Record<string, string> = {
  state_data: "State data",
  school_reported: "School-reported",
  school_website: "School website",
  parent_reviews: "Parent reviews",
  community: "Parents say",
  program: "Nearby program",
  funding_rule: "Scholarship rule",
  computed: "Computed from the school's location",
};
const LEVEL: Record<string, string> = { p: "Pre-K", e: "Elementary", m: "Middle", h: "High" };
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
};

export function blockOf(blocks: Block[], type: string) {
  return blocks.find((block) => block.type === type)?.payload ?? null;
}

/**
 * One Guide message. `latest` turns on the question and chip buttons, which only
 * make sense for the newest reply. `current` marks the results the parent is
 * looking at now; older results fold to one line so "#2" always means one list.
 */
export function AgentBlocks({ turn, latest, current, actions }: { turn: Turn; latest: boolean; current: boolean; actions: Actions }) {
  return (
    <div className="agent-blocks">
      {turn.blocks.map((block, index) => (
        <AgentBlock key={index} block={block} turn={turn} latest={latest} current={current} actions={actions} />
      ))}
    </div>
  );
}

function AgentBlock({ block, turn, latest, current, actions }: { block: Block; turn: Turn; latest: boolean; current: boolean; actions: Actions }) {
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
        </div>
      );
    }
    case "question":
      return (
        <Question
          payload={payload}
          disabled={!latest || actions.busy}
          onPick={(optionId) => actions.send({ action: "refresh", answer: { question_id: payload.id, option_id: optionId } })}
        />
      );
    case "chips":
      // Chips name a school and an action ("Open the full profile"), so they still work later.
      return <Chips items={(payload.items as ChatChip[]) ?? []} disabled={actions.busy} onAction={actions.send} />;
    case "results":
      return <Results payload={payload} criteria={turn.criteria} current={current} actions={actions} grid={blockOf(turn.blocks, "evidence_grid")} />;
    case "evidence_grid":
      // A search shows its grid under "Show all"; compare shows it right away.
      return turn.blocks.some((other) => other.type === "results") ? null : <Grid payload={payload} />;
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
          <p className="source">Source: {term.cite}</p>
        </div>
      );
    }
    case "cost":
      return <Cost schools={(payload.schools as Record<string, unknown>[]) ?? []} />;
    case "school_detail":
      return <SchoolDetail payload={payload as unknown as DetailPayload} />;
    case "comparison":
      return <Comparison schools={(payload.schools as Card[]) ?? []} />;
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

/** The filter's name ("STEM-focused"), falling back to the parent's words for anything that maps to no filter. */
function nameOf(item: Pick<Criterion, "text" | "label">): string {
  return item.label || item.text;
}

export function ChipRow({ criteria, disabled, onChange }: { criteria: Criterion[]; disabled: boolean; onChange: (next: Criterion[]) => void }) {
  const cycle: Record<string, Criterion["strength"]> = { require: "prefer", prefer: "avoid", avoid: "require" };
  return (
    <div className="chips" aria-label="Your search">
      {criteria.map((item) => (
        <span className="chip" key={item.id} title={item.label && item.label !== item.text ? `You said: “${item.text}”` : undefined}>
          <b>{nameOf(item)}</b>
          {item.kind === "need" || item.kind === "distance" ? (
            <button
              className={`strength-${item.strength}`}
              disabled={disabled}
              title="Change how much this matters"
              onClick={() => onChange(criteria.map((row) => (row.id === item.id ? { ...row, strength: cycle[row.strength] } : row)))}
            >
              {item.strength}
            </button>
          ) : (
            <span>{item.kind === "grade" ? "grade" : item.kind === "location" ? "city" : "type"}</span>
          )}
          <button aria-label={`Remove ${nameOf(item)}`} disabled={disabled} onClick={() => onChange(criteria.filter((row) => row.id !== item.id))}>×</button>
        </span>
      ))}
    </div>
  );
}

// --- results -----------------------------------------------------------------

function Results({
  payload,
  criteria,
  current,
  actions,
  grid,
}: {
  payload: Record<string, unknown>;
  criteria: Criterion[];
  current: boolean;
  actions: Actions;
  grid: Record<string, unknown> | null;
}) {
  const schools = (payload.schools as Card[]) ?? [];
  const gaps = (payload.gaps as Card[]) ?? [];
  const missed = (payload.missed as Card[]) ?? [];
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
        Earlier results: {total} school{total === 1 ? "" : "s"}
        {about ? ` for ${about}` : ""} · Show
      </button>
    );
  }

  const hidden = schools.length - SHOWN_FIRST;
  const rest = Math.max(hidden, 0) + gaps.length + missed.length;
  const card = (item: Card, number?: number) => (
    <SchoolCard key={item.id} card={item} number={number} criteria={criteria} actions={actions} />
  );
  return (
    <div className="results">
      {!current && (
        <button type="button" className="texty results-fold" onClick={() => setOpen(false)}>
          Earlier results · Hide
        </button>
      )}
      <div className="cards">{schools.slice(0, all ? undefined : SHOWN_FIRST).map((item, index) => card(item, index + 1))}</div>
      {all && gaps.length > 0 && (
        <>
          <h4 className="results-group">Missing a fact we can ask about</h4>
          <div className="cards">{gaps.map((item) => card(item))}</div>
        </>
      )}
      {all && missed.length > 0 && (
        <>
          <h4 className="results-group">Missed a must-have</h4>
          <div className="cards">{missed.map((item) => card(item))}</div>
        </>
      )}
      {all && grid && <Grid payload={grid} />}
      {rest > 0 && (
        <button type="button" className="texty results-more" onClick={() => setAll((value) => !value)}>
          {all ? "Show fewer" : `Show all ${total}` + describeRest(Math.max(hidden, 0), gaps.length, missed.length)}
        </button>
      )}
    </div>
  );
}

function describeRest(more: number, gaps: number, missed: number): string {
  const parts = [
    more ? `${more} more match${more === 1 ? "" : "es"}` : "",
    gaps ? `${gaps} missing a fact` : "",
    missed ? `${missed} missed a must-have` : "",
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
  const levels = (card.level_codes ?? []).map((code) => LEVEL[code] ?? code).join(", ");
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
    <article className={selected ? "card compact compare-on" : "card compact"}>
      <header>
        <div>
          <h3>
            {number != null && <span className="card-number">#{number}</span>}
            <button onClick={() => send({ action: "school_detail", school_ids: [card.id] })}>{card.name}</button>
          </h3>
          <div className="meta">
            {[card.city, card.entity_type, levels, card.distance_miles != null ? `${card.distance_miles} miles` : ""].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="score">
          <strong>{Math.round(card.match * 100)}%</strong>
          <span>Verified {card.verified}</span>
        </div>
      </header>
      {card.summary && <p className="summary">{card.summary}</p>}
      <GettingInLine schoolId={card.id} access={(card as Card & { access?: Access }).access} />
      {openCommunity && <CommunityLine card={card} onCommunity={openCommunity} />}
      {!evidence && (
        <div className="pills" aria-label="Evidence at a glance">
          {card.evidence.map((row) => {
            const label = `${STATUS_MARK[row.status] ?? ""} ${labels.get(row.criterion_id) ?? row.criterion_id}`;
            const onAsk = ask(row);
            return onAsk ? (
              <button key={row.criterion_id} className={`pill ${row.status}`} disabled={busy} title="Not on file. Ask the school." onClick={onAsk}>
                {label} · ask
              </button>
            ) : (
              <span key={row.criterion_id} className={`pill ${row.status}`} title={STATUS_LABEL[row.status]}>{label}</span>
            );
          })}
        </div>
      )}
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
        <button aria-expanded={evidence} onClick={() => setEvidence((value) => !value)}>{evidence ? "Hide evidence" : "Show evidence"}</button>
        <button disabled={busy} onClick={() => send({ action: "save", school_ids: [card.id] })}>Save</button>
        <button
          aria-pressed={selected}
          onClick={() =>
            setPicked(selected ? picked.filter((item) => item.id !== card.id) : [...picked, { id: card.id, name: card.name }].slice(-2))
          }
        >
          {selected ? "Selected" : "Compare"}
        </button>
        {card.entity_type === "private" && (
          <button disabled={busy} onClick={() => send({ action: "cost", school_ids: [card.id] })}>Cost after scholarships</button>
        )}
        {openCommunity && (
          <button onClick={() => openCommunity({ schoolId: card.id, from: "results" })}>
            Community{card.community?.threads ? ` (${card.community.threads})` : ""}
          </button>
        )}
        <button disabled={busy} aria-label="Thumbs up" onClick={() => send({ action: "feedback", feedback: { school_id: card.id, vote: "up" } })}>👍</button>
        <button aria-label="Thumbs down" aria-expanded={reasons} onClick={() => setReasons((value) => !value)}>👎</button>
      </div>
      {reasons && (
        <div className="reasons">
          {[
            ["too_far", "Too far"],
            ["too_expensive", "Too expensive"],
            ["missing_program", "Missing a program"],
            ["wrong_grade", "Wrong grade"],
          ].map(([id, label]) => (
            <button
              key={id}
              disabled={busy}
              onClick={() => {
                send({ action: "feedback", feedback: { school_id: card.id, vote: "down", reason: id } });
                setReasons(false);
              }}
            >
              {label}
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
          {row.parents} parent{row.parents === 1 ? "" : "s"} discussed {row.label.toLowerCase()} here
        </button>
      ))}
      {topDemand && (
        <span className="meta">
          {topDemand.count} parent{topDemand.count === 1 ? "" : "s"} asked about {topDemand.label.toLowerCase()} this month
        </span>
      )}
    </div>
  );
}

function EvidenceRow({ row, label, onAsk, onAskParents }: { row: Evidence; label: string; onAsk?: () => void; onAskParents?: () => void }) {
  const source = row.source;
  return (
    <div className="ev">
      <div>
        <span className={`pill ${row.status}`}>{STATUS_LABEL[row.status] ?? row.status}</span>
        <div>{label}</div>
      </div>
      <div>
        <div>{row.value != null && row.value !== "" ? String(row.value) : "No value on file"}</div>
        {source && (
          <div className="source">
            {SOURCE_LABEL[source.type] ?? source.type} · {source.path}
            {source.as_of ? ` · as of ${source.as_of}` : ""}
            {source.confidence ? ` · ${source.confidence} confidence` : ""}
          </div>
        )}
        {row.conflict && (
          <div className="conflict">
            Website says {String(row.conflict.website_value)}; the profile says {String(row.conflict.profile_value)}.
          </div>
        )}
        {(onAsk || onAskParents) && (
          <div className="ask-row">
            {onAsk && <button onClick={onAsk}>Ask the school</button>}
            {onAskParents && <button onClick={onAskParents}>Ask parents at this school</button>}
          </div>
        )}
      </div>
    </div>
  );
}

// --- inline answers ----------------------------------------------------------

function Grid({ payload }: { payload: Record<string, unknown> }) {
  const schools = (payload.schools as { id: string; name: string }[]) ?? [];
  const criteria = (payload.criteria as Pick<Criterion, "id" | "text" | "label">[]) ?? [];
  const cells = (payload.cells as Record<string, Record<string, Evidence | null>>) ?? {};
  if (!schools.length) return null;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>School</th>
            {criteria.map((column) => <th key={column.id}>{nameOf(column)}</th>)}
          </tr>
        </thead>
        <tbody>
          {schools.map((school) => (
            <tr key={school.id}>
              <th>{school.name}</th>
              {criteria.map((column) => {
                const cell = cells[school.id]?.[column.id];
                return (
                  <td key={column.id}>
                    {cell ? (
                      <>
                        <span className={`pill ${cell.status}`}>{STATUS_LABEL[cell.status]}</span>
                        <div className="source">{cell.source ? `${SOURCE_LABEL[cell.source.type] ?? cell.source.type}${cell.source.as_of ? ` · ${cell.source.as_of}` : ""}` : ""}</div>
                      </>
                    ) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Cost({ schools }: { schools: Record<string, unknown>[] }) {
  return (
    <div className="inline-panel">
      <h3>{schools.some((school) => school.entity_type === "private") ? "Cost after likely scholarships" : "Tuition"}</h3>
      {schools.map((school) => (
        <div key={String(school.school_id)}>
          <h4>{String(school.school_name)}</h4>
          {school.tuition != null && <p>Listed tuition: ${String(school.tuition)}. This is not a net price.</p>}
          <p>{String(school.disclaimer ?? "")}</p>
          <ul className="checklist">
            {((school.lines as Record<string, string>[]) ?? []).map((line, index) => (
              <li key={index}>
                <strong>{line.wording}</strong> {line.name ? ` ${line.name}.` : ""} {line.eligibility ?? ""}{" "}
                {line.official_url && <a href={line.official_url} target="_blank" rel="noreferrer">Official page</a>}
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
    <div className="inline-panel">
      <h3>{String(school.name)}</h3>
      <p className="meta">{String(school.street ?? "")} {String(school.city ?? "")} {String(school.state ?? "")}</p>
      <p>
        {String(school.entity_type)} · summary rating {school.summary_rating == null ? "unknown" : String(school.summary_rating)}
        {school.synthetic ? " · synthetic profile" : ""}
      </p>
      {((school.esp_text as string[]) ?? []).map((line) => <p key={line}>{line}</p>)}
      <GettingInDetail access={(payload.card as (Card & { access?: Access }) | null | undefined)?.access} />
      {payload.reviews.length > 0 && <h4>Reviews by topic</h4>}
      <div className="quotes">
        {payload.reviews.map((topic) => (
          <div key={topic.topic} className="quote">
            <strong>{topic.topic}</strong> · {topic.positive} positive · {topic.negative} negative
            {topic.earliest ? ` · ${topic.earliest} to ${topic.latest}` : ""}
            {topic.quotes.map((quote, index) => (
              <p key={index}>{quote.date} · {quote.side}: {quote.text}</p>
            ))}
          </div>
        ))}
      </div>
      <p className="source">Review scores in the file are sentiment, not stars, so they are not shown as a rating.</p>
    </div>
  );
}

function Comparison({ schools }: { schools: Card[] }) {
  return (
    <div className="comparison">
      {schools.map((school) => (
        <article key={school.id} className="card compact">
          <h3>{school.name}</h3>
          <p className="summary">{school.summary}</p>
        </article>
      ))}
    </div>
  );
}
