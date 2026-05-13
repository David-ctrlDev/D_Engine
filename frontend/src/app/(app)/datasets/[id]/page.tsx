"use client";

/**
 * Dataset detail — schema columns + a small sample preview. The
 * profiling-rich view (nulls, distinct counts, agent suggestions)
 * lands in slice E. For slice A we just need to prove "the file
 * came in and we read it back".
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { AgentNextStep } from "@/components/agent/agent-next-step";
import { CleanDataPanel } from "@/components/agent/clean-data-panel";
import { ProfileSection } from "@/components/datasets/profile-section";
import { ShareSection } from "@/components/datasets/share-section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCurrentUser } from "@/hooks/use-current-user";
import { ApiError } from "@/lib/api";
import { getDataset } from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import type { DataSourceKind, DatasetColumn } from "@/types/data";

const SOURCE_KIND_LABEL: Record<DataSourceKind, string> = {
  csv: "CSV",
  parquet: "Parquet",
  xlsx: "Excel",
  postgres: "PostgreSQL",
  mssql: "SQL Server",
  mssql_azure: "Azure SQL",
};

export default function DatasetDetailPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const me = useCurrentUser();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dataset", id],
    queryFn: () => getDataset(id),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center py-16">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Button variant="ghost" size="sm" render={<Link href="/datasets" />}>
          <ArrowLeft className="size-4" />
          {t("datasets.detail.back")}
        </Button>
        <Card>
          <CardContent className="text-destructive py-12 text-center text-sm">
            {notFound ? t("datasets.detail.not_found") : t("datasets.detail.load_failed")}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <Button variant="ghost" size="sm" render={<Link href="/datasets" />}>
          <ArrowLeft className="size-4" />
          {t("datasets.detail.back")}
        </Button>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
          <div className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
            <FileText className="size-4" />
            {SOURCE_KIND_LABEL[data.source.kind]} · {data.source.name}
          </div>
        </div>
        <Badge variant="outline">{t(`datasets.visibility.${data.visibility}`)}</Badge>
      </div>

      {/* Columns */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {t("datasets.detail.columns_title", {
              count: String(data.columns.length),
            })}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-left text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("datasets.detail.col.name")}</th>
                  <th className="px-4 py-2 font-medium">{t("datasets.detail.col.type")}</th>
                  <th className="px-4 py-2 font-medium">{t("datasets.detail.col.sample")}</th>
                </tr>
              </thead>
              <tbody className="divide-border divide-y">
                {data.columns.map((col) => (
                  <ColumnRow key={col.name} col={col} />
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Profile (slice E) */}
      <ProfileSection datasetId={data.id} />

      {/* Agent kickoff (slice G2.1 — agent-led) */}
      <AgentNextStep datasetId={data.id} />

      {/* Working copy state — only renders when the agent has actually
          done something. Shows row/col counts, ops history, sample table. */}
      <CleanDataPanel datasetId={data.id} />

      {/* Sharing (slice F) */}
      {me.data && (
        <ShareSection
          datasetId={data.id}
          currentUserId={me.data.user.id}
          initialVisibility={data.visibility}
        />
      )}

      {/* Sample rows */}
      {data.sample_rows.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {t("datasets.detail.sample_title", {
                count: String(data.sample_rows.length),
              })}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-muted-foreground bg-muted/40 text-left text-xs uppercase tracking-wide">
                  <tr>
                    {data.columns.map((c) => (
                      <th key={c.name} className="px-4 py-2 font-medium whitespace-nowrap">
                        {c.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-border divide-y">
                  {data.sample_rows.map((row, idx) => (
                    <tr key={idx}>
                      {data.columns.map((c) => (
                        <td
                          key={c.name}
                          className="text-muted-foreground px-4 py-2 whitespace-nowrap"
                        >
                          {formatCell(row[c.name])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ColumnRow({ col }: { col: DatasetColumn }) {
  return (
    <tr>
      <td className="px-4 py-2 font-medium">{col.name}</td>
      <td className="px-4 py-2">
        <Badge variant="secondary" className="font-mono text-xs">
          {col.dtype}
        </Badge>
      </td>
      <td className="text-muted-foreground px-4 py-2 font-mono text-xs">
        {col.sample_values.slice(0, 3).join(" · ") || "—"}
      </td>
    </tr>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
