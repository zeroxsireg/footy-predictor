import { allFixtureIds, getMatch } from "@/app/lib/data";
import { MatchCard } from "@/app/components/match/MatchCard";
import { NotFoundNotice } from "@/app/components/ui/NotFoundNotice";
import { resolveLocaleParams, getDict } from "@/app/lib/i18n-server";
import type { Locale } from "@/app/lib/i18n";

export function generateStaticParams() {
  return allFixtureIds().map((id) => ({ id: String(id) }));
}

export default async function MatchPage({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}) {
  const { id } = await resolveLocaleParams(params);
  const bundle = getMatch(Number(id));

  if (!bundle) return <NotFoundNotice message={getDict().match.notFound} />;
  return <MatchCard {...bundle} />;
}
