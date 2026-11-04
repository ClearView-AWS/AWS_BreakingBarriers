import { t, tn } from "../i18n";

type Option = { id: string; label: string };

export type QuestionItem = {
  id: string;
  text: string;
  options: Option[];
  default?: string | null;
};

type Props = {
  items: QuestionItem[];
  skipLabel?: string;
  onPick: (questionId: string, optionId: string) => void;
  onSkip: () => void;
};

export function QuestionPrompt({ items, skipLabel = t("questions.skip"), onPick, onSkip }: Props) {
  if (!items.length) return null;
  const heading = tn("questions.quick", items.length);

  return (
    <section className="question" aria-live="polite">
      <p className="eyebrow">{heading}</p>
      <div className="question-stack">
        {items.map((item) => (
          <div key={item.id} className="question-item">
            <h2>{item.text}</h2>
            <div className="options">
              {item.options.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className="option"
                  onClick={() => onPick(item.id, option.id)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button type="button" className="linkish" onClick={onSkip}>
        {skipLabel}
      </button>
    </section>
  );
}
