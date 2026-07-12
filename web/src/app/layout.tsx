import type { Metadata } from "next";
import { cookies } from "next/headers";

import { AppShell } from "@/components/app-shell";
import { LocaleProvider } from "@/i18n/locale-provider";
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n/translations";
import "./globals.css";

export const metadata: Metadata = {
  title: "Abachiwave",
  description: "AI-assisted music creation workspace",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const requestedLocale = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(requestedLocale) ? requestedLocale : DEFAULT_LOCALE;
  return (
    <html lang={locale}>
      <body>
        <LocaleProvider initialLocale={locale}>
          <AppShell>{children}</AppShell>
        </LocaleProvider>
      </body>
    </html>
  );
}
