import { FormEvent, useEffect, useRef, useState } from "react";
import { fetchInbox, fetchSession, postTurn } from "./api";
import { Brief } from "./components/Brief";
import { DetailPanel } from "./components/DetailPanel";
import { EvidenceGrid } from "./components/EvidenceGrid";
import { InboxView } from "./components/InboxView";
import { QuestionPrompt } from "./components/QuestionPrompt";
import { SavedView } from "./components/SavedView";
import { SchoolResult } from "./components/SchoolResult";
import { CommunityHome, CommunityPage, PersonaSwitcher, type CommunityTarget } from "./Community";
import { onZonedTap } from "./GettingIn";
import { DEMO_QUERY, type Block, type Card, type Criterion, type Turn } from "./types";
import "./community.css";

type View = "search" | "saved" | "inbox" | "community";
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
  const [persona, setPersona] = useState("parent_a");
  const [community, setCommunity] = useState<CommunityTarget | null>(null);
  const resultsRef = useRef<HTMLElement | null>(null);

  const criteria = turn?.criteria ?? [];
  const blocks = turn?.blocks ?? [];
  const results = blockOf(blocks, "results");
  const grid = blockOf(blocks, "evidence_grid");
  const questionsBlock = blockOf(blocks, "questions");
  const question = blockOf(blocks, "question");
  const message = blockOf(blocks, "message");
  const hasTurn = Boolean(turn);
  const hasResults = Boolean(results);
  const questionItems =
    (questionsBlock?.items as { id: string; text: string; options: { id: string; label: string }[] }[] | undefined) ??
    (question
      ? [
          {
            id: String(question.id ?? "q"),
            text: String(question.text ?? ""),
            options: (question.options as { id: string; label: string }[]) ?? [],
          },
        ]
      : []);

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

  // "Yes, it's mine" on a public school card. The backend keeps only the school ID.
  onZonedTap((schoolId, value) => void run({ action: "refresh", zoned: { school_id: schoolId, value } }));

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
    if (hasResults && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [hasResults]);

  return (
    <div className={`app ${hasTurn ? "has-results" : "is-landing"}`}>
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
          <button
            type="button"
            aria-pressed={view === "community"}
            onClick={() => {
              setCommunity(null);
              setView("community");
            }}
          >
            Community
          </button>
        </nav>
        <PersonaSwitcher value={persona} onChange={setPersona} />
      </header>

      <main>
        {view === "search" && (
          <>
            <section className={`hero ${hasTurn ? "compact" : ""}`}>
              <div className="hero-copy">
                {!hasTurn ? (
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
                  onChange={(next: Criterion[]) =>
                    void run({ event: "brief_edited", action: "refresh", criteria: next })
                  }
                  onApprove={() => void run({ event: "brief_approved", action: "refresh" })}
                />

                {message && <p className="agent-lead">{String(message.text ?? "")}</p>}

                {questionItems.length > 0 && !hasResults && (
                  <QuestionPrompt
                    items={questionItems}
                    skipLabel={String(questionsBlock?.skip_label ?? "Just show me results")}
                    onPick={(questionId, optionId) =>
                      void run({
                        event: "answers_submitted",
                        action: "refresh",
                        answer: { question_id: questionId, option_id: optionId },
                      })
                    }
                    onSkip={() => void run({ event: "skip_to_results", action: "refresh" })}
                  />
                )}

                {hasResults && (
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
                )}

                {hasResults && (
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
                )}
              </div>
            )}
          </>
        )}

        {view === "saved" && <SavedView saved={saved} checklist={checklist} />}
        {view === "inbox" && (
          <InboxView items={inbox} onAnswered={() => void openInbox().then(() => run({ action: "refresh" }))} />
        )}
        {view === "community" && !community && (
          <CommunityHome onOpen={(schoolId) => setCommunity({ schoolId, from: "home" })} />
        )}
        {view === "community" && community && (
          <CommunityPage
            key={`${community.schoolId}-${community.draftNeed ?? ""}-${community.filterNeed ?? ""}`}
            schoolId={community.schoolId}
            persona={persona}
            sessionId={sessionId}
            draftNeed={community.draftNeed}
            filterNeed={community.filterNeed}
            backLabel={community.from === "results" ? "Back to results" : "All schools"}
            onBack={() => (community.from === "results" ? setView("search") : setCommunity(null))}
            onChanged={() => undefined}
          />
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
