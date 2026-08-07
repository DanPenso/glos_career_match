import type { Metadata } from "next";
import { Fredoka, Nunito } from "next/font/google";
import "./globals.css";

const body = Nunito({
  subsets: ["latin"],
  variable: "--font-body",
});

const display = Fredoka({
  subsets: ["latin"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "MatchKite",
  description:
    "Ready for your career to take flight? MatchKite matches you to local jobs, courses, training, or military pathways in Bristol and Gloucestershire.",
  icons: {
    icon: "/matchkite-badge.png",
    apple: "/matchkite-badge.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-GB">
      <body className={`${body.variable} ${display.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
