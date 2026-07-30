"use client";

/**
 * Dashboard/inner-page shell mirroring the original Streamlit layout:
 * lavender background, SNAPCLASS logo + wordmark on the left, and on the
 * right either "Welcome, {name}" + Logout (pink) or a "Go back to Home"
 * button for guests. Footer: "Created with ❤️ by Antra".
 */
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";

export const LOGO_URL = "https://i.ibb.co/QjYq4Y3V/logo.png";

export function BrandWordmark({ size = "md" }: { size?: "md" | "lg" }) {
  return (
    <span
      className={
        size === "lg"
          ? "font-display text-5xl leading-[1.1] text-lavender"
          : "font-display text-2xl leading-[0.95] text-blurple"
      }
    >
      SNAP
      <br />
      CLASS
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { auth, logout } = useAuth();

  return (
    <div className="min-h-screen bg-lavender">
      <header className="mx-auto flex max-w-4xl items-center justify-between px-4 pt-6">
        <Link href="/" className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={LOGO_URL} alt="SnapClass logo" className="h-[70px]" />
          <BrandWordmark />
        </Link>

        {auth ? (
          <div className="flex items-center gap-4">
            <span className="font-body text-lg font-semibold text-ink">
              Welcome, {auth.name}
            </span>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => logout(auth.role === "student" ? "/student/login" : "/teacher/login")}
            >
              Logout
            </Button>
          </div>
        ) : (
          <Link href="/">
            <Button size="sm" variant="secondary">
              Go back to Home
            </Button>
          </Link>
        )}
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>

      <footer className="flex items-center justify-center gap-1.5 pb-8 pt-4">
        <p className="font-body font-bold text-black">Created with ❤️ by Antra</p>
      </footer>
    </div>
  );
}
