"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import { buildMFADisableSchema, type MFADisableFormValues } from "@/lib/auth-schemas";
import { useT } from "@/lib/i18n/provider";

export function DisableMFADialog({ onDisabled }: { onDisabled: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(() => buildMFADisableSchema(t), [t]);
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<MFADisableFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", code: "" },
  });

  async function onSubmit(values: MFADisableFormValues) {
    setSubmitting(true);
    setServerError(null);
    try {
      await authApi.mfaDisable(values);
      reset();
      setOpen(false);
      toast.success(t("settings.mfa.disable.toast_success"));
      onDisabled();
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : t("settings.mfa.disable.toast_failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant="destructive">{t("settings.mfa.disable.trigger")}</Button>}
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("settings.mfa.disable.title")}</DialogTitle>
          <DialogDescription>{t("settings.mfa.disable.description")}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="disable-password">{t("common.password")}</Label>
            <Input
              id="disable-password"
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-destructive text-sm">{errors.password.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="disable-code">{t("settings.mfa.scan.code_label")}</Label>
            <Input
              id="disable-code"
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

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {t("settings.mfa.scan.cancel")}
            </Button>
            <Button type="submit" variant="destructive" disabled={submitting}>
              {submitting ? t("settings.mfa.disable.submitting") : t("settings.mfa.disable.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
