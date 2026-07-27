import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Healf Product Intelligence Agent",
  description: "A specialized chat agent for Healf product pages, grounded in live data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
