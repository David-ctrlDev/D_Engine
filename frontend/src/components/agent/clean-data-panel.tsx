"use client";

/**
 * "Datos limpios (versión actual)" — surfaces the user's working copy
 * on the dataset detail page.
 *
 * The card shows the live state of the agent's transformations:
 * row/column counts, last-modified, plus a "Ver tabla" toggle that
 * loads a sample of the rows. Operations history (what the agent ran,
 * in order) lives in its own collapsible section so the user can
 * audit every change.
 *
 * Renders nothing when there's no working copy yet — the agent hasn't
 * touched the dataset.
 */

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Loader2, Sparkles, Table2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getWorkingCopy,
  getWorkingCopySample,
  listWorkingCopyOperations,
} from "@/lib/working-copy-actions";
import { cn } from "@/lib/utils";

// Same human-language labels used in the chat badge — kept in sync
// here so the journal section reads identically to the agent's
// "Ejecutado: ..." chips.
const OP_LABELS: Record<string, string> = {
  inspect_column: "Análisis de columna",
  preview_duplicates: "Búsqueda de duplicados",
  dedupe: "Eliminación de duplicados",
  fillna: "Tratamiento de nulos",
  normalize_text: "Normalización de texto",
  parse_dates: "Conversión de fechas",
  normalize_numeric: "Conversión a números",
};

export function CleanDataPanel({ datasetId }: { datasetId: string }) {
  const wcQuery = useQuery({
    queryKey: ["working-copy", datasetId],
    queryFn: () => getWorkingCopy(datasetId),
  });
  const opsQuery = useQuery({
    queryKey: ["working-copy-ops", datasetId],
    queryFn: () => listWorkingCopyOperations(datasetId),
    enabled: !!wcQuery.data,
  });
  const sampleQuery = useQuery({
    queryKey: ["working-copy-sample", datasetId],
    queryFn: () => getWorkingCopySample(datasetId),
    enabled: !!wcQuery.data,
  });

  const [tableOpen, setTableOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  if (wcQuery.isLoading) {
    return (
      <Card>
        <CardContent className="text-muted-foreground flex justify-center py-6">
          <Loader2 className="size-4 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  // No working copy yet — the agent hasn't done anything. Stay quiet
  // (the "Comenzar con la IA" card already invites the user).
  if (!wcQuery.data) return null;

  const wc = wcQuery.data;
  const operations = (opsQuery.data?.operations ?? []).filter((o) => !o.undone_at);
  const sample = sampleQuery.data;

  return (
    <Card className="border-emerald-500/20 bg-emerald-500/5">
      <CardHeader className="flex flex-row items-start justify-between pb-3">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="size-4 text-emerald-600 dark:text-emerald-400" />
            Datos limpios (versión actual)
          </CardTitle>
          <p className="text-muted-foreground text-xs">
            Esta es la versión sobre la que está trabajando el agente. El
            dataset original sigue intacto.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Quick stats */}
        <div className="flex flex-wrap gap-4 text-sm">
          <Stat label="Filas" value={wc.row_count?.toLocaleString() ?? "—"} />
          <Stat label="Columnas" value={wc.column_count?.toLocaleString() ?? "—"} />
          <Stat
            label="Cambios aplicados"
            value={operations.length.toLocaleString()}
          />
          <Stat
            label="Última actualización"
            value={new Date(wc.updated_at).toLocaleString()}
          />
        </div>

        {/* Show table toggle */}
        <div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setTableOpen((v) => !v)}
            disabled={sampleQuery.isLoading}
          >
            {tableOpen ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
            <Table2 className="size-3.5" />
            {tableOpen ? "Ocultar tabla" : "Ver tabla"}
          </Button>
        </div>

        {tableOpen && (
          <div className="bg-background rounded-md border">
            {sampleQuery.isLoading ? (
              <div className="text-muted-foreground flex justify-center py-6">
                <Loader2 className="size-4 animate-spin" />
              </div>
            ) : sample === undefined || sample === null ? (
              <div className="text-muted-foreground py-6 text-center text-sm">
                No se pudo cargar la vista previa.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-muted-foreground bg-muted/40 text-left">
                    <tr>
                      {sample.columns.map((c) => (
                        <th
                          key={c.name}
                          className="px-3 py-2 font-medium whitespace-nowrap"
                        >
                          {c.name}
                          <div className="text-[10px] font-normal opacity-60">
                            {c.dtype}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-border/60 divide-y">
                    {sample.rows.map((r, i) => (
                      <tr key={i}>
                        {sample.columns.map((c) => (
                          <td
                            key={c.name}
                            className="text-muted-foreground px-3 py-1.5 whitespace-nowrap"
                          >
                            {formatCell(r[c.name])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="text-muted-foreground border-t px-3 py-2 text-xs">
                  Mostrando {sample.rows.length.toLocaleString()} de{" "}
                  {sample.row_count.toLocaleString()} filas.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Operations history */}
        {operations.length > 0 && (
          <div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setHistoryOpen((v) => !v)}
            >
              {historyOpen ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
              Ver historial de cambios
            </Button>
            {historyOpen && (
              <ul className="divide-border/60 mt-2 divide-y rounded-md border">
                {operations.map((op) => {
                  const delta =
                    op.rows_before != null && op.rows_after != null
                      ? op.rows_after - op.rows_before
                      : null;
                  return (
                    <li
                      key={op.id}
                      className="flex items-center justify-between px-3 py-2 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">
                          {OP_LABELS[op.op] ?? op.op}
                        </div>
                        <div className="text-muted-foreground">
                          {new Date(op.created_at).toLocaleString()}
                        </div>
                      </div>
                      {delta != null && (
                        <span
                          className={cn(
                            "tabular-nums",
                            delta === 0
                              ? "text-muted-foreground"
                              : delta < 0
                                ? "text-emerald-600 dark:text-emerald-400"
                                : "text-amber-600 dark:text-amber-400",
                          )}
                        >
                          {delta > 0 ? "+" : ""}
                          {delta} filas
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-muted-foreground text-[10px] uppercase tracking-wide">
        {label}
      </span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
