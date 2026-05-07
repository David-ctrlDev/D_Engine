/**
 * Smoke test for the api primitive.
 *
 * Layer 9 will add component tests for the actual auth forms; this exists
 * so the test pipeline goes green from the moment the bootstrap lands.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends credentials and JSON content-type on POST", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const result = await api.post<{ ok: boolean }>("/test", { a: 1 });
    expect(result).toEqual({ ok: true });

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("throws ApiError on non-2xx with the backend's detail string", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid email or password." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(api.post("/login", {})).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Invalid email or password.",
    });
  });

  it("surfaces a structured detail (weak password) verbatim", async () => {
    const detail = { message: "Password is too weak.", suggestions: ["Use a passphrase."] };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail }), {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    );
    try {
      await api.post("/register", {});
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.status).toBe(422);
      expect(err.message).toBe("Password is too weak.");
      expect(err.detail).toEqual(detail);
    }
  });

  it("treats network failure as ApiError with status 0", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError("offline"));
    await expect(api.get("/x")).rejects.toMatchObject({ name: "ApiError", status: 0 });
  });
});
