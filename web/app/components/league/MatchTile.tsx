import Link from "next/link";
import { Metric } from "@/app/components/ui/Metric";
import { pct, dec, isoDate } from "@/app/lib/format";
import { pickSign } from "@/app/lib/picks";
import { HOT, PLAYER_HOT } from "@/app/lib/markets";
import { getDict, getLocale } from "@/app/lib/i18n-server";
import { localePath } from "@/app/lib/i18n";
import type { Match } from "@/app/lib/types";

/** Compact, clickable match row for the matchday coupon. */
export function MatchTile({ match }: { match: Match }) {
  const dict = getDict();
  const locale = getLocale();
  const m = match.markets;
  const pick = pickSign(m["1x2"]);
  const top = m.players_at_risk?.[0];
  const col = dict.league.columns;

  return (
    <Link
      href={localePath(locale, `/match/${match.fixture_id}`)}
      className="group block border border-line p-3 hover:border-red"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="hd text-lg group-hover:text-red">
          {match.home} <span className="text-red">/</span> {match.away}
        </span>
        <span className="lbl text-dim">{isoDate(match.date)}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric label={col.sign} value={`${pick.sign} ${pct(pick.value)}`} />
        <Metric
          label={col.ou}
          value={`O ${pct(m.goals.over_2_5)}`}
          hot={m.goals.over_2_5 >= HOT}
        />
        <Metric label={col.btts} value={pct(m.goals.btts)} />
        <Metric label={col.cards} value={m.cards ? dec(m.cards.expected) : dict.league.none} />
        <Metric
          label={col.top}
          value={top ? top.name : dict.league.none}
          hot={!!top && top.prob >= PLAYER_HOT}
        />
      </div>
    </Link>
  );
}
