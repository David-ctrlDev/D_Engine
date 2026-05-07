"use client";

import { Suspense } from "react";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { VerifyEmailFlow } from "@/components/auth/verify-email-flow";
import { useT } from "@/lib/i18n/provider";

export default function VerifyEmailPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.verify.eyebrow")}
        title={t("auth.verify.title")}
        subtitle={t("auth.verify.subtitle")}
      />
      <Suspense>
        <VerifyEmailFlow />
      </Suspense>
    </>
  );
}
