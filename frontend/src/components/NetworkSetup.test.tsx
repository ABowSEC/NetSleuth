import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NetworkSetup } from "./NetworkSetup";
import { statusBadge } from "./AppHeader";
import type { Health, LegacyList, Network } from "@/lib/types";

afterEach(cleanup);

const now = Date.parse("2026-11-21T18:00:00Z");
const network = (partial: Partial<Network> = {}): Network => ({
  id: "5d4c3b2a1f0e", label: null, ssid: "Friends-WiFi", subnet: "192.168.1.0/24", gateway_ip: "192.168.1.1",
  gateway_mac: "02:00:00:00:cc:01", trust: "idle", first_seen: "2026-11-21T17:59:00Z",
  last_seen: "2026-11-21T18:00:00Z", similar_to: null, current: true, ...partial,
});
const legacy = (partial: Partial<LegacyList> = {}): LegacyList => ({
  available: true, devices: 17, last_seen: "2026-11-21T16:00:00Z", likely_here: false, adoptable: true, ...partial,
});

function setup(props: Partial<Parameters<typeof NetworkSetup>[0]> = {}) {
  const onChoose = vi.fn();
  const onAdopt = vi.fn();
  render(
    <NetworkSetup network={network()} legacy={null} twin={null} busy={false}
      onChoose={onChoose} onAdopt={onAdopt} now={now} {...props} />,
  );
  return { onChoose, onAdopt };
}

it("says nothing is recorded yet and shows how the network was recognised", () => {
  setup();
  expect(screen.getByRole("heading", { name: /isn't recording anything on Friends-WiFi/ })).toBeTruthy();
  expect(screen.getByText("192.168.1.0/24")).toBeTruthy();
  expect(screen.getByText(/02:00:00:00:cc:01/)).toBeTruthy();
});

it("defaults to idle, and starting needs a deliberate choice", () => {
  const { onChoose } = setup();
  fireEvent.click(screen.getByRole("button", { name: "Keep it idle" }));
  expect(onChoose).toHaveBeenCalledWith("idle", null);

  fireEvent.click(screen.getByRole("radio", { name: /Home/ }));
  fireEvent.change(screen.getByLabelText(/Name this network/), { target: { value: "  Den  " } });
  fireEvent.click(screen.getByRole("button", { name: "Start monitoring" }));
  expect(onChoose).toHaveBeenLastCalledWith("home", "Den");
});

it("warns when the earlier list came from a different router", () => {
  const { onAdopt } = setup({ legacy: legacy() });
  expect(screen.getByText(/recorded on a different router/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Use it here anyway" }));
  expect(onAdopt).toHaveBeenCalledWith("home");
});

it("recommends the earlier list when it was recorded on this router", () => {
  setup({ legacy: legacy({ likely_here: true }) });
  expect(screen.getByRole("button", { name: "Use it here as Home" })).toBeTruthy();
  expect(screen.queryByText(/different router/)).toBeNull();
});

it("hides the earlier list when it can't be used here", () => {
  setup({ legacy: legacy({ adoptable: false }) });
  expect(screen.queryByRole("region", { name: "Earlier device list" })).toBeNull();
});

it("flags a look-alike of a known network", () => {
  setup({ network: network({ similar_to: "a1b2c3d4e5f6" }), twin: network({ id: "a1b2c3d4e5f6", label: "Home" }) });
  expect(screen.getByRole("alert").textContent).toContain("same name and address range as Home");
});

it("header badge says idle, listening or watching by trust", () => {
  const health = (trust: "home" | "observe" | "idle", capturing = trust !== "idle"): Health => ({
    status: "ok", version: "t", capturing, interface: "Wi-Fi", started_at: null,
    network: { id: "x", label: trust === "home" ? "Home" : null, ssid: "Friends-WiFi", trust },
  });
  expect(statusBadge("live", health("idle")).label).toBe("Idle on Friends-WiFi");
  expect(statusBadge("live", health("observe")).label).toBe("Listening on Friends-WiFi");
  expect(statusBadge("live", health("home")).label).toBe("Watching Home");
  expect(statusBadge("live", health("home", false)).label).toBe("Paused");
  expect(statusBadge("offline", null).label).toBe("Can't reach NetSleuth");
});
