"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { loginSchema, type LoginFormValues } from "@/lib/auth-schemas";

export function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginFormValues) {
    setSubmitting(true);
    setServerError(null);
    try {
      const result = await authApi.login(values);
      if (result.mfa_required) {
        // Hand off to the MFA page, which finishes login and sets cookies.
        sessionStorage.setItem("mfa_token", result.mfa_token);
        router.push("/login/mfa");
        return;
      }
      // Cookies were set by the response. Refresh the cached current user.
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, result);
      router.replace("/dashboard");
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="login-email">Email</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          {...register("email")}
        />
        {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="login-password">Password</Label>
          <Link href="/forgot-password" className="text-muted-foreground text-xs underline">
            Forgot password?
          </Link>
        </div>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.password}
          {...register("password")}
        />
        {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
      </div>

      {serverError && (
        <p className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
          {serverError}
        </p>
      )}

      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in"}
      </Button>

      <p className="text-muted-foreground text-center text-sm">
        New here?{" "}
        <Link href="/register" className="text-foreground underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}
