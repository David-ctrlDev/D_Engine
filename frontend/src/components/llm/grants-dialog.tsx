"use client";

/**
 * "Manage access" dialog for a credential whose member-access is
 * ``specific_members``. Lists current grantees + an "add member"
 * picker for everyone else in the workspace.
 *
 * Re-uses the existing ``listWorkspaceMembers`` endpoint from the data
 * domain — the workspace member roster is shared across features, no
 * point in a parallel endpoint.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
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
import { ApiError } from "@/lib/api";
import { listWorkspaceMembers } from "@/lib/data-actions";
import {
  addCredentialGrant,
  listCredentialGrants,
  removeCredentialGrant,
} from "@/lib/llm-actions";
import { useT } from "@/lib/i18n/provider";
import type { LlmCredentialPublic } from "@/types/llm";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  credential: LlmCredentialPublic | null;
}

export function GrantsDialog({ open, onOpenChange, credential }: Props) {
  const t = useT();
  const qc = useQueryClient();
  const credentialId = credential?.id ?? null;

  const grantsQuery = useQuery({
    queryKey: ["llm-credential-grants", credentialId],
    queryFn: () => (credentialId ? listCredentialGrants(credentialId) : Promise.resolve(null)),
    enabled: open && credentialId !== null,
  });

  const membersQuery = useQuery({
    queryKey: ["workspace-members"],
    queryFn: listWorkspaceMembers,
    enabled: open,
  });

  const addMut = useMutation({
    mutationFn: (userId: string) => addCredentialGrant(credentialId!, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-credential-grants", credentialId] });
      toast.success(t("settings.ai.grants.granted"));
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const removeMut = useMutation({
    mutationFn: (userId: string) => removeCredentialGrant(credentialId!, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-credential-grants", credentialId] });
      toast.success(t("settings.ai.grants.revoked"));
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const grants = grantsQuery.data?.grants ?? [];
  const grantedIds = new Set(grants.map((g) => g.user_id));
  const availableMembers =
    membersQuery.data?.members.filter(
      // Hide admins (they always have access) and people who already have a grant.
      (m) => m.role === "member" && !grantedIds.has(m.user_id),
    ) ?? [];

  if (!credential) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("settings.ai.grants.title")}</DialogTitle>
          <DialogDescription>{t("settings.ai.grants.subtitle")}</DialogDescription>
        </DialogHeader>

        {grantsQuery.isLoading || membersQuery.isLoading ? (
          <div className="text-muted-foreground flex justify-center py-10">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : grantsQuery.error ? (
          <div className="text-destructive py-6 text-center text-sm">
            {t("settings.ai.grants.load_failed")}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <select
                className="border-input bg-background h-9 flex-1 rounded-md border px-2 text-sm"
                defaultValue=""
                disabled={addMut.isPending || availableMembers.length === 0}
                onChange={(e) => {
                  if (e.target.value) {
                    addMut.mutate(e.target.value);
                    e.target.value = "";
                  }
                }}
              >
                <option value="" disabled>
                  {availableMembers.length === 0
                    ? t("settings.ai.grants.no_more_members")
                    : t("settings.ai.grants.add_placeholder")}
                </option>
                {availableMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.email}
                  </option>
                ))}
              </select>
              {addMut.isPending && <Loader2 className="size-4 animate-spin" />}
            </div>

            {grants.length === 0 ? (
              <p className="text-muted-foreground py-4 text-center text-sm">
                {t("settings.ai.grants.empty")}
              </p>
            ) : (
              <ul className="divide-border divide-y rounded-md border">
                {grants.map((g) => (
                  <li
                    key={g.id}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <span>{g.user_email}</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => removeMut.mutate(g.user_id)}
                      disabled={removeMut.isPending}
                    >
                      <Trash2 className="size-3.5" />
                      {t("settings.ai.grants.remove")}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
