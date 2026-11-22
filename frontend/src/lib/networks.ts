import type { Network, Trust } from "./types";

/** What each trust level lets NetSleuth do, in the words the UI uses everywhere. */
export const TRUST_INFO: Record<Trust, { name: string; summary: string; detail: string }> = {
  home: {
    name: "Home",
    summary: "Track everything",
    detail: "Your own network. Keeps a device list, scans for quiet devices, allows Identify, and alerts you.",
  },
  observe: {
    name: "Observe",
    summary: "Only listen",
    detail: "Keeps a device list from what it overhears. Never scans or probes. For a network you're allowed to watch.",
  },
  idle: {
    name: "Idle",
    summary: "Record nothing",
    detail: "NetSleuth doesn't listen or record anything here. Best for a friend's, school or public Wi-Fi.",
  },
};

export const TRUST_ORDER: Trust[] = ["home", "observe", "idle"];

type Named = Pick<Network, "label" | "ssid"> & Partial<Pick<Network, "subnet">>;

/** The name to show for a network: the user's label, else its Wi-Fi name, else its address range. */
export function networkName(n: Named | null | undefined, fallback = "this network"): string {
  return n?.label ?? n?.ssid ?? n?.subnet ?? fallback;
}
