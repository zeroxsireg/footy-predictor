"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LOCALES, LOCALE_LABEL, isLocale, type Locale } from "@/app/lib/i18n";
import { cx } from "@/app/lib/cx";

/** Swaps the leading locale segment of the current path, preserving the page. */
export function LanguageSwitcher({ current }: { current: Locale }) {
  const pathname = usePathname() || `/${current}`;

  const swap = (locale: Locale): string => {
    const segments = pathname.split("/");
    if (segments.length > 1 && isLocale(segments[1])) {
      segments[1] = locale;
      return segments.join("/") || "/";
    }
    return `/${locale}`;
  };

  return (
    <div className="flex gap-px">
      {LOCALES.map((l) => (
        <Link
          key={l}
          href={swap(l)}
          className={cx(
            "panel px-2 py-0.5 tracking-[0.12em]",
            l === current ? "border-red text-red" : "text-dim hover:border-fg hover:text-fg",
          )}
          aria-current={l === current ? "true" : undefined}
        >
          {LOCALE_LABEL[l]}
        </Link>
      ))}
    </div>
  );
}
