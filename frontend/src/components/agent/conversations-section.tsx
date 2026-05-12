"use client";

/**
 * "Conversations" panel on the dataset-detail page.
 *
 * Shows the calling user's conversations on this dataset (RLS already
 * filters; everyone else's are invisible), plus a CTA to start a new
 * one. Empty state explains what the agent does in plain language so
 * non-technical users know it's worth pressing the button.
 *
 * Clicking a row navigates to ``/conversations/{id}``.
 */

import { useQuery } from "@tanstack/react-query";
import { Loader2, MessageSquare, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { StartConversationDialog } from "@/components/agent/start-conversation-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listConversations } from "@/lib/agent-actions";
import { useT } from "@/lib/i18n/provider";

export function ConversationsSection({ datasetId }: { datasetId: string }) {
  const t = useT();
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["dataset-conversations", datasetId],
    queryFn: () => listConversations(datasetId),
  });

  const conversations = data?.conversations ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquare className="size-4" />
          {t("agent.list.title")}
        </CardTitle>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Sparkles className="size-3.5" />
          {t("agent.cta.button")}
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-muted-foreground flex justify-center py-6">
            <Loader2 className="size-4 animate-spin" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-muted-foreground py-6 text-center text-sm">
            {t("agent.list.empty")}
          </p>
        ) : (
          <ul className="divide-border divide-y rounded-md border">
            {conversations.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/conversations/${c.id}`}
                  className="hover:bg-muted/40 flex items-center justify-between px-3 py-2 text-sm transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate">{c.title ?? t("agent.list.untitled")}</div>
                    <div className="text-muted-foreground text-xs">
                      {c.model} ·{" "}
                      {new Date(c.updated_at).toLocaleString()}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <StartConversationDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        datasetId={datasetId}
      />
    </Card>
  );
}
