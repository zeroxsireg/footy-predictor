"use client";

import { useEffect } from "react";
import { DEFAULT_LOCALE } from "@/app/lib/i18n";

/**
 * Root entry. Static export can't do a server-side redirect, so we bounce to
 * the default-locale home on the client. Crawlers follow the canonical link.
 */
export default function RootRedirect() {
  useEffect(() => {
    window.location.replace(`/${DEFAULT_LOCALE}/`);
  }, []);

  return (
    <noscript>
      <meta httpEquiv="refresh" content={`0; url=/${DEFAULT_LOCALE}/`} />
    </noscript>
  );
}
