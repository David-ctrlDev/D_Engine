"use client";

/**
 * Sharing controls — visibility selector + per-user grants. Slice F.
 *
 * The visibility selector shows all three modes; the grants list +
 * "add person" picker is only relevant when ``shared_specific`` is
 * selected. The owner row is implicit (creator always has access)
 * so we don't list them.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import {
  addGrant,
  listGrants,
  listWorkspaceMembers,
  removeGrant,
  updateVisibility,
} from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { DatasetVisibility } from "@/types/data";

export function ShareSection({
  datasetId,
  currentUserId,
  initialVisibility,
}: {
  datasetId: string;
  currentUserId: string;
  initialVisibility: DatasetVisibility;
}) {
  const t = useT();
  const qc = useQueryClient();
  const [visibility, setVisibility] = useState<DatasetVisibility>(initialVisibility);

  const grantsQuery = useQuery({
    queryKey: ["dataset-grants", datasetId],
    queryFn: () => listGrants(datasetId),
  });

  const membersQuery = useQuery({
    queryKey: ["workspace-members"],
    queryFn: listWorkspaceMembers,
  });

  const visibilityMut = useMutation({
    mutationFn: (next: DatasetVisibility) => updateVisibility(datasetId, next),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dataset", datasetId] });
      qc.invalidateQueries({ queryKey: ["datasets"] });
      toast.success(t("share.updated"));
    },
    onError: (e, prev) => {
      setVisibility(prev as DatasetVisibility);
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const addMut = useMutation({
    mutationFn: (userId: string) => addGrant(datasetId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dataset-grants", datasetId] });
      toast.success(t("share.granted"));
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const removeMut = useMutation({
    mutationFn: (userId: string) => removeGrant(datasetId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dataset-grants", datasetId] });
      toast.success(t("share.revoked"));
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  function changeVisibility(next: DatasetVisibility) {
    const prev = visibility;
    setVisibility(next);
    visibilityMut.mutate(next, { onError: () => setVisibility(prev) });
  }

  const grants = grantsQuery.data?.grants ?? [];
  const grantedUserIds = new Set(grants.map((g) => g.user_id));
  const availableMembers =
    membersQuery.data?.members.filter(
      (m) => m.user_id !== currentUserId && !grantedUserIds.has(m.user_id),
    ) ?? [];

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="size-4" />
          {t("share.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <p className="text-muted-foreground text-xs">{t("share.visibility_label")}</p>
          <div className="flex flex-wrap gap-2">
            {(["private", "shared_workspace", "shared_specific"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => changeVisibility(v)}
                disabled={visibilityMut.isPending}
                className={cn(
                  "border-input rounded-md border px-3 py-1.5 text-sm transition-colors",
                  visibility === v
                    ? "border-primary bg-primary/5 text-foreground"
                    : "text-muted-foreground hover:bg-muted",
                  visibilityMut.isPending && "opacity-60",
                )}
              >
                {t(`share.visibility.${v}`)}
              </button>
            ))}
          </div>
        </div>

        {visibility === "shared_specific" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <select
                className="border-input bg-background h-8 flex-1 rounded-md border px-2 text-sm"
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
                  {t("share.add_user_placeholder")}
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
              <p className="text-muted-foreground text-xs">{t("share.no_grants")}</p>
            ) : (
              <ul className="divide-border divide-y rounded-md border">
                {grants.map((g) => (
                  <li
                    key={g.id}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <span>{g.user_email}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => removeMut.mutate(g.user_id)}
                      disabled={removeMut.isPending}
                    >
                      <Trash2 className="size-3.5" />
                      {t("share.remove")}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
