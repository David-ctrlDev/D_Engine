"use client";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { LoginForm } from "@/components/auth/login-form";
import { useT } from "@/lib/i18n/provider";

export default function LoginPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.login.eyebrow")}
        title={t("auth.login.title")}
        subtitle={t("auth.login.subtitle")}
      />
      <LoginForm />
    </>
  );
}
