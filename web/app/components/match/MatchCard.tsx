import Link from "next/link";
import { Container } from "@/app/components/ui/Container";
import { Panel, SectionBlock } from "@/app/components/ui/Panel";
import { ProbList } from "@/app/components/ui/ProbBar";
import { MatchHeader } from "./MatchHeader";
import { Market1x2 } from "./Market1x2";
import { CardsPanel } from "./CardsPanel";
import { PlayerRiskTable } from "./PlayerRiskTable";
import { ResultBlock } from "./ResultBlock";
import { goalsMarkets, multigolMarkets, rows, HOT } from "@/app/lib/markets";
import { getDict, getLocale } from "@/app/lib/i18n-server";
import { localePath } from "@/app/lib/i18n";
import type { MatchBundle } from "@/app/lib/types";

/** Full telemetry card — composes every market panel from the atoms. */
export function MatchCard({ match, league, matchday }: MatchBundle) {
  const dict = getDict();
  const locale = getLocale();
  const m = match.markets;
  const s = dict.match.sections;

  return (
    <Container className="py-8">
      <Link href={localePath(locale, "/")} className="lbl text-dim hover:text-red">
        {dict.match.indexLink}
      </Link>

      <Panel className="mt-4">
        <MatchHeader match={match} leagueName={league.name} matchday={matchday} />

        <div className="space-y-4 p-4">
          <SectionBlock title={s.outcome1x2}>
            <Market1x2 m={m["1x2"]} />
          </SectionBlock>

          <div className="grid gap-4 sm:grid-cols-2">
            <SectionBlock title={s.goals}>
              <ProbList items={rows(m.goals, goalsMarkets(dict))} hotAt={HOT} />
            </SectionBlock>

            <SectionBlock title={s.multigol}>
              <ProbList items={rows(m.multigol, multigolMarkets(dict))} hotAt={HOT} />
            </SectionBlock>

            {m.cards && (
              <SectionBlock title={s.teamCards}>
                <CardsPanel cards={m.cards} />
              </SectionBlock>
            )}

            {m.players_at_risk && (
              <SectionBlock title={s.playersAtRisk}>
                <PlayerRiskTable players={m.players_at_risk} home={match.home} away={match.away} />
              </SectionBlock>
            )}
          </div>

          {match.result && <ResultBlock result={match.result} />}
        </div>
      </Panel>
    </Container>
  );
}
