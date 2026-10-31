import type { NetEvent } from "./types";

// Per-browser preference; the backend has no notion of who is viewing.
const STORAGE_KEY = "netsleuth_notify";

// External store for useSyncExternalStore: changes here or in another tab.
const listeners = new Set<() => void>();

export function subscribeNotifications(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export const notificationsSupported = () => typeof window !== "undefined" && "Notification" in window;

export function notificationsEnabled(): boolean {
  if (!notificationsSupported() || Notification.permission !== "granted") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export async function setNotificationsEnabled(on: boolean): Promise<boolean> {
  if (!notificationsSupported()) return false;
  if (on && Notification.permission !== "granted") {
    if ((await Notification.requestPermission()) !== "granted") return false;
  }
  try {
    if (on) localStorage.setItem(STORAGE_KEY, "1");
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    return false;
  } finally {
    listeners.forEach((l) => l());
  }
  return on;
}

/** Events worth interrupting someone for. */
export function isNotable(event: NetEvent): boolean {
  if (event.kind === "new_device") return event.data.baseline !== true;
  if (event.kind === "mac_conflict") return true;
  return event.kind === "alert" && (event.severity === "high" || event.severity === "critical");
}

export function notifyIfWanted(event: NetEvent) {
  if (!isNotable(event) || !notificationsEnabled()) return;
  try {
    new Notification("NetSleuth", { body: event.message, tag: `netsleuth-${event.id}` });
  } catch {
    // Some browsers only allow notifications from a service worker.
  }
}
