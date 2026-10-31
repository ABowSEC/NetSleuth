import { expect, it } from "vitest";
import { presenceByDay } from "./PresenceStrip";

const at = (day: number, hour: number) => new Date(2026, 9, day, hour).toISOString();

it("splits sessions across local days and clips to now", () => {
  const now = new Date(2026, 9, 30, 12);
  const rows = presenceByDay([
    { start: at(28, 22), end: at(29, 2) },   // spans midnight
    { start: at(30, 9), end: null },         // still online
  ], now, 3);

  expect(rows.map((r) => r.dayStart.getDate())).toEqual([28, 29, 30]);
  expect(rows[0].onlineMs).toBe(2 * 3_600_000);
  expect(rows[1].onlineMs).toBe(2 * 3_600_000);
  expect(rows[2].onlineMs).toBe(3 * 3_600_000);
  expect(rows[0].segments[0].left).toBeCloseTo((22 / 24) * 100);
});

it("ignores malformed and reversed sessions", () => {
  const now = new Date(2026, 9, 30, 12);
  const rows = presenceByDay([
    { start: "garbage", end: null },
    { start: at(30, 10), end: at(30, 9) },
  ], now, 1);
  expect(rows[0].segments).toEqual([]);
});
