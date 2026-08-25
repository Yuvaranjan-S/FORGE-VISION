import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FORGE-VISION | Forensic Video Intelligence Platform",
  description: "Vendor-Agnostic DVR/NVR Forensic Intelligence & Evidence Reconstruction Platform — SIH150",
  keywords: "DVR forensics, NVR evidence, digital forensics, video analysis, chain of custody, SIH150",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
