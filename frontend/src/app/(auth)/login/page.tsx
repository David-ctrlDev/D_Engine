"use client";

import { LoginForm } from "@/components/auth/login-form";

/**
 * Login page — minimal wrapper. The form component owns the
 * eyebrow, ``<h1>`` and tenant subtitle so all the auth-page
 * copy stays colocated with the inputs.
 */
export default function LoginPage() {
  return <LoginForm />;
}
