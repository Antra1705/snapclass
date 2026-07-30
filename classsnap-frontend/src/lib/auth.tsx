"use client";

/**
 * Auth context: holds the logged-in user (from localStorage), exposes login
 * helpers that persist the token, and wires a global 401 handler that logs the
 * user out and redirects to the correct login page.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  clearAuth,
  readAuth,
  setUnauthorizedHandler,
  writeAuth,
  type StoredAuth,
} from "./authToken";
import type { Role, StudentPublic, TeacherPublic } from "./types";

interface AuthContextValue {
  auth: StoredAuth | null;
  ready: boolean;
  loginTeacher: (teacher: TeacherPublic, token: string) => void;
  loginStudent: (student: StudentPublic, token: string) => void;
  logout: (redirectTo?: string) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [auth, setAuth] = useState<StoredAuth | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAuth(readAuth());
    setReady(true);
  }, []);

  const logout = useCallback(
    (redirectTo?: string) => {
      clearAuth();
      setAuth(null);
      if (redirectTo) router.push(redirectTo);
    },
    [router]
  );

  // Global 401 handler: clear session and bounce to the right login screen.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      const role = readAuth()?.role;
      clearAuth();
      setAuth(null);
      // Unknown role (guest) goes to the home portal chooser, never a
      // specific login page.
      router.push(role === "student" ? "/student/login" : role === "teacher" ? "/teacher/login" : "/");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  const loginTeacher = useCallback((teacher: TeacherPublic, token: string) => {
    const next: StoredAuth = {
      token,
      role: "teacher",
      id: teacher.teacher_id,
      name: teacher.name,
      username: teacher.username,
    };
    writeAuth(next);
    setAuth(next);
  }, []);

  const loginStudent = useCallback((student: StudentPublic, token: string) => {
    const next: StoredAuth = {
      token,
      role: "student",
      id: student.student_id,
      name: student.name,
    };
    writeAuth(next);
    setAuth(next);
  }, []);

  const value = useMemo(
    () => ({ auth, ready, loginTeacher, loginStudent, logout }),
    [auth, ready, loginTeacher, loginStudent, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/**
 * Client-side route guard. Renders children only when a user with the required
 * role is present; otherwise redirects. Returns a lightweight loading state
 * while auth is being read from storage.
 */
export function useRequireRole(role: Role) {
  const { auth, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!auth) {
      router.replace(role === "student" ? "/student/login" : "/teacher/login");
    } else if (auth.role !== role) {
      router.replace("/");
    }
  }, [auth, ready, role, router]);

  return { auth, ready: ready && !!auth && auth.role === role };
}
