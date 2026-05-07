"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { mfaCodeSchema, type MFACodeFormValues } from "@/lib/auth-schemas";

export function MFAForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [useRecovery, setUseRecovery] = useState(false);

  useEffect(() => {
    // We need the value once at mount; the rule against setState in
    // effects is for cascading renders, not initial bootstrap.
    const t = sessionStorage.getItem("mfa_token");
    if (!t) {
      router.replace("/login");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(t);
  }, [router]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MFACodeFormValues>({
    resolver: zodResolver(mfaCodeSchema),
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
      setServerError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="mfa-code">{useRecovery ? "Recovery code" : "Authentication code"}</Label>
        <Input
          id="mfa-code"
          inputMode={useRecovery ? "text" : "numeric"}
          autoComplete="one-time-code"
          aria-invalid={!!errors.code}
          placeholder={useRecovery ? "XXXX-XXXX-XXXX" : "123456"}
          {...register("code")}
        />
        {errors.code && <p className="text-destructive text-sm">{errors.code.message}</p>}
        <button
          type="button"
          onClick={() => setUseRecovery((v) => !v)}
          className="text-muted-foreground text-xs underline"
        >
          {useRecovery ? "Use code from authenticator app" : "Use a recovery code instead"}
        </button>
      </div>

      {serverError && (
        <p className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
          {serverError}
        </p>
      )}

      <Button type="submit" className="w-full" disabled={submitting || !token}>
        {submitting ? "Verifying…" : "Verify"}
      </Button>
    </form>
  );
}
