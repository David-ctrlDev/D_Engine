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
  initial_message?: string | null;
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
