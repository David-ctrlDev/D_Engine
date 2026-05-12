"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildForgotPasswordSchema, type ForgotPasswordFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function ForgotPasswordForm() {
  const t = useT();
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(() => buildForgotPasswordSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: ForgotPasswordFormValues) {
    setSubmitting(true);
    setServerError(null);
    try {
      await authApi.passwordForgot(values);
      setSubmitted(true);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="space-y-4">
        <p className="text-sm">{t("auth.forgot.confirmation")}</p>
        <Link href="/login" className="text-foreground inline-block text-sm underline">
          {t("auth.forgot.back")}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="space-y-2">
        <Label htmlFor="forgot-email">{t("common.email")}</Label>
        <Input
          id="forgot-email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          className="h-11"
          {...register("email")}
        />
        {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
      </div>

      {serverError && (
        <p className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
          {serverError}
        </p>
      )}

      <Button
        type="submit"
        className="h-11 w-full bg-indigo-600 font-medium text-white shadow-[0_4px_16px_-4px_oklch(0.5_0.18_268/0.45),0_1px_2px_oklch(0_0_0/0.3)] transition-all hover:-translate-y-px hover:bg-indigo-500 hover:shadow-[0_6px_20px_-6px_oklch(0.55_0.2_268/0.6)] focus-visible:ring-[3px] focus-visible:ring-indigo-400/40 disabled:opacity-60 disabled:hover:translate-y-0"
        disabled={submitting}
      >
        {submitting ? t("auth.forgot.submitting") : t("auth.forgot.submit")}
      </Button>

      <p className="text-muted-foreground text-center text-sm">
        <Link href="/login" className="text-foreground underline">
          {t("auth.forgot.back")}
        </Link>
      </p>
    </form>
  );
}
