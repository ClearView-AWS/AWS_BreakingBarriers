// The search is one conversation. Parent messages and taps on the right; each
// Guide reply holds that turn's blocks (results, questions, answers) inline.
// The backend keeps the history too (POST /api/chat, backend/agent/conversation.py).
import { FormEvent, useEffect, useRef, useState } from "react";
import { AgentBlocks, type Actions } from "./blocks";
import { DEMO_QUERY, type Turn } from "./types";
import { t } from "./i18n";
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

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function Chat({
  entries,
  actions,
  onSend,
}: {
  entries: Entry[];
  actions: Actions;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");
  const last = useRef<HTMLLIElement>(null);
  const thinking = useRef<HTMLLIElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const { busy, picked, setPicked, send } = actions;

  // The newest Guide reply with results is the list "#2" and "these" refer to.
  const currentResults = entries.reduce(
    (found, entry, index) => (entry.role === "agent" && entry.turn.blocks.some((b) => b.type === "results") ? index : found),
    -1,
  );
  const latestAgent = entries.reduce((found, entry, index) => (entry.role === "agent" ? index : found), -1);
  // The newest reply that carries the brief shows it; it's where the search is read and edited.
  const currentBrief = entries.reduce(
    (found, entry, index) => (entry.role === "agent" && entry.turn.blocks.some((b) => b.type === "brief") ? index : found),
    -1,
  );

  useEffect(() => {
    // A reply can be tall (cards), so show its top. A parent line or error just needs to be in view.
    const entry = entries[entries.length - 1];
    const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
    last.current?.scrollIntoView({ block: entry?.role === "agent" ? "start" : "end", behavior });
  }, [entries.length]);
  useEffect(() => {
    if (busy) {
      thinking.current?.scrollIntoView({ block: "end", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    }
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
      <a className="skip-link" href="#chat-composer">
        {t("a11y.skip_composer")}
      </a>
      <div className="chat-scroll" id="chat-main">
        <ol className="chat-log" aria-live="polite" aria-relevant="additions" aria-busy={busy} aria-label="Conversation">
          {!entries.length && (
            <li className="chat-entry chat-agent chat-first-run">
              <span className="chat-who">{t("chat.guide")}</span>
              <div className="agent-text">
                <p>{t("chat.intro")}</p>
              </div>
              <div className="chat-chips" role="group" aria-label={t("chat.describe")}>
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" disabled={busy} onClick={() => onSend(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </li>
          )}
          {entries.map((entry, index) => {
            const ref = index === entries.length - 1 ? last : undefined;
            if (entry.role === "system") {
              return (
                <li key={index} ref={ref} className="chat-entry chat-system" role="alert">
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
                <span className="chat-who">{t("chat.guide")}</span>
                <AgentBlocks
                  turn={entry.turn}
                  latest={index === latestAgent}
                  current={index === currentResults}
                  briefHere={index === currentBrief}
                  actions={actions}
                />
              </li>
            );
          })}
          {busy && (
            <li ref={thinking} className="chat-entry chat-agent chat-thinking" aria-label={t("a11y.thinking")}>
              <span className="chat-who">{t("chat.guide")}</span>
              <span className="chat-text">{t("chat.looking")}</span>
            </li>
          )}
        </ol>
      </div>
      <div className="composer" id="chat-composer">
        {picked.length > 0 && (
          <div className="compare-tray" role="status">
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
                {t("chat.compare_pair", { a: picked[0].name, b: picked[1].name })}
              </button>
            ) : (
              <span>{t("chat.compare_one", { name: picked[0].name })}</span>
            )}
            <button type="button" className="texty" onClick={() => setPicked([])}>{t("chat.clear")}</button>
          </div>
        )}
        <form className="chat-input" onSubmit={submit}>
          <label className="sr-only" htmlFor="chat-message">
            {entries.length ? t("chat.ask_label") : t("chat.describe")}
          </label>
          <input
            id="chat-message"
            ref={input}
            aria-label={entries.length ? t("chat.ask_label") : t("chat.describe")}
            placeholder={entries.length ? t("chat.ask_placeholder") : t("chat.describe")}
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoComplete="off"
          />
          <button type="submit" className="primary" disabled={busy || !text.trim()}>
            {busy ? "…" : t("chat.send")}
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
