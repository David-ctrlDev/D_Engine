/**
 * API actions for the data domain.
 *
 * One function per backend endpoint, each returning a typed response
 * (see `types/data.ts`). Errors propagate as `ApiError` from the
 * underlying `api` client, so React Query's `onError` and `error`
 * states already see them.
 */

import { api } from "@/lib/api";
import type {
  ConnectionTestResponse,
  DatabaseConnectionPayload,
  DatasetCreatedResponse,
  DatasetDetail,
  DatasetGrantsResponse,
  DatasetListResponse,
  DatasetProfile,
  DataSourceListResponse,
  DataSourcePublic,
  DatasetVisibility,
  ImportTableRequest,
  ImportTablesResponse,
  TablesListResponse,
  WorkspaceMembersResponse,
} from "@/types/data";

export async function uploadDataset(
  file: File,
  datasetName: string,
): Promise<DatasetCreatedResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dataset_name", datasetName);
  return api.postMultipart<DatasetCreatedResponse>("/api/v1/sources/upload", fd);
}

export async function listDatasets(): Promise<DatasetListResponse> {
  return api.get<DatasetListResponse>("/api/v1/datasets");
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  return api.get<DatasetDetail>(`/api/v1/datasets/${id}`);
}

// ----- Database sources --------------------------------------------------

export async function listSources(): Promise<DataSourceListResponse> {
  return api.get<DataSourceListResponse>("/api/v1/sources");
}

export async function testConnection(
  payload: DatabaseConnectionPayload,
): Promise<ConnectionTestResponse> {
  return api.post<ConnectionTestResponse>("/api/v1/sources/test", payload);
}

export async function createDatabaseSource(
  payload: DatabaseConnectionPayload,
): Promise<DataSourcePublic> {
  return api.post<DataSourcePublic>("/api/v1/sources/database", payload);
}

export async function listSourceTables(sourceId: string): Promise<TablesListResponse> {
  return api.get<TablesListResponse>(`/api/v1/sources/${sourceId}/tables`);
}

export async function importTables(
  sourceId: string,
  tables: ImportTableRequest[],
): Promise<ImportTablesResponse> {
  return api.post<ImportTablesResponse>(`/api/v1/sources/${sourceId}/import`, { tables });
}

// ----- Profiling (slice E) ----------------------------------------------

export async function runProfile(datasetId: string): Promise<DatasetProfile> {
  return api.post<DatasetProfile>(`/api/v1/datasets/${datasetId}/profile`);
}

export async function getLatestProfile(datasetId: string): Promise<DatasetProfile | null> {
  try {
    return await api.get<DatasetProfile>(`/api/v1/datasets/${datasetId}/profile`);
  } catch (e) {
    // 404 = no profile yet; let caller treat as "not run".
    if (e instanceof Error && "status" in e && (e as { status: number }).status === 404) {
      return null;
    }
    throw e;
  }
}

// ----- Sharing (slice F) -------------------------------------------------

export async function updateVisibility(
  datasetId: string,
  visibility: DatasetVisibility,
): Promise<void> {
  await api.patch(`/api/v1/datasets/${datasetId}`, { visibility });
}

export async function listGrants(datasetId: string): Promise<DatasetGrantsResponse> {
  return api.get<DatasetGrantsResponse>(`/api/v1/datasets/${datasetId}/grants`);
}

export async function addGrant(datasetId: string, userId: string): Promise<void> {
  await api.post(`/api/v1/datasets/${datasetId}/grants`, { user_id: userId });
}

export async function removeGrant(datasetId: string, userId: string): Promise<void> {
  await api.delete(`/api/v1/datasets/${datasetId}/grants/${userId}`);
}

export async function listWorkspaceMembers(): Promise<WorkspaceMembersResponse> {
  return api.get<WorkspaceMembersResponse>("/api/v1/workspace/members");
}
