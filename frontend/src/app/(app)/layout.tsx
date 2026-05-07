"use client";

/**
 * Authenticated app layout — sidebar + topbar + content. Gates on
 * `useCurrentUser`: an unauthenticated visitor is bounced to /login.
 *
 * The redirect runs in an effect so SSR doesn't try to navigate during
 * render. While the query is loading we show a thin spinner row to
 * avoid flashing the unauthenticated layout for half a second.
 */

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { useCurrentUser } from "@/hooks/use-current-user";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useCurrentUser();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && data === null) {
      router.replace("/login");
    }
  }, [isLoading, data, router]);

  if (isLoading || !data) {
    return (
      <div className="text-muted-foreground flex min-h-screen items-center justify-center">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar user={data.user} tenant={data.tenant} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
