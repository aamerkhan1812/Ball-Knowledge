import type { Metadata } from "next";
import { Orbitron, Rajdhani } from "next/font/google";
import "./globals.css";

const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  display: "swap",
  weight: ["500", "700", "800"],
});

export const metadata: Metadata = {
  title: "Ball Knowledge | Tonight's Football Battlefield",
  description:
    "UEFA-night inspired AI match recommender with cinematic motion, tactical insights, and dynamic hype scoring.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${rajdhani.variable} ${orbitron.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
