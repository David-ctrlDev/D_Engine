"use client";

/**
 * ES / EN toggle. Pair with ``ThemeToggle`` in the same header bar.
 *
 * Hidden until mounted (same pattern as ThemeToggle) so the rendered
 * label always matches the persisted locale.
 */

import { Globe } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useLocale } from "@/lib/i18n/provider";

export function LocaleToggle() {
  const { locale, setLocale, t } = useLocale();
  const [mounted, setMounted] = useState(false);

  // Same justification as ThemeToggle: gate the first render on a mount
  // flag so SSR and the persisted preference don't disagree visually.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" disabled aria-label="Locale">
        <Globe className="size-4" />
      </Button>
    );
  }

  const next = locale === "es" ? "en" : "es";
  const aria = next === "en" ? t("locale.switch_to_english") : t("locale.switch_to_spanish");

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(next)}
      aria-label={aria}
      title={aria}
      className="gap-1.5"
    >
      <Globe className="size-4" />
      <span className="text-xs font-medium uppercase tracking-wider">{locale}</span>
    </Button>
  );
}
