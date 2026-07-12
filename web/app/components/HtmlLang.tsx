"use client";

import { useEffect } from "react";

/** Keeps <html lang> in sync with the active locale (root layout is static). */
export function HtmlLang({ locale }: { locale: string }) {
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return null;
}
