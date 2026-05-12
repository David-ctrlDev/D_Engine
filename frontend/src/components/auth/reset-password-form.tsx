"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildResetPasswordSchema, type ResetPasswordFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function ResetPasswordForm() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const schema = useMemo(() => buildResetPasswordSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: ResetPasswordFormValues) {
    setSubmitting(true);
    setServerError(null);
    setSuggestions([]);
    try {
      await authApi.passwordReset({ token, new_password: values.new_password });
      toast.success(t("auth.reset.toast_success"));
      router.replace("/login");
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

  if (!token) {
    return (
      <div className="space-y-3 text-sm">
        <p>{t("auth.reset.invalid_link")}</p>
        <Link href="/forgot-password" className="text-foreground underline">
          {t("auth.reset.request_new")}
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="space-y-2">
        <Label htmlFor="reset-password">{t("auth.reset.new_password")}</Label>
        <Input
          id="reset-password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.new_password}
          className="h-11"
          {...register("new_password")}
        />
        {errors.new_password && (
          <p className="text-destructive text-sm">{errors.new_password.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="reset-confirm">{t("common.confirm_password")}</Label>
        <Input
          id="reset-confirm"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirm_password}
          className="h-11"
          {...register("confirm_password")}
        />
        {errors.confirm_password && (
          <p className="text-destructive text-sm">{errors.confirm_password.message}</p>
        )}
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

      <Button
        type="submit"
        className="h-11 w-full bg-indigo-600 font-medium text-white shadow-[0_4px_16px_-4px_oklch(0.5_0.18_268/0.45),0_1px_2px_oklch(0_0_0/0.3)] transition-all hover:-translate-y-px hover:bg-indigo-500 hover:shadow-[0_6px_20px_-6px_oklch(0.55_0.2_268/0.6)] focus-visible:ring-[3px] focus-visible:ring-indigo-400/40 disabled:opacity-60 disabled:hover:translate-y-0"
        disabled={submitting}
      >
        {submitting ? t("auth.reset.submitting") : t("auth.reset.submit")}
      </Button>
    </form>
  );
}
