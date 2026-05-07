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
  DatasetCreatedResponse,
  DatasetDetail,
  DatasetListResponse,
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
