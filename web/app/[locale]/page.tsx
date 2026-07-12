import Link from "next/link";
import { getLeagues } from "@/app/lib/data";
import { setRequestLocale, getDict } from "@/app/lib/i18n-server";
import { localePath, type Locale } from "@/app/lib/i18n";
import { pad2 } from "@/app/lib/format";
import { Container } from "@/app/components/ui/Container";

export default async function Home({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const dict = getDict();
  const leagues = getLeagues();

  return (
    <div>
      {/* ── HERO ─────────────────────────────────────────────────────── */}
      <section className="border-b border-line py-12 sm:py-20">
        <Container>
          <p className="lbl mb-4">{dict.hero.sub}</p>
          <h1 className="hd text-[clamp(3rem,13vw,11rem)]">
            {dict.hero.titleLine1}
            <br />
            <span className="text-red">{dict.hero.titleLine2}</span>
          </h1>
          <p className="mt-6 max-w-xl text-sm leading-relaxed text-dim">
            {dict.hero.description}
          </p>
        </Container>
      </section>

      {/* ── TELEMETRY READOUT ───────────────────────────────────────── */}
      <section className="border-b border-line">
        <Container className="px-0">
          <div className="hairgrid grid-cols-2 sm:grid-cols-4">
            {dict.stats.map((s) => (
              <div key={s.key} className="p-4">
                <p className="lbl">[ {s.key} ]</p>
                <p className="hd mt-2 text-4xl text-fg">{s.value}</p>
                <p className="mt-2 text-[0.68rem] leading-tight text-dim">{s.note}</p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      {/* ── LEAGUE ENTRY POINTS ─────────────────────────────────────── */}
      <section className="py-10">
        <Container>
          <p className="lbl mb-4">{dict.home.selectLeague}</p>
          <div className="hairgrid grid-cols-1 border border-line sm:grid-cols-3">
            {leagues.map((l, i) => (
              <Link
                key={l.id}
                href={localePath(locale, `/league/${l.id}`)}
                className="group flex items-center justify-between p-6 hover:bg-panel-hover"
              >
                <div>
                  <p className="lbl">
                    {dict.home.unit} / {pad2(i + 1)}
                  </p>
                  <p className="hd mt-1 text-2xl group-hover:text-red">{l.name}</p>
                  <p className="text-[0.68rem] text-dim">{l.code}</p>
                </div>
                <span className="hd text-3xl text-line group-hover:text-red">&gt;</span>
              </Link>
            ))}
          </div>
        </Container>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────── */}
      <footer className="border-t border-line py-6 text-[0.68rem] tracking-[0.12em] text-dim">
        <Container>
          {dict.footer.disclaimer}
        </Container>
      </footer>
    </div>
  );
}
