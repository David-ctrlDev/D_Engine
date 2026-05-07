"use client";

/**
 * Profile section — runs the analyser inline and shows per-column
 * stats. Slice E.
 *
 * The "Run profile" button POSTs to ``/api/v1/datasets/{id}/profile``
 * which currently runs synchronously; once we have a worker the call
 * will return a running run + we'll poll. The state machine here
 * already handles ``running`` / ``completed`` / ``failed`` so the
 * polling switch is a one-line change.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Loader2, Play, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getLatestProfile, runProfile } from "@/lib/data-actions";
import { useT } from "@/lib/i18n/provider";
import type { ColumnProfile, DatasetProfile } from "@/types/data";

export function ProfileSection({ datasetId }: { datasetId: string }) {
  const t = useT();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["dataset-profile", datasetId],
    queryFn: () => getLatestProfile(datasetId),
    retry: false,
  });

  const runMut = useMutation({
    mutationFn: () => runProfile(datasetId),
    onSuccess: (profile) => {
      qc.setQueryData(["dataset-profile", datasetId], profile);
      qc.invalidateQueries({ queryKey: ["datasets"] });
      qc.invalidateQueries({ queryKey: ["dataset", datasetId] });
      if (profile.status === "failed") {
        toast.error(profile.error ?? t("profile.failed"));
      }
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="size-4" />
          {t("profile.title")}
        </CardTitle>
        <Button size="sm" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
          {runMut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : data ? (
            <RefreshCw className="size-3.5" />
          ) : (
            <Play className="size-3.5" />
          )}
          {runMut.isPending ? t("profile.running") : data ? t("profile.run") : t("profile.run")}
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-muted-foreground flex justify-center py-8">
            <Loader2 className="size-4 animate-spin" />
          </div>
        ) : !data ? (
          <p className="text-muted-foreground py-6 text-center text-sm">{t("profile.empty")}</p>
        ) : data.status === "failed" ? (
          <p className="text-destructive py-6 text-center text-sm">
            {data.error ?? t("profile.failed")}
          </p>
        ) : (
          <ProfileTable profile={data} />
        )}
      </CardContent>
    </Card>
  );
}

function ProfileTable({ profile }: { profile: DatasetProfile }) {
  const t = useT();
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-xs">
        {t("profile.row_count")}:{" "}
        <span className="text-foreground font-medium">
          {profile.row_count?.toLocaleString() ?? "—"}
        </span>
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted-foreground bg-muted/40 text-left text-xs uppercase tracking-wide">
            <tr>
              <th className="px-3 py-2 font-medium">{t("profile.col.name")}</th>
              <th className="px-3 py-2 font-medium">{t("profile.col.type")}</th>
              <th className="px-3 py-2 text-right font-medium">{t("profile.col.nulls")}</th>
              <th className="px-3 py-2 text-right font-medium">{t("profile.col.distinct")}</th>
              <th className="px-3 py-2 font-medium">{t("profile.col.range")}</th>
              <th className="px-3 py-2 font-medium">{t("profile.col.top")}</th>
            </tr>
          </thead>
          <tbody className="divide-border divide-y">
            {profile.columns.map((col) => (
              <ColumnProfileRow key={col.name} col={col} totalRows={profile.row_count ?? 0} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ColumnProfileRow({ col, totalRows }: { col: ColumnProfile; totalRows: number }) {
  const nullPct = (col.null_pct * 100).toFixed(1);
  const isHigh = col.null_pct >= 0.2;
  return (
    <tr>
      <td className="px-3 py-2 font-medium">{col.name}</td>
      <td className="px-3 py-2">
        <Badge variant="secondary" className="font-mono text-xs">
          {col.dtype}
        </Badge>
      </td>
      <td className="px-3 py-2 text-right text-xs tabular-nums">
        <span className={isHigh ? "text-destructive font-medium" : "text-muted-foreground"}>
          {col.null_count.toLocaleString()}
          {totalRows > 0 && <span className="ml-1 opacity-70">({nullPct}%)</span>}
        </span>
      </td>
      <td className="text-muted-foreground px-3 py-2 text-right text-xs tabular-nums">
        {col.distinct_count?.toLocaleString() ?? "—"}
      </td>
      <td className="text-muted-foreground px-3 py-2 font-mono text-xs">
        {col.min == null && col.max == null ? "—" : `${col.min ?? "—"} … ${col.max ?? "—"}`}
      </td>
      <td className="text-muted-foreground px-3 py-2 text-xs">
        {col.top_values.slice(0, 3).map((tv, i) => (
          <span key={i} className="mr-2 inline-block">
            <span className="font-mono">{tv.value || "∅"}</span>
            <span className="opacity-70"> ×{tv.count}</span>
          </span>
        ))}
      </td>
    </tr>
  );
}
