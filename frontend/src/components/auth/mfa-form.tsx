"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildMFACodeSchema, type MFACodeFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function MFAForm() {
  const t = useT();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [useRecovery, setUseRecovery] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("mfa_token");
    if (!stored) {
      router.replace("/login");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(stored);
  }, [router]);

  const schema = useMemo(() => buildMFACodeSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MFACodeFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: "" },
  });

  async function onSubmit(values: MFACodeFormValues) {
    if (!token) return;
    setSubmitting(true);
    setServerError(null);
    try {
      const result = await authApi.mfaVerify({ mfa_token: token, code: values.code });
      sessionStorage.removeItem("mfa_token");
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
        <Label htmlFor="mfa-code">
          {useRecovery ? t("auth.mfa.label_recovery") : t("auth.mfa.label_totp")}
        </Label>
        <Input
          id="mfa-code"
          inputMode={useRecovery ? "text" : "numeric"}
          autoComplete="one-time-code"
          aria-invalid={!!errors.code}
          placeholder={useRecovery ? "XXXX-XXXX-XXXX" : "123456"}
          className="h-11 font-mono tracking-widest"
          {...register("code")}
        />
        {errors.code && <p className="text-destructive text-sm">{errors.code.message}</p>}
        <button
          type="button"
          onClick={() => setUseRecovery((v) => !v)}
          className="text-muted-foreground text-xs underline"
        >
          {useRecovery ? t("auth.mfa.toggle_to_totp") : t("auth.mfa.toggle_to_recovery")}
        </button>
      </div>

      {serverError && (
        <p className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
          {serverError}
        </p>
      )}

      <Button
        type="submit"
        className="h-11 w-full bg-gradient-to-r from-sky-500 via-indigo-500 to-fuchsia-500 text-white shadow-lg shadow-indigo-500/20 transition-shadow hover:shadow-indigo-500/30 disabled:opacity-70"
        disabled={submitting || !token}
      >
        {submitting ? t("auth.mfa.submitting") : t("auth.mfa.submit")}
      </Button>
    </form>
  );
}
