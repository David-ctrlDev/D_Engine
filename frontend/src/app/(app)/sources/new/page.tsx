"use client";

/**
 * Connect a database. Slice C: postgres only.
 * Slice D extends the kind selector to include mssql + mssql_azure
 * (different default port + ssl handling).
 *
 * Flow: fill form → "Probar conexión" hits `/sources/test` → on success
 * "Conectar y elegir tablas" persists + navigates to /sources/{id}/tables.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import {
  createDatabaseSource,
  testConnection,
} from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { DatabaseConnectionPayload } from "@/types/data";

const KIND_DEFAULTS: Record<DatabaseConnectionPayload["kind"], { port: number; sslmode: string }> = {
  postgres: { port: 5432, sslmode: "prefer" },
  mssql: { port: 1433, sslmode: "disable" },
  mssql_azure: { port: 1433, sslmode: "require" },
};

export default function NewSourcePage() {
  const t = useT();
  const router = useRouter();
  const qc = useQueryClient();

  const [kind, setKind] = useState<DatabaseConnectionPayload["kind"]>("postgres");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState<number>(KIND_DEFAULTS.postgres.port);
  const [database, setDatabase] = useState("");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [sslmode, setSslmode] = useState(KIND_DEFAULTS.postgres.sslmode);
  const [testResult, setTestResult] = useState<{ ok: boolean; error: string | null } | null>(null);

  const payload: DatabaseConnectionPayload = {
    kind,
    name,
    host,
    port,
    database,
    user,
    password,
    sslmode,
  };

  const test = useMutation({
    mutationFn: () => testConnection(payload),
    onSuccess: (res) => {
      setTestResult(res);
      if (res.ok) toast.success(t("sources.new.test_ok"));
      else toast.error(res.error ?? t("sources.new.test_failed"));
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? e.message : t("common.something_went_wrong");
      setTestResult({ ok: false, error: msg });
      toast.error(msg);
    },
  });

  const create = useMutation({
    mutationFn: () => createDatabaseSource(payload),
    onSuccess: (source) => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      toast.success(t("sources.new.created"));
      router.push(`/sources/${source.id}/tables`);
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? e.message : t("common.something_went_wrong");
      toast.error(msg);
    },
  });

  function changeKind(k: DatabaseConnectionPayload["kind"]) {
    setKind(k);
    setPort(KIND_DEFAULTS[k].port);
    setSslmode(KIND_DEFAULTS[k].sslmode);
    setTestResult(null);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !host || !database || !user) {
      toast.error(t("sources.new.fill_required"));
      return;
    }
    create.mutate();
  }

  const busy = test.isPending || create.isPending;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Button variant="ghost" size="sm" render={<Link href="/datasets" />}>
        <ArrowLeft className="size-4" />
        {t("sources.new.back")}
      </Button>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("sources.new.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("sources.new.subtitle")}</p>
      </div>

      <Card>
        <CardContent className="p-6">
          <form className="space-y-5" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label>{t("sources.new.kind")}</Label>
              <div className="flex gap-2">
                {(["postgres", "mssql", "mssql_azure"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => changeKind(k)}
                    className={cn(
                      "border-input rounded-md border px-3 py-1.5 text-sm transition-colors",
                      kind === k
                        ? "border-primary bg-primary/5 text-foreground"
                        : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {t(`sources.kind.${k}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">{t("sources.new.name")}</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("sources.new.name_placeholder")}
                disabled={busy}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 space-y-2">
                <Label htmlFor="host">{t("sources.new.host")}</Label>
                <Input
                  id="host"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="db.example.com"
                  disabled={busy}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="port">{t("sources.new.port")}</Label>
                <Input
                  id="port"
                  type="number"
                  value={port}
                  onChange={(e) => setPort(parseInt(e.target.value, 10) || 0)}
                  disabled={busy}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="database">{t("sources.new.database")}</Label>
              <Input
                id="database"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                disabled={busy}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="user">{t("sources.new.user")}</Label>
                <Input
                  id="user"
                  value={user}
                  onChange={(e) => setUser(e.target.value)}
                  disabled={busy}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{t("sources.new.password")}</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={busy}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="sslmode">{t("sources.new.sslmode")}</Label>
              <select
                id="sslmode"
                className="border-input bg-background h-8 w-full rounded-md border px-2 text-sm"
                value={sslmode}
                onChange={(e) => setSslmode(e.target.value)}
                disabled={busy}
              >
                {kind === "postgres"
                  ? ["disable", "prefer", "require", "verify-ca", "verify-full"].map((v) => (
                      <option key={v}>{v}</option>
                    ))
                  : ["disable", "require"].map((v) => <option key={v}>{v}</option>)}
              </select>
            </div>

            {testResult && (
              <div
                className={cn(
                  "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
                  testResult.ok
                    ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400"
                    : "border-destructive/30 bg-destructive/5 text-destructive",
                )}
              >
                {testResult.ok ? (
                  <CheckCircle2 className="mt-0.5 size-4" />
                ) : (
                  <XCircle className="mt-0.5 size-4" />
                )}
                <span className="break-words">
                  {testResult.ok ? t("sources.new.test_ok") : testResult.error}
                </span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => test.mutate()}
                disabled={busy || !host || !database || !user}
              >
                {test.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
                {t("sources.new.test")}
              </Button>
              <Button type="submit" disabled={busy}>
                {create.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
                {t("sources.new.connect")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
