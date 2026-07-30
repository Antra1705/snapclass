"use client";

/**
 * The original app registers students inline on the FaceID login screen
 * (after an unrecognized face), so this route simply redirects there.
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui/feedback";

export default function StudentRegisterRedirect() {
  const router = useRouter();

  useEffect(() => {
    const joinCode = new URLSearchParams(window.location.search).get("join-code");
    router.replace(joinCode ? `/student/login?join-code=${joinCode}` : "/student/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-lavender">
      <Spinner label="Redirecting…" />
    </div>
  );
}
