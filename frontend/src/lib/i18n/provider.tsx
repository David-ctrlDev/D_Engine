"use client";

/**
 * Locale provider — sits beside ThemeProvider in the root layout.
 *
 * Stores the chosen locale in ``localStorage`` so a refresh keeps the
 * user's preference; falls back to ``DEFAULT_LOCALE`` on first visit.
 *
 * The ``t`` helper does dot-key lookup in the active dictionary and
 * substitutes ``{name}`` placeholders. Unknown keys log a console
 * warning in development and return the key string itself, so missing
 * translations surface immediately.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import {
  DEFAULT_LOCALE,
  type DictionaryKey,
  type Locale,
  dictionaries,
} from "@/lib/i18n/dictionaries";

const STORAGE_KEY = "dataprep.locale";

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: DictionaryKey, vars?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function format(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) =>
    name in vars ? String(vars[name]) : `{${name}}`,
  );
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  // Read the persisted preference on mount; can't be done synchronously
  // during SSR. The flicker is a single render and only on first paint.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "es" || stored === "en") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLocaleState(stored);
    }
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    window.localStorage.setItem(STORAGE_KEY, l);
    // Reflect on <html lang="..."> for assistive tech.
    document.documentElement.lang = l;
  }, []);

  const t = useCallback(
    (key: DictionaryKey, vars?: Record<string, string | number>) => {
      const dict = dictionaries[locale];
      const template = dict[key];
      if (template === undefined) {
        if (process.env.NODE_ENV !== "production") {
          console.warn(`[i18n] missing key for locale=${locale}: ${key}`);
        }
        return key;
      }
      return format(template, vars);
    },
    [locale],
  );

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used inside <LocaleProvider>");
  }
  return ctx;
}

/** Shortcut when only the translator function is needed. */
export function useT() {
  return useLocale().t;
}
