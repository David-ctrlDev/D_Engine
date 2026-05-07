"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildLoginSchema, type LoginFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function LoginForm() {
  const t = useT();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(() => buildLoginSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginFormValues) {
    setSubmitting(true);
    setServerError(null);
    try {
      const result = await authApi.login(values);
      if (result.mfa_required) {
        sessionStorage.setItem("mfa_token", result.mfa_token);
        router.push("/login/mfa");
        return;
      }
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, result);
      router.replace("/dashboard");
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="space-y-2">
        <Label htmlFor="login-email">{t("common.email")}</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          className="h-11"
          {...register("email")}
        />
        {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="login-password">{t("common.password")}</Label>
          <Link href="/forgot-password" className="text-muted-foreground text-xs underline">
            {t("auth.login.forgot")}
          </Link>
        </div>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          className="h-11"
          {...register("password")}
        />
        {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
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
        {submitting ? t("auth.login.submitting") : t("auth.login.submit")}
      </Button>

      <p className="text-muted-foreground text-center text-sm">
        {t("auth.login.no_account")}{" "}
        <Link href="/register" className="text-foreground underline">
          {t("auth.login.create_account")}
        </Link>
      </p>
    </form>
  );
}
