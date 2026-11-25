import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Opus Clip - AI Long Video to Viral Shorts Generator",
  description: "Generate 10 viral clips from 1 video, with AI virality score, auto-face reframing, and dynamic animated captions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0d0d11] text-[#ededef] antialiased selection:bg-purple-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
