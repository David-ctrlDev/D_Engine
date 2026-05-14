"use client";

/**
 * "Datos limpios (versión actual)" — the working-copy surface on the
 * dataset detail page.
 *
 * Three sections, stacked:
 *
 *   1. **Quick stats + actions** — rows / columns / op count + a
 *      "Volver al original" button that wipes every transformation.
 *   2. **Historial de cambios** — every op the agent ran, newest
 *      first, with rows-delta badges and per-row [Deshacer] buttons.
 *      Expanded by default so the user has an instant view of "what
 *      did the agent do to my data?".
 *   3. **Vista previa de la tabla** — collapsible sample of the
 *      current parquet snapshot. Off by default to keep the page
 *      light; the user clicks "Ver tabla" when they want it.
 *
 * Renders nothing when no working copy exists yet — the agent
 * hasn't done anything and the "Comenzar con la IA" CTA is the
 * obvious next step.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  RotateCcw,
  Sparkles,
  Table2,
  Undo2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import {
  getWorkingCopy,
  getWorkingCopySample,
  listWorkingCopyOperations,
  resetWorkingCopy,
  undoOperation,
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
  const qc = useQueryClient();

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

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ["working-copy", datasetId] });
    qc.invalidateQueries({ queryKey: ["working-copy-ops", datasetId] });
    qc.invalidateQueries({ queryKey: ["working-copy-sample", datasetId] });
  }

  const undoMut = useMutation({
    mutationFn: (opId: string) => undoOperation(datasetId, opId),
    onSuccess: (resp) => {
      toast.success(
        resp.undone_count === 1
          ? "Cambio deshecho."
          : `Deshechos ${resp.undone_count} cambios.`,
      );
      refreshAll();
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : "No se pudo deshacer.");
    },
  });

  const resetMut = useMutation({
    mutationFn: () => resetWorkingCopy(datasetId),
    onSuccess: (resp) => {
      toast.success(
        resp.undone_count === 0
          ? "El dataset ya estaba en su versión original."
          : `Volví a la versión original (deshice ${resp.undone_count} cambios).`,
      );
      refreshAll();
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : "No se pudo restaurar.");
    },
  });

  if (wcQuery.isLoading) {
    return (
      <Card>
        <CardContent className="text-muted-foreground flex justify-center py-6">
          <Loader2 className="size-4 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  // No working copy yet — the agent hasn't done anything.
  if (!wcQuery.data) return null;

  const wc = wcQuery.data;
  const allOps = opsQuery.data?.operations ?? [];
  const activeOps = allOps.filter((o) => !o.undone_at);
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
            dataset original sigue intacto — siempre puedes volver a él.
          </p>
        </div>
        {activeOps.length > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              if (
                window.confirm(
                  "Esto deshace TODOS los cambios y vuelve al dataset original. ¿Continuar?",
                )
              ) {
                resetMut.mutate();
              }
            }}
            disabled={resetMut.isPending}
          >
            {resetMut.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RotateCcw className="size-3.5" />
            )}
            Volver al original
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Quick stats */}
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <Stat label="Filas" value={wc.row_count?.toLocaleString() ?? "—"} />
          <Stat label="Columnas" value={wc.column_count?.toLocaleString() ?? "—"} />
          <Stat
            label="Cambios activos"
            value={activeOps.length.toLocaleString()}
          />
          <Stat
            label="Última actualización"
            value={new Date(wc.updated_at).toLocaleString()}
          />
        </div>

        {/* History — visible by default. The "what's happening" view. */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide opacity-70">
            Historial de cambios
          </h3>
          {allOps.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              Aún no se ha aplicado ningún cambio.
            </p>
          ) : (
            <ul className="divide-border/60 divide-y rounded-md border bg-background">
              {allOps.map((op) => {
                const delta =
                  op.rows_before != null && op.rows_after != null
                    ? op.rows_after - op.rows_before
                    : null;
                const isUndone = op.undone_at != null;
                return (
                  <li
                    key={op.id}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 text-sm",
                      isUndone && "opacity-50",
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div
                        className={cn(
                          "font-medium",
                          isUndone && "line-through decoration-muted-foreground",
                        )}
                      >
                        {OP_LABELS[op.op] ?? op.op}
                      </div>
                      <div className="text-muted-foreground text-xs">
                        {new Date(op.created_at).toLocaleString()}
                        {isUndone && " · deshecho"}
                      </div>
                    </div>
                    {delta != null && (
                      <span
                        className={cn(
                          "text-xs tabular-nums",
                          isUndone
                            ? "text-muted-foreground"
                            : delta === 0
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
                    {!isUndone && (
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => {
                          if (
                            window.confirm(
                              "Esto deshace este cambio y todos los posteriores. ¿Continuar?",
                            )
                          ) {
                            undoMut.mutate(op.id);
                          }
                        }}
                        disabled={undoMut.isPending}
                      >
                        <Undo2 className="size-3" />
                        Deshacer
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Sample table — collapsible */}
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
