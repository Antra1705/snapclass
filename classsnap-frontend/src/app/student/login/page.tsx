"use client";

/**
 * Student FaceID login (mirrors the Streamlit student_screen): capture a
 * photo, run recognition, and if the face is new show the inline
 * "Register new Profile" section reusing the SAME captured photo.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Alert, ErrorNotice } from "@/components/ui/feedback";
import { CameraCapture } from "@/components/CameraCapture";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { studentLogin, studentRegister } from "@/lib/endpoints";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useQueryParam } from "@/lib/useQueryParam";

export default function StudentLoginPage() {
  const router = useRouter();
  const { loginStudent } = useAuth();
  const joinCode = useQueryParam("join-code");

  const [face, setFace] = useState<Blob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [showRegistration, setShowRegistration] = useState(false);

  const [newName, setNewName] = useState("");
  const [voice, setVoice] = useState<Blob | null>(null);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<unknown>(null);

  const goToDashboard = () =>
    router.push(joinCode ? `/student/dashboard?join-code=${joinCode}` : "/student/dashboard");

  const submit = async () => {
    if (!face) return;
    setSubmitting(true);
    setError(null);
    setScanMessage(null);
    setShowRegistration(false);
    try {
      const res = await studentLogin(face);
      loginStudent(res.student, res.access_token);
      goToDashboard();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // Backend message distinguishes: no face / multiple faces / new student.
        setScanMessage(err.message);
        if (err.message.toLowerCase().includes("new student")) setShowRegistration(true);
      } else {
        setError(err);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const createAccount = async () => {
    if (!newName.trim()) {
      setRegisterError(new Error("Please enter your name!"));
      return;
    }
    if (!face) return;
    setRegistering(true);
    setRegisterError(null);
    try {
      const res = await studentRegister(newName.trim(), face, voice);
      loginStudent(res.student, res.access_token);
      goToDashboard();
    } catch (err) {
      setRegisterError(err);
    } finally {
      setRegistering(false);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-md">
        <h2 className="mb-8 text-center font-display text-3xl text-ink">Login using FaceID</h2>

        <p className="mb-2 text-sm font-medium text-ink">Position your face in the center</p>
        <CameraCapture
          onChange={(blob) => {
            setFace(blob);
            setScanMessage(null);
            setShowRegistration(false);
          }}
        />

        {scanMessage ? (
          <Alert variant={showRegistration ? "info" : "warning"} className="mt-4">
            {scanMessage}
          </Alert>
        ) : null}
        {error ? (
          <div className="mt-4">
            <ErrorNotice error={error} />
          </div>
        ) : null}

        <Button className="mt-4 w-full" onClick={submit} disabled={!face} loading={submitting}>
          Login
        </Button>

        {showRegistration ? (
          <div className="mt-8 rounded-[20px] border border-slate-400 bg-white p-6">
            <h3 className="mb-4 font-display text-2xl text-ink">Register new Profile</h3>

            <Field label="Enter your name">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="E.g. Tony Stark"
              />
            </Field>

            <h4 className="mb-1 mt-4 font-semibold text-ink">Optional : Voice Enrollment</h4>
            <Alert variant="info" className="mb-3">
              Enroll your voice for voice only attendance
            </Alert>
            <p className="mb-2 text-sm text-slate-600">
              Record a short phrase like I am present, My name is Tony Stark.
            </p>
            <VoiceRecorder onChange={setVoice} />

            {registerError ? (
              <div className="mt-4">
                <ErrorNotice error={registerError} />
              </div>
            ) : null}

            <Button className="mt-4 w-full" onClick={createAccount} loading={registering}>
              Create Account
            </Button>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
