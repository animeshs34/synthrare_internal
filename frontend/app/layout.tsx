import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SynthRare — Synthetic Rare Data",
  description: "Generate high-fidelity synthetic datasets for rare domains",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
