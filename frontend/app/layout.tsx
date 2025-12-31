import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "BGGTDM - Big Game Gabe TD Model",
  description: "NFL Touchdown Prediction Model - Find value in anytime TD scorer odds",
  icons: {
    icon: "/gabe-davis-headshot.png",
  },
  openGraph: {
    title: "BGGTDM - Big Game Gabe TD Model",
    description: "NFL Touchdown Prediction Model - Find value in anytime TD scorer odds",
    images: ["/gabe-davis-background.jpg"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BGGTDM - Big Game Gabe TD Model",
    description: "NFL Touchdown Prediction Model - Find value in anytime TD scorer odds",
    images: ["/gabe-davis-background.jpg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
