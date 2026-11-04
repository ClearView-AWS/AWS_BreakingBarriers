import { FormEvent, useEffect, useRef, useState } from "react";
import { fetchInbox, fetchSession, postTurn } from "./api";
import { Brief } from "./components/Brief";
import { DetailPanel } from "./components/DetailPanel";
import { EvidenceGrid } from "./components/EvidenceGrid";
import { InboxView } from "./components/InboxView";
import { QuestionPrompt } from "./components/QuestionPrompt";
import { SavedView } from "./components/SavedView";
import { SchoolResult } from "./components/SchoolResult";
import { DEMO_QUERY, type Block, type Card, type Criterion, type Turn } from "./types";

type View = "search" | "saved" | "inbox";
type ResultMode = "list" | "grid";

function blockOf(blocks: Block[], type: string) {
  return blocks.find((block) => block.type === type)?.payload ?? null;
}

export function App() {
  const [view, setView] = useState<View>("search");
  const [query, setQuery] = useState("");
  const [refine, setRefine] = useState("");
  const [why, setWhy] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [panel, setPanel] = useState<Turn | null>(null);
  const [saved, setSaved] = useState<{ id: string; name: string; city?: string }[]>([]);
  const [checklist, setChecklist] = useState<{ school_name: string; question: string }[]>([]);
  const [inbox, setInbox] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [resultMode, setResultMode] = useState<ResultMode>("list");
  const [questionSkipped, setQuestionSkipped] = useState(false);
  const [briefApproved, setBriefApproved] = useState(false);
  const resultsRef = useRef<HTMLElement | null>(null);

  const criteria = turn?.criteria ?? [];
  const blocks = turn?.blocks ?? [];
  const results = blockOf(blocks, "results");
  const grid = blockOf(blocks, "evidence_grid");
  const question = blockOf(blocks, "question");
  const message = blockOf(blocks, "message");
  const hasResults = Boolean(turn);

  async function run(body: Record<string, unknown>, mode: "replace" | "panel" | "keep" = "replace") {
    setBusy(true);
    setError(null);
    try {
      const data = await postTurn({ session_id: sessionId, ...body });
      setSessionId(data.session_id);
      if (mode === "panel") setPanel(data);
      else if (mode === "replace") {
        setTurn(data);
        setPanel(null);
        setQuestionSkipped(false);
        setBriefApproved(false);
      }
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(event?: FormEvent, text?: string) {
    event?.preventDefault();
    const messageText = (text ?? query).trim();
    if (!messageText) return;
    setQuery(messageText);
    setView("search");
    setPicked([]);
    setResultMode("list");
    await run({ message: messageText });
  }

  async function onRefine(event: FormEvent) {
    event.preventDefault();
    const messageText = refine.trim();
    if (!messageText) return;
    setRefine("");
    await run({ message: messageText });
  }

  async function refreshSaved(nextSession = sessionId) {
    if (!nextSession) return;
    const data = await fetchSession(nextSession);
    setSaved(data.saved ?? []);
    setChecklist(data.checklist ?? []);
  }

  async function openInbox() {
    setView("inbox");
    const data = await fetchInbox();
    setInbox(data.items ?? []);
  }

  useEffect(() => {
    if (briefApproved && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [briefApproved]);

  return (
    <div className={`app ${hasResults ? "has-results" : "is-landing"}`}>
      <header className="topbar">
        <a className="brand" href="/" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">
            <strong>GreatSchools</strong>
            <em>Guided Search</em>
          </span>
        </a>
        <nav className="nav" aria-label="Primary">
          <button type="button" aria-pressed={view === "search"} onClick={() => setView("search")}>
            Search
          </button>
          <button
            type="button"
            aria-pressed={view === "saved"}
            onClick={async () => {
              setView("saved");
              await refreshSaved();
            }}
          >
            Saved{saved.length ? ` (${saved.length})` : ""}
          </button>
          <button type="button" aria-pressed={view === "inbox"} onClick={() => void openInbox()}>
            School inbox
          </button>
        </nav>
      </header>

      <main>
        {view === "search" && (
          <>
            <section className={`hero ${hasResults ? "compact" : ""}`}>
              <div className="hero-copy">
                {!hasResults ? (
                  <>
                    <p className="eyebrow">Florida prototype · synthetic schools</p>
                    <h1>
                      <span className="brand-inline">GreatSchools</span>
                      <span className="hero-line">We investigate. You decide.</span>
                    </h1>
                    <p className="lede">
                      Tell us what your family needs in plain language. Every fact on screen cites the data behind it.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="eyebrow">Your search</p>
                    <h1 className="hero-compact-title">Refine what matters</h1>
                  </>
                )}
              </div>

              <form className="search-bar" onSubmit={(event) => void onSearch(event)}>
                <label className="sr-only" htmlFor="school-search">
                  Describe the school you need
                </label>
                <input
                  id="school-search"
                  placeholder="Middle school in Jacksonville with STEM and after-school care…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <button className="btn-primary" disabled={busy} type="submit">
                  {busy ? "Looking…" : "Search"}
                </button>
              </form>

              {!turn && (
                <p className="demo-hint">
                  Try the demo:{" "}
                  <button type="button" onClick={() => void onSearch(undefined, DEMO_QUERY)}>
                    {DEMO_QUERY}
                  </button>
                </p>
              )}
            </section>

            {error && <p className="error">{error}</p>}

            {turn && (
              <div className="workspace">
                <Brief
                  criteria={criteria}
                  onChange={(next: Criterion[]) => void run({ action: "refresh", criteria: next })}
                  onApprove={() => setBriefApproved(true)}
                />

                {message && <p className="agent-lead">{String(message.text ?? "")}</p>}

                {question && !questionSkipped && (
                  <QuestionPrompt
                    text={String(question.text ?? "")}
                    options={(question.options as { id: string; label: string }[]) ?? []}
                    onPick={(optionId) =>
                      void run({
                        action: "refresh",
                        answer: { question_id: question.id, option_id: optionId },
                      })
                    }
                    onSkip={() => setQuestionSkipped(true)}
                  />
                )}

                <section className="results" ref={resultsRef}>
                  <div className="results-toolbar">
                    <div>
                      <h2>Matches</h2>
                      <p>Ranked by fit. Coverage is shown beside the match score.</p>
                    </div>
                    <div className="view-toggle" role="group" aria-label="Result layout">
                      <button type="button" aria-pressed={resultMode === "list"} onClick={() => setResultMode("list")}>
                        List
                      </button>
                      <button type="button" aria-pressed={resultMode === "grid"} onClick={() => setResultMode("grid")}>
                        Grid
                      </button>
                      <button type="button" disabled title="Map view lands with Amazon Location (M2)">
                        Map
                      </button>
                    </div>
                  </div>

                  {resultMode === "grid" && grid ? (
                    <EvidenceGrid payload={grid} />
                  ) : (
                    <>
                      <ResultSection
                        title="Best matches"
                        cards={(results?.schools as Card[]) ?? []}
                        criteria={criteria}
                        picked={picked}
                        layout={resultMode}
                        onPick={setPicked}
                        onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
                        onSave={async (id) => {
                          const data = await run({ action: "save", school_ids: [id] }, "keep");
                          if (data) await refreshSaved(data.session_id);
                        }}
                        onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
                        onFeedback={(id, vote, reason) =>
                          void run({ action: "feedback", feedback: { school_id: id, vote, reason } })
                        }
                        onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
                      />
                      <ResultSection
                        title="Missing a fact we can ask about"
                        cards={(results?.gaps as Card[]) ?? []}
                        criteria={criteria}
                        picked={picked}
                        layout={resultMode}
                        onPick={setPicked}
                        onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
                        onSave={async (id) => {
                          const data = await run({ action: "save", school_ids: [id] }, "keep");
                          if (data) await refreshSaved(data.session_id);
                        }}
                        onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
                        onFeedback={(id, vote, reason) =>
                          void run({ action: "feedback", feedback: { school_id: id, vote, reason } })
                        }
                        onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
                      />
                      <ResultSection
                        title="Missed a must-have"
                        cards={(results?.missed as Card[]) ?? []}
                        criteria={criteria}
                        picked={picked}
                        layout={resultMode}
                        onPick={setPicked}
                        onOpen={(id) => void run({ action: "school_detail", school_ids: [id] }, "panel")}
                        onSave={async (id) => {
                          const data = await run({ action: "save", school_ids: [id] }, "keep");
                          if (data) await refreshSaved(data.session_id);
                        }}
                        onAsk={(id, need) => void run({ action: "ask_school", school_ids: [id], need })}
                        onFeedback={(id, vote, reason) =>
                          void run({ action: "feedback", feedback: { school_id: id, vote, reason } })
                        }
                        onCost={(id) => void run({ action: "cost", school_ids: [id] }, "panel")}
                      />
                    </>
                  )}

                  {picked.length === 2 && (
                    <div className="compare-bar">
                      <p>Two schools selected.</p>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => void run({ action: "compare", school_ids: picked }, "panel")}
                      >
                        Compare these two
                      </button>
                    </div>
                  )}
                </section>

                <section className="followups">
                  <form className="search-bar slim" onSubmit={(event) => void onRefine(event)}>
                    <label className="sr-only" htmlFor="refine">
                      Refine this search
                    </label>
                    <input
                      id="refine"
                      placeholder="Add something else — smaller classes, bus route, Spanish immersion…"
                      value={refine}
                      onChange={(event) => setRefine(event.target.value)}
                    />
                    <button className="btn-secondary" type="submit" disabled={busy}>
                      Refine
                    </button>
                  </form>
                  <form
                    className="search-bar slim"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (why.trim()) {
                        void run(
                          { message: why.startsWith("Why") ? why : `Why isn't ${why} here?` },
                          "panel",
                        );
                      }
                    }}
                  >
                    <label className="sr-only" htmlFor="why-not">
                      Ask why a school is missing
                    </label>
                    <input
                      id="why-not"
                      placeholder="Why isn’t a school here?"
                      value={why}
                      onChange={(event) => setWhy(event.target.value)}
                    />
                    <button className="btn-secondary" type="submit">
                      Explain
                    </button>
                  </form>
                </section>
              </div>
            )}
          </>
        )}

        {view === "saved" && <SavedView saved={saved} checklist={checklist} />}
        {view === "inbox" && (
          <InboxView items={inbox} onAnswered={() => void openInbox().then(() => run({ action: "refresh" }))} />
        )}
      </main>

      {panel && <DetailPanel turn={panel} onClose={() => setPanel(null)} />}
    </div>
  );
}

function ResultSection(props: {
  title: string;
  cards: Card[];
  criteria: Criterion[];
  picked: string[];
  layout: ResultMode;
  onPick: (ids: string[]) => void;
  onOpen: (id: string) => void;
  onSave: (id: string) => void;
  onAsk: (id: string, need: string) => void;
  onFeedback: (id: string, vote: string, reason?: string) => void;
  onCost: (id: string) => void;
}) {
  const { title, cards, layout } = props;
  if (!cards.length) return null;
  return (
    <section className="result-section">
      <h3>{title}</h3>
      <div className={`school-stack ${layout}`}>
        {cards.map((card) => (
          <SchoolResult
            key={card.id}
            card={card}
            criteria={props.criteria}
            picked={props.picked}
            layout={layout}
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
