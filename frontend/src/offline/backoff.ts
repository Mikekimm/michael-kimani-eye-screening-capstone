export interface BackoffOptions {
  baseMs: number;
  maxMs: number;
  /** Source of randomness in [0, 1); injectable so tests are deterministic. */
  random?: () => number;
}

export const DEFAULT_BACKOFF: BackoffOptions = { baseMs: 2_000, maxMs: 5 * 60_000 };

/** After this many failed attempts an item stops retrying on its own and waits for a manual retry. */
export const MAX_AUTO_ATTEMPTS = 8;

/**
 * Bounded exponential backoff with "full jitter":
 *   delay = random(0, min(maxMs, baseMs * 2^(attempt-1)))
 *
 * Exponential growth stops a weak connection being hammered; the cap keeps waits reasonable;
 * jitter spreads retries out so many devices coming back online at once do not all hit the
 * server in the same second. `attempt` is the number of attempts already made (>= 1).
 */
export function nextRetryDelay(attempt: number, options: BackoffOptions = DEFAULT_BACKOFF): number {
  if (!Number.isInteger(attempt) || attempt < 1) throw new RangeError("attempt must be an integer >= 1");
  const random = options.random ?? Math.random;
  const ceiling = Math.min(options.maxMs, options.baseMs * 2 ** Math.min(attempt - 1, 30));
  return Math.floor(random() * ceiling);
}
