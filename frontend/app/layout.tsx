import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../contexts/AuthContext";
import { AuthModalProvider } from "../contexts/AuthModalContext";
import { AuthModal } from "../components/auth/AuthModal";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Big Game Gabe — NFL TD Model",
  description: "NFL anytime touchdown probability model for WR and TE",
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "Big Game Gabe — NFL TD Model",
    description: "NFL anytime touchdown probability model for WR and TE",
    images: ["/og-image.svg"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Big Game Gabe — NFL TD Model",
    description: "NFL anytime touchdown probability model for WR and TE",
    images: ["/og-image.svg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <AuthModalProvider>
            {children}
            <AuthModal />
          </AuthModalProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
