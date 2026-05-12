"use client";

/**
 * Chat screen — single conversation, message history + input.
 *
 * For G2.1 the round-trip is synchronous: we POST the user's message
 * and wait for the assistant's full reply before rendering it. Adding
 * SSE streaming in G2.2 is a swap of the mutation body — the surface
 * doesn't change.
 *
 * UX details that matter
 * ----------------------
 *
 *   * Auto-scroll to the bottom on new messages so the user never
 *     has to chase the typing indicator. We attach a ref to a
 *     trailing sentinel and ``scrollIntoView`` it on data change.
 *   * Optimistic rendering: while ``sendMessage`` is pending we show
 *     the user's message immediately and a "Thinking…" placeholder
 *     in the agent's slot. If the request fails, we drop both and
 *     toast.
 *   * The input grows with content up to ~6 lines, then scrolls.
 *     Cmd/Ctrl+Enter sends; plain Enter inserts a newline.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Send, Sparkles, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import {
  deleteConversation,
  getConversation,
  sendMessage,
} from "@/lib/agent-actions";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { MessagePublic } from "@/types/agent";

export default function ConversationPage() {
  const t = useT();
  const router = useRouter();
  const qc = useQueryClient();
  const params = useParams<{ id: string }>();
  const conversationId = params.id;

  const { data, isLoading, error } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => getConversation(conversationId),
    retry: false,
  });

  const [input, setInput] = useState("");
  // Optimistic record of the user's message while the agent is
  // thinking. We don't optimistically render the agent reply — that's
  // what the spinner is for.
  const [pendingUser, setPendingUser] = useState<string | null>(null);

  const sendMut = useMutation({
    mutationFn: (content: string) => sendMessage(conversationId, content),
    onMutate: (content) => setPendingUser(content),
    onSuccess: (resp) => {
      // Append both new messages to the cached detail without a refetch.
      qc.setQueryData<typeof data>(["conversation", conversationId], (prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: [...prev.messages, resp.user_message, resp.assistant_message],
        };
      });
      setPendingUser(null);
      setInput("");
    },
    onError: (e) => {
      setPendingUser(null);
      toast.error(
        e instanceof ApiError ? e.message : t("agent.chat.send_failed"),
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteConversation(conversationId),
    onSuccess: () => {
      toast.success(t("agent.chat.deleted"));
      // Bounce back to the dataset the conversation was on.
      if (data?.conversation.dataset_id) {
        router.push(`/datasets/${data.conversation.dataset_id}`);
      } else {
        router.push("/datasets");
      }
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : t("common.something_went_wrong"));
    },
  });

  // Auto-scroll on new messages / pending state.
  const bottomRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [data?.messages.length, pendingUser, sendMut.isPending]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const v = input.trim();
    if (!v || sendMut.isPending) return;
    sendMut.mutate(v);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit(e);
    }
  }

  if (isLoading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center py-16">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Button variant="ghost" size="sm" render={<Link href="/datasets" />}>
          <ArrowLeft className="size-4" />
          {t("agent.chat.back")}
        </Button>
        <Card>
          <CardContent className="text-destructive py-12 text-center text-sm">
            {notFound ? t("agent.chat.not_found") : t("agent.chat.load_failed")}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;
  const { conversation, messages } = data;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Button
            variant="ghost"
            size="sm"
            render={<Link href={`/datasets/${conversation.dataset_id}`} />}
          >
            <ArrowLeft className="size-4" />
            {t("agent.chat.back")}
          </Button>
          <h1 className="mt-1 truncate text-xl font-semibold tracking-tight">
            {conversation.title ?? t("agent.list.untitled")}
          </h1>
          <p className="text-muted-foreground text-xs">
            {conversation.model}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (window.confirm(t("agent.chat.confirm_delete"))) {
              deleteMut.mutate();
            }
          }}
          disabled={deleteMut.isPending}
        >
          <Trash2 className="size-3.5" />
          {t("agent.chat.delete")}
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.length === 0 && pendingUser === null ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <div className="bg-muted flex size-12 items-center justify-center rounded-full">
                <Sparkles className="text-muted-foreground size-6" />
              </div>
              <h2 className="text-base font-semibold">{t("agent.chat.empty.title")}</h2>
              <p className="text-muted-foreground mx-auto max-w-md text-sm">
                {t("agent.chat.empty.body")}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {pendingUser !== null && (
              <MessageBubble
                message={{
                  id: "pending-user",
                  conversation_id: conversation.id,
                  role: "user",
                  content: pendingUser,
                  token_usage: null,
                  created_at: new Date().toISOString(),
                }}
              />
            )}
            {sendMut.isPending && (
              <div className="text-muted-foreground flex items-center gap-2 px-3 text-xs">
                <Loader2 className="size-3.5 animate-spin" />
                {t("agent.chat.sending")}
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={onSubmit} className="space-y-1">
        <div className="bg-background flex items-end gap-2 rounded-lg border p-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("agent.chat.input_placeholder")}
            disabled={sendMut.isPending}
            rows={1}
            className="bg-transparent max-h-40 min-h-9 flex-1 resize-none px-1 py-1.5 text-sm outline-none disabled:opacity-60"
          />
          <Button
            type="submit"
            size="sm"
            disabled={sendMut.isPending || input.trim().length === 0}
          >
            {sendMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            {t("agent.chat.send")}
          </Button>
        </div>
        <p className="text-muted-foreground px-1 text-xs">⌘/Ctrl + Enter</p>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: MessagePublic }) {
  const t = useT();
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] space-y-1 rounded-lg px-3 py-2 text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        <div className="text-xs font-medium opacity-70">
          {isUser ? t("agent.chat.you") : t("agent.chat.agent")}
        </div>
        <div className="whitespace-pre-wrap">{message.content}</div>
        {message.token_usage && (
          <div className="text-[10px] opacity-60">
            {t("agent.chat.tokens", { total: message.token_usage.total })}
          </div>
        )}
      </div>
    </div>
  );
}
