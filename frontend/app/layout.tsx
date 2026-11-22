import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "./globals.css";
import LocaleBoundary from "@/components/LocaleBoundary";

export const metadata: Metadata = {
  title: "Cadrage",
  description: "Assistant local de cadrage — projet étudiant",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <LocaleBoundary>{children}</LocaleBoundary>
      </body>
    </html>
  );
}
