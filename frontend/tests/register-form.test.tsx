/**
 * Component test for RegisterForm. We don't hit the real backend —
 * `authApi.register` is stubbed.
 *
 * The component reads strings from the LocaleProvider; tests render
 * with the project default (Spanish) and match against Spanish labels.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RegisterForm } from "@/components/auth/register-form";
import { LocaleProvider } from "@/lib/i18n/provider";

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
    <LocaleProvider>
      <QueryClientProvider client={client}>
        <RegisterForm />
      </QueryClientProvider>
    </LocaleProvider>,
  );
}

describe("RegisterForm", () => {
  it("requires a valid email and a long password", async () => {
    renderForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/correo/i), "no-es-un-email");
    await user.type(screen.getByLabelText(/nombre del espacio/i), "Acme");
    await user.type(screen.getByLabelText(/^contraseña$/i), "corto");
    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(await screen.findByText(/correo electrónico válido/i)).toBeInTheDocument();
    // Use the error-specific phrase so we don't also match the hint copy
    // ("Al menos 12 caracteres…") below the password field.
    expect(screen.getByText(/contraseña debe tener al menos 12/i)).toBeInTheDocument();
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

    await user.type(screen.getByLabelText(/correo/i), "alice@acme.io");
    await user.type(screen.getByLabelText(/nombre del espacio/i), "Acme Inc");
    await user.type(screen.getByLabelText(/^contraseña$/i), "velvet-harbor-pumice-galaxy");
    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    await vi.waitFor(() => expect(registerMock).toHaveBeenCalledTimes(1));
    expect(registerMock).toHaveBeenCalledWith({
      email: "alice@acme.io",
      workspace_name: "Acme Inc",
      password: "velvet-harbor-pumice-galaxy",
    });
  });
});
