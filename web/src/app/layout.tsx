import type { Metadata } from "next";
import { cookies } from "next/headers";

import { AppShell } from "@/components/app-shell";
import { ToastProvider } from "@/components/toast-provider";
import { LocaleProvider } from "@/i18n/locale-provider";
import { ThemeProvider, resolveInitialTheme } from "@/i18n/theme-provider";
import { DEFAULT_LOCALE, LOCALE_COOKIE, THEME_COOKIE, isLocale } from "@/i18n/translations";
import "./globals.css";

export const metadata: Metadata = {
  title: "Abachiwave",
  description: "AI-assisted music creation workspace",
  icons: { icon: "/icon.svg" },
};

// Applies the theme before first paint to avoid a flash of the wrong theme.
// Priority: persisted cookie > system preference (prefers-color-scheme).
const themeInitScript = `
(function () {
  try {
    var cookie = document.cookie
      .split("; ")
      .find(function (row) { return row.startsWith("${THEME_COOKIE}="); });
    var stored = cookie ? cookie.split("=")[1] : null;
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
  } catch (e) {}
})();
`;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const requestedLocale = cookieStore.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(requestedLocale) ? requestedLocale : DEFAULT_LOCALE;
  const theme = resolveInitialTheme(cookieStore.get(THEME_COOKIE)?.value);
  return (
    <html lang={locale} data-theme={theme}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <ThemeProvider initialTheme={theme}>
          <LocaleProvider initialLocale={locale}>
            <ToastProvider>
              <AppShell>{children}</AppShell>
            </ToastProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
