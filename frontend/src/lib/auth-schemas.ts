/**
 * Zod schemas for the auth forms.
 *
 * Each schema is built by a factory that takes the translator function so
 * validation messages render in the active locale. Strength validation is
 * delegated to the backend (zxcvbn); we only enforce shape and length here.
 */

import { z } from "zod";

import type { DictionaryKey } from "@/lib/i18n/dictionaries";

type T = (key: DictionaryKey) => string;

export function buildLoginSchema(t: T) {
  return z.object({
    email: z.string().email(t("auth.login.email_required")),
    password: z.string().min(1, t("auth.login.password_required")),
  });
}
export type LoginFormValues = z.infer<ReturnType<typeof buildLoginSchema>>;

export function buildRegisterSchema(t: T) {
  return z.object({
    email: z.string().email(t("auth.login.email_required")),
    password: z
      .string()
      .min(12, t("auth.register.password_too_short"))
      .max(200, t("auth.register.password_too_long")),
    workspace_name: z
      .string()
      .min(1, t("auth.register.workspace_required"))
      .max(120, t("auth.register.workspace_too_long")),
  });
}
export type RegisterFormValues = z.infer<ReturnType<typeof buildRegisterSchema>>;

export function buildMFACodeSchema(t: T) {
  return z.object({
    code: z
      .string()
      .min(1, t("auth.mfa.code_required"))
      .max(64, t("auth.mfa.code_too_long"))
      .regex(/^[0-9A-Za-z\- ]+$/, t("auth.mfa.code_charset")),
  });
}
export type MFACodeFormValues = z.infer<ReturnType<typeof buildMFACodeSchema>>;

export function buildForgotPasswordSchema(t: T) {
  return z.object({ email: z.string().email(t("auth.login.email_required")) });
}
export type ForgotPasswordFormValues = z.infer<ReturnType<typeof buildForgotPasswordSchema>>;

export function buildResetPasswordSchema(t: T) {
  return z
    .object({
      new_password: z
        .string()
        .min(12, t("auth.register.password_too_short"))
        .max(200, t("auth.register.password_too_long")),
      confirm_password: z.string().min(1, t("auth.reset.confirm_required")),
    })
    .refine((d) => d.new_password === d.confirm_password, {
      message: t("auth.reset.passwords_dont_match"),
      path: ["confirm_password"],
    });
}
export type ResetPasswordFormValues = z.infer<ReturnType<typeof buildResetPasswordSchema>>;

export function buildMFASetupConfirmSchema(t: T) {
  return z.object({
    code: z.string().regex(/^\d{6}$/, t("settings.mfa.scan.code_required")),
  });
}
export type MFASetupConfirmFormValues = z.infer<ReturnType<typeof buildMFASetupConfirmSchema>>;

export function buildMFADisableSchema(t: T) {
  return z.object({
    password: z.string().min(1, t("settings.mfa.disable.password_required")),
    code: z.string().regex(/^\d{6}$/, t("settings.mfa.disable.code_required")),
  });
}
export type MFADisableFormValues = z.infer<ReturnType<typeof buildMFADisableSchema>>;
