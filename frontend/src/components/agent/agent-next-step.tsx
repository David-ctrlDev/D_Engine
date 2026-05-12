"use client";

/**
 * "Comenzar con la IA" — the agent-led entry point on the dataset
 * detail page.
 *
 * Replaces the passive "Conversations" panel that lived here before.
 * The agent **takes the initiative**: when the user clicks the CTA
 * we POST a new conversation with ``kickoff=true``, the backend runs
 * the first turn server-side (diagnosis + intent chips), and we
 * navigate to the chat already populated.
 *
 * Friction budget
 * ---------------
 *
 * We pre-load the user's usable credentials in the background so the
 * click handler can branch instantly:
 *
 *   * 0 creds → open a contextual empty-state dialog (admins see
 *     "register one", members see "ask your admin").
 *   * 1 cred  → POST immediately, navigate on success — zero extra clicks.
 *   * 2+ creds → open a slim picker dialog (one select, one button).
 *
 * The dialog is intentionally tiny: we trust the agent to do the
 * heavy lifting once the chat is open. No model field, no initial
 * message, no chrome — pick the connection, go.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, MessageSquare, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ProviderIcon } from "@/components/llm/provider-icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useCurrentUser } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import {
  createConversation,
  listConversations,
  listUsableCredentials,
} from "@/lib/agent-actions";
import { useT } from "@/lib/i18n/provider";

export function AgentNextStep({ datasetId }: { datasetId: string }) {
  const t = useT();
  const router = useRouter();
  const { data: me } = useCurrentUser();
  const isAdmin = me?.tenant.role === "owner" || me?.tenant.role === "admin";

  // Pre-fetch on mount so the click handler can branch without latency.
  const credsQuery = useQuery({
    queryKey: ["llm-credentials-usable"],
    queryFn: listUsableCredentials,
  });
  const conversationsQuery = useQuery({
    queryKey: ["dataset-conversations", datasetId],
    queryFn: () => listConversations(datasetId),
  });

  const credentials = credsQuery.data?.credentials ?? [];
  const conversations = conversationsQuery.data?.conversations ?? [];

  const [dialogState, setDialogState] = useState<"closed" | "empty" | "picker">(
    "closed",
  );
  const [pickedCredentialId, setPickedCredentialId] = useState<string>("");

  const createMut = useMutation({
    mutationFn: (credentialId: string) => {
      const cred = credentials.find((c) => c.id === credentialId);
      if (!cred) throw new Error("credential not found");
      return createConversation(datasetId, {
        credential_id: credentialId,
        model: cred.model_default ?? "",
        kickoff: true,
      });
    },
    onSuccess: (data) => {
      setDialogState("closed");
      router.push(`/conversations/${data.conversation.id}`);
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  function onPrimaryClick() {
    if (credsQuery.isLoading) return; // pre-fetch still in flight
    if (credentials.length === 0) {
      setDialogState("empty");
      return;
    }
    if (credentials.length === 1) {
      // Zero-extra-click path.
      createMut.mutate(credentials[0].id);
      return;
    }
    // 2+ credentials — default to the first one, let the user pick.
    setPickedCredentialId(credentials[0].id);
    setDialogState("picker");
  }

  return (
    <>
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="space-y-4 py-6">
          <div className="flex items-start gap-3">
            <div className="bg-primary/15 flex size-10 shrink-0 items-center justify-center rounded-full">
              <Sparkles className="text-primary size-5" />
            </div>
            <div className="flex-1 space-y-1">
              <h2 className="text-base font-semibold">{t("agent.next.title")}</h2>
              <p className="text-muted-foreground text-sm">{t("agent.next.body")}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={onPrimaryClick}
              disabled={credsQuery.isLoading || createMut.isPending}
            >
              {createMut.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  {t("agent.next.starting")}
                </>
              ) : (
                <>
                  <Sparkles className="size-4" />
                  {t("agent.next.cta")}
                </>
              )}
            </Button>
          </div>

          {/* Previous conversations — small, secondary, only when there are any. */}
          {conversations.length > 0 && (
            <div className="space-y-2 border-t pt-3">
              <p className="text-muted-foreground text-xs uppercase tracking-wide">
                {t("agent.next.previous")}
              </p>
              <ul className="space-y-1">
                {conversations.slice(0, 5).map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`/conversations/${c.id}`}
                      className="hover:bg-muted/60 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors"
                    >
                      <MessageSquare className="text-muted-foreground size-3.5" />
                      <span className="flex-1 truncate">
                        {c.title ?? t("agent.list.untitled")}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {new Date(c.updated_at).toLocaleDateString()}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Empty state: no usable credentials. */}
      <Dialog
        open={dialogState === "empty"}
        onOpenChange={(o) => !o && setDialogState("closed")}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("agent.no_creds.title")}</DialogTitle>
            <DialogDescription>
              {isAdmin ? t("agent.no_creds.admin") : t("agent.no_creds.member")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogState("closed")}>
              {t("common.cancel")}
            </Button>
            {isAdmin && (
              <Button
                onClick={() => setDialogState("closed")}
                render={<Link href="/settings/ai" />}
              >
                {t("agent.no_creds.cta")}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Credential picker — only used when 2+ creds are available. */}
      <Dialog
        open={dialogState === "picker"}
        onOpenChange={(o) => !o && setDialogState("closed")}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("agent.picker.title")}</DialogTitle>
            <DialogDescription>{t("agent.picker.subtitle")}</DialogDescription>
          </DialogHeader>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (pickedCredentialId) createMut.mutate(pickedCredentialId);
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="picker_cred">{t("agent.picker.label")}</Label>
              <select
                id="picker_cred"
                value={pickedCredentialId}
                onChange={(e) => setPickedCredentialId(e.target.value)}
                disabled={createMut.isPending}
                className="border-input bg-background focus:border-ring focus:ring-ring/50 h-9 w-full rounded-md border px-2 text-sm transition-colors focus:ring-3 focus:outline-none"
                required
              >
                {credentials.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nickname} ({c.provider})
                  </option>
                ))}
              </select>
              {(() => {
                const picked = credentials.find((c) => c.id === pickedCredentialId);
                if (!picked) return null;
                return (
                  <div className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                    <ProviderIcon provider={picked.provider} size="sm" />
                    <span>{picked.nickname}</span>
                  </div>
                );
              })()}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogState("closed")}
                disabled={createMut.isPending}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={createMut.isPending || !pickedCredentialId}>
                {createMut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    {t("agent.next.starting")}
                  </>
                ) : (
                  t("agent.picker.submit")
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
