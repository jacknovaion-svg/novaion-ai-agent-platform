import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "NOVAION AI Agent Platform",
  description: "Unified AI search, procurement, and resource discovery platform.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <I18nProvider>
          <AppShell>{children}</AppShell>
        </I18nProvider>
      </body>
    </html>
  );
}
