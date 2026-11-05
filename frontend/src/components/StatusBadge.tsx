// Status shown as mark + words so color is never the only cue (WCAG 1.4.1).
import { STATUS_MARK, statusLabel } from "../labels";

type Props = {
  status: string;
  /** Hide the word label visually (kept for screen readers). Use on dense tables. */
  markOnly?: boolean;
  className?: string;
};

export function StatusBadge({ status, markOnly = false, className = "" }: Props) {
  const mark = STATUS_MARK[status] ?? "·";
  const label = statusLabel(status);
  return (
    <span className={`pill status-badge ${status} ${className}`.trim()} title={label}>
      <span className="status-mark" aria-hidden="true">
        {mark}
      </span>
      {markOnly ? <span className="sr-only">{label}</span> : <span className="status-text">{label}</span>}
    </span>
  );
}
