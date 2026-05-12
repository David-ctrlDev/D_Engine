"use client";

/**
 * "New AI connection" modal. Two-step flow:
 *
 *   1. Pick a provider (Anthropic / OpenAI / Google / Ollama).
 *   2. Fill the form (nickname, API key, model, base URL if Ollama,
 *      who can use it). Optionally test before saving.
 *
 * The "test before saving" gate is not strict — we recommend it but
 * don't block Save, because some keys are valid for the API but the
 * /models probe fails (rate limits, region restrictions). The user
 * can always rotate later.
 *
 * Member-access defaults to ``admins_only`` for safety; switching to
 * ``specific_members`` shows a hint to configure grants after saving
 * (the dedicated grants dialog handles that).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
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
import {
  createCredential,
  listProviders,
  testUnsavedCredential,
} from "@/lib/llm-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type {
  LlmCredentialPublic,
  LlmMemberAccess,
  LlmProviderKind,
  ModelOption,
  ProviderInfo,
} from "@/types/llm";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /**
   * Fired after a credential is created. The parent uses this to
   * optionally open the grants dialog when the user picked
   * ``specific_members`` so they can immediately assign people.
   */
  onCreated?: (credential: LlmCredentialPublic) => void;
}

type TestState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "ok" }
  | { status: "error"; error: string };

export function NewCredentialDialog({ open, onOpenChange, onCreated }: Props) {
  const t = useT();
  const qc = useQueryClient();

  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: listProviders,
    staleTime: Infinity, // The catalogue is static
  });

  // ----- Form state -----------------------------------------------------
  const [provider, setProvider] = useState<LlmProviderKind | null>(null);
  const [nickname, setNickname] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState<string>("");
  const [baseUrl, setBaseUrl] = useState("");
  const [access, setAccess] = useState<LlmMemberAccess>("admins_only");
  const [testState, setTestState] = useState<TestState>({ status: "idle" });
  // Live model list returned by the most recent successful test. We
  // prefer it over the curated catalogue because it reflects exactly
  // what *this* API key can hit (newest flagships, org-restricted
  // models, fine-tunes, locally-installed Ollama models, etc.).
  const [liveModels, setLiveModels] = useState<ModelOption[] | null>(null);

  function resetAndClose() {
    setProvider(null);
    setNickname("");
    setApiKey("");
    setModel("");
    setBaseUrl("");
    setAccess("admins_only");
    setTestState({ status: "idle" });
    setLiveModels(null);
    onOpenChange(false);
  }

  const selectedProvider = providersQuery.data?.providers.find((p) => p.kind === provider);

  // When the user picks a provider, default the model to its default.
  function pickProvider(p: ProviderInfo) {
    setProvider(p.kind);
    setModel(p.default_model);
  }

  // ----- Test mutation --------------------------------------------------
  const testMut = useMutation({
    mutationFn: () => {
      if (!provider) throw new Error("no provider");
      return testUnsavedCredential({
        provider,
        api_key: apiKey,
        base_url: selectedProvider?.needs_base_url ? baseUrl : null,
      });
    },
    onMutate: () => setTestState({ status: "running" }),
    onSuccess: (data) => {
      if (data.ok) {
        setTestState({ status: "ok" });
        // Swap the curated dropdown for the live one. If the live list
        // happens to include the previously-selected model id, keep
        // the selection; otherwise default to the first entry.
        if (data.models.length > 0) {
          setLiveModels(data.models);
          if (!data.models.some((m) => m.id === model)) {
            setModel(data.models[0].id);
          }
        }
      } else {
        setTestState({ status: "error", error: data.error ?? "Unknown error" });
      }
    },
    onError: (e) => {
      setTestState({
        status: "error",
        error: e instanceof ApiError ? e.message : t("common.something_went_wrong"),
      });
    },
  });

  // ----- Save mutation --------------------------------------------------
  const saveMut = useMutation({
    mutationFn: () => {
      if (!provider) throw new Error("no provider");
      return createCredential({
        provider,
        nickname: nickname.trim(),
        api_key: apiKey,
        model_default: model || null,
        base_url: selectedProvider?.needs_base_url ? baseUrl.trim() || null : null,
        member_access: access,
      });
    },
    onSuccess: (cred) => {
      qc.invalidateQueries({ queryKey: ["llm-credentials"] });
      toast.success(t("settings.ai.new.toast_success"));
      onCreated?.(cred);
      resetAndClose();
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!provider) return;
    if (!nickname.trim()) {
      toast.error(t("settings.ai.new.nickname_required"));
      return;
    }
    if (!apiKey) {
      toast.error(t("settings.ai.new.api_key_required"));
      return;
    }
    if (selectedProvider?.needs_base_url && !baseUrl.trim()) {
      toast.error(t("settings.ai.new.base_url_required"));
      return;
    }
    saveMut.mutate();
  }

  const apiKeyTouched = apiKey.length > 0;
  // Re-running test invalidates any prior result. The live model list
  // also belongs to the previous key, so clear it.
  function onApiKeyChange(v: string) {
    setApiKey(v);
    if (testState.status !== "idle") setTestState({ status: "idle" });
    if (liveModels !== null) setLiveModels(null);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) resetAndClose();
        else onOpenChange(true);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("settings.ai.new.title")}</DialogTitle>
          <DialogDescription>{t("settings.ai.new.subtitle")}</DialogDescription>
        </DialogHeader>

        {/* Step 1: provider grid */}
        {!provider ? (
          <div className="space-y-3">
            <p className="text-muted-foreground text-xs">
              {t("settings.ai.new.choose_provider")}
            </p>
            {providersQuery.isLoading ? (
              <div className="text-muted-foreground flex justify-center py-10">
                <Loader2 className="size-5 animate-spin" />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {providersQuery.data?.providers.map((p) => (
                  <button
                    type="button"
                    key={p.kind}
                    onClick={() => pickProvider(p)}
                    className={cn(
                      "border-input hover:border-primary/60 hover:bg-muted flex items-start gap-3 rounded-md border p-3 text-left transition-colors",
                    )}
                  >
                    <ProviderIcon provider={p.kind} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{p.display_name}</div>
                      <div className="text-muted-foreground line-clamp-2 text-xs">
                        {p.description}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <form className="space-y-4" onSubmit={onSubmit}>
            {/* Selected provider header */}
            <div className="bg-muted/30 flex items-center gap-3 rounded-md border px-3 py-2">
              <ProviderIcon provider={provider} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{selectedProvider?.display_name}</div>
                <div className="text-muted-foreground truncate text-xs">
                  {selectedProvider?.description}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={() => {
                  setProvider(null);
                  setTestState({ status: "idle" });
                }}
              >
                {t("common.cancel")}
              </Button>
            </div>

            {/* Nickname */}
            <div className="space-y-1.5">
              <Label htmlFor="cred_nickname">{t("settings.ai.field.nickname")}</Label>
              <Input
                id="cred_nickname"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder={t("settings.ai.field.nickname_placeholder")}
                maxLength={120}
                disabled={saveMut.isPending}
              />
              <p className="text-muted-foreground text-xs">
                {t("settings.ai.field.nickname_hint")}
              </p>
            </div>

            {/* API key */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="cred_api_key">{t("settings.ai.field.api_key")}</Label>
                {selectedProvider?.api_key_docs_url && (
                  <a
                    href={selectedProvider.api_key_docs_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary text-xs hover:underline"
                  >
                    {t("settings.ai.field.api_key_docs")}
                  </a>
                )}
              </div>
              <Input
                id="cred_api_key"
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(e) => onApiKeyChange(e.target.value)}
                placeholder={t("settings.ai.field.api_key_placeholder")}
                disabled={saveMut.isPending}
              />
              <p className="text-muted-foreground text-xs">
                {t("settings.ai.field.api_key_hint")}
              </p>
            </div>

            {/* Base URL (Ollama only) */}
            {selectedProvider?.needs_base_url && (
              <div className="space-y-1.5">
                <Label htmlFor="cred_base_url">{t("settings.ai.field.base_url")}</Label>
                <Input
                  id="cred_base_url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={t("settings.ai.field.base_url_placeholder")}
                  disabled={saveMut.isPending}
                />
                <p className="text-muted-foreground text-xs">
                  {t("settings.ai.field.base_url_hint")}
                </p>
              </div>
            )}

            {/* Default model */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="cred_model">{t("settings.ai.field.model")}</Label>
                {liveModels !== null && (
                  <span className="text-xs text-emerald-600 dark:text-emerald-400">
                    {t("settings.ai.field.model_live")}
                  </span>
                )}
              </div>
              <select
                id="cred_model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={saveMut.isPending}
                className="border-input bg-background focus:border-ring focus:ring-ring/50 h-9 w-full rounded-md border px-2 text-sm transition-colors focus:ring-3 focus:outline-none"
              >
                {(liveModels ?? selectedProvider?.models ?? []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                    {"notes" in m && m.notes ? ` — ${m.notes}` : ""}
                  </option>
                ))}
              </select>
              <p className="text-muted-foreground text-xs">
                {liveModels !== null
                  ? t("settings.ai.field.model_hint_live")
                  : t("settings.ai.field.model_hint")}
              </p>
            </div>

            {/* Member access */}
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
                      name="access"
                      value={v}
                      checked={access === v}
                      onChange={() => setAccess(v)}
                      className="mt-1"
                      disabled={saveMut.isPending}
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

            {/* Test before save */}
            <div className="flex items-center justify-between gap-2 border-t pt-3">
              <div className="flex items-center gap-2 text-xs">
                {testState.status === "running" && (
                  <span className="text-muted-foreground flex items-center gap-1">
                    <Loader2 className="size-3.5 animate-spin" />
                    {t("settings.ai.new.testing")}
                  </span>
                )}
                {testState.status === "ok" && (
                  <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="size-3.5" />
                    {t("settings.ai.new.test_ok")}
                  </span>
                )}
                {testState.status === "error" && (
                  <span className="text-destructive flex items-center gap-1">
                    <XCircle className="size-3.5" />
                    {t("settings.ai.new.test_failed", { error: testState.error })}
                  </span>
                )}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={
                  !apiKeyTouched ||
                  testState.status === "running" ||
                  saveMut.isPending ||
                  (selectedProvider?.needs_base_url && !baseUrl.trim())
                }
                onClick={() => testMut.mutate()}
              >
                {t("settings.ai.new.test_before_save")}
              </Button>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={resetAndClose}
                disabled={saveMut.isPending}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={saveMut.isPending}>
                {saveMut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    {t("settings.ai.new.submitting")}
                  </>
                ) : (
                  t("settings.ai.new.submit")
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
