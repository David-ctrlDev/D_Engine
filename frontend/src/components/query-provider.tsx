"use client";

/**
 * TanStack Query provider. Lives behind a client component so the
 * `QueryClient` is created in the browser process — sharing one across
 * server requests would leak data between users.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Auth-sensitive data — refetch on focus is helpful.
            refetchOnWindowFocus: true,
            // Keep results fresh briefly so quick navigations feel snappy.
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
