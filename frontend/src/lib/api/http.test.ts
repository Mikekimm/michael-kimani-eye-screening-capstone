import { afterEach, describe, expect, it, vi } from "vitest";

import { TokenStore } from "../auth/tokenStore";
import { ApiError, HttpClient, NetworkError } from "./http";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function client() {
  const tokens = new TokenStore(localStorage);
  tokens.save({ access_token: "old-access", refresh_token: "refresh-1", token_type: "bearer", expires_in: 900 });
  const expired = vi.fn();
  return { http: new HttpClient("/api", tokens, expired), tokens, expired };
}

afterEach(() => vi.unstubAllGlobals());

describe("HttpClient", () => {
  it("sends the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await client().http.request("/auth/me");
    expect(fetchMock.mock.calls[0]![1].headers.Authorization).toBe("Bearer old-access");
  });

  it("refreshes once on 401 and retries, even for concurrent requests", async () => {
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      if (url === "/api/auth/refresh") return json(200, { access_token: "new-access", refresh_token: "refresh-2", token_type: "bearer", expires_in: 900 });
      const auth = (init.headers as Record<string, string>).Authorization;
      return auth === "Bearer new-access" ? json(200, { ok: true }) : json(401, { message: "expired" });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { http, tokens } = client();
    await Promise.all([http.request("/a"), http.request("/b")]);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh")).toHaveLength(1);
    expect(tokens.accessToken).toBe("new-access");
  });

  it("clears the session when the refresh token is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { message: "Session is no longer valid." })));
    const { http, tokens, expired } = client();
    await expect(http.request("/a")).rejects.toBeInstanceOf(ApiError);
    expect(tokens.accessToken).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
  });

  it("surfaces the server's plain-language message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(422, { error: "unusable_image", message: "Image appears blank or uniform." })));
    await expect(client().http.request("/screenings")).rejects.toMatchObject({ status: 422, message: "Image appears blank or uniform." });
  });

  it("joins FastAPI validation errors into one sentence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(422, { detail: [{ msg: "Value error, An override requires a reason." }] })));
    await expect(client().http.request("/reviews/x")).rejects.toMatchObject({ message: "An override requires a reason." });
  });

  it("reports a NetworkError when the request never reaches the server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(client().http.request("/a")).rejects.toBeInstanceOf(NetworkError);
  });
});
