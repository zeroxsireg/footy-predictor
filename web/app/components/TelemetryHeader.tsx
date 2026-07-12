"use client";

import Link from "next/link";
import { useTheme } from "@/app/lib/theme";
import { THEMES } from "@/app/lib/theme-config";
import { localePath, type Locale } from "@/app/lib/i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";
import type { Dictionary } from "@/app/lib/locales";
import type { League } from "@/app/lib/types";

export function TelemetryHeader({
  dict,
  locale,
  leagues,
}: {
  dict: Dictionary;
  locale: Locale;
  leagues: League[];
}) {
  const { theme, setTheme } = useTheme();
  const h = dict.header;

  const linkClass =
    "panel px-3 py-1 text-[0.68rem] tracking-[0.12em] text-dim hover:border-red hover:text-fg";

  return (
    <header className="border-b border-line">
      {/* status strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-[0.68rem] tracking-[0.12em] text-dim">
        <span className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 bg-green" />
          {h.systemStatus}
        </span>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {THEMES.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTheme(t.id)}
                className={theme === t.id ? "text-red" : "cursor-pointer hover:text-fg"}
              >
                [{h.themes[t.key]}]
              </button>
            ))}
          </div>
          <span className="text-line">|</span>
          <LanguageSwitcher current={locale} />
        </div>
      </div>

      {/* brand + league bar */}
      <div className="grid grid-cols-1 items-center gap-1 border-t border-line px-4 py-2 sm:grid-cols-[1fr_auto]">
        <Link href={localePath(locale, "/")} className="hd text-red text-xl">
          {h.brand.part1}
          <span className="text-fg">{h.brand.part2}</span>
          <span className="align-super text-[0.6rem] text-dim">®</span>
        </Link>
        <nav className="flex flex-wrap gap-px">
          {leagues.map((l) => (
            <Link key={l.id} href={localePath(locale, `/league/${l.id}`)} className={linkClass}>
              <span className="text-fg">{l.code}</span> {l.name}
            </Link>
          ))}
          <Link href={localePath(locale, "/methodology")} className={linkClass}>
            {dict.methodology.nav}
          </Link>
        </nav>
      </div>
    </header>
  );
}
