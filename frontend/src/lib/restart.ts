import { api } from "./api";
import type { Health } from "./types";

const POLL_MS = 1000;
const TIMEOUT_MS = 30_000;

/**
 * Wait for NetSleuth to come back after it restarted itself (to adopt a device
 * list, or to reset). A restart is recognised by a new `started_at`. Resolves
 * with the new health, or null if it didn't come back in time (for example
 * when it was started without the tray, which is what restarts it).
 */
export async function waitForRestart(
  before: string | null,
  { pollMs = POLL_MS, timeoutMs = TIMEOUT_MS, health = api.health } = {},
): Promise<Health | null> {
  const deadline = Date.now() + timeoutMs;
  const wait = () => new Promise((r) => setTimeout(r, pollMs));
  await wait();
  while (Date.now() < deadline) {
    try {
      const h = await health();
      if (h.started_at && h.started_at !== before) return h;
    } catch {
      // still restarting
    }
    await wait();
  }
  return null;
}

export const NOT_BACK_MESSAGE =
  "NetSleuth hasn't come back yet. If you started it without the tray, start it again.";
