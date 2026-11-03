import { FormEvent, useEffect, useState } from "react";

export type Persona = { id: string; name: string; role: "parent" | "school" };

export const PERSONAS: Persona[] = [
  { id: "parent_a", name: "Parent A", role: "parent" },
  { id: "parent_b", name: "Parent B", role: "parent" },
  { id: "school_staff", name: "School staff", role: "school" },
];

type Post = {
  post_id: string;
  thread_id: string;
  school_id: string;
  author: { persona: string; role: string };
  kind: "question" | "experience" | "reply" | "school_answer";
  needs: string[];
  need_labels: string[];
  text: string;
  votes: number;
  voted: boolean;
  created_at: string;
  verified_school: boolean;
  reply_count?: number;
  school_answered?: boolean;
  origin?: string;
  _synthetic?: boolean;
};

type Demand = { need: string; label: string; count: number };
type Safety = { ok: boolean; message: string; findings: { type: string; text: string }[] };
type Tag = { need: string; label: string };

const TIME_NEEDS = new Set(["after_care", "extended_day", "before_care"]);

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

const enc = encodeURIComponent;

export function PersonaSwitcher({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  return (
    <label className="persona">
      <span>Viewing as</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {PERSONAS.map((persona) => (
          <option key={persona.id} value={persona.id}>{persona.name}</option>
        ))}
      </select>
    </label>
  );
}

export function CommunityPage(props: {
  schoolId: string;
  persona: string;
  sessionId: string | null;
  draftNeed?: string | null;
  filterNeed?: string | null;
  onBack: () => void;
}) {
  const { schoolId, persona, sessionId } = props;
  const isSchool = PERSONAS.find((row) => row.id === persona)?.role === "school";
  const [school, setSchool] = useState<{ name: string; city?: string } | null>(null);
  const [demand, setDemand] = useState<Demand[]>([]);
  const [threads, setThreads] = useState<Post[]>([]);
  const [filter, setFilter] = useState<string | null>(props.filterNeed ?? null);
  const [sort, setSort] = useState<"top" | "new">("top");
  const [open, setOpen] = useState<string | null>(null);
  const [digest, setDigest] = useState<{ subject?: string; body?: string; to?: string; mode?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const query = new URLSearchParams({ sort, persona });
      if (filter) query.set("need", filter);
      const data = await api<{ school: { name: string; city?: string }; demand: Demand[]; threads: Post[]; error?: string }>(
        `/api/community/schools/${enc(schoolId)}?${query}`,
      );
      if (data.error) throw new Error(data.error);
      setSchool(data.school);
      setDemand(data.demand);
      setThreads(data.threads);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the community");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schoolId, persona, filter, sort]);

  async function vote(postId: string) {
    const result = await api<{ votes: number; voted: boolean }>(`/api/community/posts/${enc(postId)}/vote`, { persona });
    setThreads((rows) => rows.map((row) => (row.post_id === postId ? { ...row, votes: result.votes, voted: result.voted } : row)));
  }

  async function sendDigest() {
    const data = await api<{ email: { subject: string; body: string; to: string; mode: string } }>(
      `/api/community/schools/${enc(schoolId)}/digest`,
      {},
    );
    setDigest(data.email);
  }

  const filterLabel = filter ? threads.flatMap((t) => t.needs.map((n, i) => [n, t.need_labels[i]])).find(([n]) => n === filter)?.[1] ?? filter : null;

  return (
    <section className="community" data-school-id={schoolId}>
      <button className="ghost" onClick={props.onBack}>Back to results</button>
      <header className="community-head">
        <div>
          <h2>{school?.name ?? "School"} · Community</h2>
          <p className="meta">
            Parents ask and share here. Posts can support what you see on a card. Only data or the school itself confirms it.
          </p>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <div className="demand" aria-label="What parents asked this month">
        <span className="demand-title">Parents asked this month</span>
        {demand.length === 0 && <span className="meta">No questions yet.</span>}
        {demand.map((row) => (
          <button key={row.need} className="demand-chip" aria-pressed={filter === row.need} onClick={() => setFilter(filter === row.need ? null : row.need)}>
            {row.label} <b>{row.count}</b>
          </button>
        ))}
      </div>

      {isSchool && (
        <div className="staff-bar">
          <p>You are viewing as school staff. Answer a thread once and every parent who asked will see it. Your answers carry a Verified school badge.</p>
          <button className="primary" onClick={() => void sendDigest()}>Send digest</button>
        </div>
      )}
      {digest && (
        <article className="digest" aria-label="Digest email">
          <p className="meta">To {digest.to} · {digest.mode === "ses-sandbox" ? "sent through SES sandbox" : "recorded (SES is off)"}</p>
          <h3>{digest.subject}</h3>
          <pre>{digest.body}</pre>
        </article>
      )}

      {!isSchool && (
        <Composer
          schoolId={schoolId}
          persona={persona}
          sessionId={sessionId}
          draftNeed={props.draftNeed ?? null}
          onPosted={() => void load()}
        />
      )}

      <div className="thread-tools">
        <h3 className="section-title">
          Threads{filterLabel ? ` about ${filterLabel}` : ""}
        </h3>
        <div className="options">
          {filter && <button onClick={() => setFilter(null)}>Show all topics</button>}
          <button aria-pressed={sort === "top"} onClick={() => setSort("top")}>Top</button>
          <button aria-pressed={sort === "new"} onClick={() => setSort("new")}>New</button>
        </div>
      </div>
      {threads.length === 0 && <p className="meta">No threads yet. Ask the first question.</p>}
      <ul className="threads">
        {threads.map((thread) => (
          <li key={thread.post_id} className="thread">
            <button className={thread.voted ? "vote on" : "vote"} aria-pressed={thread.voted} aria-label={`Upvote, ${thread.votes} votes`} onClick={() => void vote(thread.post_id)}>
              ▲<b>{thread.votes}</b>
            </button>
            <div className="thread-body">
              <button className="thread-title" aria-expanded={open === thread.post_id} onClick={() => setOpen(open === thread.post_id ? null : thread.post_id)}>
                {thread.text}
              </button>
              <div className="thread-meta">
                <span className={`kind kind-${thread.kind}`}>{thread.kind === "question" ? "Question" : "Experience"}</span>
                {thread.need_labels.map((label) => <span key={label} className="tag">#{label}</span>)}
                <span>{thread.reply_count ?? 0} {thread.reply_count === 1 ? "reply" : "replies"}</span>
                {thread.school_answered && <span className="answered">✓ School answered</span>}
                {thread._synthetic && <span className="meta">sample post</span>}
              </div>
              {open === thread.post_id && (
                <ThreadView threadId={thread.post_id} persona={persona} needs={thread.needs} labels={thread.need_labels} onChanged={() => void load()} />
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SafetyNote({ safety }: { safety: Safety | null }) {
  if (!safety || safety.ok) return null;
  return (
    <div className="error" role="alert">
      <strong>Not posted.</strong> {safety.message}
      {safety.findings.length > 0 && (
        <span> Found: {safety.findings.map((item) => `${item.type} "${item.text}"`).join(", ")}.</span>
      )}
    </div>
  );
}

function Composer(props: { schoolId: string; persona: string; sessionId: string | null; draftNeed: string | null; onPosted: () => void }) {
  const [kind, setKind] = useState<"question" | "experience">("question");
  const [text, setText] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [fromAgent, setFromAgent] = useState(false);
  const [safety, setSafety] = useState<Safety | null>(null);
  const [busy, setBusy] = useState(false);
  const [posted, setPosted] = useState(false);

  useEffect(() => {
    if (!props.draftNeed) return;
    void api<{ text: string; needs: string[]; need_labels: string[] }>("/api/community/draft", {
      school_id: props.schoolId,
      need: props.draftNeed,
    }).then((draft) => {
      setText(draft.text);
      setKind("question");
      setTags(draft.needs.map((need, index) => ({ need, label: draft.need_labels[index] })));
      setPicked(draft.needs);
      setFromAgent(true);
    });
  }, [props.draftNeed, props.schoolId]);

  useEffect(() => {
    const handle = setTimeout(() => {
      if (text.trim().length < 6) return;
      void api<{ tags: Tag[] }>("/api/community/suggest-tags", { text }).then((data) => {
        setTags((current) => {
          const merged = [...current];
          for (const tag of data.tags) if (!merged.some((row) => row.need === tag.need)) merged.push(tag);
          return merged;
        });
      });
    }, 400);
    return () => clearTimeout(handle);
  }, [text]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setPosted(false);
    try {
      const result = await api<{ ok: boolean; safety: Safety }>("/api/community/posts", {
        school_id: props.schoolId,
        persona: props.persona,
        kind,
        text,
        needs: picked,
        origin: fromAgent ? "agent" : "community",
        session_id: props.sessionId,
      });
      setSafety(result.safety);
      if (result.ok) {
        setText("");
        setTags([]);
        setPicked([]);
        setFromAgent(false);
        setPosted(true);
        props.onPosted();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="composer" onSubmit={(event) => void submit(event)}>
      <div className="options" role="tablist">
        <button type="button" role="tab" aria-selected={kind === "question"} aria-pressed={kind === "question"} onClick={() => setKind("question")}>Ask a question</button>
        <button type="button" role="tab" aria-selected={kind === "experience"} aria-pressed={kind === "experience"} onClick={() => setKind("experience")}>Share your experience</button>
      </div>
      {fromAgent && <p className="meta">The assistant drafted this from your search. Edit it if you like. Nothing is posted until you tap Post.</p>}
      <textarea
        aria-label={kind === "question" ? "Your question" : "Your experience"}
        placeholder={kind === "question" ? "What do you want to know from other parents?" : "What has it really been like?"}
        value={text}
        rows={3}
        onChange={(event) => { setText(event.target.value); setSafety(null); setPosted(false); }}
      />
      {tags.length > 0 && (
        <div className="tag-pick" aria-label="Topics">
          <span className="meta">Topics (tap to confirm):</span>
          {tags.map((tag) => (
            <button
              type="button"
              key={tag.need}
              aria-pressed={picked.includes(tag.need)}
              onClick={() => setPicked(picked.includes(tag.need) ? picked.filter((need) => need !== tag.need) : [...picked, tag.need])}
            >
              #{tag.label}
            </button>
          ))}
        </div>
      )}
      <SafetyNote safety={safety} />
      {posted && <p className="ok" role="status">Posted. Names, emails, phone numbers and addresses were checked first.</p>}
      <div className="composer-foot">
        <span className="meta">Don't include names, phone numbers, emails or addresses.</span>
        <button className="primary" disabled={busy || !text.trim()}>{busy ? "Checking" : "Post"}</button>
      </div>
    </form>
  );
}

function ThreadView(props: { threadId: string; persona: string; needs: string[]; labels: string[]; onChanged: () => void }) {
  const isSchool = PERSONAS.find((row) => row.id === props.persona)?.role === "school";
  const [replies, setReplies] = useState<Post[]>([]);
  const [text, setText] = useState("");
  const [safety, setSafety] = useState<Safety | null>(null);
  const [need, setNeed] = useState(props.needs[0] ?? "");
  const [value, setValue] = useState("18:00");
  const [offers, setOffers] = useState<"yes" | "no" | "info">("yes");

  async function load() {
    const data = await api<{ replies: Post[] }>(`/api/community/threads/${enc(props.threadId)}?persona=${enc(props.persona)}`);
    setReplies(data.replies ?? []);
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.threadId, props.persona]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    let answer: Record<string, unknown> | null = null;
    if (isSchool && need) {
      answer = TIME_NEEDS.has(need)
        ? { need, value }
        : offers === "info" ? null : { need, offers: offers === "yes" };
    }
    const result = await api<{ ok: boolean; safety: Safety }>(`/api/community/threads/${enc(props.threadId)}/replies`, {
      persona: props.persona,
      text,
      answer,
    });
    setSafety(result.safety);
    if (result.ok) {
      setText("");
      await load();
      props.onChanged();
    }
  }

  return (
    <div className="replies">
      {replies.map((reply) => (
        <div key={reply.post_id} className={reply.verified_school ? "reply school" : "reply"}>
          {reply.verified_school && <span className="verified">✓ Verified school</span>}
          <p>{reply.text}</p>
          <span className="meta">{reply.created_at}{reply._synthetic ? " · sample post" : ""}</span>
        </div>
      ))}
      <form className="reply-form" onSubmit={(event) => void submit(event)}>
        <textarea
          aria-label={isSchool ? "Answer as the school" : "Reply"}
          placeholder={isSchool ? "Answer once for every parent who asked" : "Write a reply"}
          rows={2}
          value={text}
          onChange={(event) => { setText(event.target.value); setSafety(null); }}
        />
        {isSchool && props.needs.length > 0 && (
          <div className="answer-tools">
            <label>
              Topic
              <select value={need} onChange={(event) => setNeed(event.target.value)}>
                {props.needs.map((row, index) => <option key={row} value={row}>{props.labels[index] ?? row}</option>)}
              </select>
            </label>
            {TIME_NEEDS.has(need) ? (
              <label>
                Ends at
                <input type="time" value={value} onChange={(event) => setValue(event.target.value)} />
              </label>
            ) : (
              <label>
                This answer
                <select value={offers} onChange={(event) => setOffers(event.target.value as "yes" | "no" | "info")}>
                  <option value="yes">confirms we offer it</option>
                  <option value="no">says we don't offer it</option>
                  <option value="info">is just information</option>
                </select>
              </label>
            )}
          </div>
        )}
        <SafetyNote safety={safety} />
        <button className="primary" disabled={!text.trim()}>{isSchool ? "Post answer" : "Reply"}</button>
      </form>
    </div>
  );
}
