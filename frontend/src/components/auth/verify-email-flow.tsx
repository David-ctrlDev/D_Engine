"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";

type State =
  | { kind: "idle" }
  | { kind: "verifying" }
  | { kind: "ok" }
  | { kind: "error"; message: string };

export function VerifyEmailFlow() {
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
        const msg = e instanceof ApiError ? e.message : "Verification failed.";
        if (!cancelled) setState({ kind: "error", message: msg });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        {state.kind === "idle"
          ? "We just sent you a link. In dev, the link is printed in the backend terminal — click it (or paste it) to verify."
          : state.kind === "verifying"
            ? "Verifying your email…"
            : state.kind === "ok"
              ? "Your email is verified."
              : "We could not verify this link."}
      </p>
      {state.kind === "error" && <p className="text-destructive text-sm">{state.message}</p>}
      {state.kind === "ok" ? (
        <Link href="/login">
          <Button>Continue to sign in</Button>
        </Link>
      ) : (
        <p className="text-muted-foreground text-sm">
          <Link href="/login" className="underline">
            Back to sign in
          </Link>
        </p>
      )}
    </div>
  );
}
