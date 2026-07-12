import { cx } from "@/app/lib/cx";

/** A compact labelled read-out: telemetry label above a value. */
export function Metric({
  label,
  value,
  hot,
}: {
  label: string;
  value: string;
  hot?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="lbl text-dim">{label}</p>
      <p className={cx("mt-0.5 truncate text-sm tracking-wide", hot ? "text-red" : "text-fg")}>
        {value}
      </p>
    </div>
  );
}
