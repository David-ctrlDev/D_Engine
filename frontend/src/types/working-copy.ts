/**
 * TypeScript mirrors of the Pydantic schemas in
 * ``backend/app/transforms/routes.py``.
 *
 * The "working copy" is the user's per-dataset draft that the agent
 * transforms. The endpoints surface its current state (sample rows,
 * row/column counts) and the journal of operations applied so far.
 */

export interface WorkingCopySummary {
  id: string;
  dataset_id: string;
  snapshot_path: string;
  row_count: number | null;
  column_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkingCopySampleResponse {
  working_copy_id: string;
  columns: Array<{ name: string; dtype: string }>;
  rows: Array<Record<string, unknown>>;
  row_count: number;
  column_count: number;
}

export interface WorkingCopyOperationPublic {
  id: string;
  op: string;
  args: Record<string, unknown>;
  rows_before: number | null;
  rows_after: number | null;
  result_summary: Record<string, unknown> | null;
  conversation_id: string | null;
  message_id: string | null;
  created_at: string;
  undone_at: string | null;
}

export interface WorkingCopyOperationsResponse {
  operations: WorkingCopyOperationPublic[];
}
