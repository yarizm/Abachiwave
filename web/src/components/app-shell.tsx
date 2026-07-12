"use client";

import { Languages } from "lucide-react";
import Link from "next/link";
import { ReactNode } from "react";

import { useLocale } from "@/i18n/locale-provider";
import { Locale } from "@/i18n/translations";

export function AppShell({ children }: { children: ReactNode }) {
  const { locale, setLocale, t } = useLocale();
  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/">
          <strong>Abachiwave</strong>
          <span>{t("Music creation workspace")}</span>
        </Link>
        <div className="topbar-actions">
          <nav className="nav" aria-label={t("Primary")}>
            <Link href="/">{t("Login")}</Link>
            <Link href="/projects">{t("Projects")}</Link>
          </nav>
          <label className="language-setting">
            <Languages aria-hidden="true" size={17} />
            <span>{t("Language")}</span>
            <select
              aria-label={t("Language")}
              onChange={(event) => setLocale(event.target.value as Locale)}
              value={locale}
            >
              <option value="en">{t("English")}</option>
              <option value="zh-CN">{t("Chinese")}</option>
            </select>
          </label>
        </div>
      </header>
      <main className="main">{children}</main>
    </div>
  );
}
