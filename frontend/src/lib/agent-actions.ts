/**
 * API actions for the agent-conversation domain.
 *
 * Same convention as ``data-actions`` / ``llm-actions``: one module per
 * backend domain. Endpoint paths mirror ``app.agent.routes`` exactly.
 */

import { api } from "@/lib/api";
import type {
  ConversationCreateRequest,
  ConversationDetail,
  ConversationListResponse,
  SendMessageResponse,
  UsableCredentialsResponse,
} from "@/types/agent";

// ----- Credential picker for the "start conversation" modal -------------

export async function listUsableCredentials(): Promise<UsableCredentialsResponse> {
  return api.get<UsableCredentialsResponse>("/api/v1/llm-credentials/usable");
}

// ----- Per-dataset conversation list + create ---------------------------

export async function listConversations(
  datasetId: string,
): Promise<ConversationListResponse> {
  return api.get<ConversationListResponse>(
    `/api/v1/datasets/${datasetId}/conversations`,
  );
}

export async function createConversation(
  datasetId: string,
  payload: ConversationCreateRequest,
): Promise<ConversationDetail> {
  return api.post<ConversationDetail>(
    `/api/v1/datasets/${datasetId}/conversations`,
    payload,
  );
}

// ----- Conversation detail + send message -------------------------------

export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return api.get<ConversationDetail>(`/api/v1/conversations/${conversationId}`);
}

export async function sendMessage(
  conversationId: string,
  content: string,
): Promise<SendMessageResponse> {
  return api.post<SendMessageResponse>(
    `/api/v1/conversations/${conversationId}/messages`,
    { content },
  );
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await api.delete(`/api/v1/conversations/${conversationId}`);
}
