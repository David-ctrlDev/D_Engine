"use client";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { useT } from "@/lib/i18n/provider";

export default function ForgotPasswordPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.forgot.eyebrow")}
        title={t("auth.forgot.title")}
        subtitle={t("auth.forgot.subtitle")}
      />
      <ForgotPasswordForm />
    </>
  );
}
