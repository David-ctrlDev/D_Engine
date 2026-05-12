/**
 * TypeScript mirrors of the Pydantic schemas in
 * ``backend/app/llm/schemas.py``. Hand-synced; the surface is small
 * and stable — providers and member-access modes change very rarely.
 */

export type LlmProviderKind = "anthropic" | "openai" | "google" | "ollama";

export type LlmMemberAccess = "admins_only" | "all_members" | "specific_members";

export interface ModelOption {
  id: string;
  label: string;
  notes: string | null;
}

export interface ProviderInfo {
  kind: LlmProviderKind;
  display_name: string;
  description: string;
  api_key_docs_url: string;
  needs_base_url: boolean;
  default_model: string;
  models: ModelOption[];
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
}

export interface LlmCredentialPublic {
  id: string;
  provider: LlmProviderKind;
  nickname: string;
  model_default: string | null;
  base_url: string | null;
  member_access: LlmMemberAccess;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_error: string | null;
  created_at: string;
}

export interface LlmCredentialListResponse {
  credentials: LlmCredentialPublic[];
}

export interface LlmCredentialCreateRequest {
  provider: LlmProviderKind;
  nickname: string;
  api_key: string;
  model_default?: string | null;
  base_url?: string | null;
  member_access: LlmMemberAccess;
}

export interface LlmCredentialUpdateRequest {
  nickname?: string | null;
  api_key?: string | null;
  model_default?: string | null;
  base_url?: string | null;
  member_access?: LlmMemberAccess | null;
}

export interface TestConnectionRequest {
  provider: LlmProviderKind;
  api_key: string;
  base_url?: string | null;
}

export interface TestConnectionResponse {
  ok: boolean;
  error: string | null;
  /**
   * Live model list parsed from the provider's ``/models`` response.
   * Empty when the probe failed; the UI falls back to its curated
   * static catalogue (the one shipped by ``GET /llm-providers``) in
   * that case.
   */
  models: ModelOption[];
}

export interface LlmCredentialGrantPublic {
  id: string;
  user_id: string;
  user_email: string;
  granted_at: string;
}

export interface LlmCredentialGrantsResponse {
  grants: LlmCredentialGrantPublic[];
}
