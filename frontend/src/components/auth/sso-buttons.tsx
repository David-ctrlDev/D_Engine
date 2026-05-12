"use client";

/**
 * Enterprise SSO row — Google, Microsoft, generic SAML.
 *
 * Google + Microsoft are wired through the backend's OAuth flow:
 *
 *   1. Button click → ``window.location.href`` jumps to
 *      ``/api/v1/auth/sso/{provider}/start``.
 *   2. The backend mints a state JWT, sets it as an HttpOnly
 *      cookie, and 302s to the provider's consent screen.
 *   3. The provider redirects back to the backend's
 *      ``/sso/{provider}/callback`` with ``code`` + ``state``.
 *   4. The backend validates state, exchanges the code for
 *      tokens, fetches userinfo, finds-or-provisions the user,
 *      sets the regular auth cookies, and 302s the browser to
 *      ``/dashboard``.
 *
 * When the backend's provider credentials are unset, /start
 * redirects back to ``/login?sso_error=not_configured`` and the
 * login page surfaces a friendly toast.
 *
 * SAML still shows the "not configured" toast — proper SAML
 * needs IdP metadata per workspace and a parser; we'll land
 * that as a separate workstream.
 */

import { KeyRound } from "lucide-react";
import { toast } from "sonner";

import { useT } from "@/lib/i18n/provider";

type Provider = "google" | "microsoft" | "saml";

const PROVIDER_LABEL: Record<Provider, string> = {
  google: "Google",
  microsoft: "Microsoft",
  saml: "SAML SSO",
};

/** Backend origin — typically the same as the API base URL so
 *  the OAuth redirect_uri registered in the provider console
 *  matches what we send. Falls back to "" so dev (Next + FastAPI
 *  on different ports) works via the env var. */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export function SsoButtons() {
  const t = useT();

  function handleSso(provider: Provider) {
    if (provider === "saml") {
      // SAML is intentionally not wired yet.
      toast.info(
        t("auth.login.sso_not_configured", { provider: PROVIDER_LABEL[provider] }),
        { description: t("auth.login.sso_not_configured_sub") },
      );
      return;
    }
    // Top-level navigation is the canonical OAuth entry point —
    // a fetch-then-redirect would lose the HttpOnly state cookie
    // because the cookie is set on the response to /start and
    // needs to live in the browser's cookie jar when the
    // provider redirects back to /callback.
    window.location.href = `${API_BASE}/api/v1/auth/sso/${provider}/start`;
  }

  return (
    <div
      className="space-y-1.5 xl:space-y-2"
      role="group"
      aria-label="Single sign-on options"
    >
      <SsoButton
        icon={<GoogleIcon className="size-4" />}
        label={t("auth.login.sso_google")}
        onClick={() => handleSso("google")}
      />
      <SsoButton
        icon={<MicrosoftIcon className="size-4" />}
        label={t("auth.login.sso_microsoft")}
        onClick={() => handleSso("microsoft")}
      />
      <SsoButton
        icon={<KeyRound className="size-4 text-zinc-400" strokeWidth={2} />}
        label={t("auth.login.sso_saml")}
        onClick={() => handleSso("saml")}
      />
    </div>
  );
}

function SsoButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="
        group flex h-10 w-full items-center justify-center gap-2.5
        rounded-md border border-white/10 bg-white/[0.025] px-4
        text-[13px] font-medium tracking-tight text-zinc-100
        transition-all xl:h-11 xl:text-[13.5px]
        hover:border-white/15 hover:bg-white/[0.045]
        focus-visible:ring-2 focus-visible:ring-indigo-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0B]
        focus-visible:outline-none
        active:translate-y-px
      "
    >
      {icon}
      {label}
    </button>
  );
}

/* ─── Brand icons (inlined SVG) ──────────────────────────────── */

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" className={className}>
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function MicrosoftIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
      <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}
