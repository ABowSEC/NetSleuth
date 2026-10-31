import { expect, it } from "vitest";
import { groupByDay, isImportant } from "./events";
import type { NetEvent } from "./types";

const event = (id: number, ts: Date, partial: Partial<NetEvent> = {}): NetEvent => ({
  id, ts: ts.toISOString(), kind: "joined", mac: null, severity: "info", message: `e${id}`, data: {}, ...partial,
});

it("groups newest-first events by local day", () => {
  const now = new Date(2026, 9, 30, 15);
  const groups = groupByDay([
    event(4, new Date(2026, 9, 30, 14)),
    event(3, new Date(2026, 9, 30, 9)),
    event(2, new Date(2026, 9, 29, 22)),
    event(1, new Date(2026, 9, 20, 8)),
  ], now);
  expect(groups.map((g) => [g.label, g.events.map((e) => e.id)])).toEqual([
    ["Today", [4, 3]],
    ["Yesterday", [2]],
    [expect.any(String), [1]],
  ]);
});

it("routine joins and leaves are not important", () => {
  const ts = new Date();
  expect(isImportant(event(1, ts))).toBe(false);
  expect(isImportant(event(2, ts, { kind: "left" }))).toBe(false);
  expect(isImportant(event(3, ts, { severity: "low" }))).toBe(true);
  expect(isImportant(event(4, ts, { kind: "new_device" }))).toBe(true);
  expect(isImportant(event(5, ts, { kind: "mac_conflict", severity: "high" }))).toBe(true);
});
