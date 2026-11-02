import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DeviceRows, NewcomerList } from "./DeviceList";
import { identifyHint } from "./DeviceDrawer";
import type { Device } from "@/lib/types";

afterEach(cleanup);

const device = (mac: string, partial: Partial<Device>): Device => ({
  mac, name: null, hostname: null, vendor: null, type: "unknown", is_known: false, online: false,
  ips: [], first_seen: "2026-10-30T09:00:00Z", last_seen: "2026-10-30T10:00:00Z", notes: null, model: null, os: null, suggested_name: null, ...partial,
});

const speaker = device("aa", { name: "Kitchen speaker", type: "speaker", is_known: true, online: true, ips: ["192.168.1.5"] });
const printer = device("cc", { name: "Office printer", type: "printer", is_known: true });
const roku = device("bb", { vendor: "Roku, Inc", type: "tv", online: true, ips: ["192.168.1.30"] });

it("known rows show the IP when here and how long ago they left when away", () => {
  const onOpen = vi.fn();
  render(<DeviceRows devices={[speaker, printer]} onOpen={onOpen} />);
  expect(screen.getByText("192.168.1.5")).toBeTruthy();
  expect(screen.getByText(/^left /)).toBeTruthy();
  fireEvent.click(screen.getByText("Kitchen speaker"));
  expect(onOpen).toHaveBeenCalledWith("aa");
});

it("newcomers can be named inline with Enter", () => {
  const onName = vi.fn();
  render(<NewcomerList devices={[roku]} busy={new Set()} onOpen={() => {}} onName={onName} onApprove={() => {}} />);

  expect(screen.getByText("Roku device")).toBeTruthy();
  expect(screen.getByText("here now")).toBeTruthy();
  const input = screen.getByPlaceholderText("Name it, e.g. Living room TV");

  // Blank names are not submitted.
  fireEvent.submit(input.closest("form")!);
  expect(onName).not.toHaveBeenCalled();

  fireEvent.change(input, { target: { value: "  Bedroom Roku " } });
  fireEvent.submit(input.closest("form")!);
  expect(onName).toHaveBeenCalledWith("bb", "Bedroom Roku");
});

it("newcomers can be approved without a name, and are locked while saving", () => {
  const onApprove = vi.fn();
  const { rerender } = render(
    <NewcomerList devices={[roku]} busy={new Set()} onOpen={() => {}} onName={() => {}} onApprove={onApprove} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Mine, skip naming" }));
  expect(onApprove).toHaveBeenCalledWith("bb");

  rerender(<NewcomerList devices={[roku]} busy={new Set(["bb"])} onOpen={() => {}} onName={() => {}} onApprove={onApprove} />);
  expect((screen.getByRole("button", { name: "Mine, skip naming" }) as HTMLButtonElement).disabled).toBe(true);
});

it("identification hints are specific to what is known about the device", () => {
  expect(identifyHint({ mac: "02:11:22:33:44:55", vendor: null, hostname: null })).toMatch(/private Wi-Fi address/);
  expect(identifyHint({ mac: "a8:b5:7c:00:00:03", vendor: "Roku, Inc", hostname: null })).toMatch(/made by Roku, Inc/);
  expect(identifyHint({ mac: "d0:57:7e:00:00:02", vendor: null, hostname: null })).toMatch(/router/);
});

it("offers the name a device gave itself", () => {
  const onName = vi.fn();
  const identified = { ...roku, model: "Roku Ultra", suggested_name: "Bedroom Roku" };
  render(<NewcomerList devices={[identified]} busy={new Set()} onOpen={() => {}} onName={onName} onApprove={() => {}} />);

  expect(screen.getByText("Roku Ultra")).toBeTruthy();
  expect(screen.getByText(/calls itself "Bedroom Roku"/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Use this name" }));
  const input = screen.getByDisplayValue("Bedroom Roku");
  expect(screen.queryByRole("button", { name: "Use this name" })).toBeNull();
  fireEvent.submit(input.closest("form")!);
  expect(onName).toHaveBeenCalledWith("bb", "Bedroom Roku");
});

it("known rows prefer the identified model over the chip maker", () => {
  render(<DeviceRows devices={[{ ...speaker, vendor: "Amazon Technologies Inc.", model: "Echo Dot" }]} onOpen={() => {}} />);
  expect(screen.getByText(/Echo Dot/)).toBeTruthy();
  expect(screen.queryByText(/Amazon/)).toBeNull();
});

it("identification hint acknowledges what the device said", () => {
  expect(identifyHint({ mac: "a8:b5:7c:00:00:03", vendor: "Roku, Inc", hostname: null, model: "Roku Ultra" }))
    .toMatch(/what the device said about itself/);
});
