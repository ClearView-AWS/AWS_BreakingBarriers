import { useMemo, useState } from "react";
import { GettingInLine, type Access } from "../GettingIn";
import { LEVEL, SOURCE_LABEL, STATUS_LABEL } from "../labels";
import type { Card, Criterion, Evidence } from "../types";

type Props = {
  card: Card;
  criteria: Criterion[];
  picked: string[];
  layout: "list" | "grid";
  onPick: (ids: string[]) => void;
  onOpen: (id: string) => void;
  onSave: (id: string) => void;
  onAsk: (id: string, need: string) => void;
  onFeedback: (id: string, vote: string, reason?: string) => void;
  onCost: (id: string) => void;
};

export function SchoolResult(props: Props) {
  const { card, criteria, picked, layout, onPick, onOpen, onSave, onAsk, onFeedback, onCost } = props;
  const [reasons, setReasons] = useState(false);
  const labels = useMemo(() => new Map(criteria.map((item) => [item.id, item.text])), [criteria]);
  const needs = useMemo(() => new Map(criteria.map((item) => [item.id, item.need])), [criteria]);
  const selected = picked.includes(card.id);
  const levels = (card.level_codes ?? []).map((code) => LEVEL[code] ?? code).join(" · ");

  return (
    <article className={`school ${layout} ${selected ? "is-picked" : ""}`} data-school-id={card.id}>
      <header className="school-head">
        <div>
          <button type="button" className="school-name" onClick={() => onOpen(card.id)}>
            {card.name}
          </button>
          <p className="meta">
            {[card.city, card.entity_type, levels].filter(Boolean).join(" · ")}
            {card.distance_miles != null ? ` · ${card.distance_miles} mi` : ""}
          </p>
        </div>
        <div className="score" aria-label={`${Math.round(card.match * 100)} percent match`}>
          <strong>{Math.round(card.match * 100)}%</strong>
          <span>Verified {card.verified}</span>
        </div>
      </header>

      {card.summary && <p className="summary">{card.summary}</p>}

      <GettingInLine schoolId={card.id} access={(card as Card & { access?: Access }).access} />

      <ul className="evidence-list">
        {card.evidence.map((row) => (
          <EvidenceItem
            key={row.criterion_id}
            row={row}
            label={labels.get(row.criterion_id) ?? row.criterion_id}
            onAsk={
              row.status === "unknown" && needs.get(row.criterion_id)
                ? () => onAsk(card.id, needs.get(row.criterion_id) as string)
                : undefined
            }
          />
        ))}
      </ul>

      <div className="school-actions">
        <button type="button" onClick={() => onSave(card.id)}>
          Save
        </button>
        <button
          type="button"
          aria-pressed={selected}
          onClick={() => onPick(selected ? picked.filter((id) => id !== card.id) : [...picked, card.id].slice(-2))}
        >
          {selected ? "Selected" : "Compare"}
        </button>
        {card.entity_type === "private" && (
          <button type="button" onClick={() => onCost(card.id)}>
            Cost after scholarships
          </button>
        )}
        <button type="button" onClick={() => onFeedback(card.id, "up")}>
          Helpful
        </button>
        <button type="button" onClick={() => setReasons((open) => !open)}>
          Not a fit
        </button>
      </div>

      {reasons && (
        <div className="reasons">
          {[
            ["too_far", "Too far"],
            ["too_expensive", "Too expensive"],
            ["missing_program", "Missing a program"],
            ["wrong_grade", "Wrong grade"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                onFeedback(card.id, "down", id);
                setReasons(false);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function EvidenceItem({ row, label, onAsk }: { row: Evidence; label: string; onAsk?: () => void }) {
  const source = row.source;
  return (
    <li className={`ev status-${row.status}`} data-criterion-id={row.criterion_id}>
      <div className="ev-status">
        <span className={`pill ${row.status}`}>{STATUS_LABEL[row.status] ?? row.status}</span>
        <strong>{label}</strong>
      </div>
      <div className="ev-body">
        <p>{row.value != null && row.value !== "" ? String(row.value) : "No value on file"}</p>
        {source && (
          <p className="cite">
            {SOURCE_LABEL[source.type] ?? source.type} · {source.path}
            {source.as_of ? ` · as of ${source.as_of}` : ""}
            {source.confidence ? ` · ${source.confidence} confidence` : ""}
          </p>
        )}
        {row.conflict && (
          <p className="conflict">
            Website says {String(row.conflict.website_value)}; the profile says {String(row.conflict.profile_value)}.
          </p>
        )}
        {onAsk && (
          <button type="button" className="linkish" onClick={onAsk}>
            Ask the school
          </button>
        )}
      </div>
    </li>
  );
}
