import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DeviceList } from "./DeviceList";
import type { Device } from "@/lib/types";

afterEach(cleanup);

const device = (mac: string, partial: Partial<Device>): Device => ({
  mac, name: null, hostname: null, vendor: null, type: "unknown", is_known: false, online: false,
  ips: [], first_seen: "", last_seen: "2026-10-30T10:00:00Z", notes: null, ...partial,
});

const devices = [
  device("aa", { name: "Kitchen speaker", type: "speaker", is_known: true, online: true, ips: ["192.168.1.5"] }),
  device("bb", { vendor: "Roku, Inc", type: "tv" }),
];

it("renders names, review badge and status", () => {
  render(<DeviceList devices={devices} busy={new Set()} onOpen={() => {}} onApprove={() => {}} />);
  expect(screen.getByText("Kitchen speaker")).toBeTruthy();
  expect(screen.getByText("Roku device")).toBeTruthy();
  expect(screen.getAllByText("New")).toHaveLength(1);
  expect(screen.getByText("Online")).toBeTruthy();
});

it("opens a device and approves unknown ones", () => {
  const onOpen = vi.fn();
  const onApprove = vi.fn();
  render(<DeviceList devices={devices} busy={new Set()} onOpen={onOpen} onApprove={onApprove} />);

  fireEvent.click(screen.getByText("Kitchen speaker"));
  expect(onOpen).toHaveBeenCalledWith("aa");

  const approve = screen.getAllByRole("button", { name: "It's mine" });
  expect(approve).toHaveLength(1);
  fireEvent.click(approve[0]);
  expect(onApprove).toHaveBeenCalledWith("bb");
  expect(onOpen).toHaveBeenCalledTimes(1);
});

it("disables approve while a request is in flight", () => {
  render(<DeviceList devices={devices} busy={new Set(["bb"])} onOpen={() => {}} onApprove={() => {}} />);
  expect((screen.getByRole("button", { name: "It's mine" }) as HTMLButtonElement).disabled).toBe(true);
});
