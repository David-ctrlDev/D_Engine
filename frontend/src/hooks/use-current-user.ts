"use client";

/**
 * `useCurrentUser` — TanStack Query around /api/v1/auth/me.
 *
 * The query is the single source of truth for "is anyone logged in?". A
 * 401 from the API resolves to ``data === null`` (not an error) so guards
 * can branch on the value without juggling `error` state.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { authApi } from "@/lib/auth-actions";
import type { LoginSuccessResponse } from "@/types/auth";

export const CURRENT_USER_QUERY_KEY = ["auth", "me"] as const;

export function useCurrentUser(): UseQueryResult<LoginSuccessResponse | null> {
  return useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: async () => {
      try {
        return await authApi.me();
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          return null;
        }
        throw e;
      }
    },
    staleTime: 30_000,
    retry: false,
  });
}
