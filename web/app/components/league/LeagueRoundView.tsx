import Link from "next/link";
import { Container } from "@/app/components/ui/Container";
import { Label } from "@/app/components/ui/Label";
import { MatchTile } from "./MatchTile";
import { MatchdaySelector } from "./MatchdaySelector";
import { pad2 } from "@/app/lib/format";
import { getDict, getLocale } from "@/app/lib/i18n-server";
import { localePath } from "@/app/lib/i18n";
import type { RoundDoc } from "@/app/lib/types";

/** Matchday "coupon" — league header, matchday selector, list of match tiles. */
export function LeagueRoundView({
  doc,
  rounds,
}: {
  doc: RoundDoc;
  rounds: number[];
}) {
  const dict = getDict();
  const locale = getLocale();

  return (
    <Container className="py-8">
      <Link href={localePath(locale, "/")} className="lbl text-dim hover:text-red">
        {dict.league.backToIndex}
      </Link>

      <div className="mt-4 flex flex-wrap items-baseline justify-between gap-4 border-b border-line pb-4">
        <h1 className="hd text-3xl sm:text-5xl">{doc.league.name}</h1>
        <Label>
          {`${dict.league.matchday} ${doc.matchday} · ${doc.season}/${pad2((doc.season + 1) % 100)}`}
        </Label>
      </div>

      <div className="mt-4">
        <Label bracket className="mb-2">
          {dict.league.selectMatchday}
        </Label>
        <MatchdaySelector
          leagueId={doc.league.id}
          current={doc.matchday}
          rounds={rounds}
        />
      </div>

      <div className="mt-6 space-y-2">
        {doc.matches.map((m) => (
          <MatchTile key={m.fixture_id} match={m} />
        ))}
      </div>
    </Container>
  );
}
