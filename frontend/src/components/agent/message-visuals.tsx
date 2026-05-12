"use client";

/**
 * Inline visualizations rendered under an agent message.
 *
 * Each entry in ``message.visualizations`` has a ``kind`` tag we
 * dispatch into the matching chart component. Most are recharts-
 * based; the pending-action card is a custom interactive widget
 * with [Aceptar / Rechazar] buttons that calls
 * ``resolvePendingAction`` and appends the agent's follow-up turn
 * to the local transcript.
 *
 * Why recharts
 * ------------
 * Lightweight, well-typed React API, sensible defaults out of the
 * box. The bundle hit is acceptable (~80KB gzipped) and we don't
 * have to hand-roll SVG primitives.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Sparkles, XCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { resolvePendingAction } from "@/lib/agent-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type {
  ConversationDetail,
  MessagePublic,
  Visualization,
} from "@/types/agent";

export function MessageVisuals({
  visualizations,
  messageId,
  conversationId,
}: {
  visualizations: Visualization[];
  messageId: string;
  conversationId: string;
}) {
  return (
    <div className="space-y-2">
      {visualizations.map((v, idx) => (
        <VisualBlock
          key={idx}
          viz={v}
          messageId={messageId}
          conversationId={conversationId}
        />
      ))}
    </div>
  );
}

function VisualBlock({
  viz,
  messageId,
  conversationId,
}: {
  viz: Visualization;
  messageId: string;
  conversationId: string;
}) {
  switch (viz.kind) {
    case "histogram":
      return <HistogramBlock viz={viz} />;
    case "value_counts":
      return <ValueCountsBlock viz={viz} />;
    case "null_pct":
      return <NullPctBlock viz={viz} />;
    case "before_after":
      return <BeforeAfterBlock viz={viz} />;
    case "duplicate_preview":
      return <DuplicatePreviewBlock viz={viz} />;
    case "pending_action":
      return (
        <PendingActionCard
          viz={viz}
          messageId={messageId}
          conversationId={conversationId}
        />
      );
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Histogram — numeric column distribution.
// ---------------------------------------------------------------------------

function HistogramBlock({
  viz,
}: {
  viz: Extract<Visualization, { kind: "histogram" }>;
}) {
  return (
    <BlockShell title={`Distribución de "${viz.column}"`}>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={viz.bins} margin={{ top: 6, right: 6, left: -20, bottom: 6 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "currentColor" }}
            interval={Math.max(0, Math.floor(viz.bins.length / 6) - 1)}
            stroke="currentColor"
            strokeOpacity={0.25}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "currentColor" }}
            stroke="currentColor"
            strokeOpacity={0.25}
          />
          <Tooltip
            contentStyle={chartTooltipStyle}
            labelStyle={{ color: "currentColor" }}
          />
          <Bar dataKey="count" fill="var(--color-primary, #6366f1)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </BlockShell>
  );
}

// ---------------------------------------------------------------------------
// Value counts — top-N for text/categorical.
// ---------------------------------------------------------------------------

function ValueCountsBlock({
  viz,
}: {
  viz: Extract<Visualization, { kind: "value_counts" }>;
}) {
  // Truncate long labels so the chart stays readable.
  const data = viz.items.map((it) => ({
    label: it.value.length > 22 ? `${it.value.slice(0, 22)}…` : it.value,
    full: it.value,
    count: it.count,
  }));
  return (
    <BlockShell title={`Valores más frecuentes en "${viz.column}"`}>
      <ResponsiveContainer width="100%" height={Math.max(140, data.length * 22)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
        >
          <XAxis type="number" tick={{ fontSize: 10, fill: "currentColor" }} stroke="currentColor" strokeOpacity={0.25} />
          <YAxis
            type="category"
            dataKey="label"
            width={120}
            tick={{ fontSize: 10, fill: "currentColor" }}
            stroke="currentColor"
            strokeOpacity={0.25}
          />
          <Tooltip
            contentStyle={chartTooltipStyle}
            formatter={(value, _name, item) => [value as number, item.payload.full]}
          />
          <Bar dataKey="count" fill="var(--color-primary, #6366f1)" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </BlockShell>
  );
}

// ---------------------------------------------------------------------------
// Null percentage — donut + number.
// ---------------------------------------------------------------------------

function NullPctBlock({
  viz,
}: {
  viz: Extract<Visualization, { kind: "null_pct" }>;
}) {
  const pct = Math.round(viz.null_pct * 100);
  const data = [
    { name: "Nulos", value: viz.null_count, color: "var(--color-destructive, #ef4444)" },
    {
      name: "Con valor",
      value: viz.total - viz.null_count,
      color: "var(--color-primary, #6366f1)",
    },
  ];
  return (
    <BlockShell title={`Nulos en "${viz.column}"`}>
      <div className="flex items-center gap-4">
        <div className="size-24 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                innerRadius={28}
                outerRadius={42}
                paddingAngle={2}
                stroke="none"
              >
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="text-sm">
          <div className="text-2xl font-semibold">{pct}%</div>
          <div className="text-muted-foreground text-xs">
            {viz.null_count.toLocaleString()} de {viz.total.toLocaleString()} filas sin valor
          </div>
        </div>
      </div>
    </BlockShell>
  );
}

// ---------------------------------------------------------------------------
// Before / after — two bars side-by-side with a delta badge.
// ---------------------------------------------------------------------------

function BeforeAfterBlock({
  viz,
}: {
  viz: Extract<Visualization, { kind: "before_after" }>;
}) {
  const max = Math.max(viz.before, viz.after, 1);
  const beforePct = (viz.before / max) * 100;
  const afterPct = (viz.after / max) * 100;
  const tone =
    viz.tone === "positive"
      ? "text-emerald-600 dark:text-emerald-400"
      : viz.tone === "warning"
        ? "text-amber-600 dark:text-amber-400"
        : "text-muted-foreground";
  return (
    <BlockShell title={viz.label}>
      <div className="space-y-2">
        <BarRow label="Antes" pct={beforePct} value={viz.before} muted />
        <BarRow label="Ahora" pct={afterPct} value={viz.after} />
        <div className={cn("text-xs font-medium", tone)}>{viz.delta_label}</div>
      </div>
    </BlockShell>
  );
}

function BarRow({
  label,
  pct,
  value,
  muted = false,
}: {
  label: string;
  pct: number;
  value: number;
  muted?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="text-muted-foreground w-12 shrink-0">{label}</div>
      <div className="bg-muted h-2 flex-1 overflow-hidden rounded-full">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            muted ? "bg-muted-foreground/40" : "bg-primary",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="w-16 shrink-0 text-right font-medium tabular-nums">
        {value.toLocaleString()}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Duplicate preview — table of the first N duplicate groups.
// ---------------------------------------------------------------------------

function DuplicatePreviewBlock({
  viz,
}: {
  viz: Extract<Visualization, { kind: "duplicate_preview" }>;
}) {
  return (
    <BlockShell
      title={`${viz.duplicate_groups} grupos duplicados (${viz.total_duplicates} filas se eliminarían)`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground text-left">
              {viz.columns.map((c) => (
                <th key={c} className="px-2 py-1 font-medium">
                  {c}
                </th>
              ))}
              <th className="px-2 py-1 text-right font-medium">Veces</th>
            </tr>
          </thead>
          <tbody className="divide-border/40 divide-y">
            {viz.example_groups.map((g, i) => (
              <tr key={i}>
                {viz.columns.map((c) => (
                  <td key={c} className="px-2 py-1 font-mono">
                    {g.key[c] ?? "—"}
                  </td>
                ))}
                <td className="px-2 py-1 text-right tabular-nums">×{g.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </BlockShell>
  );
}

// ---------------------------------------------------------------------------
// Pending action — interactive card with [Aceptar / Rechazar].
// ---------------------------------------------------------------------------

function PendingActionCard({
  viz,
  messageId,
  conversationId,
}: {
  viz: Extract<Visualization, { kind: "pending_action" }>;
  messageId: string;
  conversationId: string;
}) {
  const t = useT();
  const qc = useQueryClient();

  const resolveMut = useMutation({
    mutationFn: (accept: boolean) =>
      resolvePendingAction(conversationId, viz.tool_call_id, {
        messageId,
        accept,
      }),
    onSuccess: (resp) => {
      qc.setQueryData<ConversationDetail | undefined>(
        ["conversation", conversationId],
        (prev) => {
          if (!prev) return prev;
          const next = appendIfMissing(prev.messages, resp.assistant_messages);
          return { ...prev, messages: next };
        },
      );
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  const description = describePendingAction(viz);

  return (
    <div className="border-primary/30 bg-primary/5 space-y-3 rounded-lg border p-3">
      <div className="flex items-start gap-2">
        <Sparkles className="text-primary mt-0.5 size-4 shrink-0" />
        <div className="space-y-1 text-sm">
          <div className="font-medium">{t("agent.pending.title")}</div>
          <div className="text-muted-foreground text-xs">{description}</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => resolveMut.mutate(true)}
          disabled={resolveMut.isPending}
        >
          {resolveMut.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <CheckCircle2 className="size-4" />
          )}
          {t("agent.pending.accept")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => resolveMut.mutate(false)}
          disabled={resolveMut.isPending}
        >
          <XCircle className="size-4" />
          {t("agent.pending.reject")}
        </Button>
      </div>
    </div>
  );
}

function describePendingAction(
  viz: Extract<Visualization, { kind: "pending_action" }>,
): string {
  if (viz.tool_name === "propose_dedupe") {
    const args = viz.args as {
      columns?: string[];
      keep?: string;
      normalize_text?: boolean;
      reason?: string;
    };
    const cols = (args.columns ?? []).map((c) => `"${c}"`).join(", ");
    const keep = args.keep === "last" ? "la última aparición" : "la primera aparición";
    const norm = args.normalize_text ? " (comparando texto normalizado)" : "";
    const reason = args.reason ? ` ${args.reason}` : "";
    return `Voy a eliminar filas duplicadas por ${cols}, manteniendo ${keep}${norm}.${reason}`;
  }
  return "El asistente propone ejecutar una acción.";
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function BlockShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-border/40 bg-background/60 space-y-2 rounded-md border p-2.5">
      <div className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
        {title}
      </div>
      {children}
    </div>
  );
}

const chartTooltipStyle = {
  background: "var(--color-popover, #1f1f23)",
  border: "1px solid var(--color-border, rgba(255,255,255,0.1))",
  borderRadius: 6,
  fontSize: 12,
  padding: "4px 8px",
};

function appendIfMissing(
  existing: MessagePublic[],
  incoming: MessagePublic[],
): MessagePublic[] {
  const seen = new Set(existing.map((m) => m.id));
  const additions = incoming.filter((m) => !seen.has(m.id));
  return [...existing, ...additions];
}
