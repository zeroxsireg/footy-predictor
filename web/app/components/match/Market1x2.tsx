import { cx } from "@/app/lib/cx";
import { pct } from "@/app/lib/format";
import { oneXTwoMarkets } from "@/app/lib/markets";
import { getDict } from "@/app/lib/i18n-server";
import type { Markets } from "@/app/lib/types";

/** Three-way outcome — the most probable segment burns hazard red. */
export function Market1x2({ m }: { m: Markets["1x2"] }) {
  const max = Math.max(m.home, m.draw, m.away);
  return (
    <div className="grid grid-cols-3 gap-px bg-line">
      {oneXTwoMarkets(getDict()).map((c) => {
        const v = m[c.key];
        return (
          <div key={c.key} className="bg-panel p-4 text-center">
            <p className={cx("hd text-3xl sm:text-4xl", v === max ? "text-red" : "text-fg")}>
              {pct(v)}
            </p>
            <p className="lbl mt-1 text-dim">{c.label}</p>
          </div>
        );
      })}
    </div>
  );
}
