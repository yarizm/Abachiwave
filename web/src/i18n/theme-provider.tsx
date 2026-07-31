"use client";

import { createContext, ReactNode, startTransition, useContext, useMemo, useState } from "react";

import { DEFAULT_THEME, THEME_COOKIE, Theme, isTheme } from "@/i18n/translations";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({
  children,
  initialTheme,
}: {
  children: ReactNode;
  initialTheme: Theme;
}) {
  const [theme, setThemeState] = useState(initialTheme);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme(nextTheme) {
        document.cookie = `${THEME_COOKIE}=${nextTheme}; Path=/; Max-Age=31536000; SameSite=Lax`;
        document.documentElement.dataset.theme = nextTheme;
        startTransition(() => setThemeState(nextTheme));
      },
      toggleTheme() {
        this.setTheme(theme === "dark" ? "light" : "dark");
      },
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}

/** Resolve the initial theme from a cookie value, falling back to the default. */
export function resolveInitialTheme(cookieValue: string | undefined): Theme {
  return isTheme(cookieValue) ? cookieValue : DEFAULT_THEME;
}
