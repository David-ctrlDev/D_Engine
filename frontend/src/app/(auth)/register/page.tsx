"use client";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { RegisterForm } from "@/components/auth/register-form";
import { useT } from "@/lib/i18n/provider";

export default function RegisterPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.register.eyebrow")}
        title={t("auth.register.title")}
        subtitle={t("auth.register.subtitle")}
      />
      <RegisterForm />
    </>
  );
}
