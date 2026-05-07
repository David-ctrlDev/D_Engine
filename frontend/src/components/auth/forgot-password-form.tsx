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
        className="h-11 w-full bg-gradient-to-r from-sky-500 via-indigo-500 to-fuchsia-500 text-white shadow-lg shadow-indigo-500/20 transition-shadow hover:shadow-indigo-500/30 disabled:opacity-70"
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
