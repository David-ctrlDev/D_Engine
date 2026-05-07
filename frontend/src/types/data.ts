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
