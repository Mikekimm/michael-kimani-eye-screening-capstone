import type { ApiErrorBody, TokenPair } from "./types";
import type { TokenStore } from "../auth/tokenStore";

/** An HTTP error from the API, carrying the server's plain-language message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** The request never reached the server (offline, DNS, server down). Safe to retry later. */
export class NetworkError extends Error {
  constructor(message = "No connection to the server.") {
    super(message);
    this.name = "NetworkError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
  responseType?: "json" | "blob";
  /** Skip the Authorization header and the refresh-on-401 logic (login, register, refresh). */
  anonymous?: boolean;
}

/**
 * The single place that talks HTTP. Adds the bearer token, refreshes it once on a 401
 * (concurrent requests share one refresh), and turns failures into ApiError / NetworkError.
 */
export class HttpClient {
  private refreshing: Promise<boolean> | null = null;

  constructor(
    private readonly baseUrl: string,
    private readonly tokens: TokenStore,
    private readonly onSessionExpired: () => void = () => {},
  ) {}

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.send(path, options);
    if (response.status === 401 && !options.anonymous && this.tokens.refreshToken) {
      if (await this.refreshOnce()) {
        return this.parse<T>(await this.send(path, options), options);
      }
      this.tokens.clear();
      this.onSessionExpired();
    }
    return this.parse<T>(response, options);
  }

  private async send(path: string, options: RequestOptions): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
    if (!options.anonymous && this.tokens.accessToken) {
      headers.Authorization = `Bearer ${this.tokens.accessToken}`;
    }
    let body: BodyInit | undefined;
    if (options.form) {
      body = options.form; // the browser sets the multipart boundary
    } else if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }
    try {
      return await fetch(this.url(path, options.query), {
        method: options.method ?? "GET",
        headers,
        body,
        signal: options.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new NetworkError();
    }
  }

  private url(path: string, query?: RequestOptions["query"]): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    const suffix = params.toString() ? `?${params}` : "";
    return `${this.baseUrl}${path}${suffix}`;
  }

  private refreshOnce(): Promise<boolean> {
    this.refreshing ??= this.refresh().finally(() => {
      this.refreshing = null;
    });
    return this.refreshing;
  }

  private async refresh(): Promise<boolean> {
    try {
      const response = await this.send("/auth/refresh", {
        method: "POST",
        json: { refresh_token: this.tokens.refreshToken },
        anonymous: true,
      });
      if (!response.ok) return false;
      this.tokens.save((await response.json()) as TokenPair);
      return true;
    } catch {
      return false;
    }
  }

  private async parse<T>(response: Response, options: RequestOptions): Promise<T> {
    if (response.ok) {
      if (response.status === 204) return undefined as T;
      return (options.responseType === "blob" ? await response.blob() : await response.json()) as T;
    }
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // non-JSON error page (e.g. a proxy); fall through to a generic message
    }
    throw new ApiError(response.status, body.error ?? "error", errorMessage(response.status, body), body.details ?? {});
  }
}

/** FastAPI validation errors arrive as a list in `detail`; turn them into one readable sentence. */
function errorMessage(status: number, body: ApiErrorBody): string {
  if (body.message) return body.message;
  if (Array.isArray(body.detail)) {
    const parts = body.detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
      .filter(Boolean);
    if (parts.length) return parts.join(" ").replace(/^Value error, /, "");
  }
  if (typeof body.detail === "string") return body.detail;
  if (status >= 500) return "The server had a problem. Please try again shortly.";
  return "The request could not be completed.";
}
