import Link from "next/link";
import { cx } from "@/app/lib/cx";
import { pad2 } from "@/app/lib/format";
import { getLocale } from "@/app/lib/i18n-server";
import { localePath } from "@/app/lib/i18n";

export function MatchdaySelector({
  leagueId,
  current,
  rounds,
}: {
  leagueId: number;
  current: number;
  rounds: number[];
}) {
  const locale = getLocale();
  return (
    <div className="flex flex-wrap gap-px">
      {rounds.map((r) => (
        <Link
          key={r}
          href={localePath(locale, `/league/${leagueId}/round/${r}`)}
          className={cx(
            "panel px-3 py-1 lbl",
            r === current ? "border-red text-red" : "text-dim hover:border-fg hover:text-fg",
          )}
        >
          {pad2(r)}
        </Link>
      ))}
    </div>
  );
}
