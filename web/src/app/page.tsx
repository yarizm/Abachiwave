"use client";

import { LogIn } from "lucide-react";
import Link from "next/link";

import { useLocale } from "@/i18n/locale-provider";

export default function HomePage() {
  const { t } = useLocale();
  return (
    <section className="panel">
      <h1>{t("Local development login")}</h1>
      <p>{t("Authentication is intentionally a placeholder in Milestone 0. Use the local projects workspace to verify the API, database, and frontend integration.")}</p>
      <Link className="button" href="/projects">
        <LogIn aria-hidden="true" size={18} />
        {t("Open projects")}
      </Link>
    </section>
  );
}
