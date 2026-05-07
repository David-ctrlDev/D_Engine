"use client";

import { Suspense } from "react";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { useT } from "@/lib/i18n/provider";

export default function ResetPasswordPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.reset.eyebrow")}
        title={t("auth.reset.title")}
        subtitle={t("auth.reset.subtitle")}
      />
      <Suspense>
        <ResetPasswordForm />
      </Suspense>
    </>
  );
}
