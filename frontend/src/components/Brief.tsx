import { STRENGTH_CYCLE, STRENGTH_LABEL } from "../labels";
import type { Criterion } from "../types";

type Props = {
  criteria: Criterion[];
  onChange: (next: Criterion[]) => void;
  onApprove: () => void;
};

export function Brief({ criteria, onChange, onApprove }: Props) {
  if (!criteria.length) return null;

  // Hard filters (location/grade/type) always belong in must-have for the brief.
  const must = [
    ...criteria.filter((c) => c.kind === "location" || c.kind === "grade" || c.kind === "school_type"),
    ...criteria.filter((c) => c.kind === "need" && c.strength === "require"),
  ];
  const nice = criteria.filter((c) => c.kind === "need" && c.strength === "prefer");
  const avoid = criteria.filter((c) => c.kind === "need" && c.strength === "avoid");

  return (
    <section className="brief" aria-label="Search brief">
      <div className="brief-head">
        <div>
          <p className="eyebrow">Search brief</p>
          <h2>Here’s what I’ll look for</h2>
        </div>
        <button type="button" className="btn-primary" onClick={onApprove}>
          Looks right
        </button>
      </div>

      <div className="brief-grid">
        <BriefColumn
          title={STRENGTH_LABEL.require}
          empty="—"
          items={must}
          onCycle={(id) =>
            onChange(
              criteria.map((row) =>
                row.id === id && (row.kind === "need" || row.kind === "distance")
                  ? { ...row, strength: STRENGTH_CYCLE[row.strength] }
                  : row,
              ),
            )
          }
          onRemove={(id) => onChange(criteria.filter((row) => row.id !== id))}
        />
        <BriefColumn
          title={STRENGTH_LABEL.prefer}
          empty="—"
          items={nice}
          onCycle={(id) =>
            onChange(
              criteria.map((row) =>
                row.id === id ? { ...row, strength: STRENGTH_CYCLE[row.strength] } : row,
              ),
            )
          }
          onRemove={(id) => onChange(criteria.filter((row) => row.id !== id))}
        />
        <BriefColumn
          title={STRENGTH_LABEL.avoid}
          empty="—"
          items={avoid}
          onCycle={(id) =>
            onChange(
              criteria.map((row) =>
                row.id === id ? { ...row, strength: STRENGTH_CYCLE[row.strength] } : row,
              ),
            )
          }
          onRemove={(id) => onChange(criteria.filter((row) => row.id !== id))}
        />
      </div>
      <p className="brief-hint">Tap a need to cycle must / nice / avoid. Remove anything that doesn’t belong.</p>
    </section>
  );
}

function BriefColumn({
  title,
  empty,
  items,
  onCycle,
  onRemove,
}: {
  title: string;
  empty: string;
  items: Criterion[];
  onCycle: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="brief-col">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="brief-empty">{empty}</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`chip strength-${item.strength}`}
                onClick={() => onCycle(item.id)}
                disabled={item.kind !== "need" && item.kind !== "distance"}
                title={item.kind === "need" || item.kind === "distance" ? "Cycle strength" : undefined}
              >
                {item.text}
              </button>
              <button type="button" className="chip-x" aria-label={`Remove ${item.text}`} onClick={() => onRemove(item.id)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
