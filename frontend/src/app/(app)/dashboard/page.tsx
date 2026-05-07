"use client";

/**
 * Placeholder for the post-login landing.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useT } from "@/lib/i18n/provider";

export default function DashboardPage() {
  const t = useT();
  const { data } = useCurrentUser();
  if (!data) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("dashboard.greeting", { email: data.user.email })}
        </h1>
        <p className="text-muted-foreground text-sm">
          {t("dashboard.workspace_label")} <span className="font-medium">{data.tenant.name}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.welcome_title")}</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground space-y-2 text-sm">
          <p>{t("dashboard.welcome_body_a")}</p>
          <p>{t("dashboard.welcome_body_b")}</p>
        </CardContent>
      </Card>
    </div>
  );
}
