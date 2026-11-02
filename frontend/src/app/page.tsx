"use client";

import { Fragment, Suspense, useCallback, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DeviceDrawer } from "@/components/DeviceDrawer";
import { DeviceRows, NewcomerList } from "@/components/DeviceList";
import { IdentifyStrip } from "@/components/IdentifyStrip";
import { Button, Card, EmptyLine, ErrorNotice, GroupHeading } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { useIdentify } from "@/hooks/useIdentify";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { groupDevices } from "@/lib/devices";
import { displayName } from "@/lib/format";
import type { Device, DevicePatch } from "@/lib/types";

export default function DevicesPage() {
  return (
    <Suspense fallback={<FirstSweep />}>
      <DevicesView />
    </Suspense>
  );
}

function DevicesView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const toast = useToast();
  const { health } = useLive();
  const identify = useIdentify();

  const openMac = params.get("device");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<Set<string>>(new Set());

  const loadDevices = useCallback((signal: AbortSignal) => api.devices({}, signal), []);
  const { data, error, reload, setData } = useResource("devices", loadDevices);
  const devices = useMemo(() => data ?? [], [data]);
  const groups = useMemo(() => groupDevices(devices, query), [devices, query]);

  const setDeviceParam = (mac: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (mac === null) next.delete("device");
    else next.set("device", mac);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const replaceDevice = useCallback((updated: Device) => {
    setData((list) => list?.map((d) => (d.mac === updated.mac ? { ...d, ...updated } : d)) ?? list);
  }, [setData]);

  const patch = async (mac: string, change: DevicePatch, success: (d: Device) => string) => {
    setBusy((s) => new Set(s).add(mac));
    try {
      const updated = await api.updateDevice(mac, change);
      replaceDevice(updated);
      toast.success(success(updated));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't update that device.");
    } finally {
      setBusy((s) => {
        const next = new Set(s);
        next.delete(mac);
        return next;
      });
    }
  };

  if (!data && !error) return <FirstSweep />;

  const online = devices.filter((d) => d.online).length;
  const unrecognised = devices.filter((d) => !d.is_known).length;
  const away = devices.length - online;
  const nothingMatches = query && !groups.unrecognised.length && !groups.here.length && !groups.away.length;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            <span className="tabular-nums">{online}</span> {online === 1 ? "device" : "devices"} on your network right now
          </h1>
          <p className="text-sm text-muted">
            {[
              unrecognised > 0 && <span className="text-warn">{unrecognised} not recognised yet</span>,
              away > 0 && `${away} away`,
              health?.interface && `watching ${health.interface}`,
            ].filter(Boolean).map((part, i) => (
              <Fragment key={i}>{i > 0 && " · "}{part}</Fragment>
            ))}
          </p>
        </div>
        {!identify.status.running && devices.length > 0 && (
          <Button
            onClick={() => identify.start()}
            disabled={identify.pending}
            title="Asks each device what it is, then switches itself off"
          >
            Identify my devices
          </Button>
        )}
      </header>

      {identify.status.running && (
        <IdentifyStrip status={identify.status} pending={identify.pending} onStop={identify.stop} />
      )}

      {error && <ErrorNotice message={error} onRetry={reload} />}

      {devices.length > 0 && (
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find a device by name, maker, IP or MAC"
          aria-label="Find a device"
          className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm placeholder:text-muted/70 sm:max-w-sm"
        />
      )}

      {devices.length === 0 && !error && (
        <Card>
          <EmptyLine>
            No devices yet. NetSleuth sweeps the network a few seconds after it starts and every few minutes after that,
            so anything switched on should appear shortly.
          </EmptyLine>
        </Card>
      )}

      {nothingMatches && <p className="text-sm text-muted">No device matches &quot;{query}&quot;.</p>}

      {groups.unrecognised.length > 0 && (
        <section>
          <div className="flex items-baseline justify-between gap-3">
            <GroupHeading count={groups.unrecognised.length} tone="text-warn">Haven&apos;t met these yet</GroupHeading>
            {!identify.status.running && groups.unrecognised.some((d) => d.online) && (
              <button
                type="button"
                disabled={identify.pending}
                onClick={() => identify.start(groups.unrecognised.filter((d) => d.online).map((d) => d.mac))}
                className="text-xs text-muted underline decoration-border underline-offset-2 hover:text-text"
              >
                Identify these
              </button>
            )}
          </div>
          <Card className="border-warn/40">
            <NewcomerList
              devices={groups.unrecognised}
              busy={busy}
              onOpen={setDeviceParam}
              onName={(mac, name) => patch(mac, { name, is_known: true }, () => `Saved as "${name}".`)}
              onApprove={(mac) => patch(mac, { is_known: true }, (d) => `${displayName(d)} is marked as yours.`)}
            />
          </Card>
          <p className="mt-2 text-xs text-muted">
            Named or approved devices move into the lists below, so the next stranger stands out.
          </p>
        </section>
      )}

      {(groups.here.length > 0 || (!query && devices.length > 0)) && (
        <section>
          <GroupHeading count={groups.here.length} tone="text-ok">Home now</GroupHeading>
          <Card>
            {groups.here.length ? (
              <DeviceRows devices={groups.here} onOpen={setDeviceParam} />
            ) : (
              <EmptyLine>None of the devices you&apos;ve recognised are online right now.</EmptyLine>
            )}
          </Card>
        </section>
      )}

      {groups.away.length > 0 && (
        <section>
          <GroupHeading count={groups.away.length}>Away</GroupHeading>
          <Card>
            <DeviceRows devices={groups.away} onOpen={setDeviceParam} />
          </Card>
        </section>
      )}

      {openMac && (
        <DeviceDrawer
          mac={openMac}
          onClose={() => setDeviceParam(null)}
          onChanged={replaceDevice}
          onForgotten={(mac) => {
            setData((list) => list?.filter((d) => d.mac !== mac) ?? list);
            setDeviceParam(null);
          }}
        />
      )}
    </div>
  );
}

function FirstSweep() {
  return (
    <p className="py-16 text-center text-sm text-muted" role="status">
      Asking NetSleuth what&apos;s on your network…
    </p>
  );
}
