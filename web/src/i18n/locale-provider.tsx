"use client";

import { createContext, ReactNode, startTransition, useContext, useMemo, useState } from "react";

import {
  LOCALE_COOKIE,
  Locale,
  TranslationKey,
  TranslationParams,
  formatDateTime,
  formatLocalizedError,
  translate,
  translateText,
} from "@/i18n/translations";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, params?: TranslationParams) => string;
  text: (value: string) => string;
  dateTime: (value: string) => string;
  errorMessage: (error: unknown, fallback: TranslationKey) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale: Locale;
}) {
  const [locale, setLocaleState] = useState(initialLocale);
  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale(nextLocale) {
        document.cookie = `${LOCALE_COOKIE}=${nextLocale}; Path=/; Max-Age=31536000; SameSite=Lax`;
        document.documentElement.lang = nextLocale;
        startTransition(() => setLocaleState(nextLocale));
      },
      t: (key, params) => translate(locale, key, params),
      text: (textValue) => translateText(locale, textValue),
      dateTime: (dateValue) => formatDateTime(locale, dateValue),
      errorMessage: (error, fallback) => formatLocalizedError(locale, error, fallback),
    }),
    [locale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error("useLocale must be used within LocaleProvider");
  }
  return context;
}
