import { STRENGTH_CYCLE, nameOf } from "../labels";
import { t } from "../i18n";
import type { Criterion } from "../types";

type Props = {
  criteria: Criterion[];
  onChange: (next: Criterion[]) => void;
  onApprove: () => void;
  /** Already approved: the results are on screen, so editing re-runs the search and there's nothing to approve. */
  approved?: boolean;
};

export function Brief({ criteria, onChange, onApprove, approved = false }: Props) {
  if (!criteria.length) return null;

  // Hard filters (location/grade/type) always belong in must-have for the brief.
  const must = [
    ...criteria.filter((c) => c.kind === "location" || c.kind === "grade" || c.kind === "school_type"),
    ...criteria.filter((c) => c.kind === "need" && c.strength === "require"),
  ];
  const nice = criteria.filter((c) => c.kind === "need" && c.strength === "prefer");
  const avoid = criteria.filter((c) => c.kind === "need" && c.strength === "avoid");

  return (
    <section className="brief" aria-label={t("brief.label")}>
      <div className="brief-head">
        <div>
          <p className="eyebrow">{t("brief.label")}</p>
          <h2>{t("brief.title")}</h2>
        </div>
        {!approved && (
          <button type="button" className="btn-primary" onClick={onApprove}>
            {t("brief.approve")}
          </button>
        )}
      </div>

      <div className="brief-grid">
        <BriefColumn
          title={t("brief.must")}
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
          title={t("brief.nice")}
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
          title={t("brief.avoid")}
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
      <p className="brief-hint">{t("brief.hint")}</p>
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
                title={item.kind === "need" || item.kind === "distance" ? t("brief.cycle") : undefined}
              >
                {nameOf(item)}
              </button>
              <button type="button" className="chip-x" aria-label={t("blocks.remove", { name: nameOf(item) })} onClick={() => onRemove(item.id)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
