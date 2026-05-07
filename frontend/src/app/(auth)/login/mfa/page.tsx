"use client";

import { AuthPageHeader } from "@/components/auth/auth-page-header";
import { MFAForm } from "@/components/auth/mfa-form";
import { useT } from "@/lib/i18n/provider";

export default function LoginMFAPage() {
  const t = useT();
  return (
    <>
      <AuthPageHeader
        eyebrow={t("auth.mfa.eyebrow")}
        title={t("auth.mfa.title")}
        subtitle={t("auth.mfa.subtitle")}
      />
      <MFAForm />
    </>
  );
}
