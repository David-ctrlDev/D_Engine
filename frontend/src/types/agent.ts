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
  user_message: MessagePublic;
  assistant_message: MessagePublic;
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
