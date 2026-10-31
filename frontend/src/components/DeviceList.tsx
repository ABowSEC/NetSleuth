"use client";

import { DeviceIcon } from "./DeviceIcon";
import { Button, StatusDot } from "./ui";
import { displayName, relativeTime, shortVendor, TYPE_LABELS } from "@/lib/format";
import type { Device } from "@/lib/types";

interface Props {
  devices: Device[];
  onOpen: (mac: string) => void;
  onApprove: (mac: string) => void;
  busy: Set<string>;
}

export function DeviceList({ devices, onOpen, onApprove, busy }: Props) {
  return (
    <ul className="divide-y divide-border" aria-label="Devices">
      {devices.map((d) => (
        <li key={d.mac} className="group relative flex items-center gap-3 px-4 py-3 hover:bg-surface-2/60 sm:gap-4">
          <div
            className={`grid size-10 shrink-0 place-items-center rounded-lg ${
              d.online ? "bg-accent-soft text-accent" : "bg-surface-2 text-muted"
            }`}
          >
            <DeviceIcon type={d.type} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {/* The whole row is clickable via this button's stretched hit area. */}
              <button
                type="button"
                onClick={() => onOpen(d.mac)}
                className="truncate text-left font-medium after:absolute after:inset-0 after:content-['']"
              >
                {displayName(d)}
              </button>
              {!d.is_known && (
                <span className="shrink-0 rounded bg-warn/15 px-1.5 py-0.5 text-[11px] font-semibold text-warn">
                  New
                </span>
              )}
            </div>
            <p className="truncate text-sm text-muted">
              {[d.vendor && shortVendor(d.vendor), TYPE_LABELS[d.type]].filter(Boolean).join(" · ")}
              <span className="font-mono text-xs sm:hidden">{d.ips[0] ? ` · ${d.ips[0]}` : ""}</span>
            </p>
          </div>

          <div className="hidden w-32 font-mono text-sm text-muted sm:block">{d.ips[0] ?? "—"}</div>

          <div className="flex w-24 shrink-0 items-center justify-end gap-2 text-sm sm:w-28">
            <StatusDot online={d.online} />
            <span className={d.online ? "text-ok" : "text-muted"}>
              {d.online ? "Online" : relativeTime(d.last_seen)}
            </span>
          </div>

          {!d.is_known && (
            <Button
              size="sm"
              variant="secondary"
              className="relative z-10 hidden md:inline-flex"
              disabled={busy.has(d.mac)}
              onClick={() => onApprove(d.mac)}
            >
              It&apos;s mine
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}
