/**
 * TypeScript mirrors of the Pydantic schemas in
 * ``backend/app/agent/schemas.py``.
 */

import type { LlmProviderKind } from "@/types/llm";

export type AgentMessageRole = "user" | "assistant" | "system";

export interface ConversationPublic {
  id: string;
  dataset_id: string;
  credential_id: string;
  model: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationPublic[];
}

/**
 * Inline visual blocks the agent can attach to a turn. The agent loop
 * builds these server-side from operation results (histograms,
 * before/after bars) or from pending-action proposals. Each shape is
 * dispatched to a React component in ``MessageVisuals``.
 *
 * Stays as an open ``{kind, ...}`` union so we can add new viz types
 * without breaking the wire format.
 */
export type Visualization =
  | {
      kind: "histogram";
      column: string;
      bins: Array<{ label: string; count: number }>;
    }
  | {
      kind: "value_counts";
      column: string;
      items: Array<{ value: string; count: number }>;
    }
  | {
      kind: "null_pct";
      column: string;
      null_count: number;
      total: number;
      null_pct: number;
    }
  | {
      kind: "before_after";
      label: string;
      before: number;
      after: number;
      delta_label: string;
      tone?: "positive" | "neutral" | "warning";
    }
  | {
      kind: "duplicate_preview";
      columns: string[];
      duplicate_groups: number;
      total_duplicates: number;
      example_groups: Array<{
        key: Record<string, string | null>;
        count: number;
      }>;
    }
  | {
      kind: "pending_action";
      tool_call_id: string;
      tool_name: string;
      args: Record<string, unknown>;
    }
  | {
      kind: "fillna_summary";
      total_filled: number;
      filled: Array<{
        column: string;
        strategy: string;
        value: string;
        filled_count: number;
      }>;
    }
  | {
      kind: "normalize_text_summary";
      applied: Array<{
        column: string;
        case: string;
        strip: boolean;
        collapse_spaces: boolean;
        remove_accents: boolean;
        distinct_before: number;
        distinct_after: number;
        collapsed_variants: number;
      }>;
    }
  | {
      kind: "parse_dates_summary";
      results: Array<{
        column: string;
        matched_format: string | null;
        parsed_count: number;
        failed_count: number;
        skipped: boolean;
      }>;
    }
  | {
      kind: "normalize_numeric_summary";
      results: Array<{
        column: string;
        decimal?: string;
        converted_count: number;
        failed_count: number;
        skipped: boolean;
        reason?: string;
      }>;
    };

export interface MessagePublic {
  id: string;
  conversation_id: string;
  role: AgentMessageRole;
  content: string;
  /**
   * Intent-capture chips the agent attached to this turn. The UI
   * renders them as buttons below the message; clicking one sends
   * its text as the next user message. Only ever set on
   * ``assistant`` rows; ``null`` for user/system turns.
   */
  suggestions: string[] | null;
  /**
   * Typed visualizations rendered inline after the message text.
   * ``null`` for plain-text turns.
   */
  visualizations: Visualization[] | null;
  /**
   * Names of tools the agent actually executed on this turn — the
   * server's ground truth of what really ran (not what the agent
   * might claim in its text). Empty means "nothing ran, this is
   * a pure text turn".
   */
  executed_tools: string[];
  token_usage: { prompt: number; completion: number; total: number } | null;
  created_at: string;
}

export interface ConversationDetail {
  conversation: ConversationPublic;
  messages: MessagePublic[];
}

export interface ConversationCreateRequest {
  credential_id: string;
  model: string;
  /**
   * When ``true`` (default), the backend immediately runs the agent's
   * opening turn — the chat lands populated with the diagnosis +
   * intent chips. Set ``false`` only if you want a blank conversation
   * for some reason (we don't, currently).
   */
  kickoff?: boolean;
}

export interface SendMessageRequest {
  content: string;
}

export interface SendMessageResponse {
  /**
   * The user's message we just persisted. ``null`` when the response
   * comes from a button click (accepting / rejecting a pending
   * action) instead of typed text.
   */
  user_message: MessagePublic | null;
  /**
   * The assistant turn(s) the agent loop produced. Often one, but
   * can be multiple when the agent had to call inspection tools
   * before giving a final answer.
   */
  assistant_messages: MessagePublic[];
}

export interface ResolvePendingActionRequest {
  message_id: string;
  accept: boolean;
}

export interface UsableCredential {
  id: string;
  nickname: string;
  provider: LlmProviderKind;
  model_default: string | null;
}

export interface UsableCredentialsResponse {
  credentials: UsableCredential[];
}
