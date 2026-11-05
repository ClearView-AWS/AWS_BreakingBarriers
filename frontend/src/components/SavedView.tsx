import { t } from "../i18n";

type SavedSchool = { id: string; name: string; city?: string };
type ChecklistItem = { school_name: string; question: string };

type Props = {
  saved: SavedSchool[];
  checklist: ChecklistItem[];
};

export function SavedView({ saved, checklist }: Props) {
  return (
    <section className="page-panel" aria-labelledby="saved-schools-title">
      <div className="section-head">
        <h2 id="saved-schools-title">{t("app.saved_title")}</h2>
        <p>{t("a11y.saved_help")}</p>
      </div>
      {saved.length === 0 ? (
        <p className="empty" role="status">
          {t("app.saved_empty")}
        </p>
      ) : (
        <ul className="plain-list saved-list" aria-label={t("app.saved_title")}>
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
            <h2 id="visit-checklist-title">{t("app.checklist")}</h2>
          </div>
          <ul className="plain-list" aria-labelledby="visit-checklist-title">
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
