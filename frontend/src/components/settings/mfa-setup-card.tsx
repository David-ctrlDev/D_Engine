"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { mfaSetupConfirmSchema, type MFASetupConfirmFormValues } from "@/lib/auth-schemas";

type SetupState = { secret: string; qrDataUri: string } | null;

export function MFASetupCard({ onConfirmed }: { onConfirmed: (recoveryCodes: string[]) => void }) {
  const queryClient = useQueryClient();
  const [setup, setSetup] = useState<SetupState>(null);
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<MFASetupConfirmFormValues>({
    resolver: zodResolver(mfaSetupConfirmSchema),
    defaultValues: { code: "" },
  });

  async function startSetup() {
    setStarting(true);
    setServerError(null);
    try {
      const result = await authApi.mfaSetup();
      setSetup({ secret: result.secret, qrDataUri: result.qr_data_uri });
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Failed to start MFA setup.");
    } finally {
      setStarting(false);
    }
  }

  async function onConfirm(values: MFASetupConfirmFormValues) {
    setConfirming(true);
    setServerError(null);
    try {
      const result = await authApi.mfaSetupConfirm({ code: values.code });
      reset();
      setSetup(null);
      // Refresh /me — although /me's payload doesn't currently expose mfa
      // state, future iterations may add it. Cheap insurance.
      queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
      toast.success("Multi-factor authentication enabled.");
      onConfirmed(result.recovery_codes);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Failed to confirm code.");
    } finally {
      setConfirming(false);
    }
  }

  if (!setup) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Multi-factor authentication</CardTitle>
          <CardDescription>
            Add a second factor — a code from an authenticator app — required at every sign-in.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {serverError && <p className="text-destructive text-sm">{serverError}</p>}
          <Button onClick={startSetup} disabled={starting}>
            {starting ? "Starting…" : "Set up MFA"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scan this QR code</CardTitle>
        <CardDescription>
          Open Google Authenticator, Authy, or 1Password and scan. Then enter the 6-digit code
          below.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="bg-muted/30 flex flex-col items-center gap-3 rounded-md border p-4">
          <Image
            src={setup.qrDataUri}
            alt="MFA QR code"
            width={200}
            height={200}
            className="rounded bg-white p-2"
            unoptimized
          />
          <p className="text-muted-foreground break-all text-center text-xs">
            Or enter manually: <code className="font-mono">{setup.secret}</code>
          </p>
        </div>

        <form onSubmit={handleSubmit(onConfirm)} className="space-y-3" noValidate>
          <div className="space-y-2">
            <Label htmlFor="mfa-confirm-code">Authentication code</Label>
            <Input
              id="mfa-confirm-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              aria-invalid={!!errors.code}
              {...register("code")}
            />
            {errors.code && <p className="text-destructive text-sm">{errors.code.message}</p>}
          </div>

          {serverError && (
            <p className="border-destructive/40 text-destructive bg-destructive/5 rounded-md border p-3 text-sm">
              {serverError}
            </p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={confirming}>
              {confirming ? "Confirming…" : "Confirm"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                reset();
                setSetup(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
