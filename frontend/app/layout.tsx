import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Healf Product Intelligence Agent",
  description: "A specialized chat agent for Healf product pages, grounded in live data.",
};

// Set the theme before first paint to avoid a flash of the wrong theme.
const themeInit = `
try {
  var t = localStorage.getItem('healf.theme');
  if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  }
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        {children}
      </body>
    </html>
  );
}
