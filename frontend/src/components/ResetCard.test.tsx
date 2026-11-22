import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ResetPanel } from "./ResetCard";
import { waitForRestart } from "@/lib/restart";
import type { Health } from "@/lib/types";

afterEach(cleanup);

it("only resets after the confirmation word is typed", () => {
  const onReset = vi.fn();
  render(<ResetPanel busy={false} onReset={onReset} />);
  expect(screen.getByText(/settings and logs are kept/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reset everything…" }));

  const submit = screen.getByRole("button", { name: "Delete all device data" }) as HTMLButtonElement;
  expect(submit.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: "yes" } });
  expect(submit.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(/to confirm/), { target: { value: " Reset " } });
  expect(submit.disabled).toBe(false);
  fireEvent.click(submit);
  expect(onReset).toHaveBeenCalledTimes(1);
});

it("cancel closes the confirmation", () => {
  render(<ResetPanel busy={false} onReset={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "Reset everything…" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByLabelText(/to confirm/)).toBeNull();
});

const health = (started_at: string | null): Health => ({
  status: "ok", version: "t", capturing: false, interface: "Wi-Fi", started_at, network: null,
});

it("waits through the restart until a new start time appears", async () => {
  const replies = [health("old"), null, health("new")];
  const fake = vi.fn(async () => {
    const next = replies.shift();
    if (!next) throw new Error("down");
    return next;
  });
  const back = await waitForRestart("old", { pollMs: 1, timeoutMs: 1000, health: fake });
  expect(back?.started_at).toBe("new");
  expect(fake).toHaveBeenCalledTimes(3);
});

it("gives up when it doesn't come back", async () => {
  const back = await waitForRestart("old", { pollMs: 1, timeoutMs: 20, health: async () => health("old") });
  expect(back).toBeNull();
});
