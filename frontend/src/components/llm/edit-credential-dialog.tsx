"use client";

/**
 * Edit-credential modal — patch-style. The user can rename, rotate the
 * key, change the default model, change member-access. The provider is
 * intentionally immutable: an OpenAI key won't work against Anthropic,
 * so swapping vendors means making a new credential.
 *
 * The API-key field stays empty by default — if the admin doesn't type
 * a new one, the existing key is preserved. Pasting a value rotates it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
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
import { ApiError } from "@/lib/api";
import { listProviders, updateCredential } from "@/lib/llm-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { LlmCredentialPublic, LlmCredentialUpdateRequest, LlmMemberAccess } from "@/types/llm";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  credential: LlmCredentialPublic | null;
}

export function EditCredentialDialog({ open, onOpenChange, credential }: Props) {
  const t = useT();
  const qc = useQueryClient();

  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: listProviders,
    staleTime: Infinity,
  });

  const [nickname, setNickname] = useState(credential?.nickname ?? "");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(credential?.model_default ?? "");
  const [baseUrl, setBaseUrl] = useState(credential?.base_url ?? "");
  const [access, setAccess] = useState<LlmMemberAccess>(
    credential?.member_access ?? "admins_only",
  );

  // Reset form whenever the dialog re-opens for a different credential.
  // We key the dialog by credential.id at the call-site instead, but this
  // is the defensive belt-and-braces version.
  function syncFromCredential() {
    if (credential) {
      setNickname(credential.nickname);
      setApiKey("");
      setModel(credential.model_default ?? "");
      setBaseUrl(credential.base_url ?? "");
      setAccess(credential.member_access);
    }
  }

  const provider = credential
    ? providersQuery.data?.providers.find((p) => p.kind === credential.provider)
    : undefined;

  const updateMut = useMutation({
    mutationFn: () => {
      if (!credential) throw new Error("no credential");
      const payload: LlmCredentialUpdateRequest = {};
      if (nickname.trim() && nickname.trim() !== credential.nickname) {
        payload.nickname = nickname.trim();
      }
      if (apiKey) payload.api_key = apiKey;
      if (model !== (credential.model_default ?? "")) {
        payload.model_default = model || null;
      }
      if (provider?.needs_base_url && baseUrl.trim() !== (credential.base_url ?? "")) {
        payload.base_url = baseUrl.trim() || null;
      }
      if (access !== credential.member_access) payload.member_access = access;
      return updateCredential(credential.id, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-credentials"] });
      toast.success(t("settings.ai.edit.toast_success"));
      onOpenChange(false);
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  if (!credential) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (o) syncFromCredential();
        onOpenChange(o);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("settings.ai.edit.title")}</DialogTitle>
          <DialogDescription>{t("settings.ai.edit.subtitle")}</DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            updateMut.mutate();
          }}
        >
          <div className="bg-muted/30 flex items-center gap-3 rounded-md border px-3 py-2">
            <ProviderIcon provider={credential.provider} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{provider?.display_name ?? credential.provider}</div>
              <div className="text-muted-foreground truncate text-xs">{provider?.description}</div>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit_nickname">{t("settings.ai.field.nickname")}</Label>
            <Input
              id="edit_nickname"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              maxLength={120}
              disabled={updateMut.isPending}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit_api_key">{t("settings.ai.field.api_key")}</Label>
            <Input
              id="edit_api_key"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("settings.ai.field.api_key_rotate_placeholder")}
              disabled={updateMut.isPending}
            />
          </div>

          {provider?.needs_base_url && (
            <div className="space-y-1.5">
              <Label htmlFor="edit_base_url">{t("settings.ai.field.base_url")}</Label>
              <Input
                id="edit_base_url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={t("settings.ai.field.base_url_placeholder")}
                disabled={updateMut.isPending}
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="edit_model">{t("settings.ai.field.model")}</Label>
            <select
              id="edit_model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={updateMut.isPending}
              className="border-input bg-background focus:border-ring focus:ring-ring/50 h-9 w-full rounded-md border px-2 text-sm transition-colors focus:ring-3 focus:outline-none"
            >
              {provider?.models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                  {m.notes ? ` — ${m.notes}` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>{t("settings.ai.field.access")}</Label>
            <div className="space-y-1.5">
              {(["admins_only", "all_members", "specific_members"] as const).map((v) => (
                <label
                  key={v}
                  className={cn(
                    "border-input hover:bg-muted/50 flex cursor-pointer items-start gap-2 rounded-md border p-2.5 transition-colors",
                    access === v && "border-primary bg-primary/5",
                  )}
                >
                  <input
                    type="radio"
                    name="edit_access"
                    value={v}
                    checked={access === v}
                    onChange={() => setAccess(v)}
                    className="mt-1"
                    disabled={updateMut.isPending}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm">{t(`settings.ai.field.access_${v}`)}</div>
                    <div className="text-muted-foreground text-xs">
                      {t(`settings.ai.field.access_${v}_hint`)}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={updateMut.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={updateMut.isPending}>
              {updateMut.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  {t("settings.ai.edit.submitting")}
                </>
              ) : (
                t("settings.ai.edit.submit")
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
