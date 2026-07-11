import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Abachiwave",
  description: "AI-assisted music creation workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link className="brand" href="/">
              <strong>Abachiwave</strong>
              <span>Music creation workspace</span>
            </Link>
            <nav className="nav" aria-label="Primary">
              <Link href="/">Login</Link>
              <Link href="/projects">Projects</Link>
            </nav>
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
