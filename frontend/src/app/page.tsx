"use client";

/**
 * Root route. Redirects to /dashboard if logged in, /login otherwise.
 */

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useCurrentUser } from "@/hooks/use-current-user";

export default function Home() {
  const { data, isLoading } = useCurrentUser();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(data ? "/dashboard" : "/login");
  }, [data, isLoading, router]);

  return (
    <div className="text-muted-foreground flex min-h-screen items-center justify-center">
      <Loader2 className="size-5 animate-spin" />
    </div>
  );
}
