import { SOURCE_LABEL, STATUS_LABEL } from "../labels";
import type { Evidence } from "../types";

type Props = {
  payload: Record<string, unknown>;
};

export function EvidenceGrid({ payload }: Props) {
  const schools = (payload.schools as { id: string; name: string }[]) ?? [];
  const criteria = (payload.criteria as { id: string; text: string }[]) ?? [];
  const cells = (payload.cells as Record<string, Record<string, Evidence | null>>) ?? {};
  if (!schools.length) return null;

  return (
    <section className="grid-panel">
      <div className="section-head">
        <h2>Evidence grid</h2>
        <p>Every cell cites where the answer came from.</p>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>School</th>
              {criteria.map((column) => (
                <th key={column.id}>{column.text}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {schools.map((school) => (
              <tr key={school.id}>
                <th scope="row">{school.name}</th>
                {criteria.map((column) => {
                  const cell = cells[school.id]?.[column.id];
                  return (
                    <td key={column.id}>
                      {cell ? (
                        <>
                          <span className={`pill ${cell.status}`}>{STATUS_LABEL[cell.status]}</span>
                          <p className="cite">
                            {cell.source
                              ? `${SOURCE_LABEL[cell.source.type] ?? cell.source.type}${
                                  cell.source.as_of ? ` · ${cell.source.as_of}` : ""
                                }`
                              : ""}
                          </p>
                        </>
                      ) : (
                        "—"
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
