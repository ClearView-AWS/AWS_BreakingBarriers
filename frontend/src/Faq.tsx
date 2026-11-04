import { useEffect, useMemo, useState } from "react";

type FaqRow = {
  id: string;
  question: string;
  answer: string | null;
  source: string | null;
  added: boolean;
  asked: number;
  asked_by_me: boolean;
};

async function call(path: string, body?: Record<string, unknown>) {
  const response = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  if (!response.ok) throw new Error(`FAQ request failed (${response.status})`);
  return response.json();
}

function words(text: string) {
  return new Set(text.toLowerCase().match(/[a-z0-9]+/g) ?? []);
}

/** A round button in the bottom right that opens the common questions sidebar. */
export function FaqWidget({ persona }: { persona: string }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<FaqRow[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    call(`/api/faq?persona=${encodeURIComponent(persona)}`).then((data) => setRows(data.questions)).catch(() => setNote("Could not load questions."));
  }, [open, persona]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // While typing, show questions that already cover it so parents can add their ask there.
  const matches = useMemo(() => {
    const wanted = words(draft);
    if (wanted.size < 2) return [];
    return rows.filter((row) => {
      const have = words(row.question);
      const shared = [...wanted].filter((word) => word.length > 3 && have.has(word)).length;
      return shared >= 2;
    }).slice(0, 3);
  }, [draft, rows]);

  async function toggle(row: FaqRow) {
    const data = await call(`/api/faq/${encodeURIComponent(row.id)}/ask`, { persona });
    setRows(data.questions);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.trim() || busy) return;
    setBusy(true);
    setNote("");
    try {
      const data = await call("/api/faq", { persona, text: draft });
      if (data.ok) {
        setRows(data.questions);
        setExpanded(data.id);
        setDraft("");
        setNote(data.existing ? "That question is already here. Your ask was added to it." : "Added. It shows as unanswered until the team answers it.");
      } else {
        setNote(data.message ?? "That question could not be added.");
      }
    } catch {
      setNote("Could not add the question. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        className={`faq-fab ${open ? "is-open" : ""}`}
        aria-label={open ? "Close common questions" : "Common questions"}
        aria-expanded={open}
        aria-controls="faq-panel"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "×" : "?"}
      </button>
      {open && (
        <aside id="faq-panel" className="faq-panel" aria-label="Common questions">
          <header>
            <h2>Common questions</h2>
            <p>Sorted by how many parents asked. Tap "I have this question too" to add yours.</p>
          </header>
          <ol className="faq-list">
            {rows.map((row) => (
              <li key={row.id} className={row.answer ? "" : "faq-unanswered"}>
                <button className="faq-q" aria-expanded={expanded === row.id} onClick={() => setExpanded(expanded === row.id ? null : row.id)}>
                  {row.question}
                </button>
                {expanded === row.id && (
                  <div className="faq-a">
                    {row.answer ? <p>{row.answer}</p> : <p className="faq-pending">Not answered yet.</p>}
                    {row.source && <p className="faq-source">Source: {row.source}</p>}
                  </div>
                )}
                <button className={`faq-ask ${row.asked_by_me ? "is-on" : ""}`} aria-pressed={row.asked_by_me} onClick={() => void toggle(row)}>
                  {row.asked_by_me ? "✓ You asked this" : "I have this question too"}
                  {row.asked > 0 && <span> · {row.asked} {row.asked === 1 ? "parent" : "parents"}</span>}
                </button>
              </li>
            ))}
          </ol>
          <form className="faq-form" onSubmit={submit}>
            <label htmlFor="faq-new">Ask a new question</label>
            <textarea id="faq-new" rows={2} maxLength={200} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Do not include names, emails or addresses." />
            {matches.length > 0 && (
              <div className="faq-matches">
                <span>Already asked:</span>
                {matches.map((row) => (
                  <button type="button" key={row.id} onClick={() => { setExpanded(row.id); setDraft(""); }}>{row.question}</button>
                ))}
              </div>
            )}
            <button className="primary" type="submit" disabled={busy || !draft.trim()}>Add question</button>
            {note && <p className="faq-note" role="status">{note}</p>}
          </form>
        </aside>
      )}
    </>
  );
}
