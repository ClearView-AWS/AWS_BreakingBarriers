import { useState } from "react";
import type { Criterion } from "./types";

// "Understand before searching": up to three tap-to-answer questions, then a
// short brief (must have / nice to have / avoid) the parent approves or edits.
export const MAX_QUESTIONS = 3;

type Option = { id: string; label: string };

export function QuestionChips(props: {
  payload: Record<string, unknown>;
  step: number;
  gated: boolean;
  busy: boolean;
  onPick: (optionId: string) => void;
  onSkip: () => void;
}) {
  const options = (props.payload.options as Option[]) ?? [];
  return (
    <section className="question" aria-live="polite">
      {props.gated && <p className="step">Question {props.step} of up to {MAX_QUESTIONS}</p>}
      <p>{String(props.payload.text)}</p>
      <div className="options">
        {options.map((option) => (
          <button key={option.id} disabled={props.busy} onClick={() => props.onPick(option.id)}>
            {option.label}
          </button>
        ))}
      </div>
      {props.gated && (
        <button className="skip" disabled={props.busy} onClick={props.onSkip}>
          Just show me results
        </button>
      )}
    </section>
  );
}

const STRENGTH_LABEL: Record<Criterion["strength"], string> = {
  require: "Must have",
  prefer: "Nice to have",
  avoid: "Avoid",
};

function isScored(item: Criterion) {
  return item.kind === "need" || item.kind === "distance";
}

function chipLabel(item: Criterion) {
  if (item.kind === "grade") return `${item.text}`;
  if (item.kind === "school_type") return `${item.text} schools`;
  return item.text;
}

export function BriefCard(props: {
  criteria: Criterion[];
  approved: boolean;
  assumption?: string | null;
  busy: boolean;
  onApprove: () => void;
  onChange: (next: Criterion[]) => void;
}) {
  const [editing, setEditing] = useState(false);
  const { criteria } = props;
  if (!criteria.length) return null;

  // Location, grade and school type are hard filters, so they always sit under "Must have".
  const groups: Record<Criterion["strength"], Criterion[]> = { require: [], prefer: [], avoid: [] };
  for (const item of criteria) {
    groups[isScored(item) ? item.strength : "require"].push(item);
  }

  function setStrength(id: string, strength: Criterion["strength"]) {
    props.onChange(criteria.map((row) => (row.id === id ? { ...row, strength } : row)));
  }

  return (
    <section className={props.approved ? "brief approved" : "brief"} aria-label="Search brief">
      <h2>{props.approved ? "Your brief" : "Here's what I'll look for"}</h2>
      <dl>
        {(Object.keys(groups) as Criterion["strength"][]).map((strength) => (
          <div key={strength} className="brief-row">
            <dt>{STRENGTH_LABEL[strength]}</dt>
            <dd>
              {groups[strength].length === 0 && <span className="meta">None</span>}
              {groups[strength].map((item) => (
                <span key={item.id} className={`brief-chip ${item.kind}`}>
                  {chipLabel(item)}
                  {item.inferred_from ? <small> (from “{item.inferred_from}”)</small> : null}
                  {editing && isScored(item) && (
                    <select
                      aria-label={`How much ${item.text} matters`}
                      value={item.strength}
                      onChange={(event) => setStrength(item.id, event.target.value as Criterion["strength"])}
                    >
                      <option value="require">Must have</option>
                      <option value="prefer">Nice to have</option>
                      <option value="avoid">Avoid</option>
                    </select>
                  )}
                  {editing && (
                    <button
                      className="remove"
                      aria-label={`Remove ${item.text}`}
                      onClick={() => props.onChange(criteria.filter((row) => row.id !== item.id))}
                    >
                      ×
                    </button>
                  )}
                </span>
              ))}
            </dd>
          </div>
        ))}
      </dl>
      {props.assumption && <p className="assumption">{props.assumption}</p>}
      <div className="brief-actions">
        {!props.approved && (
          <button className="primary" disabled={props.busy} onClick={() => { setEditing(false); props.onApprove(); }}>
            Looks right, search
          </button>
        )}
        <button className="ghost" aria-pressed={editing} onClick={() => setEditing((open) => !open)}>
          {editing ? "Done editing" : props.approved ? "Edit brief" : "Edit"}
        </button>
      </div>
    </section>
  );
}
