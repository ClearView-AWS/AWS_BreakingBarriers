type SavedSchool = { id: string; name: string; city?: string };
type ChecklistItem = { school_name: string; question: string };

type Props = {
  saved: SavedSchool[];
  checklist: ChecklistItem[];
};

export function SavedView({ saved, checklist }: Props) {
  return (
    <section className="page-panel">
      <div className="section-head">
        <h2>Saved schools</h2>
        <p>Keep the ones worth a closer look. Visit questions come from facts still unknown.</p>
      </div>
      {saved.length === 0 ? (
        <p className="empty">Save a school from a result to build this list.</p>
      ) : (
        <ul className="plain-list saved-list">
          {saved.map((school) => (
            <li key={school.id}>
              <strong>{school.name}</strong>
              {school.city ? <span> · {school.city}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {checklist.length > 0 && (
        <>
          <div className="section-head tight">
            <h2>Visit checklist</h2>
          </div>
          <ul className="plain-list">
            {checklist.map((item, index) => (
              <li key={index}>
                <strong>{item.school_name}.</strong> {item.question}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
