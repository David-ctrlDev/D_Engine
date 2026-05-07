"use client";

import { Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useT } from "@/lib/i18n/provider";

export function RecoveryCodesDialog({
  open,
  codes,
  onClose,
}: {
  open: boolean;
  codes: string[];
  onClose: () => void;
}) {
  const t = useT();

  async function copy() {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      toast.success(t("settings.recovery.copied"));
    } catch {
      toast.error(t("settings.recovery.copy_failed"));
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("settings.recovery.title")}</DialogTitle>
          <DialogDescription>{t("settings.recovery.description")}</DialogDescription>
        </DialogHeader>

        <ul className="bg-muted/30 grid grid-cols-2 gap-2 rounded-md border p-3 font-mono text-sm">
          {codes.map((code) => (
            <li key={code} className="px-2 py-1 tracking-wider">
              {code}
            </li>
          ))}
        </ul>

        <DialogFooter>
          <Button variant="outline" onClick={copy}>
            <Copy className="size-4" />
            <span className="ml-2">{t("common.copy_all")}</span>
          </Button>
          <Button onClick={onClose}>{t("settings.recovery.confirm")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
