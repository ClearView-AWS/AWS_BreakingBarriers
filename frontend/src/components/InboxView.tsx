import { FormEvent, useState } from "react";
import { replyInbox } from "../api";

type Props = {
  items: Record<string, unknown>[];
  onAnswered: () => void;
};

export function InboxView({ items, onAnswered }: Props) {
  const [drafts, setDrafts] = useState<Record<string, { text: string; value: string }>>({});

  if (!items.length) {
    return (
      <section className="page-panel">
        <div className="section-head">
          <h2>School inbox</h2>
          <p>No questions yet. Use “Ask the school” on a result with an unknown fact.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="page-panel">
      <div className="section-head">
        <h2>School inbox</h2>
        <p>
          Questions about the same need are grouped into one request. Addresses are example.org, so this cannot email a
          real school.
        </p>
      </div>
      <div className="inbox-list">
        {items.map((item) => {
          const id = String(item.id);
          const draft = drafts[id] ?? { text: "", value: "18:00" };
          return (
            <article key={id} className="inbox-item">
              <h3>{String(item.school_name)}</h3>
              <p>{String(item.question)}</p>
              <p className="meta">
                {String(item.parent_count)} parent(s) · {String(item.status)} · {String(item.email_to)}
              </p>
              {item.status === "open" && (
                <form
                  className="inbox-form"
                  onSubmit={async (event: FormEvent) => {
                    event.preventDefault();
                    await replyInbox(id, {
                      text: draft.text || "Confirmed.",
                      value: draft.value,
                    });
                    onAnswered();
                  }}
                >
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
                  <button className="btn-primary" type="submit">
                    Send reply
                  </button>
                </form>
              )}
              {((item.replies as { text: string }[]) ?? []).map((reply, index) => (
                <p key={index} className="reply">
                  {reply.text}
                </p>
              ))}
            </article>
          );
        })}
      </div>
    </section>
  );
}
