import { Label } from "@/app/components/ui/Label";
import { isoDate } from "@/app/lib/format";
import { getDict } from "@/app/lib/i18n-server";
import type { Match } from "@/app/lib/types";

export function MatchHeader({
  match,
  leagueName,
  matchday,
}: {
  match: Match;
  leagueName: string;
  matchday: number;
}) {
  const h = getDict().match.header;
  return (
    <div className="border-b border-line px-4 py-6">
      <Label bracket>{`${leagueName} · ${h.matchday} ${matchday} · ${isoDate(match.date)}`}</Label>
      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <p className="hd text-right text-2xl sm:text-4xl">{match.home}</p>
        <span className="hd text-lg text-red">{"//"}</span>
        <p className="hd text-2xl sm:text-4xl">{match.away}</p>
      </div>
      <p className="lbl mt-4 text-center text-dim">
        {h.referee} / {match.referee ?? h.refereeNotFound}
      </p>
    </div>
  );
}
