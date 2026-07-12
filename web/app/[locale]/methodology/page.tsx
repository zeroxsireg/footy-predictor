import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/app/components/ui/Container";
import { SectionBlock } from "@/app/components/ui/Panel";
import { PrincipleCard } from "@/app/components/methodology/PrincipleCard";
import { ReadoutStat } from "@/app/components/methodology/ReadoutStat";
import { getDictionary } from "@/app/lib/locales";
import { resolveLocaleParams, getDict } from "@/app/lib/i18n-server";
import { localePath, type Locale } from "@/app/lib/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const d = getDictionary(locale);
  return {
    title: `${d.methodology.title} · ${d.header.brand.part1}${d.header.brand.part2}`,
  };
}

export default async function MethodologyPage({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}) {
  const { locale } = await resolveLocaleParams(params);
  const M = getDict().methodology;

  return (
    <Container className="py-8">
      <Link href={localePath(locale, "/")} className="lbl text-dim hover:text-red">
        {M.backToIndex}
      </Link>

      <h1 className="hd mt-4 text-[clamp(2.5rem,10vw,7rem)]">{M.title}</h1>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-dim">{M.intro}</p>

      <SectionBlock title={M.principlesLabel} className="mt-8">
        <div className="hairgrid grid-cols-1 sm:grid-cols-2">
          {M.principles.map((p) => (
            <PrincipleCard key={p.id} principle={p} />
          ))}
        </div>
      </SectionBlock>

      <SectionBlock title={M.calibration.label} className="mt-4">
        <p className="hd text-2xl text-fg">{M.calibration.title}</p>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-dim">
          {M.calibration.body}
        </p>
        <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
          {M.calibration.readouts.map((r) => (
            <ReadoutStat key={r.key} readout={r} />
          ))}
        </div>
      </SectionBlock>

      <SectionBlock title={M.honesty.label} className="mt-4">
        <ul className="space-y-3">
          {M.honesty.points.map((pt) => (
            <li key={pt} className="flex gap-3 text-sm leading-relaxed text-dim">
              <span className="text-red">&gt;&gt;</span>
              <span>{pt}</span>
            </li>
          ))}
        </ul>
      </SectionBlock>
    </Container>
  );
}
