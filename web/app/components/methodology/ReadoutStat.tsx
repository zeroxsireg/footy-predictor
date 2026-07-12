import type { Readout } from "@/app/lib/content";

/** Oversized telemetry read-out: label / hazard-red value / note. */
export function ReadoutStat({ readout }: { readout: Readout }) {
  return (
    <div>
      <p className="lbl text-dim">{readout.key}</p>
      <p className="hd mt-1 text-3xl text-red">{readout.value}</p>
      <p className="mt-1 text-[0.68rem] leading-tight text-dim">{readout.note}</p>
    </div>
  );
}
