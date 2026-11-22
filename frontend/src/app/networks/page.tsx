"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, EmptyLine, ErrorNotice } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { networkName, TRUST_INFO, TRUST_ORDER } from "@/lib/networks";
import type { Network, NetworkPatch, Trust } from "@/lib/types";

export default function NetworksPage() {
  const toast = useToast();
  const { refresh, setHealth } = useLive();
  const load = useCallback(() => api.networks(), []);
  const { data, error, reload, setData } = useResource<Network[]>("networks", load);
  const [busy, setBusy] = useState<string | null>(null);
  const networks = data ?? [];
  const byId = new Map(networks.map((n) => [n.id, n]));

  const update = async (network: Network, patch: NetworkPatch, message: string) => {
    setBusy(network.id);
    try {
      const saved = await api.updateNetwork(network.id, patch);
      setData((list) => list?.map((n) => (n.id === saved.id ? saved : n)) ?? list);
      toast.success(message);
      if (saved.current) {
        setHealth(await api.health());
        refresh();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't save that.");
    } finally {
      setBusy(null);
    }
  };

  const forget = async (network: Network) => {
    setBusy(network.id);
    try {
      await api.forgetNetwork(network.id);
      setData((list) => list?.filter((n) => n.id !== network.id) ?? list);
      toast.success(`Forgot ${networkName(network)} and its device list.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't forget that network.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Networks</h1>
        <p className="text-sm text-muted">
          Each network this computer joins keeps its own device list. NetSleuth recognises a network by its router, not
          its Wi-Fi name, because names repeat and can be copied. New networks start idle.
        </p>
      </div>

      {error && <ErrorNotice message={error} onRetry={reload} />}

      {data && networks.length === 0 && (
        <Card>
          <EmptyLine>No networks yet. NetSleuth adds the one this computer is on when it starts.</EmptyLine>
        </Card>
      )}

      <ul className="space-y-3">
        {networks.map((network) => (
          <li key={network.id}>
            <NetworkCard
              network={network}
              twin={network.similar_to ? byId.get(network.similar_to) ?? null : null}
              busy={busy === network.id}
              onTrust={(trust) =>
                update(network, { trust }, `${networkName(network)} is now ${TRUST_INFO[trust].name}.`)}
              onRename={(label) =>
                update(network, { label }, label ? `Renamed to "${label}".` : "Name cleared.")}
              onForget={() => forget(network)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function NetworkCard({ network, twin, busy, onTrust, onRename, onForget }: {
  network: Network;
  twin: Network | null;
  busy: boolean;
  onTrust: (trust: Trust) => void;
  onRename: (label: string | null) => void;
  onForget: () => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <Card className={`space-y-4 p-4 ${network.current ? "border-accent/50" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          {editing ? (
            <RenameForm
              initial={network.label ?? ""}
              placeholder={network.ssid ?? network.subnet}
              onCancel={() => setEditing(false)}
              onSave={(label) => {
                setEditing(false);
                if (label !== network.label) onRename(label);
              }}
            />
          ) : (
            <h2 className="flex flex-wrap items-center gap-2 font-semibold">
              {networkName(network)}
              {network.current && (
                <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted">This network</span>
              )}
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="text-xs font-normal text-muted underline decoration-border underline-offset-2 hover:text-text"
              >
                Rename
              </button>
            </h2>
          )}
          <p className="text-xs text-muted">
            {[
              network.label && network.ssid ? `Wi-Fi ${network.ssid}` : null,
              network.subnet,
              network.gateway_ip ? `router ${network.gateway_ip}` : null,
              network.current ? "connected now" : network.last_seen ? `last here ${relativeTime(network.last_seen)}` : null,
            ].filter(Boolean).join(" · ")}
          </p>
        </div>
        <TrustPicker value={network.trust} disabled={busy} onChange={onTrust} />
      </div>

      <p className="text-sm text-muted">{TRUST_INFO[network.trust].detail}</p>

      {network.similar_to && (
        <p className="text-sm text-danger">
          Same Wi-Fi name and address range as {twin ? networkName(twin) : "another of your networks"}, but a different
          router.
        </p>
      )}

      {!network.current && <ForgetNetwork network={network} disabled={busy} onConfirm={onForget} />}
    </Card>
  );
}

function TrustPicker({ value, disabled, onChange }: { value: Trust; disabled: boolean; onChange: (t: Trust) => void }) {
  return (
    <div role="group" aria-label="What NetSleuth may do here" className="inline-flex rounded-md border border-border p-0.5">
      {TRUST_ORDER.map((level) => (
        <button
          key={level}
          type="button"
          disabled={disabled}
          aria-pressed={value === level}
          title={TRUST_INFO[level].summary}
          onClick={() => value !== level && onChange(level)}
          className={`rounded px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
            value === level ? "bg-surface-2 text-text" : "text-muted hover:text-text"
          }`}
        >
          {TRUST_INFO[level].name}
        </button>
      ))}
    </div>
  );
}

function RenameForm({ initial, placeholder, onSave, onCancel }: {
  initial: string;
  placeholder: string;
  onSave: (label: string | null) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(value.trim() || null);
      }}
    >
      <input
        autoFocus
        value={value}
        maxLength={64}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onCancel()}
        placeholder={placeholder}
        aria-label="Network name"
        className="h-8 rounded-md border border-border bg-surface px-2.5 text-sm placeholder:text-muted/70"
      />
      <Button size="sm" type="submit">Save</Button>
      <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
    </form>
  );
}

function ForgetNetwork({ network, disabled, onConfirm }: { network: Network; disabled: boolean; onConfirm: () => void }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
      <Button variant="danger" size="sm" disabled={disabled} onClick={() => (armed ? onConfirm() : setArmed(true))}>
        {armed ? "Click again to forget" : "Forget network"}
      </Button>
      <span className="text-xs text-muted">
        Deletes {networkName(network)} and its whole device list. If you join it again, it starts idle.
      </span>
    </div>
  );
}
