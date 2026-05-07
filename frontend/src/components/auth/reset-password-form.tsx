"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { resetPasswordSchema, type ResetPasswordFormValues } from "@/lib/auth-schemas";

export function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: ResetPasswordFormValues) {
    setSubmitting(true);
    setServerError(null);
    setSuggestions([]);
    try {
      await authApi.passwordReset({ token, new_password: values.new_password });
      toast.success("Password updated. Please sign in.");
      router.replace("/login");
    } catch (e) {
      if (e instanceof ApiError) {
        setServerError(e.message);
        const detail = e.detail as { suggestions?: string[] } | undefined;
        if (detail?.suggestions) setSuggestions(detail.suggestions);
      } else {
        setServerError("Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="space-y-3 text-sm">
        <p>Missing or invalid reset link.</p>
        <Link href="/forgot-password" className="text-foreground underline">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="reset-password">New password</Label>
        <Input
          id="reset-password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.new_password}
          {...register("new_password")}
        />
        {errors.new_password && (
          <p className="text-destructive text-sm">{errors.new_password.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="reset-confirm">Confirm password</Label>
        <Input
          id="reset-confirm"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirm_password}
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

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Updating…" : "Update password"}
      </Button>
    </form>
  );
}
