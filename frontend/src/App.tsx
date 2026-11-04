import { FormEvent, useMemo, useState } from "react";
import { DEMO_QUERY, type Block, type Card, type Criterion, type Evidence, type Turn } from "./types";

type View = "search" | "saved" | "inbox";

const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  needs_attention: "Needs attention",
  unknown: "Unknown",
};
const SOURCE_LABEL: Record<string, string> = {
  state_data: "State data",
  school_reported: "School-reported",
  school_website: "School website",
  parent_reviews: "Parent reviews",
  program: "Nearby program",
  funding_rule: "Scholarship rule",
  computed: "Computed from the school's location",
};
const LEVEL: Record<string, string> = { p: "Pre-K", e: "Elementary", m: "Middle", h: "High" };
import { GettingInDetail, GettingInLine, SavedDeadline, onZonedTap, type Access } from "./GettingIn";

async function postTurn(body: Record<string, unknown>): Promise<Turn> {
  const response = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Search failed (${response.status})`);
  return response.json();
}

export function App() {
  const [view, setView] = useState<View>("search");
  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [panel, setPanel] = useState<Turn | null>(null);
  const [saved, setSaved] = useState<{ id: string; name: string; city?: string }[]>([]);
  const [checklist, setChecklist] = useState<{ school_name: string; question: string }[]>([]);
  const [inbox, setInbox] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [why, setWhy] = useState("");

  const criteria = turn?.criteria ?? [];
  const blocks = turn?.blocks ?? [];

  async function run(body: Record<string, unknown>, mode: "replace" | "panel" | "keep" = "replace") {
    setBusy(true);
    setError(null);
    try {
      const data = await postTurn({ session_id: sessionId, ...body });
      setSessionId(data.session_id);
      // Only a search answer replaces the results. A typed question about a school
      // (detail, compare, cost, why not, define) opens beside them.
      const isSearch = data.route === "new_search" || data.route === "refine";
      if (mode === "panel" || (mode === "replace" && !isSearch)) setPanel(data);
      else if (mode === "replace") {
        setTurn(data);
        setPanel(null);
      }
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      return null;
    } finally {
      setBusy(false);
    }
  }
  // "Yes, it's mine" on a public school card. The backend keeps only the school ID.
  onZonedTap((schoolId, value) => void run({ action: "refresh", zoned: { school_id: schoolId, value } }));

  async function onSearch(event?: FormEvent, text?: string) {
    event?.preventDefault();
    const message = (text ?? query).trim();
    if (!message) return;
    setQuery(message);
    setView("search");
    setPicked([]);
    await run({ message });
  }

  async function refreshSaved(nextSession = sessionId) {
    if (!nextSession) return;
    const response = await fetch(`/api/session/${nextSession}`);
    const data = await response.json();
    setSaved(data.saved ?? []);
    setChecklist(data.checklist ?? []);
  }

  async function openInbox() {
    setView("inbox");
    const response = await fetch("/api/inbox");
    const data = await response.json();
    setInbox(data.items ?? []);
  }

  const results = blockOf(blocks, "results");
  const grid = blockOf(blocks, "evidence_grid");
  const question = blockOf(blocks, "question");
  const message = blockOf(blocks, "message");

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <strong>Guided Search</strong>
          <span>Florida prototype · synthetic schools · facts come from the data</span>
        </div>
        <nav className="nav">
          <button aria-pressed={view === "search"} onClick={() => setView("search")}>Search</button>
          <button
            aria-pressed={view === "saved"}
            onClick={async () => {
              setView("saved");
              await refreshSaved();
            }}
          >
            Saved ({saved.length})
          </button>
          <button aria-pressed={view === "inbox"} onClick={() => void openInbox()}>School inbox</button>
        </nav>
      </header>
      <main className="wrap">
        {view === "search" && (
          <>
            <form className="search" onSubmit={(event) => void onSearch(event)}>
              <input
                aria-label="Search schools"
                placeholder="Describe the school you need"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="primary" disabled={busy}>{busy ? "Looking" : "Search"}</button>
            </form>
            {!turn && (
              <p className="hint">
                Try the demo:{" "}
                <button type="button" onClick={() => void onSearch(undefined, DEMO_QUERY)}>{DEMO_QUERY}</button>
              </p>
            )}
            {error && <p className="error">{error}</p>}
            {criteria.length > 0 && (
              <ChipRow
                criteria={criteria}
                onChange={(next) => void run({ action: "refresh", criteria: next })}
              />
            )}
            {message && <p className="lead">{String(message.text ?? "")}</p>}
            {question && (
              <Question
                payload={question}
                onPick={(optionId) => void run({ action: "refresh", answer: { question_id: question.id, option_id: optionId } })}
              />
            )}
            {panel && <Panel turn={panel} onClose={() => setPanel(null)} />}
            <CardList
              title="Matches"
              cards={(results?.schools as Card[]) ?? []}
              criteria={criteria}
              picked={picked}
              onPick={setPicked}
              onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
              onSave={async (id) => {
                const data = await run({ action: "save", school_ids: [id] }, "keep");
                if (data) await refreshSaved(data.session_id);
              }}
              onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
              onFeedback={(id, vote, reason) => void run({ action: "feedback", feedback: { school_id: id, vote, reason } })}
              onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
            />
            <CardList
              title="Missing a fact we can ask about"
              cards={(results?.gaps as Card[]) ?? []}
              criteria={criteria}
              picked={picked}
              onPick={setPicked}
              onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
              onSave={async (id) => {
                const data = await run({ action: "save", school_ids: [id] }, "keep");
                if (data) await refreshSaved(data.session_id);
              }}
              onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
              onFeedback={(id, vote, reason) => void run({ action: "feedback", feedback: { school_id: id, vote, reason } })}
              onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
            />
            <CardList
              title="Missed a must-have"
              cards={(results?.missed as Card[]) ?? []}
              criteria={criteria}
              picked={picked}
              onPick={setPicked}
              onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
              onSave={async (id) => {
                const data = await run({ action: "save", school_ids: [id] }, "keep");
                if (data) await refreshSaved(data.session_id);
              }}
              onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
              onFeedback={(id, vote, reason) => void run({ action: "feedback", feedback: { school_id: id, vote, reason } })}
              onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
            />
            {grid && <Grid payload={grid} />}
            {picked.length === 2 && (
              <p className="hint">
                <button type="button" className="primary" onClick={() => void run({ action: "compare", school_ids: picked }, "panel")}>
                  Compare these two
                </button>
              </p>
            )}
            {turn && (
              <form
                className="search"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (why.trim()) void run({ message: why.startsWith("Why") ? why : `Why isn't ${why} here?` }, "panel");
                }}
              >
                <input aria-label="Why isn't a school listed" placeholder="Why isn't a school here?" value={why} onChange={(event) => setWhy(event.target.value)} />
                <button className="ghost" type="submit">Explain</button>
              </form>
            )}
          </>
        )}
        {view === "saved" && (
          <section>
            <h2 className="section-title">Saved schools</h2>
            {saved.length === 0 && <p>Save a school from a result card. The visit list is built from what is still unknown.</p>}
            <ul className="checklist">
              {saved.map((school) => (
                <li key={school.id}><strong>{school.name}</strong> · {school.city}<SavedDeadline access={(school as { access?: Access }).access} /></li>
              ))}
            </ul>
            {checklist.length > 0 && (
              <>
                <h2 className="section-title">Visit checklist</h2>
                <ul className="checklist">
                  {checklist.map((item, index) => (
                    <li key={index}><strong>{item.school_name}.</strong> {item.question}</li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
        {view === "inbox" && <Inbox items={inbox} onAnswered={() => void openInbox().then(() => run({ action: "refresh" }))} />}
      </main>
    </div>
  );
}

function blockOf(blocks: Block[], type: string) {
  return blocks.find((block) => block.type === type)?.payload ?? null;
}

function ChipRow({ criteria, onChange }: { criteria: Criterion[]; onChange: (next: Criterion[]) => void }) {
  const cycle: Record<string, Criterion["strength"]> = { require: "prefer", prefer: "avoid", avoid: "require" };
  return (
    <div className="chips" aria-label="Criteria">
      {criteria.map((item) => (
        <span className="chip" key={item.id}>
          <b>{item.text}</b>
          {item.kind === "need" || item.kind === "distance" ? (
            <button
              className={`strength-${item.strength}`}
              onClick={() => onChange(criteria.map((row) => (row.id === item.id ? { ...row, strength: cycle[row.strength] } : row)))}
            >
              {item.strength}
            </button>
          ) : (
            <span>{item.kind === "grade" ? "grade" : item.kind === "location" ? "city" : "type"}</span>
          )}
          <button aria-label={`Remove ${item.text}`} onClick={() => onChange(criteria.filter((row) => row.id !== item.id))}>×</button>
        </span>
      ))}
    </div>
  );
}

function Question({ payload, onPick }: { payload: Record<string, unknown>; onPick: (id: string) => void }) {
  const options = (payload.options as { id: string; label: string }[]) ?? [];
  return (
    <section className="question">
      <p>{String(payload.text)}</p>
      <div className="options">
        {options.map((option) => (
          <button key={option.id} onClick={() => onPick(option.id)}>{option.label}</button>
        ))}
      </div>
    </section>
  );
}

function CardList(props: {
  title: string;
  cards: Card[];
  criteria: Criterion[];
  picked: string[];
  onPick: (ids: string[]) => void;
  onOpen: (id: string) => void;
  onSave: (id: string) => void;
  onAsk: (id: string, need: string) => void;
  onFeedback: (id: string, vote: string, reason?: string) => void;
  onCost: (id: string) => void;
}) {
  const { title, cards } = props;
  if (!cards.length) return null;
  return (
    <section>
      <h2 className="section-title">{title}</h2>
      <div className="cards">
        {cards.map((card) => (
          <SchoolCard
            key={card.id}
            card={card}
            criteria={props.criteria}
            picked={props.picked}
            onPick={props.onPick}
            onOpen={props.onOpen}
            onSave={props.onSave}
            onAsk={props.onAsk}
            onFeedback={props.onFeedback}
            onCost={props.onCost}
          />
        ))}
      </div>
    </section>
  );
}

function SchoolCard({
  card,
  criteria,
  picked,
  onPick,
  onOpen,
  onSave,
  onAsk,
  onFeedback,
  onCost,
}: {
  card: Card;
  criteria: Criterion[];
  picked: string[];
  onPick: (ids: string[]) => void;
  onOpen: (id: string) => void;
  onSave: (id: string) => void;
  onAsk: (id: string, need: string) => void;
  onFeedback: (id: string, vote: string, reason?: string) => void;
  onCost: (id: string) => void;
}) {
  const [reasons, setReasons] = useState(false);
  const labels = useMemo(() => new Map(criteria.map((item) => [item.id, item.text])), [criteria]);
  const needs = useMemo(() => new Map(criteria.map((item) => [item.id, item.need])), [criteria]);
  const selected = picked.includes(card.id);
  const levels = (card.level_codes ?? []).map((code) => LEVEL[code] ?? code).join(", ");
  return (
    <article className={selected ? "card compare-on" : "card"}>
      <header>
        <div>
          <h3><button onClick={() => onOpen(card.id)}>{card.name}</button></h3>
          <div className="meta">
            {card.city} · {card.entity_type} · {levels}
            {card.distance_miles != null ? ` · ${card.distance_miles} miles` : ""}
          </div>
        </div>
        <div className="score">
          <strong>{Math.round(card.match * 100)}%</strong>
          <span>Verified {card.verified}</span>
        </div>
      </header>
      {card.summary && <p className="summary">{card.summary}</p>}
      <GettingInLine schoolId={card.id} access={(card as Card & { access?: Access }).access} />
      <div className="evidence">
        {card.evidence.map((row) => (
          <EvidenceRow
            key={row.criterion_id}
            row={row}
            label={labels.get(row.criterion_id) ?? row.criterion_id}
            onAsk={
              row.status === "unknown" && needs.get(row.criterion_id)
                ? () => onAsk(card.id, needs.get(row.criterion_id) as string)
                : undefined
            }
          />
        ))}
      </div>
      <div className="row-actions">
        <button onClick={() => onSave(card.id)}>Save</button>
        <button
          aria-pressed={selected}
          onClick={() => onPick(selected ? picked.filter((id) => id !== card.id) : [...picked, card.id].slice(-2))}
        >
          {selected ? "Selected" : "Compare"}
        </button>
        {card.entity_type === "private" && <button onClick={() => onCost(card.id)}>Cost after scholarships</button>}
        <button onClick={() => onFeedback(card.id, "up")}>Thumbs up</button>
        <button onClick={() => setReasons((open) => !open)}>Thumbs down</button>
      </div>
      {reasons && (
        <div className="reasons">
          {[
            ["too_far", "Too far"],
            ["too_expensive", "Too expensive"],
            ["missing_program", "Missing a program"],
            ["wrong_grade", "Wrong grade"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => { onFeedback(card.id, "down", id); setReasons(false); }}>{label}</button>
          ))}
        </div>
      )}
    </article>
  );
}

function EvidenceRow({ row, label, onAsk }: { row: Evidence; label: string; onAsk?: () => void }) {
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
        {onAsk && <button onClick={onAsk}>Ask the school</button>}
      </div>
    </div>
  );
}

function Grid({ payload }: { payload: Record<string, unknown> }) {
  const schools = (payload.schools as { id: string; name: string }[]) ?? [];
  const criteria = (payload.criteria as { id: string; text: string }[]) ?? [];
  const cells = (payload.cells as Record<string, Record<string, Evidence | null>>) ?? {};
  if (!schools.length) return null;
  return (
    <section>
      <h2 className="section-title">Evidence grid</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>School</th>
              {criteria.map((column) => <th key={column.id}>{column.text}</th>)}
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
    </section>
  );
}

function Panel({ turn, onClose }: { turn: Turn; onClose: () => void }) {
  return (
    <section className="detail">
      <button className="ghost" onClick={onClose}>Close</button>
      {turn.blocks.map((block, index) => {
        if (block.type === "why_not") {
          const payload = block.payload as { school_name?: string; text?: string; change?: string };
          return (
            <div key={index}>
              <h2>{payload.school_name}</h2>
              <p>{payload.text}</p>
              {payload.change && <p>{payload.change}</p>}
            </div>
          );
        }
        if (block.type === "definition") {
          const payload = block.payload as { term?: string; title?: string; text?: string; cite?: string };
          return (
            <div key={index}>
              <h2>{payload.title ?? payload.term}</h2>
              <p>{payload.text}</p>
              <p className="source">Source: {payload.cite}</p>
            </div>
          );
        }
        if (block.type === "cost") {
          const schools = (block.payload.schools as Record<string, unknown>[]) ?? [];
          return (
            <div key={index}>
              <h2>Cost after likely scholarships</h2>
              {schools.map((school) => (
                <div key={String(school.school_id)}>
                  <h3>{String(school.school_name)}</h3>
                  {school.tuition != null && <p>Listed tuition: ${String(school.tuition)}. This is not a net price.</p>}
                  <p>{String(school.disclaimer ?? "")}</p>
                  <ul className="checklist">
                    {((school.lines as Record<string, string>[]) ?? []).map((line, lineIndex) => (
                      <li key={lineIndex}>
                        <strong>{line.wording}</strong> {line.name ? ` ${line.name}.` : ""} {line.eligibility ?? ""}{" "}
                        {line.official_url && <a href={line.official_url}>Official page</a>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          );
        }
        if (block.type === "school_detail") {
          const payload = block.payload as {
            school: Record<string, unknown>;
            reviews: { topic: string; positive: number; negative: number; earliest?: string; latest?: string; quotes: { side: string; date: string; text: string }[] }[];
            card?: Card | null;
          };
          const school = payload.school;
          return (
            <div key={index}>
              <h2>{String(school.name)}</h2>
              <p className="meta">{String(school.street ?? "")} {String(school.city ?? "")} {String(school.state ?? "")}</p>
              <p>
                {String(school.entity_type)} · summary rating {school.summary_rating == null ? "unknown" : String(school.summary_rating)}
                {school.synthetic ? " · synthetic profile" : ""}
              </p>
              {((school.esp_text as string[]) ?? []).map((line) => <p key={line}>{line}</p>)}
              <GettingInDetail access={(payload.card as (Card & { access?: Access }) | null | undefined)?.access} />
              <h3>Reviews by topic</h3>
              {payload.reviews.map((topic) => (
                <div key={topic.topic} className="quote">
                  <strong>{topic.topic}</strong> · {topic.positive} positive · {topic.negative} negative
                  {topic.earliest ? ` · ${topic.earliest} to ${topic.latest}` : ""}
                  {topic.quotes.map((quote, quoteIndex) => (
                    <p key={quoteIndex}>{quote.date} · {quote.side}: {quote.text}</p>
                  ))}
                </div>
              ))}
              <p className="source">Review scores in the file are sentiment, not stars, so they are not shown as a rating.</p>
            </div>
          );
        }
        if (block.type === "comparison") {
          const schools = (block.payload.schools as Card[]) ?? [];
          return (
            <div key={index}>
              <h2>Comparison</h2>
              <div className="cards">
                {schools.map((school) => (
                  <article key={school.id} className="card">
                    <h3>{school.name}</h3>
                    <p>{school.summary}</p>
                  </article>
                ))}
              </div>
            </div>
          );
        }
        if (block.type === "evidence_grid") return <Grid key={index} payload={block.payload} />;
        if (block.type === "message") return <p key={index}>{String(block.payload.text ?? "")}</p>;
        return null;
      })}
    </section>
  );
}

function Inbox({ items, onAnswered }: { items: Record<string, unknown>[]; onAnswered: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, { text: string; value: string }>>({});
  if (!items.length) return <p>No questions yet. Use “Ask the school” on a card with an unknown fact.</p>;
  return (
    <section className="cards">
      <h2 className="section-title">School inbox</h2>
      <p>Questions from several parents about the same need are grouped into one request. Addresses are example.org, so this cannot email a real school.</p>
      {items.map((item) => {
        const id = String(item.id);
        const draft = drafts[id] ?? { text: "", value: "18:00" };
        return (
          <article key={id} className="card">
            <h3>{String(item.school_name)}</h3>
            <p>{String(item.question)}</p>
            <p className="meta">{String(item.parent_count)} parent(s) · {String(item.status)} · {String(item.email_to)}</p>
            {item.status === "open" && (
              <form
                onSubmit={async (event) => {
                  event.preventDefault();
                  await fetch(`/api/inbox/${id}/reply`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: draft.text || "Confirmed.", value: draft.value }),
                  });
                  onAnswered();
                }}
              >
                <div className="search">
                  <input
                    aria-label="School reply"
                    value={draft.text}
                    placeholder="Reply from the school"
                    onChange={(event) => setDrafts({ ...drafts, [id]: { ...draft, text: event.target.value } })}
                  />
                  <input
                    aria-label="Confirmed value"
                    value={draft.value}
                    onChange={(event) => setDrafts({ ...drafts, [id]: { ...draft, value: event.target.value } })}
                  />
                  <button className="primary" type="submit">Send reply</button>
                </div>
              </form>
            )}
            {((item.replies as { text: string }[]) ?? []).map((reply, index) => <p key={index}>{reply.text}</p>)}
          </article>
        );
      })}
    </section>
  );
}
