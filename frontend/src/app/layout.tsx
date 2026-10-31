import type { Metadata, Viewport } from "next";
import { AppHeader } from "@/components/AppHeader";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LiveProvider } from "@/context/LiveContext";
import { THEME_BOOT_SCRIPT, ThemeProvider } from "@/context/ThemeContext";
import { ToastProvider } from "@/context/ToastContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "NetSleuth",
  description: "What's on your home network, what's new, and what left.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f6f8" },
    { media: "(prefers-color-scheme: dark)", color: "#0c0f13" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <ThemeProvider>
          <ToastProvider>
            <LiveProvider>
              <AppHeader />
              <main className="mx-auto max-w-6xl px-4 pb-16 pt-6">
                <ErrorBoundary>{children}</ErrorBoundary>
              </main>
            </LiveProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
