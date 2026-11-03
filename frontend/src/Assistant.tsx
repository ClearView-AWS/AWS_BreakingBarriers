import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

// Highlight text on a result and a small circle appears beside it. Tapping it opens a
// panel that explains the highlighted text from that school's own evidence. Every
// sentence shows where it came from; the backend drops any sentence without a source.

type Cite = { path: string; label: string };
type Answer = {
  school_id: string | null;
  school_name: string | null;
  sentences: { text: string; cites: Cite[] }[];
  next_step: string | null;
  follow_ups: string[];
  mode: "rules" | "bedrock";
};
type Target = { text: string; schoolId: string | null; criterionId: string | null; rect: DOMRect };
type Exchange = { question: string; answer: Answer | null; error?: string };

const MIN_CHARS = 2;
const MAX_CHARS = 500;
const BUBBLE = 34;

function closestData(node: Node | null, attribute: string): string | null {
  let element: Element | null = node instanceof Element ? node : node?.parentElement ?? null;
  while (element) {
    const value = element.getAttribute(attribute);
    if (value) return value;
    element = element.parentElement;
  }
  return null;
}

function readSelection(root: Element | null): Target | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0 || !root) return null;
  const text = selection.toString().replace(/\s+/g, " ").trim();
  if (text.length < MIN_CHARS) return null;
  const range = selection.getRangeAt(0);
  const anchor = range.commonAncestorContainer;
  const element = anchor instanceof Element ? anchor : anchor.parentElement;
  if (!element || !root.contains(element)) return null;
  // Typing in a field is not a question about the results.
  if (element.closest("input, textarea, select, [contenteditable='true'], .assist-panel")) return null;
  const rects = range.getClientRects();
  const rect = rects.length ? rects[rects.length - 1] : range.getBoundingClientRect();
  return {
    text: text.slice(0, MAX_CHARS),
    schoolId: closestData(range.startContainer, "data-school-id") ?? closestData(anchor, "data-school-id"),
    criterionId: closestData(range.startContainer, "data-criterion-id"),
    rect,
  };
}

function clamp(value: number, low: number, high: number) {
  return Math.max(low, Math.min(high, value));
}

async function fetchAnswer(sessionId: string | null, target: Target, question: string): Promise<Answer> {
  const response = await fetch("/api/assist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      text: target.text,
      question,
      school_id: target.schoolId,
      criterion_id: target.criterionId,
    }),
  });
  if (!response.ok) throw new Error(`The assistant could not answer (${response.status}).`);
  return response.json();
}

function SparkIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2.5l1.9 5.6 5.6 1.9-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9L12 2.5zM18.5 15l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6z"
        fill="currentColor"
      />
    </svg>
  );
}

export function HighlightAssistant({ sessionId, rootSelector = "main" }: { sessionId: string | null; rootSelector?: string }) {
  const [bubble, setBubble] = useState<Target | null>(null);
  const [panel, setPanel] = useState<Target | null>(null);
  const [history, setHistory] = useState<Exchange[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  const refresh = useCallback(() => {
    // Wait a tick so the browser has finished updating the selection.
    window.setTimeout(() => {
      const found = readSelection(document.querySelector(rootSelector));
      setBubble(found);
    }, 0);
  }, [rootSelector]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBubble(null);
        if (panel) close();
        return;
      }
      if (event.shiftKey || event.key.startsWith("Arrow")) refresh();
    };
    const onScroll = () => setBubble((current) => (current ? readSelection(document.querySelector(rootSelector)) : null));
    document.addEventListener("mouseup", refresh);
    document.addEventListener("touchend", refresh);
    document.addEventListener("keyup", onKey);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll);
    return () => {
      document.removeEventListener("mouseup", refresh);
      document.removeEventListener("touchend", refresh);
      document.removeEventListener("keyup", onKey);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, rootSelector, panel]);

  useEffect(() => {
    if (!panel) return;
    const onDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target)) return;
      if ((target as Element).closest?.(".assist-bubble")) return;
      close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panel]);

  useEffect(() => {
    // Keep the newest answer in view.
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [history]);

  async function ask(target: Target, text: string) {
    setBusy(true);
    setHistory((rows) => [...rows, { question: text, answer: null }]);
    try {
      const answer = await fetchAnswer(sessionId, target, text);
      setHistory((rows) => rows.map((row, index) => (index === rows.length - 1 ? { ...row, answer } : row)));
    } catch (err) {
      const message = err instanceof Error ? err.message : "The assistant could not answer.";
      setHistory((rows) => rows.map((row, index) => (index === rows.length - 1 ? { ...row, error: message } : row)));
    } finally {
      setBusy(false);
    }
  }

  function open() {
    if (!bubble) return;
    opener.current = document.activeElement as HTMLElement | null;
    setPanel(bubble);
    setHistory([]);
    setQuestion("");
    setBubble(null);
    void ask(bubble, "");
    window.setTimeout(() => panelRef.current?.focus(), 0);
  }

  function close() {
    setPanel(null);
    setHistory([]);
    opener.current?.focus?.();
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!panel || !text || busy) return;
    setQuestion("");
    void ask(panel, text);
  }

  // Sit just above the end of the highlight, so the circle never covers the buttons below it.
  const roomAbove = bubble ? bubble.rect.top - BUBBLE - 6 > 72 : false;
  const bubbleStyle = bubble
    ? {
        left: clamp(bubble.rect.right - BUBBLE / 2, 8, window.innerWidth - BUBBLE - 8),
        top: clamp(roomAbove ? bubble.rect.top - BUBBLE - 6 : bubble.rect.bottom + 6, 8, window.innerHeight - BUBBLE - 8),
      }
    : undefined;

  const width = Math.min(380, window.innerWidth - 16);
  const panelStyle = panel
    ? {
        left: clamp(panel.rect.left, 8, window.innerWidth - width - 8),
        top: clamp(panel.rect.bottom + 10, 8, Math.max(8, window.innerHeight - 460)),
        width,
      }
    : undefined;

  const latest = history[history.length - 1];
  const followUps = latest?.answer?.follow_ups ?? [];
  const quote = panel ? (panel.text.length > 160 ? `${panel.text.slice(0, 157)}…` : panel.text) : "";

  return (
    <>
      {bubble && !panel && (
        <button
          type="button"
          className="assist-bubble"
          style={bubbleStyle}
          aria-label={`Ask the assistant about “${bubble.text.slice(0, 60)}”`}
          title="Ask about this"
          // Keep the highlight while the circle is pressed.
          onMouseDown={(event) => event.preventDefault()}
          onClick={open}
        >
          <SparkIcon />
        </button>
      )}
      {panel && (
        <aside
          ref={panelRef}
          className="assist-panel"
          style={panelStyle}
          role="dialog"
          aria-label="Assistant"
          tabIndex={-1}
        >
          <header>
            <div>
              <span className="assist-eyebrow"><SparkIcon /> Assistant</span>
              {latest?.answer?.school_name && <span className="assist-school">{latest.answer.school_name}</span>}
            </div>
            <button type="button" className="icon" aria-label="Close assistant" onClick={close}>×</button>
          </header>
          <blockquote className="assist-quote">“{quote}”</blockquote>
          <div className="assist-thread" aria-live="polite" ref={threadRef}>
            {history.map((row, index) => (
              <div key={index} className="assist-turn">
                {row.question && <p className="assist-question">{row.question}</p>}
                {row.error && <p className="error">{row.error}</p>}
                {!row.answer && !row.error && (
                  <div className="assist-loading" aria-label="Thinking">
                    <span /><span /><span />
                  </div>
                )}
                {row.answer && (
                  <>
                    {row.answer.sentences.map((sentence, sIndex) => (
                      <p key={sIndex} className="assist-sentence">
                        {sentence.text}
                        {sentence.cites.map((cite) => (
                          <span key={cite.path} className="assist-cite" title={cite.path}>{cite.label}</span>
                        ))}
                      </p>
                    ))}
                    {row.answer.next_step && <p className="assist-next">{row.answer.next_step}</p>}
                    <p className="assist-mode">
                      {row.answer.mode === "bedrock"
                        ? "Worded by Bedrock from this school's data. Sentences without a source were removed."
                        : "Answered from this school's data."}
                    </p>
                  </>
                )}
              </div>
            ))}
          </div>
          {followUps.length > 0 && !busy && (
            <div className="assist-followups">
              {followUps.map((item) => (
                <button key={item} type="button" onClick={() => void ask(panel, item)}>{item}</button>
              ))}
            </div>
          )}
          <form className="assist-form" onSubmit={submit}>
            <input
              aria-label="Ask a follow-up question"
              placeholder="Ask a follow-up"
              value={question}
              maxLength={300}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button className="primary" disabled={busy || !question.trim()}>Ask</button>
          </form>
        </aside>
      )}
    </>
  );
}
