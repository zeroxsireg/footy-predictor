import { cx } from "@/app/lib/cx";

type Tone = "dim" | "fg" | "red";
const TONE: Record<Tone, string> = {
  dim: "text-dim",
  fg: "text-fg",
  red: "text-red",
};

/** Micro-typography telemetry label. `bracket` wraps it in [ … ]. */
export function Label({
  children,
  bracket,
  tone = "dim",
  className,
}: {
  children: React.ReactNode;
  bracket?: boolean;
  tone?: Tone;
  className?: string;
}) {
  return (
    <p className={cx("lbl", TONE[tone], className)}>
      {bracket ? <>[ {children} ]</> : children}
    </p>
  );
}
