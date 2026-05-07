/**
 * Zod schemas for the auth forms.
 *
 * Validation here is a UX hint — the backend re-checks everything.
 * Password strength specifically is delegated entirely to the backend
 * (zxcvbn) so the frontend doesn't need to ship the wordlist.
 */

import { z } from "zod";

const email = z.string().email("Enter a valid email address.");

const minPassword = z
  .string()
  .min(12, "Password must be at least 12 characters long.")
  .max(200, "Password is too long.");

export const registerSchema = z.object({
  email,
  password: minPassword,
  workspace_name: z
    .string()
    .min(1, "Workspace name is required.")
    .max(120, "Workspace name is too long."),
});
export type RegisterFormValues = z.infer<typeof registerSchema>;

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Password is required."),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

export const mfaCodeSchema = z.object({
  code: z
    .string()
    .min(1, "Enter a code.")
    .max(64, "Code is too long.")
    // Accept either 6 digits (TOTP) or a recovery code with hyphens.
    .regex(/^[0-9A-Za-z\- ]+$/, "Only digits, letters, hyphens and spaces."),
});
export type MFACodeFormValues = z.infer<typeof mfaCodeSchema>;

export const forgotPasswordSchema = z.object({ email });
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: minPassword,
    confirm_password: z.string().min(1, "Confirm your password."),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export const mfaSetupConfirmSchema = z.object({
  code: z.string().regex(/^\d{6}$/, "Enter the 6-digit code from your app."),
});
export type MFASetupConfirmFormValues = z.infer<typeof mfaSetupConfirmSchema>;

export const mfaDisableSchema = z.object({
  password: z.string().min(1, "Password is required."),
  code: z.string().regex(/^\d{6}$/, "Enter the 6-digit code from your app."),
});
export type MFADisableFormValues = z.infer<typeof mfaDisableSchema>;
