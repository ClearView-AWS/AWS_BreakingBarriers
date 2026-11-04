type Option = { id: string; label: string };

type Props = {
  text: string;
  options: Option[];
  onPick: (optionId: string) => void;
  onSkip: () => void;
};

export function QuestionPrompt({ text, options, onPick, onSkip }: Props) {
  return (
    <section className="question" aria-live="polite">
      <p className="eyebrow">One quick question</p>
      <h2>{text}</h2>
      <div className="options">
        {options.map((option) => (
          <button key={option.id} type="button" className="option" onClick={() => onPick(option.id)}>
            {option.label}
          </button>
        ))}
      </div>
      <button type="button" className="linkish" onClick={onSkip}>
        Just show me results
      </button>
    </section>
  );
}
