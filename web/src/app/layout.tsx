import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Script from "next/script";

import { TopBar } from "@/components/TopBar";

import "./globals.css";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ThetaScout",
  description:
    "Covered call screener: live option chains, Black-Scholes assignment probability and multi-stock opportunity ranking.",
};

// Apply a saved theme choice before first paint so the page never flashes the wrong theme.
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="flex min-h-full flex-col">
        <Script id="theme" strategy="beforeInteractive" dangerouslySetInnerHTML={{ __html: themeScript }} />
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
