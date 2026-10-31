"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DeviceIcon } from "./DeviceIcon";
import { PresenceStrip } from "./PresenceStrip";
import { Button, ErrorNotice, StatusDot } from "./ui";
import { useToast } from "@/context/ToastContext";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { dateTime, displayName, relativeTime, TYPE_LABELS } from "@/lib/format";
import type { Device, DeviceDetail } from "@/lib/types";

interface Props {
  mac: string;
  onClose: () => void;
  onChanged: (device: Device) => void;
  onForgotten: (mac: string) => void;
}

export function DeviceDrawer({ mac, onClose, onChanged, onForgotten }: Props) {
  const toast = useToast();
  const load = useCallback((signal: AbortSignal) => api.device(mac, signal), [mac]);
  const { data: device, error, loading, reload, setData } = useResource<DeviceDetail>(`device:${mac}`, load, 60_000);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = async (patch: Parameters<typeof api.updateDevice>[1], message: string) => {
    try {
      const updated = await api.updateDevice(mac, patch);
      setData((current) => (current ? { ...current, ...updated } : current));
      onChanged(updated);
      toast.success(message);
      return true;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't save.");
      return false;
    }
  };

  const forget = async () => {
    try {
      await api.forgetDevice(mac);
      toast.success("Device forgotten. It will reappear if it's seen again.");
      onForgotten(mac);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't forget device.");
    }
  };

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <button type="button" className="absolute inset-0 cursor-default bg-black/30" aria-label="Close" onClick={onClose} tabIndex={-1} />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl">
        <div className="flex items-start gap-3 border-b border-border px-5 py-4">
          {device && (
            <div className={`grid size-11 shrink-0 place-items-center rounded-lg ${device.online ? "bg-accent-soft text-accent" : "bg-surface-2 text-muted"}`}>
              <DeviceIcon type={device.type} className="size-6" />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h2 id="drawer-title" className="truncate text-lg font-semibold">
              {device ? displayName(device) : loading ? "Loading…" : "Device"}
            </h2>
            {device && (
              <p className="flex items-center gap-2 text-sm text-muted">
                <StatusDot online={device.online} />
                {device.online ? `Online${device.ips[0] ? ` at ${device.ips[0]}` : ""}` : `Last seen ${relativeTime(device.last_seen)}`}
              </p>
            )}
          </div>
          <button ref={closeRef} type="button" onClick={onClose} className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text" aria-label="Close device details">
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>

        <div className="flex-1 space-y-7 overflow-y-auto px-5 py-5">
          {error && !device && <ErrorNotice message={error} onRetry={reload} />}
          {device && (
            <>
              {!device.is_known && (
                <div className="rounded-lg border border-warn/30 bg-warn/10 p-4">
                  <p className="font-medium">Do you recognise this device?</p>
                  <p className="mt-1 text-sm text-muted">
                    Mark it as yours so it stops showing up as new. If you don&apos;t know what it is, check your router&apos;s device list or unplug things one at a time.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button variant="primary" size="sm" onClick={() => save({ is_known: true }, "Marked as known.")}>
                      Yes, it&apos;s mine
                    </Button>
                  </div>
                </div>
              )}

              <EditForm key={device.mac} device={device} onSave={save} />

              <Section title="Details">
                <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-sm">
                  <Fact label="Type">{TYPE_LABELS[device.type]}</Fact>
                  <Fact label="Maker">{device.vendor ?? <span className="text-muted">Unknown{isRandomized(device.mac) ? " (private Wi-Fi address)" : ""}</span>}</Fact>
                  <Fact label="Hostname">{device.hostname ?? <span className="text-muted">Not reported</span>}</Fact>
                  <Fact label="MAC address"><span className="font-mono">{device.mac}</span></Fact>
                  <Fact label="IP addresses">
                    {device.ips.length ? (
                      <span className="font-mono">
                        {device.ips[0]}
                        {device.ips.length > 1 && <span className="text-muted"> (previously {device.ips.slice(1, 4).join(", ")})</span>}
                      </span>
                    ) : "—"}
                  </Fact>
                  <Fact label="First seen">{dateTime(device.first_seen)}</Fact>
                  <Fact label="Last seen">{dateTime(device.last_seen)}</Fact>
                </dl>
              </Section>

              <Section title="When it's been online" hint="Last 7 days">
                {device.presence.length ? <PresenceStrip sessions={device.presence} /> : <p className="text-sm text-muted">No sessions recorded yet.</p>}
              </Section>

              <Section title="What it looks up" hint="Most frequent DNS lookups">
                <CountList
                  rows={device.top_domains.map((d) => ({ key: d.domain, label: d.domain, count: d.count }))}
                  empty="No lookups seen. Devices using encrypted DNS won't show any."
                />
              </Section>

              <Section title="Who it connects to" hint="Connections it started">
                <CountList
                  rows={device.top_destinations.map((d) => ({
                    key: `${d.address}:${d.port}`,
                    label: d.port === null ? d.address : `${d.address}:${d.port}`,
                    count: d.count,
                  }))}
                  empty="No outgoing connections seen yet."
                />
              </Section>

              <Section title="Forget this device">
                <ForgetButton onConfirm={forget} />
              </Section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function EditForm({ device, onSave }: {
  device: DeviceDetail;
  onSave: (patch: { name?: string | null; notes?: string | null; is_known?: boolean }, message: string) => Promise<boolean>;
}) {
  const [name, setName] = useState(device.name ?? "");
  const [notes, setNotes] = useState(device.notes ?? "");
  const [saving, setSaving] = useState(false);
  const dirty = name.trim() !== (device.name ?? "") || notes.trim() !== (device.notes ?? "");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    // Naming a device is a strong signal that the owner recognises it.
    const patch = { name: name.trim() || null, notes: notes.trim() || null, ...(name.trim() && !device.is_known ? { is_known: true } : {}) };
    await onSave(patch, "Saved.");
    setSaving(false);
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="block">
        <span className="text-sm font-medium">Name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={64}
          placeholder={device.hostname ?? (device.vendor ? `e.g. ${device.vendor.split(/[ ,]/)[0]} in the kitchen` : "e.g. Living room TV")}
          className="mt-1 h-9 w-full rounded-md border border-border bg-bg px-3 text-sm placeholder:text-muted/70"
        />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Notes</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={500}
          rows={2}
          placeholder="Where it is, who owns it…"
          className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm placeholder:text-muted/70"
        />
      </label>
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={device.is_known}
            onChange={(e) => onSave({ is_known: e.target.checked }, e.target.checked ? "Marked as known." : "Marked as not reviewed.")}
            className="size-4 accent-[var(--accent)]"
          />
          I know this device
        </label>
        <Button type="submit" variant="primary" disabled={!dirty || saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
}

function ForgetButton({ onConfirm }: { onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted">Removes the device and all of its history. If it&apos;s still on your network it will show up again as new.</p>
      <Button variant="danger" size="sm" onClick={() => (armed ? onConfirm() : setArmed(true))}>
        {armed ? "Click again to forget" : "Forget device"}
      </Button>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 flex items-baseline gap-2 text-sm font-semibold">
        {title}
        {hint && <span className="text-xs font-normal text-muted">{hint}</span>}
      </h3>
      {children}
    </section>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  );
}

function CountList({ rows, empty }: { rows: { key: string; label: string; count: number }[]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-muted">{empty}</p>;
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className="space-y-1.5">
      {rows.slice(0, 10).map((r) => (
        <li key={r.key} className="relative flex items-center justify-between gap-3 overflow-hidden rounded px-2 py-1 text-sm">
          <span className="absolute inset-y-0 left-0 bg-accent-soft" style={{ width: `${(r.count / max) * 100}%` }} aria-hidden="true" />
          <span className="relative truncate font-mono text-xs">{r.label}</span>
          <span className="relative shrink-0 tabular-nums text-muted">{r.count.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}

function isRandomized(mac: string): boolean {
  return (parseInt(mac.slice(0, 2), 16) & 0x02) === 0x02;
}
