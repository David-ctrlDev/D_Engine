"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import type { SessionInfo } from "@/types/auth";

const SESSIONS_QUERY_KEY = ["auth", "sessions"] as const;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function SessionsTable() {
  const queryClient = useQueryClient();
  const sessionsQuery = useQuery({
    queryKey: SESSIONS_QUERY_KEY,
    queryFn: () => authApi.sessionsList(),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => authApi.sessionRevoke(id),
    onSuccess: () => {
      toast.success("Session revoked.");
      queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : "Failed to revoke.");
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Active sessions</CardTitle>
        <CardDescription>
          Each session corresponds to one login. Revoking a session signs out that browser / device.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessionsQuery.isLoading && (
          <p className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading…
          </p>
        )}
        {sessionsQuery.error && (
          <p className="text-destructive text-sm">Failed to load sessions.</p>
        )}
        {sessionsQuery.data && (
          <ul className="divide-y">
            {sessionsQuery.data.sessions.length === 0 && (
              <li className="text-muted-foreground py-4 text-sm">No active sessions.</li>
            )}
            {sessionsQuery.data.sessions.map((s: SessionInfo) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {s.user_agent ?? "Unknown device"}
                    </span>
                    {s.is_current && <Badge variant="secondary">This session</Badge>}
                  </div>
                  <p className="text-muted-foreground text-xs">
                    From {s.ip ?? "unknown"} · started {formatDate(s.created_at)} · expires{" "}
                    {formatDate(s.expires_at)}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={s.is_current || revokeMutation.isPending}
                  onClick={() => revokeMutation.mutate(s.id)}
                >
                  {s.is_current ? "Current" : "Revoke"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
