"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildRegisterSchema, type RegisterFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function RegisterForm() {
  const t = useT();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const schema = useMemo(() => buildRegisterSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", workspace_name: "" },
  });

  async function onSubmit(values: RegisterFormValues) {
    setSubmitting(true);
    setServerError(null);
    setSuggestions([]);
    try {
      const result = await authApi.register(values);
      toast.success(t("auth.register.toast_success"));
      router.replace(
        `/verify-email?email=${encodeURIComponent(values.email)}&user=${result.user_id}`,
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setServerError(e.message);
        const detail = e.detail as { suggestions?: string[] } | undefined;
        if (detail?.suggestions) setSuggestions(detail.suggestions);
      } else {
        setServerError(t("common.something_went_wrong"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  const FIELD_DELAY_BASE = 120;
  const FIELD_DELAY_STEP = 60;
  const fieldStyle = (i: number) => ({
    animationDelay: `${FIELD_DELAY_BASE + FIELD_DELAY_STEP * i}ms`,
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="auth-field-in space-y-2" style={fieldStyle(0)}>
        <Label htmlFor="register-email">{t("common.email")}</Label>
        <Input
          id="register-email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          className="h-11"
          {...register("email")}
        />
        {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
      </div>

      <div className="auth-field-in space-y-2" style={fieldStyle(1)}>
        <Label htmlFor="register-workspace">{t("common.workspace_name")}</Label>
        <Input
          id="register-workspace"
          autoComplete="organization"
          placeholder={t("auth.register.workspace_placeholder")}
          aria-invalid={!!errors.workspace_name}
          className="h-11"
          {...register("workspace_name")}
        />
        {errors.workspace_name && (
          <p className="text-destructive text-sm">{errors.workspace_name.message}</p>
        )}
      </div>

      <div className="auth-field-in space-y-2" style={fieldStyle(2)}>
        <Label htmlFor="register-password">{t("common.password")}</Label>
        <Input
          id="register-password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.password}
          className="h-11"
          {...register("password")}
        />
        {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
        <p className="text-muted-foreground text-xs">{t("auth.register.password_hint")}</p>
      </div>

      {serverError && (
        <div className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
          <p>{serverError}</p>
          {suggestions.length > 0 && (
            <ul className="mt-2 list-inside list-disc space-y-1 text-xs">
              {suggestions.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="auth-field-in" style={fieldStyle(3)}>
        <Button
          type="submit"
          className="h-11 w-full bg-indigo-600 font-medium text-white shadow-[0_4px_16px_-4px_oklch(0.5_0.18_268/0.45),0_1px_2px_oklch(0_0_0/0.3)] transition-all hover:-translate-y-px hover:bg-indigo-500 hover:shadow-[0_6px_20px_-6px_oklch(0.55_0.2_268/0.6)] focus-visible:ring-[3px] focus-visible:ring-indigo-400/40 disabled:opacity-60 disabled:hover:translate-y-0"
          disabled={submitting}
        >
          {submitting ? t("auth.register.submitting") : t("auth.register.submit")}
        </Button>
      </div>

      <p
        className="auth-field-in text-muted-foreground text-center text-sm"
        style={fieldStyle(4)}
      >
        {t("auth.register.have_account")}{" "}
        <Link href="/login" className="text-foreground underline">
          {t("auth.register.login_link")}
        </Link>
      </p>
    </form>
  );
}
