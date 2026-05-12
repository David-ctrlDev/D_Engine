"use client";

/**
 * Login form — enterprise rewrite.
 *
 * Differences from the previous take:
 *   • Page eyebrow + ``<h1>`` + tenant subtitle sit at the top of
 *     the form column (not inside a card).
 *   • SSO row (Google / Microsoft / SAML) comes *before* the
 *     email/password form, because enterprise sign-ins are SSO
 *     90%+ of the time.
 *   • A divider separates SSO from the email/password fallback.
 *   • Inputs have visible labels (not placeholders only) wired to
 *     ``htmlFor``. Forgot-password link sits in the password
 *     label row.
 *   • "Remember this device" checkbox above the submit.
 *   • Caps-Lock detector under the password field — enterprise
 *     polish that prevents the "I keep typing the wrong password"
 *     dance.
 *   • Submit button is solid indigo (sober) with proper loading
 *     state (spinner + label change).
 *   • Inline error live region (``aria-live="polite"``) so screen
 *     readers announce failures.
 *   • Bottom link is "Solicita acceso" — enterprise tenants don't
 *     self-register.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { SsoButtons } from "@/components/auth/sso-buttons";
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
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);

  // If the SSO flow bounced us back with an error code, surface
  // it via toast on first render. We strip the query param so a
  // refresh doesn't fire the toast a second time.
  useEffect(() => {
    const errCode = searchParams.get("sso_error");
    if (!errCode) return;
    const provider = searchParams.get("provider");
    toast.error(t(`auth.login.sso_error.${errCode}` as never, { provider: provider ?? "SSO" }), {
      description: t("auth.login.sso_error_sub"),
    });
    // Clean the URL — replace state so refresh doesn't re-fire.
    const url = new URL(window.location.href);
    url.searchParams.delete("sso_error");
    url.searchParams.delete("provider");
    window.history.replaceState({}, "", url.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const schema = useMemo(() => buildLoginSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
    mode: "onTouched",
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

  // Caps-lock detection — fires on keydown anywhere in the form.
  // Hooked on window so it catches lock changes from any input.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.getModifierState) {
        setCapsLockOn(e.getModifierState("CapsLock"));
      }
    };
    window.addEventListener("keydown", handler);
    window.addEventListener("keyup", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      window.removeEventListener("keyup", handler);
    };
  }, []);

  return (
    <div className="space-y-4 xl:space-y-6">
      {/* Header — page eyebrow + h1 + tenant subtitle. Compact at
          lg for laptop viewports. */}
      <div className="text-center">
        <p className="font-mono text-[10.5px] tracking-[0.2em] text-zinc-500 uppercase">
          {t("auth.login.workspace_eyebrow")}
        </p>
        <h1
          id="auth-page-heading"
          className="mt-1.5 text-[1.35rem] leading-[1.2] font-semibold tracking-[-0.02em] text-zinc-50 xl:mt-2 xl:text-[1.7rem]"
        >
          {t("auth.login.title").replace("{accent}", t("auth.login.title_accent"))}
        </h1>
        <p className="mt-1 text-[12px] text-zinc-400 xl:mt-1.5 xl:text-[12.5px]">
          {t("auth.login.tenant_prefix")}{" "}
          <span className="font-mono text-zinc-200">{t("auth.login.tenant_default")}</span>
        </p>
      </div>

      {/* SSO block — primary path for enterprise. */}
      <SsoButtons />

      {/* Divider */}
      <div className="flex items-center gap-3" role="separator">
        <div className="h-px flex-1 bg-white/[0.08]" />
        <span className="font-mono text-[10px] tracking-wider text-zinc-500 uppercase">
          {t("auth.login.divider")}
        </span>
        <div className="h-px flex-1 bg-white/[0.08]" />
      </div>

      {/* Email/password form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <Label
            htmlFor="login-email"
            className="text-[12px] font-medium tracking-tight text-zinc-200"
          >
            {t("common.email")}
          </Label>
          <Input
            id="login-email"
            type="email"
            autoComplete="username"
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? "login-email-error" : undefined}
            className="h-10 border-white/[0.10] bg-white/[0.025] text-[13.5px] text-zinc-100 placeholder:text-zinc-500 focus-visible:border-indigo-400/60 focus-visible:ring-[3px] focus-visible:ring-indigo-400/20 xl:h-11 xl:text-[14px]"
            {...register("email")}
          />
          {errors.email && (
            <p
              id="login-email-error"
              role="alert"
              className="text-[11.5px] text-rose-400"
            >
              {errors.email.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <Label
              htmlFor="login-password"
              className="text-[12px] font-medium tracking-tight text-zinc-200"
            >
              {t("common.password")}
            </Label>
            <Link
              href="/forgot-password"
              className="text-[11.5px] text-zinc-400 transition-colors hover:text-zinc-200"
            >
              {t("auth.login.forgot")}
            </Link>
          </div>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            aria-describedby={
              [errors.password ? "login-password-error" : null, capsLockOn ? "caps-lock" : null]
                .filter(Boolean)
                .join(" ") || undefined
            }
            className="h-10 border-white/[0.10] bg-white/[0.025] text-[13.5px] text-zinc-100 placeholder:text-zinc-500 focus-visible:border-indigo-400/60 focus-visible:ring-[3px] focus-visible:ring-indigo-400/20 xl:h-11 xl:text-[14px]"
            {...register("password")}
          />
          {errors.password && (
            <p
              id="login-password-error"
              role="alert"
              className="text-[11.5px] text-rose-400"
            >
              {errors.password.message}
            </p>
          )}
          {capsLockOn && (
            <p
              id="caps-lock"
              role="status"
              className="flex items-center gap-1.5 text-[11px] text-amber-300/90"
            >
              <span className="size-1 rounded-full bg-amber-400" />
              {t("auth.login.caps_lock")}
            </p>
          )}
        </div>

        {/* Remember this device */}
        <label className="group flex cursor-pointer items-center gap-2 text-[12px] text-zinc-300">
          <input
            type="checkbox"
            className="size-3.5 cursor-pointer rounded-sm border-white/20 bg-white/[0.04] accent-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-400/40 focus-visible:outline-none"
          />
          <span className="select-none">{t("auth.login.remember_device")}</span>
        </label>

        {serverError && (
          <p
            role="alert"
            aria-live="polite"
            className="rounded-md border border-rose-500/30 bg-rose-500/[0.06] px-3 py-2 text-[12px] text-rose-300"
          >
            {serverError}
          </p>
        )}

        <Button
          type="submit"
          // Solid indigo, not violet — sober enterprise accent.
          // Loading state with spinner + label swap. Disabled
          // until the form is at least minimally valid so
          // hitting Enter on an empty page doesn't fire a
          // useless network call.
          className="
            group h-10 w-full xl:h-11
            bg-indigo-600 text-[13.5px] font-medium tracking-tight text-white xl:text-[14px]
            shadow-[0_1px_2px_oklch(0_0_0/0.4),0_4px_12px_-4px_oklch(0.5_0.18_268/0.4)]
            transition-all
            hover:-translate-y-px hover:bg-indigo-500 hover:shadow-[0_6px_20px_-6px_oklch(0.55_0.2_268/0.55)]
            focus-visible:ring-[3px] focus-visible:ring-indigo-400/40 focus-visible:outline-none
            disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0 disabled:hover:shadow-none
          "
          disabled={submitting || !isValid}
        >
          {submitting ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              {t("auth.login.submitting")}
            </>
          ) : (
            <>
              {t("auth.login.submit")}
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </Button>

        <p className="text-center text-[12.5px] text-zinc-400">
          <Link
            href="/register"
            className="text-indigo-300 transition-colors hover:text-indigo-200"
          >
            {t("auth.login.request_access")}
          </Link>
        </p>
      </form>
    </div>
  );
}
