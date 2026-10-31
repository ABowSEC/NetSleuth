import { describe, expect, it } from "vitest";
import { dayLabel, displayName, duration, relativeTime, shortVendor } from "./format";

describe("relativeTime", () => {
  const now = Date.parse("2026-10-30T12:00:00Z");
  it.each([
    ["2026-10-30T11:59:40Z", "just now"],
    ["2026-10-30T11:59:00Z", "1 minute ago"],
    ["2026-10-30T11:55:00Z", "5 minutes ago"],
    ["2026-10-30T11:00:00Z", "1 hour ago"],
    ["2026-10-30T09:00:00Z", "3 hours ago"],
    ["2026-10-28T12:00:00Z", "2 days ago"],
  ])("%s -> %s", (iso, expected) => {
    expect(relativeTime(iso, now)).toBe(expected);
  });

  it("older dates read as 'on <date>'", () => {
    expect(relativeTime("2026-08-01T12:00:00Z", now)).toMatch(/^on \S+/);
  });

  it("never renders NaN for bad input", () => {
    expect(relativeTime("Unknown", now)).toBe("at an unknown time");
    expect(relativeTime("", now)).toBe("at an unknown time");
  });
});

it.each([
  ["Amazon Technologies Inc.", "Amazon Technologies"],
  ["Roku, Inc", "Roku"],
  ["Micro-Star INTL CO., LTD.", "Micro-Star INTL"],
  ["Intel Corporate", "Intel"],
  ["Ring LLC", "Ring"],
  ["Sonos", "Sonos"],
])("shortVendor(%s)", (vendor, expected) => {
  expect(shortVendor(vendor)).toBe(expected);
});

it("displayName prefers name, then hostname, then vendor", () => {
  expect(displayName({ name: "TV", hostname: "roku", vendor: "Roku, Inc" })).toBe("TV");
  expect(displayName({ name: null, hostname: "roku", vendor: "Roku, Inc" })).toBe("roku");
  expect(displayName({ name: null, hostname: null, vendor: "Roku, Inc" })).toBe("Roku device");
  expect(displayName({ name: null, hostname: null, vendor: null })).toBe("Unknown device");
});

it("duration picks the largest whole unit", () => {
  expect(duration(600)).toBe("10 min");
  expect(duration(3600)).toBe("1 hour");
  expect(duration(86400 * 30)).toBe("30 days");
  expect(duration(45)).toBe("45 s");
});

it("dayLabel names today and yesterday", () => {
  const now = new Date(2026, 9, 30, 12);
  expect(dayLabel(new Date(2026, 9, 30, 1).toISOString(), now)).toBe("Today");
  expect(dayLabel(new Date(2026, 9, 29, 23).toISOString(), now)).toBe("Yesterday");
  expect(dayLabel("garbage", now)).toBe("Unknown date");
});
