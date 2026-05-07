/**
 * Typed wrappers around every /api/v1/auth/* endpoint the UI needs.
 *
 * Keeping the URL strings centralised here means a future API rename
 * (e.g. /api/v1 -> /api/v2) is a one-file change and the rest of the
 * frontend only depends on the named functions.
 */

import { api } from "@/lib/api";
import type {
  ForgotPasswordRequest,
  LoginRequest,
  LoginResponse,
  LoginSuccessResponse,
  MessageResponse,
  MFAConfirmRequest,
  MFAConfirmResponse,
  MFADisableRequest,
  MFASetupResponse,
  MFAVerifyRequest,
  RegisterRequest,
  RegisterResponse,
  ResetPasswordRequest,
  SessionListResponse,
  VerifyEmailRequest,
  VerifyEmailResponse,
} from "@/types/auth";

const BASE = "/api/v1/auth";

export const authApi = {
  register: (body: RegisterRequest) => api.post<RegisterResponse>(`${BASE}/register`, body),
  verifyEmail: (body: VerifyEmailRequest) =>
    api.post<VerifyEmailResponse>(`${BASE}/verify-email`, body),
  login: (body: LoginRequest) => api.post<LoginResponse>(`${BASE}/login`, body),
  mfaVerify: (body: MFAVerifyRequest) => api.post<LoginSuccessResponse>(`${BASE}/mfa/verify`, body),
  refresh: () => api.post<MessageResponse>(`${BASE}/refresh`),
  logout: () => api.post<MessageResponse>(`${BASE}/logout`),
  me: () => api.get<LoginSuccessResponse>(`${BASE}/me`),

  passwordForgot: (body: ForgotPasswordRequest) =>
    api.post<MessageResponse>(`${BASE}/password/forgot`, body),
  passwordReset: (body: ResetPasswordRequest) =>
    api.post<MessageResponse>(`${BASE}/password/reset`, body),

  mfaSetup: () => api.post<MFASetupResponse>(`${BASE}/mfa/setup`),
  mfaSetupConfirm: (body: MFAConfirmRequest) =>
    api.post<MFAConfirmResponse>(`${BASE}/mfa/setup/confirm`, body),
  mfaDisable: (body: MFADisableRequest) => api.post<MessageResponse>(`${BASE}/mfa/disable`, body),

  sessionsList: () => api.get<SessionListResponse>(`${BASE}/sessions`),
  sessionRevoke: (sessionId: string) =>
    api.delete<MessageResponse>(`${BASE}/sessions/${sessionId}`),
};
