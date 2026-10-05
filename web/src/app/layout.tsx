import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { TopBar } from "@/components/TopBar";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "ThetaScout",
  description:
    "Covered call screener: live option chains, Black-Scholes assignment probability and multi-stock opportunity ranking.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5 sm:px-6">{children}</main>
        <footer className="border-t border-border px-6 py-3 text-center text-xs text-muted">
          For educational purposes only. Not financial advice. Data from Yahoo Finance, may be
          delayed.
        </footer>
      </body>
    </html>
  );
}
