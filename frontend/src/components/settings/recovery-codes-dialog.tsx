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

export function RecoveryCodesDialog({
  open,
  codes,
  onClose,
}: {
  open: boolean;
  codes: string[];
  onClose: () => void;
}) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      toast.success("Recovery codes copied.");
    } catch {
      toast.error("Couldn't copy. Select and copy manually.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save your recovery codes</DialogTitle>
          <DialogDescription>
            Store these somewhere safe. Each code works once. They&apos;re your only way back in if
            you lose access to your authenticator app. They will not be shown again.
          </DialogDescription>
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
            <span className="ml-2">Copy all</span>
          </Button>
          <Button onClick={onClose}>I&apos;ve saved them</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
