import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Senus Board Intelligence",
  description: "AI-powered board reporting platform for Senus PLC",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        {/* Dark mode was previously dead code: dozens of `dark:` utility
            classes exist throughout the app, but nothing ever added the
            `.dark` class that `globals.css`'s `@custom-variant dark` keys
            off, and there was no OS-preference fallback either. This wires
            it up for real -- `attribute="class"` matches that existing
            selector, so this is a two-line fix that activates a lot of
            already-written (but previously inert) styling. */}
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
