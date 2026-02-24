import type { Metadata } from "next";
import { Exo_2, Teko } from "next/font/google";
import "./globals.css";

const exo2 = Exo_2({
  variable: "--font-exo2",
  subsets: ["latin"],
  display: "swap",
});

const teko = Teko({
  variable: "--font-teko",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ball Knowledge | Banger Radar",
  description:
    "AI-ranked football fixtures with explainable scoring and an interactive matchday experience.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${exo2.variable} ${teko.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
