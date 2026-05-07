"use client";

/**
 * Theme provider — thin wrapper around `next-themes` so we can swap the
 * implementation later without touching every consumer.
 *
 * `attribute="class"` puts `class="dark"` on the <html> element, which is
 * what Tailwind 4's `dark:` variant reads.
 */

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

type Props = ComponentProps<typeof NextThemesProvider>;

export function ThemeProvider({ children, ...rest }: Props) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...rest}
    >
      {children}
    </NextThemesProvider>
  );
}
