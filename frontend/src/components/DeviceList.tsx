"use client";

import { useRef, useState } from "react";
import { DeviceIcon } from "./DeviceIcon";
import { Button } from "./ui";
import { displayName, relativeTime, shortVendor, TYPE_LABELS } from "@/lib/format";
import type { Device } from "@/lib/types";

/** "Roku Ultra · TV / streaming", or "Roku · TV / streaming" / "Android 14 · Phone" before identification. */
function describe(d: Device): string {
  return [
    d.model ?? (d.vendor && shortVendor(d.vendor)),
    d.type !== "unknown" && TYPE_LABELS[d.type],
    !d.model && d.os,
  ].filter(Boolean).join(" · ");
}

function Glyph({ device }: { device: Device }) {
  return (
    <span className={`grid size-9 shrink-0 place-items-center rounded-md bg-surface-2 ${device.online ? "text-text" : "text-muted"}`}>
      <DeviceIcon type={device.type} />
    </span>
  );
}

/** Known devices: one quiet row each. */
export function DeviceRows({ devices, onOpen }: { devices: Device[]; onOpen: (mac: string) => void }) {
  return (
    <ul className="divide-y divide-border">
      {devices.map((d) => (
        <li key={d.mac} className="relative flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2/50">
          <Glyph device={d} />
          <div className="min-w-0 flex-1">
            {/* The whole row is clickable through this button's stretched hit area. */}
            <button
              type="button"
              onClick={() => onOpen(d.mac)}
              className={`block max-w-full truncate text-left font-medium after:absolute after:inset-0 after:content-[''] ${d.online ? "" : "text-muted"}`}
            >
              {displayName(d)}
            </button>
            <p className="truncate text-xs text-muted">{describe(d) || " "}</p>
          </div>
          <span className="shrink-0 text-right text-sm text-muted">
            {d.online ? <span className="font-mono text-xs">{d.ips[0] ?? ""}</span> : `left ${relativeTime(d.last_seen)}`}
          </span>
        </li>
      ))}
    </ul>
  );
}

interface NewcomerProps {
  devices: Device[];
  busy: Set<string>;
  onOpen: (mac: string) => void;
  onName: (mac: string, name: string) => void;
  onApprove: (mac: string) => void;
}

/** Devices nobody has vouched for yet, with naming right in the list. */
export function NewcomerList({ devices, busy, onOpen, onName, onApprove }: NewcomerProps) {
  return (
    <ul className="divide-y divide-border">
      {devices.map((d) => (
        <Newcomer key={d.mac} device={d} busy={busy.has(d.mac)} onOpen={onOpen} onName={onName} onApprove={onApprove} />
      ))}
    </ul>
  );
}

function Newcomer({ device: d, busy, onOpen, onName, onApprove }: {
  device: Device;
  busy: boolean;
  onOpen: (mac: string) => void;
  onName: (mac: string, name: string) => void;
  onApprove: (mac: string) => void;
}) {
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const facts = [describe(d), d.ips[0]].filter(Boolean);
  const looksLike = d.model ?? d.suggested_name;
  const suggestion = d.suggested_name ?? d.model;

  return (
    <li className="px-4 py-3">
      <div className="flex items-start gap-3">
        <Glyph device={d} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <button type="button" onClick={() => onOpen(d.mac)} className="truncate text-left font-medium hover:underline">
              {displayName(d)}
            </button>
            <span className="text-xs text-muted">first seen {relativeTime(d.first_seen)}</span>
          </div>
          <p className="truncate text-xs text-muted">
            {facts.join(" · ") || <span className="font-mono">{d.mac}</span>}
            {" · "}
            {d.online ? <span className="text-ok">here now</span> : `last seen ${relativeTime(d.last_seen)}`}
          </p>
          {looksLike && (
            <p className="mt-1.5 text-sm">
              Looks like <strong className="font-semibold">{looksLike}</strong>
              {d.suggested_name && d.model && d.suggested_name !== d.model && (
                <span className="text-muted">, calls itself &quot;{d.suggested_name}&quot;</span>
              )}
              {suggestion && name !== suggestion && (
                <>
                  {" "}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setName(suggestion);
                      inputRef.current?.focus();
                    }}
                    className="text-muted underline decoration-border underline-offset-2 hover:text-text"
                  >
                    Use this name
                  </button>
                </>
              )}
            </p>
          )}

          <form
            className="mt-2.5 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) onName(d.mac, name.trim());
            }}
          >
            <input
              ref={inputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              disabled={busy}
              placeholder={namePlaceholder(d)}
              aria-label={`Name for ${displayName(d)}`}
              className="h-8 min-w-0 flex-1 basis-48 rounded-md border border-border bg-bg px-2.5 text-sm placeholder:text-muted/70"
            />
            <Button type="submit" size="sm" variant="primary" disabled={busy || !name.trim()}>
              Name it
            </Button>
            <Button size="sm" disabled={busy} onClick={() => onApprove(d.mac)}>
              Mine, skip naming
            </Button>
          </form>
        </div>
      </div>
    </li>
  );
}

const PLACEHOLDERS: Partial<Record<Device["type"], string>> = {
  tv: "Living room TV",
  phone: "Sam's phone",
  tablet: "Kids' iPad",
  computer: "Work laptop",
  camera: "Front door camera",
  speaker: "Kitchen speaker",
  printer: "Office printer",
  console: "Xbox",
  iot: "Hallway smart plug",
  router: "Main router",
};

function namePlaceholder(d: Device): string {
  return `Name it, e.g. ${PLACEHOLDERS[d.type] ?? "Guest's laptop"}`;
}
