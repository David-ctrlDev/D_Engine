/**
 * TypeScript mirrors of the Pydantic schemas in
 * `backend/app/data/schemas.py`. Kept in sync by hand — the surface
 * is intentionally small for slice A.
 */

export type DataSourceKind = "postgres" | "mssql" | "mssql_azure" | "csv" | "parquet" | "xlsx";

export type DatasetKind = "table" | "file_sheet" | "query";

export type DatasetVisibility = "private" | "shared_workspace" | "shared_specific";

export interface DataSourcePublic {
  id: string;
  name: string;
  kind: DataSourceKind;
  created_at: string;
  last_tested_at: string | null;
  last_test_status: string | null;
}

export interface DatasetSummary {
  id: string;
  name: string;
  kind: DatasetKind;
  visibility: DatasetVisibility;
  row_count_estimate: number | null;
  created_at: string;
  source_id: string;
  source_name: string;
  source_kind: DataSourceKind;
}

export interface DatasetColumn {
  name: string;
  dtype: string;
  nullable: boolean;
  sample_values: string[];
}

export interface DatasetDetail {
  id: string;
  name: string;
  kind: DatasetKind;
  visibility: DatasetVisibility;
  row_count_estimate: number | null;
  created_at: string;
  source: DataSourcePublic;
  columns: DatasetColumn[];
  sample_rows: Record<string, unknown>[];
}

export interface DatasetCreatedResponse {
  dataset: DatasetSummary;
  columns: DatasetColumn[];
}

export interface DatasetListResponse {
  datasets: DatasetSummary[];
}

// ----- Database sources --------------------------------------------------

export interface DatabaseConnectionPayload {
  kind: "postgres" | "mssql" | "mssql_azure";
  name: string;
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  sslmode: string;
}

export interface ConnectionTestResponse {
  ok: boolean;
  error: string | null;
}

export interface TableInfo {
  schema: string;
  name: string;
  estimated_rows: number | null;
}

export interface TablesListResponse {
  tables: TableInfo[];
}

export interface ImportTableRequest {
  schema: string;
  table: string;
  dataset_name?: string | null;
}

export interface ImportTablesResponse {
  datasets: DatasetSummary[];
}

export interface DataSourceListResponse {
  sources: DataSourcePublic[];
}

// ----- Profiling (slice E) -----------------------------------------------

export interface ColumnProfile {
  name: string;
  dtype: string;
  null_count: number;
  null_pct: number;
  distinct_count: number | null;
  min: string | null;
  max: string | null;
  top_values: { value: string; count: number }[];
}

export interface DatasetProfile {
  id: string;
  dataset_id: string;
  status: "running" | "completed" | "failed";
  row_count: number | null;
  columns: ColumnProfile[];
  started_at: string;
  completed_at: string | null;
  error: string | null;
}

// ----- Sharing (slice F) -------------------------------------------------

export interface DatasetGrantPublic {
  id: string;
  user_id: string;
  user_email: string;
  granted_at: string;
}

export interface DatasetGrantsResponse {
  grants: DatasetGrantPublic[];
}

export interface WorkspaceMember {
  user_id: string;
  email: string;
  role: "owner" | "admin" | "member";
}

export interface WorkspaceMembersResponse {
  members: WorkspaceMember[];
}

export interface UpdateVisibilityRequest {
  visibility: DatasetVisibility;
}
