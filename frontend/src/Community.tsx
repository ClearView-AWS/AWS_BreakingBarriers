import { FormEvent, useEffect, useState } from "react";
import "./community.css";
import { t, tn } from "./i18n";
import { SchoolGallery } from "./components/SchoolGallery";

export type Persona = { id: string; name: string; role: "parent" | "school" };

/** Which school page to open, and from where: a result card goes back to results, the tab home goes back home. */
export type CommunityTarget = { schoolId: string; draftNeed?: string | null; filterNeed?: string | null; from?: "results" | "home" };

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
type SchoolQuestion = { id: string; need: string; label: string; question: string; parents: number };
type Safety = { ok: boolean; message: string; findings: { type: string; text: string }[]; checked_by?: string[] };
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
      <span>{t("community.viewing_as")}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {PERSONAS.map((persona) => (
          <option key={persona.id} value={persona.id}>{t(`persona.${persona.id}`)}</option>
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
  backLabel?: string;
  onBack: () => void;
  /** Something was posted. A school answer can change a result card. */
  onChanged?: () => void;
}) {
  const { schoolId, persona, sessionId } = props;
  const isSchool = PERSONAS.find((row) => row.id === persona)?.role === "school";
  const [school, setSchool] = useState<{ name: string; city?: string } | null>(null);
  const [demand, setDemand] = useState<Demand[]>([]);
  const [threads, setThreads] = useState<Post[]>([]);
  const [questions, setQuestions] = useState<SchoolQuestion[]>([]);
  const [filter, setFilter] = useState<string | null>(props.filterNeed ?? null);
  const [sort, setSort] = useState<"top" | "new">("top");
  const [open, setOpen] = useState<string | null>(null);
  const [digest, setDigest] = useState<{ subject?: string; body?: string; to?: string; mode?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const query = new URLSearchParams({ sort, persona });
      if (filter) query.set("need", filter);
      const data = await api<{ school: { name: string; city?: string }; demand: Demand[]; threads: Post[]; questions?: SchoolQuestion[]; error?: string }>(
        `/api/community/schools/${enc(schoolId)}?${query}`,
      );
      if (data.error) throw new Error(data.error);
      setSchool(data.school);
      setDemand(data.demand);
      setThreads(data.threads);
      setQuestions(data.questions ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("community.load_error"));
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
      <button className="ghost" onClick={props.onBack}>{props.backLabel ?? t("app.back_results")}</button>
      <header className="community-head">
        <div>
          <h2>{t("community.title", { school: school?.name ?? t("community.school") })}</h2>
          <p className="meta">{t("community.intro")}</p>
        </div>
      </header>
      {school && <SchoolGallery schoolName={school.name} />}
      {error && <p className="error">{error}</p>}

      <div className="demand" aria-label={t("community.asked_label")}>
        <span className="demand-title">{t("community.asked_title")}</span>
        {demand.length === 0 && <span className="meta">{t("community.no_questions")}</span>}
        {demand.map((row) => (
          <button key={row.need} className="demand-chip" aria-pressed={filter === row.need} onClick={() => setFilter(filter === row.need ? null : row.need)}>
            {row.label} <b>{row.count}</b>
          </button>
        ))}
      </div>

      {isSchool && (
        <div className="staff-bar">
          <p>{t("community.staff_note")}</p>
          <button className="primary" onClick={() => void sendDigest()}>{t("community.send_digest")}</button>
        </div>
      )}
      {isSchool && questions.length > 0 && (
        <SchoolQuestions
          schoolId={schoolId}
          questions={questions}
          onAnswered={() => {
            void load();
            props.onChanged?.();
          }}
        />
      )}
      {digest && (
        <article className="digest" aria-label={t("community.digest_label")}>
          <p className="meta">{t("community.digest_to", { to: digest.to ?? "" })} · {digest.mode === "ses-sandbox" ? t("community.digest_sent") : t("community.digest_recorded")}</p>
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
          onPosted={() => {
            void load();
            props.onChanged?.();
          }}
        />
      )}

      <div className="thread-tools">
        <h3 className="section-title">
          {filterLabel ? t("community.threads_about", { topic: filterLabel }) : t("community.threads")}
        </h3>
        <div className="options">
          {filter && <button onClick={() => setFilter(null)}>{t("community.all_topics")}</button>}
          <button aria-pressed={sort === "top"} onClick={() => setSort("top")}>{t("community.top")}</button>
          <button aria-pressed={sort === "new"} onClick={() => setSort("new")}>{t("community.new")}</button>
        </div>
      </div>
      {threads.length === 0 && <p className="meta">{t("community.no_threads")}</p>}
      <ul className="threads">
        {threads.map((thread) => (
          <li key={thread.post_id} className="thread">
            <button className={thread.voted ? "vote on" : "vote"} aria-pressed={thread.voted} aria-label={t("community.upvote", { n: thread.votes })} onClick={() => void vote(thread.post_id)}>
              ▲<b>{thread.votes}</b>
            </button>
            <div className="thread-body">
              <button className="thread-title" aria-expanded={open === thread.post_id} onClick={() => setOpen(open === thread.post_id ? null : thread.post_id)}>
                {thread.text}
              </button>
              <div className="thread-meta">
                <span className={`kind kind-${thread.kind}`}>{thread.kind === "question" ? t("community.question") : t("community.experience")}</span>
                {thread.need_labels.map((label) => <span key={label} className="tag">#{label}</span>)}
                <span>{tn("community.reply", thread.reply_count ?? 0)}</span>
                {thread.school_answered && <span className="answered">{t("community.school_answered")}</span>}
                {thread.origin === "ask_school" && <span className="origin">{t("community.via_ask")}</span>}
                {thread._synthetic && <span className="meta">{t("community.sample")}</span>}
              </div>
              {open === thread.post_id && (
                <ThreadView
                  threadId={thread.post_id}
                  persona={persona}
                  needs={thread.needs}
                  labels={thread.need_labels}
                  onChanged={() => {
                    void load();
                    props.onChanged?.();
                  }}
                />
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
      <strong>{t("community.not_posted")}</strong> {safety.message}
      {safety.findings.length > 0 && (
        <span> {t("community.found", { items: safety.findings.map((item) => `${item.type} "${item.text}"`).join(", ") })}</span>
      )}
      {safety.checked_by && safety.checked_by.length > 0 && (
        <small className="checked-by">
          {" "}
          {t("community.checked_by", {
            checks: safety.checked_by
              .map((check) => t(check === "bedrock_guardrails" ? "community.check_guardrails" : "community.check_rules"))
              .join(" + "),
          })}
        </small>
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
        <button type="button" role="tab" aria-selected={kind === "question"} aria-pressed={kind === "question"} onClick={() => setKind("question")}>{t("community.ask_question")}</button>
        <button type="button" role="tab" aria-selected={kind === "experience"} aria-pressed={kind === "experience"} onClick={() => setKind("experience")}>{t("community.share")}</button>
      </div>
      {fromAgent && <p className="meta">{t("community.drafted")}</p>}
      <textarea
        aria-label={kind === "question" ? t("community.your_question") : t("community.your_experience")}
        placeholder={kind === "question" ? t("community.question_placeholder") : t("community.experience_placeholder")}
        value={text}
        rows={3}
        onChange={(event) => { setText(event.target.value); setSafety(null); setPosted(false); }}
      />
      {tags.length > 0 && (
        <div className="tag-pick" aria-label={t("community.topics")}>
          <span className="meta">{t("community.topics_tap")}</span>
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
      {posted && <p className="ok" role="status">{t("community.posted")}</p>}
      <div className="composer-foot">
        <span className="meta">{t("community.no_pii")}</span>
        <button className="primary" disabled={busy || !text.trim()}>{busy ? t("community.checking") : t("community.post")}</button>
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
          {reply.verified_school && <span className="verified">{t("community.verified")}</span>}
          <p>{reply.text}</p>
          <span className="meta">{reply.created_at}{reply._synthetic ? ` · ${t("community.sample")}` : ""}</span>
        </div>
      ))}
      <form className="reply-form" onSubmit={(event) => void submit(event)}>
        <textarea
          aria-label={isSchool ? t("community.answer_as_school") : t("community.reply")}
          placeholder={isSchool ? t("community.answer_placeholder") : t("community.reply_placeholder")}
          rows={2}
          value={text}
          onChange={(event) => { setText(event.target.value); setSafety(null); }}
        />
        {isSchool && props.needs.length > 0 && (
          <div className="answer-tools">
            <label>
              {t("community.topic")}
              <select value={need} onChange={(event) => setNeed(event.target.value)}>
                {props.needs.map((row, index) => <option key={row} value={row}>{props.labels[index] ?? row}</option>)}
              </select>
            </label>
            {TIME_NEEDS.has(need) ? (
              <label>
                {t("community.ends_at")}
                <input type="time" value={value} onChange={(event) => setValue(event.target.value)} />
              </label>
            ) : (
              <label>
                {t("community.this_answer")}
                <select value={offers} onChange={(event) => setOffers(event.target.value as "yes" | "no" | "info")}>
                  <option value="yes">{t("community.offers_yes")}</option>
                  <option value="no">{t("community.offers_no")}</option>
                  <option value="info">{t("community.offers_info")}</option>
                </select>
              </label>
            )}
          </div>
        )}
        <SafetyNote safety={safety} />
        <button className="primary" disabled={!text.trim()}>{isSchool ? t("community.post_answer") : t("community.reply")}</button>
      </form>
    </div>
  );
}

/** "Ask the school" questions waiting for this school. Staff answer once, here, for every parent who asked. */
function SchoolQuestions(props: { schoolId: string; questions: SchoolQuestion[]; onAnswered: () => void }) {
  return (
    <section className="school-questions" aria-label={t("community.questions_title")}>
      <h3>{t("community.questions_title")}</h3>
      <p className="meta">{t("community.questions_note")}</p>
      {props.questions.map((question) => (
        <SchoolQuestionForm key={question.id} schoolId={props.schoolId} question={question} onAnswered={props.onAnswered} />
      ))}
    </section>
  );
}

function SchoolQuestionForm({ schoolId, question, onAnswered }: { schoolId: string; question: SchoolQuestion; onAnswered: () => void }) {
  const timed = TIME_NEEDS.has(question.need);
  const [text, setText] = useState("");
  const [value, setValue] = useState("18:00");
  const [offers, setOffers] = useState<"yes" | "no" | "info">("yes");
  const [safety, setSafety] = useState<Safety | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = timed ? { text, value } : offers === "info" ? { text } : { text, offers: offers === "yes" };
    const result = await api<{ ok: boolean; safety: Safety }>(
      `/api/community/schools/${enc(schoolId)}/questions/${enc(question.id)}/answer`,
      body,
    );
    setSafety(result.safety);
    if (result.ok) {
      setText("");
      onAnswered();
    }
  }

  return (
    <form className="school-question reply-form" onSubmit={(event) => void submit(event)}>
      <p><strong>{question.question}</strong></p>
      <p className="meta">#{question.label} · {tn("community.parents_asked", question.parents)}</p>
      <textarea
        aria-label={t("community.answer_for", { question: question.question })}
        placeholder={t("community.answer_placeholder")}
        rows={2}
        value={text}
        onChange={(event) => { setText(event.target.value); setSafety(null); }}
      />
      <div className="answer-tools">
        {timed ? (
          <label>
            {t("community.ends_at")}
            <input type="time" value={value} onChange={(event) => setValue(event.target.value)} />
          </label>
        ) : (
          <label>
            {t("community.this_answer")}
            <select value={offers} onChange={(event) => setOffers(event.target.value as "yes" | "no" | "info")}>
              <option value="yes">{t("community.offers_yes")}</option>
              <option value="no">{t("community.offers_no")}</option>
              <option value="info">{t("community.offers_info")}</option>
            </select>
          </label>
        )}
      </div>
      <SafetyNote safety={safety} />
      <button className="primary" disabled={!text.trim()}>{t("community.post_answer")}</button>
    </form>
  );
}

type SchoolRow = { id: string; name: string; city?: string; threads: number; asked_this_month: number; top_asks: Demand[] };

/** The Community tab's front page: schools with activity, and a name search to reach any school's page. */
export function CommunityHome({ onOpen }: { onOpen: (schoolId: string) => void }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<SchoolRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let live = true;
    api<{ schools: SchoolRow[] }>(`/api/community/schools${search ? `?q=${enc(search)}` : ""}`)
      .then((data) => live && (setRows(data.schools), setError(null)))
      .catch((err) => live && setError(err instanceof Error ? err.message : t("community.load_error")));
    return () => { live = false; };
  }, [search]);

  return (
    <section className="community-home">
      <div>
        <h2>{t("community.home_title")}</h2>
        <p className="meta">{t("community.home_intro")}</p>
      </div>
      <form role="search" onSubmit={(event) => { event.preventDefault(); setSearch(query.trim()); }}>
        <input type="search" aria-label={t("community.find_school")} placeholder={t("community.find_placeholder")} value={query} onChange={(event) => setQuery(event.target.value)} />
      </form>
      {error && <p className="error">{error}</p>}
      <h3 className="section-title">{search ? t("community.matching", { query: search }) : t("community.active")}</h3>
      {rows?.length === 0 && <p className="meta">{search ? t("community.no_match") : t("community.no_posts")}</p>}
      <ul className="school-list">
        {(rows ?? []).map((row) => (
          <li key={row.id}>
            <button className="school-row" onClick={() => onOpen(row.id)}>
              <span>
                <strong>{row.name}</strong>
                {row.city && <span className="meta"> · {row.city}</span>}
              </span>
              <span className="meta">
                {tn("compare.threads", row.threads)}
                {row.top_asks.map((ask) => ` · ${ask.label} ${ask.count}`).join("")}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
