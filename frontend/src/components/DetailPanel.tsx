import { EvidenceGrid } from "./EvidenceGrid";
import type { Card, Turn } from "../types";

type Props = {
  turn: Turn;
  onClose: () => void;
};

export function DetailPanel({ turn, onClose }: Props) {
  return (
    <aside className="drawer" role="dialog" aria-modal="true" aria-label="Details">
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer-panel">
        <button type="button" className="drawer-close" onClick={onClose}>
          Close
        </button>
        {turn.blocks.map((block, index) => {
          if (block.type === "why_not") {
            const payload = block.payload as { school_name?: string; text?: string; change?: string };
            return (
              <div key={index} className="drawer-block">
                <p className="eyebrow">Why this school isn’t listed</p>
                <h2>{payload.school_name}</h2>
                <p>{payload.text}</p>
                {payload.change && <p>{payload.change}</p>}
              </div>
            );
          }
          if (block.type === "definition") {
            const payload = block.payload as { term?: string; title?: string; text?: string; cite?: string };
            return (
              <div key={index} className="drawer-block">
                <p className="eyebrow">Definition</p>
                <h2>{payload.title ?? payload.term}</h2>
                <p>{payload.text}</p>
                <p className="cite">Source: {payload.cite}</p>
              </div>
            );
          }
          if (block.type === "cost") {
            const schools = (block.payload.schools as Record<string, unknown>[]) ?? [];
            return (
              <div key={index} className="drawer-block">
                <p className="eyebrow">Funding</p>
                <h2>Cost after likely scholarships</h2>
                {schools.map((school) => (
                  <div key={String(school.school_id)} className="cost-block">
                    <h3>{String(school.school_name)}</h3>
                    {school.tuition != null && (
                      <p>Listed tuition: ${String(school.tuition)}. This is not a net price.</p>
                    )}
                    <p>{String(school.disclaimer ?? "")}</p>
                    <ul className="plain-list">
                      {((school.lines as Record<string, string>[]) ?? []).map((line, lineIndex) => (
                        <li key={lineIndex}>
                          <strong>{line.wording}</strong>
                          {line.name ? ` ${line.name}.` : ""} {line.eligibility ?? ""}{" "}
                          {line.official_url && (
                            <a href={line.official_url} target="_blank" rel="noreferrer">
                              {line.link_label ?? "Official page"}
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            );
          }
          if (block.type === "school_detail") {
            const payload = block.payload as {
              school: Record<string, unknown>;
              reviews: {
                topic: string;
                positive: number;
                negative: number;
                earliest?: string;
                latest?: string;
                quotes: { side: string; date: string; text: string }[];
              }[];
              card?: Card | null;
            };
            const school = payload.school;
            return (
              <div key={index} className="drawer-block">
                <p className="eyebrow">School profile</p>
                <h2>{String(school.name)}</h2>
                <p className="meta">
                  {String(school.street ?? "")} {String(school.city ?? "")} {String(school.state ?? "")}
                </p>
                <p>
                  {String(school.entity_type)} · summary rating{" "}
                  {school.summary_rating == null ? "unknown" : String(school.summary_rating)}
                  {school.synthetic ? " · synthetic profile" : ""}
                </p>
                {((school.esp_text as string[]) ?? []).map((line) => (
                  <p key={line}>{line}</p>
                ))}
                <h3>Reviews by topic</h3>
                {payload.reviews.map((topic) => (
                  <div key={topic.topic} className="quote">
                    <strong>{topic.topic}</strong>
                    <span>
                      {" "}
                      · {topic.positive} positive · {topic.negative} negative
                      {topic.earliest ? ` · ${topic.earliest} to ${topic.latest}` : ""}
                    </span>
                    {topic.quotes.map((quote, quoteIndex) => (
                      <p key={quoteIndex}>
                        {quote.date} · {quote.side}: {quote.text}
                      </p>
                    ))}
                  </div>
                ))}
                <p className="cite">
                  Review scores in the file are sentiment, not stars, so they are not shown as a rating.
                </p>
              </div>
            );
          }
          if (block.type === "comparison") {
            const schools = (block.payload.schools as Card[]) ?? [];
            return (
              <div key={index} className="drawer-block">
                <p className="eyebrow">Side by side</p>
                <h2>Comparison</h2>
                <div className="compare-stack">
                  {schools.map((school) => (
                    <div key={school.id} className="compare-item">
                      <h3>{school.name}</h3>
                      <p>{school.summary}</p>
                    </div>
                  ))}
                </div>
              </div>
            );
          }
          if (block.type === "evidence_grid") return <EvidenceGrid key={index} payload={block.payload} />;
          if (block.type === "message") return <p key={index}>{String(block.payload.text ?? "")}</p>;
          return null;
        })}
      </div>
    </aside>
  );
}
