"use client";

/**
 * /settings/ai — workspace-admin page for BYOK provider credentials.
 *
 * The list shows every credential in the tenant (RLS already filters
 * cross-tenant, plus admins see everything in their own tenant). Each
 * row exposes Edit, Test, Manage access (when ``specific_members``),
 * and Delete. The "+ New connection" button opens the create modal.
 *
 * Non-admins reaching this URL directly get a friendly empty-state
 * card explaining what the page is for — the API would 403 them
 * anyway, but a sensible UI is better than a raw toast.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Users,
  XCircle,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EditCredentialDialog } from "@/components/llm/edit-credential-dialog";
import { GrantsDialog } from "@/components/llm/grants-dialog";
import { NewCredentialDialog } from "@/components/llm/new-credential-dialog";
import { ProviderIcon } from "@/components/llm/provider-icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCurrentUser } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import {
  deleteCredential,
  listCredentials,
  listProviders,
  testSavedCredential,
} from "@/lib/llm-actions";
import { useT } from "@/lib/i18n/provider";
import type { LlmCredentialPublic } from "@/types/llm";

export default function AiConnectionsPage() {
  const t = useT();
  const qc = useQueryClient();
  const { data: me } = useCurrentUser();
  const isAdmin = me?.tenant.role === "owner" || me?.tenant.role === "admin";

  const credsQuery = useQuery({
    queryKey: ["llm-credentials"],
    queryFn: listCredentials,
    enabled: isAdmin,
  });
  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: listProviders,
    staleTime: Infinity,
    enabled: isAdmin,
  });

  const [newOpen, setNewOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<LlmCredentialPublic | null>(null);
  const [grantsTarget, setGrantsTarget] = useState<LlmCredentialPublic | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteCredential(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-credentials"] });
      toast.success(t("settings.ai.row.toast_deleted"));
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const testMut = useMutation({
    mutationFn: (id: string) => testSavedCredential(id),
    onMutate: (id) => setTestingId(id),
    onSettled: () => setTestingId(null),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["llm-credentials"] });
      if (data.ok) {
        toast.success(t("settings.ai.row.test_ok"));
      } else {
        toast.error(t("settings.ai.row.test_failed", { error: data.error ?? "" }));
      }
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  // ----- Render guard: non-admins ---------------------------------------
  if (me && !isAdmin) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Header t={t} />
        <Card>
          <CardContent className="space-y-2 py-10 text-center">
            <h2 className="text-base font-semibold">{t("settings.ai.not_admin.title")}</h2>
            <p className="text-muted-foreground mx-auto max-w-md text-sm">
              {t("settings.ai.not_admin.body")}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const creds = credsQuery.data?.credentials ?? [];
  const providerByKind = new Map(
    (providersQuery.data?.providers ?? []).map((p) => [p.kind, p]),
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-end justify-between gap-4">
        <Header t={t} />
        {creds.length > 0 && (
          <Button onClick={() => setNewOpen(true)}>
            <Plus className="size-4" /> {t("settings.ai.list.new")}
          </Button>
        )}
      </div>

      <p className="bg-muted/40 text-muted-foreground rounded-md border px-3 py-2 text-xs">
        {t("settings.ai.who_can_register")}
      </p>

      {credsQuery.isLoading ? (
        <div className="text-muted-foreground flex justify-center py-16">
          <Loader2 className="size-5 animate-spin" />
        </div>
      ) : credsQuery.error ? (
        <Card>
          <CardContent className="text-destructive py-12 text-center text-sm">
            {t("settings.ai.list.load_failed")}
          </CardContent>
        </Card>
      ) : creds.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="bg-muted flex size-12 items-center justify-center rounded-full">
              <Sparkles className="text-muted-foreground size-6" />
            </div>
            <div className="max-w-sm space-y-1">
              <h2 className="text-base font-semibold">{t("settings.ai.list.empty.title")}</h2>
              <p className="text-muted-foreground text-sm">{t("settings.ai.list.empty.body")}</p>
            </div>
            <Button onClick={() => setNewOpen(true)}>
              <Plus className="size-4" /> {t("settings.ai.list.empty.cta")}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-muted-foreground bg-muted/40 text-left text-xs uppercase tracking-wide">
                  <tr>
                    <th className="px-4 py-3 font-medium">{t("settings.ai.list.col.nickname")}</th>
                    <th className="px-4 py-3 font-medium">{t("settings.ai.list.col.provider")}</th>
                    <th className="px-4 py-3 font-medium">{t("settings.ai.list.col.model")}</th>
                    <th className="px-4 py-3 font-medium">{t("settings.ai.list.col.access")}</th>
                    <th className="px-4 py-3 font-medium">
                      {t("settings.ai.list.col.last_test")}
                    </th>
                    <th className="px-4 py-3" aria-label={t("settings.ai.list.col.actions")} />
                  </tr>
                </thead>
                <tbody className="divide-border divide-y">
                  {creds.map((c) => {
                    const provider = providerByKind.get(c.provider);
                    const isTestingThis = testingId === c.id;
                    return (
                      <tr key={c.id} className="hover:bg-muted/20">
                        <td className="px-4 py-3 font-medium">{c.nickname}</td>
                        <td className="px-4 py-3">
                          <span className="flex items-center gap-2">
                            <ProviderIcon provider={c.provider} size="sm" />
                            <span className="text-muted-foreground">
                              {provider?.display_name ?? c.provider}
                            </span>
                          </span>
                        </td>
                        <td className="text-muted-foreground px-4 py-3 text-xs">
                          {c.model_default ?? "—"}
                        </td>
                        <td className="text-muted-foreground px-4 py-3 text-xs">
                          {t(`settings.ai.access.${c.member_access}`)}
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <TestStatus
                            credential={c}
                            testingNow={isTestingThis}
                            t={t}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              aria-label={t("settings.ai.row.test")}
                              title={t("settings.ai.row.test")}
                              disabled={isTestingThis || testMut.isPending}
                              onClick={() => testMut.mutate(c.id)}
                            >
                              {isTestingThis ? (
                                <Loader2 className="size-3.5 animate-spin" />
                              ) : (
                                <Zap className="size-3.5" />
                              )}
                            </Button>
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              aria-label={t("settings.ai.row.edit")}
                              title={t("settings.ai.row.edit")}
                              onClick={() => setEditTarget(c)}
                            >
                              <Pencil className="size-3.5" />
                            </Button>
                            {c.member_access === "specific_members" && (
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                aria-label={t("settings.ai.row.share")}
                                title={t("settings.ai.row.share")}
                                onClick={() => setGrantsTarget(c)}
                              >
                                <Users className="size-3.5" />
                              </Button>
                            )}
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              aria-label={t("settings.ai.row.delete")}
                              title={t("settings.ai.row.delete")}
                              disabled={deleteMut.isPending}
                              onClick={() => {
                                if (window.confirm(t("settings.ai.row.confirm_delete"))) {
                                  deleteMut.mutate(c.id);
                                }
                              }}
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <NewCredentialDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        onCreated={(cred) => {
          // If the admin chose specific_members, jump straight into the
          // grants dialog so they can assign people without a second
          // round-trip through the row actions.
          if (cred.member_access === "specific_members") {
            setGrantsTarget(cred);
          }
        }}
      />
      <EditCredentialDialog
        // Re-mount on credential change so the form's internal state
        // resets cleanly without us having to plumb props.
        key={editTarget?.id ?? "edit-empty"}
        open={editTarget !== null}
        onOpenChange={(o) => {
          if (!o) setEditTarget(null);
        }}
        credential={editTarget}
      />
      <GrantsDialog
        key={grantsTarget?.id ?? "grants-empty"}
        open={grantsTarget !== null}
        onOpenChange={(o) => {
          if (!o) setGrantsTarget(null);
        }}
        credential={grantsTarget}
      />
    </div>
  );
}

function Header({ t }: { t: ReturnType<typeof useT> }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{t("settings.ai.title")}</h1>
      <p className="text-muted-foreground text-sm">{t("settings.ai.subtitle")}</p>
    </div>
  );
}

function TestStatus({
  credential,
  testingNow,
  t,
}: {
  credential: LlmCredentialPublic;
  testingNow: boolean;
  t: ReturnType<typeof useT>;
}) {
  if (testingNow) {
    return (
      <span className="text-muted-foreground flex items-center gap-1">
        <Loader2 className="size-3.5 animate-spin" />
        {t("settings.ai.row.testing")}
      </span>
    );
  }
  if (!credential.last_tested_at) {
    return <span className="text-muted-foreground">{t("settings.ai.list.never_tested")}</span>;
  }
  const when = new Date(credential.last_tested_at).toLocaleString();
  if (credential.last_test_status === "ok") {
    return (
      <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
        <CheckCircle2 className="size-3.5" />
        <span className="text-muted-foreground">{when}</span>
      </span>
    );
  }
  return (
    <span className="text-destructive flex items-center gap-1">
      <XCircle className="size-3.5" />
      <span className="text-muted-foreground">{when}</span>
    </span>
  );
}
