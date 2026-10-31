"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DeviceDrawer } from "@/components/DeviceDrawer";
import { DeviceList } from "@/components/DeviceList";
import { Button, Card, EmptyState, ErrorNotice } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { FILTERS, filterDevices, isFilter, type Filter } from "@/lib/devices";
import type { Device } from "@/lib/types";

export default function DevicesPage() {
  return (
    <Suspense fallback={<ListSkeleton />}>
      <DevicesView />
    </Suspense>
  );
}

function DevicesView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const toast = useToast();
  const { summary } = useLive();

  const openMac = params.get("device");
  const filterParam = params.get("filter");
  const filter: Filter = isFilter(filterParam) ? filterParam : "all";
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<Set<string>>(new Set());

  const loadDevices = useCallback((signal: AbortSignal) => api.devices({}, signal), []);
  const { data, error, loading, reload, setData } = useResource("devices", loadDevices);
  const devices = useMemo(() => data ?? [], [data]);

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (value === null) next.delete(key);
    else next.set(key, value);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const replaceDevice = useCallback((updated: Device) => {
    setData((list) => list?.map((d) => (d.mac === updated.mac ? { ...d, ...updated } : d)) ?? list);
  }, [setData]);

  const approve = async (mac: string) => {
    setBusy((s) => new Set(s).add(mac));
    try {
      replaceDevice(await api.updateDevice(mac, { is_known: true }));
      toast.success("Marked as known.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't update device.");
    } finally {
      setBusy((s) => {
        const next = new Set(s);
        next.delete(mac);
        return next;
      });
    }
  };

  const visible = useMemo(() => filterDevices(devices, filter, query), [devices, filter, query]);
  const counts = {
    online: summary?.online ?? devices.filter((d) => d.online).length,
    review: devices.filter((d) => !d.is_known).length,
    total: summary?.total ?? devices.length,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
          <p className="mt-1 text-sm text-muted">
            {loading && !data ? "Looking for devices…" : `${counts.online} online now · ${counts.total} seen in total`}
          </p>
        </div>
      </div>

      {counts.review > 0 && filter !== "review" && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3">
          <span className="grid size-8 place-items-center rounded-full bg-warn/20 text-sm font-semibold text-warn">
            {counts.review}
          </span>
          <p className="flex-1 text-sm">
            <span className="font-medium">
              {counts.review === 1 ? "1 device needs" : `${counts.review} devices need`} a look.
            </span>{" "}
            <span className="text-muted">Mark the ones you recognise so new arrivals stand out.</span>
          </p>
          <Button size="sm" onClick={() => setParam("filter", "review")}>Review</Button>
        </div>
      )}

      {error && <ErrorNotice message={error} onRetry={reload} />}

      <Card>
        <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-center">
          <div role="tablist" aria-label="Filter devices" className="flex gap-1 overflow-x-auto">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                onClick={() => setParam("filter", f.id === "all" ? null : f.id)}
                className={`shrink-0 rounded-md px-3 py-1.5 text-sm font-medium ${
                  filter === f.id ? "bg-surface-2 text-text" : "text-muted hover:text-text"
                }`}
              >
                {f.label}
                {f.id === "review" && counts.review > 0 && <span className="ml-1.5 text-warn">{counts.review}</span>}
              </button>
            ))}
          </div>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, maker, IP or MAC"
            aria-label="Search devices"
            className="h-9 w-full rounded-md border border-border bg-bg px-3 text-sm placeholder:text-muted/70 sm:ml-auto sm:w-72"
          />
        </div>

        {loading && !data ? (
          <ListSkeleton bare />
        ) : visible.length ? (
          <DeviceList devices={visible} busy={busy} onOpen={(mac) => setParam("device", mac)} onApprove={approve} />
        ) : (
          <EmptyState title={emptyTitle(filter, query, devices.length)}>
            {devices.length === 0 && "NetSleuth sweeps your network every few minutes. Devices appear here as they're found."}
          </EmptyState>
        )}
      </Card>

      {openMac && (
        <DeviceDrawer
          mac={openMac}
          onClose={() => setParam("device", null)}
          onChanged={replaceDevice}
          onForgotten={(mac) => {
            setData((list) => list?.filter((d) => d.mac !== mac) ?? list);
            setParam("device", null);
          }}
        />
      )}
    </div>
  );
}

function emptyTitle(filter: Filter, query: string, total: number): string {
  if (total === 0) return "No devices yet";
  if (query) return `Nothing matches “${query}”`;
  if (filter === "review") return "All caught up — every device is reviewed";
  if (filter === "online") return "Nothing is online right now";
  return "No offline devices";
}

function ListSkeleton({ bare = false }: { bare?: boolean }) {
  const rows = (
    <div className="divide-y divide-border" aria-hidden="true">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <div className="size-10 animate-pulse rounded-lg bg-surface-2" />
          <div className="flex-1 space-y-2">
            <div className="h-3.5 w-40 animate-pulse rounded bg-surface-2" />
            <div className="h-3 w-24 animate-pulse rounded bg-surface-2" />
          </div>
        </div>
      ))}
    </div>
  );
  return bare ? rows : <Card>{rows}</Card>;
}
