import type { Principle } from "@/app/lib/content";

export function PrincipleCard({ principle }: { principle: Principle }) {
  return (
    <div className="p-4">
      <div className="flex items-baseline justify-between">
        <p className="lbl text-dim">{principle.label}</p>
        <span className="hd text-2xl text-line">{principle.id}</span>
      </div>
      <p className="hd mt-3 text-xl text-fg">{principle.title}</p>
      <p className="mt-2 text-sm leading-relaxed text-dim">{principle.body}</p>
    </div>
  );
}
