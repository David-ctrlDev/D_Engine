/**
 * API actions for the working-copy / transform engine.
 *
 * Same convention as the other ``*-actions`` modules — one helper per
 * endpoint. The backend lives at ``/api/v1/datasets/{id}/working-copy``.
 */

import { ApiError, api } from "@/lib/api";
import type {
  WorkingCopyOperationsResponse,
  WorkingCopySampleResponse,
  WorkingCopySummary,
} from "@/types/working-copy";

export async function getWorkingCopy(
  datasetId: string,
): Promise<WorkingCopySummary | null> {
  try {
    return await api.get<WorkingCopySummary>(
      `/api/v1/datasets/${datasetId}/working-copy`,
    );
  } catch (e) {
    // 404 means "no working copy yet" — that's the empty state, not an error.
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function getWorkingCopySample(
  datasetId: string,
): Promise<WorkingCopySampleResponse | null> {
  try {
    return await api.get<WorkingCopySampleResponse>(
      `/api/v1/datasets/${datasetId}/working-copy/sample`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function listWorkingCopyOperations(
  datasetId: string,
): Promise<WorkingCopyOperationsResponse | null> {
  try {
    return await api.get<WorkingCopyOperationsResponse>(
      `/api/v1/datasets/${datasetId}/working-copy/operations`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export interface UndoResponse {
  working_copy: WorkingCopySummary;
  undone_count: number;
}

/**
 * Roll the working copy back to *before* the given operation. Every
 * later operation also gets stamped as undone — you can't keep step
 * 3 if you reverted step 2.
 */
export async function undoOperation(
  datasetId: string,
  operationId: string,
): Promise<UndoResponse> {
  return api.post<UndoResponse>(
    `/api/v1/datasets/${datasetId}/working-copy/operations/${operationId}/undo`,
  );
}

/**
 * Discard every transformation, restoring the working copy to the
 * original CSV. The journal stays for the audit trail.
 */
export async function resetWorkingCopy(
  datasetId: string,
): Promise<UndoResponse> {
  return api.post<UndoResponse>(
    `/api/v1/datasets/${datasetId}/working-copy/reset`,
  );
}
