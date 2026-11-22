"use client";

// Shown on a network NetSleuth hasn't been told about (trust "idle"): nothing is
// recorded until the user says which network this is and what NetSleuth may do.

import { useCallback, useEffect, useId, useState } from "react";
import { Button, Card } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { networkName, TRUST_INFO, TRUST_ORDER } from "@/lib/networks";
import { NOT_BACK_MESSAGE, waitForRestart } from "@/lib/restart";
import type { LegacyList, Network, Trust } from "@/lib/types";

const START_LABEL: Record<Trust, string> = {
  home: "Start monitoring",
  observe: "Start listening",
  idle: "Keep it idle",
};

interface SetupProps {
  network: Network;
  legacy: LegacyList | null;
  /** A known network with the same Wi-Fi name and subnet but another router. */
  twin: Network | null;
  busy: boolean;
  onChoose: (trust: Trust, label: string | null) => void;
  onAdopt: (trust: "home" | "observe") => void;
  now?: number;
}

export function NetworkSetup({ network, legacy, twin, busy, onChoose, onAdopt, now }: SetupProps) {
  const [trust, setTrust] = useState<Trust>("idle");
  const [label, setLabel] = useState("");
  const labelId = useId();
  const showLegacy = legacy?.available && legacy.adoptable;

  return (
    <Card className="space-y-6 border-warn/40 p-5">
      <div className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wider text-warn">New network</p>
        <h2 className="text-xl font-semibold tracking-tight">
          NetSleuth isn&apos;t recording anything on {networkName(network)}
        </h2>
        <p className="text-sm text-muted">
          Each network keeps its own device list. Nothing is captured here until you choose what NetSleuth may do.
        </p>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
        <dt className="text-muted">Wi-Fi name</dt>
        <dd>{network.ssid ?? <span className="text-muted">Not shared by Windows (or a wired connection)</span>}</dd>
        <dt className="text-muted">Address range</dt>
        <dd className="font-mono text-xs leading-5">{network.subnet}</dd>
        <dt className="text-muted">Router</dt>
        <dd className="font-mono text-xs leading-5">
          {network.gateway_ip ?? "unknown"}
          {network.gateway_mac && <span className="text-muted"> · {network.gateway_mac}</span>}
        </dd>
        <dt className="text-muted">First seen</dt>
        <dd>{network.first_seen ? relativeTime(network.first_seen, now) : "just now"}</dd>
      </dl>

      {twin && (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          This network has the same name and address range as {networkName(twin)}, but a different router. If you
          replaced your router, set it up as Home. If you didn&apos;t, another device may be imitating your network:
          keep it idle.
        </p>
      )}

      {showLegacy && (
        <section className="space-y-2 rounded-md border border-border p-4" aria-label="Earlier device list">
          <h3 className="text-sm font-semibold">
            Your earlier device list: {legacy.devices} {legacy.devices === 1 ? "device" : "devices"}
            {legacy.last_seen && <span className="font-normal text-muted">, last updated {relativeTime(legacy.last_seen, now)}</span>}
          </h3>
          {legacy.likely_here ? (
            <p className="text-sm text-muted">It was recorded on this network&apos;s router, so this is probably where it belongs.</p>
          ) : (
            <p className="text-sm text-warn">
              It was recorded on a different router. Use it here only if this is your own network and you&apos;ve
              replaced the router. Otherwise leave it: it will be offered again on the network it came from.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant={legacy.likely_here ? "primary" : "secondary"} disabled={busy} onClick={() => onAdopt("home")}>
              {legacy.likely_here ? "Use it here as Home" : "Use it here anyway"}
            </Button>
            <span className="text-xs text-muted">NetSleuth restarts for a few seconds to move it.</span>
          </div>
        </section>
      )}

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onChoose(trust, label.trim() || null);
        }}
      >
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-semibold">
            {showLegacy ? "Or start this network fresh" : "What may NetSleuth do here?"}
          </legend>
          {TRUST_ORDER.map((level) => (
            <label
              key={level}
              className={`flex cursor-pointer gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors ${
                trust === level ? "border-accent bg-surface-2" : "border-border hover:bg-surface-2"
              }`}
            >
              <input
                type="radio"
                name="trust"
                value={level}
                checked={trust === level}
                onChange={() => setTrust(level)}
                className="mt-1 accent-current"
              />
              <span>
                <span className="font-medium">{TRUST_INFO[level].name}</span>
                <span className="text-muted"> · {TRUST_INFO[level].summary}</span>
                <span className="block text-xs text-muted">{TRUST_INFO[level].detail}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {trust !== "idle" && (
          <div className="space-y-1">
            <label htmlFor={labelId} className="text-sm font-medium">Name this network (optional)</label>
            <input
              id={labelId}
              value={label}
              maxLength={64}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={network.ssid ?? "e.g. Home"}
              className="h-9 w-full rounded-md border border-border bg-surface px-3 text-sm placeholder:text-muted/70 sm:max-w-xs"
            />
          </div>
        )}

        <Button type="submit" variant={trust === "idle" ? "secondary" : "primary"} disabled={busy}>
          {START_LABEL[trust]}
        </Button>
      </form>
    </Card>
  );
}

/** A one-line reminder once the user chose to keep this network idle. */
export function IdleNotice({ network, onSetUp }: { network: Pick<Network, "label" | "ssid">; onSetUp: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm">
      <span className="size-2 rounded-full bg-muted/40" aria-hidden="true" />
      <span className="flex-1 text-muted">
        Idle on {networkName(network)}: NetSleuth isn&apos;t recording anything here.
      </span>
      <Button size="sm" variant="ghost" onClick={onSetUp}>Set up this network</Button>
    </div>
  );
}

const keptIdleKey = (id: string) => `netsleuth:kept-idle:${id}`;

function readKeptIdle(id: string): boolean {
  try {
    return sessionStorage.getItem(keptIdleKey(id)) === "1";
  } catch {
    return false;
  }
}

/** Loads what the setup needs for the current (idle) network and carries out the choice. */
export function IdleNetworkSetup({ networkId }: { networkId: string }) {
  const { health, refresh, setHealth } = useLive();
  const toast = useToast();
  const [network, setNetwork] = useState<Network | null>(null);
  const [legacy, setLegacy] = useState<LegacyList | null>(null);
  const [twin, setTwin] = useState<Network | null>(null);
  const [busy, setBusy] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [keptIdle, setKeptIdle] = useState(() => readKeptIdle(networkId));

  useEffect(() => {
    let live = true;
    Promise.all([api.network(), api.legacy().catch(() => null), api.networks().catch(() => [] as Network[])])
      .then(([current, old, all]) => {
        if (!live) return;
        setNetwork(current);
        setLegacy(old);
        setTwin(current.similar_to ? all.find((n) => n.id === current.similar_to) ?? null : null);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [networkId]);

  const choose = useCallback(async (trust: Trust, label: string | null) => {
    if (trust === "idle") {
      try {
        sessionStorage.setItem(keptIdleKey(networkId), "1");
      } catch {
        // storage unavailable: the reminder just shows the full setup again next time
      }
      setKeptIdle(true);
      return;
    }
    setBusy(true);
    try {
      await api.updateNetwork(null, label ? { trust, label } : { trust });
      setHealth(await api.health());
      toast.success(trust === "home" ? "Monitoring this network as Home." : "Listening on this network.");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(false);
    }
  }, [networkId, refresh, setHealth, toast]);

  const adopt = useCallback(async (trust: "home" | "observe") => {
    setBusy(true);
    try {
      await api.adoptLegacy(trust);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't move the device list.");
      setBusy(false);
      return;
    }
    setRestarting(true);
    // NetSleuth restarts to move the list.
    const back = await waitForRestart(health?.started_at ?? null);
    if (back) {
      setHealth(back);
      toast.success("Your device list is on this network now.");
      refresh();
      return;
    }
    setRestarting(false);
    setBusy(false);
    toast.error(NOT_BACK_MESSAGE);
  }, [health?.started_at, refresh, setHealth, toast]);

  if (restarting) {
    return (
      <Card className="p-5">
        <p className="text-sm text-muted" role="status">Moving your device list here. NetSleuth is restarting…</p>
      </Card>
    );
  }
  if (!network) return null;
  if (keptIdle) return <IdleNotice network={network} onSetUp={() => setKeptIdle(false)} />;
  return <NetworkSetup network={network} legacy={legacy} twin={twin} busy={busy} onChoose={choose} onAdopt={adopt} />;
}
