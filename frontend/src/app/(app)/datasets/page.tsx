"use client";

/**
 * Datasets list — first thing the user sees under "Datos".
 *
 * Empty state pushes them to /datasets/upload. Once they have rows,
 * the table is the entry point for everything (detail view, agent
 * chat — those land in later slices).
 */

import { useQuery } from "@tanstack/react-query";
import { Database, Loader2, Plus } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { listDatasets } from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import type { DataSourceKind, DatasetSummary } from "@/types/data";

const SOURCE_KIND_LABEL: Record<DataSourceKind, string> = {
  csv: "CSV",
  parquet: "Parquet",
  xlsx: "Excel",
  postgres: "PostgreSQL",
  mssql: "SQL Server",
  mssql_azure: "Azure SQL",
};

export default function DatasetsPage() {
  const t = useT();
  const { data, isLoading, error } = useQuery({
    queryKey: ["datasets"],
    queryFn: listDatasets,
    staleTime: 5_000,
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("datasets.title")}</h1>
          <p className="text-muted-foreground text-sm">{t("datasets.subtitle")}</p>
        </div>
        <Button render={<Link href="/datasets/upload" />}>
          <Plus className="size-4" /> {t("datasets.upload_cta")}
        </Button>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground flex items-center justify-center py-16">
          <Loader2 className="size-5 animate-spin" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="text-destructive py-12 text-center text-sm">
            {t("datasets.load_failed")}
          </CardContent>
        </Card>
      ) : !data || data.datasets.length === 0 ? (
        <EmptyState t={t} />
      ) : (
        <DatasetsTable rows={data.datasets} t={t} />
      )}
    </div>
  );
}

function EmptyState({ t }: { t: ReturnType<typeof useT> }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="bg-muted flex size-12 items-center justify-center rounded-full">
          <Database className="text-muted-foreground size-6" />
        </div>
        <div className="max-w-sm space-y-1">
          <h2 className="text-base font-semibold">{t("datasets.empty.title")}</h2>
          <p className="text-muted-foreground text-sm">{t("datasets.empty.body")}</p>
        </div>
        <Button render={<Link href="/datasets/upload" />}>
          <Plus className="size-4" /> {t("datasets.empty.cta")}
        </Button>
      </CardContent>
    </Card>
  );
}

function DatasetsTable({
  rows,
  t,
}: {
  rows: DatasetSummary[];
  t: ReturnType<typeof useT>;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground bg-muted/40 text-left text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 font-medium">{t("datasets.col.name")}</th>
                <th className="px-4 py-3 font-medium">{t("datasets.col.source")}</th>
                <th className="px-4 py-3 font-medium">{t("datasets.col.visibility")}</th>
                <th className="px-4 py-3 font-medium">{t("datasets.col.created")}</th>
              </tr>
            </thead>
            <tbody className="divide-border divide-y">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/datasets/${row.id}`} className="hover:underline">
                      {row.name}
                    </Link>
                  </td>
                  <td className="text-muted-foreground px-4 py-3">
                    {SOURCE_KIND_LABEL[row.source_kind]} · {row.source_name}
                  </td>
                  <td className="text-muted-foreground px-4 py-3">
                    {t(`datasets.visibility.${row.visibility}`)}
                  </td>
                  <td className="text-muted-foreground px-4 py-3 text-xs">
                    {new Date(row.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
