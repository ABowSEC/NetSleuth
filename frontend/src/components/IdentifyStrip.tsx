import { Button } from "./ui";
import { useNow } from "@/hooks/useNow";
import type { IdentifyStatus } from "@/lib/types";

function minutesBetween(from: string | null, to: string | null, fallback = 0): number {
  const a = from ? Date.parse(from) : NaN;
  const b = to ? Date.parse(to) : NaN;
  return Number.isFinite(a) && Number.isFinite(b) ? Math.max(0, Math.round((b - a) / 60_000)) : fallback;
}

/** Progress of a running Identify pass, with the promise that it ends by itself. */
export function IdentifyStrip({ status, onStop, pending, now }: {
  status: IdentifyStatus;
  onStop: () => void;
  pending: boolean;
  now?: number;
}) {
  const clock = useNow();
  const left = minutesBetween(new Date(now ?? clock).toISOString(), status.ends_at);
  const limit = minutesBetween(status.started_at, status.ends_at, 10);
  const pct = status.total ? Math.round((status.done / status.total) * 100) : 0;

  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3" role="status" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <span className="font-medium">Identifying devices…</span>
        <span className="text-muted tabular-nums">
          {status.done} of {status.total}
          {" · "}
          {left <= 1 ? "under a minute left" : `${left} min left`}
        </span>
        {status.current && <span className="truncate font-mono text-xs text-muted">{status.current}</span>}
        <Button size="sm" className="ml-auto" onClick={onStop} disabled={pending}>Stop</Button>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        <div className="h-full bg-text transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted">
        Switches itself off when every device has been checked, or after {limit} minutes.
        {status.port_check ? " Includes the port check." : ""}
      </p>
    </div>
  );
}
