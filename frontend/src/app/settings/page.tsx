"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import { Button, Card, ErrorNotice } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useTheme, type ThemeMode } from "@/context/ThemeContext";
import { useToast } from "@/context/ToastContext";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { duration } from "@/lib/format";
import {
  notificationsEnabled, notificationsSupported, setNotificationsEnabled, subscribeNotifications,
} from "@/lib/notifications";
import type { Settings } from "@/lib/types";

const OFFLINE_OPTIONS = [300, 600, 1800, 3600];
const SWEEP_OPTIONS = [60, 300, 900, 3600];
const RETENTION_OPTIONS = [7, 30, 90, 365];

function savedMessage(patch: Partial<Settings>): string {
  if (patch.offline_timeout_s !== undefined) return `Devices now count as away after ${duration(patch.offline_timeout_s)} of silence.`;
  if (patch.sweep_interval_s !== undefined) return `The network is now scanned every ${duration(patch.sweep_interval_s)}.`;
  if (patch.retention_days !== undefined) return `History is now kept for ${duration(patch.retention_days * 86400)}.`;
  if (patch.lan_exposure !== undefined) {
    return patch.lan_exposure
      ? "Saved. Restart NetSleuth, then open it from another device using this computer's IP address."
      : "Saved. After a restart, only this computer can open the dashboard.";
  }
  return "Saved.";
}

export default function SettingsPage() {
  const toast = useToast();
  const load = useCallback(() => api.settings(), []);
  const { data: settings, error, reload, setData } = useResource<Settings>("settings", load, null);

  const update = async (patch: Partial<Settings>) => {
    const previous = settings;
    setData((s) => (s ? { ...s, ...patch } : s));
    try {
      const saved = await api.updateSettings(patch);
      setData(() => saved);
      toast.success(savedMessage(patch));
    } catch (err) {
      setData(() => previous);
      toast.error(err instanceof Error ? err.message : "Couldn't save settings.");
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      {error && <ErrorNotice message={error} onRetry={reload} />}

      <CaptureCard />

      <Card className="divide-y divide-border">
        <Row title="Mark devices offline after" hint="How long a device can stay silent before it counts as gone.">
          <Select
            value={settings?.offline_timeout_s}
            options={OFFLINE_OPTIONS}
            format={duration}
            onChange={(v) => update({ offline_timeout_s: v })}
          />
        </Row>
        <Row title="Scan the network every" hint="Finds quiet devices like printers and idle phones.">
          <Select
            value={settings?.sweep_interval_s}
            options={SWEEP_OPTIONS}
            format={duration}
            onChange={(v) => update({ sweep_interval_s: v })}
          />
        </Row>
        <Row title="Keep history for" hint="Activity and traffic history older than this is deleted. Devices are kept.">
          <Select
            value={settings?.retention_days}
            options={RETENTION_OPTIONS}
            format={(days) => duration(days * 86400)}
            onChange={(v) => update({ retention_days: v })}
          />
        </Row>
      </Card>

      <Card className="divide-y divide-border">
        <NotificationsRow />
        <ThemeRow />
      </Card>

      <Card>
        <Row
          title="Allow other devices on my network to open this dashboard"
          hint="Lets you check from your phone. Anyone on your Wi-Fi could then see device details. Takes effect after NetSleuth restarts."
        >
          <Switch
            checked={settings?.lan_exposure ?? false}
            disabled={!settings}
            onChange={(on) => update({ lan_exposure: on })}
            label="Allow access from the local network"
          />
        </Row>
      </Card>
    </div>
  );
}

function CaptureCard() {
  const { health, setHealth } = useLive();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const capturing = health?.capturing ?? false;

  const toggle = async () => {
    setBusy(true);
    try {
      setHealth(await (capturing ? api.pause() : api.resume()));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't change monitoring.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <Row
        title={health ? (capturing ? "Monitoring is on" : "Monitoring is paused") : "Monitoring"}
        hint={
          health
            ? `${health.interface ? `Watching ${health.interface}. ` : ""}${capturing ? "Devices and activity update live." : "Nothing is recorded while paused."}`
            : "Checking status…"
        }
      >
        <Button variant={capturing ? "secondary" : "primary"} disabled={!health || busy} onClick={toggle}>
          {capturing ? "Pause" : "Resume"}
        </Button>
      </Row>
    </Card>
  );
}

const noSubscribe = () => () => {};

function NotificationsRow() {
  const toast = useToast();
  const supported = useSyncExternalStore(noSubscribe, notificationsSupported, () => false);
  const on = useSyncExternalStore(subscribeNotifications, notificationsEnabled, () => false);

  const change = async (next: boolean) => {
    const result = await setNotificationsEnabled(next);
    if (next && !result) toast.error("Notifications are blocked. Allow them in your browser's site settings.");
  };

  return (
    <Row
      title="Desktop notifications"
      hint={supported
        ? "Alerts in this browser for new devices and security warnings, while this page is open."
        : "This browser doesn't support notifications."}
    >
      <Switch checked={on} disabled={!supported} onChange={change} label="Desktop notifications" />
    </Row>
  );
}

function ThemeRow() {
  const { mode, setMode } = useTheme();
  const options: { value: ThemeMode; label: string }[] = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];
  return (
    <Row title="Appearance">
      <div className="flex rounded-md border border-border p-0.5" role="radiogroup" aria-label="Appearance">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={mode === o.value}
            onClick={() => setMode(o.value)}
            className={`rounded px-3 py-1 text-sm ${mode === o.value ? "bg-surface-2 font-medium" : "text-muted hover:text-text"}`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </Row>
  );
}

function Row({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Select({ value, options, format, onChange }: {
  value: number | undefined;
  options: number[];
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  // A value set outside the UI (config file) is shown even if it isn't a preset.
  const all = value !== undefined && !options.includes(value) ? [...options, value].sort((a, b) => a - b) : options;
  return (
    <select
      value={value ?? ""}
      disabled={value === undefined}
      onChange={(e) => onChange(Number(e.target.value))}
      className="h-9 rounded-md border border-border bg-bg px-2 text-sm"
    >
      {all.map((o) => <option key={o} value={o}>{format(o)}</option>)}
    </select>
  );
}

function Switch({ checked, disabled, onChange, label }: {
  checked: boolean;
  disabled?: boolean;
  onChange: (on: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors disabled:opacity-50 ${checked ? "bg-accent" : "bg-surface-2 ring-1 ring-border"}`}
    >
      <span className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5.5" : "translate-x-0.5"}`} />
    </button>
  );
}
