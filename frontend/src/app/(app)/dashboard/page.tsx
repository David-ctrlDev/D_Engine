"use client";

/**
 * Placeholder for the post-login landing. The data-prep features (ingestion,
 * profiling, training-table builder, LLM-context bundle) live here in
 * subsequent iterations.
 */

import { useCurrentUser } from "@/hooks/use-current-user";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  const { data } = useCurrentUser();
  if (!data) return null; // gated by the layout

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Hello, {data.user.email}</h1>
        <p className="text-muted-foreground text-sm">
          Workspace: <span className="font-medium">{data.tenant.name}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Welcome to dataprep</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground space-y-2 text-sm">
          <p>
            Authentication is up and running. The data preparation features land in the next
            iterations: data source connectors, profiling, cleansing rules, ML training-table
            builder, and the LLM-context bundle exporter.
          </p>
          <p>
            For now, head to <strong>Security</strong> in the sidebar to set up multi-factor
            authentication.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
