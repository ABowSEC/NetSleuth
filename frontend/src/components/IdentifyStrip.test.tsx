import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { IdentifyStrip } from "./IdentifyStrip";
import type { IdentifyStatus } from "@/lib/types";

afterEach(cleanup);

const started = Date.parse("2026-10-31T10:00:00Z");
const status = (partial: Partial<IdentifyStatus> = {}): IdentifyStatus => ({
  running: true,
  started_at: new Date(started).toISOString(),
  ends_at: new Date(started + 10 * 60_000).toISOString(),
  done: 4,
  total: 16,
  current: "192.168.1.30",
  port_check: false,
  ...partial,
});

it("shows progress, time left and that it switches itself off", () => {
  render(<IdentifyStrip status={status()} pending={false} onStop={() => {}} now={started + 3 * 60_000} />);
  expect(screen.getByText(/4 of 16/).textContent).toContain("7 min left");
  expect(screen.getByText(/Switches itself off/).textContent).toContain("after 10 minutes");
  expect(screen.queryByText(/port check/)).toBeNull();
});

it("mentions the port check when the run includes it", () => {
  render(<IdentifyStrip status={status({ port_check: true })} pending={false} onStop={() => {}} now={started} />);
  expect(screen.getByText(/Includes the port check/)).toBeTruthy();
});

it("says under a minute near the end", () => {
  render(<IdentifyStrip status={status()} pending={false} onStop={() => {}} now={started + 9.7 * 60_000} />);
  expect(screen.getByText(/under a minute left/)).toBeTruthy();
});

it("Stop calls back and is disabled while a request is pending", () => {
  const onStop = vi.fn();
  const { rerender } = render(<IdentifyStrip status={status()} pending={false} onStop={onStop} now={started} />);
  fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(onStop).toHaveBeenCalled();
  rerender(<IdentifyStrip status={status()} pending onStop={onStop} now={started} />);
  expect((screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement).disabled).toBe(true);
});
