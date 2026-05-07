"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
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
import { mfaDisableSchema, type MFADisableFormValues } from "@/lib/auth-schemas";

export function DisableMFADialog({ onDisabled }: { onDisabled: () => void }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<MFADisableFormValues>({
    resolver: zodResolver(mfaDisableSchema),
    defaultValues: { password: "", code: "" },
  });

  async function onSubmit(values: MFADisableFormValues) {
    setSubmitting(true);
    setServerError(null);
    try {
      await authApi.mfaDisable(values);
      reset();
      setOpen(false);
      toast.success("Multi-factor authentication disabled.");
      onDisabled();
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Failed to disable MFA.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* Base UI's DialogTrigger doesn't accept asChild; use ``render``
          to compose the destructive Button as the trigger element. */}
      <DialogTrigger render={<Button variant="destructive">Disable MFA</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Disable multi-factor authentication</DialogTitle>
          <DialogDescription>
            Confirm your password and a current authenticator code. After disabling, any leftover
            recovery codes are also invalidated.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="disable-password">Password</Label>
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
            <Label htmlFor="disable-code">Authentication code</Label>
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
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={submitting}>
              {submitting ? "Disabling…" : "Disable MFA"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
