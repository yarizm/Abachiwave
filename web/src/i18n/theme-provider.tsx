"use client";

import {
  createContext,
  ReactNode,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { THEME_COOKIE, Theme, resolveInitialTheme, toggleThemeValue } from "@/i18n/translations";

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
  // The layout's pre-paint script already resolved cookie > system preference
  // into documentElement.dataset.theme; reuse it on the client so the React
  // state matches the painted DOM even when no cookie exists.
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof document === "undefined") {
      return initialTheme;
    }
    return resolveInitialTheme(document.documentElement.dataset.theme, initialTheme);
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const applyTheme = useCallback((nextTheme: Theme) => {
    document.cookie = `${THEME_COOKIE}=${nextTheme}; Path=/; Max-Age=31536000; SameSite=Lax`;
    document.documentElement.dataset.theme = nextTheme;
    startTransition(() => setThemeState(nextTheme));
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: applyTheme,
      toggleTheme: () => applyTheme(toggleThemeValue(theme)),
    }),
    [theme, applyTheme],
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
