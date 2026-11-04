// The search is one conversation. Parent messages and taps on the right; each
// Guide reply holds that turn's blocks (results, questions, answers) inline.
// The backend keeps the history too (POST /api/chat, backend/agent/conversation.py).
import { FormEvent, useEffect, useRef, useState } from "react";
import { AgentBlocks, ChipRow, type Actions } from "./blocks";
import { DEMO_QUERY, type Criterion, type Turn } from "./types";
import "./chat.css";

export type HistoryEntry = {
  role: "parent" | "agent";
  kind: "message" | "event";
  text: string;
  route?: string | null;
  school_ids?: string[];
};

export type Entry =
  | { role: "parent"; kind: "message" | "event"; text: string }
  | { role: "agent"; turn: Turn }
  | { role: "system"; text: string };

const EXAMPLES = [
  DEMO_QUERY,
  "Elementary school in Jacksonville with after-school care until 6pm",
  "High school in Miami with sports",
];

export function Chat({
  entries,
  criteria,
  actions,
  onSend,
}: {
  entries: Entry[];
  criteria: Criterion[];
  actions: Actions;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const last = useRef<HTMLLIElement>(null);
  const thinking = useRef<HTMLLIElement>(null);
  const { busy, picked, setPicked, send } = actions;

  // The newest Guide reply with results is the list "#2" and "these" refer to.
  const currentResults = entries.reduce(
    (found, entry, index) => (entry.role === "agent" && entry.turn.blocks.some((b) => b.type === "results") ? index : found),
    -1,
  );
  const latestAgent = entries.reduce((found, entry, index) => (entry.role === "agent" ? index : found), -1);

  useEffect(() => {
    // A reply can be tall (cards), so show its top. A parent line or error just needs to be in view.
    const entry = entries[entries.length - 1];
    last.current?.scrollIntoView({ block: entry?.role === "agent" ? "start" : "end", behavior: "smooth" });
  }, [entries.length]);
  useEffect(() => {
    if (busy) thinking.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [busy]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    onSend(message);
  }

  return (
    <div className="chat-view">
      <div className="chat-scroll">
        <ol className="chat-log" aria-live="polite" aria-label="Conversation">
          <li className="chat-entry chat-agent">
            <span className="chat-who">Guide</span>
            <div className="agent-text">
              <p>
                Tell me about the school you need: the grade, the city, and what matters to your family. I'll show the
                schools that fit and the evidence for each one, and you can ask me about any of them.
              </p>
            </div>
            {!entries.length && (
              <div className="chat-chips">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" disabled={busy} onClick={() => onSend(example)}>
                    {example}
                  </button>
                ))}
              </div>
            )}
          </li>
          {entries.map((entry, index) => {
            const ref = index === entries.length - 1 ? last : undefined;
            if (entry.role === "system") {
              return (
                <li key={index} ref={ref} className="chat-entry chat-system">
                  <span className="error">{entry.text}</span>
                </li>
              );
            }
            if (entry.role === "parent") {
              return (
                <li key={index} ref={ref} className={`chat-entry chat-parent chat-${entry.kind}`}>
                  <span className="chat-text">{entry.text}</span>
                </li>
              );
            }
            return (
              <li key={index} ref={ref} className="chat-entry chat-agent">
                <span className="chat-who">Guide</span>
                <AgentBlocks turn={entry.turn} latest={index === latestAgent} current={index === currentResults} actions={actions} />
              </li>
            );
          })}
          {busy && (
            <li ref={thinking} className="chat-entry chat-agent chat-thinking">
              <span className="chat-who">Guide</span>
              <span className="chat-text">Looking…</span>
            </li>
          )}
        </ol>
      </div>
      <div className="composer">
        {criteria.length > 0 && (
          <ChipRow criteria={criteria} disabled={busy} onChange={(next) => send({ action: "refresh", criteria: next })} />
        )}
        {picked.length > 0 && (
          <div className="compare-tray">
            {picked.length === 2 ? (
              <button
                type="button"
                className="primary"
                disabled={busy}
                onClick={() => {
                  send({ action: "compare", school_ids: picked.map((item) => item.id) });
                  setPicked([]);
                }}
              >
                Compare {picked[0].name} and {picked[1].name}
              </button>
            ) : (
              <span>Pick one more school to compare with {picked[0].name}.</span>
            )}
            <button type="button" className="texty" onClick={() => setPicked([])}>Clear</button>
          </div>
        )}
        <form className="chat-input" onSubmit={submit}>
          <input
            aria-label={entries.length ? "Ask about these schools or change your search" : "Describe the school you need"}
            placeholder={entries.length ? "Ask about these schools, like “does #2 have a bus?”, or change your search" : "Describe the school you need"}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <button className="primary" disabled={busy || !text.trim()}>
            {busy ? "…" : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

/**
 * The tap line the backend wrote for this turn ("You saved X."), if it wrote one.
 * History is capped, so find how far it moved by lining up the old tail with the new one.
 */
export function newTapLine(before: HistoryEntry[], after: HistoryEntry[]): string | null {
  // A turn adds at most two entries (the tap line and the reply). With k added, the
  // first after.length - k entries of `after` are the last ones of `before`.
  const kept = (k: number) => after.length - k;
  const linesUp = (k: number) =>
    kept(k) >= 0 &&
    kept(k) <= before.length &&
    JSON.stringify(after.slice(0, kept(k))) === JSON.stringify(before.slice(before.length - kept(k)));
  const added = [1, 2, 0].find(linesUp) ?? 0;
  return after.slice(kept(added)).find((entry) => entry.role === "parent" && entry.kind === "event")?.text ?? null;
}
