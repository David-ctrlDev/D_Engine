"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { useT } from "@/lib/i18n/provider";

type State =
  | { kind: "idle" }
  | { kind: "verifying" }
  | { kind: "ok" }
  | { kind: "error"; message: string };

export function VerifyEmailFlow() {
  const t = useT();
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<State>({ kind: token ? "verifying" : "idle" });

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        await authApi.verifyEmail({ token });
        if (!cancelled) setState({ kind: "ok" });
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : t("auth.verify.failed");
        if (!cancelled) setState({ kind: "error", message: msg });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, t]);

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        {state.kind === "idle"
          ? t("auth.verify.idle")
          : state.kind === "verifying"
            ? t("auth.verify.verifying")
            : state.kind === "ok"
              ? t("auth.verify.ok")
              : t("auth.verify.error")}
      </p>
      {state.kind === "error" && <p className="text-destructive text-sm">{state.message}</p>}
      {state.kind === "ok" ? (
        <Link href="/login">
          <Button>{t("auth.verify.continue")}</Button>
        </Link>
      ) : (
        <p className="text-muted-foreground text-sm">
          <Link href="/login" className="underline">
            {t("auth.verify.back")}
          </Link>
        </p>
      )}
    </div>
  );
}
