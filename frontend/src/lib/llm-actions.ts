/**
 * API actions for the LLM-credential domain.
 *
 * One module per backend domain, same convention as ``data-actions.ts``
 * and ``auth-actions.ts``. The router on the backend lives at
 * ``/api/v1/llm-{providers,credentials}``.
 */

import { api } from "@/lib/api";
import type {
  LlmCredentialCreateRequest,
  LlmCredentialGrantPublic,
  LlmCredentialGrantsResponse,
  LlmCredentialListResponse,
  LlmCredentialPublic,
  LlmCredentialUpdateRequest,
  ProvidersResponse,
  TestConnectionRequest,
  TestConnectionResponse,
} from "@/types/llm";

// ----- Provider catalogue (read-only) -----------------------------------

export async function listProviders(): Promise<ProvidersResponse> {
  return api.get<ProvidersResponse>("/api/v1/llm-providers");
}

// ----- Credentials CRUD -------------------------------------------------

export async function listCredentials(): Promise<LlmCredentialListResponse> {
  return api.get<LlmCredentialListResponse>("/api/v1/llm-credentials");
}

export async function createCredential(
  payload: LlmCredentialCreateRequest,
): Promise<LlmCredentialPublic> {
  return api.post<LlmCredentialPublic>("/api/v1/llm-credentials", payload);
}

export async function updateCredential(
  credentialId: string,
  payload: LlmCredentialUpdateRequest,
): Promise<LlmCredentialPublic> {
  return api.patch<LlmCredentialPublic>(`/api/v1/llm-credentials/${credentialId}`, payload);
}

export async function deleteCredential(credentialId: string): Promise<void> {
  await api.delete(`/api/v1/llm-credentials/${credentialId}`);
}

// ----- Test connection --------------------------------------------------

/**
 * Test an *unsaved* credential — the new-credential form calls this
 * before persisting so the admin sees a green tick before clicking Save.
 */
export async function testUnsavedCredential(
  payload: TestConnectionRequest,
): Promise<TestConnectionResponse> {
  return api.post<TestConnectionResponse>("/api/v1/llm-credentials/test", payload);
}

/**
 * Re-test a credential that's already persisted (admin-only on the
 * backend). The server decrypts the stored key, pings the provider,
 * and stamps ``last_tested_at`` so the UI shows freshness.
 */
export async function testSavedCredential(
  credentialId: string,
): Promise<TestConnectionResponse> {
  return api.post<TestConnectionResponse>(`/api/v1/llm-credentials/${credentialId}/test`);
}

// ----- Per-credential grants -------------------------------------------

export async function listCredentialGrants(
  credentialId: string,
): Promise<LlmCredentialGrantsResponse> {
  return api.get<LlmCredentialGrantsResponse>(`/api/v1/llm-credentials/${credentialId}/grants`);
}

export async function addCredentialGrant(
  credentialId: string,
  userId: string,
): Promise<LlmCredentialGrantPublic> {
  return api.post<LlmCredentialGrantPublic>(
    `/api/v1/llm-credentials/${credentialId}/grants`,
    { user_id: userId },
  );
}

export async function removeCredentialGrant(
  credentialId: string,
  userId: string,
): Promise<void> {
  await api.delete(`/api/v1/llm-credentials/${credentialId}/grants/${userId}`);
}
