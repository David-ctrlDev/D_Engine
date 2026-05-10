import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";

import { QueryProvider } from "@/components/query-provider";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { LocaleProvider } from "@/lib/i18n/provider";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Display serif used by the editorial auth hero. Loaded once at the
// root so any other surface that wants an "editorial" headline can
// just reference ``var(--font-fraunces)`` or the ``font-serif``
// utility (mapped in tailwind.config implicitly via the variable).
const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  // Soft italic for the accent word in the headline.
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "dataprep",
  description: "Multi-tenant data preparation platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
      // next-themes flips the class on <html>; LocaleProvider mutates the
      // ``lang`` attribute on locale change. Both are intentional, so
      // suppress the hydration mismatch warning here.
      suppressHydrationWarning
    >
      <body className="bg-background text-foreground flex min-h-full flex-col">
        <ThemeProvider>
          <LocaleProvider>
            <QueryProvider>
              {children}
              <Toaster richColors closeButton />
            </QueryProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
