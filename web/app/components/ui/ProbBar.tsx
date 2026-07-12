import { cx } from "@/app/lib/cx";
import { pct } from "@/app/lib/format";

/** A single labelled probability read-out with a mechanical fill bar. */
export function ProbBar({
  label,
  value,
  hot,
}: {
  label: string;
  value: number;
  hot?: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="lbl">{label}</span>
        <data
          value={value}
          className={cx("text-sm tracking-widest", hot ? "text-red" : "text-fg")}
        >
          {pct(value)}
        </data>
      </div>
      <div className="mt-1 h-1.5 w-full bg-line">
        <div
          className={cx("h-full", hot ? "bg-red" : "bg-fg")}
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
      </div>
    </div>
  );
}

/** Stacked list of ProbBars from {label,value}[] rows. */
export function ProbList({
  items,
  hotAt = 1,
}: {
  items: { label: string; value: number }[];
  hotAt?: number;
}) {
  return (
    <div className="space-y-3">
      {items.map((i) => (
        <ProbBar key={i.label} label={i.label} value={i.value} hot={i.value >= hotAt} />
      ))}
    </div>
  );
}
