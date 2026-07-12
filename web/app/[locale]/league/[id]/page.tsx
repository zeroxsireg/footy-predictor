import {
  getLeagueIds,
  getRoundsForLeague,
  getRound,
  getLatestRound,
} from "@/app/lib/data";
import { LeagueRoundView } from "@/app/components/league/LeagueRoundView";
import { NotFoundNotice } from "@/app/components/ui/NotFoundNotice";
import { resolveLocaleParams, getDict } from "@/app/lib/i18n-server";
import type { Locale } from "@/app/lib/i18n";

export function generateStaticParams() {
  return getLeagueIds().map((id) => ({ id: String(id) }));
}

/** League landing = the latest available matchday. */
export default async function LeaguePage({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { id } = await resolveLocaleParams(params);
  const latest = getLatestRound(Number(id));
  const doc = latest != null ? getRound(Number(id), latest) : null;

  if (!doc) return <NotFoundNotice message={getDict().league.notFound} />;
  return <LeagueRoundView doc={doc} rounds={getRoundsForLeague(Number(id))} />;
}
