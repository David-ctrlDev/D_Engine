/**
 * TypeScript mirrors of the Pydantic schemas in `backend/app/auth/schemas.py`.
 *
 * Kept in sync by hand — the surface is small (~10 types). If the API
 * grows we'll generate this from OpenAPI instead.
 */

export type TenantRole = "owner" | "admin" | "member";

export interface UserPublic {
  id: string;
  email: string;
  is_verified: boolean;
}

export interface TenantPublic {
  id: string;
  slug: string;
  name: string;
  role: TenantRole;
}

export interface RegisterRequest {
  email: string;
  password: string;
  workspace_name: string;
}

export interface RegisterResponse {
  user_id: string;
  tenant_id: string;
  tenant_slug: string;
  message: string;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface VerifyEmailResponse {
  user_id: string;
  verified: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginSuccessResponse {
  user: UserPublic;
  tenant: TenantPublic;
  mfa_required: false;
}

export interface LoginMFARequiredResponse {
  mfa_required: true;
  mfa_token: string;
}

export type LoginResponse = LoginSuccessResponse | LoginMFARequiredResponse;

export interface MFAVerifyRequest {
  mfa_token: string;
  code: string;
}

export interface MFASetupResponse {
  secret: string;
  qr_data_uri: string;
}

export interface MFAConfirmRequest {
  code: string;
}

export interface MFAConfirmResponse {
  recovery_codes: string[];
  message: string;
}

export interface MFADisableRequest {
  password: string;
  code: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  expires_at: string;
  user_agent: string | null;
  ip: string | null;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: SessionInfo[];
}

export interface MessageResponse {
  message: string;
}
