import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "The Memory Host — Voice Memory Game",
  description:
    "A voice-based memory card game. Listen to sequences of words and repeat them back. How far can you go?",
  openGraph: {
    title: "The Memory Host",
    description: "Test your memory with this voice-based word recall game!",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body
        className="min-h-screen bg-[#0f1117] text-[#e9ecef] antialiased"
        suppressHydrationWarning
      >
        {/* Subtle background gradient */}
        <div className="fixed inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(92,124,250,0.08)_0%,_transparent_50%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_rgba(255,146,43,0.04)_0%,_transparent_50%)]" />
        </div>

        {/* Simple nav bar */}
        <nav className="relative z-10 flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
          <a
            href="/"
            className="text-xl font-bold tracking-tight text-gradient hover:opacity-80 transition-opacity"
          >
            The Memory Host
          </a>
          <div className="flex items-center gap-4">
            <a
              href="/leaderboard"
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Leaderboard
            </a>
          </div>
        </nav>

        {/* Main content */}
        <main className="relative z-10">{children}</main>

        {/* Footer */}
        <footer className="relative z-10 text-center py-8 text-xs text-gray-600">
          Powered by Pipecat · Deepgram · Next.js
        </footer>
      </body>
    </html>
  );
}
