"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { ErrorNotice } from "@/components/ui/feedback";
import { teacherLogin } from "@/lib/endpoints";
import { useAuth } from "@/lib/auth";

export default function TeacherLoginPage() {
  const router = useRouter();
  const { loginTeacher } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await teacherLogin({ username, password });
      loginTeacher(res.teacher, res.access_token);
      router.push("/teacher/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-md">
        <h2 className="mb-10 text-center font-display text-3xl text-ink">
          Login using password
        </h2>

        <form onSubmit={submit}>
          <Field label="Enter username">
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="TonyStark" />
          </Field>
          <Field label="Enter password">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
            />
          </Field>

          {error ? <ErrorNotice error={error} /> : null}

          <hr className="my-6 border-slate-300" />

          <div className="flex gap-3">
            <Button type="submit" variant="secondary" className="flex-1" loading={submitting}>
              Login
            </Button>
            <Link href="/teacher/register" className="flex-1">
              <Button type="button" variant="primary" className="w-full">
                Register Instead
              </Button>
            </Link>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
