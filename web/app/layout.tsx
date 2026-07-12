import type { Metadata } from "next";
import { Archivo_Black, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/app/lib/theme";
import { DEFAULT_THEME, THEME_STORAGE_KEY } from "@/app/lib/theme-config";
import { getDictionary } from "@/app/lib/locales";
import { DEFAULT_LOCALE } from "@/app/lib/i18n";

const archivo = Archivo_Black({
  variable: "--font-archivo",
  weight: "400",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

const meta = getDictionary(DEFAULT_LOCALE).metadata;

export const metadata: Metadata = {
  title: meta.title,
  description: meta.description,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang={DEFAULT_LOCALE}
      className={`${archivo.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem(${JSON.stringify(
              THEME_STORAGE_KEY,
            )})||${JSON.stringify(
              DEFAULT_THEME,
            )};document.documentElement.setAttribute('data-theme',t)}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen bg-bg text-fg">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
