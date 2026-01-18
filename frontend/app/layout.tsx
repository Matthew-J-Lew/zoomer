import type { Metadata } from "next";
import { Lexend, Quicksand } from "next/font/google";
import "./globals.css";

const lexend = Lexend({
  variable: "--font-lexend",
  subsets: ["latin"],
});

const quicksand = Quicksand({
  variable: "--font-quicksand",
  subsets: ["latin"],
  weight: ["700"],
});

export const metadata: Metadata = {
  title: "zoomer",
  description: "Your accessible meeting assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${lexend.variable} ${quicksand.variable} antialiased bg-background text-primary-text font-sans`}
      >
        {children}
      </body>
    </html>
  );
}
