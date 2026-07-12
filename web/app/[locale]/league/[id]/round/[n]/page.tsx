import { getLeagueIds, getRoundsForLeague, getRound } from "@/app/lib/data";
import { LeagueRoundView } from "@/app/components/league/LeagueRoundView";
import { NotFoundNotice } from "@/app/components/ui/NotFoundNotice";
import { resolveLocaleParams, getDict } from "@/app/lib/i18n-server";
import type { Locale } from "@/app/lib/i18n";

export function generateStaticParams() {
  return getLeagueIds().flatMap((id) =>
    getRoundsForLeague(id).map((n) => ({ id: String(id), n: String(n) })),
  );
}

export default async function RoundPage({
  params,
}: {
  params: Promise<{ locale: Locale; id: string; n: string }>;
}) {
  const { id, n } = await resolveLocaleParams(params);
  const doc = getRound(Number(id), Number(n));

  if (!doc) return <NotFoundNotice message={getDict().league.notFound} />;
  return <LeagueRoundView doc={doc} rounds={getRoundsForLeague(Number(id))} />;
}
