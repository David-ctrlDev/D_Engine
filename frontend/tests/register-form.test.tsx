/**
 * Component test for RegisterForm. We don't hit the real backend —
 * `authApi.register` is stubbed.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RegisterForm } from "@/components/auth/register-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const registerMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth-actions", () => ({
  authApi: { register: registerMock },
}));

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RegisterForm />
    </QueryClientProvider>,
  );
}

describe("RegisterForm", () => {
  it("requires a valid email and a long password", async () => {
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/workspace name/i), "Acme");
    await user.type(screen.getByLabelText(/^password$/i), "short");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/password must be at least 12/i)).toBeInTheDocument();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("submits valid input to the API", async () => {
    registerMock.mockResolvedValueOnce({
      user_id: "u1",
      tenant_id: "t1",
      tenant_slug: "acme",
      message: "ok",
    });

    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "alice@acme.io");
    await user.type(screen.getByLabelText(/workspace name/i), "Acme Inc");
    await user.type(screen.getByLabelText(/^password$/i), "velvet-harbor-pumice-galaxy");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await vi.waitFor(() => expect(registerMock).toHaveBeenCalledTimes(1));
    expect(registerMock).toHaveBeenCalledWith({
      email: "alice@acme.io",
      workspace_name: "Acme Inc",
      password: "velvet-harbor-pumice-galaxy",
    });
  });
});
