import type { Metadata } from "next";
import { Climate_Crisis, Outfit } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const climateCrisis = Climate_Crisis({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-climate-crisis",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: "SnapClass - Making Attendance faster using AI",
  description: "Face and voice attendance for classrooms.",
  icons: { icon: "https://i.ibb.co/C34kvnqJ/icon.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${climateCrisis.variable} ${outfit.variable}`}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
