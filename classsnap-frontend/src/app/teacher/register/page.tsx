"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Alert, ErrorNotice } from "@/components/ui/feedback";
import { teacherRegister } from "@/lib/endpoints";

export default function TeacherRegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", name: "", password: "", confirm_password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await teacherRegister(form);
      setSuccess(res.message);
      setTimeout(() => router.push("/teacher/login"), 1500);
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
          Register your teacher profile
        </h2>

        <form onSubmit={submit}>
          <Field label="Enter username">
            <Input value={form.username} onChange={set("username")} placeholder="TonyStark" />
          </Field>
          <Field label="Enter name">
            <Input value={form.name} onChange={set("name")} placeholder="Tony Stark" />
          </Field>
          <Field label="Enter password">
            <Input type="password" value={form.password} onChange={set("password")} placeholder="********" />
          </Field>
          <Field label="Confirm your password">
            <Input
              type="password"
              value={form.confirm_password}
              onChange={set("confirm_password")}
              placeholder="********"
            />
          </Field>

          {error ? <ErrorNotice error={error} /> : null}
          {success ? <Alert variant="success">{success}</Alert> : null}

          <hr className="my-6 border-slate-300" />

          <div className="flex gap-3">
            <Button type="submit" variant="secondary" className="flex-1" loading={submitting}>
              Register Now
            </Button>
            <Link href="/teacher/login" className="flex-1">
              <Button type="button" variant="primary" className="w-full">
                Login Instead
              </Button>
            </Link>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
