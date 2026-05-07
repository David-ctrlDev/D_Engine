"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { registerSchema, type RegisterFormValues } from "@/lib/auth-schemas";

export function RegisterForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", workspace_name: "" },
  });

  async function onSubmit(values: RegisterFormValues) {
    setSubmitting(true);
    setServerError(null);
    setSuggestions([]);
    try {
      const result = await authApi.register(values);
      toast.success("Account created. Check your terminal for the verification link.");
      router.replace(
        `/verify-email?email=${encodeURIComponent(values.email)}&user=${result.user_id}`,
      );
    } catch (e) {
      if (e instanceof ApiError) {
        setServerError(e.message);
        const detail = e.detail as { suggestions?: string[] } | undefined;
        if (detail?.suggestions) setSuggestions(detail.suggestions);
      } else {
        setServerError("Something went wrong. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="register-email">Email</Label>
        <Input
          id="register-email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          {...register("email")}
        />
        {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="register-workspace">Workspace name</Label>
        <Input
          id="register-workspace"
          autoComplete="organization"
          placeholder="Acme Inc"
          aria-invalid={!!errors.workspace_name}
          {...register("workspace_name")}
        />
        {errors.workspace_name && (
          <p className="text-destructive text-sm">{errors.workspace_name.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="register-password">Password</Label>
        <Input
          id="register-password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.password}
          {...register("password")}
        />
        {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
        <p className="text-muted-foreground text-xs">
          At least 12 characters. A passphrase of three or four random words works well.
        </p>
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
        {submitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="text-muted-foreground text-center text-sm">
        Already have an account?{" "}
        <Link href="/login" className="text-foreground underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
