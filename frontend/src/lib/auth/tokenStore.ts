import type { TokenPair } from "../api/types";

const KEY = "retina.tokens";

/**
 * Keeps the access/refresh tokens. Persisted in localStorage so a health worker stays signed in
 * through offline periods and app restarts. Trade-off (documented in the README): any script
 * running on the page could read them, so the app ships no third-party scripts.
 */
export class TokenStore {
  private tokens: Pick<TokenPair, "access_token" | "refresh_token"> | null;

  constructor(private readonly storage: Storage = window.localStorage) {
    this.tokens = TokenStore.read(storage);
  }

  get accessToken(): string | null {
    return this.tokens?.access_token ?? null;
  }

  get refreshToken(): string | null {
    return this.tokens?.refresh_token ?? null;
  }

  save(pair: TokenPair): void {
    this.tokens = { access_token: pair.access_token, refresh_token: pair.refresh_token };
    this.storage.setItem(KEY, JSON.stringify(this.tokens));
  }

  clear(): void {
    this.tokens = null;
    this.storage.removeItem(KEY);
  }

  private static read(storage: Storage): TokenStore["tokens"] {
    try {
      const raw = storage.getItem(KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }
}
