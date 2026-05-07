/**
 * Component test for LoginForm. Stubs ``authApi.login``; checks both
 * the successful-login path and the MFA-required branch.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/auth/login-form";
import { LocaleProvider } from "@/lib/i18n/provider";

const replace = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
}));

const loginMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth-actions", () => ({
  authApi: { login: loginMock },
}));

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <LocaleProvider>
      <QueryClientProvider client={client}>
        <LoginForm />
      </QueryClientProvider>
    </LocaleProvider>,
  );
}

afterEach(() => {
  loginMock.mockReset();
  replace.mockReset();
  push.mockReset();
  sessionStorage.clear();
});

describe("LoginForm", () => {
  it("redirects to /dashboard on a non-MFA login", async () => {
    loginMock.mockResolvedValueOnce({
      mfa_required: false,
      user: { id: "u1", email: "alice@acme.io", is_verified: true },
      tenant: { id: "t1", slug: "acme", name: "Acme", role: "owner" },
    });

    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo/i), "alice@acme.io");
    await user.type(screen.getByLabelText(/^contraseña$/i), "any-password");
    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("redirects to /login/mfa when the API asks for a second factor", async () => {
    loginMock.mockResolvedValueOnce({
      mfa_required: true,
      mfa_token: "fake-mfa-jwt",
    });

    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo/i), "alice@acme.io");
    await user.type(screen.getByLabelText(/^contraseña$/i), "any-password");
    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/login/mfa"));
    expect(sessionStorage.getItem("mfa_token")).toBe("fake-mfa-jwt");
  });

  it("shows the API's error message on bad credentials", async () => {
    const { ApiError } = await import("@/lib/api");
    loginMock.mockRejectedValueOnce(new ApiError(401, "Invalid email or password."));

    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo/i), "alice@acme.io");
    await user.type(screen.getByLabelText(/^contraseña$/i), "wrong");
    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
  });
});
