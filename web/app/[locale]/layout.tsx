import { notFound } from "next/navigation";
import { LOCALES, isLocale, type Locale } from "@/app/lib/i18n";
import { setRequestLocale, getDict } from "@/app/lib/i18n-server";
import { getLeagues } from "@/app/lib/data";
import { TelemetryHeader } from "@/app/components/TelemetryHeader";
import { HtmlLang } from "@/app/components/HtmlLang";

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale as Locale);
  const dict = getDict();

  return (
    <>
      <HtmlLang locale={locale} />
      <TelemetryHeader dict={dict} locale={locale as Locale} leagues={getLeagues()} />
      <main>{children}</main>
    </>
  );
}
