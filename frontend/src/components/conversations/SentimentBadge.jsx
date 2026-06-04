import { clsx } from "clsx";
import { sentimentLabel } from "../../utils/formatters";

const COLORS = {
  very_negative: "bg-red-100 text-red-700",
  negative: "bg-orange-100 text-orange-700",
  neutral: "bg-slate-100 text-slate-600",
  positive: "bg-green-100 text-green-700",
  very_positive: "bg-emerald-100 text-emerald-700",
};

export default function SentimentBadge({ sentiment, score, className }) {
  if (!sentiment) return null;
  return (
    <span
      title={score !== undefined ? `Score: ${score}` : undefined}
      className={clsx("badge", COLORS[sentiment] || "bg-slate-100 text-slate-600", className)}
    >
      {sentimentLabel(sentiment)}
    </span>
  );
}
