"use client";

import { useId, useState } from "react";
import { Button, Card } from "@/components/ui";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import { NOT_BACK_MESSAGE, waitForRestart } from "@/lib/restart";

const CONFIRM_WORD = "reset";

/** Start-over control. Deleting every device list can't be undone, so it asks for a typed word. */
export function ResetPanel({ busy, onReset }: { busy: boolean; onReset: () => void }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const inputId = useId();
  const confirmed = typed.trim().toLowerCase() === CONFIRM_WORD;

  return (
    <Card className="space-y-3 border-danger/30 px-5 py-4">
      <div>
        <p className="font-medium">Reset NetSleuth</p>
        <p className="mt-0.5 text-sm text-muted">
          Deletes every network and its device list: names, notes, history and activity, plus the device list from
          before network profiles. Your settings and logs are kept. The network you&apos;re on starts again as new and
          idle. This can&apos;t be undone.
        </p>
      </div>
      {!open ? (
        <Button variant="danger" size="sm" onClick={() => setOpen(true)}>Reset everything…</Button>
      ) : (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (confirmed) onReset();
          }}
        >
          <div className="space-y-1">
            <label htmlFor={inputId} className="text-sm">
              Type <span className="font-mono font-semibold">{CONFIRM_WORD}</span> to confirm
            </label>
            <input
              id={inputId}
              autoFocus
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="block h-9 w-40 rounded-md border border-border bg-surface px-3 text-sm"
            />
          </div>
          <Button type="submit" variant="danger" disabled={!confirmed || busy}>
            {busy ? "Resetting…" : "Delete all device data"}
          </Button>
          <Button variant="ghost" disabled={busy} onClick={() => { setOpen(false); setTyped(""); }}>Cancel</Button>
        </form>
      )}
    </Card>
  );
}

export function ResetCard() {
  const { health, refresh, setHealth } = useLive();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  // Replay mode has no network profiles and nothing to reset.
  if (health && !health.network) return null;

  const reset = async () => {
    setBusy(true);
    try {
      await api.resetEverything();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't reset.");
      setBusy(false);
      return;
    }
    const back = await waitForRestart(health?.started_at ?? null);
    setBusy(false);
    if (!back) {
      toast.error(NOT_BACK_MESSAGE);
      return;
    }
    setHealth(back);
    refresh();
    toast.success("Everything was deleted. NetSleuth is starting fresh.");
  };

  return <ResetPanel busy={busy} onReset={reset} />;
}
