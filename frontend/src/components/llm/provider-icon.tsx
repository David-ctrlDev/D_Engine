/**
 * Provider icon — a small monogram tile coloured per-provider.
 *
 * We deliberately avoid shipping real SVG logos: each vendor has its
 * own brand-usage policy (especially OpenAI / Anthropic) and a coloured
 * monogram is unambiguous enough at this size.
 */

import { cn } from "@/lib/utils";
import type { LlmProviderKind } from "@/types/llm";

interface Theme {
  letter: string;
  bg: string;
  fg: string;
}

const THEMES: Record<LlmProviderKind, Theme> = {
  anthropic: {
    letter: "A",
    bg: "bg-orange-100 dark:bg-orange-500/15",
    fg: "text-orange-700 dark:text-orange-300",
  },
  openai: {
    letter: "O",
    bg: "bg-emerald-100 dark:bg-emerald-500/15",
    fg: "text-emerald-700 dark:text-emerald-300",
  },
  google: {
    letter: "G",
    bg: "bg-blue-100 dark:bg-blue-500/15",
    fg: "text-blue-700 dark:text-blue-300",
  },
  ollama: {
    letter: "L",
    bg: "bg-violet-100 dark:bg-violet-500/15",
    fg: "text-violet-700 dark:text-violet-300",
  },
};

export function ProviderIcon({
  provider,
  size = "md",
  className,
}: {
  provider: LlmProviderKind;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const theme = THEMES[provider];
  const sizeClass =
    size === "sm" ? "size-6 text-xs" : size === "lg" ? "size-10 text-base" : "size-8 text-sm";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md font-semibold",
        theme.bg,
        theme.fg,
        sizeClass,
        className,
      )}
      aria-hidden
    >
      {theme.letter}
    </span>
  );
}
