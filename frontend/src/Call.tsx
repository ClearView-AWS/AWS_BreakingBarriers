// "Have AI call the school": one phone call asks every open question parents have for a
// school. The panel shows the call live, then what the school said, and refreshes the
// results so the card shows the new facts. Answers change a card only after the backend
// checks them (backend/gaps/phone.py).
import { useEffect, useRef, useState } from "react";
import type { Actions } from "./blocks";
import { t, tn } from "./i18n";
import "./call.css";

type Line = { who: "agent" | "school"; text: string; at?: string };
type Answer = { need: string; label: string; quote: string; value: string | null };
type Call = {
  id: string;
  school_name: string;
  questions: { id: string; question: string }[];
  parent_count: number;
  status: "dialing" | "in_call" | "completed" | "ended" | "no_answer" | "declined" | "failed" | "off";
  transcript: Line[];
  answers: Answer[];
  error?: string | null;
};

const DONE = new Set(["completed", "ended", "no_answer", "declined", "failed", "off"]);
const POLL_MS = 1500;

export function CallButton({ schoolId, schoolName, needs, actions }: { schoolId: string; schoolName: string; needs: string[]; actions: Actions }) {
  const [call, setCall] = useState<Call | null>(null);
  const [starting, setStarting] = useState(false);
  if (!needs.length && !call) return null;

  async function start() {
    setStarting(true);
    try {
      const response = await fetch("/api/calls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ school_id: schoolId, needs, session_id: actions.sessionId ?? null }),
      });
      const data = await response.json();
      if (data.call) setCall(data.call);
    } finally {
      setStarting(false);
    }
  }

  if (call) return <CallPanel initial={call} actions={actions} onClose={() => setCall(null)} />;
  return (
    <div className="call-start">
      <button className="call-button" disabled={starting} onClick={() => void start()}>
        {tn("call.button", needs.length, { school: schoolName })}
      </button>
      <span className="meta">{t("call.hint")}</span>
    </div>
  );
}

function CallPanel({ initial, actions, onClose }: { initial: Call; actions: Actions; onClose: () => void }) {
  const [call, setCall] = useState(initial);
  const refreshed = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);
  const done = DONE.has(call.status);

  useEffect(() => {
    if (done) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`/api/calls/${encodeURIComponent(call.id)}`);
      const data = await response.json();
      if (data.call) setCall(data.call);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [call.id, done]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [call.transcript.length]);

  // New facts from the call: rerun the search once so the card shows them.
  useEffect(() => {
    if (done && call.answers.some((answer) => answer.value) && !refreshed.current) {
      refreshed.current = true;
      actions.send({ action: "refresh" });
    }
  }, [done, call.answers, actions]);

  const live = call.status === "dialing" || call.status === "in_call";
  return (
    <section className={`call-panel ${live ? "is-live" : ""}`} aria-live="polite">
      <header>
        <span className={`call-dot ${call.status}`} aria-hidden />
        <strong>{t(`call.${call.status}`, { school: call.school_name })}</strong>
        {call.parent_count > 0 && <span className="meta">{t("call.asking", { n: call.parent_count })}</span>}
        {done && (
          <button className="texty" onClick={onClose}>
            {t("call.close")}
          </button>
        )}
      </header>
      {call.questions.length > 0 && (
        <ul className="call-questions">
          {call.questions.map((question) => (
            <li key={question.id} className={call.answers.some((answer) => answer.need === question.id) ? "is-answered" : ""}>
              {question.question}
            </li>
          ))}
        </ul>
      )}
      {call.transcript.length > 0 && (
        <div className="call-transcript">
          {call.transcript.map((line, index) => (
            <div key={index} className={`call-line ${line.who}`}>
              <span>{line.who === "agent" ? t("call.ai") : t("call.school")}</span>
              <p>{line.text}</p>
            </div>
          ))}
          {live && <div className="call-line agent typing" aria-hidden><span>{t("call.ai")}</span><p>…</p></div>}
          <div ref={bottom} />
        </div>
      )}
      {done && call.status !== "off" && call.status !== "failed" && (
        <div className="call-result">
          {call.answers.length > 0 ? (
            <>
              <h4>{t("call.learned")}</h4>
              {call.answers.map((answer) => (
                <p key={answer.need}>
                  <strong>{answer.label}{answer.value ? `: ${answer.value}` : ""}</strong> · “{answer.quote}”
                </p>
              ))}
              {call.answers.some((answer) => answer.value) && <p className="meta">{t("call.updated")}</p>}
            </>
          ) : (
            call.status !== "no_answer" && call.status !== "declined" && <p className="meta">{t("call.no_answers")}</p>
          )}
        </div>
      )}
    </section>
  );
}
