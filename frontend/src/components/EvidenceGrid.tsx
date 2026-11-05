import { SOURCE_LABEL } from "../labels";
import { t } from "../i18n";
import type { Evidence } from "../types";
import { StatusBadge } from "./StatusBadge";

type Props = {
  payload: Record<string, unknown>;
};

export function EvidenceGrid({ payload }: Props) {
  const schools = (payload.schools as { id: string; name: string }[]) ?? [];
  const criteria = (payload.criteria as { id: string; text: string }[]) ?? [];
  const cells = (payload.cells as Record<string, Record<string, Evidence | null>>) ?? {};
  if (!schools.length) return null;

  return (
    <section className="grid-panel" aria-labelledby="evidence-grid-title">
      <div className="section-head">
        <h2 id="evidence-grid-title">{t("a11y.evidence_grid")}</h2>
        <p>{t("a11y.evidence_grid_help")}</p>
      </div>
      <div className="table-scroll" tabIndex={0} role="region" aria-label={t("a11y.evidence_grid")}>
        <table>
          <caption className="sr-only">{t("a11y.evidence_grid")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("a11y.school_col")}</th>
              {criteria.map((column) => (
                <th key={column.id} scope="col">
                  {column.text}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {schools.map((school) => (
              <tr key={school.id} data-school-id={school.id}>
                <th scope="row">{school.name}</th>
                {criteria.map((column) => {
                  const cell = cells[school.id]?.[column.id];
                  return (
                    <td key={column.id} data-criterion-id={column.id}>
                      {cell ? (
                        <>
                          <StatusBadge status={cell.status} />
                          <p className="cite">
                            {cell.source
                              ? `${SOURCE_LABEL[cell.source.type] ?? cell.source.type}${
                                  cell.source.as_of ? ` · ${cell.source.as_of}` : ""
                                }`
                              : ""}
                          </p>
                        </>
                      ) : (
                        <span aria-label={t("a11y.no_cell")}>—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
