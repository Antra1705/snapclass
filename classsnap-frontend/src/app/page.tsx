"use client";

/** Home screen mirroring the original Streamlit home: blurple background,
 *  centered SNAPCLASS logo/wordmark, and two lavender portal cards. */
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useQueryParam } from "@/lib/useQueryParam";
import { Button } from "@/components/ui/button";
import { LOGO_URL } from "@/components/AppShell";

export default function HomePage() {
  const { auth, ready } = useAuth();
  const router = useRouter();
  const joinCode = useQueryParam("join-code");

  // If already logged in, go to the right dashboard. Preserve ?join-code for students.
  useEffect(() => {
    if (!ready || !auth) return;
    if (auth.role === "teacher") {
      router.replace("/teacher/dashboard");
    } else {
      router.replace(joinCode ? `/student/dashboard?join-code=${joinCode}` : "/student/dashboard");
    }
  }, [auth, ready, router, joinCode]);

  const studentHref = joinCode ? `/student/login?join-code=${joinCode}` : "/student/login";

  return (
    <div className="flex min-h-screen flex-col items-center bg-blurple px-4 py-10">
      <div className="mb-8 mt-4 flex flex-col items-center justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={LOGO_URL} alt="SnapClass logo" className="h-[100px]" />
        <h1 className="text-center font-display text-6xl leading-[1.1] text-lavender">
          SNAP
          <br />
          CLASS
        </h1>
      </div>

      <div className="grid w-full max-w-2xl gap-6 sm:grid-cols-2">
        <div className="flex flex-col items-start gap-4 rounded-[5rem] bg-lavender p-10">
          <h2 className="font-display text-2xl text-ink">I&apos;m Student</h2>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="https://i.ibb.co/Nny7TyMC/Student.png" alt="Student" className="w-[120px]" />
          <Link href={studentHref}>
            <Button>
              Student Portal <span aria-hidden>↗</span>
            </Button>
          </Link>
        </div>

        <div className="flex flex-col items-start gap-4 rounded-[5rem] bg-lavender p-10">
          <h2 className="font-display text-2xl text-ink">I&apos;m Teacher</h2>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="https://i.ibb.co/wNPF0DH0/Teacher.png" alt="Teacher" className="w-[120px]" />
          <Link href="/teacher/login">
            <Button>
              Teacher Portal <span aria-hidden>↗</span>
            </Button>
          </Link>
        </div>
      </div>

      <footer className="mt-10 flex items-center justify-center gap-1.5">
        <p className="font-body font-bold text-white">Created with ❤️ by Antra</p>
      </footer>
    </div>
  );
}
