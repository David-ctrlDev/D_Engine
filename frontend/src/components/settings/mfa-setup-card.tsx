"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CURRENT_USER_QUERY_KEY } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildMFASetupConfirmSchema, type MFASetupConfirmFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

type SetupState = { secret: string; qrDataUri: string } | null;

export function MFASetupCard({ onConfirmed }: { onConfirmed: (recoveryCodes: string[]) => void }) {
  const t = useT();
  const queryClient = useQueryClient();
  const [setup, setSetup] = useState<SetupState>(null);
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(() => buildMFASetupConfirmSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<MFASetupConfirmFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: "" },
  });

  async function startSetup() {
    setStarting(true);
    setServerError(null);
    try {
      const result = await authApi.mfaSetup();
      setSetup({ secret: result.secret, qrDataUri: result.qr_data_uri });
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : t("settings.mfa.failed_start"));
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
      queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
      toast.success(t("settings.mfa.toast_enabled"));
      onConfirmed(result.recovery_codes);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : t("settings.mfa.failed_confirm"));
    } finally {
      setConfirming(false);
    }
  }

  if (!setup) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.mfa.disabled.title")}</CardTitle>
          <CardDescription>{t("settings.mfa.disabled.description")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {serverError && <p className="text-destructive text-sm">{serverError}</p>}
          <Button onClick={startSetup} disabled={starting}>
            {starting ? t("settings.mfa.disabled.starting") : t("settings.mfa.disabled.start")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.mfa.scan.title")}</CardTitle>
        <CardDescription>{t("settings.mfa.scan.description")}</CardDescription>
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
            {t("settings.mfa.scan.manual_prefix")} <code className="font-mono">{setup.secret}</code>
          </p>
        </div>

        <form onSubmit={handleSubmit(onConfirm)} className="space-y-3" noValidate>
          <div className="space-y-2">
            <Label htmlFor="mfa-confirm-code">{t("settings.mfa.scan.code_label")}</Label>
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
              {confirming ? t("settings.mfa.scan.confirming") : t("settings.mfa.scan.confirm")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                reset();
                setSetup(null);
              }}
            >
              {t("settings.mfa.scan.cancel")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
