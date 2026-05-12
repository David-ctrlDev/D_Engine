"use client";

/**
 * "Start a conversation" dialog.
 *
 * Fetches the usable credentials for the current user (RLS-filtered on
 * the backend), shows them in a picker, and on submit POSTs the new
 * conversation. If an opening message was provided, the backend runs
 * the first round-trip inline so the chat lands on /conversations/{id}
 * with one user + one assistant message already on screen.
 *
 * Edge cases worth noting in the UI:
 *
 *   * No credentials at all → swap the form for a contextual empty
 *     state. Admins see "register one"; members see "ask your admin".
 *   * Credential's model_default is used as the model unless the
 *     user picks something else (a future picker lands when we know
 *     the model lists for each saved credential).
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ProviderIcon } from "@/components/llm/provider-icon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCurrentUser } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { createConversation, listUsableCredentials } from "@/lib/agent-actions";
import { useT } from "@/lib/i18n/provider";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datasetId: string;
}

export function StartConversationDialog({ open, onOpenChange, datasetId }: Props) {
  const t = useT();
  const router = useRouter();
  const { data: me } = useCurrentUser();
  const isAdmin = me?.tenant.role === "owner" || me?.tenant.role === "admin";

  const credsQuery = useQuery({
    queryKey: ["llm-credentials-usable"],
    queryFn: listUsableCredentials,
    enabled: open,
  });

  const [credentialId, setCredentialId] = useState<string>("");
  const [model, setModel] = useState<string>("");
  const [initialMessage, setInitialMessage] = useState("");

  const credentials = credsQuery.data?.credentials ?? [];
  const selectedCred = credentials.find((c) => c.id === credentialId);

  function onCredentialChange(id: string) {
    setCredentialId(id);
    const c = credentials.find((cc) => cc.id === id);
    // Default the model to the credential's configured default;
    // user can override before submitting.
    setModel(c?.model_default ?? "");
  }

  const createMut = useMutation({
    mutationFn: () => {
      if (!credentialId) throw new Error("no credential");
      return createConversation(datasetId, {
        credential_id: credentialId,
        model: model || selectedCred?.model_default || "",
        initial_message: initialMessage.trim() || null,
      });
    },
    onSuccess: (data) => {
      onOpenChange(false);
      router.push(`/conversations/${data.conversation.id}`);
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4" />
            {t("agent.start.title")}
          </DialogTitle>
          <DialogDescription>{t("agent.start.subtitle")}</DialogDescription>
        </DialogHeader>

        {credsQuery.isLoading ? (
          <div className="text-muted-foreground flex justify-center py-10">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : credentials.length === 0 ? (
          <div className="space-y-3 py-4 text-center">
            <h3 className="text-sm font-semibold">{t("agent.start.no_credentials.title")}</h3>
            <p className="text-muted-foreground mx-auto max-w-sm text-sm">
              {isAdmin
                ? t("agent.start.no_credentials.admin")
                : t("agent.start.no_credentials.member")}
            </p>
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
                render={<Link href="/settings/ai" />}
              >
                {t("agent.start.no_credentials.cta")}
              </Button>
            )}
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!credentialId) return;
              createMut.mutate();
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="cred">{t("agent.start.credential_label")}</Label>
              <select
                id="cred"
                value={credentialId}
                onChange={(e) => onCredentialChange(e.target.value)}
                disabled={createMut.isPending}
                className="border-input bg-background focus:border-ring focus:ring-ring/50 h-9 w-full rounded-md border px-2 text-sm transition-colors focus:ring-3 focus:outline-none"
                required
              >
                <option value="" disabled>
                  {t("agent.start.credential_placeholder")}
                </option>
                {credentials.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nickname} ({c.provider})
                  </option>
                ))}
              </select>
              {selectedCred && (
                <div className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                  <ProviderIcon provider={selectedCred.provider} size="sm" />
                  <span>{selectedCred.nickname}</span>
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="model">{t("agent.start.model_label")}</Label>
              <Input
                id="model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={selectedCred?.model_default ?? ""}
                disabled={createMut.isPending}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="initial">{t("agent.start.initial_message_label")}</Label>
              <textarea
                id="initial"
                value={initialMessage}
                onChange={(e) => setInitialMessage(e.target.value)}
                placeholder={t("agent.start.initial_message_placeholder")}
                rows={3}
                disabled={createMut.isPending}
                className="border-input bg-background focus:border-ring focus:ring-ring/50 w-full resize-none rounded-md border px-2 py-1.5 text-sm transition-colors focus:ring-3 focus:outline-none"
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={createMut.isPending}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={createMut.isPending || !credentialId}>
                {createMut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    {t("agent.start.submitting")}
                  </>
                ) : (
                  t("agent.start.submit")
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
